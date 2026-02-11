#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

HUB_PORT="${FREEZER_HUB_PORT:-8099}"
UDP_PORT="${FREEZER_UDP_PORT:-50555}"

VENV_PY="./venv/bin/python"
LOGS="./logs"
mkdir -p "$LOGS"

echo "🧊 Freezer Orpheus START"
echo "root=$(pwd)"
echo "hub_port=${HUB_PORT} udp_port=${UDP_PORT}"
echo

# --- hard stop any existing freezer processes to avoid duplicate UDP bind ---
./scripts/freezer_stop_orpheus.sh >/dev/null 2>&1 || true

# --- sanity: venv python must exist ---
if [[ ! -x "$VENV_PY" ]]; then
  echo "❌ venv python missing at $VENV_PY"
  exit 1
fi

# --- start daemon (local UDP listener) ---
echo "▶ starting daemon..."
$VENV_PY ./freezer_daemon.py --udp-port "${UDP_PORT}" > "$LOGS/freezer_daemon.out" 2>&1 &
echo $! > "$LOGS/freezer_daemon.pid"

# --- start hub (HTTP server) ---
echo "▶ starting hub..."
$VENV_PY ./freezer_hub.py > "$LOGS/freezer_hub.out" 2>&1 &
echo $! > "$LOGS/freezer_hub.pid"

sleep 0.6

HUB_PID="$(cat "$LOGS/freezer_hub.pid" 2>/dev/null || true)"
DAEMON_PID="$(cat "$LOGS/freezer_daemon.pid" 2>/dev/null || true)"

echo
echo "✅ running: hub pid=${HUB_PID:-?} daemon pid=${DAEMON_PID:-?}"
echo
echo "🌐 Open UI:"
echo "  http://localhost:${HUB_PORT}/ui/freezer_ui.html"
echo

echo "🔎 Ports (expect TCP ${HUB_PORT} + UDP ${UDP_PORT}):"
ss -lntup 2>/dev/null | grep -E ":((${HUB_PORT})|(${UDP_PORT}))\b" || true
echo

echo "🧪 Smoke (JSON):"
curl -s "http://localhost:${HUB_PORT}/api/state" 2>/dev/null | head -c 200; echo
curl -s "http://localhost:${HUB_PORT}/api/nodes" 2>/dev/null | head -c 200; echo
curl -s "http://localhost:${HUB_PORT}/api/events?limit=2" 2>/dev/null | head -c 200; echo
echo

echo "📄 Recent events:"
tail -n 3 "$LOGS/freezer_events.jsonl" 2>/dev/null || true
