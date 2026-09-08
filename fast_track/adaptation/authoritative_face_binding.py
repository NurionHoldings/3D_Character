"""Cryptographic upstream binding for ADAPT-03 — pins locked NURION FACE authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.inspector import canonical_sha256

AUTHORITATIVE_FACE_PRODUCT_LOCK_ID = "NURION_FACE_PRODUCT_LOCK_V1"
AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256 = (
    "07830e1c34ce79b1d9ff9fc15a8b456ef7e3438d05ae7709d3515c00baebcf06"
)
AUTHORITATIVE_FACE_PRODUCT_LOCK_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json"
)

AUTHORITATIVE_NAMING_TABLE_ID = "NURION_FACE_CANONICAL_V1_NAMING_TABLE"
AUTHORITATIVE_NAMING_TABLE_SHA256 = (
    "61995e5c47b1c25d17cdf8733a8d23b87a7faae667dc5724ad3ea2372fe15187"
)
AUTHORITATIVE_NAMING_TABLE_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_CANONICAL_V1_NAMING_TABLE.json"
)

AUTHORITATIVE_COMPOSITION_POLICY_ID = "NURION_FACE_COMPOSITION_POLICY_V1"
AUTHORITATIVE_COMPOSITION_POLICY_SHA256 = (
    "da5b7399cc291dcf1f00fbc35052f5f69215862c26a5cf7d77c465a6778f51d3"
)
AUTHORITATIVE_COMPOSITION_POLICY_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_COMPOSITION_POLICY_V1.json"
)

AUTHORITATIVE_FACE_BODY_RUNTIME_ID = "NURION_PRODUCT03_FACE_BODY_RUNTIME_V1"
AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256 = (
    "917d640f10946e4b77fe5dafa8f6c649e36b95198361024fe4514c69d05f0fef"
)
AUTHORITATIVE_FACE_BODY_RUNTIME_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT03_FACE_BODY_RUNTIME_V1.json"
)

AUTHORITATIVE_ASSEMBLY_BASELINE_ID = "NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1"
AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256 = (
    "1a38586905d155053f7eff6a625bb3497a2a17235892017e4ad277ce06c14605"
)
AUTHORITATIVE_ASSEMBLY_BASELINE_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"
)

AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT = (
    "2d1dbb6772cd74c2a7dc991cf497d58dc5b803359f5430105dbe4ff9e513ff19"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_digest(snapshot: dict[str, Any]) -> str:
    return canonical_sha256(snapshot)


def extract_face_semantic_snapshot(naming_table: dict[str, Any], composition: dict[str, Any]) -> dict[str, Any]:
    essential = [
        r["nurionCanonical"]
        for r in naming_table.get("rows") or []
        if r.get("tier") == "ESSENTIAL_V1" and r.get("nurionCanonical")
    ]
    return {
        "schema": "NURION_ADAPT03_FACE_SEMANTIC_SNAPSHOT_V1",
        "sourceIdentity": AUTHORITATIVE_NAMING_TABLE_ID,
        "canonicalContract": "NURION_FACE_CANONICAL_V1",
        "essentialExpressions": sorted(essential),
        "essentialCount": len(essential),
        "expressionOwned": list(composition.get("expressionOwned") or []),
        "speechOwned": list(composition.get("speechOwned") or []),
        "smileFrown": list(composition.get("smileFrown") or []),
        "legacyAdapterContract": dict(naming_table.get("legacyAdapterContract") or {}),
    }


def extract_attachment_snapshot(runtime: dict[str, Any], assembly: dict[str, Any]) -> dict[str, Any]:
    iface = runtime.get("faceBodyInterface") or {}
    binding = iface.get("binding") or {}
    asm_iface = (assembly.get("faceBodyInterface") or {}).get("binding") or {}
    return {
        "schema": "NURION_ADAPT03_ATTACHMENT_SNAPSHOT_V1",
        "sourceIdentity": AUTHORITATIVE_FACE_BODY_RUNTIME_ID,
        "parent": binding.get("parent") or "NURION_head",
        "child": binding.get("child") or "FACE_Rig_Root",
        "type": binding.get("type") or "SOLE_ATTACHMENT",
        "assemblyBaselineParent": asm_iface.get("parent") or "NURION_head",
        "assemblyBaselineChild": asm_iface.get("child") or "FACE_Rig_Root",
        "crossBoundaryOwnershipCollision": iface.get("crossBoundaryOwnershipCollision") or "DENY",
    }


def extract_eye_talking_snapshot(runtime: dict[str, Any], product_lock: dict[str, Any]) -> dict[str, Any]:
    eye = runtime.get("eyePreservation") or {}
    talking = runtime.get("talkingCompatibility") or {}
    return {
        "schema": "NURION_ADAPT03_EYE_TALKING_SNAPSHOT_V1",
        "sourceIdentity": AUTHORITATIVE_FACE_BODY_RUNTIME_ID,
        "eyeCalibrationFingerprintSha256": eye.get("calibrationFingerprintSha256")
        or AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
        "eyeChannels": list(eye.get("channels") or []),
        "talkingStatus": talking.get("talking_status") or product_lock.get("talking_status") or "GO",
        "faceLockUnmutated": talking.get("faceLockUnmutated", True),
        "coplayPassCount": sum(1 for c in talking.get("coplay") or [] if c.get("status") == "PASS"),
    }


def derive_from_upstream_files(
    product_lock_path: Path,
    naming_path: Path,
    composition_path: Path,
    runtime_path: Path,
    assembly_path: Path,
) -> dict[str, Any]:
    paths = {
        "faceProductLock": product_lock_path,
        "namingTable": naming_path,
        "compositionPolicy": composition_path,
        "faceBodyRuntime": runtime_path,
        "assemblyBaseline": assembly_path,
    }
    pins = {
        "faceProductLock": (AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256, AUTHORITATIVE_FACE_PRODUCT_LOCK_ID),
        "namingTable": (AUTHORITATIVE_NAMING_TABLE_SHA256, AUTHORITATIVE_NAMING_TABLE_ID),
        "compositionPolicy": (AUTHORITATIVE_COMPOSITION_POLICY_SHA256, AUTHORITATIVE_COMPOSITION_POLICY_ID),
        "faceBodyRuntime": (AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256, AUTHORITATIVE_FACE_BODY_RUNTIME_ID),
        "assemblyBaseline": (AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256, AUTHORITATIVE_ASSEMBLY_BASELINE_ID),
    }
    observed: dict[str, str] = {}
    for key, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing authoritative FACE upstream: {path}")
        obs = sha256_file(path)
        expected, ident = pins[key]
        if obs != expected:
            raise ValueError(f"{ident} SHA256 mismatch: observed {obs} != pinned {expected}")
        observed[key] = obs

    product_lock = json.loads(product_lock_path.read_text(encoding="utf-8"))
    naming_table = json.loads(naming_path.read_text(encoding="utf-8"))
    composition = json.loads(composition_path.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    assembly = json.loads(assembly_path.read_text(encoding="utf-8"))

    face_sem = extract_face_semantic_snapshot(naming_table, composition)
    attach = extract_attachment_snapshot(runtime, assembly)
    eye_talk = extract_eye_talking_snapshot(runtime, product_lock)

    return {
        "upstream": {
            "faceProductLock": {
                "identity": AUTHORITATIVE_FACE_PRODUCT_LOCK_ID,
                "sha256": AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
                "repoRel": AUTHORITATIVE_FACE_PRODUCT_LOCK_REL,
            },
            "namingTable": {
                "identity": AUTHORITATIVE_NAMING_TABLE_ID,
                "sha256": AUTHORITATIVE_NAMING_TABLE_SHA256,
                "repoRel": AUTHORITATIVE_NAMING_TABLE_REL,
            },
            "compositionPolicy": {
                "identity": AUTHORITATIVE_COMPOSITION_POLICY_ID,
                "sha256": AUTHORITATIVE_COMPOSITION_POLICY_SHA256,
                "repoRel": AUTHORITATIVE_COMPOSITION_POLICY_REL,
            },
            "faceBodyRuntime": {
                "identity": AUTHORITATIVE_FACE_BODY_RUNTIME_ID,
                "sha256": AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256,
                "repoRel": AUTHORITATIVE_FACE_BODY_RUNTIME_REL,
            },
            "assemblyBaseline": {
                "identity": AUTHORITATIVE_ASSEMBLY_BASELINE_ID,
                "sha256": AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256,
                "repoRel": AUTHORITATIVE_ASSEMBLY_BASELINE_REL,
            },
        },
        "snapshot": {
            "derivation": "READ_ONLY_EXTRACT",
            "faceSemanticSnapshotFile": "semantic/NURION_ADAPT03_FACE_SEMANTIC_SNAPSHOT_V1.json",
            "attachmentSnapshotFile": "semantic/NURION_ADAPT03_ATTACHMENT_SNAPSHOT_V1.json",
            "eyeTalkingSnapshotFile": "semantic/NURION_ADAPT03_EYE_TALKING_SNAPSHOT_V1.json",
            "faceSemanticDigest": snapshot_digest(face_sem),
            "attachmentDigest": snapshot_digest(attach),
            "eyeTalkingDigest": snapshot_digest(eye_talk),
        },
        "faceSemanticSnapshot": face_sem,
        "attachmentSnapshot": attach,
        "eyeTalkingSnapshot": eye_talk,
        "observedUpstreamSha256": observed,
    }


def verify_authoritative_face_binding(
    binding: dict[str, Any],
    *,
    repo_root: Path | None = None,
    face_semantic_snapshot_path: Path | None = None,
    attachment_snapshot_path: Path | None = None,
    eye_talking_snapshot_path: Path | None = None,
    provenance_path: Path | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "PASS", "mode": "UNKNOWN", "checks": [], "blockers": []}

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    upstream = binding.get("upstream") or {}
    snap_meta = binding.get("snapshot") or {}

    pin_checks = [
        ("faceProductLock", AUTHORITATIVE_FACE_PRODUCT_LOCK_ID, AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256),
        ("namingTable", AUTHORITATIVE_NAMING_TABLE_ID, AUTHORITATIVE_NAMING_TABLE_SHA256),
        ("compositionPolicy", AUTHORITATIVE_COMPOSITION_POLICY_ID, AUTHORITATIVE_COMPOSITION_POLICY_SHA256),
        ("faceBodyRuntime", AUTHORITATIVE_FACE_BODY_RUNTIME_ID, AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256),
        ("assemblyBaseline", AUTHORITATIVE_ASSEMBLY_BASELINE_ID, AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256),
    ]
    for key, ident, sha in pin_checks:
        block = upstream.get(key) or {}
        if block.get("identity") != ident:
            fail("UPSTREAM_IDENTITY_MISMATCH", key)
        if block.get("sha256") != sha:
            fail("UPSTREAM_SHA256_PIN_MISMATCH", key)
    result["checks"].append("pinned_upstream_identities")

    expected = {
        "faceSemanticDigest": snap_meta.get("faceSemanticDigest"),
        "attachmentDigest": snap_meta.get("attachmentDigest"),
        "eyeTalkingDigest": snap_meta.get("eyeTalkingDigest"),
    }
    if not all(expected.values()):
        fail("SNAPSHOT_DIGEST_MISSING", "binding.snapshot digests required")
        return result

    face_snap = (
        json.loads(face_semantic_snapshot_path.read_text(encoding="utf-8"))
        if face_semantic_snapshot_path and face_semantic_snapshot_path.is_file()
        else None
    )
    attach_snap = (
        json.loads(attachment_snapshot_path.read_text(encoding="utf-8"))
        if attachment_snapshot_path and attachment_snapshot_path.is_file()
        else None
    )
    eye_snap = (
        json.loads(eye_talking_snapshot_path.read_text(encoding="utf-8"))
        if eye_talking_snapshot_path and eye_talking_snapshot_path.is_file()
        else None
    )

    if face_snap:
        obs = snapshot_digest(face_snap)
        if obs != expected["faceSemanticDigest"]:
            fail("FACE_SEMANTIC_SNAPSHOT_DIGEST_MISMATCH", obs)
        else:
            result["checks"].append("face_semantic_snapshot_digest")
    if attach_snap:
        obs = snapshot_digest(attach_snap)
        if obs != expected["attachmentDigest"]:
            fail("ATTACHMENT_SNAPSHOT_DIGEST_MISMATCH", obs)
        else:
            result["checks"].append("attachment_snapshot_digest")
    if eye_snap:
        obs = snapshot_digest(eye_snap)
        if obs != expected["eyeTalkingDigest"]:
            fail("EYE_TALKING_SNAPSHOT_DIGEST_MISMATCH", obs)
        else:
            result["checks"].append("eye_talking_snapshot_digest")

    attach_binding = binding.get("faceBodyAttachment") or {}
    if attach_snap:
        if attach_binding.get("parent") != attach_snap.get("parent"):
            fail("BINDING_ATTACHMENT_PARENT_MISMATCH", "parent")
        if attach_binding.get("child") != attach_snap.get("child"):
            fail("BINDING_ATTACHMENT_CHILD_MISMATCH", "child")
        elif result["status"] == "PASS":
            result["checks"].append("binding_attachment_semantic_link")

    if eye_snap and binding.get("eyeCalibrationFingerprintSha256"):
        if binding["eyeCalibrationFingerprintSha256"] != eye_snap.get("eyeCalibrationFingerprintSha256"):
            fail("BINDING_EYE_FINGERPRINT_MISMATCH", "eye fingerprint")
        elif result["status"] == "PASS":
            result["checks"].append("binding_eye_fingerprint_link")

    if repo_root is not None:
        result["mode"] = "MONOREPO_LIVE_VERIFY"
        try:
            derived = derive_from_upstream_files(
                repo_root / AUTHORITATIVE_FACE_PRODUCT_LOCK_REL,
                repo_root / AUTHORITATIVE_NAMING_TABLE_REL,
                repo_root / AUTHORITATIVE_COMPOSITION_POLICY_REL,
                repo_root / AUTHORITATIVE_FACE_BODY_RUNTIME_REL,
                repo_root / AUTHORITATIVE_ASSEMBLY_BASELINE_REL,
            )
            for dk in ("faceSemanticDigest", "attachmentDigest", "eyeTalkingDigest"):
                if derived["snapshot"][dk] != expected[dk]:
                    fail("LIVE_DERIVATION_MISMATCH", dk)
            if result["status"] == "PASS":
                result["checks"].append("monorepo_live_upstream_match")
        except (ValueError, KeyError, FileNotFoundError) as e:
            fail("LIVE_DERIVATION_FAILED", str(e))
    else:
        result["mode"] = "EXTRACTED_PIN_VERIFY"
        if not face_snap or not attach_snap or not eye_snap:
            fail("SNAPSHOT_FILES_REQUIRED", "extracted package must include snapshot JSON files")
        if provenance_path and provenance_path.is_file():
            prov = json.loads(provenance_path.read_text(encoding="utf-8"))
            for key, sha in [
                ("faceProductLock", AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256),
                ("namingTable", AUTHORITATIVE_NAMING_TABLE_SHA256),
                ("faceBodyRuntime", AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256),
            ]:
                if prov.get("upstream", {}).get(key, {}).get("sha256") != sha:
                    fail("PROVENANCE_PIN_MISMATCH", key)
            for dk in ("faceSemanticDigest", "attachmentDigest", "eyeTalkingDigest"):
                if prov.get("snapshot", {}).get(dk) != expected[dk]:
                    fail("PROVENANCE_DIGEST_MISMATCH", dk)
            if result["status"] == "PASS":
                result["checks"].append("provenance_receipt_pins")
        else:
            fail("PROVENANCE_RECEIPT_MISSING", "NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json required")

    result["authoritativePins"] = {
        "faceProductLockSha256": AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
        "namingTableSha256": AUTHORITATIVE_NAMING_TABLE_SHA256,
        "compositionPolicySha256": AUTHORITATIVE_COMPOSITION_POLICY_SHA256,
        "faceBodyRuntimeSha256": AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256,
        "assemblyBaselineSha256": AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256,
        "eyeCalibrationFingerprintSha256": AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
        **expected,
    }
    return result
