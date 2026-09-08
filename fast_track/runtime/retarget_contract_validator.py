#!/usr/bin/env python3
"""
NURION-RIG-02A — Retarget contract validator.

FAIL rules (contract closure — not visual quality):
  - PROTECTED SoT mutation
  - UNKNOWN canonical bone
  - duplicate canonical mapping (unless declared collapse)
  - intermediary leakage
  - twist-as-source
  - global Q_basis
  - root/pelvis ownership collision
  - undeclared collapse
  - non-unit / ambiguous duplicate quaternion storage
"""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass

from fast_track.runtime.donor_skeleton_profile import DonorSkeletonProfile
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS, load_core_bones
from fast_track.runtime.retarget.protected import assert_protected_sot_unchanged
from fast_track.runtime.retarget.quat import Quat, normalize


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: str = "FAIL"


class RetargetContractError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(f"{i.code}: {i.message}" for i in issues))


def _quat_norm(q: Quat) -> float:
    return math.sqrt(sum(c * c for c in q))


def validate_profile(profile: DonorSkeletonProfile) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    core = set(load_core_bones())

    # Q_basis_b required for every Core bone
    if set(profile.q_basis_b.keys()) != core:
        issues.append(
            ValidationIssue(
                "Q_BASIS_B_INCOMPLETE",
                f"q_basis_b must cover all Core bones; missing={core - set(profile.q_basis_b)}",
            )
        )

    # Reject twist-as-source
    if profile.twist_policy.allow_as_core_source:
        issues.append(ValidationIssue("TWIST_AS_SOURCE", "twist_policy.allow_as_core_source must be False"))

    # root/pelvis ownership
    if profile.root_policy.bone != "NURION_root":
        issues.append(ValidationIssue("ROOT_POLICY_BONE", "root_policy.bone must be NURION_root"))
    if profile.pelvis_policy.bone != "NURION_pelvis":
        issues.append(ValidationIssue("PELVIS_POLICY_BONE", "pelvis_policy.bone must be NURION_pelvis"))
    if profile.root_policy.never_merge_with != "NURION_pelvis":
        issues.append(ValidationIssue("ROOT_PELVIS_MERGE", "root must never_merge_with NURION_pelvis"))
    if profile.pelvis_policy.never_merge_with != "NURION_root":
        issues.append(ValidationIssue("ROOT_PELVIS_MERGE", "pelvis must never_merge_with NURION_root"))
    if set(profile.root_policy.owns) & set(profile.pelvis_policy.owns):
        issues.append(
            ValidationIssue(
                "ROOT_PELVIS_OWNERSHIP_COLLISION",
                f"overlapping owns: {set(profile.root_policy.owns) & set(profile.pelvis_policy.owns)}",
            )
        )

    # Mapping checks
    canon_targets: dict[str, list[str]] = {}
    collapse_declared: set[str] = {c.canonical_bone for c in profile.collapse_chains}
    collapse_donors: set[str] = set()
    for c in profile.collapse_chains:
        collapse_donors.update(c.donor_bones_in_order)

    for e in profile.bone_mapping:
        if e.canonical_bone is None:
            if e.role not in ("ADAPTER_INTERMEDIARY", "HELPER_DROP"):
                issues.append(
                    ValidationIssue(
                        "NULL_CANONICAL_ROLE",
                        f"{e.donor_bone} has null canonical but role={e.role}",
                    )
                )
            continue
        if e.canonical_bone not in core:
            issues.append(
                ValidationIssue("UNKNOWN_CANONICAL_BONE", f"{e.donor_bone} → {e.canonical_bone}")
            )
            continue
        canon_targets.setdefault(e.canonical_bone, []).append(e.donor_bone)

        if e.role == "ADAPTER_INTERMEDIARY":
            issues.append(
                ValidationIssue(
                    "INTERMEDIARY_MAPPED",
                    f"intermediary {e.donor_bone} must not map to Canonical",
                )
            )
        if e.role == "COLLAPSE_COMPOUND" and e.canonical_bone not in collapse_declared:
            issues.append(
                ValidationIssue(
                    "UNDECLARED_COLLAPSE",
                    f"{e.donor_bone} marked COLLAPSE but no collapse_chains for {e.canonical_bone}",
                )
            )

    for canon, donors in canon_targets.items():
        if len(donors) > 1:
            # allowed only if all are collapse members for that canon
            if canon not in collapse_declared:
                issues.append(
                    ValidationIssue(
                        "DUPLICATE_CANONICAL_MAPPING",
                        f"{canon} mapped from {donors} without declared collapse",
                    )
                )
            else:
                for d in donors:
                    if d not in collapse_donors and not any(
                        m.donor_bone == d and m.role == "COLLAPSE_COMPOUND" for m in profile.bone_mapping
                    ):
                        # still ok if only collapse donors
                        pass
                non_collapse = [
                    d
                    for d in donors
                    if d not in collapse_donors
                ]
                if non_collapse:
                    issues.append(
                        ValidationIssue(
                            "DUPLICATE_CANONICAL_MAPPING",
                            f"{canon} has non-collapse donors {non_collapse}",
                        )
                    )

    # Intermediaries must be listed and unmapped
    for ib in profile.intermediary_bones:
        mapped = [e for e in profile.bone_mapping if e.donor_bone == ib and e.canonical_bone is not None]
        if mapped:
            issues.append(ValidationIssue("INTERMEDIARY_LEAKAGE", f"{ib} mapped to Canonical"))

    # Collapse common-parent hierarchy must be load-bearing
    if profile.collapse_chains:
        if not profile.donor_parent_of:
            issues.append(
                ValidationIssue(
                    "COLLAPSE_HIERARCHY_REQUIRED",
                    "donor_parent_of required when collapse_chains is non-empty",
                )
            )
        else:
            for ch in profile.collapse_chains:
                try:
                    profile.assert_collapse_chain_hierarchy(ch)
                except ValueError as e:
                    code = "COLLAPSE_COMMON_PARENT_MISMATCH"
                    msg = str(e)
                    if "COLLAPSE_HIERARCHY_REQUIRED" in msg:
                        code = "COLLAPSE_HIERARCHY_REQUIRED"
                    elif "COLLAPSE_HIERARCHY" in msg:
                        code = "COLLAPSE_HIERARCHY"
                    issues.append(ValidationIssue(code, msg))

    # Twist bones must not appear as DIRECT maps to Core
    for tb in profile.twist_policy.donor_twist_bones:
        for e in profile.bone_mapping:
            if e.donor_bone == tb and e.canonical_bone is not None and e.role not in ("HELPER_DROP",):
                issues.append(ValidationIssue("TWIST_AS_SOURCE", f"twist bone {tb} mapped as Core source"))

    # Quaternion unit check
    def check_q(label: str, q: Quat) -> None:
        n = _quat_norm(q)
        if abs(n - 1.0) > 1e-3:
            issues.append(ValidationIssue("NON_UNIT_QUATERNION", f"{label} ||q||={n}"))

    check_q("q_import", profile.q_import)
    for b, q in profile.q_basis_b.items():
        check_q(f"q_basis_b[{b}]", q)

    # Placeholder policy: identity-all Q_basis_b only allowed when flag set
    vals = list(profile.q_basis_b.values())
    all_identity = all(abs(q[0] - 1.0) < 1e-9 and abs(q[1]) + abs(q[2]) + abs(q[3]) < 1e-9 for q in vals)
    if all_identity and not profile.allow_identity_q_basis_placeholders:
        issues.append(
            ValidationIssue(
                "GLOBAL_Q_BASIS_PLACEHOLDER",
                "identical identity Q_basis_b forbidden when allow_identity_q_basis_placeholders=false",
            )
        )

    return issues


