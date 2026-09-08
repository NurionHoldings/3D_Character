"""Expression auxiliary augmentation for ADAPT-04."""

from __future__ import annotations

from typing import Any


def plan_expression_operation(req: dict[str, Any]) -> dict[str, Any]:
    cap = req.get("capability") or ""
    return {
        "requirementId": req.get("requirementId"),
        "capability": cap,
        "reason": req.get("reason"),
        "targetRegion": req.get("targetRegion", "FACE"),
        "authority": req.get("authority", "NURION_FACE_SEMANTIC"),
        "authoritativeSemantic": cap,
        "augmentationType": "EXPRESSION_CONTROL",
        "parent": "FACE_Rig_Root",
        "attachment": "NURION_head → FACE_Rig_Root",
        "expectedOutput": f"AUX_EXPR_{cap.replace('FACE_', '')}",
        "geometryDependency": "FACIAL_REGION",
        "deformationDependency": cap,
        "confidence": 0.75,
        "safetyConstraints": ["LOCKED_EXPRESSION_SEMANTICS", "NO_ARBITRARY_EXPRESSION"],
        "requiresWeightBinding": False,
        "deformationScope": "AUGMENTATION_REGION_ONLY",
        "mutatesBodyHierarchy": False,
        "createsCompetingFaceRoot": False,
        "overwritesSourceWeights": False,
        "status": "PLANNED",
    }


def apply_expression_structures(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for op in operations:
        if op.get("status") != "PLANNED" or op.get("augmentationType") != "EXPRESSION_CONTROL":
            continue
        applied.append(
            {
                "controlName": op["expectedOutput"],
                "semantic": op["capability"],
                "type": "EXPRESSION_CONTROL",
                "status": "APPLIED",
            }
        )
    return applied
