"""Expression state → eye reaction targets (intensity-scaled, Neutral-relative)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .parameters import GATE5_PARAMETERS


@dataclass
class EyeReactionTarget:
    state: str
    intensity: float
    speech_active: bool
    sentence_boundary: bool
    phase: str  # HOLD | AUX | RETURN
    gaze_yaw: float  # normalized [-1,1] within safe ellipse
    gaze_pitch: float
    blink_amount: float  # Gate4B validated [0,1]
    lower_lid_raise: float  # share of lower travel, clamped
    blink_suppress: float
    openness: float


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def resolve_reaction(
    *,
    state: str,
    intensity: float,
    speech_active: bool = False,
    sentence_boundary: bool = False,
    phase: str = "HOLD",
) -> EyeReactionTarget:
    state = str(state).upper()
    if state not in GATE5_PARAMETERS["recipes"]:
        raise ValueError(f"Unsupported expressionState: {state}")
    inten = _clamp01(intensity)
    base = GATE5_PARAMETERS["recipes"]["NEUTRAL"]
    rec = GATE5_PARAMETERS["recipes"][state]
    lid = GATE5_PARAMETERS["lid"]

    def lerp(a, b):
        return float(a) + (float(b) - float(a)) * inten

    yaw = lerp(base["gazeYaw"], rec["gazeYaw"])
    pitch = lerp(base["gazePitch"], rec["gazePitch"])
    openness = lerp(base["openness"], rec["openness"])
    lower_raise = lerp(base["lowerLidRaise"], rec["lowerLidRaise"])
    blink_amt = lerp(base["blinkAmount"], rec["blinkAmount"])
    suppress = lerp(base.get("blinkSuppress", 0.0), rec.get("blinkSuppress", 0.0))

    # Aux / return phases for Explaining & Thinking
    aux = rec.get("auxGlance")
    if phase == "AUX" and aux:
        yaw = float(aux.get("yaw", yaw)) * inten * float(GATE5_PARAMETERS["gaze"]["auxScale"])
        pitch = float(aux.get("pitch", pitch)) * inten * float(GATE5_PARAMETERS["gaze"]["auxScale"])
    elif phase == "RETURN":
        yaw = 0.0
        pitch = 0.0

    # Focus: damp residual gaze offsets (stability)
    if state == "FOCUS":
        scale = float(GATE5_PARAMETERS["gaze"]["focusMotionScale"])
        # intensity increases lock — reduce off-target wander baked into recipe (already 0)
        yaw *= scale + (1.0 - scale) * (1.0 - inten)
        pitch *= scale + (1.0 - scale) * (1.0 - inten)

    # Openness → additional blink (less open = more lid close), within validated max
    close_from_open = max(0.0, 1.0 - max(float(lid["minOpenness"]), openness))
    blink_amt = max(blink_amt, close_from_open)
    blink_amt = min(blink_amt, float(lid["maxBlinkAmount"]))

    # Speaking: suppress blink unless sentence boundary
    if state == "SPEAKING" or speech_active:
        if speech_active and not sentence_boundary:
            blink_amt *= max(0.0, 1.0 - suppress)
        elif sentence_boundary:
            sb = float(rec.get("sentenceBoundaryBlink", 0.45)) * inten
            blink_amt = max(blink_amt, sb * (1.0 - 0.5 * suppress))

    lower_raise = min(lower_raise, float(lid["maxLowerRaiseShare"]))

    # Clamp gaze to unit disk
    rn = yaw * yaw + pitch * pitch
    if rn > 1.0:
        s = rn ** 0.5
        yaw /= s
        pitch /= s

    return EyeReactionTarget(
        state=state,
        intensity=inten,
        speech_active=bool(speech_active),
        sentence_boundary=bool(sentence_boundary),
        phase=phase,
        gaze_yaw=float(yaw),
        gaze_pitch=float(pitch),
        blink_amount=float(_clamp01(blink_amt)),
        lower_lid_raise=float(_clamp01(lower_raise)),
        blink_suppress=float(_clamp01(suppress)),
        openness=float(_clamp01(openness)),
    )


def blend_reactions(a: EyeReactionTarget, b: EyeReactionTarget, t: float) -> EyeReactionTarget:
    t = _clamp01(t)

    def L(x, y):
        return float(x) + (float(y) - float(x)) * t

    yaw, pitch = L(a.gaze_yaw, b.gaze_yaw), L(a.gaze_pitch, b.gaze_pitch)
    rn = yaw * yaw + pitch * pitch
    if rn > 1.0:
        s = rn ** 0.5
        yaw /= s
        pitch /= s
    return EyeReactionTarget(
        state=b.state if t >= 0.5 else a.state,
        intensity=L(a.intensity, b.intensity),
        speech_active=b.speech_active if t >= 0.5 else a.speech_active,
        sentence_boundary=b.sentence_boundary if t >= 0.5 else a.sentence_boundary,
        phase=b.phase if t >= 0.5 else a.phase,
        gaze_yaw=yaw,
        gaze_pitch=pitch,
        blink_amount=_clamp01(L(a.blink_amount, b.blink_amount)),
        lower_lid_raise=_clamp01(L(a.lower_lid_raise, b.lower_lid_raise)),
        blink_suppress=_clamp01(L(a.blink_suppress, b.blink_suppress)),
        openness=_clamp01(L(a.openness, b.openness)),
    )
