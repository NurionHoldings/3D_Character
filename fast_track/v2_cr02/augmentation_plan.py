"""CR02-P02 — FACE Attachment / Augmentation Plan (no derived artifact; no weight apply)."""

from __future__ import annotations

from typing import Any

from fast_track.adaptation.inspector import canonical_sha256

PLAN_SCHEMA = "NURION_V2_CR02_FACE_AUGMENTATION_PLAN_V1"
PROVENANCE_SCHEMA = "NURION_V2_CR02_CAPABILITY_PROVENANCE_V1"

MINIMUM_EXPRESSIONS = ("EXPR_SMILE", "EXPR_BROW_UP", "EXPR_FROWN")

# Capability-driven policy (not Idle_15 special-case)
POLICY = {
    "AVAILABLE_NATIVE_CAPABILITY": "REUSE",
    "MISSING_CAPABILITY": "MINIMUM_AUXILIARY_AUGMENTATION",
    "UNSAFE_OR_INSUFFICIENT_TOPOLOGY": "MANUAL_REVIEW_REQUIRED_OR_BLOCKED",
    "ambiguousLaterality": "BLOCKED — no arbitrary L/R assignment",
    "jawEqualsTalking": "DENY",
}


def _decision(native_status: str) -> str:
    st = (native_status or "MISSING").upper()
    if st in ("PRESENT", "DETECTED", "AVAILABLE"):
        return "REUSE_NATIVE"
    if st in ("AMBIGUOUS",):
        return "MANUAL_REVIEW_REQUIRED"
    return "MINIMUM_AUXILIARY_AUGMENTATION"


def _cap_plan(
    *,
    capability: str,
    mechanism: str,
    target_region: str,
    helper_nodes: list[str],
    required_local_skin: str,
    expected_deformation: str,
    neutral: str,
    activation: str,
    restoration: str,
    runtime_driver: str,
    decision: str,
    status: str = "PLANNED",
    consumes: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    if decision == "REUSE_NATIVE":
        mechanism = "NATIVE_REUSE"
        helper_nodes = []
        required_local_skin = "NONE_PLANNED"
    if decision == "MANUAL_REVIEW_REQUIRED":
        status = "MANUAL_REVIEW_REQUIRED"
        mechanism = "UNDECIDED"
    if decision == "BLOCKED":
        status = "BLOCKED"
        mechanism = "DENIED"

    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "capability": capability,
        "mechanism": mechanism,
        "affectedRegion": target_region,
        "driver": runtime_driver,
        "weightAdjustment": required_local_skin,
        "beforeDigest": "PENDING_P03_PLUS",
        "augmentedDigest": "PENDING_P03_PLUS",
        "functionalTest": "PENDING_EXECUTION",
        "planOnly": True,
    }
    return {
        "capability": capability,
        "decision": decision,
        "status": status,
        "mechanism": mechanism,
        "targetRegion": target_region,
        "helperNodes": helper_nodes,
        "requiredLocalSkinInfluence": required_local_skin,
        "expectedDeformation": expected_deformation,
        "neutralState": neutral,
        "activationState": activation,
        "restorationState": restoration,
        "runtimeDriver": runtime_driver,
        "consumes": consumes or [],
        "notes": notes or [],
        "provenance": provenance,
        "executionAuthority": "DENIED_AT_P02 — apply only under P03/P04",
        "weightApplyAtP02": "DENY",
    }


