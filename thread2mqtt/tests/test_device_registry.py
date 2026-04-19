"""Unit tests for device registry state mapping."""

from app.device_registry import Device
from app.web_ui import Thread2MqttWebUi


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


def test_commands_are_exposed_from_capabilities_not_current_state() -> None:
    device = Device(
        7,
        {
            "attributes": {
                "0/40/1": "Example",
                "0/40/3": "Dimmable Light",
                "1/29/0": [{"deviceType": 257, "revision": 1}],
            }
        },
    )

    serialized = Thread2MqttWebUi._serialize_device(device)

    assert serialized["state"] == {}
    assert serialized["controls"] == {
        "state": True,
        "brightness": True,
        "color_temp": False,
    }


def test_command_endpoints_ignore_sensor_only_endpoints() -> None:
    device = Device(
        9,
        {
            "attributes": {
                "0/40/1": "Example",
                "0/40/3": "Combo Device",
                "1/29/0": [{"deviceType": 263, "revision": 1}],
                "1/1030/0": 1,
                "2/29/0": [{"deviceType": 257, "revision": 1}],
                "2/6/0": True,
                "2/8/0": 128,
            }
        },
    )

    assert device.get_endpoint_for_command("state") == 2
    assert device.get_endpoint_for_command("brightness") == 2
    assert device.get_endpoint_for_command("color_temp") is None