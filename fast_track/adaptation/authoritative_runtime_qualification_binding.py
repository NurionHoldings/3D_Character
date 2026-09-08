"""Cryptographic binding for ADAPT-05 — ADAPT-04 PASS + PRODUCT-01…06 runtime authority pins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.authoritative_augmentation_binding import (
    ADAPT01_PASS_RECEIPT_SHA256,
    ADAPT02_PASS_AUDIT_ZIP_SHA256,
    ADAPT03_ATTACHMENT_DIGEST,
    ADAPT03_EYE_TALKING_DIGEST,
    ADAPT03_FACE_SEMANTIC_DIGEST,
    ADAPT03_PASS_AUDIT_ZIP_SHA256,
)
from fast_track.adaptation.authoritative_binding import (
    AUTHORITATIVE_AXIS_SHA256,
    AUTHORITATIVE_BODY_SPEC_SHA256,
)
from fast_track.adaptation.authoritative_face_binding import (
    AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256,
    AUTHORITATIVE_COMPOSITION_POLICY_SHA256,
    AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
    AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256,
    AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
    AUTHORITATIVE_NAMING_TABLE_SHA256,
)
from fast_track.adaptation.inspector import sha256_file

ADAPT04_PASS_AUDIT_ZIP_SHA256 = "dc1159c515772f4ebef3829785b6bdc6943700df0c8a7708e0ead8ac285cc5e0"
ADAPT04_PASS_RECEIPT_SHA256 = "7d00bbc1c247629359785a9757694f65eef46c8148f0395cbfe2bd3797a81122"
ADAPT04_AUGMENTATION_PLAN_DIGEST = "cf7cbf1e7866530d741f83a5e577b2cb197475af1c669bf6b35379caac203205"
ADAPT04_DERIVED_SEMANTIC_DIGEST = "2887aace941bb9a01adc30f124dae97266dc329c77b51430147f7d541da0d904"

PRODUCT01_ASSEMBLY_SHA256 = AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256
PRODUCT02_MOTION_LIBRARY_SHA256 = "37504c8c28545f7d486aba453cfc6afc66fe21f14500e8d2ac9be2affa56051f"
PRODUCT03_FACE_BODY_RUNTIME_SHA256 = AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256
PRODUCT04_ENTRANCE_STATE_SHA256 = "ad2199932100a990f9e0ad387852ff67856d9865b927d3983ff7da7301c545d7"
PRODUCT05_BEHAVIOR_RUNTIME_SHA256 = "5ae2e6c0169e51cecd8b9d2c7855d05add27738acf356ff0809e4addb3321a07"
PRODUCT06_RELEASE_BASELINE_SHA256 = "76741d7dd0df1748468c32ebbfaf174c00e401a4e375419d8f56cec46a7603ee"

PRODUCT_UPSTREAM_RELS = {
    "product01": "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json",
    "product02": "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT02_MOTION_LIBRARY_V1.json",
    "product03": "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT03_FACE_BODY_RUNTIME_V1.json",
    "product04": "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_V1.json",
    "product05": "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT05_CHARACTER_INTERACTION_BEHAVIOR_RUNTIME_V1.json",
    "product06": "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT06_PRODUCT_INTEGRATION_RELEASE_BASELINE_V1.json",
    "bodyCanonicalSpec": "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json",
    "axisRetargetConvention": "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json",
    "faceProductLock": "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json",
}

PRODUCT_PIN_MAP = {
    "product01": PRODUCT01_ASSEMBLY_SHA256,
    "product02": PRODUCT02_MOTION_LIBRARY_SHA256,
    "product03": PRODUCT03_FACE_BODY_RUNTIME_SHA256,
    "product04": PRODUCT04_ENTRANCE_STATE_SHA256,
    "product05": PRODUCT05_BEHAVIOR_RUNTIME_SHA256,
    "product06": PRODUCT06_RELEASE_BASELINE_SHA256,
    "bodyCanonicalSpec": AUTHORITATIVE_BODY_SPEC_SHA256,
    "axisRetargetConvention": AUTHORITATIVE_AXIS_SHA256,
    "faceProductLock": AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
}


def verify_adapt04_pass_receipt(path: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "PASS", "checks": [], "blockers": []}

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    if not path or not path.is_file():
        fail("ADAPT04_PASS_RECEIPT_MISSING", "NURION-ADAPT-04_PASS_receipt.json required")
        return result
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("status") != "PASS" or rec.get("technicalVerdict") != "PASS":
        fail("ADAPT04_PASS_RECEIPT_NOT_PASS", "ADAPT-04 PASS required")
    obs = (rec.get("integrity") or {}).get("submittedZipSha256")
    if obs != ADAPT04_PASS_AUDIT_ZIP_SHA256:
        fail("ADAPT04_PASS_ZIP_PIN_MISMATCH", f"observed {obs}")
    if sha256_file(path) != ADAPT04_PASS_RECEIPT_SHA256:
        fail("ADAPT04_PASS_RECEIPT_SHA_MISMATCH", "PASS receipt bytes changed")
    result["checks"].append("adapt04_pass_receipt")
    return result


def verify_runtime_qualification_binding(
    binding: dict[str, Any],
    *,
    repo_root: Path | None = None,
    provenance_path: Path | None = None,
    adapt01_pass_path: Path | None = None,
    adapt02_pass_path: Path | None = None,
    adapt03_pass_path: Path | None = None,
    adapt04_pass_path: Path | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "PASS", "mode": "UNKNOWN", "checks": [], "blockers": []}

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    preds = binding.get("predecessorPass") or {}
    if preds.get("adapt04AuditZipSha256") != ADAPT04_PASS_AUDIT_ZIP_SHA256:
        fail("ADAPT04_PASS_PIN_MISMATCH", "adapt04 zip pin")
    if preds.get("adapt03AuditZipSha256") != ADAPT03_PASS_AUDIT_ZIP_SHA256:
        fail("ADAPT03_PASS_PIN_MISMATCH", "adapt03 zip pin")
    if preds.get("adapt02AuditZipSha256") != ADAPT02_PASS_AUDIT_ZIP_SHA256:
        fail("ADAPT02_PASS_PIN_MISMATCH", "adapt02 zip pin")

    rt = binding.get("runtimeAuthorityPins") or {}
    for key, expected in PRODUCT_PIN_MAP.items():
        pin_key = _pin_key(key)
        if rt.get(pin_key) != expected:
            fail("RUNTIME_AUTHORITY_PIN_MISMATCH", pin_key)

    face = binding.get("faceAuthorityPins") or {}
    for k, expected in (
        ("faceProductLockSha256", AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256),
        ("namingTableSha256", AUTHORITATIVE_NAMING_TABLE_SHA256),
        ("compositionPolicySha256", AUTHORITATIVE_COMPOSITION_POLICY_SHA256),
        ("faceBodyRuntimeSha256", AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256),
        ("assemblyBaselineSha256", AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256),
        ("eyeCalibrationFingerprintSha256", AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT),
    ):
        if face.get(k) != expected:
            fail("FACE_AUTHORITY_PIN_MISMATCH", k)

    snap = binding.get("adapt03SnapshotDigests") or {}
    for k, expected in (
        ("faceSemanticDigest", ADAPT03_FACE_SEMANTIC_DIGEST),
        ("attachmentDigest", ADAPT03_ATTACHMENT_DIGEST),
        ("eyeTalkingDigest", ADAPT03_EYE_TALKING_DIGEST),
    ):
        if snap.get(k) != expected:
            fail("ADAPT03_SNAPSHOT_DIGEST_MISMATCH", k)

    a04 = verify_adapt04_pass_receipt(adapt04_pass_path)
    if a04["status"] != "PASS":
        fail("ADAPT04_PASS_VERIFY", str(a04.get("blockers")))
    else:
        result["checks"].append("adapt04_pass_receipt")

    for label, path, expected_zip in (
        ("ADAPT-01", adapt01_pass_path, ADAPT01_PASS_RECEIPT_SHA256),
        ("ADAPT-02", adapt02_pass_path, ADAPT02_PASS_AUDIT_ZIP_SHA256),
        ("ADAPT-03", adapt03_pass_path, ADAPT03_PASS_AUDIT_ZIP_SHA256),
    ):
        if not path or not path.is_file():
            fail("PASS_RECEIPT_MISSING", label)
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("status") != "PASS":
            fail("PASS_RECEIPT_NOT_PASS", label)
        obs = (rec.get("integrity") or {}).get("submittedZipSha256") or rec.get("authoritativeAuditZipSha256")
        if obs != expected_zip:
            fail("PASS_RECEIPT_ZIP_PIN_MISMATCH", label)
        result["checks"].append(f"{label}_pass_receipt")

    if repo_root is not None:
        result["mode"] = "MONOREPO_LIVE_VERIFY"
        for key, rel in PRODUCT_UPSTREAM_RELS.items():
            p = Path(repo_root) / rel
            if not p.is_file():
                fail("UPSTREAM_AUTHORITY_MISSING", key)
                continue
            if sha256_file(p) != PRODUCT_PIN_MAP[key]:
                fail("UPSTREAM_AUTHORITY_SHA_MISMATCH", key)
            result["checks"].append(f"live_{key}")
    else:
        result["mode"] = "EXTRACTED_PIN_VERIFY"
        if not provenance_path or not provenance_path.is_file():
            fail(
                "PROVENANCE_RECEIPT_MISSING",
                "NURION-ADAPT-05_UPSTREAM_PROVENANCE_RECEIPT.json required",
            )
        else:
            prov = json.loads(provenance_path.read_text(encoding="utf-8"))
            for key, expected in PRODUCT_PIN_MAP.items():
                obs = (prov.get("runtimeAuthorityPins") or {}).get(_pin_key(key))
                if obs != expected:
                    fail("PROVENANCE_PIN_MISMATCH", key)
            result["checks"].append("provenance_receipt_pins")

    if result["blockers"]:
        result["status"] = "BLOCKED"
    return result


def _pin_key(key: str) -> str:
    mapping = {
        "product01": "product01AssemblySha256",
        "product02": "product02MotionLibrarySha256",
        "product03": "product03FaceBodyRuntimeSha256",
        "product04": "product04EntranceStateSha256",
        "product05": "product05BehaviorRuntimeSha256",
        "product06": "product06ReleaseBaselineSha256",
        "bodyCanonicalSpec": "bodyCanonicalSpecSha256",
        "axisRetargetConvention": "axisRetargetConventionSha256",
        "faceProductLock": "faceProductLockSha256",
    }
    return mapping.get(key, key)
