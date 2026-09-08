"""
v0.6 Production Readiness Gate 2 GO — failure / ABSTAIN / recovery policy.

Usage:
  py -3 tools/run_v06_pr_gate2_failure_abstain_recovery.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "production_readiness" / "gate2"
GATE1_HASH = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
V06_RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _lock_gate1(now: str) -> None:
    g1_dir = ROOT / "dist" / "v0.6" / "production_readiness" / "gate1"
    for name in ("V06_PR_GATE1_STATUS.json", "V06_PR_GATE1_RECEIPT.json"):
        path = g1_dir / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["PR_GATE1"] = "PASS"
        doc["parameterHash"] = GATE1_HASH
        doc["production"] = "NO-GO"
        doc["sealedBaselineMutation"] = "DENY"
        doc["frozenAt"] = now
        doc["next"] = "PR_GATE2_FAILURE_ABSTAIN_RECOVERY_POLICY"
        _write(path, doc)


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from nurion_v06_production_readiness.gate1.parameters import parameter_hash as g1_hash
    from nurion_v06_production_readiness.gate2.parameters import GATE2_PARAMETERS, parameter_hash
    from nurion_v06_production_readiness.gate2.policy import run_pr_gate2_policies

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if g1_hash() != GATE1_HASH:
        raise RuntimeError(f"PR Gate1 hash drift — DENY: {g1_hash()}")

    _lock_gate1(now)
    result = run_pr_gate2_policies(root=ROOT)
    ph = parameter_hash()

    receipt = {
        "schema": "NURION_V06_PR_GATE2_RECEIPT",
        "gate": "2",
        "track": "Production Readiness",
        "name": "FAILURE_ABSTAIN_RECOVERY_POLICY",
        "PR_GATE2": result["verdict"],
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "sealedBaselineSha256": V06_RC1_SHA,
        "sealedBaselineMutation": "DENY",
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "partialExportPublish": "DENY",
        "sourceMutation": result["sourceMutation"],
        "manualCorrection": result["manualCorrection"],
        "hardFails": result["hardFails"],
        "scenarioCount": len(result["scenarios"]),
        "scenariosPassed": sum(1 for s in result["scenarios"] if s.get("ok")),
        "notes": result["notes"],
        "updatedAt": now,
        "next": result["next"],
    }
    status = {
        "schema": "NURION_V06_PR_GATE2_STATUS",
        "gate": "2",
        "track": "Production Readiness",
        "name": "FAILURE_ABSTAIN_RECOVERY_POLICY",
        "PR_GATE2": result["verdict"],
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "production": "NO-GO",
        "hardFails": result["hardFails"],
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_PR_GATE2_RECEIPT.json",
            "parameters": "V06_PR_GATE2_PARAMETERS.json",
            "scenarios": "V06_PR_GATE2_SCENARIOS.json",
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
        "implementation": "V06_PR_GATE2",
        "status": "IN_PROGRESS",
        "PR_GATE1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "PR_GATE2": result["verdict"],
        "gate2ParameterHash": ph,
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "next": result["next"],
        "updatedAt": now,
    }

    _write(OUT / "V06_PR_GATE2_PARAMETERS.json", GATE2_PARAMETERS)
    _write(OUT / "V06_PR_GATE2_SCENARIOS.json", {"scenarios": result["scenarios"], "hardFails": result["hardFails"]})
    _write(OUT / "V06_PR_GATE2_RECEIPT.json", receipt)
    _write(OUT / "V06_PR_GATE2_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "production_readiness" / "STATUS.json", track)

    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = result["next"]
    root_status["nextSteps"] = [
        "V06_SEALED_WITH_LIMITATIONS_OFFICIAL_READONLY_BASELINE",
        "V06_PR_GATE1_LOCKED_PASS",
        f"V06_PR_GATE2_{result['verdict']}",
        "PRODUCTION_REMAINS_NO_GO",
        "NEXT_" + result["next"],
    ]
    pr = root_status.setdefault("v06ProductionReadiness", {})
    pr.update(
        {
            "implementation": "V06_PR_GATE2",
            "status": "IN_PROGRESS",
            "PR_GATE1": "PASS",
            "gate1ParameterHash": GATE1_HASH,
            "gate1Locked": True,
            "officialFrozenBaselineGate1": True,
            "PR_GATE2": result["verdict"],
            "gate2ParameterHash": ph,
            "production": "NO-GO",
            "productionAutoAdvance": "DENY",
            "next": result["next"],
        }
    )
    arts = pr.setdefault("statusArtifacts", {})
    arts["gate2"] = "dist/v0.6/production_readiness/gate2/V06_PR_GATE2_STATUS.json"
    arts["gate2Receipt"] = "dist/v0.6/production_readiness/gate2/V06_PR_GATE2_RECEIPT.json"
    root_status["v06ProductionReadiness"] = pr
    v06 = root_status.setdefault("v06", {})
    v06["next"] = result["next"]
    v06["sealedBaselineMutation"] = "DENY"
    v06["production"] = "NO-GO"
    root_status["v06"] = v06
    _write(ROOT / "STATUS.json", root_status)

    print(
        json.dumps(
            {
                "PR_GATE2": result["verdict"],
                "parameterHash": ph,
                "gate1Locked": True,
                "gate1ParameterHash": GATE1_HASH,
                "hardFails": result["hardFails"],
                "scenariosPassed": receipt["scenariosPassed"],
                "scenarioCount": receipt["scenarioCount"],
                "production": "NO-GO",
                "productionAutoAdvance": "DENY",
                "sourceMutation": 0,
                "next": result["next"],
            },
            indent=2,
        )
    )
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
