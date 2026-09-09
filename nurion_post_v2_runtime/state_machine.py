"""Fail-closed Post-V2 state machine, separate from the sealed v0.6 workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import ContractViolation, validate_export_target, validate_fbx_input, validate_timing

STEPS = ("PRECHECK", "IMPORT_TRANSACTION", "SELECT_COMMIT", "ANALYZE", "BUILD", "APPLY", "VALIDATE", "EXPORT")


@dataclass
class RuntimeState:
    completed: list[str] = field(default_factory=list)
    precheck: dict = field(default_factory=dict)
    import_provenance: dict = field(default_factory=dict)
    classification: str = ""
    runtime_built: bool = False
    motion_applied: bool = False
    validation_passed: bool = False
    export_path: str = ""
    planned_export_path: str = ""
    wrote: bool = False
    last_abort: str = ""
    history: list[dict] = field(default_factory=list)


class PostV2RuntimeEngine:
    def __init__(self, state: RuntimeState | None = None):
        self.state = state or RuntimeState()

    def _record(self, step: str, status: str, detail: str = "") -> None:
        self.state.history.append({"step": step, "status": status, "detail": detail})
        if status == "ABORT":
            self.state.last_abort = detail

    def _require(self, step: str) -> str | None:
        index = STEPS.index(step)
        for prior in STEPS[:index]:
            if prior not in self.state.completed:
                return f"ORDER_VIOLATION:require_{prior}"
        return None

    def invalidate_from(self, step: str) -> None:
        """Discard stale step and all descendants before retry or new upstream data."""
        index = STEPS.index(step)
        self.state.completed = [item for item in self.state.completed if STEPS.index(item) < index]
        if index <= STEPS.index("PRECHECK"):
            self.state.precheck = {}
        if index <= STEPS.index("IMPORT_TRANSACTION"):
            self.state.import_provenance = {}
        if index <= STEPS.index("SELECT_COMMIT"):
            self.state.classification = ""
        if index <= STEPS.index("BUILD"):
            self.state.runtime_built = False
        if index <= STEPS.index("APPLY"):
            self.state.motion_applied = False
        if index <= STEPS.index("VALIDATE"):
            self.state.validation_passed = False
        if index <= STEPS.index("EXPORT"):
            self.state.export_path, self.state.planned_export_path, self.state.wrote = "", "", False

    def precheck_fbx(self, path: str | Path) -> dict:
        self.invalidate_from("PRECHECK")
        try:
            self.state.precheck = validate_fbx_input(path)
        except ContractViolation as exc:
            self._record("PRECHECK", "ABORT", str(exc))
            return {"ok": False, "abort": str(exc)}
        self.state.completed.append("PRECHECK")
        self._record("PRECHECK", "PASS", self.state.precheck["path"].as_posix())
        return {"ok": True, "precheck": dict(self.state.precheck)}

    def record_import(self, result: dict) -> dict:
        err = self._require("IMPORT_TRANSACTION")
        if err:
            self._record("IMPORT_TRANSACTION", "ABORT", err)
            return {"ok": False, "abort": err}
        if not result.get("ok") or not result.get("provenance"):
            abort = result.get("abort", "IMPORT_FAILED")
            self._record("IMPORT_TRANSACTION", "ABORT", abort)
            return {"ok": False, "abort": abort}
        provenance = result["provenance"]
        if provenance.get("sha256") != self.state.precheck.get("sha256") or provenance.get("path") != self.state.precheck["path"].as_posix():
            self._record("IMPORT_TRANSACTION", "ABORT", "IMPORT_PROVENANCE_MISMATCH")
            return {"ok": False, "abort": "IMPORT_PROVENANCE_MISMATCH"}
        self.state.import_provenance = dict(provenance)
        self.state.completed.append("IMPORT_TRANSACTION")
        self._record("IMPORT_TRANSACTION", "PASS", provenance["sha256"])
        return {"ok": True}

    def select_commit(self) -> dict:
        err = self._require("SELECT_COMMIT")
        if err:
            self._record("SELECT_COMMIT", "ABORT", err)
            return {"ok": False, "abort": err}
        if not self.state.import_provenance.get("importedObjects"):
            self._record("SELECT_COMMIT", "ABORT", "IMPORT_PROVENANCE_MISSING")
            return {"ok": False, "abort": "IMPORT_PROVENANCE_MISSING"}
        self.state.completed.append("SELECT_COMMIT")
        self._record("SELECT_COMMIT", "PASS", self.state.import_provenance["sha256"])
        return {"ok": True}

    def analyze(self, classification: str) -> dict:
        err = self._require("ANALYZE")
        if err or classification not in {"FULL", "LIMITED"}:
            abort = err or "BAD_CLASSIFICATION"
            self._record("ANALYZE", "ABORT", abort)
            return {"ok": False, "abort": abort}
        self.invalidate_from("ANALYZE")
        self.state.classification = classification
        self.state.completed.append("ANALYZE")
        self._record("ANALYZE", "PASS", classification)
        return {"ok": True}

    def build(self, *, runtime_built: bool) -> dict:
        err = self._require("BUILD")
        if err or not runtime_built:
            abort = err or "RUNTIME_BUILD_FAILED"
            self._record("BUILD", "ABORT", abort)
            return {"ok": False, "abort": abort}
        self.invalidate_from("BUILD")
        self.state.runtime_built = True
        self.state.completed.append("BUILD")
        self._record("BUILD", "PASS")
        return {"ok": True}

    def apply(self, *, motion_applied: bool) -> dict:
        err = self._require("APPLY")
        if err or not motion_applied or not self.state.runtime_built:
            abort = err or "MOTION_APPLY_FAILED"
            self._record("APPLY", "ABORT", abort)
            return {"ok": False, "abort": abort}
        self.invalidate_from("APPLY")
        self.state.motion_applied = True
        self.state.completed.append("APPLY")
        self._record("APPLY", "PASS")
        return {"ok": True}

    def validate(self, *, report: dict, passed: bool) -> dict:
        err = self._require("VALIDATE")
        if err:
            self._record("VALIDATE", "ABORT", err)
            return {"ok": False, "abort": err}
        self.invalidate_from("VALIDATE")  # stale VALIDATE/EXPORT are never retained
        try:
            validate_timing(fps=report.get("fps"), dt=report.get("dt"), frame_start=report.get("frameStart"), frame_end=report.get("frameEnd"))
        except ContractViolation as exc:
            self._record("VALIDATE", "ABORT", str(exc))
            return {"ok": False, "abort": str(exc)}
        if not passed:
            self._record("VALIDATE", "ABORT", "VALIDATION_FAILED")
            return {"ok": False, "abort": "VALIDATION_FAILED"}
        self.state.validation_passed = True
        self.state.completed.append("VALIDATE")
        self._record("VALIDATE", "PASS")
        return {"ok": True}

    def preflight_export(self, *, path: str | Path, fmt: str, root: str | Path) -> dict:
        err = self._require("EXPORT")
        if err or not self.state.validation_passed:
            abort = err or "EXPORT_REQUIRES_VALIDATION"
            self._record("EXPORT", "ABORT", abort)
            return {"ok": False, "abort": abort}
        try:
            target = validate_export_target(path, fmt=fmt, root=root)
        except ContractViolation as exc:
            self._record("EXPORT", "ABORT", str(exc))
            return {"ok": False, "abort": str(exc)}
        self.state.planned_export_path = target.as_posix()
        return {"ok": True, "target": target}

    def record_export(self, result: dict) -> dict:
        if not result.get("ok"):
            abort = result.get("abort", "EXPORT_WRITE_FAILED")
            self._record("EXPORT", "ABORT", abort)
            return {"ok": False, "abort": abort}
        target = Path(result.get("path", ""))
        if not self.state.planned_export_path or target.as_posix() != self.state.planned_export_path:
            self._record("EXPORT", "ABORT", "EXPORT_PROVENANCE_MISMATCH")
            return {"ok": False, "abort": "EXPORT_PROVENANCE_MISMATCH"}
        try:
            written = target.is_file() and target.stat().st_size > 0
        except (OSError, OverflowError):
            written = False
        if not written:
            self._record("EXPORT", "ABORT", "EXPORT_WRITE_FAILED")
            return {"ok": False, "abort": "EXPORT_WRITE_FAILED"}
        self.state.export_path, self.state.wrote = target.as_posix(), True
        self.state.completed.append("EXPORT")
        self._record("EXPORT", "PASS", self.state.export_path)
        return {"ok": True}
