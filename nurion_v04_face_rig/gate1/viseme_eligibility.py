"""Viseme eligibility and Lip Sync path selection (diagnosis only)."""

from __future__ import annotations

from typing import Dict, List

from .parameters import GATE1_PARAMETERS


def _key_hits(keys: List[dict], hints: List[str]) -> List[str]:
    out = []
    for k in keys:
        n = k.get("name", "").lower().replace(" ", "").replace("_", "")
        for h in hints:
            hh = h.lower().replace(" ", "").replace("_", "")
            if hh and hh in n:
                out.append(k["name"])
                break
    return out


def evaluate_viseme_eligibility(
    *,
    rig: Dict,
    shape_keys: Dict,
    mouth: Dict,
    oral: Dict,
    topology: Dict,
    weights: Dict,
) -> Dict:
    hints = GATE1_PARAMETERS["shapeKeyHints"]
    keys = shape_keys.get("keys") or []
    viseme_keys = _key_hits(keys, hints.get("viseme", []))
    jaw_keys = _key_hits(keys, hints.get("jaw", []))

    jaw_bones = bool(rig.get("jawLipCheekBrow", {}).get("jaw"))
    lip_bones = bool(rig.get("jawLipCheekBrow", {}).get("lip"))
    rich = rig.get("existingRigClass") == "RICH_FACE_RIG"
    partial = rig.get("existingRigClass") == "PARTIAL_FACE_RIG"
    mouth_ok = mouth.get("mouthBoundary") == "RESOLVED"
    density = mouth.get("openMouthDeformDensity")
    density_ok = density in ("HIGH", "MEDIUM")
    head_ok = weights.get("headParent") == "RESOLVED"
    face_ok = topology.get("faceRegion") == "RESOLVED"

    # Path selection priority
    if (rich or (jaw_bones and lip_bones) or (len(viseme_keys) >= 4) or (len(jaw_keys) >= 1 and lip_bones)) and mouth_ok and head_ok:
        path = "NATIVE_FACE_RIG"
        level = "HIGH"
        rationale = "Existing face bones and/or viseme/jaw shape keys support native driving."
    elif mouth_ok and density_ok and head_ok and face_ok:
        path = "PROCEDURAL_FACE_RIG"
        level = "MEDIUM" if density == "MEDIUM" else "HIGH"
        rationale = "Mouth boundary and deform density allow NURION procedural jaw/lip/brow candidates."
    elif mouth_ok and head_ok:
        path = "LIMITED_2D_VISEME"
        level = "LOW"
        rationale = "Geometry limited; restrict to coarse mouth shapes only."
    else:
        path = "LIMITED_2D_VISEME"
        level = "INELIGIBLE_OR_LOW"
        rationale = "Mouth/head unresolved; only limited 2D viseme fallback if later repaired."

    korean_viseme = {
        "level": level,
        "supportsVowels": path != "LIMITED_2D_VISEME" or density_ok,
        "supportsConsonantClosures": path == "NATIVE_FACE_RIG" or (path == "PROCEDURAL_FACE_RIG" and density == "HIGH"),
        "notes": [
            "Korean vowel set (ㅏㅓㅗㅜㅡㅣㅐㅔ) needs jaw+lip roundness.",
            "Batchim closures benefit from upper/lower lip contact proxies.",
        ],
    }

    return {
        "visemePath": path,
        "visemePathSelected": True,
        "koreanVisemeImplementability": korean_viseme,
        "evidence": {
            "existingRigClass": rig.get("existingRigClass"),
            "visemeShapeKeys": viseme_keys,
            "jawShapeKeys": jaw_keys,
            "shapeKeyCount": shape_keys.get("count", 0),
            "mouthBoundary": mouth.get("mouthBoundary"),
            "openMouthDeformDensity": density,
            "teethClass": (oral.get("teeth") or {}).get("class"),
            "tongueClass": (oral.get("tongue") or {}).get("class"),
            "headParent": weights.get("headParent"),
        },
        "rationale": rationale,
        "status": "SELECTED",
    }
