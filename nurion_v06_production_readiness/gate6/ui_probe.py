"""Blender live probe for PR Gate 6 — UI snapshot, export disclosure, policy match."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from nurion_v06_production_readiness.gate3.smoke import _install_enable, sha256_file
from nurion_v06_production_readiness.gate6.parameters import GATE6_PARAMETERS, WRAPPER_SHA256_FROZEN, WRAPPER_VERSION_FROZEN


def _ok(rs) -> bool:
    return "FINISHED" in rs


def run_live_ui_export_probe(
    *,
    wrapper_zip: Path,
    fbx_path: Path,
    out_dir: Path,
    rc1_sha: str,
) -> Dict:
    import bpy

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_path = out_dir / "gate6_disclosure_export.fbx"
    disclosure_path = out_dir / "NURION_V06_EXPORT_DISCLOSURE.json"
    deny_path = out_dir / "SHOULD_NOT_PUBLISH.fbx"

    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst = _install_enable(wrapper_zip)
    if not inst.get("enabled"):
        return {"ok": False, "reason": "ADDON_ENABLE_FAILED", "install": inst}

    # Import engine from the same installed package the operators use
    from nurion_v06_unified_runtime.gate6.operators import get_engine
    from nurion_v06_unified_runtime.gate6.parameters import GATE6_PARAMETERS as SEALED_G6

    scene = bpy.context.scene

    def _cfg() -> None:
        scene.nurion_v06_label = "pr-gate6"
        scene.nurion_v06_character_path = str(fbx_path)
        scene.nurion_v06_fps = "30"
        scene.nurion_v06_force_classification = "LIMITED"
        scene.nurion_v06_available_presets = "Idle"
        scene.nurion_v06_unavailable_presets = "Formal_Bow,Gentlemans_Bow"
        scene.nurion_v06_lipsync_supported = 0
        scene.nurion_v06_preset_choice = "Idle"
        scene.nurion_v06_export_format = "FBX"

    steps: Dict = {}

    # --- Partial export DENY: export before Validate must CANCEL ---
    _cfg()
    if deny_path.exists():
        deny_path.unlink()
    scene.nurion_v06_export_path = str(deny_path)
    for name, call in (
        ("deny_select", bpy.ops.nurion_v06.select_character),
        ("deny_analyze", bpy.ops.nurion_v06.analyze_asset),
        ("deny_build", bpy.ops.nurion_v06.build_runtime),
        ("deny_apply", bpy.ops.nurion_v06.apply_preset),
    ):
        try:
            steps[name] = _ok(call())
        except Exception as exc:
            steps[name] = False
            steps[f"{name}Error"] = str(exc)
    partial_cancelled = False
    try:
        partial_cancelled = "CANCELLED" in bpy.ops.nurion_v06.export_runtime()
    except Exception:
        partial_cancelled = True
    partial_published = deny_path.is_file() and deny_path.stat().st_size > 0
    if deny_path.exists():
        deny_path.unlink()

    # --- Full workflow + disclosure export ---
    _cfg()
    if export_path.exists():
        export_path.unlink()
    scene.nurion_v06_export_path = str(export_path)
    for name, call in (
        ("select", bpy.ops.nurion_v06.select_character),
        ("analyze", bpy.ops.nurion_v06.analyze_asset),
        ("build", bpy.ops.nurion_v06.build_runtime),
        ("apply", bpy.ops.nurion_v06.apply_preset),
        ("validate", bpy.ops.nurion_v06.validate_runtime),
        ("export", bpy.ops.nurion_v06.export_runtime),
    ):
        try:
            if name == "export":
                steps[name] = _ok(call()) and export_path.is_file()
            else:
                steps[name] = _ok(call())
        except Exception as exc:
            steps[name] = False
            steps[f"{name}Error"] = str(exc)

    snap = get_engine().ui_snapshot()
    lims = list(snap.get("inheritedLimitationsFromV05") or [])
    expected = list(GATE6_PARAMETERS["inheritedLimitations"])

    disclosure = {
        "schema": "NURION_V06_EXPORT_DISCLOSURE",
        "product": "NURION Unified Character Animation Runtime",
        "production": "NO-GO",
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "classification": scene.nurion_v06_classification,
        "lipsyncMode": scene.nurion_v06_lipsync_mode,
        "abstain": scene.nurion_v06_abstain,
        "validation": scene.nurion_v06_validation_status,
        "inheritedLimitations": lims,
        "limitationAutoClear": "DENY",
        "partialExportPublish": "DENY",
        "rc1Sha256": rc1_sha,
        "wrapperVersion": WRAPPER_VERSION_FROZEN,
        "wrapperSha256": WRAPPER_SHA256_FROZEN,
        "exportPath": str(export_path).replace("\\", "/"),
        "exportSha256": sha256_file(export_path) if export_path.is_file() else None,
        "uiSnapshot": snap,
        "sealedGate6Limitations": list(SEALED_G6.get("inheritedLimitationsFromV05") or []),
    }
    disclosure_path.write_text(json.dumps(disclosure, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ui_props = {
        "production": scene.nurion_v06_production,
        "classification": scene.nurion_v06_classification,
        "lipsyncMode": scene.nurion_v06_lipsync_mode,
        "abstain": scene.nurion_v06_abstain,
        "validation": scene.nurion_v06_validation_status,
        "panelRegistered": hasattr(bpy.types, "NURION_PT_v06_unified_runtime"),
    }

    return {
        "ok": True,
        "install": inst,
        "steps": steps,
        "uiProps": ui_props,
        "uiSnapshot": snap,
        "limitationsInSnapshot": lims,
        "limitationsMatch": lims == expected,
        "partialExportDeny": partial_cancelled and not partial_published,
        "partialCancelled": partial_cancelled,
        "partialPublished": partial_published,
        "exportOk": bool(steps.get("export")),
        "disclosurePath": str(disclosure_path).replace("\\", "/"),
        "disclosure": disclosure,
        "restFallback": ui_props.get("lipsyncMode") == "REST_FALLBACK",
        "productionNoGo": ui_props.get("production") == "NO-GO",
    }
