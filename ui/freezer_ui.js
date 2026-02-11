(() => {
  "use strict";

  // -----------------------------
  // Helpers
  // -----------------------------
  const el = (id) => document.getElementById(id);
  const clamp01 = (x) => Math.max(0, Math.min(1, x));
  const fmt = (x) => (x == null ? "—" : String(x));
  const isNum = (x) => typeof x === "number" && Number.isFinite(x);

  function safeJson(v) {
    try { return JSON.stringify(v, null, 2); } catch { return String(v); }
  }

  // -----------------------------
  // Elements (from freezer_ui.html)
  // -----------------------------
  const baseUrlText = el("baseUrlText");

  const liveDot   = el("liveDot");
  const liveLabel = el("liveLabel");

  const llmDot  = el("llmDot");
  const llmHint = el("llmHint");

  const driftBadge = el("driftBadge");
  const driftBar   = el("driftBar");

  const askInput  = el("askInput");
  const btnAsk    = el("btnAsk");
  const btnRefresh= el("btnRefresh");
  const btnAuto   = el("btnAuto");

  const nodesTbody  = el("nodesTbody");
  const nodesCount  = el("nodesCount");

  const stateText  = el("stateText");
  const stateLast  = el("stateLast");

  const inspectorBody = el("inspectorBody");
  const eventsText    = el("eventsText");
  const eventsCount   = el("eventsCount");

  // Optional 3D canvas + tooltip exist in HTML; we won’t hard-require them
  const sceneCanvas = el("scene");
  const tooltipEl   = el("tooltip");
  const sceneNote   = el("sceneNote");

  // -----------------------------
  // Config
  // -----------------------------
  const qs = new URLSearchParams(location.search);
  const DEFAULT_BASE =
    qs.get("base") ||
    `${location.protocol}//${location.host}`;

  // If the UI is served from the hub, DEFAULT_BASE is correct.
  // If you open the HTML file directly, pass ?base=http://localhost:8099
  let BASE = (DEFAULT_BASE || "").replace(/\/+$/, "");

  const POLL_MS = 1500;
  const EVENTS_LIMIT = 40;

  // State
  let autoOn = true;
  let pinnedNodeId = null;
  let lastNodes = [];
  let lastHealth = null;
  let lastAskResponse = null;

  // -----------------------------
  // UI state setters
  // -----------------------------
  function setDot(dot, on) {
    if (!dot) return;
    dot.classList.toggle("live", !!on);
  }

  function setLive(ok) {
    setDot(liveDot, ok);
    liveLabel.textContent = ok ? "live (polling)" : "offline (polling)";
  }

  function setLLM(ok, label) {
    // re-use .live green dot style for LLM presence
    setDot(llmDot, ok);
    llmHint.textContent = label || "ollama: —";
  }

  function setDrift(level01, label) {
    const v = clamp01(level01 || 0);
    driftBadge.textContent = label || `drift: ${(v * 100).toFixed(0)}%`;
    if (driftBar) driftBar.style.width = `${(v * 100).toFixed(0)}%`;
  }

  function setBaseLabel() {
    if (baseUrlText) baseUrlText.textContent = `(${BASE})`;
  }

  // -----------------------------
  // API
  // -----------------------------
  async function apiGet(path) {
    const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`${path} HTTP ${r.status}`);
    return await r.json();
  }

  async function apiPost(path, body) {
    const r = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw new Error(`${path} HTTP ${r.status}`);
    return await r.json();
  }

  // -----------------------------
  // Drift heuristic (simple & stable)
  // - more missing/stale nodes => higher drift
  // -----------------------------
  function computeDrift(nodes) {
    if (!Array.isArray(nodes) || nodes.length === 0) return { v: 0.35, label: "drift: unknown" };

    const total = nodes.length;
    const live = nodes.filter(n => n && n.presence === "live").length;
    const stale = nodes.filter(n => n && n.presence === "stale").length;
    const missing = nodes.filter(n => n && n.presence === "missing").length;

    // Weight missing more than stale
    const v = clamp01((missing * 1.0 + stale * 0.45) / Math.max(1, total));
    const label = `drift: ${v.toFixed(2)} (${live}/${total} live)`;
    return { v, label };
  }

  // -----------------------------
  // Rendering
  // -----------------------------
  function badgeForPresence(p) {
    if (p === "live") return `<span class="badge bGood">live</span>`;
    if (p === "stale") return `<span class="badge bWarn">stale</span>`;
    if (p === "missing") return `<span class="badge bBad">missing</span>`;
    return `<span class="badge">unknown</span>`;
  }

  function redactMaybe(s) {
    // In case your daemon/hub already redacts to x.x.x.x, we just show it.
    // If not redacted, we still show it (LAN tool), but you can later add a UI toggle.
    return s == null ? "—" : String(s);
  }

  function renderNodesTable(nodes) {
    lastNodes = Array.isArray(nodes) ? nodes : [];
    nodesCount.textContent = `${lastNodes.length} node(s)`;

    const rows = lastNodes.map((n) => {
      const nid = n?.node_id || n?.node || "unknown";
      const presence = n?.presence || "unknown";
      const age = isNum(n?.age_s) ? `${n.age_s.toFixed(1)}s` : "—";
      const mood = n?.mood?.tag ? `${n.mood.tag} • ${n.mood.glyph || ""}`.trim() : "—";
      const ip = redactMaybe(n?.ip);
      const udp = redactMaybe(n?.udp_port);
      const ipudp = (ip && udp && ip !== "—" && udp !== "—") ? `${ip}:${udp}` : "—";

      const pinned = (pinnedNodeId && pinnedNodeId === nid);
      const trStyle = pinned ? 'style="background: rgba(255,255,255,0.05);"' : "";

      return `
        <tr data-node="${nid}" ${trStyle}>
          <td><span class="badge">${nid}</span></td>
          <td>${badgeForPresence(presence)}</td>
          <td>${age}</td>
          <td>${mood}</td>
          <td class="monoMuted">${ipudp}</td>
        </tr>
      `;
    }).join("");

    nodesTbody.innerHTML = rows || `<tr><td colspan="5" class="monoMuted">No nodes yet.</td></tr>`;

    // Click-to-pin
    [...nodesTbody.querySelectorAll("tr[data-node]")].forEach((tr) => {
      tr.addEventListener("click", () => {
        pinnedNodeId = tr.getAttribute("data-node");
        renderNodesTable(lastNodes); // re-render to highlight
        renderInspectorPinned();
      });
    });
  }

  function renderState(st) {
    stateText.textContent = safeJson(st || {});
    stateLast.textContent = `last: ${st?.ts || "—"}`;
  }

  function renderEvents(events) {
    const arr = Array.isArray(events) ? events : [];
    eventsCount.textContent = `events: ${arr.length}`;

    // Show newest-first for “what’s happening now”
    const newestFirst = [...arr].reverse();
    eventsText.textContent = newestFirst.map(e => safeJson(e)).join("\n\n");
  }

  function renderInspectorPinned() {
    const nid = pinnedNodeId;
    if (!nid) {
      inspectorBody.textContent = "click a node row (or node in space) to pin details • Ask replies land here";
      return;
    }
    const n = (lastNodes || []).find(x => (x?.node_id || x?.node) === nid);
    inspectorBody.textContent = safeJson(n || { node_id: nid, note: "not found in current nodes list" });
  }

  function renderAskOutput(resp) {
    lastAskResponse = resp || null;

    // Your hub returns { ok, model, response, last_prediction } on success
    if (!resp) return;

    const ok = !!resp.ok;
    const model = resp.model || "—";
    const txt = resp.response || resp.error || "(no response)";

    const blob = {
      ok,
      model,
      response: txt,
      last_prediction: resp.last_prediction || null,
    };

    // Put ask output into inspector body area so it’s podcast-friendly
    pinnedNodeId = null; // unpin so “Ask Output” is the focus
    inspectorBody.textContent = safeJson(blob);
  }

  // -----------------------------
  // 3D (optional): if Three.js is available, you can wire it later.
  // For now, we just detect it and keep UI stable.
  // -----------------------------
  function init3DOptional() {
    if (!sceneCanvas || !sceneNote) return;
    const hasThree = typeof window.THREE !== "undefined";
    sceneNote.textContent = hasThree
      ? "3D ready (Three.js loaded)."
      : "Three.js not loaded — UI still fully functional in 2D mode.";
  }

  // -----------------------------
  // Poll loop
  // -----------------------------
  async function refreshOnce() {
    try {
      // Health first (tells you if Ollama is reachable)
      const health = await apiGet("/api/health");
      lastHealth = health;

      const tags = health?.ollama?.tags || [];
      const model = health?.ollama?.model || "—";
      const present = health?.ollama?.model_present;

      setLive(true);
      setLLM(!!present, `ollama: ${model}${Array.isArray(tags) && tags.length ? "" : ""}`);

      // Nodes + drift
      const nodesJ = await apiGet("/api/nodes");
      const nodes = nodesJ?.nodes || [];
      renderNodesTable(nodes);

      const d = computeDrift(nodes);
      setDrift(d.v, d.label);

      // State
      const st = await apiGet("/api/state");
      renderState(st);

      // Events tail
      const ev = await apiGet(`/api/events?limit=${EVENTS_LIMIT}`);
      renderEvents(ev?.events || []);

      // If a node is pinned, keep it refreshed
      if (pinnedNodeId) renderInspectorPinned();

    } catch (e) {
      setLive(false);
      setLLM(false, "ollama: —");
      setDrift(0.35, "drift: unknown");
      // Don’t spam; show error softly in inspector if nothing else pinned
      if (!pinnedNodeId && !lastAskResponse) {
        inspectorBody.textContent = `refresh error: ${e.message}`;
      }
    }
  }

  async function askNow() {
    const q = (askInput.value || "").trim() || "Summarize drift + missing nodes in bullets.";
    try {
      const resp = await apiPost("/api/ask", { question: q });
      renderAskOutput(resp);
    } catch (e) {
      renderAskOutput({ ok: false, error: "ask_failed", detail: e.message });
    }
  }

  function setAuto(on) {
    autoOn = !!on;
    btnAuto.textContent = autoOn ? "Auto: ON" : "Auto: OFF";
  }

  // -----------------------------
  // Wire up buttons
  // -----------------------------
  btnAsk.addEventListener("click", askNow);
  btnRefresh.addEventListener("click", refreshOnce);
  btnAuto.addEventListener("click", () => setAuto(!autoOn));

  askInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      askNow();
    }
  });

  // -----------------------------
  // Boot
  // -----------------------------
  setBaseLabel();
  init3DOptional();
  setAuto(true);

  // First draw ASAP
  refreshOnce();

  // Poll loop
  setInterval(() => {
    if (autoOn) refreshOnce();
  }, POLL_MS);

})();
