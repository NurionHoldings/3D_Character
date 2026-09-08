"""Official adjudication: NURION_PARAMETRIC_HEAD_V1 is ellipsoid, not a human face parametric mesh."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
BETA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_beta1"
ALPHA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_alpha"
GATE6 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate6"
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema": "NURION_V07_QP_ASSET_INELIGIBLE_PARAMETRIC_HEAD_ADJUDICATION_V1",
        "verdict": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
        "adjudicatedAt": now,
        "evidence": {
            "wireframeRunId": "20260816T093137Z",
            "observedMesh": "NURION_PARAMETRIC_HEAD_V1",
            "observedClass": "HIGH_DENSITY_SPHERICAL_ELLIPSOID_TRI_MESH",
            "notHumanFaceParametricTopology": True,
            "findings": [
                "NO_ANATOMICAL_EDGE_LOOPS_FOR_EYE_NOSE_MOUTH_JAW",
                "NO_EYE_SOCKET_OR_EYELID_TOPOLOGY",
                "NO_ALA_OR_NOSTRIL_STRUCTURE",
                "NO_LIP_INNER_OUTER_OR_ORAL_OPENING",
                "NO_JAW_CHEEKBONE_TEMPLE_CONTROL_TOPOLOGY",
                "NEAR_UNIFORM_SPHERICAL_TRIANGULATION",
                "HUMAN_APPEARANCE_IS_PHOTO_TEXTURE_NOT_SHAPE",
                "SIDE_VIEW_BALLOON_EFFECT_CONFIRMED",
                "WHITE_EYE_AND_MOUTH_OBJECTS_ARE_TEMPORARY_PRIMITIVES",
            ],
        },
        "stopWork": [
            "ELLIPSOID_HEAD_MESH_TWEAKING",
            "UV_REPROJECTION_ITERATION",
            "EYE_MOUTH_PRIMITIVE_REPOSITION",
            "FULL_BODY_REASSEMBLY",
            "AB_HUMAN_EVALUATION",
            "BETA_PASS_DECLARATION",
            "ARKAON_LEARNING_DATA_INCLUSION",
        ],
        "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
        "rootCause": "CORE_FACE_ASSET_ABSENCE_NOT_ALGORITHM_MICROERROR",
        "requiredAsset": {
            "quadCentricHumanFaceTopology": True,
            "eyelidOrbitNoseLipOralEarJaw": True,
            "neckJoin": True,
            "identityShapeBasis": True,
            "expressionBasis": True,
            "jawEyeJoints": True,
            "continuousUV": True,
            "mediapipe478CorrespondenceTable": True,
            "commercialUseModifyDistributeRights": True,
            "sourceFileAndLicenseSha256": True,
        },
        "strategy": {
            "path1": "COMMERCIAL_LICENSED_PARAMETRIC_HEAD_ACQUIRE",
            "path2": "NURION_OWNED_HEAD_BASE_COMMISSION",
            "recommended": "COMMERCIAL_EXTERNAL_FOR_PRODUCT_ALPHA_PARALLEL_NURION_OWNED_REPLACE_LATER",
            "engineReuse": "KEEP_478_CORRESPONDENCE_CONTRACT_AND_FIT_RIG_EXPORT",
        },
        "holds": {
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "arkaonLearningInclusion": "HOLD",
            "betaPass": "DENY",
            "production": "NO-GO",
        },
        "nextCommand": "NURION Parametric Head Asset Acquisition Commercial License And Topology Gate GO",
        "forcedPass": "DENY",
        "production": "NO-GO",
    }
    raw = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()

    write_json(BETA / "V07_QP_ASSET_INELIGIBLE_PARAMETRIC_HEAD_ADJUDICATION.json", receipt)
    write_json(ACQ / "V07_QP_ASSET_INELIGIBLE_PARAMETRIC_HEAD_ADJUDICATION.json", receipt)

    write_json(
        BETA / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
        {
            "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS_V1",
            "status": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
            "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
            "LOCKED": True,
            "updatedAt": now,
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "betaPass": "DENY",
            "forcedPass": "DENY",
            "production": "NO-GO",
            "arkaonLearningInclusion": "HOLD",
            "next": receipt["nextCommand"],
            "rootCause": receipt["rootCause"],
        },
    )

    alpha_path = ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS.json"
    if alpha_path.is_file():
        alpha = json.loads(alpha_path.read_text(encoding="utf-8"))
        alpha.update(
            {
                "status": "ALPHA_PIPELINE_CONNECTED_VISUAL_PRODUCT_NOT_EVALUABLE",
                "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
                "faceOutput": "IDENTITY_RENDER_INVALID",
                "faceRenderPath": "BLOCKER_DIRECT_FACEMESH_RENDERING_INVALID",
                "parametricHeadAsset": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
                "faceGeneration": "HOLD",
                "fullBodyAssembly": "HOLD",
                "humanEvaluation": "HOLD",
                "beta1Status": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
                "updatedAt": now,
                "production": "NO-GO",
                "next": receipt["nextCommand"],
            }
        )
        write_json(alpha_path, alpha)

    # Demote false Gate6 registry claim that ellipsoid was a commercial parametric head
    registry = {
        "schema": "NURION_V07_QP_GF_FACE_V2_GATE6_COMMERCIAL_MODEL_REGISTRY_V2",
        "updatedAt": now,
        "commercialClearance": "DENY_NO_ELIGIBLE_PARAMETRIC_HEAD_ASSET",
        "priorIncorrectClaim": "PASS_NURION_OWNED_PARAMETRIC_HEAD_ON_ELLIPSOID",
        "demotionReason": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
        "ineligibleAssets": [
            {
                "id": "NURION_PARAMETRIC_HEAD_V1",
                "class": "SPHERICAL_ELLIPSOID_TRI_MESH",
                "eligibleAsProductFaceBase": "DENY",
            }
        ],
        "eligibleAssets": [],
        "research3dmmImported": "DENY",
        "note": "Wireframe evidence proves ellipsoid is not human-face parametric topology. Asset Acquisition Gate required.",
    }
    write_json(GATE6 / "V07_QP_GF_FACE_V2_GATE6_COMMERCIAL_MODEL_REGISTRY.json", registry)

    print(json.dumps({"verdict": receipt["verdict"], "next": receipt["nextCommand"], "production": "NO-GO"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
