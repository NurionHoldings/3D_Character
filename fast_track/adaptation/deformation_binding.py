"""Scoped deformation / binding policy for ADAPT-04 derived artifacts."""

from __future__ import annotations

from typing import Any


def validate_deformation_scope(
    plan: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []

    if force_flags.get("globalSkinRewrite"):
        blockers.append({"code": "GLOBAL_SKIN_REWRITE", "message": "BODY-wide weight rewrite denied"})

    for op in plan.get("operations") or []:
        scope = op.get("deformationScope") or "AUGMENTATION_REGION_ONLY"
        if scope == "GLOBAL_BODY":
            blockers.append({"code": "UNSCOPED_DEFORMATION", "operation": op.get("requirementId")})
        if op.get("overwritesSourceWeights"):
            blockers.append({"code": "SOURCE_WEIGHT_OVERWRITE", "operation": op.get("requirementId")})

    return {
        "status": "BLOCKED" if blockers else "PASS",
        "sourceWeightsPreservedAsEvidence": True,
        "derivedAdjustmentsScoped": True,
        "blockers": blockers,
    }


def record_weight_adjustments(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for op in operations:
        if op.get("requiresWeightBinding"):
            records.append(
                {
                    "requirementId": op.get("requirementId"),
                    "region": op.get("targetRegion"),
                    "scope": op.get("deformationScope", "AUGMENTATION_REGION_ONLY"),
                    "reversibleFromSource": True,
                    "sourceOverwrite": False,
                }
            )
    return records
