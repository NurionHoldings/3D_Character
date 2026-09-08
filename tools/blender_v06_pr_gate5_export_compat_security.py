"""
v0.6 Production Readiness Gate 5 — Export Compatibility & Security.

Usage:
  blender --background --python tools/blender_v06_pr_gate5_export_compat_security.py
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "production_readiness" / "gate5"
PR = ROOT / "dist" / "v0.6" / "production_readiness"
RC1 = ROOT / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
WRAPPER_ZIP = PR / "gate3/wrapper/nurion_v06_unified_runtime_from_rc1_install_wrapper.zip"
ADDON_DIR = PR / "gate3/wrapper/nurion_v06_unified_runtime"

GATE1_HASH = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_HASH = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_HASH = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE4_HASH = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"
RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"
WRAPPER_SHA = "1094c18a12c3fda162ac061ce2cf05f5e0633446aeef41097885c81f41ecd6e7"
WRAPPER_VER = "0.6.0-wrapper.1"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _lock_gates_1_4(now: str) -> None:
    locks = [
        ("gate1/V06_PR_GATE1_STATUS.json", "PR_GATE1", GATE1_HASH),
        ("gate2/V06_PR_GATE2_STATUS.json", "PR_GATE2", GATE2_HASH),
        ("gate2/V06_PR_GATE2_RECEIPT.json", "PR_GATE2", GATE2_HASH),
        ("gate3/V06_PR_GATE3_STATUS.json", "PR_GATE3", GATE3_HASH),
        ("gate3/V06_PR_GATE3_RECEIPT.json", "PR_GATE3", GATE3_HASH),
        ("gate4/V06_PR_GATE4_STATUS.json", "PR_GATE4", GATE4_HASH),
        ("gate4/V06_PR_GATE4_RECEIPT.json", "PR_GATE4", GATE4_HASH),
    ]
    for rel, key, ph in locks:
        path = PR / rel
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        if key in doc or rel.endswith("STATUS.json"):
            doc[key] = "PASS"
        doc["parameterHash"] = ph
        doc["frozenAt"] = now
        doc["production"] = "NO-GO"
        _write(path, doc)

    wrapper_lock = {
        "schema": "NURION_V06_BLINFO_INSTALL_WRAPPER_COMPONENT",
        "component": "bl_info_install_wrapper",
        "version": WRAPPER_VER,
        "wrapperZip": str(WRAPPER_ZIP).replace("\\", "/"),
        "wrapperSha256": WRAPPER_SHA,
        "targetRc1Package": "NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip",
        "targetRc1Sha256": RC1_SHA,
        "LOCKED": True,
        "officialOpsComponent": True,
        "evidencePinned": True,
        "rc1Repack": "DENY",
        "frozenAt": now,
        "role": "OPERATIONAL_INSTALL_COMPONENT_SEPARATE_FROM_RC1",
        "note": "bl_info wrapper locked as separate operational component from sealed RC.1",
    }
    _write(PR / "gate3/V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json", wrapper_lock)
    _write(OUT / "V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json", wrapper_lock)


def _find_fbx() -> Path:
    hits = sorted((ROOT / "dist/v0.6/gate8/AILAWFRIEND").rglob("*Idle_15*withSkin.fbx"))
    if not hits:
        raise FileNotFoundError("AILAWFRIEND Idle_15 withSkin FBX missing")
    return hits[0]


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from nurion_v06_production_readiness.gate1.parameters import parameter_hash as g1h
    from nurion_v06_production_readiness.gate2.parameters import parameter_hash as g2h
    from nurion_v06_production_readiness.gate3.parameters import parameter_hash as g3h
    from nurion_v06_production_readiness.gate3.smoke import sha256_file
    from nurion_v06_production_readiness.gate4.parameters import parameter_hash as g4h
    from nurion_v06_production_readiness.gate5.compat import run_gate5_export_compat_security
    from nurion_v06_production_readiness.gate5.parameters import GATE5_PARAMETERS, parameter_hash

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if g1h() != GATE1_HASH or g2h() != GATE2_HASH or g3h() != GATE3_HASH or g4h() != GATE4_HASH:
        raise RuntimeError("PR Gate1–4 hash drift — DENY")
    if sha256_file(RC1) != RC1_SHA:
        raise RuntimeError("RC.1 hash drift — DENY")
    if not WRAPPER_ZIP.is_file() or sha256_file(WRAPPER_ZIP) != WRAPPER_SHA:
        raise RuntimeError("Wrapper hash drift — DENY")

    _lock_gates_1_4(now)

    for key in list(sys.modules):
        if key == "nurion_v06_unified_runtime" or key.startswith("nurion_v06_unified_runtime."):
            del sys.modules[key]

    fbx = _find_fbx()
    sealed_paths = [
        RC1,
        WRAPPER_ZIP,
        ROOT / "dist/v0.6/V06_FINAL_SEAL_RECEIPT.json",
        ROOT / "dist/v0.6/V06_FINAL_BASELINE_LOCK.json",
        ROOT / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip",
        ROOT / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip",
    ]

    result = run_gate5_export_compat_security(
        wrapper_zip=WRAPPER_ZIP,
        rc1_zip=RC1,
        fbx_path=fbx,
        out_dir=OUT,
        sealed_paths=sealed_paths,
        addon_dir=ADDON_DIR,
    )
    ph = parameter_hash()

    receipt = {
        "schema": "NURION_V06_PR_GATE5_RECEIPT",
        "gate": "5",
        "track": "Production Readiness",
        "name": "EXPORT_COMPATIBILITY_SECURITY",
        "PR_GATE5": result["verdict"],
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate1Locked": True,
        "gate2Locked": True,
        "gate3Locked": True,
        "gate4Locked": True,
        "officialFrozenBaselineGate1": True,
        "officialFrozenBaselineGate2": True,
        "officialFrozenBaselineGate3": True,
        "officialFrozenBaselineGate4": True,
        "rc1Sha256": RC1_SHA,
        "rc1Repack": "DENY",
        "wrapperComponent": {
            "version": WRAPPER_VER,
            "wrapperSha256": WRAPPER_SHA,
            "targetRc1Sha256": RC1_SHA,
            "LOCKED": True,
        },
        "partialExportPublish": "DENY",
        "autoRemediate": "DENY",
        "autoRepack": "DENY",
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "hardFails": result["hardFails"],
        "limitations": result.get("limitations") or [],
        "notes": result.get("notes"),
        "sourceMutation": result.get("sourceMutation"),
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V06_PR_GATE5_STATUS",
        "gate": "5",
        "track": "Production Readiness",
        "name": "EXPORT_COMPATIBILITY_SECURITY",
        "PR_GATE5": result["verdict"],
        "parameterHash": ph,
        "gate4ParameterHash": GATE4_HASH,
        "gate4Locked": True,
        "production": "NO-GO",
        "hardFails": result["hardFails"],
        "limitations": result.get("limitations") or [],
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_PR_GATE5_RECEIPT.json",
            "parameters": "V06_PR_GATE5_PARAMETERS.json",
            "checks": "V06_PR_GATE5_CHECKS.json",
            "security": "V06_PR_GATE5_SECURITY.json",
            "roundTrips": "V06_PR_GATE5_ROUNDTRIPS.json",
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
        "implementation": "V06_PR_GATE5",
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
        "PR_GATE4": "PASS",
        "gate4ParameterHash": GATE4_HASH,
        "gate4Locked": True,
        "officialFrozenBaselineGate4": True,
        "PR_GATE5": result["verdict"],
        "gate5ParameterHash": ph,
        "blInfoWrapperComponent": {
            "version": WRAPPER_VER,
            "wrapperSha256": WRAPPER_SHA,
            "targetRc1Sha256": RC1_SHA,
            "LOCKED": True,
        },
        "production": "NO-GO",
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V06_PR_GATE5_PARAMETERS.json", GATE5_PARAMETERS)
    _write(OUT / "V06_PR_GATE5_CHECKS.json", {"checks": result["checks"], "hardFails": result["hardFails"]})
    _write(
        OUT / "V06_PR_GATE5_SECURITY.json",
        {
            "zipSecurity": result.get("zipSecurity"),
            "scriptsInventory": result.get("scriptsInventory"),
            "sideEffects": result.get("sideEffects"),
            "badInputs": result.get("badInputs"),
            "partialExport": result.get("partialExport"),
        },
    )
    _write(OUT / "V06_PR_GATE5_ROUNDTRIPS.json", result.get("roundTrips") or {})
    _write(OUT / "V06_PR_GATE5_RECEIPT.json", receipt)
    _write(OUT / "V06_PR_GATE5_STATUS.json", status)
    _write(PR / "STATUS.json", track)

    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = result["next"]
    root_status["nextSteps"] = [
        "V06_PR_GATE1_LOCKED_PASS",
        "V06_PR_GATE2_LOCKED_PASS",
        "V06_PR_GATE3_LOCKED_PASS",
        "V06_PR_GATE4_LOCKED_PASS",
        f"V06_PR_GATE5_{result['verdict']}",
        "PRODUCTION_REMAINS_NO_GO",
        "NEXT_" + result["next"],
    ]
    pr = root_status.setdefault("v06ProductionReadiness", {})
    pr.update(
        {
            "implementation": "V06_PR_GATE5",
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
            "PR_GATE4": "PASS",
            "gate4ParameterHash": GATE4_HASH,
            "gate4Locked": True,
            "officialFrozenBaselineGate4": True,
            "PR_GATE5": result["verdict"],
            "gate5ParameterHash": ph,
            "blInfoWrapperComponent": {
                "version": WRAPPER_VER,
                "wrapperSha256": WRAPPER_SHA,
                "targetRc1Sha256": RC1_SHA,
                "LOCKED": True,
            },
            "production": "NO-GO",
            "next": result["next"],
        }
    )
    arts = pr.setdefault("statusArtifacts", {})
    arts["gate4"] = "dist/v0.6/production_readiness/gate4/V06_PR_GATE4_STATUS.json"
    arts["gate5"] = "dist/v0.6/production_readiness/gate5/V06_PR_GATE5_STATUS.json"
    arts["gate5Receipt"] = "dist/v0.6/production_readiness/gate5/V06_PR_GATE5_RECEIPT.json"
    arts["gate5Security"] = "dist/v0.6/production_readiness/gate5/V06_PR_GATE5_SECURITY.json"
    arts["gate3WrapperLock"] = "dist/v0.6/production_readiness/gate3/V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json"
    root_status["v06ProductionReadiness"] = pr
    _write(ROOT / "STATUS.json", root_status)

    summary = {
        "PR_GATE5": result["verdict"],
        "parameterHash": ph,
        "hardFails": result["hardFails"],
        "limitations": result.get("limitations") or [],
        "checkCount": len(result["checks"]),
        "passCount": sum(1 for c in result["checks"] if c["result"] == "PASS"),
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
