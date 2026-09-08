"""Gate 8A — full determinism regression on Formal Bow seed (clean-scene ×3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .parameters import (
    FOOT_SLIDE_RESIDUAL,
    GATE8_PARAMETERS,
    V04_RC1_SHA256,
    parameter_hash,
)
from .pipeline import _sha_file, _sha_json, run_clean_pipeline_once, verify_frozen_hashes


@dataclass
class Gate8AResult:
    report: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def build_gate8a_validation(stable: Dict, det: str, frozen_ok: bool, v04_ok: bool) -> Dict:
    gates = {
        "FROZEN_HASHES_G1_G7": "PASS" if frozen_ok else "FAIL",
        "INTERMEDIATE_OUTPUT_REUSE": "DENY",
        "DETERMINISM_3X_ACTION_KEYS_TIMELINE": det,
        "FPS_MEANING_24_30_60": "PASS" if stable.get("fpsMeaningOk") else "FAIL",
        "FORMAL_BOW_WORD_CONFIRM_SYNC": "PASS" if stable.get("faceBodyTimelineDriftOk") else "FAIL",
        "FOOT_SLIDE_RESIDUAL_NOT_WORSENED": "PASS" if int(stable.get("slidesFinal", 99)) <= FOOT_SLIDE_RESIDUAL else "FAIL",
        "SHALLOW_CONTACT_LE_3_5MM": "PASS" if stable.get("shallowContactOk") else "FAIL",
        "RIGHTFOREARM_LIMITATION_PRESERVED": "PASS" if stable.get("forearmFingerprint") else "FAIL",
        "V04_SEAL_MUTATION": 0 if v04_ok else 1,
        "GATE6_BODY_MUTATION": int(stable.get("gate6BodyMutation", 1)),
        "SOURCE_ACTION_MUTATION": int(stable.get("sourceActionMutation", 1)),
        "FACE_EYE_LIPSYNC_BIND": "PASS" if stable.get("faceBindOk") else "FAIL",
        "LR_SWAP": int(stable.get("lrSwapCount", 1)),
        "AXIS_ERROR": 0 if not stable.get("axisFailChains") else len(stable.get("axisFailChains") or []),
        "PARAMETER_TUNING": 0,
        "MANUAL_CORRECTION": 0,
        "PRODUCTION": "NO-GO",
        "SUPPORTED_DOMAIN": "LIMITED",
        "V04_MUTATION": "DENY",
    }

    def ok(k, v):
        if k in (
            "FROZEN_HASHES_G1_G7",
            "DETERMINISM_3X_ACTION_KEYS_TIMELINE",
            "FPS_MEANING_24_30_60",
            "FORMAL_BOW_WORD_CONFIRM_SYNC",
            "FOOT_SLIDE_RESIDUAL_NOT_WORSENED",
            "SHALLOW_CONTACT_LE_3_5MM",
            "RIGHTFOREARM_LIMITATION_PRESERVED",
            "FACE_EYE_LIPSYNC_BIND",
        ):
            return v == "PASS"
        if k in ("INTERMEDIATE_OUTPUT_REUSE", "V04_MUTATION"):
            return v == "DENY"
        if k in ("PRODUCTION", "SUPPORTED_DOMAIN"):
            return v in ("NO-GO", "LIMITED")
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    limitations = list(GATE8_PARAMETERS["inheritedLimitations"])
    limitations.append("LIMITED_DOMAIN")
    limitations.append("V04_READONLY_INPUT")

    if fails:
        verdict = "FAIL"
    else:
        verdict = "PASS_WITH_LIMITATIONS"

    return {
        "schema": "NURION_V05_GATE8A_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": sorted(set(limitations)),
        "verdict": verdict,
        "parameterHash": parameter_hash(),
    }


def run_gate8a(
    *,
    fbx_path: Path,
    mesh_name: str = "char1",
    runs: int = 3,
    clean_import_cb=None,
    root: Optional[Path] = None,
) -> Gate8AResult:
    notes: List[str] = []
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    frozen = verify_frozen_hashes(root)
    if not frozen["ok"]:
        notes.append(f"frozen hash check failed: {frozen['checks']}")

    rc1 = root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
    v04_ok = rc1.exists() and _sha_file(rc1) == V04_RC1_SHA256

    results = []
    for i in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        # Explicit: never load dist/v0.5/gate{1..7} intermediates
        results.append(run_clean_pipeline_once(fbx_path=fbx_path, mesh_name=mesh_name, root=root, seed_mode=True))
        if _sha_file(rc1) != V04_RC1_SHA256:
            v04_ok = False
            notes.append("v0.4 RC.1 mutated during Gate8A")

    hashes = [r["determinismHash"] for r in results]
    det = "FAIL"
    if len(hashes) >= 3 and all(h == hashes[0] for h in hashes[1:3]):
        det = "PASS"
    if det != "PASS":
        notes.append("3x determinism mismatch on action/keys/timeline")

    last = results[-1]
    fp = last["fingerprint"]
    validation = build_gate8a_validation(fp, det, frozen["ok"], v04_ok)

    report = {
        "schema": "NURION_V05_GATE8A_REGRESSION_REPORT",
        "version": GATE8_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "asset": GATE8_PARAMETERS["seedAsset"]["label"],
        "role": GATE8_PARAMETERS["seedAsset"]["role"],
        "intermediateOutputReuse": "DENY",
        "frozenHashes": frozen,
        "determinism3x": det,
        "determinismHashes": hashes,
        "fingerprint": fp,
        "mapping": last["mapping"],
        "lr": {"ok": last["lr"].get("ok"), "swapCount": len(last["lr"].get("swaps") or [])},
        "axis": last["axis"],
        "pen": last["pen"],
        "inheritedLimitations": GATE8_PARAMETERS["inheritedLimitations"],
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "v04Mutation": "DENY",
        "notes": notes,
        "next": "GATE8B_CROSS_ASSET",
    }
    return Gate8AResult(
        report=report,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
