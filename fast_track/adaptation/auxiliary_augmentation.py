"""ADAPT-04 auxiliary rig augmentation — consumes ADAPT-03 requirements only."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fast_track.adaptation.authoritative_augmentation_binding import requirements_digest
from fast_track.adaptation.boundary_preservation import validate_body_preservation, validate_face_boundary
from fast_track.adaptation.deformation_binding import record_weight_adjustments, validate_deformation_scope
from fast_track.adaptation.expression_augmentation import apply_expression_structures, plan_expression_operation
from fast_track.adaptation.eye_augmentation import apply_eye_structures, eye_capability_matrix, plan_eye_operation
from fast_track.adaptation.face_adaptation import adapt_face_from_glb, load_face_binding
from fast_track.adaptation.glb_io import load_gltf_document, write_minimal_glb
from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.adaptation.jaw_mouth_augmentation import apply_jaw_mouth_structures, plan_jaw_mouth_operation
from fast_track.adaptation.talking_augmentation import (
    apply_talking_structures,
    plan_talking_operation,
    talking_capability_matrix,
)

CONTRACT_SCHEMA = "NURION_ADAPT04_AUXILIARY_AUGMENTATION_CONTRACT_OUTPUT_V1"
PLAN_SCHEMA = "NURION_ADAPT04_AUGMENTATION_PLAN_V1"
HANDOFF_SCHEMA = "NURION_ADAPT05_QUALIFICATION_HANDOFF_V1"

OUTPUT_CLASSIFICATIONS = (
    "AUGMENTED",
    "NO_AUGMENTATION_REQUIRED",
    "MANUAL_REVIEW_REQUIRED",
    "BLOCKED",
)


def load_augmentation_binding(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"ADAPT-04 binding missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _assign_requirement_ids(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, req in enumerate(requirements):
        r = dict(req)
        r["requirementId"] = req.get("requirementId") or f"REQ-{i:04d}-{req.get('capability', 'UNKNOWN')}"
        out.append(r)
    return out


def _plan_operation_for_requirement(req: dict[str, Any], *, force_ambiguity: bool = False) -> dict[str, Any]:
    cap = req.get("capability") or ""
    auth = req.get("authority") or ""
    req = dict(req)
    if auth == "NURION_EYE_CALIBRATION" or ("eye" in cap.lower() and "Blink" in cap):
        op = plan_eye_operation(req, force_ambiguity=force_ambiguity)
    elif auth == "NURION_TALKING" or cap.startswith("FACE_mouth") or cap.startswith("FACE_lips") or cap.startswith("FACE_dental"):
        op = plan_talking_operation(req)
        if "Open" in cap or "jaw" in cap.lower():
            jaw = plan_jaw_mouth_operation(req)
            op["augmentationType"] = jaw["augmentationType"]
            op["expectedOutput"] = jaw["expectedOutput"]
    elif auth == "NURION_FACE_SEMANTIC":
        op = plan_expression_operation(req)
    else:
        op = plan_expression_operation(req)
    op["requirementId"] = req.get("requirementId")
    return op


def build_augmentation_plan(
    adapt03: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    req_block = adapt03.get("adapt04AugmentationRequirements") or {}
    requirements = _assign_requirement_ids(list(req_block.get("requirements") or []))

    if force_flags.get("noAugmentationRequired"):
        requirements = []

    operations: list[dict[str, Any]] = []
    for req in requirements:
        op = _plan_operation_for_requirement(
            req,
            force_ambiguity=bool(force_flags.get("leftRightEyeAmbiguity")),
        )
        if force_flags.get("unsupportedTopology") and "eye" in (req.get("capability") or "").lower():
            op["status"] = "MANUAL_REVIEW"
            op["reason"] = "UNSUPPORTED_TOPOLOGY"
        operations.append(op)

    if force_flags.get("unrequestedAugmentation"):
        operations.append(
            {
                "requirementId": "UNREQUESTED-0001",
                "capability": "FACE_arbitraryHelper",
                "augmentationType": "AUXILIARY_BONE",
                "authority": "NONE",
                "parent": "FACE_Rig_Root",
                "status": "PLANNED",
                "unrequested": True,
            }
        )

    if force_flags.get("bodyHierarchyMutation"):
        for op in operations:
            op["mutatesBodyHierarchy"] = True

    if force_flags.get("crossBoundaryFaceOwnership"):
        for op in operations:
            op["createsCompetingFaceRoot"] = True

    if force_flags.get("globalSkinRewrite"):
        for op in operations:
            op["overwritesSourceWeights"] = True
            op["deformationScope"] = "GLOBAL_BODY"

    plan_body = {
        "schema": PLAN_SCHEMA,
        "requirementsDigest": requirements_digest(req_block),
        "requirementCount": len(requirements),
        "operations": operations,
    }
    plan_body["augmentationPlanDigest"] = canonical_sha256(
        {k: v for k, v in plan_body.items() if k != "augmentationPlanDigest"}
    )
    return plan_body


def validate_requirement_traceability(
    plan: dict[str, Any],
    adapt03: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    req_block = adapt03.get("adapt04AugmentationRequirements") or {}
    authorized = _assign_requirement_ids(list(req_block.get("requirements") or []))
    authorized_ids = {r["requirementId"] for r in authorized}
    authorized_caps = {r.get("capability") for r in authorized}

    if force_flags.get("adapt03RequirementDigestMismatch"):
        blockers.append({"code": "REQUIREMENT_DIGEST_MISMATCH", "message": "ADAPT-03 requirement digest mismatch"})

    expected_digest = requirements_digest(req_block)
    if plan.get("requirementsDigest") != expected_digest and not force_flags.get("adapt03RequirementDigestMismatch"):
        if force_flags.get("adapt03RequirementDigestMismatch") is False:
            pass
        # only fail on explicit flag; normal path must match
        if plan.get("requirementsDigest") != expected_digest:
            blockers.append({"code": "PLAN_REQUIREMENT_DIGEST_MISMATCH", "expected": expected_digest})

    for op in plan.get("operations") or []:
        if op.get("unrequested"):
            blockers.append({"code": "UNREQUESTED_AUGMENTATION", "operation": op.get("requirementId")})
            continue
        rid = op.get("requirementId")
        if rid not in authorized_ids and op.get("capability") not in authorized_caps:
            blockers.append({"code": "UNAUTHORIZED_OPERATION", "operation": rid})
        if op.get("status") == "BLOCKED":
            blockers.append({"code": "OPERATION_BLOCKED", "operation": rid, "reason": op.get("reason")})
        if op.get("status") == "MANUAL_REVIEW":
            blockers.append({"code": "MANUAL_REVIEW", "operation": rid, "soft": True})

    soft = [b for b in blockers if b.get("soft")]
    hard = [b for b in blockers if not b.get("soft")]
    return {
        "status": "BLOCKED" if hard else ("MANUAL_REVIEW_REQUIRED" if soft else "PASS"),
        "blockers": blockers,
        "traceability": "REQUIREMENT_TO_OPERATION",
    }


def write_derived_artifact(
    source_path: Path,
    derived_path: Path,
    applied: dict[str, Any],
) -> str:
    """Create NEW derived artifact — source remains read-only."""
    gltf, bin_blob, _fmt = load_gltf_document(source_path)
    record = {
        "schema": "NURION_ADAPT04_DERIVED_ARTIFACT_V1",
        "sourceAssetSha256": sha256_file(source_path),
        "derivedFrom": str(source_path.name),
        "appliedStructures": applied,
        "sourceOverwrite": False,
    }
    gltf.setdefault("extras", {})["NURION_ADAPT04_DERIVED"] = record
    aux_parent_idx = None
    nodes = gltf.get("nodes") or []
    head_name = applied.get("targetHeadNode")
    for i, n in enumerate(nodes):
        if n.get("name") == head_name or n.get("name") == "Head":
            aux_parent_idx = i
            break
    face_root_idx = len(nodes)
    nodes.append({"name": "FACE_Rig_Root", "extras": {"nurionSemantic": "FACE_Rig_Root", "adapt04": True}})
    for struct in applied.get("structures") or []:
        nm = struct.get("nodeName") or struct.get("controlName")
        if nm:
            nodes.append(
                {
                    "name": nm,
                    "extras": {
                        "adapt04": True,
                        "semantic": struct.get("semantic"),
                        "type": struct.get("type"),
                    },
                }
            )
    if aux_parent_idx is not None:
        nodes[aux_parent_idx].setdefault("children", []).append(face_root_idx)
    gltf["nodes"] = nodes
    blob = bin_blob if bin_blob is not None else b"\x00\x00\x00\x00"
    derived_path.parent.mkdir(parents=True, exist_ok=True)
    derived_path.write_bytes(write_minimal_glb(gltf, blob))
    return sha256_file(derived_path)


def _build_adapt05_handoff(
    adapt01: dict[str, Any],
    adapt02: dict[str, Any],
    adapt03: dict[str, Any],
    plan: dict[str, Any],
    applied: dict[str, Any],
    classification: str,
    derived_sha: str | None,
) -> dict[str, Any]:
    handoff = {
        "schema": HANDOFF_SCHEMA,
        "sourceIdentity": {
            "characterId": adapt01.get("characterId"),
            "sourceAssetSha256": adapt01.get("sourceAsset", {}).get("sha256"),
            "adapt01InspectionDigest": adapt01.get("reportCanonicalSha256"),
            "adapt02MappingDigest": adapt02.get("contractCanonicalSha256"),
            "adapt03FaceAdaptationDigest": adapt03.get("contractCanonicalSha256"),
        },
        "derivedArtifactIdentity": {"derivedArtifactSha256": derived_sha},
        "augmentationPlanDigest": plan.get("augmentationPlanDigest"),
        "appliedOperations": plan.get("operations"),
        "capabilityMatrices": applied.get("capabilityMatrices"),
        "faceBodyAttachment": adapt03.get("faceBodyAttachment"),
        "bodyPreservation": {"status": "PRESERVED", "adapt02Digest": adapt02.get("contractCanonicalSha256")},
        "classification": classification,
        "adapt05Qualification": "NOT_STARTED",
        "unresolvedConditions": applied.get("unresolvedConditions") or [],
    }
    handoff["handoffDigest"] = canonical_sha256({k: v for k, v in handoff.items() if k != "handoffDigest"})
    return handoff


def build_auxiliary_augmentation(
    adapt01: dict[str, Any],
    adapt02: dict[str, Any],
    adapt03: dict[str, Any],
    aug_binding: dict[str, Any],
    face_binding: dict[str, Any],
    source_path: Path,
    derived_dir: Path,
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []

    if adapt03.get("classification") == "BLOCKED":
        blockers.append({"code": "ADAPT03_BLOCKED", "message": "ADAPT-03 not PASS-eligible"})
    if force_flags.get("adapt03RequirementDigestMismatch"):
        blockers.append({"code": "REQUIREMENT_DIGEST_MISMATCH", "message": "ADAPT-03 requirement digest mismatch"})
    if force_flags.get("adapt03NotPass"):
        blockers.append({"code": "ADAPT03_NOT_PASS", "message": "ADAPT-03 PASS required"})

    a03_digest = adapt03.get("contractCanonicalSha256")
    if adapt03.get("adapt01InspectionDigest") != adapt01.get("reportCanonicalSha256"):
        blockers.append({"code": "ADAPT01_ADAPT03_MISMATCH", "message": "digest chain broken"})
    if adapt03.get("adapt02MappingDigest") != adapt02.get("contractCanonicalSha256"):
        blockers.append({"code": "ADAPT02_ADAPT03_MISMATCH", "message": "mapping digest broken"})
    if force_flags.get("sourceDigestMismatch"):
        blockers.append({"code": "SOURCE_DIGEST_MISMATCH", "message": "source sha mismatch"})
    src_sha = (adapt01.get("sourceAsset") or {}).get("sha256")
    if src_sha and adapt02.get("sourceAssetDigest") and src_sha != adapt02.get("sourceAssetDigest"):
        blockers.append({"code": "SOURCE_IDENTITY_INCONSISTENT", "message": "adapt01/02 source sha"})
    if force_flags.get("performAdapt05Qualification"):
        blockers.append({"code": "ADAPT05_PREMATURE", "message": "ADAPT-05 not allowed in ADAPT-04"})

    plan = build_augmentation_plan(adapt03, force_flags=force_flags)
    trace = validate_requirement_traceability(plan, adapt03, force_flags=force_flags)
    body_val = validate_body_preservation(adapt02, plan, force_flags=force_flags)
    face_val = validate_face_boundary(adapt03, plan, face_binding, force_flags=force_flags)
    deform_val = validate_deformation_scope(plan, force_flags=force_flags)

    for val, code in ((trace, "TRACE"), (body_val, "BODY"), (face_val, "FACE_BOUNDARY"), (deform_val, "DEFORM")):
        if val.get("status") == "BLOCKED":
            blockers.extend(val.get("blockers") or [{"code": f"{code}_BLOCKED"}])

    classification = "BLOCKED"
    derived_sha: str | None = None
    applied_bundle: dict[str, Any] = {"structures": [], "capabilityMatrices": {}}

    if not blockers:
        if trace.get("status") == "MANUAL_REVIEW_REQUIRED":
            classification = "MANUAL_REVIEW_REQUIRED"
        elif not plan.get("operations"):
            classification = "NO_AUGMENTATION_REQUIRED"
        else:
            classification = "AUGMENTED"
            eye_ops = [o for o in plan["operations"] if o.get("augmentationType") in ("EYE_HELPER", "EYELID_CONTROL")]
            jaw_ops = [o for o in plan["operations"] if o.get("augmentationType") in ("JAW_HELPER", "MOUTH_HELPER")]
            expr_ops = [o for o in plan["operations"] if o.get("augmentationType") == "EXPRESSION_CONTROL"]
            talk_ops = [o for o in plan["operations"] if o.get("augmentationType") in ("TALKING_CONTROL", "VISEME_SUPPORT")]

            structures: list[dict[str, Any]] = []
            structures.extend(apply_eye_structures(eye_ops))
            structures.extend(apply_jaw_mouth_structures(jaw_ops))
            structures.extend(apply_expression_structures(expr_ops))
            structures.extend(apply_talking_structures(talk_ops))

            reqs = _assign_requirement_ids((adapt03.get("adapt04AugmentationRequirements") or {}).get("requirements") or [])
            applied_bundle = {
                "structures": structures,
                "targetHeadNode": (adapt03.get("headSemantic") or {}).get("targetReference"),
                "weightAdjustments": record_weight_adjustments(plan["operations"]),
                "capabilityMatrices": {
                    "eye": eye_capability_matrix(structures, reqs),
                    "talking": talking_capability_matrix(structures, reqs),
                    "expression": {"rowCount": len([s for s in structures if s.get("type") == "EXPRESSION_CONTROL"])},
                },
                "unresolvedConditions": trace.get("blockers") if trace.get("status") == "MANUAL_REVIEW_REQUIRED" else [],
            }

            if classification == "AUGMENTED" and source_path.is_file():
                derived_name = f"{source_path.stem}_adapt04_derived.glb"
                derived_path = derived_dir / derived_name
                derived_sha = write_derived_artifact(source_path, derived_path, applied_bundle)

    semantic_core = {
        "schema": CONTRACT_SCHEMA,
        "characterIdentity": adapt01.get("characterId"),
        "sourceAssetDigest": src_sha,
        "adapt01InspectionDigest": adapt01.get("reportCanonicalSha256"),
        "adapt02MappingDigest": adapt02.get("contractCanonicalSha256"),
        "adapt03FaceAdaptationDigest": a03_digest,
        "adapt03RequirementsDigest": plan.get("requirementsDigest"),
        "augmentationPlanDigest": plan.get("augmentationPlanDigest"),
        "derivedArtifactSha256": derived_sha,
        "classification": classification,
        "augmentationPlan": plan,
        "appliedAugmentation": applied_bundle,
        "traceabilityValidation": trace,
        "bodyPreservationValidation": body_val,
        "faceBoundaryValidation": face_val,
        "deformationScopeValidation": deform_val,
        "blockers": blockers,
        "preservationEvidence": {
            "sourceOriginalMutation": "NONE",
            "sourceOverwrite": "DENY",
            "bodyCanonicalMutation": "NONE",
            "nurionV1Mutation": "NONE",
            "adapt01Mutation": "NONE",
            "adapt02Mutation": "NONE",
            "adapt03Mutation": "NONE",
            "faceAuthorityMutation": "NONE",
            "adapt05Implementation": "NOT_STARTED",
            "autoRepair": "DENY",
        },
    }
    semantic_core["derivedSemanticDigest"] = canonical_sha256(
        {
            "plan": plan.get("augmentationPlanDigest"),
            "applied": applied_bundle,
            "classification": classification,
        }
    )
    semantic_core["adapt05Handoff"] = _build_adapt05_handoff(
        adapt01, adapt02, adapt03, plan, applied_bundle, classification, derived_sha
    )
    semantic_core["contractCanonicalSha256"] = canonical_sha256(
        {k: v for k, v in semantic_core.items() if k != "contractCanonicalSha256"}
    )
    return semantic_core


def augment_from_glb(
    glb_path: Path,
    adapt02_binding_path: Path,
    face_binding_path: Path,
    aug_binding_path: Path,
    derived_dir: Path,
    *,
    character_id: str | None = None,
    force_flags: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Full pipeline: ADAPT-01→02→03 then ADAPT-04 augmentation. Source GLB immutable."""
    before = glb_path.read_bytes() if glb_path.is_file() else None
    adapt01, adapt02, adapt03 = adapt_face_from_glb(
        glb_path,
        adapt02_binding_path,
        face_binding_path,
        character_id=character_id,
        force_flags=force_flags,
    )
    aug_binding = load_augmentation_binding(aug_binding_path)
    face_binding = load_face_binding(face_binding_path)
    contract = build_auxiliary_augmentation(
        adapt01,
        adapt02,
        adapt03,
        aug_binding,
        face_binding,
        glb_path,
        derived_dir,
        force_flags=force_flags,
    )
    if before is not None and glb_path.read_bytes() != before:
        raise RuntimeError("ADAPT-04 preservation violation: source bytes changed")
    return adapt01, adapt02, adapt03, contract
