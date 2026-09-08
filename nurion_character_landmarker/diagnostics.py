"""Diagnostic report writer for NURION Character Landmarker v0.1 practical tests."""

from __future__ import annotations

import json
import platform
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ADDON_VERSION = "0.2.0-alpha.2"
REPORT_FILENAME = "nurion-diagnostic-report.json"


def reports_dir() -> Path:
    base = Path.home() / "Documents" / "NURION" / "diagnostics"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _blender_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"available": False}
    try:
        import bpy

        info = {
            "available": True,
            "version": list(bpy.app.version),
            "version_string": bpy.app.version_string,
            "build_platform": getattr(bpy.app, "build_platform", b"").decode("utf-8", errors="ignore")
            if isinstance(getattr(bpy.app, "build_platform", b""), (bytes, bytearray))
            else str(getattr(bpy.app, "build_platform", "")),
        }
    except Exception as exc:  # pragma: no cover - outside Blender
        info["error"] = str(exc)
    return info


def build_report(
    *,
    stage: str,
    success: bool,
    message: str,
    error: Optional[BaseException] = None,
    checklist: Optional[Dict[str, bool]] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "schema": "NURION_DIAGNOSTIC_REPORT",
        "addon": "NURION Character Landmarker",
        "version": ADDON_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "success": success,
        "message": message,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        "blender": _blender_info(),
        "checklist": checklist or {},
        "extras": extras or {},
    }
    if error is not None:
        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        }
    return report


def write_report(report: Dict[str, Any], path: Optional[Path] = None) -> Path:
    target = path or (reports_dir() / f"nurion-diagnostic-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Also refresh a stable latest pointer for quick inspection.
    latest = reports_dir() / REPORT_FILENAME
    latest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def report_exception(stage: str, error: BaseException, extras: Optional[Dict[str, Any]] = None) -> Path:
    report = build_report(
        stage=stage,
        success=False,
        message=f"Error during {stage}: {error}",
        error=error,
        extras=extras,
    )
    return write_report(report)


def default_checklist() -> Dict[str, bool]:
    return {
        "zip_install": False,
        "sidebar_visible": False,
        "character_select": False,
        "measurements": False,
        "body_guides": False,
        "guide_move_save": False,
        "profile_restore": False,
        "profile_export": False,
        "disable_reinstall": False,
    }
