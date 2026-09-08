"""FAST-HR08 — Expression Mixer over ESSENTIAL_V1 FACE_* channels.

Combines verified canonical primitives into named facial states.
No lip-sync, no TALKING, no PRES_* inputs, no V1_1/HOLD shapes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.runtime.canonical_facial_actuator import CanonicalFacialActuator
from fast_track.runtime.legacy_face_adapter import LegacyFaceAdapter


class ExpressionMixerError(ValueError):
    """Fail-closed expression mixer error."""


# Static ESSENTIAL_V1 presets only. Values intentionally allow mild L/R asymmetry.
PRESET_CORE: dict[str, dict[str, float]] = {
    "Neutral": {},
    "SoftSmile": {
        "FACE_mouthSmileLeft": 0.28,
        "FACE_mouthSmileRight": 0.30,
        "FACE_cheekRaiseLeft": 0.10,
        "FACE_cheekRaiseRight": 0.11,
        "FACE_eyeSquintLeft": 0.04,
        "FACE_eyeSquintRight": 0.05,
    },
    "Happy": {
        "FACE_mouthSmileLeft": 0.70,
        "FACE_mouthSmileRight": 0.74,
        "FACE_cheekRaiseLeft": 0.32,
        "FACE_cheekRaiseRight": 0.34,
        "FACE_eyeSquintLeft": 0.12,
        "FACE_eyeSquintRight": 0.14,
        "FACE_browOuterUpLeft": 0.06,
        "FACE_browOuterUpRight": 0.06,
    },
    "Listening": {
        "FACE_mouthSmileLeft": 0.10,
        "FACE_mouthSmileRight": 0.10,
        "FACE_browInnerUpLeft": 0.08,
        "FACE_browInnerUpRight": 0.08,
        "FACE_eyeWideLeft": 0.04,
        "FACE_eyeWideRight": 0.04,
    },
    "Thinking": {
        "FACE_browInnerUpLeft": 0.18,
        "FACE_browInnerUpRight": 0.10,
        "FACE_browDownRight": 0.12,
        "FACE_eyeSquintRight": 0.08,
        "FACE_lipsTight": 0.10,
        "FACE_mouthSmileLeft": 0.04,
    },
    "Concerned": {
        "FACE_browInnerUpLeft": 0.34,
        "FACE_browInnerUpRight": 0.36,
        "FACE_browDownLeft": 0.08,
        "FACE_browDownRight": 0.08,
        "FACE_mouthFrownLeft": 0.22,
        "FACE_mouthFrownRight": 0.24,
        "FACE_eyeSquintLeft": 0.06,
        "FACE_eyeSquintRight": 0.06,
    },
    "Surprised": {
        "FACE_eyeWideLeft": 0.72,
        "FACE_eyeWideRight": 0.74,
        "FACE_browInnerUpLeft": 0.40,
        "FACE_browInnerUpRight": 0.42,
        "FACE_browOuterUpLeft": 0.28,
        "FACE_browOuterUpRight": 0.30,
        "FACE_mouthOpen": 0.35,
        "FACE_lipsPart": 0.20,
    },
}


def lerp_weights(a: dict[str, float], b: dict[str, float], t: float) -> dict[str, float]:
    t = max(0.0, min(1.0, float(t)))
    keys = sorted(set(a) | set(b))
    out: dict[str, float] = {}
    for key in keys:
        value = (1.0 - t) * float(a.get(key, 0.0)) + t * float(b.get(key, 0.0))
        if value > 0.0:
            out[key] = max(0.0, min(1.0, value))
    return out


class ExpressionMixer:
    """Preset composition layer → CanonicalFacialActuator only."""

    def __init__(self, naming_table_path: Path | None = None):
        self.adapter = LegacyFaceAdapter(naming_table_path)
        self.actuator = CanonicalFacialActuator(naming_table_path)
        self.presets = {name: dict(weights) for name, weights in PRESET_CORE.items()}
        self._validate_presets()
        self.current_preset: str = "Neutral"
        self.current_weights: dict[str, float] = {}
        self.actuator.reset()

    def _validate_presets(self) -> None:
        for preset, weights in self.presets.items():
            for face_name, value in weights.items():
                if face_name not in self.adapter.essential_active:
                    raise ExpressionMixerError(
                        f"Preset {preset} uses non-ESSENTIAL shape: {face_name}"
                    )
                if face_name in self.adapter.v11_set or face_name in self.adapter.hold_set:
                    raise ExpressionMixerError(
                        f"Preset {preset} uses blocked tier shape: {face_name}"
                    )
                if not (0.0 <= float(value) <= 1.0):
                    raise ExpressionMixerError(
                        f"Preset {preset} weight out of range for {face_name}: {value}"
                    )
                if face_name.startswith("PRES_"):
                    raise ExpressionMixerError(f"Preset {preset} must not use PRES_*: {face_name}")

    def list_presets(self) -> tuple[str, ...]:
        return tuple(sorted(self.presets))

    def resolve_preset(self, preset_name: str) -> dict[str, float]:
        if preset_name not in self.presets:
            raise ExpressionMixerError(f"Unknown preset: {preset_name}")
        raw = dict(self.presets[preset_name])
        # Clamp + ESSENTIAL filter via adapter request path.
        if not raw:
            return {}
        return self.adapter.request_canonical(raw)

    def apply_preset(self, preset_name: str) -> dict[str, float]:
        weights = self.resolve_preset(preset_name)
        driven = self.actuator.drive(weights, replace=True)
        self.current_preset = preset_name
        self.current_weights = dict(driven)
        return dict(driven)

    def transition(
        self,
        to_preset: str,
        *,
        t: float,
        from_preset: str | None = None,
    ) -> dict[str, float]:
        """Interpolate between presets and drive canonical actuator.

        t=0 keeps source, t=1 reaches target. No lip-sync / TALKING.
        """
        source = from_preset or self.current_preset
        a = self.resolve_preset(source)
        b = self.resolve_preset(to_preset)
        blended = lerp_weights(a, b, t)
        driven = self.actuator.drive(blended, replace=True)
        if float(t) >= 1.0:
            self.current_preset = to_preset
        self.current_weights = dict(driven)
        return dict(driven)

    def reject_pres_input(self, payload: dict[str, float]) -> None:
        if any(str(k).startswith("PRES_") for k in payload):
            raise ExpressionMixerError("PRES_* direct input is DENY in Expression Mixer")

    def snapshot(self) -> dict[str, Any]:
        return {
            "stage": "FAST-HR08_EXPRESSION_MIXER",
            "canonical_contract": "NURION_FACE_CANONICAL_V1",
            "active_tier": "ESSENTIAL_V1",
            "v1_1_enabled": False,
            "hold_enabled": False,
            "lip_sync_connected": False,
            "talking_status": "HOLD",
            "presets": list(self.list_presets()),
            "currentPreset": self.current_preset,
            "currentWeights": dict(self.current_weights),
            "actuatorSnapshot": self.actuator.snapshot(),
        }
