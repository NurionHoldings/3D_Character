"""ADAPT-06 release handoff generator — specification only; ADAPT-06 not started."""

from __future__ import annotations

from typing import Any

from fast_track.adaptation.inspector import canonical_sha256

HANDOFF_SCHEMA = "NURION_ADAPT06_RELEASE_HANDOFF_V1"


def build_adapt06_handoff(
    report: dict[str, Any],
    *,
    release_eligible: bool,
) -> dict[str, Any]:
    handoff = {
        "schema": HANDOFF_SCHEMA,
        "adapt06Implementation": "NOT_STARTED",
        "releaseEligible": release_eligible,
        "candidateIdentity": report.get("candidateIdentity"),
        "qualificationReportDigest": report.get("qualificationReportDigest"),
        "qualificationClassification": report.get("finalClassification"),
        "runtimeCompatibilityMatrix": report.get("runtimeCompatibilityMatrix"),
        "limitations": report.get("limitations") or [],
        "requiredDownstreamMetadata": {
            "consumeAdapt05Report": True,
            "nurionV1Modify": "DENY",
            "packagingAuthority": "ADAPT-06",
        },
        "policy": "ADAPT-05 does not package final adapted-character release",
    }
    handoff["handoffDigest"] = canonical_sha256({k: v for k, v in handoff.items() if k != "handoffDigest"})
    return handoff
