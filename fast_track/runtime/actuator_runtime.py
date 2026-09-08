"""FAST-04A — Presentation actuator runtime wiring (no geometry mutation)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from fast_track.runtime.legacy_face_adapter import LegacyFaceAdapter

MOUTH_ACTUATORS = (
    "PRES_JawOpen",
    "PRES_Viseme_A",
    "PRES_Viseme_E",
    "PRES_Viseme_O",
    "PRES_Viseme_M",
)
SECONDARY_ACTUATORS = ("PRES_Blink_L", "PRES_Blink_R", "PRES_SmileMild")
ALL_ACTUATORS = MOUTH_ACTUATORS + SECONDARY_ACTUATORS


class ActuatorRuntime:
    """Independent morph actuator control using locked FAST-03D deltas."""

    def __init__(self, morph_json: Path, *, enable_legacy_face_adapter: bool = True):
        data = json.loads(morph_json.read_text(encoding="utf-8"))
        self.vertex_count: int = int(data["vertexCount"])
        self._deltas: dict[str, np.ndarray] = {}
        for name in ALL_ACTUATORS:
            arr = np.zeros((self.vertex_count, 3), dtype=np.float64)
            for item in data["shapeKeys"].get(name, []):
                vi, x, y, z = item
                arr[int(vi)] = [x, y, z]
            self._deltas[name] = arr
        self._weights: dict[str, float] = {n: 0.0 for n in ALL_ACTUATORS}
        # HR06: PRES API unchanged; canonical projection is additive/read-only.
        self.legacy_face_adapter = LegacyFaceAdapter() if enable_legacy_face_adapter else None

    def names(self) -> tuple[str, ...]:
        return ALL_ACTUATORS

    def set_weight(self, name: str, weight: float) -> None:
        if name not in self._weights:
            raise KeyError(f"Unknown actuator: {name}")
        self._weights[name] = max(0.0, float(weight))

    def get_weight(self, name: str) -> float:
        return self._weights[name]

    def all_weights(self) -> dict[str, float]:
        return dict(self._weights)

    def canonical_weights(self) -> dict[str, float]:
        """Project current PRES_* weights through Legacy Face Adapter."""
        if self.legacy_face_adapter is None:
            raise RuntimeError("Legacy Face Adapter is disabled")
        return self.legacy_face_adapter.map_pres_to_canonical(self.all_weights())

    def reset_all(self) -> None:
        for k in self._weights:
            self._weights[k] = 0.0

    def is_neutral(self, tol: float = 0.0) -> bool:
        return all(abs(w) <= tol for w in self._weights.values())

    def combined_delta(self) -> np.ndarray:
        out = np.zeros((self.vertex_count, 3), dtype=np.float64)
        for name, w in self._weights.items():
            if w > 0.0:
                out += self._deltas[name] * w
        return out

    def apply_to_base(self, base_positions: np.ndarray) -> np.ndarray:
        if len(base_positions) != self.vertex_count:
            raise ValueError("Base position vertex count mismatch")
        return base_positions + self.combined_delta()

    def snapshot(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"weights": self.all_weights(), "vertexCount": self.vertex_count}
        if self.legacy_face_adapter is not None:
            payload["canonicalWeights"] = self.canonical_weights()
            payload["legacyFaceAdapter"] = self.legacy_face_adapter.snapshot_contract()
        return payload
