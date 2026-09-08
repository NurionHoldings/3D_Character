"""FAST-05B — ONE CHARACTER camera contract (interpolation only)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CameraPreset:
    name: str
    location: tuple[float, float, float]
    target: tuple[float, float, float]
    fov_deg: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CAM_FULL = CameraPreset("CAM_FULL", (0.0, 1.05, 3.35), (0.0, 1.0, 0.0), 42.0)
# Fixed presentation anchor — not head-tracked (idle animation safe)
PRES_CAMERA_UPPER_ANCHOR = (0.0, 1.48, 0.0)
# FAST-06R1.4 — one fixed 42° FOV; presentation scale comes from dolly only.
# 0.79m preserves the R1.3 upper-body occupancy with ~15% more gesture space.
CAM_UPPER = CameraPreset("CAM_UPPER", (0.0, 1.52, 0.79), PRES_CAMERA_UPPER_ANCHOR, 42.0)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp3(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    return (_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), _lerp(a[2], b[2], t))


def _ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


@dataclass
class CameraState:
    preset: str
    location: tuple[float, float, float]
    target: tuple[float, float, float]
    fov_deg: float
    interpolation_t: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "preset": self.preset,
            "location": list(self.location),
            "target": list(self.target),
            "fovDeg": self.fov_deg,
        }
        if self.interpolation_t is not None:
            d["interpolationT"] = self.interpolation_t
        return d


class CameraController:
    """Camera-only transitions — no mesh/character transform mutation."""

    def __init__(self, zoom_duration_sec: float = 0.85):
        self.zoom_duration = zoom_duration_sec
        self._preset = CAM_FULL
        self._from: CameraPreset = CAM_FULL
        self._to: CameraPreset = CAM_FULL
        self._zoom_elapsed = 0.0
        self._zooming = False

    @property
    def current_preset_name(self) -> str:
        return self._preset.name

    def state(self) -> CameraState:
        if not self._zooming:
            p = self._preset
            return CameraState(p.name, p.location, p.target, p.fov_deg)
        t = _ease_in_out(min(1.0, self._zoom_elapsed / max(self.zoom_duration, 1e-6)))
        loc = _lerp3(self._from.location, self._to.location, t)
        tgt = _lerp3(self._from.target, self._to.target, t)
        fov = _lerp(self._from.fov_deg, self._to.fov_deg, t)
        label = self._to.name if t >= 1.0 else f"INTERP_{self._from.name}_TO_{self._to.name}"
        return CameraState(label, loc, tgt, fov, interpolation_t=t)

    def begin_zoom_to_upper(self) -> None:
        self._from = self._preset
        self._to = CAM_UPPER
        self._zoom_elapsed = 0.0
        self._zooming = True

    def begin_zoom_to_full(self) -> None:
        self._from = self._preset
        self._to = CAM_FULL
        self._zoom_elapsed = 0.0
        self._zooming = True

    def tick(self, dt: float) -> bool:
        """Advance zoom; return True if zoom just completed."""
        if not self._zooming:
            return False
        prev = self._zoom_elapsed
        self._zoom_elapsed += dt
        done = self._zoom_elapsed >= self.zoom_duration
        if done:
            self._preset = self._to
            self._zooming = False
            return prev < self.zoom_duration
        return False

    def canonical_presets(self) -> dict[str, dict]:
        return {"CAM_FULL": CAM_FULL.to_dict(), "CAM_UPPER": CAM_UPPER.to_dict()}
