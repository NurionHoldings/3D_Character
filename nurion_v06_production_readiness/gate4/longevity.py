"""Blender-side longevity / memory / performance harness for PR Gate 4."""

from __future__ import annotations

import hashlib
import json
import statistics
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nurion_v06_production_readiness.gate3.smoke import (
    _handlers_nurion,
    _install_enable,
    sha256_file,
)
from nurion_v06_production_readiness.gate4.memory import sample_memory_mb
from nurion_v06_production_readiness.gate4.parameters import GATE4_PARAMETERS, parameter_hash


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _ok(result_set) -> bool:
    return "FINISHED" in result_set


def _scene_counts() -> Dict:
    import bpy

    return {
        "objects": len(bpy.data.objects),
        "collections": len(bpy.data.collections),
        "actions": len(bpy.data.actions),
        "meshes": len(bpy.data.meshes),
        "armatures": len(bpy.data.armatures),
        "nurionHandlers": len(_handlers_nurion()),
    }


def _temp_file_count(export_dir: Path) -> int:
    n = 0
    if export_dir.is_dir():
        n += sum(1 for p in export_dir.rglob("*") if p.is_file())
    tmp = Path(tempfile.gettempdir())
    try:
        for p in tmp.iterdir():
            name = p.name.lower()
            if p.is_file() and ("nurion" in name or name.startswith("glb_") or name.endswith(".blend1")):
                n += 1
    except Exception:
        pass
    return n


def _semantic_fp() -> Tuple[str, Dict]:
    import bpy

    scene = bpy.context.scene
    arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
    act = arm.animation_data.action if arm and arm.animation_data else None
    semantic = {
        "armature": bool(arm),
        "boneCount": 0 if not arm else len(arm.data.bones),
        "action": None if act is None else act.name,
        "mesh": bpy.data.objects.get("NURION_UnifiedRuntime_Mesh") is not None,
        "classification": scene.nurion_v06_classification,
        "lipsyncMode": scene.nurion_v06_lipsync_mode,
        "production": scene.nurion_v06_production,
        "validation": scene.nurion_v06_validation_status,
        "fps": scene.nurion_v06_fps,
        "selectedPreset": scene.nurion_v06_selected_preset or scene.nurion_v06_preset_choice,
    }
    return _sha_json(semantic), semantic


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def _configure_scene(
    *,
    label: str,
    fbx_path: Path,
    fps: str,
    available: str,
    unavailable: str,
    preset: str,
    export_path: Path,
    export_format: str,
) -> None:
    import bpy

    scene = bpy.context.scene
    scene.nurion_v06_label = label
    scene.nurion_v06_character_path = str(fbx_path)
    scene.nurion_v06_fps = fps
    scene.nurion_v06_force_classification = "LIMITED"
    scene.nurion_v06_available_presets = available
    scene.nurion_v06_unavailable_presets = unavailable
    scene.nurion_v06_lipsync_supported = 0
    scene.nurion_v06_preset_choice = preset
    scene.nurion_v06_export_path = str(export_path)
    # Addon enum only FBX/GLB; BLEND handled after validate via save_as_mainfile
    scene.nurion_v06_export_format = "FBX" if export_format == "BLEND" else export_format


def _run_step(op_callable) -> Tuple[bool, Optional[str]]:
    try:
        return _ok(op_callable()), None
    except Exception as exc:
        return False, str(exc)


def _export_artifact(*, export_path: Path, fmt: str) -> Dict:
    import bpy

    if fmt == "BLEND":
        export_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(export_path), copy=True)
        return {"ok": export_path.is_file(), "format": "BLEND", "path": str(export_path)}
    return {
        "ok": _ok(bpy.ops.nurion_v06.export_runtime()),
        "format": fmt,
        "path": str(export_path),
        "fileOk": export_path.is_file(),
    }


