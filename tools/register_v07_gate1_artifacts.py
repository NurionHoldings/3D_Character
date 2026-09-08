"""Register official v0.7 Gate 1 artifacts into dist/v0.7/gate1/."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1 = ROOT / "dist" / "v0.7" / "gate1"


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()


def write_json(path: Path, doc: dict) -> str:
    raw = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return sha_bytes(raw)


def main() -> None:
    G1.mkdir(parents=True, exist_ok=True)

    status = {
        "schema": "NURION_V07_GATE1_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 1,
        "name": "PRODUCT_SCOPE_INPUT_OUTPUT_AND_SAFETY_CONTRACT",
        "V07_GATE1": "PASS",
        "locked": True,
        "officialFrozenBaseline": True,
        "parameterHash": "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170",
        "checks": {
            "PRODUCT_SCOPE": "PASS",
            "INPUT_CONTRACT": "PASS",
            "OUTPUT_CONTRACT": "PASS",
            "NATIVE_ARMATURE_BOUNDARY": "PASS",
            "WEIGHT_AND_DEFORM_GATES": "PASS",
            "HOMEPAGE_CONTROL_ROLES": "PASS",
            "HAND_GESTURE_POLICY": "PASS",
            "FACE_EYE_READONLY_ATTACHMENT": "PASS",
            "GROUND_TRUTH_ACCURACY_POLICY": "PASS",
            "ABSTAIN_POLICY": "PASS",
            "HOMEPAGE_PRESET_10": "PASS",
            "V08_VIDEO_COPY_EXCLUDED": "PASS",
            "V06_ACTIVATION_UNCHANGED": "PASS",
            "SEALED_BASELINE_MUTATION": 0,
            "SOURCE_ASSET_MUTATION": 0,
            "PRODUCTION": "NO-GO",
        },
        "implementationStarted": False,
        "armatureGenerated": False,
        "weightsGenerated": False,
        "animationsGenerated": False,
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
        "limitations": [
            "NO_ASSET_EVALUATION_IN_GATE1",
            "GROUND_TRUTH_REQUIRED_FOR_ACCURACY_CLAIMS",
            "FULL_FINGER_RIG_OPTIONAL_BY_ELIGIBILITY",
            "V0.8_VIDEO_PERFORMANCE_COPY_OUT_OF_SCOPE",
            "PRODUCTION_NO_GO",
        ],
        "fails": [],
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": "V07_GATE2_ASSET_ELIGIBILITY_AND_LANDMARK_EVIDENCE",
        "workspaceRegistration": "REHYDRATED_FROM_OFFICIAL_GATE1_PAYLOAD",
    }

    contract = {
        "schema": "NURION_V07_GATE1_CONTRACT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 1,
        "name": "PRODUCT_SCOPE_INPUT_OUTPUT_AND_SAFETY_CONTRACT",
        "blenderTarget": "5.0.1",
        "productGoal": (
            "Create a homepage-performance-specific armature, weights, controls, and "
            "reusable upper-body performances without treating an existing Meshy rig as ground truth."
        ),
        "scope": {
            "included": [
                "new_native_armature",
                "joint_landmark_estimation_with_evidence",
                "upper_body_and_supporting_lower_body_bones",
                "homepage_hand_gesture_controls",
                "head_eye_face_attachment_contract",
                "automatic_initial_weights",
                "deformation_validation",
                "ten_to_fifteen_homepage_performance_presets",
                "retarget_handoff_to_v0.6_readonly_runtime",
            ],
            "excluded": [
                "universal_game_auto_rig",
                "unrestricted_dance_rig",
                "motion_capture_from_video",
                "guaranteed_anatomical_accuracy_without_ground_truth",
                "unlimited_facial_expression_generation",
                "production_activation",
                "modification_of_v0.6_or_earlier_sealed_artifacts",
            ],
        },
        "inputs": {
            "required": [
                "single_character_mesh",
                "world_transform",
                "visible_head_torso_arms_hands",
                "neutral_or_supported_rest_pose",
                "material_and_mesh_identity",
            ],
            "optional": [
                "existing_armature_as_non_authoritative_evidence",
                "existing_skin_weights_as_non_authoritative_evidence",
                "v0.2_landmarks",
                "v0.3_eye_attachments",
                "v0.4_face_rig_attachments",
                "manual_ground_truth_annotations_for_evaluation_only",
            ],
            "prohibitedAsGroundTruth": [
                "existing_meshy_bone_positions",
                "existing_meshy_weights",
                "motion_action_pose_samples",
            ],
        },
        "outputs": {
            "collection": "NURION_HomepagePerformanceRig",
            "armature": "NURION_HomepageNativeArmature",
            "deformRig": "NURION_HomepageDeformRig",
            "controlRig": "NURION_HomepageControlRig",
            "weightSet": "NURION_HomepageWeights",
            "diagnostics": "V07_RIG_DIAGNOSTICS.json",
            "evidence": "V07_LANDMARK_EVIDENCE.json",
            "compatibility": "V07_V06_HANDOFF.json",
            "sourceMutation": 0,
        },
        "minimumBoneRoles": [
            "Root",
            "Hips",
            "Spine",
            "Spine01",
            "Spine02",
            "Chest",
            "Neck",
            "Head",
            "Clavicle.L",
            "UpperArm.L",
            "ForeArm.L",
            "Hand.L",
            "Clavicle.R",
            "UpperArm.R",
            "ForeArm.R",
            "Hand.R",
            "UpperLeg.L",
            "LowerLeg.L",
            "Foot.L",
            "Toe.L",
            "UpperLeg.R",
            "LowerLeg.R",
            "Foot.R",
            "Toe.R",
        ],
        "homepageControlRoles": [
            "LookTarget",
            "HeadAim",
            "ChestAim",
            "HandTarget.L",
            "HandTarget.R",
            "PalmAim.L",
            "PalmAim.R",
            "Breath",
            "BodySway",
            "UIFocusTarget",
        ],
        "handPolicy": {
            "required": "PALM_AND_BASIC_GESTURE_CONTROL",
            "minimumGestures": [
                "OPEN_PALM",
                "RELAXED",
                "POINT_UI",
                "WELCOME",
                "CONSULTATION_INVITE",
            ],
            "fullFingerRig": "OPTIONAL_BY_ELIGIBILITY",
            "missingHandEvidence": "ABSTAIN_HAND_GESTURE_PATH",
        },
        "faceEyePolicy": {
            "nativeFaceRebuild": "OUT_OF_SCOPE",
            "v0.3AndV0.4": "READ_ONLY_ATTACHMENT",
            "missingFaceEvidence": "REST_FALLBACK",
            "missingEyeEvidence": "HEAD_AIM_ONLY_WITH_LIMITATION",
            "doubleTransform": "DENY",
        },
        "classification": [
            "HOMEPAGE_READY_LIMITED",
            "REVIEW_REQUIRED",
            "INELIGIBLE",
            "ABSTAIN",
        ],
        "safety": {
            "cloneOnlyBuild": True,
            "sourceMeshMutation": "DENY",
            "sourceRigMutation": "DENY",
            "sealedBaselineMutation": "DENY",
            "silentManualCorrection": "DENY",
            "assetSpecificHiddenTuning": "DENY",
            "forcePass": "DENY",
            "production": "NO-GO",
        },
        "readonlyBaselines": {
            "v0.3Rc1Sha256": "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238",
            "v0.4Rc1Sha256": "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5",
            "v0.5Rc1Sha256": "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722",
            "v0.6Rc1Sha256": "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1",
            "v0.6Activation": "NOT_GRANTED",
            "v0.6Execution": "NOT_STARTED",
        },
    }

    qg = {
        "schema": "NURION_V07_GATE1_QUALITY_GATES",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 1,
        "evaluationPolicy": "GROUND_TRUTH_REQUIRED_FOR_ACCURACY_CLAIMS",
        "jointPositionGatesCm": {
            "upperBodyMeanMax": 3.5,
            "upperBodySingleJointMax": 7.5,
            "wholeBodyMeanMax": 5.0,
            "wholeBodySingleJointMax": 10.0,
            "leftRightSwapCount": 0,
            "jointOutsideMeshCount": 0,
            "zeroLengthBoneCount": 0,
            "invalidParentCount": 0,
        },
        "restRigGates": {
            "deterministicBoneNaming": "PASS",
            "rollAndAxisConsistency": "PASS",
            "bilateralSymmetryCheck": "PASS",
            "scaleNormalization": "PASS",
            "originalTransformPreserved": "PASS",
        },
        "weightAndDeformationGates": {
            "unweightedRequiredVertices": 0,
            "nonFiniteWeights": 0,
            "weightSumTolerance": 0.001,
            "severeShoulderCollapse": 0,
            "severeElbowCollapse": 0,
            "severeWristCollapse": 0,
            "severeNeckCollapse": 0,
            "severeHipKneeCollapse": 0,
            "bodyClothingSeverePenetration": 0,
            "poseSuiteRequired": True,
        },
        "homepagePerformanceGates": {
            "eyeHeadDoubleTransform": 0,
            "jawNeckConflict": 0,
            "handUiTargetMissMaxPxAtReferenceRender": 12,
            "loopPosePositionDriftMaxCm": 1.0,
            "loopRotationDriftMaxDeg": 2.0,
            "fpsMeaning24_30_60": "PASS",
            "determinismRuns": 3,
            "sourceAndBaselineMutation": 0,
        },
        "accuracyClaimPolicy": {
            "groundTruthMissing": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
            "insufficientGeometry": "ABSTAIN",
            "occludedOrMergedHands": "ABSTAIN_HAND_GESTURE_PATH",
            "unsupportedTopology": "INELIGIBLE",
            "gateFailure": "ALGORITHM_FAIL_NO_AUTO_REPAIR",
        },
        "requiredEvaluationEvidence": [
            "world_space_joint_ground_truth",
            "head_local_eye_attachment_ground_truth_when_eye_path_tested",
            "pose_suite_deformation_metrics",
            "weight_statistics",
            "three_run_determinism_hashes",
            "source_and_baseline_pre_post_hashes",
        ],
        "production": "NO-GO",
    }

    md = """# NURION Homepage Performance Rig v0.7 — Gate 1 Contract

