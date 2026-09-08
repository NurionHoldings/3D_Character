"""Validate generated bone structure."""

from __future__ import annotations

from typing import List

import bpy

REQUIRED_BONES = [
    "spine",
    "upper_arm.L",
    "upper_arm.R",
    "thigh.L",
    "thigh.R",
]


def validate_bone_structure(armature: bpy.types.Object) -> List[str]:
    issues: List[str] = []
    if armature is None or armature.type != "ARMATURE":
        return ["Active object is not an armature."]

    names = {b.name for b in armature.data.bones}
    for required in REQUIRED_BONES:
        if required not in names:
            issues.append(f"Missing bone: {required}")

    for bone in armature.data.bones:
        if bone.length < 1e-4:
            issues.append(f"Bone length too small: {bone.name}")

    return issues
