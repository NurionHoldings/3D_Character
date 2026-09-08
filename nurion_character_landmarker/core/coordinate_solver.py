"""Solve stable profile-ready coordinates from landmarks."""

from __future__ import annotations

from typing import Dict, List

from mathutils import Vector

from .landmark_engine import LandmarkPoint


def solve_coordinates(landmarks: Dict[str, LandmarkPoint]) -> List[dict]:
    """Return landmark profile entries (name/position/source/confidence/reviewRequired)."""
    return [landmarks[name].to_profile_entry() for name in sorted(landmarks.keys())]


def average_pair(a: Vector, b: Vector) -> Vector:
    return (a + b) * 0.5
