#!/usr/bin/env python3
"""Pack NURION-RIG-02A source review ZIP for etherean chat audit."""

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
ZIP_PATH = EV / "NURION-RIG-02A_source_review.zip"
MANIFEST = EV / "NURION-RIG-02A_source_review_manifest.json"


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
    (ROOT / "fast_track/runtime/retarget/profile.py", "runtime/retarget/profile.py"),
    (SEM / "NURION_RETARGET_ADAPTER_CONTRACT_V1.json", "semantic/NURION_RETARGET_ADAPTER_CONTRACT_V1.json"),
    (SEM / "NURION_DONOR_PROFILE_SCHEMA_V1.json", "semantic/NURION_DONOR_PROFILE_SCHEMA_V1.json"),
    (
        SEM / "retarget_profiles/canonical_identity_profile_v1.json",
        "semantic/retarget_profiles/canonical_identity_profile_v1.json",
    ),
    (
        SEM / "retarget_profiles/mjn_legacy_profile_v1.json",
        "semantic/retarget_profiles/mjn_legacy_profile_v1.json",
    ),
    (
        SEM / "retarget_profiles/jake_cc_profile_v1.json",
        "semantic/retarget_profiles/jake_cc_profile_v1.json",
    ),
    (EV / "NURION-RIG-02A_adapter_contract_receipt.json", "evidence/NURION-RIG-02A_adapter_contract_receipt.json"),
    (ROOT / "tools/run_rig02a_contract_closure_tests.py", "tools/run_rig02a_contract_closure_tests.py"),
    (ROOT / "tools/run_nurion_rig02a_submit_for_audit.py", "tools/run_nurion_rig02a_submit_for_audit.py"),
]


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sys.path.insert(0, str(ROOT))
    from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

    sot_before = {k: sha256(SEM / k) for k in PROTECTED_SOT_SHA256}
    # re-run closure tests and capture
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_rig02a_contract_closure_tests.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    sot_after = assert_protected_sot_unchanged()
    test_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"

    # refresh receipt timestamp note without declaring PASS
    receipt_path = EV / "NURION-RIG-02A_adapter_contract_receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    else:
        receipt = {}
    try:
        test_payload = json.loads(test_line)
    except json.JSONDecodeError:
        test_payload = {"raw": test_line}
    receipt.update(
        {
            "status": "PATCHED_AWAITING_REAUDIT",
            "priorHumanVerdict": "PATCH_REQUIRED",
            "rig02aPass": "NOT_DECLARED",
            "rig02aFail": "NOT_DECLARED",
            "patchesApplied": [
                "P1_q_basis_b_exact_core23_or_parse_FAIL",
                "P2_non_unit_raw_quat_parse_FAIL_not_auto_normalize",
                "P3_body_retarget_engine_donor_literals_zero",
            ],
            "agentSelfCheck": {
                "contractClosureTests": "PASS" if proc.returncode == 0 else "FAIL",
                "tests": test_payload,
            },
            "auditBlockerPreviously": "THREE_NARROW_INPUT_CONTRACT_BLOCKERS",
            "sourceReviewPackage": str(ZIP_PATH),
            "protectedHashBeforePack": sot_before,
            "protectedHashAfterPack": sot_after,
            "protectedHashFrozenTable": PROTECTED_SOT_SHA256,
            "protectedHashMatch": sot_before == sot_after == PROTECTED_SOT_SHA256,
            "packagedAtUtc": ts,
            "humanAuditRequest": "Re-audit P1/P2/P3 closure only → RIG-02A PASS or further PATCH",
            "next": "Human RIG-02A re-audit — RIG-02B only if PASS",
        }
    )
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    missing = [str(src) for src, _ in FILES if not src.exists()]
    if missing:
        raise SystemExit(f"missing files: {missing}")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in FILES:
            zf.write(src, arcname=arc)
        # embed live test stdout
        zf.writestr(
            "evidence/RIG02A_contract_closure_tests_stdout.txt",
            proc.stdout + "\n--- stderr ---\n" + (proc.stderr or ""),
        )
        readme = {
            "purpose": "Chat upload for etherean RIG-02A source-level audit",
            "rig02aPass": "NOT_DECLARED",
            "rig02aFail": "NOT_DECLARED",
            "auditFocus": [
                "P1: profile_from_dict rejects incomplete/missing q_basis_b (no identity auto-fill)",
                "P2: raw non-unit quat FAIL on parser path (q_import + q_basis_b); hemisphere only after unit check",
                "P3: official body_retarget_engine.py has 0 donor-name literals; scanner in test layer",
                "closure: test_reject_missing_q_basis_b_member + test_reject_non_unit_quaternion_through_parser",
                "protected SoT hash before/after in receipt unchanged",
            ],
        }
        zf.writestr("README_AUDIT.json", json.dumps(readme, indent=2, ensure_ascii=False) + "\n")

    zsha = sha256(ZIP_PATH)
    file_sha = {arc: sha256(src) for src, arc in FILES}
    manifest = {
        "package": "NURION-RIG-02A_source_review.zip",
        "purpose": "Etherean source-level audit package for RIG-02A PASS / PATCH REQUIRED",
        "status": "PATCHED_AWAITING_REAUDIT",
        "priorHumanVerdict": "PATCH_REQUIRED",
        "patchesApplied": [
            "P1_q_basis_b_exact_core23_or_parse_FAIL",
            "P2_non_unit_raw_quat_parse_FAIL_not_auto_normalize",
            "P3_body_retarget_engine_donor_literals_zero",
        ],
        "rig02aPass": "NOT_DECLARED",
        "rig02aFail": "NOT_DECLARED",
        "reasonPriorBlock": "PATCH_REQUIRED on input-contract closure — this ZIP is re-audit package",
        "bytes": ZIP_PATH.stat().st_size,
        "sha256": zsha,
        "packagedAtUtc": ts,
        "contents": [arc for _, arc in FILES]
        + ["evidence/RIG02A_contract_closure_tests_stdout.txt", "README_AUDIT.json"],
        "fileSha256": file_sha,
        "protectedSoT": {
            "before": sot_before,
            "after": sot_after,
            "frozen": PROTECTED_SOT_SHA256,
            "unchanged": sot_before == sot_after == PROTECTED_SOT_SHA256,
        },
        "agentClosureTestsExitCode": proc.returncode,
        "agentClosureTestsSummaryLine": test_line,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # add manifest into zip as well (rewrite zip append)
    with zipfile.ZipFile(ZIP_PATH, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(MANIFEST, arcname="evidence/NURION-RIG-02A_source_review_manifest.json")

    # recompute sha after append
    zsha = sha256(ZIP_PATH)
    manifest["sha256"] = zsha
    manifest["bytes"] = ZIP_PATH.stat().st_size
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # update receipt with final sha
    receipt["sourceReviewPackageSha256"] = zsha
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "zip": str(ZIP_PATH),
                "sha256": zsha,
                "bytes": ZIP_PATH.stat().st_size,
                "rig02aPass": "NOT_DECLARED",
                "protectedUnchanged": manifest["protectedSoT"]["unchanged"],
                "testsExit": proc.returncode,
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
