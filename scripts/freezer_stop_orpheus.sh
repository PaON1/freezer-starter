#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

HUB_PORT="${FREEZER_HUB_PORT:-8099}"
UDP_PORT="${FREEZER_UDP_PORT:-50555}"
LOGS="./logs"

echo "🧊 Freezer Orpheus STOP"
echo "root=$(pwd)"
echo

kill_pidfile() {
  local name="$1"
  local pidfile="$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "⏹ stopping $name pid=$pid"
      kill "$pid" 2>/dev/null || true
      sleep 0.3
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
}

# stop by pidfiles first
kill_pidfile "hub"    "$LOGS/freezer_hub.pid"
kill_pidfile "daemon" "$LOGS/freezer_daemon.pid"

# then kill any stragglers (covers old runs / stale pidfiles)
echo "🧹 cleaning stragglers..."
pkill -f "freezer_hub.py" 2>/dev/null || true
pkill -f "freezer_daemon.py" 2>/dev/null || true

# show remaining binds if any
echo
echo "🔎 Remaining binds (should be empty):"
ss -lntup 2>/dev/null | grep -E ":((${HUB_PORT})|(${UDP_PORT}))\b" || true

echo
echo "✅ stopped."
