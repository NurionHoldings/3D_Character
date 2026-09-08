#!/usr/bin/env python3
"""
NURION-RIG-02C — Jake CC → Canonical numerical adapter proof.

Human PASS NOT DECLARED here. Common engine — no Jake forks.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.body_retarget_engine import BodyRetargetEngine, BoneLocal, PoseFrame
from fast_track.runtime.donor_skeleton_profile import load_profile, profile_from_dict
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS, load_core_bones
from fast_track.runtime.retarget.protected import assert_protected_sot_unchanged
from fast_track.runtime.retarget.quat import (
    IDENTITY,
    approx_eq,
    hemisphere,
    inverse,
    multiply,
    normalize,
)
from fast_track.runtime.retarget_contract_validator import (
    assert_profile_valid,
    validate_profile,
)

EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
FIX = EV / "rig02c_fixtures"
PROFILE_PATH = ROOT / (
    "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json"
)
EXTRACT = FIX / "jake_cc_pose_extract.json"
SYNTH = FIX / "jake_cc_synthetic_motion.json"

TOL_ROT = 1e-5
TOL_TR = 1e-6

DONOR_TO_CANON = {
    "CC_Base_BoneRoot": "NURION_root",
    "CC_Base_Hip": "NURION_pelvis",
    "CC_Base_Waist": "NURION_spine01",
    "CC_Base_Spine01": "NURION_spine02",
    "CC_Base_Spine02": "NURION_chest",
    "CC_Base_Head": "NURION_head",
    "CC_Base_L_Clavicle": "NURION_clavicle_L",
    "CC_Base_L_Upperarm": "NURION_upperArm_L",
    "CC_Base_L_Forearm": "NURION_lowerArm_L",
    "CC_Base_L_Hand": "NURION_hand_L",
    "CC_Base_R_Clavicle": "NURION_clavicle_R",
    "CC_Base_R_Upperarm": "NURION_upperArm_R",
    "CC_Base_R_Forearm": "NURION_lowerArm_R",
    "CC_Base_R_Hand": "NURION_hand_R",
    "CC_Base_L_Thigh": "NURION_thigh_L",
    "CC_Base_L_Calf": "NURION_calf_L",
    "CC_Base_L_Foot": "NURION_foot_L",
    "CC_Base_L_ToeBase": "NURION_toe_L",
    "CC_Base_R_Thigh": "NURION_thigh_R",
    "CC_Base_R_Calf": "NURION_calf_R",
    "CC_Base_R_Foot": "NURION_foot_R",
    "CC_Base_R_ToeBase": "NURION_toe_R",
}


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _q(lst):
    return hemisphere(normalize(tuple(float(x) for x in lst)))


def max_rot_err(a, b) -> float:
    a, b = hemisphere(a), hemisphere(b)
    return max(abs(a[i] - b[i]) for i in range(4))


def pose_from_locals(locals_map: dict) -> PoseFrame:
    out = {}
    for name, bl in locals_map.items():
        out[name] = BoneLocal(
            rotation=_q(bl["rotation_wxyz"]),
            translation=tuple(float(x) for x in bl["translation"]),
        )
    return PoseFrame(locals=out)


def expected_rotation_direct(profile, donor_bone: str, canonical_bone: str, anim):
    bind_d = profile.donor_bind_local_by_donor.get(donor_bone, IDENTITY)
    delta = multiply(inverse(bind_d), anim)
    qi = profile.q_import
    delta = multiply(multiply(qi, delta), inverse(qi))
    qb = profile.q_basis_b[canonical_bone]
    delta = multiply(multiply(qb, delta), inverse(qb))
    return multiply(profile.canonical_bind_local[canonical_bone], delta)


def expected_neck_collapse(profile, pose: PoseFrame):
    """§16 independent: path from common_parent_donor, G_i conjugacy, then Qi/Qb/bind_c."""
    ch = profile.collapse_chains[0]
    parent = ch.common_parent_donor
    profile.assert_collapse_chain_hierarchy(ch)
    composed_parent = IDENTITY
    for db in ch.donor_bones_in_order:
        path_i = profile.path_from_common_parent(parent, db)
        bind = profile.donor_bind_local_by_donor.get(db, IDENTITY)
        anim = pose.locals.get(db, BoneLocal()).rotation
        delta_local = multiply(inverse(bind), anim)
        g_from_parent = IDENTITY
        for b in path_i:
            g_from_parent = multiply(
                g_from_parent, profile.donor_bind_local_by_donor.get(b, IDENTITY)
            )
        delta_in_parent = multiply(multiply(g_from_parent, delta_local), inverse(g_from_parent))
        composed_parent = multiply(composed_parent, delta_in_parent)
    qi = profile.q_import
    d = multiply(multiply(qi, composed_parent), inverse(qi))
    qb = profile.q_basis_b["NURION_neck"]
    d = multiply(multiply(qb, d), inverse(qb))
    return multiply(profile.canonical_bind_local["NURION_neck"], d)


def naive_local_delta_product(profile, pose: PoseFrame):
    """Incorrect §16 shortcut: ∏(inv(bind)*anim) without common-parent frame map."""
    composed = IDENTITY
    for db in ("CC_Base_NeckTwist01", "CC_Base_NeckTwist02"):
        bind = profile.donor_bind_local_by_donor.get(db, IDENTITY)
        anim = pose.locals.get(db, BoneLocal()).rotation
        composed = multiply(composed, multiply(inverse(bind), anim))
    qi = profile.q_import
    d = multiply(multiply(qi, composed), inverse(qi))
    qb = profile.q_basis_b["NURION_neck"]
    d = multiply(multiply(qb, d), inverse(qb))
    return multiply(profile.canonical_bind_local["NURION_neck"], d)


def _q_axis_angle(axis: str, deg: float):
    half = math.radians(deg) * 0.5
    c, s = math.cos(half), math.sin(half)
    if axis == "x":
        return hemisphere(normalize((c, s, 0.0, 0.0)))
    if axis == "y":
        return hemisphere(normalize((c, 0.0, s, 0.0)))
    if axis == "z":
        return hemisphere(normalize((c, 0.0, 0.0, s)))
    raise ValueError(axis)


def expected_translation_rx_neg90(t_donor, unit_scale: float):
    """Analytic UNIT then Rx(-90): (x,y,z)→(x,z,-y) — not engine helper."""
    x, y, z = (t_donor[0] * unit_scale, t_donor[1] * unit_scale, t_donor[2] * unit_scale)
    return (x, z, -y)


def _calibrate_and_synth():
    for rel in (
        "tools/calibrate_rig02c_jake_profile.py",
        "tools/gen_rig02c_jake_synthetic_motion.py",
    ):
        path = ROOT / rel
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        mod.main()


def test_protected():
    h = assert_protected_sot_unchanged()
    return {"protectedHashMatch": True, "hashes": h}


def test_profile_valid(profile):
    assert_profile_valid(profile)
    _ok(abs(profile.unit_scale - 0.01) < 1e-12, "unit_scale")
    _ok(not approx_eq(profile.q_import, IDENTITY), "q_import non-I")
    _ok(profile.collapse_chains and profile.collapse_chains[0].canonical_bone == "NURION_neck", "collapse")
    _ok("CC_Base_Pelvis" in profile.intermediary_bones, "pelvis intermediary")
    return {"profile_id": profile.profile_id, "unit_scale": profile.unit_scale}


def test_core23_completeness(eng, out: PoseFrame):
    core = set(load_core_bones())
    _ok(set(out.locals.keys()) == core, f"keys {set(out.locals.keys()) ^ core}")
    return {"coreBones": 23}


def test_hierarchy_semantics(profile):
    mapped = {e.donor_bone: (e.canonical_bone, e.role) for e in profile.bone_mapping}
    checks = [
        ("CC_Base_BoneRoot", "NURION_root", "DIRECT"),
        ("CC_Base_Hip", "NURION_pelvis", "DIRECT_SEMANTIC_FORK"),
        ("CC_Base_Waist", "NURION_spine01", "DIRECT"),
        ("CC_Base_Spine01", "NURION_spine02", "DIRECT"),
        ("CC_Base_Spine02", "NURION_chest", "DIRECT"),
    ]
    for d, c, role in checks:
        _ok(mapped[d] == (c, role), f"{d} → {mapped[d]}")
    _ok(mapped["CC_Base_Pelvis"] == (None, "ADAPTER_INTERMEDIARY"), "Jake Pelvis intermediary")
    _ok(mapped["CC_Base_NeckTwist01"][0] == "NURION_neck", "twist01")
    _ok(mapped["CC_Base_NeckTwist02"][0] == "NURION_neck", "twist02")
    _ok(mapped["CC_Base_NeckTwist01"][1] == "COLLAPSE_COMPOUND", "collapse role")
    return {"hierarchy": "PASS"}


def test_root_ownership(profile, eng, synth_frame):
    donor = pose_from_locals(synth_frame["locals"])
    out = eng.donor_to_canonical(profile, donor)
    root_t = out.locals["NURION_root"].translation
    exp = expected_translation_rx_neg90(donor.locals["CC_Base_BoneRoot"].translation, profile.unit_scale)
    for i in range(3):
        _ok(abs(root_t[i] - exp[i]) <= TOL_TR, f"root t[{i}]")
    return {"rootTranslationObserved": list(root_t), "expected": list(exp)}


def test_pelvis_ownership(profile, eng, synth_frame):
    donor = pose_from_locals(synth_frame["locals"])
    out = eng.donor_to_canonical(profile, donor)
    pelvis_t = out.locals["NURION_pelvis"].translation
    exp = expected_translation_rx_neg90(donor.locals["CC_Base_Hip"].translation, profile.unit_scale)
    for i in range(3):
        _ok(abs(pelvis_t[i] - exp[i]) <= TOL_TR, f"pelvis t[{i}]")
    # Hip owns pelvis translation — not Jake Pelvis bone
    _ok("CC_Base_Pelvis" not in out.locals, "no pelvis name leak")
    return {"pelvisTranslationObserved": list(pelvis_t), "expected": list(exp)}


def test_jake_pelvis_intermediary_isolation(profile, eng):
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    donor = pose_from_locals(extract["restLocals"])
    # Force intermediary presence in donor pose
    donor.locals["CC_Base_Pelvis"] = BoneLocal(rotation=IDENTITY, translation=(9.0, 9.0, 9.0))
    out = eng.donor_to_canonical(profile, donor)
    _ok("CC_Base_Pelvis" not in out.locals, "intermediary leaked as key")
    for k in out.locals:
        _ok(k.startswith("NURION_"), f"non-canonical key {k}")
    # Attempt illegal direct map must FAIL validation
    bad = profile_from_dict(profile.to_json_dict())
    d = bad.to_json_dict()
    d["bone_mapping"] = [
        e for e in d["bone_mapping"] if e["donor_bone"] != "CC_Base_Pelvis"
    ] + [{"donor_bone": "CC_Base_Pelvis", "canonical_bone": "NURION_pelvis", "role": "DIRECT"}]
    d["intermediary_bones"] = []
    try:
        illegal = profile_from_dict(d)
        codes = {i.code for i in validate_profile(illegal)}
        # Either validator catches duplicate pelvis mapping collision or we assert Hip still preferred —
        # primary: intermediary leak rule when listed; here we removed intermediary list and mapped DIRECT —
        # DUPLICATE with Hip→pelvis should FAIL
        _ok("DUPLICATE_CANONICAL_MAPPING" in codes or "INTERMEDIARY_LEAKAGE" in codes, codes)
    except ValueError as e:
        _ok(True, str(e))
    return {"intermediaryIsolation": True, "directLeakDenied": True}


def test_waist_spine_chain(profile, eng, synth):
    donor = pose_from_locals(synth["frames"][3]["locals"])
    out = eng.donor_to_canonical(profile, donor)
    for db, cb in (
        ("CC_Base_Waist", "NURION_spine01"),
        ("CC_Base_Spine01", "NURION_spine02"),
        ("CC_Base_Spine02", "NURION_chest"),
    ):
        exp = expected_rotation_direct(profile, db, cb, donor.locals[db].rotation)
        err = max_rot_err(exp, out.locals[cb].rotation)
        _ok(err <= TOL_ROT, f"{cb} err={err}")
    return {"waistSpineChain": "PASS"}


def test_neck_collapse_compose(profile, eng, synth):
    """Must Compose Twist01×02 in common-parent space — discarding either must NOT match."""
    donor = pose_from_locals(synth["frames"][1]["locals"])
    out = eng.donor_to_canonical(profile, donor)
    exp = expected_neck_collapse(profile, donor)
    err = max_rot_err(exp, out.locals["NURION_neck"].rotation)
    _ok(err <= TOL_ROT, f"collapse err={err}")

    only1 = PoseFrame(locals=dict(donor.locals))
    only1.locals["CC_Base_NeckTwist02"] = BoneLocal(rotation=IDENTITY)
    neck_only1 = expected_neck_collapse(profile, only1)
    _ok(not approx_eq(neck_only1, out.locals["NURION_neck"].rotation, tol=1e-4), "must not equal Twist01-only")

    only2 = PoseFrame(locals=dict(donor.locals))
    only2.locals["CC_Base_NeckTwist01"] = BoneLocal(rotation=IDENTITY)
    neck_only2 = expected_neck_collapse(profile, only2)
    _ok(not approx_eq(neck_only2, out.locals["NURION_neck"].rotation, tol=1e-4), "must not equal Twist02-only")

    t1 = donor.locals["CC_Base_NeckTwist01"].rotation
    t2 = donor.locals["CC_Base_NeckTwist02"].rotation
    _ok(not approx_eq(multiply(t2, t1), multiply(t1, t2), tol=1e-6), "non-commuting axes")
    _ok(profile.collapse_chains[0].common_parent_donor == "CC_Base_Spine02", "common parent declared")
    return {
        "collapseErr": err,
        "antiDiscardTwist01Only": True,
        "antiDiscardTwist02Only": True,
        "composeOrderMatters": True,
        "common_parent_donor": profile.collapse_chains[0].common_parent_donor,
        "observedNeck": list(out.locals["NURION_neck"].rotation),
        "expectedNeck": list(exp),
    }


def test_neck_collapse_common_parent_nonidentity_bind(profile, eng):
    """
    P3/P4: non-identity NeckTwist binds + non-commuting deltas.
    Prove naive ∏Δ_local ≠ common-parent Compose, and engine matches common-parent only.
    """
    import inspect

    from fast_track.runtime.retarget.engine import RetargetEngine

    src = inspect.getsource(RetargetEngine.retarget_collapse_chain)
    _ok("common_parent_donor" in src, "engine must reference common_parent_donor")
    _ok("path_from_common_parent" in src, "engine must build G_i from common_parent path")
    _ok("assert_collapse_chain_hierarchy" in src, "engine must validate hierarchy")

    d = profile.to_json_dict()
    b1 = _q_axis_angle("x", 35.0)
    b2 = _q_axis_angle("y", 28.0)
    d["donor_bind_local_by_donor"] = dict(d["donor_bind_local_by_donor"])
    d["donor_bind_local_by_donor"]["CC_Base_NeckTwist01"] = list(b1)
    d["donor_bind_local_by_donor"]["CC_Base_NeckTwist02"] = list(b2)
    d["donor_bind_local_by_donor"].setdefault("CC_Base_Spine02", [1.0, 0.0, 0.0, 0.0])
    p2 = profile_from_dict(d)
    _ok(p2.collapse_chains[0].common_parent_donor == "CC_Base_Spine02", "parent")
    p2.assert_collapse_chain_hierarchy(p2.collapse_chains[0])

    delta1 = _q_axis_angle("z", 18.0)
    delta2 = _q_axis_angle("x", 22.0)
    _ok(not approx_eq(multiply(delta1, delta2), multiply(delta2, delta1), tol=1e-6), "deltas non-commute")

    anim1 = multiply(b1, delta1)
    anim2 = multiply(b2, delta2)

    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    donor = pose_from_locals(extract["restLocals"])
    donor.locals["CC_Base_NeckTwist01"] = BoneLocal(rotation=anim1)
    donor.locals["CC_Base_NeckTwist02"] = BoneLocal(rotation=anim2)

    correct = expected_neck_collapse(p2, donor)
    naive = naive_local_delta_product(p2, donor)
    _ok(not approx_eq(correct, naive, tol=1e-4), "correct_common_parent_result != naive_local_delta_product")

    out = eng.donor_to_canonical(p2, donor)
    err_correct = max_rot_err(correct, out.locals["NURION_neck"].rotation)
    err_naive = max_rot_err(naive, out.locals["NURION_neck"].rotation)
    _ok(err_correct <= TOL_ROT, f"engine must match common-parent expected err={err_correct}")
    _ok(err_naive > 1e-3, f"engine must NOT match naive product err={err_naive}")

    return {
        "bind_NT01": list(b1),
        "bind_NT02": list(b2),
        "correctNeck": list(correct),
        "naiveNeck": list(naive),
        "observedNeck": list(out.locals["NURION_neck"].rotation),
        "errVsCorrect": err_correct,
        "errVsNaive": err_naive,
        "common_parent_donor": p2.collapse_chains[0].common_parent_donor,
        "hierarchyPath": list(
            p2.path_from_common_parent("CC_Base_Spine02", "CC_Base_NeckTwist02")
        ),
        "proved": "correct_common_parent_result != naive_local_delta_product",
    }


def test_neck_collapse_reject_wrong_common_parent(profile, eng):
    """P1d: wrong common_parent_donor must FAIL validation and retarget."""
    d = profile.to_json_dict()
    _ok(d.get("donor_parent_of"), "donor_parent_of present")
    _ok(
        d["donor_parent_of"].get("CC_Base_NeckTwist01") == "CC_Base_Spine02",
        "NT01 parent",
    )
    _ok(
        d["donor_parent_of"].get("CC_Base_NeckTwist02") == "CC_Base_NeckTwist01",
        "NT02 parent",
    )

    # Wrong parent: Hip is NOT Spine02
    d["collapse_chains"] = [
        {
            "canonical_bone": "NURION_neck",
            "donor_bones_in_order": ["CC_Base_NeckTwist01", "CC_Base_NeckTwist02"],
            "common_parent_donor": "CC_Base_Hip",
        }
    ]
    bad = profile_from_dict(d)
    codes = {i.code for i in validate_profile(bad)}
    _ok(
        "COLLAPSE_COMMON_PARENT_MISMATCH" in codes or "COLLAPSE_HIERARCHY" in codes,
        f"validator must reject wrong parent, got {codes}",
    )
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    donor = pose_from_locals(extract["restLocals"])
    try:
        eng.donor_to_canonical(bad, donor)
        raise AssertionError("engine must FAIL on wrong common_parent_donor")
    except (ValueError, Exception) as e:
        _ok(
            "COLLAPSE_COMMON_PARENT_MISMATCH" in str(e) or "COLLAPSE_HIERARCHY" in str(e),
            str(e),
        )

    # Another wrong parent: Head
    d2 = profile.to_json_dict()
    d2["collapse_chains"] = [
        {
            "canonical_bone": "NURION_neck",
            "donor_bones_in_order": ["CC_Base_NeckTwist01", "CC_Base_NeckTwist02"],
            "common_parent_donor": "CC_Base_Head",
        }
    ]
    bad2 = profile_from_dict(d2)
    codes2 = {i.code for i in validate_profile(bad2)}
    _ok(
        "COLLAPSE_COMMON_PARENT_MISMATCH" in codes2 or "COLLAPSE_HIERARCHY" in codes2,
        codes2,
    )
    return {
        "wrongParentsRejected": ["CC_Base_Hip", "CC_Base_Head"],
        "validatorCodes": sorted(codes | codes2),
        "engineRaises": True,
    }


def test_collapse_rest_invariant(profile, eng):
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    donor = pose_from_locals(extract["restLocals"])
    out = eng.donor_to_canonical(profile, donor)
    err = max_rot_err(out.locals["NURION_neck"].rotation, profile.canonical_bind_local["NURION_neck"])
    _ok(err <= TOL_ROT, f"rest neck err={err}")
    for b in eng.core_bones:
        e = max_rot_err(out.locals[b].rotation, profile.canonical_bind_local[b])
        _ok(e <= TOL_ROT, f"rest {b}={e}")
    return {"maxRestRotErr": err, "tol": TOL_ROT}


def test_axis_and_translation_stages(profile, eng):
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    donor = pose_from_locals(extract["restLocals"])
    donor.locals["CC_Base_Hip"] = BoneLocal(rotation=IDENTITY, translation=(0.0, 0.0, 1.0))
    s = float(profile.unit_scale)
    after_unit = (0.0, 0.0, s)
    after_axis = (0.0, s, 0.0)  # Rx(-90) +Z→+Y
    out = eng.donor_to_canonical(profile, donor)
    obs = out.locals["NURION_pelvis"].translation
    for i in range(3):
        _ok(abs(obs[i] - after_axis[i]) <= TOL_TR, f"t[{i}]")
    _ok(obs != after_unit, "must apply axis remap")
    # reverse path
    back = eng.canonical_to_target(profile, out)
    hip_back = back.locals["CC_Base_Hip"].translation
    exp_rev = (0.0, 0.0, 1.0)
    for i in range(3):
        _ok(abs(hip_back[i] - exp_rev[i]) <= 1e-5, f"rev[{i}] obs={hip_back} exp={exp_rev}")
    return {
        "afterUnit": list(after_unit),
        "afterAxisExpected": list(after_axis),
        "observed": list(obs),
        "reverseHipTranslation": list(hip_back),
    }


def test_twist_as_source_isolation(profile):
    _ok(profile.twist_policy.allow_as_core_source is False, "allow_as_core_source")
    for e in profile.bone_mapping:
        if e.donor_bone in profile.twist_policy.donor_twist_bones:
            _ok(False, f"twist deform {e.donor_bone} mapped as {e.role}")
    # Inject illegal twist→Core map
    d = profile.to_json_dict()
    d["bone_mapping"] = list(d["bone_mapping"]) + [
        {
            "donor_bone": "CC_Base_L_UpperarmTwist01",
            "canonical_bone": "NURION_upperArm_L",
            "role": "DIRECT",
        }
    ]
    d["twist_policy"]["donor_twist_bones"] = list(
        set(d["twist_policy"]["donor_twist_bones"] + ["CC_Base_L_UpperarmTwist01"])
    )
    bad = profile_from_dict(d)
    codes = {i.code for i in validate_profile(bad)}
    _ok("TWIST_AS_SOURCE" in codes or "DUPLICATE_CANONICAL_MAPPING" in codes, codes)
    return {"twistSourceDenied": True, "codes": sorted(codes)}


def test_representative_motion(profile, eng, synth):
    results = []
    global_max = 0.0
    for fr in synth["frames"]:
        donor = pose_from_locals(fr["locals"])
        out = eng.donor_to_canonical(profile, donor)
        frame_max = 0.0
        # direct bones
        for e in profile.bone_mapping:
            if e.canonical_bone is None or e.role in (
                "HELPER_DROP",
                "ADAPTER_INTERMEDIARY",
                "COLLAPSE_COMPOUND",
            ):
                continue
            if e.donor_bone not in donor.locals:
                continue
            exp = expected_rotation_direct(profile, e.donor_bone, e.canonical_bone, donor.locals[e.donor_bone].rotation)
            err = max_rot_err(exp, out.locals[e.canonical_bone].rotation)
            frame_max = max(frame_max, err)
            _ok(err <= TOL_ROT, f"f{fr['frame']} {e.canonical_bone}={err}")
        # collapse
        exp_n = expected_neck_collapse(profile, donor)
        err_n = max_rot_err(exp_n, out.locals["NURION_neck"].rotation)
        frame_max = max(frame_max, err_n)
        _ok(err_n <= TOL_ROT, f"f{fr['frame']} neck={err_n}")
        global_max = max(global_max, frame_max)
        results.append(
            {
                "frame": fr["frame"],
                "maxRotErr": frame_max,
                "neck": list(out.locals["NURION_neck"].rotation),
                "pelvisT": list(out.locals["NURION_pelvis"].translation),
                "rootT": list(out.locals["NURION_root"].translation),
            }
        )
    return {"frames": results, "maxRotErr": global_max, "tol": TOL_ROT}


def test_deterministic(profile, eng, synth):
    donor = pose_from_locals(synth["frames"][1]["locals"])
    a = eng.donor_to_canonical(profile, donor)
    b = eng.donor_to_canonical(profile, donor)
    for bone in eng.core_bones:
        _ok(approx_eq(a.locals[bone].rotation, b.locals[bone].rotation, tol=0.0), bone)
    _ok(profile.deterministic_dumps() == profile.deterministic_dumps(), "dumps")
    return {"deterministic": True}


def test_donor_literal_isolation():
    forbidden = ("CC_Base", "Hips", "LeftUpLeg", "Mixamo", "NeckTwist")
    paths = [
        ROOT / "fast_track/runtime/body_retarget_engine.py",
        ROOT / "fast_track/runtime/retarget/engine.py",
    ]
    hits = []
    for p in paths:
        src = p.read_text(encoding="utf-8")
        for tok in forbidden:
            if tok in src:
                hits.append(f"{p.name}:{tok}")
    _ok(not hits, f"donor literals: {hits}")
    return {"hits": hits}


def main() -> int:
    _calibrate_and_synth()
    profile = load_profile(PROFILE_PATH)
    eng = BodyRetargetEngine()
    synth = json.loads(SYNTH.read_text(encoding="utf-8"))
    donor0 = pose_from_locals(synth["frames"][0]["locals"])
    out0 = eng.donor_to_canonical(profile, donor0)

    tests = [
        ("test_protected", lambda: test_protected()),
        ("test_profile_valid", lambda: test_profile_valid(profile)),
        ("test_core23_completeness", lambda: test_core23_completeness(eng, out0)),
        ("test_hierarchy_semantics", lambda: test_hierarchy_semantics(profile)),
        ("test_root_ownership", lambda: test_root_ownership(profile, eng, synth["frames"][2])),
        ("test_pelvis_ownership", lambda: test_pelvis_ownership(profile, eng, synth["frames"][2])),
        ("test_jake_pelvis_intermediary_isolation", lambda: test_jake_pelvis_intermediary_isolation(profile, eng)),
        ("test_waist_spine_chain", lambda: test_waist_spine_chain(profile, eng, synth)),
        ("test_neck_collapse_compose", lambda: test_neck_collapse_compose(profile, eng, synth)),
        ("test_neck_collapse_common_parent_nonidentity_bind", lambda: test_neck_collapse_common_parent_nonidentity_bind(profile, eng)),
        ("test_neck_collapse_reject_wrong_common_parent", lambda: test_neck_collapse_reject_wrong_common_parent(profile, eng)),
        ("test_collapse_rest_invariant", lambda: test_collapse_rest_invariant(profile, eng)),
        ("test_axis_and_translation_stages", lambda: test_axis_and_translation_stages(profile, eng)),
        ("test_twist_as_source_isolation", lambda: test_twist_as_source_isolation(profile)),
        ("test_representative_motion", lambda: test_representative_motion(profile, eng, synth)),
        ("test_deterministic", lambda: test_deterministic(profile, eng, synth)),
        ("test_donor_literal_isolation", lambda: test_donor_literal_isolation()),
    ]

    results = []
    for name, fn in tests:
        try:
            detail = fn()
            results.append({"test": name, "status": "PASS", "detail": detail})
        except Exception as e:
            results.append({"test": name, "status": "FAIL", "error": str(e)})

    failed = [r for r in results if r["status"] == "FAIL"]
    summary = {
        "stage": "NURION-RIG-02C_JAKE_ADAPTER_PROOF",
        "rig02cPass": "NOT_DECLARED",
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "tolerances": {"rotation": TOL_ROT, "translation": TOL_TR},
        "results": results,
    }
    out_path = EV / "NURION-RIG-02C_jake_adapter_proof_stdout.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "out": str(out_path)}, ensure_ascii=True))
    print({"passed": summary["passed"], "failed": summary["failed"], "results": [{"test": r["test"], "status": r["status"]} for r in results]})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
