# Thread2MQTT

## What This Add-on Does

Thread2MQTT is a Matter-over-Thread to MQTT bridge for Home Assistant.
It runs its own Matter controller inside the add-on container and exposes
every commissioned Thread device as an MQTT device – with full Home Assistant
MQTT Discovery, zigbee2mqtt-style topics, and bidirectional control.

### Features

- Connects to an external OpenThread Border Router (e.g. SLZB-MR4U).
- Runs a built-in python-matter-server instance with its own fabric.
- Loads the active Thread dataset from OTBR (or manual TLVs) and pushes it to
  the Matter server.
- Commissions Matter devices via MQTT (`permit_join`).
- Publishes device states in zigbee2mqtt-compatible JSON payloads.
- Supports set commands (on/off, brightness, color temperature).
- Announces every device into Home Assistant via MQTT Discovery.
- Exposes a built-in web UI through Home Assistant ingress.

## Web UI

After starting the add-on, use **Open Web UI** in the Home Assistant add-on page.

The web UI includes:

- bridge diagnostics and Matter runtime status
- Matter commissioning with pairing codes
- device cards with live state, on/off control, brightness, color temperature
- refresh and remove actions for commissioned nodes

Ingress is enabled for the add-on and the web server listens on internal port `8099`.
The UI only accepts local Home Assistant ingress traffic and localhost access.

## MQTT Topics

### Bridge topics

| Topic | Description |
|---|---|
| `thread2mqtt/bridge/state` | `online` / `offline` |
| `thread2mqtt/bridge/attributes` | Bridge diagnostics JSON |
| `thread2mqtt/bridge/request/ping` | Request a pong |
| `thread2mqtt/bridge/request/info` | Republish bridge attributes |
| `thread2mqtt/bridge/request/reload` | Reload OTBR dataset |
| `thread2mqtt/bridge/request/permit_join` | Commission a device (`{"code":"MT:..."}`) |
| `thread2mqtt/bridge/request/remove` | Remove a device (`{"node_id":1}`) |
| `thread2mqtt/bridge/response/<cmd>` | Response to a bridge request |

### Device topics

| Topic | Description |
|---|---|
| `thread2mqtt/<friendly_name>` | Device state JSON |
| `thread2mqtt/<friendly_name>/set` | Send commands (JSON or simple) |
| `thread2mqtt/<friendly_name>/get` | Refresh device state |
| `thread2mqtt/<friendly_name>/availability` | `online` / `offline` |

### Example: control a light

```json
// Publish to thread2mqtt/Living Room Light/set
{"state": "ON", "brightness": 128, "color_temp": 370}
```

## Configuration

### `mqtt`

- `host`: MQTT broker host name or IP.
- `port`: MQTT broker port.
- `username`: Optional MQTT username.
- `password`: Optional MQTT password.
- `client_id`: MQTT client identifier.
- `discovery_prefix`: Home Assistant MQTT discovery prefix.
- `base_topic`: Bridge base topic.
- `tls`: Enable TLS for MQTT.

### `otbr`

- `url`: Base URL of the external OTBR endpoint.
- `dataset_source`: `otbr` or `manual`.
- `dataset_tlvs`: Manual Thread operational dataset TLVs.
- `timeout_seconds`: HTTP timeout for OTBR requests.

### `bridge`

- `publish_retained`: Retain discovery and status payloads.
- `birth_topic`: Topic watched for Home Assistant online events.

### `matter`

- `enabled`: Enable the built-in Matter controller (default: true).
- `host`: Host used by Thread2MQTT to reach the built-in Matter server (default: `127.0.0.1`).
- `port`: TCP port for the built-in Matter server (default: `5581`).
- `listen_address`: Bind address for the built-in Matter server (default: `127.0.0.1`).

## Notes

- The Thread dataset is **never** published to MQTT in full (contains key material).
  Only a SHA-256 hash is exposed.
- The SLZB-MR4U (or any OTBR) is treated as an external border router.
  This add-on does **not** start OTBR itself.
- Only amd64 and aarch64 are supported (Matter SDK wheel availability).
- The built-in Matter server defaults to port `5581` to avoid colliding with Home Assistant's official Matter Server add-on on `5580`.