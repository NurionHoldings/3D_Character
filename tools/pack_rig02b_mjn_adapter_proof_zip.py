#!/usr/bin/env python3
"""Pack NURION-RIG-02B MJN adapter proof ZIP for etherean independent audit."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
FIX = EV / "rig02b_fixtures"
ZIP_PATH = EV / "NURION-RIG-02B_mjn_adapter_proof.zip"
MANIFEST = EV / "NURION-RIG-02B_mjn_adapter_proof_manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


FILES: list[tuple[Path, str]] = [
    (ROOT / "fast_track/runtime/body_retarget_engine.py", "runtime/body_retarget_engine.py"),
    (ROOT / "fast_track/runtime/donor_skeleton_profile.py", "runtime/donor_skeleton_profile.py"),
    (ROOT / "fast_track/runtime/retarget_contract_validator.py", "runtime/retarget_contract_validator.py"),
    (ROOT / "fast_track/runtime/retarget/__init__.py", "runtime/retarget/__init__.py"),
    (ROOT / "fast_track/runtime/retarget/engine.py", "runtime/retarget/engine.py"),
    (ROOT / "fast_track/runtime/retarget/quat.py", "runtime/retarget/quat.py"),
    (ROOT / "fast_track/runtime/retarget/canonical.py", "runtime/retarget/canonical.py"),
    (ROOT / "fast_track/runtime/retarget/protected.py", "runtime/retarget/protected.py"),
    (ROOT / "fast_track/runtime/retarget/registry.py", "runtime/retarget/registry.py"),
    (SEM / "retarget_profiles/mjn_legacy_profile_v1.json", "semantic/retarget_profiles/mjn_legacy_profile_v1.json"),
    (SEM / "NURION_RETARGET_ADAPTER_CONTRACT_V1.json", "semantic/NURION_RETARGET_ADAPTER_CONTRACT_V1.json"),
    (FIX / "mjn_idle_15_pose_extract.json", "fixtures/mjn_idle_15_pose_extract.json"),
    (FIX / "mjn_formal_bow_pose_extract.json", "fixtures/mjn_formal_bow_pose_extract.json"),
    (EV / "NURION-RIG-02B_mjn_pose_extract_summary.json", "evidence/NURION-RIG-02B_mjn_pose_extract_summary.json"),
    (EV / "NURION-RIG-02B_mjn_adapter_proof_stdout.json", "evidence/NURION-RIG-02B_mjn_adapter_proof_stdout.json"),
    (EV / "NURION-RIG-02B_adapter_proof_receipt.json", "evidence/NURION-RIG-02B_adapter_proof_receipt.json"),
    (ROOT / "tools/blender_rig02b_mjn_pose_extract.py", "tools/blender_rig02b_mjn_pose_extract.py"),
    (ROOT / "tools/run_nurion_rig02b_mjn_extract.py", "tools/run_nurion_rig02b_mjn_extract.py"),
    (ROOT / "tools/calibrate_rig02b_mjn_profile.py", "tools/calibrate_rig02b_mjn_profile.py"),
    (ROOT / "tools/run_rig02b_mjn_adapter_proof.py", "tools/run_rig02b_mjn_adapter_proof.py"),
]


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sys.path.insert(0, str(ROOT))
    from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

    sot_before = {k: sha256(SEM / k) for k in PROTECTED_SOT_SHA256}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_rig02b_mjn_adapter_proof.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    sot_after = assert_protected_sot_unchanged()
    proof = json.loads((EV / "NURION-RIG-02B_mjn_adapter_proof_stdout.json").read_text(encoding="utf-8"))

    # Build expected/observed digest for auditors
    digest = {
        "tolerances": proof.get("tolerances"),
        "gates": [],
    }
    for r in proof["results"]:
        entry = {"test": r["test"], "status": r["status"]}
        if "detail" in r:
            d = r["detail"]
            if r["test"] in ("test_motion_idle", "test_motion_bow"):
                entry["maxRotErr"] = d.get("maxRotErr")
                entry["tol"] = d.get("tol")
                entry["observedSamples"] = d.get("observedSamples")
            elif r["test"] == "test_root_pelvis_and_scale":
                entry["expected"] = {"pelvisTranslation": d.get("pelvisTranslationExpected")}
                entry["observed"] = {
                    "pelvisTranslation": d.get("pelvisTranslationObserved"),
                    "rootTranslation": d.get("rootTranslation"),
                }
            elif r["test"] == "test_rest_normalization":
                entry["maxRestRotErr"] = d.get("maxRestRotErr")
                entry["tol"] = d.get("tol")
            else:
                entry["detail"] = d
        if "error" in r:
            entry["error"] = r["error"]
        digest["gates"].append(entry)
    digest_path = EV / "NURION-RIG-02B_expected_observed_digest.json"
    digest_path.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    receipt = {
        "receiptId": f"NURION-RIG-02B_{ts}",
        "stage": "NURION-RIG-02B_MJN_LEGACY_ADAPTER_PROOF",
        "status": "PATCHED_AWAITING_REAUDIT",
        "priorHumanVerdict": "PATCH_REQUIRED",
        "patchesApplied": [
            "P1_translation_global_axis_remap",
            "P2_test_axis_translation_conversion",
            "P3_independent_pelvis_translation_expected",
        ],
        "rig02bPass": "NOT_DECLARED",
        "rig02bFail": "NOT_DECLARED",
        "rig02Pass": "NOT_DECLARED",
        "rig02aPass": "PASS",
        "track": {
            "RIG-02": "OPEN",
            "RIG-02A": "CLOSED / PASS",
            "RIG-02B": "PATCHED_AWAITING_REAUDIT",
            "RIG-02C": "NOT_AUTHORIZED",
            "RIG-02D": "NOT_STARTED",
            "RIG-02E": "NOT_STARTED",
        },
        "scope": "MJN Legacy → NURION BODY Core-23 numerical proof via common BodyRetargetEngine + MJN donor profile only",
        "canonicalRedesign": "DENY",
        "protectedSoTMutation": "DENY",
        "donorSpecificEngineFork": "DENY",
        "inputs": {
            "idleGlb": "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb",
            "bowFbx": "dist/v0.5/gate1/_extract/ai-aba.bow/.../Formal_Bow_withSkin.fbx",
            "profile": "semantic/retarget_profiles/mjn_legacy_profile_v1.json",
            "fixtures": [
                "fixtures/mjn_idle_15_pose_extract.json",
                "fixtures/mjn_formal_bow_pose_extract.json",
            ],
        },
        "calibration": {
            "unit_scale": 0.01,
            "q_import": "Rx(-90°) WXYZ — donor +Z-up import → Canonical +Y-up",
            "q_basis_b": "IDENTITY per Core-23 (world remap via Q_import only)",
            "mapping": "Hips→pelvis; virtual root; Spine02→spine01; Spine01→spine02; Spine→chest; helpers drop",
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
        "humanAuditRequest": "Review MJN numerical proof package → RIG-02B PASS or PATCH REQUIRED",
        "next": "Human RIG-02B verdict — RIG-02C only if PASS",
        "proofStdoutExitCode": proc.returncode,
    }
    receipt_path = EV / "NURION-RIG-02B_adapter_proof_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files = list(FILES) + [(digest_path, "evidence/NURION-RIG-02B_expected_observed_digest.json")]
    missing = [str(src) for src, _ in files if not src.exists()]
    if missing:
        raise SystemExit(f"missing: {missing}")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files:
            zf.write(src, arcname=arc)
        zf.writestr(
            "evidence/RIG02B_proof_runner_console.txt",
            (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""),
        )
        zf.writestr(
            "README_AUDIT.json",
            json.dumps(
                {
                    "purpose": "Chat upload for etherean RIG-02B MJN adapter numerical audit",
                    "rig02bPass": "NOT_DECLARED",
                    "auditFocus": [
                    "P1: translation UNIT then Q_import GLOBAL_AXIS_REMAP (staged)",
                    "P2: test_axis_translation_conversion — synthetic donor +Z → Canonical +Y",
                    "P3: pelvis expected via analytic Rx(-90) matrix, not engine helper",
                    "MJN differences only in mjn_legacy_profile_v1.json",
                    "common BodyRetargetEngine — no MJN branch",
                    "Hips→NURION_pelvis + VIRTUAL NURION_root",
                    "Spine02→spine01 / Spine01→spine02 / Spine→chest",
                    "helper drop head_end/headfront",
                    "Idle + Formal Bow numerical error within tolerance",
                    "Protected SoT unchanged",
                ],
                    "howToRead": [
                        "fixtures/* — extracted donor locals (input motion)",
                        "evidence/NURION-RIG-02B_expected_observed_digest.json — expected/observed + tol",
                        "evidence/NURION-RIG-02B_mjn_adapter_proof_stdout.json — full gate results",
                        "semantic/retarget_profiles/mjn_legacy_profile_v1.json — calibrated donor profile",
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )

    zsha_pre = sha256(ZIP_PATH)
    file_sha = {arc: sha256(src) for src, arc in files}
    # E1 lesson: a ZIP cannot self-describe its final SHA after the manifest is appended.
    # Inside-ZIP field records pre-append content hash; authoritative package SHA is sidecar + receipt.
    manifest = {
        "package": "NURION-RIG-02B_mjn_adapter_proof.zip",
        "purpose": "Etherean audit package for RIG-02B MJN → Canonical numerical proof",
        "status": "PACKAGED",
        "rig02bPass": "NOT_DECLARED",
        "rig02bFail": "NOT_DECLARED",
        "bytesPreManifestAppend": ZIP_PATH.stat().st_size,
        "sha256PreManifestAppend": zsha_pre,
        "packageSha256Authority": "sidecar .zip.sha256 + adapter/PASS receipt (not self-hash inside ZIP)",
        "packagedAtUtc": ts,
        "contents": [arc for _, arc in files]
        + ["evidence/RIG02B_proof_runner_console.txt", "README_AUDIT.json"],
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
        zf.write(MANIFEST, arcname="evidence/NURION-RIG-02B_mjn_adapter_proof_manifest.json")

    zsha = sha256(ZIP_PATH)
    manifest["sha256"] = zsha  # on-disk authoritative package hash (post-append)
    manifest["bytes"] = ZIP_PATH.stat().st_size
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (EV / "NURION-RIG-02B_mjn_adapter_proof.zip.sha256").write_text(zsha + "\n", encoding="utf-8")
    receipt["sourceReviewPackage"] = str(ZIP_PATH)
    receipt["sourceReviewPackageSha256"] = zsha
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "zip": str(ZIP_PATH),
                "sha256": zsha,
                "bytes": ZIP_PATH.stat().st_size,
                "rig02bPass": "NOT_DECLARED",
                "protectedUnchanged": manifest["protectedSoT"]["unchanged"],
                "testsExit": proc.returncode,
                "passed": proof["passed"],
                "failed": proof["failed"],
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
