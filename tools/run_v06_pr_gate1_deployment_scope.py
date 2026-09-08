"""
v0.6 Production Readiness Gate 1 GO — deployment scope & supported assets.

Usage:
  py -3 tools/run_v06_pr_gate1_deployment_scope.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "production_readiness" / "gate1"
V06_RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from nurion_v06_production_readiness.gate1.parameters import GATE1_PARAMETERS, parameter_hash
    from nurion_v06_production_readiness.gate1.scope import run_pr_gate1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    result = run_pr_gate1(root=ROOT)
    ph = parameter_hash()

    # Confirm official readonly baseline registration on v0.6 STATUS
    v06_status_path = ROOT / "dist" / "v0.6" / "STATUS.json"
    v06_status = json.loads(v06_status_path.read_text(encoding="utf-8"))
    v06_status.update(
        {
            "baselineConfirmed": True,
            "baselineRole": "OFFICIAL_READONLY_BASELINE",
            "SEALED": True,
            "READ_ONLY": True,
            "status": "SEALED_WITH_LIMITATIONS",
            "rc1Sha256": V06_RC1_SHA,
            "rc1Repack": "DENY",
            "production": "NO-GO",
            "productionReadiness": {
                "track": "IN_PROGRESS",
                "PR_GATE1": result["verdict"],
                "gate1ParameterHash": ph,
            },
            "next": "PR_GATE2_FAILURE_ABSTAIN_RECOVERY_POLICY",
            "updatedAt": now,
        }
    )
    _write(v06_status_path, v06_status)

    lock_path = ROOT / "dist" / "v0.6" / "V06_FINAL_BASELINE_LOCK.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["officialConfirmed"] = True
    lock["officialConfirmedAt"] = now
    lock["baselineRole"] = "OFFICIAL_READONLY_BASELINE"
    lock["productionReadinessTrack"] = "STARTED"
    _write(lock_path, lock)

    receipt = {
        "schema": "NURION_V06_PR_GATE1_RECEIPT",
        "gate": "1",
        "track": "Production Readiness",
        "name": "DEPLOYMENT_SCOPE_AND_SUPPORTED_ASSETS",
        "PR_GATE1": result["verdict"],
        "parameterHash": ph,
        "sealedBaselineSha256": V06_RC1_SHA,
        "baselineRole": "OFFICIAL_READONLY_BASELINE",
        "production": "NO-GO",
        "immediateProductionGo": "DENY",
        "hardFails": result["hardFails"],
        "publicLimitations": GATE1_PARAMETERS["publicLimitations"],
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V06_PR_GATE1_STATUS",
        "gate": "1",
        "track": "Production Readiness",
        "name": "DEPLOYMENT_SCOPE_AND_SUPPORTED_ASSETS",
        "PR_GATE1": result["verdict"],
        "parameterHash": ph,
        "production": "NO-GO",
        "hardFails": result["hardFails"],
        "updatedAt": now,
        "artifacts": {
            "scope": "V06_PR_DEPLOYMENT_SCOPE.json",
            "assets": "V06_PR_SUPPORTED_ASSETS.json",
            "receipt": "V06_PR_GATE1_RECEIPT.json",
            "parameters": "V06_PR_GATE1_PARAMETERS.json",
        },
        "next": result["next"],
    }
    track = {
        "schema": "NURION_V06_PRODUCTION_READINESS_STATUS",
        "track": "Production Readiness",
        "product": "NURION Unified Character Animation Runtime",
        "sealedBaseline": "v0.6",
        "sealedBaselineSha256": V06_RC1_SHA,
        "baselineRole": "OFFICIAL_READONLY_BASELINE",
        "implementation": "V06_PR_GATE1",
        "status": "IN_PROGRESS",
        "PR_GATE1": result["verdict"],
        "gate1ParameterHash": ph,
        "production": "NO-GO",
        "immediateProductionGo": "DENY",
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V06_PR_GATE1_PARAMETERS.json", GATE1_PARAMETERS)
    _write(OUT / "V06_PR_DEPLOYMENT_SCOPE.json", result["deploymentScope"])
    _write(OUT / "V06_PR_SUPPORTED_ASSETS.json", result["supportedAssets"])
    _write(OUT / "V06_PR_GATE1_CHECKS.json", {"checks": result["checks"], "hardFails": result["hardFails"]})
    _write(OUT / "V06_PR_GATE1_RECEIPT.json", receipt)
    _write(OUT / "V06_PR_GATE1_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "production_readiness" / "STATUS.json", track)

    # Root STATUS
    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = result["next"]
    root_status["nextSteps"] = [
        "V06_SEALED_WITH_LIMITATIONS_OFFICIAL_READONLY_BASELINE",
        "V06_RC1_REPACK_DENY",
        "PRODUCTION_REMAINS_NO_GO",
        f"V06_PR_GATE1_{result['verdict']}",
        "NEXT_" + result["next"],
    ]
    v06 = root_status.setdefault("v06", {})
    v06.update(
        {
            "baselineRole": "OFFICIAL_READONLY_BASELINE",
            "officialConfirmed": True,
            "SEALED": True,
            "READ_ONLY": True,
            "status": "SEALED_WITH_LIMITATIONS",
            "rc1Sha256": V06_RC1_SHA,
            "rc1Repack": "DENY",
            "production": "NO-GO",
            "next": result["next"],
        }
    )
    # Fix stale rcCandidate.SEALED if present
    if isinstance(v06.get("rcCandidate"), dict):
        v06["rcCandidate"]["SEALED"] = True
        v06["rcCandidate"]["baselineRole"] = "OFFICIAL_READONLY_BASELINE"
    v06["rc1Sealed"] = True
    pr = root_status.setdefault("v06ProductionReadiness", {})
    pr.update(
        {
            "name": "Production Readiness",
            "implementation": "V06_PR_GATE1",
            "status": "IN_PROGRESS",
            "PR_GATE1": result["verdict"],
            "gate1ParameterHash": ph,
            "sealedBaselineSha256": V06_RC1_SHA,
            "production": "NO-GO",
            "immediateProductionGo": "DENY",
            "statusArtifacts": {
                "track": "dist/v0.6/production_readiness/STATUS.json",
                "gate1": "dist/v0.6/production_readiness/gate1/V06_PR_GATE1_STATUS.json",
                "scope": "dist/v0.6/production_readiness/gate1/V06_PR_DEPLOYMENT_SCOPE.json",
                "assets": "dist/v0.6/production_readiness/gate1/V06_PR_SUPPORTED_ASSETS.json",
            },
            "next": result["next"],
        }
    )
    arts = v06.setdefault("statusArtifacts", {})
    arts["baselineLock"] = "dist/v0.6/V06_FINAL_BASELINE_LOCK.json"
    arts["prTrack"] = "dist/v0.6/production_readiness/STATUS.json"
    root_status["v06"] = v06
    root_status["v06ProductionReadiness"] = pr
    _write(ROOT / "STATUS.json", root_status)

    print(
        json.dumps(
            {
                "PR_GATE1": result["verdict"],
                "parameterHash": ph,
                "baselineRole": "OFFICIAL_READONLY_BASELINE",
                "rc1Sha256": V06_RC1_SHA,
                "production": "NO-GO",
                "immediateProductionGo": "DENY",
                "hardFails": result["hardFails"],
                "checkCount": len(result["checks"]),
                "passCount": sum(1 for c in result["checks"] if c["result"] == "PASS"),
                "next": result["next"],
            },
            indent=2,
        )
    )
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
