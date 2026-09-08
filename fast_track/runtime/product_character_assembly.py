#!/usr/bin/env python3
"""
NURION-PRODUCT-01 — Character Assembly & Runtime Baseline.

Assembles MJN product character onto CLOSED FACE/BODY/RIG-02 SoT.
No new retarget algorithms. No Canonical redesign. Jake product path DENY.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fast_track.runtime.body_retarget_engine import BodyRetargetEngine, BoneLocal, PoseFrame
from fast_track.runtime.donor_skeleton_profile import load_profile
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS, load_core_bones
from fast_track.runtime.retarget.quat import hemisphere, normalize
from fast_track.runtime.retarget_contract_validator import assert_profile_valid

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"

# Repo-relative logical paths only — absolute path storage DENY (P1a)
ASSET_GLB_REL = (
    "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
)
IDLE_FIXTURE_REL = (
    "fast_track/working/meshy_silver_starlight/evidence/rig02b_fixtures/mjn_idle_15_pose_extract.json"
)
# Frozen product baseline asset SHA (WORKING_BASELINE at RIG/PRODUCT freeze)
EXPECTED_ASSET_SHA256 = "a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1"

BASELINE_GLB = ROOT / ASSET_GLB_REL
MJN_PROFILE = SEM / "retarget_profiles/mjn_legacy_profile_v1.json"
JAKE_PROFILE = SEM / "retarget_profiles/jake_cc_profile_v1.json"
IDLE_FIXTURE = ROOT / IDLE_FIXTURE_REL
BODY_SPEC = SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1.json"
BODY_LOCK = SEM / "NURION_BODY_PRODUCT_LOCK_V1.json"
FACE_LOCK = SEM / "NURION_FACE_PRODUCT_LOCK_V1.json"
PRODUCT_BOUNDARY = SEM / "NURION_RIG02_PRODUCT_BOUNDARY_V1.json"
ASSEMBLY_BASELINE_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"
)
ASSEMBLY_BASELINE_PATH = ROOT / ASSEMBLY_BASELINE_REL

FACE_RIG_ROOT = "FACE_Rig_Root"
SOLE_ATTACHMENT = "NURION_head → FACE Rig Root / Face Space"

BODY_OWNS = ("root", "pelvis", "torso", "limbs", "neck", "head_transform")
FACE_OWNS = ("eyes", "eyelids", "jaw", "tongue", "facial_deformation")


class ProductAssemblyError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_logical_repo_path(path: str, *, field: str = "path") -> str:
    """P1a — repo-relative forward-slash path only; absolute storage DENY."""
    if not isinstance(path, str) or not path:
        raise ProductAssemblyError(f"{field}: empty path")
    if "\\" in path:
        raise ProductAssemblyError(f"{field}: backslash DENY — use forward slash: {path!r}")
    if path.startswith("/") or path.startswith("~"):
        raise ProductAssemblyError(f"{field}: absolute path DENY: {path!r}")
    if len(path) >= 2 and path[1] == ":":
        raise ProductAssemblyError(f"{field}: drive-absolute path DENY: {path!r}")
    if Path(path).is_absolute():
        raise ProductAssemblyError(f"{field}: absolute path DENY: {path!r}")
    return path


def canonical_json_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def canonical_json_sha256(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(data)).hexdigest()


def assert_assembly_has_no_absolute_paths(data: dict[str, Any]) -> None:
    """Walk assembly JSON string values for forbidden absolute paths."""
    stack: list[Any] = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, str):
            if "\\" in cur and (":\\" in cur or cur.startswith("\\\\")):
                raise ProductAssemblyError(f"absolute/windows path in assembly: {cur!r}")
            if len(cur) >= 2 and cur[1] == ":" and cur[0].isalpha():
                raise ProductAssemblyError(f"drive-absolute path in assembly: {cur!r}")
            if cur.startswith("/mnt/") or cur.startswith("/home/") or cur.startswith("/Users/"):
                raise ProductAssemblyError(f"absolute unix path in assembly: {cur!r}")


def _q(lst: list[float]):
    return hemisphere(normalize(tuple(float(x) for x in lst)))


def load_raw_profile(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_product_use_allowed(raw_profile: dict[str, Any]) -> None:
    pb = raw_profile.get("product_boundary") or {}
    if pb.get("product_use") is not True:
        raise ProductAssemblyError(
            f"PRODUCT_PATH_DENIED: profile {raw_profile.get('profile_id')} "
            f"product_use={pb.get('product_use')} (product assembly requires true)"
        )


def assert_jake_product_path_blocked() -> dict[str, Any]:
    """Jake may load as reference profile but must never enter product assembly path."""
    raw = load_raw_profile(JAKE_PROFILE)
    pb = raw.get("product_boundary") or {}
    if pb.get("product_use") is not False:
        raise ProductAssemblyError("Jake product_use must be false")
    if pb.get("jake_asset_incorporation") != "DENY":
        raise ProductAssemblyError("Jake asset incorporation must be DENY")
    try:
        assert_product_use_allowed(raw)
        raise ProductAssemblyError("Jake must be rejected by product_use gate")
    except ProductAssemblyError as e:
        if "PRODUCT_PATH_DENIED" not in str(e):
            raise
    return {
        "profile_id": raw.get("profile_id"),
        "product_use": False,
        "productPathBlocked": True,
        "jake_asset_incorporation": pb.get("jake_asset_incorporation"),
    }


def pose_from_extract_locals(locals_map: dict) -> PoseFrame:
    out = {}
    for name, bl in locals_map.items():
        out[name] = BoneLocal(
            rotation=_q(bl["rotation_wxyz"]),
            translation=tuple(float(x) for x in bl.get("translation", (0.0, 0.0, 0.0))),
        )
    return PoseFrame(locals=out)


def serialize_pose(pose: PoseFrame) -> dict[str, Any]:
    keys = sorted(pose.locals.keys())
    out: dict[str, Any] = {}
    for k in keys:
        bl = pose.locals[k]
        out[k] = {
            "rotation_wxyz": [float(x) for x in bl.rotation],
            "translation": [float(x) for x in bl.translation],
        }
    return out


@dataclass
class FaceBodyInterface:
    sole_attachment: str = SOLE_ATTACHMENT
    body_attachment_bone: str = "NURION_head"
    face_rig_root: str = FACE_RIG_ROOT
    body_owns: tuple[str, ...] = BODY_OWNS
    face_owns: tuple[str, ...] = FACE_OWNS
    cross_boundary_ownership_collision: str = "DENY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "soleAttachment": self.sole_attachment,
            "bodyAttachmentBone": self.body_attachment_bone,
            "faceRigRoot": self.face_rig_root,
            "BODY_owns": list(self.body_owns),
            "FACE_owns": list(self.face_owns),
            "crossBoundaryOwnershipCollision": self.cross_boundary_ownership_collision,
            "binding": {
                "parent": self.body_attachment_bone,
                "child": self.face_rig_root,
                "type": "SOLE_ATTACHMENT",
            },
        }

    def validate_against_sot(self) -> None:
        body = json.loads(BODY_SPEC.read_text(encoding="utf-8"))
        fbb = body.get("faceBodyBoundary") or {}
        if fbb.get("soleAttachment") != self.sole_attachment:
            raise ProductAssemblyError(
                f"soleAttachment mismatch: assembly={self.sole_attachment!r} "
                f"sot={fbb.get('soleAttachment')!r}"
            )
        sot_body = tuple(fbb.get("BODY_owns") or ())
        if sot_body != self.body_owns:
            raise ProductAssemblyError(f"BODY_owns mismatch: {sot_body} vs {self.body_owns}")
        # FACE_owns wording may use 'eye' vs 'eyes' in SoT — normalize check via required domains
        sot_face = set(fbb.get("FACE_owns") or ())
        required_face = {"eye", "eyelid", "jaw", "tongue", "facial_deformation"}
        if not required_face.issubset(sot_face):
            raise ProductAssemblyError(f"FACE_owns SoT incomplete: {sot_face}")
        lock = json.loads(BODY_LOCK.read_text(encoding="utf-8"))
        lock_fbb = lock.get("faceBodyBoundary") or {}
        if lock_fbb.get("soleAttachment") != self.sole_attachment:
            raise ProductAssemblyError("BODY product lock soleAttachment mismatch")


@dataclass
class CharacterAssemblyBaseline:
    """Reproducible PRODUCT-01 assembly — runtime baseline (not motion library)."""

    assembly_id: str
    product_donor_profile_id: str
    asset_glb: str
    asset_sha256: str
    unit_scale: float
    armature_world_scale: list[float]
    core_bones: list[str]
    idle_frame_index: int
    idle_canonical_pose: dict[str, Any]
    face_body_interface: dict[str, Any]
    translation_owners: list[str]
    bindings: list[dict[str, Any]]
    runtime_scene: dict[str, Any]
    foundation: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        glb = assert_logical_repo_path(self.asset_glb, field="asset.glb")
        data = {
            "schema": "NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1",
            "assemblyId": self.assembly_id,
            "status": "RUNTIME_BASELINE",
            "productDonorProfileId": self.product_donor_profile_id,
            "asset": {
                "glb": glb,
                "sha256": self.asset_sha256,
                "clip": "mjn_idle_15",
            },
            "scale": {
                "unitScale": self.unit_scale,
                "armatureWorldScale": self.armature_world_scale,
                "normalization": "uniform armature world scale → profile.unit_scale",
            },
            "coreBones": self.core_bones,
            "coreBoneCount": len(self.core_bones),
            "idle": {
                "fixture": assert_logical_repo_path(IDLE_FIXTURE_REL, field="idle.fixture"),
                "frameIndex": self.idle_frame_index,
                "canonicalPose": self.idle_canonical_pose,
            },
            "faceBodyInterface": self.face_body_interface,
            "translationOwners": self.translation_owners,
            "bindings": self.bindings,
            "runtimeScene": self.runtime_scene,
            "foundation": self.foundation,
            "notes": self.notes,
            "scope": {
                "motionLibraryExpansion": "DENY — PRODUCT-02",
                "rigRedesign": "DENY",
                "canonicalMutation": "DENY",
                "jakeProductUse": "DENY",
            },
        }
        assert_assembly_has_no_absolute_paths(data)
        return data

    def deterministic_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json_dict())


def build_mjn_assembly_baseline(*, idle_frame_index: int = 2) -> CharacterAssemblyBaseline:
    """
    MJN asset → Canonical BODY (via CLOSED RIG-02 engine+profile) → FACE/BODY interface
    → runtime scene descriptor → idle baseline drive.
    """
    if not BASELINE_GLB.exists():
        raise ProductAssemblyError(f"missing product GLB: {BASELINE_GLB}")
    if not IDLE_FIXTURE.exists():
        raise ProductAssemblyError(f"missing idle fixture: {IDLE_FIXTURE}")

    raw = load_raw_profile(MJN_PROFILE)
    assert_product_use_allowed(raw)
    profile = load_profile(MJN_PROFILE)
    assert_profile_valid(profile)

    iface = FaceBodyInterface()
    iface.validate_against_sot()

    idle = json.loads(IDLE_FIXTURE.read_text(encoding="utf-8"))
    frames = idle.get("frames") or []
    if idle_frame_index < 0 or idle_frame_index >= len(frames):
        raise ProductAssemblyError(f"idle frame index out of range: {idle_frame_index}")
    donor_pose = pose_from_extract_locals(frames[idle_frame_index]["locals"])

    eng = BodyRetargetEngine()
    core = eng.core_bones
    if len(core) != 23:
        raise ProductAssemblyError(f"Core-23 expected, got {len(core)}")
    canonical = eng.donor_to_canonical(profile, donor_pose)
    missing = [b for b in core if b not in canonical.locals]
    if missing:
        raise ProductAssemblyError(f"missing Core bones after retarget: {missing}")
    extras = sorted(set(canonical.locals) - set(core))
    if extras:
        raise ProductAssemblyError(f"non-Core leakage in canonical pose: {extras}")

    # Ownership: only root/pelvis may carry translation
    for b, bl in canonical.locals.items():
        tr = bl.translation
        mag = abs(tr[0]) + abs(tr[1]) + abs(tr[2])
        if b not in TRANSLATION_OWNERS and mag > 1e-9:
            raise ProductAssemblyError(f"translation ownership violation on {b}: {tr}")

    armature_scale = [float(x) for x in idle.get("armatureWorldScale") or [0.01, 0.01, 0.01]]
    unit_scale = float(getattr(profile, "unit_scale", raw.get("unit_scale", 0.01)))
    if abs(unit_scale - armature_scale[0]) > 1e-9:
        raise ProductAssemblyError(
            f"scale mismatch unit_scale={unit_scale} armature={armature_scale}"
        )
    if not (armature_scale[0] == armature_scale[1] == armature_scale[2]):
        raise ProductAssemblyError(f"non-uniform armature scale: {armature_scale}")

    # Required donor→canonical bindings (no missing / no duplicate non-collapse targets)
    from collections import Counter

    bindings: list[dict[str, Any]] = []
    for e in profile.bone_mapping:
        if e.canonical_bone is None:
            continue
        if e.role in ("HELPER_DROP",):
            continue
        bindings.append(
            {
                "donor": e.donor_bone,
                "canonical": e.canonical_bone,
                "role": e.role,
            }
        )
    covered = {e.canonical_bone for e in profile.bone_mapping if e.canonical_bone}
    for b in core:
        if b not in covered:
            raise ProductAssemblyError(f"Core bone unmapped: {b}")
    role_targets = [
        e.canonical_bone
        for e in profile.bone_mapping
        if e.canonical_bone
        and e.role
        not in ("HELPER_DROP", "ADAPTER_INTERMEDIARY", "COLLAPSE_COMPOUND")
    ]
    dup = [c for c, n in Counter(role_targets).items() if n > 1]
    if dup:
        raise ProductAssemblyError(f"duplicate canonical bindings: {dup}")

    face = iface.to_dict()
    bindings.append(
        {
            "donor": None,
            "canonical": face["bodyAttachmentBone"],
            "role": "FACE_SOLE_ATTACHMENT",
            "child": face["faceRigRoot"],
        }
    )

    asset_sha = _sha256_file(BASELINE_GLB)
    if asset_sha != EXPECTED_ASSET_SHA256:
        raise ProductAssemblyError(
            f"asset SHA drift: actual={asset_sha} expected={EXPECTED_ASSET_SHA256}"
        )
    scene = {
        "nodes": [
            {"id": "ProductRoot", "type": "SCENE_ROOT"},
            {
                "id": "MJN_BodyArmature",
                "type": "DONOR_SKINNED_MESH",
                "asset": ASSET_GLB_REL,
                "unitScale": unit_scale,
            },
            {
                "id": "CanonicalBodyPose",
                "type": "CANONICAL_POSE_DRIVER",
                "coreBones": 23,
                "source": "BodyRetargetEngine.donor_to_canonical(mjn_legacy_v1)",
            },
            {
                "id": FACE_RIG_ROOT,
                "type": "FACE_SPACE",
                "parent": "NURION_head",
                "owns": list(FACE_OWNS),
                "talking": "GO",
            },
        ],
        "edges": [
            {"from": "ProductRoot", "to": "MJN_BodyArmature"},
            {"from": "ProductRoot", "to": "CanonicalBodyPose"},
            {"from": "NURION_head", "to": FACE_RIG_ROOT, "relation": "SOLE_ATTACHMENT"},
        ],
        "idleDrive": {
            "enabled": True,
            "clip": "mjn_idle_15",
            "frameIndex": idle_frame_index,
            "appliesTo": "CanonicalBodyPose",
        },
    }

    return CharacterAssemblyBaseline(
        assembly_id="NURION-PRODUCT-01_MJN_ASSEMBLY_V1",
        product_donor_profile_id=profile.profile_id,
        asset_glb=ASSET_GLB_REL,
        asset_sha256=asset_sha,
        unit_scale=unit_scale,
        armature_world_scale=armature_scale,
        core_bones=list(core),
        idle_frame_index=idle_frame_index,
        idle_canonical_pose=serialize_pose(canonical),
        face_body_interface=face,
        translation_owners=sorted(TRANSLATION_OWNERS),
        bindings=bindings,
        runtime_scene=scene,
        foundation={
            "FACE_PRODUCT_LOCK": "PRESERVE",
            "Eye_Calibration": "PRESERVE",
            "TALKING": "GO / PRESERVE",
            "BODY_Canonical_v1": "CONSUME_ONLY",
            "Axis_Retarget_v1": "CONSUME_ONLY",
            "RIG-01": "CLOSED / PASS / NO_REOPEN",
            "RIG-02": "CLOSED / PASS / NO_REOPEN",
        },
        notes=[
            "PRODUCT-01 assembly baseline — idle only; motion library is PRODUCT-02",
            "Uses CLOSED BodyRetargetEngine + mjn_legacy_v1 profile",
            "Jake product path blocked via product_boundary.product_use",
            "asset.glb is repo-relative logical path (absolute DENY)",
        ],
    )


def load_assembly(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reload_assembly_deterministic(path: Path) -> tuple[dict[str, Any], str, str]:
    """Load twice; return (data, hash1, hash2) of canonical serialization."""
    a = load_assembly(path)
    b = load_assembly(path)
    return a, canonical_json_sha256(a), canonical_json_sha256(b)


__all__ = [
    "ProductAssemblyError",
    "FaceBodyInterface",
    "CharacterAssemblyBaseline",
    "build_mjn_assembly_baseline",
    "assert_jake_product_path_blocked",
    "assert_product_use_allowed",
    "assert_logical_repo_path",
    "assert_assembly_has_no_absolute_paths",
    "canonical_json_bytes",
    "canonical_json_sha256",
    "load_assembly",
    "reload_assembly_deterministic",
    "ASSET_GLB_REL",
    "IDLE_FIXTURE_REL",
    "EXPECTED_ASSET_SHA256",
    "ASSEMBLY_BASELINE_PATH",
    "FACE_RIG_ROOT",
    "SOLE_ATTACHMENT",
]
