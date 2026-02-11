#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

mkdir -p logs config ui

# ---- config defaults (override via env if you want) ----
export FREEZER_HUB_PORT="${FREEZER_HUB_PORT:-8099}"
export OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-phi}"   # set to tinyllama or phi
export FREEZER_NODES="${FREEZER_NODES:-marin,dre,harry,dennis,sven,drfengle}"

# ---- helpful banner ----
echo "== Freezer start =="
echo "root: $ROOT"
echo "hub:  http://localhost:${FREEZER_HUB_PORT}"
echo "ui:   http://localhost:${FREEZER_HUB_PORT}/ui/freezer_ui.html"
echo "ollama: ${OLLAMA_URL}  model=${OLLAMA_MODEL}"
echo

# ---- sanity checks ----
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found" >&2
  exit 1
fi

# ---- stop any old hub (if pid file exists) ----
if [[ -f logs/freezer_hub.pid ]]; then
  OLD_PID="$(cat logs/freezer_hub.pid || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" >/dev/null 2>&1; then
    echo "Stopping previous hub PID=${OLD_PID}"
    kill "${OLD_PID}" || true
    sleep 0.6
  fi
  rm -f logs/freezer_hub.pid
fi

# ---- start hub ----
echo "Starting freezer_hub.py..."
nohup python3 "$ROOT/freezer_hub.py" > "$ROOT/logs/freezer_hub.out" 2>&1 &
echo $! > "$ROOT/logs/freezer_hub.pid"
sleep 0.6

# ---- quick health ping ----
if curl -s "http://127.0.0.1:${FREEZER_HUB_PORT}/api/state" >/dev/null 2>&1; then
  echo "OK: hub is responding"
else
  echo "WARN: hub not responding yet (check logs/freezer_hub.out)" >&2
fi

echo
echo "Done."
echo "Logs:"
echo "  logs/freezer_hub.out"
echo "PIDs:"
echo "  logs/freezer_hub.pid"
echo
