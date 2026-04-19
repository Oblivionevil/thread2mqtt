# Thread2MQTT

Thread2MQTT is a Home Assistant add-on that bridges **Matter-over-Thread** devices
into MQTT – giving you a **zigbee2mqtt-style** experience for Thread.

## Highlights

- Runs its own Matter controller (python-matter-server) with a dedicated fabric.
- Connects to an external OTBR (e.g. SLZB-MR4U) for Thread networking.
- Publishes device states as JSON to MQTT and subscribes to `/set` topics for control.
- Full **Home Assistant MQTT Discovery** for every commissioned device.
- Commission new devices from MQTT via `thread2mqtt/bridge/request/permit_join`.
- Uses Matter port `5581` by default to avoid conflicting with Home Assistant's official Matter Server on `5580`.

## Supported device types

Lights (on/off, dimmable, color temperature, extended color), switches/plugs,
contact sensors, temperature sensors, humidity sensors, pressure sensors,
occupancy sensors, light sensors, door locks, thermostats.

## Quick start

1. Add this repository to Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Install **Thread2MQTT** and configure MQTT + OTBR settings.
3. Start the add-on – the bridge will appear in Home Assistant via MQTT Discovery.
4. Commission a device:
   ```
   Publish to: thread2mqtt/bridge/request/permit_join
   Payload:    {"code": "MT:Y.K9042C00KA0648G00"}
   ```
5. The device appears as `thread2mqtt/<friendly_name>` with full HA entities.