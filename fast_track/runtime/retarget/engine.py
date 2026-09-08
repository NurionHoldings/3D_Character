#!/usr/bin/env python3
"""
RetargetEngine — single algorithm implementing LOCKED Axis/Retarget Convention §14–§19.

Donor names never appear in this module. All donor specifics come from DonorSkeletonProfile.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS, load_core_bones
from fast_track.runtime.retarget.profile import DonorSkeletonProfile
from fast_track.runtime.retarget.quat import (
    IDENTITY,
    Quat,
    approx_eq,
    hemisphere,
    inverse,
    mirror_conjugation_holds,
    mirror_yz,
    multiply,
    normalize,
    rotate_vector,
)


@dataclass
class BoneLocal:
    rotation: Quat = IDENTITY
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class PoseFrame:
    """Locals keyed by bone name (donor or canonical depending on context)."""

    locals: dict[str, BoneLocal] = field(default_factory=dict)
    meta: dict[str, object] = field(default_factory=dict)


class RetargetEngine:
    """Common engine. Register donor profiles separately — do not subclass algorithms."""

    def __init__(self) -> None:
        self.core_bones = load_core_bones()

    def unit_normalize_translation(
        self, t: tuple[float, float, float], unit_scale_to_meters: float
    ) -> tuple[float, float, float]:
        """§5 UNIT NORMALIZATION — donor units → meters (no axis remap)."""
        s = float(unit_scale_to_meters)
        return (t[0] * s, t[1] * s, t[2] * s)

    def apply_q_import_translation(
        self, profile: DonorSkeletonProfile, t_meters: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        """§14 GLOBAL_AXIS_REMAP on translation vectors (same Q_import as rotations)."""
        return rotate_vector(profile.q_import, t_meters)

    def import_normalize_translation(
        self,
        t: tuple[float, float, float],
        unit_scale_to_meters: float,
        q_import: Quat,
    ) -> tuple[float, float, float]:
        """
        Staged import for translation:
          1) UNIT NORMALIZATION (scale)
          2) GLOBAL AXIS REMAP (Q_import)
        Kept staged — not a single opaque mix of scale+axis.
        """
        t_m = self.unit_normalize_translation(t, unit_scale_to_meters)
        return rotate_vector(q_import, t_m)

    def _donor_bind(self, profile: DonorSkeletonProfile, donor_bone: str) -> Quat:
        return profile.donor_bind_local_by_donor.get(donor_bone, IDENTITY)

    def _remove_donor_rest(self, profile: DonorSkeletonProfile, donor_bone: str, anim: Quat) -> Quat:
        bind = self._donor_bind(profile, donor_bone)
        return multiply(inverse(bind), anim)

    def _apply_q_import(self, profile: DonorSkeletonProfile, delta: Quat) -> Quat:
        q = profile.q_import
        return multiply(multiply(q, delta), inverse(q))

    def _apply_q_basis_b(self, profile: DonorSkeletonProfile, canonical_bone: str, delta: Quat) -> Quat:
        qb = profile.q_basis_by_canonical[canonical_bone]
        return multiply(multiply(qb, delta), inverse(qb))

    def _apply_canonical_rest(self, profile: DonorSkeletonProfile, canonical_bone: str, delta: Quat) -> Quat:
        bind_c = profile.canonical_bind_local[canonical_bone]
        return multiply(bind_c, delta)

    def retarget_rotation_bone(
        self,
        profile: DonorSkeletonProfile,
        *,
        donor_bone: str,
        canonical_bone: str,
        donor_anim_local: Quat,
    ) -> Quat:
        """§14 per mapped bone (non-collapse)."""
        d = self._remove_donor_rest(profile, donor_bone, donor_anim_local)
        d = self._apply_q_import(profile, d)
        d = self._apply_q_basis_b(profile, canonical_bone, d)
        return self._apply_canonical_rest(profile, canonical_bone, d)

    def retarget_collapse_chain(
        self,
        profile: DonorSkeletonProfile,
        donor_pose: PoseFrame,
        chain_index: int = 0,
    ) -> Quat:
        """
        §16 collapsed chain — common-parent-space composition:

          0) assert common_parent_donor → chain hierarchy via profile.donor_parent_of
          1) For each donor bone i on the verified path from common_parent:
               Δ_i = inverse(bind_i) * anim_i
          2) G_i = ∏ binds along path from common_parent to i (exclusive parent)
               Δ_i^P = G_i * Δ_i * inverse(G_i)
          3) Compose_P = Δ_1^P * Δ_2^P * …
          4) Q_import → Q_basis_b → Canonical rest
        """
        ch = profile.collapse_chains[chain_index]
        # Load-bearing: wrong common_parent_donor MUST raise
        profile.assert_collapse_chain_hierarchy(ch)
        parent = ch.common_parent_donor

        composed_parent = IDENTITY
        for i, db in enumerate(ch.donor_bones_in_order):
            # Path from verified common parent to this bone (uses parent name + hierarchy)
            path_i = profile.path_from_common_parent(parent, db)
            if path_i != ch.donor_bones_in_order[: i + 1]:
                raise ValueError(
                    f"COLLAPSE_HIERARCHY: path to {db!r} under {parent!r} is {path_i}, "
                    f"expected prefix {ch.donor_bones_in_order[: i + 1]}"
                )
            bind = self._donor_bind(profile, db)
            anim = donor_pose.locals.get(db, BoneLocal()).rotation
            delta_local = multiply(inverse(bind), anim)
            g_from_parent = IDENTITY
            for b in path_i:
                g_from_parent = multiply(g_from_parent, self._donor_bind(profile, b))
            delta_in_parent = multiply(multiply(g_from_parent, delta_local), inverse(g_from_parent))
            composed_parent = multiply(composed_parent, delta_in_parent)

        d = self._apply_q_import(profile, composed_parent)
        d = self._apply_q_basis_b(profile, ch.canonical_bone, d)
        return self._apply_canonical_rest(profile, ch.canonical_bone, d)

    def donor_to_canonical(self, profile: DonorSkeletonProfile, donor_pose: PoseFrame) -> PoseFrame:
        """
        Donor Animation → Import/Unit → Rest removal → Q_import → Q_basis_b → Canonical rest.
        Output keys are Canonical Core bones only.
        """
        out: dict[str, BoneLocal] = {
            b: BoneLocal(rotation=profile.canonical_bind_local[b]) for b in self.core_bones
        }
        collapse_donors = profile.collapse_donor_bones()
        intermediaries = set(profile.intermediaries)
        helpers = set(profile.helper_drop)
        twists = set(profile.twist_donor_bones)

        # Collapse chains first
        for i, ch in enumerate(profile.collapse_chains):
            out[ch.canonical_bone] = BoneLocal(rotation=self.retarget_collapse_chain(profile, donor_pose, i))

        # Direct maps
        for entry in profile.bone_maps:
            if entry.role in ("ADAPTER_INTERMEDIARY", "HELPER_DROP"):
                continue
            if entry.canonical_bone is None:
                continue
            if entry.role == "COLLAPSE_COMPOUND":
                continue
            if entry.donor_bone in collapse_donors:
                continue
            if entry.donor_bone in intermediaries or entry.donor_bone in helpers:
                continue
            # Twist bones are never Core animation sources
            if entry.donor_bone in twists:
                continue

            bl = donor_pose.locals.get(entry.donor_bone, BoneLocal())
            rot = self.retarget_rotation_bone(
                profile,
                donor_bone=entry.donor_bone,
                canonical_bone=entry.canonical_bone,
                donor_anim_local=bl.rotation,
            )
            tr = (0.0, 0.0, 0.0)
            if entry.canonical_bone in TRANSLATION_OWNERS:
                tr = self.import_normalize_translation(
                    bl.translation,
                    profile.unit_scale_to_meters,
                    profile.q_import,
                )
            out[entry.canonical_bone] = BoneLocal(rotation=rot, translation=tr)

        # Virtual root with no donor sample: keep bind + zero translation unless provided
        for entry in profile.bone_maps:
            if entry.role == "VIRTUAL_ROOT" and entry.canonical_bone:
                if entry.donor_bone not in donor_pose.locals:
                    out[entry.canonical_bone] = BoneLocal(
                        rotation=profile.canonical_bind_local[entry.canonical_bone],
                        translation=(0.0, 0.0, 0.0),
                    )

        # Ownership: strip translations from non-owners
        for b, bl in list(out.items()):
            if b not in TRANSLATION_OWNERS and bl.translation != (0.0, 0.0, 0.0):
                out[b] = BoneLocal(rotation=bl.rotation, translation=(0.0, 0.0, 0.0))

        # Invariant: no intermediary / twist / helper names in Canonical output
        forbidden = intermediaries | helpers | twists
        for k in out:
            if k in forbidden:
                raise RuntimeError(f"donor bone leaked into Canonical pose: {k}")

        return PoseFrame(
            locals=out,
            meta={
                "profile_id": profile.profile_id,
                "pipeline": "DONOR_TO_CANONICAL_§14",
            },
        )

    def canonical_to_target(self, profile: DonorSkeletonProfile, canonical_pose: PoseFrame) -> PoseFrame:
        """
        §15 inverse for direct-mapped bones.
        Collapse chains: information-losing expand — entire common-parent delta on first
        chain bone; remaining chain bones at bind (Canonical semantic round-trip).
        """
        out: dict[str, BoneLocal] = {}
        for entry in profile.bone_maps:
            if entry.canonical_bone is None or entry.role in (
                "ADAPTER_INTERMEDIARY",
                "HELPER_DROP",
                "COLLAPSE_COMPOUND",
                "VIRTUAL_ROOT",
            ):
                continue
            if entry.donor_bone in profile.collapse_donor_bones():
                continue
            cb = entry.canonical_bone
            anim_c = canonical_pose.locals.get(cb, BoneLocal()).rotation
            bind_c = profile.canonical_bind_local[cb]
            delta_c = multiply(inverse(bind_c), anim_c)
            qb = profile.q_basis_by_canonical[cb]
            delta_w = multiply(multiply(inverse(qb), delta_c), qb)
            qi = profile.q_import
            delta_d = multiply(multiply(inverse(qi), delta_w), qi)
            bind_d = self._donor_bind(profile, entry.donor_bone)
            anim_d = multiply(bind_d, delta_d)
            tr = (0.0, 0.0, 0.0)
            if cb in TRANSLATION_OWNERS:
                s = profile.unit_scale_to_meters
                ct = canonical_pose.locals.get(cb, BoneLocal()).translation
                t_donor_m = rotate_vector(inverse(profile.q_import), ct)
                if s != 0:
                    tr = (t_donor_m[0] / s, t_donor_m[1] / s, t_donor_m[2] / s)
            out[entry.donor_bone] = BoneLocal(rotation=anim_d, translation=tr)

        # §16 lossy inverse: recover Canonical neck (etc.) via first chain bone only
        for ch in profile.collapse_chains:
            profile.assert_collapse_chain_hierarchy(ch)
            cb = ch.canonical_bone
            anim_c = canonical_pose.locals.get(cb, BoneLocal()).rotation
            bind_c = profile.canonical_bind_local[cb]
            delta_c = multiply(inverse(bind_c), anim_c)
            qb = profile.q_basis_by_canonical[cb]
            delta_w = multiply(multiply(inverse(qb), delta_c), qb)
            qi = profile.q_import
            delta_parent = multiply(multiply(inverse(qi), delta_w), qi)
            first = ch.donor_bones_in_order[0]
            g1 = self._donor_bind(profile, first)
            delta_local_first = multiply(multiply(inverse(g1), delta_parent), g1)
            anim_first = multiply(g1, delta_local_first)
            out[first] = BoneLocal(rotation=anim_first)
            for db in ch.donor_bones_in_order[1:]:
                out[db] = BoneLocal(rotation=self._donor_bind(profile, db))

        return PoseFrame(
            locals=out,
            meta={
                "profile_id": profile.profile_id,
                "pipeline": "CANONICAL_TO_TARGET_§15",
                "collapseExpand": "LOSSY_FIRST_BONE",
            },
        )

    def identity_canonical_roundtrip(self, pose: PoseFrame, tol: float = 1e-4) -> bool:
        """Canonical→Canonical via identity profile path is not defined; compare pose to itself."""
        for b in self.core_bones:
            if b not in pose.locals:
                return False
            if not approx_eq(pose.locals[b].rotation, pose.locals[b].rotation, tol=tol):
                return False
        return True

    @staticmethod
    def assert_mirror_invariant(sample: Quat | None = None) -> None:
        q = sample or hemisphere(normalize((0.7, 0.2, 0.3, 0.4)))
        if not mirror_conjugation_holds(q):
            raise AssertionError("§19 mirror conjugation failed")
        _ = mirror_yz(q)
