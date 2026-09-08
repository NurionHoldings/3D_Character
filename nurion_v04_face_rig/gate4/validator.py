"""Gate 4 validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict

from .parameters import GATE1_FROZEN, GATE2_FROZEN, GATE3_FROZEN, GATE4_PARAMETERS, V03_RC1_SHA256, parameter_hash


def verify_upstream(root: Path) -> Dict:
    from ..gate1.parameters import parameter_hash as g1h
    from ..gate2.parameters import parameter_hash as g2h
    from ..gate3.parameters import parameter_hash as g3h

    pkg = Path(root) / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
    h = hashlib.sha256(pkg.read_bytes()).hexdigest() if pkg.exists() else ""
    return {
        "v03": "UNCHANGED" if h == V03_RC1_SHA256 else "CHANGED",
        "gate1": "UNCHANGED" if g1h() == GATE1_FROZEN else "CHANGED",
        "gate2": "UNCHANGED" if g2h() == GATE2_FROZEN else "CHANGED",
        "gate3": "UNCHANGED" if g3h() == GATE3_FROZEN else "CHANGED",
    }


def build_validation(
    *,
    source_mutation: int,
    order: Dict,
    fps: Dict,
    pops: Dict,
    safety: Dict,
    rest_return_error: float,
    hashes: Dict,
    readability: str,
) -> Dict:
    gates = {
        "SOURCE_MUTATION": source_mutation,
        "GATE1_3_HASH": (
            "UNCHANGED"
            if hashes.get("v03")
            == hashes.get("gate1")
            == hashes.get("gate2")
            == hashes.get("gate3")
            == "UNCHANGED"
            else "CHANGED"
        ),
        "PHONEME_ORDER_ERROR": order.get("phonemeOrderError", 99),
        "MISSING_SHORT_PHONEME": order.get("missingShortPhoneme", 99),
        "TIMELINE_OVERLAP_CONFLICT": order.get("timelineOverlapConflict", 99),
        "WEIGHT_SUM_OVERFLOW": safety.get("weightOverflow", 99),
        "LIP_INTERSECTION": safety.get("lipIntersection", 99),
        "LIP_ORDER_INVERSION": safety.get("lipOrderInversion", 99),
        "NON_MOUTH_VERTEX_LEAK": safety.get("nonMouthLeak", 99),
        "ABRUPT_TRANSITION_POP": pops.get("abruptTransitionPop", 99),
        "MULTIVIEW_READABILITY": readability,
        "FPS_24_30_60_SEMANTIC_CONSISTENCY": fps.get("status", "FAIL"),
        "REST_RETURN_ERROR": 0 if rest_return_error <= 1e-4 else 1,
    }

    def ok(k, v):
        if k in ("GATE1_3_HASH", "MULTIVIEW_READABILITY", "FPS_24_30_60_SEMANTIC_CONSISTENCY"):
            return v in ("PASS", "UNCHANGED")
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    return {
        "schema": "NURION_V04_GATE4_VALIDATION",
        "gates": gates,
        "fails": fails,
        "verdict": "PASS" if not fails else "FAIL",
        "parameterHash": parameter_hash(),
        "fpsDetails": fps,
        "popDetails": pops,
    }
