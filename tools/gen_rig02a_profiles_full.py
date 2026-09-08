#!/usr/bin/env python3
"""Enrich/regenerate RIG-02A profiles including Canonical Identity."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
OUT = SEM / "retarget_profiles"

ROOT_POLICY = {
    "bone": "NURION_root",
    "owns": ["world_locomotion", "global_translation", "global_heading", "character_placement"],
    "never_merge_with": "NURION_pelvis",
}
PELVIS_POLICY = {
    "bone": "NURION_pelvis",
    "owns": ["body_com", "hip_sway", "vertical_bounce", "local_pelvic_rotation"],
    "never_merge_with": "NURION_root",
}
SPACE_CANONICAL = {"right": "+X", "up": "+Y", "forward": "+Z", "handedness": "right-handed"}


def enrich(path: Path, extra: dict) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "q_basis_by_canonical" in data and "q_basis_b" not in data:
        data["q_basis_b"] = data.pop("q_basis_by_canonical")
    if "bone_maps" in data and "bone_mapping" not in data:
        data["bone_mapping"] = data.pop("bone_maps")
    if "intermediaries" in data and "intermediary_bones" not in data:
        data["intermediary_bones"] = data.pop("intermediaries")
    if "unit_scale_to_meters" in data and "unit_scale" not in data:
        data["unit_scale"] = data.pop("unit_scale_to_meters")
    twists = data.pop("twist_donor_bones", None)
    if twists is not None and "twist_policy" not in data:
        data["twist_policy"] = {
            "role": "DISTRIBUTION_TARGET_NOT_MOTION_SOURCE",
            "donor_twist_bones": twists,
            "allow_as_core_source": False,
        }
    data.update(extra)
    data.setdefault("space_basis", SPACE_CANONICAL)
    data.setdefault("root_policy", ROOT_POLICY)
    data.setdefault("pelvis_policy", PELVIS_POLICY)
    data.setdefault(
        "rest_pose",
        {"class_name": data.get("rest_pose_class", "UNKNOWN"), "notes": ""},
    )
    data["allow_identity_q_basis_placeholders"] = True
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    subprocess.check_call([sys.executable, str(ROOT / "tools/gen_rig02a_donor_profiles.py")])
    spec = json.loads((SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1.json").read_text(encoding="utf-8"))
    core = spec["tiers"]["BODY_CORE_V1"]["bones"]
    ident = [1.0, 0.0, 0.0, 0.0]
    identity = {
        "schema": "NURION_DONOR_SKELETON_PROFILE_V1",
        "profile_id": "canonical_identity_v1",
        "display_name": "NURION Canonical Identity",
        "space_basis": SPACE_CANONICAL,
        "unit_scale": 1.0,
        "rest_pose": {"class_name": "IDENTITY", "notes": "Engine self-instrument for 02A/02D"},
        "bone_mapping": [{"donor_bone": b, "canonical_bone": b, "role": "IDENTITY"} for b in core],
        "q_import": ident,
        "q_basis_b": {b: ident for b in core},
        "root_policy": ROOT_POLICY,
        "pelvis_policy": PELVIS_POLICY,
        "intermediary_bones": [],
        "collapse_chains": [],
        "twist_policy": {
            "role": "DISTRIBUTION_TARGET_NOT_MOTION_SOURCE",
            "donor_twist_bones": [],
            "allow_as_core_source": False,
        },
        "donor_bind_local_by_donor": {b: ident for b in core},
        "canonical_bind_local": {b: ident for b in core},
        "helper_drop": [],
        "allow_identity_q_basis_placeholders": True,
        "notes": ["Canonical→Engine→Canonical expected error ≈ 0"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "canonical_identity_profile_v1.json").write_text(
        json.dumps(identity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    enrich(
        OUT / "mjn_legacy_profile_v1.json",
        {
            "space_basis": SPACE_CANONICAL,
            "root_policy": ROOT_POLICY,
            "pelvis_policy": PELVIS_POLICY,
            "rest_pose": {"class_name": "UNKNOWN_PENDING_02B_CALIBRATION", "notes": ""},
        },
    )
    enrich(
        OUT / "jake_cc_profile_v1.json",
        {
            "space_basis": {
                "right": "+X",
                "up": "+Z",
                "forward": "-Y",
                "handedness": "right-handed",
                "note": "Jake import-space from RIG-01C — Q_import calibrates in 02C",
            },
            "root_policy": ROOT_POLICY,
            "pelvis_policy": PELVIS_POLICY,
            "rest_pose": {"class_name": "T_POSE_LIKE_PENDING_02C_CALIBRATION", "notes": ""},
        },
    )
    print(json.dumps({"out": str(OUT)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
