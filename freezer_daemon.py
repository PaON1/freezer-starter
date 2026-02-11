#!/usr/bin/env python3
"""
freezer_daemon.py — Freezer node daemon (v1)

- UDP beacon broadcast: "I'm here, this is my mood + motif"
- UDP listener: ping/pong + whisper + whisper_ack
- Writes local relationship events to logs/freezer_events.jsonl

No external deps. Safe defaults if config files missing.

GitHub safety:
- Optional IP redaction in logs: set FREEZER_REDACT_IP=1 or pass --redact-ip
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from freezer_schema import base_envelope, pack, unpack, hostname_node_id, clamp

UDP_PORT_DEFAULT = 50555
BEACON_EVERY_DEFAULT_S = 1.0

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "freezer_events.jsonl"
STATE_FILE = ROOT / "freezer_state.json"
MOTIF_FILE = ROOT / "freezer_motif.json"


def read_json(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _redact_ip(ip: str) -> str:
    # keep format stable but hide details
    if not ip or ip == "0.0.0.0":
        return ip
    return "x.x.x.x"


def _maybe_redact_addr(addr: Tuple[str, int], redact: bool) -> Tuple[str, int]:
    if not redact:
        return addr
    return (_redact_ip(addr[0]), int(addr[1]))


def _maybe_redact_pkt(pkt: Dict[str, Any], redact: bool) -> Dict[str, Any]:
    if not redact:
        return pkt
    try:
        p2 = dict(pkt)
        if "ip" in p2 and isinstance(p2["ip"], str):
            p2["ip"] = _redact_ip(p2["ip"])
        # some packets may embed addr-like structures, ignore unless present
        return p2
    except Exception:
        return pkt


def log_event(evt: Dict[str, Any]) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    except Exception:
        pass


def get_local_ip_hint() -> str:
    """
    Best-effort local IP guess (won’t be perfect on all setups).
    This does not require actual internet connectivity; connect() here
    just selects a default route interface.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def build_presence(node_id: str, caps: list[str], udp_port: int) -> Dict[str, Any]:
    state = read_json(STATE_FILE)
    motifwrap = read_json(MOTIF_FILE)

    mood = state.get("mood") or {}
    if not isinstance(mood, dict):
        mood = {}

    mood_tag = str(mood.get("tag", "neutral"))
    valence = clamp(mood.get("valence", 0.5), 0.0, 1.0)
    arousal = clamp(mood.get("arousal", 0.5), 0.0, 1.0)
    glyph = str(mood.get("glyph", "unknown"))

    motif = motifwrap.get("motif") if isinstance(motifwrap.get("motif"), dict) else {}
    motif = motif or {}

    env = base_envelope("beacon", node_id)
    env.update(
        {
            "ip": get_local_ip_hint(),
            "udp_port": int(udp_port),
            "caps": caps,
            "status": str(state.get("status", "chilling")),
            "traits": state.get("traits", []) if isinstance(state.get("traits", []), list) else [],
            "mood": {
                "tag": mood_tag,
                "valence": valence,
                "arousal": arousal,
                "glyph": glyph,
            },
            "motif": {
                "name": motif.get("name", "soft_ping"),
                "tempo": int(motif.get("tempo", 92)) if str(motif.get("tempo", 92)).isdigit() else 92,
                "root": motif.get("root", "D"),
                "score": motif.get("score", "D4 D4 A4 (rest) D5"),
                "texture": motif.get("texture", "warm pulses"),
            },
        }
    )
    return env


