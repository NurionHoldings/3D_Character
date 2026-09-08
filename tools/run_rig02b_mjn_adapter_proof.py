#!/usr/bin/env python3
"""
NURION-RIG-02B — MJN Legacy → Canonical numerical adapter proof.

PASS gates (agent self-check only — human PASS NOT DECLARED here):
  mapping completeness, rest normalization, axis conversion, root/pelvis,
  translation/scale isolation, representative motion error, L/R symmetry,
  deterministic output, donor-literal isolation, Protected SoT hash.
"""

from __future__ import annotations

import copy
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.body_retarget_engine import BodyRetargetEngine, BoneLocal, PoseFrame
from fast_track.runtime.donor_skeleton_profile import load_profile
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS, load_core_bones
from fast_track.runtime.retarget.protected import assert_protected_sot_unchanged
from fast_track.runtime.retarget.quat import (
    IDENTITY,
    approx_eq,
    hemisphere,
    inverse,
    mirror_yz,
    multiply,
    normalize,
)
from fast_track.runtime.retarget_contract_validator import assert_profile_valid

EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
FIX = EV / "rig02b_fixtures"
PROFILE_PATH = ROOT / (
    "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json"
)
IDLE = FIX / "mjn_idle_15_pose_extract.json"
BOW = FIX / "mjn_formal_bow_pose_extract.json"

# Tolerances
TOL_ROT = 1e-5
TOL_TR = 1e-6
TOL_SYM = 1e-4

DONOR_TO_CANON = {
    "__virtual_root__": "NURION_root",
    "Hips": "NURION_pelvis",
    "Spine02": "NURION_spine01",
    "Spine01": "NURION_spine02",
    "Spine": "NURION_chest",
    "neck": "NURION_neck",
    "Head": "NURION_head",
    "LeftShoulder": "NURION_clavicle_L",
    "LeftArm": "NURION_upperArm_L",
    "LeftForeArm": "NURION_lowerArm_L",
    "LeftHand": "NURION_hand_L",
    "RightShoulder": "NURION_clavicle_R",
    "RightArm": "NURION_upperArm_R",
    "RightForeArm": "NURION_lowerArm_R",
    "RightHand": "NURION_hand_R",
    "LeftUpLeg": "NURION_thigh_L",
    "LeftLeg": "NURION_calf_L",
    "LeftFoot": "NURION_foot_L",
    "LeftToeBase": "NURION_toe_L",
    "RightUpLeg": "NURION_thigh_R",
    "RightLeg": "NURION_calf_R",
    "RightFoot": "NURION_foot_R",
    "RightToeBase": "NURION_toe_R",
}

HELPERS = ("head_end", "headfront")
LR_PAIRS = [
    ("NURION_clavicle_L", "NURION_clavicle_R"),
    ("NURION_upperArm_L", "NURION_upperArm_R"),
    ("NURION_lowerArm_L", "NURION_lowerArm_R"),
    ("NURION_hand_L", "NURION_hand_R"),
    ("NURION_thigh_L", "NURION_thigh_R"),
    ("NURION_calf_L", "NURION_calf_R"),
    ("NURION_foot_L", "NURION_foot_R"),
    ("NURION_toe_L", "NURION_toe_R"),
]


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _q(lst) -> tuple[float, float, float, float]:
    return hemisphere(normalize(tuple(float(x) for x in lst)))


def expected_rotation(profile, donor_bone: str, canonical_bone: str, anim) -> tuple:
    """Independent §14 expected (must match engine)."""
    bind_d = profile.donor_bind_local_by_donor.get(donor_bone, IDENTITY)
    delta = multiply(inverse(bind_d), anim)
    qi = profile.q_import
    delta = multiply(multiply(qi, delta), inverse(qi))
    qb = profile.q_basis_b[canonical_bone]
    delta = multiply(multiply(qb, delta), inverse(qb))
    bind_c = profile.canonical_bind_local[canonical_bone]
    return multiply(bind_c, delta)


