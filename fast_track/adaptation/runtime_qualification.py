"""ADAPT-05 Runtime Qualification — qualify ADAPT-04 candidates without mutation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.adapt06_handoff import build_adapt06_handoff
from fast_track.adaptation.auxiliary_augmentation import augment_from_glb, load_augmentation_binding
from fast_track.adaptation.face_adaptation import load_face_binding
from fast_track.adaptation.face_capability_qualifiers import (
    qualify_expression,
    qualify_eyes,
    qualify_face_semantics,
    qualify_jaw_mouth,
    qualify_talking,
)
from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.adaptation.qualification_classifier import classify_qualification
from fast_track.adaptation.runtime_compatibility_qualifiers import (
    qualify_behavior_runtime,
    qualify_face_body_coplay,
    qualify_motion_compatibility,
    qualify_product_release,
    qualify_runtime_state,
)
from fast_track.adaptation.skeleton_mapping import load_binding
from fast_track.adaptation.structural_qualifier import (
    qualify_body,
    qualify_face_attachment,
    qualify_structural,
)

REPORT_SCHEMA = "NURION_ADAPT05_QUALIFICATION_REPORT_V1"

# Fields excluded from qualificationReportDigest — must stay identical for Human recompute
DIGEST_EXCLUDE_KEYS = frozenset(
    {
        "qualificationReportDigest",
        "adapt06Handoff",
        "adapt06HandoffDigest",
        "contractCanonicalSha256",
        "sourceAssetPath",
        "candidatePath",
        "localArtifactPaths",
        "liveChainObservation",
    }
)

CANONICAL_QUALIFIED_CHARACTER_ID = "canonical_qualified"


def qualification_report_digest_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Canonical subset used to compute qualificationReportDigest (deterministic, path-free)."""
    return {k: v for k, v in report.items() if k not in DIGEST_EXCLUDE_KEYS}


def compute_qualification_report_digest(report: dict[str, Any]) -> str:
    return canonical_sha256(qualification_report_digest_payload(report))


