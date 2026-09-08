"""Jaw / Mouth auxiliary augmentation for ADAPT-04."""

from __future__ import annotations

from typing import Any


def plan_jaw_mouth_operation(req: dict[str, Any]) -> dict[str, Any]:
    cap = req.get("capability") or ""
    if "mouthOpen" in cap or "jaw" in cap.lower():
        aug_type = "JAW_HELPER"
    elif any(x in cap for x in ("Widen", "Pucker", "Plosive", "dental", "lips")):
        aug_type = "MOUTH_HELPER"
    else:
        aug_type = "MOUTH_HELPER"
    return {
        "requirementId": req.get("requirementId"),
        "capability": cap,
        "reason": req.get("reason"),
        "targetRegion": req.get("targetRegion", "MOUTH"),
        "authority": req.get("authority", "NURION_TALKING"),
        "authoritativeSemantic": cap,
        "augmentationType": aug_type,
        "parent": "FACE_Rig_Root",
        "attachment": "NURION_head → FACE_Rig_Root",
        "expectedOutput": f"AUX_{aug_type}_{cap.replace('FACE_', '')}",
        "geometryDependency": "MOUTH_JAW_REGION",
        "deformationDependency": cap,
        "confidence": 0.8,
        "safetyConstraints": ["NO_BODY_OWNERSHIP", "LOCKED_TALKING_SEMANTICS"],
        "requiresWeightBinding": False,
        "deformationScope": "AUGMENTATION_REGION_ONLY",
        "mutatesBodyHierarchy": False,
        "createsCompetingFaceRoot": False,
        "overwritesSourceWeights": False,
        "status": "PLANNED",
    }


def apply_jaw_mouth_structures(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for op in operations:
        if op.get("status") != "PLANNED":
            continue
        if op.get("augmentationType") not in ("JAW_HELPER", "MOUTH_HELPER"):
            continue
        applied.append(
            {
                "nodeName": op["expectedOutput"],
                "semantic": op["capability"],
                "type": op["augmentationType"],
                "parent": op["parent"],
                "status": "APPLIED",
            }
        )
    return applied
