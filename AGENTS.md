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
