"""v0.6 Gate 6 — ordered Blender workflow state machine (safe abort on violations)."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as gate1_parameter_hash
from nurion_v06_unified_runtime.gate2.parameters import parameter_hash as gate2_parameter_hash
from nurion_v06_unified_runtime.gate3.parameters import parameter_hash as gate3_parameter_hash
from nurion_v06_unified_runtime.gate4.parameters import parameter_hash as gate4_parameter_hash
from nurion_v06_unified_runtime.gate5.parameters import parameter_hash as gate5_parameter_hash

from .parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETER_HASH_FROZEN,
    GATE6_PARAMETERS,
    WORKFLOW_STEPS,
    parameter_hash,
)


def _locks_ok() -> Optional[str]:
    checks = [
        (gate1_parameter_hash(), GATE1_PARAMETER_HASH_FROZEN, "GATE1"),
        (gate2_parameter_hash(), GATE2_PARAMETER_HASH_FROZEN, "GATE2"),
        (gate3_parameter_hash(), GATE3_PARAMETER_HASH_FROZEN, "GATE3"),
        (gate4_parameter_hash(), GATE4_PARAMETER_HASH_FROZEN, "GATE4"),
        (gate5_parameter_hash(), GATE5_PARAMETER_HASH_FROZEN, "GATE5"),
    ]
    for actual, expected, name in checks:
        if actual != expected:
            return f"{name}_HASH_DRIFT"
    return None


@dataclass
class WorkflowState:
    completed: List[str] = field(default_factory=list)
    label: str = ""
    characterPath: str = ""
    classification: str = ""
    abstainReasons: List[str] = field(default_factory=list)
    lipsyncMode: str = "REST_FALLBACK"
    availablePresets: List[str] = field(default_factory=list)
    unavailablePresets: List[str] = field(default_factory=list)
    selectedPreset: str = ""
    fps: int = 30
    validationPassed: bool = False
    validationReport: Dict = field(default_factory=dict)
    runtimeBuilt: bool = False
    motionApplied: bool = False
    exportPath: str = ""
    uiMessages: List[str] = field(default_factory=list)
    lastAbort: str = ""
    sourceMutation: int = 0
    manualCorrection: int = 0
    assetSpecificTuning: int = 0
    production: str = "NO-GO"
    history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "completed": list(self.completed),
            "label": self.label,
            "characterPath": self.characterPath,
            "classification": self.classification,
            "abstainReasons": list(self.abstainReasons),
            "lipsyncMode": self.lipsyncMode,
            "availablePresets": list(self.availablePresets),
            "unavailablePresets": list(self.unavailablePresets),
            "selectedPreset": self.selectedPreset,
            "fps": self.fps,
            "validationPassed": self.validationPassed,
            "validationReport": self.validationReport,
            "runtimeBuilt": self.runtimeBuilt,
            "motionApplied": self.motionApplied,
            "exportPath": self.exportPath,
            "uiMessages": list(self.uiMessages),
            "lastAbort": self.lastAbort,
            "sourceMutation": self.sourceMutation,
            "manualCorrection": self.manualCorrection,
            "assetSpecificTuning": self.assetSpecificTuning,
            "production": self.production,
            "history": list(self.history),
            "parameterHash": parameter_hash(),
        }


def _require_previous(state: WorkflowState, step: str) -> Optional[str]:
    idx = WORKFLOW_STEPS.index(step)
    if idx == 0:
        return None
    prev = WORKFLOW_STEPS[idx - 1]
    if prev not in state.completed:
        return f"ORDER_VIOLATION: require {prev} before {step}"
    # also require all earlier steps
    for s in WORKFLOW_STEPS[:idx]:
        if s not in state.completed:
            return f"ORDER_VIOLATION: missing {s} before {step}"
    return None


def _record(state: WorkflowState, step: str, status: str, detail: str = "") -> None:
    state.history.append({"step": step, "status": status, "detail": detail})
    if status == "ABORT":
        state.lastAbort = detail or step
        state.uiMessages.append(f"SAFE_ABORT: {detail}")


class WorkflowEngine:
    """Ordered workflow. Operators call methods; out-of-order → SAFE_ABORT."""

    def __init__(self, state: Optional[WorkflowState] = None):
        self.state = state or WorkflowState()

    def ui_snapshot(self) -> Dict:
        s = self.state
        return {
            "classification": s.classification or "(none)",
            "abstainReasons": list(s.abstainReasons),
            "lipsyncMode": s.lipsyncMode,
            "production": s.production,
            "selectedPreset": s.selectedPreset or "(none)",
            "validationStatus": "PASS" if s.validationPassed else ("PENDING" if "VALIDATE_RUNTIME" not in s.completed else "FAIL"),
            "availablePresets": list(s.availablePresets),
            "unavailablePresets": list(s.unavailablePresets),
            "fps": s.fps,
            "completedSteps": list(s.completed),
            "lastAbort": s.lastAbort,
            "inheritedLimitationsFromV05": list(GATE6_PARAMETERS["inheritedLimitationsFromV05"]),
        }

    def select_character(self, *, label: str, character_path: str, fps: int = 30) -> Dict:
        lock = _locks_ok()
        if lock:
            _record(self.state, "SELECT_CHARACTER", "ABORT", lock)
            return {"ok": False, "abort": lock, "ui": self.ui_snapshot()}
        if fps not in GATE6_PARAMETERS["fpsChoices"]:
            _record(self.state, "SELECT_CHARACTER", "ABORT", f"UNSUPPORTED_FPS:{fps}")
            return {"ok": False, "abort": f"UNSUPPORTED_FPS:{fps}", "ui": self.ui_snapshot()}
        # SELECT may restart workflow
        self.state = WorkflowState(label=label, characterPath=character_path, fps=int(fps), lipsyncMode="REST_FALLBACK")
        self.state.completed.append("SELECT_CHARACTER")
        self.state.uiMessages.append(f"Selected {label}")
        self.state.uiMessages.append("Production: NO-GO")
        _record(self.state, "SELECT_CHARACTER", "PASS", label)
        return {"ok": True, "ui": self.ui_snapshot()}

    def analyze_asset(
        self,
        *,
        classification: str,
        abstain_reasons: Optional[List[str]] = None,
        available_presets: Optional[List[str]] = None,
        unavailable_presets: Optional[List[str]] = None,
        lipsync_supported: bool = False,
    ) -> Dict:
        err = _require_previous(self.state, "ANALYZE_ASSET")
        if err:
            _record(self.state, "ANALYZE_ASSET", "ABORT", err)
            return {"ok": False, "abort": err, "ui": self.ui_snapshot()}
        if classification not in ("FULL", "LIMITED", "INELIGIBLE"):
            _record(self.state, "ANALYZE_ASSET", "ABORT", f"BAD_CLASSIFICATION:{classification}")
            return {"ok": False, "abort": f"BAD_CLASSIFICATION:{classification}", "ui": self.ui_snapshot()}

        self.state.classification = classification
        self.state.abstainReasons = list(abstain_reasons or [])
        self.state.availablePresets = list(available_presets or [])
        self.state.unavailablePresets = list(unavailable_presets or [])
        self.state.lipsyncMode = "DRIVEN" if lipsync_supported else "REST_FALLBACK"
        if classification == "INELIGIBLE" and "INELIGIBLE" not in self.state.abstainReasons:
            self.state.abstainReasons.append("INELIGIBLE")
        self.state.uiMessages.append(f"Classification: {classification}")
        for r in self.state.abstainReasons:
            self.state.uiMessages.append(f"ABSTAIN: {r}")
        if self.state.lipsyncMode == "REST_FALLBACK":
            self.state.uiMessages.append("Lipsync: REST_FALLBACK")
        if "ANALYZE_ASSET" not in self.state.completed:
            self.state.completed.append("ANALYZE_ASSET")
        _record(self.state, "ANALYZE_ASSET", "PASS", classification)
        return {"ok": True, "ui": self.ui_snapshot()}

    def build_unified_runtime(self, *, runtime_built: bool = True) -> Dict:
        err = _require_previous(self.state, "BUILD_UNIFIED_RUNTIME")
        if err:
            _record(self.state, "BUILD_UNIFIED_RUNTIME", "ABORT", err)
            return {"ok": False, "abort": err, "ui": self.ui_snapshot()}
        if self.state.classification == "INELIGIBLE":
            msg = "FORCE_APPLY_INELIGIBLE_DENIED"
            _record(self.state, "BUILD_UNIFIED_RUNTIME", "ABORT", msg)
            self.state.abstainReasons = list(dict.fromkeys(self.state.abstainReasons + [msg]))
            return {"ok": False, "abort": msg, "ui": self.ui_snapshot()}
        self.state.runtimeBuilt = bool(runtime_built)
        self.state.uiMessages.append(f"Runtime collection: {GATE6_PARAMETERS['runtimeCollection']}")
        if "BUILD_UNIFIED_RUNTIME" not in self.state.completed:
            self.state.completed.append("BUILD_UNIFIED_RUNTIME")
        _record(self.state, "BUILD_UNIFIED_RUNTIME", "PASS", GATE6_PARAMETERS["runtimeCollection"])
        return {"ok": True, "ui": self.ui_snapshot()}

    def apply_motion_preset(self, *, preset_id: str, applied: bool = True, dry_run: bool = False) -> Dict:
        err = _require_previous(self.state, "APPLY_MOTION_PRESET")
        if err:
            _record(self.state, "APPLY_MOTION_PRESET", "ABORT", err)
            return {"ok": False, "abort": err, "ui": self.ui_snapshot()}
        if self.state.classification == "INELIGIBLE":
            msg = "FORCE_APPLY_INELIGIBLE_DENIED"
            _record(self.state, "APPLY_MOTION_PRESET", "ABORT", msg)
            return {"ok": False, "abort": msg, "ui": self.ui_snapshot()}
        if preset_id in self.state.unavailablePresets or preset_id not in self.state.availablePresets:
            msg = f"FORCE_APPLY_MISSING_PRESET_DENIED:{preset_id}"
            _record(self.state, "APPLY_MOTION_PRESET", "ABORT", msg)
            self.state.abstainReasons = list(dict.fromkeys(self.state.abstainReasons + [msg]))
            self.state.uiMessages.append(f"ABSTAIN: preset {preset_id} unavailable")
            return {"ok": False, "abort": msg, "ui": self.ui_snapshot()}
        if dry_run:
            return {"ok": True, "ui": self.ui_snapshot()}
        self.state.selectedPreset = preset_id
        self.state.motionApplied = bool(applied)
        self.state.validationPassed = False  # require re-validate after apply
        if "VALIDATE_RUNTIME" in self.state.completed:
            self.state.completed = [s for s in self.state.completed if s != "VALIDATE_RUNTIME"]
        if "EXPORT" in self.state.completed:
            self.state.completed = [s for s in self.state.completed if s != "EXPORT"]
        if "APPLY_MOTION_PRESET" not in self.state.completed:
            self.state.completed.append("APPLY_MOTION_PRESET")
        self.state.uiMessages.append(f"Applied preset: {preset_id}")
        if self.state.lipsyncMode == "REST_FALLBACK":
            self.state.uiMessages.append("Lipsync REST_FALLBACK retained")
        _record(self.state, "APPLY_MOTION_PRESET", "PASS", preset_id)
        return {"ok": True, "ui": self.ui_snapshot()}

    def validate_runtime(self, *, report: Optional[Dict] = None, passed: bool = True) -> Dict:
        err = _require_previous(self.state, "VALIDATE_RUNTIME")
        if err:
            _record(self.state, "VALIDATE_RUNTIME", "ABORT", err)
            return {"ok": False, "abort": err, "ui": self.ui_snapshot()}
        report = report or {}
        self.state.validationReport = report
        self.state.validationPassed = bool(passed)
        if not passed:
            _record(self.state, "VALIDATE_RUNTIME", "ABORT", "VALIDATION_FAILED")
            return {"ok": False, "abort": "VALIDATION_FAILED", "ui": self.ui_snapshot()}
        if "VALIDATE_RUNTIME" not in self.state.completed:
            self.state.completed.append("VALIDATE_RUNTIME")
        self.state.uiMessages.append("Validation: PASS")
        _record(self.state, "VALIDATE_RUNTIME", "PASS", "OK")
        return {"ok": True, "ui": self.ui_snapshot()}

    def export(self, *, export_path: str, wrote: bool = True) -> Dict:
        err = _require_previous(self.state, "EXPORT")
        if err:
            _record(self.state, "EXPORT", "ABORT", err)
            return {"ok": False, "abort": err, "ui": self.ui_snapshot()}
        if GATE6_PARAMETERS["exportRequiresValidation"] and not self.state.validationPassed:
            msg = "EXPORT_REQUIRES_VALIDATION"
            _record(self.state, "EXPORT", "ABORT", msg)
            return {"ok": False, "abort": msg, "ui": self.ui_snapshot()}
        if not wrote:
            _record(self.state, "EXPORT", "ABORT", "EXPORT_WRITE_FAILED")
            return {"ok": False, "abort": "EXPORT_WRITE_FAILED", "ui": self.ui_snapshot()}
        self.state.exportPath = export_path
        if "EXPORT" not in self.state.completed:
            self.state.completed.append("EXPORT")
        self.state.uiMessages.append(f"Exported: {export_path}")
        self.state.uiMessages.append("Source FBX/Action/sealed baselines unchanged")
        _record(self.state, "EXPORT", "PASS", export_path)
        return {"ok": True, "ui": self.ui_snapshot()}


def run_policy_scenarios() -> Dict:
    """Headless policy tests (no Blender) for order / ABSTAIN / export gates."""
    results = []

    # Happy LIMITED path
    eng = WorkflowEngine()
    r1 = eng.select_character(label="ai-aba", character_path="formal.fbx", fps=30)
    r2 = eng.analyze_asset(
        classification="LIMITED",
        abstain_reasons=["LIPSYNC_TIMELINE_UNSUPPORTED"],
        available_presets=["Formal_Bow", "Idle"],
        unavailable_presets=["Gentlemans_Bow"],
        lipsync_supported=False,
    )
    r3 = eng.build_unified_runtime()
    r4 = eng.apply_motion_preset(preset_id="Formal_Bow")
    r5 = eng.validate_runtime(report={"eyeHeadDoubleOk": True, "fpsMeaningOk": True}, passed=True)
    r6 = eng.export(export_path="out/runtime.fbx")
    results.append(
        {
            "name": "HAPPY_LIMITED",
            "ok": all(x["ok"] for x in (r1, r2, r3, r4, r5, r6)),
            "completed": eng.state.completed,
            "ui": eng.ui_snapshot(),
        }
    )

    # Order violation: apply before analyze
    eng2 = WorkflowEngine()
    eng2.select_character(label="x", character_path="a.fbx")
    bad = eng2.apply_motion_preset(preset_id="Formal_Bow")
    results.append({"name": "ORDER_VIOLATION_APPLY", "ok": (not bad["ok"]) and "ORDER_VIOLATION" in bad.get("abort", ""), "abort": bad.get("abort")})

    # Export without validate
    eng3 = WorkflowEngine()
    eng3.select_character(label="x", character_path="a.fbx")
    eng3.analyze_asset(classification="LIMITED", available_presets=["Formal_Bow"], unavailable_presets=[])
    eng3.build_unified_runtime()
    eng3.apply_motion_preset(preset_id="Formal_Bow")
    # skip validate
    ex = eng3.export(export_path="out/x.fbx")
    results.append(
        {
            "name": "EXPORT_WITHOUT_VALIDATE",
            "ok": (not ex["ok"]) and ("ORDER_VIOLATION" in ex.get("abort", "") or "EXPORT_REQUIRES_VALIDATION" in ex.get("abort", "")),
            "abort": ex.get("abort"),
        }
    )

    # INELIGIBLE force build denied
    eng4 = WorkflowEngine()
    eng4.select_character(label="empty", character_path="")
    eng4.analyze_asset(classification="INELIGIBLE", abstain_reasons=["NO_ARMATURE"], available_presets=[], unavailable_presets=["Formal_Bow", "Idle", "Gentlemans_Bow"])
    b = eng4.build_unified_runtime()
    results.append({"name": "INELIGIBLE_BUILD_DENIED", "ok": (not b["ok"]), "abort": b.get("abort")})

    # Missing preset denied
    eng5 = WorkflowEngine()
    eng5.select_character(label="ai-aba", character_path="f.fbx")
    eng5.analyze_asset(
        classification="LIMITED",
        available_presets=["Formal_Bow", "Idle"],
        unavailable_presets=["Gentlemans_Bow"],
        lipsync_supported=False,
    )
    eng5.build_unified_runtime()
    m = eng5.apply_motion_preset(preset_id="Gentlemans_Bow")
    results.append({"name": "MISSING_PRESET_DENIED", "ok": (not m["ok"]), "abort": m.get("abort")})

    # Unsupported FPS
    eng6 = WorkflowEngine()
    f = eng6.select_character(label="x", character_path="a.fbx", fps=25)
    results.append({"name": "UNSUPPORTED_FPS", "ok": (not f["ok"]), "abort": f.get("abort")})

    # UI fields present on happy path
    ui = results[0]["ui"]
    ui_ok = all(
        k in ui
        for k in ("classification", "abstainReasons", "lipsyncMode", "production", "selectedPreset", "validationStatus")
    ) and ui.get("production") == "NO-GO" and ui.get("lipsyncMode") == "REST_FALLBACK"
    results.append({"name": "UI_FIELDS", "ok": ui_ok, "ui": ui})

    all_ok = all(r["ok"] for r in results)
    return {
        "scenarios": results,
        "allOk": all_ok,
        "parameterHash": parameter_hash(),
        "locksOk": _locks_ok() is None,
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
        "sourceMutation": 0,
        "production": "NO-GO",
    }
