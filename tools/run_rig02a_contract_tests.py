#!/usr/bin/env python3
"""RIG-02A contract tests — numerical / structural (not visual PASS)."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))

from fast_track.runtime.retarget.engine import BoneLocal, PoseFrame, RetargetEngine
from fast_track.runtime.retarget.profile import DonorSkeletonProfile
from fast_track.runtime.retarget.protected import assert_protected_sot_unchanged
from fast_track.runtime.retarget.quat import IDENTITY, approx_eq, hemisphere, multiply, normalize
from fast_track.runtime.retarget.registry import (
    PROFILE_JAKE_CC,
    PROFILE_MJN_LEGACY,
    RetargetAdapterRegistry,
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_protected_sot() -> None:
    assert_protected_sot_unchanged()


def test_engine_has_no_donor_literals() -> None:
    import fast_track.runtime.retarget.engine as eng
    import fast_track.runtime.retarget.canonical as can

    src = inspect.getsource(eng) + inspect.getsource(can)
    forbidden = ("CC_Base", "Hips", "Spine02", "LeftUpLeg", "Jake", "MJN", "Mixamo")
    for token in forbidden:
        _assert(token not in src, f"donor literal leaked into engine/canonical: {token}")


def test_registry_profiles() -> None:
    reg = RetargetAdapterRegistry()
    reg.register_defaults()
    _assert(set(reg.list_ids()) == {PROFILE_MJN_LEGACY, PROFILE_JAKE_CC}, "profile ids")
    mjn = reg.get(PROFILE_MJN_LEGACY)
    jake = reg.get(PROFILE_JAKE_CC)
    mjn.validate()
    jake.validate()
    _assert("CC_Base_Pelvis" in jake.intermediaries, "jake intermediary listed")
    _assert(len(jake.collapse_chains) == 1, "neck collapse present")


def test_identity_rest_removal_mjn() -> None:
    reg = RetargetAdapterRegistry()
    reg.register_defaults()
    eng = reg.engine
    mjn = reg.get(PROFILE_MJN_LEGACY)
    donor = PoseFrame(
        locals={
            e.donor_bone: BoneLocal(rotation=mjn.donor_bind_local_by_donor.get(e.donor_bone, IDENTITY))
            for e in mjn.bone_maps
            if e.role not in ("HELPER_DROP", "VIRTUAL_ROOT", "ADAPTER_INTERMEDIARY")
        }
    )
    # add pelvis bind
    donor.locals["Hips"] = BoneLocal(rotation=IDENTITY)
    for e in mjn.bone_maps:
        if e.canonical_bone and e.role not in ("VIRTUAL_ROOT", "HELPER_DROP"):
            donor.locals[e.donor_bone] = BoneLocal(
                rotation=mjn.donor_bind_local_by_donor.get(e.donor_bone, IDENTITY)
            )
    out = eng.donor_to_canonical(mjn, donor)
    for b in eng.core_bones:
        if b == "NURION_root":
            continue
        _assert(b in out.locals, f"missing {b}")
        _assert(
            approx_eq(out.locals[b].rotation, mjn.canonical_bind_local[b]),
            f"identity retarget failed for {b}",
        )
    _assert("head_end" not in out.locals, "helper leaked")


def test_jake_intermediary_not_leaked_and_neck_collapse() -> None:
    reg = RetargetAdapterRegistry()
    reg.register_defaults()
    eng = reg.engine
    jake = reg.get(PROFILE_JAKE_CC)
    donor = PoseFrame(locals={})
    for e in jake.bone_maps:
        donor.locals[e.donor_bone] = BoneLocal(
            rotation=jake.donor_bind_local_by_donor.get(e.donor_bone, IDENTITY)
        )
    # also provide twist bones — must not become Canonical keys / sources
    for t in jake.twist_donor_bones:
        donor.locals[t] = BoneLocal(rotation=IDENTITY)
    out = eng.donor_to_canonical(jake, donor)
    _assert("CC_Base_Pelvis" not in out.locals, "intermediary leaked")
    for t in jake.twist_donor_bones:
        _assert(t not in out.locals, f"twist leaked {t}")
    _assert("NURION_neck" in out.locals, "neck missing")
    _assert(
        approx_eq(out.locals["NURION_neck"].rotation, jake.canonical_bind_local["NURION_neck"]),
        "neck collapse identity",
    )


def test_per_bone_q_basis_b_applied() -> None:
    """Engine must use distinct Q_basis_b per bone — not one global."""
    reg = RetargetAdapterRegistry()
    reg.register_defaults()
    eng = reg.engine
    mjn = reg.get(PROFILE_MJN_LEGACY)

    # Build a mutated profile with different Q_basis on spine01 vs upperArm_L
    q_a = hemisphere(normalize((0.96, 0.1, 0.0, 0.0)))
    q_b = hemisphere(normalize((0.96, 0.0, 0.1, 0.0)))
    qmap = dict(mjn.q_basis_by_canonical)
    qmap["NURION_spine01"] = q_a
    qmap["NURION_upperArm_L"] = q_b
    # non-identity donor anim deltas
    anim_delta = hemisphere(normalize((0.98, 0.0, 0.2, 0.0)))

    mutated = DonorSkeletonProfile(
        profile_id=mjn.profile_id,
        display_name=mjn.display_name,
        unit_scale_to_meters=mjn.unit_scale_to_meters,
        q_import=mjn.q_import,
        q_basis_by_canonical=qmap,
        donor_bind_local_by_donor=dict(mjn.donor_bind_local_by_donor),
        canonical_bind_local=dict(mjn.canonical_bind_local),
        bone_maps=mjn.bone_maps,
        collapse_chains=mjn.collapse_chains,
        intermediaries=mjn.intermediaries,
        helper_drop=mjn.helper_drop,
        twist_donor_bones=mjn.twist_donor_bones,
        rest_pose_class=mjn.rest_pose_class,
        notes=mjn.notes,
    )
    # anim = bind * delta  => remove rest yields delta
    donor = PoseFrame(
        locals={
            "Spine02": BoneLocal(rotation=multiply(IDENTITY, anim_delta)),
            "LeftArm": BoneLocal(rotation=multiply(IDENTITY, anim_delta)),
        }
    )
    # fill other required mapped bones with bind
    for e in mutated.bone_maps:
        if e.donor_bone not in donor.locals and e.role not in ("HELPER_DROP", "VIRTUAL_ROOT"):
            donor.locals[e.donor_bone] = BoneLocal(rotation=IDENTITY)

    out = eng.donor_to_canonical(mutated, donor)
    r_spine = out.locals["NURION_spine01"].rotation
    r_arm = out.locals["NURION_upperArm_L"].rotation
    _assert(not approx_eq(r_spine, r_arm, tol=1e-6), "per-bone Q_basis_b not differentiating outputs")


def test_root_pelvis_translation_ownership() -> None:
    reg = RetargetAdapterRegistry()
    reg.register_defaults()
    eng = reg.engine
    mjn = reg.get(PROFILE_MJN_LEGACY)
    donor = PoseFrame(locals={})
    for e in mjn.bone_maps:
        if e.role in ("HELPER_DROP", "VIRTUAL_ROOT"):
            continue
        tr = (1.0, 2.0, 3.0) if e.donor_bone in ("Hips", "LeftArm") else (0.0, 0.0, 0.0)
        donor.locals[e.donor_bone] = BoneLocal(rotation=IDENTITY, translation=tr)
    out = eng.donor_to_canonical(mjn, donor)
    _assert(out.locals["NURION_pelvis"].translation == (1.0, 2.0, 3.0), "pelvis tr")
    _assert(out.locals["NURION_upperArm_L"].translation == (0.0, 0.0, 0.0), "arm tr stripped")


def test_mirror_invariant() -> None:
    RetargetEngine.assert_mirror_invariant()


def test_determinism() -> None:
    reg = RetargetAdapterRegistry()
    reg.register_defaults()
    eng = reg.engine
    jake = reg.get(PROFILE_JAKE_CC)
    donor = PoseFrame(
        locals={
            e.donor_bone: BoneLocal(rotation=IDENTITY) for e in jake.bone_maps
        }
    )
    a = eng.donor_to_canonical(jake, donor)
    b = eng.donor_to_canonical(jake, donor)
    for k in a.locals:
        _assert(approx_eq(a.locals[k].rotation, b.locals[k].rotation), f"nondeterministic {k}")
        _assert(a.locals[k].translation == b.locals[k].translation, f"nondeterministic tr {k}")


def main() -> int:
    tests = [
        test_protected_sot,
        test_engine_has_no_donor_literals,
        test_registry_profiles,
        test_identity_rest_removal_mjn,
        test_jake_intermediary_not_leaked_and_neck_collapse,
        test_per_bone_q_basis_b_applied,
        test_root_pelvis_translation_ownership,
        test_mirror_invariant,
        test_determinism,
    ]
    results = []
    for fn in tests:
        try:
            fn()
            results.append({"test": fn.__name__, "status": "PASS"})
        except Exception as e:
            results.append({"test": fn.__name__, "status": "FAIL", "error": str(e)})
    failed = [r for r in results if r["status"] == "FAIL"]
    print({"passed": len(results) - len(failed), "failed": len(failed), "results": results})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
