#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "🧊 Freezer PI start (daemon only)"
./freezer_daemon.py --udp-port 50555 > logs/freezer_daemon.out 2>&1 &
echo $! > logs/freezer_daemon.pid
echo "started pid=$(cat logs/freezer_daemon.pid)"
