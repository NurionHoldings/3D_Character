#!/usr/bin/env python3
"""
NURION-RIG-02D — Bidirectional / Invariant Proof.

Locks the common retarget system numerically (no new donors).
Human PASS NOT DECLARED here.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.body_retarget_engine import BodyRetargetEngine, BoneLocal, PoseFrame
from fast_track.runtime.donor_skeleton_profile import (
    build_canonical_identity_profile,
    load_profile,
)
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS, load_core_bones
from fast_track.runtime.retarget.protected import assert_protected_sot_unchanged
from fast_track.runtime.retarget.quat import (
    IDENTITY,
    approx_eq,
    hemisphere,
    mat_approx_eq,
    mat_mul,
    mirror_conjugation_holds,
    mirror_vector_yz,
    mirror_yz,
    multiply,
    normalize,
    quat_to_matrix,
)
from fast_track.runtime.retarget_contract_validator import assert_profile_valid

EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles"
FIX02B = EV / "rig02b_fixtures"
FIX02C = EV / "rig02c_fixtures"

TOL_ROT = 1e-5
TOL_TR = 1e-6
TOL_ID = 1e-4


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _q(lst):
    return hemisphere(normalize(tuple(float(x) for x in lst)))


def max_rot_err(a, b) -> float:
    a, b = hemisphere(a), hemisphere(b)
    return max(abs(a[i] - b[i]) for i in range(4))


def max_tr_err(a, b) -> float:
    return max(abs(a[i] - b[i]) for i in range(3))


def pose_from_locals(locals_map: dict) -> PoseFrame:
    out = {}
    for name, bl in locals_map.items():
        out[name] = BoneLocal(
            rotation=_q(bl["rotation_wxyz"]),
            translation=tuple(float(x) for x in bl["translation"]),
        )
    return PoseFrame(locals=out)


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


def merge_donor_pose(base: PoseFrame, overlay: PoseFrame) -> PoseFrame:
    merged = dict(base.locals)
    merged.update(overlay.locals)
    return PoseFrame(locals=merged)


def direct_donor_bones(profile) -> list[str]:
    collapse = profile.collapse_donor_bones()
    out = []
    for e in profile.bone_mapping:
        if e.canonical_bone is None:
            continue
        if e.role in ("HELPER_DROP", "ADAPTER_INTERMEDIARY", "VIRTUAL_ROOT", "COLLAPSE_COMPOUND"):
            continue
        if e.donor_bone in collapse:
            continue
        out.append(e.donor_bone)
    return out


def test_protected():
    h = assert_protected_sot_unchanged()
    return {"protectedHashMatch": True, "hashes": h}


def test_canonical_identity(eng: BodyRetargetEngine):
    m = eng.identity_self_test(tol=TOL_ID)
    _ok(m.max_rotation_abs_err <= TOL_ID, f"rot {m.max_rotation_abs_err}")
    _ok(m.max_translation_abs_err <= TOL_ID, f"tr {m.max_translation_abs_err}")
    _ok(m.scale_err == 0.0, "scale must be 0")
    # Also: identity file profile
    file_p = load_profile(SEM / "canonical_identity_profile_v1.json")
    assert_profile_valid(file_p)
    donor = PoseFrame(
        locals={b: BoneLocal(rotation=file_p.canonical_bind_local[b]) for b in eng.core_bones}
    )
    out = eng.donor_to_canonical(file_p, donor)
    max_r = 0.0
    for b in eng.core_bones:
        max_r = max(max_r, max_rot_err(out.locals[b].rotation, file_p.canonical_bind_local[b]))
    _ok(max_r <= TOL_ID, f"file identity rot {max_r}")
    return {
        "positionError": m.max_translation_abs_err,
        "rotationError": m.max_rotation_abs_err,
        "scaleError": m.scale_err,
        "fileIdentityMaxRotErr": max_r,
        "tol": TOL_ID,
    }


def test_identity_canonical_roundtrip(eng: BodyRetargetEngine):
    """Canonical → (identity profile as donor) → Canonical ≈ original."""
    profile = build_canonical_identity_profile()
    # Synthetic Canonical pose
    canon = PoseFrame(
        locals={
            b: BoneLocal(
                rotation=_q_axis_angle("y", 7.0) if b == "NURION_chest" else IDENTITY,
                translation=(0.01, 0.02, 0.0) if b == "NURION_pelvis" else (0.0, 0.0, 0.0),
            )
            for b in eng.core_bones
        }
    )
    # Through identity mapping: donor bones == canonical names
    mid = eng.canonical_to_target(profile, canon)
    back = eng.donor_to_canonical(profile, mid)
    max_r = 0.0
    max_t = 0.0
    for b in eng.core_bones:
        max_r = max(max_r, max_rot_err(canon.locals[b].rotation, back.locals[b].rotation))
        max_t = max(max_t, max_tr_err(canon.locals[b].translation, back.locals[b].translation))
    _ok(max_r <= TOL_ROT, f"C→D→C rot {max_r}")
    _ok(max_t <= TOL_TR, f"C→D→C tr {max_t}")
    return {"maxRotErr": max_r, "maxTrErr": max_t}


def test_mjn_donor_roundtrip(eng: BodyRetargetEngine):
    """Donor → Canonical → Donor ≈ original (MJN direct bones + hips translation)."""
    profile = load_profile(SEM / "mjn_legacy_profile_v1.json")
    assert_profile_valid(profile)
    synth = json.loads((FIX02B / "mjn_idle_15_pose_extract.json").read_text(encoding="utf-8"))
    # Use a mid frame with motion
    donor0 = pose_from_locals(synth["frames"][2]["locals"])
    # Drop helpers from comparison
    canon = eng.donor_to_canonical(profile, donor0)
    back = eng.canonical_to_target(profile, canon)
    max_r = 0.0
    max_t = 0.0
    for db in direct_donor_bones(profile):
        if db not in donor0.locals or db not in back.locals:
            continue
        max_r = max(max_r, max_rot_err(donor0.locals[db].rotation, back.locals[db].rotation))
        if db == "Hips":
            max_t = max(max_t, max_tr_err(donor0.locals[db].translation, back.locals[db].translation))
    _ok(max_r <= TOL_ROT, f"MJN D→C→D rot {max_r}")
    _ok(max_t <= TOL_TR, f"MJN D→C→D hips tr {max_t}")
    return {"maxRotErr": max_r, "maxHipsTrErr": max_t, "profile": profile.profile_id}


def test_mjn_canonical_roundtrip(eng: BodyRetargetEngine):
    """Canonical → Donor → Canonical ≈ original (MJN)."""
    profile = load_profile(SEM / "mjn_legacy_profile_v1.json")
    synth = json.loads((FIX02B / "mjn_idle_15_pose_extract.json").read_text(encoding="utf-8"))
    donor0 = pose_from_locals(synth["frames"][2]["locals"])
    canon0 = eng.donor_to_canonical(profile, donor0)
    donor1 = eng.canonical_to_target(profile, canon0)
    # Merge into full donor template so helpers/rest exist
    donor1f = merge_donor_pose(donor0, donor1)
    canon1 = eng.donor_to_canonical(profile, donor1f)
    max_r = 0.0
    max_t = 0.0
    for b in eng.core_bones:
        max_r = max(max_r, max_rot_err(canon0.locals[b].rotation, canon1.locals[b].rotation))
        max_t = max(max_t, max_tr_err(canon0.locals[b].translation, canon1.locals[b].translation))
    _ok(max_r <= TOL_ROT, f"MJN C→D→C rot {max_r}")
    _ok(max_t <= TOL_TR, f"MJN C→D→C tr {max_t}")
    return {"maxRotErr": max_r, "maxTrErr": max_t}


def test_jake_donor_roundtrip_direct(eng: BodyRetargetEngine):
    """Jake D→C→D on direct bones (not full NeckTwist recovery)."""
    profile = load_profile(SEM / "jake_cc_profile_v1.json")
    assert_profile_valid(profile)
    synth = json.loads((FIX02C / "jake_cc_synthetic_motion.json").read_text(encoding="utf-8"))
    donor0 = pose_from_locals(synth["frames"][3]["locals"])
    canon = eng.donor_to_canonical(profile, donor0)
    back = eng.canonical_to_target(profile, canon)
    max_r = 0.0
    max_t = 0.0
    for db in direct_donor_bones(profile):
        if db not in donor0.locals or db not in back.locals:
            continue
        max_r = max(max_r, max_rot_err(donor0.locals[db].rotation, back.locals[db].rotation))
        if db in ("CC_Base_BoneRoot", "CC_Base_Hip"):
            max_t = max(max_t, max_tr_err(donor0.locals[db].translation, back.locals[db].translation))
    _ok(max_r <= TOL_ROT, f"Jake D→C→D direct rot {max_r}")
    _ok(max_t <= TOL_TR, f"Jake D→C→D tr {max_t}")
    return {"maxRotErr": max_r, "maxTrErr": max_t}


def test_jake_canonical_roundtrip_including_collapse(eng: BodyRetargetEngine):
    """
    Canonical → Donor (lossy neck expand) → Canonical.
    Judges Canonical semantic invariants — not full NT01×NT02 recovery.
    """
    profile = load_profile(SEM / "jake_cc_profile_v1.json")
    synth = json.loads((FIX02C / "jake_cc_synthetic_motion.json").read_text(encoding="utf-8"))
    donor0 = pose_from_locals(synth["frames"][1]["locals"])  # neck motion
    canon0 = eng.donor_to_canonical(profile, donor0)
    donor1 = eng.canonical_to_target(profile, canon0)
    donor1f = merge_donor_pose(donor0, donor1)
    canon1 = eng.donor_to_canonical(profile, donor1f)
    max_r = 0.0
    for b in eng.core_bones:
        max_r = max(max_r, max_rot_err(canon0.locals[b].rotation, canon1.locals[b].rotation))
    neck_err = max_rot_err(canon0.locals["NURION_neck"].rotation, canon1.locals["NURION_neck"].rotation)
    _ok(max_r <= TOL_ROT, f"Jake C→D→C rot {max_r}")
    _ok(neck_err <= TOL_ROT, f"neck semantic round-trip {neck_err}")
    # Donor NT01/NT02 need not match original (lossy)
    return {
        "maxRotErr": max_r,
        "neckSemanticErr": neck_err,
        "collapseExpand": "LOSSY_FIRST_BONE",
        "note": "Canonical neck preserved; individual Twist channels not required to restore",
    }


def test_mirror_invariant():
    samples = [
        hemisphere(normalize((0.7, 0.2, 0.3, 0.4))),
        _q_axis_angle("y", 40.0),
        _q_axis_angle("z", -25.0),
        IDENTITY,
    ]
    BodyRetargetEngine  # noqa: ensure import used
    from fast_track.runtime.retarget.engine import RetargetEngine

    RetargetEngine.assert_mirror_invariant()
    for q in samples:
        _ok(mirror_conjugation_holds(q), f"conjugation {q}")
        qm = mirror_yz(q)
        _ok(approx_eq(qm, (q[0], q[1], -q[2], -q[3])), "q_mirror=(w,x,-y,-z)")
        # S R S
        s = ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        r = quat_to_matrix(q)
        lhs = quat_to_matrix(qm)
        rhs = mat_mul(mat_mul(s, r), s)
        _ok(mat_approx_eq(lhs, rhs, tol=1e-5), "R'=SRS")
    v = (1.5, -2.0, 3.0)
    _ok(mirror_vector_yz(v) == (-1.5, -2.0, 3.0), "v'=(-vx,vy,vz)")
    return {"samples": len(samples), "S": "diag(-1,+1,+1)", "q_mirror": "(w,x,-y,-z)"}


def test_root_pelvis_ownership_preserved(eng: BodyRetargetEngine):
    profile = load_profile(SEM / "mjn_legacy_profile_v1.json")
    synth = json.loads((FIX02B / "mjn_idle_15_pose_extract.json").read_text(encoding="utf-8"))
    donor = pose_from_locals(synth["frames"][2]["locals"])
    # Contaminate a non-owner with translation in donor (should strip)
    donor.locals["LeftArm"] = BoneLocal(
        rotation=donor.locals["LeftArm"].rotation, translation=(9.0, 9.0, 9.0)
    )
    out = eng.donor_to_canonical(profile, donor)
    _ok(out.locals["NURION_root"].translation == (0.0, 0.0, 0.0), "MJN virtual root tr=0")
    _ok(out.locals["NURION_upperArm_L"].translation == (0.0, 0.0, 0.0), "non-owner stripped")
    _ok(any(abs(c) > 0 for c in out.locals["NURION_pelvis"].translation), "pelvis has hips tr")
    # Jake root/pelvis both owners
    jp = load_profile(SEM / "jake_cc_profile_v1.json")
    js = json.loads((FIX02C / "jake_cc_synthetic_motion.json").read_text(encoding="utf-8"))
    jd = pose_from_locals(js["frames"][2]["locals"])
    jo = eng.donor_to_canonical(jp, jd)
    for b, bl in jo.locals.items():
        if b not in TRANSLATION_OWNERS:
            _ok(bl.translation == (0.0, 0.0, 0.0), f"jake non-owner {b}")
    return {
        "mjnRootZero": True,
        "mjnPelvisOwnsHips": True,
        "nonOwnerStrip": True,
        "jakeOwnersOnly": True,
    }


def test_scale_contamination_zero(eng: BodyRetargetEngine):
    """Scale curve contamination = 0: identity scale_err; no non-uniform scale baked into Core."""
    m = eng.identity_self_test(tol=TOL_ID)
    _ok(m.scale_err == 0.0, "identity scale_err")
    profile = load_profile(SEM / "mjn_legacy_profile_v1.json")
    _ok(abs(profile.unit_scale - 0.01) < 1e-12, "unit_scale discrete")
    # Round-trip of a pure translation must not invent rotation scale artifacts
    synth = json.loads((FIX02B / "mjn_idle_15_pose_extract.json").read_text(encoding="utf-8"))
    donor = pose_from_locals(synth["restLocals"])
    donor.locals["Hips"] = BoneLocal(rotation=IDENTITY, translation=(0.0, 0.0, 1.0))
    out = eng.donor_to_canonical(profile, donor)
    for b in eng.core_bones:
        if b == "NURION_pelvis":
            continue
        _ok(approx_eq(out.locals[b].rotation, profile.canonical_bind_local[b], tol=TOL_ROT), b)
    return {"scale_err": 0.0, "unit_scale": profile.unit_scale, "noRotContamination": True}


def test_translation_rotation_roundtrip_tolerance(eng: BodyRetargetEngine):
    """Dedicated tol check on both MJN and Jake C↔D for rot+tr owners."""
    results = {}
    for name, path, frame_locals in (
        (
            "mjn",
            SEM / "mjn_legacy_profile_v1.json",
            json.loads((FIX02B / "mjn_idle_15_pose_extract.json").read_text(encoding="utf-8"))["frames"][2][
                "locals"
            ],
        ),
        (
            "jake",
            SEM / "jake_cc_profile_v1.json",
            json.loads((FIX02C / "jake_cc_synthetic_motion.json").read_text(encoding="utf-8"))["frames"][2][
                "locals"
            ],
        ),
    ):
        profile = load_profile(path)
        donor = pose_from_locals(frame_locals)
        c0 = eng.donor_to_canonical(profile, donor)
        d1 = merge_donor_pose(donor, eng.canonical_to_target(profile, c0))
        c1 = eng.donor_to_canonical(profile, d1)
        mr = max(max_rot_err(c0.locals[b].rotation, c1.locals[b].rotation) for b in eng.core_bones)
        mt = max(max_tr_err(c0.locals[b].translation, c1.locals[b].translation) for b in eng.core_bones)
        _ok(mr <= TOL_ROT, f"{name} rot {mr}")
        _ok(mt <= TOL_TR, f"{name} tr {mt}")
        results[name] = {"maxRotErr": mr, "maxTrErr": mt}
    return {"results": results, "tolRot": TOL_ROT, "tolTr": TOL_TR}


def test_collapse_chain_roundtrip_consistency(eng: BodyRetargetEngine):
    """Jake neck: forward compose deterministic; Canonical semantic C→D→C."""
    profile = load_profile(SEM / "jake_cc_profile_v1.json")
    synth = json.loads((FIX02C / "jake_cc_synthetic_motion.json").read_text(encoding="utf-8"))
    donor = pose_from_locals(synth["frames"][1]["locals"])
    a = eng.donor_to_canonical(profile, donor)
    b = eng.donor_to_canonical(profile, donor)
    _ok(approx_eq(a.locals["NURION_neck"].rotation, b.locals["NURION_neck"].rotation, tol=0.0), "det")
    # Lossy reverse still recovers Canonical neck
    d1 = merge_donor_pose(donor, eng.canonical_to_target(profile, a))
    c1 = eng.donor_to_canonical(profile, d1)
    err = max_rot_err(a.locals["NURION_neck"].rotation, c1.locals["NURION_neck"].rotation)
    _ok(err <= TOL_ROT, f"collapse semantic {err}")
    return {"deterministicForward": True, "canonicalNeckRoundTripErr": err}


def test_deterministic(eng: BodyRetargetEngine):
    profile = load_profile(SEM / "jake_cc_profile_v1.json")
    _ok(profile.deterministic_dumps() == profile.deterministic_dumps(), "dumps")
    synth = json.loads((FIX02C / "jake_cc_synthetic_motion.json").read_text(encoding="utf-8"))
    donor = pose_from_locals(synth["frames"][3]["locals"])
    a = eng.donor_to_canonical(profile, donor)
    b = eng.donor_to_canonical(profile, donor)
    for bone in eng.core_bones:
        _ok(approx_eq(a.locals[bone].rotation, b.locals[bone].rotation, tol=0.0), bone)
        _ok(a.locals[bone].translation == b.locals[bone].translation, bone)
    return {"deterministic": True}


def test_donor_literal_isolation():
    forbidden = ("CC_Base", "Hips", "LeftUpLeg", "Mixamo", "NeckTwist", "Jake")
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
    eng = BodyRetargetEngine()
    tests = [
        ("test_protected", lambda: test_protected()),
        ("test_canonical_identity", lambda: test_canonical_identity(eng)),
        ("test_identity_canonical_roundtrip", lambda: test_identity_canonical_roundtrip(eng)),
        ("test_mjn_donor_roundtrip", lambda: test_mjn_donor_roundtrip(eng)),
        ("test_mjn_canonical_roundtrip", lambda: test_mjn_canonical_roundtrip(eng)),
        ("test_jake_donor_roundtrip_direct", lambda: test_jake_donor_roundtrip_direct(eng)),
        (
            "test_jake_canonical_roundtrip_including_collapse",
            lambda: test_jake_canonical_roundtrip_including_collapse(eng),
        ),
        ("test_mirror_invariant", lambda: test_mirror_invariant()),
        ("test_root_pelvis_ownership_preserved", lambda: test_root_pelvis_ownership_preserved(eng)),
        ("test_scale_contamination_zero", lambda: test_scale_contamination_zero(eng)),
        (
            "test_translation_rotation_roundtrip_tolerance",
            lambda: test_translation_rotation_roundtrip_tolerance(eng),
        ),
        (
            "test_collapse_chain_roundtrip_consistency",
            lambda: test_collapse_chain_roundtrip_consistency(eng),
        ),
        ("test_deterministic", lambda: test_deterministic(eng)),
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
        "stage": "NURION-RIG-02D_BIDIRECTIONAL_INVARIANT_PROOF",
        "rig02dPass": "NOT_DECLARED",
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "tolerances": {"rotation": TOL_ROT, "translation": TOL_TR, "identity": TOL_ID},
        "results": results,
    }
    out_path = EV / "NURION-RIG-02D_invariant_proof_stdout.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "out": str(out_path)}, ensure_ascii=True))
    print(
        {
            "passed": summary["passed"],
            "failed": summary["failed"],
            "results": [{"test": r["test"], "status": r["status"]} for r in results],
        }
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
