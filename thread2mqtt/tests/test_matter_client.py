"""Unit tests for Matter client message handling."""

from app.matter_client import EVENT_SERVER_INFO_UPDATED, MatterClient


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