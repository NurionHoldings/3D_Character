#!/usr/bin/env python3
"""Apply RIG-01B accepted decisions + run RIG-01C Axis/Rest/Retarget Convention."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
EVIDENCE = WORK / "evidence"
SEMANTIC = WORK / "semantic"
LEDGER = WORK / "mutation_ledger.json"

JAKE = ROOT / "fast_track/assets/external/hr05_jake/Jake.fbx"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
BLENDER_PY = ROOT / "tools/blender_rig01c_axis_rest_forensic.py"

DRAFT = SEMANTIC / "NURION_BODY_CANONICAL_BONE_SPEC_V1_DRAFT.json"
LOCK_CAND = SEMANTIC / "NURION_BODY_CANONICAL_BONE_SPEC_V1_LOCK_CANDIDATE.json"
CONVENTION = SEMANTIC / "NURION_BODY_AXIS_RETARGET_CONVENTION_V1_DRAFT.json"

RIG01B_ACCEPT = EVIDENCE / "NURION-RIG-01B_hierarchy_semantics_ACCEPT_receipt.json"
RIG01C_RAW = EVIDENCE / "NURION-RIG-01C_axis_rest_forensic_raw.json"
RIG01C = EVIDENCE / "NURION-RIG-01C_axis_retarget_convention_receipt.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


JAKE_TO_NURION = {
    "CC_Base_BoneRoot": {"nurion": "NURION_root", "role": "DIRECT"},
    "CC_Base_Hip": {"nurion": "NURION_pelvis", "role": "DIRECT_SEMANTIC_FORK"},
    "CC_Base_Pelvis": {"nurion": None, "role": "ADAPTER_INTERMEDIARY"},
    "CC_Base_Waist": {"nurion": "NURION_spine01", "role": "DIRECT"},
    "CC_Base_Spine01": {"nurion": "NURION_spine02", "role": "DIRECT"},
    "CC_Base_Spine02": {"nurion": "NURION_chest", "role": "DIRECT"},
    "CC_Base_NeckTwist01": {"nurion": "NURION_neck", "role": "COLLAPSE_COMPOUND_A"},
    "CC_Base_NeckTwist02": {"nurion": "NURION_neck", "role": "COLLAPSE_COMPOUND_B"},
    "CC_Base_Head": {"nurion": "NURION_head", "role": "DIRECT_FACE_ATTACHMENT"},
    "CC_Base_L_Clavicle": {"nurion": "NURION_clavicle_L", "role": "DIRECT"},
    "CC_Base_L_Upperarm": {"nurion": "NURION_upperArm_L", "role": "DIRECT"},
    "CC_Base_L_Forearm": {"nurion": "NURION_lowerArm_L", "role": "DIRECT"},
    "CC_Base_L_Hand": {"nurion": "NURION_hand_L", "role": "DIRECT"},
    "CC_Base_R_Clavicle": {"nurion": "NURION_clavicle_R", "role": "DIRECT"},
    "CC_Base_R_Upperarm": {"nurion": "NURION_upperArm_R", "role": "DIRECT"},
    "CC_Base_R_Forearm": {"nurion": "NURION_lowerArm_R", "role": "DIRECT"},
    "CC_Base_R_Hand": {"nurion": "NURION_hand_R", "role": "DIRECT"},
    "CC_Base_L_Thigh": {"nurion": "NURION_thigh_L", "role": "DIRECT_VIA_INTERMEDIARY_PELVIS"},
    "CC_Base_L_Calf": {"nurion": "NURION_calf_L", "role": "DIRECT"},
    "CC_Base_L_Foot": {"nurion": "NURION_foot_L", "role": "DIRECT"},
    "CC_Base_L_ToeBase": {"nurion": "NURION_toe_L", "role": "DIRECT"},
    "CC_Base_R_Thigh": {"nurion": "NURION_thigh_R", "role": "DIRECT_VIA_INTERMEDIARY_PELVIS"},
    "CC_Base_R_Calf": {"nurion": "NURION_calf_R", "role": "DIRECT"},
    "CC_Base_R_Foot": {"nurion": "NURION_foot_R", "role": "DIRECT"},
    "CC_Base_R_ToeBase": {"nurion": "NURION_toe_R", "role": "DIRECT"},
}


def apply_01b_accept(ts: str) -> dict:
    cand = json.loads(LOCK_CAND.read_text(encoding="utf-8"))
    decisions = {
        "status": "HIERARCHY_SEMANTICS_ACCEPTED",
        "acceptedAtUtc": ts,
        "fullLock": "DENY_UNTIL_RIG01C_PASS",
        "decisions": {
            "NURION_root": "BoneRoot role only — CONFIRMED",
            "NURION_pelvis": "Jake Hip semantic fork — CONFIRMED (NOT Jake Pelvis name)",
            "Waist": "NURION_spine01 keep — CONFIRMED",
            "Spine01": "NURION_spine02 — CONFIRMED",
            "Spine02": "NURION_chest — CONFIRMED",
            "Clavicle": "direct child of NURION_chest — CONFIRMED",
            "NeckTwist01_02": "collapse to single NURION_neck — CONFIRMED",
            "Jake_Pelvis": "adapter intermediary, NOT Canonical — CONFIRMED",
            "Axis_retarget": "RIG-01C required before Full LOCK — CONFIRMED",
            "root_pelvis_never_merge": "CONFIRMED",
            "bodyCoreCount": 23,
            "handExtensionCount": 30,
        },
        "jakeToNurionAccepted": JAKE_TO_NURION,
        "classificationBuckets": [
            "CORE",
            "HAND_EXTENSION",
            "DEFORM_EXTENSION",
            "FACE",
            "HELPER",
        ],
        "rootPelvisContractPreview": {
            "NURION_root": [
                "world locomotion",
                "global translation",
                "global heading/yaw",
                "character placement",
                "no mesh deformation responsibility",
            ],
            "NURION_pelvis": [
                "body COM motion",
                "hip sway",
                "vertical bounce",
                "local pelvic rotation",
                "legs + torso semantic fork",
            ],
        },
    }
    cand["hierarchySemanticsAccept"] = decisions
    cand["stillOpenBeforeFullLock"] = [
        "RIG-01C coordinate/up/forward/handedness/unit",
        "RIG-01C canonical rest pose (A-pose reference candidate)",
        "RIG-01C bone local-axis + quaternion convention",
        "RIG-01C root vs pelvis translation ownership (formal)",
        "RIG-01C collapsed-chain + intermediary + twist distribution rules",
        "RIG-01C L/R mirror + retarget validation tolerance",
    ]
    cand["lockGate"] = "RIG-01C PASS + human ACCEPT → BODY Canonical Bone Spec v1 Full LOCK"
    cand["nurionMappingImplication"] = {
        "NURION_root": "CC_Base_BoneRoot",
        "NURION_pelvis": "CC_Base_Hip",
        "NURION_spine01": "CC_Base_Waist",
        "NURION_spine02": "CC_Base_Spine01",
        "NURION_chest": "CC_Base_Spine02",
        "NURION_neck": "compound(NeckTwist01, NeckTwist02)",
        "NURION_head": "CC_Base_Head",
        "Jake_Pelvis": "ADAPTER_INTERMEDIARY",
    }
    # fix outdated implication block if present
    if "jakeHierarchyResolved" in cand:
        cand["jakeHierarchyResolved"]["nurionMappingImplication"] = cand["nurionMappingImplication"]
    LOCK_CAND.write_text(json.dumps(cand, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    draft["hierarchySemanticsAccept"] = decisions["decisions"]
    draft["jakeToNurionAccepted"] = JAKE_TO_NURION
    draft["status"] = "ESTABLISHED_NOT_LOCKED_HIERARCHY_ACCEPTED"
    DRAFT.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    accept_receipt = {
        "receiptId": f"NURION-RIG-01B_ACCEPT_{ts}",
        "stage": "NURION-RIG-01B_HIERARCHY_SEMANTICS_ACCEPT",
        "status": "PASS",
        "bodyCore23": "ACCEPTED",
        "handExtension30": "ACCEPTED",
        "hierarchySemantics": "ACCEPTED",
        "bodyCanonicalV1": "LOCK_CANDIDATE_MAINTAINED",
        "fullLock": "DENY_UNTIL_RIG01C_PASS",
        "decisions": decisions["decisions"],
        "jakeToNurionAccepted": JAKE_TO_NURION,
        "next": "NURION-RIG-01C_AXIS_RETARGET_CONVENTION",
    }
    RIG01B_ACCEPT.write_text(json.dumps(accept_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return accept_receipt


def write_convention(ts: str, measure: dict) -> dict:
    pose = measure["restPoseClassification"]
    axes = measure["characterAxesGuess"]
    conv = {
        "schema": "NURION_BODY_AXIS_RETARGET_CONVENTION_V1_DRAFT",
        "status": "DRAFT_FOR_HUMAN_REVIEW",
        "fullBodyCanonicalLock": "DENY_UNTIL_THIS_PASS_AND_ACCEPT",
        "declaredAtUtc": ts,
        "basedOnMeasurement": str(RIG01C_RAW),
        "donorSample": {
            "asset": "Jake.fbx",
            "role": "measurement donor/reference — not Canonical clone",
            "observedRestPoseClass": pose["class"],
            "averageArmAbductionFromDownDeg": pose["averageAbductionDeg"],
        },
        "1_coordinateSystem": {
            "engineCanonical": "right-handed",
            "blenderImportNote": "Blender right-handed; FBX import used automatic_bone_orientation=True",
        },
        "2_worldUpAxis": {
            "canonical": "+Y",
            "jakeSampleGuess": axes["up"],
            "note": "Canonical contract = +Y up; donor may require remapping in Adapter",
        },
        "3_characterForwardAxis": {
            "canonical": "+Z",
            "jakeSampleGuess": axes["forward"],
            "note": "Canonical facing +Z; Adapter aligns donor forward → +Z",
        },
        "4_handedness": {"canonical": "right-handed"},
        "5_unitScale": {
            "canonical": "meters",
            "jakeScaleProxies": measure["scaleProxies"],
            "rule": "Adapter normalizes donor unit → meters before retarget",
        },
        "6_canonicalRestPose": {
            "reference": "A_POSE",
            "allowsTPoseDonors": True,
            "pipeline": "DonorRest → RestPoseNormalization → NURION_Canonical_A_Pose",
            "targets": {
                "shoulderAbductionFromDownDeg": {"nominal": 40, "toleranceDeg": 10},
                "elbowFlexionDeg": {"nominal": 0, "toleranceDeg": 8},
                "wristNeutral": True,
                "hipKneeNeutral": True,
            },
            "jakeObserved": pose,
            "rationale": "A-pose preferred for skinning/auto-rig; T-pose donors accepted via normalization",
        },
        "7_boneLocalAxisConvention": {
            "canonicalBoneAim": "+Y along bone (parent joint → child joint)",
            "canonicalBoneNormal": "+Z secondary (twist reference) — finalize after multi-donor sample",
            "blenderParity": "matches Blender edit-bone +Y aim",
            "jakeBoneYAlignSample": {
                n: b.get("yAlignDeg") for n, b in list(measure["bones"].items())[:8]
            },
        },
        "8_quaternionRotationConvention": {
            "order": "WXYZ",
            "space": "local_relative_to_parent_in_canonical_bind",
            "note": "Do not copy donor quaternions across mismatched local axes",
        },
        "9_translationOwnership": {
            "NURION_root": "OWNS global translation (world locomotion / placement)",
            "NURION_pelvis": "OWNS local pelvic translation relative to root (COM sway/bounce)",
            "otherCoreBones": "rotation-primary; translation locked to bind offsets unless explicitly authored",
        },
        "10_scaleOwnership": {
            "default": "uniform scale on NURION_root only; child bones scale=1 in Canonical v1",
            "deny": "per-bone non-uniform scale in Core animation curves for v1",
        },
        "11_rootMotionContract": {
            "NURION_root": [
                "world locomotion",
                "global translation",
                "global heading/yaw",
                "character placement",
            ],
            "deformation": "NONE — root does not skin",
        },
        "12_pelvisMotionContract": {
            "NURION_pelvis": [
                "body COM motion",
                "hip sway",
                "vertical bounce",
                "local pelvic rotation",
            ],
            "semanticFork": "legs + torso",
        },
        "13_donorRestPoseNormalization": {
            "required": True,
            "steps": [
                "detect donor rest class (T/A/intermediate)",
                "build donor→canonical bind alignment",
                "bake rest deltas into Adapter, not into Canonical bone names",
            ],
        },
        "14_donorToCanonicalLocalTransform": {
            "rule": "R_c = A_bind_c * A_bind_d^{-1} * R_d * (axisCorrection)",
            "status": "FORMULA_DRAFT — implement in RIG-02 Adapter",
        },
        "15_canonicalToTargetLocalTransform": {
            "rule": "inverse of §14 for export/skin targets",
            "status": "FORMULA_DRAFT — implement in RIG-02 Adapter",
        },
        "16_collapsedChainRule": {
            "example": "NeckTwist01 × NeckTwist02 → NURION_neck",
            "measurement": measure["neckCollapse"],
            "rule": "compound local from chest parent to final neck child becomes NURION_neck bind/anim",
        },
        "17_intermediaryRule": {
            "example": "Hip → Pelvis → Thigh",
            "measurement": measure["intermediaryPelvis"],
            "rule": "Jake Pelvis not Canonical; Adapter parents thighs under NURION_pelvis with baked intermediary offset",
        },
        "18_twistBoneDistributionRule": {
            "core": "NO twist bones in BODY_CORE_V1",
            "extension": "DEFORM_EXTENSION_V1 optional",
            "distribution": "if present, twist weight split along limb length; Core anim ignores twist channels",
        },
        "19_leftRightMirrorConvention": {
            "nameSuffix": "_L / _R",
            "mirrorAxis": "canonical character lateral = X",
            "quaternionMirror": "reflect rotation across YZ plane (standard body mirror)",
        },
        "20_retargetValidationTolerance": {
            "boneLengthRatioTolerance": 0.08,
            "bindAxisAlignDegTolerance": 12.0,
            "endEffectorPositionToleranceMeters": 0.02,
            "lrSymmetryLengthRatioTolerance": 0.03,
        },
        "next": "Human ACCEPT of this convention draft → RIG-01C PASS → BODY Canonical v1 Full LOCK",
    }
    CONVENTION.write_text(json.dumps(conv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return conv


def update_ledger(ts: str) -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["presentationLayer"] = (
        "FACE LOCKED / TALKING GO — RIG-01A/01B PASS (hierarchy ACCEPTED); "
        "RIG-01C convention DRAFT ready; BODY Canonical v1 Full LOCK = DENY until 01C ACCEPT"
    )
    ids = {e.get("id") for e in ledger.get("entries", [])}
    # update 01B entry
    for e in ledger.get("entries", []):
        if e.get("id") == "NURION-RIG-01B":
            e["hierarchySemantics"] = "ACCEPTED"
            e["bodyCore23"] = "ACCEPTED"
            e["handExtension30"] = "ACCEPTED"
            e["fullLock"] = "DENY_UNTIL_RIG01C"
            e["acceptReceipt"] = str(RIG01B_ACCEPT)
            e["next"] = "NURION-RIG-01C"
    if "NURION-RIG-01C" not in ids:
        ledger["entries"].append(
            {
                "id": "NURION-RIG-01C",
                "type": "AXIS_REST_RETARGET_CONVENTION",
                "mutation": 0,
                "scope": "coordinate/up/forward/rest-pose/axis/root-pelvis ownership/collapse/intermediary rules",
                "evidence": str(RIG01C),
                "raw": str(RIG01C_RAW),
                "conventionDraft": str(CONVENTION),
                "status": "DRAFT_AWAITING_HUMAN",
                "body_canonical_v1": "LOCK_CANDIDATE_NOT_LOCKED",
                "fullLock": "DENY",
                "next": "HUMAN_ACCEPT_THEN_BODY_CANONICAL_V1_FULL_LOCK",
            }
        )
    ledger["bodyCanonicalTrack"] = {
        "faceProductLock": "DECLARED",
        "talking_status": "GO",
        "rig01a": "PASS",
        "rig01b": "PASS_HIERARCHY_ACCEPTED",
        "rig01c": "DRAFT_AWAITING_HUMAN",
        "bodyCore23": "ACCEPTED",
        "handExtension30": "ACCEPTED",
        "bodyCanonicalV1": "LOCK_CANDIDATE_NOT_LOCKED",
        "fullLock": "DENY_UNTIL_RIG01C_PASS",
        "updatedAtUtc": ts,
    }
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    apply_01b_accept(ts)

    proc = subprocess.run(
        [
            str(BLENDER),
            "--background",
            "--python",
            str(BLENDER_PY),
            "--",
            "--fbx",
            str(JAKE),
            "--out-json",
            str(RIG01C_RAW),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)

    measure = json.loads(RIG01C_RAW.read_text(encoding="utf-8"))
    conv = write_convention(ts, measure)

    receipt = {
        "receiptId": f"NURION-RIG-01C_{ts}",
        "stage": "NURION-RIG-01C_AXIS_RETARGET_CONVENTION",
        "status": "DRAFT_AWAITING_HUMAN",
        "fullLock": "DENY",
        "bodyCanonicalV1": "LOCK_CANDIDATE_NOT_LOCKED",
        "fbx": str(JAKE),
        "fbxSha256": sha256(JAKE),
        "rawArtifact": str(RIG01C_RAW),
        "conventionDraft": str(CONVENTION),
        "measurementSummary": {
            "restPoseClass": measure["restPoseClassification"]["class"],
            "avgAbductionDeg": measure["restPoseClassification"]["averageAbductionDeg"],
            "elbowFlexL": measure["restPoseClassification"]["elbowFlexL"],
            "elbowFlexR": measure["restPoseClassification"]["elbowFlexR"],
            "kneeFlexL": measure["restPoseClassification"]["kneeFlexL"],
            "kneeFlexR": measure["restPoseClassification"]["kneeFlexR"],
            "characterAxesGuess": measure["characterAxesGuess"],
            "scaleProxies": measure["scaleProxies"],
        },
        "recommendedCanonical": {
            "restPose": "A_POSE",
            "up": "+Y",
            "forward": "+Z",
            "handedness": "right",
            "units": "meters",
            "boneAim": "+Y",
            "rootPelvisSplit": "REQUIRED",
        },
        "checklist20": {str(i): "DRAFTED" for i in range(1, 21)},
        "faceProductLock": "DECLARED",
        "talking_status": "GO",
        "next": "Human ACCEPT of convention → declare RIG-01C PASS → BODY Canonical v1 Full LOCK",
        "blenderStdoutTail": (proc.stdout or "")[-1500:],
    }
    RIG01C.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    update_ledger(ts)

    print(
        json.dumps(
            {
                "rig01bAccept": str(RIG01B_ACCEPT),
                "rig01c": str(RIG01C),
                "convention": str(CONVENTION),
                "poseClass": receipt["measurementSummary"]["restPoseClass"],
                "avgAbduction": receipt["measurementSummary"]["avgAbductionDeg"],
                "fullLock": "DENY",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