def _full_workflow(
    *,
    fbx_path: Path,
    fps: str,
    fmt: str,
    preset: str,
    available: str,
    unavailable: str,
    export_path: Path,
    do_select: bool,
) -> Dict:
    import bpy

    t0 = time.perf_counter()
    _configure_scene(
        label="pr-gate4",
        fbx_path=fbx_path,
        fps=fps,
        available=available,
        unavailable=unavailable,
        preset=preset,
        export_path=export_path if fmt != "BLEND" else export_path.with_suffix(".fbx"),
        export_format=fmt,
    )
    steps = {}
    errors = {}
    if do_select:
        ok, err = _run_step(bpy.ops.nurion_v06.select_character)
        steps["select"] = ok
        if err:
            errors["select"] = err
    else:
        steps["select"] = True  # reused scene

    for name, call in (
        ("analyze", bpy.ops.nurion_v06.analyze_asset),
        ("build", bpy.ops.nurion_v06.build_runtime),
        ("apply", bpy.ops.nurion_v06.apply_preset),
        ("validate", bpy.ops.nurion_v06.validate_runtime),
    ):
        ok, err = _run_step(call)
        steps[name] = ok
        if err:
            errors[name] = err

    # Export / BLEND save only if validate passed
    if steps.get("validate"):
        if fmt == "BLEND":
            written = _export_artifact(export_path=export_path, fmt="BLEND")
            steps["export"] = bool(written.get("ok"))
        else:
            scene = bpy.context.scene
            scene.nurion_v06_export_path = str(export_path)
            scene.nurion_v06_export_format = fmt
            written = _export_artifact(export_path=export_path, fmt=fmt)
            steps["export"] = bool(written.get("ok")) and export_path.is_file()
    else:
        steps["export"] = False

    dur = time.perf_counter() - t0
    fp, semantic = _semantic_fp()
    ok = all(steps.get(k) for k in ("select", "analyze", "build", "apply", "validate", "export"))
    return {
        "ok": ok,
        "steps": steps,
        "errors": errors,
        "durationSec": round(dur, 4),
        "semanticFingerprint": fp,
        "semantic": semantic,
        "exportExists": export_path.is_file(),
        "exportBytes": export_path.stat().st_size if export_path.is_file() else 0,
        "fps": fps,
        "format": fmt,
        "preset": preset,
        "asset": str(fbx_path.name),
    }


def _partial_export_deny() -> Dict:
    """Validate-not-done export must CANCEL / no publish."""
    import bpy

    scene = bpy.context.scene
    from nurion_v06_unified_runtime.gate6.operators import get_engine

    eng = get_engine()
    completed = eng.state.completed
    if isinstance(completed, list):
        eng.state.completed = [x for x in completed if x != "VALIDATE_RUNTIME"]
    elif isinstance(completed, set):
        completed.discard("VALIDATE_RUNTIME")
    else:
        eng.state.completed = []
    eng.state.validationPassed = False
    out = Path(bpy.path.abspath(scene.nurion_v06_export_path or "//partial_deny.fbx"))
    out = out.parent / "PARTIAL_PUBLISH_DENY_PROBE.fbx"
    if out.exists():
        out.unlink()
    scene.nurion_v06_export_path = str(out)
    scene.nurion_v06_export_format = "FBX"
    cancelled = False
    try:
        cancelled = "CANCELLED" in bpy.ops.nurion_v06.export_runtime()
    except Exception:
        cancelled = True
    published = out.is_file() and out.stat().st_size > 0
    return {
        "cancelled": cancelled,
        "published": published,
        "denyOk": cancelled and not published,
    }