def build_augmentation_plan(gap_report: dict[str, Any]) -> dict[str, Any]:
    """Deterministic plan from P01 gap inventory. Does not mutate assets or apply weights."""
    blockers: list[dict[str, Any]] = []
    inv = gap_report.get("capabilityInventory") or {}
    cr01 = gap_report.get("cr01Consume") or {}
    src = gap_report.get("sourceIdentity") or {}

    head = cr01.get("NURION_head")
    if not head:
        blockers.append({"code": "NURION_HEAD_UNRESOLVED"})
    if not cr01.get("digestMatch"):
        blockers.append({"code": "CR01_DIGEST_MISMATCH"})

    # --- Laterality from inventory (fail-closed if ambiguous) ---
    eye_block = inv.get("Eye") or {}
    eye_l_native = eye_block.get("left") or "MISSING"
    eye_r_native = eye_block.get("right") or "MISSING"
    if eye_l_native == "AMBIGUOUS" or eye_r_native == "AMBIGUOUS":
        blockers.append({"code": "EYE_LATERALITY_AMBIGUOUS"})
        eye_l_decision = eye_r_decision = "BLOCKED"
    else:
        eye_l_decision = _decision(eye_l_native)
        eye_r_decision = _decision(eye_r_native)

    blink_native = (inv.get("Blink") or {}).get("status") or "MISSING"
    # Blink inherits eye laterality gate — if eyes ambiguous, blink blocked
    if any(b.get("code") == "EYE_LATERALITY_AMBIGUOUS" for b in blockers):
        blink_l_decision = blink_r_decision = "BLOCKED"
    else:
        # No native blink asymmetry signal on Idle_15 — treat as MISSING both sides independently
        blink_l_decision = _decision(blink_native)
        blink_r_decision = _decision(blink_native)

    jaw_native = (inv.get("Jaw_Mouth") or {}).get("status") or "MISSING"
    expr_native = (inv.get("Expression") or {}).get("status") or "MISSING"
    talk_native = (inv.get("TALKING") or {}).get("status") or "MISSING"
    blend_count = ((inv.get("blendshapes") or {}).get("count")) or 0

    attachment = {
        "resolvedHeadSourceBone": head,
        "FACE_Rig_Root": "FACE_Rig_Root",
        "interface": "NURION_head → FACE_Rig_Root",
        "attachmentTransform": {
            "mode": "IDENTITY_LOCAL_UNDER_HEAD",
            "translation": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0, 1.0],
            "scale": [1.0, 1.0, 1.0],
            "note": "Plan only — transform applied when P03 creates derived artifact",
        },
        "attachmentEvidence": {
            "headResolvedBy": "V2-CR-01 CONSUME",
            "cr01SemanticAdapterDigest": cr01.get("semanticAdapterDigest"),
            "sourceBoneName": head,
            "soleAttachment": True,
            "competingFaceRoot": "DENY",
        },
        "status": "PLANNED" if head else "BLOCKED",
        "executionAuthority": "DENIED_AT_P02",
    }

    capabilities: dict[str, Any] = {}

    capabilities["Eye_L"] = _cap_plan(
        capability="Eye_L",
        mechanism="AUXILIARY_RIG",
        target_region="LEFT_EYE",
        helper_nodes=["AUX_LEFT_EYE_HELPER"],
        required_local_skin="LOCAL_ONLY_PLANNED",
        expected_deformation="independent left eye aim/rotation observable",
        neutral="EYE_L_NEUTRAL",
        activation="EYE_L_LOOK_OFFSET",
        restoration="EYE_L_NEUTRAL",
        runtime_driver="NURION_EYE_L_CHANNEL",
        decision=eye_l_decision,
        notes=["Eye_L ≠ Eye_R — independent capability"],
    )
    capabilities["Eye_R"] = _cap_plan(
        capability="Eye_R",
        mechanism="AUXILIARY_RIG",
        target_region="RIGHT_EYE",
        helper_nodes=["AUX_RIGHT_EYE_HELPER"],
        required_local_skin="LOCAL_ONLY_PLANNED",
        expected_deformation="independent right eye aim/rotation observable",
        neutral="EYE_R_NEUTRAL",
        activation="EYE_R_LOOK_OFFSET",
        restoration="EYE_R_NEUTRAL",
        runtime_driver="NURION_EYE_R_CHANNEL",
        decision=eye_r_decision,
        notes=["Eye_R ≠ Eye_L — independent capability"],
    )
    capabilities["Blink_L"] = _cap_plan(
        capability="Blink_L",
        mechanism="AUXILIARY_RIG",
        target_region="LEFT_EYELID",
        helper_nodes=["AUX_LEFT_EYELID_CONTROL"],
        required_local_skin="LOCAL_ONLY_PLANNED",
        expected_deformation="left eyelid/eye-region close deformation observable",
        neutral="BLINK_L_OPEN",
        activation="BLINK_L_CLOSED",
        restoration="BLINK_L_OPEN",
        runtime_driver="NURION_BLINK_L_CHANNEL",
        decision=blink_l_decision,
        notes=["Blink_L ≠ Blink_R", "requires N→A→N functional proof at P03"],
    )
    capabilities["Blink_R"] = _cap_plan(
        capability="Blink_R",
        mechanism="AUXILIARY_RIG",
        target_region="RIGHT_EYELID",
        helper_nodes=["AUX_RIGHT_EYELID_CONTROL"],
        required_local_skin="LOCAL_ONLY_PLANNED",
        expected_deformation="right eyelid/eye-region close deformation observable",
        neutral="BLINK_R_OPEN",
        activation="BLINK_R_CLOSED",
        restoration="BLINK_R_OPEN",
        runtime_driver="NURION_BLINK_R_CHANNEL",
        decision=blink_r_decision,
        notes=["Blink_R ≠ Blink_L", "requires N→A→N functional proof at P03"],
    )
    capabilities["Jaw_Mouth"] = _cap_plan(
        capability="Jaw_Mouth",
        mechanism="AUXILIARY_RIG",
        target_region="JAW_MOUTH",
        helper_nodes=["AUX_JAW", "AUX_MOUTH_OPEN"],
        required_local_skin="LOCAL_ONLY_PLANNED",
        expected_deformation="jaw/open-close mouth deformation observable",
        neutral="JAW_CLOSED",
        activation="JAW_OPEN",
        restoration="JAW_CLOSED",
        runtime_driver="NURION_JAW_OPEN_CHANNEL",
        decision=_decision(jaw_native),
        notes=["physical deformation capability only — does NOT equal TALKING"],
    )
    capabilities["Expression"] = _cap_plan(
        capability="Expression",
        mechanism="AUXILIARY_RIG" if blend_count == 0 else "NATIVE_REUSE",
        target_region="FACE_EXPRESSION",
        helper_nodes=[f"AUX_{e}" for e in MINIMUM_EXPRESSIONS] if blend_count == 0 else [],
        required_local_skin="LOCAL_ONLY_PLANNED" if blend_count == 0 else "NONE_PLANNED",
        expected_deformation="distinct deformation per minimum expression set",
        neutral="EXPR_NEUTRAL",
        activation="EXPR_SET_ACTIVE",
        restoration="EXPR_NEUTRAL",
        runtime_driver="NURION_EXPRESSION_SET",
        decision=_decision(expr_native if blend_count == 0 else "PRESENT"),
        notes=[
            f"minimumExpressionSet={list(MINIMUM_EXPRESSIONS)}",
            f"blendshapeCount={blend_count}",
            "if native morphs sufficient → REUSE; else minimum auxiliary",
        ],
    )
    # TALKING is separate: may consume Jaw_Mouth, never identical
    talk_decision = _decision(talk_native)
    capabilities["TALKING"] = _cap_plan(
        capability="TALKING",
        mechanism="TIMED_VISEME_CONTROLLER",
        target_region="MOUTH_VISEME",
        helper_nodes=["AUX_TALKING_CONTROLLER", "AUX_VISEME_SEQ"],
        required_local_skin="LOCAL_ONLY_PLANNED",
        expected_deformation="timed sequence of changing mouth states (not static open)",
        neutral="TALK_NEUTRAL",
        activation="TALK_VISEME_SEQUENCE",
        restoration="TALK_NEUTRAL",
        runtime_driver="NURION_TALKING_TIMELINE",
        decision=talk_decision,
        consumes=["Jaw_Mouth"],
        notes=[
            "TALKING ≠ Jaw_Mouth",
            "Jaw_Mouth open/close alone is NOT TALKING PASS",
            "static mouth-open pose = BLOCKED as talking proof",
            "execution under P04 authority",
        ],
    )

    for name, cap in capabilities.items():
        if cap.get("status") == "BLOCKED":
            blockers.append({"code": f"CAPABILITY_BLOCKED:{name}"})
        if cap.get("status") == "MANUAL_REVIEW_REQUIRED":
            blockers.append({"code": f"MANUAL_REVIEW:{name}"})

    safety = {
        "sourceMutation": "DENY",
        "bodyRerig": "DENY",
        "globalAutoWeight": "DENY",
        "localAdjustmentOnly": "ALLOW_IF_PROVEN",
        "topologyReconstruction": "DENY",
        "weightApplyAtP02": "DENY",
        "derivedArtifactAtP02": "DENY",
        "CR01_REOPEN": "DENY",
        "jawMouthEqualsTalking": "DENY",
        "arbitraryLateralityAssignment": "DENY",
    }

    plan_core = {
        "schema": PLAN_SCHEMA,
        "stage": "CR02-P02",
        "changeRequestId": "V2-CR-02",
        "revision": "R1",
        "input": {
            "sourceAssetSha256": src.get("sha256"),
            "cr01SemanticAdapterDigest": cr01.get("semanticAdapterDigest"),
            "gapInspectionDigest": gap_report.get("gapInspectionDigest"),
        },
        "policy": POLICY,
        "attachment": attachment,
        "capabilityPlan": capabilities,
        "safety": safety,
        "executionBoundary": {
            "P02": "PLAN_ONLY",
            "P03": "Eye_L / Eye_R / Blink_L / Blink_R derived artifact AUTHORIZED_AFTER_P02_PASS",
            "P04": "Jaw_Mouth / Expression / TALKING AUTHORIZED_AFTER_P03",
            "weightPaint": "NOT AT THIS STAGE",
        },
    }

    status = "BLOCKED" if blockers or attachment.get("status") == "BLOCKED" else "PASS"
    plan_core["blockers"] = blockers
    plan_core["status"] = status
    plan_core["v2Engine"] = "NOT OPEN"
    plan_core["engineV1"] = "CLOSED / PASS / CONSUME ONLY"
    plan_core["augmentationPlanDigest"] = canonical_sha256(
        {k: v for k, v in plan_core.items() if k != "augmentationPlanDigest"}
    )
    return plan_core
