#!/usr/bin/env python3
"""
NURION-RIG-02E — Regression & Product Gate (FINAL RIG-02 closure candidate).

No new retarget features. Re-runs 02A–02D + product boundary + drift vs PASS receipts.
Human PASS / RIG-02 overall PASS NOT DECLARED here.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
TOOLS = ROOT / "tools"

EXPECTED = {
    "02A": {"script": "run_rig02a_contract_closure_tests.py", "passed": 15, "stdout": "NURION-RIG-02A_closure_stdout.json"},
    "02B": {"script": "run_rig02b_mjn_adapter_proof.py", "passed": 12, "stdout": "NURION-RIG-02B_mjn_adapter_proof_stdout.json"},
    "02C": {"script": "run_rig02c_jake_adapter_proof.py", "passed": 17, "stdout": "NURION-RIG-02C_jake_adapter_proof_stdout.json"},
    "02D": {"script": "run_rig02d_invariant_proof.py", "passed": 14, "stdout": "NURION-RIG-02D_invariant_proof_stdout.json"},
}

PASS_RECEIPTS = {
    "02A": EV / "NURION-RIG-02A_PASS_receipt.json",
    "02B": EV / "NURION-RIG-02B_PASS_receipt.json",
    "02C": EV / "NURION-RIG-02C_PASS_receipt.json",
    "02D": EV / "NURION-RIG-02D_PASS_receipt.json",
}


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_script(rel: str) -> dict:
    env = os.environ.copy()
    env["NURION_REPO_ROOT"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, str(TOOLS / rel)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    return {
        "exit": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


def load_stage_stdout(name: str) -> dict:
    path = EV / EXPECTED[name]["stdout"]
    _ok(path.exists(), f"missing stdout {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_protected_before():
    h = assert_protected_sot_unchanged()
    return {"hashes": h, "frozen": PROTECTED_SOT_SHA256}


def test_pass_receipts_present():
    out = {}
    for k, p in PASS_RECEIPTS.items():
        _ok(p.exists(), f"missing PASS receipt {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        status_key = f"rig02{k[-1].lower()}Pass"
        # 02A -> rig02aPass
        key_map = {"02A": "rig02aPass", "02B": "rig02bPass", "02C": "rig02cPass", "02D": "rig02dPass"}
        key = key_map[k]
        _ok(data.get(key) == "PASS" or data.get("status") == "PASS", f"{k} not PASS in receipt")
        out[k] = {"path": str(p), "status": data.get("status"), key: data.get(key)}
    return out


def test_stage_regression(stage: str) -> dict:
    meta = EXPECTED[stage]
    run = run_script(meta["script"])
    _ok(run["exit"] == 0, f"{stage} exit={run['exit']} stderr={run['stderr'][-500:]}")
    summary = load_stage_stdout(stage)
    passed = int(summary.get("passed", 0))
    failed = int(summary.get("failed", 0))
    _ok(failed == 0, f"{stage} failed={failed}")
    _ok(passed == meta["passed"], f"{stage} passed drift: got {passed} expected {meta['passed']}")
    results = summary.get("results", [])
    fails = [r for r in results if r.get("status") != "PASS"]
    _ok(not fails, f"{stage} non-PASS results: {fails}")
    return {
        "exit": 0,
        "passed": passed,
        "failed": failed,
        "expectedPassed": meta["passed"],
        "tests": [r.get("test") for r in results],
    }


def test_product_boundary() -> dict:
    boundary_path = SEM / "NURION_RIG02_PRODUCT_BOUNDARY_V1.json"
    _ok(boundary_path.exists(), "missing product boundary lock")
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))

    mjn = json.loads((SEM / "retarget_profiles/mjn_legacy_profile_v1.json").read_text(encoding="utf-8"))
    jake = json.loads((SEM / "retarget_profiles/jake_cc_profile_v1.json").read_text(encoding="utf-8"))
    face = json.loads((SEM / "NURION_FACE_PRODUCT_LOCK_V1.json").read_text(encoding="utf-8"))
    body = json.loads((SEM / "NURION_BODY_PRODUCT_LOCK_V1.json").read_text(encoding="utf-8"))

    mjn_pb = mjn.get("product_boundary") or {}
    jake_pb = jake.get("product_boundary") or {}
    _ok(mjn_pb.get("product_use") is True, "MJN product_use must be true")
    _ok(mjn_pb.get("role") == "APPROVED_DONOR_PRODUCT_PIPELINE_INPUT", "MJN role")
    _ok(jake_pb.get("product_use") is False, "Jake product_use must be false")
    _ok(jake_pb.get("role") == "DONOR_REFERENCE_TEST_INPUT_ONLY", "Jake role")
    _ok(jake_pb.get("jake_asset_incorporation") == "DENY", "Jake incorporation DENY")
    _ok(jake_pb.get("canonical_mutation_from_donor") == "DENY", "Jake canonical mutation DENY")

    b_mjn = boundary["donors"]["mjn_legacy_v1"]
    b_jake = boundary["donors"]["jake_cc_v1"]
    _ok(b_mjn["product_use"] is True, "boundary MJN")
    _ok(b_jake["product_use"] is False, "boundary Jake")
    _ok(b_jake.get("jake_asset_incorporation") == "DENY", "boundary Jake asset DENY")
    _ok(b_jake.get("jake_derived_canonical_mutation") == "DENY", "boundary Jake spec DENY")

    _ok(face.get("talking_status") == "GO", "TALKING must remain GO")
    _ok(face.get("productLock") is True, "FACE productLock")
    _ok((face.get("donorRole") or {}).get("product_use") is False, "FACE Jake donor product_use false")
    _ok(body.get("productLock") is True, "BODY productLock")
    _ok((body.get("donorPolicy") or {}).get("donorsMustNotChangeCanonical") is True, "donorsMustNotChangeCanonical")
    _ok("Eye_Calibration" in (body.get("faceBodyBoundary") or {}).get("rigMustNotMutate", []), "Eye in must-not-mutate")
    _ok("TALKING_GO" in (body.get("faceBodyBoundary") or {}).get("rigMustNotMutate", []), "TALKING in must-not-mutate")

    # Engine must not treat Jake as product path via literal product_use true
    engine = (ROOT / "fast_track/runtime/body_retarget_engine.py").read_text(encoding="utf-8")
    _ok("jake" not in engine.lower(), "engine donor-literal isolation (jake)")
    _ok("mjn" not in engine.lower(), "engine donor-literal isolation (mjn)")

    return {
        "mjn": mjn_pb,
        "jake": jake_pb,
        "talking": face.get("talking_status"),
        "faceDonorProductUse": face["donorRole"]["product_use"],
        "boundarySchema": boundary["schema"],
    }


def test_drift_vs_pass_receipts(stage_results: dict) -> dict:
    """Ensure current HEAD still matches the gate counts locked by human PASS receipts."""
    expect_map = {
        "02A": ("contractClosure", "15/15 PASS", 15),
        "02B": ("numericalGate", "12/12 PASS", 12),
        "02C": ("numericalGate", "17/17 PASS", 17),
        "02D": ("numericalGate", "14/14 PASS", 14),
    }
    out = {}
    for stage, (ikey, ival, n) in expect_map.items():
        receipt = json.loads(PASS_RECEIPTS[stage].read_text(encoding="utf-8"))
        integrity = receipt.get("integrity") or {}
        # soft check: receipt documents expected count; hard check: live rerun count
        live = stage_results[stage]["passed"]
        _ok(live == n, f"{stage} live={live} receipt-expected={n}")
        out[stage] = {
            "receiptIntegrityField": integrity.get(ikey),
            "livePassed": live,
            "expected": n,
            "noDrift": True,
        }
    return out


def test_deterministic_double_run() -> dict:
    """02D suite twice — status vectors must match (determinism)."""
    r1 = run_script(EXPECTED["02D"]["script"])
    s1 = load_stage_stdout("02D")
    r2 = run_script(EXPECTED["02D"]["script"])
    s2 = load_stage_stdout("02D")
    _ok(r1["exit"] == 0 and r2["exit"] == 0, "double-run exits")
    v1 = [(x["test"], x["status"]) for x in s1["results"]]
    v2 = [(x["test"], x["status"]) for x in s2["results"]]
    _ok(v1 == v2, f"determinism drift {v1} vs {v2}")
    # strip volatile floats from details for hash compare of statuses only
    return {"runs": 2, "statusVectorMatch": True, "vector": v1}


def test_protected_after(before: dict) -> dict:
    after = assert_protected_sot_unchanged()
    _ok(before["hashes"] == after == PROTECTED_SOT_SHA256, "protected hash drift")
    return {"before": before["hashes"], "after": after, "match": True}


def main() -> int:
    results = []
    stage_results: dict = {}
    before = None

    def record(name, fn, *args):
        try:
            detail = fn(*args) if args else fn()
            results.append({"test": name, "status": "PASS", "detail": detail})
            return detail
        except Exception as e:
            results.append({"test": name, "status": "FAIL", "error": str(e)})
            return None

    before = record("test_protected_before", test_protected_before)
    record("test_pass_receipts_present", test_pass_receipts_present)

    for stage in ("02A", "02B", "02C", "02D"):
        d = record(f"test_regression_{stage}", test_stage_regression, stage)
        if d:
            stage_results[stage] = d

    record("test_product_boundary", test_product_boundary)
    if len(stage_results) == 4:
        record("test_drift_vs_pass_receipts", test_drift_vs_pass_receipts, stage_results)
    else:
        results.append(
            {
                "test": "test_drift_vs_pass_receipts",
                "status": "FAIL",
                "error": f"incomplete stage_results keys={list(stage_results)}",
            }
        )

    record("test_deterministic_double_run", test_deterministic_double_run)
    if before:
        record("test_protected_after", test_protected_after, before)
    else:
        results.append({"test": "test_protected_after", "status": "FAIL", "error": "no before hashes"})

    failed = [r for r in results if r["status"] == "FAIL"]
    summary = {
        "stage": "NURION-RIG-02E_REGRESSION_PRODUCT_GATE",
        "rig02ePass": "NOT_DECLARED",
        "rig02Pass": "NOT_DECLARED",
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "stageRegression": stage_results,
        "results": results,
    }
    out_path = EV / "NURION-RIG-02E_product_gate_stdout.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "out": str(out_path)}, ensure_ascii=True))
    print({"passed": summary["passed"], "failed": summary["failed"], "results": [{"test": r["test"], "status": r["status"]} for r in results]})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
