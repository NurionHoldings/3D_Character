"""ARKAON Experience-Guided Improvement Loop Gate 1 GO.

Contract + de-identified memory schema only. No production learning.
Must not block Gate 6 face-quality work.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
OUT = ROOT / "dist/v0.7/product/arkaon_experience_loop/gate1"
CONTRACT = OUT / "V07_ARKAON_EXPERIENCE_LOOP_GATE1_CONTRACT.json"
HOLD = ROOT / "dist/v0.7/product/V07_ARKAON_EXPERIENCE_GUIDED_IMPROVEMENT_LOOP_DESIGN_HOLD.json"
COMMAND = "ARKAON Experience-Guided Improvement Loop Gate 1 GO"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_obj(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    parameter_hash = sha256_obj(contract)

    memory_schema = {
        "schema": "NURION_V07_ARKAON_EXPERIENCE_MEMORY_EVENT_V1",
        "version": 1,
        "fields": {
            "eventId": "string",
            "recordedAtUtc": "iso8601",
            "anonymousSessionOrParticipantId": "string",
            "consentScope": ["ONE_TIME_CHARACTER_GENERATION", "INTERNAL_QUALITY_REVIEW", "MODEL_IMPROVEMENT_LEARNING"],
            "eventType": contract["experienceMemoryRecord"]["eventTypes"],
            "structuredCodes": "string[]",
            "environmentTags": "string[]",
            "retentionClass": ["EPHEMERAL", "REVIEW_ONLY", "LEARNING_APPROVED"],
            "originalFaceImageStored": "DENY_BY_DEFAULT",
        },
        "example": {
            "eventId": "ex_demo_not_training",
            "recordedAtUtc": now,
            "anonymousSessionOrParticipantId": "PILOT_ONLY",
            "consentScope": "INTERNAL_QUALITY_REVIEW",
            "eventType": "ABSTAIN_OUTCOME",
            "structuredCodes": ["IDENTITY_DETAIL_INSUFFICIENT", "BACKLIGHT_FALSE_ABSTAIN"],
            "environmentTags": ["SINGLE_IMAGE", "FRONTAL"],
            "retentionClass": "REVIEW_ONLY",
            "originalFaceImageStored": False,
            "note": "Example only — not participant training data",
        },
    }
    write_json(OUT / "V07_ARKAON_EXPERIENCE_MEMORY_EVENT_SCHEMA.json", memory_schema)

    consent_pack = {
        "schema": "NURION_V07_ARKAON_CONSENT_SEPARATION_PACK_V1",
        "scopes": contract["consentSeparation"]["scopes"],
        "serviceConsentImpliesLearningConsent": "DENY",
        "learningConsentRequiredFields": contract["consentSeparation"]["requiredLearningFields"],
        "withdrawalAndDeletion": "REQUIRED",
        "production": "NO-GO",
    }
    write_json(OUT / "V07_ARKAON_CONSENT_SEPARATION_PACK.json", consent_pack)

    proposal_ceiling = {
        "schema": "NURION_V07_ARKAON_CANDIDATE_PROPOSAL_CEILING_V1",
        "mayPropose": True,
        "mayAutoApply": False,
        "mayPromoteBaseline": False,
        "mayTrainOnFacesWithoutLearningConsent": False,
        "destination": "ISOLATED_CANDIDATE_SPACE_ONLY",
    }
    write_json(OUT / "V07_ARKAON_CANDIDATE_PROPOSAL_CEILING.json", proposal_ceiling)

    receipt = {
        "schema": "NURION_V07_ARKAON_EXPERIENCE_LOOP_GATE1_RECEIPT_V1",
        "command": COMMAND,
        "completedAt": now,
        "verdict": "GATE1_CONTRACT_PASS",
        "parameterHash": parameter_hash,
        "implementationScope": [
            "FAILURE_PREFERENCE_RECORD_SPEC",
            "CONSENT_SEPARATION_PACK",
            "CANDIDATE_PROPOSAL_CEILING",
        ],
        "learningStarted": "DENY",
        "modelMutation": "DENY",
        "productionAutoLearning": "DENY",
        "blocksGate6": "DENY",
        "p001P003AsTrainingData": "DENY",
        "production": "NO-GO",
        "next": "AWAIT_GATE2_CANDIDATE_LEARNING_GO_AFTER_FACE_QUALITY_TRACK_ALLOWS",
    }
    write_json(OUT / "V07_ARKAON_EXPERIENCE_LOOP_GATE1_RECEIPT.json", receipt)

    status = {
        "schema": "NURION_V07_ARKAON_EXPERIENCE_LOOP_GATE1_STATUS_V1",
        "V07_ARKAON_EXPERIENCE_LOOP_GATE1": "PASS",
        "LOCKED": True,
        "parameterHash": parameter_hash,
        "authorityCeiling": "PROPOSE_IMPROVEMENT_CANDIDATES",
        "productionAutoLearning": "DENY",
        "updatedAt": now,
        "production": "NO-GO",
        "next": receipt["next"],
    }
    write_json(OUT / "V07_ARKAON_EXPERIENCE_LOOP_GATE1_STATUS.json", status)

    if HOLD.is_file():
        hold = json.loads(HOLD.read_text(encoding="utf-8"))
        hold["status"] = "GATE1_PASS_LOCKED_DESIGN_HOLD_SUPERSEDED_FOR_GATE1_ONLY"
        hold["implementation"] = "GATE1_CONTRACT_ONLY"
        hold["learningOrModelMutation"] = "NOT_STARTED"
        hold["updatedAt"] = now
        hold["gate1"] = {
            "status": "PASS_LOCKED",
            "parameterHash": parameter_hash,
            "receipt": "arkaon_experience_loop/gate1/V07_ARKAON_EXPERIENCE_LOOP_GATE1_RECEIPT.json",
        }
        write_json(HOLD, hold)

    print(json.dumps({"verdict": "GATE1_CONTRACT_PASS", "parameterHash": parameter_hash, "productionAutoLearning": "DENY"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
