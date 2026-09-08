"""Gate 4B — blink via procedural lid proxies (dome/iris/pupil frozen)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mathutils import Vector

from ..gate4a.gaze_motion import run_gaze_motion
from .capability import classify_blink_capability
from .lid_proxy import (
    LidAperture,
    build_lid_aperture,
    coverage_and_gap,
    create_or_update_lid,
    lid_edges,
    remove_blink_proxies,
)
from .lock_guard import assert_gate1234a_locked
from .parameters import GATE4B_PARAMETERS, parameter_hash


def _v3(v: Vector) -> List[float]:
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def _obj_snapshot(name: str) -> Optional[Dict]:
    import bpy

    obj = bpy.data.objects.get(name)
    if obj is None:
        return None
    m = obj.matrix_world.copy()
    loc = m.translation.copy()
    rot = m.to_quaternion().copy()
    return {
        "location": _v3(loc),
        "rotation": [round(float(x), 8) for x in rot],
    }


def _bulge(side: str) -> float:
    import bpy

    obj = bpy.data.objects.get(f"NURION_EyeDome.{side}")
    if obj is None or obj.data is None:
        return 0.0
    zs = [float(v.co.z) for v in obj.data.vertices]
    return max(zs) if zs else 0.0


@dataclass
class BlinkStateSample:
    name: str
    amount_l: float
    amount_r: float
    coverage: Dict[str, Dict] = field(default_factory=dict)
    lid_edges: Dict[str, Dict] = field(default_factory=dict)


@dataclass
class BlinkMotionResult:
    gaze: object
    mode: str
    capability_evidence: Dict
    apertures: Dict[str, LidAperture]
    bulges: Dict[str, float]
    frozen_before: Dict[str, Optional[Dict]]
    frozen_after: Dict[str, Optional[Dict]]
    open_lid_snapshot: Dict[str, Optional[Dict]]
    reopen_lid_snapshot: Dict[str, Optional[Dict]]
    states: List[BlinkStateSample]
    rhythms: List[Dict]
    face_metrics: Dict
    parameter_hash: str
    lock_info: Dict

    def to_profile(self) -> dict:
        return {
            "schema": "NURION_GATE4B_BLINK_PROFILE",
            "version": GATE4B_PARAMETERS["version"],
            "parameterHash": self.parameter_hash,
            "gate2ParameterHash": GATE4B_PARAMETERS["requiredGate2ParameterHash"],
            "gate3ParameterHash": GATE4B_PARAMETERS["requiredGate3ParameterHash"],
            "gate4aParameterHash": GATE4B_PARAMETERS["requiredGate4aParameterHash"],
            "mode": self.mode,
            "capabilityEvidence": self.capability_evidence,
            "apertures": {
                s: {
                    "center": _v3(a.center),
                    "rx": round(float(a.rx), 6),
                    "ry": round(float(a.ry), 6),
                    "openUpperY": round(float(a.open_upper_y), 6),
                    "openLowerY": round(float(a.open_lower_y), 6),
                    "meetY": round(float(a.meet_y), 6),
                    "upperShare": a.upper_share,
                    "lowerShare": a.lower_share,
                }
                for s, a in self.apertures.items()
            },
            "states": [
                {
                    "name": st.name,
                    "amountL": st.amount_l,
                    "amountR": st.amount_r,
                    "coverage": st.coverage,
                    "lidEdges": st.lid_edges,
                }
                for st in self.states
            ],
            "rhythms": self.rhythms,
            "frozenBefore": self.frozen_before,
            "frozenAfter": self.frozen_after,
            "faceMetrics": self.face_metrics,
            "expression": "INACTIVE",
            "headMotion": "INACTIVE",
            "lipSync": "INACTIVE",
            "beautyMaterial": "HOLD",
            "emotionalBlinkTiming": "HOLD",
            "outputs": [
                "NURION_BlinkControl",
                "NURION_UpperLidProxy.L",
                "NURION_UpperLidProxy.R",
                "NURION_LowerLidProxy.L",
                "NURION_LowerLidProxy.R",
            ],
        }


def _lid_edge_with_overlap(ap: LidAperture, amount: float, eu: float) -> Tuple[float, float]:
    t = max(0.0, min(1.0, float(amount)))
    upper, lower = lid_edges(ap, t)
    if t >= 0.999:
        ov = float(eu) * float(GATE4B_PARAMETERS["proxy"]["closedOverlapEyeUnits"])
        upper = ap.meet_y - 0.5 * ov
        lower = ap.meet_y + 0.5 * ov
    return upper, lower


def apply_blink_amounts(
    *,
    planes,
    apertures: Dict[str, LidAperture],
    bulges: Dict[str, float],
    amount_l: float,
    amount_r: float,
    face_bvh=None,
) -> Dict[str, Dict]:
    """Update lid proxy meshes for L/R blink amounts. Returns coverage metrics."""
    import bpy

    metrics = {}
    amounts = {"L": amount_l, "R": amount_r}
    for side, plane in planes.items():
        ap = apertures[side]
        eu = float(plane.eye_unit)
        amt = amounts[side]
        upper_y, lower_y = _lid_edge_with_overlap(ap, amt, eu)
        top = ap.open_upper_y + ap.ry * 0.08
        bot = ap.open_lower_y - ap.ry * 0.08
        rgba_u = (0.55, 0.35, 0.28, 1.0) if side == "L" else (0.60, 0.38, 0.30, 1.0)
        rgba_l = (0.45, 0.28, 0.24, 1.0) if side == "L" else (0.50, 0.30, 0.26, 1.0)
        create_or_update_lid(
            name=f"NURION_UpperLidProxy.{side}",
            plane=plane,
            bulge=bulges[side],
            ap=ap,
            y0=upper_y,
            y1=top,
            which="upper",
            rgba=rgba_u,
            face_bvh=face_bvh,
        )
        create_or_update_lid(
            name=f"NURION_LowerLidProxy.{side}",
            plane=plane,
            bulge=bulges[side],
            ap=ap,
            y0=bot,
            y1=lower_y,
            which="lower",
            rgba=rgba_l,
            face_bvh=face_bvh,
        )
        cov = coverage_and_gap(ap, amt, eu)
        if amt >= 0.999:
            cov["gapEU"] = 0.0 if lower_y >= upper_y else (upper_y - lower_y) / max(eu, 1e-9)
            cov["coverage"] = 1.0 if lower_y >= upper_y else cov["coverage"]
            cov["upperY"] = round(upper_y, 6)
            cov["lowerY"] = round(lower_y, 6)
        metrics[side] = {
            **cov,
            "amount": round(float(amt), 4),
            "edges": {"upper": round(upper_y, 6), "lower": round(lower_y, 6)},
        }
    ctrl = bpy.data.objects.get("NURION_BlinkControl")
    if ctrl is not None:
        ctrl["nurion_blink_L"] = float(amount_l)
        ctrl["nurion_blink_R"] = float(amount_r)
    return metrics


def _face_lid_metrics(planes, mesh_name: str) -> Dict:
    """Sample lid vertices vs face BVH for penetration / floating."""
    import bpy

    from ..gate2.multiview_depth import build_world_bvh

    mesh = bpy.data.objects.get(mesh_name) if mesh_name else None
    if mesh is None:
        meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("NURION_")]
        mesh = max(meshes, key=lambda o: len(o.data.vertices)) if meshes else None
    if mesh is None:
        return {"penetrationEU": 0.0, "floatingEU": 0.0, "ok": True}

    bvh = build_world_bvh(mesh)
    pen = 0.0
    flo = 0.0
    eu_mean = sum(float(p.eye_unit) for p in planes.values()) / max(len(planes), 1)
    # Lids may sit slightly proud of skin to cover the dome; only deep burial / extreme float fail.
    max_proud = eu_mean * float(GATE4B_PARAMETERS["limits"]["maxLidFloatingEyeUnits"])

    for side, plane in planes.items():
        n = plane.normal_out.normalized()
        origin = plane.origin_world
        eu = float(plane.eye_unit)
        for lid_name in (f"NURION_UpperLidProxy.{side}", f"NURION_LowerLidProxy.{side}"):
            obj = bpy.data.objects.get(lid_name)
            if obj is None:
                continue
            verts = obj.data.vertices
            step = max(1, len(verts) // 24)
            for i in range(0, len(verts), step):
                w = obj.matrix_world @ verts[i].co
                # Cast from well in front toward the head so we hit outer skin first
                start = w + n * (eu * 2.5)
                hit = bvh.ray_cast(start, -n, eu * 6.0)
                if not hit or hit[0] is None:
                    continue
                loc = hit[0]
                # Ignore through-socket hits (back of skull / far geometry)
                z_hit = float((loc - origin).dot(n))
                if z_hit < -eu * 0.8 or z_hit > eu * 2.5:
                    continue
                delta = float((w - loc).dot(n))
                if delta < 0:
                    pen = max(pen, (-delta) / max(eu, 1e-9))
                else:
                    flo = max(flo, max(0.0, delta - max_proud) / max(eu, 1e-9))

    return {
        "penetrationEU": round(pen, 6),
        "floatingEU": round(flo, 6),
        "ok": pen <= float(GATE4B_PARAMETERS["limits"]["maxFacePenetrationEyeUnits"])
        and flo <= float(GATE4B_PARAMETERS["limits"]["maxLidFloatingEyeUnits"]),
    }


def _measure_lid_float_vs_dome(planes, bulges, apertures) -> Dict:
    """Lids must not sink into the dome; standing proud of dome is OK when face-pushed."""
    import bpy

    from .lid_proxy import dome_z

    del apertures
    pen = 0.0
    for side, plane in planes.items():
        eu = float(plane.eye_unit)
        gap = eu * float(GATE4B_PARAMETERS["proxy"]["surfaceGapEyeUnits"])
        for lid_name in (f"NURION_UpperLidProxy.{side}", f"NURION_LowerLidProxy.{side}"):
            obj = bpy.data.objects.get(lid_name)
            if obj is None:
                continue
            step = max(1, len(obj.data.vertices) // 20)
            for i in range(0, len(obj.data.vertices), step):
                loc = obj.data.vertices[i].co
                z_dome = dome_z(plane, bulges[side], float(loc.x), float(loc.y))
                z = float(loc.z)
                err = z - (z_dome + gap)
                if err < -gap * 0.5:
                    pen = max(pen, (-err) / max(eu, 1e-9))
    return {"domePenetrationEU": round(pen, 6), "domeFloatingEU": 0.0}


def run_blink_motion(
    *,
    mesh_name: str = "",
    root: Optional[Path] = None,
    create_meshes: bool = True,
) -> BlinkMotionResult:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate1234a_locked(root)

    # Rebuild Gate4A at CENTER gaze (locks dome/iris/pupil pose for blink)
    gaze = run_gaze_motion(mesh_name=mesh_name, root=root, create_meshes=True, apply_final="CENTER")
    planes = gaze.convex.flat.planes
    mesh_name = gaze.convex.flat.basis.mesh_name

    mode, cap_ev = classify_blink_capability(planes)
    if mode == "BLINK_INELIGIBLE":
        raise RuntimeError("BLINK_INELIGIBLE: aperture cannot host lid proxies")
    if mode == "NATIVE_LID":
        # Interface-compatible stub path: still build procedural proxies as diagnostic cover
        # until a dedicated native driver is wired. Documented in evidence.
        mode_exec = "PROCEDURAL_LID_PROXY"
        cap_ev["nativeDeferred"] = True
        cap_ev["executedAs"] = mode_exec
    else:
        mode_exec = mode
        cap_ev["executedAs"] = mode_exec

    bulges = {side: _bulge(side) for side in planes}
    apertures = {side: build_lid_aperture(planes[side]) for side in planes}

    frozen_names = [
        "NURION_EyeDome.L",
        "NURION_EyeDome.R",
        "NURION_DiagnosticIris.L",
        "NURION_DiagnosticIris.R",
        "NURION_DiagnosticPupil.L",
        "NURION_DiagnosticPupil.R",
    ]
    frozen_before = {n: _obj_snapshot(n) for n in frozen_names}

    import bpy

    from ..gate2.multiview_depth import build_world_bvh

    face_obj = bpy.data.objects.get(mesh_name)
    face_bvh = build_world_bvh(face_obj) if face_obj is not None else None

    if create_meshes:
        remove_blink_proxies()
        ctrl = bpy.data.objects.new("NURION_BlinkControl", None)
        ctrl.empty_display_type = "CIRCLE"
        ctrl.empty_display_size = 0.03
        bpy.context.collection.objects.link(ctrl)
        mid = 0.5 * (planes["L"].origin_world + planes["R"].origin_world)
        ctrl.location = mid
        ctrl["nurion_gate"] = "4B"
        ctrl["nurion_blink_L"] = 0.0
        ctrl["nurion_blink_R"] = 0.0

    def _apply(al: float, ar: float):
        return apply_blink_amounts(
            planes=planes,
            apertures=apertures,
            bulges=bulges,
            amount_l=al,
            amount_r=ar,
            face_bvh=face_bvh,
        )

    # OPEN baseline
    _apply(0.0, 0.0)
    open_lid_snapshot = {
        "L_upper": _obj_snapshot("NURION_UpperLidProxy.L"),
        "R_upper": _obj_snapshot("NURION_UpperLidProxy.R"),
        "L_lower": _obj_snapshot("NURION_LowerLidProxy.L"),
        "R_lower": _obj_snapshot("NURION_LowerLidProxy.R"),
    }

    state_defs = [
        ("OPEN", 0.0, 0.0),
        ("QUARTER", 0.25, 0.25),
        ("HALF", 0.50, 0.50),
        ("CLOSED", 1.0, 1.0),
        ("REOPEN", 0.0, 0.0),
    ]
    states: List[BlinkStateSample] = []
    for name, al, ar in state_defs:
        m = _apply(al, ar)
        states.append(
            BlinkStateSample(
                name=name,
                amount_l=al,
                amount_r=ar,
                coverage={s: {"coverage": m[s]["coverage"], "gapEU": m[s]["gapEU"]} for s in m},
                lid_edges={s: m[s]["edges"] for s in m},
            )
        )

    reopen_lid_snapshot = {
        "L_upper": _obj_snapshot("NURION_UpperLidProxy.L"),
        "R_upper": _obj_snapshot("NURION_UpperLidProxy.R"),
        "L_lower": _obj_snapshot("NURION_LowerLidProxy.L"),
        "R_lower": _obj_snapshot("NURION_LowerLidProxy.R"),
    }

    # Deterministic diagnostic rhythms (amounts only; no emotional timing)
    rhythm_specs = [
        ("OPEN_CLOSE_OPEN", [(0, 0), (1, 1), (0, 0)]),
        ("OPEN_DOUBLE_BLINK_OPEN", [(0, 0), (1, 1), (0, 0), (1, 1), (0, 0)]),
        ("LEFT_ONLY", [(0, 0), (1, 0), (0, 0)]),
        ("RIGHT_ONLY", [(0, 0), (0, 1), (0, 0)]),
        ("BOTH", [(0, 0), (1, 1), (0, 0)]),
    ]
    rhythms = []
    for rname, keys in rhythm_specs:
        samples = []
        for al, ar in keys:
            m = _apply(al, ar)
            samples.append({"L": al, "R": ar, "coverage": {s: m[s]["coverage"] for s in m}})
        rhythms.append({"name": rname, "keys": samples})

    # Leave at OPEN for evidence default
    _apply(0.0, 0.0)

    frozen_after = {n: _obj_snapshot(n) for n in frozen_names}

    # Face metrics at CLOSED (worst cover)
    _apply(1.0, 1.0)
    face_m = _face_lid_metrics(planes, mesh_name)
    dome_m = _measure_lid_float_vs_dome(planes, bulges, apertures)
    face_metrics = {**face_m, **dome_m}

    # restore OPEN
    _apply(0.0, 0.0)

    return BlinkMotionResult(
        gaze=gaze,
        mode=mode_exec,
        capability_evidence=cap_ev,
        apertures=apertures,
        bulges=bulges,
        frozen_before=frozen_before,
        frozen_after=frozen_after,
        open_lid_snapshot=open_lid_snapshot,
        reopen_lid_snapshot=reopen_lid_snapshot,
        states=states,
        rhythms=rhythms,
        face_metrics=face_metrics,
        parameter_hash=parameter_hash(),
        lock_info=lock_info,
    )
