"""P002 False-Abstain Reanalysis After Adjudication GO.

Uses the same Gate 4 GeometryFirstAnalyzer + pinned MediaPipe backend.
Does NOT mutate Gate 4 contract/thresholds, prior execute receipt, or Identity Core.
Blur precheck is waived only by adjudication receipt exception for this pin.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nurion_qp_geometry_face_v2.analyzer import GeometryFirstAnalyzer
from nurion_qp_geometry_face_v2.gate4_contract import GATE4_CONTRACT, gate4_parameter_hash
from nurion_qp_geometry_face_v2.integration_adapter import (
    _geometry_identity_preview,
    _geometry_payload,
    _size_blur_precheck,
    compare_legacy_heuristic,
    load_gate2_params,
)
from nurion_qp_geometry_face_v2.mediapipe_backend import EXP_DET, EXP_LM, MediaPipeLandmarkerBackend, sha256_file
from nurion_quick_profile_core import DISCLOSURE, USER_DISCLOSURE_KO, recommend_body, sha256_obj

COMMAND = "NURION Quick Profile Geometry-First Face Analyzer v2 P002 False-Abstain Reanalysis After Adjudication GO"
PID = "P002"
EXP_G4 = "92ebd6e7dd9b5d79cfdee17cf9cac37d4dfd3cdf3860a973b7ba91f829af88c4"
EXP_PIN = "b0f6e6a21b0cefd7fc6f088f54eabe16df986bc40c6b2a74479ed0f9e6dee6c7"
ADJ_VERDICT = "FALSE_ABSTAIN_LARGE_IMAGE_EDGE_VARIANCE_WITH_BACKLIGHT_SOFTNESS"
CORE_SHA = "636372fc0886870d536c093c2ba8dcc001ec87f3c6cb9922518eaeffdf473816"
RUNNER_SHA = "13837c5e5b4a31e9efb10c83528703375df44f59ac15babb69207a57e22dbcc4"
ANALYZER_SHA = "ce2f57cf077031748513d9b5b50d8478cacf814a936c7bf59863054bdcb79680"
GATE8_HASH = "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697"

G4 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4"
ADJ = G4 / "adjudication" / "P002"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"
PRIOR_EXEC = (
    G4
    / "execution"
    / "V07_QP_GF_FACE_V2_P001_P003_CONSENTED_DRAFT_REVIEW_EXECUTE_RECEIPT.json"
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def map_judgment(adapter_like_verdict: str) -> str:
    if adapter_like_verdict == "GEOMETRY_FIRST_DRAFT_READY":
        return "DRAFT_READY"
    if adapter_like_verdict == "GEOMETRY_REVIEW_REQUIRED":
        return "REVIEW_REQUIRED"
    return "ABSTAIN_RECAPTURE"


def human_review_template(judgment: str) -> dict:
    return {
        "schema": "NURION_V07_QP_GF_FACE_V2_HUMAN_DRAFT_REVIEW_TEMPLATE_V1",
        "anonymousParticipantId": PID,
        "geometryFirstJudgment": judgment,
        "source": "P002_FALSE_ABSTAIN_REANALYSIS_AFTER_ADJUDICATION",
        "selfEvaluation": {
            "completed": False,
            "faceShapeAndMajorProportions": None,
            "eyeBrowNoseMouthJawSignature": None,
            "naturalAsymmetryPreserved": None,
            "comment": None,
        },
        "internalVisualReview": {
            "completed": False,
            "identityLoss": None,
            "geometryPlausibility": None,
            "captureLimitationImpact": None,
            "backlightSoftnessNoted": True,
            "comment": None,
        },
        "automaticSimilarityPass": "DENY",
        "automaticHumanLikenessPass": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "production": "NO-GO",
        "characterGeneration": "DENY",
        "blenderDraftAssembly": "DENY",
    }


def abort(reason: str, details: dict | None = None) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema": "NURION_V07_QP_GF_FACE_V2_P002_FALSE_ABSTAIN_REANALYSIS_SAFE_ABORT_V1",
        "command": COMMAND,
        "verdict": "SAFE_ABORT",
        "reason": reason,
        "details": details or {},
        "gate4Mutation": "DENY",
        "priorExecuteMutation": "DENY",
        "production": "NO-GO",
        "registeredAt": now,
    }
    write_json(ADJ / "V07_QP_GF_FACE_V2_P002_FALSE_ABSTAIN_REANALYSIS_SAFE_ABORT.json", doc)
    print(json.dumps(doc, indent=2, ensure_ascii=False))
    return 2


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # --- baseline / adjudication gates ---
    if gate4_parameter_hash() != EXP_G4:
        return abort("GATE4_HASH_MISMATCH", {"got": gate4_parameter_hash()})
    if GATE4_CONTRACT["baseline"]["production"] != "NO-GO":
        return abort("GATE4_PRODUCTION_NOT_NO_GO")
    if sha256_file(ROOT / "tools/nurion_quick_profile_core.py") != CORE_SHA:
        return abort("QP_CORE_MUTATION")
    if sha256_file(ROOT / "tools/run_quick_profile_gate3_consented_human_review.py") != RUNNER_SHA:
        return abort("QP_GATE3_RUNNER_MUTATION")
    if sha256_file(ROOT / "nurion_qp_geometry_face_v2/analyzer.py") != ANALYZER_SHA:
        return abort("ANALYZER_MUTATION")
    g8 = read_json(ROOT / "dist/v0.7/canonical/gate8/V07_CCS_GATE8_OFFICIAL_FREEZE.json")
    if g8.get("parameterHash") != GATE8_HASH:
        return abort("GATE8_MUTATION")
    if sha256_file(MODELS / "blaze_face_short_range_float16_v1.tflite") != EXP_DET:
        return abort("DETECTOR_SHA_MISMATCH")
    if sha256_file(MODELS / "face_landmarker_float16_v1.task") != EXP_LM:
        return abort("LANDMARKER_SHA_MISMATCH")

    adj_receipt_path = ADJ / "V07_QP_GF_FACE_V2_P002_CAPTURE_QUALITY_HUMAN_ADJUDICATION_RECEIPT.json"
    if not adj_receipt_path.is_file():
        return abort("ADJUDICATION_RECEIPT_MISSING")
    adj = read_json(adj_receipt_path)
    if adj.get("participantId") != PID:
        return abort("ADJUDICATION_PARTICIPANT_MISMATCH")
    if adj.get("pinnedSha256") != EXP_PIN:
        return abort("ADJUDICATION_PIN_MISMATCH")
    if adj.get("verdict") != ADJ_VERDICT:
        return abort("ADJUDICATION_VERDICT_MISMATCH", {"got": adj.get("verdict")})
    if adj.get("gate4Mutation") != "DENY":
        return abort("ADJUDICATION_IMPLIES_GATE4_MUTATION")
    if adj.get("reanalysisRequiresSeparateApproval") != "REQUIRED":
        return abort("ADJUDICATION_NOT_MARKED_FOR_SEPARATE_REANALYSIS")

    prior = read_json(PRIOR_EXEC)
    prior_sha_before = sha256_file(PRIOR_EXEC)
    prior_p002 = prior.get("participantJudgments", {}).get(PID)
    if prior_p002 != "ABSTAIN_RECAPTURE":
        return abort("PRIOR_EXECUTE_P002_NOT_ABSTAIN", {"got": prior_p002})

    face = INTAKE / "packages" / PID / "face.png"
    inp = read_json(INTAKE / "packages" / PID / "participant_input.json")
    pinned = read_json(INTAKE / "V07_QP_GATE3_PINNED_SHA256_RECORD.json")
    got = sha256_file(face)
    if got != EXP_PIN or pinned.get("pinnedSha256", {}).get(PID) != EXP_PIN:
        return abort("PINNED_IMAGE_HASH_MISMATCH", {"got": got})
    if inp.get("originalImageSha256") != EXP_PIN:
        return abort("INPUT_SHA_MISMATCH")

    params = load_gate2_params(ROOT)
    would_precheck = _size_blur_precheck(face)
    legacy = compare_legacy_heuristic(face, inp.get("declaredPose", "FRONTAL"), params)
    body = recommend_body(float(inp["heightCm"]), float(inp["weightKg"]), params)
    if body.get("verdict") == "ABSTAIN":
        return abort("BODY_ABSTAIN", {"reasons": body.get("reasons")})

    # Same analyzer as Gate 4 adapter post-precheck path — no threshold edits.
    backend = MediaPipeLandmarkerBackend(MODELS / "face_landmarker_float16_v1.task")
    analyzer = GeometryFirstAnalyzer(backend)
    rgb = np.asarray(Image.open(face).convert("RGB"), dtype=np.uint8)
    geometry_result = analyzer.analyze(rgb)

    if geometry_result.outcome == "ABSTAIN_RECAPTURE":
        adapter_verdict = "ABSTAIN"
        identity = None
        abstain_reasons = ["GEOMETRY_ABSTAIN_RECAPTURE"]
        if "BRANCH_CONFLICT" in geometry_result.disclosures:
            abstain_reasons.append("BRANCH_CONFLICT")
        if "NO_VALID_DENSE_GEOMETRY" in geometry_result.disclosures:
            abstain_reasons.append("NO_VALID_DENSE_GEOMETRY")
    elif geometry_result.outcome == "GEOMETRY_REVIEW_REQUIRED":
        adapter_verdict = "GEOMETRY_REVIEW_REQUIRED"
        identity = None
        abstain_reasons = []
    else:
        adapter_verdict = "GEOMETRY_FIRST_DRAFT_READY"
        identity = _geometry_identity_preview(geometry_result.geometry, got)
        abstain_reasons = []

    judgment = map_judgment(adapter_verdict)
    out_dir = G4 / "execution" / f"p002_reanalysis_{run_id}"
    adapter_like: dict[str, Any] = {
        "caseId": PID,
        "adapter": "GEOMETRY_FIRST_V2_ISOLATED",
        "reanalysisMode": "FALSE_ABSTAIN_AFTER_ADJUDICATION",
        "blurPrecheckThresholdMutation": "DENY",
        "blurPrecheckWaivedByAdjudicationReceiptOnly": True,
        "blurPrecheckWouldHaveFired": would_precheck,
        "verdict": adapter_verdict,
        "abstainReasons": abstain_reasons,
        "heuristicExistenceGate": "BYPASSED",
        "legacyHeuristicComparison": legacy,
        "geometryAnalysis": _geometry_payload(geometry_result),
        "identityLayer": identity,
        "identityCoreReplacement": "DENY",
        "bodyRecommendation": {
            "verdict": body["verdict"],
            "bmi": body.get("bmi"),
            "recommendedPreset": body.get("recommendedPreset"),
            "bodyMorphValues": body.get("bodyMorphValues"),
            "label": body.get("label"),
        },
        "characterGeneration": "DENY",
        "partialResultGeneration": "DENY",
        "disclosure": {
            **DISCLOSURE,
            "faceAnalyzer": "GEOMETRY_FIRST_V2_ISOLATED_ADAPTER_REANALYSIS",
            "legacyIdentityCore": "NOT_REPLACED",
            "adjudicationReceipt": str(adj_receipt_path.name),
        },
        "userFacingDisclosureKo": USER_DISCLOSURE_KO,
        "countsAsGate8ParticipantEvidence": "DENY",
        "participantEvidenceCounting": "DENY",
        "production": "NO-GO",
        "imageSha256": got,
        "backend": backend.name,
    }
    adapter_like["adapterFingerprintSha256"] = sha256_obj(
        {k: v for k, v in adapter_like.items() if k != "adapterFingerprintSha256"}
    )
    write_json(out_dir / "V07_QP_GF_FACE_V2_P002_REANALYSIS_ADAPTER_RESULT.json", adapter_like)

    judgment_doc = {
        "participantId": PID,
        "judgment": judgment,
        "priorExecuteJudgmentUnchanged": "ABSTAIN_RECAPTURE",
        "reanalysisJudgment": judgment,
        "adapterVerdict": adapter_verdict,
        "abstainReasons": abstain_reasons,
        "imageSha256": got,
        "geometryOutcome": geometry_result.outcome,
        "successfulBranches": list(geometry_result.successful_branches),
        "medianBranchDisagreement": geometry_result.median_branch_disagreement,
        "p95BranchDisagreement": geometry_result.p95_branch_disagreement,
        "captureLimitations": ["BACKLIGHT", "SOFT_CONTRAST", "SQUINT", "ELIGIBLE_WITH_CAPTURE_LIMITATIONS"],
        "automaticSimilarityPass": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "characterGeneration": "DENY",
        "blenderDraftAssembly": "DENY",
        "production": "NO-GO",
        "humanReview": "AWAITING_HUMAN_REVIEW" if judgment in ("DRAFT_READY", "REVIEW_REQUIRED") else "NOT_STARTED_ABSTAIN",
    }
    write_json(out_dir / "V07_QP_GF_FACE_V2_P002_REANALYSIS_JUDGMENT.json", judgment_doc)

    if judgment in ("DRAFT_READY", "REVIEW_REQUIRED"):
        write_json(out_dir / "V07_QP_GF_FACE_V2_HUMAN_REVIEW.json", human_review_template(judgment))
        if identity is not None:
            write_json(
                out_dir / "V07_QP_GF_FACE_V2_INTERNAL_DRAFT_RECIPE.json",
                {
                    "schema": "NURION_V07_QP_GF_FACE_V2_INTERNAL_DRAFT_RECIPE_V1",
                    "participantId": PID,
                    "distribution": "DENY",
                    "characterGeneration": "DENY",
                    "blenderDraftAssembly": "DENY",
                    "identityLayer": identity,
                    "bodyRecommendation": adapter_like["bodyRecommendation"],
                    "geometryOutcome": geometry_result.outcome,
                    "note": "INTERNAL_GEOMETRY_PREVIEW_ONLY_NOT_PRODUCT_DRAFT",
                    "source": "P002_FALSE_ABSTAIN_REANALYSIS",
                },
            )

    # Prove prior execute receipt bytes unchanged during this GO.
    prior_sha_after = sha256_file(PRIOR_EXEC)
    if prior_sha_after != prior_sha_before:
        return abort("PRIOR_EXECUTE_RECEIPT_MUTATED")

    receipt = {
        "schema": "NURION_V07_QP_GF_FACE_V2_P002_FALSE_ABSTAIN_REANALYSIS_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "participantId": PID,
        "pinnedSha256": EXP_PIN,
        "adjudicationReceipt": {
            "path": "adjudication/P002/V07_QP_GF_FACE_V2_P002_CAPTURE_QUALITY_HUMAN_ADJUDICATION_RECEIPT.json",
            "verdict": ADJ_VERDICT,
            "registeredAt": adj.get("registeredAt"),
        },
        "gate4ParameterHash": EXP_G4,
        "gate4Mutation": "DENY",
        "thresholdMutation": "DENY",
        "perParticipantTuning": "DENY",
        "blurPrecheckWaivedByAdjudicationReceiptOnly": True,
        "blurPrecheckWouldHaveFired": would_precheck,
        "analyzer": "GeometryFirstAnalyzer",
        "analyzerSha256": ANALYZER_SHA,
        "backend": backend.name,
        "landmarkerSha256": EXP_LM,
        "priorExecuteReceipt": {
            "path": "execution/V07_QP_GF_FACE_V2_P001_P003_CONSENTED_DRAFT_REVIEW_EXECUTE_RECEIPT.json",
            "sha256Unchanged": prior_sha_after,
            "P002JudgmentUnchanged": "ABSTAIN_RECAPTURE",
        },
        "reanalysisJudgment": judgment,
        "geometryOutcome": geometry_result.outcome,
        "successfulBranches": list(geometry_result.successful_branches),
        "legacyHeuristicReasons": legacy.get("reasons"),
        "automaticSimilarityPass": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "characterGeneration": "DENY",
        "blenderDraftAssembly": "DENY",
        "production": "NO-GO",
        "outputDir": f"execution/p002_reanalysis_{run_id}",
        "bundleHumanReview": "NOW_ELIGIBLE_TO_UNHOLD_WITH_P001_P003",
    }
    receipt["executionFingerprintSha256"] = sha256_obj(
        {k: v for k, v in receipt.items() if k not in ("completedAt", "executionFingerprintSha256")}
    )
    write_json(out_dir / "V07_QP_GF_FACE_V2_P002_FALSE_ABSTAIN_REANALYSIS_RECEIPT.json", receipt)
    write_json(G4 / "V07_QP_GF_FACE_V2_P002_FALSE_ABSTAIN_REANALYSIS_RECEIPT.json", receipt)
    write_json(ADJ / "V07_QP_GF_FACE_V2_P002_FALSE_ABSTAIN_REANALYSIS_RECEIPT.json", receipt)

    # Status updates only — do not rewrite prior execute receipt.
    g4s = read_json(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json")
    g4s["updatedAt"] = now
    g4s["P002FalseAbstainReanalysis"] = {
        "runId": run_id,
        "judgment": judgment,
        "priorExecuteJudgmentUnchanged": "ABSTAIN_RECAPTURE",
        "gate4Mutation": "DENY",
        "thresholdMutation": "DENY",
    }
    g4s["next"] = "UNHOLD_P001_P002_P003_BUNDLED_HUMAN_DRAFT_REVIEW"
    write_json(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json", g4s)

    qp3_path = ROOT / "dist/v0.7/product/quick_profile/gate3/V07_QP_GATE3_STATUS.json"
    qp3 = read_json(qp3_path)
    qp3["updatedAt"] = now
    qp3["P002FalseAbstainReanalysis"] = {
        "verdict": judgment,
        "priorExecuteJudgmentUnchanged": "ABSTAIN_RECAPTURE",
        "gate4Mutation": "DENY",
        "thresholdMutation": "DENY",
        "production": "NO-GO",
        "receipt": "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4/V07_QP_GF_FACE_V2_P002_FALSE_ABSTAIN_REANALYSIS_RECEIPT.json",
    }
    qp3["parallelTracks"] = {
        "P001P003HumanDraftReview": "READY_TO_UNHOLD_WITH_P002_REANALYSIS",
        "P002Path": f"REANALYSIS_{judgment}",
        "geometryFirstFaceV2": "GATE4_PASS_LOCKED_UNCHANGED",
        "threeParticipantReviewBundle": "ELIGIBLE_AFTER_OPERATOR_UNHOLD",
    }
    write_json(qp3_path, qp3)

    print(
        json.dumps(
            {
                "verdict": "REANALYSIS_COMPLETE",
                "judgment": judgment,
                "geometryOutcome": geometry_result.outcome,
                "priorExecuteP002Unchanged": "ABSTAIN_RECAPTURE",
                "gate4Mutation": "DENY",
                "thresholdMutation": "DENY",
                "runId": run_id,
                "production": "NO-GO",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
