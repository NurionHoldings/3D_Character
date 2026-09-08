#!/usr/bin/env python3
"""RIG-02A contract-closure tests (awaiting human audit — do not declare PASS here)."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.body_retarget_engine import BodyRetargetEngine, BoneLocal, PoseFrame
from fast_track.runtime.donor_skeleton_profile import (
    build_canonical_identity_profile,
    load_profile,
    profile_from_dict,
)
from fast_track.runtime.retarget_contract_validator import (
    RetargetContractError,
    assert_profile_valid,
    validate_profile,
)
from fast_track.runtime.retarget.protected import assert_protected_sot_unchanged
from fast_track.runtime.retarget.quat import IDENTITY

PROFILES = ROOT / "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles"


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_protected() -> None:
    assert_protected_sot_unchanged()


def test_identity_profile_zero_error() -> None:
    eng = BodyRetargetEngine()
    m = eng.identity_self_test(tol=1e-4)
    _ok(m.max_rotation_abs_err <= 1e-4, f"rot err {m.max_rotation_abs_err}")
    _ok(m.max_translation_abs_err <= 1e-4, f"tr err {m.max_translation_abs_err}")
    _ok(m.scale_err == 0.0, "scale err")


def test_reject_global_q_basis() -> None:
    raw = {
        "profile_id": "bad_global",
        "q_basis": [1, 0, 0, 0],
        "bone_mapping": [],
    }
    try:
        profile_from_dict(raw)
        raise AssertionError("expected GLOBAL_Q_BASIS_FORBIDDEN")
    except ValueError as e:
        _ok("GLOBAL_Q_BASIS" in str(e), str(e))


def test_reject_unknown_canonical() -> None:
    p = build_canonical_identity_profile()
    d = p.to_json_dict()
    d["bone_mapping"].append(
        {"donor_bone": "X", "canonical_bone": "NURION_not_a_bone", "role": "DIRECT"}
    )
    # also need q_basis for core only — validator catches unknown
    bad = profile_from_dict(d)
    codes = {i.code for i in validate_profile(bad)}
    _ok("UNKNOWN_CANONICAL_BONE" in codes, codes)


def test_reject_duplicate_mapping() -> None:
    p = build_canonical_identity_profile()
    d = p.to_json_dict()
    d["bone_mapping"].append(
        {"donor_bone": "dup", "canonical_bone": "NURION_head", "role": "DIRECT"}
    )
    bad = profile_from_dict(d)
    codes = {i.code for i in validate_profile(bad)}
    _ok("DUPLICATE_CANONICAL_MAPPING" in codes, codes)


def test_reject_root_pelvis_ownership_collision() -> None:
    p = build_canonical_identity_profile()
    d = p.to_json_dict()
    d["root_policy"]["owns"].append("body_com")
    d["pelvis_policy"]["owns"].append("body_com")
    bad = profile_from_dict(d)
    codes = {i.code for i in validate_profile(bad)}
    _ok("ROOT_PELVIS_OWNERSHIP_COLLISION" in codes, codes)


def test_reject_undeclared_collapse() -> None:
    p = build_canonical_identity_profile()
    d = p.to_json_dict()
    d["bone_mapping"].append(
        {"donor_bone": "n1", "canonical_bone": "NURION_neck", "role": "COLLAPSE_COMPOUND"}
    )
    d["bone_mapping"].append(
        {"donor_bone": "n2", "canonical_bone": "NURION_neck", "role": "COLLAPSE_COMPOUND"}
    )
    # no collapse_chains
    bad = profile_from_dict(d)
    codes = {i.code for i in validate_profile(bad)}
    _ok("UNDECLARED_COLLAPSE" in codes or "DUPLICATE_CANONICAL_MAPPING" in codes, codes)


def test_reject_intermediary_leakage_mapping() -> None:
    p = build_canonical_identity_profile()
    d = p.to_json_dict()
    d["intermediary_bones"] = ["DONOR_PELVIS_X"]
    d["bone_mapping"].append(
        {"donor_bone": "DONOR_PELVIS_X", "canonical_bone": "NURION_pelvis", "role": "DIRECT"}
    )
    bad = profile_from_dict(d)
    codes = {i.code for i in validate_profile(bad)}
    _ok("INTERMEDIARY_LEAKAGE" in codes, codes)


def test_reject_twist_as_source() -> None:
    p = build_canonical_identity_profile()
    d = p.to_json_dict()
    d["twist_policy"] = {
        "role": "DISTRIBUTION_TARGET_NOT_MOTION_SOURCE",
        "donor_twist_bones": ["TWIST_A"],
        "allow_as_core_source": False,
    }
    d["bone_mapping"].append(
        {"donor_bone": "TWIST_A", "canonical_bone": "NURION_upperArm_L", "role": "DIRECT"}
    )
    bad = profile_from_dict(d)
    codes = {i.code for i in validate_profile(bad)}
    _ok("TWIST_AS_SOURCE" in codes, codes)


def test_reject_missing_q_basis_b_member() -> None:
    p = build_canonical_identity_profile()
    d = p.to_json_dict()
    # Incomplete Core keyset must FAIL at parser (no identity auto-fill)
    d["q_basis_b"] = {"NURION_root": [1.0, 0.0, 0.0, 0.0]}
    try:
        profile_from_dict(d)
        raise AssertionError("expected Q_BASIS_B_INCOMPLETE")
    except ValueError as e:
        _ok("Q_BASIS_B_INCOMPLETE" in str(e) or "Q_BASIS_B_REQUIRED" in str(e), str(e))


def test_reject_non_unit_quaternion_through_parser() -> None:
    """NON_UNIT_QUATERNION must FAIL on real JSON/parser path — not via post-load hack."""
    p = build_canonical_identity_profile()
    d = p.to_json_dict()
    d["q_import"] = [2.0, 0.0, 0.0, 0.0]
    try:
        profile_from_dict(d)
        raise AssertionError("expected NON_UNIT_QUATERNION via parser")
    except ValueError as e:
        _ok("NON_UNIT_QUATERNION" in str(e), str(e))

    d2 = p.to_json_dict()
    d2["q_basis_b"] = dict(d2["q_basis_b"])
    d2["q_basis_b"]["NURION_root"] = [2.0, 0.0, 0.0, 0.0]
    try:
        profile_from_dict(d2)
        raise AssertionError("expected NON_UNIT_QUATERNION on q_basis_b via parser")
    except ValueError as e:
        _ok("NON_UNIT_QUATERNION" in str(e), str(e))


def test_deterministic_serialization() -> None:
    p = build_canonical_identity_profile()
    a = p.deterministic_dumps()
    p2 = profile_from_dict(p.to_json_dict())
    _ok(a == p2.deterministic_dumps(), "serialization nondeterministic")


def test_load_mjn_jake_validate() -> None:
    for name in ("mjn_legacy_profile_v1.json", "jake_cc_profile_v1.json", "canonical_identity_profile_v1.json"):
        p = load_profile(PROFILES / name)
        assert_profile_valid(p)


def test_engine_no_donor_literals() -> None:
    """Official body_retarget_engine.py entire source must contain 0 donor-name literals."""
    engine_path = ROOT / "fast_track/runtime/body_retarget_engine.py"
    src = engine_path.read_text(encoding="utf-8")
    forbidden = ("CC_Base", "Hips", "LeftUpLeg", "Mixamo")
    for token in forbidden:
        _ok(token not in src, f"donor literal {token!r} in {engine_path.name}")
    # Internal algorithm module also remains clean
    algo = (ROOT / "fast_track/runtime/retarget/engine.py").read_text(encoding="utf-8")
    for token in forbidden:
        _ok(token not in algo, f"donor literal {token!r} in retarget/engine.py")
    BodyRetargetEngine()  # runtime self-check on algo module still runs


def test_identity_file_matches_builder() -> None:
    file_p = load_profile(PROFILES / "canonical_identity_profile_v1.json")
    assert_profile_valid(file_p)
    eng = BodyRetargetEngine()
    donor = PoseFrame(locals={b: BoneLocal(rotation=IDENTITY) for b in eng.core_bones})
    out = eng.donor_to_canonical(file_p, donor)
    _ok(set(out.locals.keys()) == set(eng.core_bones), "core keys")


def main() -> int:
    tests = [
        test_protected,
        test_identity_profile_zero_error,
        test_reject_global_q_basis,
        test_reject_unknown_canonical,
        test_reject_duplicate_mapping,
        test_reject_root_pelvis_ownership_collision,
        test_reject_undeclared_collapse,
        test_reject_intermediary_leakage_mapping,
        test_reject_twist_as_source,
        test_reject_missing_q_basis_b_member,
        test_reject_non_unit_quaternion_through_parser,
        test_deterministic_serialization,
        test_load_mjn_jake_validate,
        test_engine_no_donor_literals,
        test_identity_file_matches_builder,
    ]
    results = []
    for fn in tests:
        try:
            fn()
            results.append({"test": fn.__name__, "status": "PASS"})
        except Exception as e:
            results.append({"test": fn.__name__, "status": "FAIL", "error": str(e)})
    failed = [r for r in results if r["status"] == "FAIL"]
    summary = {
        "stage": "NURION-RIG-02A_ADAPTER_CONTRACT_CLOSURE",
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }
    out_path = ROOT / "fast_track/working/meshy_silver_starlight/evidence/NURION-RIG-02A_closure_stdout.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "out": str(out_path)}, ensure_ascii=True))
    print({"passed": summary["passed"], "failed": summary["failed"], "results": results})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
