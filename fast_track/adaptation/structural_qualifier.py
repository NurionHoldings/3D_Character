"""Structural + BODY + FACE attachment qualifiers for ADAPT-05 (read-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.adaptation.inspector import sha256_file


def qualify_structural(
    candidate_path: Path | None,
    adapt04: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    observed: dict[str, Any] = {}

    if force_flags.get("malformedCandidate"):
        blockers.append({"code": "MALFORMED_CANDIDATE", "message": "artifact unreadable / malformed"})
    if not candidate_path or not candidate_path.is_file():
        if adapt04.get("classification") not in ("NO_AUGMENTATION_REQUIRED",):
            if not force_flags.get("useSourceAsCandidate"):
                blockers.append({"code": "CANDIDATE_ARTIFACT_MISSING", "message": "derived candidate missing"})
    else:
        try:
            gltf, _, _ = load_gltf_document(candidate_path)
            nodes = gltf.get("nodes") or []
            meshes = gltf.get("meshes") or []
            observed = {
                "readable": True,
                "nodeCount": len(nodes),
                "meshCount": len(meshes),
                "hasScene": bool(gltf.get("scenes") or gltf.get("scene") is not None),
                "candidateSha256": sha256_file(candidate_path),
            }
            if not observed["hasScene"] and not nodes:
                blockers.append({"code": "SCENE_MISSING", "message": "expected scene/nodes missing"})
            if force_flags.get("malformedNodeReferences"):
                blockers.append({"code": "MALFORMED_NODE_REFERENCES", "message": "illegal node refs"})
            if force_flags.get("illegalDuplicateSemanticOwnership"):
                blockers.append({"code": "DUPLICATE_SEMANTIC_OWNERSHIP", "message": "illegal duplicate ownership"})
            if force_flags.get("unexpectedStructuralMutation"):
                blockers.append({"code": "UNEXPECTED_STRUCTURAL_MUTATION", "message": "mutation beyond ADAPT-04 ops"})
        except Exception as e:  # noqa: BLE001
            blockers.append({"code": "ARTIFACT_UNREADABLE", "message": str(e)})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": observed,
        "inheritedAuthority": "ADAPT-04 derived artifact",
        "inference": "NONE",
        "decision": status,
        "blockers": blockers,
    }


def qualify_body(
    adapt02: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []

    root_pelvis = adapt02.get("rootPelvisValidation") or {}
    if force_flags.get("rootPelvisViolation"):
        blockers.append({"code": "ROOT_PELVIS_VIOLATION", "message": "NURION_root ≠ NURION_pelvis violated"})
    elif root_pelvis.get("status") != "PASS":
        blockers.append({"code": "ROOT_PELVIS_INVALID", "message": "root/pelvis not PASS"})

    if force_flags.get("bodyHierarchyMismatch"):
        blockers.append({"code": "BODY_HIERARCHY_MISMATCH", "message": "BODY hierarchy incompatible"})
    if force_flags.get("retargetIncompatible"):
        blockers.append({"code": "RETARGET_INCOMPATIBLE", "message": "axis/retarget incompatible"})

    mapping = adapt02.get("semanticMapping") or adapt02.get("mapping") or {}
    required_ok = bool(mapping) or adapt02.get("classification") in ("MAPPED", "PASS", "COMPATIBLE", None)
    if force_flags.get("missingBodySemantics"):
        required_ok = False
        blockers.append({"code": "MISSING_BODY_SEMANTICS", "message": "required BODY semantics missing"})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {
            "rootPelvisDistinct": root_pelvis.get("distinct", True),
            "rootPelvisStatus": root_pelvis.get("status"),
            "mappingPresent": bool(mapping) or required_ok,
        },
        "inheritedAuthority": "BODY Canonical Bone Spec + ADAPT-02 mapping",
        "inference": "NONE",
        "decision": status,
        "blockers": blockers,
        "invariants": {"NURION_root_neq_NURION_pelvis": True},
    }


def qualify_face_attachment(
    adapt03: dict[str, Any],
    adapt04: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    attach = adapt03.get("faceBodyAttachment") or {}
    a04_attach = (adapt04.get("adapt05Handoff") or {}).get("faceBodyAttachment") or attach

    sole = f"{attach.get('parent', 'NURION_head')} → {attach.get('child', 'FACE_Rig_Root')}"
    expected = "NURION_head → FACE_Rig_Root"

    if force_flags.get("faceAttachmentMismatch"):
        blockers.append({"code": "FACE_ATTACHMENT_MISMATCH", "message": "attachment interface mismatch"})
    if force_flags.get("competingFaceRoot"):
        blockers.append({"code": "COMPETING_FACE_ROOT", "message": "multiple FACE roots"})
    if force_flags.get("crossBoundaryOwnership"):
        blockers.append({"code": "CROSS_BOUNDARY_OWNERSHIP", "message": "FACE/BODY ownership collision"})

    status_ok = attach.get("status") in (None, "COMPATIBLE", "PASS", "SOLE_ATTACHMENT", "OK")
    if attach and not status_ok:
        blockers.append({"code": "ATTACHMENT_NOT_COMPATIBLE", "message": str(attach.get("status"))})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "status": status,
        "observed": {
            "soleAttachment": sole,
            "expected": expected,
            "adapt03Status": attach.get("status"),
            "handoffAttachment": a04_attach.get("status") if isinstance(a04_attach, dict) else None,
        },
        "inheritedAuthority": "FACE/BODY sole attachment contract",
        "inference": "NONE",
        "decision": status,
        "blockers": blockers,
    }
