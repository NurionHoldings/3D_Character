"""
v0.6 Gate 5 — Motion Preset isolation (Formal Bow / Idle / Gentleman's Bow).

Usage:
  blender --background --python tools/blender_v06_gate5_motion_preset.py -- \\
    --label ai-aba --gate2-class LIMITED --gate4-action APPLY_LIMITED_BIND \\
    --formal-bow dist/v0.5/gate1/.../Formal_Bow_withSkin.fbx \\
    --idle dist/v0.4/gate8c/.../Idle_15_withSkin.fbx
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.6" / "gate5"
GATE1_HASH = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"
GATE2_HASH = "b5d3c4931d1ef65a64844483e51bb74d6edcfcb9f90de28abe1c47192c85df6e"
GATE3_HASH = "35daa4fce90b00c474abcd08b7c40e313d79bcf7c50710ce8f8120b645bf1604"
GATE4_HASH = "a260ecd6d15502bbb5633e17b6c860955f9307fae25d777db6477c381bad5188"
V03 = ROOT / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
V04 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V05 = ROOT / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip"
V03_SHA = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"
V04_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V05_SHA = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"

DEFAULT_FORMAL = (
    ROOT
    / "dist/v0.5/gate1/ai-aba.bow/_extract/Meshy_AI_Silver_Starlight_Sent_biped"
    / "Meshy_AI_Silver_Starlight_Sent_biped_Animation_Formal_Bow_withSkin.fbx"
)
DEFAULT_IDLE = (
    ROOT
    / "dist/v0.4/gate8c/ai-aba.15/_extract/Meshy_AI_Silver_Starlight_Sent_biped"
    / "Meshy_AI_Silver_Starlight_Sent_biped_Animation_Idle_15_withSkin.fbx"
)


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--gate2-class", required=True, choices=["FULL", "LIMITED", "INELIGIBLE"])
    p.add_argument("--gate4-action", required=True)
    p.add_argument("--formal-bow", default=str(DEFAULT_FORMAL))
    p.add_argument("--idle", default=str(DEFAULT_IDLE))
    p.add_argument("--gentlemans-bow", default="")
    p.add_argument("--lipsync-supported", type=int, default=0)
    p.add_argument("--out-dir", default="")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--empty-scene", action="store_true")
    return p.parse_args(argv)


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


def _resolve(p: str):
    if not p:
        return None
    path = Path(p)
    if not path.is_absolute():
        path = ROOT / path
    return path if path.is_file() else None


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    sys.path.insert(0, str(ROOT))
    from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as g1_hash
    from nurion_v06_unified_runtime.gate2.parameters import parameter_hash as g2_hash
    from nurion_v06_unified_runtime.gate3.parameters import parameter_hash as g3_hash
    from nurion_v06_unified_runtime.gate4.parameters import parameter_hash as g4_hash
    from nurion_v06_unified_runtime.gate5.parameters import GATE5_PARAMETERS, parameter_hash
    from nurion_v06_unified_runtime.gate5.presets import run_gate5_presets

    if g1_hash() != GATE1_HASH or g2_hash() != GATE2_HASH or g3_hash() != GATE3_HASH or g4_hash() != GATE4_HASH:
        raise RuntimeError("Gate1–4 parameter hash mismatch — DENY")

    if args.empty_scene or args.gate2_class == "INELIGIBLE":
        sources = {"Formal_Bow": None, "Idle": None, "Gentlemans_Bow": None}
    else:
        sources = {
            "Formal_Bow": _resolve(args.formal_bow),
            "Idle": _resolve(args.idle),
            "Gentlemans_Bow": _resolve(args.gentlemans_bow),
        }

    result = run_gate5_presets(
        label=args.label,
        preset_sources=sources,
        gate2_classification=args.gate2_class,
        gate4_runtime_action=args.gate4_action,
        lipsync_supported=bool(args.lipsync_supported),
        baseline_hash_ok=_baseline_ok(),
        runs=args.runs,
    )

    _write(out_dir / "GATE5_PROFILE.json", result.profile)
    _write(out_dir / "GATE5_VALIDATION.json", result.validation)

    status = {
        "schema": "NURION_V06_GATE5_ASSET_STATUS",
        "gate": "5",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "MOTION_PRESET",
        "label": args.label,
        "gate2Classification": args.gate2_class,
        "gate4RuntimeAction": args.gate4_action,
        "presetVerdict": result.verdict,
        "runtimeAction": result.runtime_action,
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate1Locked": True,
        "gate2Locked": True,
        "gate3Locked": True,
        "gate4Locked": True,
        "availablePresets": result.validation.get("availablePresets"),
        "unavailablePresets": result.validation.get("unavailablePresets"),
        "lipsyncMode": result.validation.get("lipsyncMode"),
        "sourceMutation": result.source_mutation,
        "manualCorrection": result.manual_correction,
        "assetSpecificTuning": result.asset_specific_tuning,
        "abstainReasons": result.validation.get("abstainReasons"),
        "gates": result.validation.get("gates"),
        "inheritedLimitationsFromV05": GATE5_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "production": "NO-GO",
        "notes": result.notes,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifacts": {"profile": "GATE5_PROFILE.json", "validation": "GATE5_VALIDATION.json"},
        "next": "GATE6_BLENDER_OPERATOR_WORKFLOW",
    }
    _write(out_dir / "V06_GATE5_ASSET_STATUS.json", status)

    print(
        json.dumps(
            {
                "label": args.label,
                "presetVerdict": result.verdict,
                "runtimeAction": result.runtime_action,
                "availablePresets": status["availablePresets"],
                "unavailablePresets": status["unavailablePresets"],
                "sourceMutation": result.source_mutation,
                "parameterHash": parameter_hash(),
                "out": str(out_dir).replace("\\", "/"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result.verdict in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
