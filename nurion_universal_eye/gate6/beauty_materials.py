"""Build EEVEE-friendly beauty materials (visual only)."""

from __future__ import annotations

from typing import Dict, Tuple

from .parameters import GATE6_PARAMETERS
from .presets import get_preset


def _ensure_nodes(mat):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    return nodes, links


def _rgba(rgb, a=1.0) -> Tuple[float, float, float, float]:
    return (float(rgb[0]), float(rgb[1]), float(rgb[2]), float(a))


def build_principled(
    name: str,
    *,
    base_color,
    roughness: float,
    emission_color=None,
    emission_strength: float = 0.0,
    clearcoat: float = 0.0,
    alpha: float = 1.0,
    metallic: float = 0.0,
):
    import bpy

    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    nodes, links = _ensure_nodes(mat)
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = _rgba(base_color)
    bsdf.inputs["Roughness"].default_value = float(roughness)
    bsdf.inputs["Metallic"].default_value = float(metallic)
    # Blender 4+/5 Principled socket names
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = float(clearcoat)
    elif "Clearcoat" in bsdf.inputs:
        bsdf.inputs["Clearcoat"].default_value = float(clearcoat)
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = _rgba(emission_color or base_color)
        bsdf.inputs["Emission Strength"].default_value = float(emission_strength)
    elif "Emission" in bsdf.inputs:
        bsdf.inputs["Emission"].default_value = _rgba(emission_color or base_color)
    if alpha < 0.999:
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = float(alpha)
        mat.blend_method = "BLEND"
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = "NONE"
    else:
        mat.blend_method = "OPAQUE"
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mat["nurion_gate"] = "6"
    mat["nurion_beauty"] = True
    return mat


def build_emission(name: str, color, strength: float):
    import bpy

    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    nodes, links = _ensure_nodes(mat)
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = _rgba(color)
    emit.inputs["Strength"].default_value = float(strength)
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    mat.blend_method = "OPAQUE"
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "NONE"
    mat["nurion_gate"] = "6"
    return mat


