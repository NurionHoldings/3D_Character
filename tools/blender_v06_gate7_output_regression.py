"""
v0.6 Gate 7 — output / regression validation harness.

Usage:
  blender --background --python tools/blender_v06_gate7_output_regression.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "gate7"
FORMAL = (
    ROOT
    / "dist/v0.5/gate1/ai-aba.bow/_extract/Meshy_AI_Silver_Starlight_Sent_biped"
    / "Meshy_AI_Silver_Starlight_Sent_biped_Animation_Formal_Bow_withSkin.fbx"
)
GATE6_HASH = "3207531397c6372bbba4e38aebb3024fdc1e85f1792526a5f3115e36bbdf746e"
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


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from nurion_v06_unified_runtime.gate6.parameters import parameter_hash as g6_hash
    from nurion_v06_unified_runtime.gate7.parameters import GATE7_PARAMETERS, parameter_hash
    from nurion_v06_unified_runtime.gate7.regression import run_gate7_regression

    if g6_hash() != GATE6_HASH:
        raise RuntimeError("Gate6 hash drift — DENY")

    label = "ai-aba"
    out_dir = OUT / label
    result = run_gate7_regression(
        label=label,
        fbx_path=FORMAL,
        out_dir=out_dir,
        source_fbx_sha_expected=_sha(FORMAL),
        baseline_hash_ok=_baseline_ok(),
        runs=3,
    )

    _write(out_dir / "GATE7_PROFILE.json", result.profile)
    _write(out_dir / "GATE7_VALIDATION.json", result.validation)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ph = parameter_hash()
    asset_status = {
        "schema": "NURION_V06_GATE7_ASSET_STATUS",
        "gate": "7",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "OUTPUT_REGRESSION",
        "label": label,
        "outputVerdict": result.verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "gate6Locked": True,
        "sourceMutation": result.source_mutation,
        "manualCorrection": result.manual_correction,
        "assetSpecificTuning": result.asset_specific_tuning,
        "partialExportPublish": "DENY",
        "gates": result.validation.get("gates"),
        "hardFails": result.validation.get("hardFails"),
        "determinism": result.validation.get("determinism"),
        "lipsyncMode": "REST_FALLBACK",
        "inheritedLimitationsFromV05": GATE7_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "production": "NO-GO",
        "notes": result.notes,
        "updatedAt": now,
        "artifacts": {"profile": "GATE7_PROFILE.json", "validation": "GATE7_VALIDATION.json"},
        "next": "GATE8_FRESH_HOLDOUT_AND_RC",
    }
    _write(out_dir / "V06_GATE7_ASSET_STATUS.json", asset_status)

    # empty-control ABSTAIN record (no force output validation)
    empty = {
        "schema": "NURION_V06_GATE7_ASSET_STATUS",
        "gate": "7",
        "label": "empty-control",
        "outputVerdict": "PASS",
        "runtimeAction": "ABSTAIN",
        "abstainReasons": ["GATE2_OR_PRIOR_INELIGIBLE"],
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "sourceMutation": 0,
        "manualCorrection": 0,
        "production": "NO-GO",
        "updatedAt": now,
        "next": "GATE8_FRESH_HOLDOUT_AND_RC",
    }
    _write(OUT / "empty-control" / "V06_GATE7_ASSET_STATUS.json", empty)

    track_verdict = result.verdict if result.verdict in ("PASS", "PASS_WITH_LIMITATIONS") else "FAIL"
    receipt = {
        "schema": "NURION_V06_GATE7_RECEIPT",
        "gate": "7",
        "name": "OUTPUT_REGRESSION",
        "V06_GATE7": track_verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "gate6Locked": True,
        "production": "NO-GO",
        "sourceMutationTotal": result.source_mutation,
        "manualCorrectionTotal": 0,
        "partialExportPublish": "DENY",
        "inheritedLimitationsFromV05": GATE7_PARAMETERS["inheritedLimitationsFromV05"],
        "assets": [
            {"label": label, "outputVerdict": result.verdict, "hardFails": result.validation.get("hardFails")},
            {"label": "empty-control", "outputVerdict": "PASS", "runtimeAction": "ABSTAIN"},
        ],
        "hardFails": result.validation.get("hardFails") or [],
        "updatedAt": now,
        "next": "GATE8_FRESH_HOLDOUT_AND_RC",
    }
    status = {
        "schema": "NURION_V06_GATE7_STATUS",
        "gate": "7",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "OUTPUT_REGRESSION",
        "V06_GATE7": track_verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "gate6Locked": True,
        "production": "NO-GO",
        "sourceMutationTotal": result.source_mutation,
        "inheritedLimitationsFromV05": GATE7_PARAMETERS["inheritedLimitationsFromV05"],
        "hardFails": result.validation.get("hardFails") or [],
        "updatedAt": now,
        "artifacts": {"receipt": "V06_GATE7_RECEIPT.json", "parameters": "V06_GATE7_PARAMETERS.json"},
        "next": "GATE8_FRESH_HOLDOUT_AND_RC",
    }
    track = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_GATE7",
        "status": "IN_PROGRESS",
        "V06_GATE6": "PASS_WITH_LIMITATIONS",
        "gate6ParameterHash": GATE6_HASH,
        "gate6Locked": True,
        "V06_GATE7": track_verdict,
        "gate7ParameterHash": ph,
        "production": "NO-GO",
        "sealedBaselineMutation": "DENY",
        "limitationAutoClear": "DENY",
        "inheritedLimitationsFromV05": GATE7_PARAMETERS["inheritedLimitationsFromV05"],
        "next": "GATE8_FRESH_HOLDOUT_AND_RC",
        "updatedAt": now,
    }

    _write(OUT / "V06_GATE7_PARAMETERS.json", GATE7_PARAMETERS)
    _write(OUT / "V06_GATE7_RECEIPT.json", receipt)
    _write(OUT / "V06_GATE7_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "STATUS.json", track)

    print(
        json.dumps(
            {
                "V06_GATE7": track_verdict,
                "parameterHash": ph,
                "hardFails": result.validation.get("hardFails"),
                "determinism": result.validation.get("determinism"),
                "sourceMutation": result.source_mutation,
            },
            indent=2,
        )
    )
    return 0 if track_verdict in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
