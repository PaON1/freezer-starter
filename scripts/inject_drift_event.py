#!/usr/bin/env python3
import json, argparse
from pathlib import Path
from datetime import datetime, timezone

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="orpheusnode")
    ap.add_argument("--tag", default="drift_spike")
    ap.add_argument("--emotion", default="uneasy")
    ap.add_argument("--drift", type=float, default=0.75)
    ap.add_argument("--trust", type=float, default=0.35)
    ap.add_argument("--out", default=str(Path.home()/ "wrm_dash_core/freezer/logs/freezer_events.jsonl"))
    args = ap.parse_args()

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    evt = {
        "event": "drift_event",
        "from": args.node,
        "to": "orpheusnode",
        "addr": ["127.0.0.1", 0],
        "pkt": {
            "v": 1,
            "kind": "drift",
            "id": "manual",
            "node_id": args.node,
            "ts": iso_now(),
            "status": "drifting",
            "mood": {"tag": args.emotion, "valence": 0.2, "arousal": 0.7, "glyph": args.tag},
            "trust_score": args.trust,
            "drift_level": args.drift,
            "caps": ["freezer","tone","text"],
            "traits": ["manual_inject"],
        }
    }

    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")

    print(f"wrote drift_event -> {out}")

if __name__ == "__main__":
    main()
