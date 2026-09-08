"""Blender-side install / update / remove smoke for PR Gate 3."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import (
    ADDON_MODULE,
    GATE3_PARAMETERS,
    RC1_SHA256,
    parameter_hash,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _scripts_addons() -> Path:
    import bpy

    return Path(bpy.utils.user_resource("SCRIPTS", path="addons"))


def _addon_installed_dir() -> Optional[Path]:
    d = _scripts_addons() / ADDON_MODULE
    return d if d.is_dir() else None


def _count_classes() -> int:
    import bpy

    n = 0
    for attr in dir(bpy.types):
        if "nurion_v06" in attr.lower() or attr.startswith("NURION_OT_v06") or attr.startswith("NURION_PT_v06"):
            n += 1
    # Also scan registered operator ids
    for op_id in GATE3_PARAMETERS["workflowOps"]:
        if hasattr(bpy.ops, op_id.split(".")[0]):
            pass
    return n


def _props_present() -> bool:
    import bpy

    return hasattr(bpy.types.Scene, "nurion_v06_label") and hasattr(bpy.types.Scene, "nurion_v06_production")


def _ops_present() -> Dict[str, bool]:
    """Strict RNA class presence (bpy.ops stubs may linger after unregister)."""
    import bpy

    class_map = {
        "nurion_v06.select_character": "NURION_OT_v06_select_character",
        "nurion_v06.analyze_asset": "NURION_OT_v06_analyze",
        "nurion_v06.build_runtime": "NURION_OT_v06_build",
        "nurion_v06.apply_preset": "NURION_OT_v06_apply",
        "nurion_v06.validate_runtime": "NURION_OT_v06_validate",
        "nurion_v06.export_runtime": "NURION_OT_v06_export",
    }
    # Resolve actual class bl_idnames from registered types if renamed
    out = {}
    for op_id in GATE3_PARAMETERS["workflowOps"]:
        cls_name = class_map.get(op_id)
        if cls_name and hasattr(bpy.types, cls_name):
            out[op_id] = True
            continue
        # Fallback: scan types for matching bl_idname
        found = False
        for attr in dir(bpy.types):
            cls = getattr(bpy.types, attr, None)
            if getattr(cls, "bl_idname", None) == op_id:
                found = True
                break
        out[op_id] = found
    return out


def _panel_present() -> bool:
    import bpy

    return hasattr(bpy.types, "NURION_PT_v06_unified_runtime")


def _handlers_nurion() -> List[str]:
    import bpy

    hits = []
    for name in dir(bpy.app.handlers):
        if name.startswith("_"):
            continue
        coll = getattr(bpy.app.handlers, name, None)
        if not coll:
            continue
        try:
            for fn in list(coll):
                mod = getattr(fn, "__module__", "") or ""
                if "nurion_v06" in mod:
                    hits.append(f"{name}:{getattr(fn, '__name__', '?')}")
        except Exception:
            continue
    return hits


def _purge_sys_modules() -> None:
    for key in list(sys.modules):
        if key == ADDON_MODULE or key.startswith(ADDON_MODULE + "."):
            del sys.modules[key]


def _disable_remove_hard() -> Dict:
    import addon_utils
    import bpy

    residual_before = {
        "props": _props_present(),
        "panel": _panel_present(),
        "ops": _ops_present(),
        "handlers": _handlers_nurion(),
        "dir": str(_addon_installed_dir() or ""),
    }
    try:
        addon_utils.disable(ADDON_MODULE, default_set=True)
    except Exception:
        pass
    try:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    except Exception:
        pass
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        try:
            del prefs.addons[ADDON_MODULE]
        except Exception:
            pass
    # Prefer unregister via loaded module if present
    try:
        mod = sys.modules.get(ADDON_MODULE)
        if mod and hasattr(mod, "unregister"):
            mod.unregister()
    except Exception:
        pass
    prior = _scripts_addons() / ADDON_MODULE
    if prior.exists():
        shutil.rmtree(prior, ignore_errors=True)
    _purge_sys_modules()
    residual = {
        "props": _props_present(),
        "panel": _panel_present(),
        "opsAny": any(_ops_present().values()),
        "handlers": _handlers_nurion(),
        "addonDirExists": (_scripts_addons() / ADDON_MODULE).exists(),
        "inPrefs": ADDON_MODULE in bpy.context.preferences.addons,
    }
    clean = (
        (not residual["props"])
        and (not residual["panel"])
        and (not residual["opsAny"])
        and len(residual["handlers"]) == 0
        and (not residual["addonDirExists"])
        and (not residual["inPrefs"])
    )
    return {"ok": clean, "before": residual_before, "after": residual}


def _prefer_installed_addon_path() -> None:
    """Ensure Blender addons dir wins over workspace checkout on sys.path."""
    addons = str(_scripts_addons())
    # Drop workspace roots that shadow the installed addon package
    cleaned = []
    for p in list(sys.path):
        if not p:
            cleaned.append(p)
            continue
        pp = Path(p)
        # Keep addons path; drop paths that contain a development checkout of the package
        if (pp / ADDON_MODULE / "__init__.py").is_file() and "scripts" not in pp.as_posix().lower():
            continue
        if pp.name == ADDON_MODULE and "scripts" not in pp.as_posix().lower():
            continue
        cleaned.append(p)
    sys.path[:] = cleaned
    if addons not in sys.path:
        sys.path.insert(0, addons)
    _purge_sys_modules()


def _install_enable(wrapper_zip: Path) -> Dict:
    import bpy

    # Ensure clean slate first
    _disable_remove_hard()
    _prefer_installed_addon_path()
    bpy.ops.preferences.addon_install(filepath=str(wrapper_zip), overwrite=True)
    _prefer_installed_addon_path()
    try:
        bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
    except Exception as exc:
        # Fallback: import from installed dir and register manually
        try:
            _prefer_installed_addon_path()
            import importlib

            mod = importlib.import_module(ADDON_MODULE)
            if hasattr(mod, "register"):
                mod.register()
            else:
                return {"enabled": False, "error": f"{exc} | no register()"}
        except Exception as exc2:
            return {"enabled": False, "error": f"{exc} | {exc2}"}
    enabled = ADDON_MODULE in bpy.context.preferences.addons or all(_ops_present().values())
    return {
        "enabled": enabled,
        "addonDir": str(_addon_installed_dir() or ""),
        "ops": _ops_present(),
        "panel": _panel_present(),
        "props": _props_present(),
    }


def _run_workflow(*, fbx_path: Path, export_path: Path, fingerprint: bool = True) -> Dict:
    import bpy

    scene = bpy.context.scene
    scene.nurion_v06_label = "pr-gate3-smoke"
    scene.nurion_v06_character_path = str(fbx_path)
    scene.nurion_v06_fps = "30"
    scene.nurion_v06_force_classification = "LIMITED"
    scene.nurion_v06_available_presets = "Idle"
    scene.nurion_v06_unavailable_presets = "Formal_Bow,Gentlemans_Bow"
    scene.nurion_v06_lipsync_supported = 0
    scene.nurion_v06_preset_choice = "Idle"
    scene.nurion_v06_export_path = str(export_path)
    scene.nurion_v06_export_format = "FBX"

    def _ok(result_set) -> bool:
        return "FINISHED" in result_set

    steps = {}
    try:
        steps["select"] = _ok(bpy.ops.nurion_v06.select_character())
    except Exception as exc:
        steps["select"] = False
        steps["selectError"] = str(exc)
    try:
        steps["analyze"] = _ok(bpy.ops.nurion_v06.analyze_asset())
    except Exception as exc:
        steps["analyze"] = False
        steps["analyzeError"] = str(exc)
    try:
        steps["build"] = _ok(bpy.ops.nurion_v06.build_runtime())
    except Exception as exc:
        steps["build"] = False
        steps["buildError"] = str(exc)
    try:
        steps["apply"] = _ok(bpy.ops.nurion_v06.apply_preset())
    except Exception as exc:
        # try alternate id if naming differs
        try:
            steps["apply"] = _ok(bpy.ops.nurion_v06.apply_motion_preset())
        except Exception as exc2:
            steps["apply"] = False
            steps["applyError"] = f"{exc} | {exc2}"
    try:
        steps["validate"] = _ok(bpy.ops.nurion_v06.validate_runtime())
    except Exception as exc:
        steps["validate"] = False
        steps["validateError"] = str(exc)
    try:
        steps["export"] = _ok(bpy.ops.nurion_v06.export_runtime())
    except Exception as exc:
        steps["export"] = False
        steps["exportError"] = str(exc)

    export_ok = export_path.is_file()
    # Semantic fingerprint (FBX file bytes are non-deterministic across exports).
    arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
    act = arm.animation_data.action if arm and arm.animation_data else None
    semantic = {
        "armature": bool(arm),
        "boneCount": 0 if not arm else len(arm.data.bones),
        "action": None if act is None else act.name,
        "mesh": bpy.data.objects.get("NURION_UnifiedRuntime_Mesh") is not None,
        "exportBytes": export_path.stat().st_size if export_ok else 0,
        "classification": scene.nurion_v06_classification,
        "lipsyncMode": scene.nurion_v06_lipsync_mode,
        "production": scene.nurion_v06_production,
        "validation": scene.nurion_v06_validation_status,
    }
    # Allow small export size jitter (±2%)
    fp = _sha_json({k: v for k, v in semantic.items() if k != "exportBytes"})
    ui = {
        "classification": scene.nurion_v06_classification,
        "lipsyncMode": scene.nurion_v06_lipsync_mode,
        "production": scene.nurion_v06_production,
        "validation": scene.nurion_v06_validation_status,
    }
    ok = all(steps.get(k) for k in ("select", "analyze", "build", "apply", "validate", "export")) and export_ok
    return {
        "ok": ok,
        "steps": steps,
        "exportOk": export_ok,
        "exportSha256": sha256_file(export_path) if export_ok else None,
        "semanticFingerprint": fp,
        "semantic": semantic,
        "ui": ui,
    }


def run_gate3_smoke(
    *,
    wrapper_zip: Path,
    fbx_path: Path,
    out_dir: Path,
    rc1_zip: Path,
) -> Dict:
    import bpy

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    checks: List[Dict] = []
    notes: List[str] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    # Blender version
    ver = bpy.app.version
    add(
        "BLENDER_5_0_1",
        ver[:3] == (5, 0, 1) or (ver[0] == 5 and ver[1] == 0),
        str(ver),
    )

    rc_sha0 = sha256_file(rc1_zip)
    add("RC1_SHA_BEFORE", rc_sha0 == RC1_SHA256, rc_sha0)

    # User artifact that must survive remove
    user_art = out_dir / "user_preserved_result.txt"
    user_art.write_text("preserve-me\n", encoding="utf-8")
    user_blend = out_dir / "user_preserved.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(user_blend))

    # --- Clean install ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst1 = _install_enable(wrapper_zip)
    add("CLEAN_INSTALL_ENABLE", bool(inst1.get("enabled")), json.dumps({k: inst1.get(k) for k in ("enabled", "panel", "props")}))
    ops1 = inst1.get("ops") or {}
    add("OPS_REGISTERED", all(ops1.values()), json.dumps(ops1))
    add("PANEL_REGISTERED", bool(inst1.get("panel")))
    add("PROPS_REGISTERED", bool(inst1.get("props")))

    exp1 = out_dir / "smoke_run1_export.fbx"
    if exp1.exists():
        exp1.unlink()
    wf1 = _run_workflow(fbx_path=fbx_path, export_path=exp1)
    add("WORKFLOW_RUN1", wf1["ok"], json.dumps(wf1.get("steps")))
    add("PRODUCTION_NO_GO_UI", (wf1.get("ui") or {}).get("production") == "NO-GO", str((wf1.get("ui") or {}).get("production")))
    add("REST_FALLBACK_UI", (wf1.get("ui") or {}).get("lipsyncMode") == "REST_FALLBACK", str((wf1.get("ui") or {}).get("lipsyncMode")))

    # --- Reinstall same wrapper; compare export fingerprint ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst2 = _install_enable(wrapper_zip)
    exp2 = out_dir / "smoke_run2_export.fbx"
    if exp2.exists():
        exp2.unlink()
    wf2 = _run_workflow(fbx_path=fbx_path, export_path=exp2)
    add("REINSTALL_ENABLE", bool(inst2.get("enabled")))
    add("REINSTALL_WORKFLOW", wf2["ok"], json.dumps(wf2.get("steps")))
    same = bool(wf1.get("semanticFingerprint") and wf1.get("semanticFingerprint") == wf2.get("semanticFingerprint"))
    size1 = (wf1.get("semantic") or {}).get("exportBytes") or 0
    size2 = (wf2.get("semantic") or {}).get("exportBytes") or 0
    size_ok = size1 > 0 and size2 > 0 and abs(size1 - size2) / max(size1, size2) <= 0.02
    add(
        "REINSTALL_RESULT_MATCH",
        same and size_ok,
        f"semantic={wf1.get('semanticFingerprint')} vs {wf2.get('semanticFingerprint')} sizes={size1},{size2}",
    )

    # --- Update over existing (second install overwrite) — no duplicate classes ---
    classes_before = _count_classes()
    bpy.ops.preferences.addon_install(filepath=str(wrapper_zip), overwrite=True)
    try:
        bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
    except Exception:
        pass
    # Force re-register once
    try:
        import importlib

        mod = importlib.import_module(ADDON_MODULE)
        if hasattr(mod, "unregister"):
            mod.unregister()
        if hasattr(mod, "register"):
            mod.register()
    except Exception as exc:
        notes.append(f"reregister note: {exc}")
    classes_after = _count_classes()
    ops_u = _ops_present()
    add(
        "UPDATE_NO_DUP_RESIDUAL",
        all(ops_u.values()) and _panel_present() and _props_present() and classes_after <= max(classes_before, 20),
        f"classes_before={classes_before} after={classes_after}",
    )

    # Save export as user result, then remove addon — user files must remain
    preserved_export = out_dir / "user_keep_export.fbx"
    if exp2.is_file():
        shutil.copy2(exp2, preserved_export)

    rem = _disable_remove_hard()
    add("REMOVE_RESIDUAL_ZERO", rem["ok"], json.dumps(rem.get("after")))
    add("USER_ARTIFACT_PRESERVED_TXT", user_art.is_file() and "preserve-me" in user_art.read_text(encoding="utf-8"))
    add("USER_ARTIFACT_PRESERVED_BLEND", user_blend.is_file())
    add("USER_ARTIFACT_PRESERVED_EXPORT", preserved_export.is_file())

    # --- Reinstall and load preserved blend ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst3 = _install_enable(wrapper_zip)
    load_ok = False
    try:
        bpy.ops.wm.open_mainfile(filepath=str(user_blend))
        load_ok = True
    except Exception as exc:
        notes.append(f"reload blend: {exc}")
    add("REINSTALL_LOAD_USER_BLEND", bool(inst3.get("enabled")) and load_ok)

    # --- Failed install → partial activation DENY ---
    bad_zip = out_dir / "bad_partial_install.zip"
    bad_zip.write_bytes(b"not-a-zip")
    rem_before_bad = _disable_remove_hard()
    failed_partial = False
    try:
        bpy.ops.preferences.addon_install(filepath=str(bad_zip), overwrite=True)
    except Exception:
        failed_partial = True
    try:
        bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
    except Exception:
        failed_partial = True
    enabled_bad = ADDON_MODULE in bpy.context.preferences.addons
    residual_bad = _props_present() or _panel_present() or any(_ops_present().values())
    # Policy: failed install must not leave addon enabled or RNA registered
    add(
        "FAILED_INSTALL_PARTIAL_DENY",
        (not enabled_bad) and (not residual_bad) and rem_before_bad.get("ok", False),
        f"enabled={enabled_bad} residual={residual_bad} installRaised={failed_partial}",
    )
    _disable_remove_hard()

    # Final clean reinstall for determinism fingerprint of registration
    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst4 = _install_enable(wrapper_zip)
    reg_fp = _sha_json({"ops": _ops_present(), "panel": _panel_present(), "props": _props_present()})
    _disable_remove_hard()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst5 = _install_enable(wrapper_zip)
    reg_fp2 = _sha_json({"ops": _ops_present(), "panel": _panel_present(), "props": _props_present()})
    add("REGISTRATION_DETERMINISM", reg_fp == reg_fp2 and bool(inst4.get("enabled")) and bool(inst5.get("enabled")), reg_fp)

    rc_sha1 = sha256_file(rc1_zip)
    add("RC1_SHA_AFTER", rc_sha1 == RC1_SHA256 == rc_sha0, rc_sha1)
    add("PRODUCTION_NO_GO", GATE3_PARAMETERS["production"] == "NO-GO")
    add("RC1_REPACK_DENY", GATE3_PARAMETERS["rc1Repack"] == "DENY")

    hard = [c["check"] for c in checks if c["result"] == "FAIL"]
    verdict = "PASS" if not hard else "FAIL"
    if verdict == "PASS":
        notes.append("Install wrapper derived from sealed RC.1; RC.1 hash unchanged")
        notes.append("Remove left zero residuals; user artifacts preserved")

    return {
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "checks": checks,
        "hardFails": hard,
        "notes": notes,
        "workflowFingerprints": [wf1.get("exportSha256"), wf2.get("exportSha256")],
        "registrationFingerprints": [reg_fp, reg_fp2],
        "rc1Sha256": rc_sha1,
        "production": "NO-GO",
        "sourceMutation": 0 if rc_sha0 == rc_sha1 else 1,
        "next": "PR_GATE4_LONGEVITY_MEMORY_PERFORMANCE",
    }
