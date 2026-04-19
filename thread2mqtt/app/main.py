"""Entrypoint for the Thread2MQTT add-on."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from .config import load_config
from .device_registry import DeviceRegistry
from .matter_client import (
    EVENT_ATTRIBUTE_UPDATED,
    EVENT_NODE_ADDED,
    EVENT_NODE_REMOVED,
    EVENT_NODE_UPDATED,
    MatterClient,
)
from .mqtt_bridge import Thread2MqttBridge
from .otbr_client import OtbrClient
from .web_ui import Thread2MqttWebUi

LOG_LEVEL_MAP = {
    "TRACE": logging.DEBUG,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "NOTICE": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "FATAL": logging.CRITICAL,
}


def configure_logging(level_name: str) -> None:
    """Configure process logging."""
    level = LOG_LEVEL_MAP.get(level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


async def async_main() -> int:
    """Async main entry-point."""
    config = load_config()
    configure_logging(config.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting Thread2MQTT")

    otbr_client = OtbrClient(config.otbr)
    device_registry = DeviceRegistry()
    loop = asyncio.get_running_loop()

    bridge = Thread2MqttBridge(
        config=config,
        otbr_client=otbr_client,
        device_registry=device_registry,
        loop=loop,
    )
    web_ui = Thread2MqttWebUi(config=config, bridge=bridge, device_registry=device_registry)

    # MQTT runs in its own thread (paho loop_start)
    bridge.start()
    await web_ui.start()

    matter_client: MatterClient | None = None

    if config.matter.enabled:
        matter_client = MatterClient(url=config.matter.server_url)
        command_router = bridge.set_matter_client(matter_client, loop)
        web_ui.set_runtime(matter_client, command_router)

        # -- event callbacks (called from the asyncio listener task) ----

        def _on_node_change(_event_type: str, data: object) -> None:
            if isinstance(data, dict) and "node_id" in data:
                nid = data["node_id"]
                dev = device_registry.add_or_update(nid, data)
                bridge.publish_device_state(dev)
                bridge.publish_device_discovery(dev)
                bridge.publish_device_availability(dev)

        def _on_node_removed(_event_type: str, data: object) -> None:
            nid = data if isinstance(data, int) else None
            if isinstance(data, dict):
                nid = data.get("node_id")
            if nid is not None:
                dev = device_registry.remove(nid)
                if dev:
                    bridge.remove_device_discovery(dev)

        def _on_attr_updated(_event_type: str, data: object) -> None:
            if isinstance(data, dict):
                nid = data.get("node_id")
                if nid is not None:
                    node_data = matter_client.nodes.get(nid)
                    dev = device_registry.add_or_update(nid, node_data) if node_data else device_registry.get_device(nid)
                    if dev:
                        bridge.publish_device_state(dev)

        matter_client.subscribe(EVENT_NODE_ADDED, _on_node_change)
        matter_client.subscribe(EVENT_NODE_UPDATED, _on_node_change)
        matter_client.subscribe(EVENT_NODE_REMOVED, _on_node_removed)
        matter_client.subscribe(EVENT_ATTRIBUTE_UPDATED, _on_attr_updated)

        # -- connect with retries --------------------------------------
        connected = False
        for attempt in range(1, 31):
            try:
                await matter_client.connect()
                connected = True
                break
            except Exception as err:
                logger.warning(
                    "Matter server connection attempt %d/30 failed: %s",
                    attempt, err,
                )
                await asyncio.sleep(2)

        if connected:
            logger.info("Connected to Matter server")

            # Push Thread dataset
            try:
                dataset, meta = otbr_client.load_dataset()
                await matter_client.set_thread_dataset(dataset)
                logger.info("Thread dataset pushed to Matter server (source=%s)", meta.source)
            except Exception:
                logger.exception("Failed to push Thread dataset")

            # Wire command routing
            bridge.set_matter_client(matter_client, loop)

            # Seed device registry with existing nodes
            for nid, ndata in matter_client.nodes.items():
                dev = device_registry.add_or_update(nid, ndata)
                bridge.publish_device_state(dev)
                bridge.publish_device_discovery(dev)
                bridge.publish_device_availability(dev)
        else:
            logger.error("Could not connect to Matter server after 30 attempts")

    # -- wait for termination signal ------------------------------------
    stop_event = asyncio.Event()

    def _stop() -> None:
        logger.info("Received stop signal – shutting down")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda *_: _stop())

    await stop_event.wait()

    # -- cleanup --------------------------------------------------------
    if matter_client:
        await matter_client.disconnect()
    await web_ui.stop()
    bridge.stop()
    logger.info("Thread2MQTT stopped")
    return 0


def main() -> int:
    """Run the add-on process."""
    try:
        return asyncio.run(async_main())
    except Exception:
        logging.getLogger(__name__).exception("Thread2MQTT terminated with an error")
        return 1


if __name__ == "__main__":
    sys.exit(main())