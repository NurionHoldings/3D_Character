#!/usr/bin/env python3
"""
Calibrate mjn_legacy_profile_v1 from RIG-02B pose extract (profile data only — no engine fork).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
PROFILE = ROOT / "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json"
IDLE_EXTRACT = ROOT / (
    "fast_track/working/meshy_silver_starlight/evidence/rig02b_fixtures/mjn_idle_15_pose_extract.json"
)

# Donor import space observed +Z-up (Blender) → Canonical +Y-up: R_x(-90°)
_S2 = math.sqrt(2.0) / 2.0
Q_IMPORT_RX_NEG90 = [_S2, -_S2, 0.0, 0.0]


def main() -> int:
    extract = json.loads(IDLE_EXTRACT.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    scale = extract["armatureWorldScale"]
    # uniform 0.01 → meters
    unit = float(scale[0])
    if abs(unit - scale[1]) > 1e-9 or abs(unit - scale[2]) > 1e-9:
        raise SystemExit(f"non-uniform armature scale: {scale}")

    rest = extract["restLocals"]
    donor_bind = {name: rest[name]["rotation_wxyz"] for name in rest}
    # Virtual root has no donor bone — omit from donor_bind

    profile["unit_scale"] = unit
    profile["q_import"] = Q_IMPORT_RX_NEG90
    profile["space_basis"] = {
        "right": "+X",
        "up": "+Z",
        "forward": "-Y",
        "handedness": "right-handed",
        "note": "Observed after Blender import of MJN Idle GLB; remapped to Canonical via Q_import=Rx(-90°)",
    }
    profile["rest_pose"] = {
        "class_name": "A_POSE_LIKE",
        "notes": (
            f"Idle rest matrix_basis≈I; hips→head dominant {extract['restPoseProbe']['dominantUpAxis']}; "
            f"leftArmAbductionFromDownDeg={extract['restPoseProbe']['leftArmAbductionFromDownDeg']}"
        ),
    }
    profile["donor_bind_local_by_donor"] = donor_bind
    # Canonical bind remains Identity instrument (Canonical A-pose SoT bind not yet authored as numeric asset)
    core_keys = list(profile["canonical_bind_local"].keys())
    profile["canonical_bind_local"] = {b: [1.0, 0.0, 0.0, 0.0] for b in core_keys}
    profile["q_basis_b"] = {b: [1.0, 0.0, 0.0, 0.0] for b in core_keys}
    profile["allow_identity_q_basis_placeholders"] = True
    profile["notes"] = [
        "RIG-02B calibrated from Idle_15_withSkin_WORKING_BASELINE.glb extract",
        "Q_import = Rx(-90°) maps donor +Z-up import space → Canonical +Y-up (§1)",
        "Q_basis_b = IDENTITY per Core bone (bone-local +Y aim after Blender import; world remap is Q_import-only)",
        "donor_bind_local from cleared pose matrix_basis (rest channels ≈ identity)",
        "NURION_root = VIRTUAL_ROOT (no MJN donor bone); Hips → NURION_pelvis only",
        "Helpers head_end/headfront HELPER_DROP",
        "Spine02→spine01, Spine01→spine02, Spine→chest (MJN naming inversion)",
    ]
    profile["calibration"] = {
        "stage": "NURION-RIG-02B",
        "sourceExtract": str(IDLE_EXTRACT),
        "clipId": extract["clipId"],
        "q_import_construction": "Rx(-90deg) WXYZ",
        "unit_scale_source": "armature.matrix_world.to_scale()",
        "dominantUpObserved": extract["restPoseProbe"]["dominantUpAxis"],
    }

    PROFILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(PROFILE),
                "unit_scale": unit,
                "q_import": Q_IMPORT_RX_NEG90,
                "donor_bind_count": len(donor_bind),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
