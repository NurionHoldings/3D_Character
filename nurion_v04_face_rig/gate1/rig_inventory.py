"""Armature / face-bone inventory (read-only)."""

from __future__ import annotations

from typing import Dict, List

from .parameters import GATE1_PARAMETERS


def _hit(name: str, hints: List[str]) -> bool:
    n = name.lower().replace(" ", "").replace("_", "").replace("-", "").replace(".", "")
    for h in hints:
        hh = h.lower().replace(" ", "").replace("_", "").replace("-", "")
        if hh and hh in n:
            return True
    return False


def invent_face_rig() -> Dict:
    import bpy

    hints = GATE1_PARAMETERS["boneNameHints"]
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    inventory = {
        "armatureCount": len(arms),
        "armatures": [],
        "bones": {
            "head": [],
            "jaw": [],
            "lip": [],
            "cheek": [],
            "brow": [],
            "eye": [],
            "tongue": [],
            "teeth": [],
            "otherFaceLike": [],
        },
        "existingFaceBones": False,
        "jawLipCheekBrow": {
            "jaw": False,
            "lip": False,
            "cheek": False,
            "brow": False,
        },
        "existingRigClass": "NONE",
        "status": "CLASSIFIED",
    }

    all_bone_names: List[str] = []
    for arm in arms:
        bones = list(arm.data.bones)
        entry = {"name": arm.name, "boneCount": len(bones), "posePosition": getattr(arm.data, "pose_position", None)}
        inventory["armatures"].append(entry)
        for b in bones:
            all_bone_names.append(b.name)
            placed = False
            for cat in ("head", "jaw", "lip", "cheek", "brow", "eye", "tongue", "teeth"):
                if _hit(b.name, hints.get(cat, [])):
                    inventory["bones"][cat].append({"armature": arm.name, "bone": b.name})
                    placed = True
            if not placed and _hit(b.name, ["face", "facial", "viseme", "mouth"]):
                inventory["bones"]["otherFaceLike"].append({"armature": arm.name, "bone": b.name})

    j = bool(inventory["bones"]["jaw"])
    l = bool(inventory["bones"]["lip"])
    c = bool(inventory["bones"]["cheek"])
    br = bool(inventory["bones"]["brow"])
    inventory["jawLipCheekBrow"] = {"jaw": j, "lip": l, "cheek": c, "brow": br}
    inventory["existingFaceBones"] = any([j, l, c, br, bool(inventory["bones"]["eye"]), bool(inventory["bones"]["otherFaceLike"])])

    face_ctrl_count = sum(len(inventory["bones"][k]) for k in ("jaw", "lip", "cheek", "brow", "eye", "otherFaceLike"))
    if face_ctrl_count >= 4 and (j or l):
        inventory["existingRigClass"] = "RICH_FACE_RIG"
    elif face_ctrl_count >= 1:
        inventory["existingRigClass"] = "PARTIAL_FACE_RIG"
    elif inventory["bones"]["head"]:
        inventory["existingRigClass"] = "HEAD_ONLY"
    else:
        inventory["existingRigClass"] = "NONE"

    inventory["allBoneNamesSample"] = all_bone_names[:80]
    inventory["boneNameCount"] = len(all_bone_names)
    return inventory
