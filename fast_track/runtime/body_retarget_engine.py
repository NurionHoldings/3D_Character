#!/usr/bin/env python3
"""
NURION-RIG-02A — Body Retarget Engine public surface.

Official path: fast_track/runtime/body_retarget_engine.py
Single algorithm; donor specifics only via DonorSkeletonProfile.

Donor-specific bone name literals are DENY in this file (audit/test layer owns scanners).
"""

from __future__ import annotations

from dataclasses import dataclass

from fast_track.runtime.donor_skeleton_profile import (
    DonorSkeletonProfile,
    build_canonical_identity_profile,
)
from fast_track.runtime.retarget import engine as _engine_mod
from fast_track.runtime.retarget.engine import BoneLocal, PoseFrame, RetargetEngine
from fast_track.runtime.retarget.quat import approx_eq
from fast_track.runtime.retarget_contract_validator import (
    assert_engine_has_no_donor_literals,
    assert_profile_valid,
    validate_canonical_pose_no_leakage,
)


@dataclass
class PoseErrorMetrics:
    max_rotation_abs_err: float
    max_translation_abs_err: float
    scale_err: float


class BodyRetargetEngine:
    """Facade over RetargetEngine with contract validation hooks."""

    def __init__(self) -> None:
        # Scan internal algorithm module only (no donor-name blacklist literals in this file).
        assert_engine_has_no_donor_literals(_engine_mod)
        self._eng = RetargetEngine()

    @property
    def core_bones(self) -> list[str]:
        return list(self._eng.core_bones)

    def donor_to_canonical(self, profile: DonorSkeletonProfile, donor_pose: PoseFrame) -> PoseFrame:
        assert_profile_valid(profile)
        out = self._eng.donor_to_canonical(profile, donor_pose)  # type: ignore[arg-type]
        validate_canonical_pose_no_leakage(profile, set(out.locals.keys()))
        return out

    def canonical_to_target(self, profile: DonorSkeletonProfile, canonical_pose: PoseFrame) -> PoseFrame:
        assert_profile_valid(profile)
        return self._eng.canonical_to_target(profile, canonical_pose)  # type: ignore[arg-type]

    def identity_self_test(self, tol: float = 1e-4) -> PoseErrorMetrics:
        """
        Canonical Identity Profile → Engine → Canonical Pose
        expected: rotation≈0, translation≈0, scale=0
        """
        profile = build_canonical_identity_profile()
        assert_profile_valid(profile)
        donor = PoseFrame(
            locals={b: BoneLocal(rotation=profile.canonical_bind_local[b]) for b in self.core_bones}
        )
        out = self.donor_to_canonical(profile, donor)
        max_r = 0.0
        max_t = 0.0
        for b in self.core_bones:
            r0 = profile.canonical_bind_local[b]
            r1 = out.locals[b].rotation
            if not approx_eq(r0, r1, tol=tol):
                err = sum(abs(r0[i] - r1[i]) for i in range(4))
                max_r = max(max_r, err)
            t = out.locals[b].translation
            max_t = max(max_t, abs(t[0]) + abs(t[1]) + abs(t[2]))
        return PoseErrorMetrics(max_rotation_abs_err=max_r, max_translation_abs_err=max_t, scale_err=0.0)


__all__ = [
    "BodyRetargetEngine",
    "BoneLocal",
    "PoseFrame",
    "PoseErrorMetrics",
    "RetargetEngine",
]
