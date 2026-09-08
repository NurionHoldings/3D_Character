"""Gate 4A — move diagnostic iris/pupil on frozen EyeDome surface."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mathutils import Vector

from ..gate3.convex_conversion import convert_eye_domes
from .gaze_meshes import (
    create_disc,
    create_ellipse_ring,
    create_empty,
    dome_height_at,
    place_on_plane_frame,
    remove_gaze_diagnostics,
)
from .lock_guard import assert_gate123_locked
from .parameters import GATE4A_PARAMETERS, parameter_hash
from .safe_ellipse import (
    GazeSafeEllipse,
    build_safe_ellipse,
    clamp_to_usable,
    ellipse_contains_disk,
    iris_edge_escape_eu,
)


def _v3(v: Vector) -> List[float]:
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def _dome_snapshot(side: str) -> Optional[Dict]:
    import bpy

    obj = bpy.data.objects.get(f"NURION_EyeDome.{side}")
    if obj is None:
        return None
    m = obj.matrix_world.copy()
    loc = m.translation.copy()
    rot = m.to_quaternion().copy()
    return {
        "location": _v3(loc),
        "rotation": [round(float(x), 8) for x in rot],
        "matrix": [[round(float(m[i][j]), 8) for j in range(4)] for i in range(4)],
    }


def _bulge_from_dome(plane, side: str) -> float:
    import bpy

    obj = bpy.data.objects.get(f"NURION_EyeDome.{side}")
    if obj is None or obj.data is None:
        return 0.0
    # max local Z in object space (dome bulge)
    zs = [float(v.co.z) for v in obj.data.vertices]
    return max(zs) if zs else 0.0


def _gaze_dir_angle_deg(a: Vector, b: Vector) -> float:
    an = a.normalized()
    bn = b.normalized()
    c = max(-1.0, min(1.0, float(an.dot(bn))))
    return math.degrees(math.acos(c))


@dataclass
class EyeGazeState:
    side: str
    local_xy: Vector
    world: Vector
    gaze_dir: Vector
    iris_escape_eu: float
    inside: bool


@dataclass
class GazeFrameResult:
    name: str
    target_world: Vector
    eyes: Dict[str, EyeGazeState] = field(default_factory=dict)
    convergence_deg: float = 0.0
    divergence_fail: bool = False
    cross_fail: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class GazeMotionResult:
    convex: object
    ellipses: Dict[str, GazeSafeEllipse]
    bulges: Dict[str, float]
    dome_before: Dict[str, Optional[Dict]]
    dome_after: Dict[str, Optional[Dict]]
    frames: List[GazeFrameResult]
    reorder_frames: List[GazeFrameResult]
    center_return_error_eu: float
    parameter_hash: str
    gate123_lock: Dict
    rejected: List[str] = field(default_factory=list)

    def to_profile(self) -> dict:
        frames = []
        for fr in self.frames:
            eyes = {}
            for side, st in fr.eyes.items():
                eyes[side] = {
                    "localXY": _v3(st.local_xy),
                    "world": _v3(st.world),
                    "gazeDir": _v3(st.gaze_dir),
                    "irisEscapeEU": round(float(st.iris_escape_eu), 6),
                    "inside": bool(st.inside),
                }
            frames.append(
                {
                    "name": fr.name,
                    "targetWorld": _v3(fr.target_world),
                    "eyes": eyes,
                    "convergenceDeg": round(float(fr.convergence_deg), 4),
                    "divergenceFail": bool(fr.divergence_fail),
                    "crossFail": bool(fr.cross_fail),
                    "notes": list(fr.notes),
                }
            )
        ell = {}
        for side, e in self.ellipses.items():
            ell[side] = {
                "centerLocal": _v3(e.center_local),
                "rx": round(float(e.rx), 6),
                "ry": round(float(e.ry), 6),
                "irisRadius": round(float(e.iris_radius), 6),
                "pupilRadius": round(float(e.pupil_radius), 6),
            }
        return {
            "schema": "NURION_GATE4A_GAZE_MOTION_PROFILE",
            "version": GATE4A_PARAMETERS["version"],
            "parameterHash": self.parameter_hash,
            "gate2ParameterHash": GATE4A_PARAMETERS["requiredGate2ParameterHash"],
            "gate3ParameterHash": GATE4A_PARAMETERS["requiredGate3ParameterHash"],
            "ellipses": ell,
            "bulges": {k: round(float(v), 6) for k, v in self.bulges.items()},
            "domeBefore": self.dome_before,
            "domeAfter": self.dome_after,
            "frames": frames,
            "centerReturnErrorEU": round(float(self.center_return_error_eu), 6),
            "rejectedTargets": list(self.rejected),
            "blink": "HOLD",
            "expression": "INACTIVE",
            "headMotion": "INACTIVE",
            "lipSync": "INACTIVE",
            "beautyMaterial": "HOLD",
            "outputs": [
                "NURION_GazeControl",
                "NURION_GazeAnchor.L",
                "NURION_GazeAnchor.R",
                "NURION_DiagnosticIris.L",
                "NURION_DiagnosticIris.R",
                "NURION_DiagnosticPupil.L",
                "NURION_DiagnosticPupil.R",
                "NURION_GazeSafeEllipse.L",
                "NURION_GazeSafeEllipse.R",
            ],
        }


def _eye_pivot(plane, bulge: float) -> Vector:
    # Shallow-dome pivot slightly behind plane along -normal
    return plane.origin_world - plane.normal_out.normalized() * (0.55 * float(bulge) + 1e-5)


def _ideal_gaze(pivot: Vector, target: Vector, normal: Vector) -> Vector:
    g = target - pivot
    if g.length < 1e-12:
        return normal.normalized()
    return g.normalized()


def _gaze_to_local(
    plane,
    ellipse: GazeSafeEllipse,
    pivot: Vector,
    target: Vector,
    axes,
) -> Tuple[Vector, Vector]:
    """Map per-eye 3D target direction into safe-ellipse local XY via head-space angles."""
    n = plane.normal_out.normalized()
    ideal = _ideal_gaze(pivot, target, n)
    g = GATE4A_PARAMETERS["gaze"]
    yaw_max = math.radians(float(g["yawCardinalDeg"]))
    pitch_max = math.radians(float(g["pitchCardinalDeg"]))
    fwd = axes.forward.normalized()
    right = axes.right.normalized()
    up = axes.up.normalized()
    # Per-eye yaw/pitch from that eye's pivot to the shared 3D target (enables near convergence)
    yaw = math.atan2(float(ideal.dot(right)), max(1e-6, float(ideal.dot(fwd))))
    pitch = math.atan2(float(ideal.dot(up)), max(1e-6, float(ideal.dot(fwd))))
    u = max(-1.0, min(1.0, yaw / max(yaw_max, 1e-6)))
    v = max(-1.0, min(1.0, pitch / max(pitch_max, 1e-6)))
    rn = u * u + v * v
    if rn > 1.0:
        s = rn ** 0.5
        u /= s
        v /= s
    # Offset along plane axes aligned with head right/up projections
    pr = plane.right.normalized()
    pu = plane.up.normalized()
    # If plane.right opposes head.right, flip u so +yaw still means character-right look
    if pr.dot(right) < 0:
        u = -u
    if pu.dot(up) < 0:
        v = -v
    local = Vector(
        (
            float(ellipse.center_local.x) + u * ellipse.usable_rx,
            float(ellipse.center_local.y) + v * ellipse.usable_ry,
            0.0,
        )
    )
    local = clamp_to_usable(ellipse, local)
    return local, ideal


def _apply_eye(
    *,
    plane,
    ellipse: GazeSafeEllipse,
    bulge: float,
    target: Vector,
    iris_obj,
    pupil_obj,
    anchor_obj,
    axes,
) -> EyeGazeState:
    pivot = _eye_pivot(plane, bulge)
    local, _ideal = _gaze_to_local(plane, ellipse, pivot, target, axes)
    z = dome_height_at(plane, bulge, local)
    right = plane.right.normalized()
    up = plane.up.normalized()
    normal = plane.normal_out.normalized()
    place_on_plane_frame(
        iris_obj,
        origin=plane.origin_world,
        right=right,
        up=up,
        normal=normal,
        local_xy=local,
        dome_z=z,
    )
    place_on_plane_frame(
        pupil_obj,
        origin=plane.origin_world,
        right=right,
        up=up,
        normal=normal,
        local_xy=local,
        dome_z=z + 1.5e-4,
    )
    world = plane.origin_world + right * float(local.x) + up * float(local.y) + normal * float(z)
    anchor_obj.location = world
    gaze2 = world - pivot
    if gaze2.length > 1e-12:
        gaze2.normalize()
    else:
        gaze2 = normal
    escape = iris_edge_escape_eu(ellipse, local, float(plane.eye_unit))
    inside = ellipse_contains_disk(ellipse, local, ellipse.iris_radius)
    return EyeGazeState(
        side=plane.side,
        local_xy=local,
        world=world,
        gaze_dir=gaze2,
        iris_escape_eu=float(escape),
        inside=bool(inside),
    )


def _binocular_flags(
    eyes: Dict[str, EyeGazeState],
    axes,
    target: Vector,
    *,
    frame_name: str,
    pivots: Dict[str, Vector],
    ellipses: Dict[str, GazeSafeEllipse],
) -> Tuple[float, bool, bool, List[str]]:
    notes: List[str] = []
    if "L" not in eyes or "R" not in eyes:
        return 0.0, True, True, ["missing eye"]
    max_div = float(GATE4A_PARAMETERS["gaze"]["maxDivergenceDeg"])
    max_conv = float(GATE4A_PARAMETERS["gaze"]["maxConvergenceDeg"])

    il = _ideal_gaze(pivots["L"], target, axes.forward)
    ir = _ideal_gaze(pivots["R"], target, axes.forward)
    # Authoritative binocular angle = angle between per-eye ideal target directions
    conv = _gaze_dir_angle_deg(il, ir)

    def _u(side: str) -> float:
        e = ellipses[side]
        dx = float(eyes[side].local_xy.x) - float(e.center_local.x)
        return dx / max(e.usable_rx, 1e-9)

    u_l, u_r = _u("L"), _u("R")
    base = frame_name.replace("REORDER_", "").replace("FINAL_", "")
    frontal = base in ("CENTER", "NEAR", "FAR", "RETURN_CENTER", "MICRO_LEFT", "MICRO_RIGHT", "UP", "DOWN")

    # Divergence = both eyes biased outward on ellipse (L− / R+)
    divergence_fail = frontal and (u_l < -0.35 and u_r > 0.35)
    # Cross-eye = both eyes biased hard inward beyond natural near convergence
    cross_fail = (u_l > 0.92 and u_r < -0.92) or (frontal and conv > max_conv)
    if divergence_fail:
        notes.append(f"divergence uL={u_l:.2f} uR={u_r:.2f}")
    if cross_fail:
        notes.append(f"cross-eye uL={u_l:.2f} uR={u_r:.2f} idealConv={conv:.2f}")
    return conv, divergence_fail, cross_fail, notes


def _build_targets(axes, planes: Dict, eu: float) -> List[Tuple[str, Vector]]:
    g = GATE4A_PARAMETERS["gaze"]
    mid = 0.5 * (planes["L"].origin_world + planes["R"].origin_world)
    fwd = axes.forward.normalized()
    right = axes.right.normalized()
    up = axes.up.normalized()
    far = eu * float(g["farTargetEyeUnits"])
    near = eu * float(g["nearTargetEyeUnits"])
    yaw = math.radians(float(g["yawCardinalDeg"]))
    pitch = math.radians(float(g["pitchCardinalDeg"]))
    diag = float(g["diagonalScale"])
    micro = eu * float(g["microOffsetEyeUnits"])

    def aim(yaw_r: float, pitch_r: float, dist: float) -> Vector:
        d = (
            fwd * math.cos(yaw_r) * math.cos(pitch_r)
            + right * math.sin(yaw_r) * math.cos(pitch_r)
            + up * math.sin(pitch_r)
        )
        return mid + d.normalized() * dist

    targets: List[Tuple[str, Vector]] = [
        ("CENTER", aim(0.0, 0.0, far)),
        ("LEFT", aim(yaw, 0.0, far)),
        ("RIGHT", aim(-yaw, 0.0, far)),
        ("UP", aim(0.0, pitch, far)),
        ("DOWN", aim(0.0, -pitch, far)),
        ("UP_LEFT", aim(yaw * diag, pitch * diag, far)),
        ("UP_RIGHT", aim(-yaw * diag, pitch * diag, far)),
        ("DOWN_LEFT", aim(yaw * diag, -pitch * diag, far)),
        ("DOWN_RIGHT", aim(-yaw * diag, -pitch * diag, far)),
        ("NEAR", aim(0.0, 0.0, near)),
        ("FAR", aim(0.0, 0.0, far * 1.5)),
        ("MICRO_LEFT", aim(0.0, 0.0, far) + right * micro),
        ("MICRO_RIGHT", aim(0.0, 0.0, far) - right * micro),
        ("RETURN_CENTER", aim(0.0, 0.0, far)),
    ]
    return targets


def run_gaze_motion(
    *,
    mesh_name: str = "",
    root: Optional[Path] = None,
    create_meshes: bool = True,
    apply_final: str = "CENTER",
) -> GazeMotionResult:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate123_locked(root)

    convex = convert_eye_domes(mesh_name=mesh_name, root=root, create_meshes=True)
    planes = convex.flat.planes
    axes = convex.flat.basis.axes
    eu = sum(float(p.eye_unit) for p in planes.values()) / max(len(planes), 1)

    dome_before = {side: _dome_snapshot(side) for side in ("L", "R")}
    bulges = {side: _bulge_from_dome(planes[side], side) for side in planes}

    ellipses = {side: build_safe_ellipse(planes[side], bulge_m=bulges[side]) for side in planes}

    import bpy

    if create_meshes:
        remove_gaze_diagnostics()

    iris = {}
    pupil = {}
    anchors = {}
    for side, plane in planes.items():
        e = ellipses[side]
        rgba_e = (0.2, 0.95, 0.55, 1.0) if side == "L" else (0.95, 0.55, 0.2, 1.0)
        rgba_i = (0.15, 0.55, 1.0, 1.0) if side == "L" else (0.2, 0.85, 1.0, 1.0)
        rgba_p = (0.02, 0.02, 0.05, 1.0)
        if create_meshes:
            ring = create_ellipse_ring(
                name=f"NURION_GazeSafeEllipse.{side}",
                rx=e.rx,
                ry=e.ry,
                rgba=rgba_e,
            )
            # place ellipse on plane (z~0), centered at ellipse center
            place_on_plane_frame(
                ring,
                origin=plane.origin_world,
                right=plane.right.normalized(),
                up=plane.up.normalized(),
                normal=plane.normal_out.normalized(),
                local_xy=e.center_local,
                dome_z=0.0005,
            )
            # ring geometry is centered at 0; shift by baking offset into matrix translation already via local_xy
            iris[side] = create_disc(
                name=f"NURION_DiagnosticIris.{side}",
                radius=e.iris_radius,
                rgba=rgba_i,
            )
            pupil[side] = create_disc(
                name=f"NURION_DiagnosticPupil.{side}",
                radius=e.pupil_radius,
                rgba=rgba_p,
            )
            anchors[side] = create_empty(f"NURION_GazeAnchor.{side}", plane.origin_world)
        else:
            iris[side] = bpy.data.objects[f"NURION_DiagnosticIris.{side}"]
            pupil[side] = bpy.data.objects[f"NURION_DiagnosticPupil.{side}"]
            anchors[side] = bpy.data.objects[f"NURION_GazeAnchor.{side}"]

    mid = 0.5 * (planes["L"].origin_world + planes["R"].origin_world)
    control = create_empty("NURION_GazeControl", mid + axes.forward.normalized() * (eu * float(GATE4A_PARAMETERS["gaze"]["farTargetEyeUnits"]))) if create_meshes else bpy.data.objects["NURION_GazeControl"]

    targets = _build_targets(axes, planes, eu)
    frames: List[GazeFrameResult] = []
    rejected: List[str] = []
    center_local = {}

    pivots = {side: _eye_pivot(planes[side], bulges[side]) for side in planes}

    def eval_target(name: str, target: Vector) -> GazeFrameResult:
        control.location = target
        eyes: Dict[str, EyeGazeState] = {}
        for side, plane in planes.items():
            st = _apply_eye(
                plane=plane,
                ellipse=ellipses[side],
                bulge=bulges[side],
                target=target,
                iris_obj=iris[side],
                pupil_obj=pupil[side],
                anchor_obj=anchors[side],
                axes=axes,
            )
            eyes[side] = st
        conv, div_f, cross_f, notes = _binocular_flags(
            eyes, axes, target, frame_name=name, pivots=pivots, ellipses=ellipses
        )
        if div_f or cross_f:
            rejected.append(name)
        return GazeFrameResult(
            name=name,
            target_world=target.copy(),
            eyes=eyes,
            convergence_deg=conv,
            divergence_fail=div_f,
            cross_fail=cross_f,
            notes=notes,
        )

    for name, target in targets:
        fr = eval_target(name, target)
        frames.append(fr)
        if name == "CENTER":
            center_local = {s: fr.eyes[s].local_xy.copy() for s in fr.eyes}

    # reorder pass (different sequence)
    reorder_names = [
        "FAR",
        "DOWN_RIGHT",
        "MICRO_LEFT",
        "UP",
        "NEAR",
        "LEFT",
        "RETURN_CENTER",
        "CENTER",
        "RIGHT",
        "DOWN",
        "UP_LEFT",
        "MICRO_RIGHT",
        "UP_RIGHT",
        "DOWN_LEFT",
    ]
    by_name = {n: t for n, t in targets}
    reorder_frames: List[GazeFrameResult] = []
    for name in reorder_names:
        if name in by_name:
            reorder_frames.append(eval_target(f"REORDER_{name}", by_name[name]))

    # final pose
    final_name = apply_final if apply_final in by_name else "CENTER"
    final_fr = eval_target(final_name, by_name[final_name])
    frames.append(GazeFrameResult(
        name="FINAL_" + final_fr.name,
        target_world=final_fr.target_world,
        eyes=final_fr.eyes,
        convergence_deg=final_fr.convergence_deg,
        divergence_fail=final_fr.divergence_fail,
        cross_fail=final_fr.cross_fail,
        notes=final_fr.notes,
    ))

    # center return error from RETURN_CENTER vs CENTER
    ret = next((f for f in frames if f.name == "RETURN_CENTER"), None)
    cen = next((f for f in frames if f.name == "CENTER"), None)
    cre = 0.0
    if ret and cen:
        for side in ("L", "R"):
            d = (ret.eyes[side].local_xy - cen.eyes[side].local_xy).length
            cre = max(cre, d / max(eu, 1e-9))

    dome_after = {side: _dome_snapshot(side) for side in ("L", "R")}

    return GazeMotionResult(
        convex=convex,
        ellipses=ellipses,
        bulges=bulges,
        dome_before=dome_before,
        dome_after=dome_after,
        frames=frames,
        reorder_frames=reorder_frames,
        center_return_error_eu=float(cre),
        parameter_hash=parameter_hash(),
        gate123_lock=lock_info,
        rejected=rejected,
    )
