import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const canvas = document.getElementById('viewport');
const bootMsg = document.getElementById('boot-msg');
const stateOverlay = document.getElementById('state-overlay');
const statusBadge = document.getElementById('status-badge');
const menuButtons = [...document.querySelectorAll('.menu-btn')];

const PRES_ACTUATORS = [
  'PRES_JawOpen',
  'PRES_Blink_L',
  'PRES_Blink_R',
  'PRES_Viseme_A',
  'PRES_Viseme_E',
  'PRES_Viseme_O',
  'PRES_Viseme_M',
  'PRES_SmileMild',
];

const DEBUG_KIND = new URLSearchParams(window.location.search).get('debug');
const DEBUG_MORPH = DEBUG_KIND === 'morph';
const DEBUG_BLINK = DEBUG_KIND === 'blink';
const DEBUG_MODE = DEBUG_MORPH || DEBUG_BLINK;
const DEBUG_SEQUENCE = [
  { label: 'Neutral', weights: {}, sec: 1.4 },
  { label: 'JawOpen', weights: { PRES_JawOpen: 1.0 }, sec: 1.4 },
  { label: 'Blink', weights: { PRES_Blink_L: 1.0, PRES_Blink_R: 1.0 }, sec: 1.4 },
  { label: 'SmileMild', weights: { PRES_SmileMild: 1.0 }, sec: 1.4 },
  { label: 'Viseme_A', weights: { PRES_Viseme_A: 1.0 }, sec: 1.4 },
  { label: 'Neutral', weights: {}, sec: 1.4 },
];

let config = null;
let charMesh = null;
let presentationMorphBindings = [];
let morphIndex = {};
let mixer = null;
let idleAction = null;
let clientCam = null;
let prevSnapState = 'FULL_IDLE';
let audioEl = null;
let lastFrame = performance.now();
let tickInFlight = false;

let facialTrack = null;
let talkingStartMs = 0;
let currentSnapState = 'FULL_IDLE';
let facialFrameCursor = 0;

let debugStep = 0;
let debugStepStart = 0;
let debugPauseStart = 0;
let debugBlinkStart = 0;

window.__setMorphDebugFrozen = (frozen) => {
  if (!DEBUG_MODE) return;
  const now = performance.now();
  if (frozen && !debugPauseStart) {
    debugPauseStart = now;
  } else if (!frozen && debugPauseStart) {
    if (debugStepStart) debugStepStart += now - debugPauseStart;
    if (debugBlinkStart) debugBlinkStart += now - debugPauseStart;
    debugPauseStart = 0;
  }
};

const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: false,
  powerPreference: 'high-performance',
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.25));
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x12151c);

const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 100);

scene.add(new THREE.HemisphereLight(0xffffff, 0x333344, 1.1));
const dir = new THREE.DirectionalLight(0xffffff, 1.4);
dir.position.set(2, 4, 3);
scene.add(dir);
const fill = new THREE.DirectionalLight(0xaabbff, 0.35);
fill.position.set(-2, 1, 2);
scene.add(fill);

function easeInOut(t) {
  const x = Math.max(0, Math.min(1, t));
  return x * x * (3 - 2 * x);
}

class ClientCamera {
  constructor(fullPreset, upperPreset, zoomDurationSec) {
    this.full = fullPreset;
    this.upper = upperPreset;
    this.zoomDuration = zoomDurationSec;
    this.zooming = false;
    this.elapsed = 0;
    this.from = this._clonePreset(fullPreset);
    this.to = this._clonePreset(fullPreset);
    this.current = this._clonePreset(fullPreset);
  }

  _clonePreset(p) {
    return {
      location: [...p.location],
      target: [...p.target],
      fov: p.fov_deg ?? p.fovDeg ?? 42,
    };
  }

  _applyPreset(out, p) {
    out.location = [...p.location];
    out.target = [...p.target];
    out.fov = p.fov_deg ?? p.fovDeg ?? 42;
  }

