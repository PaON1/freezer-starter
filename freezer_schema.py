#!/usr/bin/env python3
"""
freezer_schema.py — minimal schema helpers for Freezer v1
No external deps. Keep packets small, readable, resilient.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import json
import time
import socket
import uuid

FREEZER_VERSION = 1

def now_iso() -> str:
    # lightweight ISO-like without pulling dateutil
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def hostname_node_id() -> str:
    try:
        return socket.gethostname().strip().lower()
    except Exception:
        return "unknown"

def make_msg_id() -> str:
    return uuid.uuid4().hex[:12]

def pack(d: Dict[str, Any]) -> bytes:
    return (json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

def unpack(b: bytes) -> Optional[Dict[str, Any]]:
    try:
        s = b.decode("utf-8", errors="replace").strip()
        if not s:
            return None
        return json.loads(s)
    except Exception:
        return None

def base_envelope(kind: str, node_id: str) -> Dict[str, Any]:
    return {
        "v": FREEZER_VERSION,
        "kind": kind,
        "id": make_msg_id(),
        "node_id": node_id,
        "ts": now_iso(),
    }

def clamp(x: float, lo: float, hi: float) -> float:
    try:
        x = float(x)
    except Exception:
        return lo
    return max(lo, min(hi, x))
