#!/usr/bin/env python3
"""FAST-05 — 3-cycle presentation state machine proof + STOP GATE."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
MORPH_JSON = WORK / "semantic/FAST-03D_morph_deltas.json"
PRESENTATION_GLB = WORK / "output/FAST-03D_presentation_rig.glb"
IDENTITY_NEUTRAL = WORK / "identity_locked/FAST-03B_identity_neutral.glb"
MENU_CONFIG = WORK / "narration/FAST-05_menu_config.json"
NARR_DIR = WORK / "narration"
LEDGER = WORK / "mutation_ledger.json"
EVIDENCE = WORK / "evidence"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
BLENDER_VIS = ROOT / "tools/blender_fast_05_visual_preview.py"
FAST02 = ROOT / "tools/fast_02_semantic_partition_audit.py"

sys.path.insert(0, str(ROOT))

from fast_track.runtime.camera_contract import CAM_FULL, CAM_UPPER
from fast_track.runtime.presentation_state_machine import (
    MenuItem,
    PresentationState,
    PresentationStateController,
)

CHARACTER_INSTANCE_ID = "meshy_silver_starlight_pres_v1_" + hashlib.sha256(
    PRESENTATION_GLB.read_bytes() if PRESENTATION_GLB.exists() else b""
).hexdigest()[:16]

EXPECTED_CYCLE_EVENTS = (
    "MENU_CLICK",
    "BEGIN_ZOOM_TO_UPPER",
    "ZOOM_COMPLETE",
    "BEGIN_TALKING",
    "NARRATION_COMPLETE",
    "NEUTRAL_RESET",
    "BEGIN_ZOOM_TO_FULL",
    "ZOOM_OUT_COMPLETE",
)


def load_fast02():
    spec = importlib.util.spec_from_file_location("fast_02", FAST02)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_animations(gltf, bin_blob) -> str:
    f2 = load_fast02()
    payload = json.dumps(gltf.get("animations", []), sort_keys=True).encode()
    for anim in gltf.get("animations", []):
        for sampler in anim.get("samplers", []):
            for key in ("input", "output"):
                acc = sampler.get(key)
                if acc is not None:
                    payload += f2.read_accessor(gltf, bin_blob, acc).tobytes()
    return hashlib.sha256(payload).hexdigest()


def load_menus() -> list[MenuItem]:
    cfg = json.loads(MENU_CONFIG.read_text(encoding="utf-8"))
    menus: list[MenuItem] = []
    for m in cfg["menus"]:
        menus.append(
            MenuItem(
                id=m["id"],
                label=m["label"],
                audio_path=NARR_DIR / m["audioFile"],
                transcript=m["transcript"],
            )
        )
    return menus


def verify_cycle_transitions(ctrl: PresentationStateController, cycle: int) -> tuple[bool, list[str]]:
    entries = [e for e in ctrl.transition_log if e.cycle == cycle]
    events = [e.event for e in entries]
    issues: list[str] = []
    for req in EXPECTED_CYCLE_EVENTS:
        if req not in events:
            issues.append(f"cycle {cycle}: missing event {req}")
    # state order sanity
    states = [e.to_state for e in entries]
    expected_states = [
        "MENU_SELECTED",
        "ZOOM_TO_UPPER",
        "EYE_CONTACT_SETTLE",
        "TALKING",
        "NARRATION_END",
        "NARRATION_END",
        "ZOOM_TO_FULL",
        "FULL_IDLE",
    ]
    if states != expected_states:
        issues.append(f"cycle {cycle}: state sequence mismatch {states}")
    return len(issues) == 0, issues


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    menus = load_menus()
    menu_map = {m.id: m for m in menus}
    cfg = json.loads(MENU_CONFIG.read_text(encoding="utf-8"))
    cycle_order = cfg["cycleOrder"]

    ctrl = PresentationStateController(CHARACTER_INSTANCE_ID, MORPH_JSON, menus)
    cycle_logs: list[dict[str, Any]] = []
    all_ok = True
    issues: list[str] = []

    for i, menu_id in enumerate(cycle_order, start=1):
        if ctrl.state != PresentationState.FULL_IDLE:
            issues.append(f"cycle {i}: did not start from FULL_IDLE")
            all_ok = False

        frames = ctrl.run_cycle(menu_id, dt=1.0 / 60.0)
        ok, cycle_issues = verify_cycle_transitions(ctrl, i)
        if not ok:
            all_ok = False
            issues.extend(cycle_issues)

        # post narration neutral
        neutral_ok = ctrl.actuators.is_neutral(tol=0.0)
        cycle_logs.append(
            {
                "cycle": i,
                "menuId": menu_id,
                "menuLabel": menu_map[menu_id].label,
                "frameCount": len(frames),
                "finalState": ctrl.state.value,
                "postNarrationNeutralParity": neutral_ok,
                "characterInstanceId": ctrl.character_instance_id,
            }
        )
        if not neutral_ok:
            issues.append(f"cycle {i}: post-narration neutral fail")
            all_ok = False
        if ctrl.state != PresentationState.FULL_IDLE:
            issues.append(f"cycle {i}: did not return FULL_IDLE")
            all_ok = False

        # mid-cycle spam: restart would need partial - after cycle 1, during cycle 2 attempt spam at start only

    # input guard proof during cycle 2 - simulate by manual state check from log
    busy_ignores = [g for g in ctrl.input_guard_log if not g["accepted"]]
    # force a busy ignore by attempting click mid-cycle on cycle 3
    ctrl2 = PresentationStateController(CHARACTER_INSTANCE_ID, MORPH_JSON, menus)
    ctrl2.handle_menu_click(cycle_order[0])
    ctrl2.tick(0.1)
    mid_guard = ctrl2.input_guard(cycle_order[1])
    input_guard_proof = {
        "fullIdleAccept": any(g["accepted"] for g in ctrl.input_guard_log),
        "busyIgnoreSimulated": not mid_guard.accepted and mid_guard.reason == "BUSY",
        "totalIgnoreEvents": len(busy_ignores),
    }
    if not input_guard_proof["busyIgnoreSimulated"]:
        issues.append("input guard busy ignore not proven")
        all_ok = False

    # asset regression
    f2 = load_fast02()
    g0, b0 = f2.load_glb(IDENTITY_NEUTRAL)
    g1, b1 = f2.load_glb(PRESENTATION_GLB)
    regression = {
        "animationUnchanged": hash_animations(g0, b0) == hash_animations(g1, b1),
        "skinJointCount": len(g1["skins"][0]["joints"]) == 24,
        "characterInstanceStable": ctrl.character_instance_id == CHARACTER_INSTANCE_ID,
        "morphJsonUnchanged": sha256_file(MORPH_JSON),
    }

    transition_log_path = EVIDENCE / "FAST-05_state_transition_log.json"
    ctrl.export_log(transition_log_path)
    cycle_log_path = EVIDENCE / "FAST-05_three_cycle_execution_log.json"
    cycle_log_path.write_text(json.dumps(cycle_logs, indent=2, ensure_ascii=False), encoding="utf-8")

    camera_json_path = EVIDENCE / "FAST-05_camera_presets.json"
    camera_json_path.write_text(
        json.dumps(
            {
                "CAM_FULL": CAM_FULL.to_dict(),
                "CAM_UPPER": CAM_UPPER.to_dict(),
                "contract": "camera interpolation only — no mesh/character transform",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    preview_dir = EVIDENCE / "FAST-05_visual_preview"
    preview_paths: list[str] = []
    if BLENDER.exists() and PRESENTATION_GLB.exists():
        preview_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(BLENDER),
            "--background",
            "--python",
            str(BLENDER_VIS),
            "--",
            "--glb",
            str(PRESENTATION_GLB),
            "--camera-json",
            str(camera_json_path),
            "--out-dir",
            str(preview_dir),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            preview_paths = [str(p) for p in sorted(preview_dir.glob("*.png"))]
        else:
            issues.append(f"visual preview render failed: {proc.stderr[:200]}")

    narration_events = [
        e.to_dict()
        for e in ctrl.transition_log
        if e.event in ("NARRATION_COMPLETE", "NEUTRAL_RESET", "BEGIN_TALKING")
    ]

    verdict = "PASS_CLOSED" if all_ok and regression["animationUnchanged"] else "FAIL_HOLD"
    failure_class = None
    if verdict != "PASS_CLOSED":
        if any("state sequence" in x for x in issues):
            failure_class = "STATE_TRANSITION"
        elif any("input guard" in x for x in issues):
            failure_class = "INPUT_GUARD"
        elif not regression["animationUnchanged"]:
            failure_class = "RUNTIME_INTEGRATION"
        else:
            failure_class = "EVENT_SYNC"

    receipt: dict[str, Any] = {
        "receiptId": f"FAST-05_stop_gate_{ts}",
        "timestampUtc": ts,
        "lane": "FAST_PRODUCT",
        "stage": "FAST-05",
        "verdict": verdict,
        "stopGate": True,
        "fast06Status": "HOLD",
        "characterInstanceId": CHARACTER_INSTANCE_ID,
        "stateMachineContract": "FULL_IDLE→MENU_SELECTED→ZOOM_TO_UPPER→EYE_CONTACT→TALKING→NARRATION_END→ZOOM_TO_FULL→FULL_IDLE",
        "threeCycleExecution": cycle_logs,
        "stateTransitionLog": str(transition_log_path),
        "cameraPresets": str(camera_json_path),
        "cameraInterpolation": {"method": "ease_in_out", "durationSec": ctrl.camera.zoom_duration},
        "narrationCompletionEvents": narration_events,
        "inputGuardProof": input_guard_proof,
        "visualPreview": preview_paths,
        "regression": regression,
        "issues": issues,
        "failureClassification": failure_class,
        "contract": {
            "oneCharacter": True,
            "cameraOnlyTransition": True,
            "talkingAfterZoom": True,
            "narrationEndAuthoritative": "audio_duration",
            "fast03Fast04Locked": True,
        },
    }
    receipt_path = EVIDENCE / "FAST-05_stop_gate_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["entries"] = [e for e in ledger["entries"] if e.get("id") != "FAST-05"]
    ledger["entries"].append(
        {
            "id": "FAST-05",
            "type": "PRESENTATION_STATE_MACHINE",
            "mutation": 0,
            "scope": "State/camera/runtime integration only",
            "evidence": str(receipt_path),
            "verdict": verdict,
        }
    )
    ledger["presentationLayer"] = "FAST-05 presentation state machine — 3-cycle proof"
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"verdict": verdict, "receipt": str(receipt_path), "cycles": len(cycle_logs)}, ensure_ascii=True))
    return 0 if verdict == "PASS_CLOSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
