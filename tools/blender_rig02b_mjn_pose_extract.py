#!/usr/bin/env python3
"""
NURION-RIG-02B — extract MJN Legacy bone locals (rest + sample frames) via Blender.
Runs inside Blender: blender --background --python this.py -- --glb ... --out ...
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


MJN_JOINTS = [
    "Hips",
    "LeftUpLeg",
    "LeftLeg",
    "LeftFoot",
    "LeftToeBase",
    "RightUpLeg",
    "RightLeg",
    "RightFoot",
    "RightToeBase",
    "Spine02",
    "Spine01",
    "Spine",
    "LeftShoulder",
    "LeftArm",
    "LeftForeArm",
    "LeftHand",
    "RightShoulder",
    "RightArm",
    "RightForeArm",
    "RightHand",
    "neck",
    "Head",
    "head_end",
    "headfront",
]


def parse_args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--asset", type=Path, required=True, help="GLB or FBX path")
    p.add_argument("--out-json", type=Path, required=True)
    p.add_argument("--clip-id", type=str, required=True)
    p.add_argument("--frame-samples", type=str, default="0,15,30,45,60")
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


def import_asset(path: Path):
    suf = path.suffix.lower()
    if suf in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suf == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=True)
    else:
        raise SystemExit(f"unsupported asset type: {suf}")


def main():
    args = parse_args()
    clear_scene()
    import_asset(args.asset)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    bpy.context.view_layer.objects.active = arm

    # Rest / bind: reset pose then read matrix_basis
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.transforms_clear()
    bpy.context.view_layer.update()

    bones = {b.name: b for b in arm.pose.bones}
    missing = [n for n in MJN_JOINTS if n not in bones]
    if missing:
        raise SystemExit(f"missing MJN joints: {missing}; have={sorted(bones)}")

    rest_locals = {}
    hierarchy = {}
    for name in MJN_JOINTS:
        pb = bones[name]
        rest_locals[name] = {
            "rotation_wxyz": quat_wxyz(pb.matrix_basis.to_quaternion().normalized()),
            "translation": vec3(pb.matrix_basis.to_translation()),
        }
        db = arm.data.bones[name]
        hierarchy[name] = db.parent.name if db.parent else None

    # World axis probe at rest (Hips→Head)
    mw = arm.matrix_world
    hips_h = mw @ arm.data.bones["Hips"].head_local
    head_h = mw @ arm.data.bones["Head"].head_local
    up_vec = unit(head_h - hips_h)
    abs_up = [abs(up_vec.x), abs(up_vec.y), abs(up_vec.z)]
    dominant = ["X", "Y", "Z"][abs_up.index(max(abs_up))]
    sign = 1 if getattr(up_vec, dominant.lower()) >= 0 else -1

    # Arm abduction proxy (LeftArm)
    la = arm.data.bones["LeftArm"]
    arm_dir = unit((mw @ la.tail_local) - (mw @ la.head_local))
    down = Vector((0, -1, 0)) if dominant == "Y" else Vector((0, 0, -1))
    try:
        abduct = math.degrees(arm_dir.angle(down))
    except ValueError:
        abduct = float("nan")

    # Animation samples
    scene = bpy.context.scene
    frame_start = int(scene.frame_start)
    frame_end = int(scene.frame_end)
    wanted = []
    for tok in args.frame_samples.split(","):
        tok = tok.strip()
        if not tok:
            continue
        f = int(tok)
        # clamp into clip range if clip has length
        if frame_end > frame_start:
            f = max(frame_start, min(frame_end, f))
        wanted.append(f)
    wanted = sorted(set(wanted))

    frames = []
    for f in wanted:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        locals_f = {}
        for name in MJN_JOINTS:
            pb = bones[name]
            locals_f[name] = {
                "rotation_wxyz": quat_wxyz(pb.matrix_basis.to_quaternion().normalized()),
                "translation": vec3(pb.matrix_basis.to_translation()),
            }
        frames.append({"frame": f, "locals": locals_f})

    # Armature world scale
    sx, sy, sz = arm.matrix_world.to_scale()

    out = {
        "clipId": args.clip_id,
        "asset": str(args.asset),
        "blenderVersion": bpy.app.version_string,
        "armature": arm.name,
        "jointCount": len(MJN_JOINTS),
        "joints": list(MJN_JOINTS),
        "hierarchyParent": hierarchy,
        "frameRange": [frame_start, frame_end],
        "armatureWorldScale": [round(float(sx), 8), round(float(sy), 8), round(float(sz), 8)],
        "restPoseProbe": {
            "hipsToHeadWorld": vec3(up_vec),
            "dominantUpAxis": f"{'+' if sign > 0 else '-'}{dominant}",
            "leftArmAbductionFromDownDeg": round(float(abduct), 6) if abduct == abduct else None,
        },
        "restLocals": rest_locals,
        "frames": frames,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(args.out_json), "frames": len(frames), "missing": missing}))


if __name__ == "__main__":
    main()
