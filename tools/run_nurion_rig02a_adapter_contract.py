#!/usr/bin/env python3
"""Write NURION-RIG-02A Adapter Contract receipt + ledger update."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
LEDGER = ROOT / "fast_track/working/meshy_silver_starlight/mutation_ledger.json"
RECEIPT = EV / "NURION-RIG-02A_adapter_contract_receipt.json"


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_rig02a_contract_tests.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    # stdout is a python dict repr from print
    payload = None
    if proc.stdout.strip():
        import ast

        payload = ast.literal_eval(proc.stdout.strip().splitlines()[-1])
    ok = proc.returncode == 0
    from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

    hashes = assert_protected_sot_unchanged()
    receipt = {
        "receiptId": f"NURION-RIG-02A_{ts}",
        "stage": "NURION-RIG-02A_ADAPTER_CONTRACT",
        "status": "PASS" if ok else "FAIL",
        "rig02Pass": "NOT_DECLARED",
        "track": {
            "RIG-02": "OPEN",
            "RIG-02A": "PASS" if ok else "FAIL",
            "RIG-02B": "NOT_STARTED",
            "RIG-02C": "NOT_STARTED",
            "RIG-02D": "NOT_STARTED",
            "RIG-02E": "NOT_STARTED",
        },
        "protected": {
            "FACE_PRODUCT_LOCK": "DECLARED",
            "BODY_CANONICAL_V1": "FULL_LOCK",
            "TALKING": "GO",
            "Eye_Calibration": "PROTECTED",
            "sotHashesUnchanged": hashes,
            "frozenTable": PROTECTED_SOT_SHA256,
        },
        "artifacts": {
            "contract": str(SEM / "NURION_RETARGET_ADAPTER_CONTRACT_V1.json"),
            "engine": "fast_track/runtime/retarget/engine.py",
            "profiles": [
                str(SEM / "retarget_profiles/mjn_legacy_profile_v1.json"),
                str(SEM / "retarget_profiles/jake_cc_profile_v1.json"),
            ],
        },
        "contractTests": payload,
        "next": "NURION-RIG-02B_MJN_ADAPTER_CALIBRATION",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["presentationLayer"] = (
        "FACE+BODY LOCKED / TALKING GO — NURION-RIG-02 OPEN; RIG-02A Adapter Contract "
        + ("PASS" if ok else "FAIL")
        + "; next RIG-02B MJN Adapter"
    )
    ids = {e.get("id") for e in ledger.get("entries", [])}
    if "NURION-RIG-02A" not in ids:
        ledger["entries"].append(
            {
                "id": "NURION-RIG-02A",
                "type": "RETARGET_ADAPTER_CONTRACT",
                "mutation": 0,
                "scope": "RetargetEngine + DonorSkeletonProfile registry; no SoT mutation",
                "evidence": str(RECEIPT),
                "status": "PASS" if ok else "FAIL",
                "rig02Pass": "NOT_DECLARED",
                "next": "NURION-RIG-02B",
            }
        )
    ledger["rig02Track"] = {
        "status": "OPEN",
        "rig02a": "PASS" if ok else "FAIL",
        "rig02b": "NOT_STARTED",
        "rig02c": "NOT_STARTED",
        "rig02d": "NOT_STARTED",
        "rig02e": "NOT_STARTED",
        "rig02Pass": "NOT_DECLARED",
        "updatedAtUtc": ts,
    }
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(RECEIPT), "status": receipt["status"], "tests": payload}, ensure_ascii=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
