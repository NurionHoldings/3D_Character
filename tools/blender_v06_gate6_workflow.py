"""
v0.6 Gate 6 — Blender operator workflow harness.

Usage:
  blender --background --python tools/blender_v06_gate6_workflow.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "gate6"
FORMAL = (
    ROOT
    / "dist/v0.5/gate1/ai-aba.bow/_extract/Meshy_AI_Silver_Starlight_Sent_biped"
    / "Meshy_AI_Silver_Starlight_Sent_biped_Animation_Formal_Bow_withSkin.fbx"
)
GATE5_HASH = "81885dbc3c119c08c63add3a9e45caf9860a8bcbd1e9b4363cac46ac9aa9c0be"
V03 = ROOT / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
V04 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V05 = ROOT / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip"
V03_SHA = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"
V04_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V05_SHA = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _baseline_ok() -> bool:
    for path, expected in [(V03, V03_SHA), (V04, V04_SHA), (V05, V05_SHA)]:
        if not path.is_file() or _sha(path) != expected:
            return False
    return True


def _op_ok(result_set) -> bool:
    return "FINISHED" in result_set


def _op_call(op_fn):
    """Call operator; CANCELLED/WARNING should not raise."""
    try:
        return op_fn()
    except RuntimeError as exc:
        return {"CANCELLED", str(exc)}


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from nurion_v06_unified_runtime.gate5.parameters import parameter_hash as g5_hash
    from nurion_v06_unified_runtime.gate6 import operators, panel
    from nurion_v06_unified_runtime.gate6.parameters import GATE6_PARAMETERS, parameter_hash
    from nurion_v06_unified_runtime.gate6.workflow import run_policy_scenarios

    if g5_hash() != GATE5_HASH:
        raise RuntimeError("Gate5 hash drift — DENY")

    policy = run_policy_scenarios()

    cases = []

    # --- Happy path LIMITED ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    operators.register()
    panel.register()
    scene = bpy.context.scene
    scene.nurion_v06_label = "ai-aba"
    scene.nurion_v06_character_path = str(FORMAL)
    scene.nurion_v06_fps = "30"
    scene.nurion_v06_force_classification = "LIMITED"
    scene.nurion_v06_available_presets = "Formal_Bow,Idle"
    scene.nurion_v06_unavailable_presets = "Gentlemans_Bow"
    scene.nurion_v06_lipsync_supported = 0
    scene.nurion_v06_preset_choice = "Formal_Bow"
    export_path = OUT / "ai-aba" / "NURION_UnifiedRuntime_Export.fbx"
    scene.nurion_v06_export_path = str(export_path)

    src_sha_before = _sha(FORMAL)
    happy = True
    happy &= _op_ok(_op_call(bpy.ops.nurion_v06.select_character))
    happy &= _op_ok(_op_call(bpy.ops.nurion_v06.analyze_asset))
    happy &= _op_ok(_op_call(bpy.ops.nurion_v06.build_runtime))
    happy &= _op_ok(_op_call(bpy.ops.nurion_v06.apply_preset))
    happy &= _op_ok(_op_call(bpy.ops.nurion_v06.validate_runtime))
    happy &= _op_ok(_op_call(bpy.ops.nurion_v06.export_runtime))
    src_sha_after = _sha(FORMAL)
    eng = operators.get_engine()
    cases.append(
        {
            "name": "HAPPY_LIMITED_OPERATORS",
            "ok": (
                happy
                and eng.state.completed == list(GATE6_PARAMETERS["workflowSteps"])
                and src_sha_before == src_sha_after
                and export_path.is_file()
                and scene.nurion_v06_production == "NO-GO"
                and scene.nurion_v06_lipsync_mode == "REST_FALLBACK"
                and "LIPSYNC_TIMELINE_UNSUPPORTED" in (eng.state.abstainReasons or [])
                and eng.state.lipsyncMode == "REST_FALLBACK"
            ),
            "completed": list(eng.state.completed),
            "ui": eng.ui_snapshot(),
            "sourceFbxShaUnchanged": src_sha_before == src_sha_after,
            "exportExists": export_path.is_file(),
        }
    )

    # --- Order violation via operators ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    operators.register()
    panel.register()
    scene = bpy.context.scene
    scene.nurion_v06_label = "order-test"
    scene.nurion_v06_character_path = str(FORMAL)
    scene.nurion_v06_fps = "30"
    operators.reset_engine()
    bpy.ops.nurion_v06.select_character()
    # skip analyze; try apply
    scene.nurion_v06_preset_choice = "Formal_Bow"
    order_res = _op_call(bpy.ops.nurion_v06.apply_preset)
    cases.append(
        {
            "name": "OPERATOR_ORDER_VIOLATION",
            "ok": not _op_ok(order_res),
            "result": list(order_res) if hasattr(order_res, "__iter__") else [str(order_res)],
            "abort": operators.get_engine().state.lastAbort,
        }
    )

    # --- Export without validate ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    operators.register()
    panel.register()
    scene = bpy.context.scene
    scene.nurion_v06_label = "export-test"
    scene.nurion_v06_character_path = str(FORMAL)
    scene.nurion_v06_fps = "24"
    scene.nurion_v06_force_classification = "LIMITED"
    scene.nurion_v06_available_presets = "Formal_Bow"
    scene.nurion_v06_unavailable_presets = "Idle,Gentlemans_Bow"
    scene.nurion_v06_lipsync_supported = 0
    scene.nurion_v06_preset_choice = "Formal_Bow"
    scene.nurion_v06_export_path = str(OUT / "export-test" / "should_not_write.fbx")
    _op_call(bpy.ops.nurion_v06.select_character)
    _op_call(bpy.ops.nurion_v06.analyze_asset)
    _op_call(bpy.ops.nurion_v06.build_runtime)
    _op_call(bpy.ops.nurion_v06.apply_preset)
    ex = _op_call(bpy.ops.nurion_v06.export_runtime)
    cases.append(
        {
            "name": "OPERATOR_EXPORT_WITHOUT_VALIDATE",
            "ok": not _op_ok(ex),
            "abort": operators.get_engine().state.lastAbort,
            "exportExists": (OUT / "export-test" / "should_not_write.fbx").is_file(),
        }
    )
    cases[-1]["ok"] = cases[-1]["ok"] and not cases[-1]["exportExists"]

    # --- Missing preset ABSTAIN ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    operators.register()
    panel.register()
    scene = bpy.context.scene
    scene.nurion_v06_label = "missing-preset"
    scene.nurion_v06_character_path = str(FORMAL)
    scene.nurion_v06_fps = "60"
    scene.nurion_v06_force_classification = "LIMITED"
    scene.nurion_v06_available_presets = "Formal_Bow,Idle"
    scene.nurion_v06_unavailable_presets = "Gentlemans_Bow"
    scene.nurion_v06_lipsync_supported = 0
    scene.nurion_v06_preset_choice = "Gentlemans_Bow"
    _op_call(bpy.ops.nurion_v06.select_character)
    _op_call(bpy.ops.nurion_v06.analyze_asset)
    _op_call(bpy.ops.nurion_v06.build_runtime)
    miss = _op_call(bpy.ops.nurion_v06.apply_preset)
    cases.append(
        {
            "name": "OPERATOR_MISSING_PRESET_ABSTAIN",
            "ok": not _op_ok(miss),
            "abort": operators.get_engine().state.lastAbort,
        }
    )

    # --- INELIGIBLE ---
    bpy.ops.wm.read_factory_settings(use_empty=True)
    operators.register()
    panel.register()
    scene = bpy.context.scene
    scene.nurion_v06_label = "empty-control"
    scene.nurion_v06_character_path = ""
    scene.nurion_v06_fps = "30"
    scene.nurion_v06_force_classification = "INELIGIBLE"
    scene.nurion_v06_available_presets = ""
    scene.nurion_v06_unavailable_presets = "Formal_Bow,Idle,Gentlemans_Bow"
    scene.nurion_v06_lipsync_supported = 0
    operators.reset_engine()
    _op_call(bpy.ops.nurion_v06.select_character)
    _op_call(bpy.ops.nurion_v06.analyze_asset)
    inel = _op_call(bpy.ops.nurion_v06.build_runtime)
    cases.append(
        {
            "name": "OPERATOR_INELIGIBLE_ABSTAIN",
            "ok": not _op_ok(inel),
            "abort": operators.get_engine().state.lastAbort,
            "classification": operators.get_engine().state.classification,
        }
    )

    blender_ok = all(c["ok"] for c in cases)
    overall = "PASS_WITH_LIMITATIONS" if blender_ok and policy.get("allOk") and _baseline_ok() else "FAIL"
    ph = parameter_hash()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    receipt = {
        "schema": "NURION_V06_GATE6_RECEIPT",
        "gate": "6",
        "name": "BLENDER_OPERATOR_WORKFLOW",
        "V06_GATE6": overall,
        "parameterHash": ph,
        "gate5ParameterHash": GATE5_HASH,
        "gate5Locked": True,
        "production": "NO-GO",
        "sourceMutationTotal": 0,
        "manualCorrectionTotal": 0,
        "assetSpecificTuningTotal": 0,
        "inheritedLimitationsFromV05": GATE6_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "policyScenarios": policy,
        "operatorCases": cases,
        "workflowSteps": GATE6_PARAMETERS["workflowSteps"],
        "hardFails": [] if overall != "FAIL" else ["WORKFLOW_CASE_FAIL"],
        "updatedAt": now,
        "next": "GATE7_OUTPUT_VALIDATION",
    }
    status = {
        "schema": "NURION_V06_GATE6_STATUS",
        "gate": "6",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "BLENDER_OPERATOR_WORKFLOW",
        "V06_GATE6": overall,
        "parameterHash": ph,
        "gate5ParameterHash": GATE5_HASH,
        "gate5Locked": True,
        "production": "NO-GO",
        "sourceMutationTotal": 0,
        "manualCorrectionTotal": 0,
        "inheritedLimitationsFromV05": GATE6_PARAMETERS["inheritedLimitationsFromV05"],
        "updatedAt": now,
        "artifacts": {"receipt": "V06_GATE6_RECEIPT.json", "parameters": "V06_GATE6_PARAMETERS.json"},
        "next": "GATE7_OUTPUT_VALIDATION",
    }
    track = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_GATE6",
        "status": "IN_PROGRESS",
        "V06_GATE5": "PASS_WITH_LIMITATIONS",
        "gate5ParameterHash": GATE5_HASH,
        "gate5Locked": True,
        "V06_GATE6": overall,
        "gate6ParameterHash": ph,
        "production": "NO-GO",
        "sealedBaselineMutation": "DENY",
        "limitationAutoClear": "DENY",
        "inheritedLimitationsFromV05": GATE6_PARAMETERS["inheritedLimitationsFromV05"],
        "next": "GATE7_OUTPUT_VALIDATION",
        "updatedAt": now,
    }

    _write(OUT / "V06_GATE6_PARAMETERS.json", GATE6_PARAMETERS)
    _write(OUT / "V06_GATE6_RECEIPT.json", receipt)
    _write(OUT / "V06_GATE6_STATUS.json", status)
    _write(OUT / "GATE6_OPERATOR_CASES.json", {"cases": cases, "policy": policy})
    _write(ROOT / "dist" / "v0.6" / "STATUS.json", track)

    print(json.dumps({"V06_GATE6": overall, "parameterHash": ph, "cases": {c["name"]: c["ok"] for c in cases}, "policyAllOk": policy.get("allOk")}, indent=2))
    return 0 if overall in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
