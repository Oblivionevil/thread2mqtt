"""Home Assistant MQTT Discovery payloads for Matter devices."""

from __future__ import annotations

from typing import Any

from .clusters import EntityMapping
from .device_registry import Device


def build_device_discovery(
    device: Device,
    base_topic: str,
    discovery_prefix: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Return a list of ``(discovery_topic, payload)`` tuples for *device*."""
    results: list[tuple[str, dict[str, Any]]] = []
    dev_info: dict[str, Any] = {
        "ids": [f"thread2mqtt_{device.unique_id}"],
        "name": device.friendly_name,
        "mf": device.vendor_name,
        "mdl": device.product_name,
        "via_device": "thread2mqtt_bridge",
    }
    if device.serial_number:
        dev_info["serial_number"] = device.serial_number

    seen: set[tuple[str, str]] = set()
    for ep_id, ep_info in device.endpoints.items():
        for mapping in ep_info.entity_mappings:
            key = (mapping.ha_platform, mapping.attribute_key)
            if key in seen:
                continue
            seen.add(key)

            entity_id = _entity_id(device, mapping)
            topic = f"{discovery_prefix}/{mapping.ha_platform}/{entity_id}/config"
            payload = _build_entity_payload(
                device, ep_id, mapping, entity_id, base_topic, dev_info,
            )
            results.append((topic, payload))
    return results


def build_device_removal(device: Device, discovery_prefix: str) -> list[str]:
    """Return discovery topics to clear for device removal."""
    topics: list[str] = []
    seen: set[tuple[str, str]] = set()
    for _ep_id, ep_info in device.endpoints.items():
        for mapping in ep_info.entity_mappings:
            key = (mapping.ha_platform, mapping.attribute_key)
            if key in seen:
                continue
            seen.add(key)
            topics.append(
                f"{discovery_prefix}/{mapping.ha_platform}/{_entity_id(device, mapping)}/config"
            )
    return topics


# ── helpers ──────────────────────────────────────────────────────────

def _entity_id(device: Device, mapping: EntityMapping) -> str:
    base = f"thread2mqtt_{device.node_id}"
    if mapping.ha_platform in ("light", "switch", "lock", "climate"):
        return base
    return f"{base}_{mapping.attribute_key}"


def _build_entity_payload(
    device: Device,
    endpoint_id: int,
    mapping: EntityMapping,
    entity_id: str,
    base_topic: str,
    dev_info: dict[str, Any],
) -> dict[str, Any]:
    friendly = device.friendly_name
    state_topic = f"{base_topic}/{friendly}"
    payload: dict[str, Any] = {
        "name": _entity_name(mapping),
        "unique_id": entity_id,
        "dev": dev_info,
        "stat_t": state_topic,
        "avty_t": f"{base_topic}/{friendly}/availability",
        "pl_avail": "online",
        "pl_not_avail": "offline",
        "o": {"name": "thread2mqtt"},
    }

    p = mapping.ha_platform

    if p == "light":
        payload["cmd_t"] = f"{base_topic}/{friendly}/set"
        payload["schema"] = "json"
        payload["brightness"] = any(
            m.attribute_key == "brightness"
            for ep in device.endpoints.values()
            for m in ep.entity_mappings
        )
        payload["color_temp"] = any(
            m.attribute_key == "color_temp"
            for ep in device.endpoints.values()
            for m in ep.entity_mappings
        )

    elif p == "switch":
        payload["cmd_t"] = f"{base_topic}/{friendly}/set"
        payload["val_tpl"] = "{{ value_json.state }}"
        payload["pl_on"] = "ON"
        payload["pl_off"] = "OFF"
        payload["stat_on"] = "ON"
        payload["stat_off"] = "OFF"

    elif p == "lock":
        payload["cmd_t"] = f"{base_topic}/{friendly}/set"
        payload["val_tpl"] = "{{ value_json.state }}"
        payload["pl_lock"] = "LOCK"
        payload["pl_unlk"] = "UNLOCK"
        payload["state_locked"] = "LOCKED"
        payload["state_unlocked"] = "UNLOCKED"

    elif p == "binary_sensor":
        payload["val_tpl"] = f"{{{{ value_json.{mapping.attribute_key} }}}}"
        payload["pl_on"] = "True"
        payload["pl_off"] = "False"
        if mapping.device_class:
            payload["dev_cla"] = mapping.device_class

    elif p == "sensor":
        payload["val_tpl"] = f"{{{{ value_json.{mapping.attribute_key} }}}}"
        if mapping.device_class:
            payload["dev_cla"] = mapping.device_class
        if mapping.unit:
            payload["unit_of_meas"] = mapping.unit

    elif p == "climate":
        payload["cmd_t"] = f"{base_topic}/{friendly}/set"
        payload["temp_stat_t"] = state_topic
        payload["curr_temp_t"] = state_topic
        payload["curr_temp_tpl"] = "{{ value_json.current_temperature }}"

    return payload


def _entity_name(mapping: EntityMapping) -> str:
    names: dict[str, str | None] = {
        "state": None,
        "brightness": "Brightness",
        "color_temp": "Color Temperature",
        "temperature": "Temperature",
        "humidity": "Humidity",
        "pressure": "Pressure",
        "illuminance": "Illuminance",
        "contact": "Contact",
        "occupancy": "Occupancy",
        "current_temperature": "Temperature",
        "heating_setpoint": "Heating Setpoint",
        "cooling_setpoint": "Cooling Setpoint",
        "system_mode": "Mode",
    }
    result = names.get(mapping.attribute_key)
    if result is None:
        return mapping.attribute_key.replace("_", " ").title()
    return result
