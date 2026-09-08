"""v0.6 Gate 3 — unified bone mapping parameters (Gate 1·2 frozen)."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_unified_runtime.gate1.parameters import INHERITED_V05_LIMITATIONS

GATE1_PARAMETER_HASH_FROZEN = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"
GATE2_PARAMETER_HASH_FROZEN = "b5d3c4931d1ef65a64844483e51bb74d6edcfcb9f90de28abe1c47192c85df6e"

# Standard role -> ordered name aliases (first exact/casefold match wins)
ROLE_ALIASES = {
    "HIPS": ["Hips", "Hip", "Pelvis", "mixamorig:Hips"],
    "SPINE_LOW": ["Spine02", "Spine2", "spine2", "Chest"],
    "SPINE_MID": ["Spine01", "Spine1", "spine1"],
    "SPINE_UP": ["Spine", "spine", "Spine0"],
    "NECK": ["neck", "Neck"],
    "HEAD": ["Head", "head"],
    "L_SHOULDER": ["LeftShoulder", "Left_Shoulder", "shoulder.L", "Shoulder.L"],
    "L_UPPER_ARM": ["LeftArm", "Left_Arm", "UpperArm.L", "upperarm.L"],
    "L_FOREARM": ["LeftForeArm", "Left_ForeArm", "ForeArm.L", "lowerarm.L"],
    "L_HAND": ["LeftHand", "Left_Hand", "Hand.L", "hand.L"],
    "R_SHOULDER": ["RightShoulder", "Right_Shoulder", "shoulder.R", "Shoulder.R"],
    "R_UPPER_ARM": ["RightArm", "Right_Arm", "UpperArm.R", "upperarm.R"],
    "R_FOREARM": ["RightForeArm", "Right_ForeArm", "ForeArm.R", "lowerarm.R"],
    "R_HAND": ["RightHand", "Right_Hand", "Hand.R", "hand.R"],
    "L_UP_LEG": ["LeftUpLeg", "Left_UpLeg", "Thigh.L", "UpperLeg.L"],
    "L_LEG": ["LeftLeg", "Left_Leg", "Calf.L", "LowerLeg.L"],
    "L_FOOT": ["LeftFoot", "Left_Foot", "Foot.L", "foot.L"],
    "L_TOE": ["LeftToeBase", "LeftToe", "Toe.L", "toe.L"],
    "R_UP_LEG": ["RightUpLeg", "Right_UpLeg", "Thigh.R", "UpperLeg.R"],
    "R_LEG": ["RightLeg", "Right_Leg", "Calf.R", "LowerLeg.R"],
    "R_FOOT": ["RightFoot", "Right_Foot", "Foot.R", "foot.R"],
    "R_TOE": ["RightToeBase", "RightToe", "Toe.R", "toe.R"],
}

# Eye attach uses Head when named eye bones are absent (Meshy biped).
EYE_ATTACH_ROLE = "HEAD"
EYE_BONE_ALIASES = ["Eye.L", "Eye.R", "LeftEye", "RightEye", "eye_L", "eye_R"]

REQUIRED_BODY_ROLES = [
    "HIPS",
    "SPINE_UP",
    "NECK",
    "HEAD",
    "L_UPPER_ARM",
    "R_UPPER_ARM",
    "L_FOREARM",
    "R_FOREARM",
    "L_UP_LEG",
    "R_UP_LEG",
    "L_LEG",
    "R_LEG",
    "L_FOOT",
    "R_FOOT",
]

CHAINS = {
    "spine": ["HIPS", "SPINE_LOW", "SPINE_MID", "SPINE_UP", "NECK", "HEAD"],
    "armL": ["L_SHOULDER", "L_UPPER_ARM", "L_FOREARM", "L_HAND"],
    "armR": ["R_SHOULDER", "R_UPPER_ARM", "R_FOREARM", "R_HAND"],
    "legL": ["L_UP_LEG", "L_LEG", "L_FOOT", "L_TOE"],
    "legR": ["R_UP_LEG", "R_LEG", "R_FOOT", "R_TOE"],
}

# Continuity-required chains (spine may skip optional middle spines if parent path still reaches)
AXIS_GATE_CHAINS = ["armL", "armR", "legL", "legR"]
LR_ROLE_PAIRS = [
    ["L_SHOULDER", "R_SHOULDER"],
    ["L_UPPER_ARM", "R_UPPER_ARM"],
    ["L_FOREARM", "R_FOREARM"],
    ["L_HAND", "R_HAND"],
    ["L_UP_LEG", "R_UP_LEG"],
    ["L_LEG", "R_LEG"],
    ["L_FOOT", "R_FOOT"],
    ["L_TOE", "R_TOE"],
]

GATE3_PARAMETERS = {
    "schema": "NURION_V06_GATE3_UNIFIED_BONE_MAPPING_PARAMETERS",
    "version": "0.6.0-gate3",
    "track": "Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "production": "NO-GO",
    "sourceCharacterMutation": "DENY",
    "sealedBaselineMutation": "DENY",
    "manualMapping": "DENY",
    "assetSpecificTuning": "DENY",
    "forceApplyWhenInsufficient": "DENY",
    "correctionTarget": "MAPPING_TABLE_ONLY",
    "determinismRuns": 3,
    "axisDotMin": 0.25,
    "lengthRelEps": 1e-5,
    "scaleUniformEps": 1e-4,
    "roleAliases": ROLE_ALIASES,
    "requiredBodyRoles": REQUIRED_BODY_ROLES,
    "chains": CHAINS,
    "axisGateChains": AXIS_GATE_CHAINS,
    "lrRolePairs": LR_ROLE_PAIRS,
    "eyeAttachRole": EYE_ATTACH_ROLE,
    "eyeBoneAliases": EYE_BONE_ALIASES,
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "limitationAutoClear": "DENY",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE3_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
