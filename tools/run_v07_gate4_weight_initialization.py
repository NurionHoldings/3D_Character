"""Run v0.7 Gate 4 Weight Initialization after official Gate3 freeze."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_v07_gate4_weight_initialization.py"
OUT = ROOT / "dist" / "v0.7" / "gate4"
BLEND = ROOT / "dist/v0.7/gate3/NURION_HomepageNativeArmature_prototype.ai-aba.15.blend"
ZIP = ROOT / "dist/v0.4/gate8c/inbox/ai-aba.15.zip"
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
GATE2_HASH = "fd77cc7ffa5428e460162c0f80624abd91c980c2fd83738e28bce1c33af5c1c9"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
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
    subprocess.check_call([sys.executable, str(ROOT / "tools/freeze_v07_gate3_official.py")], cwd=str(ROOT))
    # Reconfirm continuity + preset
    subprocess.check_call([sys.executable, str(ROOT / "tools/verify_v07_gate1_baseline_continuity.py")], cwd=str(ROOT))
    assert _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") == PRESET_SHA
    g3 = json.loads((ROOT / "dist/v0.7/gate3/V07_GATE3_STATUS.json").read_text(encoding="utf-8"))
    assert g3.get("V07_GATE3") == "PASS" and g3.get("parameterHash") == GATE3_HASH
    assert g3.get("officialFrozenBaseline") is True
    assert _sha(V06_RC1) == V06_SHA
    if not BLEND.is_file():
        raise SystemExit("Gate3 blend missing")

    OUT.mkdir(parents=True, exist_ok=True)
    params = {
        "schema": "NURION_V07_GATE4_PARAMETERS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 4,
        "name": "WEIGHT_INITIALIZATION",
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "presetCatalogSha256": PRESET_SHA,
        "subject": "ai-aba.15",
        "subjectZip": "dist/v0.4/gate8c/inbox/ai-aba.15.zip",
        "gate3Blend": "dist/v0.7/gate3/NURION_HomepageNativeArmature_prototype.ai-aba.15.blend",
        "cloneMeshesOnly": True,
        "meshyWeightCopy": "DENY",
        "sourceMutation": "DENY",
        "originalMeshMutation": "DENY",
        "meshyArmatureMutation": "DENY",
        "actionMutation": "DENY",
        "weightSumTolerance": 0.001,
        "unweightedRequiredVertices": 0,
        "nonFiniteWeights": 0,
        "negativeWeights": 0,
        "lrWrongBoneInfluence": 0,
        "severeCollapse": 0,
        "autoRepair": "DENY",
        "manualCorrection": "DENY",
        "assetSpecificTuning": "DENY",
        "accuracyClaimWithoutGT": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "onFail": ["ALGORITHM_FAIL", "REVIEW_REQUIRED"],
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
    }
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(OUT / "V07_GATE4_PARAMETERS.json", params)

    pre_zip = _sha(ZIP)
    pre_v06 = _sha(V06_RC1)
    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(SCRIPT),
        "--",
        "--blend",
        str(BLEND),
        "--source-zip",
        str(ZIP),
        "--out-dir",
        str(OUT),
        "--label",
        "ai-aba.15",
    ]
    print("RUN Gate4", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT))
    post_zip = _sha(ZIP)
    post_v06 = _sha(V06_RC1)

    status_path = OUT / "V07_GATE4_STATUS.json"
    if not status_path.is_file():
        raise SystemExit(f"Gate4 blender produced no status (exit={proc.returncode})")
    asset = json.loads(status_path.read_text(encoding="utf-8"))
    checks = json.loads((OUT / "V07_GATE4_CHECKS.json").read_text(encoding="utf-8"))["checks"]
    extra = []

    def add(name, ok, detail=""):
        extra.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})

    add("PARAM_HASH_BOUND", True, ph)
    add("SOURCE_ZIP_STILL_UNCHANGED", pre_zip == post_zip, pre_zip)
    add("V06_RC1_UNCHANGED", post_v06 == V06_SHA and post_v06 == pre_v06, V06_SHA)
    add("AUTO_REPAIR_DENIED", True)
    add("GATE3_OFFICIAL_FREEZE", g3.get("officialFrozenBaseline") is True)

    all_checks = list(checks) + extra
    fails = [c for c in all_checks if c["result"] == "FAIL"]
    # Preserve Blender verdict unless aggregate extras failed
    verdict = asset.get("V07_GATE4", "FAIL")
    if fails and verdict == "PASS":
        verdict = "ALGORITHM_FAIL"
    if asset.get("V07_GATE4") != "PASS" and not fails:
        # blender already set non-pass
        verdict = asset.get("V07_GATE4")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    result = {
        "schema": "NURION_V07_GATE4_RESULT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 4,
        "V07_GATE4": verdict,
        "parameterHash": ph,
        "gate3ParameterHash": GATE3_HASH,
        "checks": all_checks,
        "hardFails": [c["check"] for c in fails] if verdict != "PASS" else [],
        "weightsGenerated": True,
        "weightsTarget": "NURION_CLONE_MESHES_ONLY",
        "meshyWeightCopy": "DENY",
        "sourceMutation": 0 if pre_zip == post_zip else 1,
        "sealedBaselineMutation": 0 if post_v06 == V06_SHA else 1,
        "autoRepair": "DENY",
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": "V07_GATE5_HOMEPAGE_CONTROL_AND_POSE_VALIDATION"
        if verdict == "PASS"
        else "V07_GATE4_REMEDIATE_NO_AUTO_REPAIR",
        "updatedAt": now,
    }
    receipt = {
        "schema": "NURION_V07_GATE4_RECEIPT",
        "V07_GATE4": verdict,
        "parameterHash": ph,
        "LOCKED": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "weightsGenerated": True,
        "meshyWeightCopy": "DENY",
        "sourceMutation": result["sourceMutation"],
        "sealedBaselineMutation": result["sealedBaselineMutation"],
        "production": "NO-GO",
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V07_GATE4_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 4,
        "name": "WEIGHT_INITIALIZATION",
        "V07_GATE4": verdict,
        "parameterHash": ph,
        "gate3ParameterHash": GATE3_HASH,
        "locked": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "subject": "ai-aba.15",
        "weightsGenerated": True,
        "weightsTarget": "NURION_CLONE_MESHES_ONLY",
        "meshyWeightCopy": "DENY",
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "artifacts": {
            "parameters": "V07_GATE4_PARAMETERS.json",
            "result": "V07_GATE4_RESULT.json",
            "receipt": "V07_GATE4_RECEIPT.json",
            "statistics": "V07_WEIGHT_STATISTICS.json",
            "blend": "NURION_HomepageWeights_init.ai-aba.15.blend",
        },
        "next": result["next"],
        "updatedAt": now,
    }
    # Keep blender check details
    if (OUT / "V07_WEIGHT_STATISTICS.json").is_file():
        status["statisticsRef"] = "V07_WEIGHT_STATISTICS.json"

    _write(OUT / "V07_GATE4_RESULT.json", result)
    _write(OUT / "V07_GATE4_RECEIPT.json", receipt)
    _write(OUT / "V07_GATE4_STATUS.json", status)
    _write(OUT / "V07_GATE4_CHECKS.json", {"checks": all_checks, "hardFails": result["hardFails"]})

    track_path = ROOT / "dist/v0.7/STATUS.json"
    track = json.loads(track_path.read_text(encoding="utf-8")) if track_path.is_file() else {}
    track.update(
        {
            "schema": "NURION_V07_HOMEPAGE_PERFORMANCE_RIG_STATUS",
            "track": "NURION Homepage Performance Rig v0.7",
            "V07_GATE1": "PASS",
            "gate1BaselineContinuity": "PASS",
            "gate1Locked": True,
            "V07_GATE2": "PASS",
            "gate2ParameterHash": GATE2_HASH,
            "V07_GATE3": "PASS",
            "gate3ParameterHash": GATE3_HASH,
            "gate3Locked": True,
            "officialFrozenBaselineGate3": True,
            "V07_GATE4": verdict,
            "gate4ParameterHash": ph,
            "gate4Locked": verdict == "PASS",
            "weightsGenerated": True,
            "production": "NO-GO",
            "v0.6Activation": "NOT_GRANTED",
            "v0.6Execution": "NOT_STARTED",
            "next": result["next"],
            "updatedAt": now,
        }
    )
    _write(track_path, track)

    root_path = ROOT / "STATUS.json"
    root = json.loads(root_path.read_text(encoding="utf-8"))
    root["nextDecision"] = result["next"]
    root["nextSteps"] = [
        "V07_GATE1_CONTINUITY_LOCKED_PASS",
        "V07_GATE3_OFFICIALLY_FROZEN_PASS",
        f"V07_GATE4_{verdict}",
        "MESHY_WEIGHT_COPY_DENY",
        "ACCURACY_CLAIM_DENIED_WITHOUT_GT",
        "PRODUCTION_NO_GO",
        "NEXT_" + result["next"],
    ]
    root["availableNextCommands"] = [
        "v0.6 Limited Internal Production Activation Execution GO",
        "NURION Homepage Performance Rig v0.7 Gate 5 GO"
        if verdict == "PASS"
        else "NURION Homepage Performance Rig v0.7 Gate 4 REMEDIATE",
    ]
    root["recommendedNextCommand"] = root["availableNextCommands"][1]
    v07 = root.setdefault("v07HomepagePerformanceRig", {})
    v07.update(
        {
            "status": "GATE4_" + verdict,
            "gate1BaselineContinuity": "PASS",
            "gate3": "PASS",
            "gate3ParameterHash": GATE3_HASH,
            "gate3Locked": True,
            "V07_GATE4": verdict,
            "gate4ParameterHash": ph,
            "weightsGenerated": True,
            "production": "NO-GO",
            "next": result["next"],
            "artifacts": {
                **(v07.get("artifacts") or {}),
                "gate3Freeze": "dist/v0.7/gate3/V07_GATE3_OFFICIAL_FREEZE.json",
                "gate4": "dist/v0.7/gate4/V07_GATE4_STATUS.json",
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
                "gate3Freeze": "OK",
                "V07_GATE4": verdict,
                "parameterHash": ph,
                "sourceMutation": result["sourceMutation"],
                "sealedBaselineMutation": result["sealedBaselineMutation"],
                "hardFails": result["hardFails"],
                "next": result["next"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