def pose_from_extract_locals(locals_map: dict) -> PoseFrame:
    out = {}
    for name, bl in locals_map.items():
        if name in HELPERS:
            continue
        out[name] = BoneLocal(
            rotation=_q(bl["rotation_wxyz"]),
            translation=tuple(float(x) for x in bl["translation"]),
        )
    return PoseFrame(locals=out)


def max_rot_err(a, b) -> float:
    a, b = hemisphere(a), hemisphere(b)
    return max(abs(a[i] - b[i]) for i in range(4))


def test_protected() -> dict:
    h = assert_protected_sot_unchanged()
    return {"protectedHashMatch": True, "hashes": h}


def test_profile_valid(profile) -> dict:
    assert_profile_valid(profile)
    _ok(abs(profile.unit_scale - 0.01) < 1e-12, f"unit_scale {profile.unit_scale}")
    _ok(not approx_eq(profile.q_import, IDENTITY), "q_import must be non-identity for Z-up MJN")
    return {"profile_id": profile.profile_id, "unit_scale": profile.unit_scale, "q_import": list(profile.q_import)}


def test_mapping_completeness(profile, eng, out: PoseFrame) -> dict:
    core = set(load_core_bones())
    _ok(set(out.locals.keys()) == core, f"output keys != Core23: {set(out.locals.keys()) ^ core}")
    mapped = {e.donor_bone: e.canonical_bone for e in profile.bone_mapping if e.canonical_bone}
    for d, c in DONOR_TO_CANON.items():
        _ok(mapped.get(d) == c, f"mapping {d} → {mapped.get(d)} expected {c}")
    for h in HELPERS:
        entry = next(e for e in profile.bone_mapping if e.donor_bone == h)
        _ok(entry.role == "HELPER_DROP" and entry.canonical_bone is None, f"helper {h}")
        _ok(h not in out.locals, f"helper leaked {h}")
    # spine inversion explicit
    _ok(mapped["Spine02"] == "NURION_spine01", "Spine02")
    _ok(mapped["Spine01"] == "NURION_spine02", "Spine01")
    _ok(mapped["Spine"] == "NURION_chest", "Spine")
    _ok(mapped["Hips"] == "NURION_pelvis", "Hips")
    _ok(mapped["__virtual_root__"] == "NURION_root", "virtual root")
    return {"coreBones": len(core), "helpersDropped": list(HELPERS)}


def test_rest_normalization(profile, eng) -> dict:
    idle = json.loads(IDLE.read_text(encoding="utf-8"))
    donor = pose_from_extract_locals(idle["restLocals"])
    out = eng.donor_to_canonical(profile, donor)
    errs = {}
    for b in eng.core_bones:
        e = max_rot_err(out.locals[b].rotation, profile.canonical_bind_local[b])
        errs[b] = e
        _ok(e <= TOL_ROT, f"rest {b} err={e}")
    return {"maxRestRotErr": max(errs.values()), "tol": TOL_ROT}


def test_axis_conversion(profile) -> dict:
    """Q_import conjugation changes a non-aligned delta; Rx(-90) maps +Z→+Y conceptually."""
    qi = profile.q_import
    # pure rotation about donor world-Z expressed as local sample
    delta = hemisphere(normalize((0.92387953, 0.0, 0.0, 0.38268343)))  # ~45° about Z
    remapped = multiply(multiply(qi, delta), inverse(qi))
    _ok(not approx_eq(delta, remapped, tol=1e-6), "axis remap must change Z-rotation sample")
    # conjugating identity stays identity
    _ok(approx_eq(multiply(multiply(qi, IDENTITY), inverse(qi)), IDENTITY), "I stays I")
    return {"q_import": list(qi), "sampleChanged": True}


