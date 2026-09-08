"""Lock dense capture identity-review demotion per operator adjudication."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
G5 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate5"
G4 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4"
QP3 = ROOT / "dist/v0.7/product/quick_profile/gate3/V07_QP_GATE3_STATUS.json"
BUNDLE = G5 / "human_review/dense_blinded_bundle_20260816T075023Z"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
VERDICT = "TECHNICAL_SHAPE_QA_ONLY_IDENTITY_REVIEW_DENY"
UNEVAL = "NOT_EVALUABLE_IDENTITY_DETAIL_ABSENT"

JUDGEABLE = [
    "A_B_FACE_WIDTH_LENGTH_DIFFERENCE",
    "OUTLINE_ROUNDNESS_AND_SMOOTHING_DIFFERENCE",
    "LEFT_RIGHT_SYMMETRY_DEGREE",
    "MESH_COLLAPSE_AT_45DEG",
    "DISTORTION_AROUND_EYE_HOLES_MOUTH_NOSE",
    "FRONT_SIDE_SHAPE_CONSISTENCY",
]
NOT_JUDGEABLE = [
    "RECOGNIZE_PARTICIPANT_IDENTITY",
    "EYE_NOSE_MOUTH_IDENTITY_SIGNATURE_PRESERVED",
    "WHICH_OF_NATURAL_POLISHED_MORE_SELF_LIKE",
    "SKIN_IMPRESSION_AGE_EXPRESSION_SIMILARITY",
    "HOMEPAGE_PROFILE_QUALITY",
]
SCREEN_DEFECTS = [
    "STILL_WHITE_LOW_RES_SURFACE_MESH_DESPITE_478",
    "EYES_ARE_BLACK_HOLES_NOT_GLOBE_OR_LIDS",
    "LIP_BORDER_AND_VOLUME_NEARLY_ABSENT",
    "NOSE_JAW_CHEEK_SIDE_SHAPE_EXAGGERATED_OR_FLATTENED",
    "45DEG_SHOWS_MESH_DISTORTION_BEFORE_FEATURES",
    "NO_TEXTURE_SKIN_BROW_HAIR_NO_HUMAN_IMPRESSION",
    "854_TRIANGLES_IS_POINT_COUNT_NOT_IDENTITY_EXPRESSIVITY",
]
NEXT_IMPROVEMENTS = [
    "LEAVE_DIRECT_478_POINT_TRIANGULATION",
    "FIT_LANDMARKS_TO_FACE_CANONICAL_MESH_OR_3DMM",
    "BUILD_SEPARATE_EYELID_GLOBE_ALAE_LIP_ORAL_JAW_STRUCTURES",
    "SEPARATE_PROJECT_FACE_TEXTURE_AND_SHADING_FROM_PHOTO",
    "RESTORE_FRONTAL_CANONICAL_SHAPE_WITHOUT_PERSPECTIVE_DISTORTION",
    "GENERATE_45DEG_BY_3D_CANONICAL_MESH_ROTATION_NOT_2D_POINT_SHIFT",
    "SHOW_RENDER_MATCHED_TO_ORIGINAL_PHOTO_FRAMING",
    "ONLY_THEN_RUN_AB_BLINDED_SELF_SIMILARITY_REVIEW",
]


def write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    for pid in ("P001", "P002", "P003"):
        for kind in ("SELF", "INTERNAL"):
            path = BUNDLE / "participants" / pid / "review" / f"{pid}_{kind}_REVIEW.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["status"] = UNEVAL
            doc["completed"] = False
            doc["reviewedAtUtc"] = None
            if kind == "SELF":
                doc["preferredDraft"] = None
            else:
                doc["reviewerId"] = None
            doc["overall"] = UNEVAL
            doc["comment"] = (
                "Dense FaceMesh clay captures lack identity-evaluable detail. "
                "Form not completed as identity review. Capture class demoted to TECHNICAL_SHAPE_QA_ONLY."
            )
            doc["identityReviewAllowed"] = "DENY"
            doc["captureClass"] = VERDICT
            doc["formCompletionPolicy"] = "DO_NOT_FILL_IDENTITY_SCORES"
            doc["photorealClaim"] = "DENY"
            doc["countsAsGate8ParticipantEvidence"] = "DENY"
            doc["production"] = "NO-GO"
            write(path, doc)

        write(
            BUNDLE / "participants" / pid / "V07_QP_GF_FACE_V2_DENSE_CAPTURE_CLASS_DEMOTION.json",
            {
                "schema": "NURION_V07_QP_GF_FACE_V2_DENSE_CAPTURE_CLASS_DEMOTION_V1",
                "participantId": pid,
                "priorJudgment": "DENSE_CAPTURE_READY",
                "demotedCaptureClass": VERDICT,
                "identityReview": "DENY",
                "selfInternalForms": UNEVAL,
                "blindMappingDisclosure": "DENY",
                "demotedAt": NOW,
                "production": "NO-GO",
            },
        )

    receipt = {
        "schema": "NURION_V07_QP_GF_FACE_V2_DENSE_IDENTITY_REVIEW_DEMOTION_RECEIPT_V1",
        "commandContext": "OPERATOR_HUMAN_VISUAL_ADJUDICATION_OF_DENSE_BLINDED_REVIEW_DESK",
        "runId": "20260816T075023Z",
        "bundle": "human_review/dense_blinded_bundle_20260816T075023Z",
        "completedAt": NOW,
        "verdict": VERDICT,
        "gate5Pipeline": "PASS_LOCKED_UNCHANGED",
        "gate5ParameterHash": "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d",
        "gate5Mutation": "DENY",
        "identityDraftQualityPass": "DENY",
        "identityDraftQualityExpansion": "DENY",
        "humanForms": {
            "count": 6,
            "policy": "DO_NOT_COMPLETE_AS_IDENTITY_REVIEW",
            "status": UNEVAL,
            "scoresInvented": "DENY",
            "collectionAdjudicationGo": "DENY_UNTIL_IDENTITY_GRADE_RECONSTRUCTION",
        },
        "judgeableNow": JUDGEABLE,
        "notJudgeableNow": NOT_JUDGEABLE,
        "screenDefects": SCREEN_DEFECTS,
        "captureCountDemoted": 18,
        "blindMappingDisclosure": "DENY",
        "photorealClaim": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
        "requiredNextImprovements": NEXT_IMPROVEMENTS,
        "recommendedNextCommand": (
            "NURION Quick Profile Geometry-First Face Analyzer v2 "
            "Gate 6 Identity-Grade Parametric Face Reconstruction GO"
        ),
        "gate6PassCriterion": (
            "HUMAN_CAN_JUDGE_EYE_NOSE_MOUTH_FACE_SHAPE_VS_ORIGINAL_NOT_MERELY_MESH_GENERATED"
        ),
        "note": "854 triangles increase point connectivity; they do not establish identity expressivity.",
    }
    write(BUNDLE / "V07_QP_GF_FACE_V2_DENSE_IDENTITY_REVIEW_DEMOTION_RECEIPT.json", receipt)
    write(G5 / "V07_QP_GF_FACE_V2_DENSE_IDENTITY_REVIEW_DEMOTION_RECEIPT.json", receipt)

    g5 = json.loads((G5 / "V07_QP_GF_FACE_V2_GATE5_STATUS.json").read_text(encoding="utf-8"))
    g5["updatedAt"] = NOW
    g5["V07_QP_GF_FACE_V2_GATE5"] = "PASS"
    g5["LOCKED"] = True
    g5["identityDraftQualityPass"] = "DENY"
    g5["denseParticipantCaptures"] = {
        "priorVerdict": "DENSE_CAPTURES_READY_AWAITING_HUMAN_RESPONSES",
        "verdict": VERDICT,
        "runId": "20260816T075023Z",
        "humanResponsesCollected": False,
        "formsStatus": UNEVAL,
        "identityReview": "DENY",
    }
    g5["next"] = "GATE6_IDENTITY_GRADE_PARAMETRIC_FACE_RECONSTRUCTION"
    g5["production"] = "NO-GO"
    g5["photorealAutomaticPass"] = "DENY"
    write(G5 / "V07_QP_GF_FACE_V2_GATE5_STATUS.json", g5)

    g4 = json.loads((G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json").read_text(encoding="utf-8"))
    g4["updatedAt"] = NOW
    g4["humanSimilarityCollectionAdjudication"] = "DENY_IDENTITY_DETAIL_ABSENT"
    g4["denseCaptureBundle"] = "../gate5/human_review/dense_blinded_bundle_20260816T075023Z"
    g4["denseCaptureClass"] = VERDICT
    g4["next"] = "AWAIT_GATE6_IDENTITY_GRADE_PARAMETRIC_FACE_RECONSTRUCTION_GO"
    g4["production"] = "NO-GO"
    g4["humanResponseCollection"] = {
        "phase": "SUSPENDED_IDENTITY_DETAIL_ABSENT",
        "formsStatus": UNEVAL,
        "interpolation": "DENY",
        "collectionAdjudicationGo": "DENY",
        "gate4Mutation": "DENY",
    }
    write(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json", g4)

    qp3 = json.loads(QP3.read_text(encoding="utf-8"))
    qp3["updatedAt"] = NOW
    qp3["geometryFirstDenseCaptureBlindedReview"] = {
        "verdict": VERDICT,
        "runId": "20260816T075023Z",
        "humanResponsesCollected": False,
        "formsStatus": UNEVAL,
        "identityReview": "DENY",
        "identityDraftQualityPass": "DENY",
        "production": "NO-GO",
        "bundle": str(BUNDLE).replace(str(ROOT) + "\\", "").replace("\\", "/"),
        "demotionReceipt": "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate5/V07_QP_GF_FACE_V2_DENSE_IDENTITY_REVIEW_DEMOTION_RECEIPT.json",
    }
    qp3["parallelTracks"] = {
        "lowPolyIdentityReview": "HOLD_INSUFFICIENT_VISUAL_FIDELITY",
        "denseIdentityCaptures": VERDICT,
        "humanFormCompletion": UNEVAL,
        "geometryFirstFaceV2": "GATE5_PASS_LOCKED_PIPELINE_ONLY_NOT_IDENTITY_QUALITY",
        "recommendedNext": "GATE6_IDENTITY_GRADE_PARAMETRIC_FACE_RECONSTRUCTION",
    }
    write(QP3, qp3)

    write(
        BUNDLE / "V07_QP_GF_FACE_V2_DENSE_REVIEW_OPERATOR_PACKET.json",
        {
            "schema": "NURION_V07_QP_GF_FACE_V2_DENSE_REVIEW_OPERATOR_PACKET_V1",
            "registeredAt": NOW,
            "supersedes": "prior awaiting-human-forms packet for run 20260816T075023Z",
            "verdict": VERDICT,
            "doNot": [
                "Fill SELF/INTERNAL forms as identity similarity scores",
                "Open NATURAL/POLISHED blind mapping for identity adjudication",
                "Run Human Review Collection And Adjudication GO on these 18 captures",
                "Claim Identity Draft quality PASS from Gate5 pipeline PASS",
            ],
            "formsStatus": UNEVAL,
            "awaitCommand": (
                "NURION Quick Profile Geometry-First Face Analyzer v2 "
                "Gate 6 Identity-Grade Parametric Face Reconstruction GO"
            ),
            "gate6PassCriterion": (
                "HUMAN_CAN_JUDGE_EYE_NOSE_MOUTH_FACE_SHAPE_VS_ORIGINAL_NOT_MERELY_MESH_GENERATED"
            ),
            "production": "NO-GO",
        },
    )

    # Update review desk banner notice
    desk = BUNDLE / "DENSE_BLINDED_REVIEW_DESK.html"
    html = desk.read_text(encoding="utf-8")
    notice = (
        '<p style="color:#c4a574;font-weight:600;margin:.5rem 0 0">'
        "공식 강등: TECHNICAL_SHAPE_QA_ONLY_IDENTITY_REVIEW_DENY — "
        "본인 유사성 양식 작성 금지 (NOT_EVALUABLE_IDENTITY_DETAIL_ABSENT). "
        "Gate5 파이프라인 PASS/LOCKED 유지, Identity Draft 품질 PASS 확대 DENY."
        "</p>"
    )
    if "TECHNICAL_SHAPE_QA_ONLY_IDENTITY_REVIEW_DENY" not in html:
        html = html.replace(
            '<div class="badges">',
            notice + '\n    <div class="badges">\n      <span class="badge warn">IDENTITY_REVIEW: DENY</span>',
            1,
        )
        desk.write_text(html, encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": VERDICT,
                "forms": UNEVAL,
                "gate5": "PASS_LOCKED",
                "identityDraftQualityPass": "DENY",
                "next": "Gate 6 Identity-Grade Parametric Face Reconstruction GO",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
