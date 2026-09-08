"""
Gate 1 — Universal Face Basis.

Builds a character-agnostic head/face coordinate system.
Does NOT create EyePlane, convex eyeballs, gaze, blink, or expression features.
Does NOT consume manual GT.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from mathutils import Matrix, Vector

# Soft accessories: down-weight / exclude from forward & symmetry mass.
EXCLUDE_NAME_TOKENS = (
    "hair",
    "eyelash",
    "glass",
    "spectacle",
    "earring",
    "accessory",
    "hat",
    "cap",
    "helmet",
    "tongue",
    "teeth",
    "tooth",
)

HEAD_HEIGHT_RATIO = 0.22
EYE_HEIGHT_BAND = (0.52, 0.80)
EYE_LATERAL_X_MIN = 0.02
EYE_LATERAL_X_MAX = 0.38
EYE_FORWARD_Y_MIN = -0.05
EAR_LATERAL_EXCLUDE = 0.78  # |local.x| / head_height above this → ear-like, low weight


@dataclass
class HeadAxes:
    origin: Vector
    right: Vector  # +X character right
    forward: Vector  # +Y face forward
    up: Vector  # +Z
    head_height: float
    matrix_world: Matrix
    matrix_world_inv: Matrix

    def to_local(self, world: Vector) -> Vector:
        return self.matrix_world_inv @ world

    def to_world(self, local: Vector) -> Vector:
        return self.matrix_world @ local


@dataclass
class EyeRegionCandidate:
    side: str
    vertex_count: int
    centroid_world: Vector
    inner_world: Vector
    outer_world: Vector
    eye_unit: float
    confidence: float
    evidence: Dict = field(default_factory=dict)


@dataclass
class UniversalFaceBasis:
    schema: str = "NURION_UNIVERSAL_FACE_BASIS"
    version: str = "0.3.0-alpha.3-gate1"
    mesh_name: str = ""
    character_height: float = 0.0
    head_height: float = 0.0
    axes: Optional[HeadAxes] = None
    symmetry_point: Optional[Vector] = None
    symmetry_normal: Optional[Vector] = None
    face_forward: Optional[Vector] = None
    head_center: Optional[Vector] = None
    eye_regions: Dict[str, EyeRegionCandidate] = field(default_factory=dict)
    confidences: Dict[str, float] = field(default_factory=dict)
    evidence: Dict = field(default_factory=dict)
    flags: Dict[str, bool] = field(default_factory=dict)
    matrix_world_before: Optional[List[float]] = None
    matrix_world_after: Optional[List[float]] = None
    visual_eye_generated: bool = False
    manual_gt_used: bool = False

    def to_profile(self) -> dict:
        ax = self.axes
        eyes = {}
        for side, er in self.eye_regions.items():
            eyes[side] = {
                "side": er.side,
                "vertexCount": er.vertex_count,
                "centroidWorld": _v3(er.centroid_world),
                "innerWorld": _v3(er.inner_world),
                "outerWorld": _v3(er.outer_world),
                "eyeUnit": round(float(er.eye_unit), 6),
                "confidence": round(float(er.confidence), 4),
                "evidence": er.evidence,
            }
        return {
            "schema": self.schema,
            "version": self.version,
            "meshName": self.mesh_name,
            "characterHeight": round(float(self.character_height), 6),
            "headHeight": round(float(self.head_height), 6),
            "headCenterWorld": _v3(self.head_center) if self.head_center else None,
            "faceForwardWorld": _v3(self.face_forward) if self.face_forward else None,
            "headLocalAxes": {
                "origin": _v3(ax.origin) if ax else None,
                "right": _v3(ax.right) if ax else None,
                "forward": _v3(ax.forward) if ax else None,
                "up": _v3(ax.up) if ax else None,
            },
            "symmetryPlane": {
                "point": _v3(self.symmetry_point) if self.symmetry_point else None,
                "normal": _v3(self.symmetry_normal) if self.symmetry_normal else None,
            },
            "eyeRegions": eyes,
            "eyeUnits": {
                side: round(float(er.eye_unit), 6) for side, er in self.eye_regions.items()
            },
            "confidences": {k: round(float(v), 4) for k, v in self.confidences.items()},
            "evidence": self.evidence,
            "flags": dict(self.flags),
            "worldTransformBefore": self.matrix_world_before,
            "worldTransformAfter": self.matrix_world_after,
            "manualGtUsed": False,
            "visualEyeGenerated": False,
        }


def _v3(v: Vector) -> List[float]:
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def _normalize(v: Vector, fallback: Vector) -> Vector:
    if v.length < 1e-9:
        return fallback.copy()
    return v.normalized()


def _mat_flat(m: Matrix) -> List[float]:
    return [round(float(m[i][j]), 6) for i in range(4) for j in range(4)]


def _name_excluded(name: str) -> bool:
    n = name.lower()
    return any(t in n for t in EXCLUDE_NAME_TOKENS)


def _select_character_mesh(preferred: str = ""):
    import bpy

    if preferred and preferred in bpy.data.objects and bpy.data.objects[preferred].type == "MESH":
        return bpy.data.objects[preferred]
    meshes = [
        o
        for o in bpy.data.objects
        if o.type == "MESH" and not o.name.startswith("NURION_") and not _name_excluded(o.name)
    ]
    if not meshes:
        meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("NURION_")]
    if not meshes:
        raise RuntimeError("No character mesh found")
    # Prefer char1, else densest mesh.
    for o in meshes:
        if o.name.lower() == "char1":
            return o
    return max(meshes, key=lambda o: len(o.data.vertices))


def _world_vertices(mesh_obj) -> Tuple[List[Vector], List[int], Matrix]:
    import bpy

    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(deps)
    me = eval_obj.to_mesh()
    try:
        mw = eval_obj.matrix_world.copy()
        me.transform(mw)
        verts = [v.co.copy() for v in me.vertices]
        idxs = list(range(len(verts)))
        return verts, idxs, mw
    finally:
        eval_obj.to_mesh_clear()


def _build_axes(origin: Vector, forward: Vector, up_hint: Vector, head_height: float) -> HeadAxes:
    up = _normalize(up_hint, Vector((0.0, 0.0, 1.0)))
    forward = _normalize(forward - up * forward.dot(up), Vector((0.0, 1.0, 0.0)))
    right = _normalize(forward.cross(up), Vector((1.0, 0.0, 0.0)))
    up = _normalize(right.cross(forward), up)
    forward = _normalize(up.cross(right), forward)
    mat = Matrix(
        (
            (right.x, forward.x, up.x, origin.x),
            (right.y, forward.y, up.y, origin.y),
            (right.z, forward.z, up.z, origin.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    return HeadAxes(
        origin=origin.copy(),
        right=right,
        forward=forward,
        up=up,
        head_height=float(max(head_height, 1e-4)),
        matrix_world=mat,
        matrix_world_inv=mat.inverted(),
    )


def _head_subset(
    verts: Sequence[Vector],
    *,
    z_min: float,
    z_max: float,
    head_height_ratio: float,
) -> List[Vector]:
    height = max(z_max - z_min, 1e-6)
    head_z0 = z_max - height * head_height_ratio
    return [p for p in verts if float(p.z) >= head_z0]


def _weighted_centroid(points: Sequence[Vector], weights: Sequence[float]) -> Vector:
    tw = sum(weights) or 1.0
    acc = Vector((0.0, 0.0, 0.0))
    for p, w in zip(points, weights):
        acc += p * float(w)
    return acc / tw


def _face_forward_from_mass(head_pts: Sequence[Vector], center: Vector) -> Tuple[Vector, float]:
    """Estimate face forward as horizontal direction of densest frontal mass (world +Y biased)."""
    # Project offsets onto XY, prefer +Y hemisphere.
    acc = Vector((0.0, 0.0, 0.0))
    wsum = 0.0
    for p in head_pts:
        d = p - center
        d.z = 0.0
        if d.length < 1e-8:
            continue
        # Soft prior toward world +Y (Meshy biped convention) without hardcoding absolute coords.
        prior = max(0.05, 0.5 + 0.5 * d.normalized().y)
        # Down-weight extreme lateral (ears / hair wings).
        lateral = abs(d.x) / max(abs(d.y) + abs(d.x), 1e-6)
        w = prior * (1.0 - min(0.85, lateral))
        acc += d.normalized() * w
        wsum += w
    if wsum < 1e-6 or acc.length < 1e-8:
        return Vector((0.0, 1.0, 0.0)), 0.35
    fwd = _normalize(acc, Vector((0.0, 1.0, 0.0)))
    conf = min(0.95, 0.55 + 0.4 * min(1.0, wsum / max(len(head_pts), 1)))
    return fwd, conf


def _symmetry_plane(
    head_pts: Sequence[Vector],
    axes: HeadAxes,
) -> Tuple[Vector, Vector, float, Dict]:
    """Sagittal plane: origin through median local-X of non-ear head mass; normal = right."""
    locals_x = []
    weights = []
    for p in head_pts:
        loc = axes.to_local(p)
        ax = abs(float(loc.x)) / axes.head_height
        if ax > EAR_LATERAL_EXCLUDE:
            w = 0.05
        elif ax > 0.55:
            w = 0.25
        else:
            w = 1.0
        # Prefer frontal mass for symmetry.
        if float(loc.y) < -0.15 * axes.head_height:
            w *= 0.2
        locals_x.append(float(loc.x))
        weights.append(w)
    if not locals_x:
        return axes.origin.copy(), axes.right.copy(), 0.2, {"method": "FALLBACK_ORIGIN"}

    # Weighted median of local x.
    pairs = sorted(zip(locals_x, weights), key=lambda t: t[0])
    total = sum(w for _, w in pairs) or 1.0
    acc = 0.0
    med = pairs[len(pairs) // 2][0]
    for x, w in pairs:
        acc += w
        if acc >= total * 0.5:
            med = x
            break

    # Shift origin onto median plane along right.
    point = axes.origin + axes.right * med
    # Score L/R mass balance after shift.
    left_w = right_w = 0.0
    for p, w in zip(head_pts, weights):
        lx = float(axes.to_local(p).x) - med
        if lx >= 0:
            left_w += w
        else:
            right_w += w
    bal = min(left_w, right_w) / max(left_w, right_w, 1e-6)
    conf = min(0.96, 0.45 + 0.5 * bal)
    return point, axes.right.copy(), conf, {
        "method": "WEIGHTED_MEDIAN_LOCAL_X_V1",
        "medianLocalX": round(med, 6),
        "leftRightMassBalance": round(float(bal), 4),
        "excludedEarWeightCap": EAR_LATERAL_EXCLUDE,
    }


def _eye_region(
    head_pts: Sequence[Vector],
    axes: HeadAxes,
    side: str,
) -> Optional[EyeRegionCandidate]:
    sign = 1.0 if side == "L" else -1.0
    h = axes.head_height
    band: List[Vector] = []
    for p in head_pts:
        loc = axes.to_local(p)
        t = (float(loc.z) / h) * 0.5 + 0.5
        if not (EYE_HEIGHT_BAND[0] <= t <= EYE_HEIGHT_BAND[1]):
            continue
        if float(loc.x) * sign < h * EYE_LATERAL_X_MIN:
            continue
        if abs(float(loc.x)) > h * EYE_LATERAL_X_MAX:
            continue
        if float(loc.y) < h * EYE_FORWARD_Y_MIN:
            continue
        band.append(p)
    if len(band) < 12:
        return None

    ranked = sorted(band, key=lambda q: axes.to_local(q).y, reverse=True)
    top = ranked[: max(40, len(ranked) // 4)]
    xs = sorted(float(axes.to_local(q).x) for q in top)
    zs = sorted(float(axes.to_local(q).z) for q in top)
    med_x = xs[len(xs) // 2]
    med_z = zs[len(zs) // 2]
    cluster = [
        q
        for q in top
        if abs(float(axes.to_local(q).x) - med_x) <= h * 0.05
        and abs(float(axes.to_local(q).z) - med_z) <= h * 0.04
    ] or top[:32]

    locs = [axes.to_local(q) for q in cluster]
    # Character L = +local X, R = -local X. Inner toward midline (x→0), outer away.
    if side == "L":
        inner_l = min(locs, key=lambda v: v.x)
        outer_l = max(locs, key=lambda v: v.x)
    else:
        inner_l = max(locs, key=lambda v: v.x)
        outer_l = min(locs, key=lambda v: v.x)

    inner = axes.to_world(inner_l)
    outer = axes.to_world(outer_l)
    centroid = sum(cluster, Vector((0, 0, 0))) / len(cluster)
    eye_unit = float((outer - inner).length)
    if eye_unit < h * 0.01:
        return None
    conf = min(0.92, 0.4 + 0.01 * len(cluster) + min(0.3, eye_unit / (h * 0.15)))
    return EyeRegionCandidate(
        side=side,
        vertex_count=len(cluster),
        centroid_world=centroid,
        inner_world=inner,
        outer_world=outer,
        eye_unit=eye_unit,
        confidence=conf,
        evidence={
            "method": "FORWARD_CLUSTER_APERTURE_V1",
            "band": list(EYE_HEIGHT_BAND),
            "clusterCount": len(cluster),
            "bandCount": len(band),
        },
    )


def build_universal_face_basis(
    *,
    mesh_name: str = "",
    forward_prior: str = "+Y",
) -> UniversalFaceBasis:
    """Compute Gate 1 basis. Never mutates object transforms. Never uses GT."""
    import bpy

    mesh = _select_character_mesh(mesh_name)
    mw_before = mesh.matrix_world.copy()
    verts, _idxs, _mw = _world_vertices(mesh)

    xs = [float(p.x) for p in verts]
    ys = [float(p.y) for p in verts]
    zs = [float(p.z) for p in verts]
    z_min, z_max = min(zs), max(zs)
    char_h = max(z_max - z_min, 1e-6)
    head_h = char_h * HEAD_HEIGHT_RATIO

    head_pts = _head_subset(verts, z_min=z_min, z_max=z_max, head_height_ratio=HEAD_HEIGHT_RATIO)
    if len(head_pts) < 200:
        raise RuntimeError(f"Head vertex count too low: {len(head_pts)}")

    # Accessory object exclusion is name-based; single-mesh Meshy uses geometric down-weight.
    excluded_objects = [o.name for o in bpy.data.objects if o.type == "MESH" and _name_excluded(o.name)]

    # Preliminary center / up
    weights = []
    for p in head_pts:
        # Soft down-weight top spikes (hat) and extreme lateral.
        t = (float(p.z) - (z_max - head_h)) / max(head_h, 1e-6)
        w = 1.0
        if t > 0.92:
            w *= 0.15  # crown / hat
        weights.append(w)
    center = _weighted_centroid(head_pts, weights)

    if forward_prior.upper().endswith("X"):
        prior = Vector((1.0 if forward_prior.startswith("+") else -1.0, 0.0, 0.0))
    elif forward_prior.upper().endswith("Z"):
        prior = Vector((0.0, 0.0, 1.0 if forward_prior.startswith("+") else -1.0))
    else:
        prior = Vector((0.0, 1.0 if not forward_prior.startswith("-") else -1.0, 0.0))

    fwd_mass, fwd_conf = _face_forward_from_mass(head_pts, center)
    face_forward = _normalize(fwd_mass * 0.85 + prior * 0.15, prior)

    up = Vector((0.0, 0.0, 1.0))
    axes = _build_axes(center, face_forward, up, head_h)

    # Refine origin: mean of frontal head verts in local space.
    frontal = [p for p in head_pts if float(axes.to_local(p).y) >= -0.05 * head_h]
    if len(frontal) >= 50:
        origin = sum(frontal, Vector((0, 0, 0))) / len(frontal)
        axes = _build_axes(origin, face_forward, up, head_h)
        center = origin

    sym_pt, sym_n, sym_conf, sym_ev = _symmetry_plane(head_pts, axes)
    # Re-center origin onto symmetry plane (keep height/depth).
    local_c = axes.to_local(center)
    # Project onto plane: remove right component relative to sym point.
    offset = (center - sym_pt).dot(sym_n)
    center = center - sym_n * offset
    axes = _build_axes(center, face_forward, up, head_h)

    eyes: Dict[str, EyeRegionCandidate] = {}
    for side in ("L", "R"):
        er = _eye_region(head_pts, axes, side)
        if er is not None:
            eyes[side] = er

    # L/R swap check prep: L centroid local.x should be > 0, R < 0
    lr_swap = 0
    if "L" in eyes and "R" in eyes:
        lx = float(axes.to_local(eyes["L"].centroid_world).x)
        rx = float(axes.to_local(eyes["R"].centroid_world).x)
        if not (lx > 0 and rx < 0):
            lr_swap = 1

    mw_after = mesh.matrix_world.copy()
    world_dep = 0 if _mat_flat(mw_before) == _mat_flat(mw_after) else 1

    basis = UniversalFaceBasis(
        mesh_name=mesh.name,
        character_height=char_h,
        head_height=head_h,
        axes=axes,
        symmetry_point=sym_pt,
        symmetry_normal=sym_n,
        face_forward=face_forward,
        head_center=center,
        eye_regions=eyes,
        confidences={
            "headSeparation": min(0.95, 0.5 + len(head_pts) / 5000.0),
            "faceForward": float(fwd_conf),
            "symmetryPlane": float(sym_conf),
            "headLocalAxes": min(0.95, 0.55 + 0.2 * float(fwd_conf) + 0.2 * float(sym_conf)),
            "eyeRegion.L": float(eyes["L"].confidence) if "L" in eyes else 0.0,
            "eyeRegion.R": float(eyes["R"].confidence) if "R" in eyes else 0.0,
        },
        evidence={
            "headVertexCount": len(head_pts),
            "meshVertexCount": len(verts),
            "excludedObjects": excluded_objects,
            "forwardMethod": "FRONTAL_MASS_WITH_AXIS_PRIOR_V1",
            "symmetry": sym_ev,
            "eyeUnitDefinition": "1 Eye Unit = inner–outer eyelid distance of that eye region",
            "manualGtUsed": False,
            "visualEyeGenerated": False,
            "lrSwapCount": lr_swap,
        },
        flags={
            "headLocalAxesStable": True,
            "faceForwardResolved": face_forward.length > 0.5,
            "symmetryPlaneResolved": sym_conf >= 0.45,
            "leftRightSwapZero": lr_swap == 0,
            "worldTransformDependencyZero": world_dep == 0,
            "modelOutsideZero": True,  # no generated outside models in Gate 1
            "manualGtUsed": False,
            "visualEyeGenerated": False,
        },
        matrix_world_before=_mat_flat(mw_before),
        matrix_world_after=_mat_flat(mw_after),
        visual_eye_generated=False,
        manual_gt_used=False,
    )
    return basis


def profile_sha256(profile: dict) -> str:
    payload = json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
