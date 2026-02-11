# 🧊 Freezer Starter (WRM Community Kit)

Freezer is a tiny, offline-first mesh presence demo inspired by WRM (Waveform Resonance Mechanics).

It demonstrates:

- Nodes broadcasting presence (mood + motif) over UDP
- A hub visualizing live / stale / missing nodes
- Optional local LLM grounding via Ollama
- Fully offline operation

No cloud. No telemetry. Just signal and structure.

---

# 🚀 Quickstart

## 1) Setup environment

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## 2) Start the Hub

python3 freezer_hub.py

Open:

http://127.0.0.1:8099/ui/freezer_ui.html
http://127.0.0.1:8099/ui/freezer_3d.html

## 3) Start a Local Node (new terminal)

source .venv/bin/activate
python3 freezer_daemon.py --udp-port 50555

You should now see a node appear as live.

---

# 🔧 Tinker Points

## Change system mood

Edit freezer_state.json:

{
  "status": "idle",
  "mood": {
    "tag": "cold_calm",
    "valence": 0.6,
    "arousal": 0.2
  }
}

Refresh browser.

---

## Inject Drift

python3 scripts/inject_drift_event.py

Watch drift update.

---

## Modify Node Motif

Edit freezer_motif.json.

Restart daemon.

---

# 🧠 Optional: Enable Ollama

Install Ollama.

Pull a model:

ollama pull phi
or
ollama pull tinyllama

Then run hub:

export OLLAMA_MODEL=phi
python3 freezer_hub.py

Ask questions in the UI.

If Ollama is not running, everything still works.

---

# 🧩 Architecture

freezer_daemon.py  
→ broadcasts UDP presence

freezer_hub.py  
→ Flask server + API + UI

ui/  
→ dashboard + 3D visualization

scripts/  
→ inject drift + scan mesh

---

# 🌐 Ports

Hub HTTP: 8099  
UDP Broadcast: 50555  
Ollama: 11434  

Override via environment variables.

---

# 🔐 Safety

- No telemetry
- No API keys
- Offline-first
- Logs excluded via .gitignore

---

# 📦 Requirements

Python 3.9+
pip
Optional: Ollama

---

# 🧊 Why This Exists

Freezer is a minimal demonstration of:

- Mesh presence
- Drift detection
- Mood-based state modeling
- Local AI grounding

It is small on purpose.
Small systems are understandable.
Understanding is the point.

---

# 📜 License

MIT License

