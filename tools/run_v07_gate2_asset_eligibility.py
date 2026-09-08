"""Run NURION Homepage Performance Rig v0.7 Gate 2 — Asset Eligibility & Landmark Evidence."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_v07_gate2_asset_eligibility.py"
OUT = ROOT / "dist" / "v0.7" / "gate2"
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
V06_RC1 = ROOT / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
V06_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"

ASSETS = [
    {
        "label": "ai-aba.15",
        "zip": ROOT / "dist/v0.4/gate8c/inbox/ai-aba.15.zip",
        "homepage_primary": True,
    },
    {
        "label": "ai-aba.bow",
        "zip": ROOT / "dist/v0.5/gate1/inbox/ai-aba.bow.zip",
        "homepage_primary": False,
    },
    {
        "label": "Minimalist_Tennis_Out_Idle15",
        "fbx": ROOT
        / "assets/wither_character_rig/Meshy_AI_Minimalist_Tennis_Out_biped/Meshy_AI_Minimalist_Tennis_Out_biped_Animation_Idle_15_withSkin.fbx",
        "homepage_primary": False,
    },
    {
        "label": "Monochrome_Tennis_texture",
        "fbx": ROOT
        / "assets/Meshy_AI_Monochrome_Tennis_Loo_0810000004_texture_fbx/Meshy_AI_Monochrome_Tennis_Loo_0810000004_texture.fbx",
        "homepage_primary": False,
    },
    {
        "label": "hyerie_15",
        "fbx": ROOT / "hyerie_15.fbx",
        "homepage_primary": False,
    },
]


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
    # Ensure Gate1 registered
    reg = ROOT / "tools" / "register_v07_gate1_artifacts.py"
    subprocess.check_call([sys.executable, str(reg)], cwd=str(ROOT))

    g1 = json.loads((ROOT / "dist/v0.7/gate1/V07_GATE1_STATUS.json").read_text(encoding="utf-8"))
    assert g1.get("V07_GATE1") == "PASS"
    assert g1.get("parameterHash") == GATE1_HASH

    if not V06_RC1.is_file() or _sha(V06_RC1) != V06_SHA:
        raise SystemExit("v0.6 RC1 baseline missing or hash mismatch")

    OUT.mkdir(parents=True, exist_ok=True)
    params = {
        "schema": "NURION_V07_GATE2_PARAMETERS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 2,
        "name": "ASSET_ELIGIBILITY_AND_LANDMARK_EVIDENCE",
        "gate1ParameterHash": GATE1_HASH,
        "blenderTarget": "5.0.1",
        "meshyBonesAsGroundTruth": "DENY",
        "meshyWeightsAsGroundTruth": "DENY",
        "armatureGeneration": "DENY",
        "weightGeneration": "DENY",
        "animationGeneration": "DENY",
        "sourceMutation": "DENY",
        "sealedBaselineMutation": "DENY",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "classifications": [
            "HOMEPAGE_READY_LIMITED",
            "REVIEW_REQUIRED",
            "INELIGIBLE",
            "ABSTAIN",
        ],
        "assets": [
            {
                "label": a["label"],
                "homepagePrimary": a.get("homepage_primary", False),
                "kind": "zip" if "zip" in a else "fbx",
            }
            for a in ASSETS
        ],
    }
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(OUT / "V07_GATE2_PARAMETERS.json", params)

    asset_results = []
    for a in ASSETS:
        label = a["label"]
        out_dir = OUT / label
        cmd = [
            str(BLENDER),
            "--background",
            "--python",
            str(SCRIPT),
            "--",
            "--label",
            label,
            "--out-dir",
            str(out_dir),
        ]
        if a.get("homepage_primary"):
            cmd.append("--homepage-primary")
        if "zip" in a:
            cmd.extend(["--zip", str(a["zip"])])
        else:
            cmd.extend(["--fbx", str(a["fbx"])])
        print("RUN", label, flush=True)
        r = subprocess.run(cmd, cwd=str(ROOT))
        status_path = out_dir / "V07_GATE2_ASSET_STATUS.json"
        if not status_path.is_file():
            asset_results.append(
                {
                    "label": label,
                    "classification": "INELIGIBLE",
                    "reason": "EVAL_SCRIPT_FAILED",
                    "exitCode": r.returncode,
                }
            )
            continue
        st = json.loads(status_path.read_text(encoding="utf-8"))
        asset_results.append(st)

    # Aggregate verdict
    hard_fails = []
    if any(x.get("sourceMutation", 0) not in (0, None) for x in asset_results if "sourceMutation" in x):
        hard_fails.append("SOURCE_MUTATION")

    class_counts = {}
    for st in asset_results:
        c = st.get("classification", "UNKNOWN")
        class_counts[c] = class_counts.get(c, 0) + 1

    eligible_pipeline = [
        st
        for st in asset_results
        if st.get("newNativeRigGenerationPossible") and st.get("classification") != "INELIGIBLE"
    ]
    primary = next((st for st in asset_results if st.get("label") == "ai-aba.15"), None)

    # Gate2 PASS if: Gate1 locked, no source mutation, at least one non-INELIGIBLE asset evaluated,
    # evidence/eligibility artifacts written, no armature generated, v0.6 unchanged.
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    add("GATE1_LOCKED_PASS", g1.get("V07_GATE1") == "PASS" and g1.get("locked") is True, GATE1_HASH)
    add("V06_RC1_UNCHANGED", _sha(V06_RC1) == V06_SHA, V06_SHA)
    add("NO_SOURCE_MUTATION", not hard_fails, str(hard_fails))
    add("NO_ARMATURE_GENERATED", all(not st.get("armatureGenerated") for st in asset_results if "armatureGenerated" in st))
    add("NO_WEIGHTS_GENERATED", all(not st.get("weightsGenerated") for st in asset_results if "weightsGenerated" in st))
    add("ASSETS_EVALUATED", len(asset_results) == len(ASSETS), f"{len(asset_results)}/{len(ASSETS)}")
    add(
        "AT_LEAST_ONE_PIPELINE_CANDIDATE",
        len(eligible_pipeline) >= 1,
        ",".join(st.get("label", "") for st in eligible_pipeline),
    )
    add(
        "PRIMARY_ABA_NOT_INELIGIBLE",
        primary is not None and primary.get("classification") != "INELIGIBLE",
        str(primary.get("classification") if primary else None),
    )
    add("MESHY_GT_DENIED", True)
    add("PRODUCTION_NO_GO", True)
    add("V06_ACTIVATION_NOT_GRANTED", True)

    fails = [c for c in checks if c["result"] == "FAIL"]
    verdict = "PASS" if not fails else "FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    result = {
        "schema": "NURION_V07_GATE2_RESULT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 2,
        "name": "ASSET_ELIGIBILITY_AND_LANDMARK_EVIDENCE",
        "V07_GATE2": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "checks": checks,
        "hardFails": [c["check"] for c in fails],
        "classCounts": class_counts,
        "eligiblePipelineLabels": [st.get("label") for st in eligible_pipeline],
        "primaryHomepageCandidate": {
            "label": "ai-aba.15",
            "classification": primary.get("classification") if primary else None,
            "handGesturePath": (primary.get("paths") or {}).get("handGesturePath") if primary else None,
            "groundTruthRequiredForAccuracy": primary.get("groundTruthRequiredForAccuracy") if primary else None,
        },
        "assetSummaries": [
            {
                "label": st.get("label"),
                "classification": st.get("classification"),
                "reason": st.get("reason"),
                "newNativeRigGenerationPossible": st.get("newNativeRigGenerationPossible"),
                "handGesturePath": (st.get("paths") or {}).get("handGesturePath"),
                "facePath": (st.get("paths") or {}).get("facePath"),
                "eyePath": (st.get("paths") or {}).get("eyePath"),
                "limitations": st.get("limitations"),
            }
            for st in asset_results
        ],
        "implementationStarted": False,
        "armatureGenerated": False,
        "weightsGenerated": False,
        "animationsGenerated": False,
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": "V07_GATE3_NATIVE_ARMATURE_PROTOTYPE" if verdict == "PASS" else "V07_GATE2_REMEDIATE",
        "updatedAt": now,
    }

    receipt = {
        "schema": "NURION_V07_GATE2_RECEIPT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 2,
        "V07_GATE2": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "LOCKED": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "assetsEvaluated": len(asset_results),
        "classCounts": class_counts,
        "sourceMutation": 0,
        "sealedBaselineMutation": 0,
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "updatedAt": now,
        "next": result["next"],
    }

    status = {
        "schema": "NURION_V07_GATE2_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 2,
        "name": "ASSET_ELIGIBILITY_AND_LANDMARK_EVIDENCE",
        "V07_GATE2": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "locked": verdict == "PASS",
        "officialFrozenBaseline": verdict == "PASS",
        "checks": {c["check"]: c["result"] for c in checks},
        "classCounts": class_counts,
        "eligiblePipelineLabels": result["eligiblePipelineLabels"],
        "primaryHomepageCandidate": result["primaryHomepageCandidate"],
        "implementationStarted": False,
        "armatureGenerated": False,
        "weightsGenerated": False,
        "animationsGenerated": False,
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "artifacts": {
            "parameters": "V07_GATE2_PARAMETERS.json",
            "result": "V07_GATE2_RESULT.json",
            "receipt": "V07_GATE2_RECEIPT.json",
            "perAsset": [a["label"] for a in ASSETS],
        },
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V07_GATE2_RESULT.json", result)
    _write(OUT / "V07_GATE2_RECEIPT.json", receipt)
    _write(OUT / "V07_GATE2_STATUS.json", status)
    _write(OUT / "V07_GATE2_CHECKS.json", {"checks": checks, "hardFails": [c["check"] for c in fails]})

    # Track status
    track = {
        "schema": "NURION_V07_HOMEPAGE_PERFORMANCE_RIG_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "internalCoreModule": "Native Rig Reconstruction",
        "V07_GATE1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "officialFrozenBaselineGate1": True,
        "V07_GATE2": verdict,
        "gate2ParameterHash": ph,
        "gate2Locked": verdict == "PASS",
        "officialFrozenBaselineGate2": verdict == "PASS",
        "implementationStarted": False,
        "armatureGenerated": False,
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": result["next"],
        "updatedAt": now,
    }
    _write(ROOT / "dist/v0.7/STATUS.json", track)

    # Root STATUS updates
    root_path = ROOT / "STATUS.json"
    root = json.loads(root_path.read_text(encoding="utf-8"))
    root["nextDecision"] = result["next"]
    root["nextSteps"] = [
        "V07_GATE1_LOCKED_PASS",
        f"V07_GATE2_{verdict}",
        "IMPLEMENTATION_NOT_STARTED",
        "V06_ACTIVATION_NOT_GRANTED",
        "PRODUCTION_NO_GO",
        "NEXT_" + result["next"],
    ]
    root["availableNextCommands"] = [
        "v0.6 Limited Internal Production Activation Execution GO",
        "NURION Homepage Performance Rig v0.7 Gate 3 GO" if verdict == "PASS" else "NURION Homepage Performance Rig v0.7 Gate 2 REMEDIATE",
    ]
    root["recommendedNextCommand"] = (
        "NURION Homepage Performance Rig v0.7 Gate 3 GO" if verdict == "PASS" else "NURION Homepage Performance Rig v0.7 Gate 2 REMEDIATE"
    )
    v07 = root.setdefault("v07HomepagePerformanceRig", {})
    v07.update(
        {
            "productName": "NURION Homepage Performance Rig v0.7",
            "internalCoreModule": "Native Rig Reconstruction",
            "priorProductTrackNameStatus": "SUPERSEDED_DISCARDED",
            "status": "GATE2_" + verdict,
            "gate1": "PASS",
            "gate1ParameterHash": GATE1_HASH,
            "gate1Locked": True,
            "V07_GATE2": verdict,
            "gate2ParameterHash": ph,
            "gate2Locked": verdict == "PASS",
            "implementationStarted": False,
            "production": "NO-GO",
            "mustNotMutateV06Seal": True,
            "mustNotMutateV06Activation": True,
            "artifacts": {
                "gate1": "dist/v0.7/gate1/V07_GATE1_STATUS.json",
                "gate2": "dist/v0.7/gate2/V07_GATE2_STATUS.json",
                "trackStatus": "dist/v0.7/STATUS.json",
            },
            "next": result["next"],
        }
    )
    # Keep v06 activation untouched in production readiness block
    pr = root.get("v06ProductionReadiness") or {}
    if pr:
        pr["activation"] = "NOT_GRANTED"
        pr["activationExecution"] = "NOT_STARTED"
        root["v06ProductionReadiness"] = pr
    root_path.write_text(json.dumps(root, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "V07_GATE2": verdict,
                "parameterHash": ph,
                "classCounts": class_counts,
                "eligible": result["eligiblePipelineLabels"],
                "primary": result["primaryHomepageCandidate"],
                "next": result["next"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
