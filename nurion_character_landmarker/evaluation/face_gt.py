"""Evaluation-only face GT access (must never run inside generation_scope)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from mathutils import Vector

from ..core.face.gt_schema import gt_positions_world, load_face_gt
from ..core.face.keys import ALPHA1_CORE_KEYS
from ..core.leak_guard import note_gt_access


def collect_face_gt_landmarks(
    gt_path: Path,
    keys: Optional[List[str]] = None,
) -> Dict[str, dict]:
    """Read face GT JSON. Raises GroundTruthLeakError if called during generation."""
    note_gt_access("face_gt:collect_face_gt_landmarks")
    doc = load_face_gt(gt_path)
    wanted = set(keys or ALPHA1_CORE_KEYS)
    positions = gt_positions_world(doc)
    out: Dict[str, dict] = {}
    for name, pos in positions.items():
        if name not in wanted:
            continue
        out[name] = {
            "name": name,
            "position": [float(pos.x), float(pos.y), float(pos.z)],
            "source": "GT_MANUAL",
        }
    return out


def face_gt_vector_map(gt_path: Path, keys: Optional[List[str]] = None) -> Dict[str, Vector]:
    raw = collect_face_gt_landmarks(gt_path, keys=keys)
    return {k: Vector(v["position"]) for k, v in raw.items()}
