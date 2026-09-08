#!/usr/bin/env python3
"""Pack NURION-PRODUCT-01_character_assembly_proof.zip — deps + GLB + independent smoke."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
BASE = ROOT / "fast_track/working/meshy_silver_starlight/baseline"
FIX02B = EV / "rig02b_fixtures"
ZIP_PATH = EV / "NURION-PRODUCT-01_character_assembly_proof.zip"
MANIFEST = EV / "NURION-PRODUCT-01_character_assembly_proof_manifest.json"
SIDECAR = EV / "NURION-PRODUCT-01_character_assembly_proof.zip.sha256"


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
    (ROOT / "fast_track/runtime/product_character_assembly.py", "repo/fast_track/runtime/product_character_assembly.py"),
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
    (SEM / "NURION_RIG02_PRODUCT_BOUNDARY_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_RIG02_PRODUCT_BOUNDARY_V1.json"),
    (SEM / "NURION_PRODUCT_CHARACTER_PIPELINE_TRACK_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT_CHARACTER_PIPELINE_TRACK_V1.json"),
    (SEM / "retarget_profiles/mjn_legacy_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json"),
    (SEM / "retarget_profiles/jake_cc_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json"),
    (SEM / "retarget_profiles/canonical_identity_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/canonical_identity_profile_v1.json"),
    (FIX02B / "mjn_idle_15_pose_extract.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02b_fixtures/mjn_idle_15_pose_extract.json"),
    (BASE / "Idle_15_withSkin_WORKING_BASELINE.glb", "repo/fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"),
    (ROOT / "tools/build_product01_assembly_baseline.py", "repo/tools/build_product01_assembly_baseline.py"),
    (ROOT / "tools/run_product01_assembly_proof.py", "repo/tools/run_product01_assembly_proof.py"),
    (ROOT / "tools/run_product01_independent_proof.py", "run_product01_independent_proof.py"),
]


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sys.path.insert(0, str(ROOT))
    from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

    for p in (ROOT / "fast_track/__init__.py", ROOT / "fast_track/runtime/__init__.py"):
        if not p.exists():
            p.write_text("", encoding="utf-8")

    env = {**os.environ, "NURION_REPO_ROOT": str(ROOT)}
    sot_before = {k: sha256(SEM / k) for k in PROTECTED_SOT_SHA256}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_product01_assembly_proof.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    sot_after = assert_protected_sot_unchanged()
    proof = json.loads((EV / "NURION-PRODUCT-01_assembly_proof_stdout.json").read_text(encoding="utf-8"))
    asm_path = SEM / "NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"
    if not asm_path.exists():
        raise SystemExit("assembly baseline missing after proof")

    digest = {"gates": []}
    for r in proof["results"]:
        entry = {"test": r["test"], "status": r["status"]}
        if "detail" in r:
            entry["detail"] = r["detail"]
        if "error" in r:
            entry["error"] = r["error"]
        digest["gates"].append(entry)
    digest_path = EV / "NURION-PRODUCT-01_expected_observed_digest.json"
    digest_path.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    receipt = {
        "receiptId": f"NURION-PRODUCT-01_{ts}",
        "stage": "NURION-PRODUCT-01_CHARACTER_ASSEMBLY_RUNTIME_BASELINE",
        "status": "PATCHED_AWAITING_REAUDIT",
        "product01Pass": "NOT_DECLARED",
        "product01Status": "PATCH_REQUIRED_CLOSED_P1a-P1d",
        "productPipelineOverall": "NOT_DECLARED",
        "rig01": "CLOSED / PASS",
        "rig02": "CLOSED / PASS / NO_REOPEN",
        "patch": {
            "P1a": "repo-relative asset path; absolute DENY",
            "P1b": "packaged.asset.sha256 verified vs on-disk GLB before overwrite",
            "P1c": "fresh rebuild canonical hash == packaged baseline",
            "P1d": "relocation determinism Root-A == Root-B"
        },
        "track": {
            "PRODUCT_CHARACTER_PIPELINE": "OPEN",
            "PRODUCT-01": "PATCHED / AWAITING_REAUDIT",
            "PRODUCT-02": "NOT_AUTHORIZED",
            "PRODUCT-03": "NOT_AUTHORIZED",
            "PRODUCT-04": "NOT_AUTHORIZED",
            "PRODUCT-05": "NOT_AUTHORIZED",
            "PRODUCT-06": "NOT_AUTHORIZED",
        },
        "scope": "MJN asset → Canonical BODY → FACE/BODY interface → runtime scene → idle baseline",
        "motionLibrary": "DENY — PRODUCT-02",
        "productDonor": "MJN APPROVED",
        "jakeProductUse": "DENY",
        "frozenAssetSha256": "a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1",
        "gates": [r["test"] for r in proof["results"]],
        "agentSelfCheck": {
            "passed": proof["passed"],
            "failed": proof["failed"],
            "tests": [{"test": r["test"], "status": r["status"]} for r in proof["results"]],
        },
        "protectedHashBeforePack": sot_before,
        "protectedHashAfterPack": sot_after,
        "protectedHashFrozenTable": PROTECTED_SOT_SHA256,
        "protectedHashMatch": sot_before == sot_after == PROTECTED_SOT_SHA256,
        "packagedAtUtc": ts,
        "auditPackageRules": {
            "runnerDependencyComplete": True,
            "authoritativeZipSha": "sidecar + receipt",
            "independentRerunFromExtractedZip": "run_product01_independent_proof.py",
        },
        "humanAuditRequest": "Re-audit P1a–P1d blockers — PRODUCT-01 PASS or further PATCH",
        "next": "Human PRODUCT-01 re-audit",
        "proofStdoutExitCode": proc.returncode,
    }
    receipt_path = EV / "NURION-PRODUCT-01_assembly_proof_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files = list(REPO_FILES) + [
        (asm_path, "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"),
        (EV / "NURION-PRODUCT-01_assembly_proof_stdout.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-01_assembly_proof_stdout.json"),
        (digest_path, "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-01_expected_observed_digest.json"),
        (receipt_path, "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-01_assembly_proof_receipt.json"),
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
            "evidence/PRODUCT01_proof_runner_console.txt",
            (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""),
        )
        zf.writestr(
            "README_AUDIT.json",
            json.dumps(
                {
                    "purpose": "Chat upload for etherean PRODUCT-01 assembly baseline audit",
                    "product01Pass": "NOT_DECLARED",
                    "patch": "P1a-P1d",
                    "howToIndependentRerun": [
                        "Extract ZIP",
                        "py -3 run_product01_independent_proof.py",
                    ],
                    "auditFocus": [
                        "P1a repo-relative asset path (absolute DENY)",
                        "P1b packaged.asset.sha256 == on-disk GLB BEFORE overwrite",
                        "P1c fresh rebuild canonical hash == packaged",
                        "P1d relocation Root-A hash == Root-B hash",
                        "frozen asset SHA a113cca6…05db1",
                        "12/12 gates including new asset+relocation tests",
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
        "package": "NURION-PRODUCT-01_character_assembly_proof.zip",
        "purpose": "Etherean audit package for PRODUCT-01 character assembly baseline",
        "status": "PATCHED_AWAITING_REAUDIT",
        "product01Pass": "NOT_DECLARED",
        "patch": "P1a-P1d",
        "bytesPreManifestAppend": ZIP_PATH.stat().st_size,
        "sha256PreManifestAppend": zsha_pre,
        "packageSha256Authority": "sidecar .zip.sha256 + receipt",
        "packagedAtUtc": ts,
        "contents": [arc for _, arc in files]
        + ["evidence/PRODUCT01_proof_runner_console.txt", "README_AUDIT.json"],
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
        zf.write(MANIFEST, arcname="evidence/NURION-PRODUCT-01_character_assembly_proof_manifest.json")

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
            td_path / "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-01_assembly_proof_receipt.json",
        )
        ind = subprocess.run(
            [sys.executable, str(td_path / "run_product01_independent_proof.py")],
            capture_output=True,
            text=True,
            cwd=str(td_path),
            env={**os.environ, "NURION_REPO_ROOT": str(td_path / "repo")},
        )

    print(
        json.dumps(
            {
                "zip": str(ZIP_PATH),
                "sha256": zsha,
                "bytes": ZIP_PATH.stat().st_size,
                "sidecar": str(SIDECAR),
                "product01Pass": "NOT_DECLARED",
                "protectedUnchanged": manifest["protectedSoT"]["unchanged"],
                "testsExit": proc.returncode,
                "passed": proof["passed"],
                "failed": proof["failed"],
                "independentRerun": {
                    "exit": ind.returncode,
                    "stdoutTail": (ind.stdout or "")[-400:],
                    "stderrTail": (ind.stderr or "")[-400:],
                },
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    return 0 if proc.returncode == 0 and ind.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
