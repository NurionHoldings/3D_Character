"""TALKING / Viseme auxiliary augmentation for ADAPT-04."""

from __future__ import annotations

from typing import Any


def plan_talking_operation(req: dict[str, Any]) -> dict[str, Any]:
    cap = req.get("capability") or ""
    if "mouthOpen" in cap:
        aug_type = "TALKING_CONTROL"
    elif any(x in cap for x in ("Plosive", "Pucker", "Widen", "dental", "lips")):
        aug_type = "VISEME_SUPPORT"
    else:
        aug_type = "TALKING_CONTROL"
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
        "expectedOutput": f"AUX_TALK_{cap.replace('FACE_', '')}",
        "geometryDependency": "MOUTH_SPEECH_REGION",
        "deformationDependency": cap,
        "confidence": 0.8,
        "safetyConstraints": ["LOCKED_TALKING_VOCABULARY", "NO_NEW_VISEME_SEMANTICS"],
        "requiresWeightBinding": False,
        "deformationScope": "AUGMENTATION_REGION_ONLY",
        "mutatesBodyHierarchy": False,
        "createsCompetingFaceRoot": False,
        "overwritesSourceWeights": False,
        "status": "PLANNED",
    }


def apply_talking_structures(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for op in operations:
        if op.get("status") != "PLANNED":
            continue
        if op.get("augmentationType") not in ("TALKING_CONTROL", "VISEME_SUPPORT"):
            continue
        applied.append(
            {
                "controlName": op["expectedOutput"],
                "semantic": op["capability"],
                "type": op["augmentationType"],
                "status": "APPLIED",
            }
        )
    return applied


def talking_capability_matrix(applied: list[dict[str, Any]], requirements: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    applied_caps = {a["semantic"] for a in applied}
    for req in requirements:
        if req.get("authority") != "NURION_TALKING":
            continue
        cap = req.get("capability")
        rows.append({"capability": cap, "status": "AUGMENTED" if cap in applied_caps else "MISSING"})
    return {"rows": rows, "status": "PASS" if rows else "NOT_APPLICABLE"}
