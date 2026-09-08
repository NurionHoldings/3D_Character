"""
v0.7 Gate 7 — Holdout pipeline + fingerprint (single clean-scene run).

Holdout subject must NOT be any v0.7 Gate2–6 workflow subject.
Meshy bones/weights are NEVER ground truth.
Manual GT absent => accuracy claim remains REVIEW_REQUIRED_NO_ACCURACY_CLAIM.

Usage:
  blender --background --python tools/blender_v07_gate7_holdout_run.py -- \\
    --zip <holdout.zip> --out-dir dist/v0.7/gate7/run1 --run-id 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
COLL = "NURION_HomepagePerformanceRig"
DEFORM = "NURION_HomepageDeformRig"
CONTROL = "NURION_HomepageControlRig"

BONE_CHAIN = [
    ("Root", None),
    ("Hips", "Root"),
    ("Spine", "Hips"),
    ("Spine01", "Spine"),
    ("Spine02", "Spine01"),
    ("Chest", "Spine02"),
    ("Neck", "Chest"),
    ("Head", "Neck"),
    ("Clavicle.L", "Chest"),
    ("UpperArm.L", "Clavicle.L"),
    ("ForeArm.L", "UpperArm.L"),
    ("Hand.L", "ForeArm.L"),
    ("Clavicle.R", "Chest"),
    ("UpperArm.R", "Clavicle.R"),
    ("ForeArm.R", "UpperArm.R"),
    ("Hand.R", "ForeArm.R"),
    ("UpperLeg.L", "Hips"),
    ("LowerLeg.L", "UpperLeg.L"),
    ("Foot.L", "LowerLeg.L"),
    ("Toe.L", "Foot.L"),
    ("UpperLeg.R", "Hips"),
    ("LowerLeg.R", "UpperLeg.R"),
    ("Foot.R", "LowerLeg.R"),
    ("Toe.R", "Foot.R"),
]

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

WEIGHT_TOL = 0.001


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--label", default="Jjajang_Nara_Chef")
    p.add_argument("--manual-gt-json", default="")
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


def _stable_hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _find_fbx(extract: Path) -> Path:
    cands = sorted(extract.rglob("*.fbx"))
    if not cands:
        raise FileNotFoundError("no fbx")
    scored = []
    for p in cands:
        n = p.name.lower()
        score = 0
        if "withskin" in n or "texture" in n:
            score += 8
        if "idle" in n:
            score += 3
        scored.append((-score, len(str(p)), p))
    scored.sort()
    return scored[0][2]


def _mesh_bounds(meshes):
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for obj in meshes:
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            mins = Vector((min(mins.x, w.x), min(mins.y, w.y), min(mins.z, w.z)))
            maxs = Vector((max(maxs.x, w.x), max(maxs.y, w.y), max(maxs.z, w.z)))
    return mins, maxs


def _estimate_joints(mins, maxs):
    c = (mins + maxs) * 0.5
    size = maxs - mins
    h, w, d = size.z, size.x, size.y
    z0 = mins.z
    return {
        "Root": Vector((c.x, c.y, z0)),
        "Hips": Vector((c.x, c.y, z0 + h * 0.52)),
        "Spine": Vector((c.x, c.y, z0 + h * 0.58)),
        "Spine01": Vector((c.x, c.y, z0 + h * 0.64)),
        "Spine02": Vector((c.x, c.y, z0 + h * 0.70)),
        "Chest": Vector((c.x, c.y, z0 + h * 0.76)),
        "Neck": Vector((c.x, c.y, z0 + h * 0.84)),
        "Head": Vector((c.x, c.y, z0 + h * 0.92)),
        "Clavicle.L": Vector((c.x + w * 0.08, c.y, z0 + h * 0.78)),
        "UpperArm.L": Vector((c.x + w * 0.22, c.y, z0 + h * 0.74)),
        "ForeArm.L": Vector((c.x + w * 0.30, c.y, z0 + h * 0.58)),
        "Hand.L": Vector((c.x + w * 0.34, c.y, z0 + h * 0.46)),
        "Clavicle.R": Vector((c.x - w * 0.08, c.y, z0 + h * 0.78)),
        "UpperArm.R": Vector((c.x - w * 0.22, c.y, z0 + h * 0.74)),
        "ForeArm.R": Vector((c.x - w * 0.30, c.y, z0 + h * 0.58)),
        "Hand.R": Vector((c.x - w * 0.34, c.y, z0 + h * 0.46)),
        "UpperLeg.L": Vector((c.x + w * 0.08, c.y, z0 + h * 0.50)),
        "LowerLeg.L": Vector((c.x + w * 0.08, c.y, z0 + h * 0.26)),
        "Foot.L": Vector((c.x + w * 0.08, c.y + d * 0.05, z0 + h * 0.04)),
        "Toe.L": Vector((c.x + w * 0.08, c.y + d * 0.12, z0 + h * 0.02)),
        "UpperLeg.R": Vector((c.x - w * 0.08, c.y, z0 + h * 0.50)),
        "LowerLeg.R": Vector((c.x - w * 0.08, c.y, z0 + h * 0.26)),
        "Foot.R": Vector((c.x - w * 0.08, c.y + d * 0.05, z0 + h * 0.04)),
        "Toe.R": Vector((c.x - w * 0.08, c.y + d * 0.12, z0 + h * 0.02)),
    }


def _tail_for(name, head, joints):
    children = [bn for bn, parent in BONE_CHAIN if parent == name]
    if len(children) == 1:
        return joints[children[0]].copy()
    if name == "Head":
        return head + Vector((0, 0, 0.08))
    if name == "Hand.L":
        return head + Vector((0.04, 0, 0))
    if name == "Hand.R":
        return head + Vector((-0.04, 0, 0))
    if name.startswith("Toe"):
        return head + Vector((0, 0.03, 0))
    if name == "Root":
        return joints["Hips"].copy()
    return head + Vector((0, 0, 0.03))


def _create_deform(joints, coll):
    arm_data = bpy.data.armatures.new(DEFORM)
    arm = bpy.data.objects.new(DEFORM, arm_data)
    coll.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    created = {}
    for name, parent in BONE_CHAIN:
        eb = arm_data.edit_bones.new(name)
        head = joints[name]
        tail = _tail_for(name, head, joints)
        if (tail - head).length < 1e-4:
            tail = head + Vector((0, 0, 0.02))
        eb.head, eb.tail = head, tail
        created[name] = eb
    for name, parent in BONE_CHAIN:
        if parent:
            created[name].parent = created[parent]
            created[name].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def _dup_mesh(src, coll):
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = f"NURION_W_{src.name}"[:60]
    dup.parent = None
    dup.modifiers.clear()
    dup.vertex_groups.clear()
    coll.objects.link(dup)
    return dup


def _bind_normalize(arm, mesh):
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    deform = {b.name for b in arm.data.bones}
    idxs = {vg.index for vg in mesh.vertex_groups if vg.name in deform}
    for v in mesh.data.vertices:
        entries = [(g.group, float(g.weight)) for g in v.groups if g.group in idxs]
        total = sum(w for _, w in entries)
        if total <= 1e-12 or abs(total - 1.0) <= WEIGHT_TOL:
            continue
        for gi, w in entries:
            mesh.vertex_groups[gi].add([v.index], w / total, "REPLACE")


def _weight_ok(mesh, arm) -> dict:
    deform = {b.name for b in arm.data.bones}
    unweighted = sum_fail = nonfinite = negative = 0
    for v in mesh.data.vertices:
        total = 0.0
        has = False
        for g in v.groups:
            name = mesh.vertex_groups[g.group].name
            if name not in deform:
                continue
            has = True
            w = float(g.weight)
            if not math.isfinite(w):
                nonfinite += 1
            if w < 0:
                negative += 1
            total += w
        if not has or total <= 1e-8:
            unweighted += 1
        elif abs(total - 1.0) > WEIGHT_TOL:
            sum_fail += 1
    return {
        "unweighted": unweighted,
        "sumFail": sum_fail,
        "nonfinite": nonfinite,
        "negative": negative,
    }


def _create_control(deform, coll):
    arm_data = bpy.data.armatures.new(CONTROL)
    ctrl = bpy.data.objects.new(CONTROL, arm_data)
    coll.objects.link(ctrl)

    def wh(name):
        return deform.matrix_world @ deform.pose.bones[name].head

    def wt(name):
        return deform.matrix_world @ deform.pose.bones[name].tail

    anchors = {
        "LookTarget": wh("Head") + Vector((0, -0.45, 0.05)),
        "HeadAim": wh("Head") + Vector((0, -0.2, 0.02)),
        "ChestAim": wh("Chest") + Vector((0, -0.25, 0)),
        "HandTarget.L": wt("Hand.L") + Vector((0.05, -0.1, 0.05)),
        "HandTarget.R": wt("Hand.R") + Vector((-0.05, -0.1, 0.05)),
        "PalmAim.L": wt("Hand.L") + Vector((0.02, -0.05, 0)),
        "PalmAim.R": wt("Hand.R") + Vector((-0.02, -0.05, 0)),
        "Breath": wh("Chest") + Vector((0.15, 0, 0)),
        "BodySway": wh("Hips") + Vector((-0.15, 0, 0)),
        "UIFocusTarget": wh("Chest") + Vector((0.25, -0.55, 0.1)),
    }
    bpy.context.view_layer.objects.active = ctrl
    bpy.ops.object.mode_set(mode="EDIT")
    for role, head in anchors.items():
        eb = arm_data.edit_bones.new(role)
        eb.head = head
        eb.tail = head + Vector((0, 0, 0.08))
        eb.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # Wire minimal constraints
    head = deform.pose.bones["Head"]
    while head.constraints:
        head.constraints.remove(head.constraints[0])
    c = head.constraints.new("DAMPED_TRACK")
    c.target = ctrl
    c.subtarget = "HeadAim"
    c.track_axis = "TRACK_Y"
    for side in ("L", "R"):
        hand = deform.pose.bones[f"Hand.{side}"]
        while hand.constraints:
            hand.constraints.remove(hand.constraints[0])
        ik = hand.constraints.new("IK")
        ik.target = ctrl
        ik.subtarget = f"HandTarget.{side}"
        ik.chain_count = 3
        ik.use_tail = True
    return ctrl


def _ensure_action(arm, name):
    if name in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[name], do_unlink=True)
    act = bpy.data.actions.new(name)
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    # Blender 5 action slots (best-effort)
    try:
        slots = getattr(act, "slots", None)
        if slots is not None:
            slot = None
            for s in slots:
                slot = s
                break
            if slot is None and hasattr(slots, "new"):
                slot = slots.new(id_type="OBJECT", name="OB" + arm.name)
            if slot is not None and hasattr(arm.animation_data, "action_slot"):
                arm.animation_data.action_slot = slot
    except Exception:
        pass
    return act


def _list_homepage_actions():
    names = []
    for a in bpy.data.actions:
        if a.name.startswith("NURION_Homepage_HOME_") and not a.name.endswith("_CTRL"):
            names.append(a.name)
    return sorted(names)


def _disable_rigify_handlers():
    """Avoid Blender 5 rigify load_post crash wiping/interfering with reload checks."""
    try:
        import addon_utils

        addon_utils.disable("rigify", default_set=True)
    except Exception:
        pass
    # Also clear broken handlers if present
    try:
        handlers = bpy.app.handlers.load_post
        keep = []
        for h in list(handlers):
            mod = getattr(h, "__module__", "") or ""
            if "rigify" in mod:
                continue
            keep.append(h)
        handlers.clear()
        for h in keep:
            handlers.append(h)
    except Exception:
        pass


def _insert(arm, frame):
    bpy.context.view_layer.objects.active = arm
    try:
        bpy.ops.object.mode_set(mode="POSE")
    except Exception:
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.scene.frame_set(frame)
    for b in arm.pose.bones:
        b.rotation_mode = "XYZ"
        b.keyframe_insert(data_path="location", frame=frame)
        b.keyframe_insert(data_path="rotation_euler", frame=frame)
    # Ensure action still assigned after insert (Blender 5 slotting)
    if arm.animation_data and arm.animation_data.action is None:
        # find latest NURION action
        for a in reversed(list(bpy.data.actions)):
            if a.name.startswith("NURION_Homepage_"):
                arm.animation_data.action = a
                break


def _action_channel_count(act) -> int:
    n = 0
    if hasattr(act, "fcurves") and act.fcurves is not None:
        try:
            return len(act.fcurves)
        except Exception:
            pass
    # Blender 5 layered actions
    layers = getattr(act, "layers", None)
    if layers is not None:
        for layer in layers:
            strips = getattr(layer, "strips", None) or []
            for strip in strips:
                channels = getattr(strip, "channelbags", None) or getattr(strip, "channels", None)
                if channels is None:
                    continue
                try:
                    n += len(channels)
                except Exception:
                    n += 1
    return n


def _reset_pose(arm):
    for b in arm.pose.bones:
        b.rotation_mode = "XYZ"
        b.rotation_euler = (0, 0, 0)
        b.location = (0, 0, 0)


def _author_presets(deform, ctrl):
    out = []
    for preset in PRESETS:
        pid = preset["id"]
        aname = f"NURION_Homepage_{pid}"
        n = preset["frames"]
        gesture = preset["gesture"]
        d_act = _ensure_action(deform, aname)
        c_act = _ensure_action(ctrl, aname + "_CTRL")
        _reset_pose(deform)
        _reset_pose(ctrl)
        start, hold_s, hold_e, ret = 1, max(2, n // 4), max(3, (3 * n) // 4), n
        _insert(deform, start)
        _insert(ctrl, start)
        l_eul, r_eul = GESTURE_EULER[gesture]
        for f in (hold_s, hold_e):
            bpy.context.scene.frame_set(f)
            deform.pose.bones["Hand.L"].rotation_euler = Euler(l_eul, "XYZ")
            deform.pose.bones["Hand.R"].rotation_euler = Euler(r_eul, "XYZ")
            deform.pose.bones["Head"].rotation_euler = Euler((0.08, 0, 0), "XYZ")
            if preset["loop"]:
                t = (f - hold_s) / max(1, hold_e - hold_s)
                deform.pose.bones["Spine"].location = (0, 0, 0.004 * math.sin(t * math.pi * 2))
            _insert(deform, f)
            _insert(ctrl, f)
        _reset_pose(deform)
        _reset_pose(ctrl)
        _insert(deform, ret)
        _insert(ctrl, ret)
        d_act["nurion_preset_id"] = pid
        d_act["nurion_loop"] = preset["loop"]
        d_act["nurion_gesture"] = gesture
        d_act["nurion_fps_canonical"] = 30
        d_act["nurion_channel_count"] = _action_channel_count(d_act)
        d_act.use_fake_user = True
        c_act["nurion_pair_deform_action"] = aname
        c_act.use_fake_user = True
        out.append(aname)
    deform.animation_data.action = None
    ctrl.animation_data.action = None
    return out


def _bone_fingerprint(arm):
    rows = []
    for b in sorted(arm.data.bones, key=lambda x: x.name):
        rows.append(
            {
                "name": b.name,
                "parent": b.parent.name if b.parent else None,
                "head": [round(float(x), 5) for x in b.head_local],
                "tail": [round(float(x), 5) for x in b.tail_local],
            }
        )
    return rows


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = Path(args.zip)
    if not zip_path.is_absolute():
        zip_path = ROOT / zip_path
    pre_zip = _sha(zip_path)

    work = out_dir / "_extract"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(work)
    fbx = _find_fbx(work)
    fbx_sha = _sha(fbx)

    manual_gt = None
    if args.manual_gt_json:
        gt_path = Path(args.manual_gt_json)
        if not gt_path.is_absolute():
            gt_path = ROOT / gt_path
        if gt_path.is_file():
            manual_gt = json.loads(gt_path.read_text(encoding="utf-8"))

    _reset_scene()
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=False, use_anim=False)

    source_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not source_meshes:
        _write(
            out_dir / "V07_GATE7_RUN_STATUS.json",
            {"V07_GATE7_RUN": "ASSET_INELIGIBLE", "reason": "NO_MESH", "runId": args.run_id},
        )
        return 2

    # Eligibility soft: verts
    verts = sum(len(m.data.vertices) for m in source_meshes)
    if verts < 500:
        _write(
            out_dir / "V07_GATE7_RUN_STATUS.json",
            {"V07_GATE7_RUN": "ASSET_INELIGIBLE", "reason": "INSUFFICIENT_GEOMETRY", "runId": args.run_id},
        )
        return 2

    coll = bpy.data.collections.new(COLL)
    bpy.context.scene.collection.children.link(coll)
    mins, maxs = _mesh_bounds(source_meshes)
    joints = _estimate_joints(mins, maxs)
    deform = _create_deform(joints, coll)

    src_vg = {m.name: len(m.vertex_groups) for m in source_meshes}
    clones = [_dup_mesh(m, coll) for m in source_meshes]
    for c in clones:
        _bind_normalize(deform, c)

    # originals unchanged
    if any(len(bpy.data.objects[n].vertex_groups) != src_vg[n] for n in src_vg if n in bpy.data.objects):
        raise SystemExit("original mesh mutated")

    wstats = [_weight_ok(c, deform) for c in clones]
    weight_fail = any(s["unweighted"] or s["sumFail"] or s["nonfinite"] or s["negative"] for s in wstats)

    ctrl = _create_control(deform, coll)
    actions = _author_presets(deform, ctrl)
    actions_before_save = _list_homepage_actions()
    if len(actions_before_save) != 10:
        # fall back to authored list
        actions_before_save = sorted(actions)

    blend_path = out_dir / f"NURION_HomepageHoldout_{args.label}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    # reload with rigify interference reduced
    _disable_rigify_handlers()
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    _disable_rigify_handlers()
    deform2 = bpy.data.objects.get(DEFORM)
    ctrl2 = bpy.data.objects.get(CONTROL)
    reload_ok = deform2 is not None and ctrl2 is not None
    action_names = _list_homepage_actions()
    # If Blender 5 lost action datablocks on reload, restore from authored names
    # only when objects reloaded and pre-save had 10 (determinism still compares fingerprints).
    if len(action_names) == 0 and len(actions_before_save) == 10:
        action_names = list(actions_before_save)
        actions_rehydrated_from_presave = True
    else:
        actions_rehydrated_from_presave = False
    # Prefer actual datablocks when present
    action_datablock_count = len(_list_homepage_actions())

    # FPS semantic markers
    fps_doc = {str(fps): {"canonicalFps": 30, "timeScale": 30 / fps} for fps in (24, 30, 60)}

    # Optional GT accuracy
    accuracy = {
        "manualGroundTruthPresent": manual_gt is not None,
        "meshyBonesAsGroundTruth": "DENY",
        "claim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "jointErrorsCm": None,
    }
    if manual_gt and deform2:
        # Expect { "joints": { "Head": [x,y,z], ... } } in world meters
        errs = []
        for jname, xyz in (manual_gt.get("joints") or {}).items():
            pb = deform2.pose.bones.get(jname)
            if not pb:
                continue
            world = deform2.matrix_world @ pb.head
            gt = Vector(xyz)
            errs.append({"joint": jname, "errCm": round((world - gt).length * 100.0, 4)})
        if errs:
            mean = sum(e["errCm"] for e in errs) / len(errs)
            mx = max(e["errCm"] for e in errs)
            accuracy["jointErrorsCm"] = {"mean": round(mean, 4), "max": round(mx, 4), "perJoint": errs}
            # Gate1 thresholds upper-body-ish
            if mean <= 3.5 and mx <= 7.5:
                accuracy["claim"] = "GT_JOINT_GATES_PASS"
            else:
                accuracy["claim"] = "ALGORITHM_FAIL_GT_JOINT_GATES"

    fingerprint = {
        "boneCount": len(deform2.data.bones) if deform2 else 0,
        "bones": _bone_fingerprint(deform2) if deform2 else [],
        "controlRoles": sorted(b.name for b in ctrl2.data.bones) if ctrl2 else [],
        "actions": actions_before_save,
        "actionsAfterReload": _list_homepage_actions(),
        "actionDatablockCountAfterReload": action_datablock_count,
        "actionsRehydratedNameOnly": actions_rehydrated_from_presave,
        "cloneMeshCount": len([o for o in bpy.data.objects if o.name.startswith("NURION_W_")]),
        "weightStats": wstats,
        "fpsSemantics": fps_doc,
    }
    fp_hash = _stable_hash(
        {
            "boneCount": fingerprint["boneCount"],
            "bones": fingerprint["bones"],
            "controlRoles": fingerprint["controlRoles"],
            "actions": fingerprint["actions"],
            "cloneMeshCount": fingerprint["cloneMeshCount"],
            "weightStats": fingerprint["weightStats"],
            "fpsSemantics": fingerprint["fpsSemantics"],
        }
    )

    post_zip = _sha(zip_path)
    # Require authored 10 actions pre-save; reload must retain datablocks (not name-only rehydrate)
    actions_ok = len(actions_before_save) == 10 and action_datablock_count == 10
    run_pipeline = (not weight_fail) and reload_ok and actions_ok and (not actions_rehydrated_from_presave)
    run_status = {
        "schema": "NURION_V07_GATE7_RUN_STATUS",
        "runId": args.run_id,
        "label": args.label,
        "V07_GATE7_RUN": "PIPELINE_OK" if run_pipeline else "ALGORITHM_FAIL",
        "weightFail": weight_fail,
        "reloadOk": reload_ok,
        "actionCount": len(actions_before_save),
        "actionDatablockCountAfterReload": action_datablock_count,
        "actionsRehydratedNameOnly": actions_rehydrated_from_presave,
        "fingerprintHash": fp_hash,
        "sourceZipSha256": pre_zip,
        "fbxSha256": fbx_sha,
        "sourceMutation": 0 if pre_zip == post_zip else 1,
        "accuracy": accuracy,
        "blendFile": str(blend_path.relative_to(ROOT)).replace("\\", "/"),
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
    }
    _write(out_dir / "V07_GATE7_FINGERPRINT.json", {"fingerprintHash": fp_hash, "fingerprint": fingerprint})
    _write(out_dir / "V07_GATE7_RUN_STATUS.json", run_status)
    _write(
        out_dir / "V07_V06_HANDOFF.json",
        {
            "schema": "NURION_V07_V06_HANDOFF",
            "subject": args.label,
            "holdout": True,
            "deformRig": DEFORM,
            "controlRig": CONTROL,
            "actions": action_names,
            "meshyActionCopy": "DENY",
            "accuracyClaim": accuracy["claim"],
            "production": "NO-GO",
        },
    )

    print(
        json.dumps(
            {
                "runId": args.run_id,
                "status": run_status["V07_GATE7_RUN"],
                "fp": fp_hash,
                "actions": len(actions_before_save),
                "actionsAfterReload": action_datablock_count,
            },
            ensure_ascii=False,
        )
    )
    return 0 if run_status["V07_GATE7_RUN"] == "PIPELINE_OK" and run_status["sourceMutation"] == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
