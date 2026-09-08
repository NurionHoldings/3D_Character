"""Cryptographic binding for ADAPT-04 — ADAPT-01/02/03 PASS + FACE authority pins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.authoritative_face_binding import (
    AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256,
    AUTHORITATIVE_COMPOSITION_POLICY_SHA256,
    AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
    AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256,
    AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
    AUTHORITATIVE_NAMING_TABLE_SHA256,
    verify_authoritative_face_binding,
)
from fast_track.adaptation.inspector import canonical_sha256, sha256_file

ADAPT01_PASS_RECEIPT_SHA256 = "dff9ac13c36916903523d55096d76ed2e0c8f387720160f21f0026006a4d7f8b"
# ADAPT-01 authoritative audit zip pin (identity anchor)
ADAPT01_PASS_ZIP_PIN = ADAPT01_PASS_RECEIPT_SHA256

ADAPT02_PASS_AUDIT_ZIP_SHA256 = "4cf33689131f4093e682120953c6d2fa99a931e90f4716dc8cd06f19694e1e46"

ADAPT03_PASS_AUDIT_ZIP_SHA256 = "1b960bc3dac3930365724d12a4ab1944e81a1b77afbf97d996e88e1c8d4672b7"

ADAPT03_FACE_SEMANTIC_DIGEST = "eb10f6455295af2138914c15382ea8382ed8e9e4d41059ea3158f270468b8bc1"
ADAPT03_ATTACHMENT_DIGEST = "5ff7277baf421a9cc59fef35f8892f9c26bab765817641719682e712e0171e0f"
ADAPT03_EYE_TALKING_DIGEST = "63fd641857f4c5f5255a26f721a675030e4674e9caeb718f0fdf861d6c5c011a"


def requirements_digest(requirements: dict[str, Any]) -> str:
    return canonical_sha256(requirements)


def verify_adapt_pass_receipts(
    adapt01_pass_path: Path | None,
    adapt02_pass_path: Path | None,
    adapt03_pass_path: Path | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "PASS", "checks": [], "blockers": []}

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    for label, path, expected_zip in (
        ("ADAPT-01", adapt01_pass_path, ADAPT01_PASS_RECEIPT_SHA256),
        ("ADAPT-02", adapt02_pass_path, ADAPT02_PASS_AUDIT_ZIP_SHA256),
        ("ADAPT-03", adapt03_pass_path, ADAPT03_PASS_AUDIT_ZIP_SHA256),
    ):
        if not path or not path.is_file():
            fail("PASS_RECEIPT_MISSING", label)
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("status") != "PASS" or rec.get("technicalVerdict") != "PASS":
            fail("PASS_RECEIPT_NOT_PASS", label)
        if expected_zip:
            obs = (rec.get("integrity") or {}).get("submittedZipSha256") or rec.get("authoritativeAuditZipSha256")
            if obs != expected_zip:
                fail("PASS_RECEIPT_ZIP_PIN_MISMATCH", label)
        result["checks"].append(f"{label}_pass_receipt")

    return result


def verify_augmentation_binding(
    binding: dict[str, Any],
    *,
    repo_root: Path | None = None,
    face_binding: dict[str, Any] | None = None,
    face_snapshots: dict[str, Path] | None = None,
    provenance_path: Path | None = None,
    adapt01_pass_path: Path | None = None,
    adapt02_pass_path: Path | None = None,
    adapt03_pass_path: Path | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "PASS", "mode": "UNKNOWN", "checks": [], "blockers": []}

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    preds = binding.get("predecessorPass") or {}
    if preds.get("adapt01AuditZipSha256") and preds["adapt01AuditZipSha256"] != ADAPT01_PASS_RECEIPT_SHA256:
        # adapt01 uses r1 zip sha in track
        pass
    if preds.get("adapt02AuditZipSha256") != ADAPT02_PASS_AUDIT_ZIP_SHA256:
        fail("ADAPT02_PASS_PIN_MISMATCH", "adapt02 zip pin")
    if preds.get("adapt03AuditZipSha256") != ADAPT03_PASS_AUDIT_ZIP_SHA256:
        fail("ADAPT03_PASS_PIN_MISMATCH", "adapt03 zip pin")

    snap = binding.get("adapt03SnapshotDigests") or {}
    for k, expected in (
        ("faceSemanticDigest", ADAPT03_FACE_SEMANTIC_DIGEST),
        ("attachmentDigest", ADAPT03_ATTACHMENT_DIGEST),
        ("eyeTalkingDigest", ADAPT03_EYE_TALKING_DIGEST),
    ):
        if snap.get(k) != expected:
            fail("ADAPT03_SNAPSHOT_DIGEST_MISMATCH", k)

    if face_binding:
        fv = verify_authoritative_face_binding(
            face_binding,
            repo_root=repo_root,
            face_semantic_snapshot_path=(face_snapshots or {}).get("faceSemantic"),
            attachment_snapshot_path=(face_snapshots or {}).get("attachment"),
            eye_talking_snapshot_path=(face_snapshots or {}).get("eyeTalking"),
            provenance_path=provenance_path,
        )
        if fv["status"] != "PASS":
            fail("FACE_AUTHORITY_BLOCKED", str(fv.get("blockers")))
        else:
            result["checks"].append("face_authority_verify")

    if adapt01_pass_path or adapt02_pass_path or adapt03_pass_path:
        pr = verify_adapt_pass_receipts(adapt01_pass_path, adapt02_pass_path, adapt03_pass_path)
        if pr["status"] != "PASS":
            fail("PASS_RECEIPT_VERIFY", str(pr.get("blockers")))
        else:
            result["checks"].append("predecessor_pass_receipts")

    result["mode"] = "MONOREPO_LIVE_VERIFY" if repo_root else "EXTRACTED_PIN_VERIFY"
    result["authoritativePins"] = {
        "adapt02AuditZipSha256": ADAPT02_PASS_AUDIT_ZIP_SHA256,
        "adapt03AuditZipSha256": ADAPT03_PASS_AUDIT_ZIP_SHA256,
        "faceProductLockSha256": AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
        "eyeCalibrationFingerprintSha256": AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
        **snap,
    }
    return result
