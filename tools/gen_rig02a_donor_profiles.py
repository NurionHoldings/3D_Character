#!/usr/bin/env python3
"""Generate RIG-02A donor profile JSON from LOCKED BODY Canonical mapping."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
OUT = SEM / "retarget_profiles"


def main() -> int:
    spec = json.loads((SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1.json").read_text(encoding="utf-8"))
    core = spec["tiers"]["BODY_CORE_V1"]["bones"]
    ident = [1.0, 0.0, 0.0, 0.0]
    c_bind = {b: ident for b in core}
    q_basis = {b: ident for b in core}

    mjn_maps = [
        {"donor_bone": "__virtual_root__", "canonical_bone": "NURION_root", "role": "VIRTUAL_ROOT"},
        {"donor_bone": "Hips", "canonical_bone": "NURION_pelvis", "role": "DIRECT_SEMANTIC_FORK"},
        {"donor_bone": "Spine02", "canonical_bone": "NURION_spine01", "role": "DIRECT"},
        {"donor_bone": "Spine01", "canonical_bone": "NURION_spine02", "role": "DIRECT"},
        {"donor_bone": "Spine", "canonical_bone": "NURION_chest", "role": "DIRECT"},
        {"donor_bone": "neck", "canonical_bone": "NURION_neck", "role": "DIRECT"},
        {"donor_bone": "Head", "canonical_bone": "NURION_head", "role": "DIRECT_FACE_ATTACHMENT"},
        {"donor_bone": "LeftShoulder", "canonical_bone": "NURION_clavicle_L", "role": "DIRECT"},
        {"donor_bone": "LeftArm", "canonical_bone": "NURION_upperArm_L", "role": "DIRECT"},
        {"donor_bone": "LeftForeArm", "canonical_bone": "NURION_lowerArm_L", "role": "DIRECT"},
        {"donor_bone": "LeftHand", "canonical_bone": "NURION_hand_L", "role": "DIRECT"},
        {"donor_bone": "RightShoulder", "canonical_bone": "NURION_clavicle_R", "role": "DIRECT"},
        {"donor_bone": "RightArm", "canonical_bone": "NURION_upperArm_R", "role": "DIRECT"},
        {"donor_bone": "RightForeArm", "canonical_bone": "NURION_lowerArm_R", "role": "DIRECT"},
        {"donor_bone": "RightHand", "canonical_bone": "NURION_hand_R", "role": "DIRECT"},
        {"donor_bone": "LeftUpLeg", "canonical_bone": "NURION_thigh_L", "role": "DIRECT"},
        {"donor_bone": "LeftLeg", "canonical_bone": "NURION_calf_L", "role": "DIRECT"},
        {"donor_bone": "LeftFoot", "canonical_bone": "NURION_foot_L", "role": "DIRECT"},
        {"donor_bone": "LeftToeBase", "canonical_bone": "NURION_toe_L", "role": "DIRECT"},
        {"donor_bone": "RightUpLeg", "canonical_bone": "NURION_thigh_R", "role": "DIRECT"},
        {"donor_bone": "RightLeg", "canonical_bone": "NURION_calf_R", "role": "DIRECT"},
        {"donor_bone": "RightFoot", "canonical_bone": "NURION_foot_R", "role": "DIRECT"},
        {"donor_bone": "RightToeBase", "canonical_bone": "NURION_toe_R", "role": "DIRECT"},
        {"donor_bone": "head_end", "canonical_bone": None, "role": "HELPER_DROP"},
        {"donor_bone": "headfront", "canonical_bone": None, "role": "HELPER_DROP"},
    ]
    mjn_donor_bind = {
        e["donor_bone"]: ident for e in mjn_maps if e["role"] not in ("HELPER_DROP", "VIRTUAL_ROOT")
    }
    mjn = {
        "schema": "NURION_DONOR_SKELETON_PROFILE_V1",
        "profile_id": "mjn_legacy_v1",
        "display_name": "MJN Legacy 24-joint",
        "unit_scale_to_meters": 1.0,
        "q_import": ident,
        "q_basis_by_canonical": q_basis,
        "canonical_bind_local": c_bind,
        "donor_bind_local_by_donor": mjn_donor_bind,
        "bone_maps": mjn_maps,
        "collapse_chains": [],
        "intermediaries": [],
        "helper_drop": ["head_end", "headfront"],
        "twist_donor_bones": [],
        "rest_pose_class": "UNKNOWN_PENDING_02B_CALIBRATION",
        "notes": [
            "RIG-02A contract profile — calibrate Q_import/Q_basis_b/bind in RIG-02B",
            "NURION_root is VIRTUAL (no MJN donor bone)",
        ],
    }

    allowed = {
        "DIRECT",
        "DIRECT_SEMANTIC_FORK",
        "DIRECT_FACE_ATTACHMENT",
        "DIRECT_VIA_INTERMEDIARY",
        "COLLAPSE_COMPOUND",
        "VIRTUAL_ROOT",
        "ADAPTER_INTERMEDIARY",
        "HELPER_DROP",
    }
    jake_maps = []
    for donor, row in spec["jakeToNurionAccepted"].items():
        nurion = row.get("nurion")
        role = row["role"]
        if role == "ADAPTER_INTERMEDIARY":
            jake_maps.append({"donor_bone": donor, "canonical_bone": None, "role": "ADAPTER_INTERMEDIARY"})
        elif str(role).startswith("COLLAPSE"):
            jake_maps.append({"donor_bone": donor, "canonical_bone": nurion, "role": "COLLAPSE_COMPOUND"})
        elif role == "DIRECT_VIA_INTERMEDIARY_PELVIS":
            jake_maps.append(
                {"donor_bone": donor, "canonical_bone": nurion, "role": "DIRECT_VIA_INTERMEDIARY"}
            )
        else:
            r = role if role in allowed else "DIRECT"
            jake_maps.append({"donor_bone": donor, "canonical_bone": nurion, "role": r})

    jake_donor_bind = {e["donor_bone"]: ident for e in jake_maps}
    twists = [
        "CC_Base_L_UpperarmTwist01",
        "CC_Base_L_UpperarmTwist02",
        "CC_Base_L_ForearmTwist01",
        "CC_Base_L_ForearmTwist02",
        "CC_Base_R_UpperarmTwist01",
        "CC_Base_R_UpperarmTwist02",
        "CC_Base_R_ForearmTwist01",
        "CC_Base_R_ForearmTwist02",
        "CC_Base_L_ThighTwist01",
        "CC_Base_L_ThighTwist02",
        "CC_Base_R_ThighTwist01",
        "CC_Base_R_ThighTwist02",
        "CC_Base_L_CalfTwist01",
        "CC_Base_L_CalfTwist02",
        "CC_Base_R_CalfTwist01",
        "CC_Base_R_CalfTwist02",
    ]
    jake = {
        "schema": "NURION_DONOR_SKELETON_PROFILE_V1",
        "profile_id": "jake_cc_v1",
        "display_name": "Jake CC_Base donor",
        "unit_scale_to_meters": 0.01,
        "q_import": ident,
        "q_basis_by_canonical": q_basis,
        "canonical_bind_local": c_bind,
        "donor_bind_local_by_donor": jake_donor_bind,
        "bone_maps": jake_maps,
        "collapse_chains": [
            {
                "canonical_bone": "NURION_neck",
                "donor_bones_in_order": ["CC_Base_NeckTwist01", "CC_Base_NeckTwist02"],
                "common_parent_donor": "CC_Base_Spine02",
            }
        ],
        "intermediaries": ["CC_Base_Pelvis"],
        "helper_drop": [],
        "twist_donor_bones": twists,
        "rest_pose_class": "T_POSE_LIKE_PENDING_02C_CALIBRATION",
        "notes": [
            "RIG-02A contract profile — calibrate Q_import/Q_basis_b from forensic in RIG-02C",
            "CC_Base_Pelvis intermediary must never appear in Canonical pose keys",
            "NeckTwist01x02 collapse via engine section 16",
            "twist bones are distribution targets only",
        ],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mjn_legacy_profile_v1.json").write_text(
        json.dumps(mjn, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT / "jake_cc_profile_v1.json").write_text(
        json.dumps(jake, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(OUT), "jake_maps": len(jake_maps)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