def assert_profile_valid(profile: DonorSkeletonProfile) -> None:
    issues = validate_profile(profile)
    fails = [i for i in issues if i.severity == "FAIL"]
    if fails:
        raise RetargetContractError(fails)


def assert_engine_has_no_donor_literals(engine_module) -> None:
    src = inspect.getsource(engine_module)
    forbidden = ("CC_Base", "Hips", "Spine02", "LeftUpLeg", "Mixamo")
    for token in forbidden:
        if token in src:
            raise RetargetContractError(
                [ValidationIssue("DONOR_LITERAL_IN_ENGINE", f"found {token} in engine source")]
            )


def assert_protected() -> dict[str, str]:
    return assert_protected_sot_unchanged()


def validate_canonical_pose_no_leakage(
    profile: DonorSkeletonProfile, canonical_bone_keys: set[str]
) -> None:
    leaks = set(profile.intermediary_bones) & canonical_bone_keys
    if leaks:
        raise RetargetContractError(
            [ValidationIssue("INTERMEDIARY_LEAKAGE", f"Canonical pose contains {leaks}")]
        )
    twists = set(profile.twist_policy.donor_twist_bones) & canonical_bone_keys
    if twists:
        raise RetargetContractError(
            [ValidationIssue("TWIST_AS_SOURCE", f"Canonical pose contains twist keys {twists}")]
        )
    unknown = canonical_bone_keys - set(load_core_bones())
    if unknown:
        raise RetargetContractError(
            [ValidationIssue("UNKNOWN_CANONICAL_BONE", f"pose has non-core keys {unknown}")]
        )