## Decision

Gate 1 locks the product scope, evidence contract, measurable quality gates, homepage controls, and the first ten performance presets. It does not generate or modify an armature, weights, animations, or any sealed v0.6 artifact.

## Product boundary

v0.7 creates a new homepage-performance rig from mesh and landmark evidence. An existing Meshy armature or skin may be inspected, but it is non-authoritative evidence and must never be copied as ground truth. Video-based performance reconstruction remains v0.8 scope.

## Required result

The output is a separate `NURION_HomepagePerformanceRig` collection containing a new deform rig, control rig, initial weights, diagnostics, evidence, and a read-only handoff to the sealed v0.6 runtime. Source meshes, source rigs, actions, and sealed baselines must remain byte- and state-invariant.

## Accuracy policy

Accuracy claims require world-space joint ground truth. Without ground truth, the result is `REVIEW_REQUIRED_NO_ACCURACY_CLAIM`, not a silent pass. Insufficient geometry, merged hands, unsupported topology, or missing evidence must route to `ABSTAIN`, `ABSTAIN_HAND_GESTURE_PATH`, or `INELIGIBLE`.

Locked targets include upper-body mean joint error at or below 3.5 cm, upper-body maximum at or below 7.5 cm, whole-body mean at or below 5.0 cm, whole-body maximum at or below 10.0 cm, zero L/R swaps, zero outside-mesh joints, and zero severe deformation failures in the required pose suite.

