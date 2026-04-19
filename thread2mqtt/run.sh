#!/command/with-contenv bashio
set -euo pipefail

MATTER_PORT=5580
MATTER_STORAGE="/data/matter"

mkdir -p "${MATTER_STORAGE}"

# ── Start python-matter-server in the background ──────────────────
bashio::log.info "Starting Matter Server on port ${MATTER_PORT}"
matter-server \
    --storage-path "${MATTER_STORAGE}" \
    --port "${MATTER_PORT}" \
    --log-level info &
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
    if nc -z localhost "${MATTER_PORT}" 2>/dev/null; then
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