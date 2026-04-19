"""Web UI for Thread2MQTT."""

from __future__ import annotations

from ipaddress import ip_address
import json
import logging
from typing import Any

from aiohttp import web

from . import __version__
from .command_router import CommandRouter
from .config import AppConfig
from .device_registry import Device, DeviceRegistry
from .matter_client import MatterClient
from .mqtt_bridge import Thread2MqttBridge


LOGGER = logging.getLogger(__name__)
INGRESS_PORT = 8099
ALLOWED_REMOTES = {"127.0.0.1", "::1", "172.30.32.2"}

UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <base href="./">
  <title>Thread2MQTT</title>
  <style>
    :root {
      --bg: #0e1516;
      --panel: rgba(18, 28, 30, 0.86);
      --panel-strong: rgba(27, 41, 44, 0.94);
      --line: rgba(153, 201, 193, 0.18);
      --text: #edf7f4;
      --muted: #9bb7b1;
      --accent: #ff8a3d;
      --accent-soft: rgba(255, 138, 61, 0.16);
      --success: #4ed0a8;
      --danger: #ff6b6b;
      --shadow: 0 28px 70px rgba(0, 0, 0, 0.28);
      --radius: 22px;
      --font: "Avenir Next", "Segoe UI Variable", "IBM Plex Sans", "Trebuchet MS", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--font);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(255, 138, 61, 0.22), transparent 32%),
        radial-gradient(circle at top right, rgba(78, 208, 168, 0.16), transparent 24%),
        linear-gradient(180deg, #102022 0%, #0a1112 100%);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 32px 32px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.45), transparent 90%);
    }

    .shell {
      width: min(1400px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }

    .hero {
      position: relative;
      overflow: hidden;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: calc(var(--radius) + 6px);
      background:
        linear-gradient(135deg, rgba(255, 138, 61, 0.12), transparent 38%),
        linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02)),
        var(--panel-strong);
      box-shadow: var(--shadow);
    }

    .eyebrow {
      margin-bottom: 10px;
      color: var(--accent);
      letter-spacing: 0.18em;
      text-transform: uppercase;
      font-size: 12px;
      font-weight: 700;
    }

    h1 {
      margin: 0;
      font-size: clamp(34px, 5vw, 58px);
      line-height: 0.95;
      letter-spacing: -0.04em;
      max-width: 10ch;
    }

    .hero p {
      max-width: 64ch;
      margin: 14px 0 20px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.6;
    }

    .hero-actions,
    .actions-row,
    .device-actions,
    .command-row {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }

    .layout {
      display: grid;
      gap: 18px;
      margin-top: 18px;
      grid-template-columns: repeat(12, minmax(0, 1fr));
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 22px;
      backdrop-filter: blur(10px);
    }

    .panel h2,
    .device-header h3 {
      margin: 0 0 6px;
      font-size: 22px;
      letter-spacing: -0.03em;
    }

    .panel p,
    .subtle {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }

    .bridge-panel { grid-column: span 7; }
    .commission-panel { grid-column: span 5; }
    .devices-panel { grid-column: 1 / -1; }

    .stat-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 14px;
      margin-top: 18px;
    }

    .stat {
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
    }

    .stat-label {
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }

    .stat-value {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.04em;
      word-break: break-word;
    }

    form {
      display: grid;
      gap: 12px;
      margin-top: 18px;
    }

    label {
      display: grid;
      gap: 8px;
      font-size: 13px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    input,
    button,
    textarea {
      font: inherit;
    }

    input,
    textarea {
      width: 100%;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(7, 13, 14, 0.72);
      color: var(--text);
      padding: 14px 15px;
      border-radius: 16px;
      outline: none;
    }

    input:focus,
    textarea:focus {
      border-color: rgba(255, 138, 61, 0.65);
      box-shadow: 0 0 0 4px rgba(255, 138, 61, 0.16);
    }

    button {
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      cursor: pointer;
      color: #15110c;
      background: linear-gradient(135deg, #ffb36b, var(--accent));
      font-weight: 700;
      letter-spacing: 0.01em;
      transition: transform 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease;
      box-shadow: 0 14px 28px rgba(255, 138, 61, 0.25);
    }

    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.55; cursor: wait; transform: none; }

    .ghost {
      color: var(--text);
      background: rgba(255,255,255,0.05);
      box-shadow: none;
      border: 1px solid var(--line);
    }

    .danger {
      color: white;
      background: linear-gradient(135deg, #ff8f8f, var(--danger));
      box-shadow: 0 14px 28px rgba(255, 107, 107, 0.22);
    }

    .flash {
      display: none;
      margin-top: 18px;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(78, 208, 168, 0.12);
    }

    .flash.error {
      display: block;
      background: rgba(255, 107, 107, 0.12);
      border-color: rgba(255, 107, 107, 0.4);
    }

    .flash.success {
      display: block;
      background: rgba(78, 208, 168, 0.12);
      border-color: rgba(78, 208, 168, 0.35);
    }

    .device-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
      gap: 16px;
      margin-top: 20px;
    }

    .device-card {
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
    }

    .device-header {
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }

    .pill-row,
    .state-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 12px 0 0;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 7px 10px;
      background: rgba(255,255,255,0.06);
      color: var(--muted);
      font-size: 12px;
      border: 1px solid rgba(255,255,255,0.05);
    }

    .status-online {
      color: #052118;
      background: rgba(78, 208, 168, 0.95);
      border-color: transparent;
    }

    .status-offline {
      color: white;
      background: rgba(255, 107, 107, 0.85);
      border-color: transparent;
    }

    .state-chip {
      font-size: 12px;
      border-radius: 14px;
      padding: 8px 10px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255,255,255,0.07);
    }

    .range-wrap {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }

    input[type="range"] {
      padding: 0;
      background: transparent;
      box-shadow: none;
    }

    details {
      margin-top: 14px;
      border-top: 1px solid rgba(255,255,255,0.08);
      padding-top: 14px;
    }

    summary {
      cursor: pointer;
      color: var(--muted);
    }

    pre {
      margin: 10px 0 0;
      padding: 14px;
      border-radius: 16px;
      background: rgba(4, 8, 9, 0.7);
      overflow: auto;
      font-size: 12px;
      border: 1px solid rgba(255,255,255,0.05);
    }

    .empty {
      padding: 22px;
      border-radius: 18px;
      border: 1px dashed rgba(255,255,255,0.14);
      color: var(--muted);
      text-align: center;
      background: rgba(255,255,255,0.02);
    }

    @media (max-width: 960px) {
      .bridge-panel,
      .commission-panel,
      .devices-panel {
        grid-column: 1 / -1;
      }

      .shell {
        width: min(100vw - 20px, 1400px);
        padding-top: 12px;
      }

      .hero,
      .panel {
        padding: 18px;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">Matter over Thread control room</div>
      <h1>Thread fabric dashboard</h1>
      <p>
        Commission devices, inspect the bridge, and drive supported Matter endpoints from one place.
        This UI talks directly to Thread2MQTT and mirrors the same runtime used for MQTT control.
      </p>
      <div class="hero-actions">
        <button type="button" onclick="refreshOverview()">Refresh view</button>
        <button type="button" class="ghost" onclick="reloadBridge()">Reload bridge snapshot</button>
      </div>
      <div id="flash" class="flash"></div>
    </section>

    <section class="layout">
      <section class="panel bridge-panel">
        <h2>Bridge status</h2>
        <p>Live OTBR, dataset, MQTT and Matter runtime visibility.</p>
        <div id="bridge-stats" class="stat-grid"></div>
      </section>

      <section class="panel commission-panel">
        <h2>Commission device</h2>
        <p>Paste a Matter setup code or QR payload and Thread2MQTT will start commissioning on its own fabric.</p>
        <form id="commission-form">
          <label>
            Pairing code
            <textarea id="commission-code" rows="4" placeholder="MT:... or setup code"></textarea>
          </label>
          <div class="actions-row">
            <button type="submit">Start commissioning</button>
          </div>
        </form>
      </section>

      <section class="panel devices-panel">
        <div class="device-header">
          <div>
            <h2>Devices</h2>
            <p id="device-subtitle">No data yet.</p>
          </div>
        </div>
        <div id="device-grid" class="device-grid"></div>
      </section>
    </section>
  </main>

  <script>
    const POLL_INTERVAL_MS = 5000;

    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function humanize(key) {
      return key.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
    }

    function showFlash(message, variant = 'success') {
      const flash = document.getElementById('flash');
      flash.textContent = message;
      flash.className = `flash ${variant}`;
      window.clearTimeout(showFlash.timeoutId);
      showFlash.timeoutId = window.setTimeout(() => {
        flash.className = 'flash';
        flash.textContent = '';
      }, 4200);
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        ...options,
      });

      const text = await response.text();
      let data = {};
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = { message: text };
        }
      }

      if (!response.ok) {
        throw new Error(data.error || data.message || `Request failed (${response.status})`);
      }

      return data;
    }

    function renderBridge(overview) {
      const bridge = overview.bridge || {};
      const matter = overview.matter || {};
      const stats = [
        ['Bridge', bridge.dataset_loaded ? 'Online' : 'Booting'],
        ['Dataset source', bridge.dataset_source || 'unknown'],
        ['OTBR reachable', bridge.otbr_reachable ? 'Yes' : 'No'],
        ['Managed devices', overview.devices.length],
        ['Matter endpoint', matter.url || 'n/a'],
        ['Matter connected', matter.connected ? 'Yes' : 'No'],
      ];

      if (bridge.last_error) {
        stats.push(['Last error', bridge.last_error]);
      }

      document.getElementById('bridge-stats').innerHTML = stats.map(([label, value]) => `
        <div class="stat">
          <div class="stat-label">${escapeHtml(label)}</div>
          <div class="stat-value">${escapeHtml(value)}</div>
        </div>
      `).join('');
    }

    function renderStateChips(device) {
      const state = device.state || {};
      const entries = Object.entries(state);
      if (!entries.length) {
        return '<div class="state-chip">No reported state yet</div>';
      }

      return entries.map(([key, value]) => `
        <div class="state-chip"><strong>${escapeHtml(humanize(key))}:</strong> ${escapeHtml(value)}</div>
      `).join('');
    }

    function renderCapabilities(device) {
      return (device.capabilities || []).map((capability) => `
        <div class="pill">${escapeHtml(humanize(capability))}</div>
      `).join('');
    }

    function renderDeviceCard(device) {
      const brightness = Number(device.state?.brightness ?? 128);
      const colorTemp = Number(device.state?.color_temp ?? 370);
      const canSwitch = Boolean(device.controls?.state);
      const canBrightness = Boolean(device.controls?.brightness);
      const canColorTemp = Boolean(device.controls?.color_temp);

      return `
        <article class="device-card">
          <div class="device-header">
            <div>
              <h3>${escapeHtml(device.friendly_name)}</h3>
              <div class="subtle">${escapeHtml(device.vendor_name)} / ${escapeHtml(device.product_name)}</div>
            </div>
            <div class="pill ${device.available ? 'status-online' : 'status-offline'}">
              ${device.available ? 'Online' : 'Offline'}
            </div>
          </div>

          <div class="pill-row">
            <div class="pill">Node ${escapeHtml(device.node_id)}</div>
            <div class="pill">${escapeHtml(device.unique_id)}</div>
            ${(device.capabilities || []).length ? renderCapabilities(device) : ''}
          </div>

          <div class="state-row">${renderStateChips(device)}</div>

          <div class="device-actions" style="margin-top:14px;">
            ${canSwitch ? `<button type="button" onclick="sendDeviceCommand(${device.node_id}, {state: 'ON'})">On</button>
            <button type="button" class="ghost" onclick="sendDeviceCommand(${device.node_id}, {state: 'OFF'})">Off</button>` : ''}
            <button type="button" class="ghost" onclick="refreshDevice(${device.node_id})">Refresh</button>
            <button type="button" class="danger" onclick="removeDevice(${device.node_id})">Remove</button>
          </div>

          ${canBrightness ? `
            <div class="range-wrap">
              <label>
                Brightness
                <input id="brightness-${device.node_id}" type="range" min="0" max="254" value="${brightness}">
              </label>
              <div class="command-row">
                <button type="button" class="ghost" onclick="applyBrightness(${device.node_id})">Apply brightness</button>
              </div>
            </div>
          ` : ''}

          ${canColorTemp ? `
            <div class="range-wrap">
              <label>
                Color temperature
                <input id="color-${device.node_id}" type="range" min="153" max="500" value="${colorTemp}">
              </label>
              <div class="command-row">
                <button type="button" class="ghost" onclick="applyColorTemp(${device.node_id})">Apply color temperature</button>
              </div>
            </div>
          ` : ''}

          <details>
            <summary>Raw state payload</summary>
            <pre>${escapeHtml(JSON.stringify(device.state || {}, null, 2))}</pre>
          </details>
        </article>
      `;
    }

    function renderDevices(overview) {
      const devices = overview.devices || [];
      document.getElementById('device-subtitle').textContent = `${devices.length} device(s) known to the bridge.`;

      if (!devices.length) {
        document.getElementById('device-grid').innerHTML = '<div class="empty">No commissioned devices yet. Start with a Matter pairing code above.</div>';
        return;
      }

      document.getElementById('device-grid').innerHTML = devices.map(renderDeviceCard).join('');
    }

    async function refreshOverview(showToast = false) {
      const overview = await api('api/overview');
      renderBridge(overview);
      renderDevices(overview);
      if (showToast) {
        showFlash('Dashboard refreshed.');
      }
    }

    async function reloadBridge() {
      try {
        await api('api/bridge/refresh', { method: 'POST', body: '{}' });
        await refreshOverview(false);
        showFlash('Bridge snapshot reloaded.');
      } catch (error) {
        showFlash(error.message, 'error');
      }
    }

    async function sendDeviceCommand(nodeId, payload) {
      try {
        await api(`api/device/${nodeId}/command`, { method: 'POST', body: JSON.stringify(payload) });
        showFlash('Command sent.');
        window.setTimeout(() => refreshOverview(false), 700);
      } catch (error) {
        showFlash(error.message, 'error');
      }
    }

    async function refreshDevice(nodeId) {
      try {
        await api(`api/device/${nodeId}/refresh`, { method: 'POST', body: '{}' });
        showFlash('Interview requested.');
        window.setTimeout(() => refreshOverview(false), 700);
      } catch (error) {
        showFlash(error.message, 'error');
      }
    }

    async function removeDevice(nodeId) {
      if (!window.confirm(`Remove node ${nodeId} from the fabric?`)) {
        return;
      }
      try {
        await api(`api/device/${nodeId}`, { method: 'DELETE' });
        showFlash('Device removal requested.');
        window.setTimeout(() => refreshOverview(false), 700);
      } catch (error) {
        showFlash(error.message, 'error');
      }
    }

    async function applyBrightness(nodeId) {
      const input = document.getElementById(`brightness-${nodeId}`);
      await sendDeviceCommand(nodeId, { brightness: Number(input.value) });
    }

    async function applyColorTemp(nodeId) {
      const input = document.getElementById(`color-${nodeId}`);
      await sendDeviceCommand(nodeId, { color_temp: Number(input.value) });
    }

    document.getElementById('commission-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const code = document.getElementById('commission-code').value.trim();
      if (!code) {
        showFlash('Enter a Matter pairing code first.', 'error');
        return;
      }

      try {
        await api('api/commission', { method: 'POST', body: JSON.stringify({ code }) });
        document.getElementById('commission-code').value = '';
        showFlash('Commissioning started.');
      } catch (error) {
        showFlash(error.message, 'error');
      }
    });

    refreshOverview(false).catch((error) => showFlash(error.message, 'error'));
    window.setInterval(() => refreshOverview(false).catch(() => {}), POLL_INTERVAL_MS);
  </script>
