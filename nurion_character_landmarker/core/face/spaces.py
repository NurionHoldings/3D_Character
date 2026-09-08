"""World / head-local face coordinate frames (no object transform mutation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from mathutils import Matrix, Vector

from ..landmark_engine import LandmarkPoint


@dataclass
class HeadFrame:
    """Orthonormal head frame in world space."""

    origin: Vector
    forward: Vector  # +Y typically (character forward)
    right: Vector  # +X character right (negative world X if mirrored — keep world-consistent)
    up: Vector  # +Z
    head_height: float
    matrix_world: Matrix  # columns = right, forward, up; translation = origin
    matrix_world_inv: Matrix

    def to_local(self, world: Vector) -> Vector:
        return self.matrix_world_inv @ world

    def to_world(self, local: Vector) -> Vector:
        return self.matrix_world @ local


def _normalize(v: Vector, fallback: Vector) -> Vector:
    if v.length < 1e-9:
        return fallback.copy()
    return v.normalized()


def build_head_frame(
    *,
    head_center: Vector,
    forward_axis: str,
    head_height: float,
    body: Optional[Dict[str, LandmarkPoint]] = None,
) -> HeadFrame:
    """Build head frame from body landmarks / axis without mutating scene transforms."""
    axis = (forward_axis or "+Y").upper()
    if axis.endswith("X"):
        forward = Vector((1.0 if axis.startswith("+") else -1.0, 0.0, 0.0))
    elif axis.endswith("Z"):
        forward = Vector((0.0, 0.0, 1.0 if axis.startswith("+") else -1.0))
    else:
        forward = Vector((0.0, 1.0 if not axis.startswith("-") else -1.0, 0.0))

    up = Vector((0.0, 0.0, 1.0))
    if body and "head" in body and "neck" in body:
        neck_to_head = body["head"].position - body["neck"].position
        if neck_to_head.length > 1e-6:
            up = _normalize(neck_to_head, up)
            # Re-orthogonalize forward against up.
            forward = _normalize(forward - up * forward.dot(up), Vector((0.0, 1.0, 0.0)))

    right = _normalize(forward.cross(up), Vector((1.0, 0.0, 0.0)))
    # Ensure right-handed: right × forward ≈ up
    up = _normalize(right.cross(forward), up)
    forward = _normalize(up.cross(right), forward)

    origin = head_center.copy()
    if body and "head" in body:
        origin = body["head"].position.copy()

    mat = Matrix(
        (
            (right.x, forward.x, up.x, origin.x),
            (right.y, forward.y, up.y, origin.y),
            (right.z, forward.z, up.z, origin.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    return HeadFrame(
        origin=origin,
        forward=forward,
        right=right,
        up=up,
        head_height=float(max(head_height, 1e-4)),
        matrix_world=mat,
        matrix_world_inv=mat.inverted(),
    )


def face_entry(
    name: str,
    world: Vector,
    frame: HeadFrame,
    *,
    source: str,
    confidence: float,
    evidence: Optional[dict] = None,
    review_required: Optional[bool] = None,
) -> dict:
    local = frame.to_local(world)
    entry = {
        "name": name,
        "position": [round(float(world.x), 6), round(float(world.y), 6), round(float(world.z), 6)],
        "positionWorld": [round(float(world.x), 6), round(float(world.y), 6), round(float(world.z), 6)],
        "positionHeadLocal": [round(float(local.x), 6), round(float(local.y), 6), round(float(local.z), 6)],
        "source": source,
        "confidence": round(float(confidence), 4),
        "reviewRequired": bool(review_required) if review_required is not None else float(confidence) < 0.90,
    }
    if evidence:
        entry["evidence"] = evidence
    return entry


def entries_from_landmarks(
    landmarks: Dict[str, LandmarkPoint],
    frame: HeadFrame,
) -> List[dict]:
    out: List[dict] = []
    for name, lp in landmarks.items():
        out.append(
            face_entry(
                name,
                lp.position,
                frame,
                source=lp.source,
                confidence=lp.confidence,
                evidence=lp.evidence,
                review_required=lp.review_required,
            )
        )
    return out


def symmetry_plane_x(frame: HeadFrame) -> Tuple[Vector, Vector]:
    """Return (point_on_plane, normal) for L/R symmetry (sagittal) in world."""
    return frame.origin.copy(), frame.right.copy()
