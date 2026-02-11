const qs = new URLSearchParams(location.search);
const hub = qs.get("hub") || location.origin;

const el = (id) => document.getElementById(id);
const hubPill = el("hubPill");
const nodePill = el("nodePill");
const modePill = el("modePill");
const wrap = document.getElementById("canvasWrap");
const fallback = document.getElementById("fallback");

hubPill.textContent = `hub: ${hub.replace(/^https?:\/\//,"")}`;

function showFallback(msg){
  fallback.style.display = "block";
  fallback.textContent = msg;
}

// Offline-first: local vendored Three.js
let THREE, OrbitControls;
try {
  THREE = await import("/ui/vendor/three.module.js");
  ({ OrbitControls } = await import("/ui/vendor/OrbitControls.js"));
} catch (e) {
  showFallback("3D libs missing. Run: ui/vendor download step (three.module.js + OrbitControls.js).");
  throw e;
}

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x0b1220, 8, 42);

const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200);
camera.position.set(0, 6, 16);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
wrap.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.target.set(0, 1.2, 0);

scene.add(new THREE.AmbientLight(0xffffff, 0.45));
const key = new THREE.DirectionalLight(0xffffff, 0.85);
key.position.set(8, 14, 10);
scene.add(key);

const grid = new THREE.GridHelper(40, 40, 0x2a3a66, 0x162244);
grid.position.y = 0;
scene.add(grid);

const ringGeo = new THREE.TorusGeometry(6.4, 0.05, 12, 220);
const ringMat = new THREE.MeshStandardMaterial({ color: 0x355a9c, metalness: 0.2, roughness: 0.85 });
const ring = new THREE.Mesh(ringGeo, ringMat);
ring.rotation.x = Math.PI / 2;
ring.position.y = 0.02;
scene.add(ring);

function hash01(str){
  let h = 2166136261 >>> 0;
  for (let i=0;i<str.length;i++){
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

function moodColor(m){
  const v = (m?.valence ?? 0.5);
  const a = (m?.arousal ?? 0.3);
  const base = new THREE.Color();
  base.setHSL(0.58 - v*0.22, 0.75, 0.45 + a*0.18);
  return base;
}

const nodes = new Map();
const orbGeo = new THREE.SphereGeometry(0.55, 28, 28);
const glowGeo = new THREE.SphereGeometry(0.80, 28, 28);

function ensureNode(n){
  const id = n.node_id || n.id || "unknown";
  if (nodes.has(id)) return nodes.get(id);

  const col = moodColor(n.mood);
  const mat = new THREE.MeshStandardMaterial({ color: col, metalness: 0.25, roughness: 0.55 });
  const mesh = new THREE.Mesh(orbGeo, mat);

  const glowMat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.18 });
  const glow = new THREE.Mesh(glowGeo, glowMat);

  const t = hash01(id) * Math.PI * 2;
  const r = 6.2 + (hash01(id+"r")*1.4);
  mesh.position.set(Math.cos(t)*r, 1.2 + hash01(id+"y")*1.8, Math.sin(t)*r);
  glow.position.copy(mesh.position);

  scene.add(mesh);
  scene.add(glow);

  const obj = { mesh, glow, lastTs: n.ts || "" };
  nodes.set(id, obj);
  return obj;
}

async function getJSON(path){
  const url = `${hub}${path}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

let lastCount = 0;

async function tick(){
  try {
    const [state, nodeData] = await Promise.all([
      getJSON("/api/state"),
      getJSON("/api/nodes")
    ]);

    modePill.textContent = `mode: ${state?.status ?? "?"} (${state?.mood?.tag ?? "?"})`;

    const list = nodeData?.nodes || [];
    lastCount = nodeData?.count ?? list.length;
    nodePill.textContent = `nodes: ${lastCount}`;

    for (const n of list){
      const obj = ensureNode(n);
      obj.lastTs = n.ts || obj.lastTs;

      const col = moodColor(n.mood);
      obj.mesh.material.color.copy(col);
      obj.glow.material.color.copy(col);

      const id = n.node_id || n.id || "unknown";
      const baseT = hash01(id) * Math.PI * 2;
      const t = baseT + (Date.now()/1000) * (0.05 + hash01(id+"spd")*0.08);
      const r = 6.2 + (hash01(id+"r")*1.4);
      obj.mesh.position.x = Math.cos(t)*r;
      obj.mesh.position.z = Math.sin(t)*r;
      obj.mesh.position.y = 1.0 + hash01(id+"y")*2.2 + Math.sin((Date.now()/1000)+(hash01(id+"b")*6))*0.25;
      obj.glow.position.copy(obj.mesh.position);

      const a = (n?.mood?.arousal ?? 0.3);
      obj.glow.material.opacity = 0.10 + a*0.22 + (Math.sin(Date.now()/400 + hash01(id)*10)*0.03);
    }
  } catch (_e) {
    nodePill.textContent = `nodes: ${lastCount} (poll err)`;
  }
}

function resize(){
  const w = window.innerWidth;
  const h = window.innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}
window.addEventListener("resize", resize);
resize();

let last = performance.now();
function animate(now){
  const dt = (now - last) / 1000;
  last = now;

  ring.rotation.z += dt * 0.05;
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);

await tick();
setInterval(tick, 1000);
