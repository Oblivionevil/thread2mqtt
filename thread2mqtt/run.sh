#!/command/with-contenv bashio
set -euo pipefail

MATTER_HOST="$(bashio::config 'matter.host')"
MATTER_PORT="$(bashio::config 'matter.port')"
MATTER_LISTEN_ADDRESS="$(bashio::config 'matter.listen_address')"
MATTER_STORAGE="/data/matter"

mkdir -p "${MATTER_STORAGE}"

if nc -z "${MATTER_HOST}" "${MATTER_PORT}" 2>/dev/null; then
    bashio::log.error "Matter port ${MATTER_PORT} on ${MATTER_HOST} is already in use. Set matter.port to a free port in the add-on options."
    exit 1
fi

# ── Start python-matter-server in the background ──────────────────
bashio::log.info "Starting Matter Server on port ${MATTER_PORT}"
MATTER_ARGS=(
    --storage-path "${MATTER_STORAGE}"
    --port "${MATTER_PORT}"
    --log-level info
)

if [ -n "${MATTER_LISTEN_ADDRESS}" ]; then
    MATTER_ARGS+=(--listen-address "${MATTER_LISTEN_ADDRESS}")
fi

BLUETOOTH_ADAPTER="$(bashio::config 'matter.bluetooth_adapter' || echo '')"
if [ -n "${BLUETOOTH_ADAPTER}" ]; then
    bashio::log.info "Bluetooth adapter configured: hci${BLUETOOTH_ADAPTER}"
    MATTER_ARGS+=(--bluetooth-adapter "${BLUETOOTH_ADAPTER}")
fi

matter-server "${MATTER_ARGS[@]}" &
MATTER_PID=$!

cleanup() {
    bashio::log.info "Stopping Matter Server (PID ${MATTER_PID})"
    kill "${MATTER_PID}" 2>/dev/null || true
    wait "${MATTER_PID}" 2>/dev/null || true
}
trap cleanup EXIT TERM INT

# Wait for the WebSocket port to be available
bashio::log.info "Waiting for Matter Server to initialize …"
READY=0
for i in $(seq 1 30); do
    if nc -z "${MATTER_HOST}" "${MATTER_PORT}" 2>/dev/null; then
        bashio::log.info "Matter Server is ready"
        READY=1
        break
    fi
    if ! kill -0 "${MATTER_PID}" 2>/dev/null; then
        bashio::log.error "Matter Server process died"
        exit 1
    fi
    sleep 1
done

if [ "${READY}" -ne 1 ]; then
    bashio::log.error "Matter Server did not become ready within 30 seconds"
    exit 1
fi

# ── Start the Thread2MQTT bridge ──────────────────────────────────
bashio::log.info "Starting Thread2MQTT bridge"
cd /opt/thread2mqtt
python3 -m app.main
EXIT_CODE=$?

cleanup
exit ${EXIT_CODE}