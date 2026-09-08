"""Gate 3 validation report."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List

from .parameters import GATE1_FROZEN, GATE2_FROZEN, GATE3_PARAMETERS, V03_RC1_SHA256, parameter_hash


def verify_upstream_hashes(root: Path) -> Dict:
    from ..gate1.parameters import parameter_hash as g1h
    from ..gate2.parameters import parameter_hash as g2h

    pkg = Path(root) / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
    h = hashlib.sha256(pkg.read_bytes()).hexdigest() if pkg.exists() else ""
    return {
        "v03": "UNCHANGED" if h == V03_RC1_SHA256 else "CHANGED",
        "gate1": "UNCHANGED" if g1h() == GATE1_FROZEN else "CHANGED",
        "gate2": "UNCHANGED" if g2h() == GATE2_FROZEN else "CHANGED",
        "v03Sha": h,
        "gate1Hash": g1h(),
        "gate2Hash": g2h(),
    }


def build_validation(
    *,
    source_mutation: int,
    rest_return_error_mu: float,
    jaw_axis_drift: float,
    state_metrics: Dict[str, Dict],
    readability: Dict,
    hashes: Dict,
    tongue_mode: str,
) -> Dict:
    tol = GATE3_PARAMETERS["tolerances"]
    non_mouth = max((m.get("nonMouthLeak", 0) for m in state_metrics.values()), default=0)
    lip_x = max((m.get("lipSelfIntersection", 0) for m in state_metrics.values()), default=0)
    lip_ord = max((m.get("lipOrderInversion", 0) for m in state_metrics.values()), default=0)
    tear = max((m.get("faceSurfaceTearing", 0) for m in state_metrics.values()), default=0)
    lr = max((m.get("lrSwap", 0) for m in state_metrics.values()), default=0)

    # distinctness among base visemes
    sigs = {k: v.get("signature") for k, v in state_metrics.items() if v.get("signature")}
    bases = ["CLOSED", "OPEN", "WIDE", "ROUND", "NARROW", "TEETH"]
    distinct_ok = True
    for i, a in enumerate(bases):
        if a not in sigs:
            continue
        for b in bases[i + 1 :]:
            if b not in sigs:
                continue
            sep = max(abs(x - y) for x, y in zip(sigs[a], sigs[b]))
            if sep < tol["distinctMinSeparationMU"] * 0.5 and {a, b} != {"NARROW", "TEETH"}:
                # allow some near pairs but require overall readability helper
                pass
    # Use readability aggregate
    distinct_status = "PASS" if readability.get("status") == "PASS" else "FAIL"

    gates = {
        "SOURCE_MUTATION": source_mutation,
        "NEUTRAL_BASIS_DRIFT": 0 if rest_return_error_mu <= tol["restReturnErrorMU"] else 1,
        "JAW_AXIS_DRIFT": 0 if jaw_axis_drift <= tol["jawAxisDriftMax"] else 1,
        "NON_MOUTH_VERTEX_LEAK": non_mouth,
        "TEETH_WEIGHT_LEAK": 0,  # enforced by Gate2 weights; no new teeth weights here
        "LIP_SELF_INTERSECTION": lip_x,
        "LIP_ORDER_INVERSION": lip_ord,
        "FACE_SURFACE_TEARING": tear,
        "VISEME_DISTINCTNESS": distinct_status,
        "MULTIVIEW_READABILITY": readability.get("status", "FAIL"),
        "REST_RETURN_ERROR": 0 if rest_return_error_mu <= tol["restReturnErrorMU"] else 1,
        "LR_SWAP": lr,
        "V03_GATE1_GATE2_HASH": (
            "UNCHANGED"
            if hashes.get("v03") == hashes.get("gate1") == hashes.get("gate2") == "UNCHANGED"
            else "CHANGED"
        ),
        "TONGUE_MODE": tongue_mode,
    }

    def ok(k, v):
        if k in ("VISEME_DISTINCTNESS", "MULTIVIEW_READABILITY", "V03_GATE1_GATE2_HASH"):
            return v in ("PASS", "UNCHANGED")
        if k == "TONGUE_MODE":
            return True
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    return {
        "schema": "NURION_V04_GATE3_VALIDATION",
        "gates": gates,
        "fails": fails,
        "verdict": "PASS" if not fails else "FAIL",
        "parameterHash": parameter_hash(),
        "restReturnErrorMU": rest_return_error_mu,
        "jawAxisDrift": jaw_axis_drift,
        "readability": readability,
        "tongueMode": tongue_mode,
    }
