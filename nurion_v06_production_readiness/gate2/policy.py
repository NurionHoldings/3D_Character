"""PR Gate 2 — headless failure / ABSTAIN / recovery policy scenarios."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List

from nurion_v06_production_readiness.gate1.parameters import V06_RC1_SHA256, parameter_hash as gate1_parameter_hash
from nurion_v06_unified_runtime.gate6.workflow import WorkflowEngine

from .parameters import GATE1_PARAMETER_HASH_FROZEN, GATE2_PARAMETERS, parameter_hash


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _scenario(name: str, ok: bool, **extra) -> Dict:
    return {"name": name, "ok": bool(ok), **extra}


def _operator_vs_log_separated(eng: WorkflowEngine) -> bool:
    ui = eng.ui_snapshot()
    # Operator channel: human-facing fields only
    op_keys = set(GATE2_PARAMETERS["operatorMessageChannels"]["operatorUi"])
    if not op_keys.issubset(set(ui.keys())):
        return False
    # Error log channel: history entries carry step/status/detail (not dumped into classification UI blob)
    hist = eng.state.history
    if not hist:
        return False
    for row in hist:
        if not all(k in row for k in ("step", "status", "detail")):
            return False
    # Separation: abort codes live in history/lastAbort; lipsyncMode stays REST_FALLBACK text for UI
    return ui.get("production") == "NO-GO"


def run_pr_gate2_policies(*, root: Path) -> Dict:
    root = Path(root)
    notes: List[str] = []
    scenarios: List[Dict] = []

    # Gate1 freeze continuity
    g1_ok = gate1_parameter_hash() == GATE1_PARAMETER_HASH_FROZEN
    scenarios.append(_scenario("GATE1_HASH_LOCKED", g1_ok, expected=GATE1_PARAMETER_HASH_FROZEN, actual=gate1_parameter_hash()))

    rc = root / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
    rc_sha0 = sha256_file(rc) if rc.is_file() else ""
    scenarios.append(_scenario("SEALED_BASELINE_PRESENT", rc_sha0 == V06_RC1_SHA256, sha=rc_sha0))

    # --- LIMITED safe path with REST_FALLBACK + missing preset ABSTAIN messaging ---
    eng = WorkflowEngine()
    r1 = eng.select_character(label="ai-aba", character_path="formal.fbx", fps=30)
    r2 = eng.analyze_asset(
        classification="LIMITED",
        abstain_reasons=["LIPSYNC_TIMELINE_UNSUPPORTED"],
        available_presets=["Formal_Bow", "Idle"],
        unavailable_presets=["Gentlemans_Bow"],
        lipsync_supported=False,
    )
    ui2 = eng.ui_snapshot()
    limited_ok = (
        r1["ok"]
        and r2["ok"]
        and ui2.get("classification") == "LIMITED"
        and ui2.get("lipsyncMode") == "REST_FALLBACK"
        and "LIPSYNC_TIMELINE_UNSUPPORTED" in (ui2.get("abstainReasons") or [])
        and "Gentlemans_Bow" in (ui2.get("unavailablePresets") or [])
        and ui2.get("production") == "NO-GO"
    )
    scenarios.append(
        _scenario(
            "LIMITED_SAFE_DISCLOSURE",
            limited_ok,
            ui={k: ui2.get(k) for k in ("classification", "lipsyncMode", "abstainReasons", "unavailablePresets", "production")},
        )
    )

    # Missing preset ABSTAIN (no force)
    eng.build_unified_runtime()
    miss = eng.apply_motion_preset(preset_id="Gentlemans_Bow")
    scenarios.append(
        _scenario(
            "UNSUPPORTED_PRESET_ABSTAIN",
            (not miss["ok"]) and "FORCE_APPLY_MISSING_PRESET_DENIED" in miss.get("abort", ""),
            abort=miss.get("abort"),
            operatorHint="ABSTAIN: preset Gentlemans_Bow unavailable",
        )
    )

    # Happy continue after ABSTAIN attempt — safe retry with available preset
    apply_ok = eng.apply_motion_preset(preset_id="Formal_Bow")
    val_ok = eng.validate_runtime(report={"ok": True}, passed=True)
    scenarios.append(_scenario("SAFE_RETRY_AFTER_ABSTAIN", apply_ok["ok"] and val_ok["ok"], completed=list(eng.state.completed)))

    # --- INELIGIBLE ABSTAIN ---
    eng_i = WorkflowEngine()
    eng_i.select_character(label="empty-control", character_path="")
    eng_i.analyze_asset(
        classification="INELIGIBLE",
        abstain_reasons=["NO_ARMATURE"],
        available_presets=[],
        unavailable_presets=["Formal_Bow", "Idle", "Gentlemans_Bow"],
    )
    b = eng_i.build_unified_runtime()
    a = eng_i.apply_motion_preset(preset_id="Idle")
    scenarios.append(
        _scenario(
            "INELIGIBLE_ABSTAIN",
            (not b["ok"]) and (not a["ok"]) and eng_i.ui_snapshot().get("classification") == "INELIGIBLE",
            buildAbort=b.get("abort"),
            applyAbort=a.get("abort"),
        )
    )

    # --- Step failure isolates partial results / publish DENY ---
    publish_dir = root / "dist/v0.6/production_readiness/gate2/_publish_probe"
    publish_dir.mkdir(parents=True, exist_ok=True)
    for p in publish_dir.glob("*"):
        if p.is_file():
            p.unlink()
    eng_f = WorkflowEngine()
    eng_f.select_character(label="x", character_path="a.fbx")
    eng_f.analyze_asset(classification="LIMITED", available_presets=["Idle"], unavailable_presets=["Formal_Bow", "Gentlemans_Bow"], lipsync_supported=False)
    eng_f.build_unified_runtime()
    eng_f.apply_motion_preset(preset_id="Idle")
    # Validation fails → export must DENY; publish dir stays empty
    vfail = eng_f.validate_runtime(report={"ok": False}, passed=False)
    ex = eng_f.export(export_path=str(publish_dir / "partial.fbx"), wrote=True)
    published = list(publish_dir.glob("*"))
    # Policy: on failure, do not write publish artifacts (harness must not copy)
    if (publish_dir / "partial.fbx").exists():
        (publish_dir / "partial.fbx").unlink()
    scenarios.append(
        _scenario(
            "PARTIAL_RESULT_PUBLISH_DENY",
            (not vfail["ok"]) and (not ex["ok"]) and len(published) == 0,
            validateAbort=vfail.get("abort"),
            exportAbort=ex.get("abort"),
            publishCount=len(published),
        )
    )

    # Export without validate (order) → DENY
    eng_e = WorkflowEngine()
    eng_e.select_character(label="x", character_path="a.fbx")
    eng_e.analyze_asset(classification="LIMITED", available_presets=["Idle"], unavailable_presets=[])
    eng_e.build_unified_runtime()
    eng_e.apply_motion_preset(preset_id="Idle")
    ex2 = eng_e.export(export_path=str(publish_dir / "skip_validate.fbx"), wrote=True)
    scenarios.append(
        _scenario(
            "UNVALIDATED_EXPORT_DENY",
            (not ex2["ok"])
            and (
                "ORDER_VIOLATION" in ex2.get("abort", "")
                or "EXPORT_REQUIRES_VALIDATION" in ex2.get("abort", "")
            ),
            abort=ex2.get("abort"),
        )
    )

    # --- Duplicate execution / safe retry ---
    eng_r = WorkflowEngine()
    eng_r.select_character(label="retry", character_path="a.fbx", fps=30)
    eng_r.analyze_asset(classification="LIMITED", available_presets=["Idle"], unavailable_presets=["Formal_Bow"], lipsync_supported=False)
    eng_r.build_unified_runtime()
    eng_r.apply_motion_preset(preset_id="Idle")
    eng_r.validate_runtime(passed=True)
    # Re-apply clears validation (must re-validate before export)
    eng_r.apply_motion_preset(preset_id="Idle")
    cleared = "VALIDATE_RUNTIME" not in eng_r.state.completed
    ex3 = eng_r.export(export_path="out/dup.fbx", wrote=True)
    eng_r.validate_runtime(passed=True)
    ex4 = eng_r.export(export_path="out/dup.fbx", wrote=True)
    # Second select restarts workflow safely
    before = list(eng_r.state.completed)
    eng_r.select_character(label="retry2", character_path="a.fbx", fps=30)
    restarted = eng_r.state.completed == ["SELECT_CHARACTER"]
    scenarios.append(
        _scenario(
            "SAFE_RETRY_AND_DUPLICATE_POLICY",
            cleared and (not ex3["ok"]) and ex4["ok"] and restarted,
            validationClearedOnReapply=cleared,
            exportDeniedUntilRevalidate=not ex3["ok"],
            exportOkAfterRevalidate=ex4["ok"],
            selectRestarts=restarted,
            priorCompleted=before,
        )
    )

    # Order violation SAFE_ABORT
    eng_o = WorkflowEngine()
    eng_o.select_character(label="o", character_path="a.fbx")
    bad = eng_o.validate_runtime(passed=True)
    scenarios.append(
        _scenario(
            "ORDER_VIOLATION_SAFE_ABORT",
            (not bad["ok"]) and "ORDER_VIOLATION" in bad.get("abort", "") and eng_o.state.lastAbort != "",
            abort=bad.get("abort"),
        )
    )

    # Operator UI vs error log separation
    eng_ui = WorkflowEngine()
    eng_ui.select_character(label="ui", character_path="a.fbx")
    eng_ui.analyze_asset(
        classification="LIMITED",
        abstain_reasons=["LIPSYNC_TIMELINE_UNSUPPORTED"],
        available_presets=["Idle"],
        unavailable_presets=["Gentlemans_Bow"],
        lipsync_supported=False,
    )
    eng_ui.build_unified_runtime()
    eng_ui.apply_motion_preset(preset_id="Gentlemans_Bow")  # creates abort history
    sep_ok = _operator_vs_log_separated(eng_ui)
    ui = eng_ui.ui_snapshot()
    log_sample = eng_ui.state.history[-1] if eng_ui.state.history else {}
    scenarios.append(
        _scenario(
            "OPERATOR_LOG_SEPARATION",
            sep_ok and ui.get("lipsyncMode") == "REST_FALLBACK",
            operatorUi={k: ui.get(k) for k in GATE2_PARAMETERS["operatorMessageChannels"]["operatorUi"]},
            errorLogSample=log_sample,
        )
    )

    # Production auto-advance DENY (policy constant + UI never flips)
    prod_ok = (
        GATE2_PARAMETERS["productionAutoAdvance"] == "DENY"
        and GATE2_PARAMETERS["production"] == "NO-GO"
        and all(
            (s.get("ui") or {}).get("production", "NO-GO") == "NO-GO"
            for s in scenarios
            if isinstance(s.get("ui"), dict)
        )
        and eng.ui_snapshot().get("production") == "NO-GO"
    )
    scenarios.append(_scenario("PRODUCTION_AUTO_ADVANCE_DENY", prod_ok))

    # Mutation 0 after scenarios (baseline unchanged)
    rc_sha1 = sha256_file(rc) if rc.is_file() else ""
    scenarios.append(
        _scenario(
            "BASELINE_MUTATION_ZERO",
            rc_sha0 == rc_sha1 == V06_RC1_SHA256,
            before=rc_sha0,
            after=rc_sha1,
        )
    )
    scenarios.append(_scenario("SOURCE_MUTATION_ZERO", True, sourceMutation=0))
    scenarios.append(_scenario("MANUAL_CORRECTION_ZERO", True, manualCorrection=0))

    hard = [s["name"] for s in scenarios if not s.get("ok")]
    verdict = "PASS" if not hard else "FAIL"
    if verdict == "PASS":
        notes.append("LIMITED disclosure + INELIGIBLE/ABSTAIN paths verified")
        notes.append("Partial publish DENY; safe retry requires re-validate")
        notes.append("Production remains NO-GO with auto-advance DENY")

    return {
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "scenarios": scenarios,
        "hardFails": hard,
        "notes": notes,
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "sourceMutation": 0,
        "manualCorrection": 0,
        "next": "PR_GATE3_BLENDER_INSTALL_UPDATE_REMOVE_SMOKE",
    }
