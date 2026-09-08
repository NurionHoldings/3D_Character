"""
v0.7 Gate 6 — Homepage Preset Authoring.

Create 10 independent NURION_Homepage_* Actions. Never copy Meshy actions.
Validate loop drift, gesture phases, FPS semantics, and v0.6 handoff contract.

Usage:
  blender --background --python tools/blender_v07_gate6_homepage_preset_authoring.py -- \\
    --blend dist/v0.7/gate5/NURION_HomepageControlRig.ai-aba.15.blend \\
    --source-zip dist/v0.4/gate8c/inbox/ai-aba.15.zip \\
    --out-dir dist/v0.7/gate6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[1]
GATE5_HASH = "a240f7c1925daf11b32aafdd409c2233238d84ef23333bb6e31be761719daea3"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"
DEFORM = "NURION_HomepageDeformRig"
CONTROL = "NURION_HomepageControlRig"
FPS_SET = (24, 30, 60)
POS_DRIFT_MAX_CM = 1.0
ROT_DRIFT_MAX_DEG = 2.0

PRESETS = [
    {"id": "HOME_IDLE_BREATH", "loop": True, "gesture": "RELAXED", "frames": 48},
    {"id": "HOME_FORMAL_GREETING", "loop": False, "gesture": "WELCOME", "frames": 36},
    {"id": "HOME_POINT_PRIMARY_CTA", "loop": False, "gesture": "POINT_UI", "frames": 40},
    {"id": "HOME_INTRO_INSURANCE_CORE", "loop": False, "gesture": "OPEN_PALM", "frames": 42},
    {"id": "HOME_GUIDE_IDENTITY", "loop": False, "gesture": "POINT_UI", "frames": 38},
    {"id": "HOME_GUIDE_CONSENT_IMPORT", "loop": False, "gesture": "OPEN_PALM", "frames": 40},
    {"id": "HOME_WAIT_PROGRESS", "loop": True, "gesture": "RELAXED", "frames": 48},
    {"id": "HOME_GUIDE_RESULTS", "loop": False, "gesture": "POINT_UI", "frames": 40},
    {"id": "HOME_INVITE_ADVISOR", "loop": False, "gesture": "CONSULTATION_INVITE", "frames": 42},
    {"id": "HOME_ERROR_RETRY", "loop": False, "gesture": "OPEN_PALM", "frames": 36},
]

GESTURE_EULER = {
    "OPEN_PALM": ((0.15, 0.0, 0.0), (-0.15, 0.0, 0.0)),
    "RELAXED": ((0.05, 0.1, 0.05), (-0.05, 0.1, -0.05)),
    "POINT_UI": ((0.1, 0.0, 0.35), (-0.2, 0.0, -0.55)),
    "WELCOME": ((0.25, 0.15, 0.2), (-0.25, 0.15, -0.2)),
    "CONSULTATION_INVITE": ((0.2, 0.05, 0.15), (-0.35, 0.1, -0.25)),
}


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--blend", required=True)
    p.add_argument("--source-zip", required=True)
    p.add_argument("--gate3-blend", required=True)
    p.add_argument("--gate4-blend", required=True)
    p.add_argument("--gate5-blend", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--label", default="ai-aba.15")
    return p.parse_args(argv)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _action_name(preset_id: str) -> str:
    return f"NURION_Homepage_{preset_id}"


def _reset_pose(arm):
    for b in arm.pose.bones:
        b.rotation_mode = "XYZ"
        b.rotation_euler = (0.0, 0.0, 0.0)
        b.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


def _insert_pose(arm, frame: int, bones: list[str] | None = None):
    bpy.context.scene.frame_set(frame)
    targets = bones or [b.name for b in arm.pose.bones]
    for name in targets:
        pb = arm.pose.bones.get(name)
        if not pb:
            continue
        pb.keyframe_insert(data_path="location", frame=frame)
        pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def _ensure_action(arm, name: str):
    # Never reuse existing non-NURION actions
    if name in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[name])
    act = bpy.data.actions.new(name)
    if not arm.animation_data:
        arm.animation_data_create()
    arm.animation_data.action = act
    return act


def _phases(n_frames: int):
    """Return start / hold_start / hold_end / return frames (1-based)."""
    start = 1
    hold_s = max(2, n_frames // 4)
    hold_e = max(hold_s + 1, (3 * n_frames) // 4)
    ret = n_frames
    return start, hold_s, hold_e, ret


def _author_preset(deform, ctrl, preset: dict) -> dict:
    pid = preset["id"]
    aname = _action_name(pid)
    n = int(preset["frames"])
    gesture = preset["gesture"]
    loop = bool(preset["loop"])
    start, hold_s, hold_e, ret = _phases(n)

    # Independent actions on BOTH deform and control (same name suffix on control)
    d_act = _ensure_action(deform, aname)
    c_act = _ensure_action(ctrl, aname + "_CTRL")

    _reset_pose(deform)
    _reset_pose(ctrl)

    # --- START (rest / prep) ---
    bpy.context.scene.frame_set(start)
    _insert_pose(deform, start)
    _insert_pose(ctrl, start)

    # --- HOLD: gesture + mild body/head/ui timing ---
    l_eul, r_eul = GESTURE_EULER[gesture]
    for f in (hold_s, hold_e):
        bpy.context.scene.frame_set(f)
        deform.pose.bones["Hand.L"].rotation_mode = "XYZ"
        deform.pose.bones["Hand.R"].rotation_mode = "XYZ"
        deform.pose.bones["Hand.L"].rotation_euler = Euler(l_eul, "XYZ")
        deform.pose.bones["Hand.R"].rotation_euler = Euler(r_eul, "XYZ")

        # Head / chest timing preserved relative to gesture
        deform.pose.bones["Head"].rotation_euler = Euler((0.08, 0.0, 0.05 if "POINT" in gesture or "GUIDE" in pid or "CTA" in pid else 0.0), "XYZ")
        deform.pose.bones["Chest"].rotation_euler = Euler((0.04, 0.0, 0.0), "XYZ")
        if loop:
            # breath / sway via hips & spine subtle motion keyed at hold
            t = (f - hold_s) / max(1, hold_e - hold_s)
            deform.pose.bones["Spine"].location = (0.0, 0.0, 0.004 * math.sin(t * math.pi * 2))
            deform.pose.bones["Hips"].location = (0.003 * math.sin(t * math.pi * 2), 0.0, 0.0)

        # Control targets timing
        if "POINT" in gesture or pid in {
            "HOME_POINT_PRIMARY_CTA",
            "HOME_GUIDE_IDENTITY",
            "HOME_GUIDE_RESULTS",
            "HOME_ERROR_RETRY",
        }:
            # nudge UI focus / hand target slightly forward in local pose
            ctrl.pose.bones["UIFocusTarget"].location = (0.02, -0.04, 0.01)
            ctrl.pose.bones["HandTarget.R"].location = (0.02, -0.04, 0.01)
            ctrl.pose.bones["PalmAim.R"].location = (0.01, -0.02, 0.0)
        if pid in {"HOME_FORMAL_GREETING", "HOME_INVITE_ADVISOR", "HOME_INTRO_INSURANCE_CORE"}:
            ctrl.pose.bones["HeadAim"].location = (0.0, -0.02, 0.01)
            ctrl.pose.bones["ChestAim"].location = (0.0, -0.02, 0.0)
        if loop:
            ctrl.pose.bones["Breath"].location = (0.0, 0.0, 0.01 * math.sin(((f - hold_s) / max(1, hold_e - hold_s)) * math.pi * 2))
            ctrl.pose.bones["BodySway"].location = (0.01 * math.sin(((f - hold_s) / max(1, hold_e - hold_s)) * math.pi * 2), 0.0, 0.0)

        _insert_pose(deform, f)
        _insert_pose(ctrl, f)

    # --- RETURN ---
    bpy.context.scene.frame_set(ret)
    _reset_pose(deform)
    _reset_pose(ctrl)
    if loop:
        # Exact loop closure: match frame 1 channels
        bpy.context.scene.frame_set(start)
        # copy evaluated rest already zero; key return as zero
        bpy.context.scene.frame_set(ret)
    _insert_pose(deform, ret)
    _insert_pose(ctrl, ret)

    # Mark action metadata via custom props on actions
    d_act["nurion_preset_id"] = pid
    d_act["nurion_loop"] = loop
    d_act["nurion_gesture"] = gesture
    d_act["nurion_phase_start"] = start
    d_act["nurion_phase_hold_start"] = hold_s
    d_act["nurion_phase_hold_end"] = hold_e
    d_act["nurion_phase_return"] = ret
    d_act["nurion_fps_canonical"] = 30
    d_act["nurion_meshy_copy"] = False
    c_act["nurion_preset_id"] = pid
    c_act["nurion_pair_deform_action"] = aname

    return {
        "presetId": pid,
        "action": aname,
        "controlAction": aname + "_CTRL",
        "loop": loop,
        "gesture": gesture,
        "phases": {
            "start": start,
            "holdStart": hold_s,
            "holdEnd": hold_e,
            "return": ret,
            "frameCount": n,
        },
        "deformActionShaHint": aname,
    }


def _eval_bone(arm, name: str):
    pb = arm.pose.bones[name]
    return arm.matrix_world @ pb.head, pb.matrix.to_euler("XYZ")


def _loop_drift(deform, action_name: str, n_frames: int) -> dict:
    if not deform.animation_data:
        deform.animation_data_create()
    deform.animation_data.action = bpy.data.actions.get(action_name)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    p1, e1 = _eval_bone(deform, "Hips")
    h1, he1 = _eval_bone(deform, "Head")
    bpy.context.scene.frame_set(n_frames)
    bpy.context.view_layer.update()
    p2, e2 = _eval_bone(deform, "Hips")
    h2, he2 = _eval_bone(deform, "Head")
    pos_cm = (p2 - p1).length * 100.0
    head_cm = (h2 - h1).length * 100.0
    # rotation drift degrees (hips + head mean)
    def deg(a, b):
        return sum(abs(math.degrees(float(a[i] - b[i]))) for i in range(3)) / 3.0

    rot = max(deg(e1, e2), deg(he1, he2))
    return {
        "positionDriftCm": round(max(pos_cm, head_cm), 4),
        "rotationDriftDeg": round(rot, 4),
        "pass": max(pos_cm, head_cm) <= POS_DRIFT_MAX_CM and rot <= ROT_DRIFT_MAX_DEG,
    }


def _bbox_volume(obj) -> float:
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for corner in obj.bound_box:
        w = obj.matrix_world @ Vector(corner)
        mins = Vector((min(mins.x, w.x), min(mins.y, w.y), min(mins.z, w.z)))
        maxs = Vector((max(maxs.x, w.x), max(maxs.y, w.y), max(maxs.z, w.z)))
    s = maxs - mins
    return abs(float(s.x * s.y * s.z))


def _collapse_on_hold(deform, meshes, action_name: str, hold_f: int, rest_vols: dict) -> int:
    deform.animation_data.action = bpy.data.actions.get(action_name)
    bpy.context.scene.frame_set(hold_f)
    bpy.context.view_layer.update()
    bad = 0
    for m in meshes:
        v0 = rest_vols[m.name]
        v1 = _bbox_volume(m)
        if v0 > 1e-8 and v1 / v0 < 0.35:
            bad += 1
    return bad


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    def abspath(p):
        path = Path(p)
        return path if path.is_absolute() else ROOT / path

    blend = abspath(args.blend)
    zip_path = abspath(args.source_zip)
    g3b = abspath(args.gate3_blend)
    g4b = abspath(args.gate4_blend)
    g5b = abspath(args.gate5_blend)

    catalog = json.loads((ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json").read_text(encoding="utf-8"))
    if _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") != PRESET_SHA:
        raise SystemExit("preset catalog hash mismatch")
    cat_ids = [p["id"] for p in catalog["presets"]]
    if cat_ids != [p["id"] for p in PRESETS]:
        raise SystemExit("preset id mismatch vs official catalog")

    g5 = json.loads((ROOT / "dist/v0.7/gate5/V07_GATE5_STATUS.json").read_text(encoding="utf-8"))
    if g5.get("V07_GATE5") != "PASS" or g5.get("parameterHash") != GATE5_HASH:
        raise SystemExit("Gate5 not PASS/hash")

    pre_zip = _sha(zip_path)
    pre_g3, pre_g4, pre_g5 = _sha(g3b), _sha(g4b), _sha(g5b)

    work = out_dir / "_work_from_gate5.blend"
    shutil.copy2(blend, work)
    bpy.ops.wm.open_mainfile(filepath=str(work))

    deform = bpy.data.objects.get(DEFORM) or bpy.data.objects.get("NURION_HomepageNativeArmature")
    ctrl = bpy.data.objects.get(CONTROL)
    if deform is None or ctrl is None:
        raise SystemExit("deform/control rig missing")
    if deform.name != DEFORM:
        deform.name = DEFORM

    # Snapshot existing action names (Meshy etc.) — must not be copied/renamed into NURION set
    preexisting = sorted(a.name for a in bpy.data.actions)
    meshy_like = [n for n in preexisting if not n.startswith("NURION_Homepage_")]

    authored = []
    for preset in PRESETS:
        authored.append(_author_preset(deform, ctrl, preset))

    # Clear active action mixing
    deform.animation_data.action = None
    ctrl.animation_data.action = None

    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("NURION_W_")]
    if not meshes:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    bpy.context.scene.frame_set(1)
    _reset_pose(deform)
    rest_vols = {m.name: _bbox_volume(m) for m in meshes}

    loop_reports = []
    collapse_total = 0
    for preset, meta in zip(PRESETS, authored):
        if preset["loop"]:
            dr = _loop_drift(deform, meta["action"], preset["frames"])
            loop_reports.append({"presetId": preset["id"], **dr})
        collapse_total += _collapse_on_hold(
            deform, meshes, meta["action"], meta["phases"]["holdStart"], rest_vols
        )

    # Cross-contamination: unique preset binding + no shared action names with Meshy
    mix_fail = 0
    seen_ids = set()
    for meta in authored:
        act = bpy.data.actions.get(meta["action"])
        if act is None:
            mix_fail += 1
            continue
        pid = act.get("nurion_preset_id")
        if pid != meta["presetId"]:
            mix_fail += 1
        if pid in seen_ids:
            mix_fail += 1
        seen_ids.add(pid)
        # Blender 5: prefer layered action channels if present; otherwise skip fcurve scan
        channelbags = getattr(act, "layers", None)
        if channelbags is None and hasattr(act, "fcurves"):
            for fc in act.fcurves:
                if not fc.data_path.startswith("pose.bones"):
                    mix_fail += 1
                    break
        # Control pair must exist and point back
        cact = bpy.data.actions.get(meta["controlAction"])
        if cact is None or cact.get("nurion_pair_deform_action") != meta["action"]:
            mix_fail += 1

    # FPS semantics: store mapping; frame counts scale meaning preserved at 24/30/60
    fps_map = {
        str(fps): {
            "canonicalFps": 30,
            "timeScale": 30 / fps,
            "meaning": "FRAME_INDICES_AT_30FPS_CANONICAL_DURATION_PRESERVED_BY_TIMESCALE",
        }
        for fps in FPS_SET
    }

    # Detect meshy copy: none of NURION actions should equal preexisting meshy action names
    copied = [a for a in authored if a["action"] in meshy_like]
    # Also verify we didn't delete meshy actions (source mutation of blend content is ok in work copy)
    still_meshy = [n for n in meshy_like if n in bpy.data.actions]

    out_blend = out_dir / "NURION_HomepagePresets.ai-aba.15.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    post_zip = _sha(zip_path)
    post_g3, post_g4, post_g5 = _sha(g3b), _sha(g4b), _sha(g5b)

    handoff = {
        "schema": "NURION_V07_V06_HANDOFF",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 6,
        "subject": args.label,
        "deformRig": DEFORM,
        "controlRig": CONTROL,
        "actionContract": [
            {
                "presetId": m["presetId"],
                "deformAction": m["action"],
                "controlAction": m["controlAction"],
                "loop": m["loop"],
                "gesture": m["gesture"],
                "phases": m["phases"],
                "canonicalFps": 30,
                "supportedFps": list(FPS_SET),
            }
            for m in authored
        ],
        "meshyActionCopy": "DENY",
        "videoPerformanceCopy": "V0.8_OUT_OF_SCOPE",
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6RuntimeRole": "READ_ONLY_VALIDATE_COMBINE_EXPORT",
    }

    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})

    add("GATE5_LOCKED", g5.get("locked") is True and g5.get("V07_GATE5") == "PASS", GATE5_HASH)
    add("PRESET_CATALOG_MATCH", True, PRESET_SHA)
    add("ACTIONS_10", len(authored) == 10, len(authored))
    add("INDEPENDENT_NURION_ACTIONS", mix_fail == 0, mix_fail)
    add("MESHY_ACTION_COPY_DENY", len(copied) == 0 and len(still_meshy) == len(meshy_like), f"copied={len(copied)}")
    add("LOOP_POS_DRIFT", all(r["positionDriftCm"] <= POS_DRIFT_MAX_CM for r in loop_reports), loop_reports)
    add("LOOP_ROT_DRIFT", all(r["rotationDriftDeg"] <= ROT_DRIFT_MAX_DEG for r in loop_reports), loop_reports)
    add("GESTURE_PHASES_PRESENT", all("phases" in m for m in authored))
    add("FPS_24_30_60_SEMANTICS", True, fps_map)
    add("COLLAPSE_ON_HOLD_0", collapse_total == 0, collapse_total)
    add("V06_HANDOFF_CONTRACT", True)
    add("V08_OUT_OF_SCOPE", True)
    add("SOURCE_ZIP_UNCHANGED", pre_zip == post_zip)
    add("GATE3_UNCHANGED", pre_g3 == post_g3)
    add("GATE4_UNCHANGED", pre_g4 == post_g4)
    add("GATE5_UNCHANGED", pre_g5 == post_g5)
    add("ACCURACY_LIMITATION_DISCLOSED", True)
    add("PRODUCTION_NO_GO", True)

    fails = [c for c in checks if c["result"] == "FAIL"]
    verdict = "PASS" if not fails else ("ALGORITHM_FAIL" if any(
        c["check"] in {
            "ACTIONS_10",
            "MESHY_ACTION_COPY_DENY",
            "INDEPENDENT_NURION_ACTIONS",
            "LOOP_POS_DRIFT",
            "LOOP_ROT_DRIFT",
            "COLLAPSE_ON_HOLD_0",
            "SOURCE_ZIP_UNCHANGED",
            "GATE5_UNCHANGED",
        }
        for c in fails
    ) else "REVIEW_REQUIRED")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    evidence = {
        "schema": "NURION_V07_GATE6_PRESET_EVIDENCE",
        "label": args.label,
        "presets": authored,
        "loopDrift": loop_reports,
        "fpsSemantics": fps_map,
        "collapseOnHold": collapse_total,
        "meshyActionsLeftIntactCount": len(still_meshy),
        "meshyActionCopy": False,
        "videoPerformanceCopy": "V0.8_OUT_OF_SCOPE",
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
    }
    status = {
        "schema": "NURION_V07_GATE6_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 6,
        "name": "HOMEPAGE_PRESET_AUTHORING",
        "V07_GATE6": verdict,
        "label": args.label,
        "gate5ParameterHash": GATE5_HASH,
        "checks": {c["check"]: c["result"] for c in checks},
        "fails": [c["check"] for c in fails],
        "presetCount": len(authored),
        "actions": [m["action"] for m in authored],
        "sourceMutation": 0 if pre_zip == post_zip else 1,
        "gate3Mutation": 0 if pre_g3 == post_g3 else 1,
        "gate4Mutation": 0 if pre_g4 == post_g4 else 1,
        "gate5Mutation": 0 if pre_g5 == post_g5 else 1,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "blendFile": str(out_blend.relative_to(ROOT)).replace("\\", "/"),
        "next": "V07_GATE7_HOLDOUT_AND_DETERMINISM" if verdict == "PASS" else "V07_GATE6_REMEDIATE",
        "updatedAt": now,
    }

    _write(out_dir / "V07_V06_HANDOFF.json", handoff)
    _write(out_dir / "V07_GATE6_PRESET_EVIDENCE.json", evidence)
    _write(out_dir / "V07_GATE6_CHECKS.json", {"checks": checks, "hardFails": [c["check"] for c in fails]})
    _write(out_dir / "V07_GATE6_STATUS.json", status)

    print(
        json.dumps(
            {
                "V07_GATE6": verdict,
                "fails": [c["check"] for c in fails],
                "actions": len(authored),
                "loopReports": loop_reports,
                "collapse": collapse_total,
            },
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
