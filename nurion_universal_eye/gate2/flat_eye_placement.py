"""
Gate 2 — Flat Eye Placement.

Uses locked Gate 1 Universal Face Basis. Creates only NURION_EyePlane.L/R.
No convex eyeball, gaze, blink, or expression.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mathutils import Vector

from ..gate1.universal_face_basis import HeadAxes, UniversalFaceBasis, build_universal_face_basis, _v3
from .eye_plane_mesh import create_eye_plane_object, remove_eye_planes
from .multiview_depth import build_world_bvh, fuse_aperture_depth, sample_depth_along_yaw
from .parameters import GATE2_PARAMETERS, parameter_hash

GATE1_LOCK_HASHES = {
    "universal_face_basis.py": "63bc179e68cd03dda345ffc2295abb1fb97e700074deb1888250a13b15f83647",
    "multiview_evidence.py": "1968d12dbb307c6937ac84574bc405055fa5b24d890fc82ba47fdab3ca4fe108",
    "face_basis_validator.py": "324d2e075ee53fefa474831809a6305f05ca13c07ce369255cb8522110081e78",
}


def assert_gate1_sources_locked(root: Path) -> None:
    g1 = root / "nurion_universal_eye" / "gate1"
    for name, expected in GATE1_LOCK_HASHES.items():
        path = g1 / name
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        if h != expected:
            raise RuntimeError(f"Gate1 source mutated ({name}): {h} != {expected}")


@dataclass
class EyePlaneResult:
    side: str
    origin_world: Vector
    normal_out: Vector
    right: Vector
    up: Vector
    width: float
    height: float
    eye_unit: float
    aperture_inner: Vector
    aperture_outer: Vector
    local_center: Vector
    confidence: float
    evidence: Dict = field(default_factory=dict)
    scores: Dict = field(default_factory=dict)


@dataclass
class FlatEyePlacementResult:
    basis: UniversalFaceBasis
    planes: Dict[str, EyePlaneResult] = field(default_factory=dict)
    parameter_hash: str = ""
    manual_gt: bool = False
    convex_eye: bool = False
    motion: str = "INACTIVE"
    expression: str = "INACTIVE"
    correction_log: List[Dict] = field(default_factory=list)

    def to_profile(self) -> dict:
        planes = {}
        for side, p in self.planes.items():
            planes[side] = {
                "name": f"NURION_EyePlane.{side}",
                "side": side,
                "originWorld": _v3(p.origin_world),
                "normalOut": _v3(p.normal_out),
                "right": _v3(p.right),
                "up": _v3(p.up),
                "width": round(float(p.width), 6),
                "height": round(float(p.height), 6),
                "eyeUnit": round(float(p.eye_unit), 6),
                "apertureInner": _v3(p.aperture_inner),
                "apertureOuter": _v3(p.aperture_outer),
                "centerHeadLocal": _v3(p.local_center),
                "confidence": round(float(p.confidence), 4),
                "evidence": p.evidence,
                "scores": p.scores,
            }
        return {
            "schema": "NURION_FLAT_EYE_PLACEMENT_PROFILE",
            "version": "0.3.0-alpha.3-gate2",
            "parameterHash": self.parameter_hash,
            "gate1MeshName": self.basis.mesh_name,
            "planes": planes,
            "manualGt": False,
            "convexEye": False,
            "motion": "INACTIVE",
            "expression": "INACTIVE",
            "correctionLog": self.correction_log,
            "gate1Confidences": self.basis.confidences,
        }


def _orthonormalize_plane(normal_out: Vector, axes: HeadAxes) -> Tuple[Vector, Vector, Vector]:
    n = normal_out.normalized()
    # Prefer facing roughly along face forward.
    if n.dot(axes.forward) < 0:
        n = -n
    # Right: project character right onto plane
    right = (axes.right - n * axes.right.dot(n))
    if right.length < 1e-8:
        right = axes.up.cross(n)
    right.normalize()
    up = n.cross(right).normalized()
    # Keep up roughly aligned with head up
    if up.dot(axes.up) < 0:
        up = -up
        right = -right
    return n, right, up


def _surface_metrics(
    bvh,
    origin: Vector,
    normal_out: Vector,
    eye_unit: float,
) -> Dict[str, float]:
    # Nearest surface from plane center
    loc, normal, _i, dist = bvh.find_nearest(origin)
    if loc is None:
        return {"nearestDist": 1e9, "penetration": 1e9, "protrusion": 1e9, "floating": 1e9}
    # Signed: positive if origin is outside along outward normal approx
    delta = origin - loc
    signed = float(delta.dot(normal_out.normalized()))
    penetration = max(0.0, -signed)
    protrusion = max(0.0, signed)
    floating = float(dist)
    return {
        "nearestDist": floating,
        "penetration": penetration,
        "protrusion": protrusion,
        "floating": floating,
        "signedGap": signed,
    }


def _score_plane(metrics: Dict[str, float], eye_unit: float, params: dict) -> float:
    """Higher is better. Penalize penetration/float/excess protrusion."""
    pen = metrics["penetration"] / max(eye_unit, 1e-6)
    flo = metrics["floating"] / max(eye_unit, 1e-6)
    pro = metrics["protrusion"] / max(eye_unit, 1e-6)
    target = float(params["plane"]["surfaceGapEyeUnits"])
    gap_err = abs(pro - target) if metrics["signedGap"] >= 0 else pen + target
    score = 1.0 - 3.0 * pen - 1.5 * max(0.0, flo - target) - 0.8 * gap_err - 0.5 * max(0.0, pro - params["plane"]["maxProtrusionEyeUnits"])
    return float(score)


def _place_one_side(
    *,
    mesh_obj,
    bvh,
    basis: UniversalFaceBasis,
    side: str,
) -> EyePlaneResult:
    axes = basis.axes
    assert axes is not None
    er = basis.eye_regions[side]
    params = GATE2_PARAMETERS
    eu = float(er.eye_unit)

    inner = er.inner_world
    outer = er.outer_world
    mid = (inner + outer) * 0.5
    mid_l = axes.to_local(mid)
    # Provisional local center (aperture X/Z, centroid Y as seed for ray aim)
    center_seed = Vector((float(mid_l.x), float(axes.to_local(er.centroid_world).y), float(mid_l.z)))

    yaw_sign = 1.0 if side == "L" else -1.0
    samples = []
    max_xz = float(params["depth"].get("maxXzDevEyeUnits", 0.40))
    for yaw_abs in [0.0] + list(params["depth"]["yawDeg"]):
        # For 30°, also probe nearby angles but store canonical yaw tag.
        probe_angles = [yaw_abs]
        if yaw_abs == 30.0:
            probe_angles = [22.0, 30.0, 38.0]
        best_s = None
        for probe_abs in probe_angles:
            yaw = probe_abs * yaw_sign if probe_abs != 0.0 else 0.0
            for dx, dz in (
                (0.0, 0.0),
                (0.12 * eu * yaw_sign, 0.0),
                (0.0, 0.08 * eu),
                (0.0, -0.08 * eu),
                (-0.08 * eu * yaw_sign, 0.0),
                (0.20 * eu * yaw_sign, 0.05 * eu),
            ):
                aim = Vector((center_seed.x + dx, center_seed.y, center_seed.z + dz))
                for start_eu in (
                    float(params["depth"]["rayStartEyeUnits"]),
                    float(params["depth"]["rayStartEyeUnits"]) * 0.55,
                ):
                    s = sample_depth_along_yaw(
                        bvh,
                        axes,
                        aim,
                        yaw_deg=yaw,
                        eye_unit=eu,
                        ray_start_eu=start_eu,
                        max_xz_dev_eu=max_xz if yaw_abs == 0.0 else max_xz * 1.6,
                    )
                    if s is None:
                        continue
                    # Canonicalize reported yaw to requested gate angle.
                    s = dict(s)
                    s["yawDeg"] = yaw_abs * yaw_sign if yaw_abs != 0.0 else 0.0
                    s["probeYawDeg"] = yaw
                    if best_s is None or float(s.get("xzErrorEyeUnits", 99)) < float(best_s.get("xzErrorEyeUnits", 99)):
                        best_s = s
        if best_s is None and yaw_abs != 0.0:
            yaw = yaw_abs * yaw_sign
            s = sample_depth_along_yaw(
                bvh,
                axes,
                center_seed,
                yaw_deg=yaw,
                eye_unit=eu,
                ray_start_eu=float(params["depth"]["rayStartEyeUnits"]),
                max_xz_dev_eu=1.6,
            )
            if s is not None:
                loc = s["hitLocal"]
                if (float(loc.x) * yaw_sign > 0) and abs(float(loc.z) - float(center_seed.z)) < eu * 1.4:
                    best_s = dict(s)
                    best_s["yawDeg"] = yaw
                    best_s["fallback"] = True
        if best_s is not None:
            samples.append(best_s)

    hit_world, n_fused, fuse_ev = fuse_aperture_depth(
        samples,
        front_w=float(params["depth"]["frontWeight"]),
        w30=float(params["depth"]["yaw30Weight"]),
        w60=float(params["depth"]["yaw60Weight"]),
        forward=axes.forward,
    )
    if hit_world is None:
        hit_world = er.centroid_world.copy()
        n_fused = axes.forward.copy()
        fuse_ev = {"method": "CENTROID_FALLBACK"}

    fused_y = float(fuse_ev.get("fusedLocalY", axes.to_local(hit_world).y))
    local_center = Vector((float(mid_l.x), fused_y, float(mid_l.z)))
    seed_origin = axes.to_world(local_center)

    # Snap seed onto surface along head forward if needed, then use surface normal.
    loc_n, normal_n, _i, dist_n = bvh.find_nearest(seed_origin)
    if loc_n is not None:
        seed_origin = loc_n.copy()
        if normal_n is not None:
            n_use = normal_n.copy()
            if n_use.dot(axes.forward) < 0:
                n_use = -n_use
            n_fused = (n_use * 0.75 + axes.forward * 0.25).normalized()
    if n_fused is None:
        n_fused = axes.forward.copy()
    normal_out, right, up = _orthonormalize_plane(n_fused, axes)

    width = eu * float(params["plane"]["widthEyeUnits"])
    height = eu * float(params["plane"]["heightEyeUnits"])

    best = None
    best_score = -1e9
    log = []
    for gap_eu in params["correction"]["gapCandidatesEyeUnits"]:
        origin = seed_origin + normal_out * (eu * float(gap_eu))
        metrics = _surface_metrics(bvh, origin, normal_out, eu)
        score = _score_plane(metrics, eu, params)
        log.append({"gapEyeUnits": gap_eu, "score": round(score, 4), "metrics": {k: round(float(v), 6) for k, v in metrics.items()}})
        if score > best_score:
            best_score = score
            best = (origin, metrics, gap_eu)

    assert best is not None
    origin, metrics, gap_eu = best
    local_center = axes.to_local(origin)

    # Front-center error: aperture XZ vs plane XZ
    front_err = Vector((float(mid_l.x) - float(local_center.x), 0.0, float(mid_l.z) - float(local_center.z))).length / max(eu, 1e-6)
    conf = min(0.93, 0.45 + 0.1 * len(samples) + 0.2 * max(0.0, best_score))
    return EyePlaneResult(
        side=side,
        origin_world=origin,
        normal_out=normal_out,
        right=right,
        up=up,
        width=width,
        height=height,
        eye_unit=eu,
        aperture_inner=inner,
        aperture_outer=outer,
        local_center=local_center,
        confidence=conf,
        evidence={
            "depthFusion": fuse_ev,
            "samples": [
                {
                    "yawDeg": s["yawDeg"],
                    "depthLocalY": round(float(s["depthLocalY"]), 6),
                    "hitWorld": _v3(s["hitWorld"]),
                }
                for s in samples
            ],
            "selectedGapEyeUnits": gap_eu,
            "correctionCandidates": log,
            "apertureMethod": er.evidence.get("method"),
        },
        scores={
            "frontCenterErrorEyeUnits": round(float(front_err), 4),
            "bestScore": round(float(best_score), 4),
            **{k: round(float(v) / max(eu, 1e-6), 4) if k != "signedGap" else round(float(v), 6) for k, v in metrics.items()},
        },
    )


def place_flat_eye_planes(
    *,
    mesh_name: str = "",
    create_meshes: bool = True,
    root: Optional[Path] = None,
) -> FlatEyePlacementResult:
    if root is not None:
        assert_gate1_sources_locked(root)

    basis = build_universal_face_basis(mesh_name=mesh_name)
    if basis.axes is None or set(basis.eye_regions.keys()) != {"L", "R"}:
        raise RuntimeError("Gate1 basis incomplete for Flat Eye Placement")

    import bpy

    mesh = bpy.data.objects.get(basis.mesh_name)
    if mesh is None:
        raise RuntimeError(f"Mesh missing: {basis.mesh_name}")

    # World transform independence: capture before/after
    mw_before = [round(float(mesh.matrix_world[i][j]), 6) for i in range(4) for j in range(4)]
    bvh = build_world_bvh(mesh)

    if create_meshes:
        remove_eye_planes()

    planes: Dict[str, EyePlaneResult] = {}
    corr_log: List[Dict] = []
    for side in ("L", "R"):
        pr = _place_one_side(mesh_obj=mesh, bvh=bvh, basis=basis, side=side)
        planes[side] = pr
        corr_log.extend({"side": side, **c} for c in pr.evidence.get("correctionCandidates", []))
        if create_meshes:
            create_eye_plane_object(
                side=side,
                origin=pr.origin_world,
                right=pr.right,
                up=pr.up,
                normal_out=pr.normal_out,
                width=pr.width,
                height=pr.height,
                thickness=pr.eye_unit * float(GATE2_PARAMETERS["plane"]["thicknessEyeUnits"]),
            )

    mw_after = [round(float(mesh.matrix_world[i][j]), 6) for i in range(4) for j in range(4)]
    if mw_before != mw_after:
        raise RuntimeError("Character matrix_world mutated during Gate2 placement")

    # Ensure no convex eyeballs were created
    for name in ("NURION_Eyeball.L", "NURION_Eyeball.R", "NURION_VisualEye.L", "NURION_VisualEye.R"):
        if bpy.data.objects.get(name) is not None:
            raise RuntimeError(f"Convex/visual eye object present during Gate2: {name}")

    return FlatEyePlacementResult(
        basis=basis,
        planes=planes,
        parameter_hash=parameter_hash(),
        correction_log=corr_log,
    )


def profile_sha256(profile: dict) -> str:
    payload = json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
