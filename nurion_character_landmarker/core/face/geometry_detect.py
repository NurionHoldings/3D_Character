"""Geometry-based face landmark candidates (Alpha1 core 13). No GT inputs."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from mathutils import Vector

from ..landmark_engine import LandmarkPoint
from ..leak_guard import assert_no_gt_parameters, generation_scope
from ..sources import ESTIMATED, FACE_GEOMETRY_CORRECTED
from ..transform_normalize import WorldMeshView, nearest_on_mesh, point_inside_mesh
from .parameters import FACE_ALPHA1_PARAMETERS
from .region import FaceRegionResult
from .spaces import HeadFrame


def _lp(name: str, pos: Vector, source: str, conf: float, evidence: Optional[dict] = None) -> LandmarkPoint:
    side = "L" if name.endswith(".L") else "R" if name.endswith(".R") else "C"
    return LandmarkPoint(
        name=name,
        position=pos,
        source=source,
        confidence=conf,
        side=side,
        evidence=evidence,
    )


def _band(worlds: List[Vector], frame: HeadFrame, z0: float, z1: float) -> List[Vector]:
    out: List[Vector] = []
    for p in worlds:
        loc = frame.to_local(p)
        # Normalize local height 0 at chin-ish bottom of head verts, 1 at top.
        # Use up component relative to head origin.
        t = (loc.z / frame.head_height) * 0.5 + 0.5
        if z0 <= t <= z1:
            out.append(p)
    return out


def _fit_sphere(points: List[Vector]) -> Tuple[Optional[Vector], float, float]:
    if len(points) < 8:
        return None, 0.0, float("inf")
    c = sum(points, Vector((0, 0, 0))) / len(points)
    rs = [(p - c).length for p in points]
    r = sum(rs) / len(rs)
    residual = (sum((x - r) ** 2 for x in rs) / len(rs)) ** 0.5
    return c, r, residual


def _detect_eyeball_meshes(frame: HeadFrame, eyeball_names: List[str]) -> Dict[str, Tuple[Vector, float, float]]:
    import bpy

    found: Dict[str, Tuple[Vector, float, float]] = {}
    for name in eyeball_names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            continue
        deps = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(deps)
        me = eval_obj.to_mesh()
        try:
            me.transform(eval_obj.matrix_world)
            pts = [v.co.copy() for v in me.vertices]
        finally:
            eval_obj.to_mesh_clear()
        center, radius, residual = _fit_sphere(pts)
        if center is None:
            continue
        local = frame.to_local(center)
        side = "L" if local.x >= 0 else "R"
        key = f"eye.center.{side}"
        # Keep better residual if both map same side.
        prev = found.get(key)
        if prev is None or residual < prev[2]:
            found[key] = (center, radius, residual)
    return found


def _eye_from_surface(
    worlds: List[Vector],
    frame: HeadFrame,
    side: str,
) -> Tuple[Optional[Vector], dict]:
    params = FACE_ALPHA1_PARAMETERS["eyes"]
    band = _band(worlds, frame, params["heightBand"][0], params["heightBand"][1])
    sign = 1.0 if side == "L" else -1.0
    cands = []
    for p in band:
        loc = frame.to_local(p)
        if loc.x * sign < frame.head_height * 0.02:
            continue
        if abs(loc.x) > frame.head_height * 0.35:
            continue
        # Prefer forward surface (high local y).
        cands.append((float(loc.y), p, loc))
    if not cands:
        return None, {"method": "EYE_SURFACE_FALLBACK_V1", "candidateCount": 0}
    cands.sort(key=lambda t: t[0], reverse=True)
    top = cands[: max(12, len(cands) // 8)]
    # Cluster by x around median of top-forward points.
    xs = sorted(t[2].x for t in top)
    med_x = xs[len(xs) // 2]
    cluster = [t for t in top if abs(t[2].x - med_x) < frame.head_height * 0.04]
    if not cluster:
        cluster = top[:8]
    center_local = sum((t[2] for t in cluster), Vector((0, 0, 0))) / len(cluster)
    # Pull slightly inside along -forward for eyeball center.
    center_local = center_local - Vector((0.0, frame.head_height * 0.02, 0.0))
    world = frame.to_world(center_local)
    return world, {
        "method": "EYE_SURFACE_FALLBACK_V1",
        "candidateCount": len(cluster),
        "fitResidualMm": None,
    }


def detect_face_geometry_candidates(
    view: WorldMeshView,
    region: FaceRegionResult,
    **kwargs,
) -> Dict[str, LandmarkPoint]:
    assert_no_gt_parameters(**kwargs)
    if region.headFrame is None:
        return {}
    frame = region.headFrame
    worlds = region.faceVertexWorld
    params = FACE_ALPHA1_PARAMETERS
    out: Dict[str, LandmarkPoint] = {}

    with generation_scope("face_geometry_detect"):
        eyeballs = _detect_eyeball_meshes(frame, region.eyeballObjects)
        for key, (center, radius, residual) in eyeballs.items():
            out[key] = _lp(
                key,
                center,
                ESTIMATED,
                0.78,
                {
                    "method": params["methods"]["eyeball"],
                    "candidateCount": 1,
                    "fitResidualMm": round(residual * 1000.0, 3),
                    "radiusM": round(radius, 6),
                    "insideMesh": point_inside_mesh(view, center),
                },
            )

        for side in ("L", "R"):
            key = f"eye.center.{side}"
            if key not in out:
                pos, meta = _eye_from_surface(worlds, frame, side)
                if pos is not None:
                    meta["insideMesh"] = point_inside_mesh(view, pos)
                    out[key] = _lp(key, pos, ESTIMATED, 0.62, meta)

        # Inner / outer from eye centers.
        off = frame.head_height * float(params["eyes"]["innerOuterOffsetHeadHeight"])
        for side, sign in (("L", 1.0), ("R", -1.0)):
            ckey = f"eye.center.{side}"
            if ckey not in out:
                continue
            c = out[ckey].position
            cl = frame.to_local(c)
            inner = frame.to_world(cl + Vector((-sign * off * 0.55, 0.0, 0.0)))
            outer = frame.to_world(cl + Vector((sign * off, 0.0, 0.0)))
            out[f"eye.inner.{side}"] = _lp(
                f"eye.inner.{side}",
                inner,
                ESTIMATED,
                0.58,
                {"method": "EYE_CORNER_OFFSET_V1", "from": ckey},
            )
            out[f"eye.outer.{side}"] = _lp(
                f"eye.outer.{side}",
                outer,
                ESTIMATED,
                0.58,
                {"method": "EYE_CORNER_OFFSET_V1", "from": ckey},
            )

        # Nose tip — most forward in mid band near center X.
        nose_band = _band(worlds, frame, params["nose"]["heightBand"][0], params["nose"]["heightBand"][1])
        mid = frame.head_height * float(params["nose"]["midXRatio"])
        nose_cands = [p for p in nose_band if abs(frame.to_local(p).x) <= mid]
        if nose_cands:
            nose = max(nose_cands, key=lambda p: frame.to_local(p).y)
            out["nose.tip"] = _lp(
                "nose.tip",
                nose,
                ESTIMATED,
                0.70,
                {
                    "method": params["methods"]["nose"],
                    "candidateCount": len(nose_cands),
                    "insideMesh": True,
                },
            )

        # Mouth center / corners.
        mouth_band = _band(worlds, frame, params["mouth"]["heightBand"][0], params["mouth"]["heightBand"][1])
        if "nose.tip" in out:
            nz = frame.to_local(out["nose.tip"].position).z
            mouth_band = [
                p
                for p in mouth_band
                if frame.to_local(p).z < nz - frame.head_height * float(params["mouth"]["belowNoseMinHeadHeight"])
            ]
        if mouth_band:
            # Forward lip ridge near center.
            forward_sorted = sorted(mouth_band, key=lambda p: frame.to_local(p).y, reverse=True)
            lip = forward_sorted[: max(20, len(forward_sorted) // 10)]
            center_local = sum((frame.to_local(p) for p in lip), Vector((0, 0, 0))) / len(lip)
            center_local.x = 0.0
            mouth_c = frame.to_world(center_local)
            out["mouth.center"] = _lp(
                "mouth.center",
                mouth_c,
                ESTIMATED,
                0.66,
                {"method": params["methods"]["mouth"], "candidateCount": len(lip)},
            )
            corner_off = frame.head_height * float(params["mouth"]["cornerOffsetHeadHeight"])
            out["mouth.corner.L"] = _lp(
                "mouth.corner.L",
                frame.to_world(center_local + Vector((corner_off, 0.0, 0.0))),
                ESTIMATED,
                0.60,
                {"method": "MOUTH_CORNER_OFFSET_V1"},
            )
            out["mouth.corner.R"] = _lp(
                "mouth.corner.R",
                frame.to_world(center_local + Vector((-corner_off, 0.0, 0.0))),
                ESTIMATED,
                0.60,
                {"method": "MOUTH_CORNER_OFFSET_V1"},
            )

        # Chin — low forward.
        chin_band = _band(worlds, frame, params["chin"]["heightBand"][0], params["chin"]["heightBand"][1])
        if chin_band:
            ys = sorted(frame.to_local(p).y for p in chin_band)
            thresh = ys[int(len(ys) * float(params["chin"]["forwardPercentile"])) - 1]
            forward_chin = [p for p in chin_band if frame.to_local(p).y >= thresh]
            if forward_chin:
                chin = min(forward_chin, key=lambda p: frame.to_local(p).z)
                # Snap near mesh.
                near, _, _ = nearest_on_mesh(view, chin)
                if near is not None:
                    chin = near
                out["chin"] = _lp(
                    "chin",
                    chin,
                    ESTIMATED,
                    0.68,
                    {"method": params["methods"]["chin"], "candidateCount": len(forward_chin)},
                )

        # Ears — lateral protrusions.
        ear_band = _band(worlds, frame, params["ears"]["heightBand"][0], params["ears"]["heightBand"][1])
        lat = float(params["ears"]["lateralXRatio"]) * frame.head_height * 0.5
        for side, sign in (("L", 1.0), ("R", -1.0)):
            side_pts = [p for p in ear_band if frame.to_local(p).x * sign >= lat]
            if not side_pts:
                side_pts = sorted(ear_band, key=lambda p: frame.to_local(p).x * sign, reverse=True)[:40]
            if side_pts:
                extreme = max(side_pts, key=lambda p: frame.to_local(p).x * sign)
                nearby = [
                    p
                    for p in side_pts
                    if (p - extreme).length < frame.head_height * 0.05
                ] or [extreme]
                center = sum(nearby, Vector((0, 0, 0))) / len(nearby)
                candidate_count = len(nearby)
            else:
                # Ratio fallback so Alpha1 core remains complete on eligible faces.
                center = frame.to_world(
                    Vector((sign * frame.head_height * 0.28, -frame.head_height * 0.02, frame.head_height * 0.05))
                )
                nearby = []
                candidate_count = 0
            near, _, _ = nearest_on_mesh(view, center)
            if near is not None:
                center = near
            out[f"ear.center.{side}"] = _lp(
                f"ear.center.{side}",
                center,
                ESTIMATED,
                0.55 if nearby else 0.42,
                {
                    "method": params["methods"]["ear"],
                    "candidateCount": candidate_count,
                    "insideMesh": point_inside_mesh(view, center),
                },
            )

    return out
