"""Gate 7B fresh holdout: eligibility → clean import → frozen Gate1–6 → 3× determinism."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..gate6.beauty_integration import run_beauty_integration
from ..gate6.beauty_validator import validate_beauty_integration
from ..gate7a.lock_registry import assert_all_gate_params_locked, required_pipeline_objects
from .eligibility import (
    extract_holdout_zip,
    face_eye_eligibility,
    pick_primary_model,
    pre_import_eligibility,
    scene_structural_eligibility,
    sha256_file,
)
from .parameters import GATE7B_PARAMETERS, RC1_PACKAGE, RC1_SHA256, parameter_hash


def _sha_json(doc: dict) -> str:
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class HoldoutResult:
    verdict: str
    eligibility: Dict
    lock_report: Dict
    beauty_reports: List[Dict]
    profiles: List[Dict]
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    zip_sha256: str = ""
    model_sha256: str = ""
    model_path: str = ""
    rc1_sha256: str = RC1_SHA256

    def to_report(self) -> dict:
        return {
            "schema": "NURION_GATE7B_HOLDOUT_REPORT",
            "version": GATE7B_PARAMETERS["version"],
            "verdict": self.verdict,
            "parameterHash": self.parameter_hash or parameter_hash(),
            "rc1Package": RC1_PACKAGE,
            "rc1Sha256": self.rc1_sha256,
            "releaseCandidate": True,
            "sealed": False if self.verdict != "HOLDOUT_PASS" else False,
            "holdout": (
                "PASS"
                if self.verdict == "HOLDOUT_PASS"
                else ("WAITING" if self.verdict == "WAITING_FOR_NEW_ASSET" else self.verdict)
            ),
            "finalSeal": "HOLD",
            "manualCorrection": 0,
            "parameterTuning": 0,
            "retryAfterEdit": "DENY",
            "gateParamChange": int(self.lock_report.get("gateParamChange", 0)) if self.lock_report else 0,
            "zipSha256": self.zip_sha256,
            "modelSha256": self.model_sha256,
            "modelPath": self.model_path,
            "eligibility": self.eligibility,
            "lockReport": {
                "gate2ParameterHash": self.lock_report.get("gate2ParameterHash"),
                "gate3ParameterHash": self.lock_report.get("gate3ParameterHash"),
                "gate4aParameterHash": self.lock_report.get("gate4aParameterHash"),
                "gate4bParameterHash": self.lock_report.get("gate4bParameterHash"),
                "gate5ParameterHash": self.lock_report.get("gate5ParameterHash"),
                "gate6ParameterHash": self.lock_report.get("gate6ParameterHash"),
            }
            if self.lock_report
            else {},
            "beautyVerdicts": [r.get("verdict") for r in self.beauty_reports],
            "profileSha256": [_sha_json(p) for p in self.profiles],
            "notes": list(self.notes),
        }


def _check_objects() -> Dict:
    import bpy

    required = required_pipeline_objects()
    missing = [n for n in required if bpy.data.objects.get(n) is None]
    return {"requiredCount": len(required), "missing": missing, "ok": len(missing) == 0}


def verify_rc1_package(root: Path) -> Dict:
    pkg = Path(root) / "dist/v0.3/universal_eye/gate7a/package" / RC1_PACKAGE
    if not pkg.exists():
        return {"ok": False, "notes": [f"RC.1 package missing: {pkg}"], "sha256": ""}
    digest = sha256_file(pkg)
    ok = digest == RC1_SHA256
    return {
        "ok": ok,
        "sha256": digest,
        "expected": RC1_SHA256,
        "notes": [] if ok else ["RC.1 SHA mismatch — package must not be repacked"],
    }


def run_fresh_holdout(
    *,
    zip_path: Path,
    root: Optional[Path] = None,
    mesh_name: str = "",
    work_dir: Optional[Path] = None,
    clean_import_cb=None,
    runs: int = 3,
) -> HoldoutResult:
    """
    Pipeline:
      ELIGIBILITY → CLEAN IMPORT → GATE1–6 FROZEN → 3× DETERMINISM → REVIEW
    No manual correction, no parameter tuning, no retry-after-edit.
    """
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    zip_path = Path(zip_path)
    notes: List[str] = []
    beauty_reports: List[Dict] = []
    profiles: List[Dict] = []
    eligibility: Dict = {}
    lock_report: Dict = {}

    rc1 = verify_rc1_package(root)
    if not rc1["ok"]:
        notes.extend(rc1["notes"])
        return HoldoutResult(
            verdict="ALGORITHM_FAIL",
            eligibility={"rc1": rc1},
            lock_report={},
            beauty_reports=[],
            profiles=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=sha256_file(zip_path) if zip_path.exists() else "",
        )

    work_dir = Path(work_dir) if work_dir else root / "dist/v0.3/universal_eye/gate7b/_extract"
    extract_info = extract_holdout_zip(zip_path, work_dir)
    model = pick_primary_model(extract_info)
    pre = pre_import_eligibility(zip_path, extract_info, model)
    eligibility["preImport"] = pre
    if pre["verdict"] != "PASS":
        notes.extend(pre.get("notes") or [])
        return HoldoutResult(
            verdict="ASSET_INELIGIBLE",
            eligibility=eligibility,
            lock_report={},
            beauty_reports=[],
            profiles=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=extract_info["zipSha256"],
            model_sha256=pre.get("modelSha256") or "",
            model_path=pre.get("modelPath") or "",
        )

    if clean_import_cb is None:
        raise RuntimeError("clean_import_cb required (Blender harness)")

    # Structural + face eligibility on first clean import
    clean_import_cb(Path(pre["modelPath"]))
    structural = scene_structural_eligibility()
    eligibility["structural"] = structural
    if structural["verdict"] != "PASS":
        notes.extend(structural.get("notes") or [])
        return HoldoutResult(
            verdict="ASSET_INELIGIBLE",
            eligibility=eligibility,
            lock_report={},
            beauty_reports=[],
            profiles=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=extract_info["zipSha256"],
            model_sha256=pre["modelSha256"],
            model_path=pre["modelPath"],
        )

    face = face_eye_eligibility(mesh_name=mesh_name)
    eligibility["faceEyes"] = face
    if face["verdict"] != "PASS":
        notes.extend(face.get("notes") or [])
        return HoldoutResult(
            verdict="ASSET_INELIGIBLE",
            eligibility=eligibility,
            lock_report={},
            beauty_reports=[],
            profiles=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=extract_info["zipSha256"],
            model_sha256=pre["modelSha256"],
            model_path=pre["modelPath"],
        )

    # Frozen Gate1–6 execution (3× clean rebuild)
    try:
        lock_report = assert_all_gate_params_locked(root)
    except Exception as exc:  # noqa: BLE001
        notes.append(str(exc))
        return HoldoutResult(
            verdict="ALGORITHM_FAIL",
            eligibility=eligibility,
            lock_report={},
            beauty_reports=[],
            profiles=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=extract_info["zipSha256"],
            model_sha256=pre["modelSha256"],
            model_path=pre["modelPath"],
        )

    mesh_arg = mesh_name or face.get("meshName") or ""
    object_checks = []
    for i in range(int(runs)):
        clean_import_cb(Path(pre["modelPath"]))
        try:
            result = run_beauty_integration(
                mesh_name=mesh_arg,
                root=root,
                preset="NATURAL",
                tier="High",
                evaluate_all_presets=True,
            )
            profiles.append(result.to_profile())
            report = validate_beauty_integration(result, root=root, determinism_profiles=None)
            beauty_reports.append(report)
            oc = _check_objects()
            oc["run"] = i
            object_checks.append(oc)
            if report.get("verdict") != "PASS":
                notes.append(f"run{i} beauty FAIL: {report.get('fails')}")
            if not oc["ok"]:
                notes.append(f"run{i} missing objects: {oc['missing']}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"run{i} pipeline exception: {exc}")
            beauty_reports.append({"verdict": "FAIL", "fails": ["PIPELINE_EXCEPTION"], "error": str(exc)})
            object_checks.append({"run": i, "ok": False, "missing": ["EXCEPTION"]})

    def stab(p: dict) -> dict:
        return {
            "parameterHash": p.get("parameterHash"),
            "appliedPreset": p.get("appliedPreset"),
            "catchlight": p.get("catchlight"),
            "geometryAfter": p.get("geometryAfter"),
            "gate5ParameterHash": p.get("gate5ParameterHash"),
            "evaluatedPresets": p.get("evaluatedPresets"),
        }

    if len(profiles) >= 3:
        h0 = _sha_json(stab(profiles[0]))
        det_ok = all(_sha_json(stab(p)) == h0 for p in profiles[1:3])
        determinism = "PASS" if det_ok else "FAIL"
        if not det_ok:
            notes.append("3x end-to-end determinism mismatch")
    else:
        determinism = "FAIL"
        notes.append("insufficient determinism runs")

    eligibility["determinism3x"] = determinism
    eligibility["objectChecks"] = object_checks

    all_beauty = all(r.get("verdict") == "PASS" for r in beauty_reports) and len(beauty_reports) >= runs
    all_objs = all(c.get("ok") for c in object_checks) if object_checks else False
    param_ok = lock_report.get("gateParamChange") == 0

    if all_beauty and all_objs and determinism == "PASS" and param_ok:
        verdict = "HOLDOUT_PASS"
    else:
        # Eligible asset reached frozen execution — failure is algorithmic
        verdict = "ALGORITHM_FAIL"

    return HoldoutResult(
        verdict=verdict,
        eligibility=eligibility,
        lock_report=lock_report,
        beauty_reports=beauty_reports,
        profiles=profiles,
        notes=notes,
        parameter_hash=parameter_hash(),
        zip_sha256=extract_info["zipSha256"],
        model_sha256=pre["modelSha256"],
        model_path=pre["modelPath"],
    )
