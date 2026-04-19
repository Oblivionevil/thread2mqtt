"""Unit tests for OTBR helpers."""

from app.otbr_client import OtbrError, normalize_dataset_tlvs


def test_normalize_dataset_tlvs_strips_whitespace_and_case() -> None:
    assert normalize_dataset_tlvs("AA bb\ncc") == "aabbcc"


def test_normalize_dataset_tlvs_rejects_odd_length() -> None:
    try:
        normalize_dataset_tlvs("abc")
    except OtbrError as err:
        assert "even number" in str(err)
    else:
        raise AssertionError("Expected odd-length TLVs to raise OtbrError")