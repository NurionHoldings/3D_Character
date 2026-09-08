"""
v0.6 Limited Internal Production Activation Review (READ-ONLY).

Usage:
  py -3 tools/run_v06_limited_internal_activation_review.py

This command does NOT activate production.
Activation Execution requires a separate GO after REVIEW_PASS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PR = ROOT / "dist" / "v0.6" / "production_readiness"
OUT = PR / "activation_review"

GATE1_HASH = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_HASH = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_HASH = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE4_HASH = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"
GATE5_HASH = "d5bcfe242c856d746b1190346cfec3cc0f2959f3b6071179a1b486a0491709fe"
GATE6_HASH = "65aff0f4edced493e3dd62ac8c0d062bcdde7531d13d348a1530bf59c70f290b"
GATE7_HASH = "2e34ee9082c97d9fac46ba423e3748b456700cb3f7224a161c53207430ca2a11"
GATE8_HASH = "b00f7694346b448743fb6940e9aab2fe38d40645c37a15c59fab688eda2c024a"
RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"
WRAPPER_SHA = "1094c18a12c3fda162ac061ce2cf05f5e0633446aeef41097885c81f41ecd6e7"
WRAPPER_VER = "0.6.0-wrapper.1"
HOLDOUT_ZIP = "dd6ca3e7055d18b838e863c5aae8a9ce597647893cc303d6ace475e84fbb6e7a"
HOLDOUT_FBX = "509d6a3fec38235f84adbf4c3f16ec4dccf35315f8dddd137ddb7d65f43706d4"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _freeze_gate7_gate8(now: str) -> None:
    for rel, key, verdict, ph in [
        ("gate7/V06_PR_GATE7_STATUS.json", "PR_GATE7", "HOLDOUT_PASS", GATE7_HASH),
        ("gate7/V06_PR_GATE7_RECEIPT.json", "PR_GATE7", "HOLDOUT_PASS", GATE7_HASH),
        ("gate8/V06_PR_GATE8_STATUS.json", "PR_GATE8", "CONDITIONAL_GO", GATE8_HASH),
        ("gate8/V06_PR_GATE8_RECEIPT.json", "PR_GATE8", "CONDITIONAL_GO", GATE8_HASH),
    ]:
        path = PR / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc[key] = verdict
        doc["parameterHash"] = ph
        doc["frozenAt"] = now
        if key == "PR_GATE7":
            doc["noveltyScope"] = "FRESH_WITHIN_PR_TRACK"
            doc["projectWideFreshHoldoutClaim"] = "DENY"
            doc["holdoutZipSha256"] = HOLDOUT_ZIP
            doc["holdoutFbxSha256"] = HOLDOUT_FBX
        if key == "PR_GATE8":
            doc["activation"] = "NOT_GRANTED"
            doc["unconditionalGo"] = "DENY"
        _write(path, doc)

    identity = PR / "gate7/V06_PR_GATE7_HOLDOUT_ASSET_IDENTITY.json"
    doc = json.loads(identity.read_text(encoding="utf-8"))
    doc["LOCKED"] = True
    doc["officialFrozenBaselineGate7"] = True
    doc["frozenAt"] = now
    _write(identity, doc)


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from nurion_v06_production_readiness.activation_review.parameters import (
        ACTIVATION_REVIEW_PARAMETERS,
        parameter_hash,
    )
    from nurion_v06_production_readiness.activation_review.review import run_activation_review
    from nurion_v06_production_readiness.gate7.parameters import PR_INHERITED_LIMITATIONS

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    _freeze_gate7_gate8(now)

    result = run_activation_review(root=ROOT)
    ph = parameter_hash()
    verdict = result["verdict"]

    receipt = {
        "schema": "NURION_V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_RECEIPT",
        "track": "Limited Internal Production Activation Review",
        "name": "READ_ONLY_PRE_ACTIVATION_REVIEW",
        "ACTIVATION_REVIEW": verdict,
        "parameterHash": ph,
        "mode": "READ_ONLY_REVIEW",
        "thisCommandActivatedProduction": False,
        "activation": "NOT_GRANTED",
        "activationExecution": "NOT_STARTED",
        "deploy": "DENY",
        "conditionChange": "DENY",
        "limitationClear": "DENY",
        "unconditionalGo": "DENY",
        "prerequisite": {
            "PR_GATE8": "CONDITIONAL_GO",
            "gate8ParameterHash": GATE8_HASH,
            "PR_GATE7": "HOLDOUT_PASS",
            "gate7ParameterHash": GATE7_HASH,
        },
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "rc1Sha256": RC1_SHA,
        "wrapperComponent": {
            "version": WRAPPER_VER,
            "wrapperSha256": WRAPPER_SHA,
            "targetRc1Sha256": RC1_SHA,
            "LOCKED": True,
        },
        "holdout": {
            "label": "MINIMALIST_TENNIS_OUT",
            "zipFileName": "Wither_character-rig.zip",
            "zipSha256": HOLDOUT_ZIP,
            "fbxSha256": HOLDOUT_FBX,
            "noveltyScope": "FRESH_WITHIN_PR_TRACK",
            "projectWideFreshHoldoutClaim": "DENY",
        },
        "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
        "conditionsFrozen": result.get("conditionsFrozen"),
        "hardFails": result.get("hardFails"),
        "note": result.get("note"),
        "updatedAt": now,
        "next": result.get("next"),
    }
    status = {
        "schema": "NURION_V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_STATUS",
        "track": "Limited Internal Production Activation Review",
        "ACTIVATION_REVIEW": verdict,
        "parameterHash": ph,
        "LOCKED": True,
        "mode": "READ_ONLY_REVIEW",
        "activation": "NOT_GRANTED",
        "activationExecution": "NOT_STARTED",
        "deploy": "DENY",
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_RECEIPT.json",
            "parameters": "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_PARAMETERS.json",
            "checks": "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_CHECKS.json",
            "result": "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_RESULT.json",
        },
        "next": result.get("next"),
    }
    track = {
        "schema": "NURION_V06_PRODUCTION_READINESS_STATUS",
        "track": "Production Readiness",
        "product": "NURION Unified Character Animation Runtime",
        "sealedBaselineSha256": RC1_SHA,
        "implementation": "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW",
        "status": "ACTIVATION_REVIEW_COMPLETE" if verdict.startswith("REVIEW_PASS") else "ACTIVATION_REVIEW_OPEN",
        "PR_GATE7": "HOLDOUT_PASS",
        "gate7ParameterHash": GATE7_HASH,
        "gate7Locked": True,
        "officialFrozenBaselineGate7": True,
        "PR_GATE8": "CONDITIONAL_GO",
        "gate8ParameterHash": GATE8_HASH,
        "gate8Locked": True,
        "officialFrozenBaselineGate8": True,
        "ACTIVATION_REVIEW": verdict,
        "activationReviewParameterHash": ph,
        "holdoutNoveltyScope": "FRESH_WITHIN_PR_TRACK",
        "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "production": "CONDITIONAL_GO_PENDING_ACTIVATION",
        "activation": "NOT_GRANTED",
        "activationExecution": "NOT_STARTED",
        "deploy": "DENY",
        "conditionChange": "DENY",
        "limitationClear": "DENY",
        "blInfoWrapperComponent": {
            "version": WRAPPER_VER,
            "wrapperSha256": WRAPPER_SHA,
            "targetRc1Sha256": RC1_SHA,
            "LOCKED": True,
        },
        "next": result.get("next"),
        "updatedAt": now,
    }

    _write(OUT / "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_PARAMETERS.json", ACTIVATION_REVIEW_PARAMETERS)
    _write(OUT / "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_CHECKS.json", {"checks": result["checks"], "hardFails": result.get("hardFails")})
    _write(OUT / "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_RESULT.json", result)
    _write(OUT / "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_RECEIPT.json", receipt)
    _write(OUT / "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_STATUS.json", status)
    _write(PR / "STATUS.json", track)

    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = result.get("next")
    root_status["nextSteps"] = [
        "V06_PR_GATE7_LOCKED_HOLDOUT_PASS",
        "V06_PR_GATE8_LOCKED_CONDITIONAL_GO",
        f"V06_ACTIVATION_REVIEW_{verdict}",
        "ACTIVATION_NOT_GRANTED",
        "DEPLOY_DENY",
        "NEXT_" + str(result.get("next")),
    ]
    prs = root_status.setdefault("v06ProductionReadiness", {})
    prs.update(
        {
            "implementation": "V06_LIMITED_INTERNAL_ACTIVATION_REVIEW",
            "status": track["status"],
            "PR_GATE7": "HOLDOUT_PASS",
            "gate7ParameterHash": GATE7_HASH,
            "gate7Locked": True,
            "officialFrozenBaselineGate7": True,
            "PR_GATE8": "CONDITIONAL_GO",
            "gate8ParameterHash": GATE8_HASH,
            "gate8Locked": True,
            "officialFrozenBaselineGate8": True,
            "ACTIVATION_REVIEW": verdict,
            "activationReviewParameterHash": ph,
            "holdoutNoveltyScope": "FRESH_WITHIN_PR_TRACK",
            "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
            "channel": "LIMITED_INTERNAL_OPERATOR",
            "production": "CONDITIONAL_GO_PENDING_ACTIVATION",
            "activation": "NOT_GRANTED",
            "activationExecution": "NOT_STARTED",
            "deploy": "DENY",
            "conditionChange": "DENY",
            "limitationClear": "DENY",
            "blInfoWrapperComponent": {
                "version": WRAPPER_VER,
                "wrapperSha256": WRAPPER_SHA,
                "targetRc1Sha256": RC1_SHA,
                "LOCKED": True,
            },
            "next": result.get("next"),
        }
    )
    arts = prs.setdefault("statusArtifacts", {})
    arts["gate8"] = "dist/v0.6/production_readiness/gate8/V06_PR_GATE8_STATUS.json"
    arts["activationReview"] = "dist/v0.6/production_readiness/activation_review/V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_STATUS.json"
    arts["activationReviewReceipt"] = "dist/v0.6/production_readiness/activation_review/V06_LIMITED_INTERNAL_ACTIVATION_REVIEW_RECEIPT.json"
    root_status["v06ProductionReadiness"] = prs
    _write(ROOT / "STATUS.json", root_status)

    summary = {
        "ACTIVATION_REVIEW": verdict,
        "parameterHash": ph,
        "mode": "READ_ONLY_REVIEW",
        "activation": "NOT_GRANTED",
        "activationExecution": "NOT_STARTED",
        "deploy": "DENY",
        "conditionChange": "DENY",
        "limitationClear": "DENY",
        "hardFails": result.get("hardFails"),
        "checkCount": len(result.get("checks") or []),
        "passCount": sum(1 for c in (result.get("checks") or []) if c["result"] == "PASS"),
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "next": result.get("next"),
    }
    print(json.dumps(summary, indent=2))
    return 0 if verdict == "REVIEW_PASS_AWAIT_ACTIVATION_EXECUTION_GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
