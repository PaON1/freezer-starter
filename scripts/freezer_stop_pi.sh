#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f logs/freezer_daemon.pid ]]; then
  pid="$(cat logs/freezer_daemon.pid)"
  echo "stopping pid=$pid"
  kill "$pid" 2>/dev/null || true
  rm -f logs/freezer_daemon.pid
else
  echo "no pid file"
fi
