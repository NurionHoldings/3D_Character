"""Gate 6 — Beauty Eye visual integration over locked Gate1–5 geometry/motion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from mathutils import Vector

from ..gate5.expression_matching import apply_expression_pose, run_expression_matching
from ..gate5.expression_recipes import resolve_reaction
from .beauty_layers import create_beauty_layers_for_eye, place_catchlight, remove_beauty_layers
from .beauty_materials import apply_tier_materials
from .lock_guard import assert_gate12345_locked
from .parameters import GATE6_PARAMETERS, parameter_hash
from .presets import COLOR_PRESETS


def _v3(v: Vector) -> List[float]:
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def _snapshot(name: str) -> Optional[Dict]:
    import bpy

    obj = bpy.data.objects.get(name)
    if obj is None:
        return None
    m = obj.matrix_world.copy()
    # mesh signature for distortion check
    sig = None
    if obj.type == "MESH" and obj.data is not None:
        verts = obj.data.vertices
        sig = {
            "count": len(verts),
            "bbox": [
                round(min((v.co.x for v in verts), default=0.0), 6),
                round(max((v.co.x for v in verts), default=0.0), 6),
                round(min((v.co.y for v in verts), default=0.0), 6),
                round(max((v.co.y for v in verts), default=0.0), 6),
                round(min((v.co.z for v in verts), default=0.0), 6),
                round(max((v.co.z for v in verts), default=0.0), 6),
            ],
        }
    return {
        "location": _v3(m.translation),
        "rotation": [round(float(x), 8) for x in m.to_quaternion()],
        "mesh": sig,
    }


@dataclass
class BeautyIntegrationResult:
    expression: object
    preset: str
    tier: str
    evaluated_presets: Dict[str, Dict]
    tier_reports: Dict[str, Dict]
    geometry_before: Dict[str, Optional[Dict]]
    geometry_after: Dict[str, Optional[Dict]]
    motion_before: Dict[str, Optional[Dict]]
    motion_after: Dict[str, Optional[Dict]]
    catchlight: Dict[str, Dict]
    layers: Dict[str, Dict]
    over_emission: float
    parameter_hash: str
    lock_info: Dict
    notes: List[str] = field(default_factory=list)

    def to_profile(self) -> dict:
        return {
            "schema": "NURION_GATE6_BEAUTY_EYE_PROFILE",
            "version": GATE6_PARAMETERS["version"],
            "parameterHash": self.parameter_hash,
            "gate5ParameterHash": GATE6_PARAMETERS["requiredGate5ParameterHash"],
            "defaultPreset": GATE6_PARAMETERS["defaultPreset"],
            "appliedPreset": self.preset,
            "appliedTier": self.tier,
            "evaluatedPresets": self.evaluated_presets,
            "tierReports": self.tier_reports,
            "geometryBefore": self.geometry_before,
            "geometryAfter": self.geometry_after,
            "motionBefore": self.motion_before,
            "motionAfter": self.motion_after,
            "catchlight": self.catchlight,
            "layers": {k: {"names": list(v.keys())} for k, v in self.layers.items()},
            "overEmissionMax": round(float(self.over_emission), 4),
            "brandPresetPolicy": GATE6_PARAMETERS["brandPresetPolicy"],
            "geometryMotionParameterChange": "DENY",
            "finalSeal": "HOLD",
            "freshHoldoutRequired": True,
            "notes": list(self.notes),
            "outputs": [
                "NURION_LimbalRing.L/R",
                "NURION_CornealHighlight.L/R",
                "NURION_Catchlight.L/R",
                "NURION_SoftSclera.L/R",
                "NURION_BeautyControl",
            ],
        }


def _base_names() -> List[str]:
    names = []
    for side in ("L", "R"):
        names.extend(
            [
                f"NURION_EyeDome.{side}",
                f"NURION_EyePlane.{side}",
                f"NURION_DiagnosticIris.{side}",
                f"NURION_DiagnosticPupil.{side}",
            ]
        )
    return names


def _light_dir_local(axes, iris_obj) -> tuple:
    """Upper-left key light in iris local XY."""
    # World light preference
    world_l = (-axes.right + axes.up * 1.1 + axes.forward * 0.2).normalized()
    # Iris plane axes from world matrix
    mw = iris_obj.matrix_world
    right = Vector((mw[0][0], mw[1][0], mw[2][0])).normalized()
    up = Vector((mw[0][1], mw[1][1], mw[2][1])).normalized()
    return float(world_l.dot(right)), float(world_l.dot(up))


def apply_beauty_stack(
    *,
    planes,
    axes,
    preset: str,
    tier: str,
    create_layers: bool = True,
) -> Dict:
    import bpy

    if create_layers:
        remove_beauty_layers()
    layer_info = {}
    objects_by_side = {}
    for side, plane in planes.items():
        dome = bpy.data.objects.get(f"NURION_EyeDome.{side}")
        iris = bpy.data.objects.get(f"NURION_DiagnosticIris.{side}")
        pupil = bpy.data.objects.get(f"NURION_DiagnosticPupil.{side}")
        if create_layers:
            meta = create_beauty_layers_for_eye(
                side=side,
                iris_obj=iris,
                pupil_obj=pupil,
                dome_obj=dome,
                eye_unit=float(plane.eye_unit),
            )
        else:
            meta = {
                "limbal": bpy.data.objects.get(f"NURION_LimbalRing.{side}"),
                "cornea": bpy.data.objects.get(f"NURION_CornealHighlight.{side}"),
                "catchlight": bpy.data.objects.get(f"NURION_Catchlight.{side}"),
                "sclera": bpy.data.objects.get(f"NURION_SoftSclera.{side}"),
                "irisRadius": 0.01,
                "catchRadius": 0.002,
            }
        layer_info[side] = meta
        objects_by_side[side] = {
            "dome": dome,
            "iris": iris,
            "pupil": pupil,
            "limbal": meta["limbal"],
            "cornea": meta["cornea"],
            "catchlight": meta["catchlight"],
            "sclera": meta["sclera"],
        }

    # Catchlights
    catch_rep = {}
    dynamic = tier == "High"
    for side, plane in planes.items():
        iris = objects_by_side[side]["iris"]
        meta = layer_info[side]
        ld = _light_dir_local(axes, iris) if iris is not None else (-0.4, 0.55)
        catch_rep[side] = place_catchlight(
            catch_obj=meta["catchlight"],
            iris_radius=float(meta["irisRadius"]),
            catch_radius=float(meta["catchRadius"]),
            light_dir_local_xy=ld,
            dynamic=dynamic,
        )
        # convert escape to EU
        catch_rep[side]["escapeEU"] = round(
            float(catch_rep[side]["escape"]) / max(float(plane.eye_unit), 1e-9), 6
        )

    tier_rep = {}
    over = 0.0
    for side in planes:
        tr = apply_tier_materials(
            side=side, preset_name=preset, tier=tier, objects=objects_by_side[side]
        )
        tier_rep[side] = tr
        for v in tr.get("emission", {}).values():
            over = max(over, float(v))

    ctrl = bpy.data.objects.get("NURION_BeautyControl")
    if ctrl is None:
        ctrl = bpy.data.objects.new("NURION_BeautyControl", None)
        ctrl.empty_display_type = "CUBE"
        ctrl.empty_display_size = 0.02
        bpy.context.collection.objects.link(ctrl)
    ctrl["nurion_gate"] = "6"
    ctrl["beautyPreset"] = preset
    ctrl["beautyTier"] = tier
    ctrl["engineDefaultPreset"] = GATE6_PARAMETERS["defaultPreset"]

    # Soften lid proxy materials slightly (visual only)
    for side in ("L", "R"):
        for name in (f"NURION_UpperLidProxy.{side}", f"NURION_LowerLidProxy.{side}"):
            obj = bpy.data.objects.get(name)
            if obj is None:
                continue
            from .beauty_materials import assign_material, build_principled

            assign_material(
                obj,
                build_principled(
                    name + "_BeautySkin",
                    base_color=(0.45, 0.32, 0.28),
                    roughness=0.65,
                    emission_strength=0.0,
                ),
            )

    return {
        "layers": layer_info,
        "catchlight": catch_rep,
        "tierReports": tier_rep,
        "overEmission": over,
    }


def run_beauty_integration(
    *,
    mesh_name: str = "",
    root: Optional[Path] = None,
    preset: str = "",
    tier: str = "",
    evaluate_all_presets: bool = True,
) -> BeautyIntegrationResult:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate12345_locked(root)

    preset = (preset or GATE6_PARAMETERS["defaultPreset"]).upper()
    tier = tier or GATE6_PARAMETERS["defaultTier"]

    # Build full locked pipeline through Gate5 (geometry/motion frozen)
    expr = run_expression_matching(mesh_name=mesh_name, root=root, create_meshes=True)
    planes = expr.blink.gaze.convex.flat.planes
    axes = expr.blink.gaze.convex.flat.basis.axes

    # Neutral beauty pose
    apply_expression_pose(
        planes=planes,
        axes=axes,
        ellipses=expr.ellipses,
        apertures=expr.apertures,
        bulges=expr.bulges,
        reaction=resolve_reaction(state="NEUTRAL", intensity=0.0),
        attention_world=None,
        face_bvh=expr.face_bvh,
    )

    geom_before = {n: _snapshot(n) for n in _base_names()}

    evaluated = {}
    # Evaluate all visual candidates on Tennis path; engine default remains NATURAL
    presets_to_run = list(COLOR_PRESETS.keys()) if evaluate_all_presets else [preset]
    last_stack = None
    for p in presets_to_run:
        stack = apply_beauty_stack(
            planes=planes, axes=axes, preset=p, tier="High", create_layers=(last_stack is None)
        )
        evaluated[p] = {
            "catchlightEscapeEU": {
                s: stack["catchlight"][s]["escapeEU"] for s in stack["catchlight"]
            },
            "overEmission": stack["overEmission"],
            "tier": "High",
        }
        last_stack = stack

    # Apply engine default preset at requested tier (and verify other tiers without geom change)
    tier_reports = {}
    for t in GATE6_PARAMETERS["tiers"]:
        stack = apply_beauty_stack(
            planes=planes, axes=axes, preset=preset, tier=t, create_layers=False
        )
        tier_reports[t] = stack["tierReports"]
        if t == tier:
            last_stack = stack

    # Ensure final applied state is default preset + requested tier
    last_stack = apply_beauty_stack(
        planes=planes, axes=axes, preset=preset, tier=tier, create_layers=False
    )

    geom_after = {n: _snapshot(n) for n in _base_names()}

    # Motion drift check: apply smile + speaking and ensure dome/plane unchanged; iris may move
    # (motion itself is Gate5 — we check beauty parenting doesn't alter base mesh signatures)
    motion_before = {
        f"NURION_EyeDome.{s}": _snapshot(f"NURION_EyeDome.{s}") for s in ("L", "R")
    }
    motion_before.update(
        {f"NURION_EyePlane.{s}": _snapshot(f"NURION_EyePlane.{s}") for s in ("L", "R")}
    )
    apply_expression_pose(
        planes=planes,
        axes=axes,
        ellipses=expr.ellipses,
        apertures=expr.apertures,
        bulges=expr.bulges,
        reaction=resolve_reaction(state="FRIENDLY_SMILE", intensity=1.0),
        attention_world=None,
        face_bvh=expr.face_bvh,
    )
    # Re-place catchlights after iris moved (parented — should follow; refresh dynamic offset)
    apply_beauty_stack(planes=planes, axes=axes, preset=preset, tier=tier, create_layers=False)
    apply_expression_pose(
        planes=planes,
        axes=axes,
        ellipses=expr.ellipses,
        apertures=expr.apertures,
        bulges=expr.bulges,
        reaction=resolve_reaction(state="NEUTRAL", intensity=0.0),
        attention_world=None,
        face_bvh=expr.face_bvh,
    )
    motion_after = {
        f"NURION_EyeDome.{s}": _snapshot(f"NURION_EyeDome.{s}") for s in ("L", "R")
    }
    motion_after.update(
        {f"NURION_EyePlane.{s}": _snapshot(f"NURION_EyePlane.{s}") for s in ("L", "R")}
    )

    notes = [
        "Visual presets evaluated; engine default preset is NATURAL.",
        "ARKAON ABA brand preset selection is policy-only (AI_PREMIUM), not auto-applied here.",
        "FINAL SEAL = HOLD; fresh holdout character required (Captain is not holdout).",
    ]

    return BeautyIntegrationResult(
        expression=expr,
        preset=preset,
        tier=tier,
        evaluated_presets=evaluated,
        tier_reports=tier_reports,
        geometry_before=geom_before,
        geometry_after=geom_after,
        motion_before=motion_before,
        motion_after=motion_after,
        catchlight=last_stack["catchlight"],
        layers=last_stack["layers"],
        over_emission=float(last_stack["overEmission"]),
        parameter_hash=parameter_hash(),
        lock_info=lock_info,
        notes=notes,
    )
