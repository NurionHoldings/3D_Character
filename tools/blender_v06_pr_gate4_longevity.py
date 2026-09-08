"""
v0.6 Production Readiness Gate 4 — longevity / memory / performance.

Usage:
  blender --background --python tools/blender_v06_pr_gate4_longevity.py
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "production_readiness" / "gate4"
PR = ROOT / "dist" / "v0.6" / "production_readiness"
RC1 = ROOT / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
WRAPPER_ZIP = (
    PR
    / "gate3/wrapper/nurion_v06_unified_runtime_from_rc1_install_wrapper.zip"
)
GATE1_HASH = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_HASH = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_HASH = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"
WRAPPER_SHA = "1094c18a12c3fda162ac061ce2cf05f5e0633446aeef41097885c81f41ecd6e7"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _lock_gates_1_3(now: str) -> None:
    # Gate 1
    for rel in ("gate1/V06_PR_GATE1_STATUS.json",):
        path = PR / rel
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["parameterHash"] = GATE1_HASH
        doc["frozenAt"] = now
        doc["production"] = "NO-GO"
        _write(path, doc)
    # Gate 2
    for rel in ("gate2/V06_PR_GATE2_STATUS.json", "gate2/V06_PR_GATE2_RECEIPT.json"):
        path = PR / rel
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["PR_GATE2"] = "PASS"
        doc["parameterHash"] = GATE2_HASH
        doc["frozenAt"] = now
        doc["production"] = "NO-GO"
        _write(path, doc)
    # Gate 3
    for rel in ("gate3/V06_PR_GATE3_STATUS.json", "gate3/V06_PR_GATE3_RECEIPT.json"):
        path = PR / rel
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["PR_GATE3"] = "PASS"
        doc["parameterHash"] = GATE3_HASH
        doc["gate1Locked"] = True
        doc["gate2Locked"] = True
        doc["frozenAt"] = now
        doc["production"] = "NO-GO"
        doc["blenderInstallSmoke"] = "PASS"
        doc["checks"] = "23/23"
        _write(path, doc)


def _find_fbx(root: Path, pattern: str) -> Path:
    hits = sorted(root.rglob(pattern))
    if not hits:
        raise FileNotFoundError(f"FBX not found: {pattern} under {root}")
    return hits[0]


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from nurion_v06_production_readiness.gate1.parameters import parameter_hash as g1h
    from nurion_v06_production_readiness.gate2.parameters import parameter_hash as g2h
    from nurion_v06_production_readiness.gate3.parameters import parameter_hash as g3h
    from nurion_v06_production_readiness.gate3.smoke import sha256_file
    from nurion_v06_production_readiness.gate4.longevity import run_gate4_longevity
    from nurion_v06_production_readiness.gate4.parameters import (
        GATE4_PARAMETERS,
        WRAPPER_COMPONENT,
        parameter_hash,
    )

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if g1h() != GATE1_HASH or g2h() != GATE2_HASH or g3h() != GATE3_HASH:
        raise RuntimeError("PR Gate1/2/3 hash drift — DENY")

    _lock_gates_1_3(now)

    if not WRAPPER_ZIP.is_file():
        raise FileNotFoundError(f"wrapper zip missing: {WRAPPER_ZIP}")
    wrap_sha = sha256_file(WRAPPER_ZIP)
    if wrap_sha != WRAPPER_SHA:
        raise RuntimeError(f"wrapper hash drift: {wrap_sha} != {WRAPPER_SHA}")
    if sha256_file(RC1) != RC1_SHA:
        raise RuntimeError("RC.1 hash drift — DENY")

    wrapper_lock = {
        **WRAPPER_COMPONENT,
        "LOCKED": True,
        "officialOpsComponent": True,
        "wrapperSha256Verified": wrap_sha,
        "targetRc1Sha256Verified": RC1_SHA,
        "frozenAt": now,
        "evidencePinned": True,
        "rc1Repack": "DENY",
        "note": "bl_info wrapper is a separate operational install component from sealed RC.1",
    }
    _write(PR / "gate3/V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json", wrapper_lock)
    _write(OUT / "V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json", wrapper_lock)

    # Drop workspace shadowing
    for key in list(sys.modules):
        if key == "nurion_v06_unified_runtime" or key.startswith("nurion_v06_unified_runtime."):
            del sys.modules[key]

    limited_fbx = _find_fbx(ROOT / "dist/v0.6/gate8/AILAWFRIEND", "*Idle_15*withSkin.fbx")
    bow_fbx = _find_fbx(ROOT / "dist/v0.5/gate1/ai-aba.bow", "*Formal_Bow*withSkin.fbx")

    sealed_paths = [
        RC1,
        WRAPPER_ZIP,
        ROOT / "dist/v0.6/V06_FINAL_SEAL_RECEIPT.json",
        ROOT / "dist/v0.6/V06_FINAL_BASELINE_LOCK.json",
        ROOT / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip",
        ROOT / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip",
    ]

    result = run_gate4_longevity(
        wrapper_zip=WRAPPER_ZIP,
        limited_fbx=limited_fbx,
        bow_fbx=bow_fbx,
        out_dir=OUT,
        rc1_zip=RC1,
        sealed_paths=sealed_paths,
    )
    ph = parameter_hash()

    receipt = {
        "schema": "NURION_V06_PR_GATE4_RECEIPT",
        "gate": "4",
        "track": "Production Readiness",
        "name": "LONGEVITY_MEMORY_PERFORMANCE",
        "PR_GATE4": result["verdict"],
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate1Locked": True,
        "gate2Locked": True,
        "gate3Locked": True,
        "officialFrozenBaselineGate1": True,
        "officialFrozenBaselineGate2": True,
        "officialFrozenBaselineGate3": True,
        "rc1Sha256": RC1_SHA,
        "rc1Repack": "DENY",
        "sealedBaselineMutation": "DENY",
        "wrapperComponent": wrapper_lock,
        "partialExportPublish": "DENY",
        "autoOptimize": "DENY",
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "hardFails": result["hardFails"],
        "limitations": result.get("limitations") or [],
        "metrics": result.get("metrics"),
        "notes": result.get("notes"),
        "sourceMutation": result.get("sourceMutation"),
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V06_PR_GATE4_STATUS",
        "gate": "4",
        "track": "Production Readiness",
        "name": "LONGEVITY_MEMORY_PERFORMANCE",
        "PR_GATE4": result["verdict"],
        "parameterHash": ph,
        "gate3ParameterHash": GATE3_HASH,
        "gate3Locked": True,
        "production": "NO-GO",
        "hardFails": result["hardFails"],
        "limitations": result.get("limitations") or [],
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_PR_GATE4_RECEIPT.json",
            "parameters": "V06_PR_GATE4_PARAMETERS.json",
            "checks": "V06_PR_GATE4_CHECKS.json",
            "metrics": "V06_PR_GATE4_METRICS.json",
            "iterations": "V06_PR_GATE4_ITERATIONS.json",
            "wrapperLock": "V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json",
        },
        "next": result["next"],
    }
    track = {
        "schema": "NURION_V06_PRODUCTION_READINESS_STATUS",
        "track": "Production Readiness",
        "product": "NURION Unified Character Animation Runtime",
        "sealedBaseline": "v0.6",
        "sealedBaselineSha256": RC1_SHA,
        "implementation": "V06_PR_GATE4",
        "status": "IN_PROGRESS",
        "PR_GATE1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "officialFrozenBaselineGate1": True,
        "PR_GATE2": "PASS",
        "gate2ParameterHash": GATE2_HASH,
        "gate2Locked": True,
        "officialFrozenBaselineGate2": True,
        "PR_GATE3": "PASS",
        "gate3ParameterHash": GATE3_HASH,
        "gate3Locked": True,
        "officialFrozenBaselineGate3": True,
        "PR_GATE4": result["verdict"],
        "gate4ParameterHash": ph,
        "blInfoWrapperComponent": {
            "version": WRAPPER_COMPONENT["version"],
            "wrapperSha256": WRAPPER_SHA,
            "targetRc1Sha256": RC1_SHA,
            "LOCKED": True,
        },
        "production": "NO-GO",
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V06_PR_GATE4_PARAMETERS.json", GATE4_PARAMETERS)
    _write(OUT / "V06_PR_GATE4_CHECKS.json", {"checks": result["checks"], "hardFails": result["hardFails"]})
    _write(OUT / "V06_PR_GATE4_METRICS.json", result.get("metrics") or {})
    _write(
        OUT / "V06_PR_GATE4_ITERATIONS.json",
        {"iterations": result.get("iterations") or [], "memorySamples": result.get("memorySamples") or []},
    )
    _write(OUT / "V06_PR_GATE4_RECEIPT.json", receipt)
    _write(OUT / "V06_PR_GATE4_STATUS.json", status)
    _write(PR / "STATUS.json", track)

    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = result["next"]
    root_status["nextSteps"] = [
        "V06_PR_GATE1_LOCKED_PASS",
        "V06_PR_GATE2_LOCKED_PASS",
        "V06_PR_GATE3_LOCKED_PASS",
        f"V06_PR_GATE4_{result['verdict']}",
        "PRODUCTION_REMAINS_NO_GO",
        "NEXT_" + result["next"],
    ]
    pr = root_status.setdefault("v06ProductionReadiness", {})
    pr.update(
        {
            "implementation": "V06_PR_GATE4",
            "status": "IN_PROGRESS",
            "PR_GATE1": "PASS",
            "gate1ParameterHash": GATE1_HASH,
            "gate1Locked": True,
            "officialFrozenBaselineGate1": True,
            "PR_GATE2": "PASS",
            "gate2ParameterHash": GATE2_HASH,
            "gate2Locked": True,
            "officialFrozenBaselineGate2": True,
            "PR_GATE3": "PASS",
            "gate3ParameterHash": GATE3_HASH,
            "gate3Locked": True,
            "officialFrozenBaselineGate3": True,
            "PR_GATE4": result["verdict"],
            "gate4ParameterHash": ph,
            "blInfoWrapperComponent": {
                "version": WRAPPER_COMPONENT["version"],
                "wrapperSha256": WRAPPER_SHA,
                "targetRc1Sha256": RC1_SHA,
                "LOCKED": True,
            },
            "production": "NO-GO",
            "next": result["next"],
        }
    )
    arts = pr.setdefault("statusArtifacts", {})
    arts["gate3WrapperLock"] = "dist/v0.6/production_readiness/gate3/V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json"
    arts["gate4"] = "dist/v0.6/production_readiness/gate4/V06_PR_GATE4_STATUS.json"
    arts["gate4Receipt"] = "dist/v0.6/production_readiness/gate4/V06_PR_GATE4_RECEIPT.json"
    arts["gate4Metrics"] = "dist/v0.6/production_readiness/gate4/V06_PR_GATE4_METRICS.json"
    root_status["v06ProductionReadiness"] = pr
    _write(ROOT / "STATUS.json", root_status)

    summary = {
        "PR_GATE4": result["verdict"],
        "parameterHash": ph,
        "hardFails": result["hardFails"],
        "limitations": result.get("limitations") or [],
        "checkCount": len(result["checks"]),
        "passCount": sum(1 for c in result["checks"] if c["result"] == "PASS"),
        "metrics": {
            "iterations": (result.get("metrics") or {}).get("iterations"),
            "meanDurationSec": (result.get("metrics") or {}).get("meanDurationSec"),
            "p95DurationSec": (result.get("metrics") or {}).get("p95DurationSec"),
            "maxDurationSec": (result.get("metrics") or {}).get("maxDurationSec"),
            "failureRatePct": (result.get("metrics") or {}).get("failureRatePct"),
            "memoryGrowthMb": ((result.get("metrics") or {}).get("memory") or {}).get("growthMb"),
            "sealedMutationCount": (result.get("metrics") or {}).get("sealedMutationCount"),
        },
        "wrapperSha256": WRAPPER_SHA,
        "rc1Sha256": RC1_SHA,
        "production": "NO-GO",
        "next": result["next"],
    }
    print(json.dumps(summary, indent=2))
    return 0 if result["verdict"] in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
