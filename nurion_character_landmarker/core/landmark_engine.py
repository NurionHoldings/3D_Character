"""Body landmark estimation / storage (v0.1: ESTIMATED joint guides)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from mathutils import Vector

from .character_analyzer import CharacterAnalysis
from .measurement_engine import CharacterMeasurements, axis_vector
from .sources import ESTIMATED, MANUAL, MEASURED, review_required


BODY_LANDMARK_KEYS = [
    "pelvis",
    "spine",
    "chest",
    "neck",
    "head",
    "shoulder.L",
    "elbow.L",
    "wrist.L",
    "shoulder.R",
    "elbow.R",
    "wrist.R",
    "hip.L",
    "knee.L",
    "ankle.L",
    "hip.R",
    "knee.R",
    "ankle.R",
]

# Bounds-derived helpers stored alongside joint estimates.
MEASURED_HELPER_KEYS = [
    "bounds.head_top",
    "bounds.feet",
    "bounds.center",
]


@dataclass
class LandmarkPoint:
    name: str
    position: Vector
    source: str = ESTIMATED
    confidence: float = 1.0
    side: str = "C"  # L / R / C
    review_required: bool = True
    evidence: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        self.review_required = review_required(self.source, self.confidence)

    def to_profile_entry(self) -> dict:
        pos = self.position
        entry = {
            "name": self.name,
            "position": [round(float(pos.x), 6), round(float(pos.y), 6), round(float(pos.z), 6)],
            "source": self.source,
            "confidence": round(float(self.confidence), 4),
            "reviewRequired": bool(self.review_required),
        }
        if self.evidence:
            entry["evidence"] = self.evidence
        return entry

    @classmethod
    def from_profile_entry(cls, data: dict) -> "LandmarkPoint":
        # Backward compatible: bare [x,y,z] or full object.
        if isinstance(data, (list, tuple)) and len(data) >= 3:
            return cls(
                name="unknown",
                position=Vector((float(data[0]), float(data[1]), float(data[2]))),
                source=ESTIMATED,
                confidence=0.5,
            )
        name = data.get("name", "unknown")
        pos = data.get("position", [0.0, 0.0, 0.0])
        return cls(
            name=name,
            position=Vector((float(pos[0]), float(pos[1]), float(pos[2]))),
            source=data.get("source", ESTIMATED),
            confidence=float(data.get("confidence", 0.5)),
            side="L" if name.endswith(".L") else "R" if name.endswith(".R") else "C",
            review_required=bool(data.get("reviewRequired", True)),
            evidence=dict(data["evidence"]) if data.get("evidence") else None,
        )


@dataclass
class LandmarkSet:
    body: Dict[str, LandmarkPoint] = field(default_factory=dict)
    face: Dict[str, LandmarkPoint] = field(default_factory=dict)

    def as_profile_list(self) -> List[dict]:
        out: List[dict] = []
        for group in (self.body, self.face):
            for point in group.values():
                out.append(point.to_profile_entry())
        return out


def _lp(name: str, pos: Vector, source: str, confidence: float, side: str = "C") -> LandmarkPoint:
    return LandmarkPoint(name=name, position=pos, source=source, confidence=confidence, side=side)


def build_measured_helpers(analysis: CharacterAnalysis) -> Dict[str, LandmarkPoint]:
    """Directly MEASURED extent markers — not joint centers."""
    c = analysis.center
    mins = analysis.bounds_min
    maxs = analysis.bounds_max
    return {
        "bounds.head_top": _lp("bounds.head_top", Vector((c.x, c.y, maxs.z)), MEASURED, 1.0),
        "bounds.feet": _lp("bounds.feet", Vector((c.x, c.y, mins.z)), MEASURED, 1.0),
        "bounds.center": _lp("bounds.center", c.copy(), MEASURED, 1.0),
    }


def estimate_body_landmarks(
    analysis: CharacterAnalysis,
    measurements: CharacterMeasurements,
) -> Dict[str, LandmarkPoint]:
    """
    v0.1 joint placeholders from anthropometric ratios.

    These are ESTIMATED starting guides for manual correction — not true joint centers.
    """
    c = analysis.center
    mins = analysis.bounds_min
    maxs = analysis.bounds_max
    h = measurements.height.value
    sw = measurements.shoulder_width.value * 0.5
    hw = measurements.hip_width.value * 0.5
    arm = measurements.arm_length.value
    forward = axis_vector(measurements.forward_axis) * 0.01

    def p(x: float, y: float, z: float) -> Vector:
        return Vector((x, y, z)) + forward

    pelvis_z = mins.z + h * 0.54
    chest_z = mins.z + h * 0.78
    neck_z = mins.z + h * 0.86
    head_z = mins.z + h * 0.95
    shoulder_z = mins.z + h * 0.82
    elbow_z = mins.z + h * 0.70
    wrist_z = mins.z + h * 0.58
    knee_z = mins.z + h * 0.31
    ankle_z = mins.z + h * 0.05
    cx, cy = c.x, c.y

    # Lower confidence for distal joints — bbox ratios are weakest there.
    points = {
        "pelvis": _lp("pelvis", p(cx, cy, pelvis_z), ESTIMATED, 0.70),
        "spine": _lp("spine", p(cx, cy, (pelvis_z + chest_z) * 0.5), ESTIMATED, 0.66),
        "chest": _lp("chest", p(cx, cy, chest_z), ESTIMATED, 0.68),
        "neck": _lp("neck", p(cx, cy, neck_z), ESTIMATED, 0.62),
        "head": _lp("head", p(cx, cy, head_z), ESTIMATED, 0.60),
        "shoulder.L": _lp("shoulder.L", p(cx + sw, cy, shoulder_z), ESTIMATED, 0.66, "L"),
        "elbow.L": _lp("elbow.L", p(cx + sw + arm * 0.35, cy, elbow_z), ESTIMATED, 0.64, "L"),
        "wrist.L": _lp("wrist.L", p(cx + sw + arm * 0.70, cy, wrist_z), ESTIMATED, 0.60, "L"),
        "shoulder.R": _lp("shoulder.R", p(cx - sw, cy, shoulder_z), ESTIMATED, 0.66, "R"),
        "elbow.R": _lp("elbow.R", p(cx - sw - arm * 0.35, cy, elbow_z), ESTIMATED, 0.64, "R"),
        "wrist.R": _lp("wrist.R", p(cx - sw - arm * 0.70, cy, wrist_z), ESTIMATED, 0.60, "R"),
        "hip.L": _lp("hip.L", p(cx + hw, cy, pelvis_z), ESTIMATED, 0.68, "L"),
        "knee.L": _lp("knee.L", p(cx + hw * 0.9, cy, knee_z), ESTIMATED, 0.64, "L"),
        "ankle.L": _lp("ankle.L", p(cx + hw * 0.85, cy, ankle_z), ESTIMATED, 0.62, "L"),
        "hip.R": _lp("hip.R", p(cx - hw, cy, pelvis_z), ESTIMATED, 0.68, "R"),
        "knee.R": _lp("knee.R", p(cx - hw * 0.9, cy, knee_z), ESTIMATED, 0.64, "R"),
        "ankle.R": _lp("ankle.R", p(cx - hw * 0.85, cy, ankle_z), ESTIMATED, 0.62, "R"),
    }

    for point in points.values():
        point.position.z = max(mins.z, min(maxs.z, point.position.z))

    helpers = build_measured_helpers(analysis)
    points.update(helpers)
    return points


# Keep old name as alias for callers during transition.
detect_body_landmarks = estimate_body_landmarks


def detect_face_landmarks(
    analysis: CharacterAnalysis,
    measurements: CharacterMeasurements,
    body: Optional[Dict[str, LandmarkPoint]] = None,
    mesh_obj=None,
) -> Dict[str, LandmarkPoint]:
    """v0.3a face detection facade (Alpha1 core via geometry+multiview fusion)."""
    import bpy

    from .face.correct import correct_face_landmarks

    obj = mesh_obj or bpy.data.objects.get(analysis.object_name)
    if obj is None or obj.type != "MESH":
        return {}
    return correct_face_landmarks(
        obj,
        body=body,
        forward_axis=measurements.forward_axis,
        core_only=True,
    ).landmarks


def mirror_left_to_right(landmarks: Dict[str, LandmarkPoint], center_x: float) -> Dict[str, LandmarkPoint]:
    """Mirror *.L landmarks onto matching *.R landmarks (result marked MANUAL)."""
    updated = dict(landmarks)
    for name, point in landmarks.items():
        if not name.endswith(".L"):
            continue
        right_name = name[:-2] + ".R"
        mirrored = point.position.copy()
        mirrored.x = center_x - (point.position.x - center_x)
        updated[right_name] = LandmarkPoint(
            name=right_name,
            position=mirrored,
            source=MANUAL,
            confidence=max(point.confidence, 0.9),
            side="R",
        )
    return updated
