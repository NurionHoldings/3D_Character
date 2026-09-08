#!/usr/bin/env python3
"""
NURION-RIG-02A — DonorSkeletonProfile public contract surface.

Official path: fast_track/runtime/donor_skeleton_profile.py
Donor names ALLOWED here only. Algorithms DENY.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS, load_core_bones
from fast_track.runtime.retarget.quat import IDENTITY, Quat, hemisphere, normalize

MapRole = Literal[
    "DIRECT",
    "DIRECT_SEMANTIC_FORK",
    "DIRECT_FACE_ATTACHMENT",
    "DIRECT_VIA_INTERMEDIARY",
    "COLLAPSE_COMPOUND",
    "VIRTUAL_ROOT",
    "ADAPTER_INTERMEDIARY",
    "HELPER_DROP",
    "IDENTITY",
]


@dataclass(frozen=True)
class BoneMapEntry:
    donor_bone: str
    canonical_bone: str | None
    role: MapRole


@dataclass(frozen=True)
class CollapseChain:
    canonical_bone: str
    donor_bones_in_order: tuple[str, ...]
    common_parent_donor: str


@dataclass(frozen=True)
class SpaceBasis:
    """Donor/tool space description — remapped via Q_import to Canonical §1."""

    right: str
    up: str
    forward: str
    handedness: str = "right-handed"


@dataclass(frozen=True)
class RestPoseInfo:
    class_name: str  # T_POSE_LIKE | A_POSE | INTERMEDIATE | IDENTITY | UNKNOWN
    notes: str = ""


@dataclass(frozen=True)
class OwnershipPolicy:
    bone: str
    owns: tuple[str, ...]
    never_merge_with: str | None = None


@dataclass(frozen=True)
class TwistPolicy:
    role: str = "DISTRIBUTION_TARGET_NOT_MOTION_SOURCE"
    donor_twist_bones: tuple[str, ...] = ()
    allow_as_core_source: bool = False


@dataclass(frozen=True)
class DonorSkeletonProfile:
    profile_id: str
    display_name: str
    space_basis: SpaceBasis
    unit_scale: float
    rest_pose: RestPoseInfo
    bone_mapping: tuple[BoneMapEntry, ...]
    q_import: Quat
    q_basis_b: dict[str, Quat]  # REQUIRED per Core bone key
    root_policy: OwnershipPolicy
    pelvis_policy: OwnershipPolicy
    intermediary_bones: tuple[str, ...]
    collapse_chains: tuple[CollapseChain, ...]
    twist_policy: TwistPolicy
    donor_bind_local_by_donor: dict[str, Quat]
    canonical_bind_local: dict[str, Quat]
    helper_drop: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    # donor_bone -> parent donor bone (None = root). Required when collapse_chains non-empty.
    donor_parent_of: dict[str, str | None] = field(default_factory=dict)
    # Internal aliases used by engine package
    allow_identity_q_basis_placeholders: bool = True

    # --- compatibility aliases for RetargetEngine package ---
    @property
    def unit_scale_to_meters(self) -> float:
        return self.unit_scale

    @property
    def q_basis_by_canonical(self) -> dict[str, Quat]:
        return self.q_basis_b

    @property
    def bone_maps(self) -> tuple[BoneMapEntry, ...]:
        return self.bone_mapping

    @property
    def intermediaries(self) -> tuple[str, ...]:
        return self.intermediary_bones

    @property
    def twist_donor_bones(self) -> tuple[str, ...]:
        return self.twist_policy.donor_twist_bones

    @property
    def rest_pose_class(self) -> str:
        return self.rest_pose.class_name

    def collapse_donor_bones(self) -> set[str]:
        s: set[str] = set()
        for ch in self.collapse_chains:
            s.update(ch.donor_bones_in_order)
        return s

    def path_from_common_parent(self, common_parent: str, end_bone: str) -> tuple[str, ...]:
        """
        Walk donor_parent_of upward from end_bone until common_parent.
        Returns ordered path (exclusive of parent, inclusive of end): first child … end.
        """
        if not self.donor_parent_of:
            raise ValueError("COLLAPSE_HIERARCHY_REQUIRED: donor_parent_of missing")
        if end_bone == common_parent:
            raise ValueError(
                f"COLLAPSE_HIERARCHY: end_bone {end_bone!r} equals common_parent_donor"
            )
        rev: list[str] = []
        cur: str | None = end_bone
        seen: set[str] = set()
        while cur != common_parent:
            if cur is None:
                raise ValueError(
                    f"COLLAPSE_COMMON_PARENT_MISMATCH: reached armature root before {common_parent!r} "
                    f"while walking from {end_bone!r}"
                )
            if cur in seen:
                raise ValueError(f"COLLAPSE_HIERARCHY: cycle at {cur!r}")
            seen.add(cur)
            if cur not in self.donor_parent_of:
                raise ValueError(f"COLLAPSE_HIERARCHY: missing parent entry for {cur!r}")
            rev.append(cur)
            cur = self.donor_parent_of[cur]
        return tuple(reversed(rev))

    def assert_collapse_chain_hierarchy(self, ch: CollapseChain) -> None:
        """Fail unless common_parent_donor → chain[0] → … → chain[-1] matches donor_parent_of."""
        parent = ch.common_parent_donor
        if not parent:
            raise ValueError("COLLAPSE_COMMON_PARENT_REQUIRED: common_parent_donor missing")
        if not ch.donor_bones_in_order:
            raise ValueError("COLLAPSE_HIERARCHY: empty donor_bones_in_order")
        if not self.donor_parent_of:
            raise ValueError("COLLAPSE_HIERARCHY_REQUIRED: donor_parent_of required for collapse")

        first = ch.donor_bones_in_order[0]
        if self.donor_parent_of.get(first) != parent:
            raise ValueError(
                f"COLLAPSE_COMMON_PARENT_MISMATCH: {first!r} parent is "
                f"{self.donor_parent_of.get(first)!r}, expected common_parent_donor={parent!r}"
            )
        for i in range(1, len(ch.donor_bones_in_order)):
            child = ch.donor_bones_in_order[i]
            expect = ch.donor_bones_in_order[i - 1]
            got = self.donor_parent_of.get(child)
            if got != expect:
                raise ValueError(
                    f"COLLAPSE_HIERARCHY: {child!r} parent is {got!r}, expected {expect!r} "
                    f"(chain under {parent!r})"
                )
        path = self.path_from_common_parent(parent, ch.donor_bones_in_order[-1])
        if path != ch.donor_bones_in_order:
            raise ValueError(
                f"COLLAPSE_HIERARCHY: path from {parent!r} to {ch.donor_bones_in_order[-1]!r} "
                f"is {path}, declared chain is {ch.donor_bones_in_order}"
            )

    def to_json_dict(self) -> dict[str, Any]:
        def qlist(q: Quat) -> list[float]:
            q = hemisphere(normalize(q))
            return [float(q[0]), float(q[1]), float(q[2]), float(q[3])]

        return {
            "schema": "NURION_DONOR_SKELETON_PROFILE_V1",
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "space_basis": asdict(self.space_basis),
            "unit_scale": self.unit_scale,
            "rest_pose": {"class_name": self.rest_pose.class_name, "notes": self.rest_pose.notes},
            "bone_mapping": [
                {
                    "donor_bone": e.donor_bone,
                    "canonical_bone": e.canonical_bone,
                    "role": e.role,
                }
                for e in self.bone_mapping
            ],
            "q_import": qlist(self.q_import),
            "q_basis_b": {k: qlist(v) for k, v in sorted(self.q_basis_b.items())},
            "root_policy": {
                "bone": self.root_policy.bone,
                "owns": list(self.root_policy.owns),
                "never_merge_with": self.root_policy.never_merge_with,
            },
            "pelvis_policy": {
                "bone": self.pelvis_policy.bone,
                "owns": list(self.pelvis_policy.owns),
                "never_merge_with": self.pelvis_policy.never_merge_with,
            },
            "intermediary_bones": list(self.intermediary_bones),
            "collapse_chains": [
                {
                    "canonical_bone": c.canonical_bone,
                    "donor_bones_in_order": list(c.donor_bones_in_order),
                    "common_parent_donor": c.common_parent_donor,
                }
                for c in self.collapse_chains
            ],
            "twist_policy": {
                "role": self.twist_policy.role,
                "donor_twist_bones": list(self.twist_policy.donor_twist_bones),
                "allow_as_core_source": self.twist_policy.allow_as_core_source,
            },
            "donor_bind_local_by_donor": {k: qlist(v) for k, v in sorted(self.donor_bind_local_by_donor.items())},
            "canonical_bind_local": {k: qlist(v) for k, v in sorted(self.canonical_bind_local.items())},
            "donor_parent_of": {k: self.donor_parent_of[k] for k in sorted(self.donor_parent_of.keys())},
            "helper_drop": list(self.helper_drop),
            "notes": list(self.notes),
            "allow_identity_q_basis_placeholders": self.allow_identity_q_basis_placeholders,
        }

    def deterministic_dumps(self) -> str:
        return json.dumps(self.to_json_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _quat_norm(values: tuple[float, float, float, float]) -> float:
    return (values[0] ** 2 + values[1] ** 2 + values[2] ** 2 + values[3] ** 2) ** 0.5


def _q(obj: Any, *, label: str = "quat", unit_tol: float = 1e-3) -> Quat:
    """Parse quaternion: NON_UNIT → FAIL (not auto-normalize). Then hemisphere only."""
    if obj in (None, "IDENTITY", "identity"):
        return IDENTITY
    if isinstance(obj, (list, tuple)) and len(obj) == 4:
        raw = (float(obj[0]), float(obj[1]), float(obj[2]), float(obj[3]))
        n = _quat_norm(raw)
        if abs(n - 1.0) > unit_tol:
            raise ValueError(f"NON_UNIT_QUATERNION: {label} ||q||={n} (FAIL, not auto-normalize)")
        return hemisphere(normalize(raw))
    raise TypeError(f"invalid quat ({label}): {obj!r}")


def profile_from_dict(data: dict[str, Any]) -> DonorSkeletonProfile:
    # Reject illegal global Q_basis field at parse time
    if "q_basis" in data and "q_basis_b" not in data and "q_basis_by_canonical" not in data:
        raise ValueError("GLOBAL_Q_BASIS_FORBIDDEN: use q_basis_b per canonical bone")
    if data.get("q_basis_policy") == "SINGLE_GLOBAL":
        raise ValueError("GLOBAL_Q_BASIS_FORBIDDEN: q_basis_policy=SINGLE_GLOBAL")

    core = load_core_bones()
    core_set = set(core)

    # P1: q_basis_b REQUIRED exact Core-23 keyset — no identity auto-fill in parser
    if "q_basis_b" in data:
        q_basis_src = data["q_basis_b"]
    elif "q_basis_by_canonical" in data:
        q_basis_src = data["q_basis_by_canonical"]
    else:
        raise ValueError("Q_BASIS_B_REQUIRED: missing q_basis_b (REQUIRED for all BODY Core bones)")
    if not isinstance(q_basis_src, dict):
        raise ValueError("Q_BASIS_B_REQUIRED: q_basis_b must be an object/map")
    raw_keys = set(q_basis_src.keys())
    if raw_keys != core_set:
        missing = core_set - raw_keys
        extra = raw_keys - core_set
        raise ValueError(
            f"Q_BASIS_B_INCOMPLETE: q_basis_b keys must equal Core-23; missing={sorted(missing)} extra={sorted(extra)}"
        )
    q_basis = {b: _q(q_basis_src[b], label=f"q_basis_b[{b}]") for b in core}

    if "q_import" not in data:
        raise ValueError("Q_IMPORT_REQUIRED: missing q_import")
    q_import = _q(data["q_import"], label="q_import")

    c_bind_src = data.get("canonical_bind_local") or {}
    # bind may be builder-filled only when explicitly complete; require exact keys if present
    if c_bind_src:
        if set(c_bind_src.keys()) != core_set:
            raise ValueError(
                f"CANONICAL_BIND_INCOMPLETE: keys must equal Core-23; "
                f"missing={sorted(core_set - set(c_bind_src.keys()))}"
            )
        c_bind = {b: _q(c_bind_src[b], label=f"canonical_bind_local[{b}]") for b in core}
    else:
        # Only internal builders should omit this; JSON profiles must include it.
        raise ValueError("CANONICAL_BIND_REQUIRED: missing canonical_bind_local")

    d_bind = {
        k: _q(v, label=f"donor_bind_local_by_donor[{k}]")
        for k, v in (data.get("donor_bind_local_by_donor") or {}).items()
    }

    maps_raw = data.get("bone_mapping") or data.get("bone_maps") or []
    maps = tuple(
        BoneMapEntry(
            donor_bone=e["donor_bone"],
            canonical_bone=e.get("canonical_bone"),
            role=e["role"],
        )
        for e in maps_raw
    )
    collapses = tuple(
        CollapseChain(
            canonical_bone=c["canonical_bone"],
            donor_bones_in_order=tuple(c["donor_bones_in_order"]),
            common_parent_donor=c["common_parent_donor"],
        )
        for c in data.get("collapse_chains", [])
    )
    sb = data.get("space_basis") or {
        "right": "+X",
        "up": "+Y",
        "forward": "+Z",
        "handedness": "right-handed",
    }
    space = SpaceBasis(
        right=str(sb.get("right", "+X")),
        up=str(sb.get("up", "+Y")),
        forward=str(sb.get("forward", "+Z")),
        handedness=str(sb.get("handedness", "right-handed")),
    )
    rp = data.get("rest_pose") or {"class_name": data.get("rest_pose_class", "UNKNOWN"), "notes": ""}
    root = data.get("root_policy") or {
        "bone": "NURION_root",
        "owns": ["world_locomotion", "global_translation", "global_heading"],
        "never_merge_with": "NURION_pelvis",
    }
    pelvis = data.get("pelvis_policy") or {
        "bone": "NURION_pelvis",
        "owns": ["body_com", "hip_sway", "vertical_bounce", "local_pelvic_rotation"],
        "never_merge_with": "NURION_root",
    }
    twist = data.get("twist_policy") or {
        "role": "DISTRIBUTION_TARGET_NOT_MOTION_SOURCE",
        "donor_twist_bones": list(data.get("twist_donor_bones", [])),
        "allow_as_core_source": False,
    }
    return DonorSkeletonProfile(
        profile_id=data["profile_id"],
        display_name=data.get("display_name", data["profile_id"]),
        space_basis=space,
        unit_scale=float(data.get("unit_scale", data.get("unit_scale_to_meters", 1.0))),
        rest_pose=RestPoseInfo(class_name=rp.get("class_name", "UNKNOWN"), notes=rp.get("notes", "")),
        bone_mapping=maps,
        q_import=q_import,
        q_basis_b=q_basis,
        root_policy=OwnershipPolicy(
            bone=root["bone"],
            owns=tuple(root.get("owns", ())),
            never_merge_with=root.get("never_merge_with"),
        ),
        pelvis_policy=OwnershipPolicy(
            bone=pelvis["bone"],
            owns=tuple(pelvis.get("owns", ())),
            never_merge_with=pelvis.get("never_merge_with"),
        ),
        intermediary_bones=tuple(data.get("intermediary_bones") or data.get("intermediaries") or []),
        collapse_chains=collapses,
        twist_policy=TwistPolicy(
            role=twist.get("role", "DISTRIBUTION_TARGET_NOT_MOTION_SOURCE"),
            donor_twist_bones=tuple(twist.get("donor_twist_bones") or []),
            allow_as_core_source=bool(twist.get("allow_as_core_source", False)),
        ),
        donor_bind_local_by_donor=d_bind,
        canonical_bind_local=c_bind,
        helper_drop=tuple(data.get("helper_drop") or []),
        notes=tuple(data.get("notes") or []),
        donor_parent_of={
            str(k): (None if v is None else str(v))
            for k, v in (data.get("donor_parent_of") or {}).items()
        },
        allow_identity_q_basis_placeholders=bool(data.get("allow_identity_q_basis_placeholders", True)),
    )


def load_profile(path: Path) -> DonorSkeletonProfile:
    return profile_from_dict(json.loads(path.read_text(encoding="utf-8")))


def build_canonical_identity_profile() -> DonorSkeletonProfile:
    """Canonical→Canonical identity instrument for RIG-02A/02D."""
    core = load_core_bones()
    maps = tuple(
        BoneMapEntry(donor_bone=b, canonical_bone=b, role="IDENTITY") for b in core
    )
    binds = {b: IDENTITY for b in core}
    return DonorSkeletonProfile(
        profile_id="canonical_identity_v1",
        display_name="NURION Canonical Identity",
        space_basis=SpaceBasis(right="+X", up="+Y", forward="+Z", handedness="right-handed"),
        unit_scale=1.0,
        rest_pose=RestPoseInfo(class_name="IDENTITY", notes="Engine self-instrument"),
        bone_mapping=maps,
        q_import=IDENTITY,
        q_basis_b={b: IDENTITY for b in core},
        root_policy=OwnershipPolicy(
            bone="NURION_root",
            owns=("world_locomotion", "global_translation", "global_heading"),
            never_merge_with="NURION_pelvis",
        ),
        pelvis_policy=OwnershipPolicy(
            bone="NURION_pelvis",
            owns=("body_com", "hip_sway", "vertical_bounce", "local_pelvic_rotation"),
            never_merge_with="NURION_root",
        ),
        intermediary_bones=(),
        collapse_chains=(),
        twist_policy=TwistPolicy(),
        donor_bind_local_by_donor={b: IDENTITY for b in core},
        canonical_bind_local=binds,
        helper_drop=(),
        notes=("RIG-02A identity profile — expected pose/rotation/scale error ≈ 0",),
        allow_identity_q_basis_placeholders=True,
    )


# Re-export translation owners for validators
__all__ = [
    "BoneMapEntry",
    "CollapseChain",
    "DonorSkeletonProfile",
    "SpaceBasis",
    "RestPoseInfo",
    "OwnershipPolicy",
    "TwistPolicy",
    "load_profile",
    "profile_from_dict",
    "build_canonical_identity_profile",
    "TRANSLATION_OWNERS",
]
