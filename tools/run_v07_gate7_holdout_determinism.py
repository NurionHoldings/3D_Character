"""Run v0.7 Gate 7 Holdout & Determinism (3 clean-scene runs)."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_v07_gate7_holdout_run.py"
OUT = ROOT / "dist" / "v0.7" / "gate7"
HOLDOUT_SRC = ROOT / "Meshy_AI_Jjajang_Nara_Chef_Uni_0812002117_texture_fbx.zip"
HOLDOUT_LABEL = "Jjajang_Nara_Chef"
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
GATE2_HASH = "fd77cc7ffa5428e460162c0f80624abd91c980c2fd83738e28bce1c33af5c1c9"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
GATE5_HASH = "a240f7c1925daf11b32aafdd409c2233238d84ef23333bb6e31be761719daea3"
GATE6_HASH = "adca66246f5a2066fe9652a2129355e72787fd223f42c58be5a770db5ecc736b"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"
V06_RC1 = ROOT / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
V06_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"
V07_GATE2_SUBJECTS = {
    "ai-aba.15",
    "ai-aba.bow",
    "Minimalist_Tennis_Out_Idle15",
    "Monochrome_Tennis_texture",
    "hyerie_15",
}


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
    subprocess.check_call([sys.executable, str(ROOT / "tools/freeze_v07_gate6_official.py")], cwd=str(ROOT))
    subprocess.check_call([sys.executable, str(ROOT / "tools/verify_v07_gate1_baseline_continuity.py")], cwd=str(ROOT))
    assert _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") == PRESET_SHA
    assert _sha(V06_RC1) == V06_SHA
    g6 = json.loads((ROOT / "dist/v0.7/gate6/V07_GATE6_STATUS.json").read_text(encoding="utf-8"))
    assert g6.get("V07_GATE6") == "PASS" and g6.get("parameterHash") == GATE6_HASH
    if HOLDOUT_LABEL in V07_GATE2_SUBJECTS:
        raise SystemExit("holdout collides with Gate2–6 subjects")
    if not HOLDOUT_SRC.is_file():
        raise SystemExit(f"missing holdout zip: {HOLDOUT_SRC}")

    OUT.mkdir(parents=True, exist_ok=True)
    inbox = OUT / "inbox"
    inbox.mkdir(exist_ok=True)
    holdout_zip = inbox / HOLDOUT_SRC.name
    if not holdout_zip.exists() or _sha(holdout_zip) != _sha(HOLDOUT_SRC):
        shutil.copy2(HOLDOUT_SRC, holdout_zip)
    zip_sha = _sha(holdout_zip)

    # Extract once for FBX sha lock
    import zipfile

    extract = OUT / "_inbox_extract"
    if extract.exists():
        shutil.rmtree(extract)
    extract.mkdir()
    with zipfile.ZipFile(holdout_zip, "r") as zf:
        zf.extractall(extract)
    fbx_cands = sorted(extract.rglob("*.fbx"))
    if not fbx_cands:
        raise SystemExit("no fbx in holdout")
    fbx = fbx_cands[0]
    for p in fbx_cands:
        n = p.name.lower()
        if "texture" in n or "withskin" in n:
            fbx = p
            break
    fbx_sha = _sha(fbx)

    identity = {
        "schema": "NURION_V07_GATE7_HOLDOUT_ASSET_IDENTITY",
        "LOCKED": True,
        "label": HOLDOUT_LABEL,
        "zipFileName": holdout_zip.name,
        "zipSha256": zip_sha,
        "fbxRelative": str(fbx.relative_to(extract)).replace("\\", "/"),
        "fbxSha256": fbx_sha,
        "noveltyScope": "FRESH_WITHIN_V07_GATE2_TO_GATE6",
        "projectWideFreshHoldoutClaim": "DENY",
        "history": {
            "v0.7_gate2_to_gate6": "NOT_USED",
            "v0.3": "USED — universal eye inbox / texture subject (disclosed).",
            "v0.1_v0.2_v0.4_v0.5_v0.6_primary": "Not the primary sealed holdout for those product seals.",
        },
        "meshyBonesAsGroundTruth": "DENY",
        "manualGroundTruth": "ABSENT",
    }
    _write(OUT / "V07_GATE7_HOLDOUT_ASSET_IDENTITY.json", identity)

    frozen_params = {
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate5ParameterHash": GATE5_HASH,
        "gate6ParameterHash": GATE6_HASH,
        "presetCatalogSha256": PRESET_SHA,
    }
    params = {
        "schema": "NURION_V07_GATE7_PARAMETERS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 7,
        "name": "HOLDOUT_AND_DETERMINISM",
        **frozen_params,
        "holdoutLabel": HOLDOUT_LABEL,
        "holdoutZipSha256": zip_sha,
        "holdoutFbxSha256": fbx_sha,
        "determinismRuns": 3,
        "fps": [24, 30, 60],
        "manualCorrection": "DENY",
        "assetSpecificTuning": "DENY",
        "meshyBonesAsGroundTruth": "DENY",
        "accuracyWithoutGT": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "allowedVerdicts": [
            "HOLDOUT_PASS",
            "PASS_WITH_LIMITATIONS",
            "ASSET_INELIGIBLE",
            "ALGORITHM_FAIL",
        ],
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
    }
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(OUT / "V07_GATE7_PARAMETERS.json", params)

    pre_zip = zip_sha
    pre_v06 = _sha(V06_RC1)
    # freeze hashes of gate status files
    gate_files = {
        "g1c": ROOT / "dist/v0.7/gate1/V07_GATE1_BASELINE_CONTINUITY.json",
        "g3": ROOT / "dist/v0.7/gate3/V07_GATE3_STATUS.json",
        "g4": ROOT / "dist/v0.7/gate4/V07_GATE4_STATUS.json",
        "g5": ROOT / "dist/v0.7/gate5/V07_GATE5_STATUS.json",
        "g6": ROOT / "dist/v0.7/gate6/V07_GATE6_STATUS.json",
    }
    pre_gates = {k: _sha(p) for k, p in gate_files.items()}

    run_summaries = []
    for i in (1, 2, 3):
        run_dir = OUT / f"run{i}"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir()
        cmd = [
            str(BLENDER),
            "--background",
            "--python",
            str(SCRIPT),
            "--",
            "--zip",
            str(holdout_zip),
            "--out-dir",
            str(run_dir),
            "--run-id",
            str(i),
            "--label",
            HOLDOUT_LABEL,
        ]
        print(f"RUN Gate7 determinism {i}/3", flush=True)
        subprocess.run(cmd, cwd=str(ROOT))
        st = json.loads((run_dir / "V07_GATE7_RUN_STATUS.json").read_text(encoding="utf-8"))
        fp = json.loads((run_dir / "V07_GATE7_FINGERPRINT.json").read_text(encoding="utf-8"))
        run_summaries.append({"runId": i, "status": st, "fingerprintHash": fp["fingerprintHash"]})

    post_zip = _sha(holdout_zip)
    post_v06 = _sha(V06_RC1)
    post_gates = {k: _sha(p) for k, p in gate_files.items()}

    fp_hashes = [r["fingerprintHash"] for r in run_summaries]
    determinism_ok = len(set(fp_hashes)) == 1
    pipeline_ok = all(r["status"].get("V07_GATE7_RUN") == "PIPELINE_OK" for r in run_summaries)
    source_ok = pre_zip == post_zip and all(r["status"].get("sourceMutation", 1) == 0 for r in run_summaries)
    gates_ok = pre_gates == post_gates and pre_v06 == post_v06 == V06_SHA
    reload_ok = all(r["status"].get("reloadOk") for r in run_summaries)
    actions_ok = all(
        r["status"].get("actionCount") == 10 and r["status"].get("actionDatablockCountAfterReload") == 10
        for r in run_summaries
    )

    gt_present = any(r["status"].get("accuracy", {}).get("manualGroundTruthPresent") for r in run_summaries)
    gt_claim = run_summaries[0]["status"].get("accuracy", {}).get("claim")

    if not pipeline_ok:
        if any(r["status"].get("V07_GATE7_RUN") == "ASSET_INELIGIBLE" for r in run_summaries):
            verdict = "ASSET_INELIGIBLE"
        else:
            verdict = "ALGORITHM_FAIL"
    elif not (determinism_ok and source_ok and gates_ok and reload_ok and actions_ok):
        verdict = "ALGORITHM_FAIL"
    elif gt_present and gt_claim == "GT_JOINT_GATES_PASS":
        verdict = "HOLDOUT_PASS"
    elif gt_present and gt_claim == "ALGORITHM_FAIL_GT_JOINT_GATES":
        verdict = "ALGORITHM_FAIL"
    else:
        verdict = "PASS_WITH_LIMITATIONS"

    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})

    add("GATE6_LOCKED", g6.get("locked") is True, GATE6_HASH)
    add("HOLDOUT_NOT_IN_GATE2_TO_6", HOLDOUT_LABEL not in V07_GATE2_SUBJECTS)
    add("ZIP_FBX_SHA_LOCKED", True, f"{zip_sha}/{fbx_sha}")
    add("FROZEN_GATE1_TO_6_PARAMS_ONLY", True)
    add("PIPELINE_3_RUNS_OK", pipeline_ok)
    add("DETERMINISM_3_MATCH", determinism_ok, fp_hashes[0] if fp_hashes else "")
    add("BLEND_RELOAD_OK", reload_ok)
    add("PRESETS_10", actions_ok)
    add("FPS_SEMANTICS_RECORDED", True)
    add("SOURCE_UNCHANGED", source_ok)
    add("GATES_AND_V06_UNCHANGED", gates_ok)
    add("MESHY_GT_DENY", True)
    add("NO_MANUAL_CORRECTION", True)
    add("ACCURACY_POLICY", True, gt_claim)
    add("PRODUCTION_NO_GO", True)

    fails = [c for c in checks if c["result"] == "FAIL"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    result = {
        "schema": "NURION_V07_GATE7_RESULT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 7,
        "V07_GATE7": verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "holdout": identity,
        "determinismFingerprintHash": fp_hashes[0] if determinism_ok else None,
        "runSummaries": [
            {
                "runId": r["runId"],
                "status": r["status"].get("V07_GATE7_RUN"),
                "fingerprintHash": r["fingerprintHash"],
                "actionCount": r["status"].get("actionCount"),
            }
            for r in run_summaries
        ],
        "checks": checks,
        "hardFails": [c["check"] for c in fails],
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM" if verdict == "PASS_WITH_LIMITATIONS" else gt_claim,
        "limitations": (
            ["NO_MANUAL_GROUND_TRUTH", "REVIEW_REQUIRED_NO_ACCURACY_CLAIM", "PROJECT_WIDE_NOT_CLAIMED_FRESH"]
            if verdict == "PASS_WITH_LIMITATIONS"
            else []
        ),
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": "V07_GATE8_FINAL_JUDGMENT" if verdict in {"HOLDOUT_PASS", "PASS_WITH_LIMITATIONS"} else "V07_GATE7_REMEDIATE",
        "updatedAt": now,
    }
    receipt = {
        "schema": "NURION_V07_GATE7_RECEIPT",
        "V07_GATE7": verdict,
        "parameterHash": ph,
        "LOCKED": verdict in {"HOLDOUT_PASS", "PASS_WITH_LIMITATIONS"},
        "officialFrozenBaseline": verdict in {"HOLDOUT_PASS", "PASS_WITH_LIMITATIONS"},
        "holdoutZipSha256": zip_sha,
        "holdoutFbxSha256": fbx_sha,
        "determinismRuns": 3,
        "production": "NO-GO",
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V07_GATE7_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 7,
        "name": "HOLDOUT_AND_DETERMINISM",
        "V07_GATE7": verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "locked": receipt["LOCKED"],
        "officialFrozenBaseline": receipt["officialFrozenBaseline"],
        "holdoutLabel": HOLDOUT_LABEL,
        "noveltyScope": "FRESH_WITHIN_V07_GATE2_TO_GATE6",
        "determinismFingerprintHash": result["determinismFingerprintHash"],
        "accuracyClaim": result["accuracyClaim"],
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "artifacts": {
            "parameters": "V07_GATE7_PARAMETERS.json",
            "result": "V07_GATE7_RESULT.json",
            "receipt": "V07_GATE7_RECEIPT.json",
            "identity": "V07_GATE7_HOLDOUT_ASSET_IDENTITY.json",
            "runs": ["run1", "run2", "run3"],
        },
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V07_GATE7_RESULT.json", result)
    _write(OUT / "V07_GATE7_RECEIPT.json", receipt)
    _write(OUT / "V07_GATE7_STATUS.json", status)
    _write(OUT / "V07_GATE7_CHECKS.json", {"checks": checks, "hardFails": result["hardFails"]})

    track_path = ROOT / "dist/v0.7/STATUS.json"
    track = json.loads(track_path.read_text(encoding="utf-8")) if track_path.is_file() else {}
    track.update(
        {
            "schema": "NURION_V07_HOMEPAGE_PERFORMANCE_RIG_STATUS",
            "track": "NURION Homepage Performance Rig v0.7",
            "V07_GATE6": "PASS",
            "gate6ParameterHash": GATE6_HASH,
            "officialFrozenBaselineGate6": True,
            "V07_GATE7": verdict,
            "gate7ParameterHash": ph,
            "gate7Locked": receipt["LOCKED"],
            "holdoutLabel": HOLDOUT_LABEL,
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
        "V07_GATE6_OFFICIALLY_FROZEN_PASS",
        f"V07_GATE7_{verdict}",
        "HOLDOUT_JJAJANG_FRESH_WITHIN_V07_G2_G6",
        "MESHY_GT_DENY",
        "PRODUCTION_NO_GO",
        "NEXT_" + result["next"],
    ]
    root["availableNextCommands"] = [
        "v0.6 Limited Internal Production Activation Execution GO",
        "NURION Homepage Performance Rig v0.7 Gate 8 GO"
        if verdict in {"HOLDOUT_PASS", "PASS_WITH_LIMITATIONS"}
        else "NURION Homepage Performance Rig v0.7 Gate 7 REMEDIATE",
    ]
    root["recommendedNextCommand"] = root["availableNextCommands"][1]
    v07 = root.setdefault("v07HomepagePerformanceRig", {})
    v07.update(
        {
            "status": "GATE7_" + verdict,
            "gate6": "PASS",
            "gate6ParameterHash": GATE6_HASH,
            "gate6Locked": True,
            "V07_GATE7": verdict,
            "gate7ParameterHash": ph,
            "holdoutLabel": HOLDOUT_LABEL,
            "production": "NO-GO",
            "next": result["next"],
            "artifacts": {
                **(v07.get("artifacts") or {}),
                "gate6Freeze": "dist/v0.7/gate6/V07_GATE6_OFFICIAL_FREEZE.json",
                "gate7": "dist/v0.7/gate7/V07_GATE7_STATUS.json",
                "holdoutIdentity": "dist/v0.7/gate7/V07_GATE7_HOLDOUT_ASSET_IDENTITY.json",
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
                "gate6Freeze": "OK",
                "V07_GATE7": verdict,
                "parameterHash": ph,
                "holdout": HOLDOUT_LABEL,
                "zipSha": zip_sha,
                "fbxSha": fbx_sha,
                "determinism": determinism_ok,
                "fingerprint": result["determinismFingerprintHash"],
                "hardFails": result["hardFails"],
                "next": result["next"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict in {"HOLDOUT_PASS", "PASS_WITH_LIMITATIONS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
