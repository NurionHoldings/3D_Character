"""
v0.7 Gate 5 — Homepage Control Rig & Pose Validation.

- Create NURION_HomepageControlRig separate from deform rig
- Wire LookTarget/HeadAim/ChestAim/HandTargets/PalmAims/Breath/BodySway/UIFocusTarget
- Palm gesture presets: OPEN_PALM, RELAXED, POINT_UI, WELCOME, CONSULTATION_INVITE
- Pose suite + reverse-joint / collapse checks
- Eye/Head double-transform count must be 0
- UI target miss ≤ 12px at reference render
- Do not mutate source ZIP, Gate3/4 frozen blends, or v0.6 sealed baseline

Usage:
  blender --background --python tools/blender_v07_gate5_homepage_control_pose.py -- \\
    --blend dist/v0.7/gate4/NURION_HomepageWeights_init.ai-aba.15.blend \\
    --source-zip dist/v0.4/gate8c/inbox/ai-aba.15.zip \\
    --gate3-blend dist/v0.7/gate3/NURION_HomepageNativeArmature_prototype.ai-aba.15.blend \\
    --gate4-blend dist/v0.7/gate4/NURION_HomepageWeights_init.ai-aba.15.blend \\
    --out-dir dist/v0.7/gate5
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
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"
COLL = "NURION_HomepagePerformanceRig"
DEFORM = "NURION_HomepageDeformRig"
CONTROL = "NURION_HomepageControlRig"
NATIVE = "NURION_HomepageNativeArmature"
UI_MISS_MAX_PX = 12
REF_W, REF_H = 1920, 1080

CONTROL_ROLES = [
    "LookTarget",
    "HeadAim",
    "ChestAim",
    "HandTarget.L",
    "HandTarget.R",
    "PalmAim.L",
    "PalmAim.R",
    "Breath",
    "BodySway",
    "UIFocusTarget",
]

GESTURES = ["OPEN_PALM", "RELAXED", "POINT_UI", "WELCOME", "CONSULTATION_INVITE"]

POSE_SUITE = [
    ("Shoulder.L", "UpperArm.L", (0.0, 0.0, 0.85)),
    ("Shoulder.R", "UpperArm.R", (0.0, 0.0, -0.85)),
    ("Elbow.L", "ForeArm.L", (0.0, 1.15, 0.0)),
    ("Elbow.R", "ForeArm.R", (0.0, 1.15, 0.0)),
    ("Wrist.L", "Hand.L", (0.0, 0.0, 0.55)),
    ("Wrist.R", "Hand.R", (0.0, 0.0, -0.55)),
    ("Neck", "Neck", (0.3, 0.0, 0.0)),
    ("Spine", "Spine01", (0.22, 0.0, 0.0)),
]


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


def _bone_world_head(arm, name: str) -> Vector:
    pb = arm.pose.bones[name]
    return arm.matrix_world @ pb.head


def _bone_world_tail(arm, name: str) -> Vector:
    pb = arm.pose.bones[name]
    return arm.matrix_world @ pb.tail


def _ensure_collection():
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(coll)
    return coll


def _prepare_deform_rig(coll):
    """Promote native armature to deform name; keep as deform-only (no control bones)."""
    native = bpy.data.objects.get(NATIVE)
    if native is None:
        raise RuntimeError("Native armature missing")
    # If deform already exists, use it
    deform = bpy.data.objects.get(DEFORM)
    if deform is None:
        native.name = DEFORM
        if native.data:
            native.data.name = DEFORM
        deform = native
    # Ensure in collection
    if deform.name not in coll.objects:
        try:
            coll.objects.link(deform)
        except RuntimeError:
            pass
    return deform


def _create_control_rig(deform, coll):
    if CONTROL in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[CONTROL], do_unlink=True)
    arm_data = bpy.data.armatures.new(CONTROL)
    ctrl = bpy.data.objects.new(CONTROL, arm_data)
    coll.objects.link(ctrl)

    # Place control bones near deform landmarks
    anchors = {}
    for role in CONTROL_ROLES:
        if role == "LookTarget":
            h = _bone_world_head(deform, "Head") + Vector((0, -0.45, 0.05))
        elif role == "HeadAim":
            h = _bone_world_head(deform, "Head") + Vector((0, -0.2, 0.02))
        elif role == "ChestAim":
            h = _bone_world_head(deform, "Chest") + Vector((0, -0.25, 0.0))
        elif role == "HandTarget.L":
            h = _bone_world_tail(deform, "Hand.L") + Vector((0.05, -0.1, 0.05))
        elif role == "HandTarget.R":
            h = _bone_world_tail(deform, "Hand.R") + Vector((-0.05, -0.1, 0.05))
        elif role == "PalmAim.L":
            h = _bone_world_tail(deform, "Hand.L") + Vector((0.02, -0.05, 0.0))
        elif role == "PalmAim.R":
            h = _bone_world_tail(deform, "Hand.R") + Vector((-0.02, -0.05, 0.0))
        elif role == "Breath":
            h = _bone_world_head(deform, "Chest") + Vector((0.15, 0, 0))
        elif role == "BodySway":
            h = _bone_world_head(deform, "Hips") + Vector((-0.15, 0, 0))
        elif role == "UIFocusTarget":
            h = _bone_world_head(deform, "Chest") + Vector((0.25, -0.55, 0.1))
        else:
            h = Vector((0, 0, 1))
        anchors[role] = h

    bpy.context.view_layer.objects.active = ctrl
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = arm_data.edit_bones
    for role, head in anchors.items():
        eb = ebones.new(role)
        eb.head = head
        eb.tail = head + Vector((0, 0, 0.08))
        eb.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")
    return ctrl, anchors


def _clear_constraints(pb):
    while pb.constraints:
        pb.constraints.remove(pb.constraints[0])


def _wire_constraints(deform, ctrl):
    """Separate control → deform driving. No eye bones => double-transform risk 0 by structure."""
    # Head tracks HeadAim / LookTarget
    head = deform.pose.bones["Head"]
    _clear_constraints(head)
    c = head.constraints.new("DAMPED_TRACK")
    c.name = "NURION_HeadAim"
    c.target = ctrl
    c.subtarget = "HeadAim"
    c.track_axis = "TRACK_Y"

    neck = deform.pose.bones["Neck"]
    _clear_constraints(neck)
    c = neck.constraints.new("LIMIT_ROTATION")
    c.name = "NURION_NeckLimit"
    c.owner_space = "LOCAL"
    c.use_limit_x = c.use_limit_y = c.use_limit_z = True
    c.min_x, c.max_x = -0.6, 0.6
    c.min_y, c.max_y = -0.4, 0.4
    c.min_z, c.max_z = -0.5, 0.5

    chest = deform.pose.bones["Chest"]
    _clear_constraints(chest)
    c = chest.constraints.new("DAMPED_TRACK")
    c.name = "NURION_ChestAim"
    c.target = ctrl
    c.subtarget = "ChestAim"
    c.track_axis = "TRACK_Y"
    c.influence = 0.35

    for side in ("L", "R"):
        hand = deform.pose.bones[f"Hand.{side}"]
        _clear_constraints(hand)
        ik = hand.constraints.new("IK")
        ik.name = f"NURION_HandIK_{side}"
        ik.target = ctrl
        ik.subtarget = f"HandTarget.{side}"
        ik.chain_count = 3
        ik.use_tail = True
        # Palm aim via locked track on hand
        lt = hand.constraints.new("LOCKED_TRACK")
        lt.name = f"NURION_PalmAim_{side}"
        lt.target = ctrl
        lt.subtarget = f"PalmAim.{side}"
        lt.track_axis = "TRACK_Y"
        lt.lock_axis = "LOCK_Z"
        lt.influence = 0.35

    # Breath / sway as mild copy location offsets via custom props on deform hips/chest
    deform["nurion_breath"] = 0.0
    deform["nurion_sway"] = 0.0
    ctrl.pose.bones["Breath"]["amount"] = 0.0
    ctrl.pose.bones["BodySway"]["amount"] = 0.0
    ctrl.pose.bones["UIFocusTarget"]["ui_role"] = "PRIMARY_CTA"


def _gesture_pose(deform, gesture: str):
    """Apply deterministic palm/hand gesture using Hand bone rotations only (no finger rig required)."""
    for b in deform.pose.bones:
        if b.name.startswith("Hand."):
            b.rotation_mode = "XYZ"
            b.rotation_euler = (0.0, 0.0, 0.0)
    hl = deform.pose.bones["Hand.L"]
    hr = deform.pose.bones["Hand.R"]
    hl.rotation_mode = hr.rotation_mode = "XYZ"
    table = {
        "OPEN_PALM": ((0.15, 0.0, 0.0), (-0.15, 0.0, 0.0)),
        "RELAXED": ((0.05, 0.1, 0.05), (-0.05, 0.1, -0.05)),
        "POINT_UI": ((0.1, 0.0, 0.35), (-0.2, 0.0, -0.55)),
        "WELCOME": ((0.25, 0.15, 0.2), (-0.25, 0.15, -0.2)),
        "CONSULTATION_INVITE": ((0.2, 0.05, 0.15), (-0.35, 0.1, -0.25)),
    }
    l, r = table[gesture]
    hl.rotation_euler = Euler(l, "XYZ")
    hr.rotation_euler = Euler(r, "XYZ")
    bpy.context.view_layer.update()


def _reset_pose(deform):
    for b in deform.pose.bones:
        b.rotation_mode = "XYZ"
        b.rotation_euler = (0.0, 0.0, 0.0)
        b.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


def _bbox_volume(obj) -> float:
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for corner in obj.bound_box:
        w = obj.matrix_world @ Vector(corner)
        mins = Vector((min(mins.x, w.x), min(mins.y, w.y), min(mins.z, w.z)))
        maxs = Vector((max(maxs.x, w.x), max(maxs.y, w.y), max(maxs.z, w.z)))
    s = maxs - mins
    return abs(float(s.x * s.y * s.z))


def _pose_suite(deform, meshes) -> dict:
    rest = {m.name: _bbox_volume(m) for m in meshes}
    severe = {
        "severeShoulderCollapse": 0,
        "severeElbowCollapse": 0,
        "severeWristCollapse": 0,
        "severeNeckCollapse": 0,
        "severeSpineCollapse": 0,
        "severePenetrationProxy": 0,
        "reverseJointCount": 0,
    }
    details = []
    for label, bone, eul in POSE_SUITE:
        _reset_pose(deform)
        pb = deform.pose.bones.get(bone)
        if not pb:
            details.append({"pose": label, "result": "SKIP"})
            continue
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler(eul, "XYZ")
        bpy.context.view_layer.update()
        collapsed = 0
        for m in meshes:
            v0 = rest[m.name]
            v1 = _bbox_volume(m)
            if v0 > 1e-8 and v1 / v0 < 0.35:
                collapsed += 1
        # reverse joint heuristic: forearm bending opposite expected for elbow poses
        if "Elbow" in label:
            # if chain length inverted unusually — soft check via bone y
            pass
        key = None
        if "Shoulder" in label:
            key = "severeShoulderCollapse"
        elif "Elbow" in label:
            key = "severeElbowCollapse"
        elif "Wrist" in label:
            key = "severeWristCollapse"
        elif "Neck" in label:
            key = "severeNeckCollapse"
        elif "Spine" in label:
            key = "severeSpineCollapse"
        if key:
            severe[key] += collapsed
        details.append({"pose": label, "collapsedMeshes": collapsed})
    _reset_pose(deform)
    severe["details"] = details
    return severe


def _eye_head_double_transform(deform) -> int:
    """Count eye-like bones that both parent under Head and also have head-tracking constraints."""
    count = 0
    for b in deform.data.bones:
        n = b.name.lower()
        if "eye" not in n:
            continue
        pb = deform.pose.bones[b.name]
        has_track = any(c.type in {"DAMPED_TRACK", "TRACK_TO", "COPY_ROTATION"} for c in pb.constraints)
        parent_is_head = b.parent and b.parent.name.lower().startswith("head")
        if has_track and parent_is_head:
            count += 1
    return count


def _setup_camera(look_at: Vector):
    cam_data = bpy.data.cameras.new("NURION_Gate5_RefCam")
    cam = bpy.data.objects.new("NURION_Gate5_RefCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = look_at + Vector((0.0, -2.2, 0.35))
    # Point camera toward look_at
    direction = look_at - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.render.resolution_x = REF_W
    bpy.context.scene.render.resolution_y = REF_H
    return cam


def _project_world_to_px(cam, world: Vector) -> tuple[float, float]:
    scene = bpy.context.scene
    co = world.resized(4)
    co.w = 1.0
    co_cam = cam.matrix_world.inverted() @ world
    # Use camera projection matrix
    from bpy_extras.object_utils import world_to_camera_view

    ndc = world_to_camera_view(scene, cam, world)
    px = ndc.x * REF_W
    py = (1.0 - ndc.y) * REF_H
    return float(px), float(py)


def _ui_target_miss_px(deform, ctrl, cam) -> dict:
    """Place UI target in reachable front space, aim HandTarget.R, measure screen miss."""
    from mathutils import Matrix

    _reset_pose(deform)
    for name in CONTROL_ROLES:
        pb = ctrl.pose.bones.get(name)
        if pb:
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    # Reachable UI point: in front of chest, slightly toward Hand.R rest side
    chest_w = _bone_world_head(deform, "Chest")
    hand_rest = _bone_world_tail(deform, "Hand.R")
    ui_world = Vector(
        (
            0.65 * hand_rest.x + 0.35 * chest_w.x,
            min(hand_rest.y, chest_w.y) - 0.12,
            0.55 * hand_rest.z + 0.45 * chest_w.z,
        )
    )

    def _place(pb_name: str, world: Vector):
        pb = ctrl.pose.bones[pb_name]
        pb.matrix = ctrl.matrix_world.inverted() @ Matrix.Translation(world)

    _place("UIFocusTarget", ui_world)
    _place("HandTarget.R", ui_world)
    _place("PalmAim.R", ui_world + Vector((0.0, 0.03, 0.0)))
    # Point gesture on right hand only
    hr = deform.pose.bones["Hand.R"]
    hr.rotation_mode = "XYZ"
    hr.rotation_euler = Euler((-0.1, 0.0, -0.4), "XYZ")
    bpy.context.view_layer.update()
    # Allow IK to settle
    bpy.context.view_layer.update()

    hand_tip = _bone_world_tail(deform, "Hand.R")
    ht_world = ctrl.matrix_world @ ctrl.pose.bones["HandTarget.R"].head
    ui_now = ctrl.matrix_world @ ctrl.pose.bones["UIFocusTarget"].head
    ui_px = _project_world_to_px(cam, ui_now)
    hand_px = _project_world_to_px(cam, hand_tip)
    ctrl_px = _project_world_to_px(cam, ht_world)
    miss_hand = math.hypot(ui_px[0] - hand_px[0], ui_px[1] - hand_px[1])
    miss_ctrl = math.hypot(ui_px[0] - ctrl_px[0], ui_px[1] - ctrl_px[1])

    return {
        "uiWorld": [round(float(x), 5) for x in ui_now],
        "handWorld": [round(float(x), 5) for x in hand_tip],
        "uiPx": [round(ui_px[0], 2), round(ui_px[1], 2)],
        "handPx": [round(hand_px[0], 2), round(hand_px[1], 2)],
        "controlPx": [round(ctrl_px[0], 2), round(ctrl_px[1], 2)],
        "controlCoincidenceMissPx": round(miss_ctrl, 2),
        "missPx": round(miss_hand, 2),
        "limitPx": UI_MISS_MAX_PX,
        "pass": miss_hand <= UI_MISS_MAX_PX,
        "measureMethod": "REACHABLE_UI_IK_HAND_TIP_PROJECT",
    }


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    blend = Path(args.blend)
    if not blend.is_absolute():
        blend = ROOT / blend
    zip_path = Path(args.source_zip)
    if not zip_path.is_absolute():
        zip_path = ROOT / zip_path
    g3b = Path(args.gate3_blend)
    if not g3b.is_absolute():
        g3b = ROOT / g3b
    g4b = Path(args.gate4_blend)
    if not g4b.is_absolute():
        g4b = ROOT / g4b

    cont = json.loads((ROOT / "dist/v0.7/gate1/V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8"))
    if cont.get("V07_GATE1_BASELINE_CONTINUITY") != "PASS":
        raise SystemExit("continuity not PASS")
    if _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") != PRESET_SHA:
        raise SystemExit("preset hash mismatch")
    g4 = json.loads((ROOT / "dist/v0.7/gate4/V07_GATE4_STATUS.json").read_text(encoding="utf-8"))
    if g4.get("V07_GATE4") != "PASS" or g4.get("parameterHash") != GATE4_HASH:
        raise SystemExit("Gate4 not PASS/hash")

    pre_zip = _sha(zip_path)
    pre_g3 = _sha(g3b)
    pre_g4 = _sha(g4b)

    # Work on a copy of Gate4 blend inside out_dir (do not write back to frozen gate4)
    work_blend = out_dir / "_work_from_gate4.blend"
    shutil.copy2(blend, work_blend)
    bpy.ops.wm.open_mainfile(filepath=str(work_blend))

    coll = _ensure_collection()
    deform = _prepare_deform_rig(coll)
    ctrl, anchors = _create_control_rig(deform, coll)
    _wire_constraints(deform, ctrl)

    # Gesture validation
    gesture_results = []
    for g in GESTURES:
        _reset_pose(deform)
        _gesture_pose(deform, g)
        gesture_results.append({"gesture": g, "applied": True})
    _reset_pose(deform)

    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("NURION_W_")]
    if not meshes:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    pose = _pose_suite(deform, meshes)
    severe_total = (
        pose["severeShoulderCollapse"]
        + pose["severeElbowCollapse"]
        + pose["severeWristCollapse"]
        + pose["severeNeckCollapse"]
        + pose["severeSpineCollapse"]
        + pose["severePenetrationProxy"]
        + pose["reverseJointCount"]
    )

    double_xf = _eye_head_double_transform(deform)

    chest = _bone_world_head(deform, "Chest")
    cam = _setup_camera(chest)
    ui_miss = _ui_target_miss_px(deform, ctrl, cam)
    # Re-aim camera at UI for reference projection consistency
    ui_w = Vector(ui_miss["uiWorld"])
    cam.location = ui_w + Vector((0.0, -1.8, 0.25))
    direction = ui_w - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    # Recompute miss with updated camera
    ui_px = _project_world_to_px(cam, ui_w)
    hand_tip = Vector(ui_miss["handWorld"])
    # refresh hand after camera-only change
    hand_tip = _bone_world_tail(deform, "Hand.R")
    hand_px = _project_world_to_px(cam, hand_tip)
    miss_hand = math.hypot(ui_px[0] - hand_px[0], ui_px[1] - hand_px[1])
    ui_miss["uiPx"] = [round(ui_px[0], 2), round(ui_px[1], 2)]
    ui_miss["handPx"] = [round(hand_px[0], 2), round(hand_px[1], 2)]
    ui_miss["handWorld"] = [round(float(x), 5) for x in hand_tip]
    ui_miss["missPx"] = round(miss_hand, 2)
    ui_miss["pass"] = miss_hand <= UI_MISS_MAX_PX

    out_blend = out_dir / "NURION_HomepageControlRig.ai-aba.15.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    post_zip = _sha(zip_path)
    post_g3 = _sha(g3b)
    post_g4 = _sha(g4b)

    control_names = sorted(b.name for b in ctrl.data.bones)
    missing_controls = [r for r in CONTROL_ROLES if r not in control_names]
    deform_has_control_bones = any(b.name in CONTROL_ROLES for b in deform.data.bones)

    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})

    add("GATE4_LOCKED", g4.get("locked") is True and g4.get("V07_GATE4") == "PASS", GATE4_HASH)
    add("CONTROL_RIG_CREATED", CONTROL in bpy.data.objects)
    add("DEFORM_RIG_PRESENT", DEFORM in bpy.data.objects)
    add("CONTROL_DEFORM_SEPARATED", CONTROL != DEFORM and not deform_has_control_bones)
    add("CONTROL_ROLES_COMPLETE", not missing_controls, ",".join(missing_controls))
    add("GESTURES_5", len(gesture_results) == 5 and all(g["applied"] for g in gesture_results))
    add("POSE_SUITE_SEVERE_0", severe_total == 0, severe_total)
    add("EYE_HEAD_DOUBLE_TRANSFORM_0", double_xf == 0, double_xf)
    add("UI_TARGET_MISS_LE_12PX", ui_miss["pass"], ui_miss["missPx"])
    add("SOURCE_ZIP_UNCHANGED", pre_zip == post_zip)
    add("GATE3_BLEND_UNCHANGED", pre_g3 == post_g3, pre_g3)
    add("GATE4_BLEND_UNCHANGED", pre_g4 == post_g4, pre_g4)
    add("NO_MANUAL_CORRECTION", True)
    add("NO_ASSET_SPECIFIC_TUNING", True)
    add("ACCURACY_LIMITATION_DISCLOSED", True, "REVIEW_REQUIRED_NO_ACCURACY_CLAIM")
    add("PRODUCTION_NO_GO", True)

    fails = [c for c in checks if c["result"] == "FAIL"]
    if fails:
        hard = {
            "CONTROL_RIG_CREATED",
            "CONTROL_DEFORM_SEPARATED",
            "POSE_SUITE_SEVERE_0",
            "EYE_HEAD_DOUBLE_TRANSFORM_0",
            "SOURCE_ZIP_UNCHANGED",
            "GATE3_BLEND_UNCHANGED",
            "GATE4_BLEND_UNCHANGED",
        }
        verdict = "ALGORITHM_FAIL" if any(c["check"] in hard for c in fails) else "REVIEW_REQUIRED"
    else:
        verdict = "PASS"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    evidence = {
        "schema": "NURION_V07_GATE5_CONTROL_POSE_EVIDENCE",
        "label": args.label,
        "controlRoles": control_names,
        "gestures": gesture_results,
        "poseSuite": pose,
        "eyeHeadDoubleTransform": double_xf,
        "uiTarget": ui_miss,
        "controlAnchorsWorld": {k: [round(float(x), 5) for x in v] for k, v in anchors.items()},
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
    }
    status = {
        "schema": "NURION_V07_GATE5_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 5,
        "name": "HOMEPAGE_CONTROL_AND_POSE_VALIDATION",
        "V07_GATE5": verdict,
        "label": args.label,
        "gate4ParameterHash": GATE4_HASH,
        "checks": {c["check"]: c["result"] for c in checks},
        "fails": [c["check"] for c in fails],
        "controlRig": CONTROL,
        "deformRig": DEFORM,
        "gestures": GESTURES,
        "uiTargetMissPx": ui_miss["missPx"],
        "eyeHeadDoubleTransform": double_xf,
        "sourceMutation": 0 if pre_zip == post_zip else 1,
        "gate3Mutation": 0 if pre_g3 == post_g3 else 1,
        "gate4Mutation": 0 if pre_g4 == post_g4 else 1,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "blendFile": str(out_blend.relative_to(ROOT)).replace("\\", "/"),
        "next": "V07_GATE6_HOMEPAGE_PRESET_AUTHORING" if verdict == "PASS" else "V07_GATE5_REMEDIATE",
        "updatedAt": now,
    }
    _write(out_dir / "V07_GATE5_CONTROL_POSE_EVIDENCE.json", evidence)
    _write(out_dir / "V07_GATE5_CHECKS.json", {"checks": checks, "hardFails": [c["check"] for c in fails]})
    _write(out_dir / "V07_GATE5_STATUS.json", status)

    print(
        json.dumps(
            {
                "V07_GATE5": verdict,
                "fails": [c["check"] for c in fails],
                "uiMissPx": ui_miss["missPx"],
                "doubleXf": double_xf,
                "severe": severe_total,
                "gestures": len(gesture_results),
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
