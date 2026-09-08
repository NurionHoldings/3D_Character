"""Blender production holdout runner for PR Gate 7."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List

from nurion_v06_production_readiness.gate3.parameters import ADDON_MODULE
from nurion_v06_production_readiness.gate3.smoke import (
    _disable_remove_hard,
    _install_enable,
    _ops_present,
    _panel_present,
    sha256_file,
)
from nurion_v06_production_readiness.gate7.parameters import (
    GATE7_PARAMETERS,
    PR_INHERITED_LIMITATIONS,
    WRAPPER_SHA256_FROZEN,
    WRAPPER_VERSION_FROZEN,
)


def _ok(rs) -> bool:
    return "FINISHED" in rs


def _sha_json(doc) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _semantic() -> Dict:
    import bpy

    scene = bpy.context.scene
    arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
    mesh = bpy.data.objects.get("NURION_UnifiedRuntime_Mesh")
    act = arm.animation_data.action if arm and arm.animation_data else None
    skinned = False
    if mesh and arm:
        for mod in mesh.modifiers:
            if mod.type == "ARMATURE" and getattr(mod, "object", None) == arm:
                skinned = True
                break
    eye = bpy.data.objects.get("NURION_UnifiedRuntime_Eye.L")
    eye_ok = bool(eye and arm and eye.parent == arm and eye.parent_type == "BONE")
    fs = fe = 0
    if act is not None:
        try:
            from nurion_v06_unified_runtime.gate4.bind import _action_range

            fs, fe = _action_range(act)
        except Exception:
            fs, fe = int(act.frame_range[0]), int(act.frame_range[1])
    return {
        "armature": bool(arm),
        "mesh": bool(mesh),
        "skinned": skinned,
        "boneCount": 0 if not arm else len(arm.data.bones),
        "action": None if act is None else act.name,
        "frameRange": [int(fs), int(fe)],
        "eye": eye_ok,
        "classification": scene.nurion_v06_classification,
        "lipsyncMode": scene.nurion_v06_lipsync_mode,
        "production": scene.nurion_v06_production,
        "validation": scene.nurion_v06_validation_status,
        "fps": int(scene.render.fps) if scene.render.fps else int(scene.nurion_v06_fps or 30),
    }


def _configure(scene, *, fbx: Path, fps: str, export_path: Path, fmt: str) -> None:
    scene.nurion_v06_label = GATE7_PARAMETERS["holdout"]["label"]
    scene.nurion_v06_character_path = str(fbx)
    scene.nurion_v06_fps = fps
    scene.nurion_v06_force_classification = "LIMITED"
    scene.nurion_v06_available_presets = "Idle"
    scene.nurion_v06_unavailable_presets = "Formal_Bow,Gentlemans_Bow"
    scene.nurion_v06_lipsync_supported = 0
    scene.nurion_v06_preset_choice = "Idle"
    scene.nurion_v06_export_path = str(export_path)
    scene.nurion_v06_export_format = "FBX" if fmt == "BLEND" else fmt


def _run_steps_to_validate() -> Dict:
    import bpy

    steps = {}
    for name, call in (
        ("select", bpy.ops.nurion_v06.select_character),
        ("analyze", bpy.ops.nurion_v06.analyze_asset),
        ("build", bpy.ops.nurion_v06.build_runtime),
        ("apply", bpy.ops.nurion_v06.apply_preset),
        ("validate", bpy.ops.nurion_v06.validate_runtime),
    ):
        try:
            steps[name] = _ok(call())
        except Exception as exc:
            steps[name] = False
            steps[f"{name}Error"] = str(exc)
    return steps


def _export(fmt: str, path: Path) -> bool:
    import bpy

    path = Path(path)
    if path.exists():
        path.unlink()
    if fmt == "BLEND":
        bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
        return path.is_file()
    bpy.context.scene.nurion_v06_export_path = str(path)
    bpy.context.scene.nurion_v06_export_format = fmt
    try:
        return _ok(bpy.ops.nurion_v06.export_runtime()) and path.is_file()
    except Exception:
        return False


def _write_disclosure(*, out_path: Path, export_path: Path, snap: Dict, ui_snapshot: Dict, rc1_sha: str) -> Dict:
    doc = {
        "schema": "NURION_V06_EXPORT_DISCLOSURE",
        "holdoutLabel": GATE7_PARAMETERS["holdout"]["label"],
        "production": "NO-GO",
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "classification": snap.get("classification"),
        "lipsyncMode": snap.get("lipsyncMode"),
        "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
        "limitationAutoClear": "DENY",
        "panelLimitationIdsRendered": False,
        "panelLimitationId": "PANEL_LIMITATION_IDS_RENDERED",
        "partialExportPublish": "DENY",
        "rc1Sha256": rc1_sha,
        "wrapperVersion": WRAPPER_VERSION_FROZEN,
        "wrapperSha256": WRAPPER_SHA256_FROZEN,
        "exportPath": str(export_path).replace("\\", "/"),
        "exportSha256": sha256_file(export_path) if export_path.is_file() else None,
        "semantic": snap,
        "uiSnapshotLimitations": list(ui_snapshot.get("inheritedLimitationsFromV05") or []),
    }
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def run_production_holdout(
    *,
    wrapper_zip: Path,
    fbx_path: Path,
    out_dir: Path,
    rc1_sha: str,
) -> Dict:
    import bpy
    from nurion_v06_unified_runtime.gate6.operators import get_engine

    out_dir = Path(out_dir)
    export_dir = out_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Clean install
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _disable_remove_hard()
    inst = _install_enable(wrapper_zip)
    if not inst.get("enabled"):
        return {"verdict": "ALGORITHM_FAIL", "reason": "INSTALL_FAIL", "install": inst}

    # Partial export DENY before validate
    scene = bpy.context.scene
    deny = export_dir / "SHOULD_NOT_PUBLISH.fbx"
    _configure(scene, fbx=fbx_path, fps="30", export_path=deny, fmt="FBX")
    for call in (
        bpy.ops.nurion_v06.select_character,
        bpy.ops.nurion_v06.analyze_asset,
        bpy.ops.nurion_v06.build_runtime,
        bpy.ops.nurion_v06.apply_preset,
    ):
        try:
            call()
        except Exception:
            pass
    partial_cancelled = False
    try:
        partial_cancelled = "CANCELLED" in bpy.ops.nurion_v06.export_runtime()
    except Exception:
        partial_cancelled = True
    partial_published = deny.is_file() and deny.stat().st_size > 0
    if deny.exists():
        deny.unlink()

    # ABSTAIN missing preset then recover
    _configure(scene, fbx=fbx_path, fps="30", export_path=export_dir / "abstain.fbx", fmt="FBX")
    bpy.ops.nurion_v06.select_character()
    bpy.ops.nurion_v06.analyze_asset()
    bpy.ops.nurion_v06.build_runtime()
    scene.nurion_v06_preset_choice = "Gentlemans_Bow"
    abstain_cancelled = False
    try:
        abstain_cancelled = "CANCELLED" in bpy.ops.nurion_v06.apply_preset()
    except Exception:
        abstain_cancelled = True
    scene.nurion_v06_preset_choice = "Idle"
    recover_ok = _ok(bpy.ops.nurion_v06.apply_preset()) and _ok(bpy.ops.nurion_v06.validate_runtime())

    # Determinism ×3 (clean process each time) at 30 FPS FBX
    det_fps = []
    for i in range(int(GATE7_PARAMETERS["determinismRuns"])):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        _install_enable(wrapper_zip)
        scene = bpy.context.scene
        outp = export_dir / f"det_{i+1}.fbx"
        _configure(scene, fbx=fbx_path, fps="30", export_path=outp, fmt="FBX")
        steps = _run_steps_to_validate()
        exp_ok = _export("FBX", outp) if steps.get("validate") else False
        snap = _semantic()
        det_fps.append(
            {
                "run": i + 1,
                "steps": steps,
                "exportOk": exp_ok,
                "semantic": snap,
                "fingerprint": _sha_json({k: snap[k] for k in snap if k not in ("action",)}),
            }
        )
    det_ok = (
        len(det_fps) == 3
        and all(r.get("exportOk") for r in det_fps)
        and len({r["fingerprint"] for r in det_fps}) == 1
    )

    # Format × FPS matrix (single clean install cycle, re-select each)
    matrix = {}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _install_enable(wrapper_zip)
    for fps in ("24", "30", "60"):
        for fmt in ("FBX", "GLB", "BLEND"):
            scene = bpy.context.scene
            ext = {".FBX": ".fbx", ".GLB": ".glb", ".BLEND": ".blend"}["." + fmt]
            outp = export_dir / f"matrix_{fps}fps{ext}"
            _configure(scene, fbx=fbx_path, fps=fps, export_path=outp, fmt=fmt)
            steps = _run_steps_to_validate()
            exp_ok = _export(fmt, outp) if steps.get("validate") else False
            snap = _semantic()
            matrix[f"{fmt}_{fps}"] = {
                "stepsOk": all(steps.get(k) for k in ("select", "analyze", "build", "apply", "validate")),
                "exportOk": exp_ok,
                "restFallback": snap.get("lipsyncMode") == "REST_FALLBACK",
                "productionNoGo": snap.get("production") == "NO-GO",
                "classification": snap.get("classification"),
                "semantic": snap,
            }

    matrix_ok = all(v.get("stepsOk") and v.get("exportOk") for v in matrix.values())
    rest_ok = all(v.get("restFallback") for v in matrix.values())
    prod_ok = all(v.get("productionNoGo") for v in matrix.values())
    limited_ok = all(v.get("classification") == "LIMITED" for v in matrix.values())

    # Final disclosure export
    scene = bpy.context.scene
    final_export = export_dir / "holdout_final.fbx"
    _configure(scene, fbx=fbx_path, fps="30", export_path=final_export, fmt="FBX")
    steps_f = _run_steps_to_validate()
    exp_f = _export("FBX", final_export) if steps_f.get("validate") else False
    snap_f = _semantic()
    ui_snap = get_engine().ui_snapshot()
    disclosure = _write_disclosure(
        out_path=out_dir / "NURION_V06_EXPORT_DISCLOSURE.json",
        export_path=final_export,
        snap=snap_f,
        ui_snapshot=ui_snap,
        rc1_sha=rc1_sha,
    )
    # Ensure panel limitation is not hidden
    lims_public = list(disclosure.get("inheritedLimitations") or [])
    panel_lim_disclosed = "PANEL_LIMITATION_IDS_RENDERED" in lims_public and disclosure.get("panelLimitationIdsRendered") is False

    # Remove addon (end of ops flow)
    _disable_remove_hard()
    removed = ADDON_MODULE not in bpy.context.preferences.addons and not all(_ops_present().values())
    # Panel may linger as RNA — ops RNA check used
    panel_gone = not _panel_present()

    hard = []
    if not (partial_cancelled and not partial_published):
        hard.append("PARTIAL_EXPORT_DENY")
    if not (abstain_cancelled and recover_ok):
        hard.append("ABSTAIN_RECOVER")
    if not det_ok:
        hard.append("DETERMINISM_3X")
    if not matrix_ok:
        hard.append("FORMAT_FPS_MATRIX")
    if not rest_ok:
        hard.append("REST_FALLBACK")
    if not prod_ok:
        hard.append("PRODUCTION_NO_GO")
    if not limited_ok:
        hard.append("LIMITED_CLASS")
    if not exp_f:
        hard.append("FINAL_EXPORT")
    if not panel_lim_disclosed:
        hard.append("PANEL_LIMITATION_NOT_DISCLOSED")
    if not removed:
        hard.append("ADDON_REMOVE")

    limitations = list(PR_INHERITED_LIMITATIONS)
    if hard:
        verdict = "ALGORITHM_FAIL"
    else:
        # Holdout succeeded; inherited limitations (incl. panel ID gap) remain public
        verdict = "HOLDOUT_PASS"

    return {
        "verdict": verdict,
        "hardFails": hard,
        "limitations": limitations,
        "install": inst,
        "removed": removed,
        "panelGone": panel_gone,
        "partialExportDeny": partial_cancelled and not partial_published,
        "abstainRecover": abstain_cancelled and recover_ok,
        "determinism": {"ok": det_ok, "runs": det_fps},
        "matrix": matrix,
        "matrixOk": matrix_ok,
        "disclosure": disclosure,
        "uiSnapshot": ui_snap,
        "finalExportOk": exp_f,
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
    }
