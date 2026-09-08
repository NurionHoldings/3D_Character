"""FAST-HR07 — Canonical facial actuator (FACE_* ESSENTIAL_V1 only).

Primary API is NURION FACE Canonical v1. No expression presets, no lip-sync,
no TALKING activation. HOLD/V1_1 shapes are rejected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.runtime.legacy_face_adapter import LegacyFaceAdapter, LegacyFaceAdapterError


class CanonicalFacialActuatorError(ValueError):
    """Fail-closed canonical actuator error."""


class CanonicalFacialActuator:
    """Drive ESSENTIAL_V1 FACE_* channels from canonical weights only."""

    def __init__(self, naming_table_path: Path | None = None):
        self.adapter = LegacyFaceAdapter(naming_table_path)
        self._weights: dict[str, float] = {name: 0.0 for name in sorted(self.adapter.essential_active)}
        if len(self._weights) != 25:
            raise CanonicalFacialActuatorError(
                f"ESSENTIAL_V1 active set must be 25, got {len(self._weights)}"
            )

    @property
    def active_names(self) -> tuple[str, ...]:
        return tuple(self._weights.keys())

    def reset(self) -> None:
        for name in self._weights:
            self._weights[name] = 0.0

    def set_weight(self, face_name: str, weight: float) -> float:
        validated = self.adapter.request_canonical({face_name: weight})
        # request_canonical drops zero weights; still allow explicit zero set.
        if face_name not in self._weights:
            raise CanonicalFacialActuatorError(f"Not an ESSENTIAL_V1 actuator: {face_name}")
        value = self.adapter.clamp_weight(weight)
        # Re-check tier for zero-weight sets (request_canonical omits zeros).
        if face_name in self.adapter.v11_set or face_name in self.adapter.hold_set:
            raise CanonicalFacialActuatorError(f"Blocked tier for {face_name}")
        if face_name not in self.adapter.essential_active:
            raise CanonicalFacialActuatorError(f"Not ESSENTIAL_V1: {face_name}")
        self._weights[face_name] = value
        return value

    def set_weights(self, face_weights: dict[str, float]) -> dict[str, float]:
        # Validate all first (fail-closed); then apply atomically.
        validated = self.adapter.request_canonical(face_weights)
        # Also accept explicit zeros for channels already known essential.
        pending: dict[str, float] = {}
        for name, raw in face_weights.items():
            if name not in self._weights:
                # request_canonical would already raise for unknown/HOLD/V1_1
                # unless weight is zero and somehow slipped; force check.
                if name in self.adapter.v11_set:
                    raise CanonicalFacialActuatorError(f"V1_1 blocked: {name}")
                if name in self.adapter.hold_set:
                    raise CanonicalFacialActuatorError(f"HOLD blocked: {name}")
                raise CanonicalFacialActuatorError(f"Unknown/non-essential: {name}")
            pending[name] = self.adapter.clamp_weight(raw)
        for name, value in pending.items():
            self._weights[name] = value
        return {k: validated[k] for k in sorted(validated)}

    def get_weight(self, face_name: str) -> float:
        if face_name not in self._weights:
            raise CanonicalFacialActuatorError(f"Unknown ESSENTIAL actuator: {face_name}")
        return self._weights[face_name]

    def all_weights(self) -> dict[str, float]:
        return {k: self._weights[k] for k in sorted(self._weights)}

    def active_weights(self) -> dict[str, float]:
        return {k: w for k, w in self.all_weights().items() if w > 0.0}

    def is_neutral(self, tol: float = 0.0) -> bool:
        return all(abs(w) <= tol for w in self._weights.values())

    def drive(self, face_weights: dict[str, float], *, replace: bool = True) -> dict[str, float]:
        """Primary drive entry: FACE_* only → actuator channels."""
        if replace:
            self.reset()
        self.set_weights(face_weights)
        return self.active_weights()

    def snapshot(self) -> dict[str, Any]:
        return {
            "canonical_contract": "NURION_FACE_CANONICAL_V1",
            "active_tier": "ESSENTIAL_V1",
            "v1_1_enabled": False,
            "hold_enabled": False,
            "legacy_api_changed": False,
            "talking_status": "HOLD",
            "channelCount": len(self._weights),
            "weights": self.all_weights(),
            "activeWeights": self.active_weights(),
        }
