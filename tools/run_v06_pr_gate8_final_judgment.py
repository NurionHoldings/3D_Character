"""
v0.6 Production Readiness Gate 8 — Final Production Readiness Judgment.

Usage:
  py -3 tools/run_v06_pr_gate8_final_judgment.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "production_readiness" / "gate8"
PR = ROOT / "dist" / "v0.6" / "production_readiness"

GATE1_HASH = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_HASH = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_HASH = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE4_HASH = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"
GATE5_HASH = "d5bcfe242c856d746b1190346cfec3cc0f2959f3b6071179a1b486a0491709fe"
GATE6_HASH = "65aff0f4edced493e3dd62ac8c0d062bcdde7531d13d348a1530bf59c70f290b"
GATE7_HASH = "2e34ee9082c97d9fac46ba423e3748b456700cb3f7224a161c53207430ca2a11"
RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"
WRAPPER_SHA = "1094c18a12c3fda162ac061ce2cf05f5e0633446aeef41097885c81f41ecd6e7"
WRAPPER_VER = "0.6.0-wrapper.1"
HOLDOUT_ZIP = "dd6ca3e7055d18b838e863c5aae8a9ce597647893cc303d6ace475e84fbb6e7a"
HOLDOUT_FBX = "509d6a3fec38235f84adbf4c3f16ec4dccf35315f8dddd137ddb7d65f43706d4"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _lock_gates_1_7(now: str) -> None:
    specs = [
        ("gate1/V06_PR_GATE1_STATUS.json", "PR_GATE1", "PASS", GATE1_HASH),
        ("gate2/V06_PR_GATE2_STATUS.json", "PR_GATE2", "PASS", GATE2_HASH),
        ("gate3/V06_PR_GATE3_STATUS.json", "PR_GATE3", "PASS", GATE3_HASH),
        ("gate4/V06_PR_GATE4_STATUS.json", "PR_GATE4", "PASS", GATE4_HASH),
        ("gate5/V06_PR_GATE5_STATUS.json", "PR_GATE5", "PASS", GATE5_HASH),
        ("gate6/V06_PR_GATE6_STATUS.json", "PR_GATE6", "PASS_WITH_LIMITATIONS", GATE6_HASH),
        ("gate7/V06_PR_GATE7_STATUS.json", "PR_GATE7", "HOLDOUT_PASS", GATE7_HASH),
        ("gate7/V06_PR_GATE7_RECEIPT.json", "PR_GATE7", "HOLDOUT_PASS", GATE7_HASH),
    ]
    for rel, key, verdict, ph in specs:
        path = PR / rel
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc[key] = verdict
        doc["parameterHash"] = ph
        doc["frozenAt"] = now
        doc["production"] = "NO-GO"
        if "gate7" in rel:
            doc["noveltyScope"] = "FRESH_WITHIN_PR_TRACK"
            doc["projectWideFreshHoldoutClaim"] = "DENY"
            doc["holdoutZipSha256"] = HOLDOUT_ZIP
            doc["holdoutFbxSha256"] = HOLDOUT_FBX
            doc["assetIdentity"] = "V06_PR_GATE7_HOLDOUT_ASSET_IDENTITY.json"
        _write(path, doc)

    # Ensure identity artifact present & locked
    identity = PR / "gate7/V06_PR_GATE7_HOLDOUT_ASSET_IDENTITY.json"
    if identity.is_file():
        doc = json.loads(identity.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaselineGate7"] = True
        doc["frozenAt"] = now
        _write(identity, doc)
        _write(OUT / "V06_PR_GATE7_HOLDOUT_ASSET_IDENTITY.json", doc)


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from nurion_v06_production_readiness.gate8.judgment import run_final_judgment
    from nurion_v06_production_readiness.gate8.parameters import GATE8_PARAMETERS, parameter_hash
    from nurion_v06_production_readiness.gate7.parameters import PR_INHERITED_LIMITATIONS

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    _lock_gates_1_7(now)

    result = run_final_judgment(root=ROOT)
    ph = parameter_hash()
    verdict = result["verdict"]

    receipt = {
        "schema": "NURION_V06_PR_GATE8_RECEIPT",
        "gate": "8",
        "track": "Production Readiness",
        "name": "FINAL_PRODUCTION_READINESS_JUDGMENT",
        "PR_GATE8": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate5ParameterHash": GATE5_HASH,
        "gate6ParameterHash": GATE6_HASH,
        "gate7ParameterHash": GATE7_HASH,
        "gates1to7Locked": True,
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
        "conditions": result.get("conditions"),
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "externalCustomerDeploy": "DENY",
        "unattendedAutomation": "DENY",
        "generalPublicRelease": "DENY",
        "operatorPreTrainingRequired": True,
        "exportDisclosureCheckRequired": True,
        "productionAutoActivate": "DENY",
        "unconditionalGo": "DENY",
        "activation": result.get("activation"),
        "activationRequires": result.get("activationRequires"),
        "hardFails": result.get("hardFails"),
        "production": "NO-GO" if verdict != "CONDITIONAL_GO" else "CONDITIONAL_GO_PENDING_ACTIVATION",
        "updatedAt": now,
        "next": result.get("next"),
    }
    status = {
        "schema": "NURION_V06_PR_GATE8_STATUS",
        "gate": "8",
        "track": "Production Readiness",
        "name": "FINAL_PRODUCTION_READINESS_JUDGMENT",
        "PR_GATE8": verdict,
        "parameterHash": ph,
        "LOCKED": True,
        "officialFrozenBaseline": True,
        "production": receipt["production"],
        "activation": "NOT_GRANTED",
        "hardFails": result.get("hardFails"),
        "conditions": result.get("conditions"),
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_PR_GATE8_RECEIPT.json",
            "parameters": "V06_PR_GATE8_PARAMETERS.json",
            "checks": "V06_PR_GATE8_CHECKS.json",
            "judgment": "V06_PR_GATE8_JUDGMENT.json",
            "holdoutIdentity": "../gate7/V06_PR_GATE7_HOLDOUT_ASSET_IDENTITY.json",
        },
        "next": result.get("next"),
    }
    track = {
        "schema": "NURION_V06_PRODUCTION_READINESS_STATUS",
        "track": "Production Readiness",
        "product": "NURION Unified Character Animation Runtime",
        "sealedBaseline": "v0.6",
        "sealedBaselineSha256": RC1_SHA,
        "implementation": "V06_PR_GATE8",
        "status": "JUDGED" if verdict == "CONDITIONAL_GO" else "IN_PROGRESS",
        "PR_GATE1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "PR_GATE2": "PASS",
        "gate2ParameterHash": GATE2_HASH,
        "gate2Locked": True,
        "PR_GATE3": "PASS",
        "gate3ParameterHash": GATE3_HASH,
        "gate3Locked": True,
        "PR_GATE4": "PASS",
        "gate4ParameterHash": GATE4_HASH,
        "gate4Locked": True,
        "PR_GATE5": "PASS",
        "gate5ParameterHash": GATE5_HASH,
        "gate5Locked": True,
        "PR_GATE6": "PASS_WITH_LIMITATIONS",
        "gate6ParameterHash": GATE6_HASH,
        "gate6Locked": True,
        "PR_GATE7": "HOLDOUT_PASS",
        "gate7ParameterHash": GATE7_HASH,
        "gate7Locked": True,
        "officialFrozenBaselineGate7": True,
        "PR_GATE8": verdict,
        "gate8ParameterHash": ph,
        "gate8Locked": True,
        "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
        "holdoutNoveltyScope": "FRESH_WITHIN_PR_TRACK",
        "blInfoWrapperComponent": {
            "version": WRAPPER_VER,
            "wrapperSha256": WRAPPER_SHA,
            "targetRc1Sha256": RC1_SHA,
            "LOCKED": True,
        },
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "production": receipt["production"],
        "productionAutoActivate": "DENY",
        "activation": "NOT_GRANTED",
        "unconditionalGo": "DENY",
        "next": result.get("next"),
        "updatedAt": now,
    }

    _write(OUT / "V06_PR_GATE8_PARAMETERS.json", GATE8_PARAMETERS)
    _write(OUT / "V06_PR_GATE8_CHECKS.json", {"checks": result["checks"], "hardFails": result.get("hardFails")})
    _write(OUT / "V06_PR_GATE8_JUDGMENT.json", result)
    _write(OUT / "V06_PR_GATE8_RECEIPT.json", receipt)
    _write(OUT / "V06_PR_GATE8_STATUS.json", status)
    _write(PR / "STATUS.json", track)

    # Operator conditions brief
    brief = {
        "schema": "NURION_V06_PR_CONDITIONAL_GO_OPERATOR_BRIEF",
        "verdict": verdict,
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "must": [
            "Complete operator pre-training on LIMITED / ABSTAIN / REST_FALLBACK / Validate-before-Export",
            "Confirm Export disclosure sidecar lists all 5 inherited limitations",
            "Treat PANEL_LIMITATION_IDS_RENDERED as accepted residual risk (IDs not on sealed panel)",
            "Do not deploy to external customers, unattended automation, or general public release",
            "Do not claim holdout as project-wide Fresh; scope is FRESH_WITHIN_PR_TRACK only",
            "Activation requires a separate explicit approval — Gate8 judgment does not activate production",
        ],
        "hashes": {
            "rc1Sha256": RC1_SHA,
            "wrapperSha256": WRAPPER_SHA,
            "holdoutZipSha256": HOLDOUT_ZIP,
            "holdoutFbxSha256": HOLDOUT_FBX,
            "gate8ParameterHash": ph,
        },
        "activation": "NOT_GRANTED",
    }
    _write(OUT / "V06_PR_CONDITIONAL_GO_OPERATOR_BRIEF.json", brief)

    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = result.get("next")
    root_status["nextSteps"] = [
        "V06_PR_GATE1_TO_7_LOCKED",
        f"V06_PR_GATE8_{verdict}",
        "ACTIVATION_NOT_GRANTED",
        "UNCONDITIONAL_GO_DENY",
        "NEXT_" + str(result.get("next")),
    ]
    prs = root_status.setdefault("v06ProductionReadiness", {})
    prs.update(
        {
            "implementation": "V06_PR_GATE8",
            "status": track["status"],
            "PR_GATE1": "PASS",
            "gate1Locked": True,
            "PR_GATE2": "PASS",
            "gate2Locked": True,
            "PR_GATE3": "PASS",
            "gate3Locked": True,
            "PR_GATE4": "PASS",
            "gate4Locked": True,
            "PR_GATE5": "PASS",
            "gate5Locked": True,
            "PR_GATE6": "PASS_WITH_LIMITATIONS",
            "gate6Locked": True,
            "PR_GATE7": "HOLDOUT_PASS",
            "gate7ParameterHash": GATE7_HASH,
            "gate7Locked": True,
            "officialFrozenBaselineGate7": True,
            "holdoutNoveltyScope": "FRESH_WITHIN_PR_TRACK",
            "PR_GATE8": verdict,
            "gate8ParameterHash": ph,
            "gate8Locked": True,
            "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
            "blInfoWrapperComponent": {
                "version": WRAPPER_VER,
                "wrapperSha256": WRAPPER_SHA,
                "targetRc1Sha256": RC1_SHA,
                "LOCKED": True,
            },
            "channel": "LIMITED_INTERNAL_OPERATOR",
            "production": receipt["production"],
            "productionAutoActivate": "DENY",
            "activation": "NOT_GRANTED",
            "unconditionalGo": "DENY",
            "next": result.get("next"),
        }
    )
    arts = prs.setdefault("statusArtifacts", {})
    arts["gate7"] = "dist/v0.6/production_readiness/gate7/V06_PR_GATE7_STATUS.json"
    arts["gate7HoldoutIdentity"] = "dist/v0.6/production_readiness/gate7/V06_PR_GATE7_HOLDOUT_ASSET_IDENTITY.json"
    arts["gate8"] = "dist/v0.6/production_readiness/gate8/V06_PR_GATE8_STATUS.json"
    arts["gate8Receipt"] = "dist/v0.6/production_readiness/gate8/V06_PR_GATE8_RECEIPT.json"
    arts["gate8Brief"] = "dist/v0.6/production_readiness/gate8/V06_PR_CONDITIONAL_GO_OPERATOR_BRIEF.json"
    root_status["v06ProductionReadiness"] = prs
    _write(ROOT / "STATUS.json", root_status)

    summary = {
        "PR_GATE8": verdict,
        "parameterHash": ph,
        "hardFails": result.get("hardFails"),
        "conditions": result.get("conditions"),
        "activation": "NOT_GRANTED",
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "unconditionalGo": "DENY",
        "holdoutNoveltyScope": "FRESH_WITHIN_PR_TRACK",
        "holdoutZipSha256": HOLDOUT_ZIP,
        "holdoutFbxSha256": HOLDOUT_FBX,
        "production": receipt["production"],
        "next": result.get("next"),
    }
    print(json.dumps(summary, indent=2))
    return 0 if verdict == "CONDITIONAL_GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
