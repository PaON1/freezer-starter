#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, request, send_from_directory

HERE = Path(__file__).resolve().parent
LOGS = HERE / "logs"
UI_DIR = HERE / "ui"
CONFIG_DIR = HERE / "config"

EVENTS_PATH = LOGS / "freezer_events.jsonl"
STATE_PATH = LOGS / "freezer_state.json"
PRED_PATH = LOGS / "predictions.jsonl"
PROMPT_PATH = CONFIG_DIR / "freezer_prompt.md"

HUB_PORT = int(os.environ.get("FREEZER_HUB_PORT", "8099"))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
# Set to "phi" or "tinyllama" (your ollama tag).
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi")

EXPECTED_NODES = [
    n.strip()
    for n in os.environ.get("FREEZER_NODES", "marin,dre,harry,dennis,sven,drfengle").split(",")
    if n.strip()
]

LIVE_SEC = float(os.environ.get("FREEZER_LIVE_SEC", "8.0"))
STALE_SEC = float(os.environ.get("FREEZER_STALE_SEC", "25.0"))
TAIL_EVENTS_LIMIT = int(os.environ.get("FREEZER_TAIL_EVENTS", "400"))

# GitHub safety: redact private IPs in API responses if set
REDACT_IP = os.environ.get("FREEZER_REDACT_IP", "0").strip() == "1"

# Ollama timeouts tuned for “never stall the UI”
# connect timeout small; read timeout bounded
OLLAMA_CONNECT_S = float(os.environ.get("FREEZER_OLLAMA_CONNECT_S", "3.0"))
OLLAMA_READ_S = float(os.environ.get("FREEZER_OLLAMA_READ_S", "18.0"))

app = Flask(__name__, static_folder=None)


def _now() -> float:
    return time.time()


def _read_text(p: Path, default: str = "") -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return default


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _tail_jsonl(p: Path, limit: int = 200) -> List[Dict[str, Any]]:
    if not p.exists():
        return []
    try:
        size = p.stat().st_size
        chunk = min(size, max(65536, limit * 900))
        with p.open("rb") as f:
            f.seek(max(0, size - chunk))
            data = f.read().decode("utf-8", errors="replace")
        lines = [ln for ln in data.splitlines() if ln.strip()]
        out: List[Dict[str, Any]] = []
        for ln in lines[-limit:]:
            try:
                obj = json.loads(ln)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
        return out
    except Exception:
        return []


def _last_jsonl(p: Path) -> Optional[Dict[str, Any]]:
    tail = _tail_jsonl(p, limit=5)
    return tail[-1] if tail else None


