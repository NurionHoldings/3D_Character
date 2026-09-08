#!/usr/bin/env python3
"""DonorSkeletonProfile — donor-specific data only; algorithms live in RetargetEngine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS, load_core_bones
from fast_track.runtime.retarget.quat import IDENTITY, Quat, from_iterable

MapRole = Literal[
    "DIRECT",
    "DIRECT_SEMANTIC_FORK",
    "DIRECT_FACE_ATTACHMENT",
    "DIRECT_VIA_INTERMEDIARY",
    "COLLAPSE_COMPOUND",
    "VIRTUAL_ROOT",
    "ADAPTER_INTERMEDIARY",
    "HELPER_DROP",
]


@dataclass(frozen=True)
class BoneMapEntry:
    donor_bone: str
    canonical_bone: str | None
    role: MapRole


@dataclass(frozen=True)
class CollapseChain:
    """Donor bones composed into one Canonical bone (Convention §16)."""

    canonical_bone: str
    donor_bones_in_order: tuple[str, ...]
    common_parent_donor: str


@dataclass(frozen=True)
class DonorSkeletonProfile:
    """Data contract for one donor family. Must not embed retarget algorithms."""

    profile_id: str
    display_name: str
    unit_scale_to_meters: float
    q_import: Quat
    # canonical_bone -> Q_basis_b (REQUIRED per mapped Core bone; never one global for all)
    q_basis_by_canonical: dict[str, Quat]
    # canonical_bone -> donor bind local (for rest removal)
    donor_bind_local_by_donor: dict[str, Quat]
    # canonical bind (A-pose) locals — may be identity placeholders until calibrated
    canonical_bind_local: dict[str, Quat]
    bone_maps: tuple[BoneMapEntry, ...]
    collapse_chains: tuple[CollapseChain, ...] = ()
    intermediaries: tuple[str, ...] = ()  # donor bones never emitted as Canonical
    helper_drop: tuple[str, ...] = ()
    twist_donor_bones: tuple[str, ...] = ()  # distribution targets only — never Core sources
    rest_pose_class: str = "UNKNOWN"
    notes: tuple[str, ...] = ()

    def donor_to_canonical_direct(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for e in self.bone_maps:
            if e.canonical_bone and e.role not in ("ADAPTER_INTERMEDIARY", "HELPER_DROP", "COLLAPSE_COMPOUND"):
                out[e.donor_bone] = e.canonical_bone
            elif e.canonical_bone and e.role == "VIRTUAL_ROOT":
                out[e.donor_bone] = e.canonical_bone
        return out

    def collapse_donor_bones(self) -> set[str]:
        s: set[str] = set()
        for ch in self.collapse_chains:
            s.update(ch.donor_bones_in_order)
        return s

    def validate(self) -> None:
        core = set(load_core_bones())
        if set(self.canonical_bind_local.keys()) != core:
            missing = core - set(self.canonical_bind_local.keys())
            extra = set(self.canonical_bind_local.keys()) - core
            raise ValueError(f"canonical_bind_local keys must equal Core23; missing={missing} extra={extra}")
        if set(self.q_basis_by_canonical.keys()) != core:
            raise ValueError("q_basis_by_canonical must define Q_basis_b for every Core bone")
        # Fail if all Q_basis_b are forced identical AND profile claims calibrated diversity —
        # for 02A identity placeholders are allowed, but engine still indexes per bone.
        for e in self.bone_maps:
            if e.role == "ADAPTER_INTERMEDIARY":
                if e.canonical_bone is not None:
                    raise ValueError(f"intermediary {e.donor_bone} must not map to Canonical bone")
                if e.donor_bone not in self.intermediaries:
                    raise ValueError(f"intermediary {e.donor_bone} must be listed in intermediaries")
            if e.role == "HELPER_DROP" and e.canonical_bone is not None:
                raise ValueError(f"helper {e.donor_bone} must drop")
        for ch in self.collapse_chains:
            if ch.canonical_bone not in core:
                raise ValueError(f"collapse target {ch.canonical_bone} not in Core")
            if len(ch.donor_bones_in_order) < 2:
                raise ValueError("collapse chain needs >=2 donor bones")
        for name in TRANSLATION_OWNERS:
            if name not in self.canonical_bind_local:
                raise ValueError("translation owners missing from bind")


def _q(obj: Any) -> Quat:
    if isinstance(obj, (list, tuple)) and len(obj) == 4:
        return from_iterable(obj)
    if obj in (None, "IDENTITY", "identity"):
        return IDENTITY
    raise TypeError(f"invalid quat: {obj!r}")


def profile_from_dict(data: dict[str, Any]) -> DonorSkeletonProfile:
    core = load_core_bones()
    q_basis = {b: _q(data.get("q_basis_by_canonical", {}).get(b, IDENTITY)) for b in core}
    c_bind = {b: _q(data.get("canonical_bind_local", {}).get(b, IDENTITY)) for b in core}
    d_bind = {k: _q(v) for k, v in data.get("donor_bind_local_by_donor", {}).items()}
    maps = tuple(
        BoneMapEntry(
            donor_bone=e["donor_bone"],
            canonical_bone=e.get("canonical_bone"),
            role=e["role"],
        )
        for e in data["bone_maps"]
    )
    collapses = tuple(
        CollapseChain(
            canonical_bone=c["canonical_bone"],
            donor_bones_in_order=tuple(c["donor_bones_in_order"]),
            common_parent_donor=c["common_parent_donor"],
        )
        for c in data.get("collapse_chains", [])
    )
    return DonorSkeletonProfile(
        profile_id=data["profile_id"],
        display_name=data["display_name"],
        unit_scale_to_meters=float(data.get("unit_scale_to_meters", 1.0)),
        q_import=_q(data.get("q_import", IDENTITY)),
        q_basis_by_canonical=q_basis,
        donor_bind_local_by_donor=d_bind,
        canonical_bind_local=c_bind,
        bone_maps=maps,
        collapse_chains=collapses,
        intermediaries=tuple(data.get("intermediaries", [])),
        helper_drop=tuple(data.get("helper_drop", [])),
        twist_donor_bones=tuple(data.get("twist_donor_bones", [])),
        rest_pose_class=str(data.get("rest_pose_class", "UNKNOWN")),
        notes=tuple(data.get("notes", [])),
    )


def load_profile(path: Path) -> DonorSkeletonProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    prof = profile_from_dict(data)
    prof.validate()
    return prof
