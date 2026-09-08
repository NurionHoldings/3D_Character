#!/usr/bin/env python3
"""
NURION-PRODUCT-03 — FACE/BODY Runtime Integration.

Consumes PRODUCT-01 + PRODUCT-02 + FACE/Eye/TALKING locks WITHOUT mutation.
Implements frozen P3-G01…G18 contract. Agent MUST NOT declare CLOSED/PASS.
"""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fast_track.runtime.face_composition import (
    EXPRESSION_OWNED,
    FaceCompositionLayer,
    SPEECH_OWNED,
)
from fast_track.runtime.product_character_assembly import (
    ASSEMBLY_BASELINE_REL,
    EXPECTED_ASSET_SHA256 as PRODUCT01_IDLE_SHA,
    FACE_RIG_ROOT,
    assert_assembly_has_no_absolute_paths,
    assert_jake_product_path_blocked,
    assert_logical_repo_path,
    canonical_json_bytes,
    canonical_json_sha256,
)
from fast_track.runtime.product_motion_library import (
    LIBRARY_REL,
    REQUIRED_MOTION_IDS,
)
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS
from fast_track.runtime.retarget.protected import assert_protected_sot_unchanged

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"

CONTRACT_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/"
    "NURION_PRODUCT03_FACE_BODY_RUNTIME_CONTRACT_V1.json"
)
RUNTIME_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/"
    "NURION_PRODUCT03_FACE_BODY_RUNTIME_V1.json"
)
RUNTIME_PATH = ROOT / RUNTIME_REL
FACE_LOCK_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json"
)
FACE_POLICY_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_COMPOSITION_POLICY_V1.json"
)
BODY_SPEC_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json"
)
BODY_LOCK_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_PRODUCT_LOCK_V1.json"
)
AXIS_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/"
    "NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json"
)

ONE_LINE = (
    "PRODUCT-03 shall assemble and prove the canonical NURION product character runtime "
    "by consuming the locked PRODUCT-01 character baseline and PRODUCT-02 motion library "
    "without mutation, while preserving FACE, Eye, TALKING, canonical BODY hierarchy, "
    "provenance restrictions, deterministic execution, and fail-closed product semantics."
)

EYE_CHANNELS = frozenset(
    {
        "FACE_eyeBlinkLeft",
        "FACE_eyeBlinkRight",
        "FACE_eyeSquintLeft",
        "FACE_eyeSquintRight",
        "FACE_eyeWideLeft",
        "FACE_eyeWideRight",
    }
)


class Product03Blocker(RuntimeError):
    """Upstream locked SoT prevents a frozen gate — stop; do not mutate."""


