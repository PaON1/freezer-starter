#!/usr/bin/env python3
"""
freezer_tone_emitter.py — text-first musical motif layer (v1)

MVP behavior:
- Prints a tiny "score" line to stdout (always works).
- Optionally writes a tiny .mid later (Phase 1.5).
- Optionally plays audio later when speakers arrive.

Usage:
  ./freezer_tone_emitter.py --motif freezer_motif.json
  echo '{"motif":{"score":"C4 E4 G4","tempo":110}}' | ./freezer_tone_emitter.py --stdin
"""

import argparse, json, sys, time
from pathlib import Path

def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--motif", default="freezer_motif.json")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--prefix", default="🎵")
    args = ap.parse_args()

    payload = {}
    if args.stdin:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except Exception:
            payload = {}
    else:
        payload = load_json(Path(args.motif))

    motif = (payload.get("motif") or payload.get("motif", {})) if isinstance(payload, dict) else {}
    if "motif" in payload and isinstance(payload["motif"], dict):
        motif = payload["motif"]
    tempo = motif.get("tempo", 90)
    root = motif.get("root", "?")
    name = motif.get("name", "motif")
    score = motif.get("score", "(no score)")
    texture = motif.get("texture", "")

    line = f'{args.prefix} {name} | root={root} tempo={tempo} | {score}'
    if texture:
        line += f"  ~ {texture}"
    print(line)
    # tiny “pulse” feel for the terminal
    time.sleep(0.02)

if __name__ == "__main__":
    main()
