"""MQTT bridge runtime for Thread2MQTT."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from threading import Event
from typing import Any

import paho.mqtt.client as mqtt

from . import __version__
from .command_router import CommandRouter
from .config import AppConfig
from .device_registry import Device, DeviceRegistry
from .ha_discovery import build_device_discovery, build_device_removal
from .matter_client import MatterClient
from .otbr_client import OtbrClient


LOGGER = logging.getLogger(__name__)


class Thread2MqttBridge:
    """Bridges OTBR + Matter state into MQTT with HA discovery."""

    def __init__(
        self,
        config: AppConfig,
        otbr_client: OtbrClient,
        device_registry: DeviceRegistry,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._config = config
        self._otbr_client = otbr_client
        self._registry = device_registry
        self._loop = loop
        self._command_router: CommandRouter | None = None
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.mqtt.client_id,
            clean_session=True,
        )
        self._connected = Event()
        self._last_snapshot: dict[str, Any] = {}
        self._configure_client()

    @property
    def last_snapshot(self) -> dict[str, Any]:
        snapshot = dict(self._last_snapshot)
        snapshot["devices"] = len(self._registry.devices)
        return snapshot

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the MQTT connection (non-blocking, uses paho loop_start)."""
        will_topic = self._topic("bridge/state")
        self._client.will_set(
            will_topic,
            payload="offline",
            qos=0,
            retain=self._config.bridge.publish_retained,
        )
        self._client.connect(self._config.mqtt.host, self._config.mqtt.port)
        self._client.loop_start()
        if not self._connected.wait(timeout=15):
            raise RuntimeError("MQTT connection timed out")
        self.refresh_and_publish("startup")

    def stop(self) -> None:
        """Publish offline and disconnect."""
        LOGGER.info("Stopping MQTT bridge")
        self._publish(
            self._topic("bridge/state"), "offline",
            retain=self._config.bridge.publish_retained,
        )
        self._client.loop_stop()
        self._client.disconnect()

    def set_matter_client(self, matter_client: MatterClient, loop: asyncio.AbstractEventLoop) -> CommandRouter:
        """Wire up command routing once the Matter server is connected."""
        self._command_router = CommandRouter(
            self._registry,
            matter_client,
            loop,
            default_commission_ip=self._config.matter.commissioning_ip,
        )
        return self._command_router

    # ------------------------------------------------------------------
    # Bridge-level publishing
    # ------------------------------------------------------------------

    def refresh_and_publish(self, reason: str) -> None:
        snapshot = self._otbr_client.build_snapshot()
        snapshot.update(
            {
                "version": __version__,
                "reason": reason,
                "timestamp": int(time.time()),
                "devices": len(self._registry.devices),
            }
        )
        self._last_snapshot = snapshot
        LOGGER.info(
            "Bridge snapshot: dataset_loaded=%s source=%s devices=%s",
            snapshot.get("dataset_loaded"),
            snapshot.get("dataset_source"),
            snapshot.get("devices"),
        )
        self.publish_bridge_discovery()
        self._publish(
            self._topic("bridge/state"), "online",
            retain=self._config.bridge.publish_retained,
        )
        self._publish_json(
            self._topic("bridge/attributes"), snapshot,
            retain=self._config.bridge.publish_retained,
        )

    def publish_bridge_discovery(self) -> None:
        discovery_topic = f"{self._config.mqtt.discovery_prefix}/device/thread2mqtt_bridge/config"
        payload = {
            "dev": {
                "ids": ["thread2mqtt_bridge"],
                "name": "Thread2MQTT Bridge",
                "mf": "Oblivionevil",
                "mdl": "Thread2MQTT Add-on",
                "sw": __version__,
            },
            "o": {
                "name": "thread2mqtt",
                "sw": __version__,
                "url": "https://github.com/Oblivionevil/thread2mqtt",
            },
            "cmps": {
                "bridge_state": {
                    "p": "binary_sensor",
                    "name": "Bridge",
                    "device_class": "connectivity",
                    "state_topic": self._topic("bridge/state"),
                    "payload_on": "online",
                    "payload_off": "offline",
                    "unique_id": "thread2mqtt_bridge_state",
                    "entity_category": "diagnostic",
                },
                "dataset_source": {
                    "p": "sensor",
                    "name": "Dataset Source",
                    "state_topic": self._topic("bridge/attributes"),
                    "value_template": "{{ value_json.dataset_source | default('unknown') }}",
                    "unique_id": "thread2mqtt_dataset_source",
                    "entity_category": "diagnostic",
                },
                "otbr_reachable": {
                    "p": "binary_sensor",
                    "name": "OTBR Reachable",
                    "device_class": "connectivity",
                    "state_topic": self._topic("bridge/attributes"),
                    "value_template": "{{ 'ON' if value_json.otbr_reachable else 'OFF' }}",
                    "payload_on": "ON",
                    "payload_off": "OFF",
                    "unique_id": "thread2mqtt_otbr_reachable",
                    "entity_category": "diagnostic",
                },
                "dataset_hash": {
                    "p": "sensor",
                    "name": "Dataset Hash",
                    "state_topic": self._topic("bridge/attributes"),
                    "value_template": "{{ value_json.dataset_sha256 | default('') }}",
                    "unique_id": "thread2mqtt_dataset_hash",
                    "entity_category": "diagnostic",
                },
            },
            "state_topic": self._topic("bridge/attributes"),
        }
        self._publish_json(discovery_topic, payload, retain=self._config.bridge.publish_retained)

    # ------------------------------------------------------------------
    # Device-level publishing (called from any thread, paho is threadsafe)
    # ------------------------------------------------------------------

    def publish_device_state(self, device: Device) -> None:
        state = device.get_state_payload()
        if state:
            self._publish_json(
                self._topic(f"{device.friendly_name}"),
                state,
                retain=self._config.bridge.publish_retained,
            )

    def publish_device_availability(self, device: Device) -> None:
        self._publish(
            self._topic(f"{device.friendly_name}/availability"),
            "online" if device.available else "offline",
            retain=self._config.bridge.publish_retained,
        )

    def publish_device_discovery(self, device: Device) -> None:
        pairs = build_device_discovery(
            device,
            self._config.mqtt.base_topic,
            self._config.mqtt.discovery_prefix,
        )
        for topic, payload in pairs:
            self._publish_json(topic, payload, retain=self._config.bridge.publish_retained)

    def remove_device_discovery(self, device: Device) -> None:
        topics = build_device_removal(device, self._config.mqtt.discovery_prefix)
        for topic in topics:
            self._publish(topic, "", retain=True)
        # remove availability + state
        self._publish(self._topic(f"{device.friendly_name}/availability"), "", retain=True)
        self._publish(self._topic(f"{device.friendly_name}"), "", retain=True)

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------

    def _configure_client(self) -> None:
        if self._config.mqtt.username:
            self._client.username_pw_set(self._config.mqtt.username, self._config.mqtt.password)
        if self._config.mqtt.tls:
            self._client.tls_set()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(
        self,
        client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            raise RuntimeError(f"MQTT connection failed: {reason_code}")
        LOGGER.info("Connected to MQTT broker at %s:%s", self._config.mqtt.host, self._config.mqtt.port)
        client.subscribe(self._config.bridge.birth_topic)
        client.subscribe(self._topic("bridge/request/#"))
        client.subscribe(self._topic("+/set"))
        client.subscribe(self._topic("+/get"))
        self._connected.set()

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        LOGGER.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_message(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        topic = message.topic
        payload = message.payload.decode("utf-8", errors="replace").strip()

        # HA birth message
        if topic == self._config.bridge.birth_topic:
            if payload.lower() == "online":
                LOGGER.info("HA birth → republishing discovery")
                self.publish_bridge_discovery()
                if self._last_snapshot:
                    self._publish_json(
                        self._topic("bridge/attributes"),
                        self._last_snapshot,
                        retain=self._config.bridge.publish_retained,
                    )
                    self._publish(
                        self._topic("bridge/state"), "online",
                        retain=self._config.bridge.publish_retained,
                    )
                # Re-publish all device discovery
                for dev in self._registry.devices.values():
                    self.publish_device_discovery(dev)
                    self.publish_device_state(dev)
                    self.publish_device_availability(dev)
            return

        base = self._config.mqtt.base_topic
        if not topic.startswith(base + "/"):
            return

        suffix = topic[len(base) + 1:]

        # Bridge request topics
        if suffix.startswith("bridge/request/"):
            command = suffix.removeprefix("bridge/request/").strip("/")
            self._handle_request(command, payload)
            return

        # Device set command: <friendly_name>/set
        if suffix.endswith("/set"):
            friendly = suffix[:-4]
            if self._command_router and friendly:
                self._command_router.handle_set(friendly, payload)
            return

        # Device get command: <friendly_name>/get
        if suffix.endswith("/get"):
            friendly = suffix[:-4]
            if self._command_router and friendly:
                self._command_router.handle_get(friendly)
            return

    # ------------------------------------------------------------------
    # Bridge request handling
    # ------------------------------------------------------------------

    def _handle_request(self, command: str, payload: str) -> None:
        LOGGER.info("Bridge request: %s", command)

        if command in {"reload", "info", "dataset"}:
            self.refresh_and_publish(command)
            self._respond(command, {"ok": True, "command": command, "snapshot": self._last_snapshot})
            return

        if command == "ping":
            self._respond(command, {"ok": True, "command": command, "message": payload or "pong", "version": __version__})
            return

        if command == "shutdown":
            self._respond(command, {"ok": True, "command": command, "message": "stopping"})
            return

        if command == "permit_join":
            if self._command_router:
                self._command_router.handle_commission(payload)
                self._respond(command, {"ok": True, "command": command, "message": "commissioning started"})
            else:
                self._respond(command, {"ok": False, "error": "Matter controller not connected"})
            return

        if command == "remove":
            if self._command_router:
                self._command_router.handle_remove(payload)
                self._respond(command, {"ok": True, "command": command, "message": "removal requested"})
            else:
                self._respond(command, {"ok": False, "error": "Matter controller not connected"})
            return

        self._respond(command or "unknown", {"ok": False, "error": f"Unknown request '{command}'"})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _respond(self, command: str, payload: dict[str, Any]) -> None:
        self._publish_json(self._topic(f"bridge/response/{command}"), payload, retain=False)

    def _publish(self, topic: str, payload: str, retain: bool) -> None:
        LOGGER.debug("MQTT → %s", topic)
        self._client.publish(topic, payload=payload, qos=0, retain=retain)

    def _publish_json(self, topic: str, payload: dict[str, Any], retain: bool) -> None:
        self._publish(topic, json.dumps(payload, sort_keys=True), retain=retain)

    def _topic(self, suffix: str) -> str:
        return f"{self._config.mqtt.base_topic.rstrip('/')}/{suffix.lstrip('/')}"