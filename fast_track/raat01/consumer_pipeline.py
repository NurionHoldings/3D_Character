"""RAAT-01 consumer pipeline — runs frozen ADAPT-01…06 without mutating Engine V1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.auxiliary_augmentation import augment_from_glb
from fast_track.adaptation.character_release import (
    RELEASE_ID,
    RELEASE_VERSION,
    build_character_release,
    compute_release_report_digest,
    load_release_binding,
)
from fast_track.adaptation.face_adaptation import adapt_face_from_glb
from fast_track.adaptation.inspector import inspect_character, sha256_file
from fast_track.adaptation.release_classifier import classify_release
from fast_track.adaptation.runtime_qualification import qualify_from_glb
from fast_track.adaptation.skeleton_mapping import adapt_from_glb

RAAT_SCHEMA = "NURION_RAAT_ACCEPTANCE_REPORT_V1"


def _stage_outcome(
    stage: str,
    *,
    status: str,
    classification: str | None = None,
    blockers: list[dict[str, Any]] | None = None,
    manual_review: list[Any] | None = None,
    notes: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "classification": classification,
        "blockers": blockers or [],
        "manualReviewItems": manual_review or [],
        "notes": notes or [],
        **(extra or {}),
    }


def _blocked(stage: str, reason: str, *, blockers: list[dict] | None = None) -> dict[str, Any]:
    return _stage_outcome(
        stage,
        status="BLOCKED",
        classification="BLOCKED",
        blockers=blockers or [{"code": "UPSTREAM_BLOCKED", "message": reason}],
        notes=[reason],
    )


def build_raat_acceptance_release(
    qualification: dict[str, Any],
    release_binding: dict[str, Any],
    candidate_path: Path | None,
    *,
    character_id: str,
) -> dict[str, Any]:
    """ADAPT-06 consumer release for RAAT — no Engine V1 canonical pin enforcement."""
    report = build_character_release(qualification, release_binding, candidate_path)
    # Strip closure-only canonical pin blockers; RAAT evaluates live asset outcome
    pin_codes = {
        "QUALIFICATION_CHARACTER_MISMATCH",
        "CANDIDATE_SHA_PIN_MISMATCH",
        "QUALIFICATION_REPORT_DIGEST_PIN_MISMATCH",
        "RUNTIME_COMPATIBILITY_DIGEST_PIN_MISMATCH",
        "ADAPT05_HANDOFF_DIGEST_PIN_MISMATCH",
        "HANDOFF_QUALIFICATION_DIGEST_PIN_MISMATCH",
    }
    blockers = [b for b in (report.get("blockers") or []) if b.get("code") not in pin_codes]
    report["blockers"] = blockers
    report["releaseIdentity"]["characterId"] = character_id
    report["authorityRole"] = "RAAT_ACCEPTANCE_RELEASE"
    report["raatMode"] = True
    report["engineV1CanonicalMutation"] = "DENY"
    classified = classify_release({**report, "blockers": blockers})
    report["finalClassification"] = classified["finalClassification"]
    if blockers:
        if classified["finalClassification"] == "RELEASED":
            report["finalClassification"] = "BLOCKED"
        report["blockers"] = blockers + list(classified.get("blockers") or [])
    report["releaseReportDigest"] = compute_release_report_digest(report)
    return report


def build_raat_result_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Canonical RAAT RESULT fields for human/support-envelope measurement."""
    stages = result.get("stages") or {}
    automatic_passed = []
    for s in ("ADAPT-01", "ADAPT-02", "ADAPT-03", "ADAPT-04", "ADAPT-05", "ADAPT-06"):
        v = stages.get(s) or {}
        st = v.get("status")
        cl = v.get("classification")
        if st == "BLOCKED":
            break
        if st == "PASS" or cl in (
            "QUALIFIED",
            "QUALIFIED_WITH_LIMITATIONS",
            "RELEASED",
            "RELEASED_WITH_LIMITATIONS",
            "AUGMENTED",
            "NO_AUGMENTATION_REQUIRED",
            "MAPPED",
            "CLASS_A",
            "CLASS_B",
            "CLASS_C",
        ):
            automatic_passed.append(s)
        elif st == "OBSERVED" and cl and cl != "BLOCKED":
            automatic_passed.append(s)

    blocked_reasons = []
    for s, v in stages.items():
        for b in v.get("blockers") or []:
            blocked_reasons.append({"stage": s, **b})

    manual = any((v.get("manualReviewItems") or []) for v in stages.values()) or any(
        (v.get("classification") == "MANUAL_REVIEW_REQUIRED") for v in stages.values()
    )

    release_sha = None
    a05 = stages.get("ADAPT-05") or {}
    a06 = stages.get("ADAPT-06") or {}
    if a06.get("classification") in ("RELEASED", "RELEASED_WITH_LIMITATIONS"):
        release_sha = a05.get("candidateSha256")

    return {
        "schema": "NURION_RAAT_RESULT_V1",
        "testId": result.get("testId"),
        "sourceSha256": (result.get("sourceAsset") or {}).get("sha256"),
        "assetIdentity": {
            "characterId": result.get("characterId"),
            "path": (result.get("sourceAsset") or {}).get("path"),
            "byteLength": (result.get("sourceAsset") or {}).get("byteLength"),
        },
        "ADAPT-01_classification": (stages.get("ADAPT-01") or {}).get("classification"),
        "ADAPT-02_mappingResult": {
            "status": (stages.get("ADAPT-02") or {}).get("status"),
            "classification": (stages.get("ADAPT-02") or {}).get("classification"),
            "chainValidation": (stages.get("ADAPT-02") or {}).get("chainValidation"),
            "blockers": (stages.get("ADAPT-02") or {}).get("blockers"),
        },
        "ADAPT-03_faceCapabilityResult": {
            "status": (stages.get("ADAPT-03") or {}).get("status"),
            "classification": (stages.get("ADAPT-03") or {}).get("classification"),
            "faceBodyAttachment": (stages.get("ADAPT-03") or {}).get("faceBodyAttachment"),
            "blockers": (stages.get("ADAPT-03") or {}).get("blockers"),
        },
        "ADAPT-04_augmentationResult": {
            "status": (stages.get("ADAPT-04") or {}).get("status"),
            "classification": (stages.get("ADAPT-04") or {}).get("classification"),
            "derivedArtifactSha256": (stages.get("ADAPT-04") or {}).get("derivedArtifactSha256"),
            "blockers": (stages.get("ADAPT-04") or {}).get("blockers"),
        },
        "ADAPT-05_runtimeQualification": {
            "status": (stages.get("ADAPT-05") or {}).get("status"),
            "classification": (stages.get("ADAPT-05") or {}).get("classification"),
            "qualificationReportDigest": (stages.get("ADAPT-05") or {}).get("qualificationReportDigest"),
            "blockers": (stages.get("ADAPT-05") or {}).get("blockers"),
        },
        "ADAPT-06_releaseResult": {
            "status": (stages.get("ADAPT-06") or {}).get("status"),
            "classification": (stages.get("ADAPT-06") or {}).get("classification"),
            "releaseReportDigest": (stages.get("ADAPT-06") or {}).get("releaseReportDigest"),
            "finalReleaseDigest": (stages.get("ADAPT-06") or {}).get("finalReleaseDigest"),
            "blockers": (stages.get("ADAPT-06") or {}).get("blockers"),
        },
        "firstStopStage": result.get("firstStopStage"),
        "automaticStagesPassed": automatic_passed,
        "manualReviewRequired": manual,
        "blockedReasons": blocked_reasons,
        "sourceMutation": "NONE" if (result.get("preservation") or {}).get("sourceBytesUnchanged") else "DETECTED",
        "EngineV1Mutation": "NONE",
        "releaseCandidateSha256": release_sha,
        "pipelineStatus": result.get("pipelineStatus"),
        "raptEligible": release_sha is not None,
    }


