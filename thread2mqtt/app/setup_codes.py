"""Helpers for Matter onboarding payloads."""

from __future__ import annotations

import re


class MatterSetupCodeError(ValueError):
    """Raised when a Matter setup code cannot be parsed."""


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)

_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def parse_manual_setup_pin_code(code: str) -> int:
    """Extract the setup PIN code from a Matter manual pairing code."""
    normalized = _normalize_manual_pairing_code(code)
    if len(normalized) not in (11, 21):
        raise MatterSetupCodeError(
            "Manual pairing codes must be 11 or 21 digits long, including the check digit."
        )

    if int(normalized[0]) > 7:
        raise MatterSetupCodeError("Unsupported Matter manual pairing code version.")

    if not _is_valid_verhoeff(normalized):
        raise MatterSetupCodeError("Invalid Matter manual pairing code check digit.")

    representation = normalized[:-1]
    chunk1 = int(representation[0:1])
    is_long_code = bool((chunk1 >> 2) & 1)
    expected_length = 20 if is_long_code else 10
    if len(representation) != expected_length:
        raise MatterSetupCodeError("Manual pairing code length does not match its encoded format.")

    chunk2 = int(representation[1:6])
    chunk3 = int(representation[6:10])
    setup_pin_code = (chunk2 & ((1 << 14) - 1)) | ((chunk3 & ((1 << 13) - 1)) << 14)
    if setup_pin_code == 0:
        raise MatterSetupCodeError("Matter setup PIN code decoded to 0, which is invalid.")

    return setup_pin_code


def _normalize_manual_pairing_code(code: str) -> str:
    stripped = code.strip()
    if not stripped:
        raise MatterSetupCodeError("Missing Matter pairing code.")
    if stripped.upper().startswith("MT:"):
        raise MatterSetupCodeError(
            "IP-directed commissioning needs a manual pairing code or explicit setup_pin_code."
        )

    normalized = re.sub(r"[\s-]+", "", stripped)
    if not normalized.isdigit():
        raise MatterSetupCodeError(
            "Manual pairing codes may only contain digits, spaces, or '-' separators."
        )
    return normalized


def _is_valid_verhoeff(value: str) -> bool:
    checksum = 0
    for index, char in enumerate(reversed(value)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[index % 8][int(char)]]
    return checksum == 0