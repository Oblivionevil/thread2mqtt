"""Unit tests for command routing behavior."""

import asyncio

from app.command_router import CommandRouter
from app.matter_client import MatterClientError


class FakeMatterClient:
    def __init__(self, *, bluetooth_enabled: bool, responses: list[object] | None = None) -> None:
        self.server_info = {"bluetooth_enabled": bluetooth_enabled}
        self.calls: list[tuple[str, bool]] = []
        self._responses = list(responses or [])

    async def commission_with_code(self, code: str, network_only: bool = False) -> None:
        self.calls.append((code, network_only))
        if self._responses:
            result = self._responses.pop(0)
            if isinstance(result, Exception):
                raise result


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
    else:
        raise AssertionError("Expected network-only commissioning failure")