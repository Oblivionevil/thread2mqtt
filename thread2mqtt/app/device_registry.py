"""Device registry – tracks Matter nodes and maps them to MQTT devices."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from .clusters import (
    ClusterId,
    DEVICE_TYPE_ENTITIES,
    EntityMapping,
    apply_transform,
)

LOGGER = logging.getLogger(__name__)

# Basic‑Information attribute paths (endpoint 0)
_BI = str(ClusterId.BASIC_INFORMATION)
ATTR_VENDOR_NAME = f"0/{_BI}/1"
ATTR_VENDOR_ID = f"0/{_BI}/2"
ATTR_PRODUCT_NAME = f"0/{_BI}/3"
ATTR_PRODUCT_ID = f"0/{_BI}/4"
ATTR_NODE_LABEL = f"0/{_BI}/5"
ATTR_SERIAL_NUMBER = f"0/{_BI}/15"
ATTR_UNIQUE_ID = f"0/{_BI}/17"


class EndpointInfo:
    """Description of a single non-root endpoint."""

    __slots__ = ("endpoint_id", "device_type_ids", "entity_mappings")

    def __init__(
        self,
        endpoint_id: int,
        device_type_ids: list[int],
        entity_mappings: list[EntityMapping],
    ) -> None:
        self.endpoint_id = endpoint_id
        self.device_type_ids = device_type_ids
        self.entity_mappings = entity_mappings


class Device:
    """One Matter node mapped to an MQTT-publishable device."""

    def __init__(self, node_id: int, node_data: dict[str, Any]) -> None:
        self.node_id = node_id
        self._raw = node_data
        self.friendly_name: str = ""
        self.endpoints: dict[int, EndpointInfo] = {}
        self._refresh()

    # -- convenience properties -----------------------------------------

    @property
    def available(self) -> bool:
        return bool(self._raw.get("available", False))

    @property
    def vendor_name(self) -> str:
        return str(self._attr(ATTR_VENDOR_NAME, "Unknown"))

    @property
    def product_name(self) -> str:
        return str(self._attr(ATTR_PRODUCT_NAME, "Unknown"))

    @property
    def vendor_id(self) -> int | None:
        v = self._attr(ATTR_VENDOR_ID)
        return int(v) if v is not None else None

    @property
    def product_id(self) -> int | None:
        v = self._attr(ATTR_PRODUCT_ID)
        return int(v) if v is not None else None

    @property
    def node_label(self) -> str:
        return str(self._attr(ATTR_NODE_LABEL, ""))

    @property
    def serial_number(self) -> str | None:
        v = self._attr(ATTR_SERIAL_NUMBER)
        return str(v) if v is not None else None

    @property
    def unique_id(self) -> str:
        uid = self._attr(ATTR_UNIQUE_ID)
        if uid:
            return str(uid)
        sn = self.serial_number
        if sn:
            return sn
        return f"matter_{self.node_id}"

    # -- state payload --------------------------------------------------

    def get_state_payload(self) -> dict[str, Any]:
        """Build the JSON state for MQTT publishing."""
        state: dict[str, Any] = {}
        for ep_id, ep_info in self.endpoints.items():
            for mapping in ep_info.entity_mappings:
                attr_path = f"{ep_id}/{mapping.cluster_id}/{mapping.attribute_id}"
                raw = self._attr(attr_path)
                value = apply_transform(raw, mapping.transform)
                if mapping.attribute_key == "state" and isinstance(raw, bool):
                    value = "ON" if raw else "OFF"
                if value is not None:
                    state[mapping.attribute_key] = value
        return state

    # -- update ---------------------------------------------------------

    def update(self, node_data: dict[str, Any]) -> None:
        self._raw = node_data
        self._refresh()

    # -- internals ------------------------------------------------------

    def _refresh(self) -> None:
        attrs = self._raw.get("attributes", {})
        self.endpoints.clear()

        ep_ids: set[int] = set()
        for path in attrs:
            try:
                ep_ids.add(int(path.split("/")[0]))
            except (ValueError, IndexError):
                pass

        for ep_id in sorted(ep_ids):
            if ep_id == 0:
                continue  # root endpoint – metadata only
            dt_raw = attrs.get(f"{ep_id}/{ClusterId.DESCRIPTOR}/0", [])
            dt_ids: list[int] = []
            if isinstance(dt_raw, list):
                for item in dt_raw:
                    if isinstance(item, dict):
                        dt_ids.append(item.get("deviceType", item.get("type", 0)))
                    elif isinstance(item, int):
                        dt_ids.append(item)

            mappings: list[EntityMapping] = []
            for dt_id in dt_ids:
                mappings.extend(DEVICE_TYPE_ENTITIES.get(dt_id, []))

            if mappings:
                self.endpoints[ep_id] = EndpointInfo(ep_id, dt_ids, mappings)

        # derive friendly name
        if not self.friendly_name:
            label = self.node_label
            if label:
                self.friendly_name = label
            else:
                name = self.product_name
                self.friendly_name = (
                    f"{name}_{self.node_id}" if name and name != "Unknown" else f"matter_{self.node_id}"
                )

    def _attr(self, path: str, default: Any = None) -> Any:
        return self._raw.get("attributes", {}).get(path, default)


class DeviceRegistry:
    """Thread-safe registry of all known Matter devices."""

    def __init__(self, storage_path: str = "/data/devices.json") -> None:
        self._devices: dict[int, Device] = {}
        self._lock = Lock()
        self._storage_path = Path(storage_path)
        self._custom_names: dict[str, str] = {}
        self._load_custom_names()

    @property
    def devices(self) -> dict[int, Device]:
        with self._lock:
            return dict(self._devices)

    def get_device(self, node_id: int) -> Device | None:
        with self._lock:
            return self._devices.get(node_id)

    def get_device_by_name(self, friendly_name: str) -> Device | None:
        with self._lock:
            for d in self._devices.values():
                if d.friendly_name == friendly_name:
                    return d
        return None

    def add_or_update(self, node_id: int, node_data: dict[str, Any]) -> Device:
        with self._lock:
            dev = self._devices.get(node_id)
            if dev:
                dev.update(node_data)
            else:
                dev = Device(node_id, node_data)
                self._devices[node_id] = dev
                LOGGER.info("New device: node_id=%d name=%s", node_id, dev.friendly_name)
            custom = self._custom_names.get(str(node_id))
            if custom:
                dev.friendly_name = custom
            return dev

    def remove(self, node_id: int) -> Device | None:
        with self._lock:
            return self._devices.pop(node_id, None)

    def rename_device(self, node_id: int, new_name: str) -> bool:
        with self._lock:
            dev = self._devices.get(node_id)
            if not dev:
                return False
            dev.friendly_name = new_name
            self._custom_names[str(node_id)] = new_name
        self._save_custom_names()
        return True

    # -- persistence ----------------------------------------------------

    def _load_custom_names(self) -> None:
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text("utf-8"))
                self._custom_names = data.get("custom_names", {})
            except Exception:
                LOGGER.warning("Failed to load device names from %s", self._storage_path)

    def _save_custom_names(self) -> None:
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._storage_path.write_text(
                json.dumps({"custom_names": self._custom_names}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            LOGGER.warning("Failed to persist device names to %s", self._storage_path)
