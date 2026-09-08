#!/usr/bin/env python3
"""Generate ADAPT-05 authoritative runtime binding + provenance receipt."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.authoritative_augmentation_binding import (
    ADAPT01_PASS_RECEIPT_SHA256,
    ADAPT02_PASS_AUDIT_ZIP_SHA256,
    ADAPT03_ATTACHMENT_DIGEST,
    ADAPT03_EYE_TALKING_DIGEST,
    ADAPT03_FACE_SEMANTIC_DIGEST,
    ADAPT03_PASS_AUDIT_ZIP_SHA256,
)
from fast_track.adaptation.authoritative_face_binding import (
    AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256,
    AUTHORITATIVE_COMPOSITION_POLICY_SHA256,
    AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
    AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256,
    AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
    AUTHORITATIVE_NAMING_TABLE_SHA256,
)
from fast_track.adaptation.authoritative_runtime_qualification_binding import (
    ADAPT04_AUGMENTATION_PLAN_DIGEST,
    ADAPT04_DERIVED_SEMANTIC_DIGEST,
    ADAPT04_PASS_AUDIT_ZIP_SHA256,
    ADAPT04_PASS_RECEIPT_SHA256,
    AUTHORITATIVE_AXIS_SHA256,
    AUTHORITATIVE_BODY_SPEC_SHA256,
    PRODUCT01_ASSEMBLY_SHA256,
    PRODUCT02_MOTION_LIBRARY_SHA256,
    PRODUCT03_FACE_BODY_RUNTIME_SHA256,
    PRODUCT04_ENTRANCE_STATE_SHA256,
    PRODUCT05_BEHAVIOR_RUNTIME_SHA256,
    PRODUCT06_RELEASE_BASELINE_SHA256,
)
from fast_track.adaptation.inspector import sha256_file

SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
EV = ROOT / "fast_track/working/adaptation_engine_v1/evidence"


def main() -> None:
    binding = {
        "schema": "NURION_ADAPT05_RUNTIME_AUTHORITY_BINDING_V1",
        "revision": "R1",
        "role": "CONSUME_ONLY cryptographically pinned ADAPT-01…04 PASS + PRODUCT-01…06 runtime authority",
        "predecessorPass": {
            "adapt01Status": "CLOSED / PASS / CONSUME ONLY",
            "adapt01AuditZipSha256": ADAPT01_PASS_RECEIPT_SHA256,
            "adapt01PassReceipt": "evidence/NURION-ADAPT-01_PASS_receipt.json",
            "adapt02Status": "CLOSED / PASS / CONSUME ONLY",
            "adapt02AuditZipSha256": ADAPT02_PASS_AUDIT_ZIP_SHA256,
            "adapt02PassReceipt": "evidence/NURION-ADAPT-02_PASS_receipt.json",
            "adapt03Status": "CLOSED / PASS / CONSUME ONLY",
            "adapt03AuditZipSha256": ADAPT03_PASS_AUDIT_ZIP_SHA256,
            "adapt03PassReceipt": "evidence/NURION-ADAPT-03_PASS_receipt.json",
            "adapt04Status": "CLOSED / PASS / CONSUME ONLY",
            "adapt04AuditZipSha256": ADAPT04_PASS_AUDIT_ZIP_SHA256,
            "adapt04PassReceipt": "evidence/NURION-ADAPT-04_PASS_receipt.json",
            "adapt04PassReceiptSha256": ADAPT04_PASS_RECEIPT_SHA256,
        },
        "adapt04CandidateProvenance": {
            "augmentationPlanDigest": ADAPT04_AUGMENTATION_PLAN_DIGEST,
            "derivedSemanticDigest": ADAPT04_DERIVED_SEMANTIC_DIGEST,
        },
        "adapt03SnapshotDigests": {
            "faceSemanticDigest": ADAPT03_FACE_SEMANTIC_DIGEST,
            "attachmentDigest": ADAPT03_ATTACHMENT_DIGEST,
            "eyeTalkingDigest": ADAPT03_EYE_TALKING_DIGEST,
        },
        "runtimeAuthorityPins": {
            "product01AssemblySha256": PRODUCT01_ASSEMBLY_SHA256,
            "product02MotionLibrarySha256": PRODUCT02_MOTION_LIBRARY_SHA256,
            "product03FaceBodyRuntimeSha256": PRODUCT03_FACE_BODY_RUNTIME_SHA256,
            "product04EntranceStateSha256": PRODUCT04_ENTRANCE_STATE_SHA256,
            "product05BehaviorRuntimeSha256": PRODUCT05_BEHAVIOR_RUNTIME_SHA256,
            "product06ReleaseBaselineSha256": PRODUCT06_RELEASE_BASELINE_SHA256,
            "bodyCanonicalSpecSha256": AUTHORITATIVE_BODY_SPEC_SHA256,
            "axisRetargetConventionSha256": AUTHORITATIVE_AXIS_SHA256,
            "faceProductLockSha256": AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
        },
        "faceAuthorityPins": {
            "faceProductLockSha256": AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
            "namingTableSha256": AUTHORITATIVE_NAMING_TABLE_SHA256,
            "compositionPolicySha256": AUTHORITATIVE_COMPOSITION_POLICY_SHA256,
            "faceBodyRuntimeSha256": AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256,
            "assemblyBaselineSha256": AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256,
            "eyeCalibrationFingerprintSha256": AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
        },
        "faceBodyAttachment": {
            "parent": "NURION_head",
            "child": "FACE_Rig_Root",
            "type": "SOLE_ATTACHMENT",
        },
        "invariants": {
            "qualificationOnly": True,
            "autoRepair": "DENY",
            "candidateMutation": "DENY",
            "adapt06Implementation": "NOT_STARTED",
            "nurionV1Modify": "DENY",
        },
    }
    binding_path = SEM / "NURION_ADAPT05_RUNTIME_AUTHORITY_BINDING_V1.json"
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    provenance = {
        "schema": "NURION_ADAPT05_UPSTREAM_PROVENANCE_RECEIPT_V1",
        "revision": "R1",
        "derivation": "READ_ONLY_CONSUME",
        "generatedFromMonorepo": True,
        "predecessorPass": binding["predecessorPass"],
        "adapt04CandidateProvenance": binding["adapt04CandidateProvenance"],
        "adapt03SnapshotDigests": binding["adapt03SnapshotDigests"],
        "runtimeAuthorityPins": binding["runtimeAuthorityPins"],
        "faceAuthorityPins": binding["faceAuthorityPins"],
        "bindingSha256": sha256_file(binding_path),
        "policy": "ADAPT-05 qualifies only; unpinned required authority = FAIL CLOSED",
        "nurionV1Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
        "adapt03Mutation": "NONE",
        "adapt04Mutation": "NONE",
        "autoRepair": "DENY",
    }
    prov_path = EV / "NURION-ADAPT-05_UPSTREAM_PROVENANCE_RECEIPT.json"
    prov_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "binding": str(binding_path), "provenance": str(prov_path)}, indent=2))


if __name__ == "__main__":
    main()
