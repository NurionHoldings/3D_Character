#!/usr/bin/env python3
"""Build ADAPT-05 fixtures — reuse ADAPT-04 GLBs + qualification scenario flags."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_ADAPT05_REPO_ROOT", os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker")))
sys.path.insert(0, str(ROOT))

OUT = Path(os.environ.get("NURION_ADAPT05_FIXTURE_DIR", str(ROOT / "fast_track/adaptation/fixtures_adapt05")))
# Always read ADAPT-04 GLBs from their canonical fixture dir (not the ADAPT-05 OUT dir)
SRC04 = ROOT / "fast_track/adaptation/fixtures_adapt04"


SCENARIOS = {
    "fully_qualified_augmented": {"asset": "body_minimal_face.glb", "force": {}},
    "no_augmentation_required": {"asset": "body_minimal_face.glb", "force": {"noAugmentationRequired": True}},
    "malformed_candidate": {"asset": "body_minimal_face.glb", "force": {"malformedCandidate": True}},
    "candidate_sha_mismatch": {"asset": "body_minimal_face.glb", "force": {"candidateShaMismatch": True}},
    "root_pelvis_violation": {"asset": "body_minimal_face.glb", "force": {"rootPelvisViolation": True}},
    "body_hierarchy_mismatch": {"asset": "body_minimal_face.glb", "force": {"bodyHierarchyMismatch": True}},
    "face_attachment_mismatch": {"asset": "body_minimal_face.glb", "force": {"faceAttachmentMismatch": True}},
    "competing_face_root": {"asset": "body_minimal_face.glb", "force": {"competingFaceRoot": True}},
    "left_right_eye_inversion": {"asset": "body_minimal_face.glb", "force": {"leftRightEyeInversion": True}},
    "missing_blink": {"asset": "body_minimal_face.glb", "force": {"missingBlink": True}},
    "missing_required_expression": {"asset": "expression_mapping_required.glb", "force": {"missingRequiredExpression": True}},
    "missing_jaw_mouth": {"asset": "talking_augmentation_required.glb", "force": {"missingJawMouth": True}},
    "talking_incompatible": {"asset": "talking_augmentation_required.glb", "force": {"talkingIncompatible": True}},
    "canonical_motion_incompatible": {"asset": "body_minimal_face.glb", "force": {"canonicalMotionIncompatible": True}},
    "face_body_coplay_failure": {"asset": "body_minimal_face.glb", "force": {"faceBodyCoplayFailure": True}},
    "runtime_state_incompatible": {"asset": "body_minimal_face.glb", "force": {"runtimeStateIncompatible": True}},
    "behavior_mapping_incompatible": {"asset": "body_minimal_face.glb", "force": {"behaviorMappingIncompatible": True}},
    "unauthorized_candidate_mutation": {"asset": "body_minimal_face.glb", "force": {"unauthorizedCandidateMutation": True}},
    "upstream_pin_mismatch": {"asset": "body_minimal_face.glb", "force": {"upstreamPinMismatch": True}},
    "adapt04_provenance_mismatch": {"asset": "body_minimal_face.glb", "force": {"adapt04ProvenanceMismatch": True}},
    "manual_review_required": {"asset": "body_minimal_face.glb", "force": {"manualReviewRequired": True}},
    "meshy_style_augmented": {"asset": "meshy_style.glb", "force": {}},
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    # Ensure ADAPT-04 fixtures exist in canonical location
    os.environ["NURION_ADAPT04_FIXTURE_DIR"] = str(SRC04)
    os.environ.setdefault("NURION_ADAPT04_REPO_ROOT", str(ROOT))
    from tools.build_adapt04_fixtures import main as build04

    build04()

    OUT.mkdir(parents=True, exist_ok=True)
    assets = [
        "body_minimal_face.glb",
        "meshy_style.glb",
        "rich_facial_morphs.glb",
        "talking_augmentation_required.glb",
        "expression_mapping_required.glb",
    ]
    copied = []
    for name in assets:
        src = SRC04 / name
        if src.is_file():
            dst = OUT / name
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
            copied.append({"name": name, "sha256": sha256_file(dst)})

    flags_path = OUT / "SCENARIO_FLAGS.json"
    flags = {"schema": "NURION_ADAPT05_SCENARIO_FLAGS_V1", "scenarios": SCENARIOS}
    flags_path.write_text(json.dumps(flags, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "schema": "NURION_ADAPT05_FIXTURE_MANIFEST_V1",
        "assets": copied,
        "scenarioCount": len(SCENARIOS),
        "scenarioFlagsSha256": sha256_file(flags_path),
    }
    (OUT / "FIXTURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "count": len(copied), "scenarios": len(SCENARIOS)}, indent=2))


if __name__ == "__main__":
    main()