def load_runtime_binding(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_identity(
    adapt01: dict[str, Any],
    adapt02: dict[str, Any],
    adapt03: dict[str, Any],
    adapt04: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    handoff = adapt04.get("adapt05Handoff") or {}
    src = (adapt01.get("sourceAsset") or {}).get("sha256")
    derived = (handoff.get("derivedArtifactIdentity") or {}).get("derivedArtifactSha256") or adapt04.get(
        "derivedArtifactSha256"
    )
    # Path-stable authority identity only (absolute paths in ADAPT-01 reports must not enter seal)
    identity = {
        "sourceAssetSha256": src,
        "derivedArtifactSha256": derived,
        "adapt04AugmentationPlanDigest": adapt04.get("augmentationPlanDigest")
        or handoff.get("augmentationPlanDigest"),
        "adapt04DerivedSemanticDigest": adapt04.get("derivedSemanticDigest"),
    }
    # Live chain digests may embed absolute paths — observe only, never seal
    live_chain = {
        "adapt01InspectionDigest": adapt01.get("reportCanonicalSha256"),
        "adapt02MappingDigest": adapt02.get("contractCanonicalSha256"),
        "adapt03FaceAdaptationDigest": adapt03.get("contractCanonicalSha256"),
        "authority": "NON_AUTHORITATIVE_LIVE_OBSERVATION",
        "note": "May vary by extraction path; excluded from qualificationReportDigest",
    }
    blockers: list[dict[str, Any]] = []
    if force_flags.get("candidateShaMismatch"):
        blockers.append({"code": "CANDIDATE_SHA_MISMATCH", "message": "qualification bound to different binary"})
        identity["derivedArtifactSha256"] = "DEADBEEF" + (derived or "")[8:]
    if force_flags.get("adapt04ProvenanceMismatch"):
        blockers.append({"code": "ADAPT04_PROVENANCE_MISMATCH", "message": "augmentation plan/provenance mismatch"})
    if force_flags.get("upstreamPinMismatch"):
        blockers.append({"code": "UPSTREAM_PIN_MISMATCH", "message": "required authority unpinned/mismatched"})
    # Chain integrity checks without sealing volatile digests
    if adapt03.get("adapt01InspectionDigest") and adapt03.get("adapt01InspectionDigest") != adapt01.get(
        "reportCanonicalSha256"
    ):
        blockers.append({"code": "ADAPT01_ADAPT03_CHAIN_BREAK", "message": "live chain mismatch"})
    if adapt03.get("adapt02MappingDigest") and adapt03.get("adapt02MappingDigest") != adapt02.get(
        "contractCanonicalSha256"
    ):
        blockers.append({"code": "ADAPT02_ADAPT03_CHAIN_BREAK", "message": "live chain mismatch"})
    return {"identity": identity, "liveChain": live_chain, "blockers": blockers}


def build_runtime_qualification(
    adapt01: dict[str, Any],
    adapt02: dict[str, Any],
    adapt03: dict[str, Any],
    adapt04: dict[str, Any],
    runtime_binding: dict[str, Any],
    candidate_path: Path | None,
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []

    if force_flags.get("unauthorizedCandidateMutation"):
        blockers.append(
            {
                "code": "UNAUTHORIZED_CANDIDATE_MUTATION",
                "message": "candidate mutation during ADAPT-05 denied",
            }
        )
    if force_flags.get("performAdapt06Release"):
        blockers.append({"code": "ADAPT06_PREMATURE", "message": "ADAPT-06 not started / LOCKED"})

    id_block = _candidate_identity(adapt01, adapt02, adapt03, adapt04, force_flags=force_flags)
    blockers.extend(id_block["blockers"])

    # When NO_AUGMENTATION_REQUIRED, qualify source as candidate if derived absent
    use_source = adapt04.get("classification") == "NO_AUGMENTATION_REQUIRED"
    if use_source and (not candidate_path or not candidate_path.is_file()):
        force_flags = {**force_flags, "useSourceAsCandidate": True}

    structural = qualify_structural(candidate_path, adapt04, force_flags=force_flags)
    body = qualify_body(adapt02, force_flags=force_flags)
    attachment = qualify_face_attachment(adapt03, adapt04, force_flags=force_flags)
    face = qualify_face_semantics(adapt03, adapt04, force_flags=force_flags)
    eye = qualify_eyes(adapt03, adapt04, force_flags=force_flags)
    expression = qualify_expression(adapt03, adapt04, force_flags=force_flags)
    jaw = qualify_jaw_mouth(adapt03, adapt04, force_flags=force_flags)
    talking = qualify_talking(adapt03, adapt04, force_flags=force_flags)
    motion = qualify_motion_compatibility(force_flags=force_flags)
    state = qualify_runtime_state(force_flags=force_flags)
    behavior = qualify_behavior_runtime(force_flags=force_flags)
    product = qualify_product_release(force_flags=force_flags)
    coplay = qualify_face_body_coplay(
        face.get("status") == "PASS",
        body.get("status") == "PASS",
        talking.get("status") == "PASS",
        force_flags=force_flags,
    )

    sections = {
        "structuralQualification": structural,
        "bodyQualification": body,
        "faceAttachmentQualification": attachment,
        "faceQualification": face,
        "eyeQualification": eye,
        "expressionQualification": expression,
        "jawMouthQualification": jaw,
        "talkingQualification": talking,
        "motionCompatibility": motion,
        "faceBodyCoPlay": coplay,
        "runtimeStateCompatibility": state,
        "behaviorRuntimeCompatibility": behavior,
        "productReleaseCompatibility": product,
    }

    if blockers:
        # inject identity/policy blockers into structural for classifier visibility
        structural = {
            **structural,
            "status": "BLOCKED",
            "blockers": list(structural.get("blockers") or []) + blockers,
        }
        sections["structuralQualification"] = structural

    classified = classify_qualification(sections, force_flags=force_flags)

    runtime_matrix = {
        "motions": motion.get("observed"),
        "coPlay": coplay.get("observed"),
        "entranceStates": state.get("observed"),
        "behaviorMap": behavior.get("observed"),
        "productRelease": product.get("observed"),
        "talking": talking.get("talkingClassification"),
    }
    runtime_compatibility_digest = canonical_sha256(runtime_matrix)

    preservation = {
        "nurionV1Mutation": "NONE",
        "product01to06Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
        "adapt03Mutation": "NONE",
        "adapt04Mutation": "NONE",
        "faceAuthorityMutation": "NONE",
        "bodyCanonicalMutation": "NONE",
        "sourceOriginalMutation": "NONE",
        "candidateMutationDuringAdapt05": "NONE",
        "adapt06Implementation": "NOT_STARTED",
        "autoRepair": "DENY",
    }

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "stage": "ADAPT-05",
        "authorityRole": "QUALIFICATION_REPORT",
        "candidateIdentity": id_block["identity"],
        "sourceIdentity": {
            "characterId": adapt01.get("characterId"),
            "sourceAssetSha256": id_block["identity"].get("sourceAssetSha256"),
            "adapt04Classification": adapt04.get("classification"),
        },
        "upstreamAuthorityPins": {
            "runtimeAuthorityPins": runtime_binding.get("runtimeAuthorityPins"),
            "faceAuthorityPins": runtime_binding.get("faceAuthorityPins"),
            "predecessorPass": runtime_binding.get("predecessorPass"),
        },
        **sections,
        "limitations": classified["limitations"],
        "blockers": classified["blockers"],
        "manualReviewItems": classified["manualReviewItems"],
        "preservation": preservation,
        "finalClassification": classified["finalClassification"],
        "runtimeCompatibilityMatrix": runtime_matrix,
        "runtimeCompatibilityDigest": runtime_compatibility_digest,
        "evidenceLayers": {
            "observedEvidence": True,
            "inheritedAuthority": True,
            "inference": "DENIED_FOR_REQUIRED_CAPABILITY",
            "qualificationDecision": classified["finalClassification"],
        },
        "policy": classified["policy"],
        "autoRepair": "DENY",
        "digestPolicy": {
            "algorithm": "SHA256(canonical_json)",
            "excludes": sorted(DIGEST_EXCLUDE_KEYS),
            "note": "Human recompute MUST exclude DIGEST_EXCLUDE_KEYS; local paths and live chain digests never enter authority digest",
        },
        # Excluded from digest — may contain absolute-path-volatile upstream report digests
        "liveChainObservation": id_block.get("liveChain"),
    }
    report["qualificationReportDigest"] = compute_qualification_report_digest(report)

    release_eligible = report["finalClassification"] in ("QUALIFIED", "QUALIFIED_WITH_LIMITATIONS")
    handoff = build_adapt06_handoff(report, release_eligible=release_eligible)
    report["adapt06Handoff"] = handoff
    report["adapt06HandoffDigest"] = handoff.get("handoffDigest")
    report["contractCanonicalSha256"] = report["qualificationReportDigest"]
    return report


def qualify_from_glb(
    glb_path: Path,
    adapt02_binding_path: Path,
    face_binding_path: Path,
    aug_binding_path: Path,
    runtime_binding_path: Path,
    derived_dir: Path,
    *,
    character_id: str | None = None,
    force_flags: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Produce ADAPT-04 candidate then qualify read-only (ADAPT-05 does not mutate)."""
    force_flags = force_flags or {}
    a01, a02, a03, a04 = augment_from_glb(
        glb_path,
        adapt02_binding_path,
        face_binding_path,
        aug_binding_path,
        derived_dir,
        character_id=character_id,
        force_flags={k: v for k, v in force_flags.items() if not str(k).startswith("qual")},
    )
    # Map qualification-specific force flags (strip qual_ prefix optional)
    qflags = {k: v for k, v in force_flags.items()}

    derived_name = None
    derived_sha = a04.get("derivedArtifactSha256")
    candidate: Path | None = None
    if derived_sha:
        # find derived glb in derived_dir
        for p in derived_dir.rglob("*_adapt04_derived.glb"):
            if sha256_file(p) == derived_sha or candidate is None:
                candidate = p
                if sha256_file(p) == derived_sha:
                    break
        if candidate is None:
            for p in derived_dir.rglob("*.glb"):
                candidate = p
                break
    elif a04.get("classification") == "NO_AUGMENTATION_REQUIRED":
        candidate = glb_path
        qflags = {**qflags, "useSourceAsCandidate": True}

    # Capture source bytes before qualification to prove no mutation
    src_before = glb_path.read_bytes() if glb_path.is_file() else None
    cand_before = candidate.read_bytes() if candidate and candidate.is_file() else None

    runtime_binding = load_runtime_binding(runtime_binding_path)
    report = build_runtime_qualification(
        a01, a02, a03, a04, runtime_binding, candidate, force_flags=qflags
    )

    if src_before is not None and glb_path.read_bytes() != src_before:
        report["finalClassification"] = "BLOCKED"
        report["blockers"] = list(report.get("blockers") or []) + [
            {"code": "SOURCE_MUTATED_DURING_QUALIFICATION", "message": "source changed"}
        ]
    if cand_before is not None and candidate and candidate.read_bytes() != cand_before:
        report["finalClassification"] = "BLOCKED"
        report["blockers"] = list(report.get("blockers") or []) + [
            {"code": "CANDIDATE_MUTATED_DURING_QUALIFICATION", "message": "candidate changed"}
        ]
        report["preservation"]["candidateMutationDuringAdapt05"] = "DETECTED"

    report["sourceAssetPath"] = str(glb_path)
    report["candidatePath"] = str(candidate) if candidate else None
    report["localArtifactPaths"] = {
        "sourceAssetPath": str(glb_path),
        "candidatePath": str(candidate) if candidate else None,
        "authority": "NON_AUTHORITATIVE_LOCAL_ONLY",
    }
    # Re-verify digest is still valid after attaching ephemeral local paths
    recomputed = compute_qualification_report_digest(report)
    if recomputed != report["qualificationReportDigest"]:
        report["finalClassification"] = "BLOCKED"
        report["blockers"] = list(report.get("blockers") or []) + [
            {"code": "QUALIFICATION_DIGEST_SEAL_BROKEN", "message": "digest drifted after local path attach"}
        ]
    return a01, a02, a03, a04, report
