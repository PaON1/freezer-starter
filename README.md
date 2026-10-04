# 🧊 Freezer Starter

**A tiny offline-first mesh presence demo inspired by WRM (Waveform Resonance Mechanics).**

Freezer lets small nodes announce their local state over UDP while a local hub visualizes whether each node is live, stale, or missing. It is intentionally understandable: no cloud account, no telemetry service, and no hidden control plane.

## What it demonstrates

- UDP node presence broadcasts
- live / stale / missing state at the hub
- drift injection for testing changing conditions
- mood / motif state as a lightweight structured signal
- browser dashboards, including a 3D view
- optional local LLM grounding through Ollama
- offline-first operation

## Quick start

```bash
git clone https://github.com/PaON1/freezer-starter.git
cd freezer-starter

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 freezer_hub.py
```

Open:

- `http://127.0.0.1:8099/ui/freezer_ui.html`
- `http://127.0.0.1:8099/ui/freezer_3d.html`

In another terminal:

```bash
cd freezer-starter
source .venv/bin/activate
python3 freezer_daemon.py --udp-port 50555
```

A node should appear in the hub as live.

## Inject drift

```bash
python3 scripts/inject_drift_event.py
```

Use the dashboard to watch the state change.

## Change node state

Edit `freezer_state.json`:

```json
{
  "status": "idle",
  "mood": {
    "tag": "cold_calm",
    "valence": 0.6,
    "arousal": 0.2
  }
}
```

You can also edit `freezer_motif.json` and restart the daemon to experiment with a different motif.

## Optional local LLM grounding

If Ollama is installed:

```bash
ollama pull phi
export OLLAMA_MODEL=phi
python3 freezer_hub.py
```

If Ollama is not running, the rest of Freezer still works.

## Architecture

```text
freezer_daemon.py
    ↓ UDP presence
freezer_hub.py
    ↓
local API + UI
    ↓
freezer_ui.html / freezer_3d.html
```

The `scripts/` directory contains small tools for experiments such as drift injection and mesh inspection.

## Default ports

| Service | Port |
| --- | ---: |
| Hub HTTP | 8099 |
| UDP broadcast | 50555 |
| Ollama | 11434 |

Ports can be overridden with environment variables.

## Safety / privacy posture

- no telemetry
- no required API keys
- offline-first by design
- local logs excluded through `.gitignore`
- Ollama is optional

## Why this exists

Freezer is deliberately small. It is a place to experiment with **presence, drift, local state, and inspectable coordination** before those ideas become buried inside a larger system.

Small systems are easier to understand. Understanding is the point.

## Related work

- [WRM Core Kit](https://github.com/PaON1/wrm_core_kit_public)
- [Playable Doodles](https://github.com/PaON1/playable-doodles)
- [Raymond Bryant / project index](https://github.com/PaON1)

## License

The project is currently described as MIT-licensed in its original public documentation. Add a root `LICENSE` file before treating that statement as a complete licensing package.
