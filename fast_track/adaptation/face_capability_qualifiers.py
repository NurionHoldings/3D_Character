"""FACE / Eye / Expression / Jaw / TALKING capability qualifiers for ADAPT-05."""

from __future__ import annotations

from typing import Any

CAPABILITY_STATES = (
    "AVAILABLE",
    "AVAILABLE_VIA_ADAPTER",
    "LIMITED",
    "MISSING",
    "AMBIGUOUS",
    "INVALID",
)


def _matrix_state(matrix: dict[str, Any] | None, key: str, default: str = "AVAILABLE") -> str:
    if not matrix:
        return default
    entry = matrix.get(key)
    if isinstance(entry, dict):
        return str(entry.get("status") or entry.get("state") or default)
    if isinstance(entry, str):
        return entry
    return default


def qualify_face_semantics(
    adapt03: dict[str, Any],
    adapt04: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    caps = (adapt04.get("adapt05Handoff") or {}).get("capabilityMatrices") or {}
    face_caps = caps.get("expression") or adapt03.get("expressionCapabilities") or {}

    required = ["blink", "brow", "smile"]
    classified: dict[str, str] = {}
    for sem in required:
        state = _matrix_state(face_caps, sem, "AVAILABLE")
        if force_flags.get("missingRequiredExpression") and sem in ("smile", "brow"):
            state = "MISSING"
        if force_flags.get("invalidExpressionTarget") and sem == "smile":
            state = "INVALID"
        classified[sem] = state
        if state in ("MISSING", "AMBIGUOUS", "INVALID"):
            blockers.append({"code": f"FACE_{state}", "semantic": sem})

    if force_flags.get("nameOnlyPresence"):
        blockers.append({"code": "NAME_ONLY_PRESENCE", "message": "name present but invalid target behavior"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {"capabilities": classified},
        "inheritedAuthority": "FACE Product Lock + ADAPT-03/04 handoff evidence",
        "inference": "NONE — observe final candidate/handoff only",
        "decision": status,
        "blockers": blockers,
    }


def qualify_eyes(
    adapt03: dict[str, Any],
    adapt04: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    caps = (adapt04.get("adapt05Handoff") or {}).get("capabilityMatrices") or {}
    eye = caps.get("eye") or adapt03.get("eyeCapabilities") or {}

    if force_flags.get("leftRightEyeInversion"):
        blockers.append({"code": "LEFT_RIGHT_EYE_INVERSION", "message": "L/R eye inverted"})
    if force_flags.get("missingBlink"):
        blockers.append({"code": "MISSING_BLINK", "message": "blink capability missing"})
    if force_flags.get("eyeAmbiguity"):
        blockers.append({"code": "EYE_LATERALITY_AMBIGUOUS", "message": "unsafe L/R eye state"})

    blink = _matrix_state(eye, "blink", "AVAILABLE")
    if blink in ("MISSING", "AMBIGUOUS", "INVALID") and not force_flags.get("missingBlink"):
        blockers.append({"code": f"BLINK_{blink}", "message": "blink not qualified"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {
            "leftRightIdentity": "PRESERVED" if not force_flags.get("leftRightEyeInversion") else "INVERTED",
            "blink": blink,
            "eyeCalibration": "PRESERVE",
        },
        "inheritedAuthority": "Eye Calibration (PRESERVE)",
        "inference": "NONE",
        "decision": status,
        "blockers": blockers,
    }


def qualify_expression(
    adapt03: dict[str, Any],
    adapt04: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Expression overlaps face semantics; keep dedicated report section
    face = qualify_face_semantics(adapt03, adapt04, force_flags=force_flags)
    return {
        **face,
        "section": "expressionQualification",
        "requiredSemantics": ["blink", "brow", "smile", "frown", "cheek", "mouth-expression"],
    }


def qualify_jaw_mouth(
    adapt03: dict[str, Any],
    adapt04: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    caps = (adapt04.get("adapt05Handoff") or {}).get("capabilityMatrices") or {}
    jaw = caps.get("jawMouth") or caps.get("talking") or {}

    if force_flags.get("missingJawMouth"):
        blockers.append({"code": "MISSING_JAW_MOUTH", "message": "required jaw/mouth capability missing"})
    if force_flags.get("invalidBodyMouthOwnership"):
        blockers.append({"code": "INVALID_BODY_MOUTH_OWNERSHIP", "message": "mouth owned by BODY"})

    open_state = _matrix_state(jaw, "jawOpen", "AVAILABLE")
    if open_state in ("MISSING", "INVALID") and not force_flags.get("missingJawMouth"):
        blockers.append({"code": f"JAW_{open_state}", "message": "jaw/open not representable"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {"jawOpen": open_state, "mouthOpen": _matrix_state(jaw, "mouthOpen", "AVAILABLE")},
        "inheritedAuthority": "FACE mouth/jaw semantics",
        "inference": "NONE",
        "decision": status,
        "blockers": blockers,
    }


def qualify_talking(
    adapt03: dict[str, Any],
    adapt04: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    caps = (adapt04.get("adapt05Handoff") or {}).get("capabilityMatrices") or {}
    talking = caps.get("talking") or adapt03.get("talkingCapabilities") or {}

    classification = "TALKING_COMPATIBLE"
    if force_flags.get("talkingIncompatible"):
        classification = "TALKING_BLOCKED"
        blockers.append({"code": "TALKING_INCOMPATIBLE", "message": "locked TALKING not representable"})
    elif force_flags.get("talkingLimited"):
        classification = "TALKING_LIMITED"
    elif force_flags.get("talkingViaAdapter"):
        classification = "TALKING_COMPATIBLE_WITH_ADAPTER"

    for key in ("mouthOpen", "mouthWiden", "mouthPucker", "plosive"):
        st = _matrix_state(talking, key, "AVAILABLE")
        if st in ("MISSING", "INVALID") and classification == "TALKING_COMPATIBLE":
            # soft: treat as adapter-compatible unless forced blocked
            classification = "TALKING_COMPATIBLE_WITH_ADAPTER"

    if classification == "TALKING_BLOCKED":
        blockers.append({"code": "TALKING_BLOCKED", "message": "required TALKING capability blocked"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "talkingClassification": classification,
        "observed": {"matrixKeys": list(talking.keys()) if isinstance(talking, dict) else []},
        "inheritedAuthority": "locked TALKING authority",
        "inference": "NONE — do not create missing visemes",
        "decision": status,
        "blockers": blockers,
    }
