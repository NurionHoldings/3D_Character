#!/usr/bin/env python3
"""Calibrate jake_cc_profile_v1 from RIG-02C pose extract (profile data only)."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
PROFILE = ROOT / "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json"
EXTRACT = ROOT / (
    "fast_track/working/meshy_silver_starlight/evidence/rig02c_fixtures/jake_cc_pose_extract.json"
)

_S2 = math.sqrt(2.0) / 2.0
Q_IMPORT_RX_NEG90 = [_S2, -_S2, 0.0, 0.0]


def main() -> int:
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    scale = extract["armatureWorldScale"]
    unit = float(scale[0])
    if abs(unit - scale[1]) > 1e-9 or abs(unit - scale[2]) > 1e-9:
        raise SystemExit(f"non-uniform scale: {scale}")

    rest = extract["restLocals"]
    donor_bind = {name: rest[name]["rotation_wxyz"] for name in rest}

    for req in ("CC_Base_NeckTwist01", "CC_Base_NeckTwist02", "CC_Base_Pelvis"):
        if req not in donor_bind:
            raise SystemExit(f"missing bind {req}")

    parents = extract["neckCollapseParents"]
    if parents["CC_Base_NeckTwist01"] != "CC_Base_Spine02":
        raise SystemExit(f"NeckTwist01 parent unexpected: {parents}")
    if parents["CC_Base_NeckTwist02"] != "CC_Base_NeckTwist01":
        raise SystemExit(f"NeckTwist02 parent unexpected: {parents}")

    profile["unit_scale"] = unit
    profile["q_import"] = Q_IMPORT_RX_NEG90
    profile["space_basis"] = {
        "right": "+X",
        "up": "+Z",
        "forward": "-Y",
        "handedness": "right-handed",
        "note": "Jake FBX import space (RIG-01C/02C); remapped via Q_import=Rx(-90°)",
    }
    profile["rest_pose"] = {
        "class_name": "T_POSE_LIKE",
        "notes": (
            f"dominantUp={extract['restPoseProbe']['dominantUpAxis']}; "
            f"leftArmAbductionFromDownDeg={extract['restPoseProbe']['leftArmAbductionFromDownDeg']}"
        ),
    }
    profile["donor_bind_local_by_donor"] = donor_bind
    core_keys = list(profile["canonical_bind_local"].keys())
    profile["canonical_bind_local"] = {b: [1.0, 0.0, 0.0, 0.0] for b in core_keys}
    profile["q_basis_b"] = {b: [1.0, 0.0, 0.0, 0.0] for b in core_keys}
    profile["allow_identity_q_basis_placeholders"] = True
    twists = [
        n
        for n in extract.get("twistBonesPresent", [])
        if n not in ("CC_Base_NeckTwist01", "CC_Base_NeckTwist02")
    ]
    profile["twist_policy"] = {
        "role": "DISTRIBUTION_TARGET_NOT_MOTION_SOURCE",
        "donor_twist_bones": sorted(
            set(profile.get("twist_policy", {}).get("donor_twist_bones", []) + twists)
        ),
        "allow_as_core_source": False,
    }
    profile["notes"] = [
        "RIG-02C calibrated from Jake.fbx extract — donor/reference only (product_use=false)",
        "Q_import = Rx(-90°) maps donor +Z-up → Canonical +Y-up",
        "Q_basis_b = IDENTITY (world remap via Q_import; per-bone diversity deferred if needed)",
        "CC_Base_BoneRoot → NURION_root; CC_Base_Hip → NURION_pelvis; CC_Base_Pelvis = intermediary",
        "Waist→spine01, Spine01→spine02, Spine02→chest",
        "NeckTwist01×02 COLLAPSE_COMPOUND → NURION_neck (Compose rest-removed deltas, §16)",
        "twist/deform bones DENY as Canonical Core sources",
    ]
    profile["calibration"] = {
        "stage": "NURION-RIG-02C",
        "sourceExtract": str(EXTRACT),
        "clipId": extract["clipId"],
        "q_import_construction": "Rx(-90deg) WXYZ",
        "dominantUpObserved": extract["restPoseProbe"]["dominantUpAxis"],
        "neckCollapseCommonParent": "CC_Base_Spine02",
    }
    profile["collapse_chains"] = [
        {
            "canonical_bone": "NURION_neck",
            "donor_bones_in_order": ["CC_Base_NeckTwist01", "CC_Base_NeckTwist02"],
            "common_parent_donor": "CC_Base_Spine02",
        }
    ]
    profile["intermediary_bones"] = ["CC_Base_Pelvis"]
    # P1a: donor hierarchy for collapse load-bearing validation
    hier = extract.get("hierarchyParent") or {}
    profile["donor_parent_of"] = {k: hier[k] for k in hier}

    PROFILE.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(PROFILE),
                "unit_scale": unit,
                "q_import": Q_IMPORT_RX_NEG90,
                "donor_bind_count": len(donor_bind),
                "twist_count": len(profile["twist_policy"]["donor_twist_bones"]),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
