"""Eye auxiliary augmentation for ADAPT-04."""

from __future__ import annotations

from typing import Any


def plan_eye_operation(req: dict[str, Any], *, force_ambiguity: bool = False) -> dict[str, Any]:
    cap = req.get("capability") or ""
    side = "LEFT" if "Left" in cap else "RIGHT"
    aug_type = "EYELID_CONTROL" if "Blink" in cap else "EYE_HELPER"
    if force_ambiguity:
        return {
            "requirementId": req.get("requirementId"),
            "capability": cap,
            "augmentationType": aug_type,
            "status": "BLOCKED",
            "reason": "LEFT_RIGHT_EYE_AMBIGUITY",
            "laterality": "AMBIGUOUS",
        }
    return {
        "requirementId": req.get("requirementId"),
        "capability": cap,
        "reason": req.get("reason"),
        "targetRegion": req.get("targetRegion"),
        "authority": req.get("authority", "NURION_EYE_CALIBRATION"),
        "authoritativeSemantic": cap,
        "augmentationType": aug_type,
        "parent": "FACE_Rig_Root",
        "attachment": "NURION_head → FACE_Rig_Root",
        "expectedOutput": f"AUX_{side}_EYE_{aug_type}",
        "laterality": side,
        "geometryDependency": "EYE_REGION",
        "deformationDependency": cap,
        "confidence": 0.85,
        "safetyConstraints": ["PRESERVE_EYE_CALIBRATION", "NO_BODY_OWNERSHIP"],
        "requiresWeightBinding": aug_type == "EYELID_CONTROL",
        "deformationScope": "AUGMENTATION_REGION_ONLY",
        "mutatesBodyHierarchy": False,
        "createsCompetingFaceRoot": False,
        "overwritesSourceWeights": False,
        "status": "PLANNED",
    }


def apply_eye_structures(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for op in operations:
        if op.get("status") != "PLANNED":
            continue
        if op.get("augmentationType") not in ("EYE_HELPER", "EYELID_CONTROL"):
            continue
        applied.append(
            {
                "nodeName": op["expectedOutput"],
                "semantic": op["capability"],
                "type": op["augmentationType"],
                "parent": op["parent"],
                "laterality": op.get("laterality"),
                "status": "APPLIED",
            }
        )
    return applied


def eye_capability_matrix(applied: list[dict[str, Any]], requirements: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    applied_caps = {a["semantic"] for a in applied}
    for req in requirements:
        if req.get("authority") != "NURION_EYE_CALIBRATION" and "eye" not in (req.get("capability") or "").lower():
            continue
        cap = req.get("capability")
        rows.append(
            {
                "capability": cap,
                "status": "AUGMENTED" if cap in applied_caps else "MISSING",
            }
        )
    return {"rows": rows, "status": "PASS" if rows else "NOT_APPLICABLE"}
