"""Multi-view render helpers for future AI landmark detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ViewSpec:
    name: str
    azimuth_deg: float
    elevation_deg: float


DEFAULT_VIEWS: List[ViewSpec] = [
    ViewSpec("front", 0.0, 0.0),
    ViewSpec("left", 90.0, 0.0),
    ViewSpec("right", -90.0, 0.0),
    ViewSpec("back", 180.0, 0.0),
]


def list_default_views() -> List[ViewSpec]:
    return list(DEFAULT_VIEWS)


def prepare_multiview_job(character_name: str) -> dict:
    """Placeholder job descriptor for offscreen multi-view capture."""
    return {
        "character": character_name,
        "views": [v.name for v in DEFAULT_VIEWS],
        "status": "planned",
        "engine": "NURION_MULTIVIEW_V1",
    }
