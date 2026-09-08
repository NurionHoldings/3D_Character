#!/usr/bin/env python3
"""
NURION-RIG-02C — extract Jake CC bone locals (rest + sample frames) via Blender.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

# Donor bones required for Core-23 retarget + isolation checks
JAKE_JOINTS = [
    "CC_Base_BoneRoot",
    "CC_Base_Hip",
    "CC_Base_Pelvis",
    "CC_Base_Waist",
    "CC_Base_Spine01",
    "CC_Base_Spine02",
    "CC_Base_NeckTwist01",
    "CC_Base_NeckTwist02",
    "CC_Base_Head",
    "CC_Base_L_Clavicle",
    "CC_Base_L_Upperarm",
    "CC_Base_L_Forearm",
    "CC_Base_L_Hand",
    "CC_Base_R_Clavicle",
    "CC_Base_R_Upperarm",
    "CC_Base_R_Forearm",
    "CC_Base_R_Hand",
    "CC_Base_L_Thigh",
    "CC_Base_L_Calf",
    "CC_Base_L_Foot",
    "CC_Base_L_ToeBase",
    "CC_Base_R_Thigh",
    "CC_Base_R_Calf",
    "CC_Base_R_Foot",
    "CC_Base_R_ToeBase",
]


def parse_args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", type=Path, required=True)
    p.add_argument("--out-json", type=Path, required=True)
    p.add_argument("--clip-id", type=str, default="jake_cc_embedded")
    p.add_argument("--frame-samples", type=str, default="1,10,20,30,40")
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def quat_wxyz(q):
    return [round(float(q.w), 8), round(float(q.x), 8), round(float(q.y), 8), round(float(q.z), 8)]


def vec3(v: Vector):
    return [round(float(v.x), 8), round(float(v.y), 8), round(float(v.z), 8)]


def unit(v: Vector):
    if v.length < 1e-12:
        return Vector((0, 0, 0))
    return v.normalized()


def main():
    args = parse_args()
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(args.fbx), automatic_bone_orientation=True)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.transforms_clear()
    bpy.context.view_layer.update()

    bones = {b.name: b for b in arm.pose.bones}
    missing = [n for n in JAKE_JOINTS if n not in bones]
    if missing:
        raise SystemExit(f"missing Jake joints: {missing}")

    rest_locals = {}
    hierarchy = {}
    for name in JAKE_JOINTS:
        pb = bones[name]
        rest_locals[name] = {
            "rotation_wxyz": quat_wxyz(pb.matrix_basis.to_quaternion().normalized()),
            "translation": vec3(pb.matrix_basis.to_translation()),
        }
        db = arm.data.bones[name]
        hierarchy[name] = db.parent.name if db.parent else None

    mw = arm.matrix_world
    root_h = mw @ arm.data.bones["CC_Base_BoneRoot"].head_local
    head_h = mw @ arm.data.bones["CC_Base_Head"].head_local
    up_vec = unit(head_h - root_h)
    abs_up = [abs(up_vec.x), abs(up_vec.y), abs(up_vec.z)]
    dominant = ["X", "Y", "Z"][abs_up.index(max(abs_up))]
    sign = 1 if getattr(up_vec, dominant.lower()) >= 0 else -1

    la = arm.data.bones["CC_Base_L_Upperarm"]
    arm_dir = unit((mw @ la.tail_local) - (mw @ la.head_local))
    down = Vector((0, 0, -1)) if dominant == "Z" else Vector((0, -1, 0))
    try:
        abduct = math.degrees(arm_dir.angle(down))
    except ValueError:
        abduct = float("nan")

    # Collect twist-ish bone names present on armature (for isolation evidence)
    twist_present = sorted(n for n in bones if "Twist" in n or "twist" in n)

    scene = bpy.context.scene
    frame_start = int(scene.frame_start)
    frame_end = int(scene.frame_end)
    actions = [a.name for a in bpy.data.actions]

    wanted = []
    for tok in args.frame_samples.split(","):
        tok = tok.strip()
        if not tok:
            continue
        f = int(tok)
        if frame_end > frame_start:
            f = max(frame_start, min(frame_end, f))
        wanted.append(f)
    wanted = sorted(set(wanted))

    frames = []
    for f in wanted:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        locals_f = {}
        for name in JAKE_JOINTS:
            pb = bones[name]
            locals_f[name] = {
                "rotation_wxyz": quat_wxyz(pb.matrix_basis.to_quaternion().normalized()),
                "translation": vec3(pb.matrix_basis.to_translation()),
            }
        frames.append({"frame": f, "locals": locals_f})

    sx, sy, sz = arm.matrix_world.to_scale()
    out = {
        "clipId": args.clip_id,
        "asset": str(args.fbx),
        "product_use": False,
        "role": "DONOR_REFERENCE_ONLY",
        "blenderVersion": bpy.app.version_string,
        "armature": arm.name,
        "actions": actions,
        "jointCount": len(JAKE_JOINTS),
        "joints": list(JAKE_JOINTS),
        "hierarchyParent": hierarchy,
        "twistBonesPresent": twist_present,
        "frameRange": [frame_start, frame_end],
        "armatureWorldScale": [round(float(sx), 8), round(float(sy), 8), round(float(sz), 8)],
        "restPoseProbe": {
            "rootToHeadWorld": vec3(up_vec),
            "dominantUpAxis": f"{'+' if sign > 0 else '-'}{dominant}",
            "leftArmAbductionFromDownDeg": round(float(abduct), 6) if abduct == abduct else None,
        },
        "restLocals": rest_locals,
        "frames": frames,
        "neckCollapseParents": {
            "CC_Base_NeckTwist01": hierarchy.get("CC_Base_NeckTwist01"),
            "CC_Base_NeckTwist02": hierarchy.get("CC_Base_NeckTwist02"),
            "expectedCommonParent": "CC_Base_Spine02",
        },
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(args.out_json), "frames": len(frames), "actions": actions, "missing": missing}))


if __name__ == "__main__":
    main()