  snapToFull() {
    this.zooming = false;
    this.elapsed = 0;
    this._applyPreset(this.current, this.full);
    this._applyPreset(this.from, this.full);
    this._applyPreset(this.to, this.full);
  }

  snapToUpper() {
    this.zooming = false;
    this.elapsed = 0;
    this._applyPreset(this.current, this.upper);
    this._applyPreset(this.from, this.upper);
    this._applyPreset(this.to, this.upper);
  }

  beginZoomToUpper() {
    this._applyPreset(this.from, this.current);
    this._applyPreset(this.to, this.upper);
    this.elapsed = 0;
    this.zooming = true;
  }

  beginZoomToFull() {
    this._applyPreset(this.from, this.current);
    this._applyPreset(this.to, this.full);
    this.elapsed = 0;
    this.zooming = true;
  }

  tick(dt) {
    if (!this.zooming) return;
    this.elapsed += dt;
    const t = easeInOut(Math.min(1, this.elapsed / Math.max(this.zoomDuration, 1e-6)));
    const f = this.from;
    const to = this.to;
    this.current.location[0] = f.location[0] + (to.location[0] - f.location[0]) * t;
    this.current.location[1] = f.location[1] + (to.location[1] - f.location[1]) * t;
    this.current.location[2] = f.location[2] + (to.location[2] - f.location[2]) * t;
    this.current.target[0] = f.target[0] + (to.target[0] - f.target[0]) * t;
    this.current.target[1] = f.target[1] + (to.target[1] - f.target[1]) * t;
    this.current.target[2] = f.target[2] + (to.target[2] - f.target[2]) * t;
    // R1.3-B: FOV fixed during transition; snap only at end
    this.current.fov = f.fov;
    if (t >= 1) {
      this.zooming = false;
      this._applyPreset(this.current, to);
    }
  }

  applyToThreeCam(threeCam) {
    threeCam.position.set(this.current.location[0], this.current.location[1], this.current.location[2]);
    threeCam.lookAt(this.current.target[0], this.current.target[1], this.current.target[2]);
    threeCam.fov = this.current.fov;
    threeCam.updateProjectionMatrix();
  }
}

