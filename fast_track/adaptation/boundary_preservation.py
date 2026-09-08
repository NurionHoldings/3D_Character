"""BODY / FACE boundary preservation validators for ADAPT-04."""

from __future__ import annotations

from typing import Any


def validate_body_preservation(
    adapt02: dict[str, Any],
    plan: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []

    if force_flags.get("bodyHierarchyMutation"):
        blockers.append({"code": "BODY_HIERARCHY_MUTATION", "message": "BODY hierarchy mutation denied"})
    if force_flags.get("rootPelvisCollision"):
        blockers.append({"code": "ROOT_PELVIS_COLLISION", "message": "root/pelvis semantic corruption"})
    elif adapt02.get("rootPelvisValidation", {}).get("status") != "PASS":
        blockers.append({"code": "ROOT_PELVIS_INVALID", "message": "ADAPT-02 root/pelvis not PASS"})

    for op in plan.get("operations") or []:
        if op.get("mutatesBodyHierarchy"):
            blockers.append({"code": "UNAUTHORIZED_BODY_MUTATION", "operation": op.get("requirementId")})

    return {
        "status": "BLOCKED" if blockers else "PASS",
        "rootPelvisDistinct": adapt02.get("rootPelvisValidation", {}).get("distinct"),
        "bodySemanticPreserved": True,
        "blockers": blockers,
    }


def validate_face_boundary(
    adapt03: dict[str, Any],
    plan: dict[str, Any],
    face_binding: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    attach = face_binding.get("faceBodyAttachment") or {}
    a03_attach = adapt03.get("faceBodyAttachment") or {}

    if force_flags.get("crossBoundaryFaceOwnership"):
        blockers.append({"code": "CROSS_BOUNDARY_OWNERSHIP", "message": "FACE/BODY ownership collision"})
    if a03_attach.get("status") != "COMPATIBLE":
        blockers.append({"code": "ATTACHMENT_NOT_COMPATIBLE", "message": "ADAPT-03 attachment not compatible"})

    face_roots = [op for op in (plan.get("operations") or []) if op.get("createsCompetingFaceRoot")]
    if face_roots:
        blockers.append({"code": "MULTIPLE_FACE_ROOTS", "count": len(face_roots)})

    for op in plan.get("operations") or []:
        parent = op.get("parent") or "FACE_Rig_Root"
        if parent not in ("FACE_Rig_Root", attach.get("child", "FACE_Rig_Root")):
            if op.get("augmentationType") != "ATTACHMENT_HELPER":
                blockers.append({"code": "INVALID_FACE_PARENT", "operation": op.get("requirementId")})

    return {
        "status": "BLOCKED" if blockers else "PASS",
        "soleAttachment": f"{attach.get('parent')} → {attach.get('child')}",
        "attachmentType": attach.get("type"),
        "blockers": blockers,
    }
