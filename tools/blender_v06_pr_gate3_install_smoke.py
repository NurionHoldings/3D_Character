"""
v0.6 Production Readiness Gate 3 — Blender 5.0.1 install/update/remove smoke.

Usage:
  blender --background --python tools/blender_v06_pr_gate3_install_smoke.py
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "production_readiness" / "gate3"
RC1 = ROOT / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
FBX = (
    ROOT
    / "dist/v0.6/gate8/AILAWFRIEND/_extract"
)
GATE1_HASH = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_HASH = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _lock_prior(now: str) -> None:
    pr = ROOT / "dist" / "v0.6" / "production_readiness"
    # Gate1 already locked; ensure Gate2 locked
    for name in ("gate2/V06_PR_GATE2_STATUS.json", "gate2/V06_PR_GATE2_RECEIPT.json"):
        path = pr / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["PR_GATE2"] = "PASS"
        doc["parameterHash"] = GATE2_HASH
        doc["gate1Locked"] = True
        doc["frozenAt"] = now
        doc["production"] = "NO-GO"
        _write(path, doc)
    g1s = pr / "gate1/V06_PR_GATE1_STATUS.json"
    d = json.loads(g1s.read_text(encoding="utf-8"))
    d["LOCKED"] = True
    d["officialFrozenBaseline"] = True
    d["parameterHash"] = GATE1_HASH
    _write(g1s, d)


def main() -> int:
    # Keep ROOT for harness imports, but smoke will prefer installed addon path at enable-time.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from nurion_v06_production_readiness.gate1.parameters import parameter_hash as g1h
    from nurion_v06_production_readiness.gate2.parameters import parameter_hash as g2h
    from nurion_v06_production_readiness.gate3.install_wrapper import build_install_wrapper
    from nurion_v06_production_readiness.gate3.parameters import GATE3_PARAMETERS, parameter_hash
    from nurion_v06_production_readiness.gate3.smoke import run_gate3_smoke

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if g1h() != GATE1_HASH or g2h() != GATE2_HASH:
        raise RuntimeError("PR Gate1/2 hash drift — DENY")
    _lock_prior(now)
    # Drop any preloaded workspace addon package so enable uses installed copy.
    for key in list(sys.modules):
        if key == "nurion_v06_unified_runtime" or key.startswith("nurion_v06_unified_runtime."):
            del sys.modules[key]

    fbx_hits = list(FBX.rglob("*Idle_15*withSkin.fbx")) if FBX.is_dir() else []
    if not fbx_hits:
        raise FileNotFoundError("AILAWFRIEND Idle_15 withSkin FBX missing under gate8 extract")
    fbx = fbx_hits[0]

    wrap = build_install_wrapper(rc1_zip=RC1, out_dir=OUT / "wrapper")
    _write(OUT / "V06_PR_GATE3_INSTALL_WRAPPER.json", wrap)
    if not wrap.get("ok"):
        raise RuntimeError(f"install wrapper failed: {wrap}")

    result = run_gate3_smoke(
        wrapper_zip=Path(wrap["wrapperZip"]),
        fbx_path=fbx,
        out_dir=OUT / "smoke_artifacts",
        rc1_zip=RC1,
    )
    ph = parameter_hash()

    receipt = {
        "schema": "NURION_V06_PR_GATE3_RECEIPT",
        "gate": "3",
        "track": "Production Readiness",
        "name": "BLENDER_INSTALL_UPDATE_REMOVE_SMOKE",
        "PR_GATE3": result["verdict"],
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate1Locked": True,
        "gate2Locked": True,
        "rc1Sha256": RC1_SHA,
        "rc1Repack": "DENY",
        "sealedBaselineMutation": "DENY",
        "installWrapperSha256": wrap.get("wrapperSha256"),
        "installWrapperNote": GATE3_PARAMETERS["installWrapperNote"],
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "sourceMutation": result["sourceMutation"],
        "hardFails": result["hardFails"],
        "notes": result["notes"],
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V06_PR_GATE3_STATUS",
        "gate": "3",
        "track": "Production Readiness",
        "name": "BLENDER_INSTALL_UPDATE_REMOVE_SMOKE",
        "PR_GATE3": result["verdict"],
        "parameterHash": ph,
        "gate2ParameterHash": GATE2_HASH,
        "gate2Locked": True,
        "production": "NO-GO",
        "hardFails": result["hardFails"],
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_PR_GATE3_RECEIPT.json",
            "parameters": "V06_PR_GATE3_PARAMETERS.json",
            "checks": "V06_PR_GATE3_CHECKS.json",
            "wrapper": "V06_PR_GATE3_INSTALL_WRAPPER.json",
        },
        "next": result["next"],
    }
    track = {
        "schema": "NURION_V06_PRODUCTION_READINESS_STATUS",
        "track": "Production Readiness",
        "product": "NURION Unified Character Animation Runtime",
        "sealedBaseline": "v0.6",
        "sealedBaselineSha256": RC1_SHA,
        "implementation": "V06_PR_GATE3",
        "status": "IN_PROGRESS",
        "PR_GATE1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "PR_GATE2": "PASS",
        "gate2ParameterHash": GATE2_HASH,
        "gate2Locked": True,
        "PR_GATE3": result["verdict"],
        "gate3ParameterHash": ph,
        "production": "NO-GO",
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V06_PR_GATE3_PARAMETERS.json", GATE3_PARAMETERS)
    _write(OUT / "V06_PR_GATE3_CHECKS.json", {"checks": result["checks"], "hardFails": result["hardFails"]})
    _write(OUT / "V06_PR_GATE3_RECEIPT.json", receipt)
    _write(OUT / "V06_PR_GATE3_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "production_readiness" / "STATUS.json", track)

    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = result["next"]
    root_status["nextSteps"] = [
        "V06_PR_GATE1_LOCKED_PASS",
        "V06_PR_GATE2_LOCKED_PASS",
        f"V06_PR_GATE3_{result['verdict']}",
        "PRODUCTION_REMAINS_NO_GO",
        "NEXT_" + result["next"],
    ]
    pr = root_status.setdefault("v06ProductionReadiness", {})
    pr.update(
        {
            "implementation": "V06_PR_GATE3",
            "status": "IN_PROGRESS",
            "PR_GATE1": "PASS",
            "gate1ParameterHash": GATE1_HASH,
            "gate1Locked": True,
            "PR_GATE2": "PASS",
            "gate2ParameterHash": GATE2_HASH,
            "gate2Locked": True,
            "officialFrozenBaselineGate2": True,
            "PR_GATE3": result["verdict"],
            "gate3ParameterHash": ph,
            "production": "NO-GO",
            "next": result["next"],
        }
    )
    arts = pr.setdefault("statusArtifacts", {})
    arts["gate3"] = "dist/v0.6/production_readiness/gate3/V06_PR_GATE3_STATUS.json"
    arts["gate3Receipt"] = "dist/v0.6/production_readiness/gate3/V06_PR_GATE3_RECEIPT.json"
    root_status["v06ProductionReadiness"] = pr
    _write(ROOT / "STATUS.json", root_status)

    print(
        json.dumps(
            {
                "PR_GATE3": result["verdict"],
                "parameterHash": ph,
                "hardFails": result["hardFails"],
                "checkCount": len(result["checks"]),
                "passCount": sum(1 for c in result["checks"] if c["result"] == "PASS"),
                "rc1Sha256": result["rc1Sha256"],
                "sourceMutation": result["sourceMutation"],
                "wrapperSha256": wrap.get("wrapperSha256"),
                "production": "NO-GO",
                "next": result["next"],
            },
            indent=2,
        )
    )
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