function resize() {
  const wrap = document.getElementById('viewport-wrap');
  const w = wrap.clientWidth;
  const h = Math.max(wrap.clientHeight, 480);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

function enableMorphMaterials(mesh) {
  const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  mats.forEach((mat) => {
    if (!mat) return;
    mat.morphTargets = true;
    mat.morphNormals = true;
    mat.needsUpdate = true;
  });
}

function bindPresentationMorphMeshes(gltf, actuatorNames) {
  gltf.scene.traverse((obj) => {
    if (!obj.isMesh) return;
    if (obj.name === 'char1') charMesh = obj;
    const dict = obj.morphTargetDictionary || {};
    const influences = obj.morphTargetInfluences || [];
    const indices = {};
    actuatorNames.forEach((name) => {
      if (dict[name] !== undefined) indices[name] = dict[name];
      else if (obj.name === 'char1' && influences.length === actuatorNames.length) {
        const i = actuatorNames.indexOf(name);
        if (i >= 0) indices[name] = i;
      }
    });
    if (Object.keys(indices).length) {
      enableMorphMaterials(obj);
      presentationMorphBindings.push({ mesh: obj, indices });
      Object.entries(indices).forEach(([name, index]) => {
        if (morphIndex[name] === undefined) morphIndex[name] = index;
      });
    }
  });
  if (!charMesh) {
    throw new Error('char1 structural mesh not found in presentation GLB');
  }
  if (!presentationMorphBindings.length) {
    throw new Error('No presentation morph mesh found in presentation GLB');
  }
}

function buildMorphProbe(extra = {}) {
  const rendererSide = {};
  PRES_ACTUATORS.forEach((name) => {
    const values = presentationMorphBindings
      .filter((binding) => binding.indices[name] !== undefined)
      .map((binding) => binding.mesh.morphTargetInfluences[binding.indices[name]]);
    rendererSide[name] = values.length ? Math.max(...values) : null;
  });
  const meshRegistry = presentationMorphBindings.map(({ mesh, indices }) => {
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    return {
      meshName: mesh.name,
      isSkinnedMesh: !!mesh.isSkinnedMesh,
      actuatorIndices: { ...indices },
      morphTargetDictionary: { ...(mesh.morphTargetDictionary || {}) },
      morphTargetInfluencesLength: mesh.morphTargetInfluences?.length ?? 0,
      materialMorphTargetsEnabled: mats.map((m) => !!m?.morphTargets),
    };
  });
  return {
    meshName: charMesh?.name ?? null,
    isSkinnedMesh: !!charMesh?.isSkinnedMesh,
    presentationMeshRegistry: meshRegistry,
    presentationMeshCount: meshRegistry.length,
    presActuators: PRES_ACTUATORS.map((name) => ({
      name,
      index: morphIndex[name] ?? null,
      present: morphIndex[name] !== undefined,
      rendererInfluence: rendererSide[name],
    })),
    allPresPresent: PRES_ACTUATORS.every((n) => morphIndex[n] !== undefined),
    allBlinkPresent: ['PRES_Blink_L', 'PRES_Blink_R'].every((n) => morphIndex[n] !== undefined),
    glbUrl: config?.glbUrl ?? null,
    ...extra,
  };
}

async function loadConfig() {
  const res = await fetch('/api/config');
  config = await res.json();
  clientCam = new ClientCamera(
    config.cameraPresets.CAM_FULL,
    config.cameraPresets.CAM_UPPER,
    config.zoomDurationSec ?? 1.05,
  );
  clientCam.applyToThreeCam(camera);
}

async function loadCharacter() {
  const loader = new GLTFLoader();
  return new Promise((resolve, reject) => {
    loader.load(config.glbUrl, (gltf) => {
      scene.add(gltf.scene);
      bindPresentationMorphMeshes(gltf, config.morphTargets || PRES_ACTUATORS);
      window.__morphProbe = buildMorphProbe({ phase: 'post_load' });
      console.info('[FAST-06R1.3 morph probe]', window.__morphProbe);
      if (gltf.animations?.length) {
        mixer = new THREE.AnimationMixer(gltf.scene);
        idleAction = mixer.clipAction(gltf.animations[0]);
        idleAction.play();
      }
      resolve(gltf);
    }, undefined, reject);
  });
}

function resetPresMorphs() {
  presentationMorphBindings.forEach(({ mesh, indices }) => {
    Object.values(indices).forEach((index) => {
      mesh.morphTargetInfluences[index] = 0;
    });
    mesh.morphTargetInfluencesNeedUpdate = true;
  });
}

function applyPresMorphWeights(weights) {
  presentationMorphBindings.forEach(({ mesh, indices }) => {
    Object.entries(indices).forEach(([name, index]) => {
      mesh.morphTargetInfluences[index] = weights?.[name] ?? 0;
    });
    mesh.morphTargetInfluencesNeedUpdate = true;
  });
}

function sampleFacialTrack(track, tSec) {
  const frames = track.frames;
  if (!frames?.length) return null;
  if (tSec <= frames[0].t) return frames[0].weights;
  if (tSec >= track.durationSec) return frames[frames.length - 1].weights;
  let i = Math.min(facialFrameCursor, frames.length - 2);
  while (i > 0 && tSec < frames[i].t) i -= 1;
  while (i < frames.length - 2 && tSec > frames[i + 1].t) i += 1;
  facialFrameCursor = i;
  const a = frames[i];
  const b = frames[i + 1];
  const u = (tSec - a.t) / Math.max(b.t - a.t, 1e-6);
  const out = {};
  PRES_ACTUATORS.forEach((key) => {
    out[key] = (a.weights[key] ?? 0) + ((b.weights[key] ?? 0) - (a.weights[key] ?? 0)) * u;
  });
  return out;
}

function talkingTimeSec(now) {
  if (audioEl && !Number.isNaN(audioEl.currentTime) && audioEl.currentTime > 0) {
    return audioEl.currentTime;
  }
  return (now - talkingStartMs) / 1000;
}

function setMenuEnabled(enabled) {
  if (DEBUG_MODE) return;
  menuButtons.forEach((btn) => {
    btn.disabled = !enabled;
    btn.classList.toggle('busy-flash', !enabled);
  });
  statusBadge.textContent = enabled ? 'READY' : 'BUSY';
  statusBadge.classList.toggle('busy', !enabled);
}

async function playAudio(url) {
  if (audioEl) {
    audioEl.pause();
    audioEl = null;
  }
  audioEl = new Audio(url);
  audioEl.volume = 1;
  try {
    await audioEl.play();
  } catch (e) {
    console.warn('audio play blocked', e);
  }
}

function applySnapshot(snap) {
  if (DEBUG_MODE) return;
  currentSnapState = snap.state;
  stateOverlay.textContent = `${snap.state} | cycle ${snap.cycle}`;
  setMenuEnabled(snap.menuEnabled);

  if (snap.facialTrack) {
    facialTrack = snap.facialTrack;
    facialFrameCursor = 0;
    talkingStartMs = performance.now();
  }

  if (snap.state === 'ZOOM_TO_UPPER' && !clientCam.zooming) {
    clientCam.beginZoomToUpper();
  }
  if (snap.state === 'ZOOM_TO_FULL' && prevSnapState !== 'ZOOM_TO_FULL') {
    clientCam.beginZoomToFull();
  }
  if (snap.state === 'TALKING' && prevSnapState !== 'TALKING') {
    talkingStartMs = performance.now();
    if (snap.audioUrl) playAudio(snap.audioUrl);
  }
  if (snap.state === 'FULL_IDLE' && prevSnapState !== 'FULL_IDLE') {
    if (audioEl) {
      audioEl.pause();
      audioEl = null;
    }
    facialTrack = null;
    clientCam.snapToFull();
    resetPresMorphs();
  }

  if (snap.state === 'TALKING' && snap.facialTrack) {
    window.__morphProbe = buildMorphProbe({
      phase: 'talking_track_received',
      sampleWeights: sampleFacialTrack(snap.facialTrack, 0.5),
    });
  }

  prevSnapState = snap.state;
}

function pushServerTick(dt) {
  if (DEBUG_MODE || tickInFlight) return;
  tickInFlight = true;
  fetch('/api/tick', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dt }),
  })
    .then((res) => res.json())
    .then((snap) => applySnapshot(snap))
    .catch((e) => console.error(e))
    .finally(() => { tickInFlight = false; });
}

