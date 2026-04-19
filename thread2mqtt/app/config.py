"""Configuration loading for Thread2MQTT."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_OPTIONS_PATH = "/data/options.json"


@dataclass(frozen=True)
class MqttConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    client_id: str
    discovery_prefix: str
    base_topic: str
    tls: bool


@dataclass(frozen=True)
class OtbrConfig:
    url: str
    dataset_source: str
    dataset_tlvs: str | None
    timeout_seconds: int


@dataclass(frozen=True)
class BridgeConfig:
    publish_retained: bool
    birth_topic: str


@dataclass(frozen=True)
class MatterConfig:
    enabled: bool
    server_url: str
    storage_path: str


@dataclass(frozen=True)
class AppConfig:
    log_level: str
    mqtt: MqttConfig
    otbr: OtbrConfig
    bridge: BridgeConfig
    matter: MatterConfig


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_mapping(raw: Any, key: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Configuration key '{key}' must be an object")
    return raw


def load_config(options_path: str | None = None) -> AppConfig:
    """Load add-on configuration from Home Assistant options.json."""
    resolved_path = Path(options_path or os.environ.get("THREAD2MQTT_OPTIONS_PATH", DEFAULT_OPTIONS_PATH))
    with resolved_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    mqtt_raw = _require_mapping(raw.get("mqtt", {}), "mqtt")
    otbr_raw = _require_mapping(raw.get("otbr", {}), "otbr")
    bridge_raw = _require_mapping(raw.get("bridge", {}), "bridge")

    mqtt = MqttConfig(
        host=str(mqtt_raw.get("host", "core-mosquitto")).strip(),
        port=int(mqtt_raw.get("port", 1883)),
        username=_optional_string(mqtt_raw.get("username")),
        password=_optional_string(mqtt_raw.get("password")),
        client_id=str(mqtt_raw.get("client_id", "thread2mqtt")).strip(),
        discovery_prefix=str(mqtt_raw.get("discovery_prefix", "homeassistant")).strip(),
        base_topic=str(mqtt_raw.get("base_topic", "thread2mqtt")).strip().rstrip("/"),
        tls=bool(mqtt_raw.get("tls", False)),
    )

    if not mqtt.host:
        raise ValueError("MQTT host must not be empty")
    if not mqtt.client_id:
        raise ValueError("MQTT client_id must not be empty")
    if not mqtt.base_topic:
        raise ValueError("MQTT base_topic must not be empty")

    otbr = OtbrConfig(
        url=str(otbr_raw.get("url", "")).strip().rstrip("/"),
        dataset_source=str(otbr_raw.get("dataset_source", "otbr")).strip(),
        dataset_tlvs=_optional_string(otbr_raw.get("dataset_tlvs")),
        timeout_seconds=int(otbr_raw.get("timeout_seconds", 10)),
    )

    if not otbr.url:
        raise ValueError("OTBR url must not be empty")
    if otbr.dataset_source not in {"otbr", "manual"}:
        raise ValueError("OTBR dataset_source must be either 'otbr' or 'manual'")

    bridge = BridgeConfig(
        publish_retained=bool(bridge_raw.get("publish_retained", True)),
        birth_topic=str(bridge_raw.get("birth_topic", "homeassistant/status")).strip(),
    )

    if not bridge.birth_topic:
        raise ValueError("Bridge birth_topic must not be empty")

    matter_raw = _require_mapping(raw.get("matter", {}), "matter")
    matter = MatterConfig(
        enabled=bool(matter_raw.get("enabled", True)),
        server_url=str(matter_raw.get("server_url", "ws://localhost:5580/ws")).strip(),
        storage_path=str(matter_raw.get("storage_path", "/data/matter")).strip(),
    )

    return AppConfig(
        log_level=str(raw.get("log_level", "info")).strip().upper(),
        mqtt=mqtt,
        otbr=otbr,
        bridge=bridge,
        matter=matter,
    )