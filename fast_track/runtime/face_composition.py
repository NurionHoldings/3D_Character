"""FAST-HR10 — Face Composition Layer (Expression + Lip Sync → FACE weights).

Composition Policy (locked):
- EYE/BROW/CHEEK: Expression owns
- SPEECH primitives: LipSync owns
- SMILE/FROWN: Expression base + speech attenuation
- Final: normalize/clamp 0..1, deterministic
"""

from __future__ import annotations

from typing import Any

from fast_track.runtime.canonical_facial_actuator import CanonicalFacialActuator
from fast_track.runtime.expression_mixer import ExpressionMixer, lerp_weights
from fast_track.runtime.korean_lip_sync_v2 import KoreanLipSyncV2, PhonemeEvent, build_phoneme_timeline
from fast_track.runtime.legacy_face_adapter import LegacyFaceAdapter

# Ownership sets (ESSENTIAL_V1 only).
EXPRESSION_OWNED = frozenset(
    {
        "FACE_eyeBlinkLeft",
        "FACE_eyeBlinkRight",
        "FACE_eyeSquintLeft",
        "FACE_eyeSquintRight",
        "FACE_eyeWideLeft",
        "FACE_eyeWideRight",
        "FACE_browInnerUpLeft",
        "FACE_browInnerUpRight",
        "FACE_browOuterUpLeft",
        "FACE_browOuterUpRight",
        "FACE_browDownLeft",
        "FACE_browDownRight",
        "FACE_cheekRaiseLeft",
        "FACE_cheekRaiseRight",
    }
)

SPEECH_OWNED = frozenset(
    {
        "FACE_mouthOpen",
        "FACE_mouthPucker",
        "FACE_mouthWiden",
        "FACE_lipsPart",
        "FACE_lipsTight",
        "FACE_mouthPlosive",
        "FACE_dentalLip",
    }
)

SMILE_FROWN = frozenset(
    {
        "FACE_mouthSmileLeft",
        "FACE_mouthSmileRight",
        "FACE_mouthFrownLeft",
        "FACE_mouthFrownRight",
    }
)

