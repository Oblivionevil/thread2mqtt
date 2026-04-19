"""Matter cluster and device type mapping."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class ClusterId(IntEnum):
    """Subset of commonly used Matter cluster IDs."""

    DESCRIPTOR = 0x001D  # 29
    BASIC_INFORMATION = 0x0028  # 40
    ON_OFF = 0x0006  # 6
    LEVEL_CONTROL = 0x0008  # 8
    COLOR_CONTROL = 0x0300  # 768
    BOOLEAN_STATE = 0x0045  # 69
    DOOR_LOCK = 0x0101  # 257
    THERMOSTAT = 0x0201  # 513
    TEMPERATURE_MEASUREMENT = 0x0402  # 1026
    PRESSURE_MEASUREMENT = 0x0403  # 1027
    HUMIDITY_MEASUREMENT = 0x0405  # 1029
    OCCUPANCY_SENSING = 0x0406  # 1030
    ILLUMINANCE_MEASUREMENT = 0x0400  # 1024


class DeviceTypeId(IntEnum):
    """Commonly used Matter device type IDs."""

    ON_OFF_LIGHT = 0x0100  # 256
    DIMMABLE_LIGHT = 0x0101  # 257
    COLOR_TEMP_LIGHT = 0x010C  # 268
    EXTENDED_COLOR_LIGHT = 0x010D  # 269
    ON_OFF_PLUG = 0x010A  # 266
    DIMMABLE_PLUG = 0x010B  # 267
    DOOR_LOCK = 0x000A  # 10
    THERMOSTAT = 0x0301  # 769
    TEMPERATURE_SENSOR = 0x0302  # 770
    HUMIDITY_SENSOR = 0x0307  # 775
    OCCUPANCY_SENSOR = 0x0107  # 263
    CONTACT_SENSOR = 0x0015  # 21
    LIGHT_SENSOR = 0x0106  # 262
    PRESSURE_SENSOR = 0x0305  # 773


@dataclass(frozen=True)
class EntityMapping:
    """Maps a Matter cluster attribute to an HA entity property."""

    ha_platform: str  # light, switch, binary_sensor, sensor, lock, climate
    attribute_key: str  # key in the state JSON
    cluster_id: int
    attribute_id: int
    device_class: str | None = None
    unit: str | None = None
    transform: str | None = None  # "divide_100", "divide_10", "invert"


# Maps device type → entity mappings
DEVICE_TYPE_ENTITIES: dict[int, list[EntityMapping]] = {
    DeviceTypeId.ON_OFF_LIGHT: [
        EntityMapping("light", "state", ClusterId.ON_OFF, 0),
    ],
    DeviceTypeId.DIMMABLE_LIGHT: [
        EntityMapping("light", "state", ClusterId.ON_OFF, 0),
        EntityMapping("light", "brightness", ClusterId.LEVEL_CONTROL, 0),
    ],
    DeviceTypeId.COLOR_TEMP_LIGHT: [
        EntityMapping("light", "state", ClusterId.ON_OFF, 0),
        EntityMapping("light", "brightness", ClusterId.LEVEL_CONTROL, 0),
        EntityMapping("light", "color_temp", ClusterId.COLOR_CONTROL, 7),
    ],
    DeviceTypeId.EXTENDED_COLOR_LIGHT: [
        EntityMapping("light", "state", ClusterId.ON_OFF, 0),
        EntityMapping("light", "brightness", ClusterId.LEVEL_CONTROL, 0),
        EntityMapping("light", "color_temp", ClusterId.COLOR_CONTROL, 7),
        EntityMapping("light", "hue", ClusterId.COLOR_CONTROL, 0),
        EntityMapping("light", "saturation", ClusterId.COLOR_CONTROL, 1),
    ],
    DeviceTypeId.ON_OFF_PLUG: [
        EntityMapping("switch", "state", ClusterId.ON_OFF, 0),
    ],
    DeviceTypeId.DIMMABLE_PLUG: [
        EntityMapping("switch", "state", ClusterId.ON_OFF, 0),
        EntityMapping("switch", "brightness", ClusterId.LEVEL_CONTROL, 0),
    ],
    DeviceTypeId.CONTACT_SENSOR: [
        EntityMapping(
            "binary_sensor", "contact", ClusterId.BOOLEAN_STATE, 0,
            device_class="door", transform="invert",
        ),
    ],
    DeviceTypeId.OCCUPANCY_SENSOR: [
        EntityMapping(
            "binary_sensor", "occupancy", ClusterId.OCCUPANCY_SENSING, 0,
            device_class="occupancy",
        ),
    ],
    DeviceTypeId.TEMPERATURE_SENSOR: [
        EntityMapping(
            "sensor", "temperature", ClusterId.TEMPERATURE_MEASUREMENT, 0,
            device_class="temperature", unit="°C", transform="divide_100",
        ),
    ],
    DeviceTypeId.HUMIDITY_SENSOR: [
        EntityMapping(
            "sensor", "humidity", ClusterId.HUMIDITY_MEASUREMENT, 0,
            device_class="humidity", unit="%", transform="divide_100",
        ),
    ],
    DeviceTypeId.PRESSURE_SENSOR: [
        EntityMapping(
            "sensor", "pressure", ClusterId.PRESSURE_MEASUREMENT, 0,
            device_class="pressure", unit="hPa", transform="divide_10",
        ),
    ],
    DeviceTypeId.DOOR_LOCK: [
        EntityMapping("lock", "state", ClusterId.DOOR_LOCK, 0),
    ],
    DeviceTypeId.THERMOSTAT: [
        EntityMapping(
            "climate", "current_temperature", ClusterId.THERMOSTAT, 0,
            transform="divide_100",
        ),
        EntityMapping(
            "climate", "heating_setpoint", ClusterId.THERMOSTAT, 6,
            transform="divide_100",
        ),
        EntityMapping(
            "climate", "cooling_setpoint", ClusterId.THERMOSTAT, 5,
            transform="divide_100",
        ),
        EntityMapping("climate", "system_mode", ClusterId.THERMOSTAT, 28),
    ],
    DeviceTypeId.LIGHT_SENSOR: [
        EntityMapping(
            "sensor", "illuminance", ClusterId.ILLUMINANCE_MEASUREMENT, 0,
            device_class="illuminance", unit="lx",
        ),
    ],
}


def apply_transform(value: Any, transform: str | None) -> Any:
    """Apply a value transformation."""
    if value is None or transform is None:
        return value
    if transform == "divide_100" and isinstance(value, (int, float)):
        return round(value / 100, 2)
    if transform == "divide_10" and isinstance(value, (int, float)):
        return round(value / 10, 1)
    if transform == "invert" and isinstance(value, bool):
        return not value
    return value
