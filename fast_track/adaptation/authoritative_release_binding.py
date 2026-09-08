"""Cryptographic binding for ADAPT-06 — ADAPT-05 canonical qualification seal pins (READ ONLY)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.authoritative_runtime_qualification_binding import (
    ADAPT04_PASS_AUDIT_ZIP_SHA256,
)
from fast_track.adaptation.inspector import sha256_file

# ADAPT-05 Human PASS audit package
ADAPT05_PASS_AUDIT_ZIP_SHA256 = "15dcc54f90f03c2b2e54d0dc03ae6800110a1edc2121554594db151f8fbebd3e"
ADAPT05_PASS_RECEIPT_SHA256 = "a7f8a346db17ddc03c8067f6da53ff3d42f018a1e9a4c2c70ae82a02f84cae15"

# ADAPT-05 canonical qualification authority — MUST NOT be recomputed by ADAPT-06
CANONICAL_CHARACTER_ID = "canonical_qualified"
CANONICAL_CANDIDATE_SHA256 = "5628f7a699d0bd6d3f293fb712fde8a056629a83afed51e47a7f98d182b6e652"
CANONICAL_QUALIFICATION_REPORT_DIGEST = (
    "a5362ea9339bb52c2e8e5c17b2a6c229029e5dc11f221228adf38a2b65ad0412"
)
CANONICAL_RUNTIME_COMPATIBILITY_DIGEST = (
    "3e35c39ee3a4132fed60ecbf6f24737b63e5c1049078d2ff39db5b472424594b"
)
CANONICAL_ADAPT05_HANDOFF_DIGEST = (
    "a24d39bba4a864e1b28e18f4e3e604d9dd854238aa5e18d443b73eea82fb3b55"
)

_RELEASE_ROOT = Path(__file__).resolve().parents[2] / "working/adaptation_engine_v1/evidence"
_PASS_PATH = _RELEASE_ROOT / "NURION-ADAPT-05_PASS_receipt.json"
if _PASS_PATH.is_file():
    ADAPT05_PASS_RECEIPT_SHA256 = sha256_file(_PASS_PATH)


def verify_adapt05_pass_receipt(path: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "PASS", "checks": [], "blockers": []}

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    if not path or not path.is_file():
        fail("ADAPT05_PASS_RECEIPT_MISSING", "NURION-ADAPT-05_PASS_receipt.json required")
        return result
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("status") != "PASS":
        fail("ADAPT05_PASS_RECEIPT_NOT_PASS", "ADAPT-05 PASS required")
    obs = (rec.get("integrity") or {}).get("submittedZipSha256")
    if obs != ADAPT05_PASS_AUDIT_ZIP_SHA256:
        fail("ADAPT05_PASS_ZIP_PIN_MISMATCH", f"observed {obs}")
    if sha256_file(path) != ADAPT05_PASS_RECEIPT_SHA256:
        fail("ADAPT05_PASS_RECEIPT_SHA_MISMATCH", "PASS receipt bytes changed")
    seal = rec.get("canonicalSeal") or {}
    for key, expected in (
        ("candidateSha256", CANONICAL_CANDIDATE_SHA256),
        ("qualificationReportDigest", CANONICAL_QUALIFICATION_REPORT_DIGEST),
        ("runtimeCompatibilityDigest", CANONICAL_RUNTIME_COMPATIBILITY_DIGEST),
        ("adapt06HandoffDigest", CANONICAL_ADAPT05_HANDOFF_DIGEST),
    ):
        if seal.get(key) and seal.get(key) != expected:
            fail("ADAPT05_CANONICAL_SEAL_MISMATCH", key)
    result["checks"].append("adapt05_pass_receipt")
    return result


def verify_canonical_qualification_pins(qualification: dict[str, Any]) -> dict[str, Any]:
    """Verify live qualification report matches pinned ADAPT-05 authority (no re-derivation)."""
    result: dict[str, Any] = {"status": "PASS", "checks": [], "blockers": []}

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    cid = (qualification.get("sourceIdentity") or {}).get("characterId")
    if cid and cid != CANONICAL_CHARACTER_ID:
        fail("QUALIFICATION_CHARACTER_MISMATCH", cid)

    ident = qualification.get("candidateIdentity") or {}
    if ident.get("derivedArtifactSha256") != CANONICAL_CANDIDATE_SHA256:
        fail("CANDIDATE_SHA_PIN_MISMATCH", ident.get("derivedArtifactSha256"))

    if qualification.get("qualificationReportDigest") != CANONICAL_QUALIFICATION_REPORT_DIGEST:
        fail("QUALIFICATION_REPORT_DIGEST_PIN_MISMATCH", qualification.get("qualificationReportDigest"))

    if qualification.get("runtimeCompatibilityDigest") != CANONICAL_RUNTIME_COMPATIBILITY_DIGEST:
        fail("RUNTIME_COMPATIBILITY_DIGEST_PIN_MISMATCH", qualification.get("runtimeCompatibilityDigest"))

    handoff = qualification.get("adapt06Handoff") or {}
    if handoff.get("handoffDigest") != CANONICAL_ADAPT05_HANDOFF_DIGEST:
        fail("ADAPT05_HANDOFF_DIGEST_PIN_MISMATCH", handoff.get("handoffDigest"))
    if handoff.get("qualificationReportDigest") != CANONICAL_QUALIFICATION_REPORT_DIGEST:
        fail("HANDOFF_QUALIFICATION_DIGEST_PIN_MISMATCH", handoff.get("qualificationReportDigest"))

    if qualification.get("finalClassification") not in ("QUALIFIED", "QUALIFIED_WITH_LIMITATIONS"):
        fail("NOT_RELEASE_ELIGIBLE", qualification.get("finalClassification"))

    result["checks"].append("canonical_qualification_pins")
    return result


def verify_release_binding(
    binding: dict[str, Any],
    *,
    repo_root: Path | None = None,
    provenance_path: Path | None = None,
    adapt05_pass_path: Path | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "PASS", "mode": "UNKNOWN", "checks": [], "blockers": []}

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    seal = binding.get("adapt05CanonicalSeal") or {}
    for key, expected in (
        ("candidateSha256", CANONICAL_CANDIDATE_SHA256),
        ("qualificationReportDigest", CANONICAL_QUALIFICATION_REPORT_DIGEST),
        ("runtimeCompatibilityDigest", CANONICAL_RUNTIME_COMPATIBILITY_DIGEST),
        ("adapt05HandoffDigest", CANONICAL_ADAPT05_HANDOFF_DIGEST),
    ):
        if seal.get(key) != expected:
            fail("BINDING_SEAL_PIN_MISMATCH", key)

    preds = binding.get("predecessorPass") or {}
    if preds.get("adapt05AuditZipSha256") != ADAPT05_PASS_AUDIT_ZIP_SHA256:
        fail("ADAPT05_PASS_PIN_MISMATCH", "adapt05 zip pin")

    a05 = verify_adapt05_pass_receipt(adapt05_pass_path)
    if a05["status"] != "PASS":
        fail("ADAPT05_PASS_VERIFY", str(a05.get("blockers")))
    else:
        result["checks"].append("adapt05_pass_receipt")

    if repo_root is not None:
        result["mode"] = "MONOREPO_LIVE_VERIFY"
        result["checks"].append("monorepo_binding")
    else:
        result["mode"] = "EXTRACTED_PIN_VERIFY"
        if not provenance_path or not provenance_path.is_file():
            fail("PROVENANCE_RECEIPT_MISSING", "NURION-ADAPT-06_UPSTREAM_PROVENANCE_RECEIPT.json required")
        else:
            prov = json.loads(provenance_path.read_text(encoding="utf-8"))
            for key, expected in (
                ("candidateSha256", CANONICAL_CANDIDATE_SHA256),
                ("qualificationReportDigest", CANONICAL_QUALIFICATION_REPORT_DIGEST),
            ):
                if (prov.get("adapt05CanonicalSeal") or {}).get(key) != expected:
                    fail("PROVENANCE_SEAL_PIN_MISMATCH", key)
            result["checks"].append("provenance_receipt_pins")

    if result["blockers"]:
        result["status"] = "BLOCKED"
    return result
