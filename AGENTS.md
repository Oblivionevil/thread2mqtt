# AGENTS.md

## Scope

- This repository is a Home Assistant add-on repository.
- The add-on implementation lives in [thread2mqtt/](thread2mqtt/).
- Root-level [repository.yaml](repository.yaml) only describes the add-on repository for Home Assistant.

## Start Here

- Read [thread2mqtt/README.md](thread2mqtt/README.md) for the product overview, supported devices, and MQTT topic shape.
- Read [thread2mqtt/DOCS.md](thread2mqtt/DOCS.md) for ingress UI behavior, commissioning notes, and add-on configuration details.

## Common Commands

Run commands from [thread2mqtt/](thread2mqtt/):

- Install dependencies: `python -m pip install -r requirements.txt`
- Run unit tests: `pytest -q`
- Run the app locally: `THREAD2MQTT_OPTIONS_PATH=/path/to/options.json python -m app.main`
- Run the container entrypoint: `./run.sh`

Notes:

- Local runs need a valid Home Assistant-style `options.json` file.
- [thread2mqtt/run.sh](thread2mqtt/run.sh) starts `matter-server` first and then launches `python3 -m app.main`.

## Architecture Map

- [thread2mqtt/app/main.py](thread2mqtt/app/main.py): startup, shutdown, Matter event wiring, initial node seeding.
- [thread2mqtt/app/config.py](thread2mqtt/app/config.py): loads `/data/options.json` or `THREAD2MQTT_OPTIONS_PATH`.
- [thread2mqtt/app/matter_client.py](thread2mqtt/app/matter_client.py): WebSocket client for `python-matter-server`; caches node and attribute state.
- [thread2mqtt/app/mqtt_bridge.py](thread2mqtt/app/mqtt_bridge.py): owns MQTT lifecycle, bridge topics, device publish/subscribe handling.
- [thread2mqtt/app/command_router.py](thread2mqtt/app/command_router.py): converts MQTT and web UI actions into Matter commands and commissioning flows.
- [thread2mqtt/app/device_registry.py](thread2mqtt/app/device_registry.py), [thread2mqtt/app/clusters.py](thread2mqtt/app/clusters.py), [thread2mqtt/app/ha_discovery.py](thread2mqtt/app/ha_discovery.py): turn Matter attributes into device state and Home Assistant discovery payloads.
- [thread2mqtt/app/otbr_client.py](thread2mqtt/app/otbr_client.py): fetches and normalizes the active Thread dataset from the external OTBR.
- [thread2mqtt/app/web_ui.py](thread2mqtt/app/web_ui.py): aiohttp ingress UI; HTML/CSS/JS are intentionally embedded in this file.

## Conventions For Changes

- Keep MQTT topics and payloads aligned with the shapes documented in [thread2mqtt/README.md](thread2mqtt/README.md) and [thread2mqtt/DOCS.md](thread2mqtt/DOCS.md).
- For new Matter device support, usually update mappings in [thread2mqtt/app/clusters.py](thread2mqtt/app/clusters.py), state/discovery handling in [thread2mqtt/app/device_registry.py](thread2mqtt/app/device_registry.py) or [thread2mqtt/app/ha_discovery.py](thread2mqtt/app/ha_discovery.py), and add a focused unit test in [thread2mqtt/tests/](thread2mqtt/tests/).
- Do not publish raw Thread dataset contents to MQTT. Only derived metadata, hashes, or status flags are acceptable.
- Preserve the default Matter port `5581` unless the task explicitly requires coordinated changes; this avoids clashing with Home Assistant's official Matter Server on `5580`.
- The MQTT device topic is derived from `friendly_name`; renames affect topics and discovery identifiers.
- The web UI is a single-file implementation. Keep edits localized and avoid splitting it unless the task explicitly requires a larger refactor.

## Testing Style

- Tests live under [thread2mqtt/tests/](thread2mqtt/tests/).
- Existing tests are small pytest unit tests with fake clients and direct object construction rather than end-to-end integration tests.
- Prefer adding a narrow regression test next to the affected module instead of building new test infrastructure.

## Release Notes

- When bumping a release, update both [thread2mqtt/app/__init__.py](thread2mqtt/app/__init__.py) and [thread2mqtt/config.yaml](thread2mqtt/config.yaml).
- Update [repository.yaml](repository.yaml) only when repository-level add-on metadata changes.

## Environment Pitfall

- In GitHub virtual workspaces, terminal and git operations may not have a local checkout path even though file editing works. Prefer editor-aware file tools when direct terminal access to the repository is unavailable.