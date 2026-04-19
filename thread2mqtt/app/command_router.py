"""Routes MQTT set / get commands to Matter device commands."""

from __future__ import annotations

import asyncio
from ipaddress import ip_address
import json
import logging
from typing import Any

from .clusters import ClusterId
from .device_registry import Device, DeviceRegistry
from .matter_client import MatterClient, MatterClientError
from .setup_codes import MatterSetupCodeError, parse_manual_setup_pin_code

LOGGER = logging.getLogger(__name__)


class CommandRouter:
    """Translates MQTT payloads into Matter cluster commands."""

    def __init__(
        self,
        device_registry: DeviceRegistry,
        matter_client: MatterClient,
        loop: asyncio.AbstractEventLoop,
        default_commission_ip: str | None = None,
    ) -> None:
        self._registry = device_registry
        self._matter = matter_client
        self._loop = loop
        self._default_commission_ip = default_commission_ip.strip() if default_commission_ip else None

    # -- public (called from paho MQTT thread) --------------------------

    async def set_device(self, device: Device, payload: dict[str, Any]) -> None:
        ep = self._first_controllable_ep(device)
        if ep is None:
            raise ValueError(f"No controllable endpoint on {device.friendly_name}")

        if "state" in payload:
            await self._on_off(device.node_id, ep, payload["state"])
        if "brightness" in payload:
            await self._brightness(device.node_id, ep, payload["brightness"])
        if "color_temp" in payload:
            await self._color_temp(device.node_id, ep, payload["color_temp"])

    async def set_device_by_name(self, friendly_name: str, payload: dict[str, Any]) -> None:
        device = self._registry.get_device_by_name(friendly_name)
        if not device:
            raise ValueError(f"Unknown device: {friendly_name}")
        await self.set_device(device, payload)

    async def set_device_by_node(self, node_id: int, payload: dict[str, Any]) -> None:
        device = self._registry.get_device(node_id)
        if not device:
            raise ValueError(f"Unknown node_id: {node_id}")
        await self.set_device(device, payload)

    async def refresh_device(self, device: Device) -> None:
        await self._matter.interview_node(device.node_id)

    async def refresh_device_by_name(self, friendly_name: str) -> None:
        device = self._registry.get_device_by_name(friendly_name)
        if not device:
            raise ValueError(f"Unknown device: {friendly_name}")
        await self.refresh_device(device)

    async def refresh_device_by_node(self, node_id: int) -> None:
        device = self._registry.get_device(node_id)
        if not device:
            raise ValueError(f"Unknown node_id: {node_id}")
        await self.refresh_device(device)

    async def commission(
        self,
        code: str | None = None,
        *,
        ip_addr: str | None = None,
        setup_pin_code: int | None = None,
    ) -> None:
        normalized_code = code.strip() if isinstance(code, str) else ""
        normalized_ip = str(ip_addr).strip() if ip_addr else ""

        if not normalized_ip and self._default_commission_ip:
            if setup_pin_code is not None:
                normalized_ip = self._default_commission_ip
                LOGGER.info("Using configured default commissioning IP %s", normalized_ip)
            elif normalized_code and not normalized_code.upper().startswith("MT:"):
                normalized_ip = self._default_commission_ip
                LOGGER.info("Using configured default commissioning IP %s", normalized_ip)

        if normalized_ip:
            try:
                normalized_ip = str(ip_address(normalized_ip))
            except ValueError as err:
                raise MatterClientError(f"Invalid target IP address: {normalized_ip}") from err

            if setup_pin_code is None:
                if not normalized_code:
                    raise MatterClientError(
                        "IP-directed commissioning requires a manual pairing code or explicit setup_pin_code."
                    )
                try:
                    setup_pin_code = parse_manual_setup_pin_code(normalized_code)
                except MatterSetupCodeError as err:
                    raise MatterClientError(str(err)) from err

            LOGGER.info("Commissioning device with target IP %s", normalized_ip)
            try:
                await self._matter.commission_on_network(setup_pin_code, ip_addr=normalized_ip)
            except MatterClientError as err:
                raise MatterClientError(f"IP-directed commissioning failed for {normalized_ip}: {err}") from err
            return

        if not normalized_code:
            raise MatterClientError("Missing Matter pairing code")

        LOGGER.info("Commissioning device with code: %s", normalized_code)
        bluetooth_enabled = bool(self._matter.server_info.get("bluetooth_enabled"))
        network_only = not bluetooth_enabled

        try:
            await self._matter.commission_with_code(normalized_code, network_only=network_only)
        except MatterClientError as err:
            if not network_only and "Bluetooth commissioning is not available" in str(err):
                LOGGER.info("Retrying commissioning in network-only mode")
                await self._matter.commission_with_code(normalized_code, network_only=True)
                return

            if network_only:
                raise MatterClientError(
                    "Network-only commissioning failed. The request used discovery only. The device must already be visible as a "
                    "commissionable Matter node on your Thread network, for example after vendor-app onboarding or an open multi-admin window. "
                    "If discovery is unreliable, resend the request with a target IP or configure matter.commissioning_ip in the add-on options."
                ) from err

            raise

    async def remove_node(self, node_id: int) -> None:
        LOGGER.info("Removing node %d", node_id)
        await self._matter.remove_node(node_id)

    def handle_set(self, friendly_name: str, payload_str: str) -> None:
        try:
            payload = json.loads(payload_str) if payload_str.strip().startswith("{") else {"state": payload_str}
        except json.JSONDecodeError:
            payload = {"state": payload_str}
        future = asyncio.run_coroutine_threadsafe(self.set_device_by_name(friendly_name, payload), self._loop)
        future.add_done_callback(lambda fut: self._log_future_error(fut, f"Command failed for {friendly_name}"))

    def handle_get(self, friendly_name: str) -> None:
        future = asyncio.run_coroutine_threadsafe(self.refresh_device_by_name(friendly_name), self._loop)
        future.add_done_callback(lambda fut: self._log_future_error(fut, f"Refresh failed for {friendly_name}"))

    def handle_commission(self, payload_str: str) -> None:
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            data = None

        if isinstance(data, dict):
            code_value = data.get("code") or data.get("value")
            ip_addr = data.get("ip") or data.get("ip_addr")
            try:
                setup_pin_code = self._parse_setup_pin_code(data.get("setup_pin_code", data.get("setup_pin")))
            except ValueError as err:
                LOGGER.warning("Invalid commission request: %s", err)
                return
            code = str(code_value).strip() if code_value is not None else None
            ip_addr = str(ip_addr).strip() if ip_addr is not None else None
        else:
            code = payload_str.strip() or None
            ip_addr = None
            setup_pin_code = None

        if not code and setup_pin_code is None:
            return

        future = asyncio.run_coroutine_threadsafe(
            self.commission(code, ip_addr=ip_addr, setup_pin_code=setup_pin_code),
            self._loop,
        )
        context = ip_addr or code or f"setup_pin_code={setup_pin_code}"
        future.add_done_callback(lambda fut: self._log_future_error(fut, f"Commission failed for {context}"))

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
        future = asyncio.run_coroutine_threadsafe(self.remove_node(node_id), self._loop)
        future.add_done_callback(lambda fut: self._log_future_error(fut, f"Remove failed for node {node_id}"))

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

    @staticmethod
    def _log_future_error(future: asyncio.Future[Any], context: str) -> None:
        try:
            future.result()
        except Exception as err:
            LOGGER.error("%s: %s", context, err, exc_info=(type(err), err, err.__traceback__))

    @staticmethod
    def _parse_setup_pin_code(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as err:
            raise ValueError("setup_pin_code must be an integer") from err
