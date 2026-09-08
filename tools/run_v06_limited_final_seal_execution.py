"""
v0.6 Limited Final Seal Execution GO — readonly hash compare only.

Usage:
  py -3 tools/run_v06_limited_final_seal_execution.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6"
REVIEW_HASH = "eb2bd86959b5d199fb367046daa3835b34d181883b977b0e788d43a52213768e"
RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from nurion_v06_unified_runtime.final_seal_execution.execute import execute_limited_final_seal
    from nurion_v06_unified_runtime.final_seal_execution.parameters import SEAL_EXECUTION_PARAMETERS
    from nurion_v06_unified_runtime.final_seal_review.parameters import parameter_hash as review_ph

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # Keep Final Seal Review official state (do not mutate review verdict)
    review_path = OUT / "NURION_v0.6_FINAL_SEAL_REVIEW.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("reviewVerdict") != "APPROVED_FOR_LIMITED_FINAL_SEAL":
        raise RuntimeError("Final Seal Review not APPROVED — DENY execution")
    if review.get("parameterHash") != REVIEW_HASH or review_ph() != REVIEW_HASH:
        raise RuntimeError("Final Seal Review hash drift — SEAL_DENY (no repair)")

    result = execute_limited_final_seal(root=ROOT)
    receipt = result["receipt"]
    lock = result["baselineLock"]
    validation = result["validationStatus"]

    # Persist artifacts (even on SEAL_DENY for audit trail)
    _write(OUT / "V06_FINAL_SEAL_EXECUTION_PARAMETERS.json", SEAL_EXECUTION_PARAMETERS)
    _write(OUT / "V06_FINAL_SEAL_RECEIPT.json", receipt)
    _write(OUT / "V06_FINAL_BASELINE_LOCK.json", lock)
    _write(OUT / "V06_VALIDATION_STATUS.json", validation)
    _write(ROOT / "V06_FINAL_SEAL_RECEIPT.json", receipt)
    _write(ROOT / "V06_FINAL_BASELINE_LOCK.json", lock)

    # Annotate review document with seal execution outcome (do not change reviewVerdict)
    review["sealExecution"] = result["sealExecution"]
    review["sealVerdict"] = result["verdict"]
    review["SEALED"] = bool(result["passed"])
    review["sealed"] = bool(result["passed"])
    if result["passed"]:
        review["sealedAt"] = receipt.get("sealedAt")
    review["sealExecutionAt"] = now
    review["next"] = receipt.get("next")
    _write(review_path, review)
    _write(ROOT / "NURION_v0.6_FINAL_SEAL_REVIEW.json", review)

    # Update freeze record if sealed
    freeze_path = OUT / "gate8" / "package" / "RC1_CANDIDATE_FREEZE.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if result["passed"]:
        freeze["SEALED"] = True
        freeze["FROZEN"] = True
        freeze["baselineRole"] = "OFFICIAL_READONLY_BASELINE"
        freeze["repack"] = "DENY"
        freeze["sealedAt"] = receipt.get("sealedAt")
        freeze["sealVerdict"] = "SEALED_WITH_LIMITATIONS"
    else:
        freeze["SEALED"] = False
        freeze["sealVerdict"] = "SEAL_DENY"
    freeze["updatedAt"] = now
    _write(freeze_path, freeze)

    track = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_LIMITED_FINAL_SEAL",
        "status": result["verdict"],
        "SEALED": bool(result["passed"]),
        "READ_ONLY": bool(result["passed"]),
        "finalSealReview": "APPROVED_FOR_LIMITED_FINAL_SEAL",
        "finalSealReviewParameterHash": REVIEW_HASH,
        "sealExecution": result["sealExecution"],
        "verdict": result["verdict"],
        "rc1Sha256": RC1_SHA,
        "rc1Repack": "DENY",
        "autoSeal": "DENY",
        "production": "NO-GO",
        "supportedDomain": "LIMITED",
        "inheritedLimitationsFromV05": SEAL_EXECUTION_PARAMETERS["inheritedLimitationsFromV05"],
        "hardFails": result["hardFails"],
        "sealExecutionParameterHash": result["parameterHash"],
        "next": receipt.get("next"),
        "updatedAt": now,
    }
    _write(OUT / "STATUS.json", track)

    # Root STATUS
    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = receipt.get("next")
    root_status["nextSteps"] = [
        "V06_FINAL_SEAL_REVIEW_APPROVED_FOR_LIMITED_FINAL_SEAL",
        f"V06_SEAL_EXECUTION_{result['sealExecution']}",
        f"V06_{result['verdict']}",
        "RC1_REPACK_DENY",
        "PRODUCTION_REMAINS_NO_GO",
        "NEXT_" + str(receipt.get("next")),
    ]
    v06 = root_status.setdefault("v06", {})
    v06.update(
        {
            "implementation": "V0.6_LIMITED_FINAL_SEAL",
            "status": result["verdict"],
            "SEALED": bool(result["passed"]),
            "READ_ONLY": bool(result["passed"]),
            "baselineRole": "OFFICIAL_READONLY_BASELINE" if result["passed"] else "NOT_SEALED",
            "finalSealReview": "APPROVED_FOR_LIMITED_FINAL_SEAL",
            "finalSealReviewParameterHash": REVIEW_HASH,
            "sealExecution": result["sealExecution"],
            "verdict": result["verdict"],
            "rc1Sha256": RC1_SHA,
            "rc1Repack": "DENY",
            "autoSeal": "DENY",
            "production": "NO-GO",
            "supportedDomain": "LIMITED",
            "sealExecutionParameterHash": result["parameterHash"],
            "next": receipt.get("next"),
        }
    )
    arts = v06.setdefault("statusArtifacts", {})
    arts["sealReceipt"] = "dist/v0.6/V06_FINAL_SEAL_RECEIPT.json"
    arts["baselineLock"] = "dist/v0.6/V06_FINAL_BASELINE_LOCK.json"
    arts["validationStatus"] = "dist/v0.6/V06_VALIDATION_STATUS.json"
    arts["finalSealReview"] = "dist/v0.6/NURION_v0.6_FINAL_SEAL_REVIEW.json"
    root_status["v06"] = v06
    _write(ROOT / "STATUS.json", root_status)

    print(
        json.dumps(
            {
                "sealExecution": result["sealExecution"],
                "verdict": result["verdict"],
                "SEALED": bool(result["passed"]),
                "production": "NO-GO",
                "rc1Sha256": RC1_SHA,
                "finalSealReview": "APPROVED_FOR_LIMITED_FINAL_SEAL",
                "reviewParameterHash": REVIEW_HASH,
                "sealExecutionParameterHash": result["parameterHash"],
                "hardFails": result["hardFails"],
                "checkCount": len(result["checks"]),
                "passCount": sum(1 for c in result["checks"] if c["result"] == "PASS"),
            },
            indent=2,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