## Safety and production

Clone-only generation is mandatory. Hidden per-asset tuning, silent manual correction, force-pass, automatic repair after a failed gate, and mutation of v0.6 or earlier sealed baselines are denied. Production remains `NO-GO`; v0.6 Activation remains `NOT_GRANTED / NOT_STARTED`.
"""

    h_status = write_json(G1 / "V07_GATE1_STATUS.json", status)
    h_contract = write_json(G1 / "V07_GATE1_CONTRACT.json", contract)
    h_qg = write_json(G1 / "V07_GATE1_QUALITY_GATES.json", qg)
    (G1 / "V07_GATE1_CONTRACT.md").write_text(md, encoding="utf-8", newline="\n")
    h_md = sha_file(G1 / "V07_GATE1_CONTRACT.md")
    h_preset = sha_file(G1 / "V07_HOMEPAGE_PRESET_CATALOG.json")

    official = {
        "V07_GATE1_CONTRACT.json": "aa6fdbc11f8a92485c9727d58ebb2c141cc7e156d6c7d6148d8f7b2180be9ac8",
        "V07_GATE1_QUALITY_GATES.json": "35e0965c3481140e4236670971e6f93d161ccacc9bbe59ca70a1e913223d54ec",
        "V07_HOMEPAGE_PRESET_CATALOG.json": "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071",
        "V07_GATE1_CONTRACT.md": "4a669759f09941b1b9c512899c4263164d58a560a0ee2c6f10fa5f2499b7398b",
    }
    workspace = {
        "V07_GATE1_CONTRACT.json": h_contract,
        "V07_GATE1_QUALITY_GATES.json": h_qg,
        "V07_HOMEPAGE_PRESET_CATALOG.json": h_preset,
        "V07_GATE1_CONTRACT.md": h_md,
        "V07_GATE1_STATUS.json": h_status,
    }

    lock = {
        "schema": "NURION_V07_GATE1_BASELINE_LOCK",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 1,
        "status": "LOCKED",
        "officialFrozenBaseline": True,
        "parameterHash": "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170",
        "artifactHashes": official,
        "workspaceRegisteredArtifactHashes": workspace,
        "artifactHashMatchOfficial": {k: workspace.get(k) == official.get(k) for k in official},
        "readonlyBaselines": {
            "v0.3Rc1Sha256": "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238",
            "v0.4Rc1Sha256": "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5",
            "v0.5Rc1Sha256": "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722",
            "v0.6Rc1Sha256": "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1",
        },
        "baselineEvidenceMode": "OFFICIAL_REGISTERED_HASHES_PLUS_WORKSPACE_REHYDRATION",
        "baselineMutation": "DENY",
        "production": "NO-GO",
        "lockedAt": "2026-08-15T11:24:08+09:00",
        "workspaceRegisteredAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
    }
    write_json(G1 / "V07_GATE1_BASELINE_LOCK.json", lock)
    print(json.dumps({"match": lock["artifactHashMatchOfficial"], "workspace": workspace}, indent=2))


if __name__ == "__main__":
    main()
