#!/usr/bin/env python3
"""NURION-RIG-01B — Jake FBX skeleton hierarchy / rest / axis forensic."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


FACE_TOKENS = (
    "jaw",
    "eye",
    "tongue",
    "facial",
    "teeth",
    "upperjaw",
)
TWIST_TOKENS = ("twist",)
FINGER_TOKENS = ("thumb", "index", "mid", "ring", "pinky")
TOE_TOKENS = ("toe", "bigtoe", "pinkytoes")
SHARE_TOKENS = ("sharebone", "breast", "ribstwist")


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


def classify(name: str) -> str:
    n = name.lower()
    if any(t in n for t in FACE_TOKENS):
        return "FACE_OWNED_DO_NOT_ABSORB"
    if any(t in n for t in SHARE_TOKENS) and "toe" not in n:
        return "DEFORM_OR_HELPER_OPTIONAL"
    if "twist" in n:
        return "DEFORM_EXTENSION_CANDIDATE"
    if any(t in n for t in FINGER_TOKENS) and "toe" not in n:
        return "HAND_EXTENSION_CANDIDATE"
    if any(t in n for t in ("toebase", "bigtoe", "pinkytoes", "ringtoe", "midtoe", "indextoe")):
        return "TOE_EXTENSION_OR_HELPER"
    if "toebase" in n or (n.endswith("toe") and "toebase" in n):
        return "BODY_CORE_MAP_CANDIDATE"
    # Core-ish CC names
    core_keys = (
        "boneroot",
        "hip",
        "pelvis",
        "waist",
        "spine",
        "neck",
        "head",
        "clavicle",
        "upperarm",
        "forearm",
        "hand",
        "thigh",
        "calf",
        "foot",
        "toebase",
    )
    if any(k in n for k in core_keys) and "twist" not in n and "facial" not in n:
        if "hand" in n and any(t in n for t in FINGER_TOKENS):
            return "HAND_EXTENSION_CANDIDATE"
        return "BODY_CORE_MAP_CANDIDATE"
    return "OTHER_OR_HELPER"


def mat_to_list(m):
    return [[round(m[i][j], 6) for j in range(4)] for i in range(4)]


def axis_from_bone(bone):
    # Blender bones: Y along bone (head→tail), X/Z from bone matrix
    m = bone.matrix.to_3x3()
    x = m @ Vector((1, 0, 0))
    y = m @ Vector((0, 1, 0))
    z = m @ Vector((0, 0, 1))
    def unit(v):
        if v.length < 1e-12:
            return [0.0, 0.0, 0.0]
        u = v.normalized()
        return [round(u.x, 6), round(u.y, 6), round(u.z, 6)]
    return {"x": unit(x), "y": unit(y), "z": unit(z)}


def find_armature():
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            return obj
    raise RuntimeError("No armature found after FBX import")


def bone_record(arm_obj, bone):
    parent = bone.parent.name if bone.parent else None
    head_w = arm_obj.matrix_world @ bone.head_local
    tail_w = arm_obj.matrix_world @ bone.tail_local
    length = (tail_w - head_w).length
    children = [c.name for c in bone.children]
    return {
        "name": bone.name,
        "parent": parent,
        "children": sorted(children),
        "classification": classify(bone.name),
        "length": round(float(length), 6),
        "headLocal": [round(float(v), 6) for v in bone.head_local],
        "tailLocal": [round(float(v), 6) for v in bone.tail_local],
        "headWorld": [round(float(v), 6) for v in head_w],
        "tailWorld": [round(float(v), 6) for v in tail_w],
        "matrixLocal": mat_to_list(bone.matrix_local),
        "axesLocal": axis_from_bone(bone),
        "useConnect": bool(bone.use_connect),
        "roll": round(float(bone.roll), 6),
    }


def build_tree(bones_by_name: dict, root_names: list[str]) -> dict:
    def node(name: str):
        b = bones_by_name[name]
        return {
            "name": name,
            "classification": b["classification"],
            "children": [node(c) for c in b["children"] if c in bones_by_name],
        }

    return [node(r) for r in root_names]


def pair_symmetry(bones: dict) -> dict:
    """Compare L/R length and axis rough symmetry for core limb bones."""
    pairs = [
        ("CC_Base_L_Clavicle", "CC_Base_R_Clavicle"),
        ("CC_Base_L_Upperarm", "CC_Base_R_Upperarm"),
        ("CC_Base_L_Forearm", "CC_Base_R_Forearm"),
        ("CC_Base_L_Hand", "CC_Base_R_Hand"),
        ("CC_Base_L_Thigh", "CC_Base_R_Thigh"),
        ("CC_Base_L_Calf", "CC_Base_R_Calf"),
        ("CC_Base_L_Foot", "CC_Base_R_Foot"),
        ("CC_Base_L_ToeBase", "CC_Base_R_ToeBase"),
        ("CC_Base_L_Thumb1", "CC_Base_R_Thumb1"),
        ("CC_Base_L_Index1", "CC_Base_R_Index1"),
    ]
    out = []
    for l, r in pairs:
        if l not in bones or r not in bones:
            out.append({"pair": [l, r], "present": False})
            continue
        bl, br = bones[l], bones[r]
        len_ratio = bl["length"] / br["length"] if br["length"] > 1e-9 else None
        # Mirror X of head world roughly
        hx_sum = bl["headWorld"][0] + br["headWorld"][0]
        out.append(
            {
                "pair": [l, r],
                "present": True,
                "lengthL": bl["length"],
                "lengthR": br["length"],
                "lengthRatioLoverR": round(len_ratio, 4) if len_ratio is not None else None,
                "headWorldXSum": round(hx_sum, 4),
                "parentL": bl["parent"],
                "parentR": br["parent"],
                "parentRoleMatch": (
                    bl["parent"].replace("_L_", "_X_").replace("_R_", "_X_")
                    == br["parent"].replace("_L_", "_X_").replace("_R_", "_X_")
                    if bl["parent"] and br["parent"]
                    else bl["parent"] == br["parent"]
                ),
            }
        )
    return out


def path_to_root(bones: dict, name: str) -> list[str]:
    path = []
    cur = name
    seen = set()
    while cur and cur not in seen:
        path.append(cur)
        seen.add(cur)
        cur = bones[cur]["parent"] if cur in bones else None
    return path


def main():
    args = parse_args()
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(args.fbx), automatic_bone_orientation=True)
    arm = find_armature()
    # Ensure rest pose data from edit bones for accuracy
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = {b.name: b for b in arm.data.edit_bones}
    records = {}
    for name, eb in edit_bones.items():
        parent = eb.parent.name if eb.parent else None
        children = sorted(c.name for c in eb.children)
        head_w = arm.matrix_world @ eb.head
        tail_w = arm.matrix_world @ eb.tail
        length = (tail_w - head_w).length
        # axis from edit bone matrix
        m = eb.matrix.to_3x3()

        def unit(v):
            if v.length < 1e-12:
                return [0.0, 0.0, 0.0]
            u = v.normalized()
            return [round(u.x, 6), round(u.y, 6), round(u.z, 6)]

        axes = {
            "x": unit(m @ Vector((1, 0, 0))),
            "y": unit(m @ Vector((0, 1, 0))),
            "z": unit(m @ Vector((0, 0, 1))),
        }
        records[name] = {
            "name": name,
            "parent": parent,
            "children": children,
            "classification": classify(name),
            "length": round(float(length), 6),
            "headLocal": [round(float(v), 6) for v in eb.head],
            "tailLocal": [round(float(v), 6) for v in eb.tail],
            "headWorld": [round(float(v), 6) for v in head_w],
            "tailWorld": [round(float(v), 6) for v in tail_w],
            "matrixLocal": mat_to_list(eb.matrix),
            "axesLocal": axes,
            "useConnect": bool(eb.use_connect),
            "roll": round(float(eb.roll), 6),
        }
    bpy.ops.object.mode_set(mode="OBJECT")

    roots = sorted(n for n, b in records.items() if b["parent"] is None)
    by_class: dict[str, list[str]] = {}
    for n, b in records.items():
        by_class.setdefault(b["classification"], []).append(n)
    for k in by_class:
        by_class[k] = sorted(by_class[k])

    # Key hierarchy chains of interest
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
        "CC_Base_L_Upperarm",
        "CC_Base_L_Forearm",
        "CC_Base_L_Hand",
        "CC_Base_L_Thigh",
        "CC_Base_L_Calf",
        "CC_Base_L_Foot",
        "CC_Base_L_ToeBase",
        "CC_Base_L_Thumb1",
        "CC_Base_JawRoot",
        "CC_Base_L_Eye",
        "CC_Base_FacialBone",
    ]
    focus_paths = {n: path_to_root(records, n) for n in focus if n in records}

    # Length ratios along a reference chain (pelvis→head / thigh→toe)
    def ratio(a, b):
        if a not in records or b not in records or records[b]["length"] < 1e-9:
            return None
        return round(records[a]["length"] / records[b]["length"], 4)

    length_ratios = {
        "thighL_over_calfL": ratio("CC_Base_L_Thigh", "CC_Base_L_Calf"),
        "upperArmL_over_foreArmL": ratio("CC_Base_L_Upperarm", "CC_Base_L_Forearm"),
        "spine01_over_spine02": ratio("CC_Base_Spine01", "CC_Base_Spine02"),
        "foreArmL_over_handL": ratio("CC_Base_L_Forearm", "CC_Base_L_Hand"),
    }

    # Proposed NURION mapping anchors from Jake (informational)
    jake_to_nurion_anchor = {
        "CC_Base_BoneRoot": "NURION_root (or above wrapper)",
        "CC_Base_Hip": "review — may map near NURION_root/pelvis split",
        "CC_Base_Pelvis": "NURION_pelvis candidate",
        "CC_Base_Waist": "may fold into spine01 or drop as helper — 01B decides",
        "CC_Base_Spine01": "NURION_spine01 or spine02 — confirm order",
        "CC_Base_Spine02": "NURION_spine02 or chest — confirm order",
        "CC_Base_NeckTwist01": "NURION_neck candidate (or twist→neck)",
        "CC_Base_Head": "NURION_head + FACE attachment sole point",
        "CC_Base_L_Clavicle": "NURION_clavicle_L",
        "CC_Base_L_Upperarm": "NURION_upperArm_L",
        "CC_Base_L_Forearm": "NURION_lowerArm_L",
        "CC_Base_L_Hand": "NURION_hand_L",
        "CC_Base_L_Thigh": "NURION_thigh_L",
        "CC_Base_L_Calf": "NURION_calf_L",
        "CC_Base_L_Foot": "NURION_foot_L",
        "CC_Base_L_ToeBase": "NURION_toe_L",
    }

    payload = {
        "stage": "NURION-RIG-01B_JAKE_SKELETON_HIERARCHY_FORENSIC",
        "fbx": str(args.fbx),
        "armatureObject": arm.name,
        "armatureData": arm.data.name,
        "boneCount": len(records),
        "rootBones": roots,
        "hierarchyTree": build_tree(records, roots),
        "bones": records,
        "byClassification": by_class,
        "classificationCounts": {k: len(v) for k, v in sorted(by_class.items())},
        "focusPathsToRoot": focus_paths,
        "lrSymmetry": pair_symmetry(records),
        "lengthRatios": length_ratios,
        "jakeToNurionAnchorNotes": jake_to_nurion_anchor,
        "faceBoundaryReminder": {
            "doNotAbsorb": by_class.get("FACE_OWNED_DO_NOT_ABSORB", []),
            "soleBodyFaceAttachment": "NURION_head ← CC_Base_Head transform only",
        },
        "blenderVersion": bpy.app.version_string,
        "importNote": "automatic_bone_orientation=True (same as HR11 visual gate)",
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out_json),
                "boneCount": len(records),
                "roots": roots,
                "classificationCounts": payload["classificationCounts"],
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