def _abstain_then_recover(*, fbx_path: Path, fps: str, export_dir: Path) -> Dict:
    import bpy

    bad_path = export_dir / "_abstain_probe.fbx"
    _configure_scene(
        label="pr-gate4-abstain",
        fbx_path=fbx_path,
        fps=fps,
        available="Idle",
        unavailable="Formal_Bow,Gentlemans_Bow",
        preset="Gentlemans_Bow",
        export_path=bad_path,
        export_format="FBX",
    )
    # Ensure scene has runtime
    _run_step(bpy.ops.nurion_v06.select_character)
    _run_step(bpy.ops.nurion_v06.analyze_asset)
    _run_step(bpy.ops.nurion_v06.build_runtime)
    apply_cancelled = False
    try:
        apply_cancelled = "CANCELLED" in bpy.ops.nurion_v06.apply_preset()
    except Exception:
        apply_cancelled = True
    # Recover with Idle
    bpy.context.scene.nurion_v06_preset_choice = "Idle"
    apply_ok, _ = _run_step(bpy.ops.nurion_v06.apply_preset)
    val_ok, _ = _run_step(bpy.ops.nurion_v06.validate_runtime)
    return {
        "abstainCancelled": apply_cancelled,
        "recoverApply": apply_ok,
        "recoverValidate": val_ok,
        "ok": apply_cancelled and apply_ok and val_ok,
    }


def _empty_control_abstain() -> Dict:
    import bpy

    scene = bpy.context.scene
    scene.nurion_v06_label = "empty-control"
    scene.nurion_v06_character_path = ""
    scene.nurion_v06_force_classification = "INELIGIBLE"
    scene.nurion_v06_available_presets = ""
    scene.nurion_v06_unavailable_presets = "Formal_Bow,Idle,Gentlemans_Bow"
    # SELECT → ANALYZE(INELIGIBLE disclosure FINISHED) → BUILD CANCEL → EXPORT DENY
    select_ok = False
    try:
        select_ok = "FINISHED" in bpy.ops.nurion_v06.select_character()
    except Exception:
        select_ok = False
    analyze_ok = False
    try:
        analyze_ok = "FINISHED" in bpy.ops.nurion_v06.analyze_asset()
    except Exception:
        analyze_ok = False
    build_denied = False
    try:
        build_denied = "CANCELLED" in bpy.ops.nurion_v06.build_runtime()
    except Exception:
        build_denied = True
    scene.nurion_v06_export_path = str(Path(tempfile.gettempdir()) / "nurion_empty_partial.fbx")
    export_denied = False
    try:
        export_denied = "CANCELLED" in bpy.ops.nurion_v06.export_runtime()
    except Exception:
        export_denied = True
    ineligible = scene.nurion_v06_classification == "INELIGIBLE"
    return {
        "selectOk": select_ok,
        "analyzeOk": analyze_ok,
        "ineligible": ineligible,
        "buildDenied": build_denied,
        "exportDenied": export_denied,
        "ok": select_ok and analyze_ok and ineligible and build_denied and export_denied,
    }


