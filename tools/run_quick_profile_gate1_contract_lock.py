"""NURION Quick Profile Single Image Pipeline Gate 1 — contract lock.

Locks input, output, and ABSTAIN contracts (plus photo quality, face priority,
body scope, exaggeration bans). Does NOT generate characters.
Does NOT count outputs as participant evidence.
Does NOT mutate CCS Gate 8 baseline.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.7" / "product" / "quick_profile" / "gate1"
GATE8_HASH = "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697"
PRODUCT = "c483f1a189f762cd8af08b780f55f55412aafcf6e5e5a7b8cdae263bf9095c2f"
COMMAND = "NURION Quick Profile Single Image Pipeline Gate 1 GO"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _param_hash(params: dict) -> str:
    raw = json.dumps(
        {k: v for k, v in params.items() if k != "parameterHash"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _checks(params: dict) -> list[dict]:
    checks = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    ic = params["inputContract"]
    add("INPUT_REQUIRED_THREE_FIELDS", ic["required"] == [
        "SINGLE_CLEAR_FACE_IMAGE",
        "HEIGHT_CM",
        "WEIGHT_KG",
    ])
    add("FULL_BODY_NOT_REQUIRED_AT_ENTRY", "FULL_BODY_PHOTO" in ic["forbiddenAsRequiredAtEntry"])
    add("HEIGHT_RANGE_LOCKED", ic["heightCmMin"] == 120.0 and ic["heightCmMax"] == 230.0)
    add("WEIGHT_RANGE_LOCKED", ic["weightKgMin"] == 30.0 and ic["weightKgMax"] == 250.0)

    pq = params["photoQualityCriteria"]
    add("POSE_FRONTAL_OR_WEAK_45", pq["acceptedPose"] == ["FRONTAL", "WEAK_45_DEGREE_FACE"])
    add("BACK_VIEW_DENY", pq["backView"] == "DENY")

    face = params["faceIdentityPriority"]
    add("FACE_FIRST_PRIORITY", face["precisionAndDevCapacity"] == "FACE_FIRST")
    add("SKELETON_SWAP_LOOK_DENY", face["facialSkeletonChangeToOtherPersonLook"] == "DENY")

    body = params["bodyRecommendationScope"]
    add(
        "INITIAL_PRESETS_SLIM_BALANCED_SOFT",
        body["initialPresetsAllowed"] == ["SLIM", "BALANCED", "SOFT"],
    )
    add("FULL_BODY_RECONSTRUCTION_NOT_CLAIMED", "FULL_REAL_BODY_RECONSTRUCTION" in body["doNotClaimAccurate"])
    add("UNOBSERVED_BACK_STANDARD", body["unobservedBack"] == "CANONICAL_STANDARD_COMPLETION")

    add("DEFAULT_POLISHED", params["beautificationDefault"]["mode"] == "POLISHED")
    add("ASPIRATIONAL_WITHOUT_CHOICE_DENY", params["beautificationDefault"]["aspirationalWithoutExplicitChoice"] == "DENY")

    disc = params["disclosureLabels"]
    add("FACE_AUTH_OUT_OF_SCOPE", disc["faceAuthentication"] == "OUT_OF_SCOPE")
    add("RESULT_GRADE_QUICK_PREVIEW", disc["resultGrade"] == "QUICK_PROFILE_PREVIEW")

    oc = params["outputContract"]
    add("OUTPUT_CONTRACT_PRESENT", isinstance(oc.get("mustProduceWhenEligible"), list) and len(oc["mustProduceWhenEligible"]) >= 6)
    add("OUTPUT_NOT_PARTICIPANT_EVIDENCE", oc.get("countsAsGate8ParticipantEvidence") == "DENY")
    add("OUTPUT_BLOCKS_VOICE_LIPSYNC", "VOICE" in oc.get("mustNotProduceAtQuickEntry", []) and "LIPSYNC" in oc["mustNotProduceAtQuickEntry"])
    add("INTERNAL_DRY_RUN_FLAG", oc.get("internalDryRunOnlyUntilHumanCollection") is True)

    ex = params["exaggerationBan"]
    add("EXAGGERATION_BAN_LOCKED", all(v == "DENY" for v in ex.values()))

    add("ABSTAIN_SET_NONEMPTY", len(params["abstainConditions"]) >= 8)
    add("NO_CHARACTER_GEN_IN_GATE1", params["characterGenerationInThisGate"] == "DENY")
    add("PARTICIPANT_EVIDENCE_COUNTING_DENY", params.get("participantEvidenceCounting") == "DENY")
    add("ARKAON_GEN_INTERVENTION_DENY", params["arkaonCharacterGenerationIntervention"] == "DENY")
    add("ARKAON_RIG_WEIGHT_INTERVENTION_DENY", params.get("arkaonGenerationRigWeightIntervention") == "DENY")
    add("GATE8_BASELINE_MUTATION_DENY", params["gate8BaselineMutation"] == "DENY")
    add("GATE8_HASH_PINNED", params["gate8ParameterHash"] == GATE8_HASH)
    add("GATE8_STATE_PINNED", params.get("gate8OfficialStatePinned") == "AWAITING_PHASE1_HUMAN_EVIDENCE_COLLECTION")
    add("TALKING_PROFILE_MIX_DENY", params.get("talkingProfileMix") == "DENY")
    add("VOICE_LIPSYNC_DENY", params["voiceLipsyncInQuickGate1"] == "DENY")
    add("PRODUCTION_NO_GO", params["production"] == "NO-GO")

    return checks


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    params_path = OUT / "V07_QP_GATE1_PARAMETERS.json"
    params = json.loads(params_path.read_text(encoding="utf-8"))
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(params_path, params)

    checks = _checks(params)
    failed = [c for c in checks if c["result"] != "PASS"]
    verdict = "PASS" if not failed else "FAIL"
    now = datetime.now(timezone.utc).isoformat()

    status = {
        "schema": "NURION_V07_QP_GATE1_STATUS",
        "track": "NURION Quick Profile Single Image Pipeline",
        "gate": 1,
        "command": COMMAND,
        "V07_QP_GATE1": verdict,
        "lockMeaning": "INPUT_OUTPUT_ABSTAIN_CONTRACT_LOCKED_NOT_PIPELINE_IMPLEMENTATION",
        "parameterHash": ph,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "characterGeneration": "DENY",
        "participantEvidenceCounting": "DENY",
        "pipelineImplementation": "NOT_STARTED",
        "internalDryRun": "REQUIRED_NEXT",
        "checksTotal": len(checks),
        "checksPassed": len(checks) - len(failed),
        "checksFailed": len(failed),
        "failedChecks": [c["check"] for c in failed],
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "gate8OfficialState": "AWAITING_PHASE1_HUMAN_EVIDENCE_COLLECTION",
        "gate8Verdict": "MORE_HUMAN_EVIDENCE_REQUIRED",
        "talkingProfileMix": "DENY",
        "arkaonCharacterGenerationIntervention": "DENY",
        "arkaonGenerationRigWeightIntervention": "DENY",
        "arkaonPostQuickPresetBinding": "ALLOWED_AFTER_QUICK_COMPLETE",
        "productBaselineParameterHash": PRODUCT,
        "production": "NO-GO",
        "next": "AWAIT_QUICK_PROFILE_GATE2_IMPLEMENTATION_AND_INTERNAL_DRY_RUN_GO",
        "updatedAt": now,
    }
    _write(OUT / "V07_QP_GATE1_STATUS.json", status)

    freeze = {
        "schema": "NURION_V07_QP_GATE1_OFFICIAL_FREEZE",
        "V07_QP_GATE1": verdict,
        "LOCKED": verdict == "PASS",
        "lockMeaning": "INPUT_OUTPUT_ABSTAIN_CONTRACT_LOCKED_NOT_PIPELINE_IMPLEMENTATION",
        "parameterHash": ph,
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "characterGeneration": "DENY",
        "participantEvidenceCounting": "DENY",
        "talkingProfileMix": "DENY",
        "arkaonGenerationRigWeightIntervention": "DENY",
        "production": "NO-GO",
        "lockedAt": now,
    }
    _write(OUT / "V07_QP_GATE1_OFFICIAL_FREEZE.json", freeze)

    receipt = {
        "schema": "NURION_V07_QP_GATE1_CONTRACT_LOCK_RECEIPT",
        "command": COMMAND,
        "V07_QP_GATE1": verdict,
        "parameterHash": ph,
        "checks": checks,
        "lockedAxes": [
            "INPUT_CONTRACT",
            "OUTPUT_CONTRACT",
            "ABSTAIN_CONDITIONS",
            "PHOTO_QUALITY_CRITERIA",
            "FACE_IDENTITY_PRIORITY",
            "HEIGHT_WEIGHT_BODY_RECOMMENDATION_SCOPE",
            "DEFAULT_POLISHED",
            "DISCLOSURE_LABELS",
            "EXAGGERATION_BAN",
            "ARKAON_NON_INTERVENTION_IN_GENERATION_RIG_WEIGHT",
            "PARTICIPANT_EVIDENCE_COUNTING_DENY",
        ],
        "gate8BaselineUnaffected": True,
        "participantEvidenceCounting": "DENY",
        "implementationAndInternalDryRunNext": True,
        "production": "NO-GO",
        "completedAt": now,
        "next": "AWAIT_QUICK_PROFILE_GATE2_IMPLEMENTATION_AND_INTERNAL_DRY_RUN_GO",
    }
    _write(OUT / "V07_QP_GATE1_CONTRACT_LOCK_RECEIPT.json", receipt)

    track = {
        "schema": "NURION_V07_QUICK_PROFILE_PIPELINE_STATUS",
        "track": "NURION Quick Profile Single Image Pipeline",
        "gate1": verdict,
        "gate1ParameterHash": ph,
        "gate1Lock": "INPUT_OUTPUT_ABSTAIN_CONTRACT_LOCKED",
        "pipelineImplementation": "NOT_STARTED",
        "internalDryRun": "REQUIRED_BEFORE_HUMAN_EVIDENCE",
        "participantEvidenceCounting": "DENY",
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "gate8OfficialState": "AWAITING_PHASE1_HUMAN_EVIDENCE_COLLECTION",
        "production": "NO-GO",
        "nextCommand": "NURION Quick Profile Single Image Pipeline Gate 2 GO",
        "updatedAt": now,
    }
    _write(OUT.parent / "V07_QUICK_PROFILE_PIPELINE_STATUS.json", track)

    print(json.dumps({"V07_QP_GATE1": verdict, "parameterHash": ph, "failed": len(failed)}, ensure_ascii=False))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