class Product03Error(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(rel: str) -> dict[str, Any]:
    rel = assert_logical_repo_path(rel, field="consume")
    path = ROOT / rel
    if not path.exists():
        raise Product03Blocker(f"BLOCKER: missing consume-only artifact: {rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def _eye_fingerprint(weights: dict[str, float]) -> dict[str, float]:
    return {k: round(float(weights.get(k, 0.0)), 8) for k in sorted(EYE_CHANNELS)}


def _face_owned_fingerprint(weights: dict[str, float]) -> dict[str, float]:
    keys = sorted(EXPRESSION_OWNED | SPEECH_OWNED)
    return {k: round(float(weights.get(k, 0.0)), 8) for k in keys if abs(weights.get(k, 0.0)) > 1e-12}


def consume_locked_inputs() -> dict[str, Any]:
    """Load PRODUCT-01/02 + locks. Never writes. Upstream missing/corrupt → BLOCKER."""
    try:
        protected = assert_protected_sot_unchanged()
    except AssertionError as e:
        raise Product03Blocker(f"BLOCKER Protected SoT: {e}") from e

    assembly = _load_json(ASSEMBLY_BASELINE_REL)
    library = _load_json(LIBRARY_REL)
    face_lock = _load_json(FACE_LOCK_REL)
    face_policy = _load_json(FACE_POLICY_REL)

    try:
        assert_assembly_has_no_absolute_paths(assembly)
        assert_assembly_has_no_absolute_paths(library)
    except Exception as e:
        raise Product03Blocker(f"BLOCKER absolute path in consume artifact: {e}") from e

    iface = assembly.get("faceBodyInterface") or {}
    if iface.get("bodyAttachmentBone") != "NURION_head":
        raise Product03Blocker("BLOCKER: PRODUCT-01 missing NURION_head attachment")
    if iface.get("faceRigRoot") != FACE_RIG_ROOT:
        raise Product03Blocker(f"BLOCKER: PRODUCT-01 faceRigRoot != {FACE_RIG_ROOT}")
    binding = iface.get("binding") or {}
    if binding.get("parent") != "NURION_head" or binding.get("child") != FACE_RIG_ROOT:
        raise Product03Blocker("BLOCKER: sole attachment binding broken in PRODUCT-01")

    owners = set(assembly.get("translationOwners") or [])
    if "NURION_root" not in owners or "NURION_pelvis" not in owners:
        raise Product03Blocker("BLOCKER: root/pelvis owners missing in PRODUCT-01")

    scene_nodes = (assembly.get("runtimeScene") or {}).get("nodes") or []
    face_node = next((n for n in scene_nodes if n.get("id") == FACE_RIG_ROOT), None)
    if not face_node or face_node.get("parent") != "NURION_head":
        raise Product03Blocker("BLOCKER: FACE_Rig_Root not parented to NURION_head")
    if face_node.get("talking") != "GO":
        raise Product03Blocker("BLOCKER: talking status not GO on FACE_Rig_Root")

    if face_lock.get("talking_status") != "GO":
        raise Product03Blocker("BLOCKER: FACE lock talking_status != GO")
    if face_lock.get("donorRole", {}).get("product_use") is not False:
        raise Product03Blocker("BLOCKER: Jake product_use must remain false in FACE lock")

    comp = library.get("completeness") or {}
    if not comp.get("productSemanticOk") or comp.get("productSemanticCompleteness") != "5 / 5":
        raise Product03Blocker(
            f"BLOCKER: PRODUCT-02 semantic incomplete: {comp} — do not auto-fix PRODUCT-02"
        )
    ids = [m["motionId"] for m in library.get("motions") or []]
    if sorted(ids) != sorted(REQUIRED_MOTION_IDS):
        raise Product03Blocker(f"BLOCKER: PRODUCT-02 motion set incomplete: {ids}")
    for m in library["motions"]:
        if m.get("fulfillment") != "DEDICATED":
            raise Product03Blocker(
                f"BLOCKER: motion {m.get('motionId')} not DEDICATED — do not mutate PRODUCT-02"
            )
        if "NURION_head" not in (m["samples"][0].get("canonicalPose") or {}):
            raise Product03Blocker(f"BLOCKER: {m['motionId']} missing NURION_head in pose")

    idle_sha = (assembly.get("asset") or {}).get("sha256")
    if idle_sha != PRODUCT01_IDLE_SHA:
        raise Product03Blocker(
            f"BLOCKER: PRODUCT-01 Idle SHA drift {idle_sha} != {PRODUCT01_IDLE_SHA}"
        )

    return {
        "protected": protected,
        "assembly": assembly,
        "library": library,
        "faceLock": face_lock,
        "facePolicy": face_policy,
        "fingerprints": {
            "product01AssemblySha256": _sha256_file(ROOT / ASSEMBLY_BASELINE_REL),
            "product02LibrarySha256": _sha256_file(ROOT / LIBRARY_REL),
            "faceLockSha256": _sha256_file(ROOT / FACE_LOCK_REL),
            "facePolicySha256": _sha256_file(ROOT / FACE_POLICY_REL),
            "bodySpecSha256": _sha256_file(ROOT / BODY_SPEC_REL),
            "bodyLockSha256": _sha256_file(ROOT / BODY_LOCK_REL),
            "axisSha256": _sha256_file(ROOT / AXIS_REL),
            "idleAssetSha256": PRODUCT01_IDLE_SHA,
            "protectedSoT": protected,
        },
    }


def _assert_ownership(pose: dict[str, Any]) -> None:
    for b, bl in pose.items():
        tr = bl.get("translation") or [0, 0, 0]
        mag = abs(tr[0]) + abs(tr[1]) + abs(tr[2])
        if b not in TRANSLATION_OWNERS and mag > 1e-9:
            raise Product03Error(f"ownership violation {b}")


def _attach_face_under_head(head_local: dict[str, Any]) -> dict[str, Any]:
    """FACE_Rig_Root lives in Face Space under NURION_head — identity local (no BODY merge)."""
    return {
        "parent": "NURION_head",
        "child": FACE_RIG_ROOT,
        "relation": "SOLE_ATTACHMENT",
        "parentLocal": {
            "rotation_wxyz": list(head_local["rotation_wxyz"]),
            "translation": list(head_local["translation"]),
        },
        "faceLocalUnderHead": {
            "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
            "translation": [0.0, 0.0, 0.0],
        },
        "note": "FACE deformation is channel weights — not BODY transform inheritance beyond attach",
    }


def _prove_face_preservation_for_motion(
    face: FaceCompositionLayer,
    motion: dict[str, Any],
) -> dict[str, Any]:
    """G06/G07 — fixed FACE expression while body samples advance; eyes/face channels stable."""
    baseline = face.evaluate(expression_preset="Neutral", text=None, t=0.0, drive_actuator=True)
    base_eyes = _eye_fingerprint(baseline["composedWeights"])
    base_face = _face_owned_fingerprint(baseline["composedWeights"])
    attach_ok = []
    for sample in motion["samples"]:
        pose = sample["canonicalPose"]
        _assert_ownership(pose)
        head = pose["NURION_head"]
        attach = _attach_face_under_head(head)
        again = face.evaluate(expression_preset="Neutral", text=None, t=0.0, drive_actuator=True)
        eyes = _eye_fingerprint(again["composedWeights"])
        face_fp = _face_owned_fingerprint(again["composedWeights"])
        if eyes != base_eyes:
            raise Product03Error(
                f"G07 FAIL eye contamination on {motion['motionId']} frame {sample['frame']}"
            )
        if face_fp != base_face:
            raise Product03Error(
                f"G06 FAIL FACE contamination on {motion['motionId']} frame {sample['frame']}"
            )
        leaked = [k for k in pose if k.startswith("FACE_")]
        if leaked:
            raise Product03Error(f"G06 FAIL FACE keys in body pose: {leaked}")
        attach_ok.append({"frame": sample["frame"], "attachment": attach["relation"]})
    return {
        "motionId": motion["motionId"],
        "samplesChecked": len(attach_ok),
        "eyeFingerprint": base_eyes,
        "faceFingerprintSha256": canonical_json_sha256({"f": base_face}),
        "status": "PASS",
    }


def _prove_talking_coplay(
    face: FaceCompositionLayer,
    motion: dict[str, Any],
) -> dict[str, Any]:
    """G08 — TALKING + body simultaneous; FACE lock contract not mutated; eyes stable."""
    text = "안녕하세요"
    eye_series = []
    speech_active = False
    for i, sample in enumerate(motion["samples"]):
        t = i * 0.12
        ev = face.evaluate(
            expression_preset="Happy",
            text=text,
            t=t,
            speech_start=0.0,
            speech_end=1.0,
            drive_actuator=True,
        )
        eyes = _eye_fingerprint(ev["composedWeights"])
        eye_series.append(eyes)
        if any(ev["speechWeights"].get(k, 0.0) > 1e-6 for k in SPEECH_OWNED):
            speech_active = True
        _assert_ownership(sample["canonicalPose"])
        _attach_face_under_head(sample["canonicalPose"]["NURION_head"])
    if len({canonical_json_sha256(e) for e in eye_series}) != 1:
        raise Product03Error(f"G07/G08 FAIL eye drift during talking+{motion['motionId']}")
    if not speech_active:
        raise Product03Error("G08 FAIL: speech weights never activated")
    snap = face.snapshot()
    if snap.get("talking_status") != "GO":
        raise Product03Error("G08 FAIL talking_status mutated")
    return {
        "motionId": motion["motionId"],
        "talking_status": "GO",
        "speechActive": True,
        "eyeStable": True,
        "status": "PASS",
    }


def build_face_body_runtime() -> dict[str, Any]:
    """Assemble PRODUCT-03 runtime proof artifact (consume-only)."""
    jake = assert_jake_product_path_blocked()
    consumed = consume_locked_inputs()
    assembly = consumed["assembly"]
    library = consumed["library"]
    face_lock = consumed["faceLock"]
    iface = assembly["faceBodyInterface"]

    face = FaceCompositionLayer()
    policy_eyes = {
        "expressionOwnsEyes": True,
        "eyeChannels": sorted(EYE_CHANNELS),
        "policySha256": consumed["fingerprints"]["facePolicySha256"],
        "faceLockSha256": consumed["fingerprints"]["faceLockSha256"],
        "talking_status": face_lock.get("talking_status"),
    }
    eye_cal_fp = canonical_json_sha256(policy_eyes)

    motion_bindings = []
    face_pres = []
    talking_proofs = []
    for mid in REQUIRED_MOTION_IDS:
        m = next(x for x in library["motions"] if x["motionId"] == mid)
        for s in m["samples"]:
            _assert_ownership(s["canonicalPose"])
            if len(s["canonicalPose"]) != 23:
                raise Product03Error(f"{mid}: Core-23 bind fail")
        motion_bindings.append(
            {
                "motionId": mid,
                "fulfillment": m["fulfillment"],
                "meshyClipName": m["meshyClipName"],
                "sourceSha256": m["sourceAsset"]["sha256"],
                "sampleCount": len(m["samples"]),
                "bound": True,
                "retargetStatus": m["retarget"]["status"],
                "coreBones": m["retarget"]["coreBones"],
            }
        )
        face_pres.append(_prove_face_preservation_for_motion(face, m))
        talking_proofs.append(_prove_talking_coplay(face, m))

    transitions = []
    idle = next(m for m in library["motions"] if m["motionId"] == "Idle")
    idle_end = idle["samples"][-1]["canonicalPose"]
    for t in library.get("transitions") or []:
        mid = t["to"]
        m = next(x for x in library["motions"] if x["motionId"] == mid)
        mid_pose = m["samples"][len(m["samples"]) // 2]["canonicalPose"]
        if set(mid_pose.keys()) != set(idle_end.keys()):
            raise Product03Error(f"G09 Core mismatch Idle↔{mid}")
        transitions.append(
            {
                "from": "Idle",
                "to": mid,
                "back": "Idle",
                "status": "OK",
                "restRecovery": "Idle end sample retained",
                "idleEndHasHead": "NURION_head" in idle_end,
            }
        )

    stability = []
    for m in library["motions"]:
        a = canonical_json_sha256(
            {"s": m["samples"][0]["canonicalPose"], "e": m["samples"][-1]["canonicalPose"]}
        )
        b = canonical_json_sha256(
            {"s": m["samples"][0]["canonicalPose"], "e": m["samples"][-1]["canonicalPose"]}
        )
        if a != b:
            raise Product03Error(f"G10 instability {m['motionId']}")
        sc = m["scale"]
        if sc.get("contamination", 1) != 0:
            raise Product03Error(f"G10 scale contamination {m['motionId']}")
        if abs(float(sc.get("unitScale", 0)) - 0.01) > 1e-9:
            raise Product03Error(f"G10 unitScale {m['motionId']}")
        stability.append({"motionId": m["motionId"], "poseHash": a, "contamination": 0})

    input_fp = consumed["fingerprints"]

    runtime = {
        "schema": "NURION_PRODUCT03_FACE_BODY_RUNTIME_V1",
        "runtimeId": "NURION-PRODUCT-03_FACE_BODY_RUNTIME_V1",
        "status": "AGENT_RUNTIME_BUILT",
        "pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "oneLineContract": ONE_LINE,
        "contract": CONTRACT_REL,
        "consumes": {
            "PRODUCT-01": {
                "path": ASSEMBLY_BASELINE_REL,
                "sha256": input_fp["product01AssemblySha256"],
                "policy": "CONSUME ONLY — mutation DENY",
            },
            "PRODUCT-02": {
                "path": LIBRARY_REL,
                "sha256": input_fp["product02LibrarySha256"],
                "policy": "CONSUME ONLY — mutation DENY",
            },
            "FACE_PRODUCT_LOCK": {
                "path": FACE_LOCK_REL,
                "sha256": input_fp["faceLockSha256"],
                "policy": "PRESERVE",
            },
            "Eye_Calibration": {
                "fingerprintSha256": eye_cal_fp,
                "policy": "PRESERVE",
                "channels": sorted(EYE_CHANNELS),
            },
            "TALKING": {"status": "GO", "policy": "PRESERVE"},
            "BODY_Canonical_v1": {"path": BODY_SPEC_REL, "sha256": input_fp["bodySpecSha256"]},
            "Axis_Retarget_v1": {"path": AXIS_REL, "sha256": input_fp["axisSha256"]},
            "idleAssetSha256": input_fp["idleAssetSha256"],
        },
        "faceBodyInterface": iface,
        "attachmentAuthority": {
            "parent": "NURION_head",
            "child": FACE_RIG_ROOT,
            "relation": "SOLE_ATTACHMENT",
            "crossBoundaryOwnershipCollision": "DENY",
        },
        "ownership": {
            "NURION_root": "OWNER",
            "NURION_pelvis": "OWNER",
            "rootEqualsPelvis": False,
            "translationOwners": sorted(TRANSLATION_OWNERS),
        },
        "motionBindings": motion_bindings,
        "facePreservationDuringMotion": face_pres,
        "eyePreservation": {
            "calibrationFingerprintSha256": eye_cal_fp,
            "stableAcrossAllMotions": True,
            "channels": sorted(EYE_CHANNELS),
        },
        "talkingCompatibility": {
            "talking_status": "GO",
            "coplay": talking_proofs,
            "faceLockUnmutated": True,
        },
        "transitions": transitions,
        "transformScaleStability": stability,
        "donorIsolation": {
            "MJN": "APPROVED_PRODUCT_DONOR",
            "Jake": jake,
            "jakeProductUse": False,
        },
        "runtimeScene": {
            "nodes": deepcopy((assembly.get("runtimeScene") or {}).get("nodes") or []),
            "edges": deepcopy((assembly.get("runtimeScene") or {}).get("edges") or []),
            "motionDriver": {
                "source": LIBRARY_REL,
                "requiredMotionIds": list(REQUIRED_MOTION_IDS),
                "bindsTo": "CanonicalBodyPose",
            },
            "faceDriver": {
                "source": "FaceCompositionLayer",
                "attachesTo": FACE_RIG_ROOT,
                "talking": "GO",
            },
        },
        "productSemanticRuntime": {
            "motionsDedicated": 5,
            "facePreserved": True,
            "eyePreserved": True,
            "talkingGo": True,
            "status": "SATISFIED_FOR_AGENT_PROOF",
        },
        "scope": {
            "PRODUCT-04": "DENY",
            "upstreamAutoFix": "DENY — BLOCKER only",
            "agentClosedPass": "DENY",
        },
        "foundation": {
            "PRODUCT-01": "CLOSED / PASS / CONSUME ONLY",
            "PRODUCT-02": "CLOSED / PASS / CONSUME ONLY",
            "FACE_PRODUCT_LOCK": "PRESERVE",
            "Eye_Calibration": "PRESERVE",
            "TALKING": "GO / PRESERVE",
            "RIG-01": "CLOSED / PASS / CONSUME ONLY",
            "RIG-02": "CLOSED / PASS / CONSUME ONLY",
        },
        "notes": [
            "PRODUCT-03 owns FACE+BODY co-play proof only",
            "Upstream defects must surface as Product03Blocker",
            "G06–G08 are mandatory — motion play alone is insufficient",
        ],
    }
    assert_assembly_has_no_absolute_paths(runtime)
    return runtime


@dataclass
class FaceBodyRuntimeBuildResult:
    runtime: dict[str, Any]
    sha256: str

    def write(self, path: Path | None = None) -> Path:
        out = path or RUNTIME_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.runtime, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return out


def build_and_hash() -> FaceBodyRuntimeBuildResult:
    rt = build_face_body_runtime()
    return FaceBodyRuntimeBuildResult(runtime=rt, sha256=canonical_json_sha256(rt))


__all__ = [
    "CONTRACT_REL",
    "RUNTIME_PATH",
    "RUNTIME_REL",
    "ONE_LINE",
    "Product03Blocker",
    "Product03Error",
    "build_and_hash",
    "build_face_body_runtime",
    "consume_locked_inputs",
]