def run_raat_pipeline(
    asset_path: Path,
    *,
    character_id: str,
    semantic_dir: Path,
    derived_dir: Path,
    test_id: str = "RAAT-01",
) -> dict[str, Any]:
    """Execute ADAPT-01→06 as consumer acceptance test. Source asset read-only."""
    derived_dir.mkdir(parents=True, exist_ok=True)
    adapt02_binding = semantic_dir / "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1.json"
    face_binding = semantic_dir / "NURION_ADAPT03_CANONICAL_FACE_BINDING_V1.json"
    aug_binding = semantic_dir / "NURION_ADAPT04_REQUIREMENT_BINDING_V1.json"
    runtime_binding = semantic_dir / "NURION_ADAPT05_RUNTIME_AUTHORITY_BINDING_V1.json"
    release_binding_path = semantic_dir / "NURION_ADAPT06_RELEASE_AUTHORITY_BINDING_V1.json"

    source_before = asset_path.read_bytes()
    source_sha = sha256_file(asset_path)

    stages: dict[str, dict[str, Any]] = {}
    reports: dict[str, Any] = {}
    pipeline_status = "IN_PROGRESS"
    stop_at: str | None = None

    # ADAPT-01
    adapt01 = inspect_character(asset_path, character_id=character_id)
    reports["adapt01"] = adapt01
    a01_class = (adapt01.get("adaptationClassification") or {}).get("adaptationClass")
    stages["ADAPT-01"] = _stage_outcome(
        "ADAPT-01",
        status="PASS" if a01_class not in (None, "BLOCKED") else "OBSERVED",
        classification=a01_class,
        notes=[f"sourceSha256={source_sha}"],
        extra={
            "adaptationClassification": adapt01.get("adaptationClassification"),
            "sourceAsset": adapt01.get("sourceAsset"),
        },
    )

    # ADAPT-02
    adapt01, adapt02 = adapt_from_glb(asset_path, adapt02_binding, character_id=character_id)
    reports["adapt02"] = adapt02
    a02_class = adapt02.get("classification")
    a02_blocked = a02_class == "BLOCKED" or bool(adapt02.get("blockers"))
    stages["ADAPT-02"] = _stage_outcome(
        "ADAPT-02",
        status="BLOCKED" if a02_blocked else "PASS",
        classification=a02_class,
        blockers=list(adapt02.get("blockers") or []),
        extra={"chainValidation": adapt02.get("chainValidation")},
    )
    if a02_blocked:
        stop_at = "ADAPT-02"
        for s in ("ADAPT-03", "ADAPT-04", "ADAPT-05", "ADAPT-06"):
            stages[s] = _blocked(s, f"upstream blocked at {stop_at}")

    # ADAPT-03
    if not stop_at:
        adapt01, adapt02, adapt03 = adapt_face_from_glb(
            asset_path, adapt02_binding, face_binding, character_id=character_id
        )
        reports["adapt03"] = adapt03
        a03_class = adapt03.get("classification")
        attachment = (adapt03.get("faceBodyAttachment") or {}).get("status")
        a03_blocked = a03_class == "BLOCKED" or attachment == "BLOCKED"
        stages["ADAPT-03"] = _stage_outcome(
            "ADAPT-03",
            status="BLOCKED" if a03_blocked else "PASS",
            classification=a03_class,
            blockers=list(adapt03.get("blockers") or []),
            manual_review=list(adapt03.get("manualReviewItems") or []),
            extra={"faceBodyAttachment": adapt03.get("faceBodyAttachment")},
        )
        if a03_blocked:
            stop_at = "ADAPT-03"
            for s in ("ADAPT-04", "ADAPT-05", "ADAPT-06"):
                stages[s] = _blocked(s, f"upstream blocked at {stop_at}")

    # ADAPT-04
    if not stop_at:
        adapt01, adapt02, adapt03, adapt04 = augment_from_glb(
            asset_path,
            adapt02_binding,
            face_binding,
            aug_binding,
            derived_dir,
            character_id=character_id,
        )
        reports["adapt04"] = adapt04
        a04_class = adapt04.get("classification")
        a04_blocked = a04_class == "BLOCKED"
        stages["ADAPT-04"] = _stage_outcome(
            "ADAPT-04",
            status="BLOCKED" if a04_blocked else "PASS",
            classification=a04_class,
            blockers=list(adapt04.get("blockers") or []),
            extra={"derivedArtifactSha256": adapt04.get("derivedArtifactSha256")},
        )
        if a04_blocked:
            stop_at = "ADAPT-04"
            for s in ("ADAPT-05", "ADAPT-06"):
                stages[s] = _blocked(s, f"upstream blocked at {stop_at}")

    # ADAPT-05
    candidate_path: Path | None = None
    adapt05: dict[str, Any] | None = None
    if not stop_at:
        adapt01, adapt02, adapt03, adapt04, adapt05 = qualify_from_glb(
            asset_path,
            adapt02_binding,
            face_binding,
            aug_binding,
            runtime_binding,
            derived_dir,
            character_id=character_id,
        )
        reports["adapt05"] = adapt05
        a05_class = adapt05.get("finalClassification")
        derived_sha = (adapt05.get("candidateIdentity") or {}).get("derivedArtifactSha256")
        if derived_sha:
            for p in derived_dir.rglob("*.glb"):
                if sha256_file(p) == derived_sha:
                    candidate_path = p
                    break
        stages["ADAPT-05"] = _stage_outcome(
            "ADAPT-05",
            status=a05_class or "OBSERVED",
            classification=a05_class,
            blockers=list(adapt05.get("blockers") or []),
            manual_review=list(adapt05.get("manualReviewItems") or []),
            extra={
                "candidateSha256": derived_sha,
                "runtimeCompatibilityDigest": adapt05.get("runtimeCompatibilityDigest"),
                "qualificationReportDigest": adapt05.get("qualificationReportDigest"),
            },
        )
        if a05_class in ("BLOCKED", "MANUAL_REVIEW_REQUIRED"):
            stop_at = "ADAPT-05"
            stages["ADAPT-06"] = _blocked("ADAPT-06", f"upstream stopped at {stop_at}; classification={a05_class}")

    # ADAPT-06
    adapt06: dict[str, Any] | None = None
    if not stop_at and adapt05 is not None:
        binding = load_release_binding(release_binding_path)
        adapt06 = build_raat_acceptance_release(
            adapt05, binding, candidate_path, character_id=character_id
        )
        reports["adapt06"] = adapt06
        a06_class = adapt06.get("finalClassification")
        stages["ADAPT-06"] = _stage_outcome(
            "ADAPT-06",
            status=a06_class or "OBSERVED",
            classification=a06_class,
            blockers=list(adapt06.get("blockers") or []),
            extra={
                "releaseId": RELEASE_ID,
                "releaseVersion": RELEASE_VERSION,
                "releaseReportDigest": adapt06.get("releaseReportDigest"),
                "finalReleaseDigest": adapt06.get("finalReleaseDigest"),
            },
        )

    source_after = asset_path.read_bytes()
    preservation_ok = source_before == source_after

    if stop_at:
        pipeline_status = "BLOCKED" if any(
            stages[s].get("classification") == "BLOCKED" for s in stages if stages[s].get("status") == "BLOCKED"
        ) else "STOPPED"
    elif adapt05 and adapt05.get("finalClassification") == "MANUAL_REVIEW_REQUIRED":
        pipeline_status = "MANUAL_REVIEW_REQUIRED"
    elif adapt06 and adapt06.get("finalClassification") in ("RELEASED", "RELEASED_WITH_LIMITATIONS"):
        pipeline_status = "RELEASED"
    else:
        pipeline_status = "BLOCKED"

    result = {
        "schema": RAAT_SCHEMA,
        "testId": test_id,
        "characterId": character_id,
        "sourceAsset": {
            "path": str(asset_path),
            "sha256": source_sha,
            "byteLength": len(source_before),
        },
        "engineV1": "CLOSED / PASS / CONSUME ONLY",
        "canonicalMutation": "DENY",
        "pipelineStatus": pipeline_status,
        "firstStopStage": stop_at,
        "stages": stages,
        "preservation": {
            "sourceBytesUnchanged": preservation_ok,
            "engineV1Mutation": "NONE",
            "adaptStageMutation": "NONE",
        },
        "reports": reports,
    }
    result["raatResult"] = build_raat_result_summary(result)
    return result