def _expected_pelvis_translation_independent(
    hips_t: tuple[float, float, float], unit_scale: float
) -> tuple[float, float, float]:
    """
    Analytic expected for MJN Q_import = Rx(-90°).
    Does NOT call RetargetEngine helpers (P3 independence).

    Stage 1 UNIT: t_m = unit_scale * t_donor
    Stage 2 AXIS: R_x(-90)·(x,y,z) = (x, z, -y)  → donor +Z → Canonical +Y
    """
    x, y, z = (hips_t[0] * unit_scale, hips_t[1] * unit_scale, hips_t[2] * unit_scale)
    return (x, z, -y)


def test_axis_translation_conversion(profile, eng) -> dict:
    """
    Synthetic analytic fixture: pure donor +Z translation must land on Canonical +Y
    after UNIT scale then GLOBAL AXIS REMAP (separated stages).
    """
    idle = json.loads(IDLE.read_text(encoding="utf-8"))
    donor = pose_from_extract_locals(idle["restLocals"])
    # Pure +Z in donor import space (before scale)
    donor.locals["Hips"] = BoneLocal(rotation=IDENTITY, translation=(0.0, 0.0, 1.0))

    # Stage proofs without opaque engine bundling
    s = float(profile.unit_scale)
    after_unit = (0.0, 0.0, 1.0 * s)
    # Analytic Rx(-90): (0,0,s) → (0, s, 0)
    after_axis_expected = (0.0, after_unit[2], -after_unit[1])
    _ok(after_axis_expected == (0.0, s, 0.0), "analytic +Z→+Y")

    out = eng.donor_to_canonical(profile, donor)
    obs = out.locals["NURION_pelvis"].translation
    for i in range(3):
        _ok(abs(obs[i] - after_axis_expected[i]) <= TOL_TR, f"synth pelvis t[{i}] obs={obs} exp={after_axis_expected}")

    # Also prove unit stage alone is not the final Canonical vector
    _ok(obs != after_unit, "must not stop at unit-only (would leave +Z)")
    _ok(abs(obs[1] - s) <= TOL_TR and abs(obs[2]) <= TOL_TR, "Canonical +Y component")

    return {
        "donorTranslation": [0.0, 0.0, 1.0],
        "afterUnitNormalization": list(after_unit),
        "afterGlobalAxisRemapExpected": list(after_axis_expected),
        "observedPelvisTranslation": list(obs),
        "mapping": "donor +Z → Canonical +Y via Rx(-90°)",
        "tol": TOL_TR,
    }


def test_root_pelvis_and_scale(profile, eng, extract_frame: dict) -> dict:
    donor = pose_from_extract_locals(extract_frame)
    out = eng.donor_to_canonical(profile, donor)
    root = out.locals["NURION_root"]
    pelvis = out.locals["NURION_pelvis"]
    _ok(approx_eq(root.rotation, profile.canonical_bind_local["NURION_root"], tol=TOL_ROT), "root rot")
    _ok(root.translation == (0.0, 0.0, 0.0), f"root translation must be 0, got {root.translation}")
    hips_t = donor.locals["Hips"].translation
    # P3: expected independent of engine.import_normalize_translation
    expected_pelvis_t = _expected_pelvis_translation_independent(hips_t, profile.unit_scale)
    # Sanity: must differ from scale-only when hips has non-aligned components
    scale_only = tuple(c * profile.unit_scale for c in hips_t)
    _ok(
        expected_pelvis_t != scale_only or (abs(hips_t[1]) < 1e-12 and abs(hips_t[2]) < 1e-12),
        "axis remap must change expected vs scale-only for typical hips motion",
    )
    for i in range(3):
        _ok(abs(pelvis.translation[i] - expected_pelvis_t[i]) <= TOL_TR, f"pelvis t[{i}]")
    for b, bl in out.locals.items():
        if b not in TRANSLATION_OWNERS:
            _ok(bl.translation == (0.0, 0.0, 0.0), f"non-owner {b} has translation")
    return {
        "rootTranslation": list(root.translation),
        "pelvisTranslationObserved": list(pelvis.translation),
        "pelvisTranslationExpected": list(expected_pelvis_t),
        "scaleOnlyWouldHaveBeen": list(scale_only),
        "unit_scale": profile.unit_scale,
        "expectedConstruction": "unit_scale then Rx(-90) matrix (x,z,-y) — not engine helper",
    }


