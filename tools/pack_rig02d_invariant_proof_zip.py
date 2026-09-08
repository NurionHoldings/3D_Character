#!/usr/bin/env python3
"""Pack NURION-RIG-02D invariant proof ZIP — complete runner deps + sidecar SHA."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
FIX02B = EV / "rig02b_fixtures"
FIX02C = EV / "rig02c_fixtures"
ZIP_PATH = EV / "NURION-RIG-02D_invariant_proof.zip"
MANIFEST = EV / "NURION-RIG-02D_invariant_proof_manifest.json"
SIDECAR = EV / "NURION-RIG-02D_invariant_proof.zip.sha256"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


REPO_FILES: list[tuple[Path, str]] = [
    (ROOT / "fast_track/__init__.py", "repo/fast_track/__init__.py"),
    (ROOT / "fast_track/runtime/__init__.py", "repo/fast_track/runtime/__init__.py"),
    (ROOT / "fast_track/runtime/body_retarget_engine.py", "repo/fast_track/runtime/body_retarget_engine.py"),
    (ROOT / "fast_track/runtime/donor_skeleton_profile.py", "repo/fast_track/runtime/donor_skeleton_profile.py"),
    (ROOT / "fast_track/runtime/retarget_contract_validator.py", "repo/fast_track/runtime/retarget_contract_validator.py"),
    (ROOT / "fast_track/runtime/retarget/__init__.py", "repo/fast_track/runtime/retarget/__init__.py"),
    (ROOT / "fast_track/runtime/retarget/engine.py", "repo/fast_track/runtime/retarget/engine.py"),
    (ROOT / "fast_track/runtime/retarget/quat.py", "repo/fast_track/runtime/retarget/quat.py"),
    (ROOT / "fast_track/runtime/retarget/canonical.py", "repo/fast_track/runtime/retarget/canonical.py"),
    (ROOT / "fast_track/runtime/retarget/protected.py", "repo/fast_track/runtime/retarget/protected.py"),
    (ROOT / "fast_track/runtime/retarget/registry.py", "repo/fast_track/runtime/retarget/registry.py"),
    (ROOT / "fast_track/runtime/retarget/profile.py", "repo/fast_track/runtime/retarget/profile.py"),
    (SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json"),
    (SEM / "NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json"),
    (SEM / "NURION_FACE_PRODUCT_LOCK_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json"),
    (SEM / "NURION_BODY_PRODUCT_LOCK_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_PRODUCT_LOCK_V1.json"),
    (SEM / "NURION_RETARGET_ADAPTER_CONTRACT_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_RETARGET_ADAPTER_CONTRACT_V1.json"),
    (SEM / "retarget_profiles/canonical_identity_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/canonical_identity_profile_v1.json"),
    (SEM / "retarget_profiles/mjn_legacy_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json"),
    (SEM / "retarget_profiles/jake_cc_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json"),
    (FIX02B / "mjn_idle_15_pose_extract.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02b_fixtures/mjn_idle_15_pose_extract.json"),
    (FIX02C / "jake_cc_synthetic_motion.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02c_fixtures/jake_cc_synthetic_motion.json"),
    (FIX02C / "jake_cc_pose_extract.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02c_fixtures/jake_cc_pose_extract.json"),
    (EV / "NURION-RIG-02D_invariant_proof_stdout.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02D_invariant_proof_stdout.json"),
    (ROOT / "tools/run_rig02d_invariant_proof.py", "repo/tools/run_rig02d_invariant_proof.py"),
    (ROOT / "tools/run_rig02d_independent_proof.py", "run_rig02d_independent_proof.py"),
]


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sys.path.insert(0, str(ROOT))
    from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

    for p in (ROOT / "fast_track/__init__.py", ROOT / "fast_track/runtime/__init__.py"):
        if not p.exists():
            p.write_text("", encoding="utf-8")

    sot_before = {k: sha256(SEM / k) for k in PROTECTED_SOT_SHA256}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_rig02d_invariant_proof.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    sot_after = assert_protected_sot_unchanged()
    proof = json.loads((EV / "NURION-RIG-02D_invariant_proof_stdout.json").read_text(encoding="utf-8"))

    digest = {"tolerances": proof.get("tolerances"), "gates": []}
    for r in proof["results"]:
        entry = {"test": r["test"], "status": r["status"]}
        if "detail" in r:
            entry["detail"] = r["detail"]
        if "error" in r:
            entry["error"] = r["error"]
        digest["gates"].append(entry)
    digest_path = EV / "NURION-RIG-02D_expected_observed_digest.json"
    digest_path.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    receipt = {
        "receiptId": f"NURION-RIG-02D_{ts}",
        "stage": "NURION-RIG-02D_BIDIRECTIONAL_INVARIANT_PROOF",
        "status": "IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_AUDIT",
        "rig02dPass": "NOT_DECLARED",
        "rig02dFail": "NOT_DECLARED",
        "rig02Pass": "NOT_DECLARED",
        "rig02aPass": "PASS",
        "rig02bPass": "PASS",
        "rig02cPass": "PASS",
        "track": {
            "RIG-02": "OPEN",
            "RIG-02A": "CLOSED / PASS",
            "RIG-02B": "CLOSED / PASS",
            "RIG-02C": "CLOSED / PASS",
            "RIG-02D": "OPEN / AWAITING_HUMAN_AUDIT",
            "RIG-02E": "NOT_AUTHORIZED",
        },
        "scope": "Bidirectional / invariant numerical lock of common retarget system — no new donors",
        "newDonor": "DENY",
        "canonicalMutation": "DENY",
        "protectedSoTMutation": "DENY",
        "gates": [r["test"] for r in proof["results"]],
        "agentSelfCheck": {
            "passed": proof["passed"],
            "failed": proof["failed"],
            "tests": [{"test": r["test"], "status": r["status"]} for r in proof["results"]],
        },
        "tolerances": proof.get("tolerances"),
        "collapseRoundTripPolicy": "Canonical semantic invariants; lossy first-bone expand for Jake neck",
        "protectedHashBeforePack": sot_before,
        "protectedHashAfterPack": sot_after,
        "protectedHashFrozenTable": PROTECTED_SOT_SHA256,
        "protectedHashMatch": sot_before == sot_after == PROTECTED_SOT_SHA256,
        "packagedAtUtc": ts,
        "auditPackageRules": {
            "runnerDependencyComplete": True,
            "authoritativeZipSha": "sidecar + receipt",
            "independentRerunFromExtractedZip": "run_rig02d_independent_proof.py",
        },
        "humanAuditRequest": "Independent ZIP rerun → RIG-02D PASS or PATCH REQUIRED",
        "next": "Human RIG-02D verdict — RIG-02E only if PASS",
        "proofStdoutExitCode": proc.returncode,
    }
    receipt_path = EV / "NURION-RIG-02D_invariant_proof_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files = list(REPO_FILES) + [
        (digest_path, "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02D_expected_observed_digest.json"),
        (receipt_path, "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02D_invariant_proof_receipt.json"),
    ]
    seen: set[str] = set()
    uniq = []
    for src, arc in files:
        if arc in seen:
            continue
        seen.add(arc)
        uniq.append((src, arc))
    files = uniq
    missing = [str(s) for s, _ in files if not s.exists()]
    if missing:
        raise SystemExit(f"missing: {missing}")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files:
            zf.write(src, arcname=arc)
        zf.writestr(
            "evidence/RIG02D_proof_runner_console.txt",
            (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""),
        )
        zf.writestr(
            "README_AUDIT.json",
            json.dumps(
                {
                    "purpose": "Chat upload for etherean RIG-02D bidirectional/invariant audit",
                    "rig02dPass": "NOT_DECLARED",
                    "howToIndependentRerun": [
                        "Extract ZIP",
                        "py -3 run_rig02d_independent_proof.py",
                    ],
                    "auditFocus": [
                        "Canonical→Canonical identity (pos/rot≈0, scale=0)",
                        "MJN/Jake D→C→D and C→D→C separated",
                        "Jake collapse: Canonical neck semantic round-trip (lossy expand)",
                        "Mirror §19: S=diag(-1,1,1), q'=(w,x,-y,-z), R'=SRS",
                        "root/pelvis ownership + scale contamination 0",
                        "determinism + donor-literal isolation + Protected SoT",
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )

    zsha_pre = sha256(ZIP_PATH)
    file_sha = {arc: sha256(src) for src, arc in files}
    manifest = {
        "package": "NURION-RIG-02D_invariant_proof.zip",
        "purpose": "Etherean audit package for RIG-02D bidirectional/invariant proof",
        "status": "IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_AUDIT",
        "rig02dPass": "NOT_DECLARED",
        "rig02dFail": "NOT_DECLARED",
        "bytesPreManifestAppend": ZIP_PATH.stat().st_size,
        "sha256PreManifestAppend": zsha_pre,
        "packageSha256Authority": "sidecar .zip.sha256 + receipt",
        "packagedAtUtc": ts,
        "contents": [arc for _, arc in files]
        + ["evidence/RIG02D_proof_runner_console.txt", "README_AUDIT.json"],
        "fileSha256": file_sha,
        "protectedSoT": {
            "before": sot_before,
            "after": sot_after,
            "frozen": PROTECTED_SOT_SHA256,
            "unchanged": sot_before == sot_after == PROTECTED_SOT_SHA256,
        },
        "agentProofExitCode": proc.returncode,
        "agentProofSummary": {"passed": proof["passed"], "failed": proof["failed"]},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with zipfile.ZipFile(ZIP_PATH, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(MANIFEST, arcname="evidence/NURION-RIG-02D_invariant_proof_manifest.json")

    zsha = sha256(ZIP_PATH)
    manifest["sha256"] = zsha
    manifest["bytes"] = ZIP_PATH.stat().st_size
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SIDECAR.write_text(zsha + "\n", encoding="utf-8")
    receipt["sourceReviewPackage"] = str(ZIP_PATH)
    receipt["sourceReviewPackageSha256"] = zsha
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall(td_path)
        shutil.copy2(
            receipt_path,
            td_path / "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02D_invariant_proof_receipt.json",
        )
        ind = subprocess.run(
            [sys.executable, str(td_path / "run_rig02d_independent_proof.py")],
            capture_output=True,
            text=True,
            cwd=str(td_path),
        )

    print(
        json.dumps(
            {
                "zip": str(ZIP_PATH),
                "sha256": zsha,
                "bytes": ZIP_PATH.stat().st_size,
                "sidecar": str(SIDECAR),
                "rig02dPass": "NOT_DECLARED",
                "protectedUnchanged": manifest["protectedSoT"]["unchanged"],
                "testsExit": proc.returncode,
                "passed": proof["passed"],
                "failed": proof["failed"],
                "independentRerun": {
                    "exit": ind.returncode,
                    "stdoutTail": (ind.stdout or "")[-400:],
                },
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    return 0 if proc.returncode == 0 and ind.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
