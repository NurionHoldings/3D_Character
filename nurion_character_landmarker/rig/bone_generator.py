"""Generate a standard armature from landmark coordinates."""

from __future__ import annotations

from typing import Dict, List, Tuple

import bpy
from mathutils import Vector

from ..core.landmark_engine import LandmarkPoint

BoneDef = Tuple[str, str, str]  # bone_name, head_key, tail_key

STANDARD_BONES: List[BoneDef] = [
    ("spine", "pelvis", "chest"),
    ("neck", "chest", "neck"),
    ("head", "neck", "head"),
    ("upper_arm.L", "shoulder.L", "elbow.L"),
    ("forearm.L", "elbow.L", "wrist.L"),
    ("upper_arm.R", "shoulder.R", "elbow.R"),
    ("forearm.R", "elbow.R", "wrist.R"),
    ("thigh.L", "hip.L", "knee.L"),
    ("shin.L", "knee.L", "ankle.L"),
    ("thigh.R", "hip.R", "knee.R"),
    ("shin.R", "knee.R", "ankle.R"),
]


def generate_standard_rig(
    landmarks: Dict[str, LandmarkPoint],
    armature_name: str = "NURION_Standard_Rig",
) -> bpy.types.Object:
    arm_data = bpy.data.armatures.new(armature_name)
    arm_obj = bpy.data.objects.new(armature_name, arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = arm_data.edit_bones
    created = []

    for bone_name, head_key, tail_key in STANDARD_BONES:
        if head_key not in landmarks or tail_key not in landmarks:
            continue
        bone = edit_bones.new(bone_name)
        bone.head = Vector(landmarks[head_key].position)
        bone.tail = Vector(landmarks[tail_key].position)
        if (bone.tail - bone.head).length < 1e-4:
            bone.tail = bone.head + Vector((0.0, 0.0, 0.05))
        created.append(bone_name)

    # Simple parenting for a usable hierarchy.
    parents = {
        "neck": "spine",
        "head": "neck",
        "upper_arm.L": "spine",
        "forearm.L": "upper_arm.L",
        "upper_arm.R": "spine",
        "forearm.R": "upper_arm.R",
        "thigh.L": "spine",
        "shin.L": "thigh.L",
        "thigh.R": "spine",
        "shin.R": "thigh.R",
    }
    for child, parent in parents.items():
        if child in edit_bones and parent in edit_bones:
            edit_bones[child].parent = edit_bones[parent]
            edit_bones[child].use_connect = False

    bpy.ops.object.mode_set(mode="OBJECT")
    arm_obj["nurion_bones_created"] = ",".join(created)
    return arm_obj
