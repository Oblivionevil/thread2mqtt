"""HTTP client helpers for an external OpenThread Border Router."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any

import requests

from .config import OtbrConfig


TLVS_RE = re.compile(r"[^0-9a-fA-F]")


class OtbrError(RuntimeError):
    """Raised when OTBR data cannot be loaded."""


@dataclass(frozen=True)
class DatasetMetadata:
    source: str
    length: int
    sha256: str


def normalize_dataset_tlvs(raw_tlvs: str) -> str:
    """Normalize a Thread dataset TLV string into lowercase hex."""
    normalized = TLVS_RE.sub("", raw_tlvs or "").lower()
    if not normalized:
        raise OtbrError("Thread dataset TLVs are empty")
    if len(normalized) % 2 != 0:
        raise OtbrError("Thread dataset TLVs must contain an even number of hex digits")
    return normalized


class OtbrClient:
    """Client for reading dataset metadata from an external OTBR instance."""

    def __init__(self, config: OtbrConfig, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or requests.Session()

    def load_dataset(self) -> tuple[str, DatasetMetadata]:
        """Load the active Thread dataset from OTBR or manual fallback."""
        if self._config.dataset_source == "manual":
            return self._load_manual_dataset()

        try:
            return self._load_otbr_dataset()
        except Exception as err:
            if self._config.dataset_tlvs:
                dataset, metadata = self._load_manual_dataset()
                return dataset, DatasetMetadata(
                    source="manual-fallback",
                    length=metadata.length,
                    sha256=metadata.sha256,
                )
            raise OtbrError(f"Failed to load Thread dataset from OTBR: {err}") from err

    def build_snapshot(self) -> dict[str, Any]:
        """Build a safe diagnostics snapshot for MQTT publishing."""
        snapshot: dict[str, Any] = {
            "otbr_url": self._config.url,
            "configured_dataset_source": self._config.dataset_source,
            "timeout_seconds": self._config.timeout_seconds,
            "otbr_reachable": False,
            "dataset_loaded": False,
        }

        try:
            _, metadata = self.load_dataset()
        except Exception as err:
            snapshot["last_error"] = str(err)
            snapshot["dataset_source"] = "unavailable"
            return snapshot

        snapshot.update(
            {
                "otbr_reachable": metadata.source == "otbr",
                "dataset_loaded": True,
                "dataset_source": metadata.source,
                "dataset_length": metadata.length,
                "dataset_sha256": metadata.sha256,
            }
        )
        return snapshot

    def _load_manual_dataset(self) -> tuple[str, DatasetMetadata]:
        if not self._config.dataset_tlvs:
            raise OtbrError("Manual dataset source selected but dataset_tlvs is empty")
        dataset = normalize_dataset_tlvs(self._config.dataset_tlvs)
        return dataset, self._metadata_for(dataset, "manual")

    def _load_otbr_dataset(self) -> tuple[str, DatasetMetadata]:
        response = self._session.get(
            f"{self._config.url}/node/dataset/active",
            headers={"Accept": "text/plain"},
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        dataset = normalize_dataset_tlvs(response.text)
        return dataset, self._metadata_for(dataset, "otbr")

    @staticmethod
    def _metadata_for(dataset_tlvs: str, source: str) -> DatasetMetadata:
        return DatasetMetadata(
            source=source,
            length=len(dataset_tlvs) // 2,
            sha256=hashlib.sha256(dataset_tlvs.encode("ascii")).hexdigest(),
        )