def assign_material(obj, mat) -> None:
    if obj is None or obj.data is None:
        return
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def apply_tier_materials(
    *,
    side: str,
    preset_name: str,
    tier: str,
    objects: Dict[str, object],
) -> Dict:
    """Apply materials to beauty/base objects for one eye side."""
    preset = get_preset(preset_name)
    caps = GATE6_PARAMETERS["emissionCaps"][preset_name.upper()]
    hard = float(GATE6_PARAMETERS["overEmissionHardCap"])
    tier = str(tier)
    report = {"tier": tier, "preset": preset_name.upper(), "emission": {}}

    def cap(key: str) -> float:
        return min(float(caps[key]), hard)

    dome = objects.get("dome")
    iris = objects.get("iris")
    pupil = objects.get("pupil")
    limbal = objects.get("limbal")
    cornea = objects.get("cornea")
    catch = objects.get("catchlight")
    sclera = objects.get("sclera")

    if tier == "Fallback":
        # Single static-looking eye material on dome; hide layered optics
        mat = build_principled(
            f"NURION_BeautyFallback.{side}",
            base_color=preset["irisOuter"],
            roughness=0.55,
            emission_color=preset["irisInner"],
            emission_strength=min(0.08, cap("iris")),
        )
        assign_material(dome, mat)
        for o in (iris, pupil, limbal, cornea, catch, sclera):
            if o is not None:
                o.hide_viewport = True
                o.hide_render = True
        report["emission"]["fallback"] = min(0.08, cap("iris"))
        return report

    if tier == "Low":
        mat = build_principled(
            f"NURION_BeautyEyeLow.{side}",
            base_color=preset["irisOuter"],
            roughness=preset["roughnessIris"],
            emission_color=preset["irisInner"],
            emission_strength=cap("iris") * 0.5,
            clearcoat=0.15,
        )
        assign_material(dome, mat)
        # Bake-style: keep iris/pupil simple or hidden
        if iris is not None:
            assign_material(
                iris,
                build_principled(
                    f"NURION_BeautyIrisLow.{side}",
                    base_color=preset["irisInner"],
                    roughness=0.5,
                    emission_strength=cap("iris") * 0.35,
                    emission_color=preset["irisInner"],
                ),
            )
            iris.hide_viewport = False
            iris.hide_render = False
        if pupil is not None:
            assign_material(
                pupil,
                build_principled(
                    f"NURION_BeautyPupilLow.{side}",
                    base_color=preset["pupil"],
                    roughness=0.7,
                    emission_strength=cap("pupil"),
                    emission_color=preset["pupil"],
                ),
            )
        for o in (limbal, cornea, catch, sclera):
            if o is not None:
                o.hide_viewport = True
                o.hide_render = True
        report["emission"]["iris"] = cap("iris") * 0.5
        return report

    # Medium / High — dome as soft sclera carrier
    assign_material(
        dome,
        build_principled(
            f"NURION_BeautyDome.{side}",
            base_color=preset["sclera"],
            roughness=0.55,
            emission_strength=0.0,
            clearcoat=0.05,
            alpha=0.92,
        ),
    )
    if iris is not None:
        assign_material(
            iris,
            build_principled(
                f"NURION_BeautyIris.{side}",
                base_color=preset["irisOuter"],
                roughness=preset["roughnessIris"],
                emission_color=preset["irisInner"],
                emission_strength=cap("iris"),
                clearcoat=0.2,
            ),
        )
        iris.hide_viewport = False
        iris.hide_render = False
    if pupil is not None:
        assign_material(
            pupil,
            build_principled(
                f"NURION_BeautyPupil.{side}",
                base_color=preset["pupil"],
                roughness=0.65,
                emission_color=preset["pupil"],
                emission_strength=cap("pupil"),
            ),
        )
        pupil.hide_viewport = False
        pupil.hide_render = False

    if tier == "Medium":
        if limbal is not None:
            limbal.hide_viewport = True
            limbal.hide_render = True
        if cornea is not None:
            cornea.hide_viewport = True
            cornea.hide_render = True
        if sclera is not None:
            sclera.hide_viewport = True
            sclera.hide_render = True
        if catch is not None:
            assign_material(
                catch,
                build_emission(f"NURION_BeautyCatchFixed.{side}", preset["catchlight"], cap("catchlight") * 0.7),
            )
            catch.hide_viewport = False
            catch.hide_render = False
        report["emission"] = {"iris": cap("iris"), "catchlight": cap("catchlight") * 0.7}
        return report

    # High
    if sclera is not None:
        assign_material(
            sclera,
            build_principled(
                f"NURION_BeautySclera.{side}",
                base_color=preset["sclera"],
                roughness=0.6,
                alpha=float(GATE6_PARAMETERS["layers"]["scleraOpacity"]),
            ),
        )
        sclera.hide_viewport = False
        sclera.hide_render = False
    if limbal is not None:
        assign_material(
            limbal,
            build_principled(
                f"NURION_BeautyLimbal.{side}",
                base_color=preset["limbal"],
                roughness=0.55,
                emission_strength=0.02,
                emission_color=preset["limbal"],
            ),
        )
        limbal.hide_viewport = False
        limbal.hide_render = False
    if cornea is not None:
        assign_material(
            cornea,
            build_principled(
                f"NURION_BeautyCornea.{side}",
                base_color=preset["corneaTint"],
                roughness=preset["roughnessCornea"],
                emission_color=preset["corneaTint"],
                emission_strength=cap("cornea"),
                clearcoat=preset["clearcoat"],
                alpha=0.25,
            ),
        )
        cornea.hide_viewport = False
        cornea.hide_render = False
    if catch is not None:
        assign_material(
            catch,
            build_emission(f"NURION_BeautyCatch.{side}", preset["catchlight"], cap("catchlight")),
        )
        catch.hide_viewport = False
        catch.hide_render = False
    report["emission"] = {
        "iris": cap("iris"),
        "pupil": cap("pupil"),
        "catchlight": cap("catchlight"),
        "cornea": cap("cornea"),
    }
    return report
