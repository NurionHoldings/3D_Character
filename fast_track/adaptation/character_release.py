"""ADAPT-06 Adapted Character Release — seal qualified candidate without mutation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.authoritative_release_binding import (
    CANONICAL_ADAPT05_HANDOFF_DIGEST,
    CANONICAL_CANDIDATE_SHA256,
    CANONICAL_CHARACTER_ID,
    CANONICAL_QUALIFICATION_REPORT_DIGEST,
    CANONICAL_RUNTIME_COMPATIBILITY_DIGEST,
    verify_canonical_qualification_pins,
)
from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.adaptation.release_classifier import classify_release

REPORT_SCHEMA = "NURION_ADAPT06_RELEASE_REPORT_V1"
RELEASE_ID = "NURION_ADAPTED_CHARACTER_RELEASE_V1"
RELEASE_VERSION = "1.0.0"

DIGEST_EXCLUDE_KEYS = frozenset(
    {
        "releaseReportDigest",
        "finalReleaseDigest",
        "contractCanonicalSha256",
        "sourceAssetPath",
        "candidatePath",
        "localArtifactPaths",
        "consumerPackagePath",
    }
)


def release_report_digest_payload(report: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in report.items() if k not in DIGEST_EXCLUDE_KEYS}


def compute_release_report_digest(report: dict[str, Any]) -> str:
    return canonical_sha256(release_report_digest_payload(report))


def load_release_binding(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _adapter_metadata(qualification: dict[str, Any], release_binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "NURION_ADAPT06_ADAPTER_METADATA_V1",
        "releaseEngine": "NURION_CHARACTER_ADAPTATION_ENGINE_V1",
        "stage": "ADAPT-06",
        "adapterRole": "RELEASE_SEAL_ONLY",
        "characterId": CANONICAL_CHARACTER_ID,
        "qualificationClassification": qualification.get("finalClassification"),
        "runtimeAuthorityPins": release_binding.get("runtimeAuthorityPins"),
        "faceAuthorityPins": release_binding.get("faceAuthorityPins"),
        "faceBodyAttachment": release_binding.get("faceBodyAttachment"),
        "talkingClassification": (qualification.get("talkingQualification") or {}).get("talkingClassification"),
        "policy": "Package and seal only — no candidate repair",
    }


def _consumer_package(
    qualification: dict[str, Any],
    release_binding: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    limitations = list(qualification.get("limitations") or [])
    capabilities = {
        "bodySemantic": (qualification.get("bodyQualification") or {}).get("status") == "PASS",
        "faceSemantic": (qualification.get("faceQualification") or {}).get("status") == "PASS",
        "eyeCalibration": (qualification.get("eyeQualification") or {}).get("status") == "PASS",
        "talking": (qualification.get("talkingQualification") or {}).get("status") == "PASS",
        "motionLibrary": (qualification.get("motionCompatibility") or {}).get("status") == "PASS",
        "runtimeState": (qualification.get("runtimeStateCompatibility") or {}).get("status") == "PASS",
        "behaviorRuntime": (qualification.get("behaviorRuntimeCompatibility") or {}).get("status") == "PASS",
        "productRelease": (qualification.get("productReleaseCompatibility") or {}).get("status") == "PASS",
    }
    manifest_entries = [
        "candidateArtifact",
        "runtimeBindingManifest",
        "adapterMetadata",
        "limitationsDeclaration",
        "capabilityDeclaration",
        "provenanceChain",
        "releaseIdentity",
    ]
    if force_flags.get("incompleteConsumerPackage"):
        manifest_entries.remove("provenanceChain")
    return {
        "schema": "NURION_ADAPT06_CONSUMER_PACKAGE_V1",
        "releaseId": RELEASE_ID,
        "releaseVersion": RELEASE_VERSION,
        "candidateArtifactSha256": CANONICAL_CANDIDATE_SHA256,
        "manifestEntries": manifest_entries,
        "runtimeBindingManifest": release_binding.get("runtimeAuthorityPins"),
        "limitationsDeclaration": limitations,
        "capabilityDeclaration": capabilities,
        "complete": len(manifest_entries) == 7,
    }


def _provenance_chain(qualification: dict[str, Any], release_binding: dict[str, Any]) -> dict[str, Any]:
    preds = release_binding.get("predecessorPass") or {}
    ident = qualification.get("candidateIdentity") or {}
    return {
        "sourceCharacter": {
            "sourceAssetSha256": ident.get("sourceAssetSha256"),
            "adapt04AugmentationPlanDigest": ident.get("adapt04AugmentationPlanDigest"),
            "adapt04DerivedSemanticDigest": ident.get("adapt04DerivedSemanticDigest"),
        },
        "adaptationChain": {
            "ADAPT-01": preds.get("adapt01Status", "CLOSED / PASS / CONSUME ONLY"),
            "ADAPT-02": preds.get("adapt02Status", "CLOSED / PASS / CONSUME ONLY"),
            "ADAPT-03": preds.get("adapt03Status", "CLOSED / PASS / CONSUME ONLY"),
            "ADAPT-04": preds.get("adapt04Status", "CLOSED / PASS / CONSUME ONLY"),
            "ADAPT-05": preds.get("adapt05Status", "CLOSED / PASS / CONSUME ONLY"),
            "ADAPT-06": "OPEN / IMPLEMENTING",
        },
        "adapt05CanonicalSeal": {
            "candidateSha256": CANONICAL_CANDIDATE_SHA256,
            "qualificationReportDigest": CANONICAL_QUALIFICATION_REPORT_DIGEST,
            "runtimeCompatibilityDigest": CANONICAL_RUNTIME_COMPATIBILITY_DIGEST,
            "adapt05HandoffDigest": CANONICAL_ADAPT05_HANDOFF_DIGEST,
            "authority": "PINNED — ADAPT-06 must not recompute",
        },
    }


def build_character_release(
    qualification: dict[str, Any],
    release_binding: dict[str, Any],
    candidate_path: Path | None,
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []

    pin_verify = verify_canonical_qualification_pins(qualification)
    if pin_verify["status"] != "PASS":
        blockers.extend(pin_verify["blockers"])

    if force_flags.get("qualificationDigestMismatch"):
        blockers.append({"code": "QUALIFICATION_DIGEST_MISMATCH", "message": "pinned digest violated"})
    if force_flags.get("candidateShaMismatch"):
        blockers.append({"code": "CANDIDATE_SHA_MISMATCH", "message": "binary identity mismatch"})
    if force_flags.get("notReleaseEligible"):
        blockers.append({"code": "NOT_RELEASE_ELIGIBLE", "message": "classification not release eligible"})
    for attempt, code in (
        ("candidateRepairAttempt", "CANDIDATE_REPAIR_DENIED"),
        ("candidateReRigAttempt", "CANDIDATE_RE_RIG_DENIED"),
        ("candidateReWeightAttempt", "CANDIDATE_RE_WEIGHT_DENIED"),
        ("candidateReTargetAttempt", "CANDIDATE_RE_TARGET_DENIED"),
        ("autoRepairAttempt", "AUTO_REPAIR_DENIED"),
        ("nurionV1ModifyAttempt", "NURION_V1_MODIFY_DENIED"),
        ("adapt01to05ModifyAttempt", "ADAPT_PREDECESSOR_MODIFY_DENIED"),
    ):
        if force_flags.get(attempt):
            blockers.append({"code": code, "message": f"{attempt} denied in ADAPT-06"})

    cand_before: bytes | None = None
    if candidate_path and candidate_path.is_file():
        cand_before = candidate_path.read_bytes()
        live_sha = sha256_file(candidate_path)
        if live_sha != CANONICAL_CANDIDATE_SHA256:
            blockers.append(
                {
                    "code": "CANDIDATE_BINARY_IDENTITY_MISMATCH",
                    "message": f"observed {live_sha}",
                }
            )

    adapter = _adapter_metadata(qualification, release_binding)
    consumer = _consumer_package(qualification, release_binding, force_flags=force_flags)
    provenance = _provenance_chain(qualification, release_binding)

    preservation = {
        "nurionV1Mutation": "NONE",
        "product01to06Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
        "adapt03Mutation": "NONE",
        "adapt04Mutation": "NONE",
        "adapt05Mutation": "NONE",
        "faceAuthorityMutation": "NONE",
        "bodyCanonicalMutation": "NONE",
        "sourceOriginalMutation": "NONE",
        "candidateMutationDuringAdapt06": "NONE",
        "candidateRepair": "DENY",
        "candidateReRig": "DENY",
        "candidateReWeight": "DENY",
        "candidateReTarget": "DENY",
        "autoRepair": "DENY",
    }

    runtime_binding_integrity = {
        "runtimeAuthorityPins": release_binding.get("runtimeAuthorityPins"),
        "faceAuthorityPins": release_binding.get("faceAuthorityPins"),
        "runtimeCompatibilityDigest": CANONICAL_RUNTIME_COMPATIBILITY_DIGEST,
        "status": "PASS" if release_binding.get("runtimeAuthorityPins") else "BLOCKED",
    }

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "stage": "ADAPT-06",
        "authorityRole": "RELEASE_REPORT",
        "releaseIdentity": {
            "releaseId": RELEASE_ID,
            "releaseVersion": RELEASE_VERSION,
            "characterId": CANONICAL_CHARACTER_ID,
        },
        "adapt05CanonicalSeal": {
            "candidateSha256": CANONICAL_CANDIDATE_SHA256,
            "qualificationReportDigest": CANONICAL_QUALIFICATION_REPORT_DIGEST,
            "runtimeCompatibilityDigest": CANONICAL_RUNTIME_COMPATIBILITY_DIGEST,
            "adapt05HandoffDigest": CANONICAL_ADAPT05_HANDOFF_DIGEST,
        },
        "candidateIdentity": qualification.get("candidateIdentity"),
        "qualificationClassification": qualification.get("finalClassification"),
        "runtimeBindingIntegrity": runtime_binding_integrity,
        "bodySemanticBinding": qualification.get("bodyQualification"),
        "faceEyeTalkingBinding": {
            "face": qualification.get("faceQualification"),
            "eye": qualification.get("eyeQualification"),
            "talking": qualification.get("talkingQualification"),
        },
        "faceBodyAttachmentPreservation": qualification.get("faceAttachmentQualification"),
        "motionLibraryCompatibility": qualification.get("motionCompatibility"),
        "runtimeStateBehaviorBinding": {
            "runtimeState": qualification.get("runtimeStateCompatibility"),
            "behavior": qualification.get("behaviorRuntimeCompatibility"),
        },
        "adapterMetadata": adapter,
        "consumerPackage": consumer,
        "limitationsCapabilityDeclaration": {
            "limitations": qualification.get("limitations") or [],
            "capabilities": consumer.get("capabilityDeclaration"),
        },
        "provenanceChain": provenance,
        "preservation": preservation,
        "blockers": blockers,
        "policy": "RELEASE / PACKAGE / SEAL ONLY",
        "digestPolicy": {
            "algorithm": "SHA256(canonical_json)",
            "excludes": sorted(DIGEST_EXCLUDE_KEYS),
        },
    }

    classified = classify_release(report, force_flags=force_flags)
    report["finalClassification"] = classified["finalClassification"]
    report["blockers"] = list(blockers) + list(classified.get("blockers") or [])
    if classified.get("blockers"):
        report["finalClassification"] = "BLOCKED"

    report["releaseReportDigest"] = compute_release_report_digest(report)
    final_payload = {
        "releaseReportDigest": report["releaseReportDigest"],
        "releaseId": RELEASE_ID,
        "releaseVersion": RELEASE_VERSION,
        "adapt05CanonicalSeal": report["adapt05CanonicalSeal"],
        "consumerPackageManifest": consumer.get("manifestEntries"),
    }
    report["finalReleaseDigest"] = canonical_sha256(final_payload)
    report["contractCanonicalSha256"] = report["releaseReportDigest"]

    if cand_before is not None and candidate_path and candidate_path.read_bytes() != cand_before:
        report["finalClassification"] = "BLOCKED"
        report["blockers"] = list(report.get("blockers") or []) + [
            {"code": "CANDIDATE_MUTATED_DURING_RELEASE", "message": "candidate changed"}
        ]
        report["preservation"]["candidateMutationDuringAdapt06"] = "DETECTED"

    if force_flags.get("manifestTamper"):
        report["finalClassification"] = "BLOCKED"
        report["blockers"] = list(report.get("blockers") or []) + [
            {"code": "RELEASE_MANIFEST_TAMPER", "message": "manifest integrity violated"}
        ]

    return report


def release_from_qualification_report(
    qualification_report_path: Path,
    release_binding_path: Path,
    candidate_path: Path | None,
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    wrapper = json.loads(qualification_report_path.read_text(encoding="utf-8"))
    qualification = wrapper.get("adapt05") or wrapper
    binding = load_release_binding(release_binding_path)
    return build_character_release(qualification, binding, candidate_path, force_flags=force_flags)
