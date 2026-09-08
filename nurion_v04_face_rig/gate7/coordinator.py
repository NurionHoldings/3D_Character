"""Conflict coordinator — priority-based attenuation across face channels."""

from __future__ import annotations

from typing import Dict, List, Tuple

from nurion_v04_face_rig.gate4.phoneme_map import class_for

from .parameters import GATE7_PARAMETERS


def active_phoneme(phonemes: List[Dict], t_ms: float) -> Dict:
    for p in phonemes:
        if float(p["startMs"]) <= t_ms < float(p["endMs"]):
            return p
    if phonemes:
        return phonemes[-1]
    return {"symbol": "SIL", "confidence": 1.0, "startMs": 0, "endMs": 0}


def is_rest_fallback(p: Dict) -> bool:
    if p.get("symbol") == "SIL" and p.get("rule") == "SAFE_REST_LOW_OR_INSUFFICIENT":
        return True
    if p.get("symbol") == "SIL" and p.get("alignedSymbol") and p.get("alignedSymbol") != "SIL":
        return True
    tier = str(p.get("intensityTier") or "")
    return tier in ("LOW", "INSUFFICIENT") and p.get("symbol") == "SIL"


def sentence_boundary(phonemes: List[Dict], t_ms: float, window_ms: float = 120.0) -> bool:
    """True near SIL gaps that look like pauses / ends."""
    for i, p in enumerate(phonemes):
        if p["symbol"] != "SIL":
            continue
        if int(p["endMs"]) - int(p["startMs"]) < 80:
            continue
        if abs(t_ms - float(p["startMs"])) <= window_ms or abs(t_ms - float(p["endMs"])) <= window_ms:
            return True
        # mid of long SIL
        if float(p["startMs"]) < t_ms < float(p["endMs"]):
            return True
    return False


def coordinate(
    *,
    phonemes: List[Dict],
    t_ms: float,
    mouth_axes: Dict[str, float],
    expression_state: str,
    expression_intensity: float,
    speech_active: bool,
) -> Dict:
    """
    Returns coordinated channel scales/targets.
    Priority: mesh safety > closed lip > viseme sync > blink > gaze > expression > micro.
    """
    p = active_phoneme(phonemes, t_ms)
    cls = class_for(p.get("symbol", "SIL"))
    rest_fb = is_rest_fallback(p) or (p.get("symbol") == "SIL" and not speech_active and expression_state != "SPEAKING")
    boundary = sentence_boundary(phonemes, t_ms)

    expr_scale = float(expression_intensity)
    state = expression_state.upper()

    # Lip sync wins during speech
    if speech_active or state == "SPEAKING":
        expr_scale *= float(GATE7_PARAMETERS["speakingExpressionScale"])
        if cls == "CLOSED":
            expr_scale *= float(GATE7_PARAMETERS["closedConsonantExpressionScale"])
        # FRIENDLY_SMILE headroom vs lipWide/lipClose
        if state == "FRIENDLY_SMILE":
            close = abs(float(mouth_axes.get("lipClose", 0.0)))
            wide = abs(float(mouth_axes.get("lipWide", 0.0)))
            if close > 0.25 or wide > 0.5:
                expr_scale *= float(GATE7_PARAMETERS["smileVisemeHeadroom"])

    if rest_fb:
        # preserve REST mouth; keep eyes mild
        mouth_axes = {}
        if state not in ("NEUTRAL", "EMPATHY", "FOCUS"):
            state = "SPEAKING" if speech_active else "NEUTRAL"
        expr_scale = min(expr_scale, 0.35)

    # Blink policy
    allow_blink = True
    if speech_active and not boundary:
        allow_blink = state in ("EMPATHY",)  # slow empathy blink only
        blink_scale = 0.35 if state == "EMPATHY" else 0.0
    else:
        blink_scale = 1.0 if boundary or state in ("NEUTRAL", "EMPATHY") else 0.5

    # Gaze: user-facing default; aux only for EXPLAINING on long holds
    gaze_mode = "USER"
    if state == "FOCUS":
        gaze_mode = "LOCK"
    elif state == "EXPLAINING" and speech_active and int(t_ms) % 900 < 120:
        gaze_mode = "AUX_SHORT"
    elif state == "EXPLAINING":
        gaze_mode = "USER"

    return {
        "tMs": t_ms,
        "phoneme": p.get("symbol"),
        "class": cls,
        "restFallback": rest_fb,
        "sentenceBoundary": boundary,
        "mouthAxes": mouth_axes,
        "expressionState": state,
        "expressionIntensity": max(0.0, min(1.0, expr_scale)),
        "speechActive": speech_active,
        "allowBlink": allow_blink,
        "blinkScale": blink_scale,
        "gazeMode": gaze_mode,
        "gradeTag": "SUPPORTED_WITH_FALLBACK" if rest_fb else "SUPPORTED",
    }