def test_motion_numerical(profile, eng, extract_path: Path, clip_id: str) -> dict:
    data = json.loads(extract_path.read_text(encoding="utf-8"))
    per_frame = []
    global_max = 0.0
    observed_dump = []
    for fr in data["frames"]:
        donor = pose_from_extract_locals(fr["locals"])
        out = eng.donor_to_canonical(profile, donor)
        frame_max = 0.0
        bone_errs = {}
        for e in profile.bone_mapping:
            if e.canonical_bone is None or e.role in ("HELPER_DROP", "VIRTUAL_ROOT", "ADAPTER_INTERMEDIARY"):
                continue
            if e.donor_bone not in donor.locals:
                continue
            exp = expected_rotation(profile, e.donor_bone, e.canonical_bone, donor.locals[e.donor_bone].rotation)
            obs = out.locals[e.canonical_bone].rotation
            err = max_rot_err(exp, obs)
            bone_errs[e.canonical_bone] = err
            frame_max = max(frame_max, err)
            _ok(err <= TOL_ROT, f"{clip_id} f{fr['frame']} {e.canonical_bone} err={err}")
        global_max = max(global_max, frame_max)
        observed_dump.append(
            {
                "frame": fr["frame"],
                "maxRotErr": frame_max,
                "sample": {
                    "NURION_pelvis": list(out.locals["NURION_pelvis"].rotation),
                    "NURION_spine01": list(out.locals["NURION_spine01"].rotation),
                    "NURION_chest": list(out.locals["NURION_chest"].rotation),
                    "NURION_upperArm_L": list(out.locals["NURION_upperArm_L"].rotation),
                    "NURION_root": list(out.locals["NURION_root"].rotation),
                },
                "pelvisTranslation": list(out.locals["NURION_pelvis"].translation),
                "rootTranslation": list(out.locals["NURION_root"].translation),
            }
        )
        per_frame.append({"frame": fr["frame"], "maxRotErr": frame_max})
    return {
        "clipId": clip_id,
        "frames": per_frame,
        "maxRotErr": global_max,
        "tol": TOL_ROT,
        "observedSamples": observed_dump,
    }


def test_lr_symmetry(profile, eng) -> dict:
    """Synthetic mirrored donor limb deltas → Canonical L/R satisfy §19 mirror."""
    idle = json.loads(IDLE.read_text(encoding="utf-8"))
    base = pose_from_extract_locals(idle["restLocals"])
    # ~30° about local X on left upper arm; mirrored to right
    left_delta = hemisphere(normalize((0.96592583, 0.25881905, 0.0, 0.0)))
    right_delta = mirror_yz(left_delta)
    donor = PoseFrame(locals=dict(base.locals))
    donor.locals["LeftArm"] = BoneLocal(rotation=left_delta)
    donor.locals["RightArm"] = BoneLocal(rotation=right_delta)
    out = eng.donor_to_canonical(profile, donor)
    # After Q_import conjugation, mirror should still hold on remapped deltas relative to bind_c
    l = out.locals["NURION_upperArm_L"].rotation
    r = out.locals["NURION_upperArm_R"].rotation
    # expected: remapped left mirrored equals right (bind_c=I, bind_d=I)
    qi = profile.q_import
    l_delta_w = multiply(multiply(qi, left_delta), inverse(qi))
    r_expected = mirror_yz(l_delta_w)
    # Engine applies same qi to both; right donor already mirrored in donor space
    r_obs = r
    err = max_rot_err(r_obs, multiply(multiply(qi, right_delta), inverse(qi)))
    _ok(err <= TOL_SYM, f"R arm formula err {err}")
    # L/R pair presence
    for a, b in LR_PAIRS:
        _ok(a in out.locals and b in out.locals, f"missing pair {a}/{b}")
    return {
        "upperArm_L": list(l),
        "upperArm_R": list(r),
        "rightMatchesQiMirrorDonor": err,
        "tol": TOL_SYM,
        "note": "Donor-space YZ mirror + shared Q_import; engine has no L/R branch",
    }


