#!/usr/bin/env python3
"""Emit RIG-02A receipt for human audit (PASS not declared by agent)."""

from __future__ import annotations

import ast
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
LEDGER = ROOT / "fast_track/working/meshy_silver_starlight/mutation_ledger.json"
RECEIPT = EV / "NURION-RIG-02A_adapter_contract_receipt.json"


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_rig02a_contract_closure_tests.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    tests = ast.literal_eval(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    sys.path.insert(0, str(ROOT))
    from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

    hashes = assert_protected_sot_unchanged()
    agent_impl_ok = proc.returncode == 0
    receipt = {
        "receiptId": f"NURION-RIG-02A_{ts}",
        "stage": "NURION-RIG-02A_ADAPTER_CONTRACT",
        "status": "IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_AUDIT",
        "rig02aPass": "NOT_DECLARED",
        "rig02Pass": "NOT_DECLARED",
        "agentSelfCheck": {
            "contractClosureTests": "PASS" if agent_impl_ok else "FAIL",
            "tests": tests,
        },
        "track": {
            "RIG-02": "OPEN",
            "RIG-02A": "AWAITING_HUMAN_AUDIT",
            "RIG-02B": "NOT_STARTED",
            "RIG-02C": "NOT_STARTED",
            "RIG-02D": "NOT_STARTED",
            "RIG-02E": "NOT_STARTED",
        },
        "scope": "Adapter Contract only — no MJN/Jake production retarget calibration",
        "canonicalModification": "DENY",
        "donorSpecificRuntimeAlgorithm": "DENY",
        "protected": {
            "FACE_PRODUCT_LOCK": "DECLARED",
            "BODY_CANONICAL_V1": "FULL_LOCK",
            "TALKING": "GO",
            "Eye_Calibration": "PROTECTED",
            "sotHashesUnchanged": hashes,
            "frozenTable": PROTECTED_SOT_SHA256,
        },
        "artifacts": {
            "engine": "fast_track/runtime/body_retarget_engine.py",
            "profile": "fast_track/runtime/donor_skeleton_profile.py",
            "validator": "fast_track/runtime/retarget_contract_validator.py",
            "contract": str(SEM / "NURION_RETARGET_ADAPTER_CONTRACT_V1.json"),
            "profileSchema": str(SEM / "NURION_DONOR_PROFILE_SCHEMA_V1.json"),
            "identityProfile": str(SEM / "retarget_profiles/canonical_identity_profile_v1.json"),
            "mjnProfileDraft": str(SEM / "retarget_profiles/mjn_legacy_profile_v1.json"),
            "jakeProfileDraft": str(SEM / "retarget_profiles/jake_cc_profile_v1.json"),
        },
        "humanAuditRequest": "Review contract/code structure → RIG-02A PASS or PATCH REQUIRED",
        "next": "Human RIG-02A verdict — then RIG-02B only if PASS",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["presentationLayer"] = (
        "FACE+BODY LOCKED / TALKING GO — RIG-02 OPEN; RIG-02A implementation complete, "
        "AWAITING HUMAN AUDIT (PASS NOT DECLARED); 02B blocked until 02A PASS"
    )
    for e in ledger.get("entries", []):
        if e.get("id") == "NURION-RIG-02A":
            e["status"] = "AWAITING_HUMAN_AUDIT"
            e["rig02aPass"] = "NOT_DECLARED"
            e["evidence"] = str(RECEIPT)
    if "rig02Track" in ledger:
        ledger["rig02Track"].update(
            {
                "rig02a": "AWAITING_HUMAN_AUDIT",
                "rig02aPass": "NOT_DECLARED",
                "rig02Pass": "NOT_DECLARED",
                "updatedAtUtc": ts,
            }
        )
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "receipt": str(RECEIPT),
                "status": receipt["status"],
                "rig02aPass": "NOT_DECLARED",
                "agentTests": tests.get("passed"),
                "agentFailed": tests.get("failed"),
            },
            ensure_ascii=True,
        )
    )
    return 0 if agent_impl_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
