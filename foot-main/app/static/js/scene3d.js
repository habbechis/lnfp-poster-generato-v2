/* =========================================================================
   Ambient 3D backdrop — Three.js (self-hosted, no CDN).

   Decorative only: a slow drift of football-like icosahedra behind the UI,
   plus a 3D spinning ball mark in the top bar. Everything degrades quietly:
   if WebGL is unavailable, or the visitor prefers reduced motion, or the tab
   is hidden, the scene simply does not run and the page is unaffected.
   ========================================================================= */
import * as THREE from "../vendor/three.module.min.js";

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------------------------------------------------------------- helpers */
function makeRenderer(canvas, alpha = true) {
  try {
    const r = new THREE.WebGLRenderer({
      canvas, alpha, antialias: true, powerPreference: "low-power",
    });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    return r;
  } catch {
    return null; // no WebGL — silently skip
  }
}

/** A stylised football: dark icosahedron body with a gold wireframe shell. */
function makeBall(radius, detail = 1) {
  const g = new THREE.Group();
  const geo = new THREE.IcosahedronGeometry(radius, detail);
  g.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: 0x8d0b12, roughness: 0.55, metalness: 0.15,
    transparent: true, opacity: 0.85,
  })));
  g.add(new THREE.LineSegments(
    new THREE.WireframeGeometry(geo),
    new THREE.LineBasicMaterial({
      color: 0xf7cd6a, transparent: true, opacity: 0.55,
    })));
  return g;
}

/* ------------------------------------------------------------ background */
function initBackdrop() {
  const canvas = document.getElementById("bg3d");
  if (!canvas || reduceMotion) return;
  const renderer = makeRenderer(canvas);
  if (!renderer) return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100);
  camera.position.z = 18;

  scene.add(new THREE.AmbientLight(0xffdca8, 1.1));
  const key = new THREE.DirectionalLight(0xffe6b0, 1.5);
  key.position.set(6, 8, 10);
  scene.add(key);

  // Scatter a handful of balls across the view; fewer on small screens.
  const count = window.innerWidth < 760 ? 7 : 13;
  const balls = [];
  for (let i = 0; i < count; i++) {
    const r = 0.5 + Math.random() * 1.5;
    const b = makeBall(r);
    b.position.set(
      (Math.random() - 0.5) * 34,
      (Math.random() - 0.5) * 22,
      (Math.random() - 0.5) * 16 - 4,
    );
    b.userData = {
      spin: (Math.random() - 0.5) * 0.006,
      drift: 0.0015 + Math.random() * 0.0035,
      phase: Math.random() * Math.PI * 2,
    };
    balls.push(b);
    scene.add(b);
  }

  const resize = () => {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  resize();
  window.addEventListener("resize", resize);

  // Gentle parallax toward the pointer.
  const target = { x: 0, y: 0 };
  window.addEventListener("pointermove", (e) => {
    target.x = (e.clientX / window.innerWidth - 0.5) * 1.6;
    target.y = (e.clientY / window.innerHeight - 0.5) * 1.0;
  }, { passive: true });

  let running = true;
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
    if (running) tick();
  });

  let t = 0;
  function tick() {
    if (!running) return;
    requestAnimationFrame(tick);
    t += 0.01;
    for (const b of balls) {
      b.rotation.x += b.userData.spin;
      b.rotation.y += b.userData.spin * 1.4;
      b.position.y += Math.sin(t + b.userData.phase) * b.userData.drift;
    }
    camera.position.x += (target.x - camera.position.x) * 0.03;
    camera.position.y += (-target.y - camera.position.y) * 0.03;
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
  }
  tick();
}

/* ------------------------------------------------------- top-bar 3D mark */
function initMark() {
  const host = document.getElementById("topbarMark");
  if (!host) return;
  const canvas = document.createElement("canvas");
  host.appendChild(canvas);
  const renderer = makeRenderer(canvas);
  if (!renderer) { host.remove(); return; }

  const size = 44;
  renderer.setSize(size, size, false);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 50);
  camera.position.z = 4.2;
  scene.add(new THREE.AmbientLight(0xffffff, 1.2));
  const d = new THREE.DirectionalLight(0xfff0cf, 1.6);
  d.position.set(2, 3, 4);
  scene.add(d);

  const ball = makeBall(1.25, 1);
  scene.add(ball);

  (function spin() {
    requestAnimationFrame(spin);
    if (document.hidden) return;
    ball.rotation.y += reduceMotion ? 0 : 0.012;
    ball.rotation.x += reduceMotion ? 0 : 0.004;
    renderer.render(scene, camera);
  })();
}

initBackdrop();
initMark();