# When speech is active, preserve this fraction of expression smile/frown base.
SMILE_KEEP_RATIO = 0.55
# Attenuate smile further under strong OU pucker to avoid over-deformation.
PUCKER_SMILE_ATTENUATION = 0.45
# Under MBP closure, keep smile base but do not let expression reopen lips.
MBP_SMILE_KEEP_RATIO = 0.48
# HR11R quality patch: on open/non-MBP speech, retain Happy smile identity more strongly.
# Ownership policy unchanged — only attenuation magnitude by speech class.
OPEN_SMILE_KEEP_RATIO = 0.90
HR11R_QUALITY_PATCH = {
    "blinkPeakClosureBoost": True,
    "speechClassSmileAttenuation": True,
    "architectureChange": False,
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _sorted_weights(weights: dict[str, float]) -> dict[str, float]:
    return {k: _clamp01(weights[k]) for k in sorted(weights) if weights[k] > 1e-9}


COMPOSITION_POLICY: dict[str, Any] = {
    "schema": "NURION_FACE_COMPOSITION_POLICY_V1",
    "EYE_BROW_CHEEK": "Expression owns",
    "SPEECH_PRIMITIVES": "LipSync owns",
    "SMILE_FROWN": "Expression base + speech attenuation",
    "FINAL": "normalized, clamped 0..1, deterministic",
    "smileKeepRatio": SMILE_KEEP_RATIO,
    "puckerSmileAttenuation": PUCKER_SMILE_ATTENUATION,
    "mbpSmileKeepRatio": MBP_SMILE_KEEP_RATIO,
    "openSmileKeepRatio": OPEN_SMILE_KEEP_RATIO,
    "hr11rQualityPatch": HR11R_QUALITY_PATCH,
    "expressionOwned": sorted(EXPRESSION_OWNED),
    "speechOwned": sorted(SPEECH_OWNED),
    "smileFrown": sorted(SMILE_FROWN),
}


class FaceCompositionError(ValueError):
    """Fail-closed composition error."""


class FaceCompositionLayer:
    """Merge Expression Mixer + Korean Lip Sync v2 into canonical actuator weights."""

    def __init__(self, naming_table_path=None):
        self.adapter = LegacyFaceAdapter(naming_table_path)
        self.mixer = ExpressionMixer(naming_table_path)
        self.lipsync = KoreanLipSyncV2(naming_table_path)
        self.actuator = CanonicalFacialActuator(naming_table_path)
        self.policy = dict(COMPOSITION_POLICY)
        self._validate_policy_channels()

    def _validate_policy_channels(self) -> None:
        for name in EXPRESSION_OWNED | SPEECH_OWNED | SMILE_FROWN:
            if name not in self.adapter.essential_active:
                raise FaceCompositionError(f"Policy channel not ESSENTIAL_V1: {name}")

    def compose(
        self,
        expression_weights: dict[str, float],
        speech_weights: dict[str, float],
    ) -> dict[str, float]:
        """Deterministic channel ownership merge."""
        if any(k.startswith("PRES_") for k in expression_weights) or any(
            k.startswith("PRES_") for k in speech_weights
        ):
            raise FaceCompositionError("PRES_* direct input is DENY in Face Composition")

        expr = self.adapter.request_canonical(expression_weights) if expression_weights else {}
        speech = self.adapter.request_canonical(speech_weights) if speech_weights else {}

        # Reject any non-policy essential leakage into wrong buckets by filtering.
        out: dict[str, float] = {}

        # 1) Eyes/brow/cheek — Expression owns exclusively.
        for key in EXPRESSION_OWNED:
            if key in expr:
                out[key] = expr[key]
            # LipSync must not contribute here even if somehow present.
            if key in speech:
                # Explicit non-invasion: ignore speech contribution.
                pass

        # 2) Speech primitives — LipSync owns exclusively.
        for key in SPEECH_OWNED:
            if key in speech:
                out[key] = speech[key]

        # 3) Smile/Frown — Expression base with speech-class attenuation (HR11R).
        # Ownership unchanged: Expression base + speech attenuation only.
        speech_active = any(speech.get(k, 0.0) > 1e-6 for k in SPEECH_OWNED)
        pucker = speech.get("FACE_mouthPucker", 0.0)
        plosive = speech.get("FACE_mouthPlosive", 0.0)
        openness = max(
            speech.get("FACE_mouthOpen", 0.0),
            speech.get("FACE_mouthWiden", 0.0),
            speech.get("FACE_lipsPart", 0.0),
        )
        keep = SMILE_KEEP_RATIO
        if plosive > 0.4:
            # MBP: speech closure priority — strong smile attenuation allowed.
            keep = min(keep, MBP_SMILE_KEEP_RATIO)
        elif openness > 0.22 and plosive < 0.25:
            # A/EI-like open speech: retain Happy smile identity.
            keep = max(keep, OPEN_SMILE_KEEP_RATIO)
        if pucker > 0.35:
            keep = keep * (1.0 - PUCKER_SMILE_ATTENUATION * min(1.0, pucker))

        for key in SMILE_FROWN:
            base = expr.get(key, 0.0)
            if base <= 1e-9:
                continue
            if speech_active:
                out[key] = _clamp01(base * keep)
            else:
                out[key] = _clamp01(base)

        # 4) Final clamp + ESSENTIAL filter + deterministic order.
        if not out:
            return {}
        # mouthOpen already speech-owned; ensure clamp if any residual
        for k, v in list(out.items()):
            out[k] = _clamp01(v)
        return self.adapter.request_canonical(out)

    def evaluate(
        self,
        *,
        expression_preset: str,
        text: str | None = None,
        events: list[PhonemeEvent] | None = None,
        t: float = 0.0,
        speech_start: float = 0.0,
        speech_end: float | None = None,
        drive_actuator: bool = True,
    ) -> dict[str, Any]:
        expr = self.mixer.resolve_preset(expression_preset)
        if events is None:
            if text:
                events = build_phoneme_timeline(text, start=speech_start, end=speech_end)
            else:
                events = []
        speech = self.lipsync.evaluate_timeline(events, t) if events else {}
        composed = self.compose(expr, speech)
        if drive_actuator:
            self.actuator.drive(composed, replace=True)
        return {
            "expressionPreset": expression_preset,
            "expressionWeights": expr,
            "speechWeights": speech,
            "composedWeights": composed,
            "t": t,
            "policy": self.policy,
        }

    def transition_expression_while_speaking(
        self,
        *,
        from_preset: str,
        to_preset: str,
        blend_t: float,
        text: str,
        speech_t: float,
        speech_start: float = 0.0,
        speech_end: float = 1.0,
    ) -> dict[str, Any]:
        a = self.mixer.resolve_preset(from_preset)
        b = self.mixer.resolve_preset(to_preset)
        expr = lerp_weights(a, b, blend_t)
        events = build_phoneme_timeline(text, start=speech_start, end=speech_end)
        speech = self.lipsync.evaluate_timeline(events, speech_t)
        composed = self.compose(expr, speech)
        self.actuator.drive(composed, replace=True)
        return {
            "fromPreset": from_preset,
            "toPreset": to_preset,
            "expressionBlendT": blend_t,
            "expressionWeights": expr,
            "speechWeights": speech,
            "composedWeights": composed,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "stage": "FAST-HR11_FACE_PRODUCT_LOCKED",
            "talking_status": "GO",
            "face_product_lock": "DECLARED",
            "canonical_contract": "NURION_FACE_CANONICAL_V1",
            "active_tier": "ESSENTIAL_V1",
            "policy": self.policy,
            "actuator": self.actuator.snapshot(),
        }
