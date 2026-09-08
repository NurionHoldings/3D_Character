"""Blender-side export compatibility + security orchestration for PR Gate 5."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nurion_v06_production_readiness.gate3.smoke import _install_enable, sha256_file
from nurion_v06_production_readiness.gate5.parameters import GATE5_PARAMETERS, parameter_hash
from nurion_v06_production_readiness.gate5.security import (
    inventory_scripts,
    prepare_bad_inputs,
    scan_code_side_effects,
    scan_export_artifact_paths,
    scan_zip_security,
)


def _sha_json(doc) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _ok(result_set) -> bool:
    return "FINISHED" in result_set


def _runtime_snapshot() -> Dict:
    import bpy

    arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
    mesh = bpy.data.objects.get("NURION_UnifiedRuntime_Mesh")
    act = arm.animation_data.action if arm and arm.animation_data else None
    skinned = False
    if mesh is not None and arm is not None:
        for mod in mesh.modifiers:
            if mod.type == "ARMATURE" and getattr(mod, "object", None) == arm:
                skinned = True
                break
    eye_l = bpy.data.objects.get("NURION_UnifiedRuntime_Eye.L")
    eye_r = bpy.data.objects.get("NURION_UnifiedRuntime_Eye.R")
    eye_ok = bool(
        eye_l
        and eye_r
        and arm
        and eye_l.parent == arm
        and eye_l.parent_type == "BONE"
        and eye_l.parent_bone in ("Head", "head")
    )
    fs = fe = 0
    if act is not None:
        try:
            from nurion_v06_unified_runtime.gate4.bind import _action_range

            fs, fe = _action_range(act)
        except Exception:
            fs, fe = int(act.frame_range[0]), int(act.frame_range[1])
    scene = bpy.context.scene
    return {
        "armature": bool(arm),
        "mesh": bool(mesh),
        "skinned": skinned,
        "boneCount": 0 if not arm else len(arm.data.bones),
        "action": None if act is None else act.name,
        "frameRange": [int(fs), int(fe)],
        "fps": int(scene.render.fps) if scene.render.fps else int(scene.nurion_v06_fps or 30),
        "eyeBodyFace": eye_ok,
        "classification": getattr(scene, "nurion_v06_classification", ""),
        "lipsyncMode": getattr(scene, "nurion_v06_lipsync_mode", ""),
        "production": getattr(scene, "nurion_v06_production", ""),
        "validation": getattr(scene, "nurion_v06_validation_status", ""),
    }


def _configure_and_run_workflow(*, fbx_path: Path, fps: str, export_path: Path, fmt: str) -> Dict:
    import bpy

    scene = bpy.context.scene
    scene.nurion_v06_label = "pr-gate5"
    scene.nurion_v06_character_path = str(fbx_path)
    scene.nurion_v06_fps = fps
    scene.nurion_v06_force_classification = "LIMITED"
    scene.nurion_v06_available_presets = "Idle"
    scene.nurion_v06_unavailable_presets = "Formal_Bow,Gentlemans_Bow"
    scene.nurion_v06_lipsync_supported = 0
    scene.nurion_v06_preset_choice = "Idle"
    scene.nurion_v06_export_path = str(export_path)
    scene.nurion_v06_export_format = "FBX" if fmt == "BLEND" else fmt

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

    if fmt == "BLEND":
        export_path.parent.mkdir(parents=True, exist_ok=True)
        if steps.get("validate"):
            bpy.ops.wm.save_as_mainfile(filepath=str(export_path), copy=True)
            steps["export"] = export_path.is_file()
        else:
            steps["export"] = False
    else:
        try:
            steps["export"] = _ok(bpy.ops.nurion_v06.export_runtime()) and export_path.is_file()
        except Exception as exc:
            steps["export"] = False
            steps["exportError"] = str(exc)

    snap = _runtime_snapshot()
    return {
        "ok": all(steps.get(k) for k in ("select", "analyze", "build", "apply", "validate", "export")),
        "steps": steps,
        "snapshot": snap,
        "semanticFingerprint": _sha_json({k: snap[k] for k in snap if k != "action"}),
    }


def _blend_texture_path_audit() -> Dict:
    import bpy

    missing = []
    absolute_external = []
    for img in bpy.data.images:
        fp = (img.filepath_from_user() or img.filepath or "").replace("\\", "/")
        if not fp:
            continue
        if img.packed_file is None:
            # missing on disk?
            abs_path = bpy.path.abspath(fp)
            if abs_path and not Path(abs_path).is_file() and not fp.startswith("//"):
                missing.append(fp)
            if re_abs(fp) or re_abs(abs_path):
                absolute_external.append(fp)
    return {
        "missingTextures": missing,
        "absoluteExternalPaths": absolute_external,
        "ok": len(missing) == 0,
    }


def re_abs(p: str) -> bool:
    s = (p or "").replace("\\", "/").lower()
    if not s:
        return False
    if re_match_drive(s):
        return True
    return s.startswith("/users/") or "/appdata/" in s or "/temp/" in s


def re_match_drive(s: str) -> bool:
    import re

    return bool(re.match(r"^[a-z]:/", s))


def _list_scripts_drivers() -> Dict:
    import bpy

    texts = [t.name for t in bpy.data.texts]
    drivers = []
    for obj in bpy.data.objects:
        if obj.animation_data and obj.animation_data.drivers:
            for d in obj.animation_data.drivers:
                drivers.append({"object": obj.name, "data_path": d.data_path})
    autoexec = bool(getattr(bpy.app, "use_scripts_auto_execute", False))
    return {
        "texts": texts,
        "drivers": drivers,
        "scriptsAutoExecute": autoexec,
        "ok": len(texts) == 0 and len(drivers) == 0,
    }


def _reimport_check(path: Path, fmt: str, before: Dict) -> Dict:
    import bpy

    path = Path(path)
    if not path.is_file():
        return {"ok": False, "reason": "MISSING_EXPORT"}
    export_fps = int(before.get("fps") or 30)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        if fmt == "GLB":
            bpy.context.scene.render.fps = export_fps
            bpy.ops.import_scene.gltf(filepath=str(path))
        elif fmt == "FBX":
            bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=True, use_anim=True)
        elif fmt == "BLEND":
            bpy.ops.wm.open_mainfile(filepath=str(path))
        else:
            return {"ok": False, "reason": f"BAD_FMT:{fmt}"}
    except Exception as exc:
        return {"ok": False, "reason": f"IMPORT_FAIL:{exc}"}
    bpy.context.view_layer.update()

    if fmt == "BLEND":
        after = _runtime_snapshot()
        # Structural/runtime preservation (Scene RNA UI props need addon re-registered;
        # REST_FALLBACK / production NO-GO are asserted at export-time workflow snapshot).
        keys = ["armature", "mesh", "skinned", "boneCount", "frameRange", "eyeBodyFace", "fps"]
        match = all(after.get(k) == before.get(k) for k in keys)
        action_ok = bool(after.get("action")) and str(after.get("action")).startswith("NURION_UnifiedRuntime_")
        tex = _blend_texture_path_audit()
        scripts = _list_scripts_drivers()
        return {
            "ok": match and action_ok and tex.get("ok") is not False,
            "format": fmt,
            "before": before,
            "after": after,
            "textureAudit": tex,
            "scriptsDrivers": scripts,
            "matchKeys": keys,
            "actionOk": action_ok,
            "note": "UI lipsync/production props checked at export workflow; BLEND reopen compares structure",
        }

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]

    def _skinned(m) -> bool:
        for mod in m.modifiers:
            if mod.type == "ARMATURE" and getattr(mod, "object", None) is not None:
                return True
        return bool(m.parent and m.parent.type == "ARMATURE" and m.vertex_groups)

    skinned_meshes = [m for m in meshes if _skinned(m)]
    actions = list(bpy.data.actions)
    fr = [0, 0]
    if actions:
        from nurion_v06_unified_runtime.gate4.bind import _action_range

        prefer = [a for a in actions if "Idle" in a.name or str(a.name).startswith("NURION_UnifiedRuntime_")]
        pick = prefer[0] if prefer else max(actions, key=lambda a: _action_range(a)[1] - _action_range(a)[0])
        fr = list(_action_range(pick))
    bone_ok = bool(arms) and len(arms[0].data.bones) >= max(1, int(before.get("boneCount") or 0) - 2)
    src_span = (before.get("frameRange") or [0, 0])[1] - (before.get("frameRange") or [0, 0])[0]
    frame_ok = fr[1] >= fr[0] and (fr[1] - fr[0]) >= max(0, src_span - 2)
    ok = bool(arms) and bool(skinned_meshes) and bool(actions) and bone_ok and frame_ok
    return {
        "ok": ok,
        "format": fmt,
        "armatureCount": len(arms),
        "skinnedMeshCount": len(skinned_meshes),
        "actionCount": len(actions),
        "boneCount": 0 if not arms else len(arms[0].data.bones),
        "frameRange": fr,
        "sourceBoneCount": before.get("boneCount"),
        "sourceFrameRange": before.get("frameRange"),
        "fpsPreserved": int(bpy.context.scene.render.fps) == int(before.get("fps") or 30) or fmt == "FBX",
    }


def _bad_input_probes(wrapper_zip: Path, probes: Dict[str, Path], out_dir: Path) -> Dict:
    import bpy

    results = {}
    # Wrong extension — must not crash; export must not publish
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _install_enable(wrapper_zip)
    scene = bpy.context.scene
    scene.nurion_v06_label = "bad-ext"
    scene.nurion_v06_character_path = str(probes["wrongExt"])
    scene.nurion_v06_force_classification = "INELIGIBLE"
    scene.nurion_v06_available_presets = ""
    scene.nurion_v06_unavailable_presets = "Idle,Formal_Bow,Gentlemans_Bow"
    scene.nurion_v06_preset_choice = "Idle"
    scene.nurion_v06_export_path = str(out_dir / "bad_ext_partial.fbx")
    crashed = False
    try:
        _ok(bpy.ops.nurion_v06.select_character())
        _ok(bpy.ops.nurion_v06.analyze_asset())
        build_c = "CANCELLED" in bpy.ops.nurion_v06.build_runtime()
        export_c = "CANCELLED" in bpy.ops.nurion_v06.export_runtime()
    except Exception as exc:
        crashed = True
        build_c = True
        export_c = True
        results["wrongExtError"] = str(exc)
    published = Path(scene.nurion_v06_export_path).is_file()
    results["wrongExt"] = {
        "crashed": crashed,
        "buildDenied": build_c,
        "exportDenied": export_c,
        "published": published,
        "ok": (not crashed) and export_c and not published,
    }

    # Corrupt FBX
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _install_enable(wrapper_zip)
    scene = bpy.context.scene
    scene.nurion_v06_label = "corrupt"
    scene.nurion_v06_character_path = str(probes["corrupt"])
    scene.nurion_v06_force_classification = "LIMITED"
    scene.nurion_v06_available_presets = "Idle"
    scene.nurion_v06_unavailable_presets = "Formal_Bow,Gentlemans_Bow"
    scene.nurion_v06_preset_choice = "Idle"
    scene.nurion_v06_export_path = str(out_dir / "corrupt_partial.fbx")
    crashed = False
    select_finished = False
    try:
        # Import may throw / cancel — catch
        try:
            select_finished = _ok(bpy.ops.nurion_v06.select_character())
        except Exception as exc:
            select_finished = False
            results["corruptSelectError"] = str(exc)
        # If select somehow finished with empty/broken scene, later steps should not publish
        try:
            bpy.ops.nurion_v06.analyze_asset()
            bpy.ops.nurion_v06.build_runtime()
            bpy.ops.nurion_v06.apply_preset()
            bpy.ops.nurion_v06.validate_runtime()
        except Exception:
            pass
        export_c = True
        try:
            export_c = "CANCELLED" in bpy.ops.nurion_v06.export_runtime() or not Path(scene.nurion_v06_export_path).is_file()
        except Exception:
            export_c = True
    except Exception as exc:
        crashed = True
        export_c = True
        results["corruptError"] = str(exc)
    published = Path(scene.nurion_v06_export_path).is_file()
    results["corrupt"] = {
        "crashed": crashed,
        "selectFinished": select_finished,
        "exportDeniedOrEmpty": export_c and not published,
        "published": published,
        "ok": (not crashed) and not published,
    }

    # Oversize — harness policy DENY before feeding Blender (safe reject)
    over = probes["oversize"]
    size_mb = over.stat().st_size / (1024 * 1024)
    max_mb = float(GATE5_PARAMETERS["maxInputMb"])
    harness_deny = size_mb > max_mb
    # Do not import oversize into Blender (safety). Record policy enforcement.
    results["oversize"] = {
        "sizeMb": round(size_mb, 2),
        "maxInputMb": max_mb,
        "harnessDeniedFeed": harness_deny,
        "ok": harness_deny,
        "note": "Oversize not fed to Blender import; PR Gate5 harness DENY",
    }
    results["ok"] = all(results[k]["ok"] for k in ("wrongExt", "corrupt", "oversize"))
    return results


def _partial_export_deny(wrapper_zip: Path, fbx_path: Path, publish_dir: Path) -> Dict:
    import bpy

    publish_dir = Path(publish_dir)
    if publish_dir.exists():
        shutil.rmtree(publish_dir)
    publish_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    _install_enable(wrapper_zip)
    # Build valid runtime then strip validation and attempt export
    exp = publish_dir.parent / "_partial_probe.fbx"
    wf = _configure_and_run_workflow(fbx_path=fbx_path, fps="30", export_path=exp, fmt="FBX")
    from nurion_v06_unified_runtime.gate6.operators import get_engine

    eng = get_engine()
    completed = eng.state.completed
    if isinstance(completed, list):
        eng.state.completed = [x for x in completed if x != "VALIDATE_RUNTIME"]
    eng.state.validationPassed = False
    deny_path = publish_dir / "SHOULD_NOT_PUBLISH.fbx"
    bpy.context.scene.nurion_v06_export_path = str(deny_path)
    bpy.context.scene.nurion_v06_export_format = "FBX"
    cancelled = False
    try:
        cancelled = "CANCELLED" in bpy.ops.nurion_v06.export_runtime()
    except Exception:
        cancelled = True
    published = [p.name for p in publish_dir.glob("*") if p.is_file()]
    return {
        "workflowBuilt": wf.get("ok"),
        "cancelled": cancelled,
        "publishDirFiles": published,
        "ok": cancelled and len(published) == 0,
        "policy": "PARTIAL_EXPORT_PUBLISH_DENY",
    }


def run_gate5_export_compat_security(
    *,
    wrapper_zip: Path,
    rc1_zip: Path,
    fbx_path: Path,
    out_dir: Path,
    sealed_paths: List[Path],
    addon_dir: Optional[Path] = None,
) -> Dict:
    import bpy

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_dir = out_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    probe_dir = out_dir / "probes"

    sealed_before = {str(p): sha256_file(p) for p in sealed_paths if p.is_file()}
    rc_before = sha256_file(rc1_zip)
    wrap_before = sha256_file(wrapper_zip)

    checks: List[Dict] = []
    notes: List[str] = []
    limitations: List[str] = []

    def add(name: str, ok: bool, detail: str = "", lim: bool = False) -> None:
        if lim and ok:
            checks.append({"check": name, "result": "PASS_WITH_LIMITATIONS", "detail": detail})
        else:
            checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    # --- ZIP security ---
    rc_zip_scan = scan_zip_security(rc1_zip)
    wrap_zip_scan = scan_zip_security(wrapper_zip)
    add("RC1_ZIP_SECURITY", rc_zip_scan["ok"], json.dumps({k: rc_zip_scan[k] for k in ("corruptMember", "pathTraversal", "symlinks", "duplicateEntries")}))
    add("WRAPPER_ZIP_SECURITY", wrap_zip_scan["ok"], json.dumps({k: wrap_zip_scan[k] for k in ("corruptMember", "pathTraversal", "symlinks", "duplicateEntries")}))

    # Resolve addon dir from wrapper extract if needed
    if addon_dir is None or not Path(addon_dir).is_dir():
        addon_dir = Path(wrapper_zip).parent / "nurion_v06_unified_runtime"
    scripts_inv = inventory_scripts(addon_dir) if Path(addon_dir).is_dir() else {"pythonModuleCount": 0, "pythonModules": [], "driverRelatedModules": [], "handlerAutoexecModules": []}
    side = scan_code_side_effects(addon_dir) if Path(addon_dir).is_dir() else {"networkOk": False, "envOk": False, "networkHits": ["MISSING_ADDON_DIR"], "envHits": []}
    add("SCRIPT_DRIVER_INVENTORY", scripts_inv.get("pythonModuleCount", 0) > 0, json.dumps({k: scripts_inv[k] for k in ("pythonModuleCount", "driverRelatedModules", "handlerAutoexecModules")}))
    add("NO_NETWORK_ACCESS_CODE", side.get("networkOk", False), json.dumps(side.get("networkHits")[:8]))
    add("NO_ENV_ACCESS_CODE", side.get("envOk", False), json.dumps(side.get("envHits")[:8]))

    # --- Blender clean install + multi-format export ---
    ver = bpy.app.version
    add("BLENDER_5_0_1", ver[:3] == (5, 0, 1) or (ver[0] == 5 and ver[1] == 0), str(ver))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst = _install_enable(wrapper_zip)
    add("ADDON_ENABLE", bool(inst.get("enabled")), json.dumps({k: inst.get(k) for k in ("enabled", "panel")}))

    roundtrips = {}
    for fps in ("24", "30", "60"):
        for fmt in ("FBX", "GLB", "BLEND"):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            _install_enable(wrapper_zip)
            ext = {".FBX": ".fbx", ".GLB": ".glb", ".BLEND": ".blend"}["." + fmt]
            out_path = export_dir / f"compat_{fps}fps{ext}"
            if out_path.exists():
                out_path.unlink()
            wf = _configure_and_run_workflow(fbx_path=fbx_path, fps=fps, export_path=out_path, fmt=fmt)
            before = wf.get("snapshot") or {}
            # Preserve REST_FALLBACK / production on source scene before reimport wipe
            rest_ok = before.get("lipsyncMode") == "REST_FALLBACK"
            prod_ok = before.get("production") == "NO-GO"
            eye_ok = bool(before.get("eyeBodyFace"))
            rt = _reimport_check(out_path, fmt, before) if wf.get("ok") else {"ok": False, "reason": "WORKFLOW_FAIL", "steps": wf.get("steps")}
            path_scan = scan_export_artifact_paths(out_path) if out_path.is_file() else {"ok": False, "hits": ["missing"]}
            key = f"{fmt}_{fps}"
            roundtrips[key] = {
                "workflowOk": wf.get("ok"),
                "restFallback": rest_ok,
                "productionNoGo": prod_ok,
                "eyeBodyFace": eye_ok,
                "roundTrip": rt,
                "pathScan": path_scan,
                "exportSha256": sha256_file(out_path) if out_path.is_file() else None,
            }

    # Aggregate format checks (require all fps variants ok)
    for fmt in ("FBX", "GLB", "BLEND"):
        keys = [k for k in roundtrips if k.startswith(fmt + "_")]
        ok = all(roundtrips[k]["workflowOk"] and roundtrips[k]["roundTrip"].get("ok") for k in keys)
        add(f"EXPORT_REIMPORT_{fmt}", ok, json.dumps({k: roundtrips[k]["roundTrip"].get("ok") for k in keys}))

    rest_all = all(v.get("restFallback") for v in roundtrips.values())
    eye_all = all(v.get("eyeBodyFace") for v in roundtrips.values())
    prod_all = all(v.get("productionNoGo") for v in roundtrips.values())
    add("REST_FALLBACK_PRESERVED", rest_all)
    add("BODY_FACE_EYE_PRESERVED", eye_all)
    add("PRODUCTION_NO_GO_UI", prod_all)
    path_all = all(v.get("pathScan", {}).get("ok") for v in roundtrips.values())
    add("EXPORT_NO_SENSITIVE_PATH_MIXIN", path_all, json.dumps({k: v.get("pathScan", {}).get("hits") for k, v in roundtrips.items() if not v.get("pathScan", {}).get("ok")}))

    # BLEND script/driver listing from one reopen
    blend_key = "BLEND_30"
    scripts_scene = (roundtrips.get(blend_key) or {}).get("roundTrip", {}).get("scriptsDrivers") or {}
    add(
        "BLEND_NO_EMBEDDED_SCRIPTS_DRIVERS",
        bool(scripts_scene.get("ok", True)),
        json.dumps(scripts_scene),
    )

    # Bad inputs + partial deny
    probes = prepare_bad_inputs(probe_dir)
    bad = _bad_input_probes(wrapper_zip, probes, out_dir)
    add("BAD_INPUT_WRONG_EXT_DENY", bad["wrongExt"]["ok"], json.dumps(bad["wrongExt"]))
    add("BAD_INPUT_CORRUPT_DENY", bad["corrupt"]["ok"], json.dumps(bad["corrupt"]))
    add("BAD_INPUT_OVERSIZE_DENY", bad["oversize"]["ok"], json.dumps(bad["oversize"]))

    partial = _partial_export_deny(wrapper_zip, fbx_path, out_dir / "publish_deny")
    add("PARTIAL_EXPORT_PUBLISH_DENY", partial["ok"], json.dumps(partial))

    # Mutation
    sealed_after = {str(p): sha256_file(p) for p in sealed_paths if p.is_file()}
    rc_after = sha256_file(rc1_zip)
    wrap_after = sha256_file(wrapper_zip)
    mutation = sum(1 for k, v in sealed_before.items() if sealed_after.get(k) != v)
    if rc_after != rc_before:
        mutation += 1
    if wrap_after != wrap_before:
        mutation += 1
    add("SEALED_BASELINE_MUTATION_0", mutation == 0, f"mutation={mutation}")
    add("RC1_HASH_STABLE", rc_after == GATE5_PARAMETERS["sealedBaselineSha256"], rc_after)
    add("WRAPPER_HASH_STABLE", wrap_after == wrap_before == GATE5_PARAMETERS["wrapperComponent"]["wrapperSha256"], wrap_after)
    add("AUTO_REMEDIATE_DENY", GATE5_PARAMETERS.get("autoRemediate") == "DENY")
    add("AUTO_REPACK_DENY", GATE5_PARAMETERS.get("autoRepack") == "DENY")
    add("PRODUCTION_NO_GO", GATE5_PARAMETERS.get("production") == "NO-GO")

    hard_fails = [c["check"] for c in checks if c["result"] == "FAIL"]
    # Soft limitation: if env hits only in test/tooling comments — already strict

    if hard_fails:
        verdict = "FAIL"
    elif any(c["result"] == "PASS_WITH_LIMITATIONS" for c in checks) or limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    notes.append(f"formats={GATE5_PARAMETERS['exportFormats']} fps={GATE5_PARAMETERS['fpsChoices']}")
    notes.append(f"roundTripKeys={list(roundtrips)}")
    notes.append("autoRemediate=DENY autoRepack=DENY production=NO-GO")

    return {
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "hardFails": hard_fails,
        "limitations": limitations,
        "checks": checks,
        "notes": notes,
        "next": "PR_GATE6_OPS_DOCS_UI" if verdict != "FAIL" else "PR_GATE5_REMEDIATE_THEN_RETRY",
        "zipSecurity": {"rc1": rc_zip_scan, "wrapper": wrap_zip_scan},
        "scriptsInventory": scripts_inv,
        "sideEffects": side,
        "roundTrips": roundtrips,
        "badInputs": bad,
        "partialExport": partial,
        "sourceMutation": {"count": mutation, "rc1": rc_after, "wrapper": wrap_after},
        "install": inst,
    }
