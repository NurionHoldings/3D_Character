#!/usr/bin/env python3
"""Build ADAPT-06 fixtures — reuse ADAPT-05 GLBs + release scenario flags."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_ADAPT06_REPO_ROOT", os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker")))
sys.path.insert(0, str(ROOT))

OUT = Path(os.environ.get("NURION_ADAPT06_FIXTURE_DIR", str(ROOT / "fast_track/adaptation/fixtures_adapt06")))
SRC05 = ROOT / "fast_track/adaptation/fixtures_adapt05"

SCENARIOS = {
    "canonical_release": {"asset": "body_minimal_face.glb", "force": {}},
    "candidate_sha_mismatch": {"asset": "body_minimal_face.glb", "force": {"candidateShaMismatch": True}},
    "qualification_digest_mismatch": {"asset": "body_minimal_face.glb", "force": {"qualificationDigestMismatch": True}},
    "not_release_eligible": {"asset": "body_minimal_face.glb", "force": {"notReleaseEligible": True}},
    "candidate_repair_attempt": {"asset": "body_minimal_face.glb", "force": {"candidateRepairAttempt": True}},
    "candidate_re_rig_attempt": {"asset": "body_minimal_face.glb", "force": {"candidateReRigAttempt": True}},
    "nurion_v1_modify_attempt": {"asset": "body_minimal_face.glb", "force": {"nurionV1ModifyAttempt": True}},
    "incomplete_consumer_package": {"asset": "body_minimal_face.glb", "force": {"incompleteConsumerPackage": True}},
    "manifest_tamper": {"asset": "body_minimal_face.glb", "force": {"manifestTamper": True}},
    "auto_repair_attempt": {"asset": "body_minimal_face.glb", "force": {"autoRepairAttempt": True}},
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    required = [
        "body_minimal_face.glb",
        "meshy_style.glb",
        "expression_mapping_required.glb",
        "talking_augmentation_required.glb",
    ]
    if all((OUT / name).is_file() for name in required):
        manifest = {"schema": "NURION_ADAPT06_FIXTURE_MANIFEST_V1", "scenarios": SCENARIOS, "source": "PREPACKAGED"}
        (OUT / "ADAPT06_fixture_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({"ok": True, "fixtures": str(OUT), "scenarios": len(SCENARIOS), "prepackaged": True}, indent=2))
        return

    os.environ.setdefault("NURION_ADAPT05_REPO_ROOT", str(ROOT))
    os.environ.setdefault("NURION_ADAPT05_FIXTURE_DIR", str(SRC05))
    from tools.build_adapt05_fixtures import main as build05

    build05()
    OUT.mkdir(parents=True, exist_ok=True)
    for p in SRC05.iterdir():
        if p.is_file():
            dst = OUT / p.name
            if not dst.exists() or dst.stat().st_size != p.stat().st_size:
                shutil.copy2(p, dst)
    manifest = {"schema": "NURION_ADAPT06_FIXTURE_MANIFEST_V1", "scenarios": SCENARIOS}
    (OUT / "ADAPT06_fixture_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": True, "fixtures": str(OUT), "scenarios": len(SCENARIOS)}, indent=2))


if __name__ == "__main__":
    main()
