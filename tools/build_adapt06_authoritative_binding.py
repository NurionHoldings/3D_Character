#!/usr/bin/env python3
"""Generate ADAPT-06 authoritative release binding + provenance receipt."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.authoritative_release_binding import (
    ADAPT05_PASS_AUDIT_ZIP_SHA256,
    ADAPT05_PASS_RECEIPT_SHA256,
    CANONICAL_ADAPT05_HANDOFF_DIGEST,
    CANONICAL_CANDIDATE_SHA256,
    CANONICAL_CHARACTER_ID,
    CANONICAL_QUALIFICATION_REPORT_DIGEST,
    CANONICAL_RUNTIME_COMPATIBILITY_DIGEST,
)
from fast_track.adaptation.authoritative_runtime_qualification_binding import (
    ADAPT04_PASS_AUDIT_ZIP_SHA256,
    ADAPT04_PASS_RECEIPT_SHA256,
    PRODUCT_PIN_MAP,
)
from fast_track.adaptation.inspector import sha256_file

SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
EV = ROOT / "fast_track/working/adaptation_engine_v1/evidence"


def main() -> None:
    runtime_binding_path = SEM / "NURION_ADAPT05_RUNTIME_AUTHORITY_BINDING_V1.json"
    runtime_binding = json.loads(runtime_binding_path.read_text(encoding="utf-8"))

    binding = {
        "schema": "NURION_ADAPT06_RELEASE_AUTHORITY_BINDING_V1",
        "revision": "R1",
        "role": "CONSUME_ONLY ADAPT-05 canonical seal + runtime authority pins for release packaging",
        "releaseIdentity": {
            "releaseId": "NURION_ADAPTED_CHARACTER_RELEASE_V1",
            "releaseVersion": "1.0.0",
        },
        "predecessorPass": {
            "adapt05Status": "CLOSED / PASS / CONSUME ONLY",
            "adapt05AuditZipSha256": ADAPT05_PASS_AUDIT_ZIP_SHA256,
            "adapt05PassReceipt": "evidence/NURION-ADAPT-05_PASS_receipt.json",
            "adapt05PassReceiptSha256": ADAPT05_PASS_RECEIPT_SHA256,
            "adapt04Status": "CLOSED / PASS / CONSUME ONLY",
            "adapt04AuditZipSha256": ADAPT04_PASS_AUDIT_ZIP_SHA256,
            "adapt04PassReceiptSha256": ADAPT04_PASS_RECEIPT_SHA256,
            "adapt03Status": "CLOSED / PASS / CONSUME ONLY",
            "adapt02Status": "CLOSED / PASS / CONSUME ONLY",
            "adapt01Status": "CLOSED / PASS / CONSUME ONLY",
        },
        "adapt05CanonicalSeal": {
            "characterId": CANONICAL_CHARACTER_ID,
            "candidateSha256": CANONICAL_CANDIDATE_SHA256,
            "qualificationReportDigest": CANONICAL_QUALIFICATION_REPORT_DIGEST,
            "runtimeCompatibilityDigest": CANONICAL_RUNTIME_COMPATIBILITY_DIGEST,
            "adapt05HandoffDigest": CANONICAL_ADAPT05_HANDOFF_DIGEST,
            "authority": "PINNED — must not be recomputed by ADAPT-06",
        },
        "runtimeAuthorityPins": runtime_binding.get("runtimeAuthorityPins"),
        "faceAuthorityPins": runtime_binding.get("faceAuthorityPins"),
        "faceBodyAttachment": runtime_binding.get("faceBodyAttachment"),
        "invariants": {
            "releaseOnly": True,
            "autoRepair": "DENY",
            "candidateMutation": "DENY",
            "candidateRepair": "DENY",
            "nurionV1Modify": "DENY",
            "adapt01to05Modify": "DENY",
            "adapt05DigestRecompute": "DENY",
        },
    }
    binding_path = SEM / "NURION_ADAPT06_RELEASE_AUTHORITY_BINDING_V1.json"
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    provenance = {
        "schema": "NURION_ADAPT06_UPSTREAM_PROVENANCE_RECEIPT_V1",
        "revision": "R1",
        "derivation": "READ_ONLY_CONSUME",
        "generatedFromMonorepo": True,
        "predecessorPass": binding["predecessorPass"],
        "adapt05CanonicalSeal": binding["adapt05CanonicalSeal"],
        "runtimeAuthorityPins": binding["runtimeAuthorityPins"],
        "faceAuthorityPins": binding["faceAuthorityPins"],
        "bindingSha256": sha256_file(binding_path),
        "policy": "ADAPT-06 packages release only; unpinned ADAPT-05 authority = FAIL CLOSED",
        "nurionV1Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
        "adapt03Mutation": "NONE",
        "adapt04Mutation": "NONE",
        "adapt05Mutation": "NONE",
        "autoRepair": "DENY",
    }
    prov_path = EV / "NURION-ADAPT-06_UPSTREAM_PROVENANCE_RECEIPT.json"
    prov_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "binding": str(binding_path), "provenance": str(prov_path)}, indent=2))


if __name__ == "__main__":
    main()
