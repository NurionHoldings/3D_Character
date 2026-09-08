#!/usr/bin/env python3
"""Repackage RIG-01C convention after §14/§19/§20 patch."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
LEDGER = ROOT / "fast_track/working/meshy_silver_starlight/mutation_ledger.json"

CONV = SEM / "NURION_BODY_AXIS_RETARGET_CONVENTION_V1_DRAFT.json"
RAW = EV / "NURION-RIG-01C_axis_rest_forensic_raw.json"
RECEIPT = EV / "NURION-RIG-01C_axis_retarget_convention_receipt.json"
ZIP_PATH = EV / "NURION-RIG-01C_convention_source_review.zip"
MANIFEST = EV / "NURION-RIG-01C_convention_source_review_manifest.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    c = json.loads(CONV.read_text(encoding="utf-8"))
    assert c["19_leftRightMirrorConvention"]["quaternionMirror"]["formula"] == "q_mirror = (w, x, -y, -z)"
    assert "Q_basis_b" in c["14_donorToCanonicalLocalTransform"]["definitions"]
    assert (
        "mirror_quaternion_matches_reflection_conjugation"
        in c["20_retargetValidationTolerance"]["mechanicalTestSuite"]
    )
    assert "flexion angle from full extension" in c["6_canonicalRestPose"]["numericContract"][
        "elbowFlexionDeg"
    ]["definition"]

    receipt = {
        "receiptId": f"NURION-RIG-01C_PATCH_{ts}",
        "stage": "NURION-RIG-01C_CONVENTION_PATCH_§14_§19_§20",
        "status": "PATCHED_AWAITING_REAUDIT",
        "rig01cPass": "NOT_DECLARED",
        "bodyCanonicalV1": "LOCK_CANDIDATE",
        "fullLock": "DENY",
        "priorAuditBlockersFixedInDraft": {
            "§14": "Q_basis_b per-bone + Q_import global separation",
            "§19": "quaternionMirror (w, x, -y, -z); R' = S R S; S = diag(-1,1,1)",
            "§20": "mirror_quaternion_matches_reflection_conjugation added",
            "§6": "elbowFlexionDeg wording clarified (non-blocker)",
        },
        "officialStatusUnchanged": {
            "rig01a": "PASS",
            "rig01b": "PASS_ACCEPTED",
            "rig01cPass": "NOT_DECLARED",
            "fullLock": "DENY",
        },
        "conventionPath": str(CONV),
        "conventionSha256": sha(CONV),
        "rawPath": str(RAW),
        "rawSha256": sha(RAW),
        "next": "Re-attach ZIP for etherean re-audit → RIG-01C PASS / Full LOCK decision only",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files = [
        (CONV, "NURION_BODY_AXIS_RETARGET_CONVENTION_V1_DRAFT.json"),
        (RECEIPT, "NURION-RIG-01C_axis_retarget_convention_receipt.json"),
        (RAW, "NURION-RIG-01C_axis_rest_forensic_raw.json"),
    ]
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files:
            zf.write(src, arcname=arc)

    zsha = sha(ZIP_PATH)
    file_sha = {arc: sha(src) for src, arc in files}
    manifest = {
        "package": "NURION-RIG-01C_convention_source_review.zip",
        "revision": "PATCH_§14_§19_§20",
        "purpose": "Re-audit package after LOCK-blocker patches (no PASS/Full LOCK declared)",
        "status": "PATCHED_AWAITING_REAUDIT",
        "rig01cPass": "NOT_DECLARED",
        "fullLock": "DENY",
        "bytes": ZIP_PATH.stat().st_size,
        "sha256": zsha,
        "contents": [arc for _, arc in files],
        "fileSha256": file_sha,
        "patchFocus": [
            "§14 Q_basis_b",
            "§19 (w,x,-y,-z)",
            "§20 mirror invariant",
            "§6 elbow wording",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["presentationLayer"] = (
        "FACE LOCKED / TALKING GO — RIG-01C Convention PATCHED (§14/§19/§20) "
        "awaiting re-audit; PASS/Full LOCK DENY"
    )
    for e in ledger.get("entries", []):
        if e.get("id") == "NURION-RIG-01C":
            e["status"] = "PATCHED_AWAITING_REAUDIT"
            e["rig01cPass"] = "NOT_DECLARED"
            e["fullLock"] = "DENY"
            e["reviewPackage"] = str(ZIP_PATH)
            e["reviewPackageSha256"] = zsha
            e["conventionSha256"] = file_sha["NURION_BODY_AXIS_RETARGET_CONVENTION_V1_DRAFT.json"]
    if "bodyCanonicalTrack" in ledger:
        ledger["bodyCanonicalTrack"].update(
            {
                "rig01c": "PATCHED_AWAITING_REAUDIT",
                "rig01cPass": "NOT_DECLARED",
                "fullLock": "DENY",
                "reviewPackageSha256": zsha,
                "updatedAtUtc": ts,
            }
        )
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "zip": str(ZIP_PATH),
                "sha256": zsha,
                "bytes": manifest["bytes"],
                "conventionSha": file_sha["NURION_BODY_AXIS_RETARGET_CONVENTION_V1_DRAFT.json"],
                "rawSha": file_sha["NURION-RIG-01C_axis_rest_forensic_raw.json"],
                "rig01cPass": "NOT_DECLARED",
                "fullLock": "DENY",
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
