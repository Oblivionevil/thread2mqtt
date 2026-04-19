"""Unit tests for Matter client message handling."""

from app.matter_client import EVENT_ATTRIBUTE_UPDATED, EVENT_SERVER_INFO_UPDATED, MatterClient


def test_server_info_is_updated_from_event_messages() -> None:
    client = MatterClient()
    client._handle_message(
        {
            "event": EVENT_SERVER_INFO_UPDATED,
            "data": {
                "thread_credentials_set": True,
                "bluetooth_enabled": False,
            },
        }
    )

    assert client.server_info == {
        "thread_credentials_set": True,
        "bluetooth_enabled": False,
    }


def test_attribute_updates_are_normalized_and_cached() -> None:
    client = MatterClient()
    client._nodes[1] = {"node_id": 1, "attributes": {}}
    received: list[object] = []
    client.subscribe(EVENT_ATTRIBUTE_UPDATED, lambda _event, data: received.append(data))

    client._handle_message(
        {
            "event": EVENT_ATTRIBUTE_UPDATED,
            "data": [1, "1/1030/0", 1],
        }
    )

    assert client.nodes[1]["attributes"] == {"1/1030/0": 1}
    assert received == [{"node_id": 1, "attribute_path": "1/1030/0", "value": 1}]