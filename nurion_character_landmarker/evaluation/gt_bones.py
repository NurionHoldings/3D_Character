"""Ground-truth bone readers — evaluation only."""

from __future__ import annotations

from typing import Dict, List, Optional

from mathutils import Vector

from ..core.leak_guard import note_gt_access


BONE_CANDIDATES = {
    "pelvis": ["Hips", "hips", "Pelvis", "pelvis", "Root", "mixamorig:Hips"],
    "spine": ["Spine", "spine", "mixamorig:Spine"],
    "chest": ["Spine02", "Spine01", "Spine2", "Spine1", "Chest"],
    "neck": ["Neck", "neck", "mixamorig:Neck"],
    "head": ["Head", "head", "mixamorig:Head"],
    "shoulder.L": ["LeftArm", "LeftShoulder", "mixamorig:LeftArm"],
    "elbow.L": ["LeftForeArm", "mixamorig:LeftForeArm"],
    "wrist.L": ["LeftHand", "mixamorig:LeftHand"],
    "shoulder.R": ["RightArm", "RightShoulder", "mixamorig:RightArm"],
    "elbow.R": ["RightForeArm", "mixamorig:RightForeArm"],
    "wrist.R": ["RightHand", "mixamorig:RightHand"],
    "hip.L": ["LeftUpLeg", "mixamorig:LeftUpLeg"],
    "knee.L": ["LeftLeg", "mixamorig:LeftLeg"],
    "ankle.L": ["LeftFoot", "mixamorig:LeftFoot"],
    "hip.R": ["RightUpLeg", "mixamorig:RightUpLeg"],
    "knee.R": ["RightLeg", "mixamorig:RightLeg"],
    "ankle.R": ["RightFoot", "mixamorig:RightFoot"],
}


def resolve_bone_name(arm, landmark: str) -> Optional[str]:
    note_gt_access(f"resolve_bone_name:{landmark}")
    names = {b.name for b in arm.data.bones}
    for candidate in BONE_CANDIDATES.get(landmark, []):
        if candidate in names:
            return candidate
    return None


def bone_world_head(arm, bone_name: str) -> Vector:
    note_gt_access(f"bone_world_head:{bone_name}")
    bone = arm.data.bones[bone_name]
    return arm.matrix_world @ bone.head_local


def collect_gt_landmarks(arm, landmark_names: List[str]) -> Dict[str, dict]:
    note_gt_access("collect_gt_landmarks")
    out: Dict[str, dict] = {}
    for name in landmark_names:
        bone = resolve_bone_name(arm, name)
        if bone is None:
            continue
        head = bone_world_head(arm, bone)
        out[name] = {
            "bone": bone,
            "position": [round(float(head.x), 6), round(float(head.y), 6), round(float(head.z), 6)],
        }
    return out