def safe_run_tone(motif: Dict[str, Any]) -> None:
    """
    Text-first motif emitter (never blocks hard; best effort).
    Uses current Python (venv-safe) to launch freezer_tone_emitter.py.
    """
    try:
        payload = {"motif": motif}
        tone_py = str(ROOT / "freezer_tone_emitter.py")

        p = subprocess.Popen(
            [sys.executable, tone_py, "--stdin"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        p.communicate(json.dumps(payload), timeout=1.0)
    except Exception:
        pass


def render_template_reply(node_id: str, src: str, text: str, mood: Dict[str, Any]) -> str:
    tag = (mood or {}).get("tag", "neutral")
    glyph = (mood or {}).get("glyph", "unknown")
    # tiny WRM-ish tone without LLM dependency
    return f"from {node_id} → {src}: got you. mood={tag} glyph={glyph}. echo: “{text}”"


def make_socket(udp_port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.bind(("", int(udp_port)))
    s.settimeout(0.5)
    return s


def beacon_loop(
    sock: socket.socket,
    node_id: str,
    caps: list[str],
    udp_port: int,
    broadcast_host: str,
    beacon_every_s: float,
    stop_flag: threading.Event,
) -> None:
    broadcast_addr = (broadcast_host, int(udp_port))
    every = max(0.2, float(beacon_every_s))
    while not stop_flag.is_set():
        pkt = build_presence(node_id, caps, udp_port)
        try:
            sock.sendto(pack(pkt), broadcast_addr)
        except Exception:
            pass
        time.sleep(every)


def handle_packet(
    sock: socket.socket,
    node_id: str,
    caps: list[str],
    udp_port: int,
    pkt: Dict[str, Any],
    addr: Tuple[str, int],
    redact_ip: bool,
) -> None:
    kind = pkt.get("kind")
    src = str(pkt.get("node_id", "unknown"))
    if src == node_id:
        return  # ignore own echoes

    safe_addr = _maybe_redact_addr(addr, redact_ip)
    safe_pkt = _maybe_redact_pkt(pkt, redact_ip)

    if kind == "ping":
        presence = build_presence(node_id, caps, udp_port)
        pong = base_envelope("pong", node_id)
        pong["to"] = src
        pong["mood"] = presence.get("mood", {})
        try:
            sock.sendto(pack(pong), addr)
        except Exception:
            pass
        log_event({"event": "pong", "from": node_id, "to": src, "addr": safe_addr, "pkt": _maybe_redact_pkt(pong, redact_ip)})

    elif kind == "whisper":
        text = str(pkt.get("text", ""))

        presence = build_presence(node_id, caps, udp_port)
        mood = presence.get("mood", {})
        motif = presence.get("motif", {})

        # local ack immediately (fast), hub can later “polish” tone if desired
        ack = base_envelope("whisper_ack", node_id)
        ack["to"] = src
        ack["in_reply_to"] = pkt.get("id")
        ack["text"] = render_template_reply(node_id, src, text, mood)
        ack["mood"] = mood
        ack["motif"] = motif

        try:
            sock.sendto(pack(ack), addr)
        except Exception:
            pass

        log_event({"event": "whisper_rx", "from": src, "to": node_id, "addr": safe_addr, "pkt": safe_pkt})
        log_event({"event": "whisper_ack", "from": node_id, "to": src, "addr": safe_addr, "pkt": _maybe_redact_pkt(ack, redact_ip)})

        # play motif (text-first)
        if isinstance(motif, dict) and motif:
            safe_run_tone(motif)

    elif kind in ("beacon", "pong", "whisper_ack"):
        # log interesting inbound packets locally (useful for debugging)
        log_event({"event": f"rx_{kind}", "from": src, "to": node_id, "addr": safe_addr, "pkt": safe_pkt})


def listen_loop(
    sock: socket.socket,
    node_id: str,
    caps: list[str],
    udp_port: int,
    stop_flag: threading.Event,
    redact_ip: bool,
) -> None:
    while not stop_flag.is_set():
        try:
            b, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except Exception:
            continue

        pkt = unpack(b)
        if not pkt or not isinstance(pkt, dict):
            continue

        try:
            handle_packet(sock, node_id, caps, udp_port, pkt, addr, redact_ip)
        except Exception:
            # never crash the daemon for a bad packet
            continue


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--udp-port", type=int, default=int(os.environ.get("FREEZER_UDP_PORT", str(UDP_PORT_DEFAULT))))
    ap.add_argument("--node-id", default=os.environ.get("FREEZER_NODE_ID", "").strip())
    ap.add_argument("--caps", default=os.environ.get("FREEZER_CAPS", "freezer,tone,text"))
    ap.add_argument("--broadcast", default=os.environ.get("FREEZER_BROADCAST", "255.255.255.255"))
    ap.add_argument("--beacon-every", type=float, default=float(os.environ.get("FREEZER_BEACON_EVERY_S", str(BEACON_EVERY_DEFAULT_S))))
    ap.add_argument("--redact-ip", action="store_true", default=(os.environ.get("FREEZER_REDACT_IP", "0").strip() == "1"))
    args = ap.parse_args()

    node_id = args.node_id or hostname_node_id()
    caps = [c.strip() for c in (args.caps or "").split(",") if c.strip()]

    sock = make_socket(args.udp_port)
    stop_flag = threading.Event()

    t_beacon = threading.Thread(
        target=beacon_loop,
        args=(sock, node_id, caps, args.udp_port, args.broadcast, args.beacon_every, stop_flag),
        daemon=True,
    )
    t_listen = threading.Thread(
        target=listen_loop,
        args=(sock, node_id, caps, args.udp_port, stop_flag, bool(args.redact_ip)),
        daemon=True,
    )

    log_event(
        {
            "event": "daemon_start",
            "node_id": node_id,
            "udp_port": int(args.udp_port),
            "caps": caps,
            "broadcast": str(args.broadcast),
            "beacon_every_s": float(args.beacon_every),
            "redact_ip": bool(args.redact_ip),
        }
    )

    t_beacon.start()
    t_listen.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop_flag.set()
        try:
            sock.close()
        except Exception:
            pass
        log_event({"event": "daemon_stop", "node_id": node_id})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
