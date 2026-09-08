"""ABSTAIN conditions for unsupported dimensions — Gate 1 contract."""

from __future__ import annotations

from typing import Dict, List, Optional

ABSTAIN_RULES = {
    "schema": "NURION_V06_GATE1_ABSTAIN_RULES",
    "version": "0.6.0-gate1",
    "policy": "UNSUPPORTED_DIMENSION_MUST_ABSTAIN",
    "notes": [
        "ABSTAIN is not a soft warning: operators must not force Apply Motion / Export as FULL.",
        "LIMITED may proceed only when body core is present and limitations are disclosed.",
        "INELIGIBLE forces full ABSTAIN of unified runtime application.",
    ],
    "rules": [
        {
            "id": "NO_ARMATURE",
            "severity": "INELIGIBLE",
            "when": "No ARMATURE object in imported package",
            "action": "ABSTAIN",
        },
        {
            "id": "NO_SKINNED_MESH",
            "severity": "INELIGIBLE",
            "when": "No mesh with armature deform modifiers / vertex groups",
            "action": "ABSTAIN",
        },
        {
            "id": "CORE_BONE_SET_MISSING",
            "severity": "INELIGIBLE",
            "when": "Hips/spine and bilateral arm/leg core cannot be resolved",
            "action": "ABSTAIN",
        },
        {
            "id": "ZERO_LENGTH_CRITICAL_BONES",
            "severity": "INELIGIBLE",
            "when": "Critical bones have zero rest length that blocks mapping",
            "action": "ABSTAIN",
        },
        {
            "id": "SIBLING_ANIMATION_ZIP_MIX",
            "severity": "INELIGIBLE",
            "when": "Package mixes unrelated sibling animation ZIPs into holdout/runtime input",
            "action": "ABSTAIN",
        },
        {
            "id": "SEALED_BASELINE_HASH_MISMATCH",
            "severity": "INELIGIBLE",
            "when": "v0.3 / v0.4 / v0.5 RC hash does not match locked baseline",
            "action": "ABSTAIN_AND_SEAL_DENY_STYLE_HALT",
        },
        {
            "id": "NO_MOTION_PRESET_ACTION",
            "severity": "INELIGIBLE",
            "when": "None of Formal Bow / Idle / Gentleman's Bow (or equivalent) is available",
            "action": "ABSTAIN",
        },
        {
            "id": "FACE_PATH_UNSUPPORTED",
            "severity": "LIMITED",
            "when": "Body OK but face rig / mouth boundary path unsupported",
            "action": "ABSTAIN_FACE_PATH_ONLY",
        },
        {
            "id": "EYE_PATH_UNSUPPORTED",
            "severity": "LIMITED",
            "when": "Body OK but eye evidence / v0.3 compat path unsupported",
            "action": "ABSTAIN_EYE_PATH_ONLY",
        },
        {
            "id": "LIPSYNC_TIMELINE_UNSUPPORTED",
            "severity": "LIMITED",
            "when": "Face mesh present but lipsync timeline bind unsupported",
            "action": "ABSTAIN_LIPSYNC_ONLY",
        },
        {
            "id": "NON_MESHY_OR_UNKNOWN_RIG_FAMILY",
            "severity": "LIMITED_OR_INELIGIBLE",
            "when": "Bone naming / axis family cannot be auto-mapped without manual mapping",
            "action": "ABSTAIN_IF_UNMAPPABLE_ELSE_LIMITED",
        },
        {
            "id": "MANUAL_MAPPING_REQUIRED",
            "severity": "INELIGIBLE",
            "when": "Only recoverable via manual bone mapping (v0.6 forbids manual mapping in limited path)",
            "action": "ABSTAIN",
        },
        {
            "id": "PRODUCTION_CLAIM",
            "severity": "POLICY",
            "when": "Any request to mark Production GO without separate readiness track",
            "action": "ABSTAIN_PRODUCTION_REMAINS_NO_GO",
        },
    ],
    "v05LimitationInheritance": {
        "autoClear": "DENY",
        "codes": [
            "FOOT_SLIDE_RESIDUAL_11",
            "SHALLOW_SUSTAINED_CONTACT_ACCEPTED",
            "GATE3_REVERSE_FOREARM_MILD_PRESERVED",
            "HOLDOUT_FOOT_SLIDE_9",
        ],
        "note": "Codes remain public on asset results even when a specific asset remeasures better.",
    },
}


