"""Meshy Eye Proxy — surface aperture landmarks + procedural eye centers (Alpha2).

Does not require native spherical eyeball meshes.
eye.center.* is PROCEDURAL_PROXY derived from surface landmarks (NURION_EYE_PROXY_V1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from mathutils import Vector

from ..landmark_engine import LandmarkPoint
from ..leak_guard import assert_no_gt_parameters, generation_scope
from ..sources import ESTIMATED, PROCEDURAL_PROXY
from ..transform_normalize import WorldMeshView, nearest_on_mesh, point_inside_or_on_mesh
from .parameters_alpha2 import FACE_ALPHA2_PARAMETERS
from .region import FaceRegionResult
from .spaces import HeadFrame


@dataclass
class EyeAperture:
    side: str
    inner: Vector
    outer: Vector
    upper: Vector
    lower: Vector
    surface_center: Vector
    normal_out: Vector
    width: float
    height: float


@dataclass
class EyeProxyResult:
    surface: Dict[str, LandmarkPoint] = field(default_factory=dict)
    centers: Dict[str, LandmarkPoint] = field(default_factory=dict)
    apertures: Dict[str, EyeAperture] = field(default_factory=dict)
    radii: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def all_landmarks(self) -> Dict[str, LandmarkPoint]:
        out = dict(self.surface)
        out.update(self.centers)
        return out


def _lp(name: str, pos: Vector, source: str, conf: float, evidence: Optional[dict] = None) -> LandmarkPoint:
    side = "L" if name.endswith(".L") else "R" if name.endswith(".R") else "C"
    return LandmarkPoint(name=name, position=pos, source=source, confidence=conf, side=side, evidence=evidence)


def _eye_band(worlds: List[Vector], frame: HeadFrame, side: str) -> List[Vector]:
    p = FACE_ALPHA2_PARAMETERS["aperture"]
    sign = 1.0 if side == "L" else -1.0
    h = frame.head_height
    out: List[Vector] = []
    for pt in worlds:
        loc = frame.to_local(pt)
        t = (loc.z / h) * 0.5 + 0.5
        if not (p["heightBand"][0] <= t <= p["heightBand"][1]):
            continue
        if loc.x * sign < h * p["lateralXMinHeadHeight"]:
            continue
        if abs(loc.x) > h * p["lateralXMaxHeadHeight"]:
            continue
        if loc.y < h * p["forwardYMinHeadHeight"]:
            continue
        out.append(pt)
    return out


def _cluster_eye(points: List[Vector], frame: HeadFrame) -> List[Vector]:
    if not points:
        return []
    p = FACE_ALPHA2_PARAMETERS["aperture"]
    h = frame.head_height
    # Prefer forward surface points.
    ranked = sorted(points, key=lambda q: frame.to_local(q).y, reverse=True)
    top = ranked[: max(40, len(ranked) // 4)]
    xs = sorted(frame.to_local(q).x for q in top)
    zs = sorted(frame.to_local(q).z for q in top)
    med_x = xs[len(xs) // 2]
    med_z = zs[len(zs) // 2]
    return [
        q
        for q in top
        if abs(frame.to_local(q).x - med_x) <= h * p["clusterXHeadHeight"]
        and abs(frame.to_local(q).z - med_z) <= h * p["clusterZHeadHeight"]
    ] or top[:32]


def _detect_aperture(
    view: WorldMeshView,
    frame: HeadFrame,
    worlds: List[Vector],
    side: str,
) -> Optional[EyeAperture]:
    cluster = _cluster_eye(_eye_band(worlds, frame, side), frame)
    if len(cluster) < 12:
        return None
    locals_ = [frame.to_local(q) for q in cluster]
    # Extreme points in head-local axes.
    inner_i = max(range(len(locals_)), key=lambda i: -locals_[i].x if side == "L" else locals_[i].x)
    # For L (+x side): inner is toward center (smaller |x| / toward - for L means min x among L cluster)
    if side == "L":
        inner_i = min(range(len(locals_)), key=lambda i: locals_[i].x)
        outer_i = max(range(len(locals_)), key=lambda i: locals_[i].x)
    else:
        inner_i = max(range(len(locals_)), key=lambda i: locals_[i].x)
        outer_i = min(range(len(locals_)), key=lambda i: locals_[i].x)
    upper_i = max(range(len(locals_)), key=lambda i: locals_[i].z)
    lower_i = min(range(len(locals_)), key=lambda i: locals_[i].z)

    inner, outer = cluster[inner_i], cluster[outer_i]
    upper, lower = cluster[upper_i], cluster[lower_i]
    # Snap to mesh surface.
    for label, pt in (("i", inner), ("o", outer), ("u", upper), ("l", lower)):
        near, _, _ = nearest_on_mesh(view, pt)
        if near is not None:
            if label == "i":
                inner = near
            elif label == "o":
                outer = near
            elif label == "u":
                upper = near
            else:
                lower = near

    surface = (inner + outer + upper + lower) * 0.25
    near, nrm, _ = nearest_on_mesh(view, surface)
    if near is not None:
        surface = near
    # Outward normal: prefer mesh normal facing forward in head frame.
    if nrm is not None and nrm.length > 1e-8:
        n_out = nrm.normalized()
        if n_out.dot(frame.forward) < 0:
            n_out = -n_out
    else:
        n_out = frame.forward.copy()

    width = (outer - inner).length
    height = (upper - lower).length
    min_w = frame.head_height * FACE_ALPHA2_PARAMETERS["aperture"]["innerOuterSpreadMinHeadHeight"]
    if width < min_w:
        return None
    return EyeAperture(
        side=side,
        inner=inner,
        outer=outer,
        upper=upper,
        lower=lower,
        surface_center=surface,
        normal_out=n_out,
        width=width,
        height=height,
    )


def _radius_mm_candidates(ap_l: EyeAperture, ap_r: EyeAperture, frame: HeadFrame) -> float:
    p = FACE_ALPHA2_PARAMETERS["proxy"]
    width_r = 0.5 * (ap_l.width + ap_r.width) * p["radiusFromWidth"]
    ipd = (ap_l.surface_center - ap_r.surface_center).length
    ipd_r = ipd * p["radiusFromIpd"]
    # Approximate head width from lateral span of face verts is unavailable here; use IPD proxy.
    head_w = max(ipd * 2.2, frame.head_height * 0.55)
    head_r = head_w * p["radiusFromHeadWidth"]
    r = (width_r + ipd_r + head_r) / 3.0
    r = max(frame.head_height * p["minRadiusHeadHeight"], min(frame.head_height * p["maxRadiusHeadHeight"], r))
    return r


def _derive_center(
    view: WorldMeshView,
    frame: HeadFrame,
    ap: EyeAperture,
    radius: float,
) -> Tuple[Vector, dict]:
    p = FACE_ALPHA2_PARAMETERS["proxy"]
    depth = radius * p["depthFromRadius"]
    center = ap.surface_center - ap.normal_out.normalized() * depth
    # Retract if protruding too far in front of surface.
    for _ in range(8):
        near, nrm, dist = nearest_on_mesh(view, center)
        if near is None:
            break
        # Vector from center to surface along outward normal should be ~radius.
        to_surf = ap.surface_center - center
        along = to_surf.dot(ap.normal_out.normalized())
        if along < radius * 0.55:
            center = center - ap.normal_out.normalized() * (radius * 0.08)
            continue
        if along > radius * 1.35:
            center = center + ap.normal_out.normalized() * (radius * 0.06)
            continue
        break
    # Clamp protrusion: sphere must not stick out more than maxProtrusion beyond surface.
    max_prot = frame.head_height * p["maxProtrusionHeadHeight"]
    protrude = radius - (ap.surface_center - center).dot(ap.normal_out.normalized())
    if protrude > max_prot:
        center = center - ap.normal_out.normalized() * (protrude - max_prot)
        radius = max(frame.head_height * p["minRadiusHeadHeight"], radius * 0.95)

    inside = point_inside_or_on_mesh(view, center)
    if not inside:
        # Pull toward head origin.
        center = center.lerp(frame.origin, 0.25)
        inside = point_inside_or_on_mesh(view, center)

    evidence = {
        "method": FACE_ALPHA2_PARAMETERS["methods"]["eyeCenter"],
        "source": PROCEDURAL_PROXY,
        "derivedFrom": [
            f"eye.inner.{ap.side}",
            f"eye.outer.{ap.side}",
            f"eyelid.upper.{ap.side}",
            f"eyelid.lower.{ap.side}",
        ],
        "radiusMm": round(radius * 1000.0, 3),
        "insideHead": inside,
        "deterministic": True,
        "apertureWidthMm": round(ap.width * 1000.0, 3),
        "apertureHeightMm": round(ap.height * 1000.0, 3),
    }
    return center, evidence


def build_eye_proxy(
    view: WorldMeshView,
    region: FaceRegionResult,
    **kwargs,
) -> EyeProxyResult:
    assert_no_gt_parameters(**kwargs)
    result = EyeProxyResult()
    if region.headFrame is None or not region.faceVertexWorld:
        result.notes.append("No face region for eye proxy")
        return result
    frame = region.headFrame

    with generation_scope("meshy_eye_proxy"):
        apertures: Dict[str, EyeAperture] = {}
        for side in ("L", "R"):
            ap = _detect_aperture(view, frame, region.faceVertexWorld, side)
            if ap is None:
                result.notes.append(f"aperture.{side} missing")
                continue
            apertures[side] = ap

        if "L" not in apertures or "R" not in apertures:
            result.notes.append("Need both eye apertures")
            result.apertures = apertures
            return result

        # Soft L/R height alignment
        zl = frame.to_local(apertures["L"].surface_center).z
        zr = frame.to_local(apertures["R"].surface_center).z
        zmid = 0.5 * (zl + zr)
        for side, ap in apertures.items():
            sc = frame.to_local(ap.surface_center)
            sc.z = zmid
            ap.surface_center = frame.to_world(sc)

        radius = _radius_mm_candidates(apertures["L"], apertures["R"], frame)
        # Enforce LR radius equality for standard eyeballs.
        for side, ap in apertures.items():
            result.apertures[side] = ap
            for name, pos, conf in (
                (f"eye.inner.{side}", ap.inner, 0.72),
                (f"eye.outer.{side}", ap.outer, 0.72),
                (f"eyelid.upper.{side}", ap.upper, 0.68),
                (f"eyelid.lower.{side}", ap.lower, 0.68),
                (f"iris.visualCenter.{side}", ap.surface_center, 0.70),
            ):
                result.surface[name] = _lp(
                    name,
                    pos,
                    ESTIMATED,
                    conf,
                    {
                        "method": FACE_ALPHA2_PARAMETERS["methods"]["eyeSurface"],
                        "side": side,
                    },
                )

            center, evidence = _derive_center(view, frame, ap, radius)
            result.radii[side] = float(evidence["radiusMm"]) / 1000.0
            # Keep equal radii
            result.radii[side] = radius
            evidence["radiusMm"] = round(radius * 1000.0, 3)
            result.centers[f"eye.center.{side}"] = _lp(
                f"eye.center.{side}",
                center,
                PROCEDURAL_PROXY,
                0.88,
                evidence,
            )

        result.notes.append("NURION_EYE_PROXY_V1 applied (Meshy-compatible, no native eyeball required)")
    return result
