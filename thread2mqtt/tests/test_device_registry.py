"""Unit tests for device registry state mapping."""

from app.device_registry import Device


def test_device_type_struct_accepts_snake_case_keys() -> None:
    device = Device(
        1,
        {
            "attributes": {
                "0/40/1": "Aqara",
                "0/40/3": "Motion and Light Sensor P2",
                "1/29/0": [{"device_type": 263, "revision": 1}],
                "1/1030/0": 1,
            }
        },
    )

    assert 1 in device.endpoints
    assert device.get_state_payload() == {"occupancy": True}


def test_cluster_fallback_adds_secondary_sensor_capabilities() -> None:
    device = Device(
        1,
        {
            "attributes": {
                "0/40/1": "Aqara",
                "0/40/3": "Motion and Light Sensor P2",
                "1/29/0": [{"deviceType": 263, "revision": 1}],
                "1/1030/0": 0,
                "1/1024/0": 10001,
            }
        },
    )

    assert device.get_state_payload() == {"occupancy": False, "illuminance": 10.0}


def test_cluster_fallback_works_without_descriptor_device_type_list() -> None:
    device = Device(
        1,
        {
            "attributes": {
                "0/40/1": "Aqara",
                "0/40/3": "Motion and Light Sensor P2",
                "1/1030/0": 1,
                "1/1024/0": 1,
            }
        },
    )

    assert 1 in device.endpoints
    assert device.get_state_payload() == {"occupancy": True, "illuminance": 1.0}