def classify_abstain(
    *,
    has_armature: bool,
    has_skinned_mesh: bool,
    core_bones_ok: bool,
    zero_length_critical: bool,
    sibling_zip_mix: bool,
    baseline_hash_ok: bool,
    has_motion_preset: bool,
    face_path_ok: bool,
    eye_path_ok: bool,
    lipsync_ok: bool,
    auto_mappable: bool,
    manual_mapping_required: bool,
) -> Dict:
    """Pure classification helper used by later gates; Gate 1 freezes the rules."""
    triggered: List[str] = []
    abstain_actions: List[str] = []

    def hit(rule_id: str, action: str) -> None:
        triggered.append(rule_id)
        abstain_actions.append(action)

    if not baseline_hash_ok:
        hit("SEALED_BASELINE_HASH_MISMATCH", "ABSTAIN_AND_SEAL_DENY_STYLE_HALT")
    if sibling_zip_mix:
        hit("SIBLING_ANIMATION_ZIP_MIX", "ABSTAIN")
    if not has_armature:
        hit("NO_ARMATURE", "ABSTAIN")
    if not has_skinned_mesh:
        hit("NO_SKINNED_MESH", "ABSTAIN")
    if not core_bones_ok:
        hit("CORE_BONE_SET_MISSING", "ABSTAIN")
    if zero_length_critical:
        hit("ZERO_LENGTH_CRITICAL_BONES", "ABSTAIN")
    if not has_motion_preset:
        hit("NO_MOTION_PRESET_ACTION", "ABSTAIN")
    if manual_mapping_required or not auto_mappable:
        if manual_mapping_required:
            hit("MANUAL_MAPPING_REQUIRED", "ABSTAIN")
        else:
            hit("NON_MESHY_OR_UNKNOWN_RIG_FAMILY", "ABSTAIN_IF_UNMAPPABLE_ELSE_LIMITED")

    hard_ineligible = any(
        r
        in {
            "NO_ARMATURE",
            "NO_SKINNED_MESH",
            "CORE_BONE_SET_MISSING",
            "ZERO_LENGTH_CRITICAL_BONES",
            "SIBLING_ANIMATION_ZIP_MIX",
            "SEALED_BASELINE_HASH_MISMATCH",
            "NO_MOTION_PRESET_ACTION",
            "MANUAL_MAPPING_REQUIRED",
        }
        for r in triggered
    )

    if hard_ineligible:
        classification = "INELIGIBLE"
        runtime_action = "ABSTAIN"
    else:
        path_abstains: List[str] = []
        if not face_path_ok:
            hit("FACE_PATH_UNSUPPORTED", "ABSTAIN_FACE_PATH_ONLY")
            path_abstains.append("FACE")
        if not eye_path_ok:
            hit("EYE_PATH_UNSUPPORTED", "ABSTAIN_EYE_PATH_ONLY")
            path_abstains.append("EYE")
        if not lipsync_ok:
            hit("LIPSYNC_TIMELINE_UNSUPPORTED", "ABSTAIN_LIPSYNC_ONLY")
            path_abstains.append("LIPSYNC")
        classification = "FULL" if not path_abstains else "LIMITED"
        runtime_action = "APPLY_WITH_DISCLOSED_ABSTAINS" if path_abstains else "APPLY_FULL_LIMITED_DOMAIN"

    return {
        "classification": classification,
        "runtimeAction": runtime_action,
        "triggeredRules": triggered,
        "abstainActions": abstain_actions,
        "inheritedLimitationsFromV05MustRemain": True,
    }
