#!/usr/bin/env python3
"""
scan_freezer_mesh.py — scans for available WRM nodes on the LAN
Reads from wrm_mesh logs and cortex core config to generate a summary
"""

import json
from pathlib import Path
from datetime import datetime

MESH_LOG = Path("../../wrm_mesh/logs/vote_bus/received_trust_pulses.jsonl")
CONFIG = Path("../../wrm_cortex_core/config/cortex_config.json")
OUTPUT = Path("../logs/freezer_mesh_discovery.json")

def read_last_pulses(log_path, max_lines=5000):
    if not log_path.exists():
        return []
    lines = log_path.read_text().splitlines()[-max_lines:]
    return [json.loads(line) for line in lines if line.strip()]

def read_config(config_path):
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text())

def build_summary():
    pulses = read_last_pulses(MESH_LOG)
    config = read_config(CONFIG)
    seen_nodes = {}
    for p in pulses:
        node = p.get("node")
        if node:
            seen_nodes[node] = {
                "last_seen": p.get("ts"),
                "source": p.get("source"),
                "trust": p.get("trust"),
                "drift": p.get("drift"),
                "raw": p,
            }
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "node_count": len(seen_nodes),
        "nodes": seen_nodes,
        "mesh_config": config,
    }

def main():
    summary = build_summary()
    OUTPUT.write_text(json.dumps(summary, indent=2))
    print(f"✅ Mesh scan complete. Found {summary['node_count']} nodes.")
    print(f"📄 Output written to {OUTPUT.resolve()}")

if __name__ == "__main__":
    main()
