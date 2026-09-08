"""
CCS Gate 2 — Canonical Joint GT & Anatomical Rig.

Clone Gate1 base mesh read-only, place mesh-only joint GT, build Canonical Armature.
Weights DENY. Meshy/v0.7 bones as GT DENY.

Usage:
  blender --background --python tools/blender_ccs_gate2_joint_gt_rig.py -- \\
    --base-blend <path> --out-dir dist/v0.7/canonical/gate2
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
from mathutils import Matrix, Vector

BONES = [
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
    ("Eye.L", "Head"),
    ("Eye.R", "Head"),
    ("Jaw", "Head"),
    ("FaceAttach.Nose", "Head"),
    ("FaceAttach.Mouth", "Head"),
    ("FaceAttach.Brow", "Head"),
]

CONTROLS = [
    "CTRL_LookTarget",
    "CTRL_HeadAim",
    "CTRL_ChestAim",
    "CTRL_HandTarget.L",
    "CTRL_HandTarget.R",
    "CTRL_IK_Foot.L",
    "CTRL_IK_Foot.R",
    "CTRL_Pole_Elbow.L",
    "CTRL_Pole_Elbow.R",
    "CTRL_Pole_Knee.L",
    "CTRL_Pole_Knee.R",
    "CTRL_UIFocusTarget",
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--base-blend", required=True)
    p.add_argument("--expected-blend-sha256", required=True)
    p.add_argument("--out-dir", required=True)
    return p.parse_args(argv)


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _ensure_col(name: str):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def _vg_centroid(obj, name: str):
    vg = obj.vertex_groups.get(name)
    if vg is None:
        return None
    pts = []
    for v in obj.data.vertices:
        try:
            w = vg.weight(v.index)
        except RuntimeError:
            continue
        if w > 0:
            pts.append(obj.matrix_world @ v.co)
    if not pts:
        return None
    return sum(pts, Vector()) / len(pts)


def _bounds(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(v[i] for v in corners) for i in range(3)))
    mx = Vector((max(v[i] for v in corners) for i in range(3)))
    return mn, mx, (mn + mx) * 0.5, mx - mn


def _lerp(a: Vector, b: Vector, t: float) -> Vector:
    return a + (b - a) * t


def _place_joint_gt(mesh_obj):
    mn, mx, center, size = _bounds(mesh_obj)
    z0, z1 = mn.z, mx.z
    h = max(z1 - z0, 1e-6)

    def at_z(t, x=0.0, y=0.0):
        return Vector((x, y, z0 + h * t))

    torso = _vg_centroid(mesh_obj, "REGION_TORSO") or center
    head_c = _vg_centroid(mesh_obj, "REGION_HEAD") or at_z(0.92)
    face_c = _vg_centroid(mesh_obj, "REGION_FACE") or Vector((0.0, mn.y + 0.02, head_c.z))
    hand_l = _vg_centroid(mesh_obj, "REGION_HAND_L") or at_z(0.55, 0.45)
    hand_r = _vg_centroid(mesh_obj, "REGION_HAND_R") or at_z(0.55, -0.45)
    arm_l = _vg_centroid(mesh_obj, "REGION_ARM_L") or at_z(0.72, 0.30)
    arm_r = _vg_centroid(mesh_obj, "REGION_ARM_R") or at_z(0.72, -0.30)
    leg_l = _vg_centroid(mesh_obj, "REGION_LEG_L") or at_z(0.28, 0.09)
    leg_r = _vg_centroid(mesh_obj, "REGION_LEG_R") or at_z(0.28, -0.09)
    foot_l = _vg_centroid(mesh_obj, "REGION_FOOT_L") or Vector((0.09, mn.y + 0.05, z0 + 0.03))
    foot_r = _vg_centroid(mesh_obj, "REGION_FOOT_R") or Vector((-0.09, mn.y + 0.05, z0 + 0.03))

    hips = Vector((0.0, 0.0, z0 + h * 0.48))
    chest = Vector((0.0, 0.0, z0 + h * 0.72))
    neck = Vector((0.0, 0.0, z0 + h * 0.82))
    head = Vector((head_c.x, head_c.y, head_c.z))

    joints = {
        "Root": Vector((0.0, 0.0, z0)),
        "Hips": hips,
        "Spine": _lerp(hips, chest, 0.25),
        "Spine01": _lerp(hips, chest, 0.5),
        "Spine02": _lerp(hips, chest, 0.75),
        "Chest": chest,
        "Neck": neck,
        "Head": head,
        "Clavicle.L": Vector((0.06, 0.0, chest.z + 0.02)),
        "Clavicle.R": Vector((-0.06, 0.0, chest.z + 0.02)),
        "UpperArm.L": Vector((arm_l.x * 0.7 + 0.08, arm_l.y, arm_l.z + 0.05)),
        "UpperArm.R": Vector((arm_r.x * 0.7 - 0.08, arm_r.y, arm_r.z + 0.05)),
        "ForeArm.L": _lerp(arm_l, hand_l, 0.45),
        "ForeArm.R": _lerp(arm_r, hand_r, 0.45),
        "Hand.L": hand_l,
        "Hand.R": hand_r,
        "UpperLeg.L": Vector((0.08, 0.0, hips.z - 0.02)),
        "UpperLeg.R": Vector((-0.08, 0.0, hips.z - 0.02)),
        "LowerLeg.L": Vector((leg_l.x, leg_l.y, (hips.z + foot_l.z) * 0.5)),
        "LowerLeg.R": Vector((leg_r.x, leg_r.y, (hips.z + foot_r.z) * 0.5)),
        "Foot.L": foot_l,
        "Foot.R": foot_r,
        "Toe.L": Vector((foot_l.x, foot_l.y - 0.06, foot_l.z)),
        "Toe.R": Vector((foot_r.x, foot_r.y - 0.06, foot_r.z)),
        "Eye.L": Vector((0.03, face_c.y - 0.01, head.z + 0.02)),
        "Eye.R": Vector((-0.03, face_c.y - 0.01, head.z + 0.02)),
        "Jaw": Vector((0.0, face_c.y - 0.01, head.z - 0.05)),
        "FaceAttach.Nose": Vector((0.0, face_c.y - 0.02, head.z)),
        "FaceAttach.Mouth": Vector((0.0, face_c.y - 0.01, head.z - 0.04)),
        "FaceAttach.Brow": Vector((0.0, face_c.y - 0.01, head.z + 0.04)),
    }
    return joints


def _create_gt_empties(joints, col):
    for name, loc in joints.items():
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=loc)
        e = bpy.context.active_object
        e.name = f"GT_{name}"
        e.empty_display_size = 0.03
        _link(e, col)
        e["gt_source"] = "MESH_GEOMETRY_ONLY"
        e["meshy_ref"] = "DENY"
        e["v07_bone_ref"] = "DENY"


def _build_armature(joints):
    arm_data = bpy.data.armatures.new("NURION_CanonicalArmature_V1_DATA")
    arm_obj = bpy.data.objects.new("NURION_CanonicalArmature_V1", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = arm_data.edit_bones
    created = {}
    tip_eps = {
        "Head": Vector((0, 0, 0.08)),
        "Hand.L": Vector((0.04, 0, 0)),
        "Hand.R": Vector((-0.04, 0, 0)),
        "Toe.L": Vector((0, -0.03, 0)),
        "Toe.R": Vector((0, -0.03, 0)),
        "Eye.L": Vector((0, -0.02, 0)),
        "Eye.R": Vector((0, -0.02, 0)),
        "Jaw": Vector((0, -0.03, -0.01)),
        "FaceAttach.Nose": Vector((0, -0.02, 0)),
        "FaceAttach.Mouth": Vector((0, -0.02, 0)),
        "FaceAttach.Brow": Vector((0, -0.02, 0)),
        "Root": Vector((0, 0, 0.05)),
    }
    children = {}
    for name, parent in BONES:
        children.setdefault(parent, []).append(name)

    for name, parent in BONES:
        eb = ebones.new(name)
        head = joints[name]
        # tip: toward first child or default tip
        kids = children.get(name, [])
        if kids:
            tail = joints[kids[0]]
            if (tail - head).length < 1e-4:
                tail = head + tip_eps.get(name, Vector((0, 0, 0.05)))
        else:
            tail = head + tip_eps.get(name, Vector((0, 0, 0.05)))
        eb.head = head
        eb.tail = tail
        created[name] = eb

    for name, parent in BONES:
        if parent:
            created[name].parent = created[parent]
            created[name].use_connect = False

    # Align roll roughly: use +Y as world forward hint for arms
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.armature.select_all(action="SELECT")
    try:
        bpy.ops.armature.calculate_roll(type="GLOBAL_POS_Y")
    except Exception:
        pass
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def _add_controls(joints, col):
    placements = {
        "CTRL_LookTarget": joints["Head"] + Vector((0, -0.45, 0.05)),
        "CTRL_HeadAim": joints["Head"] + Vector((0, -0.25, 0.02)),
        "CTRL_ChestAim": joints["Chest"] + Vector((0, -0.30, 0)),
        "CTRL_HandTarget.L": joints["Hand.L"] + Vector((0.05, -0.05, 0)),
        "CTRL_HandTarget.R": joints["Hand.R"] + Vector((-0.05, -0.05, 0)),
        "CTRL_IK_Foot.L": joints["Foot.L"],
        "CTRL_IK_Foot.R": joints["Foot.R"],
        "CTRL_Pole_Elbow.L": joints["ForeArm.L"] + Vector((0, 0.12, 0)),
        "CTRL_Pole_Elbow.R": joints["ForeArm.R"] + Vector((0, 0.12, 0)),
        "CTRL_Pole_Knee.L": joints["LowerLeg.L"] + Vector((0, -0.12, 0)),
        "CTRL_Pole_Knee.R": joints["LowerLeg.R"] + Vector((0, -0.12, 0)),
        "CTRL_UIFocusTarget": joints["Chest"] + Vector((0.15, -0.50, 0.05)),
    }
    for name, loc in placements.items():
        bpy.ops.object.empty_add(type="SPHERE", location=loc)
        e = bpy.context.active_object
        e.name = name
        e.empty_display_size = 0.04
        _link(e, col)


def _add_ik(arm_obj):
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")
    for bone_name, target, pole, chain in [
        ("ForeArm.L", "CTRL_HandTarget.L", "CTRL_Pole_Elbow.L", 2),
        ("ForeArm.R", "CTRL_HandTarget.R", "CTRL_Pole_Elbow.R", 2),
        ("LowerLeg.L", "CTRL_IK_Foot.L", "CTRL_Pole_Knee.L", 2),
        ("LowerLeg.R", "CTRL_IK_Foot.R", "CTRL_Pole_Knee.R", 2),
    ]:
        pb = arm_obj.pose.bones.get(bone_name)
        if pb is None:
            continue
        c = pb.constraints.new("IK")
        c.target = bpy.data.objects.get(target)
        c.pole_target = bpy.data.objects.get(pole)
        c.chain_count = chain
        c.pole_angle = 0.0
    bpy.ops.object.mode_set(mode="OBJECT")


def _bone_inside_volume(arm_obj, mesh_obj):
    """Approximate: bone head within expanded mesh bounds."""
    mn, mx, _, _ = _bounds(mesh_obj)
    pad = Vector((0.02, 0.02, 0.02))
    mn = mn - pad
    mx = mx + pad
    outside = []
    for b in arm_obj.data.bones:
        p = arm_obj.matrix_world @ b.head_local
        if not (mn.x <= p.x <= mx.x and mn.y <= p.y <= mx.y and mn.z <= p.z <= mx.z):
            outside.append(b.name)
    return outside


def _gt_vs_armature_errors(joints, arm_obj):
    rows = []
    for name, gt in joints.items():
        bone = arm_obj.data.bones.get(name)
        if bone is None:
            rows.append({"joint": name, "errorM": None, "missing": True})
            continue
        head = arm_obj.matrix_world @ bone.head_local
        err = (head - gt).length
        rows.append({"joint": name, "errorM": round(err, 6), "missing": False})
    vals = [r["errorM"] for r in rows if r["errorM"] is not None]
    return {
        "perJoint": rows,
        "meanM": round(sum(vals) / len(vals), 6) if vals else None,
        "maxM": round(max(vals), 6) if vals else None,
        "missingBones": [r["joint"] for r in rows if r["missing"]],
    }


def _xray_renders(out_dir: Path, mesh_obj, arm_obj):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "SINGLE"
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    mesh_obj.show_in_front = False
    arm_obj.show_in_front = True
    arm_obj.data.display_type = "OCTAHEDRAL"
    # Enable x-ray-like: bone in front
    for area_type in ():
        pass
    mn, mx, center, size = _bounds(mesh_obj)
    dist = max(size.length, 1.0) * 1.8
    cams = {
        "FRONT": ((center.x, center.y - dist, center.z), (math.radians(90), 0, 0)),
        "BACK": ((center.x, center.y + dist, center.z), (math.radians(90), 0, math.radians(180))),
        "LEFT": ((center.x - dist, center.y, center.z), (math.radians(90), 0, math.radians(90))),
        "RIGHT": ((center.x + dist, center.y, center.z), (math.radians(90), 0, math.radians(-90))),
        "TOP": ((center.x, center.y, center.z + dist), (0, 0, 0)),
        "BOTTOM": ((center.x, center.y, center.z - dist), (math.radians(180), 0, 0)),
    }
    evidence = out_dir / "xray"
    evidence.mkdir(parents=True, exist_ok=True)
    files = []
    for role, (loc, rot) in cams.items():
        bpy.ops.object.camera_add(location=loc, rotation=rot)
        cam = bpy.context.active_object
        cam.name = f"XRAY_{role}"
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = max(size.x, size.y, size.z) * 1.4
        scene.camera = cam
        path = evidence / f"{role}.png"
        scene.render.filepath = str(path.with_suffix(""))
        bpy.ops.render.render(write_still=True)
        if not path.exists():
            cand = Path(str(path) + ".png")
            if cand.exists():
                cand.replace(path)
        if path.exists():
            files.append({"view": role, "sha256": _sha_file(path), "path": f"xray/{role}.png"})
    return files


def main() -> int:
    args = _parse(sys.argv)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = Path(args.base_blend)
    sha = _sha_file(base)
    if sha.lower() != args.expected_blend_sha256.lower():
        raise SystemExit(f"base blend sha mismatch: {sha}")

    work_blend_src = out / "source_readonly" / base.name
    work_blend_src.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base, work_blend_src)
    if _sha_file(work_blend_src) != sha:
        raise SystemExit("clone sha mismatch")

    bpy.ops.wm.open_mainfile(filepath=str(work_blend_src))

    # Remove any accidental armatures from clone (Gate1 should have none)
    for obj in list(bpy.data.objects):
        if obj.type == "ARMATURE":
            bpy.data.objects.remove(obj, do_unlink=True)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("no mesh in base blend")
    mesh_obj = meshes[0]
    mesh_col = _ensure_col("NURION_CCS_MESH_READONLY")
    _link(mesh_obj, mesh_col)
    mesh_obj.hide_select = True

    gt_col = _ensure_col("NURION_CCS_JOINT_GT")
    ctrl_col = _ensure_col("NURION_CCS_CONTROLS")
    arm_col = _ensure_col("NURION_CCS_ARMATURE")

    joints = _place_joint_gt(mesh_obj)
    _create_gt_empties(joints, gt_col)
    arm_obj = _build_armature(joints)
    _link(arm_obj, arm_col)
    _add_controls(joints, ctrl_col)
    _add_ik(arm_obj)

    # Weights DENY: ensure no armature modifier added
    for mod in list(mesh_obj.modifiers):
        if mod.type == "ARMATURE":
            mesh_obj.modifiers.remove(mod)

    outside = _bone_inside_volume(arm_obj, mesh_obj)
    errors = _gt_vs_armature_errors(joints, arm_obj)
    xray = _xray_renders(out, mesh_obj, arm_obj)

    # Lock bone metadata
    bone_lock = []
    for name, parent in BONES:
        b = arm_obj.data.bones[name]
        head = list(arm_obj.matrix_world @ b.head_local)
        tail = list(arm_obj.matrix_world @ b.tail_local)
        length = (Vector(tail) - Vector(head)).length
        bone_lock.append(
            {
                "name": name,
                "parent": parent,
                "head": [round(v, 6) for v in head],
                "tail": [round(v, 6) for v in tail],
                "lengthM": round(length, 6),
                "roll": round(float(b.matrix_local.to_euler().z), 6),
            }
        )

    gt_doc = {
        "schema": "NURION_V07_CCS_GATE2_JOINT_GT",
        "source": "MESH_GEOMETRY_ONLY",
        "meshyBonesAsGt": "DENY",
        "v07GeneratedBonesAsGt": "DENY",
        "unit": "meter",
        "space": "WORLD",
        "joints": {k: [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)] for k, v in joints.items()},
        "sets": {
            "BODY": [n for n, _ in BONES if n.split(".")[0] in {
                "Root", "Hips", "Spine", "Spine01", "Spine02", "Chest", "Neck", "Head",
                "Clavicle", "UpperArm", "ForeArm", "Hand", "UpperLeg", "LowerLeg", "Foot", "Toe"
            } or n in {"Root", "Hips", "Spine", "Spine01", "Spine02", "Chest", "Neck", "Head"}],
            "HAND": ["Hand.L", "Hand.R"],
            "EYE": ["Eye.L", "Eye.R"],
            "JAW": ["Jaw"],
            "FACE_ATTACHMENT": ["FaceAttach.Nose", "FaceAttach.Mouth", "FaceAttach.Brow"],
        },
    }
    _write(out / "V07_CCS_GATE2_JOINT_GT.json", gt_doc)

    out_blend = out / "NURION_CanonicalRig_V1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    receipt = {
        "schema": "NURION_V07_CCS_GATE2_RUN_RECEIPT",
        "baseBlendSha256": sha,
        "outBlendSha256": _sha_file(out_blend),
        "boneCount": len(BONES),
        "controlCount": len(CONTROLS),
        "weightsGenerated": False,
        "bonesOutsideVolume": outside,
        "gtVsArmature": errors,
        "xray": xray,
        "boneLockSha256": _stable_hash(bone_lock),
        "jointGtSha256": _stable_hash(gt_doc),
        "blenderVersion": bpy.app.version_string,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(out / "V07_CCS_GATE2_BONE_LOCK.json", {"bones": bone_lock, "sha256": receipt["boneLockSha256"]})
    _write(out / "V07_CCS_GATE2_RUN_RECEIPT.json", receipt)
    print("GATE2_DONE", out_blend)
    print("OUTSIDE", outside)
    print("MAX_ERR", errors.get("maxM"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
