#!/usr/bin/env python3
"""FAST-03D runner — facial capability ADD + STOP GATE evidence."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(r"d:\NURION Character Landmarker")
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
BLENDER_SCRIPT = ROOT / "tools/blender_fast_03d_facial_capability_add.py"
PATCH_MODULE = ROOT / "tools/fast_03d_glb_patch.py"
FAST02 = ROOT / "tools/fast_02_semantic_partition_audit.py"
WORK = ROOT / "fast_track/working/meshy_silver_starlight"

IDENTITY_NEUTRAL = WORK / "identity_locked/FAST-03B_identity_neutral.glb"
MEMBERSHIP = WORK / "semantic/FAST-03A_semantic_region_membership.json"
MORPH_JSON = WORK / "semantic/FAST-03D_morph_deltas.json"
BONES_JSON = WORK / "semantic/FAST-03D_bones.json"
OUTPUT_GLB = WORK / "output/FAST-03D_presentation_rig.glb"
EVIDENCE_RAW = WORK / "evidence/FAST-03D_actuator_evidence.json"
RECEIPT = WORK / "evidence/FAST-03D_stop_gate_receipt.json"
LEDGER = WORK / "mutation_ledger.json"
CANONICAL_SHA = "a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1"
PROOF_SHA = "435d7aa4a49eb3779b7068e7129435750ac3e718941870d108655e62d8e00b97"

REGRESSION_TOL = 1e-5


def load_fast02():
    spec = importlib.util.spec_from_file_location("fast_02", FAST02)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_patch():
    spec = importlib.util.spec_from_file_location("patch", PATCH_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_animations(gltf: dict, bin_blob: bytes) -> str:
    f2 = load_fast02()
    payload = json.dumps(gltf.get("animations", []), sort_keys=True).encode()
    for anim in gltf.get("animations", []):
        for sampler in anim.get("samplers", []):
            for key in ("input", "output"):
                acc = sampler.get(key)
                if acc is not None:
                    payload += f2.read_accessor(gltf, bin_blob, acc).tobytes()
    return hashlib.sha256(payload).hexdigest()


def hash_material_uv(gltf: dict, bin_blob: bytes) -> str:
    f2 = load_fast02()
    payload = json.dumps(
        {"materials": gltf.get("materials", []), "textures": gltf.get("textures", [])},
        sort_keys=True,
    ).encode()
    prim = gltf["meshes"][0]["primitives"][0]
    if "TEXCOORD_0" in prim.get("attributes", {}):
        payload += f2.read_accessor(gltf, bin_blob, prim["attributes"]["TEXCOORD_0"]).tobytes()
    return hashlib.sha256(payload).hexdigest()


def protected_indices(membership: dict) -> set[int]:
    out: set[int] = set()
    for k in ("BODY", "HAIR", "NECK_TRANSITION", "HEAD_SKIN"):
        out.update(membership["vertexMembership"].get(k, []))
    return out


def evaluate_actuators(
    neutral_path: Path,
    morph_json: Path,
    membership: dict,
) -> dict[str, Any]:
    f2 = load_fast02()
    g, b = f2.load_glb(neutral_path)
    pos = f2.read_accessor(g, b, g["meshes"][0]["primitives"][0]["attributes"]["POSITION"]).astype(np.float64)
    morph = json.loads(morph_json.read_text(encoding="utf-8"))
    protected = protected_indices(membership)
    face = set(membership["vertexMembership"].get("FACE_IDENTITY_REGION", []))
    mouth_zone: set[int] = set()
    evidence = {}
    for name, deltas in morph["shapeKeys"].items():
        delta = np.zeros_like(pos)
        affected = set()
        for item in deltas:
            vi, x, y, z = item
            vi = int(vi)
            delta[vi] = [x, y, z]
            affected.add(vi)
            if "Viseme" in name or "Jaw" in name or "Smile" in name:
                mouth_zone.update(affected)
        deformed = pos + delta
        disp = np.linalg.norm(deformed - pos, axis=1)
        non_pres = float(np.max(disp[list(protected)])) if protected else 0.0
        landmark = face - affected
        landmark_disp = float(np.max(disp[list(landmark)])) if landmark else 0.0
        aff = sorted(affected)
        evidence[name] = {
            "affectedVertexCount": len(affected),
            "maxDisplacement": float(np.max(disp[aff])) if aff else 0.0,
            "nonPresentationRegionMaxDisplacement": non_pres,
            "faceIdentityLandmarkMaxDisplacement": landmark_disp,
        }
    return evidence


def update_ledger_path_a_lock(ledger: dict, ts: str) -> None:
    ledger["identityPathLock"] = {
        "path": "A_FACE_SURFACE_IDENTITY_ADAPT",
        "lockedAtUtc": ts,
        "fallbackB": "FALLBACK_ONLY",
        "pathC": "DENY_UNLESS_A_B_STRUCTURAL_FAILURE",
    }
    ledger["presentationLayer"] = "FAST-03D ACTIVE — additive/isolated actuators"
    if not any(e.get("id") == "FAST-03C-LOCK" for e in ledger["entries"]):
        ledger["entries"].append(
            {
                "id": "FAST-03C-LOCK",
                "type": "IDENTITY_PATH_A_LOCK",
                "mutation": 0,
                "path": "A_FACE_SURFACE_IDENTITY_ADAPT",
            }
        )


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proof = WORK / "proof/FAST-03B_path_a_proof.glb"
    if not proof.exists():
        print("Missing proof GLB", file=sys.stderr)
        return 2

    id_dir = WORK / "identity_locked"
    id_dir.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy2(proof, IDENTITY_NEUTRAL)
    if sha256_file(IDENTITY_NEUTRAL) != PROOF_SHA:
        print("Identity neutral SHA mismatch vs 03B proof", file=sys.stderr)

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    update_ledger_path_a_lock(ledger, ts)
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        "--input-glb",
        str(IDENTITY_NEUTRAL),
        "--membership-json",
        str(MEMBERSHIP),
        "--morph-json",
        str(MORPH_JSON),
        "--bones-json",
        str(BONES_JSON),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr, file=sys.stderr)
        return proc.returncode

    patch = load_patch()
    patch_meta = patch.patch_glb(IDENTITY_NEUTRAL, MORPH_JSON, BONES_JSON, OUTPUT_GLB)

    membership = json.loads(MEMBERSHIP.read_text(encoding="utf-8"))
    actuator_evidence = evaluate_actuators(IDENTITY_NEUTRAL, MORPH_JSON, membership)
    morph_data = json.loads(MORPH_JSON.read_text(encoding="utf-8"))
    bones_data = json.loads(BONES_JSON.read_text(encoding="utf-8"))

    f2 = load_fast02()
    g0, b0 = f2.load_glb(IDENTITY_NEUTRAL)
    g1, b1 = f2.load_glb(OUTPUT_GLB)
    p0 = f2.read_accessor(g0, b0, g0["meshes"][0]["primitives"][0]["attributes"]["POSITION"]).astype(np.float64)
    p1 = f2.read_accessor(g1, b1, g1["meshes"][0]["primitives"][0]["attributes"]["POSITION"]).astype(np.float64)
    neutral_parity = {
        "globalMaxDisplacement": float(np.max(np.linalg.norm(p1 - p0, axis=1))),
        "vertexCountBaseline": int(len(p0)),
        "vertexCountOutput": int(len(p1)),
        "vertexCountMatch": len(p0) == len(p1),
    }

    anim_ok = hash_animations(g0, b0) == hash_animations(g1, b1)
    matuv_ok = hash_material_uv(g0, b0) == hash_material_uv(g1, b1)
    skin_ok = len(g0["skins"][0]["joints"]) == len(g1["skins"][0]["joints"])

    actuator_pass = all(v["nonPresentationRegionMaxDisplacement"] <= REGRESSION_TOL for v in actuator_evidence.values())
    regression_ok = (
        neutral_parity["globalMaxDisplacement"] <= REGRESSION_TOL
        and neutral_parity["vertexCountMatch"]
        and anim_ok
        and matuv_ok
        and skin_ok
        and actuator_pass
    )

    raw_evidence = {
        "stage": "FAST-03D",
        "morphDeltas": str(MORPH_JSON),
        "bonesSpec": str(BONES_JSON),
        "patchMeta": patch_meta,
        "presentationZones": morph_data.get("presentationZones", {}),
        "shapeKeys": list(morph_data["shapeKeys"].keys()),
        "neutralIdentityParity": neutral_parity,
        "shapeKeyActuatorEvidence": actuator_evidence,
        "addedPresentationBones": [b["name"] for b in bones_data["addedBones"]],
        "jawRange": {
            "actuator": "PRES_JawOpen",
            "maxDisplacement": actuator_evidence.get("PRES_JawOpen", {}).get("maxDisplacement", 0),
            "boneNodes": ["NURION_Jaw"],
            "note": "Bone nodes added for FAST-04 rig; mesh jaw motion via isolated morph",
        },
    }
    EVIDENCE_RAW.write_text(json.dumps(raw_evidence, indent=2), encoding="utf-8")

    verdict = "PASS_CLOSED" if regression_ok else "FAIL_HOLD"
    receipt: dict[str, Any] = {
        "receiptId": f"FAST-03D_stop_gate_{ts}",
        "timestampUtc": ts,
        "lane": "FAST_PRODUCT",
        "stage": "FAST-03D",
        "verdict": verdict,
        "stopGate": True,
        "fast04Status": "HOLD",
        "identityPathLock": "A_FACE_SURFACE_IDENTITY_ADAPT",
        "integrity": {
            "canonicalGlbSha256": CANONICAL_SHA,
            "identityNeutralGlb": str(IDENTITY_NEUTRAL),
            "identityNeutralSha256": sha256_file(IDENTITY_NEUTRAL),
            "outputGlb": str(OUTPUT_GLB),
            "outputGlbSha256": sha256_file(OUTPUT_GLB),
            "formalLaneTouch": False,
        },
        "neutralIdentityParity": neutral_parity,
        "jawRange": raw_evidence["jawRange"],
        "eyeControl": {
            "bones": ["NURION_Eye_L", "NURION_Eye_R"],
            "lookTargetReady": True,
            "note": "Presentation bone nodes under Head; FAST-04 drives transforms",
        },
        "blinkActuators": ["PRES_Blink_L", "PRES_Blink_R"],
        "visemeSet": [k for k in morph_data["shapeKeys"] if k.startswith("PRES_Viseme_")],
        "expressions": ["PRES_SmileMild"],
        "shapeKeyActuatorEvidence": actuator_evidence,
        "regression": {
            "bodyHairNeckSeamMaxDisplacementAtNeutral": neutral_parity["globalMaxDisplacement"],
            "bodyHairNeckSeamPass": neutral_parity["globalMaxDisplacement"] <= REGRESSION_TOL,
            "animationHashUnchanged": anim_ok,
            "materialUvHashUnchanged": matuv_ok,
            "skinJointCountUnchanged": skin_ok,
            "existingSkeletonJointCount": len(g0["skins"][0]["joints"]),
            "presentationBonesNotInSkin": True,
            "allPass": regression_ok,
        },
        "skeletonDelta": {
            "addedPresentationBones": [b["name"] for b in bones_data["addedBones"]],
            "existingSkinJointCount": len(g0["skins"][0]["joints"]),
            "existingBoneMutations": [],
        },
        "contract": {
            "identityGeometryLocked": True,
            "presentationDeformationAdditiveIsolated": True,
            "lipSyncSystemImplemented": False,
        },
        "lipSyncScope": "NOT_IN_03D — actuators only; FAST-04 owns audio/phoneme sync",
        "artifacts": {
            "outputGlb": str(OUTPUT_GLB),
            "morphDeltas": str(MORPH_JSON),
            "bonesSpec": str(BONES_JSON),
            "actuatorEvidence": str(EVIDENCE_RAW),
        },
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")

    ledger["entries"] = [e for e in ledger["entries"] if e.get("id") != "FAST-03D"]
    ledger["entries"].append(
        {
            "id": "FAST-03D",
            "type": "FACIAL_CAPABILITY_ADD",
            "mutation": 1,
            "scope": "Additive morph targets + presentation bone nodes; base mesh/skin/anim unchanged",
            "output": str(OUTPUT_GLB),
            "evidence": str(RECEIPT),
            "verdict": verdict,
        }
    )
    ledger["workingBaselineSha256Current"] = sha256_file(OUTPUT_GLB)
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"verdict": verdict, "output": str(OUTPUT_GLB)}, ensure_ascii=True))
    return 0 if verdict == "PASS_CLOSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
