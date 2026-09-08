"""Create empty-based body guide markers in the scene."""

from __future__ import annotations

from typing import Dict, Optional

import bpy
from mathutils import Vector

from ..core.landmark_engine import LandmarkPoint
from ..core.sources import ESTIMATED, MANUAL, VALID_SOURCES

GUIDE_COLLECTION = "NURION_Body_Guides"
GUIDE_PREFIX = "NURION_LM_"


def _ensure_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _write_guide_props(obj: bpy.types.Object, point: LandmarkPoint) -> None:
    obj["nurion_landmark"] = point.name
    obj["nurion_source"] = point.source
    obj["nurion_confidence"] = float(point.confidence)
    obj["nurion_review_required"] = bool(point.review_required)


def create_body_guides(landmarks: Dict[str, LandmarkPoint], overwrite_positions: bool = True) -> int:
    col = _ensure_collection(GUIDE_COLLECTION)
    created = 0

    for name, point in landmarks.items():
        obj_name = f"{GUIDE_PREFIX}{name}"
        existing = bpy.data.objects.get(obj_name)
        if existing is not None:
            if overwrite_positions:
                existing.location = point.position
            _write_guide_props(existing, point)
            continue

        empty = bpy.data.objects.new(obj_name, None)
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = 0.03 if not name.startswith("bounds.") else 0.045
        empty.location = Vector(point.position)
        _write_guide_props(empty, point)
        col.objects.link(empty)
        created += 1

    return created


def sync_landmarks_from_guides(
    previous: Optional[Dict[str, LandmarkPoint]] = None,
    mark_moved_as_manual: bool = True,
    move_epsilon: float = 1e-5,
) -> Dict[str, LandmarkPoint]:
    """Read guide empties. Moved guides become MANUAL with high confidence."""
    result: Dict[str, LandmarkPoint] = {}
    prev = previous or {}

    for obj in bpy.data.objects:
        if not obj.name.startswith(GUIDE_PREFIX):
            continue
        key = obj.name[len(GUIDE_PREFIX) :]
        side = "L" if key.endswith(".L") else "R" if key.endswith(".R") else "C"

        source = str(obj.get("nurion_source", ESTIMATED))
        if source not in VALID_SOURCES:
            source = ESTIMATED
        confidence = float(obj.get("nurion_confidence", 0.7))

        if mark_moved_as_manual and key in prev:
            delta = (obj.location - prev[key].position).length
            if delta > move_epsilon:
                source = MANUAL
                confidence = 1.0

        point = LandmarkPoint(
            name=key,
            position=obj.matrix_world.translation.copy(),
            source=source,
            confidence=confidence,
            side=side,
        )
        _write_guide_props(obj, point)
        result[key] = point

    return result
