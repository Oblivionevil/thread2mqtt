"""Built-in web UI for Thread2MQTT."""

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
from .matter_client import MatterClient, MatterClientError
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
      --bg: #0d1617;
      --panel: rgba(17, 29, 31, 0.88);
      --panel-strong: rgba(25, 40, 43, 0.95);
      --line: rgba(166, 214, 205, 0.15);
      --text: #eef7f5;
      --muted: #9db7b2;
      --accent: #ff8c40;
      --accent-soft: rgba(255, 140, 64, 0.16);
      --success: #55cea4;
      --danger: #ff7676;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.3);
      --radius: 22px;
      --font: "Avenir Next", "Segoe UI Variable", "IBM Plex Sans", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--font);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(255, 140, 64, 0.22), transparent 28%),
        radial-gradient(circle at top right, rgba(85, 206, 164, 0.14), transparent 22%),
        linear-gradient(180deg, #102022 0%, #091011 100%);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
      background-size: 30px 30px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.45), transparent 90%);
    }

    .shell {
      width: min(1360px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 20px 0 36px;
    }

    .hero,
    .panel,
    .device-card {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }

    .hero {
      padding: 28px;
      background:
        linear-gradient(135deg, var(--accent-soft), transparent 40%),
        linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02)),
        var(--panel-strong);
    }

    .eyebrow {
      margin-bottom: 10px;
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.18em;
    }

    h1 {
      margin: 0;
      max-width: 10ch;
      font-size: clamp(34px, 6vw, 58px);
      line-height: 0.94;
      letter-spacing: -0.045em;
    }

    .hero p,
    .panel p,
    .subtle {
      color: var(--muted);
      line-height: 1.6;
    }

    .hero p {
      margin: 14px 0 20px;
      max-width: 64ch;
      font-size: 16px;
    }

    .toolbar,
    .actions-row,
    .device-actions,
    .range-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }

    .layout {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 18px;
      margin-top: 18px;
    }

    .panel {
      padding: 22px;
    }

    .bridge-panel { grid-column: span 7; }
    .commission-panel { grid-column: span 5; }
    .devices-panel { grid-column: 1 / -1; }

    h2,
    h3 {
      margin: 0 0 8px;
      letter-spacing: -0.03em;
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 14px;
      margin-top: 18px;
    }

    .stat {
      padding: 16px;
      border-radius: 18px;
      border: 1px solid rgba(255,255,255,0.06);
      background: rgba(255,255,255,0.03);
    }

    .stat-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
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
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    input,
    textarea,
    button {
      font: inherit;
    }

    input,
    textarea {
      width: 100%;
      padding: 14px 15px;
      color: var(--text);
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(7, 13, 14, 0.72);
      outline: none;
    }

    input:focus,
    textarea:focus {
      border-color: rgba(255, 140, 64, 0.7);
      box-shadow: 0 0 0 4px rgba(255, 140, 64, 0.16);
    }

    button {
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      cursor: pointer;
      font-weight: 700;
      color: #1b140d;
      background: linear-gradient(135deg, #ffb56c, var(--accent));
      box-shadow: 0 14px 26px rgba(255, 140, 64, 0.24);
      transition: transform 0.16s ease, opacity 0.16s ease;
    }

    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.55; cursor: wait; transform: none; }

    .ghost {
      color: var(--text);
      background: rgba(255,255,255,0.05);
      border: 1px solid var(--line);
      box-shadow: none;
    }

    .danger {
      color: white;
      background: linear-gradient(135deg, #ff9797, var(--danger));
      box-shadow: 0 14px 26px rgba(255, 118, 118, 0.22);
    }

    .update-info {
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(85, 206, 164, 0.08);
      border: 1px solid rgba(85, 206, 164, 0.25);
    }

    .update-info h4 { margin: 0 0 8px; color: var(--success); font-size: 14px; }
    .update-info .update-detail { font-size: 13px; color: var(--muted); margin-bottom: 4px; }
    .update-info .update-actions { margin-top: 10px; }

    .flash {
      display: none;
      margin-top: 18px;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
    }

    .flash.success {
      display: block;
      background: rgba(85, 206, 164, 0.12);
      border-color: rgba(85, 206, 164, 0.35);
    }

    .flash.error {
      display: block;
      background: rgba(255, 118, 118, 0.12);
      border-color: rgba(255, 118, 118, 0.4);
    }

    .device-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-top: 18px;
    }

    .device-card {
      padding: 18px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02)),
        var(--panel);
    }

    .device-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }

    .pills,
    .state-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    .pill,
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      border-radius: 999px;
      padding: 7px 10px;
      border: 1px solid rgba(255,255,255,0.06);
      background: rgba(255,255,255,0.05);
      color: var(--muted);
    }

    .status-online {
      color: #052118;
      background: rgba(85, 206, 164, 0.95);
      border-color: transparent;
    }

    .status-offline {
      color: white;
      background: rgba(255, 118, 118, 0.84);
      border-color: transparent;
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
      background: rgba(4, 8, 9, 0.74);
      overflow: auto;
      font-size: 12px;
      border: 1px solid rgba(255,255,255,0.05);
    }

    .empty {
      padding: 24px;
      color: var(--muted);
      text-align: center;
      border-radius: 18px;
      border: 1px dashed rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.02);
    }

    .detail-grid {
      display: grid;
      gap: 4px;
      margin-top: 10px;
    }

    .detail-row {
      display: flex;
      gap: 12px;
      font-size: 13px;
      padding: 4px 0;
      border-bottom: 1px solid rgba(255,255,255,0.04);
    }

    .detail-label {
      color: var(--muted);
      min-width: 100px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .hint {
      font-size: 12px;
      color: var(--muted);
      line-height: 1.5;
      margin: 4px 0 8px;
    }

    @media (max-width: 960px) {
      .bridge-panel,
      .commission-panel,
      .devices-panel {
        grid-column: 1 / -1;
      }

      .shell {
        width: min(100vw - 18px, 1360px);
      }

      .hero,
      .panel,
      .device-card {
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
        Inspect the bridge, commission on-network Matter devices, and operate supported nodes from the same runtime that serves MQTT.
      </p>
      <div class="toolbar">
        <button type="button" onclick="refreshOverview(true)">Refresh view</button>
        <button type="button" class="ghost" onclick="reloadBridge()">Reload bridge snapshot</button>
      </div>
      <div id="flash" class="flash"></div>
    </section>

    <section class="layout">
      <section class="panel bridge-panel">
        <h2>Bridge status</h2>
        <p>Live OTBR, dataset, MQTT and Matter runtime visibility.</p>
        <div id="bridge-stats" class="stats"></div>
      </section>

      <section class="panel commission-panel">
        <h2>Commission device</h2>
        <p>
          <strong>Important:</strong> this add-on has <em>no Bluetooth</em>. That means a brand-new Matter device
          (only the factory sticker code) cannot be onboarded here &mdash; initial commissioning needs BLE. Use the
          Home Assistant Companion app, the Google/Apple/Samsung app, or another BLE-capable controller for the
          first pairing, then use <em>Share device / multi-admin</em> to get an 11-digit share code and paste that
          here. The sticker code only works if the device still has an open commissioning window.
        </p>
        <p>
          Leave the target IP empty for normal discovery-based commissioning (mDNS on the fabric). Set a target IP
          only when you know the device's own IP (for Thread devices that is an IPv6 <code>fd&hellip;</code>
          address from the Border Router &mdash; <strong>not</strong> the Home Assistant host IP). The IP path needs
          a manual pairing code or an explicit setup PIN.
        </p>
        <form id="commission-form">
          <label>
            Pairing code
            <textarea id="commission-code" rows="4" placeholder="MT:... or 11/21-digit manual code (share code preferred)"></textarea>
          </label>
          <label>
            Target IP (optional, device IP only)
            <input id="commission-ip" type="text" placeholder="e.g. fd12:3456::abcd for Thread, or LAN IPv4 of the device">
          </label>
          <p class="hint">
            The grey text is only a placeholder. Do <strong>not</strong> put the Home Assistant host IP here &mdash;
            that will fail with &ldquo;Invalid PASE parameter&rdquo;. Leave the field empty unless you truly know
            the device's own address.
          </p>
          <div class="actions-row">
            <button type="submit">Start commissioning</button>
          </div>
        </form>
      </section>

      <section class="panel devices-panel">
        <h2>Devices</h2>
        <p id="devices-subtitle">No data yet.</p>
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

    function humanize(value) {
      return String(value).replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
    }

    function setFlash(message, variant = 'success') {
      const flash = document.getElementById('flash');
      flash.textContent = message;
      flash.className = `flash ${variant}`;
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

    function renderStats(overview) {
      const bridge = overview.bridge || {};
      const matter = overview.matter || {};
      const serverInfo = matter.server_info || {};
      const stats = [
        ['Bridge', bridge.dataset_loaded ? 'Online' : 'Booting'],
        ['Dataset source', bridge.dataset_source || 'unknown'],
        ['OTBR reachable', bridge.otbr_reachable ? 'Yes' : 'No'],
        ['Managed devices', overview.devices.length],
        ['Matter endpoint', matter.url || 'n/a'],
        ['Matter connected', matter.connected ? 'Yes' : 'No'],
        ['Thread dataset in Matter', serverInfo.thread_credentials_set ? 'Loaded' : 'Missing'],
        ['Commissioning mode', serverInfo.bluetooth_enabled ? 'Bluetooth + network' : 'Network only'],
        ['Default commission IP', matter.default_commission_ip || 'Not set'],
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

    function renderState(device) {
      const entries = Object.entries(device.state || {});
      if (!entries.length) {
        return '<div class="chip">No reported state yet</div>';
      }

      return entries.map(([key, value]) => `
        <div class="chip"><strong>${escapeHtml(humanize(key))}:</strong> ${escapeHtml(value)}</div>
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
      const endpoints = device.endpoints || {};
      const epCount = Object.keys(endpoints).length;

      return `
        <article class="device-card">
          <div class="device-head">
            <div>
              <h3 id="name-display-${device.node_id}">${escapeHtml(device.friendly_name)}</h3>
              <div class="subtle">${escapeHtml(device.vendor_name)} / ${escapeHtml(device.product_name)}</div>
            </div>
            <div class="pill ${device.available ? 'status-online' : 'status-offline'}">
              ${device.available ? 'Online' : 'Offline'}
            </div>
          </div>

          <div class="pills">
            <div class="pill">Node ${escapeHtml(device.node_id)}</div>
            <div class="pill">${escapeHtml(device.unique_id)}</div>
            ${device.serial_number ? `<div class="pill">S/N ${escapeHtml(device.serial_number)}</div>` : ''}
            ${device.vendor_id != null ? `<div class="pill">VID ${escapeHtml(device.vendor_id)}</div>` : ''}
            ${device.product_id != null ? `<div class="pill">PID ${escapeHtml(device.product_id)}</div>` : ''}
            <div class="pill">${epCount} endpoint(s)</div>
            ${renderCapabilities(device)}
          </div>

          <div class="state-chips">${renderState(device)}</div>

          <div class="device-actions" style="margin-top:14px;">
            ${canSwitch ? `<button type="button" onclick="sendDeviceCommand(${device.node_id}, {state: 'ON'})">On</button>
            <button type="button" class="ghost" onclick="sendDeviceCommand(${device.node_id}, {state: 'OFF'})">Off</button>` : ''}
            <button type="button" class="ghost" onclick="refreshDevice(${device.node_id})">Refresh</button>
            <button type="button" class="ghost" onclick="pingDevice(${device.node_id})">Ping</button>
            <button type="button" class="ghost" onclick="renameDevice(${device.node_id}, '${escapeHtml(device.friendly_name)}')">Rename</button>
            <button type="button" class="ghost" onclick="openCommissioningWindow(${device.node_id})">Share</button>
            <button type="button" class="ghost" onclick="checkUpdate(${device.node_id})">Check Update</button>
            <button type="button" class="danger" onclick="removeDevice(${device.node_id})">Remove</button>
          </div>

          <div id="update-info-${device.node_id}" class="update-info" style="display:none; margin-top:10px;"></div>

          ${canBrightness ? `
            <div class="range-wrap">
              <label>
                Brightness
                <input id="brightness-${device.node_id}" type="range" min="0" max="254" value="${brightness}">
              </label>
              <div class="range-actions">
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
              <div class="range-actions">
                <button type="button" class="ghost" onclick="applyColorTemp(${device.node_id})">Apply color temperature</button>
              </div>
            </div>
          ` : ''}

          <details>
            <summary>Device details &amp; endpoints</summary>
            <div class="detail-grid">
              <div class="detail-row"><span class="detail-label">Node ID</span><span>${escapeHtml(device.node_id)}</span></div>
              <div class="detail-row"><span class="detail-label">Unique ID</span><span>${escapeHtml(device.unique_id)}</span></div>
              <div class="detail-row"><span class="detail-label">Vendor</span><span>${escapeHtml(device.vendor_name)} (${device.vendor_id ?? 'n/a'})</span></div>
              <div class="detail-row"><span class="detail-label">Product</span><span>${escapeHtml(device.product_name)} (${device.product_id ?? 'n/a'})</span></div>
              ${device.serial_number ? `<div class="detail-row"><span class="detail-label">Serial</span><span>${escapeHtml(device.serial_number)}</span></div>` : ''}
              ${device.node_label ? `<div class="detail-row"><span class="detail-label">Node label</span><span>${escapeHtml(device.node_label)}</span></div>` : ''}
            </div>
            ${Object.entries(endpoints).map(([epId, ep]) => `
              <div style="margin-top:10px;">
                <strong>Endpoint ${escapeHtml(epId)}</strong>
                <span class="subtle"> — Device types: ${(ep.device_type_ids || []).map(id => '0x' + id.toString(16).toUpperCase().padStart(4, '0')).join(', ') || 'none'}</span>
                <div class="pills" style="margin-top:6px;">
                  ${(ep.mappings || []).map(m => `<div class="pill">${escapeHtml(m.platform)}:${escapeHtml(m.key)} (${m.cluster}/${m.attribute})</div>`).join('')}
                </div>
              </div>
            `).join('')}
          </details>

          <details>
            <summary>Raw state payload</summary>
            <pre>${escapeHtml(JSON.stringify(device.state || {}, null, 2))}</pre>
          </details>
        </article>
      `;
    }

    function renderDevices(overview) {
      const devices = overview.devices || [];
      document.getElementById('devices-subtitle').textContent = `${devices.length} device(s) known to the bridge.`;

      if (!devices.length) {
        document.getElementById('device-grid').innerHTML = '<div class="empty">No commissioned devices yet. Start with a Matter pairing code above.</div>';
        return;
      }

      // Preserve open <details> and update-info panels across re-renders
      const openDetails = {};
      const updatePanels = {};
      document.querySelectorAll('.device-card').forEach(card => {
        const nodeId = card.querySelector('[id^="name-display-"]')?.id?.replace('name-display-', '');
        if (!nodeId) return;
        openDetails[nodeId] = [...card.querySelectorAll('details')].map(d => d.open);
        const up = card.querySelector(`[id^="update-info-"]`);
        if (up && up.style.display !== 'none') {
          updatePanels[nodeId] = up.innerHTML;
        }
      });

      document.getElementById('device-grid').innerHTML = devices.map(renderDeviceCard).join('');

      // Restore open <details> and update-info panels
      devices.forEach(device => {
        const nid = String(device.node_id);
        if (openDetails[nid]) {
          const card = document.getElementById(`name-display-${nid}`)?.closest('.device-card');
          if (card) {
            [...card.querySelectorAll('details')].forEach((d, i) => {
              if (openDetails[nid][i]) d.open = true;
            });
          }
        }
        if (updatePanels[nid]) {
          const up = document.getElementById(`update-info-${nid}`);
          if (up) {
            up.style.display = 'block';
            up.innerHTML = updatePanels[nid];
          }
        }
      });
    }

    async function refreshOverview(showToast = false) {
      const overview = await api('api/overview');
      renderStats(overview);
      renderDevices(overview);
      const commissioningIp = overview.matter?.default_commission_ip || '';
      const commissionIpInput = document.getElementById('commission-ip');
      if (commissioningIp && commissionIpInput && !commissionIpInput.value.trim()) {
        commissionIpInput.value = commissioningIp;
      }
      if (showToast) {
        setFlash('Dashboard refreshed.');
      }
    }

    async function reloadBridge() {
      try {
        await api('api/bridge/refresh', { method: 'POST', body: '{}' });
        await refreshOverview(false);
        setFlash('Bridge snapshot reloaded.');
      } catch (error) {
        setFlash(error.message, 'error');
      }
    }

    async function sendDeviceCommand(nodeId, payload) {
      try {
        await api(`api/device/${nodeId}/command`, { method: 'POST', body: JSON.stringify(payload) });
        setFlash('Command sent.');
        window.setTimeout(() => refreshOverview(false), 700);
      } catch (error) {
        setFlash(error.message, 'error');
      }
    }

    async function refreshDevice(nodeId) {
      try {
        await api(`api/device/${nodeId}/refresh`, { method: 'POST', body: '{}' });
        setFlash('Interview requested.');
        window.setTimeout(() => refreshOverview(false), 700);
      } catch (error) {
        setFlash(error.message, 'error');
      }
    }

    async function removeDevice(nodeId) {
      if (!window.confirm(`Remove node ${nodeId} from the fabric?`)) {
        return;
      }
      try {
        await api(`api/device/${nodeId}`, { method: 'DELETE' });
        setFlash('Device removal requested.');
        window.setTimeout(() => refreshOverview(false), 700);
      } catch (error) {
        setFlash(error.message, 'error');
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

    async function renameDevice(nodeId, currentName) {
      const newName = window.prompt('New name for this device:', currentName);
      if (!newName || newName.trim() === currentName) {
        return;
      }
      try {
        await api(`api/device/${nodeId}/rename`, { method: 'POST', body: JSON.stringify({ name: newName.trim() }) });
        setFlash(`Renamed node ${nodeId} to "${newName.trim()}".`);
        window.setTimeout(() => refreshOverview(false), 400);
      } catch (error) {
        setFlash(error.message, 'error');
      }
    }

    async function pingDevice(nodeId) {
      try {
        const result = await api(`api/device/${nodeId}/ping`, { method: 'POST', body: '{}' });
        setFlash(`Ping node ${nodeId}: reachable.`);
      } catch (error) {
        setFlash(`Ping node ${nodeId} failed: ${error.message}`, 'error');
      }
    }

    async function openCommissioningWindow(nodeId) {
      if (!window.confirm(`Open a commissioning window on node ${nodeId}? This allows another controller to add this device (multi-admin).`)) {
        return;
      }
      try {
        const result = await api(`api/device/${nodeId}/open-commissioning-window`, { method: 'POST', body: '{}' });
        setFlash(`Commissioning window opened for node ${nodeId}. The device is now discoverable for ~3 minutes.`);
      } catch (error) {
        setFlash(error.message, 'error');
      }
    }

    async function checkUpdate(nodeId) {
      const panel = document.getElementById(`update-info-${nodeId}`);
      panel.style.display = 'block';
      panel.innerHTML = '<div class="update-detail">Checking for updates…</div>';
      try {
        const result = await api(`api/device/${nodeId}/check-update`, { method: 'POST', body: '{}' });
        if (result.update_available && result.update_info) {
          const info = result.update_info;
          const swVersion = info.software_version != null ? info.software_version : '';
          panel.innerHTML = `
            <h4>Update available</h4>
            ${info.software_version_string ? `<div class="update-detail">Version: ${escapeHtml(info.software_version_string)}</div>` : ''}
            ${info.software_version != null ? `<div class="update-detail">Build: ${escapeHtml(info.software_version)}</div>` : ''}
            ${info.release_notes_url ? `<div class="update-detail"><a href="${escapeHtml(info.release_notes_url)}" target="_blank" rel="noopener" style="color:var(--accent);">Release notes</a></div>` : ''}
            <div class="update-actions">
              <button type="button" onclick="applyUpdate(${nodeId}, ${escapeHtml(String(swVersion))})">Install Update</button>
              <button type="button" class="ghost" onclick="dismissUpdate(${nodeId})">Dismiss</button>
            </div>
          `;
          setFlash(`Update available for node ${nodeId}.`);
        } else {
          panel.innerHTML = '<div class="update-detail">No update available. Device is up to date.</div>';
          setFlash(`Node ${nodeId} is up to date.`);
          window.setTimeout(() => { panel.style.display = 'none'; }, 4000);
        }
      } catch (error) {
        panel.innerHTML = `<div class="update-detail" style="color:var(--danger);">${escapeHtml(error.message)}</div>`;
        setFlash(error.message, 'error');
      }
    }

    async function applyUpdate(nodeId, softwareVersion) {
      if (!window.confirm(`Install the software update on node ${nodeId}? The device may restart during the update.`)) {
        return;
      }
      const panel = document.getElementById(`update-info-${nodeId}`);
      panel.innerHTML = '<div class="update-detail">Starting update… This may take several minutes.</div>';
      try {
        await api(`api/device/${nodeId}/update`, { method: 'POST', body: JSON.stringify({ software_version: softwareVersion }) });
        panel.innerHTML = '<div class="update-detail" style="color:var(--success);">Update started. The device will restart when complete.</div>';
        setFlash(`Update started on node ${nodeId}.`);
      } catch (error) {
        panel.innerHTML = `<div class="update-detail" style="color:var(--danger);">Update failed: ${escapeHtml(error.message)}</div>`;
        setFlash(error.message, 'error');
      }
    }

    function dismissUpdate(nodeId) {
      const panel = document.getElementById(`update-info-${nodeId}`);
      panel.style.display = 'none';
    }

    document.getElementById('commission-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const code = document.getElementById('commission-code').value.trim();
      const ip = document.getElementById('commission-ip').value.trim();
      if (!code) {
        setFlash('Enter a Matter pairing code first.', 'error');
        return;
      }

      if (!ip) {
        const proceed = window.confirm(
          'No target IP entered. The add-on will fall back to mDNS discovery, which usually fails for devices '
          + 'that do not advertise themselves. Continue anyway?'
        );
        if (!proceed) {
          return;
        }
      }

      try {
        const payload = { code };
        if (ip) {
          payload.ip = ip;
        }
        await api('api/commission', { method: 'POST', body: JSON.stringify(payload) });
        document.getElementById('commission-code').value = '';
        setFlash(ip ? `IP-directed commissioning started (${ip}).` : 'Discovery-based commissioning started.');
      } catch (error) {
        setFlash(error.message, 'error');
      }
    });

    refreshOverview(false).catch((error) => setFlash(error.message, 'error'));
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
        """Start the ingress web UI server."""

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
                web.post(r"/api/device/{node_id:\\d+}/rename", self._handle_device_rename),
                web.post(r"/api/device/{node_id:\\d+}/ping", self._handle_device_ping),
                web.post(r"/api/device/{node_id:\\d+}/open-commissioning-window", self._handle_open_commissioning_window),
                web.post(r"/api/device/{node_id:\\d+}/check-update", self._handle_check_update),
                web.post(r"/api/device/{node_id:\\d+}/update", self._handle_update),
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
        code_value = payload.get("code")
        code = str(code_value).strip() if code_value is not None else ""
        ip_addr = str(payload.get("ip") or payload.get("ip_addr") or "").strip()

        try:
            setup_pin_code = self._parse_setup_pin_code(payload.get("setup_pin_code", payload.get("setup_pin")))
        except ValueError as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err

        if not code and setup_pin_code is None:
            raise self._json_error(web.HTTPBadRequest, "Missing Matter pairing code or setup_pin_code")

        router = self._require_command_router()
        try:
            await router.commission(code or None, ip_addr=ip_addr or None, setup_pin_code=setup_pin_code)
        except MatterClientError as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err
        return web.json_response({"ok": True})

    async def _handle_device_command(self, request: web.Request) -> web.Response:
        payload = await self._read_json(request)
        node_id = int(request.match_info["node_id"])
        router = self._require_command_router()
        try:
            await router.set_device_by_node(node_id, payload)
        except (MatterClientError, ValueError) as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err
        return web.json_response({"ok": True})

    async def _handle_device_refresh(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        router = self._require_command_router()
        try:
            await router.refresh_device_by_node(node_id)
        except (MatterClientError, ValueError) as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err
        return web.json_response({"ok": True})

    async def _handle_device_remove(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        router = self._require_command_router()
        try:
            await router.remove_node(node_id)
        except (MatterClientError, ValueError) as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err
        return web.json_response({"ok": True})

    async def _handle_device_rename(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        payload = await self._read_json(request)
        new_name = str(payload.get("name", "")).strip()
        if not new_name:
            raise self._json_error(web.HTTPBadRequest, "Missing or empty 'name' field")
        if not self._registry.rename_device(node_id, new_name):
            raise self._json_error(web.HTTPBadRequest, f"Unknown node_id: {node_id}")
        LOGGER.info("Renamed node %d to '%s'", node_id, new_name)
        return web.json_response({"ok": True})

    async def _handle_device_ping(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        self._require_command_router()
        try:
            result = await self._matter_client.ping_node(node_id)
        except MatterClientError as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err
        return web.json_response({"ok": True, "result": result})

    async def _handle_open_commissioning_window(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        self._require_command_router()
        try:
            result = await self._matter_client.open_commissioning_window(node_id)
        except MatterClientError as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err
        return web.json_response({"ok": True, "result": result})

    async def _handle_check_update(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        self._require_command_router()
        try:
            result = await self._matter_client.check_node_update(node_id)
        except MatterClientError as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err
        return web.json_response({"ok": True, "update_available": result is not None, "update_info": result})

    async def _handle_update(self, request: web.Request) -> web.Response:
        node_id = int(request.match_info["node_id"])
        self._require_command_router()
        payload = await self._read_json(request)
        software_version = payload.get("software_version")
        if software_version is None:
            raise self._json_error(web.HTTPBadRequest, "Missing 'software_version' in payload")
        try:
            result = await self._matter_client.update_node(node_id, software_version)
        except MatterClientError as err:
            raise self._json_error(web.HTTPBadRequest, str(err)) from err
        return web.json_response({"ok": True, "result": result})

    def _build_overview(self, request: web.Request | None = None) -> dict[str, Any]:
        devices = sorted(self._registry.devices.values(), key=lambda device: device.friendly_name.lower())
        matter_connected = bool(self._matter_client and self._matter_client.connected)

        return {
            "bridge": self._bridge.last_snapshot,
            "matter": {
                "enabled": self._config.matter.enabled,
                "connected": matter_connected,
                "url": self._config.matter.server_url,
                "default_commission_ip": self._config.matter.commissioning_ip,
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
        capabilities = sorted(device.get_capabilities())
        state = device.get_state_payload()
        return {
            "node_id": device.node_id,
            "unique_id": device.unique_id,
            "friendly_name": device.friendly_name,
            "vendor_name": device.vendor_name,
            "product_name": device.product_name,
            "vendor_id": device.vendor_id,
            "product_id": device.product_id,
            "serial_number": device.serial_number,
            "node_label": device.node_label,
            "available": device.available,
            "state": state,
            "capabilities": capabilities,
            "endpoints": {
                str(ep_id): {
                    "device_type_ids": ep.device_type_ids,
                    "mappings": [
                        {"platform": m.ha_platform, "key": m.attribute_key, "cluster": m.cluster_id, "attribute": m.attribute_id}
                        for m in ep.entity_mappings
                    ],
                }
                for ep_id, ep in device.endpoints.items()
            },
            "controls": {
                "state": device.get_endpoint_for_command("state") is not None,
                "brightness": device.get_endpoint_for_command("brightness") is not None,
                "color_temp": device.get_endpoint_for_command("color_temp") is not None,
            },
        }

    @staticmethod
    async def _read_json(request: web.Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except json.JSONDecodeError as err:
            raise Thread2MqttWebUi._json_error(
                web.HTTPBadRequest,
                f"Invalid JSON payload: {err}",
            ) from err
        if not isinstance(data, dict):
            raise Thread2MqttWebUi._json_error(
                web.HTTPBadRequest,
                "JSON payload must be an object",
            )
        return data

    def _require_command_router(self) -> CommandRouter:
        if not self._command_router or not self._matter_client or not self._matter_client.connected:
            raise self._json_error(web.HTTPServiceUnavailable, "Matter controller is not connected")
        return self._command_router

    @staticmethod
    def _json_error(error_type: type[web.HTTPException], message: str) -> web.HTTPException:
        return error_type(text=json.dumps({"error": message}), content_type="application/json")

    @staticmethod
    def _is_allowed_remote(remote: str | None) -> bool:
        if not remote:
            return False
        try:
            return str(ip_address(remote)) in ALLOWED_REMOTES
        except ValueError:
            return False

    @staticmethod
    def _parse_setup_pin_code(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as err:
            raise ValueError("setup_pin_code must be an integer") from err
