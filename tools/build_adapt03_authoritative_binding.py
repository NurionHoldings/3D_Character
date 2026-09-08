#!/usr/bin/env python3
"""Generate ADAPT-03 authoritative FACE binding + snapshots + provenance receipt."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.authoritative_face_binding import (
    AUTHORITATIVE_ASSEMBLY_BASELINE_REL,
    AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256,
    AUTHORITATIVE_COMPOSITION_POLICY_REL,
    AUTHORITATIVE_COMPOSITION_POLICY_SHA256,
    AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
    AUTHORITATIVE_FACE_BODY_RUNTIME_REL,
    AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256,
    AUTHORITATIVE_FACE_PRODUCT_LOCK_REL,
    AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
    AUTHORITATIVE_NAMING_TABLE_REL,
    AUTHORITATIVE_NAMING_TABLE_SHA256,
    derive_from_upstream_files,
)
from fast_track.adaptation.inspector import sha256_file

SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
EV = ROOT / "fast_track/working/adaptation_engine_v1/evidence"


def main() -> None:
    derived = derive_from_upstream_files(
        ROOT / AUTHORITATIVE_FACE_PRODUCT_LOCK_REL,
        ROOT / AUTHORITATIVE_NAMING_TABLE_REL,
        ROOT / AUTHORITATIVE_COMPOSITION_POLICY_REL,
        ROOT / AUTHORITATIVE_FACE_BODY_RUNTIME_REL,
        ROOT / AUTHORITATIVE_ASSEMBLY_BASELINE_REL,
    )

    face_sem_path = SEM / "NURION_ADAPT03_FACE_SEMANTIC_SNAPSHOT_V1.json"
    attach_path = SEM / "NURION_ADAPT03_ATTACHMENT_SNAPSHOT_V1.json"
    eye_talk_path = SEM / "NURION_ADAPT03_EYE_TALKING_SNAPSHOT_V1.json"
    for path, obj in (
        (face_sem_path, derived["faceSemanticSnapshot"]),
        (attach_path, derived["attachmentSnapshot"]),
        (eye_talk_path, derived["eyeTalkingSnapshot"]),
    ):
        path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    attach = derived["attachmentSnapshot"]
    binding = {
        "schema": "NURION_ADAPT03_CANONICAL_FACE_BINDING_V1",
        "revision": "R1",
        "role": "CONSUME_ONLY cryptographically pinned FACE authority for ADAPT-03",
        "upstream": derived["upstream"],
        "snapshot": derived["snapshot"],
        "faceSemanticSnapshot": derived["faceSemanticSnapshot"],
        "attachmentSnapshot": derived["attachmentSnapshot"],
        "eyeTalkingSnapshot": derived["eyeTalkingSnapshot"],
        "faceBodyAttachment": {
            "parent": attach["parent"],
            "child": attach["child"],
            "type": attach["type"],
        },
        "eyeCalibrationFingerprintSha256": AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
        "talkingStatus": derived["eyeTalkingSnapshot"]["talkingStatus"],
        "invariants": {
            "faceAuthorityMutation": "DENY",
            "eyeCalibrationMutation": "DENY",
            "talkingAuthorityMutation": "DENY",
            "physicalHelperRigAugmentation": "DENY_IN_ADAPT03",
            "adapt04Implementation": "NOT_STARTED",
        },
    }
    binding_path = SEM / "NURION_ADAPT03_CANONICAL_FACE_BINDING_V1.json"
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    provenance = {
        "schema": "NURION_ADAPT03_UPSTREAM_PROVENANCE_RECEIPT_V1",
        "revision": "R1",
        "derivation": "READ_ONLY_EXTRACT",
        "generatedFromMonorepo": True,
        "upstream": derived["upstream"],
        "snapshot": derived["snapshot"],
        "observedUpstreamSha256": derived["observedUpstreamSha256"],
        "snapshotFileSha256": {
            "faceSemanticSnapshot": sha256_file(face_sem_path),
            "attachmentSnapshot": sha256_file(attach_path),
            "eyeTalkingSnapshot": sha256_file(eye_talk_path),
        },
        "bindingSha256": sha256_file(binding_path),
        "policy": "Pins must match authoritative_face_binding constants; mismatch = FAIL CLOSED",
        "nurionV1Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
        "autoRepair": "DENY",
    }
    prov_path = EV / "NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json"
    prov_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "faceProductLockSha256": AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
                "namingTableSha256": AUTHORITATIVE_NAMING_TABLE_SHA256,
                "compositionPolicySha256": AUTHORITATIVE_COMPOSITION_POLICY_SHA256,
                "faceBodyRuntimeSha256": AUTHORITATIVE_FACE_BODY_RUNTIME_SHA256,
                "assemblyBaselineSha256": AUTHORITATIVE_ASSEMBLY_BASELINE_SHA256,
                "faceSemanticDigest": derived["snapshot"]["faceSemanticDigest"],
                "attachmentDigest": derived["snapshot"]["attachmentDigest"],
                "eyeTalkingDigest": derived["snapshot"]["eyeTalkingDigest"],
                "binding": str(binding_path),
                "provenance": str(prov_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
