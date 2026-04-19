<<<<<<< HEAD
# Agent Instructions — Thread2MQTT

Home Assistant add-on: Matter-over-Thread → MQTT bridge.  
All add-on code lives under `thread2mqtt/` (the HA slug folder).

## Quick Reference

```bash
# Run tests (from repo root, Windows or Linux)
cd thread2mqtt && PYTHONPATH=. pytest tests/ -v

# Compile-check a module
python -m py_compile thread2mqtt/app/web_ui.py

# Build the Docker image (HA add-on builder)
docker run --rm --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/thread2mqtt:/data \
  ghcr.io/home-assistant/amd64-builder --target /data --amd64
```

> **Windows note:** `orjson` (transitive dep) needs Rust. Tests run fine with minimal deps: `aiohttp websockets paho-mqtt requests dacite aenum attrs pytest`.

## Architecture

See [DOCS.md](thread2mqtt/DOCS.md) for user-facing docs.

```
run.sh  →  matter-server (port 5581)  →  python3 -m app.main
                                            ├── config.py        (frozen dataclasses from /data/options.json)
                                            ├── otbr_client.py   (REST → OTBR for Thread dataset)
                                            ├── matter_client.py (websockets → python-matter-server)
                                            ├── mqtt_bridge.py   (paho-mqtt, HA Discovery, request dispatch)
                                            ├── command_router.py(MQTT/web → Matter cluster commands)
                                            ├── web_ui.py        (aiohttp SPA on ingress port 8099)
                                            ├── device_registry.py, clusters.py, ha_discovery.py
                                            └── setup_codes.py   (Verhoeff check, manual code → PIN)
```

**Threading model:** asyncio event loop for Matter WS + aiohttp; paho-mqtt on a separate thread bridged via `asyncio.run_coroutine_threadsafe()`.

## Key Conventions

- Python 3.10+, `from __future__ import annotations` in every module
- Relative imports within the `app` package (`from .config import ...`)
- Frozen `@dataclass` for config objects
- Custom exceptions: `MatterClientError`, `OtbrError`, `MatterSetupCodeError`
- Web UI is a **single inline SPA** in `web_ui.py` (HTML/CSS/JS as a Python string constant `UI_HTML`)

## Versioning

Version must be updated in **two** files simultaneously:
- `thread2mqtt/app/__init__.py` → `__version__ = "X.Y.Z"`
- `thread2mqtt/config.yaml` → `version: "X.Y.Z"`

## Testing

- Framework: `pytest` (no config file, no conftest.py)
- Tests use `asyncio.run()` directly, not `@pytest.mark.asyncio`
- Test files: `thread2mqtt/tests/test_*.py`
- Always run `python -m py_compile` on changed modules before committing

## Add-on Configuration

- `config.yaml` — HA add-on manifest: options, schema, arch, ingress
- `run.sh` — s6/bashio entrypoint, starts matter-server then the bridge
- `translations/en.yaml` — English labels for the HA options UI
- `build.yaml` — base image per architecture (Debian bookworm)

## Pitfalls

- The web UI IP allowlist (`ALLOWED_REMOTES`) restricts access to `127.0.0.1`, `::1`, `172.30.32.2`. External access goes through HA ingress only.
- `commission_on_network` needs the **device's own IP** (IPv6 `fd…` for Thread), never the HA host IP.
- BLE commissioning requires `bluez` in the container + host Bluetooth hardware.
- `matter.commissioning_ip` in add-on options auto-fills the IP for manual codes (factory sticker codes).
=======
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
>>>>>>> 37decee854c6d90e0e23c739db02fc9ffa27e7cb
