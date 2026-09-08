#!/usr/bin/env python3
"""Pack NURION-RIG-02E_product_gate.zip — full 02A–02D deps + product boundary + sidecar SHA."""

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
ZIP_PATH = EV / "NURION-RIG-02E_product_gate.zip"
MANIFEST = EV / "NURION-RIG-02E_product_gate_manifest.json"
SIDECAR = EV / "NURION-RIG-02E_product_gate.zip.sha256"


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
    (SEM / "NURION_RIG02_PRODUCT_BOUNDARY_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_RIG02_PRODUCT_BOUNDARY_V1.json"),
    (SEM / "retarget_profiles/canonical_identity_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/canonical_identity_profile_v1.json"),
    (SEM / "retarget_profiles/mjn_legacy_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json"),
    (SEM / "retarget_profiles/jake_cc_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json"),
    (FIX02B / "mjn_idle_15_pose_extract.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02b_fixtures/mjn_idle_15_pose_extract.json"),
    (FIX02B / "mjn_formal_bow_pose_extract.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02b_fixtures/mjn_formal_bow_pose_extract.json"),
    (FIX02C / "jake_cc_synthetic_motion.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02c_fixtures/jake_cc_synthetic_motion.json"),
    (FIX02C / "jake_cc_pose_extract.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02c_fixtures/jake_cc_pose_extract.json"),
    (EV / "NURION-RIG-02A_PASS_receipt.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02A_PASS_receipt.json"),
    (EV / "NURION-RIG-02B_PASS_receipt.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02B_PASS_receipt.json"),
    (EV / "NURION-RIG-02C_PASS_receipt.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02C_PASS_receipt.json"),
    (EV / "NURION-RIG-02D_PASS_receipt.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02D_PASS_receipt.json"),
    (ROOT / "tools/run_rig02a_contract_closure_tests.py", "repo/tools/run_rig02a_contract_closure_tests.py"),
    (ROOT / "tools/run_rig02b_mjn_adapter_proof.py", "repo/tools/run_rig02b_mjn_adapter_proof.py"),
    (ROOT / "tools/run_rig02c_jake_adapter_proof.py", "repo/tools/run_rig02c_jake_adapter_proof.py"),
    (ROOT / "tools/run_rig02d_invariant_proof.py", "repo/tools/run_rig02d_invariant_proof.py"),
    (ROOT / "tools/run_rig02e_product_gate.py", "repo/tools/run_rig02e_product_gate.py"),
    (ROOT / "tools/calibrate_rig02b_mjn_profile.py", "repo/tools/calibrate_rig02b_mjn_profile.py"),
    (ROOT / "tools/calibrate_rig02c_jake_profile.py", "repo/tools/calibrate_rig02c_jake_profile.py"),
    (ROOT / "tools/gen_rig02c_jake_synthetic_motion.py", "repo/tools/gen_rig02c_jake_synthetic_motion.py"),
    (ROOT / "tools/run_rig02e_independent_proof.py", "run_rig02e_independent_proof.py"),
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
        [sys.executable, str(ROOT / "tools/run_rig02e_product_gate.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "NURION_REPO_ROOT": str(ROOT)},
    )
    sot_after = assert_protected_sot_unchanged()
    proof = json.loads((EV / "NURION-RIG-02E_product_gate_stdout.json").read_text(encoding="utf-8"))

    digest = {
        "stageRegression": proof.get("stageRegression"),
        "gates": [],
    }
    for r in proof["results"]:
        entry = {"test": r["test"], "status": r["status"]}
        if "detail" in r:
            entry["detail"] = r["detail"]
        if "error" in r:
            entry["error"] = r["error"]
        digest["gates"].append(entry)
    digest_path = EV / "NURION-RIG-02E_expected_observed_digest.json"
    digest_path.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Include stage stdout snapshots produced by nested runners
    stage_stdouts = [
        EV / "NURION-RIG-02A_closure_stdout.json",
        EV / "NURION-RIG-02B_mjn_adapter_proof_stdout.json",
        EV / "NURION-RIG-02C_jake_adapter_proof_stdout.json",
        EV / "NURION-RIG-02D_invariant_proof_stdout.json",
        EV / "NURION-RIG-02E_product_gate_stdout.json",
    ]

    receipt = {
        "receiptId": f"NURION-RIG-02E_{ts}",
        "stage": "NURION-RIG-02E_REGRESSION_PRODUCT_GATE",
        "status": "IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_AUDIT",
        "rig02ePass": "NOT_DECLARED",
        "rig02eFail": "NOT_DECLARED",
        "rig02Pass": "NOT_DECLARED",
        "rig02aPass": "PASS",
        "rig02bPass": "PASS",
        "rig02cPass": "PASS",
        "rig02dPass": "PASS",
        "track": {
            "RIG-01": "CLOSED / PASS",
            "RIG-02": "OPEN",
            "RIG-02A": "CLOSED / PASS",
            "RIG-02B": "CLOSED / PASS",
            "RIG-02C": "CLOSED / PASS",
            "RIG-02D": "CLOSED / PASS",
            "RIG-02E": "OPEN / AWAITING_HUMAN_AUDIT",
        },
        "scope": "Final RIG-02 regression & product boundary gate — no new retarget features",
        "newRetargetFeature": "DENY",
        "canonicalRedesign": "DENY",
        "protectedSoTMutation": "DENY",
        "productBoundary": {
            "MJN": "APPROVED_DONOR_PRODUCT_PIPELINE_INPUT",
            "Jake": "DONOR_REFERENCE_TEST_INPUT_ONLY product_use=false",
            "jakeAssetIncorporation": "DENY",
            "jakeDerivedCanonicalMutation": "DENY",
        },
        "gates": [r["test"] for r in proof["results"]],
        "agentSelfCheck": {
            "passed": proof["passed"],
            "failed": proof["failed"],
            "tests": [{"test": r["test"], "status": r["status"]} for r in proof["results"]],
            "stageRegression": proof.get("stageRegression"),
        },
        "protectedHashBeforePack": sot_before,
        "protectedHashAfterPack": sot_after,
        "protectedHashFrozenTable": PROTECTED_SOT_SHA256,
        "protectedHashMatch": sot_before == sot_after == PROTECTED_SOT_SHA256,
        "packagedAtUtc": ts,
        "auditPackageRules": {
            "runnerDependencyComplete": True,
            "authoritativeZipSha": "sidecar + receipt",
            "independentRerunFromExtractedZip": "run_rig02e_independent_proof.py",
        },
        "humanAuditRequest": "Independent ZIP rerun → if no blockers: RIG-02E PASS + RIG-02 CLOSED/PASS",
        "next": "Human RIG-02E / RIG-02 overall verdict",
        "proofStdoutExitCode": proc.returncode,
    }
    receipt_path = EV / "NURION-RIG-02E_product_gate_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files = list(REPO_FILES)
    for p in stage_stdouts + [digest_path, receipt_path]:
        files.append((p, f"repo/fast_track/working/meshy_silver_starlight/evidence/{p.name}"))

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
            "evidence/RIG02E_proof_runner_console.txt",
            (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""),
        )
        zf.writestr(
            "README_AUDIT.json",
            json.dumps(
                {
                    "purpose": "Chat upload for etherean RIG-02E final product gate audit",
                    "rig02ePass": "NOT_DECLARED",
                    "rig02Pass": "NOT_DECLARED",
                    "howToIndependentRerun": [
                        "Extract ZIP",
                        "py -3 run_rig02e_independent_proof.py",
                    ],
                    "auditFocus": [
                        "02A–02D full closure re-run (15/12/17/14)",
                        "drift vs PASS receipts",
                        "product boundary MJN vs Jake",
                        "FACE/Eye/TALKING/BODY Protected SoT hashes",
                        "deterministic double-run",
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
        "package": "NURION-RIG-02E_product_gate.zip",
        "purpose": "Etherean audit package for RIG-02E regression & product gate",
        "status": "IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_AUDIT",
        "rig02ePass": "NOT_DECLARED",
        "rig02Pass": "NOT_DECLARED",
        "bytesPreManifestAppend": ZIP_PATH.stat().st_size,
        "sha256PreManifestAppend": zsha_pre,
        "packageSha256Authority": "sidecar .zip.sha256 + receipt",
        "packagedAtUtc": ts,
        "contents": [arc for _, arc in files]
        + ["evidence/RIG02E_proof_runner_console.txt", "README_AUDIT.json"],
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
        zf.write(MANIFEST, arcname="evidence/NURION-RIG-02E_product_gate_manifest.json")

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
            td_path / "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02E_product_gate_receipt.json",
        )
        ind = subprocess.run(
            [sys.executable, str(td_path / "run_rig02e_independent_proof.py")],
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
                "rig02ePass": "NOT_DECLARED",
                "rig02Pass": "NOT_DECLARED",
                "protectedUnchanged": manifest["protectedSoT"]["unchanged"],
                "testsExit": proc.returncode,
                "passed": proof["passed"],
                "failed": proof["failed"],
                "independentRerun": {
                    "exit": ind.returncode,
                    "stdoutTail": (ind.stdout or "")[-500:],
                    "stderrTail": (ind.stderr or "")[-500:],
                },
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    return 0 if proc.returncode == 0 and ind.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
