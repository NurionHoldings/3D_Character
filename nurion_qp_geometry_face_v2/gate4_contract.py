"""Gate 4 — controlled isolated integration contract (Identity Core not replaced)."""
from __future__ import annotations

import hashlib
import json


GATE4_CONTRACT = {
    "schema": "NURION_V07_QP_GF_FACE_V2_GATE4_CONTRACT_V1",
    "gate": 4,
    "purpose": "ISOLATED_ADAPTER_BIND_GEOMETRY_FIRST_V2_WITHOUT_REPLACING_FROZEN_IDENTITY_CORE",
    "gate3OfficialParameterHash": "160662e0a954643883be1ae154817cffabf83fced2a429bce63f47ddbb936f5e",
    "gate2OfficialParameterHash": "93d87283d3a5492d6c2773f46122f4d32cce63026bfa77f111a956fd4345fc60",
    "integration": {
        "mode": "ISOLATED_ADAPTER",
        "replaceFrozenIdentityCore": "DENY",
        "mutateQuickProfileCore": "DENY",
        "mutateGate3Runner": "DENY",
        "legacyHeuristicAsExistenceGate": "BYPASS_ON_ADAPTER_PATH",
        "legacyIdentityCorePath": "READ_ONLY_COMPARISON_ONLY",
        "geometryFirstIdentityPreview": "OPTIONAL_RATIO_MAP_NOT_LEGACY_HASH",
        "characterGeneration": "DENY",
        "advancesGate3Execute": "DENY",
    },
    "heuristics": {
        "skinColorExistenceGate": "BYPASS",
        "centerOccupancyExistenceGate": "BYPASS",
        "NO_DETECTABLE_FACE_from_skin_center": "MUST_NOT_BLOCK_ADAPTER_PATH",
        "blurAndSizeGates": "RETAINED_PRECHECK_ONLY",
    },
    "abstainPolicy": {
        "geometryFailure": "ABSTAIN_RECAPTURE_NO_FABRICATION",
        "branchConflict": "ABSTAIN_RECAPTURE_NO_FABRICATION",
        "identityValuesOnAbstain": "DENY",
        "partialDraftOnAbstain": "DENY",
    },
    "validation": {
        "synthetic": "REQUIRED",
        "nonParticipantFixture": "REQUIRED",
        "realParticipantP001P002P003": "DENY",
        "threeRunDeterminism": "REQUIRED",
        "legacyHeuristicFalseAbstainRegression": "REQUIRED",
        "abstainNoFabricationRegression": "REQUIRED",
    },
    "baseline": {
        "quickProfileGate2CoreMutation": 0,
        "quickProfileGate3RunnerMutation": 0,
        "gate8Mutation": 0,
        "gate3AnalyzerMutation": 0,
        "production": "NO-GO",
    },
    "runtime": {
        "network": "DENY",
        "modelShaVerificationBeforeLoad": "REQUIRED",
    },
    "nextAfterPass": "SEPARATE_APPROVAL_FOR_P001_P003_REAL_RERUN",
}


def gate4_parameter_hash() -> str:
    raw = json.dumps(GATE4_CONTRACT, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
