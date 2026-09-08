"""Gate 5B validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List

from .parameters import (
    GATE1_FROZEN,
    GATE2_FROZEN,
    GATE3_FROZEN,
    GATE4_FROZEN,
    GATE5A_FROZEN,
    GATE5B_PARAMETERS,
    V03_RC1_SHA256,
    parameter_hash,
)


def verify_upstream(root: Path) -> Dict:
    from nurion_v04_face_rig.gate1.parameters import parameter_hash as g1h
    from nurion_v04_face_rig.gate2.parameters import parameter_hash as g2h
    from nurion_v04_face_rig.gate3.parameters import parameter_hash as g3h
    from nurion_v04_face_rig.gate4.parameters import parameter_hash as g4h
    from nurion_v04_face_rig.gate5a.parameters import parameter_hash as g5ah

    pkg = Path(root) / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
    h = hashlib.sha256(pkg.read_bytes()).hexdigest() if pkg.exists() else ""
    return {
        "v03": "UNCHANGED" if h == V03_RC1_SHA256 else "CHANGED",
        "gate1": "UNCHANGED" if g1h() == GATE1_FROZEN else "CHANGED",
        "gate2": "UNCHANGED" if g2h() == GATE2_FROZEN else "CHANGED",
        "gate3": "UNCHANGED" if g3h() == GATE3_FROZEN else "CHANGED",
        "gate4": "UNCHANGED" if g4h() == GATE4_FROZEN else "CHANGED",
        "gate5a": "UNCHANGED" if g5ah() == GATE5A_FROZEN else "CHANGED",
        "gate5bSelf": parameter_hash(),
    }


def build_validation(
    *,
    source_mutation: int,
    metrics_agg: Dict,
    fps_status: str,
    pops: int,
    rest_return_error: float,
    hashes: Dict,
    readability: str,
    sync_status: str,
    range_mismatch: int,
    determinism: str,
) -> Dict:
    gate_hash = (
        "UNCHANGED"
        if all(hashes.get(k) == "UNCHANGED" for k in ("v03", "gate1", "gate2", "gate3", "gate4", "gate5a"))
        else "CHANGED"
    )
    gates = {
        "SOURCE_MUTATION": source_mutation,
        "GATE1_5A_HASH": gate_hash,
        "AUDIO_ACTION_RANGE_MISMATCH": range_mismatch,
        "SILENCE_FALSE_MOTION": int(metrics_agg.get("silenceFalseMotion", 0)),
        "SHORT_PHONEME_LOSS": int(metrics_agg.get("shortPhonemeLoss", 0)),
        "CLOSED_CONSONANT_SEAL_LOSS": int(metrics_agg.get("closedConsonantSealLoss", 0)),
        "WEIGHT_SUM_OVERFLOW": int(metrics_agg.get("weightOverflow", 0)),
        "LOW_CONFIDENCE_OVERDRIVE": int(metrics_agg.get("lowConfidenceOverdrive", 0)),
        "LIP_INTERSECTION": int(metrics_agg.get("lipIntersection", 0)),
        "LIP_ORDER_INVERSION": int(metrics_agg.get("lipOrderInversion", 0)),
        "NON_MOUTH_VERTEX_LEAK": int(metrics_agg.get("nonMouthLeak", 0)),
        "ABRUPT_TRANSITION_POP": int(pops),
        "AUDIO_VISEME_SYNC": sync_status,
        "MULTIVIEW_READABILITY": readability,
        "FPS_24_30_60_CONSISTENCY": fps_status,
        "REST_RETURN_ERROR": 0 if rest_return_error <= float(GATE5B_PARAMETERS["restReturnMu"]) else 1,
        "DETERMINISM_3X": determinism,
    }

    def ok(k, v):
        if k in (
            "GATE1_5A_HASH",
            "AUDIO_VISEME_SYNC",
            "MULTIVIEW_READABILITY",
            "FPS_24_30_60_CONSISTENCY",
            "DETERMINISM_3X",
        ):
            return v in ("PASS", "UNCHANGED")
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    return {
        "schema": "NURION_V04_GATE5B_VALIDATION",
        "gates": gates,
        "fails": fails,
        "verdict": "PASS" if not fails else "FAIL",
        "parameterHash": parameter_hash(),
    }
