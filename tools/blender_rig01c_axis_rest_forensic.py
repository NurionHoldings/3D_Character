#!/usr/bin/env python3
"""NURION-RIG-01C — measure Jake rest pose / axes for Canonical Axis & Retarget Convention."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def parse_args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", type=Path, required=True)
    p.add_argument("--out-json", type=Path, required=True)
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def vlist(v: Vector):
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def unit(v: Vector):
    if v.length < 1e-12:
        return Vector((0, 0, 0))
    return v.normalized()


def angle_deg(a: Vector, b: Vector) -> float:
    if a.length < 1e-12 or b.length < 1e-12:
        return float("nan")
    return math.degrees(a.angle(b))


def quat_list(q):
    return [round(float(q.w), 6), round(float(q.x), 6), round(float(q.y), 6), round(float(q.z), 6)]


def main():
    args = parse_args()
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(args.fbx), automatic_bone_orientation=True)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")

    ebs = {b.name: b for b in arm.data.edit_bones}
    mw = arm.matrix_world

    def bone_metrics(name: str) -> dict | None:
        if name not in ebs:
            return None
        eb = ebs[name]
        head_w = mw @ eb.head
        tail_w = mw @ eb.tail
        y_w = unit(tail_w - head_w)
        m = (mw @ eb.matrix).to_3x3()
        x_w = unit(m @ Vector((1, 0, 0)))
        z_w = unit(m @ Vector((0, 0, 1)))
        # Blender bone local Y should align with head→tail
        y_local_check = unit(m @ Vector((0, 1, 0)))
        q = (mw @ eb.matrix).to_quaternion()
        return {
            "name": name,
            "parent": eb.parent.name if eb.parent else None,
            "length": round(float((tail_w - head_w).length), 6),
            "headWorld": vlist(head_w),
            "tailWorld": vlist(tail_w),
            "axisWorld": {"x": vlist(x_w), "y": vlist(y_w), "z": vlist(z_w)},
            "blenderBoneYWorld": vlist(y_local_check),
            "yAlignDeg": round(angle_deg(y_w, y_local_check), 4),
            "roll": round(float(eb.roll), 6),
            "worldQuaternionWXYZ": quat_list(q),
            "matrixWorld": [[round(float((mw @ eb.matrix)[i][j]), 6) for j in range(4)] for i in range(4)],
        }

    focus = [
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
        "CC_Base_R_Clavicle",
        "CC_Base_L_Upperarm",
        "CC_Base_R_Upperarm",
        "CC_Base_L_Forearm",
        "CC_Base_R_Forearm",
        "CC_Base_L_Hand",
        "CC_Base_R_Hand",
        "CC_Base_L_Thigh",
        "CC_Base_R_Thigh",
        "CC_Base_L_Calf",
        "CC_Base_R_Calf",
        "CC_Base_L_Foot",
        "CC_Base_R_Foot",
        "CC_Base_L_ToeBase",
        "CC_Base_R_ToeBase",
    ]
    bones = {n: bone_metrics(n) for n in focus if n in ebs}

    # Character axes heuristics from Hip/Head/feet
    hip = bones["CC_Base_Hip"]
    head = bones["CC_Base_Head"]
    l_foot = bones.get("CC_Base_L_Foot")
    r_foot = bones.get("CC_Base_R_Foot")
    l_ua = bones["CC_Base_L_Upperarm"]
    r_ua = bones["CC_Base_R_Upperarm"]
    spine02 = bones["CC_Base_Spine02"]

    up_guess = unit(
        Vector(head["headWorld"]) - Vector(hip["headWorld"])
    )
    # sideways from left→right upper arm heads
    side_guess = unit(Vector(r_ua["headWorld"]) - Vector(l_ua["headWorld"]))
    forward_guess = unit(up_guess.cross(side_guess))
    # If feet available, refine forward from toe direction average
    if l_foot and r_foot:
        toe_fwd = unit(
            (
                Vector(l_foot["tailWorld"])
                - Vector(l_foot["headWorld"])
                + Vector(r_foot["tailWorld"])
                - Vector(r_foot["headWorld"])
            )
            * 0.5
        )
        # project toe onto ground plane (perp to up)
        toe_fwd = unit(toe_fwd - up_guess * toe_fwd.dot(up_guess))
        if toe_fwd.length > 0.1:
            forward_guess = toe_fwd
            side_guess = unit(forward_guess.cross(up_guess))

    # Arm abduction: angle between upperarm direction and down (-up) projected
    def abduction(upper: dict) -> float:
        arm_dir = unit(Vector(upper["tailWorld"]) - Vector(upper["headWorld"]))
        # angle from torso down (-up) toward side
        down = -up_guess
        return round(angle_deg(arm_dir, down), 3)

    abd_l = abduction(l_ua)
    abd_r = abduction(r_ua)
    avg_abd = (abd_l + abd_r) * 0.5
    # T-pose ~90° from down (horizontal), A-pose typically ~30–50° from down
    if avg_abd >= 75:
        pose_class = "T_POSE_LIKE"
    elif avg_abd <= 55:
        pose_class = "A_POSE_LIKE"
    else:
        pose_class = "INTERMEDIATE"

    # Elbow flexion
    def elbow_angle(ua, fa):
        a = unit(Vector(ua["tailWorld"]) - Vector(ua["headWorld"]))
        b = unit(Vector(fa["tailWorld"]) - Vector(fa["headWorld"]))
        return round(180.0 - angle_deg(a, b), 3)

    # Knee flexion
    def knee_angle(th, ca):
        a = unit(Vector(th["tailWorld"]) - Vector(th["headWorld"]))
        b = unit(Vector(ca["tailWorld"]) - Vector(ca["headWorld"]))
        return round(180.0 - angle_deg(a, b), 3)

    # Collapsed neck compound: NeckTwist01 * NeckTwist02 relative
    n1 = ebs["CC_Base_NeckTwist01"]
    n2 = ebs["CC_Base_NeckTwist02"]
    m1 = mw @ n1.matrix
    m2 = mw @ n2.matrix
    # compound from chest/spine02 parent space: use local chain product approximation
    compound = m1 @ (m1.inverted() @ m2)
    # Better: relative n2 in n1 parent chain — world of n2 expressed from n1 head
    neck_compound_q = (m1.to_quaternion().normalized() @ Matrix.Identity(3).to_quaternion())  # placeholder
    # Proper: T_neck_world ≈ T_n2_world (end of chain); local collapse = inv(parent_world) * n2_world
    parent_neck = ebs["CC_Base_Spine02"]
    parent_w = mw @ parent_neck.matrix
    neck_collapse_local = parent_w.inverted() @ (mw @ n2.matrix)

    # Height / scale proxy
    height = (Vector(head["tailWorld"]) - Vector(hip["headWorld"])).length
    thigh_len = bones["CC_Base_L_Thigh"]["length"]

    # Armature object transform
    arm_loc = arm.matrix_world.to_translation()
    arm_q = arm.matrix_world.to_quaternion()
    arm_scale = arm.matrix_world.to_scale()

    bpy.ops.object.mode_set(mode="OBJECT")

    payload = {
        "stage": "NURION-RIG-01C_MEASUREMENT",
        "fbx": str(args.fbx),
        "blenderVersion": bpy.app.version_string,
        "importNote": "automatic_bone_orientation=True",
        "armature": {
            "object": arm.name,
            "location": vlist(arm_loc),
            "quaternionWXYZ": quat_list(arm_q),
            "scale": vlist(arm_scale),
        },
        "characterAxesGuess": {
            "up": vlist(up_guess),
            "forward": vlist(forward_guess),
            "sideLeftToRight": vlist(side_guess),
            "note": "Heuristic from Hip→Head up, feet/toes forward, L→R upperarm side",
        },
        "restPoseClassification": {
            "leftUpperArmAbductionFromDownDeg": abd_l,
            "rightUpperArmAbductionFromDownDeg": abd_r,
            "averageAbductionDeg": round(avg_abd, 3),
            "class": pose_class,
            "elbowFlexL": elbow_angle(l_ua, bones["CC_Base_L_Forearm"]),
            "elbowFlexR": elbow_angle(r_ua, bones["CC_Base_R_Forearm"]),
            "kneeFlexL": knee_angle(bones["CC_Base_L_Thigh"], bones["CC_Base_L_Calf"]),
            "kneeFlexR": knee_angle(bones["CC_Base_R_Thigh"], bones["CC_Base_R_Calf"]),
        },
        "scaleProxies": {
            "hipToHeadLength": round(float(height), 6),
            "leftThighLength": thigh_len,
            "assumedSceneUnit": "meters_if_CC_default",
        },
        "neckCollapse": {
            "rule": "T_neck = T_NeckTwist01 × T_NeckTwist02 (compound → NURION_neck)",
            "parent": "CC_Base_Spine02",
            "endBone": "CC_Base_NeckTwist02",
            "collapseLocalMatrix": [
                [round(float(neck_collapse_local[i][j]), 6) for j in range(4)] for i in range(4)
            ],
            "collapseLocalQuaternionWXYZ": quat_list(neck_collapse_local.to_quaternion()),
        },
        "intermediaryPelvis": {
            "rule": "Jake Pelvis is adapter intermediary under Hip(NURION_pelvis); thighs parent through it",
            "hipChildren": sorted(c.name for c in ebs["CC_Base_Hip"].children),
            "pelvisChildren": sorted(c.name for c in ebs["CC_Base_Pelvis"].children),
        },
        "bones": bones,
        "blenderBoneAxisNote": "Blender edit-bones: +Y along head→tail; X/Z from bone roll/matrix",
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out_json),
                "poseClass": pose_class,
                "avgAbduction": round(avg_abd, 3),
                "up": vlist(up_guess),
                "forward": vlist(forward_guess),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