def _default_state() -> Dict[str, Any]:
    return {
        "status": "idle",
        "mood": {"tag": "cold_calm", "valence": 0.6, "arousal": 0.2, "glyph": "icebox"},
        "traits": ["offline-first", "mesh-aware"],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def _iso_to_epoch(ts: str) -> Optional[float]:
    try:
        from datetime import datetime

        t = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        return datetime.fromisoformat(t).timestamp()
    except Exception:
        return None


def _redact_ip(ip: str) -> str:
    if not ip or ip == "0.0.0.0":
        return ip
    return "x.x.x.x"


def _maybe_redact_pkt(pkt: Dict[str, Any]) -> Dict[str, Any]:
    if not REDACT_IP:
        return pkt
    try:
        p2 = dict(pkt)
        if "ip" in p2 and isinstance(p2["ip"], str):
            p2["ip"] = _redact_ip(p2["ip"])
        return p2
    except Exception:
        return pkt


def _maybe_redact_event(e: Dict[str, Any]) -> Dict[str, Any]:
    if not REDACT_IP:
        return e
    try:
        e2 = dict(e)
        if "addr" in e2 and isinstance(e2["addr"], (list, tuple)) and len(e2["addr"]) == 2:
            e2["addr"] = [_redact_ip(str(e2["addr"][0])), int(e2["addr"][1])]
        if "pkt" in e2 and isinstance(e2["pkt"], dict):
            e2["pkt"] = _maybe_redact_pkt(e2["pkt"])
        return e2
    except Exception:
        return e


def derive_nodes(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for e in events:
        if e.get("event") not in ("rx_beacon", "tx_beacon", "beacon"):
            continue
        pkt = e.get("pkt") or {}
        if not isinstance(pkt, dict):
            continue
        nid = pkt.get("node_id")
        if nid:
            latest[str(nid)] = pkt

    now = _now()
    out: List[Dict[str, Any]] = []

    def _presence_for_age(age: Optional[float]) -> str:
        if age is None:
            return "unknown"
        if age <= LIVE_SEC:
            return "live"
        if age <= STALE_SEC:
            return "stale"
        return "missing"

    for nid in EXPECTED_NODES:
        pkt = latest.get(nid)
        if not pkt:
            out.append(
                {
                    "node_id": nid,
                    "presence": "missing",
                    "status": "missing",
                    "age_s": None,
                    "caps": [],
                    "mood": {"tag": "silence"},
                }
            )
            continue

        ts = pkt.get("ts") or ""
        ep = _iso_to_epoch(ts) if isinstance(ts, str) else None
        age = (now - ep) if ep else None

        pkt2 = dict(pkt)
        pkt2["age_s"] = round(age, 2) if age is not None else None
        pkt2["presence"] = _presence_for_age(age)
        if REDACT_IP and isinstance(pkt2.get("ip"), str):
            pkt2["ip"] = _redact_ip(pkt2["ip"])
        out.append(pkt2)

    # include unexpected nodes too
    for nid, pkt in latest.items():
        if nid in EXPECTED_NODES:
            continue
        pkt2 = dict(pkt)
        pkt2["presence"] = "live"
        pkt2["age_s"] = None
        if REDACT_IP and isinstance(pkt2.get("ip"), str):
            pkt2["ip"] = _redact_ip(pkt2["ip"])
        out.append(pkt2)

    return out


def ollama_tags() -> List[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=(OLLAMA_CONNECT_S, 6.0))
        j = r.json() if r.ok else {}
        return [m.get("name") for m in (j.get("models") or []) if m.get("name")]
    except Exception:
        return []


def ollama_generate(prompt: str) -> str:
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json=payload,
        timeout=(OLLAMA_CONNECT_S, OLLAMA_READ_S),
    )
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or f"ollama HTTP {r.status_code}")
    return (j.get("response") or "").strip()


def _fallback_answer(question: str, nodes: List[Dict[str, Any]]) -> str:
    live = [n for n in nodes if n.get("presence") == "live"]
    stale = [n for n in nodes if n.get("presence") == "stale"]
    missing = [n for n in nodes if n.get("presence") == "missing"]

    def names(xs: List[Dict[str, Any]]) -> str:
        return ", ".join([str(x.get("node_id", x.get("node", "?"))) for x in xs]) if xs else "none"

    return (
        "Ollama is unavailable right now, so here’s an evidence-only snapshot.\n\n"
        f"Question: {question}\n"
        f"Live nodes ({len(live)}): {names(live)}\n"
        f"Stale nodes ({len(stale)}): {names(stale)}\n"
        f"Missing nodes ({len(missing)}): {names(missing)}\n\n"
        "Interpretation: if many nodes are stale/missing, the mesh may be quiet (no beacons) or your UDP listener "
        "isn’t running on some nodes. If live is healthy, you’re in a good state to proceed."
    )


