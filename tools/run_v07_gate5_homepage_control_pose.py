"""Run v0.7 Gate 5 Homepage Control & Pose Validation."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_v07_gate5_homepage_control_pose.py"
OUT = ROOT / "dist" / "v0.7" / "gate5"
BLEND4 = ROOT / "dist/v0.7/gate4/NURION_HomepageWeights_init.ai-aba.15.blend"
BLEND3 = ROOT / "dist/v0.7/gate3/NURION_HomepageNativeArmature_prototype.ai-aba.15.blend"
ZIP = ROOT / "dist/v0.4/gate8c/inbox/ai-aba.15.zip"
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
GATE2_HASH = "fd77cc7ffa5428e460162c0f80624abd91c980c2fd83738e28bce1c33af5c1c9"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
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
    subprocess.check_call([sys.executable, str(ROOT / "tools/freeze_v07_gate4_official.py")], cwd=str(ROOT))
    subprocess.check_call([sys.executable, str(ROOT / "tools/verify_v07_gate1_baseline_continuity.py")], cwd=str(ROOT))
    assert _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") == PRESET_SHA
    assert _sha(V06_RC1) == V06_SHA
    g4 = json.loads((ROOT / "dist/v0.7/gate4/V07_GATE4_STATUS.json").read_text(encoding="utf-8"))
    assert g4.get("V07_GATE4") == "PASS" and g4.get("parameterHash") == GATE4_HASH
    assert g4.get("officialFrozenBaseline") is True

    OUT.mkdir(parents=True, exist_ok=True)
    params = {
        "schema": "NURION_V07_GATE5_PARAMETERS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 5,
        "name": "HOMEPAGE_CONTROL_AND_POSE_VALIDATION",
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "presetCatalogSha256": PRESET_SHA,
        "subject": "ai-aba.15",
        "controlRig": "NURION_HomepageControlRig",
        "deformRig": "NURION_HomepageDeformRig",
        "controlRoles": [
            "LookTarget",
            "HeadAim",
            "ChestAim",
            "HandTarget.L",
            "HandTarget.R",
            "PalmAim.L",
            "PalmAim.R",
            "Breath",
            "BodySway",
            "UIFocusTarget",
        ],
        "gestures": [
            "OPEN_PALM",
            "RELAXED",
            "POINT_UI",
            "WELCOME",
            "CONSULTATION_INVITE",
        ],
        "uiTargetMissMaxPx": 12,
        "eyeHeadDoubleTransform": 0,
        "manualCorrection": "DENY",
        "assetSpecificTuning": "DENY",
        "sourceMutation": "DENY",
        "gate3Mutation": "DENY",
        "gate4Mutation": "DENY",
        "sealedBaselineMutation": "DENY",
        "accuracyClaimWithoutGT": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
    }
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(OUT / "V07_GATE5_PARAMETERS.json", params)

    pre_zip = _sha(ZIP)
    pre_g3 = _sha(BLEND3)
    pre_g4 = _sha(BLEND4)
    pre_v06 = _sha(V06_RC1)

    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(SCRIPT),
        "--",
        "--blend",
        str(BLEND4),
        "--source-zip",
        str(ZIP),
        "--gate3-blend",
        str(BLEND3),
        "--gate4-blend",
        str(BLEND4),
        "--out-dir",
        str(OUT),
        "--label",
        "ai-aba.15",
    ]
    print("RUN Gate5", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT))
    post_zip = _sha(ZIP)
    post_g3 = _sha(BLEND3)
    post_g4 = _sha(BLEND4)
    post_v06 = _sha(V06_RC1)

    status_path = OUT / "V07_GATE5_STATUS.json"
    if not status_path.is_file():
        raise SystemExit(f"Gate5 missing status (exit={proc.returncode})")
    asset = json.loads(status_path.read_text(encoding="utf-8"))
    checks = json.loads((OUT / "V07_GATE5_CHECKS.json").read_text(encoding="utf-8"))["checks"]

    extra = []

    def add(name, ok, detail=""):
        extra.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})

    add("PARAM_HASH_BOUND", True, ph)
    add("SOURCE_ZIP_STILL_UNCHANGED", pre_zip == post_zip)
    add("GATE3_STILL_UNCHANGED", pre_g3 == post_g3)
    add("GATE4_STILL_UNCHANGED", pre_g4 == post_g4)
    add("V06_RC1_UNCHANGED", pre_v06 == post_v06 == V06_SHA)
    add("GATE4_OFFICIAL_FREEZE", True)

    all_checks = list(checks) + extra
    fails = [c for c in all_checks if c["result"] == "FAIL"]
    verdict = asset.get("V07_GATE5", "FAIL")
    if fails and verdict == "PASS":
        verdict = "ALGORITHM_FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    result = {
        "schema": "NURION_V07_GATE5_RESULT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 5,
        "V07_GATE5": verdict,
        "parameterHash": ph,
        "gate4ParameterHash": GATE4_HASH,
        "checks": all_checks,
        "hardFails": [c["check"] for c in fails] if verdict != "PASS" else [],
        "controlRig": "NURION_HomepageControlRig",
        "deformRig": "NURION_HomepageDeformRig",
        "uiTargetMissPx": asset.get("uiTargetMissPx"),
        "eyeHeadDoubleTransform": asset.get("eyeHeadDoubleTransform"),
        "sourceMutation": 0 if pre_zip == post_zip else 1,
        "gate3Mutation": 0 if pre_g3 == post_g3 else 1,
        "gate4Mutation": 0 if pre_g4 == post_g4 else 1,
        "sealedBaselineMutation": 0 if post_v06 == V06_SHA else 1,
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": "V07_GATE6_HOMEPAGE_PRESET_AUTHORING" if verdict == "PASS" else "V07_GATE5_REMEDIATE",
        "updatedAt": now,
    }
    receipt = {
        "schema": "NURION_V07_GATE5_RECEIPT",
        "V07_GATE5": verdict,
        "parameterHash": ph,
        "LOCKED": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "production": "NO-GO",
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V07_GATE5_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 5,
        "name": "HOMEPAGE_CONTROL_AND_POSE_VALIDATION",
        "V07_GATE5": verdict,
        "parameterHash": ph,
        "gate4ParameterHash": GATE4_HASH,
        "locked": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "subject": "ai-aba.15",
        "controlRig": "NURION_HomepageControlRig",
        "deformRig": "NURION_HomepageDeformRig",
        "gestures": params["gestures"],
        "uiTargetMissPx": asset.get("uiTargetMissPx"),
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "artifacts": {
            "parameters": "V07_GATE5_PARAMETERS.json",
            "result": "V07_GATE5_RESULT.json",
            "receipt": "V07_GATE5_RECEIPT.json",
            "evidence": "V07_GATE5_CONTROL_POSE_EVIDENCE.json",
            "blend": "NURION_HomepageControlRig.ai-aba.15.blend",
        },
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V07_GATE5_RESULT.json", result)
    _write(OUT / "V07_GATE5_RECEIPT.json", receipt)
    _write(OUT / "V07_GATE5_STATUS.json", status)
    _write(OUT / "V07_GATE5_CHECKS.json", {"checks": all_checks, "hardFails": result["hardFails"]})

    track_path = ROOT / "dist/v0.7/STATUS.json"
    track = json.loads(track_path.read_text(encoding="utf-8")) if track_path.is_file() else {}
    track.update(
        {
            "schema": "NURION_V07_HOMEPAGE_PERFORMANCE_RIG_STATUS",
            "track": "NURION Homepage Performance Rig v0.7",
            "gate1BaselineContinuity": "PASS",
            "V07_GATE3": "PASS",
            "gate3ParameterHash": GATE3_HASH,
            "V07_GATE4": "PASS",
            "gate4ParameterHash": GATE4_HASH,
            "officialFrozenBaselineGate4": True,
            "V07_GATE5": verdict,
            "gate5ParameterHash": ph,
            "gate5Locked": verdict == "PASS",
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
        "V07_GATE4_OFFICIALLY_FROZEN_PASS",
        f"V07_GATE5_{verdict}",
        "CONTROL_DEFORM_SEPARATED",
        "ACCURACY_CLAIM_DENIED_WITHOUT_GT",
        "PRODUCTION_NO_GO",
        "NEXT_" + result["next"],
    ]
    root["availableNextCommands"] = [
        "v0.6 Limited Internal Production Activation Execution GO",
        "NURION Homepage Performance Rig v0.7 Gate 6 GO"
        if verdict == "PASS"
        else "NURION Homepage Performance Rig v0.7 Gate 5 REMEDIATE",
    ]
    root["recommendedNextCommand"] = root["availableNextCommands"][1]
    v07 = root.setdefault("v07HomepagePerformanceRig", {})
    v07.update(
        {
            "status": "GATE5_" + verdict,
            "gate4": "PASS",
            "gate4ParameterHash": GATE4_HASH,
            "gate4Locked": True,
            "V07_GATE5": verdict,
            "gate5ParameterHash": ph,
            "production": "NO-GO",
            "next": result["next"],
            "artifacts": {
                **(v07.get("artifacts") or {}),
                "gate4Freeze": "dist/v0.7/gate4/V07_GATE4_OFFICIAL_FREEZE.json",
                "gate5": "dist/v0.7/gate5/V07_GATE5_STATUS.json",
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
                "gate4Freeze": "OK",
                "V07_GATE5": verdict,
                "parameterHash": ph,
                "uiMissPx": asset.get("uiTargetMissPx"),
                "mutations": {
                    "zip": result["sourceMutation"],
                    "gate3": result["gate3Mutation"],
                    "gate4": result["gate4Mutation"],
                    "v06": result["sealedBaselineMutation"],
                },
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
