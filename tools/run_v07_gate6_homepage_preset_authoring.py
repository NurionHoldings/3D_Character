"""Run v0.7 Gate 6 Homepage Preset Authoring."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_v07_gate6_homepage_preset_authoring.py"
OUT = ROOT / "dist" / "v0.7" / "gate6"
BLEND5 = ROOT / "dist/v0.7/gate5/NURION_HomepageControlRig.ai-aba.15.blend"
BLEND4 = ROOT / "dist/v0.7/gate4/NURION_HomepageWeights_init.ai-aba.15.blend"
BLEND3 = ROOT / "dist/v0.7/gate3/NURION_HomepageNativeArmature_prototype.ai-aba.15.blend"
ZIP = ROOT / "dist/v0.4/gate8c/inbox/ai-aba.15.zip"
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
GATE2_HASH = "fd77cc7ffa5428e460162c0f80624abd91c980c2fd83738e28bce1c33af5c1c9"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
GATE5_HASH = "a240f7c1925daf11b32aafdd409c2233238d84ef23333bb6e31be761719daea3"
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
    subprocess.check_call([sys.executable, str(ROOT / "tools/freeze_v07_gate5_official.py")], cwd=str(ROOT))
    subprocess.check_call([sys.executable, str(ROOT / "tools/verify_v07_gate1_baseline_continuity.py")], cwd=str(ROOT))
    assert _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") == PRESET_SHA
    assert _sha(V06_RC1) == V06_SHA
    g5 = json.loads((ROOT / "dist/v0.7/gate5/V07_GATE5_STATUS.json").read_text(encoding="utf-8"))
    assert g5.get("V07_GATE5") == "PASS" and g5.get("parameterHash") == GATE5_HASH

    OUT.mkdir(parents=True, exist_ok=True)
    params = {
        "schema": "NURION_V07_GATE6_PARAMETERS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 6,
        "name": "HOMEPAGE_PRESET_AUTHORING",
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate5ParameterHash": GATE5_HASH,
        "presetCatalogSha256": PRESET_SHA,
        "subject": "ai-aba.15",
        "presets": [p["id"] for p in json.loads((ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json").read_text(encoding="utf-8"))["presets"]],
        "actionPrefix": "NURION_Homepage_",
        "meshyActionCopy": "DENY",
        "videoPerformanceCopy": "V0.8_OUT_OF_SCOPE",
        "loopPositionDriftMaxCm": 1.0,
        "loopRotationDriftMaxDeg": 2.0,
        "fps": [24, 30, 60],
        "v06HandoffContract": True,
        "accuracyClaimWithoutGT": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
    }
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(OUT / "V07_GATE6_PARAMETERS.json", params)

    pre = {k: _sha(p) for k, p in {"zip": ZIP, "g3": BLEND3, "g4": BLEND4, "g5": BLEND5, "v06": V06_RC1}.items()}
    cmd = [
        str(BLENDER), "--background", "--python", str(SCRIPT), "--",
        "--blend", str(BLEND5),
        "--source-zip", str(ZIP),
        "--gate3-blend", str(BLEND3),
        "--gate4-blend", str(BLEND4),
        "--gate5-blend", str(BLEND5),
        "--out-dir", str(OUT),
        "--label", "ai-aba.15",
    ]
    print("RUN Gate6", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT))
    post = {k: _sha(p) for k, p in {"zip": ZIP, "g3": BLEND3, "g4": BLEND4, "g5": BLEND5, "v06": V06_RC1}.items()}

    status_path = OUT / "V07_GATE6_STATUS.json"
    if not status_path.is_file():
        raise SystemExit(f"Gate6 missing status (exit={proc.returncode})")
    asset = json.loads(status_path.read_text(encoding="utf-8"))
    checks = json.loads((OUT / "V07_GATE6_CHECKS.json").read_text(encoding="utf-8"))["checks"]

    extra = []
    def add(name, ok, detail=""):
        extra.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})
    add("PARAM_HASH_BOUND", True, ph)
    add("SOURCE_ZIP_STILL_UNCHANGED", pre["zip"] == post["zip"])
    add("GATE3_STILL_UNCHANGED", pre["g3"] == post["g3"])
    add("GATE4_STILL_UNCHANGED", pre["g4"] == post["g4"])
    add("GATE5_STILL_UNCHANGED", pre["g5"] == post["g5"])
    add("V06_RC1_UNCHANGED", post["v06"] == V06_SHA)
    add("HANDOFF_ARTIFACT", (OUT / "V07_V06_HANDOFF.json").is_file())

    all_checks = list(checks) + extra
    fails = [c for c in all_checks if c["result"] == "FAIL"]
    verdict = asset.get("V07_GATE6", "FAIL")
    if fails and verdict == "PASS":
        verdict = "ALGORITHM_FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    result = {
        "schema": "NURION_V07_GATE6_RESULT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 6,
        "V07_GATE6": verdict,
        "parameterHash": ph,
        "gate5ParameterHash": GATE5_HASH,
        "checks": all_checks,
        "hardFails": [c["check"] for c in fails] if verdict != "PASS" else [],
        "presetCount": asset.get("presetCount"),
        "actions": asset.get("actions"),
        "meshyActionCopy": "DENY",
        "videoPerformanceCopy": "V0.8_OUT_OF_SCOPE",
        "sourceMutation": 0 if pre["zip"] == post["zip"] else 1,
        "gate3Mutation": 0 if pre["g3"] == post["g3"] else 1,
        "gate4Mutation": 0 if pre["g4"] == post["g4"] else 1,
        "gate5Mutation": 0 if pre["g5"] == post["g5"] else 1,
        "sealedBaselineMutation": 0 if post["v06"] == V06_SHA else 1,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": "V07_GATE7_HOLDOUT_AND_DETERMINISM" if verdict == "PASS" else "V07_GATE6_REMEDIATE",
        "updatedAt": now,
    }
    receipt = {
        "schema": "NURION_V07_GATE6_RECEIPT",
        "V07_GATE6": verdict,
        "parameterHash": ph,
        "LOCKED": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "production": "NO-GO",
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V07_GATE6_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 6,
        "name": "HOMEPAGE_PRESET_AUTHORING",
        "V07_GATE6": verdict,
        "parameterHash": ph,
        "gate5ParameterHash": GATE5_HASH,
        "locked": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "subject": "ai-aba.15",
        "presetCount": asset.get("presetCount"),
        "actions": asset.get("actions"),
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "artifacts": {
            "parameters": "V07_GATE6_PARAMETERS.json",
            "result": "V07_GATE6_RESULT.json",
            "receipt": "V07_GATE6_RECEIPT.json",
            "evidence": "V07_GATE6_PRESET_EVIDENCE.json",
            "handoff": "V07_V06_HANDOFF.json",
            "blend": "NURION_HomepagePresets.ai-aba.15.blend",
        },
        "next": result["next"],
        "updatedAt": now,
    }
    _write(OUT / "V07_GATE6_RESULT.json", result)
    _write(OUT / "V07_GATE6_RECEIPT.json", receipt)
    _write(OUT / "V07_GATE6_STATUS.json", status)
    _write(OUT / "V07_GATE6_CHECKS.json", {"checks": all_checks, "hardFails": result["hardFails"]})

    track_path = ROOT / "dist/v0.7/STATUS.json"
    track = json.loads(track_path.read_text(encoding="utf-8")) if track_path.is_file() else {}
    track.update({
        "schema": "NURION_V07_HOMEPAGE_PERFORMANCE_RIG_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate1BaselineContinuity": "PASS",
        "V07_GATE3": "PASS",
        "V07_GATE4": "PASS",
        "V07_GATE5": "PASS",
        "gate5ParameterHash": GATE5_HASH,
        "officialFrozenBaselineGate5": True,
        "V07_GATE6": verdict,
        "gate6ParameterHash": ph,
        "gate6Locked": verdict == "PASS",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": result["next"],
        "updatedAt": now,
    })
    _write(track_path, track)

    root_path = ROOT / "STATUS.json"
    root = json.loads(root_path.read_text(encoding="utf-8"))
    root["nextDecision"] = result["next"]
    root["nextSteps"] = [
        "V07_GATE5_OFFICIALLY_FROZEN_PASS",
        f"V07_GATE6_{verdict}",
        "MESHY_ACTION_COPY_DENY",
        "V08_OUT_OF_SCOPE",
        "PRODUCTION_NO_GO",
        "NEXT_" + result["next"],
    ]
    root["availableNextCommands"] = [
        "v0.6 Limited Internal Production Activation Execution GO",
        "NURION Homepage Performance Rig v0.7 Gate 7 GO" if verdict == "PASS" else "NURION Homepage Performance Rig v0.7 Gate 6 REMEDIATE",
    ]
    root["recommendedNextCommand"] = root["availableNextCommands"][1]
    v07 = root.setdefault("v07HomepagePerformanceRig", {})
    v07.update({
        "status": "GATE6_" + verdict,
        "gate5": "PASS",
        "gate5ParameterHash": GATE5_HASH,
        "gate5Locked": True,
        "V07_GATE6": verdict,
        "gate6ParameterHash": ph,
        "production": "NO-GO",
        "next": result["next"],
        "artifacts": {
            **(v07.get("artifacts") or {}),
            "gate5Freeze": "dist/v0.7/gate5/V07_GATE5_OFFICIAL_FREEZE.json",
            "gate6": "dist/v0.7/gate6/V07_GATE6_STATUS.json",
            "v06Handoff": "dist/v0.7/gate6/V07_V06_HANDOFF.json",
        },
    })
    pr = root.get("v06ProductionReadiness") or {}
    if pr:
        pr["activation"] = "NOT_GRANTED"
        pr["activationExecution"] = "NOT_STARTED"
        root["v06ProductionReadiness"] = pr
    root_path.write_text(json.dumps(root, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "gate5Freeze": "OK",
        "V07_GATE6": verdict,
        "parameterHash": ph,
        "hardFails": result["hardFails"],
        "actions": result.get("actions"),
        "next": result["next"],
    }, indent=2, ensure_ascii=False))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
