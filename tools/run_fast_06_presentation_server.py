"""FAST-06 Flask server — UI consumer for FAST-05 state machine."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
APP_DIR = ROOT / "fast_track/presentation_app"
STATIC = APP_DIR / "static"
MORPH_JSON = WORK / "semantic/FAST-03D_morph_deltas.json"
MENU_CONFIG = WORK / "narration/FAST-05_menu_config.json"
NARR_DIR = WORK / "narration"
GLB = Path(os.environ.get("NURION_PRESENTATION_GLB", str(WORK / "output/FAST-03D_presentation_rig.glb")))

import sys

sys.path.insert(0, str(ROOT))

from fast_track.runtime.camera_contract import CAM_FULL, CAM_UPPER, PRES_CAMERA_UPPER_ANCHOR
from fast_track.runtime.facial_performance import FacialPerformanceRuntime
from fast_track.runtime.presentation_state_machine import MenuItem, PresentationState, PresentationStateController

CHARACTER_INSTANCE_ID = "meshy_silver_starlight_pres_v1_" + hashlib.sha256(
    GLB.read_bytes() if GLB.exists() else b""
).hexdigest()[:16]

MORPH_TARGETS = list(json.loads(MORPH_JSON.read_text(encoding="utf-8"))["shapeKeys"].keys())
PRESENTATION_ZOOM_DURATION_SEC = 1.35
FACIAL_TRACK_FPS = 30.0


def _bake_facial_track(facial: FacialPerformanceRuntime) -> dict:
    frames = [
        {"t": fr["timeSec"], "weights": fr["weights"]}
        for fr in facial.simulate(fps=FACIAL_TRACK_FPS)
    ]
    return {
        "fps": FACIAL_TRACK_FPS,
        "durationSec": facial.duration,
        "frames": frames,
    }


def _load_menus() -> list[MenuItem]:
    cfg = json.loads(MENU_CONFIG.read_text(encoding="utf-8"))
    return [
        MenuItem(
            id=m["id"],
            label=m["label"],
            audio_path=NARR_DIR / m["audioFile"],
            transcript=m["transcript"],
        )
        for m in cfg["menus"]
    ]


class PresentationAppState:
    def __init__(self):
        self.ctrl = PresentationStateController(
            CHARACTER_INSTANCE_ID,
            MORPH_JSON,
            _load_menus(),
            zoom_duration=PRESENTATION_ZOOM_DURATION_SEC,
        )
        self.last_successful_menu_id: str | None = None
        self._lock = threading.Lock()
        self._prev_state = PresentationState.FULL_IDLE.value
        self.e2e_log: list[dict] = []
        self._facial_track_cycle: int | None = None
        self._cached_facial_track: dict | None = None

    def snapshot(self, snap: dict) -> dict:
        snap = dict(snap)
        snap["menuEnabled"] = self.ctrl.state == PresentationState.FULL_IDLE
        snap["uiBusy"] = not snap["menuEnabled"]
        snap["characterInstanceId"] = self.ctrl.character_instance_id
        if self.ctrl._selected_menu:
            snap["activeMenuId"] = self.ctrl._selected_menu.id
            snap["activeMenuLabel"] = self.ctrl._selected_menu.label
        if self.ctrl.state == PresentationState.TALKING and self.ctrl._selected_menu:
            m = self.ctrl._selected_menu
            snap["audioUrl"] = f"/assets/audio/{m.audio_path.name}"
        if self.ctrl.state == PresentationState.TALKING and self.ctrl._facial is not None:
            if self._facial_track_cycle != self.ctrl.cycle_index:
                self._cached_facial_track = _bake_facial_track(self.ctrl._facial)
                self._facial_track_cycle = self.ctrl.cycle_index
                snap["facialTrack"] = self._cached_facial_track
        if self.ctrl.state == PresentationState.FULL_IDLE:
            self._facial_track_cycle = None
            self._cached_facial_track = None
        if self.ctrl.state.value != self._prev_state:
            snap["stateChanged"] = True
            snap["previousState"] = self._prev_state
            if self.ctrl.state == PresentationState.TALKING:
                snap["audioStart"] = True
            self._prev_state = self.ctrl.state.value
        else:
            snap["stateChanged"] = False
        return snap

    def advance(self, dt: float) -> dict:
        remaining = max(0.0, min(float(dt), 0.25))
        snap: dict = {}
        with self._lock:
            while remaining > 1e-6:
                step = min(remaining, 1.0 / 60.0)
                snap = self.snapshot(self.ctrl.tick(step))
                remaining -= step
            if (
                self.ctrl.state == PresentationState.FULL_IDLE
                and self.ctrl.transition_log
                and self.ctrl.transition_log[-1].event == "ZOOM_OUT_COMPLETE"
            ):
                for entry in reversed(self.ctrl.transition_log):
                    if entry.event == "MENU_CLICK":
                        self.last_successful_menu_id = entry.detail.get("menuId")
                        break
        return snap

    def tick(self, dt: float) -> dict:
        return self.advance(dt)

    def click_menu(self, menu_id: str) -> dict:
        with self._lock:
            if menu_id == "replay":
                if not self.last_successful_menu_id:
                    return {"ok": False, "reason": "NO_REPLAY_HISTORY"}
                menu_id = self.last_successful_menu_id
            ok = self.ctrl.handle_menu_click(menu_id)
            result = {
                "ok": ok,
                "menuId": menu_id,
                "state": self.ctrl.state.value,
                "uiBusy": self.ctrl.state != PresentationState.FULL_IDLE,
            }
            self.e2e_log.append({"action": "menu_click", **result})
            return result


app_state = PresentationAppState()
app = Flask(__name__, static_folder=str(STATIC), static_url_path="")


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/config")
def config():
    cfg = json.loads(MENU_CONFIG.read_text(encoding="utf-8"))
    return jsonify(
        {
            "characterInstanceId": CHARACTER_INSTANCE_ID,
            "morphTargets": MORPH_TARGETS,
            "menus": cfg["menus"],
            "glbUrl": "/assets/character.glb",
            "replayMenuId": "replay",
            "fast05Consumer": True,
            "presentationLayer": os.environ.get("NURION_PRESENTATION_LAYER", "FAST-06R1.5"),
            "cameraPresets": {
                "CAM_FULL": CAM_FULL.to_dict(),
                "CAM_UPPER": CAM_UPPER.to_dict(),
            },
            "upperPresentationAnchor": list(PRES_CAMERA_UPPER_ANCHOR),
            "zoomDurationSec": PRESENTATION_ZOOM_DURATION_SEC,
        }
    )


@app.post("/api/tick")
def tick():
    data = request.get_json(silent=True) or {}
    dt = float(data.get("dt", 1.0 / 60.0))
    return jsonify(app_state.tick(dt))


@app.get("/api/state")
def state():
    with app_state._lock:
        snap = app_state.snapshot(
            {
                "state": app_state.ctrl.state.value,
                "camera": app_state.ctrl.camera.state().to_dict(),
                "cycle": app_state.ctrl.cycle_index,
                "weightsNeutral": app_state.ctrl.actuators.is_neutral(tol=0.0),
                "timeSec": round(app_state.ctrl.global_time, 4),
            }
        )
        w = app_state.ctrl.actuators.all_weights()
        if any(v > 0 for v in w.values()):
            snap["facialWeights"] = w
        return jsonify(snap)


@app.post("/api/menu/<menu_id>")
def menu_click(menu_id: str):
    return jsonify(app_state.click_menu(menu_id))


@app.get("/assets/character.glb")
def character_glb():
    return send_from_directory(GLB.parent, GLB.name)


@app.get("/assets/audio/<path:filename>")
def audio_file(filename: str):
    return send_from_directory(NARR_DIR, filename)


def create_app():
    return app


if __name__ == "__main__":
    port = int(os.environ.get("FAST06_PORT", "8765"))
    host = "127.0.0.1"
    print(f"NURION Presentation Character v0 -> http://{host}:{port}")
    print("Press Ctrl+C to stop")
    import sys
    sys.stdout.flush()
    try:
        from waitress import serve

        serve(app, host=host, port=port, threads=4)
    except ImportError:
        app.run(host=host, port=port, debug=False, threaded=True)
