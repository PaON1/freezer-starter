#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "== Freezer stop =="

if [[ -f logs/freezer_hub.pid ]]; then
  PID="$(cat logs/freezer_hub.pid || true)"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" >/dev/null 2>&1; then
    echo "Stopping hub PID=${PID}"
    kill "${PID}" || true
    sleep 0.6
    if kill -0 "${PID}" >/dev/null 2>&1; then
      echo "Force stopping hub PID=${PID}"
      kill -9 "${PID}" || true
    fi
  else
    echo "No running hub found for PID=${PID}"
  fi
  rm -f logs/freezer_hub.pid
else
  echo "No pid file logs/freezer_hub.pid"
fi

echo "Done."
