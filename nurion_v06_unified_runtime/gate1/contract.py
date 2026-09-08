"""Unified I/O contract for v0.6 — structure only; no source mutation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List

from .parameters import (
    GATE1_PARAMETERS,
    V03_PACKAGE_REL,
    V03_RC1_SHA256,
    V04_PACKAGE_REL,
    V04_RC1_SHA256,
    V05_PACKAGE_REL,
    V05_RC1_SHA256,
    parameter_hash,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_contract() -> Dict:
    """Canonical Gate 1 contract document (machine + human readable fields)."""
    return {
        "schema": "NURION_V06_UNIFIED_RUNTIME_CONTRACT",
        "version": "0.6.0-gate1",
        "product": GATE1_PARAMETERS["product"],
        "track": GATE1_PARAMETERS["track"],
        "parameterHash": parameter_hash(),
        "goal": (
            "Bind sealed v0.3 Universal Eye, v0.4 Native Face Rig & Lip Sync, "
            "and v0.5 Body Motion Retarget as read-only baselines into one "
            "character workflow without mutating those baselines."
        ),
        "production": "NO-GO",
        "mutationPolicy": {
            "sealedV03": "DENY",
            "sealedV04": "DENY",
            "sealedV05": "DENY",
            "sourceZipFbx": "DENY",
            "sourceAction": "DENY",
            "limitationAutoClear": "DENY",
            "rcRepackOfSealed": "DENY",
            "inPlaceRepair": "DENY",
            "allowedWriteTargets": [
                "CLONE_ARMATURE",
                "CLONE_MESH",
                "RUNTIME_LAYER_ACTIONS",
                "RUNTIME_MARKERS",
                "EXPORT_DERIVATIVES",
                "GATE_RECEIPTS",
            ],
        },
        "input": {
            "acceptedContainers": ["ZIP", "DIRECTORY"],
            "requiredModelExtension": [".fbx", ".FBX"],
            "optionalTextures": [".png", ".jpg", ".jpeg", ".tga"],
            "characterPackageRules": {
                "singlePrimaryFbxPreferred": True,
                "siblingAnimationZipMix": "DENY",
                "originalMeshyPackagePreferred": True,
            },
            "armature": {
                "objectType": "ARMATURE",
                "minCoreBones": [
                    "hips_or_pelvis",
                    "spine",
                    "neck_or_head",
                    "left_upper_arm",
                    "right_upper_arm",
                    "left_upper_leg",
                    "right_upper_leg",
                ],
                "restPoseRequired": True,
                "zeroLengthBones": "FAIL_OR_ABSTAIN",
            },
            "mesh": {
                "skinnedMeshRequiredForFull": True,
                "withSkinHint": ["withSkin", "with_skin"],
                "faceMeshRequiredForFacePath": True,
                "eyeEvidenceRequiredForEyePath": True,
            },
            "actions": {
                "bodyMotionSources": [
                    "Formal_Bow",
                    "Idle",
                    "Gentlemans_Bow",
                    "Gentleman's_Bow",
                    "Gentleman_s_Bow",
                ],
                "faceTimelineUid": "word_확인",
                "unifiedRuntimeActionNaming": "NURION_UnifiedRuntime_<Preset>",
                "independentActionPerPreset": True,
            },
            "faceEyeBind": {
                "v04Timeline": "word_확인",
                "headParentSync": True,
                "preventEyeDoubleTransform": True,
                "jawNeckLipCollisionCheck": True,
            },
        },
        "output": {
            "blenderSceneMarkers": [
                "NURION_UnifiedRuntime",
                "NURION_UnifiedRuntime_Report",
            ],
            "exportFormats": ["BLEND_SCENE", "FBX", "GLB"],
            "fpsSemanticsPreserve": [24, 30, 60],
            "receipts": [
                "classification",
                "boneMapping",
                "bindReport",
                "validation",
                "limitationsInherited",
            ],
            "determinismRuns": 3,
            "sourceAndBaselineMutationCount": 0,
        },
        "classification": {
            "FULL": {
                "meaning": "Body + face + eye paths all eligible under limited domain rules",
                "requires": [
                    "ARMATURE_CORE",
                    "SKINNED_BODY",
                    "FACE_RIG_OR_MESH_PATH",
                    "EYE_EVIDENCE_OR_V03_COMPAT",
                    "AT_LEAST_ONE_MOTION_PRESET",
                ],
            },
            "LIMITED": {
                "meaning": "Runnable with disclosed gaps or inherited v0.5 limitations",
                "requires": [
                    "ARMATURE_CORE",
                    "SKINNED_BODY",
                    "AT_LEAST_ONE_MOTION_PRESET",
                ],
                "mayOmit": ["FULL_FACE_PATH", "FULL_EYE_PATH"],
            },
            "INELIGIBLE": {
                "meaning": "Must ABSTAIN; do not force apply unified runtime",
                "triggers": "SEE_ABSTAIN_RULES",
            },
        },
        "inheritedLimitationsPolicy": {
            "fromV05": GATE1_PARAMETERS["inheritedLimitationsFromV05"],
            "autoRemove": "DENY",
            "propagation": "PER_ASSET_RESULT_MUST_CARRY_FORWARD",
        },
        "readonlyBaselines": GATE1_PARAMETERS["readonlyBaselines"],
        "workflowOperators": [
            "Select Character",
            "Analyze",
            "Build Unified Runtime",
            "Apply Motion",
            "Validate",
            "Export",
        ],
        "gates": GATE1_PARAMETERS["pipeline"],
    }


def validate_sealed_baselines(repo_root: Path) -> Dict:
    """Read-only hash verification of sealed v0.3 / v0.4 / v0.5 RC packages."""
    repo_root = Path(repo_root)
    checks = [
        ("v0.3", V03_PACKAGE_REL, V03_RC1_SHA256),
        ("v0.4", V04_PACKAGE_REL, V04_RC1_SHA256),
        ("v0.5", V05_PACKAGE_REL, V05_RC1_SHA256),
    ]
    gates: Dict[str, str] = {}
    details: List[Dict] = []
    notes: List[str] = []

    for label, rel, expected in checks:
        path = repo_root / rel
        present = path.is_file()
        key_present = f"{label.upper().replace('.', '')}_PACKAGE_PRESENT"
        key_hash = f"{label.upper().replace('.', '')}_SHA_MATCH"
        gates[key_present] = "PASS" if present else "FAIL"
        actual = ""
        match = False
        if present:
            actual = sha256_file(path)
            match = actual == expected and len(actual) == 64
            gates[key_hash] = "PASS" if match else "FAIL"
            if not match:
                notes.append(f"{label} SHA mismatch: got {actual}, expected {expected}")
        else:
            gates[key_hash] = "FAIL"
            notes.append(f"{label} package missing: {rel}")
        details.append(
            {
                "baseline": label,
                "path": rel.replace("\\", "/"),
                "present": present,
                "expectedSha256": expected,
                "actualSha256": actual,
                "match": match,
                "mutation": "DENY",
            }
        )

    gates["SEALED_BASELINE_MUTATION"] = "DENY"
    gates["LIMITATION_AUTO_CLEAR"] = "DENY"
    gates["PRODUCTION"] = "NO-GO"

    hard_fails = [k for k, v in gates.items() if v == "FAIL"]
    verdict = "PASS" if not hard_fails else "FAIL"
    return {
        "verdict": verdict,
        "gates": gates,
        "hardFails": hard_fails,
        "details": details,
        "notes": notes,
        "parameterHash": parameter_hash(),
    }
