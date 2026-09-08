"""
Run Gate 1 — Universal Face Basis on a character FBX (development: Tennis).

Usage:
  blender --background --python tools/blender_gate1_universal_face_basis.py -- \\
    --fbx PATH [--label tennis] [--out-dir dist/v0.3/universal_eye/gate1]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.3" / "universal_eye" / "gate1"
DEFAULT_TENNIS = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", default=str(DEFAULT_TENNIS))
    p.add_argument("--label", default="tennis")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--mesh", default="char1")
    p.add_argument("--no-render", action="store_true")
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


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    out_dir = Path(args.out_dir)
    if not fbx.exists():
        raise FileNotFoundError(fbx)

    sys.path.insert(0, str(ROOT))
    from nurion_universal_eye.gate1.face_basis_validator import validate_face_basis
    from nurion_universal_eye.gate1.multiview_evidence import render_multiview_evidence
    from nurion_universal_eye.gate1.universal_face_basis import build_universal_face_basis

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    # Determinism: 3 independent builds
    profiles = []
    bases = []
    for _ in range(3):
        b = build_universal_face_basis(mesh_name=args.mesh)
        bases.append(b)
        profiles.append(b.to_profile())

    basis = bases[0]
    evidence_dir = out_dir / "evidence" / args.label
    evidence = render_multiview_evidence(
        basis,
        evidence_dir,
        do_render=not args.no_render,
    )
    report = validate_face_basis(
        basis,
        evidence=evidence,
        determinism_profiles=profiles,
    )

    profile_path = out_dir / "UNIVERSAL_FACE_BASIS_PROFILE.json"
    report_path = out_dir / "GATE1_VALIDATION_REPORT.json"
    status_path = out_dir / "GATE1_STATUS.json"
    evidence_path = out_dir / "GATE1_MULTIVIEW_EVIDENCE.json"

    profile = profiles[0]
    profile["assetRole"] = "DEVELOPMENT"
    profile["characterId"] = args.label
    profile["fbx"] = str(fbx).replace("\\", "/")
    profile["fbxSha256"] = _sha(fbx)
    profile["createdAt"] = datetime.now(timezone.utc).isoformat()

    status = {
        "schema": "NURION_GATE1_STATUS",
        "track": "NURION Universal Eye Calibration Alpha3",
        "gate": 1,
        "name": "UNIVERSAL_FACE_BASIS",
        "DESIGN_RESET": True,
        "IMPLEMENTATION": "COMPLETE_CANDIDATE" if report["verdict"] == "PASS" else "IN_PROGRESS",
        "GATE1": report["verdict"],
        "NEXT_DECISION": report["nextDecision"],
        "SEALED": False,
        "manualGtUsed": False,
        "visualEyeGenerated": False,
        "asset": args.label,
        "fbxSha256": profile["fbxSha256"],
        "profileSha256": report["profileSha256"],
        "gates": report["gates"],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "profile": str(profile_path if not profile_path.is_relative_to(ROOT) else profile_path.relative_to(ROOT)).replace("\\", "/"),
            "report": str(report_path if not report_path.is_relative_to(ROOT) else report_path.relative_to(ROOT)).replace("\\", "/"),
            "evidence": str(evidence_path if not evidence_path.is_relative_to(ROOT) else evidence_path.relative_to(ROOT)).replace("\\", "/"),
        },
        "forbiddenUntilPass": [
            "EyePlane",
            "convex eyeball",
            "gaze",
            "blink",
            "expression matching",
        ],
    }

    _write(profile_path, profile)
    _write(report_path, report)
    _write(evidence_path, evidence)
    _write(status_path, status)

    # Mirror root STATUS.json for track-level state
    root_status = {
        "track": "NURION Universal Eye Calibration Alpha3",
        "designReset": True,
        "legacyR1ToR4": "SUPERSEDED",
        "implementation": "IN_PROGRESS" if report["verdict"] != "PASS" else "GATE1_PASS_CANDIDATE",
        "gate1": report["verdict"],
        "nextGate": "FLAT_EYE_PLACEMENT" if report["verdict"] == "PASS" else "UNIVERSAL_FACE_BASIS",
        "nextDecision": report["nextDecision"],
        "sealed": False,
        "manualGtUsed": False,
        "visualEyeGenerated": False,
    }
    _write(ROOT / "STATUS.json", root_status)

    print(json.dumps({"verdict": report["verdict"], "gates": report["gates"], "out": str(out_dir)}, indent=2))
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
