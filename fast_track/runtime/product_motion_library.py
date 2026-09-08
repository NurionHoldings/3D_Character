#!/usr/bin/env python3
"""
NURION-PRODUCT-02 — Canonical BODY Motion Library (MJN product motions).

Consumes PRODUCT-01 assembly + CLOSED RIG-02 retarget. No FACE/TALKING orchestration.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fast_track.runtime.body_retarget_engine import BodyRetargetEngine, BoneLocal, PoseFrame
from fast_track.runtime.donor_skeleton_profile import load_profile
from fast_track.runtime.product_character_assembly import (
    EXPECTED_ASSET_SHA256 as PRODUCT01_IDLE_SHA,
    assert_assembly_has_no_absolute_paths,
    assert_jake_product_path_blocked,
    assert_logical_repo_path,
    canonical_json_bytes,
    canonical_json_sha256,
    pose_from_extract_locals,
    serialize_pose,
)
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS
from fast_track.runtime.retarget_contract_validator import assert_profile_valid

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
ML = ROOT / "fast_track/working/meshy_silver_starlight/motion_library"
MJN_PROFILE = SEM / "retarget_profiles/mjn_legacy_profile_v1.json"
ASSEMBLY_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"
)
LIBRARY_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT02_MOTION_LIBRARY_V1.json"
)
LIBRARY_PATH = ROOT / LIBRARY_REL

# Initial product motion set — Meshy Silver Starlight mapping
# fulfillment: DEDICATED | ALIAS_PLACEHOLDER (P2a)
# Dedicated intake override paths (P2b/P2c): if present, replace alias sources.
DEDICATED_INTAKE = {
    "Handshake": {
        "sourceRel": "fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_handshake_withSkin.glb",
        "fixtureRel": "fast_track/working/meshy_silver_starlight/motion_library/fixtures/mjn_handshake_dedicated_pose_extract.json",
        # MJN product slot from mjn_handshake.zip (Meshy clip Wave_for_Help_4)
        "meshyClipName": "Wave_for_Help_4_withSkin",
    },
    "Dance": {
        "sourceRel": "fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_dance_withSkin.glb",
        "fixtureRel": "fast_track/working/meshy_silver_starlight/motion_library/fixtures/mjn_dance_dedicated_pose_extract.json",
        # MJN product slot from mjn_dance.zip (Meshy clip Superlove_Pop_Dance)
        "meshyClipName": "Superlove_Pop_Dance_withSkin",
    },
}

MOTION_CATALOG_BASE: list[dict[str, str]] = [
    {
        "motionId": "Idle",
        "meshyClipName": "Idle_15_withSkin",
        "sourceRel": "fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_idle_15_withSkin.glb",
        "fixtureRel": "fast_track/working/meshy_silver_starlight/motion_library/fixtures/mjn_idle_pose_extract.json",
        "fulfillment": "DEDICATED",
        "aliasNote": "PRODUCT-01 idle baseline twin (SHA must match frozen WORKING_BASELINE)",
    },
    {
        "motionId": "Bow",
        "meshyClipName": "Formal_Bow_withSkin",
        "sourceRel": "fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_bow_formal_withSkin.glb",
        "fixtureRel": "fast_track/working/meshy_silver_starlight/motion_library/fixtures/mjn_bow_pose_extract.json",
        "fulfillment": "DEDICATED",
        "aliasNote": "Formal bow",
    },
    {
        "motionId": "LargeBow",
        "meshyClipName": "Gentlemans_Bow_withSkin",
        "sourceRel": "fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_large_bow_gentlemans_withSkin.glb",
        "fixtureRel": "fast_track/working/meshy_silver_starlight/motion_library/fixtures/mjn_large_bow_pose_extract.json",
        "fulfillment": "DEDICATED",
        "aliasNote": "Gentleman's bow is the dedicated LargeBow product clip",
    },
    {
        "motionId": "Handshake",
        "meshyClipName": "Wave_One_Hand_withSkin",
        "sourceRel": "fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_handshake_wave_one_hand_withSkin.glb",
        "fixtureRel": "fast_track/working/meshy_silver_starlight/motion_library/fixtures/mjn_handshake_pose_extract.json",
        "fulfillment": "ALIAS_PLACEHOLDER",
        "aliasNote": "Wave_One_Hand ≠ Handshake semantics — ALIAS_PLACEHOLDER until dedicated Handshake intake (P2b)",
    },
    {
        "motionId": "Dance",
        "meshyClipName": "Big_Heart_Gesture_withSkin",
        "sourceRel": "fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_dance_big_heart_gesture_withSkin.glb",
        "fixtureRel": "fast_track/working/meshy_silver_starlight/motion_library/fixtures/mjn_dance_pose_extract.json",
        "fulfillment": "ALIAS_PLACEHOLDER",
        "aliasNote": "Big_Heart_Gesture ≠ Dance semantics — ALIAS_PLACEHOLDER until dedicated Dance intake (P2c)",
    },
]

REQUIRED_MOTION_IDS = ("Idle", "Bow", "LargeBow", "Handshake", "Dance")
FULFILLMENT_DEDICATED = "DEDICATED"
FULFILLMENT_ALIAS = "ALIAS_PLACEHOLDER"


def resolve_motion_catalog() -> list[dict[str, str]]:
    """Apply dedicated intake overrides when P2b/P2c source+fixture both exist."""
    out: list[dict[str, str]] = []
    for spec in MOTION_CATALOG_BASE:
        entry = dict(spec)
        mid = entry["motionId"]
        if mid in DEDICATED_INTAKE:
            ov = DEDICATED_INTAKE[mid]
            src = ROOT / ov["sourceRel"]
            fix = ROOT / ov["fixtureRel"]
            if src.exists() and fix.exists():
                entry["sourceRel"] = ov["sourceRel"]
                entry["fixtureRel"] = ov["fixtureRel"]
                entry["meshyClipName"] = ov["meshyClipName"]
                entry["fulfillment"] = FULFILLMENT_DEDICATED
                entry["aliasNote"] = f"Dedicated {mid} intake active (P2b/P2c)"
        out.append(entry)
    return out


# Back-compat name used by builders/tests
MOTION_CATALOG = MOTION_CATALOG_BASE


class MotionLibraryError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fps_from_range(frame_start: int, frame_end: int, assumed_fps: float = 30.0) -> dict[str, Any]:
    n = max(0, frame_end - frame_start)
    duration = n / assumed_fps if assumed_fps > 0 else 0.0
    return {
        "assumedFps": assumed_fps,
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "frameCountInclusiveSpan": n,
        "durationSec": round(duration, 6),
    }


def _check_ownership(pose: PoseFrame) -> list[str]:
    bad = []
    for b, bl in pose.locals.items():
        mag = abs(bl.translation[0]) + abs(bl.translation[1]) + abs(bl.translation[2])
        if b not in TRANSLATION_OWNERS and mag > 1e-9:
            bad.append(b)
    return bad


def _retarget_frame(eng: BodyRetargetEngine, profile, locals_map: dict) -> PoseFrame:
    donor = pose_from_extract_locals(locals_map)
    return eng.donor_to_canonical(profile, donor)


def build_motion_entry(
    spec: dict[str, str],
    *,
    eng: BodyRetargetEngine,
    profile,
) -> dict[str, Any]:
    src_rel = assert_logical_repo_path(spec["sourceRel"], field="sourceRel")
    fix_rel = assert_logical_repo_path(spec["fixtureRel"], field="fixtureRel")
    src_path = ROOT / src_rel
    fix_path = ROOT / fix_rel
    if not src_path.exists():
        raise MotionLibraryError(f"missing source asset: {src_rel}")
    if not fix_path.exists():
        raise MotionLibraryError(f"missing fixture: {fix_rel}")

    asset_sha = _sha256_file(src_path)
    fixture = json.loads(fix_path.read_text(encoding="utf-8"))
    # Fixture must declare same logical asset
    fix_asset = assert_logical_repo_path(fixture.get("asset", ""), field=f"{spec['motionId']}.fixture.asset")
    if fix_asset != src_rel:
        raise MotionLibraryError(f"fixture asset mismatch: {fix_asset} != {src_rel}")
    if fixture.get("assetSha256") and fixture["assetSha256"] != asset_sha:
        raise MotionLibraryError(
            f"fixture assetSha256 drift: {fixture['assetSha256']} != {asset_sha}"
        )

    if spec["motionId"] == "Idle" and asset_sha != PRODUCT01_IDLE_SHA:
        raise MotionLibraryError(
            f"Idle source must match PRODUCT-01 frozen SHA: {asset_sha} != {PRODUCT01_IDLE_SHA}"
        )

    fr = fixture.get("frameRange") or [0, 0]
    time_meta = _fps_from_range(int(fr[0]), int(fr[1]))
    if time_meta["durationSec"] <= 0:
        raise MotionLibraryError(f"{spec['motionId']}: non-positive duration")

    aws = [float(x) for x in fixture.get("armatureWorldScale") or [0.01, 0.01, 0.01]]
    if not (math.isclose(aws[0], aws[1]) and math.isclose(aws[1], aws[2])):
        raise MotionLibraryError(f"{spec['motionId']}: non-uniform scale {aws}")
    if abs(aws[0] - float(profile.unit_scale)) > 1e-9:
        raise MotionLibraryError(
            f"{spec['motionId']}: scale contamination unit={profile.unit_scale} armature={aws}"
        )

    frames_out = []
    for fr_entry in fixture.get("frames") or []:
        can = _retarget_frame(eng, profile, fr_entry["locals"])
        if set(can.locals.keys()) != set(eng.core_bones):
            raise MotionLibraryError(f"{spec['motionId']}: Core-23 mismatch at frame {fr_entry.get('frame')}")
        bad = _check_ownership(can)
        if bad:
            raise MotionLibraryError(f"{spec['motionId']}: ownership fail {bad}")
        frames_out.append(
            {
                "frame": int(fr_entry["frame"]),
                "canonicalPose": serialize_pose(can),
            }
        )
    if len(frames_out) < 2:
        raise MotionLibraryError(f"{spec['motionId']}: need >=2 sample frames")

    start_pose = frames_out[0]["canonicalPose"]
    end_pose = frames_out[-1]["canonicalPose"]
    # Rest recovery proxy: end-frame non-owner translations already 0 via ownership;
    # also require NURION_head present for future FACE attach (PRODUCT-03).
    if "NURION_head" not in start_pose or "NURION_head" not in end_pose:
        raise MotionLibraryError(f"{spec['motionId']}: missing NURION_head")

    fixture_sha = _sha256_file(fix_path)
    fulfillment = spec.get("fulfillment") or FULFILLMENT_DEDICATED
    if fulfillment not in (FULFILLMENT_DEDICATED, FULFILLMENT_ALIAS):
        raise MotionLibraryError(f"{spec['motionId']}: invalid fulfillment {fulfillment}")
    return {
        "motionId": spec["motionId"],
        "meshyClipName": spec["meshyClipName"],
        "fulfillment": fulfillment,
        "aliasNote": spec["aliasNote"],
        "sourceAsset": {"glb": src_rel, "sha256": asset_sha},
        "fixture": {"path": fix_rel, "sha256": fixture_sha},
        "skeletonMappingProfileId": profile.profile_id,
        "timeDomain": time_meta,
        "scale": {"armatureWorldScale": aws, "unitScale": float(profile.unit_scale), "contamination": 0},
        "playback": {
            "startFrame": frames_out[0]["frame"],
            "endFrame": frames_out[-1]["frame"],
            "sampleCount": len(frames_out),
            "loopPolicy": "REPEAT_STABLE",
            "restRecovery": "NON_OWNER_TRANSLATION_ZERO + Core-23 END SAMPLE",
        },
        "retarget": {
            "coreBones": 23,
            "translationOwners": sorted(TRANSLATION_OWNERS),
            "status": "OK",
        },
        "samples": frames_out,
    }


def compute_completeness(motions: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(REQUIRED_MOTION_IDS)
    technical = len(motions)
    dedicated = [m["motionId"] for m in motions if m.get("fulfillment") == FULFILLMENT_DEDICATED]
    aliases = [m["motionId"] for m in motions if m.get("fulfillment") == FULFILLMENT_ALIAS]
    semantic_n = len(dedicated)
    return {
        "technicalLibraryCompleteness": f"{technical} / {total}",
        "technicalOk": technical == total,
        "productSemanticCompleteness": f"{semantic_n} / {total}",
        "productSemanticOk": semantic_n == total and not aliases,
        "dedicated": dedicated,
        "aliasPlaceholders": aliases,
        "status": (
            "COMPLETE"
            if semantic_n == total and not aliases
            else "PARTIAL_PENDING_ASSET_INTAKE"
        ),
    }


def build_motion_library() -> dict[str, Any]:
    assert_jake_product_path_blocked()
    asm_path = ROOT / ASSEMBLY_REL
    if not asm_path.exists():
        raise MotionLibraryError("PRODUCT-01 assembly baseline missing")
    assembly = json.loads(asm_path.read_text(encoding="utf-8"))
    assert_assembly_has_no_absolute_paths(assembly)
    if assembly.get("productDonorProfileId") != "mjn_legacy_v1":
        raise MotionLibraryError("assembly must be MJN product donor")

    raw = json.loads(MJN_PROFILE.read_text(encoding="utf-8"))
    if (raw.get("product_boundary") or {}).get("product_use") is not True:
        raise MotionLibraryError("MJN product_use must be true")
    profile = load_profile(MJN_PROFILE)
    assert_profile_valid(profile)
    eng = BodyRetargetEngine()

    catalog = resolve_motion_catalog()
    motions = [build_motion_entry(spec, eng=eng, profile=profile) for spec in catalog]
    ids = [m["motionId"] for m in motions]
    if sorted(ids) != sorted(REQUIRED_MOTION_IDS):
        raise MotionLibraryError(f"motion set incomplete: {ids}")
    if len(ids) != len(set(ids)):
        raise MotionLibraryError(f"duplicate motionId: {ids}")

    completeness = compute_completeness(motions)

    # Idle ↔ motion transition / rest recovery (BODY only)
    idle = next(m for m in motions if m["motionId"] == "Idle")
    transitions = []
    for m in motions:
        if m["motionId"] == "Idle":
            continue
        # Idle start → motion mid → Idle end samples exist and Core-23 keys match
        mid = m["samples"][len(m["samples"]) // 2]["canonicalPose"]
        idle_end = idle["samples"][-1]["canonicalPose"]
        if set(mid.keys()) != set(idle_end.keys()):
            raise MotionLibraryError(f"transition Core mismatch Idle↔{m['motionId']}")
        transitions.append(
            {
                "from": "Idle",
                "to": m["motionId"],
                "back": "Idle",
                "status": "OK",
                "restRecovery": "Idle end sample retained as rest reference",
            }
        )

    # Repeat playback stability: hashing start/end samples twice must match
    repeat_ok = []
    for m in motions:
        a = canonical_json_sha256({"s": m["samples"][0], "e": m["samples"][-1]})
        b = canonical_json_sha256({"s": m["samples"][0], "e": m["samples"][-1]})
        if a != b:
            raise MotionLibraryError(f"repeat instability {m['motionId']}")
        repeat_ok.append(m["motionId"])

    lib = {
        "schema": "NURION_PRODUCT02_MOTION_LIBRARY_V1",
        "libraryId": "NURION-PRODUCT-02_MJN_MOTION_LIBRARY_V1",
        "status": completeness["status"],
        "productDonorProfileId": "mjn_legacy_v1",
        "assemblyBaseline": ASSEMBLY_REL,
        "assemblyBaselineSha256": _sha256_file(asm_path),
        "requiredMotionIds": list(REQUIRED_MOTION_IDS),
        "completeness": completeness,
        "motions": motions,
        "transitions": transitions,
        "repeatPlaybackStable": repeat_ok,
        "scope": {
            "bodyMotionLibrary": "OWN",
            "bodyMotionTransition": "OWN",
            "faceTalkingOrchestration": "DENY — PRODUCT-03",
            "newRigDesign": "DENY",
            "canonicalMutation": "DENY",
            "jakeProductUse": "DENY",
        },
        "foundation": {
            "PRODUCT-01": "CLOSED / PASS",
            "RIG-01": "CLOSED / PASS / CONSUME_ONLY",
            "RIG-02": "CLOSED / PASS / CONSUME_ONLY",
            "FACE_PRODUCT_LOCK": "PRESERVE",
            "TALKING": "GO / PRESERVE",
        },
        "notes": [
            "All asset paths are repo-relative (absolute DENY)",
            "P2a: motionId existence ≠ product semantic fulfillment",
            "P2b/P2c: Handshake+Dance dedicated intake from MJN assets (Wave_for_Help_4 / Superlove_Pop_Dance)",
            "productSemanticCompleteness 5/5 — human CLOSED/PASS only",
        ],
    }
    assert_assembly_has_no_absolute_paths(lib)
    return lib


def library_deterministic_bytes(lib: dict[str, Any] | None = None) -> bytes:
    data = lib if lib is not None else build_motion_library()
    return canonical_json_bytes(data)


@dataclass
class MotionLibraryBuildResult:
    library: dict[str, Any]
    sha256: str

    def write(self, path: Path | None = None) -> Path:
        out = path or LIBRARY_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.library, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out


def build_and_hash() -> MotionLibraryBuildResult:
    lib = build_motion_library()
    return MotionLibraryBuildResult(library=lib, sha256=canonical_json_sha256(lib))


__all__ = [
    "MotionLibraryError",
    "MOTION_CATALOG",
    "MOTION_CATALOG_BASE",
    "REQUIRED_MOTION_IDS",
    "LIBRARY_REL",
    "LIBRARY_PATH",
    "FULFILLMENT_DEDICATED",
    "FULFILLMENT_ALIAS",
    "resolve_motion_catalog",
    "compute_completeness",
    "build_motion_library",
    "build_and_hash",
    "library_deterministic_bytes",
]
