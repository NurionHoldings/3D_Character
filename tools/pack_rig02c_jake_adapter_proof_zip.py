#!/usr/bin/env python3
"""Pack NURION-RIG-02C Jake adapter proof ZIP — complete runner deps + sidecar SHA."""

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
FIX = EV / "rig02c_fixtures"
ZIP_PATH = EV / "NURION-RIG-02C_jake_adapter_proof.zip"
MANIFEST = EV / "NURION-RIG-02C_jake_adapter_proof_manifest.json"
SIDECAR = EV / "NURION-RIG-02C_jake_adapter_proof.zip.sha256"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# Files mirrored under repo/ for independent rerun
REPO_FILES: list[tuple[Path, str]] = [
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
    (ROOT / "fast_track/runtime/__init__.py", "repo/fast_track/runtime/__init__.py"),
    (ROOT / "fast_track/__init__.py", "repo/fast_track/__init__.py"),
    (SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json"),
    (SEM / "NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json"),
    (SEM / "NURION_FACE_PRODUCT_LOCK_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json"),
    (SEM / "NURION_BODY_PRODUCT_LOCK_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_PRODUCT_LOCK_V1.json"),
    (SEM / "NURION_RETARGET_ADAPTER_CONTRACT_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_RETARGET_ADAPTER_CONTRACT_V1.json"),
    (SEM / "retarget_profiles/jake_cc_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json"),
    (FIX / "jake_cc_pose_extract.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02c_fixtures/jake_cc_pose_extract.json"),
    (FIX / "jake_cc_synthetic_motion.json", "repo/fast_track/working/meshy_silver_starlight/evidence/rig02c_fixtures/jake_cc_synthetic_motion.json"),
    (EV / "NURION-RIG-02C_jake_pose_extract_summary.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02C_jake_pose_extract_summary.json"),
    (EV / "NURION-RIG-02C_jake_adapter_proof_stdout.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02C_jake_adapter_proof_stdout.json"),
    (EV / "NURION-RIG-02C_adapter_proof_receipt.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02C_adapter_proof_receipt.json"),
    (ROOT / "tools/blender_rig02c_jake_pose_extract.py", "repo/tools/blender_rig02c_jake_pose_extract.py"),
    (ROOT / "tools/run_nurion_rig02c_jake_extract.py", "repo/tools/run_nurion_rig02c_jake_extract.py"),
    (ROOT / "tools/calibrate_rig02c_jake_profile.py", "repo/tools/calibrate_rig02c_jake_profile.py"),
    (ROOT / "tools/gen_rig02c_jake_synthetic_motion.py", "repo/tools/gen_rig02c_jake_synthetic_motion.py"),
    (ROOT / "tools/run_rig02c_jake_adapter_proof.py", "repo/tools/run_rig02c_jake_adapter_proof.py"),
    (ROOT / "tools/run_rig02c_independent_proof.py", "run_rig02c_independent_proof.py"),
]


def ensure_init(zf: zipfile.ZipFile, arc: str) -> None:
    """Ensure package __init__ placeholders exist for import."""
    parts = Path(arc).parts
    for i in range(1, len(parts)):
        prefix = "/".join(parts[:i])
        if prefix.endswith("fast_track") or prefix.endswith("runtime") or prefix.endswith("retarget") or prefix.endswith("working") or prefix.endswith("meshy_silver_starlight") or prefix.endswith("semantic") or prefix.endswith("retarget_profiles") or prefix.endswith("evidence") or prefix.endswith("rig02c_fixtures") or prefix.endswith("tools"):
            init_arc = prefix + "/__init__.py"
            try:
                zf.getinfo(init_arc)
            except KeyError:
                if init_arc.endswith("fast_track/__init__.py") or init_arc.endswith("runtime/__init__.py") or init_arc.endswith("retarget/__init__.py"):
                    pass  # real files included


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sys.path.insert(0, str(ROOT))
    from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

    # Ensure empty package inits exist on disk
    for p in (
        ROOT / "fast_track/__init__.py",
        ROOT / "fast_track/runtime/__init__.py",
    ):
        if not p.exists():
            p.write_text("", encoding="utf-8")

    sot_before = {k: sha256(SEM / k) for k in PROTECTED_SOT_SHA256}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_rig02c_jake_adapter_proof.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    sot_after = assert_protected_sot_unchanged()
    proof = json.loads((EV / "NURION-RIG-02C_jake_adapter_proof_stdout.json").read_text(encoding="utf-8"))

    digest = {"tolerances": proof.get("tolerances"), "gates": []}
    for r in proof["results"]:
        entry = {"test": r["test"], "status": r["status"]}
        if "detail" in r:
            entry["detail"] = r["detail"]
        if "error" in r:
            entry["error"] = r["error"]
        digest["gates"].append(entry)
    digest_path = EV / "NURION-RIG-02C_expected_observed_digest.json"
    digest_path.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    receipt = {
        "receiptId": f"NURION-RIG-02C_{ts}",
        "stage": "NURION-RIG-02C_JAKE_CC_ADAPTER_PROOF",
        "status": "PATCHED_AWAITING_REAUDIT",
        "priorHumanVerdict": "PATCH_REQUIRED",
        "patchesApplied": [
            "P1_collapse_uses_common_parent_donor",
            "P2_delta_map_into_common_parent_frame",
            "P3_nonidentity_bind_fixture",
            "P4_naive_vs_common_parent_proof",
        ],
        "rig02cPass": "NOT_DECLARED",
        "rig02cFail": "NOT_DECLARED",
        "rig02Pass": "NOT_DECLARED",
        "rig02aPass": "PASS",
        "rig02bPass": "PASS",
        "track": {
            "RIG-02": "OPEN",
            "RIG-02A": "CLOSED / PASS",
            "RIG-02B": "CLOSED / PASS",
            "RIG-02C": "PATCHED_AWAITING_REAUDIT",
            "RIG-02D": "NOT_AUTHORIZED",
        },
        "scope": "Jake CC donor profile + collapse/intermediary numerical proof via common BodyRetargetEngine",
        "jakeRole": "DONOR_REFERENCE_ONLY",
        "product_use": False,
        "canonicalMutation": "DENY",
        "donorSpecificEngineFork": "DENY",
        "calibration": {
            "unit_scale": 0.01,
            "q_import": "Rx(-90°)",
            "collapse": "NeckTwist01×02 → NURION_neck Compose §16",
            "intermediary": "CC_Base_Pelvis",
            "root": "CC_Base_BoneRoot → NURION_root",
            "pelvis": "CC_Base_Hip → NURION_pelvis",
        },
        "agentSelfCheck": {
            "passed": proof["passed"],
            "failed": proof["failed"],
            "tests": [{"test": r["test"], "status": r["status"]} for r in proof["results"]],
        },
        "tolerances": proof.get("tolerances"),
        "protectedHashBeforePack": sot_before,
        "protectedHashAfterPack": sot_after,
        "protectedHashFrozenTable": PROTECTED_SOT_SHA256,
        "protectedHashMatch": sot_before == sot_after == PROTECTED_SOT_SHA256,
        "packagedAtUtc": ts,
        "auditPackageRules": {
            "runnerDependencyComplete": True,
            "canonicalPyIncluded": True,
            "authoritativeZipSha": "sidecar + receipt",
            "inZipPreAppendHash": "informational only",
            "independentRerunFromExtractedZip": "TARGET via run_rig02c_independent_proof.py",
        },
        "humanAuditRequest": "Independent ZIP rerun preferred → RIG-02C PASS or PATCH REQUIRED",
        "next": "Human RIG-02C verdict — RIG-02D only if PASS",
        "proofStdoutExitCode": proc.returncode,
    }
    receipt_path = EV / "NURION-RIG-02C_adapter_proof_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files = list(REPO_FILES) + [
        (digest_path, "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02C_expected_observed_digest.json"),
        (receipt_path, "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02C_adapter_proof_receipt.json"),
    ]
    # dedupe arcs
    seen = set()
    uniq = []
    for src, arc in files:
        if arc in seen:
            continue
        seen.add(arc)
        uniq.append((src, arc))
    files = uniq

    missing = [str(src) for src, _ in files if not src.exists()]
    if missing:
        raise SystemExit(f"missing: {missing}")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files:
            zf.write(src, arcname=arc)
        zf.writestr(
            "evidence/RIG02C_proof_runner_console.txt",
            (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""),
        )
        zf.writestr(
            "README_AUDIT.json",
            json.dumps(
                {
                    "purpose": "Chat upload for etherean RIG-02C Jake CC adapter numerical audit",
                    "rig02cPass": "NOT_DECLARED",
                    "howToIndependentRerun": [
                        "Extract ZIP",
                        "py -3 run_rig02c_independent_proof.py",
                        "Requires only Python stdlib + package contents (no Blender for proof gates)",
                    ],
                    "auditFocus": [
                        "P1a–d: common_parent_donor load-bearing via donor_parent_of hierarchy",
                        "test_neck_collapse_reject_wrong_common_parent (Hip/Head must FAIL)",
                        "P2–P4: conjugacy + non-identity bind + correct≠naive",
                        "CC_Base_Pelvis intermediary isolation",
                        "BoneRoot→root / Hip→pelvis ownership",
                        "common engine — no Jake fork",
                        "Protected SoT unchanged",
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
        "package": "NURION-RIG-02C_jake_adapter_proof.zip",
        "purpose": "Etherean audit package for RIG-02C Jake → Canonical numerical proof",
        "status": "PATCHED_AWAITING_REAUDIT",
        "priorHumanVerdict": "PATCH_REQUIRED",
        "patchesApplied": [
            "P1_collapse_uses_common_parent_donor",
            "P2_delta_map_into_common_parent_frame",
            "P3_nonidentity_bind_fixture",
            "P4_naive_vs_common_parent_proof",
        ],
        "rig02cPass": "NOT_DECLARED",
        "rig02cFail": "NOT_DECLARED",
        "bytesPreManifestAppend": ZIP_PATH.stat().st_size,
        "sha256PreManifestAppend": zsha_pre,
        "packageSha256Authority": "sidecar .zip.sha256 + receipt (not self-hash inside ZIP)",
        "packagedAtUtc": ts,
        "contents": [arc for _, arc in files]
        + ["evidence/RIG02C_proof_runner_console.txt", "README_AUDIT.json"],
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
        zf.write(MANIFEST, arcname="evidence/NURION-RIG-02C_jake_adapter_proof_manifest.json")

    zsha = sha256(ZIP_PATH)
    manifest["sha256"] = zsha
    manifest["bytes"] = ZIP_PATH.stat().st_size
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SIDECAR.write_text(zsha + "\n", encoding="utf-8")
    receipt["sourceReviewPackage"] = str(ZIP_PATH)
    receipt["sourceReviewPackageSha256"] = zsha
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Smoke: extract to temp and run independent proof
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall(td_path)
        # copy authoritative receipt into extracted repo (may be older inside zip)
        shutil.copy2(receipt_path, td_path / "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02C_adapter_proof_receipt.json")
        ind = subprocess.run(
            [sys.executable, str(td_path / "run_rig02c_independent_proof.py")],
            capture_output=True,
            text=True,
            cwd=str(td_path),
        )
        independent = {"exit": ind.returncode, "stdoutTail": (ind.stdout or "")[-500:], "stderrTail": (ind.stderr or "")[-500:]}

    print(
        json.dumps(
            {
                "zip": str(ZIP_PATH),
                "sha256": zsha,
                "bytes": ZIP_PATH.stat().st_size,
                "sidecar": str(SIDECAR),
                "rig02cPass": "NOT_DECLARED",
                "protectedUnchanged": manifest["protectedSoT"]["unchanged"],
                "testsExit": proc.returncode,
                "passed": proof["passed"],
                "failed": proof["failed"],
                "independentRerun": independent,
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    return 0 if proc.returncode == 0 and ind.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
