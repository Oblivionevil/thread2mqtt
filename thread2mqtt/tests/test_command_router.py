"""Unit tests for command routing behavior."""

import asyncio

from app.command_router import CommandRouter
from app.device_registry import Device
from app.matter_client import MatterClientError


class FakeMatterClient:
    def __init__(self, *, bluetooth_enabled: bool, responses: list[object] | None = None) -> None:
        self.server_info = {"bluetooth_enabled": bluetooth_enabled}
        self.calls: list[tuple[str, bool]] = []
        self.on_network_calls: list[tuple[int, str | None]] = []
        self.device_commands: list[tuple[int, int, int, str, dict[str, object] | None]] = []
        self._responses = list(responses or [])

    async def commission_with_code(self, code: str, network_only: bool = False) -> None:
        self.calls.append((code, network_only))
        if self._responses:
            result = self._responses.pop(0)
            if isinstance(result, Exception):
                raise result

    async def commission_on_network(self, setup_pin_code: int, ip_addr: str | None = None) -> None:
        self.on_network_calls.append((setup_pin_code, ip_addr))
        if self._responses:
            result = self._responses.pop(0)
            if isinstance(result, Exception):
                raise result

    async def send_device_command(
        self,
        node_id: int,
        endpoint_id: int,
        cluster_id: int,
        command_name: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.device_commands.append((node_id, endpoint_id, cluster_id, command_name, payload))


def test_commission_uses_network_only_without_bluetooth() -> None:
    router = CommandRouter(device_registry=object(), matter_client=FakeMatterClient(bluetooth_enabled=False), loop=object())

    asyncio.run(router.commission("12345678901"))

    assert router._matter.calls == [("12345678901", True)]


def test_commission_retries_network_only_when_bluetooth_path_is_unavailable() -> None:
    matter = FakeMatterClient(
        bluetooth_enabled=True,
        responses=[MatterClientError("Error 1: Bluetooth commissioning is not available."), None],
    )
    router = CommandRouter(device_registry=object(), matter_client=matter, loop=object())

    asyncio.run(router.commission("12345678901"))

    assert matter.calls == [("12345678901", False), ("12345678901", True)]


def test_commission_wraps_network_only_failures_with_actionable_message() -> None:
    matter = FakeMatterClient(
        bluetooth_enabled=False,
        responses=[MatterClientError("Error 5: commissioning failed")],
    )
    router = CommandRouter(device_registry=object(), matter_client=matter, loop=object())

    try:
        asyncio.run(router.commission("12345678901"))
    except MatterClientError as err:
        assert "Network-only commissioning failed" in str(err)
        assert "commissionable Matter node" in str(err)
        assert "target IP" in str(err)
    else:
        raise AssertionError("Expected network-only commissioning failure")


def test_commission_uses_target_ip_with_manual_code() -> None:
    matter = FakeMatterClient(bluetooth_enabled=False)
    router = CommandRouter(device_registry=object(), matter_client=matter, loop=object())

    asyncio.run(router.commission("21259335691", ip_addr="192.168.2.168"))

    assert matter.calls == []
    assert matter.on_network_calls == [(58487089, "192.168.2.168")]


def test_commission_uses_explicit_setup_pin_for_target_ip() -> None:
    matter = FakeMatterClient(bluetooth_enabled=False)
    router = CommandRouter(device_registry=object(), matter_client=matter, loop=object())

    asyncio.run(router.commission(ip_addr="192.168.2.168", setup_pin_code=58487089))

    assert matter.calls == []
    assert matter.on_network_calls == [(58487089, "192.168.2.168")]


def test_commission_rejects_qr_payload_for_target_ip_without_setup_pin_code() -> None:
    matter = FakeMatterClient(bluetooth_enabled=False)
    router = CommandRouter(device_registry=object(), matter_client=matter, loop=object())

    try:
        asyncio.run(router.commission("MT:TESTPAYLOAD", ip_addr="192.168.2.168"))
    except MatterClientError as err:
        assert "manual pairing code" in str(err)
        assert "setup_pin_code" in str(err)
    else:
        raise AssertionError("Expected IP-directed commissioning validation failure")


def test_commission_uses_configured_default_ip_for_manual_codes() -> None:
    matter = FakeMatterClient(bluetooth_enabled=False)
    router = CommandRouter(
        device_registry=object(),
        matter_client=matter,
        loop=object(),
        default_commission_ip="192.168.2.168",
    )

    asyncio.run(router.commission("21259335691"))

    assert matter.calls == []
    assert matter.on_network_calls == [(58487089, "192.168.2.168")]


def test_commission_without_target_ip_keeps_discovery_path() -> None:
    matter = FakeMatterClient(bluetooth_enabled=False)
    router = CommandRouter(device_registry=object(), matter_client=matter, loop=object())

    asyncio.run(router.commission("21259335691"))

    assert matter.calls == [("21259335691", True)]
    assert matter.on_network_calls == []


def test_set_device_uses_endpoint_matching_each_command() -> None:
    matter = FakeMatterClient(bluetooth_enabled=False)
    router = CommandRouter(device_registry=object(), matter_client=matter, loop=object())
    device = Device(
        3,
        {
            "attributes": {
                "0/40/1": "Example",
                "0/40/3": "Combo Device",
                "1/29/0": [{"deviceType": 263, "revision": 1}],
                "1/1030/0": 1,
                "2/29/0": [{"deviceType": 268, "revision": 1}],
                "2/6/0": False,
                "2/8/0": 120,
                "2/768/7": 300,
            }
        },
    )

    asyncio.run(router.set_device(device, {"state": "ON", "brightness": 144, "color_temp": 250}))

    assert matter.device_commands == [
        (3, 2, 6, "OnOff.Commands.On", None),
        (3, 2, 8, "LevelControl.Commands.MoveToLevel", {"level": 144, "transitionTime": 5, "optionsMask": 0, "optionsOverride": 0}),
        (3, 2, 768, "ColorControl.Commands.MoveToColorTemperature", {"colorTemperatureMireds": 250, "transitionTime": 5, "optionsMask": 0, "optionsOverride": 0}),
    ]