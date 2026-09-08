"""Aggregate runner for v0.7 Gate 3 Native Armature Prototype."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_v07_gate3_native_armature_prototype.py"
OUT = ROOT / "dist" / "v0.7" / "gate3"
ZIP = ROOT / "dist/v0.4/gate8c/inbox/ai-aba.15.zip"
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
GATE2_HASH = "fd77cc7ffa5428e460162c0f80624abd91c980c2fd83738e28bce1c33af5c1c9"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"
V06_RC1 = ROOT / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
V06_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _param_hash(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    # 1) Restore official preset + verify continuity
    subprocess.check_call([sys.executable, str(ROOT / "tools/restore_v07_preset_catalog_official.py")], cwd=str(ROOT))
    rc = subprocess.call([sys.executable, str(ROOT / "tools/verify_v07_gate1_baseline_continuity.py")], cwd=str(ROOT))
    if rc != 0:
        raise SystemExit("Gate1 baseline continuity HOLD — refuse Gate3")

    continuity = json.loads((ROOT / "dist/v0.7/gate1/V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8"))
    assert continuity["V07_GATE1_BASELINE_CONTINUITY"] == "PASS"
    assert _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") == PRESET_SHA

    g2 = json.loads((ROOT / "dist/v0.7/gate2/V07_GATE2_STATUS.json").read_text(encoding="utf-8"))
    assert g2.get("V07_GATE2") == "PASS" and g2.get("parameterHash") == GATE2_HASH
    assert _sha(V06_RC1) == V06_SHA

    OUT.mkdir(parents=True, exist_ok=True)
    params = {
        "schema": "NURION_V07_GATE3_PARAMETERS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 3,
        "name": "NATIVE_ARMATURE_PROTOTYPE",
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "presetCatalogSha256": PRESET_SHA,
        "subject": "ai-aba.15",
        "subjectZip": "dist/v0.4/gate8c/inbox/ai-aba.15.zip",
        "cloneOnly": True,
        "weightGeneration": "DENY",
        "meshMutation": "DENY",
        "sourceMutation": "DENY",
        "sealedBaselineMutation": "DENY",
        "meshyBonesAsGroundTruth": "DENY",
        "estimationMethod": "MESH_BOUNDS_PROPORTIONAL_HOMEPAGE_REST",
        "collection": "NURION_HomepagePerformanceRig",
        "armature": "NURION_HomepageNativeArmature",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
    }
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(OUT / "V07_GATE3_PARAMETERS.json", params)

    pre_zip = _sha(ZIP)
    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(SCRIPT),
        "--",
        "--zip",
        str(ZIP),
        "--out-dir",
        str(OUT),
        "--label",
        "ai-aba.15",
    ]
    print("RUN Gate3", flush=True)
    subprocess.check_call(cmd, cwd=str(ROOT))
    post_zip = _sha(ZIP)
    post_v06 = _sha(V06_RC1)

    asset_status = json.loads((OUT / "V07_GATE3_STATUS.json").read_text(encoding="utf-8"))
    checks = json.loads((OUT / "V07_GATE3_CHECKS.json").read_text(encoding="utf-8"))["checks"]
    # Aggregate extras
    extra = []

    def add(name, ok, detail=""):
        extra.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    add("PARAM_HASH_BOUND", True, ph)
    add("SOURCE_ZIP_STILL_UNCHANGED", pre_zip == post_zip, pre_zip)
    add("V06_RC1_UNCHANGED", post_v06 == V06_SHA, V06_SHA)
    add("WEIGHTS_STILL_DENIED", asset_status.get("weightsGenerated") is False)
    add("ARMATURE_PROTOTYPE_CREATED", asset_status.get("armatureGenerated") is True)

    all_checks = list(checks) + extra
    fails = [c for c in all_checks if c["result"] == "FAIL"]
    verdict = "PASS" if not fails and asset_status.get("V07_GATE3") == "PASS" else "FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    result = {
        "schema": "NURION_V07_GATE3_RESULT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 3,
        "V07_GATE3": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "baselineContinuity": "PASS",
        "presetCatalogSha256": PRESET_SHA,
        "checks": all_checks,
        "hardFails": [c["check"] for c in fails],
        "subject": "ai-aba.15",
        "armatureGenerated": True,
        "weightsGenerated": False,
        "animationsGenerated": False,
        "sourceMutation": 0 if pre_zip == post_zip else 1,
        "sealedBaselineMutation": 0 if post_v06 == V06_SHA else 1,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": "V07_GATE4_WEIGHT_INITIALIZATION" if verdict == "PASS" else "V07_GATE3_REMEDIATE",
        "updatedAt": now,
    }
    receipt = {
        "schema": "NURION_V07_GATE3_RECEIPT",
        "V07_GATE3": verdict,
        "parameterHash": ph,
        "LOCKED": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "armatureGenerated": True,
        "weightsGenerated": False,
        "sourceMutation": result["sourceMutation"],
        "sealedBaselineMutation": result["sealedBaselineMutation"],
        "production": "NO-GO",
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V07_GATE3_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 3,
        "name": "NATIVE_ARMATURE_PROTOTYPE",
        "V07_GATE3": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "locked": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "baselineContinuity": "PASS",
        "subject": "ai-aba.15",
        "armatureGenerated": True,
        "weightsGenerated": False,
        "animationsGenerated": False,
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "artifacts": {
            "parameters": "V07_GATE3_PARAMETERS.json",
            "result": "V07_GATE3_RESULT.json",
            "receipt": "V07_GATE3_RECEIPT.json",
            "diagnostics": "V07_RIG_DIAGNOSTICS.json",
            "blend": "NURION_HomepageNativeArmature_prototype.ai-aba.15.blend",
        },
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V07_GATE3_RESULT.json", result)
    _write(OUT / "V07_GATE3_RECEIPT.json", receipt)
    _write(OUT / "V07_GATE3_STATUS.json", status)
    _write(OUT / "V07_GATE3_CHECKS.json", {"checks": all_checks, "hardFails": [c["check"] for c in fails]})

    track = {
        "schema": "NURION_V07_HOMEPAGE_PERFORMANCE_RIG_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "internalCoreModule": "Native Rig Reconstruction",
        "V07_GATE1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "gate1BaselineContinuity": "PASS",
        "V07_GATE2": "PASS",
        "gate2ParameterHash": GATE2_HASH,
        "gate2Locked": True,
        "V07_GATE3": verdict,
        "gate3ParameterHash": ph,
        "gate3Locked": verdict == "PASS",
        "armatureGenerated": True,
        "weightsGenerated": False,
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": result["next"],
        "updatedAt": now,
    }
    _write(ROOT / "dist/v0.7/STATUS.json", track)

    root_path = ROOT / "STATUS.json"
    root = json.loads(root_path.read_text(encoding="utf-8"))
    root["nextDecision"] = result["next"]
    root["nextSteps"] = [
        "V07_GATE1_BASELINE_CONTINUITY_PASS",
        "V07_GATE2_LOCKED_PASS",
        f"V07_GATE3_{verdict}",
        "WEIGHTS_NOT_GENERATED",
        "V06_ACTIVATION_NOT_GRANTED",
        "PRODUCTION_NO_GO",
        "NEXT_" + result["next"],
    ]
    root["availableNextCommands"] = [
        "v0.6 Limited Internal Production Activation Execution GO",
        "NURION Homepage Performance Rig v0.7 Gate 4 GO" if verdict == "PASS" else "NURION Homepage Performance Rig v0.7 Gate 3 REMEDIATE",
    ]
    root["recommendedNextCommand"] = root["availableNextCommands"][1]
    v07 = root.setdefault("v07HomepagePerformanceRig", {})
    v07.update(
        {
            "status": "GATE3_" + verdict,
            "gate1": "PASS",
            "gate1ParameterHash": GATE1_HASH,
            "gate1BaselineContinuity": "PASS",
            "gate2": "PASS",
            "gate2ParameterHash": GATE2_HASH,
            "V07_GATE3": verdict,
            "gate3ParameterHash": ph,
            "armatureGenerated": True,
            "weightsGenerated": False,
            "production": "NO-GO",
            "next": result["next"],
            "artifacts": {
                "gate1": "dist/v0.7/gate1/V07_GATE1_STATUS.json",
                "gate1Continuity": "dist/v0.7/gate1/V07_GATE1_BASELINE_CONTINUITY.json",
                "gate2": "dist/v0.7/gate2/V07_GATE2_STATUS.json",
                "gate3": "dist/v0.7/gate3/V07_GATE3_STATUS.json",
                "trackStatus": "dist/v0.7/STATUS.json",
            },
        }
    )
    pr = root.get("v06ProductionReadiness") or {}
    if pr:
        pr["activation"] = "NOT_GRANTED"
        pr["activationExecution"] = "NOT_STARTED"
        root["v06ProductionReadiness"] = pr
    root_path.write_text(json.dumps(root, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "baselineContinuity": "PASS",
                "presetSha": PRESET_SHA,
                "V07_GATE3": verdict,
                "parameterHash": ph,
                "weightsGenerated": False,
                "sourceMutation": result["sourceMutation"],
                "next": result["next"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
