"""Gate 8C Fresh Holdout — frozen RC.1 + Core14 timelines, no tuning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from nurion_v04_face_rig.gate7.integration import run_gate7_once
from nurion_v04_face_rig.gate7.parameters import CORE_IDS, STRESS_IDS
from nurion_v04_face_rig.gate8a.lock_check import verify_all_locked

from .eligibility import (
    extract_holdout_zip,
    face_mouth_eligibility,
    pick_primary_model,
    pre_import_eligibility,
    scene_structural_eligibility,
    sha256_file,
)
from .parameters import GATE8C_PARAMETERS, RC1_PACKAGE, RC1_SHA256, parameter_hash


def _sha_json(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class HoldoutResult:
    verdict: str
    eligibility: Dict
    lock_report: Dict
    runs: List[Dict]
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    zip_sha256: str = ""
    model_sha256: str = ""
    model_path: str = ""
    rc1_sha256: str = RC1_SHA256

    def to_report(self) -> dict:
        return {
            "schema": "NURION_V04_GATE8C_HOLDOUT_REPORT",
            "version": GATE8C_PARAMETERS["version"],
            "verdict": self.verdict,
            "parameterHash": self.parameter_hash or parameter_hash(),
            "rc1Package": RC1_PACKAGE,
            "rc1Sha256": self.rc1_sha256,
            "rc1Repack": "DENY",
            "releaseCandidate": True,
            "supportedDomain": "LIMITED",
            "humanSpeech": "PASS_WITH_LIMITATIONS",
            "sealed": False,
            "holdout": self.verdict if self.verdict != "WAITING_FOR_NEW_ASSET" else "WAITING",
            "finalSeal": "HOLD",
            "manualCorrection": 0,
            "parameterTuning": 0,
            "core14TimelineChange": "DENY",
            "retryAfterEdit": "DENY",
            "zipSha256": self.zip_sha256,
            "modelSha256": self.model_sha256,
            "modelPath": self.model_path,
            "eligibility": self.eligibility,
            "lockReport": self.lock_report,
            "runStables": [r.get("stable") for r in self.runs],
            "notes": list(self.notes),
            "pipeline": GATE8C_PARAMETERS["pipeline"],
        }


def verify_rc1_package(root: Path) -> Dict:
    pkg = Path(root) / "dist/v0.4/gate8b/package" / RC1_PACKAGE
    if not pkg.exists():
        return {"ok": False, "notes": [f"RC.1 package missing: {pkg}"], "sha256": ""}
    digest = sha256_file(pkg)
    ok = digest == RC1_SHA256
    return {
        "ok": ok,
        "sha256": digest,
        "expected": RC1_SHA256,
        "notes": [] if ok else ["RC.1 SHA mismatch — REPACK DENY"],
    }


def _classify_verdict(g7: Dict, locks: Dict, det: str) -> str:
    if locks.get("gateParamChange", 1) != 0 or locks.get("v03") != "UNCHANGED":
        return "ALGORITHM_FAIL"
    m = g7.get("metrics") or {}
    hard = [
        m.get("lowConfidenceOverdrive", 0),
        m.get("silenceFalseMotion", 0),
        m.get("lipIntersection", 0),
        m.get("lipOrderInversion", 0),
        m.get("nonFaceLeak", 0),
        m.get("blinkLipsyncConflict", 0),
        m.get("expressionVisemeConflict", 0),
        m.get("eyeDomeBaseDrift", 0),
        g7.get("srcMut", 1),
    ]
    if any(int(x) != 0 for x in hard):
        return "ALGORITHM_FAIL"
    if g7.get("fpsStatus") != "PASS" or g7.get("restPres") != "PASS" or det != "PASS":
        return "ALGORITHM_FAIL"
    # Propagated Gate6 limitations are expected → PASS_WITH_LIMITATIONS unless fully clean
    rest = int(m.get("restFallbackSeen", 0) or (g7.get("stable") or {}).get("restFallbackSeen", 0) or 0)
    if rest > 0:
        return "PASS_WITH_LIMITATIONS"
    return "HOLDOUT_PASS"


def run_fresh_holdout(
    *,
    zip_path: Path,
    root: Optional[Path] = None,
    mesh_name: str = "",
    work_dir: Optional[Path] = None,
    timelines_dir: Optional[Path] = None,
    clean_import_cb=None,
    runs: int = 3,
) -> HoldoutResult:
    """
    ELIGIBILITY → CLEAN IMPORT/REST → frozen Gate7 (eyes+lips+coordinator on Core14)
    CORE14 timeline files are read-only (no realign).
    """
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    zip_path = Path(zip_path)
    notes: List[str] = []
    eligibility: Dict = {}
    runs_out: List[Dict] = []

    rc1 = verify_rc1_package(root)
    if not rc1["ok"]:
        notes.extend(rc1["notes"])
        return HoldoutResult(
            verdict="ALGORITHM_FAIL",
            eligibility={"rc1": rc1},
            lock_report={},
            runs=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=sha256_file(zip_path) if zip_path.exists() else "",
        )

    locks = verify_all_locked(root)
    # Gate7/8a self hashes are checked via gate1-7; also assert frozen constants
    from nurion_v04_face_rig.gate7.parameters import parameter_hash as g7h
    from nurion_v04_face_rig.gate8a.parameters import parameter_hash as g8ah
    from .parameters import GATE7_FROZEN, GATE8A_FROZEN

    if g7h() != GATE7_FROZEN or g8ah() != GATE8A_FROZEN:
        notes.append("Gate7/8A parameter drift vs RC freeze")
        return HoldoutResult(
            verdict="ALGORITHM_FAIL",
            eligibility={"rc1": rc1},
            lock_report=locks,
            runs=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=sha256_file(zip_path) if zip_path.exists() else "",
        )

    work_dir = Path(work_dir) if work_dir else root / "dist/v0.4/gate8c/_extract"
    tdir = Path(timelines_dir) if timelines_dir else root / "dist/v0.4/gate6/human_gate4_timelines"
    if not tdir.exists():
        notes.append("Frozen Core14 timelines missing")
        return HoldoutResult(
            verdict="ALGORITHM_FAIL",
            eligibility={"rc1": rc1},
            lock_report=locks,
            runs=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=sha256_file(zip_path) if zip_path.exists() else "",
        )

    extract_info = extract_holdout_zip(zip_path, work_dir)
    model = pick_primary_model(extract_info)
    pre = pre_import_eligibility(zip_path, extract_info, model)
    eligibility["preImport"] = pre
    if pre["verdict"] != "PASS":
        notes.extend(pre.get("notes") or [])
        return HoldoutResult(
            verdict="ASSET_INELIGIBLE",
            eligibility=eligibility,
            lock_report=locks,
            runs=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=extract_info.get("zipSha256", ""),
            model_sha256=pre.get("modelSha256", ""),
            model_path=pre.get("modelPath") or "",
        )

    if clean_import_cb is None:
        notes.append("clean_import_cb required")
        return HoldoutResult(
            verdict="ALGORITHM_FAIL",
            eligibility=eligibility,
            lock_report=locks,
            runs=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=extract_info.get("zipSha256", ""),
            model_sha256=pre.get("modelSha256", ""),
            model_path=str(model).replace("\\", "/"),
        )

    # First import: structural + face/mouth eligibility
    clean_import_cb(model)
    struct = scene_structural_eligibility()
    eligibility["structural"] = struct
    if struct["verdict"] != "PASS":
        notes.extend(struct.get("notes") or [])
        return HoldoutResult(
            verdict="ASSET_INELIGIBLE",
            eligibility=eligibility,
            lock_report=locks,
            runs=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=extract_info.get("zipSha256", ""),
            model_sha256=pre.get("modelSha256", ""),
            model_path=str(model).replace("\\", "/"),
        )

    face = face_mouth_eligibility(mesh_name=mesh_name)
    eligibility["faceMouth"] = face
    if face["verdict"] != "PASS":
        notes.extend(face.get("notes") or [])
        return HoldoutResult(
            verdict="ASSET_INELIGIBLE",
            eligibility=eligibility,
            lock_report=locks,
            runs=[],
            notes=notes,
            parameter_hash=parameter_hash(),
            zip_sha256=extract_info.get("zipSha256", ""),
            model_sha256=pre.get("modelSha256", ""),
            model_path=str(model).replace("\\", "/"),
        )

    resolved_mesh = face.get("meshName") or mesh_name or ""

    for i in range(int(runs)):
        clean_import_cb(model)
        g7 = run_gate7_once(timelines_dir=tdir, mesh_name=resolved_mesh, root=root)
        # Ensure Core14 present
        core_n = int((g7.get("stable") or {}).get("coreCount") or 0)
        stress_n = int((g7.get("stable") or {}).get("stressCount") or 0)
        if core_n != len(CORE_IDS):
            notes.append(f"run{i} coreCount={core_n} expected={len(CORE_IDS)}")
        runs_out.append(
            {
                "run": i,
                "stable": g7.get("stable"),
                "metrics": g7.get("metrics"),
                "restPres": g7.get("restPres"),
                "fpsStatus": g7.get("fpsStatus"),
                "srcMut": g7.get("srcMut"),
                "readability": g7.get("readability"),
                "coreCount": core_n,
                "stressCount": stress_n,
                "stressIds": list(STRESS_IDS),
            }
        )

    stables = [r["stable"] for r in runs_out if r.get("stable")]
    det = "FAIL"
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det = "PASS" if all(_sha_json(s) == h0 for s in stables[1:3]) else "FAIL"
    if det != "PASS":
        notes.append("3x holdout determinism mismatch")

    last = runs_out[-1]
    verdict = _classify_verdict(last, locks, det)
    if any("coreCount=" in n for n in notes) and verdict != "ASSET_INELIGIBLE":
        verdict = "ALGORITHM_FAIL"

    return HoldoutResult(
        verdict=verdict,
        eligibility=eligibility,
        lock_report=locks,
        runs=runs_out,
        notes=notes,
        parameter_hash=parameter_hash(),
        zip_sha256=extract_info.get("zipSha256", ""),
        model_sha256=pre.get("modelSha256", ""),
        model_path=str(model).replace("\\", "/"),
    )
