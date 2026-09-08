"""FAST-04E — Blink, mild smile, fixed camera look target (secondary motion)."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraLookTarget:
    position: tuple[float, float, float]
    name: str = "FAST_CAMERA_PROOF"


@dataclass
class SecondaryMotionState:
    blink_l: float = 0.0
    blink_r: float = 0.0
    smile: float = 0.0
    eye_yaw_l: float = 0.0
    eye_yaw_r: float = 0.0
    eye_pitch_l: float = 0.0
    eye_pitch_r: float = 0.0


DEFAULT_CAMERA = CameraLookTarget(position=(0.0, 1.45, 2.2))


def _blink_pulse(t: float, center: float, width: float = 0.12) -> float:
    d = abs(t - center)
    if d > width:
        return 0.0
    return 1.0 - d / width


class SecondaryMotionLayer:
    """Adds blink/smile/eye-look after mouth weights are resolved."""

    def __init__(
        self,
        speech_start: float,
        speech_end: float,
        blink_interval: float = 3.2,
        smile_level: float = 0.18,
        camera: CameraLookTarget | None = None,
    ):
        self.speech_start = speech_start
        self.speech_end = speech_end
        self.blink_interval = blink_interval
        self.smile_level = smile_level
        self.camera = camera or DEFAULT_CAMERA
        # Fixed proof look: slight convergence toward camera
        self._eye_yaw = 0.04
        self._eye_pitch = -0.02

    def sample(self, t: float) -> SecondaryMotionState:
        st = SecondaryMotionState()
        if t < self.speech_start - 0.05 or t > self.speech_end + 0.15:
            return st

        # blink schedule during speech only
        if self.speech_start <= t <= self.speech_end:
            phase = (t - self.speech_start) % self.blink_interval
            pulse = _blink_pulse(phase, self.blink_interval * 0.85, width=0.1)
            st.blink_l = pulse
            st.blink_r = pulse
            st.smile = self.smile_level

        st.eye_yaw_l = self._eye_yaw
        st.eye_yaw_r = -self._eye_yaw
        st.eye_pitch_l = self._eye_pitch
        st.eye_pitch_r = self._eye_pitch
        return st

    def apply_to_weights(self, weights: dict[str, float], t: float) -> dict[str, float]:
        st = self.sample(t)
        out = dict(weights)
        out["PRES_Blink_L"] = max(out.get("PRES_Blink_L", 0.0), st.blink_l)
        out["PRES_Blink_R"] = max(out.get("PRES_Blink_R", 0.0), st.blink_r)
        out["PRES_SmileMild"] = max(out.get("PRES_SmileMild", 0.0), st.smile)
        return out

    def look_target_proof(self) -> dict:
        return {
            "cameraLookTarget": {
                "name": self.camera.name,
                "position": list(self.camera.position),
            },
            "eyeYawLeft": self._eye_yaw,
            "eyeYawRight": -self._eye_yaw,
            "eyePitchLeft": self._eye_pitch,
            "eyePitchRight": self._eye_pitch,
            "note": "Fixed camera look proof — FULL/UPPER transition deferred to FAST-05",
        }
