"""v0.6 Production Readiness Gate 1 — deployment scope & supported assets."""

from __future__ import annotations

import hashlib
import json

# Sealed v0.6 baseline (immutable for this track)
V06_RC1_PACKAGE = "NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
V06_RC1_SHA256 = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"
V06_BASELINE_ROLE = "OFFICIAL_READONLY_BASELINE"
V06_SEAL_VERDICT = "SEALED_WITH_LIMITATIONS"

V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V05_RC1_SHA256 = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"

INHERITED_LIMITATIONS = [
    "FOOT_SLIDE_RESIDUAL_11",
    "SHALLOW_SUSTAINED_CONTACT_ACCEPTED",
    "GATE3_REVERSE_FOREARM_MILD_PRESERVED",
    "HOLDOUT_FOOT_SLIDE_9",
]

GATE1_PARAMETERS = {
    "schema": "NURION_V06_PR_GATE1_DEPLOYMENT_SCOPE_PARAMETERS",
    "version": "0.6.0-pr-gate1",
    "track": "Production Readiness",
    "product": "NURION Unified Character Animation Runtime",
    "sealedBaseline": {
        "version": "v0.6",
        "verdict": V06_SEAL_VERDICT,
        "SEALED": True,
        "baselineRole": V06_BASELINE_ROLE,
        "package": V06_RC1_PACKAGE,
        "sha256": V06_RC1_SHA256,
        "mutation": "DENY",
        "repack": "DENY",
        "inPlaceRepair": "DENY",
    },
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "immediateProductionGoReview": "DENY",
    "deploymentScope": {
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "blenderVersions": ["5.0.1"],
        "os": ["Windows_10_plus"],
        "runtimeCollection": "NURION_UnifiedRuntime",
        "exportFormats": ["BLEND", "FBX", "GLB"],
        "fps": [24, 30, 60],
        "workflow": [
            "SELECT_CHARACTER",
            "ANALYZE_ASSET",
            "BUILD_UNIFIED_RUNTIME",
            "APPLY_MOTION_PRESET",
            "VALIDATE_RUNTIME",
            "EXPORT",
        ],
        "partialExportPublish": "DENY",
        "unvalidatedExport": "DENY",
        "orderViolation": "SAFE_ABORT",
    },
    "supportedAssetClasses": {
        "FULL": {
            "runtimeAction": "APPLY",
            "notes": "All body/face/eye/lipsync/motion paths available — none observed in v0.6 sealed evidence set.",
        },
        "LIMITED": {
            "runtimeAction": "APPLY_LIMITED",
            "requiredPublicDisclosure": [
                "inheritedLimitations",
                "REST_FALLBACK_when_lipsync_unsupported",
                "missingPreset_ABSTAIN",
            ],
        },
        "INELIGIBLE": {
            "runtimeAction": "ABSTAIN",
            "forceApply": "DENY",
        },
    },
    "supportedCharacterEvidence": [
        {
            "label": "ai-aba.bow",
            "meshyFamily": "Silver_Starlight_Sent",
            "class": "LIMITED",
            "presetsAvailable": ["Formal_Bow", "Idle"],
            "presetsAbstain": ["Gentlemans_Bow"],
            "lipsyncMode": "REST_FALLBACK",
            "role": "SEED_DEVELOPMENT",
        },
        {
            "label": "ai-baeby",
            "meshyFamily": "Lightning_Pilot",
            "class": "LIMITED",
            "presetsAvailable": ["Formal_Bow"],
            "presetsAbstain": ["Idle", "Gentlemans_Bow"],
            "lipsyncMode": "REST_FALLBACK",
            "role": "V05_HOLDOUT_CROSSCHECK",
        },
        {
            "label": "hyerie",
            "meshyFamily": "hyerie",
            "class": "LIMITED",
            "presetsAvailable": [],
            "presetsAbstain": ["Formal_Bow", "Idle", "Gentlemans_Bow"],
            "lipsyncMode": "REST_FALLBACK",
            "role": "V03_CROSSCHECK",
        },
        {
            "label": "ai-aba.15",
            "meshyFamily": "Silver_Starlight_Sent",
            "class": "LIMITED",
            "presetsAvailable": ["Idle"],
            "presetsAbstain": ["Formal_Bow", "Gentlemans_Bow"],
            "lipsyncMode": "REST_FALLBACK",
            "role": "IDLE_PRESET_SOURCE",
        },
        {
            "label": "AILAWFRIEND",
            "meshyFamily": "AI_법률_파트너",
            "class": "LIMITED",
            "presetsAvailable": ["Idle"],
            "presetsAbstain": ["Formal_Bow", "Gentlemans_Bow"],
            "lipsyncMode": "REST_FALLBACK",
            "role": "V06_FRESH_HOLDOUT",
            "zipSha256": "aaf39c897f32baefe7083eb5bae5a107c5b934981773b717549b239321b18e0b",
            "fbxSha256": "0135661b51ad6acee657b6a2cf07f3d92ca72903c686a7246c1638e8c8e19927",
        },
        {
            "label": "empty-control",
            "class": "INELIGIBLE",
            "runtimeAction": "ABSTAIN",
            "role": "NEGATIVE_CONTROL",
        },
    ],
    "submissionFormRequired": "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP",
    "unsupportedOrAbstain": {
        "missingMotionPreset": "ABSTAIN",
        "gentlemansBowWithoutSource": "ABSTAIN",
        "lipsyncUnsupported": "REST_FALLBACK",
        "ineligibleAsset": "ABSTAIN",
        "siblingZipMix": "DENY",
        "textureOnlyUnriggedZip": "INELIGIBLE",
    },
    "publicLimitations": INHERITED_LIMITATIONS,
    "limitationAutoClear": "DENY",
    "outOfScopeForImmediateGo": [
        "FULL_UNRESTRICTED_PRODUCTION",
        "AUTO_CLEAR_LIMITATIONS",
        "FORCE_UNSUPPORTED_PRESETS",
        "LIPSYNC_INVENTION_WITHOUT_EVIDENCE",
    ],
    "readonlyDependencies": {
        "v0.3": V03_RC1_SHA256,
        "v0.4": V04_RC1_SHA256,
        "v0.5": V05_RC1_SHA256,
        "v0.6": V06_RC1_SHA256,
    },
    "nextGates": [
        "PR_GATE2_FAILURE_ABSTAIN_RECOVERY_POLICY",
        "PR_GATE3_BLENDER_INSTALL_UPDATE_REMOVE_SMOKE",
        "PR_GATE4_LONGEVITY_MEMORY_PERFORMANCE",
        "PR_GATE5_EXPORT_COMPAT_SECURITY",
        "PR_GATE6_OPS_DOCS_LIMITATIONS_UI",
        "PR_GATE7_PRODUCTION_READINESS_HOLDOUT",
        "PR_GATE8_FINAL_GO_CONDITIONAL_GO_NO_GO",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE1_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
