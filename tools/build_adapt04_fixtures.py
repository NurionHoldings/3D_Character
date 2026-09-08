#!/usr/bin/env python3
"""Build ADAPT-04 fixtures — reuses ADAPT-03 GLBs + scenario flags."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_ADAPT04_REPO_ROOT") or os.environ.get("NURION_REPO_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))

_OUT = os.environ.get("NURION_ADAPT04_FIXTURE_DIR")
if _OUT:
    OUT = Path(_OUT)
elif Path(__file__).resolve().parents[1].name == "repo":
    OUT = Path(__file__).resolve().parents[2] / "fixtures"
else:
    OUT = ROOT / "fast_track" / "adaptation" / "fixtures_adapt04"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ["NURION_ADAPT03_FIXTURE_DIR"] = str(OUT)
    from tools.build_adapt03_fixtures import main as build_a03

    build_a03()

    scenarios = {
        "no_augmentation_required": {"asset": "rich_facial_morphs.glb", "force": {"noAugmentationRequired": True}},
        "blink_helpers_required": {"asset": "body_minimal_face.glb"},
        "eye_helper_required": {"asset": "eye_adaptation_required.glb"},
        "jaw_helper_required": {"asset": "talking_augmentation_required.glb"},
        "mouth_speech_required": {"asset": "talking_augmentation_required.glb"},
        "viseme_support_required": {"asset": "talking_augmentation_required.glb"},
        "expression_support_required": {"asset": "expression_mapping_required.glb"},
        "multiple_requirements": {"asset": "body_minimal_face.glb"},
        "left_right_eye_ambiguity": {"asset": "rich_facial_morphs.glb", "force": {"leftRightEyeAmbiguity": True}},
        "source_digest_mismatch": {"asset": "rich_facial_morphs.glb", "force": {"sourceDigestMismatch": True}},
        "adapt03_requirement_digest_mismatch": {
            "asset": "body_minimal_face.glb",
            "force": {"adapt03RequirementDigestMismatch": True},
        },
        "unrequested_augmentation": {"asset": "body_minimal_face.glb", "force": {"unrequestedAugmentation": True}},
        "body_hierarchy_mutation": {"asset": "body_minimal_face.glb", "force": {"bodyHierarchyMutation": True}},
        "root_pelvis_collision": {"asset": "rich_facial_morphs.glb", "force": {"rootPelvisCollision": True}},
        "cross_boundary_face_ownership": {"asset": "body_minimal_face.glb", "force": {"crossBoundaryFaceOwnership": True}},
        "unsupported_topology": {"asset": "body_minimal_face.glb", "force": {"unsupportedTopology": True}},
        "manual_review_required": {"asset": "body_minimal_face.glb", "force": {"unsupportedTopology": True}},
        "determinism": {"asset": "body_minimal_face.glb"},
        "meshy_style_minimal": {"asset": "meshy_style.glb"},
        "adapt05_premature": {"asset": "body_minimal_face.glb", "force": {"performAdapt05Qualification": True}},
    }
    (OUT / "SCENARIO_FLAGS.json").write_text(json.dumps(scenarios, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {"schema": "NURION_ADAPT04_FIXTURE_MANIFEST_V1", "fixtures": {}}
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "FIXTURE_MANIFEST.json":
            manifest["fixtures"][p.name] = {"sha256": _sha(p), "byteLength": p.stat().st_size}
    (OUT / "FIXTURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "count": len(manifest["fixtures"])}, indent=2))


if __name__ == "__main__":
    main()
