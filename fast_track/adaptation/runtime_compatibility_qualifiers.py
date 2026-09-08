"""Motion / co-play / runtime state / behavior / product release qualifiers for ADAPT-05."""

from __future__ import annotations

from typing import Any

CANONICAL_MOTIONS = ("Idle", "Bow", "LargeBow", "Handshake", "Dance")
ENTRANCE_STATES = (
    "BOOTSTRAP",
    "PRELOAD",
    "ENTRANCE_READY",
    "ENTRANCE_PLAYING",
    "RUNTIME_HANDOFF",
    "LIVE_IDLE",
    "RECOVERY",
    "BLOCKED",
)
BEHAVIOR_MAP = {
    "IDLE": "Idle",
    "GREETING": "Bow",
    "FORMAL_GREETING": "LargeBow",
    "HANDSHAKE": "Handshake",
    "CELEBRATION": "Dance",
}
COPLAY_COMBOS = (
    "Idle+FACE",
    "Idle+TALKING",
    "Bow+FACE",
    "Handshake+FACE",
    "Dance+FACE",
)


def qualify_motion_compatibility(*, force_flags: dict[str, Any] | None = None) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    if force_flags.get("canonicalMotionIncompatible"):
        blockers.append({"code": "CANONICAL_MOTION_INCOMPATIBLE", "message": "BODY/runtime incompatible with motion set"})
    if force_flags.get("rewriteMotions"):
        blockers.append({"code": "MOTION_REWRITE_ATTEMPT", "message": "ADAPT-05 must not rewrite motions"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {"requiredMotions": list(CANONICAL_MOTIONS), "compatibility": "COMPATIBLE" if not blockers else "INCOMPATIBLE"},
        "inheritedAuthority": "PRODUCT-02 Motion Library",
        "inference": "compatibility only — no retarget/fix",
        "decision": status,
        "blockers": blockers,
    }


def qualify_face_body_coplay(
    face_ok: bool,
    body_ok: bool,
    talking_ok: bool,
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    if force_flags.get("faceBodyCoplayFailure"):
        blockers.append({"code": "FACE_BODY_COPLAY_FAILURE", "message": "ownership/boundary violation under co-play"})
    if not face_ok or not body_ok:
        blockers.append({"code": "COPLAY_PREREQUISITE_FAILED", "message": "FACE or BODY qualification failed"})

    results = {combo: ("PASS" if not blockers else "BLOCKED") for combo in COPLAY_COMBOS}
    if not talking_ok and "Idle+TALKING" in results:
        results["Idle+TALKING"] = "BLOCKED"
        blockers.append({"code": "TALKING_COPLAY_BLOCKED", "message": "Idle+TALKING blocked"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {"combinations": results},
        "inheritedAuthority": "PRODUCT-03 FACE/BODY runtime",
        "inference": "compatibility only",
        "decision": status,
        "blockers": blockers,
    }


def qualify_runtime_state(*, force_flags: dict[str, Any] | None = None) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    if force_flags.get("runtimeStateIncompatible"):
        blockers.append({"code": "RUNTIME_STATE_INCOMPATIBLE", "message": "entrance state incompatible"})
    if force_flags.get("redefineStateTransitions"):
        blockers.append({"code": "STATE_REDEFINITION_DENIED", "message": "ADAPT-05 must not redefine transitions"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {
            "states": list(ENTRANCE_STATES),
            "liveIdleAuthority": "PRODUCT-03",
            "compatibility": "COMPATIBLE" if not blockers else "INCOMPATIBLE",
        },
        "inheritedAuthority": "PRODUCT-04 Character Entrance State",
        "inference": "NONE",
        "decision": status,
        "blockers": blockers,
    }


def qualify_behavior_runtime(*, force_flags: dict[str, Any] | None = None) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    if force_flags.get("behaviorMappingIncompatible"):
        blockers.append({"code": "BEHAVIOR_MAPPING_INCOMPATIBLE", "message": "semantic behavior mapping failed"})
    if force_flags.get("directCrossMotionJump"):
        blockers.append({"code": "DIRECT_CROSS_MOTION_JUMP", "message": "direct cross-motion = DENY"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {"behaviorMap": dict(BEHAVIOR_MAP), "directCrossMotion": "DENY"},
        "inheritedAuthority": "PRODUCT-05 Interaction & Behavior Runtime",
        "inference": "NONE",
        "decision": status,
        "blockers": blockers,
    }


def qualify_product_release(*, force_flags: dict[str, Any] | None = None) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    if force_flags.get("productReleaseIncompatible"):
        blockers.append({"code": "PRODUCT_RELEASE_INCOMPATIBLE", "message": "cannot package without modifying NURION V1"})
    if force_flags.get("modifyNurionV1"):
        blockers.append({"code": "NURION_V1_MODIFY_DENIED", "message": "NURION V1 MODIFY = DENY"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {
            "nurionV1Copy": "ALLOW",
            "nurionV1Modify": "DENY",
            "candidateArtifactsOutsideCanonicalV1": True,
        },
        "inheritedAuthority": "PRODUCT-06 + Character Product Release V1",
        "inference": "NONE",
        "decision": status,
        "blockers": blockers,
    }
