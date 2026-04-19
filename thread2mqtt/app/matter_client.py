"""Lightweight async WebSocket client for python-matter-server."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

import websockets

LOGGER = logging.getLogger(__name__)

# Event types emitted by python-matter-server
EVENT_NODE_ADDED = "node_added"
EVENT_NODE_UPDATED = "node_updated"
EVENT_NODE_REMOVED = "node_removed"
EVENT_NODE_EVENT = "node_event"
EVENT_ATTRIBUTE_UPDATED = "attribute_updated"
EVENT_SERVER_INFO_UPDATED = "server_info_updated"


class MatterClientError(RuntimeError):
    """Error communicating with the Matter server."""


class MatterClient:
    """Async WebSocket client that speaks the python-matter-server protocol."""

    def __init__(self, url: str = "ws://localhost:5580/ws") -> None:
        self._url = url
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._message_id: int = 0
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._listen_task: asyncio.Task[None] | None = None
        self._event_callbacks: dict[str, list[Callable[..., Any]]] = {}
        self._nodes: dict[int, dict[str, Any]] = {}
        self._server_info: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def nodes(self) -> dict[int, dict[str, Any]]:
        return dict(self._nodes)

    @property
    def server_info(self) -> dict[str, Any]:
        return dict(self._server_info)

    @property
    def connected(self) -> bool:
        return self._ws is not None

    # ------------------------------------------------------------------
    # Event subscription
    # ------------------------------------------------------------------

    def subscribe(self, event_type: str, callback: Callable[..., Any]) -> None:
        self._event_callbacks.setdefault(event_type, []).append(callback)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the matter server, fetch initial state."""
        LOGGER.info("Connecting to Matter server at %s", self._url)
        self._ws = await websockets.connect(self._url, max_size=None, ping_interval=30)
        self._listen_task = asyncio.create_task(self._listen_loop())

        result = await self._send_command("start_listening")
        if isinstance(result, dict):
            self._server_info = result.get("server_info", {})
            for node in result.get("nodes", []):
                nid = node.get("node_id")
                if nid is not None:
                    self._nodes[nid] = node

        LOGGER.info("Connected to Matter server – %d existing node(s)", len(self._nodes))

    async def disconnect(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    async def set_thread_dataset(self, dataset_tlvs: str) -> Any:
        return await self._send_command("set_thread_dataset", dataset=dataset_tlvs)

    async def commission_with_code(self, code: str) -> Any:
        return await self._send_command("commission_with_code", code=code)

    async def commission_on_network(self, setup_pin_code: int) -> Any:
        return await self._send_command("commission_on_network", setup_pin_code=setup_pin_code)

    async def open_commissioning_window(self, node_id: int) -> Any:
        return await self._send_command("open_commissioning_window", node_id=node_id)

    async def discover(self) -> Any:
        return await self._send_command("discover")

    async def get_node(self, node_id: int) -> dict[str, Any]:
        return await self._send_command("get_node", node_id=node_id)

    async def interview_node(self, node_id: int) -> Any:
        return await self._send_command("interview_node", node_id=node_id)

    async def remove_node(self, node_id: int) -> Any:
        return await self._send_command("remove_node", node_id=node_id)

    async def ping_node(self, node_id: int) -> Any:
        return await self._send_command("ping_node", node_id=node_id)

    async def send_device_command(
        self,
        node_id: int,
        endpoint_id: int,
        cluster_id: int,
        command_name: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Send a cluster command serialised for the matter-server WS API.

        ``command_name`` is the chip command class path relative to
        ``chip.clusters.Objects``, e.g. ``"OnOff.Commands.On"``.
        """
        command_obj: dict[str, Any] = {
            "_type": f"chip.clusters.Objects.{command_name}",
        }
        if payload:
            command_obj.update(payload)
        return await self._send_command(
            "send_device_command",
            node_id=node_id,
            endpoint_id=endpoint_id,
            command=command_obj,
        )

    async def read_attribute(self, node_id: int, attribute_path: str) -> Any:
        return await self._send_command(
            "read_attribute", node_id=node_id, attribute_path=attribute_path,
        )

    async def write_attribute(self, node_id: int, attribute_path: str, value: Any) -> Any:
        return await self._send_command(
            "write_attribute", node_id=node_id, attribute_path=attribute_path, value=value,
        )

    # ------------------------------------------------------------------
    # WebSocket transport
    # ------------------------------------------------------------------

    async def _send_command(self, command: str, **kwargs: Any) -> Any:
        if not self._ws:
            raise MatterClientError("Not connected")
        self._message_id += 1
        mid = str(self._message_id)
        message: dict[str, Any] = {"message_id": mid, "command": command}
        if kwargs:
            message["args"] = kwargs

        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[mid] = future

        LOGGER.debug("WS → %s (id=%s)", command, mid)
        await self._ws.send(json.dumps(message))

        try:
            return await asyncio.wait_for(future, timeout=120)
        except asyncio.TimeoutError:
            self._pending.pop(mid, None)
            raise MatterClientError(f"Command '{command}' timed out") from None

    async def _listen_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    LOGGER.warning("Invalid JSON from Matter server")
                    continue
                self._handle_message(data)
        except websockets.ConnectionClosed:
            LOGGER.warning("Matter server WebSocket closed")
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Error in Matter server listener")

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    def _handle_message(self, data: dict[str, Any]) -> None:
        # Command response
        if "message_id" in data:
            mid = str(data["message_id"])
            future = self._pending.pop(mid, None)
            if future and not future.done():
                if "error_code" in data:
                    future.set_exception(
                        MatterClientError(
                            f"Error {data['error_code']}: {data.get('details', 'unknown')}"
                        )
                    )
                else:
                    future.set_result(data.get("result"))
            return

        # Event
        event_type = data.get("event")
        if not event_type:
            return
        event_data = data.get("data")
        self._update_node_cache(event_type, event_data)

        for cb in self._event_callbacks.get(event_type, []):
            try:
                cb(event_type, event_data)
            except Exception:
                LOGGER.exception("Error in event callback for %s", event_type)

    def _update_node_cache(self, event_type: str, event_data: Any) -> None:
        if event_type in (EVENT_NODE_ADDED, EVENT_NODE_UPDATED) and isinstance(event_data, dict):
            nid = event_data.get("node_id")
            if nid is not None:
                self._nodes[nid] = event_data
        elif event_type == EVENT_NODE_REMOVED:
            nid = event_data if isinstance(event_data, int) else None
            if nid is not None:
                self._nodes.pop(nid, None)
        elif event_type == EVENT_ATTRIBUTE_UPDATED and isinstance(event_data, dict):
            nid = event_data.get("node_id")
            attr_path = event_data.get("attribute_path")
            value = event_data.get("value")
            if nid in self._nodes and attr_path:
                self._nodes[nid].setdefault("attributes", {})[attr_path] = value