</body>
</html>
"""


class Thread2MqttWebUi:
    """Built-in web UI for bridge inspection and device control."""

    def __init__(
        self,
        config: AppConfig,
        bridge: Thread2MqttBridge,
        device_registry: DeviceRegistry,
    ) -> None:
        self._config = config
        self._bridge = bridge
        self._registry = device_registry
        self._matter_client: MatterClient | None = None
        self._command_router: CommandRouter | None = None
        self._runner: web.AppRunner | None = None

    def set_runtime(self, matter_client: MatterClient, command_router: CommandRouter) -> None:
        self._matter_client = matter_client
        self._command_router = command_router

    async def start(self) -> None:
        """Start the web UI server."""

        @web.middleware
        async def ingress_only(request: web.Request, handler: web.Handler) -> web.StreamResponse:
            if not self._is_allowed_remote(request.remote):
                raise web.HTTPForbidden(text="Web UI access is allowed only through Home Assistant ingress")
            return await handler(request)

        app = web.Application(middlewares=[ingress_only])
        app.add_routes(
            [
                web.get("/", self._handle_index),
                web.get("/health", self._handle_health),
                web.get("/api/overview", self._handle_overview),
                web.post("/api/bridge/refresh", self._handle_bridge_refresh),
                web.post("/api/commission", self._handle_commission),
                web.post(r"/api/device/{node_id:\\d+}/command", self._handle_device_command),
                web.post(r"/api/device/{node_id:\\d+}/refresh", self._handle_device_refresh),
                web.delete(r"/api/device/{node_id:\\d+}", self._handle_device_remove),
            ]
        )

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host="0.0.0.0", port=INGRESS_PORT)
        await site.start()
        LOGGER.info("Web UI listening on ingress port %s", INGRESS_PORT)

    async def stop(self) -> None:
        """Stop the web UI server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None

    async def _handle_index(self, _request: web.Request) -> web.Response:
        return web.Response(text=UI_HTML, content_type="text/html")

    async def _handle_health(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "version": __version__})

    async def _handle_overview(self, request: web.Request) -> web.Response:
        return web.json_response(self._build_overview(request))

    async def _handle_bridge_refresh(self, request: web.Request) -> web.Response:
        self._bridge.refresh_and_publish("web-ui")
        return web.json_response(self._build_overview(request))

    async def _handle_commission(self, request: web.Request) -> web.Response:
        payload = await self._read_json(request)
        code = str(payload.get("code", "")).strip()
        if not code:
            raise web.HTTPBadRequest(text=json.dumps({"error": "Missing Matter pairing code"}), content_type="application/json")

        router = self._require_command_router()
        await router.commission(code)
        return web.json_response({"ok": True})

    async def _handle_device_command(self, request: web.Request) -> web.Response:
        payload = await self._read_json(request)
        node_id = int(request.match_info["node_id"])
        router = self._require_command_router()
        await router.set_device_by_node(node_id, payload)
        return web.json_response({"ok": True})

    async def _handle_device_refresh(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        router = self._require_command_router()
        await router.refresh_device_by_node(node_id)
        return web.json_response({"ok": True})

    async def _handle_device_remove(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        router = self._require_command_router()
        await router.remove_node(node_id)
        return web.json_response({"ok": True})

    def _build_overview(self, request: web.Request | None = None) -> dict[str, Any]:
        devices = sorted(self._registry.devices.values(), key=lambda device: device.friendly_name.lower())
        matter_connected = bool(self._matter_client and self._matter_client.connected)

        return {
            "bridge": self._bridge.last_snapshot,
            "matter": {
                "enabled": self._config.matter.enabled,
                "connected": matter_connected,
                "url": self._config.matter.server_url,
                "server_info": self._matter_client.server_info if self._matter_client else {},
            },
            "devices": [self._serialize_device(device) for device in devices],
            "ui": {
                "version": __version__,
                "ingress_path": request.headers.get("X-Ingress-Path", "") if request else "",
            },
        }

    @staticmethod
    def _serialize_device(device: Device) -> dict[str, Any]:
        capabilities = sorted(
            {
                mapping.attribute_key
                for endpoint in device.endpoints.values()
                for mapping in endpoint.entity_mappings
            }
        )
        state = device.get_state_payload()
        return {
            "node_id": device.node_id,
            "unique_id": device.unique_id,
            "friendly_name": device.friendly_name,
            "vendor_name": device.vendor_name,
            "product_name": device.product_name,
            "available": device.available,
            "state": state,
            "capabilities": capabilities,
            "controls": {
                "state": "state" in state,
                "brightness": "brightness" in state,
                "color_temp": "color_temp" in state,
            },
        }

    @staticmethod
    async def _read_json(request: web.Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except json.JSONDecodeError as err:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": f"Invalid JSON payload: {err}"}),
                content_type="application/json",
            ) from err
        if not isinstance(data, dict):
            raise web.HTTPBadRequest(
                text=json.dumps({"error": "JSON payload must be an object"}),
                content_type="application/json",
            )
        return data

    def _require_command_router(self) -> CommandRouter:
        if not self._command_router or not self._matter_client or not self._matter_client.connected:
            raise web.HTTPServiceUnavailable(
                text=json.dumps({"error": "Matter controller is not connected"}),
                content_type="application/json",
            )
        return self._command_router

    @staticmethod
    def _is_allowed_remote(remote: str | None) -> bool:
        if not remote:
            return False
        try:
            return str(ip_address(remote)) in ALLOWED_REMOTES
        except ValueError:
            return False