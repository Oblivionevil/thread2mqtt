"""Routes MQTT set / get commands to Matter device commands."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from .clusters import ClusterId
from .device_registry import Device, DeviceRegistry
from .matter_client import MatterClient

LOGGER = logging.getLogger(__name__)


class CommandRouter:
    """Translates MQTT payloads into Matter cluster commands."""

    def __init__(
        self,
        device_registry: DeviceRegistry,
        matter_client: MatterClient,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._registry = device_registry
        self._matter = matter_client
        self._loop = loop

    # -- public (called from paho MQTT thread) --------------------------

    def handle_set(self, friendly_name: str, payload_str: str) -> None:
        device = self._registry.get_device_by_name(friendly_name)
        if not device:
            LOGGER.warning("Set command for unknown device: %s", friendly_name)
            return
        try:
            payload = json.loads(payload_str) if payload_str.strip().startswith("{") else {"state": payload_str}
        except json.JSONDecodeError:
            payload = {"state": payload_str}
        asyncio.run_coroutine_threadsafe(self._process_set(device, payload), self._loop)

    def handle_get(self, friendly_name: str) -> None:
        device = self._registry.get_device_by_name(friendly_name)
        if not device:
            return
        asyncio.run_coroutine_threadsafe(self._process_get(device), self._loop)

    def handle_commission(self, payload_str: str) -> None:
        try:
            data = json.loads(payload_str)
            code = data.get("code") or data.get("value") or payload_str
        except json.JSONDecodeError:
            code = payload_str.strip()
        if not code:
            return
        asyncio.run_coroutine_threadsafe(self._process_commission(str(code)), self._loop)

    def handle_remove(self, payload_str: str) -> None:
        try:
            data = json.loads(payload_str)
            node_id = int(data.get("node_id", data.get("value", payload_str)))
        except (json.JSONDecodeError, ValueError, TypeError):
            try:
                node_id = int(payload_str.strip())
            except ValueError:
                LOGGER.warning("Invalid node_id for remove: %s", payload_str)
                return
        asyncio.run_coroutine_threadsafe(self._process_remove(node_id), self._loop)

    # -- async processing -----------------------------------------------

    async def _process_set(self, device: Device, payload: dict[str, Any]) -> None:
        ep = self._first_controllable_ep(device)
        if ep is None:
            LOGGER.warning("No controllable endpoint on %s", device.friendly_name)
            return
        try:
            if "state" in payload:
                await self._on_off(device.node_id, ep, payload["state"])
            if "brightness" in payload:
                await self._brightness(device.node_id, ep, payload["brightness"])
            if "color_temp" in payload:
                await self._color_temp(device.node_id, ep, payload["color_temp"])
        except Exception:
            LOGGER.exception("Command failed for %s", device.friendly_name)

    async def _process_get(self, device: Device) -> None:
        try:
            await self._matter.interview_node(device.node_id)
        except Exception:
            LOGGER.exception("Get/interview failed for %s", device.friendly_name)

    async def _process_commission(self, code: str) -> None:
        LOGGER.info("Commissioning device with code: %s", code)
        try:
            await self._matter.commission_with_code(code)
        except Exception:
            LOGGER.exception("Commission failed for code %s", code)

    async def _process_remove(self, node_id: int) -> None:
        LOGGER.info("Removing node %d", node_id)
        try:
            await self._matter.remove_node(node_id)
        except Exception:
            LOGGER.exception("Remove failed for node %d", node_id)

    # -- cluster helpers ------------------------------------------------

    async def _on_off(self, node_id: int, ep: int, state: Any) -> None:
        on = str(state).upper() in ("ON", "TRUE", "1")
        cmd_name = "OnOff.Commands.On" if on else "OnOff.Commands.Off"
        await self._matter.send_device_command(node_id, ep, ClusterId.ON_OFF, cmd_name)

    async def _brightness(self, node_id: int, ep: int, brightness: Any) -> None:
        level = max(0, min(254, int(brightness)))
        await self._matter.send_device_command(
            node_id, ep, ClusterId.LEVEL_CONTROL,
            "LevelControl.Commands.MoveToLevel",
            {"level": level, "transitionTime": 5, "optionsMask": 0, "optionsOverride": 0},
        )

    async def _color_temp(self, node_id: int, ep: int, mireds: Any) -> None:
        await self._matter.send_device_command(
            node_id, ep, ClusterId.COLOR_CONTROL,
            "ColorControl.Commands.MoveToColorTemperature",
            {
                "colorTemperatureMireds": max(153, min(500, int(mireds))),
                "transitionTime": 5,
                "optionsMask": 0,
                "optionsOverride": 0,
            },
        )

    # -- util -----------------------------------------------------------

    @staticmethod
    def _first_controllable_ep(device: Device) -> int | None:
        for ep_id, ep_info in device.endpoints.items():
            if ep_info.entity_mappings:
                return ep_id
        return None
