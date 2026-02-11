#!/usr/bin/env python3
"""
freezer_wrm_context.py — Pull WRM context into Freezer (best-effort, no crashes)

Primary use:
- Called by freezer_daemon.py and/or freezer_hub.py to enrich beacons/UI with:
  - trust context (score/direction/momentum/volatility/stability)
  - optional cortex identity (if available)

Design principles:
- tolerate missing files
- tolerate schema drift
- no external deps
- never throw exceptions upward
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from freezer_paths import mesh, cortex


# -----------------------------
# JSONL tail helpers
# -----------------------------
def _read_last_jsonl_obj(path: Path, max_bytes: int = 250_000) -> Optional[Dict[str, Any]]:
    """
    Read up to max_bytes from the end of a JSONL file and return the last valid JSON object.
    Cheap + robust; avoids loading huge logs.

    Returns:
      dict if found, else None
    """
    try:
        if not path.exists():
            return None

        size = path.stat().st_size
        start = max(0, size - max_bytes)

        with path.open("rb") as f:
            f.seek(start)
            blob = f.read()

        lines = blob.splitlines()
        for raw in reversed(lines):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw.decode("utf-8", errors="replace"))
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue
        return None
    except Exception:
        return None


# -----------------------------
# Trust context
# -----------------------------
def _normalize_trust_record(rec: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Normalize a variety of trust schemas into a single shape.
    We accept either:
      - rec["trust"] dict (preferred)
      - flat fields like trust_score/direction
      - ray-style trust_fields_tail.jsonl variants (trust.score etc)
    """
    trust = rec.get("trust") if isinstance(rec.get("trust"), dict) else {}

    # Common possibilities
    score = None
    if isinstance(trust, dict):
        score = trust.get("score", None)
    if score is None:
        score = rec.get("trust_score", rec.get("score", None))

    direction = None
    if isinstance(trust, dict):
        direction = trust.get("direction", None)
    if direction is None:
        direction = rec.get("direction", "unknown")

    momentum = trust.get("momentum") if isinstance(trust, dict) else rec.get("momentum")
    volatility = trust.get("volatility") if isinstance(trust, dict) else rec.get("volatility")
    stability = trust.get("stability") if isinstance(trust, dict) else rec.get("stability")

    # Optional "who" fields (helps UI)
    node_id = rec.get("node_id") or rec.get("host") or rec.get("writer_id") or None

    return {
        "score": score,
        "direction": direction if direction is not None else "unknown",
        "momentum": momentum,
        "volatility": volatility,
        "stability": stability,
        "node_id": node_id,
        "source": source,
    }


def get_trust_context() -> Dict[str, Any]:
    """
    Locate the best available trust context source and return normalized trust context.

    Search order:
      1) wrm_cortex_core/logs/trust_fields_enriched.jsonl
      2) wrm_cortex_core/logs/trust_fields.jsonl
      3) wrm_mesh/logs/ui/trust_fields_tail.jsonl

    Returns dict always (never raises).
    """
    candidates = [
        cortex("logs", "trust_fields_enriched.jsonl"),
        cortex("logs", "trust_fields.jsonl"),
        mesh("logs", "ui", "trust_fields_tail.jsonl"),
    ]

    for p in candidates:
        rec = _read_last_jsonl_obj(p)
        if isinstance(rec, dict):
            return _normalize_trust_record(rec, source=str(p))

    return {
        "score": None,
        "direction": "unknown",
        "momentum": None,
        "volatility": None,
        "stability": None,
        "node_id": None,
        "source": "none",
    }


# -----------------------------
# Cortex identity (optional)
# -----------------------------
def _try_parse_json_from_stdout(s: str) -> Optional[Dict[str, Any]]:
    s = (s or "").strip()
    if not s:
        return None
    # if stdout is pure JSON
    if s.startswith("{") and s.endswith("}"):
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    # else try to extract a JSON object within text
    i = s.find("{")
    j = s.rfind("}")
    if i != -1 and j != -1 and j > i:
        try:
            obj = json.loads(s[i : j + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def get_cortex_identity_best_effort(timeout_s: float = 1.2) -> Optional[Dict[str, Any]]:
    """
    Try to run wrm_cortex_core/scripts/print_cortex_identity.py and parse JSON.

    We try:
      - python3 print_cortex_identity.py --json
      - python3 print_cortex_identity.py

    If script missing or output not JSON, returns None.
    Never raises.
    """
    script = cortex("scripts", "print_cortex_identity.py")
    if not script.exists():
        return None

    # Attempt 1: --json
    try:
        r = subprocess.run(
            ["python3", str(script), "--json"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if r.returncode == 0:
            obj = _try_parse_json_from_stdout(r.stdout)
            if obj:
                return obj
    except Exception:
        pass

    # Attempt 2: raw
    try:
        r = subprocess.run(
            ["python3", str(script)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if r.returncode == 0:
            obj = _try_parse_json_from_stdout(r.stdout)
            if obj:
                return obj
    except Exception:
        pass

    return None


# -----------------------------
# CLI for quick sanity checks
# -----------------------------
if __name__ == "__main__":
    trust = get_trust_context()
    ident = get_cortex_identity_best_effort()
    print(json.dumps({"trust": trust, "identity": ident}, ensure_ascii=False, indent=2))
