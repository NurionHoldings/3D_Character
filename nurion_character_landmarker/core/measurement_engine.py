"""Derive body measurements from analyzed character bounds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal

from mathutils import Vector

from .character_analyzer import CharacterAnalysis
from .sources import ESTIMATED, MEASURED

ForwardAxis = Literal["+X", "-X", "+Y", "-Y", "+Z", "-Z"]


@dataclass
class MeasuredValue:
    value: float
    source: str
    note: str = ""


@dataclass
class CharacterMeasurements:
    height: MeasuredValue
    width: MeasuredValue
    depth: MeasuredValue
    center: tuple[float, float, float]
    center_source: str
    shoulder_width: MeasuredValue
    hip_width: MeasuredValue
    arm_length: MeasuredValue
    leg_length: MeasuredValue
    forward_axis: ForwardAxis
    forward_axis_source: str
    floor_position: MeasuredValue
    notes: list[str] = field(default_factory=list)

    def ui_floats(self) -> Dict[str, float]:
        return {
            "height": self.height.value,
            "width": self.width.value,
            "shoulder_width": self.shoulder_width.value,
            "hip_width": self.hip_width.value,
            "arm_length": self.arm_length.value,
            "leg_length": self.leg_length.value,
            "floor_position": self.floor_position.value,
        }


def _axis_component(axis: ForwardAxis) -> tuple[str, float]:
    sign = 1.0 if axis.startswith("+") else -1.0
    return axis[-1].lower(), sign


def infer_forward_axis(dims: Vector) -> ForwardAxis:
    # Prefer the shorter horizontal axis as forward for upright characters.
    if dims.x <= dims.y:
        return "-Y"
    return "-X"


def measure_character(
    analysis: CharacterAnalysis,
    forward_axis: ForwardAxis | None = None,
) -> CharacterMeasurements:
    dims = analysis.dimensions
    height = float(dims.z)
    width = float(max(dims.x, dims.y))
    depth = float(min(dims.x, dims.y))
    axis = forward_axis or infer_forward_axis(dims)
    axis_source = MEASURED if forward_axis else ESTIMATED

    return CharacterMeasurements(
        height=MeasuredValue(height, MEASURED, "World Z extent of mesh bounds"),
        width=MeasuredValue(width, MEASURED, "Larger horizontal extent of mesh bounds"),
        depth=MeasuredValue(depth, MEASURED, "Smaller horizontal extent of mesh bounds"),
        center=(float(analysis.center.x), float(analysis.center.y), float(analysis.center.z)),
        center_source=MEASURED,
        shoulder_width=MeasuredValue(width * 0.42, ESTIMATED, "≈42% of measured width"),
        hip_width=MeasuredValue(width * 0.34, ESTIMATED, "≈34% of measured width"),
        arm_length=MeasuredValue(height * 0.36, ESTIMATED, "≈36% of measured height"),
        leg_length=MeasuredValue(height * 0.48, ESTIMATED, "≈48% of measured height"),
        forward_axis=axis,
        forward_axis_source=axis_source,
        floor_position=MeasuredValue(float(analysis.bounds_min.z), MEASURED, "Minimum world Z of mesh bounds"),
        notes=[
            "MEASURED: height, width, depth, center, floor.",
            "ESTIMATED: shoulder/hip/arm/leg proportions — not joint centers.",
        ],
    )


def axis_vector(axis: ForwardAxis) -> Vector:
    name, sign = _axis_component(axis)
    vec = Vector((0.0, 0.0, 0.0))
    setattr(vec, name, sign)
    return vec