function updateDebugMorph(now) {
  if (debugPauseStart) return;
  if (!debugStepStart) debugStepStart = now;
  const step = DEBUG_SEQUENCE[debugStep];
  const elapsed = (now - debugStepStart) / 1000;
  if (elapsed >= step.sec) {
    debugStep = (debugStep + 1) % DEBUG_SEQUENCE.length;
    debugStepStart = now;
  }
  const active = DEBUG_SEQUENCE[debugStep];
  applyPresMorphWeights(active.weights);
  stateOverlay.textContent = `DEBUG_MORPH | ${active.label}`;
  statusBadge.textContent = 'DEBUG';
  window.__morphProbe = buildMorphProbe({
    phase: 'debug_actuator_probe',
    debugLabel: active.label,
    requestedWeights: active.weights,
  });
}

function smoothstep01(value) {
  const t = Math.min(1, Math.max(0, value));
  return t * t * (3 - 2 * t);
}

function updateDebugBlink(now) {
  if (debugPauseStart) return;
  if (!debugBlinkStart) debugBlinkStart = now;
  const periodSec = 2.4;
  const neutralLeadSec = 0.8;
  const closeSec = 0.16;
  const closedHoldSec = 0.08;
  const reopenSec = 0.24;
  const t = ((now - debugBlinkStart) / 1000) % periodSec;
  let weight = 0;
  let label = 'Neutral';

  if (t >= neutralLeadSec && t < neutralLeadSec + closeSec) {
    const p = (t - neutralLeadSec) / closeSec;
    weight = smoothstep01(p);
    label = 'BlinkClosing';
  } else if (t < neutralLeadSec + closeSec + closedHoldSec && t >= neutralLeadSec + closeSec) {
    weight = 1;
    label = 'BlinkClosed';
  } else if (t < neutralLeadSec + closeSec + closedHoldSec + reopenSec
      && t >= neutralLeadSec + closeSec + closedHoldSec) {
    const p = (t - neutralLeadSec - closeSec - closedHoldSec) / reopenSec;
    weight = 1 - smoothstep01(p);
    label = 'BlinkReopening';
  }

  const weights = { PRES_Blink_L: weight, PRES_Blink_R: weight };
  applyPresMorphWeights(weights);
  stateOverlay.textContent = `DEBUG_BLINK | ${label} | ${weight.toFixed(3)}`;
  statusBadge.textContent = 'DEBUG';
  window.__morphProbe = buildMorphProbe({
    phase: 'debug_anatomical_blink',
    debugLabel: label,
    requestedWeights: weights,
    blinkWeight: weight,
    closeDurationMs: 160,
    reopenDurationMs: 240,
  });
}

