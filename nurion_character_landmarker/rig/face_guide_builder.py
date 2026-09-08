"""Create / sync face landmark guide empties (separate collection from body)."""

from __future__ import annotations

from typing import Dict, Optional

import bpy
from mathutils import Vector

from ..core.face.keys import FACE_LANDMARK_KEYS_FULL
from ..core.landmark_engine import LandmarkPoint
from ..core.sources import ESTIMATED, MANUAL, VALID_SOURCES

FACE_GUIDE_COLLECTION = "NURION_Face_Guides"
FACE_GUIDE_PREFIX = "NURION_FACE_"


def _ensure_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _write_props(obj: bpy.types.Object, point: LandmarkPoint) -> None:
    obj["nurion_landmark"] = point.name
    obj["nurion_source"] = point.source
    obj["nurion_confidence"] = float(point.confidence)
    obj["nurion_review_required"] = bool(point.review_required)
    obj["nurion_domain"] = "face"


def create_face_guides(
    landmarks: Dict[str, LandmarkPoint],
    *,
    overwrite_positions: bool = True,
    display_size: float = 0.012,
) -> int:
    col = _ensure_collection(FACE_GUIDE_COLLECTION)
    created = 0
    for name, point in landmarks.items():
        obj_name = f"{FACE_GUIDE_PREFIX}{name}"
        existing = bpy.data.objects.get(obj_name)
        if existing is not None:
            if overwrite_positions:
                existing.location = point.position
            _write_props(existing, point)
            continue
        empty = bpy.data.objects.new(obj_name, None)
        empty.empty_display_type = "SPHERE"
        empty.empty_display_size = display_size
        empty.location = Vector(point.position)
        _write_props(empty, point)
        col.objects.link(empty)
        created += 1
    return created


def create_face_gt_template_guides(
    seeds: Dict[str, LandmarkPoint],
    *,
    keys=None,
) -> int:
    """Create empties for full face GT set; missing keys get seed or origin."""
    keys = keys or FACE_LANDMARK_KEYS_FULL
    landmarks: Dict[str, LandmarkPoint] = {}
    fallback = Vector((0.0, 0.0, 1.6))
    if seeds:
        fallback = next(iter(seeds.values())).position.copy()
    for name in keys:
        if name in seeds:
            landmarks[name] = seeds[name]
        else:
            landmarks[name] = LandmarkPoint(
                name=name,
                position=fallback.copy(),
                source=ESTIMATED,
                confidence=0.2,
                side="L" if name.endswith(".L") else "R" if name.endswith(".R") else "C",
            )
    return create_face_guides(landmarks, overwrite_positions=False)


def sync_face_landmarks_from_guides(
    previous: Optional[Dict[str, LandmarkPoint]] = None,
    mark_moved_as_manual: bool = True,
    move_epsilon: float = 1e-5,
) -> Dict[str, LandmarkPoint]:
    result: Dict[str, LandmarkPoint] = {}
    prev = previous or {}
    for obj in bpy.data.objects:
        if not obj.name.startswith(FACE_GUIDE_PREFIX):
            continue
        key = obj.name[len(FACE_GUIDE_PREFIX) :]
        side = "L" if key.endswith(".L") else "R" if key.endswith(".R") else "C"
        source = str(obj.get("nurion_source", ESTIMATED))
        if source not in VALID_SOURCES:
            source = ESTIMATED
        confidence = float(obj.get("nurion_confidence", 0.7))
        if mark_moved_as_manual and key in prev:
            if (obj.location - prev[key].position).length > move_epsilon:
                source = MANUAL
                confidence = 1.0
        result[key] = LandmarkPoint(
            name=key,
            position=obj.location.copy(),
            source=source,
            confidence=confidence,
            side=side,
        )
    return result