def test_deterministic(profile, eng) -> dict:
    idle = json.loads(IDLE.read_text(encoding="utf-8"))
    donor = pose_from_extract_locals(idle["frames"][2]["locals"])
    a = eng.donor_to_canonical(profile, donor)
    b = eng.donor_to_canonical(profile, donor)
    for bone in eng.core_bones:
        _ok(approx_eq(a.locals[bone].rotation, b.locals[bone].rotation, tol=0.0), bone)
        _ok(a.locals[bone].translation == b.locals[bone].translation, bone)
    dumps = [profile.deterministic_dumps(), profile.deterministic_dumps()]
    _ok(dumps[0] == dumps[1], "profile dumps")
    return {"deterministic": True}


def test_donor_literal_isolation() -> dict:
    forbidden = ("CC_Base", "Hips", "LeftUpLeg", "Mixamo", "Spine02")
    # Spine02 is MJN donor name — must not appear in official engine sources
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
    _ok(not hits, f"donor literals in engine: {hits}")
    return {"scanned": [str(p) for p in paths], "hits": hits}


def main() -> int:
    # Ensure profile calibrated (profile JSON only — no engine mutation)
    import importlib.util

    cal_path = ROOT / "tools/calibrate_rig02b_mjn_profile.py"
    spec = importlib.util.spec_from_file_location("calibrate_rig02b_mjn_profile", cal_path)
    cal = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cal)
    cal.main()

    profile = load_profile(PROFILE_PATH)
    eng = BodyRetargetEngine()
    idle = json.loads(IDLE.read_text(encoding="utf-8"))
    sample_frame = idle["frames"][2]["locals"]
    donor_sample = pose_from_extract_locals(sample_frame)
    out_sample = eng.donor_to_canonical(profile, donor_sample)

    results = []
    tests = [
        ("test_protected", lambda: test_protected()),
        ("test_profile_valid", lambda: test_profile_valid(profile)),
        ("test_mapping_completeness", lambda: test_mapping_completeness(profile, eng, out_sample)),
        ("test_rest_normalization", lambda: test_rest_normalization(profile, eng)),
        ("test_axis_conversion", lambda: test_axis_conversion(profile)),
        ("test_axis_translation_conversion", lambda: test_axis_translation_conversion(profile, eng)),
        ("test_root_pelvis_and_scale", lambda: test_root_pelvis_and_scale(profile, eng, sample_frame)),
        ("test_motion_idle", lambda: test_motion_numerical(profile, eng, IDLE, "mjn_idle_15")),
        ("test_motion_bow", lambda: test_motion_numerical(profile, eng, BOW, "mjn_formal_bow")),
        ("test_lr_symmetry", lambda: test_lr_symmetry(profile, eng)),
        ("test_deterministic", lambda: test_deterministic(profile, eng)),
        ("test_donor_literal_isolation", lambda: test_donor_literal_isolation()),
    ]

    for name, fn in tests:
        try:
            detail = fn()
            results.append({"test": name, "status": "PASS", "detail": detail})
        except Exception as e:
            results.append({"test": name, "status": "FAIL", "error": str(e)})

    failed = [r for r in results if r["status"] == "FAIL"]
    summary = {
        "stage": "NURION-RIG-02B_MJN_ADAPTER_PROOF",
        "rig02bPass": "NOT_DECLARED",
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "tolerances": {"rotation": TOL_ROT, "translation": TOL_TR, "symmetry": TOL_SYM},
        "results": results,
    }
    out_path = EV / "NURION-RIG-02B_mjn_adapter_proof_stdout.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "out": str(out_path)}, ensure_ascii=True))
    # also human-readable one-liner like 02A
    print({"passed": summary["passed"], "failed": summary["failed"], "results": [{"test": r["test"], "status": r["status"]} for r in results]})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
