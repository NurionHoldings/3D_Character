"""Confidence tier → deformation intensity (does not mutate Gate5A confidence values)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .parameters import GATE5B_PARAMETERS


def classify_confidence(confidence: float) -> Tuple[str, float]:
    tiers = GATE5B_PARAMETERS["confidenceTiers"]
    c = float(confidence)
    if c >= float(tiers["HIGH"]["min"]):
        return "HIGH", float(tiers["HIGH"]["scale"])
    if c >= float(tiers["MEDIUM"]["min"]):
        return "MEDIUM", float(tiers["MEDIUM"]["scale"])
    if c >= float(tiers["LOW"]["min"]):
        return "LOW", float(tiers["LOW"]["scale"])
    return "INSUFFICIENT", float(tiers["INSUFFICIENT"]["scale"])


def prepare_solver_phonemes(phonemes: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Build solver copies. Original confidence fields on input are never written back.
    Returns (solver_phonemes, attenuation_log).
    """
    solver: List[Dict] = []
    log: List[Dict] = []
    safe_jaw = float(GATE5B_PARAMETERS["insufficientSafeJaw"])
    for p in phonemes:
        orig_conf = float(p.get("confidence", 1.0))
        tier, scale = classify_confidence(orig_conf)
        q = {
            "symbol": p["symbol"],
            "startMs": int(p["startMs"]),
            "endMs": int(p["endMs"]),
            "confidence": float(scale),
            "_origConfidence": orig_conf,
            "_tier": tier,
            "_intensity": float(scale),
        }
        if p["symbol"] == "SIL":
            q["confidence"] = 1.0
            q["_tier"] = "HIGH"
            q["_intensity"] = 1.0
        elif tier == "INSUFFICIENT":
            q["confidence"] = 0.0
            q["_safeJaw"] = safe_jaw
        solver.append(q)
        if tier in ("MEDIUM", "LOW", "INSUFFICIENT") and p["symbol"] != "SIL":
            log.append(
                {
                    "symbol": p["symbol"],
                    "startMs": int(p["startMs"]),
                    "endMs": int(p["endMs"]),
                    "origConfidence": orig_conf,
                    "tier": tier,
                    "intensityScale": float(scale),
                }
            )
    return solver, log