def build_prompt(
    question: str,
    state: Dict[str, Any],
    nodes: List[Dict[str, Any]],
    events_recent: List[Dict[str, Any]],
    pred: Optional[Dict[str, Any]],
) -> str:
    system = _read_text(PROMPT_PATH, default="You are Freezer, a WRM mesh monitor. Be grounded in evidence.")
    evidence = {
        "question": question,
        "state": state,
        "nodes_summary": {
            "total": len(nodes),
            "live": sum(1 for n in nodes if n.get("presence") == "live"),
            "stale": sum(1 for n in nodes if n.get("presence") == "stale"),
            "missing": sum(1 for n in nodes if n.get("presence") == "missing"),
        },
        "nodes": nodes,
        "events_tail": events_recent[:35],
        "last_prediction": pred or None,
    }
    return (
        system.strip()
        + "\n\n--- LIVE EVIDENCE (JSON) ---\n"
        + json.dumps(evidence, ensure_ascii=False, indent=2)
        + "\n\nInstruction: Answer using LIVE EVIDENCE. If last_prediction exists, treat it as posture evidence (decision hint) not truth.\n"
        + "Be concise, practical, and do not invent facts that are not in evidence.\n"
    )


@app.get("/")
def root():
    return jsonify({"ok": True, "ui": "/ui/freezer_ui.html", "port": HUB_PORT})


@app.get("/ui/<path:filename>")
def ui_files(filename: str):
    return send_from_directory(UI_DIR, filename)


@app.get("/api/state")
def api_state():
    st = _read_json(STATE_PATH)
    if not isinstance(st, dict):
        st = _default_state()
    return jsonify(st)


@app.get("/api/events")
def api_events():
    limit = int(request.args.get("limit", "40"))
    limit = max(1, min(500, limit))
    events = _tail_jsonl(EVENTS_PATH, limit=limit)
    if REDACT_IP:
        events = [_maybe_redact_event(e) for e in events]
    return jsonify({"events": events})


@app.get("/api/nodes")
def api_nodes():
    events = _tail_jsonl(EVENTS_PATH, limit=TAIL_EVENTS_LIMIT)
    if REDACT_IP:
        events = [_maybe_redact_event(e) for e in events]
    nodes = derive_nodes(events)
    return jsonify({"nodes": nodes})


@app.get("/api/prediction")
def api_prediction():
    last = _last_jsonl(PRED_PATH)
    return jsonify({"ok": bool(last), "last": last})


@app.get("/api/health")
def api_health():
    tags = ollama_tags()
    return jsonify(
        {
            "ok": True,
            "ollama": {
                "url": OLLAMA_URL,
                "model": OLLAMA_MODEL,
                "tags": tags,
                "model_present": (OLLAMA_MODEL in tags) if tags else None,
                "timeouts": {"connect_s": OLLAMA_CONNECT_S, "read_s": OLLAMA_READ_S},
            },
            "paths": {
                "events": str(EVENTS_PATH),
                "events_exists": EVENTS_PATH.exists(),
                "predictions": str(PRED_PATH),
                "predictions_exists": PRED_PATH.exists(),
                "prompt": str(PROMPT_PATH),
                "prompt_exists": PROMPT_PATH.exists(),
            },
            "expected_nodes": EXPECTED_NODES,
            "redact_ip": REDACT_IP,
        }
    )


@app.post("/api/ask")
def api_ask():
    body = request.get_json(silent=True) or {}
    question = str(body.get("question", "")).strip() or "Summarize drift + missing nodes in bullets."

    state = _read_json(STATE_PATH)
    if not isinstance(state, dict):
        state = _default_state()

    events = _tail_jsonl(EVENTS_PATH, limit=TAIL_EVENTS_LIMIT)
    if REDACT_IP:
        events = [_maybe_redact_event(e) for e in events]

    nodes = derive_nodes(events)
    last_pred = _last_jsonl(PRED_PATH)

    # Most recent first for evidence readability
    events_recent = list(reversed(events))[:40]

    prompt = build_prompt(question, state, nodes, events_recent, last_pred)

    try:
        text = ollama_generate(prompt)
        return jsonify({"ok": True, "model": OLLAMA_MODEL, "response": text, "last_prediction": last_pred})
    except Exception as e:
        # never stall a demo: return evidence-only fallback
        fb = _fallback_answer(question, nodes)
        return jsonify(
            {
                "ok": True,
                "model": OLLAMA_MODEL,
                "response": fb,
                "ollama_error": str(e),
                "last_prediction": last_pred,
            }
        )


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=HUB_PORT, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
