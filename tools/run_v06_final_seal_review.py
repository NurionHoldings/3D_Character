"""
v0.6 Final Seal Review GO — audit only; does not seal.

Usage:
  py -3 tools/run_v06_final_seal_review.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6"
GATE8_HASH = "33fd74ae5cb123d1f3d195fa5f2eb34c39bb360e4c872cb72704a06526a7759b"
RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _register_gate8_rc(now: str) -> None:
    """Official registration of Gate 8 + RC.1 candidate freeze state."""
    g8_status = OUT / "gate8" / "V06_GATE8_STATUS.json"
    g8_receipt = OUT / "gate8" / "V06_GATE8_RECEIPT.json"
    freeze = OUT / "gate8" / "package" / "RC1_CANDIDATE_FREEZE.json"

    for path in (g8_status, g8_receipt):
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["gate8Locked"] = True
        doc["V06_GATE8"] = "PASS_WITH_LIMITATIONS"
        doc["parameterHash"] = GATE8_HASH
        doc["rc1Frozen"] = True
        doc["rc1Sealed"] = False
        doc["rcPackageSha256"] = doc.get("rcPackageSha256") or RC1_SHA
        doc["autoSeal"] = "DENY"
        doc["production"] = "NO-GO"
        doc["officialRegisteredAt"] = now
        doc["next"] = "FINAL_SEAL_REVIEW_COMPLETE"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    fr = json.loads(freeze.read_text(encoding="utf-8"))
    fr["FROZEN"] = True
    fr["SEALED"] = False
    fr["autoSeal"] = "DENY"
    fr["production"] = "NO-GO"
    fr["repack"] = "DENY"
    fr["officialRegisteredAt"] = now
    fr["packageSha256"] = RC1_SHA
    freeze.write_text(json.dumps(fr, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from nurion_v06_unified_runtime.final_seal_review.parameters import REVIEW_PARAMETERS, parameter_hash
    from nurion_v06_unified_runtime.final_seal_review.review import run_final_seal_review
    from nurion_v06_unified_runtime.gate8.parameters import parameter_hash as g8_hash

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if g8_hash() != GATE8_HASH:
        raise RuntimeError(f"Gate8 hash drift: {g8_hash()}")

    _register_gate8_rc(now)
    review = run_final_seal_review(root=ROOT)
    ph = parameter_hash()

    receipt = {
        "schema": "NURION_V06_FINAL_SEAL_REVIEW_RECEIPT",
        "track": "v0.6 Unified Character Animation Runtime",
        "reviewVerdict": review["reviewVerdict"],
        "sealExecution": "NOT_EXECUTED",
        "SEALED": False,
        "autoSeal": "DENY",
        "production": "NO-GO",
        "rc1Repack": "DENY",
        "parameterHash": ph,
        "gate8ParameterHash": GATE8_HASH,
        "rc1Sha256": review["rc1"]["sha256"],
        "holdoutLabel": review["holdout"]["label"],
        "holdoutZipSha256": review["holdout"]["zipSha256"],
        "holdoutFbxSha256": review["holdout"]["fbxSha256"],
        "hardFails": review["hardFails"],
        "limitations": review["limitations"],
        "APPROVED_FOR_LIMITED_FINAL_SEAL": review["reviewVerdict"] == "APPROVED_FOR_LIMITED_FINAL_SEAL",
        "updatedAt": now,
        "next": review["next"],
    }

    status = {
        "schema": "NURION_V06_FINAL_SEAL_REVIEW_STATUS",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "FINAL_SEAL_REVIEW",
        "reviewVerdict": review["reviewVerdict"],
        "sealExecution": "NOT_EXECUTED",
        "SEALED": False,
        "autoSeal": "DENY",
        "production": "NO-GO",
        "parameterHash": ph,
        "gate8Locked": True,
        "rc1Frozen": True,
        "rc1Sealed": False,
        "rc1Sha256": RC1_SHA,
        "hardFails": review["hardFails"],
        "updatedAt": now,
        "artifacts": {
            "review": "NURION_v0.6_FINAL_SEAL_REVIEW.json",
            "receipt": "V06_FINAL_SEAL_REVIEW_RECEIPT.json",
            "parameters": "V06_FINAL_SEAL_REVIEW_PARAMETERS.json",
        },
        "next": review["next"],
    }

    track = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_FINAL_SEAL_REVIEW",
        "status": "APPROVED_FOR_LIMITED_FINAL_SEAL"
        if review["reviewVerdict"] == "APPROVED_FOR_LIMITED_FINAL_SEAL"
        else "SEAL_REVIEW_DENY",
        "V06_GATE8": "PASS_WITH_LIMITATIONS",
        "gate8ParameterHash": GATE8_HASH,
        "gate8Locked": True,
        "rc1Frozen": True,
        "rc1Sealed": False,
        "rc1Sha256": RC1_SHA,
        "finalSealReview": review["reviewVerdict"],
        "sealExecution": "NOT_EXECUTED",
        "SEALED": False,
        "autoSeal": "DENY",
        "production": "NO-GO",
        "rc1Repack": "DENY",
        "inheritedLimitationsFromV05": REVIEW_PARAMETERS["inheritedLimitationsFromV05"],
        "next": review["next"],
        "updatedAt": now,
    }

    _write(OUT / "V06_FINAL_SEAL_REVIEW_PARAMETERS.json", REVIEW_PARAMETERS)
    _write(OUT / "NURION_v0.6_FINAL_SEAL_REVIEW.json", review)
    _write(OUT / "V06_FINAL_SEAL_REVIEW_RECEIPT.json", receipt)
    _write(OUT / "V06_FINAL_SEAL_REVIEW_STATUS.json", status)
    _write(OUT / "STATUS.json", track)
    # root convenience copy of review JSON
    _write(ROOT / "NURION_v0.6_FINAL_SEAL_REVIEW.json", review)

    # Update root STATUS.json v06 block
    root_status_path = ROOT / "STATUS.json"
    root_status = json.loads(root_status_path.read_text(encoding="utf-8"))
    root_status["nextDecision"] = review["next"]
    root_status["nextSteps"] = [
        "V05_REMAINS_OFFICIAL_READONLY_BASELINE",
        "V06_GATE1_TO_GATE7_LOCKED",
        "V06_GATE8_LOCKED_PASS_WITH_LIMITATIONS",
        "V06_RC1_FROZEN_SEALED_FALSE",
        f"V06_FINAL_SEAL_REVIEW_{review['reviewVerdict']}",
        "AUTO_SEAL_DENY",
        "PRODUCTION_REMAINS_NO_GO",
        "SEALED_REMAINS_FALSE",
        "NEXT_" + review["next"],
    ]
    v06 = root_status.setdefault("v06", {})
    v06.update(
        {
            "implementation": "V0.6_FINAL_SEAL_REVIEW",
            "status": track["status"],
            "V06_GATE8": "PASS_WITH_LIMITATIONS",
            "gate8ParameterHash": GATE8_HASH,
            "gate8Locked": True,
            "officialFrozenBaselineGate8": True,
            "rc1Frozen": True,
            "rc1Sealed": False,
            "rc1Sha256": RC1_SHA,
            "finalSealReview": review["reviewVerdict"],
            "sealExecution": "NOT_EXECUTED",
            "SEALED": False,
            "autoSeal": "DENY",
            "production": "NO-GO",
            "productionAutoAdvance": "DENY",
            "rc1Repack": "DENY",
            "next": review["next"],
        }
    )
    arts = v06.setdefault("statusArtifacts", {})
    arts["finalSealReview"] = "dist/v0.6/NURION_v0.6_FINAL_SEAL_REVIEW.json"
    arts["finalSealReviewReceipt"] = "dist/v0.6/V06_FINAL_SEAL_REVIEW_RECEIPT.json"
    arts["finalSealReviewStatus"] = "dist/v0.6/V06_FINAL_SEAL_REVIEW_STATUS.json"
    arts["rcFreeze"] = "dist/v0.6/gate8/package/RC1_CANDIDATE_FREEZE.json"
    root_status["v06"] = v06
    _write(root_status_path, root_status)

    print(
        json.dumps(
            {
                "reviewVerdict": review["reviewVerdict"],
                "SEALED": False,
                "autoSeal": "DENY",
                "production": "NO-GO",
                "parameterHash": ph,
                "rc1Sha256": review["rc1"]["sha256"],
                "hardFails": review["hardFails"],
                "checkCount": len(review["checks"]),
                "passCount": sum(1 for c in review["checks"] if c["result"] == "PASS"),
            },
            indent=2,
        )
    )
    return 0 if review["reviewVerdict"] == "APPROVED_FOR_LIMITED_FINAL_SEAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