window.__setBlinkDebugPose = (weight, label) => {
  if (!DEBUG_BLINK) return null;
  window.__setMorphDebugFrozen(true);
  const synchronizedWeight = Math.min(1, Math.max(0, Number(weight)));
  const weights = {
    PRES_Blink_L: synchronizedWeight,
    PRES_Blink_R: synchronizedWeight,
  };
  applyPresMorphWeights(weights);
  stateOverlay.textContent = `DEBUG_BLINK | ${label} | ${synchronizedWeight.toFixed(3)}`;
  window.__morphProbe = buildMorphProbe({
    phase: 'debug_anatomical_blink',
    debugLabel: label,
    requestedWeights: weights,
    blinkWeight: synchronizedWeight,
    closeDurationMs: 160,
    reopenDurationMs: 240,
  });
  return window.__morphProbe;
};

function frameLoop(now) {
  const dt = Math.min(0.05, (now - lastFrame) / 1000);
  lastFrame = now;

  if (clientCam) {
    clientCam.tick(dt);
    clientCam.applyToThreeCam(camera);
  }

  if (DEBUG_BLINK) {
    updateDebugBlink(now);
  } else if (DEBUG_MORPH) {
    updateDebugMorph(now);
  } else if (facialTrack && (currentSnapState === 'TALKING' || currentSnapState === 'NARRATION_END')) {
    const weights = sampleFacialTrack(facialTrack, talkingTimeSec(now));
    if (weights) {
      applyPresMorphWeights(weights);
      window.__morphProbe = buildMorphProbe({ phase: 'talking', sampleWeights: weights });
    }
  }

  if (mixer && !DEBUG_MODE) mixer.update(dt);
  renderer.render(scene, camera);
  requestAnimationFrame(frameLoop);
}

menuButtons.forEach((btn) => {
  btn.addEventListener('click', async () => {
    if (DEBUG_MODE) return;
    clientCam.beginZoomToUpper();
    const menuId = btn.dataset.menu;
    const res = await fetch(`/api/menu/${menuId}`, { method: 'POST' });
    const data = await res.json();
    if (!data.ok) console.warn('menu rejected', data);
  });
});

(async () => {
  await loadConfig();
  await loadCharacter();
  bootMsg.style.display = 'none';
  if (DEBUG_MODE) {
    setMenuEnabled(false);
    menuButtons.forEach((b) => { b.disabled = true; });
    clientCam.snapToUpper();
    stateOverlay.textContent = DEBUG_BLINK ? 'DEBUG_BLINK | starting' : 'DEBUG_MORPH | starting';
  } else {
    setMenuEnabled(true);
    setInterval(() => pushServerTick(1 / 20), 50);
  }
  requestAnimationFrame(frameLoop);
})();
