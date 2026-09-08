"""Gate5B safety contract — confidence/intensity separation without mutating Gate5B params."""

from __future__ import annotations

from typing import Dict, List

from nurion_v04_face_rig.gate4.phoneme_map import class_for
from nurion_v04_face_rig.gate5b.confidence_policy import classify_confidence

from .parameters import GATE5A2_PARAMETERS


def _merge_sil(phonemes: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    for p in phonemes:
        if out and p["symbol"] == "SIL" and out[-1]["symbol"] == "SIL":
            out[-1]["endMs"] = max(int(out[-1]["endMs"]), int(p["endMs"]))
            continue
        out.append(dict(p))
    return out


def _ensure_min_hold(phonemes: List[Dict]) -> List[Dict]:
    """Keep consumer non-SIL phones long enough for Gate5B sampling (no locked-param change)."""
    min_map = GATE5A2_PARAMETERS["phonemeDurationMinMs"]
    step = 10
    out = [dict(p) for p in phonemes]
    for i, p in enumerate(out):
        if p["symbol"] == "SIL":
            continue
        need = max(step + 1, int(min_map.get(class_for(p["symbol"]), 35)))
        dur = int(p["endMs"]) - int(p["startMs"])
        if dur >= need:
            continue
        grow = need - dur
        # grow forward into following SIL when possible
        if i + 1 < len(out) and out[i + 1]["symbol"] == "SIL":
            take = min(grow, int(out[i + 1]["endMs"]) - int(out[i + 1]["startMs"]) - 1)
            if take > 0:
                out[i]["endMs"] = int(out[i]["endMs"]) + take
                out[i + 1]["startMs"] = int(out[i]["endMs"])
                grow -= take
        if grow > 0 and i > 0 and out[i - 1]["symbol"] == "SIL":
            take = min(grow, int(out[i - 1]["endMs"]) - int(out[i - 1]["startMs"]) - 1)
            if take > 0:
                out[i]["startMs"] = int(out[i]["startMs"]) - take
                out[i - 1]["endMs"] = int(out[i]["startMs"])
    # drop empty SIL
    cleaned = []
    for p in out:
        if int(p["endMs"]) > int(p["startMs"]):
            cleaned.append(p)
    return _merge_sil(cleaned)


def apply_gate5b_safety_contract(phonemes: List[Dict]) -> List[Dict]:
    """
    Preserve alignment evidence; emit Gate5B-safe consumer timeline.

    LOW / INSUFFICIENT alignment tiers become SIL for the consumer so locked Gate5B
    cannot accumulate neighbor-coarticulation magnitude inside low-confidence windows
    (structural LOW_CONFIDENCE_OVERDRIVE = 0).
    """
    cfg = GATE5A2_PARAMETERS["gate5bSafetyContract"]
    if not cfg.get("enabled", True):
        return [dict(p) for p in phonemes]
    field = str(cfg.get("preserveAlignmentConfidenceField") or "alignmentConfidence")
    out: List[Dict] = []
    for p in phonemes:
        q = dict(p)
        align = float(p.get("confidence", 1.0))
        q[field] = align
        q["alignedSymbol"] = p.get("symbol")
        if p.get("symbol") == "SIL":
            q["confidence"] = 1.0
            q["intensityTier"] = "HIGH"
            out.append(q)
            continue
        tier, _ = classify_confidence(align)
        q["intensityTier"] = tier
        if tier == "HIGH":
            q["confidence"] = max(0.75, align)
        elif tier == "MEDIUM":
            q["confidence"] = 0.60
        else:
            # LOW + INSUFFICIENT → REST for locked Gate5B consumer
            q["symbol"] = "SIL"
            q["confidence"] = 1.0
            q["rule"] = "SAFE_REST_LOW_OR_INSUFFICIENT"
            q["intensityTier"] = tier
        out.append(q)
    return _ensure_min_hold(_merge_sil(out))
