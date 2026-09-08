"""CCS Gate 8 — Identity Recognition / Preference / Acceptance Holdout.

Technical pipeline cannot auto-PASS. Scans human evidence intake; without
consented evaluations issues MORE_HUMAN_EVIDENCE_REQUIRED.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.7" / "canonical" / "gate8"
EVIDENCE = OUT / "evidence"
GATE7_HASH = "a421a7592ff64429db2f47ef7c0d6263d424a13226e5b6e53bb8d4b852ec7da7"
GATE7_PERF_FP = "62902104e0b62c9c558fdf9407eaf20f66f754c8f3f3472e65d9371ed83be066"
PRODUCT = "c483f1a189f762cd8af08b780f55f55412aafcf6e5e5a7b8cdae263bf9095c2f"
ALLOWED = {
    "HOLDOUT_PASS_WITH_LIMITATIONS",
    "PASS_WITH_LIMITATIONS",
    "MORE_HUMAN_EVIDENCE_REQUIRED",
    "CONSENT_INVALID",
    "HOLDOUT_FAIL",
}


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _param_hash(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _count_json(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(p for p in folder.glob("*.json") if p.is_file() and not p.name.startswith("_"))


def _valid_consent(doc: dict) -> bool:
    if doc.get("status") == "NOT_COLLECTED":
        return False
    need = [
        "participantId",
        "consentTimestampUtc",
        "photoUseConsent",
        "voiceUseConsent",
        "characterLikenessConsent",
        "siteScope",
        "purposes",
        "revocationUnderstood",
        "deletionUnderstood",
        "signatureOrEquivalent",
    ]
    if any(doc.get(k) in (None, "", [], False) and k not in ("photoUseConsent", "voiceUseConsent", "characterLikenessConsent") for k in need):
        # booleans must be explicitly true for use consents
        pass
    if not doc.get("photoUseConsent") or not doc.get("characterLikenessConsent"):
        return False
    if not doc.get("consentTimestampUtc"):
        return False
    if not doc.get("revocationUnderstood") or not doc.get("deletionUnderstood"):
        return False
    if not doc.get("signatureOrEquivalent"):
        return False
    if not doc.get("siteScope") or not doc.get("purposes"):
        return False
    return True


def main() -> int:
    for sub in ("consents", "self_eval", "acquaintance_eval", "stranger_eval", "revocation"):
        (EVIDENCE / sub).mkdir(parents=True, exist_ok=True)
        readme = EVIDENCE / sub / "_README.txt"
        if not readme.exists():
            readme.write_text(
                f"Place completed {sub} JSON evidence here. Do not invent scores. Redact biometrics per policy.\n",
                encoding="utf-8",
            )

    params_path = OUT / "V07_CCS_GATE8_PARAMETERS.json"
    params = json.loads(params_path.read_text(encoding="utf-8"))
    ph = _param_hash({k: v for k, v in params.items() if k != "parameterHash"})
    params["parameterHash"] = ph
    _write(params_path, params)

    consents = _count_json(EVIDENCE / "consents")
    self_evals = _count_json(EVIDENCE / "self_eval")
    acq = _count_json(EVIDENCE / "acquaintance_eval")
    strangers = _count_json(EVIDENCE / "stranger_eval")
    revocations = _count_json(EVIDENCE / "revocation")

    valid_consents = []
    invalid_consents = []
    for p in consents:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if _valid_consent(doc):
            valid_consents.append(p.name)
        else:
            invalid_consents.append(p.name)

    evidence = {
        "consentFiles": len(consents),
        "validConsentFiles": len(valid_consents),
        "invalidConsentFiles": len(invalid_consents),
        "selfEvalFiles": len(self_evals),
        "acquaintanceEvalFiles": len(acq),
        "strangerEvalFiles": len(strangers),
        "revocationFiles": len(revocations),
        "minParticipantsRequired": 3,
        "minAcquaintancePerParticipant": 3,
    }

    fails = []
    limitations = list(params.get("inheritedLimitations", []))
    # Hard policy: never invent
    limitations.append("TECHNICAL_PIPELINE_AUTO_PASS_DENY")
    limitations.append("HUMAN_HOLDOUT_EVIDENCE_REQUIRED")

    # Determine verdict without inventing scores
    if invalid_consents and not valid_consents and consents:
        verdict = "CONSENT_INVALID"
    elif (
        evidence["validConsentFiles"] >= 3
        and evidence["selfEvalFiles"] >= 3
        and evidence["acquaintanceEvalFiles"] >= 9
        and evidence["strangerEvalFiles"] >= 1
    ):
        # Evidence present — but aggregation/pass decision requires human adjudication package.
        # Without a sealed adjudication receipt, do not auto HOLDOUT_PASS.
        adj = OUT / "evidence" / "ADJUDICATION_RECEIPT.json"
        if adj.exists():
            adj_doc = json.loads(adj.read_text(encoding="utf-8"))
            v = adj_doc.get("verdict")
            if v in ALLOWED and v not in {"MORE_HUMAN_EVIDENCE_REQUIRED"}:
                # Still require hard-fail zeros if provided
                hard = adj_doc.get("hardFailCounts", {})
                if hard.get("unauthorizedFaceVoiceScriptUse", 0) > 0 or hard.get("consentRevocationFailure", 0) > 0:
                    verdict = "HOLDOUT_FAIL"
                    fails.append("HARD_FAIL_CONSENT_OR_UNAUTHORIZED_USE")
                else:
                    verdict = v
            else:
                verdict = "MORE_HUMAN_EVIDENCE_REQUIRED"
                limitations.append("ADJUDICATION_RECEIPT_INCOMPLETE")
        else:
            verdict = "MORE_HUMAN_EVIDENCE_REQUIRED"
            limitations.append("ADJUDICATION_RECEIPT_ABSENT")
    else:
        verdict = "MORE_HUMAN_EVIDENCE_REQUIRED"

    if verdict not in ALLOWED:
        verdict = "MORE_HUMAN_EVIDENCE_REQUIRED"

    missing = []
    if evidence["validConsentFiles"] < 3:
        missing.append("CONSENTED_PARTICIPANTS_LT_3")
    if evidence["selfEvalFiles"] < 3:
        missing.append("SELF_EVAL_LT_3")
    if evidence["acquaintanceEvalFiles"] < 9:
        missing.append("ACQUAINTANCE_EVAL_LT_9")
    if evidence["strangerEvalFiles"] < 1:
        missing.append("STRANGER_EVAL_ABSENT")
    if not (OUT / "evidence" / "ADJUDICATION_RECEIPT.json").exists():
        missing.append("ADJUDICATION_RECEIPT")

    receipt = {
        "schema": "NURION_V07_CCS_GATE8_EVIDENCE_SCAN_RECEIPT",
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "evidence": evidence,
        "validConsentFiles": valid_consents,
        "invalidConsentFiles": invalid_consents,
        "missingForHoldoutAttempt": missing,
        "autoInventScores": "DENY",
        "technicalPipelineAutoPass": "DENY",
    }
    _write(OUT / "V07_CCS_GATE8_EVIDENCE_SCAN_RECEIPT.json", receipt)

    status = {
        "schema": "NURION_V07_CCS_GATE8_STATUS",
        "track": "NURION Canonical Character System",
        "gate": 8,
        "name": "IDENTITY_RECOGNITION_PREFERENCE_ACCEPTANCE_HOLDOUT",
        "V07_CCS_GATE8": verdict,
        "parameterHash": ph,
        "gate7ParameterHash": GATE7_HASH,
        "gate7PerformanceFingerprintSha256": GATE7_PERF_FP,
        "protocolLocked": True,
        "technicalPipelineAutoPass": "DENY",
        "axes": params["axes"],
        "holdoutCompositionRequired": params["holdoutComposition"],
        "passCriteriaRecommended": params["passCriteriaRecommended"],
        "evidenceScan": evidence,
        "missingForHoldoutAttempt": missing,
        "fails": fails,
        "limitations": limitations,
        "inheritedLimitations": params.get("inheritedLimitations", []),
        "manualGt": "INDEPENDENT_PARALLEL_OFFICIAL_MANUAL_ANNOTATION_WAIT",
        "transparentVideoWebComponent": "SEPARATED_FOLLOW_ON_OUTPUT_TRACK",
        "productBaselineParameterHash": PRODUCT,
        "production": "NO-GO",
        "LOCKED": True,
        "lockMeaning": "PROTOCOL_AND_INTAKE_LOCKED_NOT_PRODUCT_ACCEPTANCE",
        "allowedVerdicts": sorted(ALLOWED),
        "artifacts": {
            "protocol": "V07_CCS_GATE8_HOLDOUT_PROTOCOL.md",
            "parameters": "V07_CCS_GATE8_PARAMETERS.json",
            "evidenceScan": "V07_CCS_GATE8_EVIDENCE_SCAN_RECEIPT.json",
            "templates": "templates/",
            "evidenceRoot": "evidence/",
        },
        "nextHumanWork": [
            "COLLECT_EXPLICIT_CONSENTS_MIN_3",
            "RUN_SELF_AND_ACQUAINTANCE_AND_STRANGER_EVALS",
            "BLIND_COMPARE_NATURAL_POLISHED_ASPIRATIONAL",
            "SEPARATE_CHARACTER_STYLE_EVAL",
            "VERIFY_REVOCATION_AND_DELETION",
            "FILE_ADJUDICATION_RECEIPT",
        ],
        "next": "AWAIT_HUMAN_HOLDOUT_EVIDENCE_OR_ADJUDICATION",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_CCS_GATE8_STATUS.json", status)

    freeze = {
        "schema": "NURION_V07_CCS_GATE8_OFFICIAL_FREEZE",
        "V07_CCS_GATE8": verdict,
        "LOCKED": True,
        "lockMeaning": "PROTOCOL_AND_INTAKE_LOCKED_NOT_PRODUCT_ACCEPTANCE",
        "parameterHash": ph,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "gate7ParameterHash": GATE7_HASH,
        "technicalPipelineAutoPass": "DENY",
        "autoInventScores": "DENY",
        "production": "NO-GO",
        "inheritedLimitations": params.get("inheritedLimitations", []),
        "lockedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_CCS_GATE8_OFFICIAL_FREEZE.json", freeze)

    print(
        json.dumps(
            {
                "verdict": verdict,
                "parameterHash": ph,
                "evidence": evidence,
                "missing": missing,
                "production": "NO-GO",
            },
            indent=2,
        )
    )
    # MORE_HUMAN_EVIDENCE_REQUIRED is an expected hold state (exit 0)
    return 0 if verdict in ALLOWED else 1


if __name__ == "__main__":
    raise SystemExit(main())
