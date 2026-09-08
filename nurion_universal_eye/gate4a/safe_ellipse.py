"""Build per-eye gaze safe ellipses from Gate2 eyelid aperture."""

from __future__ import annotations

from dataclasses import dataclass

from mathutils import Vector

from .parameters import GATE4A_PARAMETERS


@dataclass
class GazeSafeEllipse:
    side: str
    center_local: Vector  # plane-local (x,y,0) — x along right, y along up
    rx: float
    ry: float
    iris_radius: float
    pupil_radius: float
    inset_m: float = 0.0

    @property
    def usable_rx(self) -> float:
        return max(1e-6, self.rx - self.iris_radius - self.inset_m)

    @property
    def usable_ry(self) -> float:
        return max(1e-6, self.ry - self.iris_radius - self.inset_m)


def build_safe_ellipse(plane, *, bulge_m: float = 0.0) -> GazeSafeEllipse:
    """Safe ellipse in EyePlane local XY from aperture span + plane height."""
    del bulge_m  # reserved for future lid-aware shaping
    params = GATE4A_PARAMETERS
    eu = float(plane.eye_unit)
    origin = plane.origin_world
    right = plane.right.normalized()
    up = plane.up.normalized()

    inner = Vector(plane.aperture_inner)
    outer = Vector(plane.aperture_outer)
    mid = (inner + outer) * 0.5
    to_mid = mid - origin
    cx = float(to_mid.dot(right))
    cy = float(to_mid.dot(up))

    aperture_half = 0.5 * (outer - inner).length * float(params["ellipse"]["widthFromAperture"])
    height_half = 0.5 * float(plane.height) * float(params["ellipse"]["heightFromPlane"])
    aperture_half = min(aperture_half, 0.48 * float(plane.width))
    height_half = min(height_half, 0.48 * float(plane.height))

    iris_r = eu * float(params["iris"]["radiusEyeUnits"])
    pupil_r = iris_r * float(params["iris"]["pupilRadiusScale"])
    inset_m = eu * float(params["ellipse"]["insetIrisEyeUnits"])

    return GazeSafeEllipse(
        side=plane.side,
        center_local=Vector((cx, cy, 0.0)),
        rx=float(aperture_half),
        ry=float(height_half),
        iris_radius=float(iris_r),
        pupil_radius=float(pupil_r),
        inset_m=float(inset_m),
    )


def ellipse_contains_disk(ellipse: GazeSafeEllipse, local_xy: Vector, radius: float) -> bool:
    """True iff disk of given radius at local_xy is inside the full safe ellipse."""
    dx = float(local_xy.x) - float(ellipse.center_local.x)
    dy = float(local_xy.y) - float(ellipse.center_local.y)
    rx = max(1e-9, ellipse.rx - radius)
    ry = max(1e-9, ellipse.ry - radius)
    return (dx / rx) ** 2 + (dy / ry) ** 2 <= 1.0 + 1e-6


def clamp_to_usable(ellipse: GazeSafeEllipse, local_xy: Vector) -> Vector:
    """Clamp point so iris disk of ellipse.iris_radius stays inside safe ellipse."""
    dx = float(local_xy.x) - float(ellipse.center_local.x)
    dy = float(local_xy.y) - float(ellipse.center_local.y)
    rx = ellipse.usable_rx
    ry = ellipse.usable_ry
    rn = (dx / rx) ** 2 + (dy / ry) ** 2
    if rn <= 1.0:
        return Vector((local_xy.x, local_xy.y, 0.0))
    s = rn ** 0.5
    return Vector((ellipse.center_local.x + dx / s, ellipse.center_local.y + dy / s, 0.0))


def iris_edge_escape_eu(ellipse: GazeSafeEllipse, local_xy: Vector, eu: float) -> float:
    """How far iris edge exceeds ellipse, in eye-units (0 = inside)."""
    dx = float(local_xy.x) - float(ellipse.center_local.x)
    dy = float(local_xy.y) - float(ellipse.center_local.y)
    rx = max(1e-9, ellipse.rx)
    ry = max(1e-9, ellipse.ry)
    rn = (dx / rx) ** 2 + (dy / ry) ** 2
    if rn < 1e-12:
        overflow = max(0.0, ellipse.iris_radius - min(rx, ry))
        return overflow / max(eu, 1e-9)
    s = rn ** 0.5
    dist_c = (dx * dx + dy * dy) ** 0.5
    dist_edge = dist_c / s
    overflow = max(0.0, dist_c + ellipse.iris_radius - dist_edge)
    return overflow / max(eu, 1e-9)