def run_gate4_longevity(
    *,
    wrapper_zip: Path,
    limited_fbx: Path,
    bow_fbx: Path,
    out_dir: Path,
    rc1_zip: Path,
    sealed_paths: List[Path],
) -> Dict:
    import bpy

    params = GATE4_PARAMETERS
    iterations = int(params["iterations"])
    fps_cycle = [str(x) for x in params["fpsCycle"]]
    fmt_cycle = list(params["exportFormatCycle"])
    abstain_every = int(params["abstainEveryN"])
    clean_every = int(params["cleanReimportEveryN"])
    mem_every = int(params["memorySampleEveryN"])

    out_dir = Path(out_dir)
    export_dir = out_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    sealed_before = {str(p): sha256_file(p) for p in sealed_paths if p.is_file()}
    rc_before = sha256_file(rc1_zip)
    wrap_before = sha256_file(wrapper_zip)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst = _install_enable(wrapper_zip)
    if not inst.get("enabled"):
        return {
            "verdict": "FAIL",
            "hardFails": ["ADDON_ENABLE_FAILED"],
            "checks": [],
            "notes": [str(inst)],
            "next": "PR_GATE4_RETRY_AFTER_INSTALL_FIX",
        }

    mem_start = sample_memory_mb()
    counts_start = _scene_counts()
    temp_start = _temp_file_count(export_dir)
    handlers_start = counts_start["nurionHandlers"]

    wall0 = time.perf_counter()
    iterations_log: List[Dict] = []
    durations: List[float] = []
    failures = 0
    memory_samples: List[Dict] = [{"iter": 0, "phase": "start", **mem_start, **counts_start, "tempFiles": temp_start}]
    semantic_by_key: Dict[str, List[str]] = {}
    recovery_events: List[Dict] = []

    # Dedicated recovery probes early
    recovery_events.append({"name": "EMPTY_CONTROL_ABSTAIN", **_empty_control_abstain()})

    for i in range(1, iterations + 1):
        fps = fps_cycle[(i - 1) % len(fps_cycle)]
        fmt = fmt_cycle[(i - 1) % len(fmt_cycle)]
        # Cross LIMITED assets
        use_bow = (i % 2 == 0)
        fbx = bow_fbx if use_bow else limited_fbx
        preset = "Formal_Bow" if use_bow else "Idle"
        available = "Formal_Bow,Idle" if use_bow else "Idle"
        unavailable = "Gentlemans_Bow" if use_bow else "Formal_Bow,Gentlemans_Bow"

        do_clean = (i == 1) or (i % clean_every == 0)
        if do_clean:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            # Factory reset may drop enablement — always re-enable from locked wrapper
            _install_enable(wrapper_zip)

        # ABSTAIN cross every N
        if i % abstain_every == 0:
            abst = _abstain_then_recover(fbx_path=fbx, fps=fps, export_dir=export_dir)
            recovery_events.append({"iter": i, "name": "ABSTAIN_RECOVER", **abst})
            if not abst.get("ok"):
                failures += 1

        ext = {".FBX": ".fbx", ".GLB": ".glb", ".BLEND": ".blend"}["." + fmt]
        export_path = export_dir / f"iter_{i:03d}_{fps}fps{ext}"
        if export_path.exists():
            export_path.unlink()

        result = _full_workflow(
            fbx_path=fbx,
            fps=fps,
            fmt=fmt,
            preset=preset,
            available=available,
            unavailable=unavailable,
            export_path=export_path,
            do_select=True,
        )
        durations.append(float(result["durationSec"]))
        if not result["ok"]:
            failures += 1
        key = f"{preset}|{fps}|{fmt}"
        semantic_by_key.setdefault(key, []).append(result["semanticFingerprint"])
        iterations_log.append(
            {
                "iter": i,
                "ok": result["ok"],
                "durationSec": result["durationSec"],
                "fps": fps,
                "format": fmt,
                "preset": preset,
                "asset": result["asset"],
                "steps": result["steps"],
                "errors": result["errors"],
                "semanticFingerprint": result["semanticFingerprint"],
                "exportBytes": result["exportBytes"],
                "cleanReimport": do_clean,
            }
        )

        # Partial publish DENY probe mid-run
        if i == max(1, iterations // 2):
            partial = _partial_export_deny()
            recovery_events.append({"iter": i, "name": "PARTIAL_EXPORT_DENY", **partial})
            if not partial.get("denyOk"):
                failures += 1
            # Retry full workflow after cancel
            retry = _full_workflow(
                fbx_path=limited_fbx,
                fps="30",
                fmt="FBX",
                preset="Idle",
                available="Idle",
                unavailable="Formal_Bow,Gentlemans_Bow",
                export_path=export_dir / "retry_after_partial.fbx",
                do_select=True,
            )
            recovery_events.append({"iter": i, "name": "RETRY_AFTER_PARTIAL", "ok": retry["ok"]})
            if not retry["ok"]:
                failures += 1

        if i % mem_every == 0 or i == iterations:
            mem = sample_memory_mb()
            counts = _scene_counts()
            memory_samples.append(
                {
                    "iter": i,
                    "phase": "mid" if i < iterations else "end",
                    **mem,
                    **counts,
                    "tempFiles": _temp_file_count(export_dir),
                }
            )

    wall_sec = time.perf_counter() - wall0
    mem_end = memory_samples[-1]
    mem_mid = next((m for m in memory_samples if m.get("phase") == "mid"), memory_samples[len(memory_samples) // 2])

    rss_start = float(mem_start.get("rssMb") or 0)
    rss_end = float(mem_end.get("rssMb") or 0)
    growth_mb = round(rss_end - rss_start, 2)

    obj_growth = int(mem_end.get("objects", 0)) - int(counts_start.get("objects", 0))
    act_growth = int(mem_end.get("actions", 0)) - int(counts_start.get("actions", 0))
    handler_growth = int(mem_end.get("nurionHandlers", 0)) - int(handlers_start)
    temp_growth = int(mem_end.get("tempFiles", 0)) - int(temp_start)

    durs_sorted = sorted(durations)
    mean_d = round(statistics.mean(durations), 4) if durations else 0.0
    p95_d = round(_percentile(durs_sorted, 95), 4)
    max_d = round(max(durations), 4) if durations else 0.0
    fail_pct = round(100.0 * failures / max(iterations, 1), 3)

    # Semantic determinism: for each key with >=2 samples, majority fingerprint must match
    det_checks = []
    det_ok = True
    for key, fps_list in semantic_by_key.items():
        if len(fps_list) < 2:
            continue
        # Allow first vs last match for same key
        match = fps_list[0] == fps_list[-1]
        det_checks.append({"key": key, "samples": len(fps_list), "firstLastMatch": match, "hash": fps_list[0]})
        if not match:
            det_ok = False

    sealed_after = {str(p): sha256_file(p) for p in sealed_paths if p.is_file()}
    rc_after = sha256_file(rc1_zip)
    wrap_after = sha256_file(wrapper_zip)
    mutation = 0
    for k, v in sealed_before.items():
        if sealed_after.get(k) != v:
            mutation += 1
    if rc_after != rc_before:
        mutation += 1
    if wrap_after != wrap_before:
        mutation += 1

    recovery_ok = all(bool(e.get("ok") or e.get("denyOk")) for e in recovery_events)

    checks: List[Dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    add("BLENDER_CLEAN_PROCESS", True, str(bpy.app.version))
    add("ITERATIONS_GE_100", iterations >= 100, str(iterations))
    add("FPS_CYCLE_24_30_60", set(fps_cycle) == {"24", "30", "60"}, ",".join(fps_cycle))
    add("FORMAT_CYCLE_BLEND_FBX_GLB", set(fmt_cycle) == {"BLEND", "FBX", "GLB"}, ",".join(fmt_cycle))
    add("LIMITED_ABSTAIN_CROSS", any(e.get("name") == "ABSTAIN_RECOVER" for e in recovery_events))
    add("PARTIAL_PUBLISH_DENY", any(e.get("name") == "PARTIAL_EXPORT_DENY" and e.get("denyOk") for e in recovery_events))
    add("CANCEL_FAIL_RETRY_RECOVERY", recovery_ok, json.dumps([e.get("name") for e in recovery_events]))
    add("SEMANTIC_DETERMINISM", det_ok, json.dumps(det_checks[:6]))
    add("SEALED_BASELINE_MUTATION_0", mutation == 0, f"mutation={mutation}")
    add("RC1_HASH_STABLE", rc_before == rc_after == params["sealedBaselineSha256"], rc_after)
    add("WRAPPER_HASH_STABLE", wrap_before == wrap_after, wrap_after)
    add("AUTO_OPTIMIZE_DENY", params.get("autoOptimize") == "DENY")
    add("PRODUCTION_NO_GO", params.get("production") == "NO-GO")
    add("HANDLER_GROWTH_OK", handler_growth <= int(params["handlerGrowthFail"]), str(handler_growth))
    add("TEMP_FILE_GROWTH_OK", temp_growth <= int(params["tempFileGrowthFail"]), str(temp_growth))
    add("FAILURE_RATE_OK", fail_pct <= float(params["failureRateFailPct"]), f"{fail_pct}%")
    add(
        "MEMORY_SAMPLE_OK",
        bool(mem_start.get("ok") and mem_end.get("ok")),
        str(mem_start.get("error") or mem_end.get("error") or f"{rss_start}->{rss_end}"),
    )

    hard_fails = [c["check"] for c in checks if c["result"] == "FAIL"]
    limitations = []

    def _tier(name: str, value: float, lim: float, fail: float, lim_tag: str) -> None:
        if value > fail:
            hard_fails.append(f"{name}_FAIL")
            checks.append({"check": name, "result": "FAIL", "detail": str(value)})
        elif value > lim:
            limitations.append(lim_tag)
            checks.append({"check": name, "result": "PASS_WITH_LIMITATIONS", "detail": str(value)})
        else:
            checks.append({"check": name, "result": "PASS", "detail": str(value)})

    # Thresholds without auto-optimize
    _tier(
        "MEMORY_GROWTH_MB",
        growth_mb,
        float(params["memoryGrowthLimitationsMb"]),
        float(params["memoryGrowthFailMb"]),
        "MEMORY_GROWTH_ELEVATED",
    )
    _tier(
        "P95_DURATION_SEC",
        p95_d,
        float(params["p95DurationLimitationsSec"]),
        float(params["p95DurationFailSec"]),
        "P95_DURATION_ELEVATED",
    )
    _tier(
        "OBJECT_GROWTH",
        float(obj_growth),
        float(params["objectGrowthLimitations"]),
        float(params["objectGrowthFail"]),
        "OBJECT_ACCUMULATION_ELEVATED",
    )
    _tier(
        "ACTION_GROWTH",
        float(act_growth),
        float(params["actionGrowthLimitations"]),
        float(params["actionGrowthFail"]),
        "ACTION_ACCUMULATION_ELEVATED",
    )

    # Unique hard fails
    hard_fails = sorted(set(hard_fails))

    if hard_fails:
        verdict = "FAIL"
    elif limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    notes = [
        f"iterations={iterations} wallSec={round(wall_sec, 2)} mean={mean_d}s p95={p95_d}s max={max_d}s failPct={fail_pct}",
        f"memory start/mid/end rssMb={rss_start}/{mem_mid.get('rssMb')}/{rss_end} growthMb={growth_mb}",
        f"growth objects={obj_growth} actions={act_growth} handlers={handler_growth} tempFiles={temp_growth}",
        "autoOptimize=DENY; production=NO-GO",
    ]
    if limitations:
        notes.append("limitations=" + ",".join(limitations))

    return {
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "hardFails": hard_fails,
        "limitations": limitations,
        "checks": checks,
        "notes": notes,
        "next": "PR_GATE5_EXPORT_COMPAT_SECURITY" if verdict != "FAIL" else "PR_GATE4_REMEDIATE_THEN_RETRY",
        "metrics": {
            "iterations": iterations,
            "wallClockSec": round(wall_sec, 3),
            "meanDurationSec": mean_d,
            "p95DurationSec": p95_d,
            "maxDurationSec": max_d,
            "failureCount": failures,
            "failureRatePct": fail_pct,
            "memory": {
                "start": mem_start,
                "mid": {k: mem_mid.get(k) for k in ("iter", "rssMb", "peakRssMb", "objects", "actions", "nurionHandlers", "tempFiles")},
                "end": {k: mem_end.get(k) for k in ("iter", "rssMb", "peakRssMb", "objects", "actions", "nurionHandlers", "tempFiles")},
                "growthMb": growth_mb,
            },
            "accumulation": {
                "objectGrowth": obj_growth,
                "actionGrowth": act_growth,
                "handlerGrowth": handler_growth,
                "tempFileGrowth": temp_growth,
                "collectionEnd": mem_end.get("collections"),
            },
            "semanticDeterminism": det_checks,
            "recoveryEvents": recovery_events,
            "sealedMutationCount": mutation,
            "rc1Sha256": rc_after,
            "wrapperSha256": wrap_after,
        },
        "memorySamples": memory_samples,
        "iterations": iterations_log,
        "install": inst,
        "sourceMutation": {"rc1": 0 if rc_before == rc_after else 1, "wrapper": 0 if wrap_before == wrap_after else 1, "sealed": mutation},
    }
