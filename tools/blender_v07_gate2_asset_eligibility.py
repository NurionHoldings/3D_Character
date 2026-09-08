"""
v0.7 Gate 2 — Asset Eligibility & Landmark Evidence (read-only evaluation).

Does NOT generate armature/weights/animations.
Does NOT mutate source assets or sealed baselines.
Existing Meshy bones/weights are non-authoritative evidence only (never GT).

Usage:
  blender --background --python tools/blender_v07_gate2_asset_eligibility.py -- \\
    --zip path/to.zip --label LABEL --out-dir dist/v0.7/gate2/LABEL

  blender --background --python tools/blender_v07_gate2_asset_eligibility.py -- \\
    --fbx path/to.fbx --label LABEL --out-dir dist/v0.7/gate2/LABEL
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
GATE1_STATUS = ROOT / "dist" / "v0.7" / "gate1" / "V07_GATE1_STATUS.json"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", default="")
    p.add_argument("--fbx", default="")
    p.add_argument("--label", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--homepage-primary", action="store_true")
    return p.parse_args(argv)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _import_fbx(path: Path) -> None:
    bpy.ops.import_scene.fbx(
        filepath=str(path),
        automatic_bone_orientation=False,
        use_anim=False,
    )


def _find_fbx(extract: Path) -> Path | None:
    cands = sorted(extract.rglob("*.fbx"))
    if not cands:
        return None
    # Prefer withSkin / Idle / texture
    scored = []
    for p in cands:
        n = p.name.lower()
        score = 0
        if "withskin" in n:
            score += 10
        if "idle" in n:
            score += 5
        if "texture" in n:
            score += 3
        if "walking" in n or "run" in n:
            score -= 2
        scored.append((score, len(str(p)), p))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return scored[0][2]


def _meshes():
    return [o for o in bpy.data.objects if o.type == "MESH"]


def _armatures():
    return [o for o in bpy.data.objects if o.type == "ARMATURE"]


def _world_bounds(objs):
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    count = 0
    for obj in objs:
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            mins = Vector((min(mins.x, w.x), min(mins.y, w.y), min(mins.z, w.z)))
            maxs = Vector((max(maxs.x, w.x), max(maxs.y, w.y), max(maxs.z, w.z)))
            count += 1
    if count == 0:
        return None
    size = maxs - mins
    return {
        "min": [round(float(x), 5) for x in mins],
        "max": [round(float(x), 5) for x in maxs],
        "size": [round(float(x), 5) for x in size],
        "heightM": round(float(size.z), 5),
        "center": [round(float(x), 5) for x in ((mins + maxs) * 0.5)],
    }


def _vertex_stats(mesh_objs):
    total = 0
    for obj in mesh_objs:
        total += len(obj.data.vertices)
    return {"meshCount": len(mesh_objs), "vertexCount": total}


def _sample_region_density(mesh_objs, bounds):
    """Heuristic region occupancy from vertex world positions (read-only)."""
    if not bounds or not mesh_objs:
        return {}
    mn = Vector(bounds["min"])
    mx = Vector(bounds["max"])
    size = mx - mn
    if size.z < 1e-6 or size.x < 1e-6:
        return {"insufficientBounds": True}

    regions = {
        "head": 0,
        "torso": 0,
        "armL": 0,
        "armR": 0,
        "handL": 0,
        "handR": 0,
        "faceBand": 0,
        "eyeBand": 0,
    }
    total = 0
    # sample every Nth vertex for speed
    step = 1
    for obj in mesh_objs:
        me = obj.data
        n = len(me.vertices)
        if n > 40000:
            step = max(1, n // 20000)
        mw = obj.matrix_world
        for i, v in enumerate(me.vertices):
            if i % step:
                continue
            p = mw @ v.co
            total += 1
            # normalized height 0..1
            t = (p.z - mn.z) / size.z
            x_n = (p.x - mn.x) / max(size.x, 1e-6)
            if t >= 0.82:
                regions["head"] += 1
                if 0.86 <= t <= 0.96:
                    regions["faceBand"] += 1
                if 0.88 <= t <= 0.94:
                    regions["eyeBand"] += 1
            if 0.45 <= t <= 0.82:
                regions["torso"] += 1
            if 0.45 <= t <= 0.85 and x_n < 0.35:
                regions["armL"] += 1
            if 0.45 <= t <= 0.85 and x_n > 0.65:
                regions["armR"] += 1
            if 0.35 <= t <= 0.62 and x_n < 0.28:
                regions["handL"] += 1
            if 0.35 <= t <= 0.62 and x_n > 0.72:
                regions["handR"] += 1

    dens = {k: (v / max(total, 1)) for k, v in regions.items()}
    dens["sampledVertices"] = total
    return dens


def _bone_name_hints(arm_objs):
    names = []
    for arm in arm_objs:
        for b in arm.data.bones:
            names.append(b.name)
    low = [n.lower() for n in names]
    def has(*keys):
        return any(any(k in n for k in keys) for n in low)

    return {
        "boneCount": len(names),
        "hasHead": has("head"),
        "hasNeck": has("neck"),
        "hasSpine": has("spine", "chest", "torso"),
        "hasArm": has("arm", "shoulder", "clavicle", "upperarm", "forearm"),
        "hasHand": has("hand", "wrist", "palm"),
        "hasFinger": has("finger", "thumb", "index", "middle", "ring", "pinky"),
        "hasEye": has("eye"),
        "hasJaw": has("jaw", "mouth"),
        "sampleNames": names[:40],
        "authoritativeGroundTruth": False,
        "role": "NON_AUTHORITATIVE_EVIDENCE_ONLY",
    }


def _has_vgroups(mesh_objs):
    any_vg = False
    max_groups = 0
    for obj in mesh_objs:
        max_groups = max(max_groups, len(obj.vertex_groups))
        if obj.vertex_groups:
            any_vg = True
    return {"hasVertexGroups": any_vg, "maxVertexGroups": max_groups, "authoritativeGroundTruth": False}


def _classify(evidence: dict) -> dict:
    fails = []
    limitations = []
    paths = {
        "newRigGeneration": "UNKNOWN",
        "handGesturePath": "UNKNOWN",
        "facePath": "UNKNOWN",
        "eyePath": "UNKNOWN",
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
    }

    verts = evidence["vertexStats"]["vertexCount"]
    meshes = evidence["vertexStats"]["meshCount"]
    dens = evidence.get("regionDensity") or {}
    bones = evidence.get("existingArmatureEvidence") or {}
    gt_manual = evidence.get("manualGroundTruthPresent", False)

    if meshes < 1 or verts < 500:
        return {
            "classification": "INELIGIBLE",
            "reason": "INSUFFICIENT_MESH_GEOMETRY",
            "paths": {**paths, "newRigGeneration": "DENY"},
            "fails": ["INSUFFICIENT_MESH_GEOMETRY"],
            "limitations": [],
            "homepageReadyLimited": False,
            "groundTruthRequiredForAccuracy": True,
        }

    height = (evidence.get("bounds") or {}).get("heightM") or 0.0
    if height < 0.3 or height > 5.0:
        fails.append("UNSUPPORTED_SCALE_OR_BOUNDS")
        # soft — still may be limited

    head_ok = dens.get("head", 0) > 0.01 or bones.get("hasHead")
    torso_ok = dens.get("torso", 0) > 0.05 or bones.get("hasSpine")
    arms_ok = (dens.get("armL", 0) > 0.002 and dens.get("armR", 0) > 0.002) or bones.get("hasArm")
    hand_l = dens.get("handL", 0)
    hand_r = dens.get("handR", 0)
    hand_geom = hand_l > 0.0008 and hand_r > 0.0008
    hand_bones = bool(bones.get("hasHand"))
    finger_bones = bool(bones.get("hasFinger"))
    face_ok = dens.get("faceBand", 0) > 0.002 or bones.get("hasJaw")
    eye_ok = dens.get("eyeBand", 0) > 0.0005 or bones.get("hasEye")

    if not (head_ok and torso_ok and arms_ok):
        return {
            "classification": "INELIGIBLE",
            "reason": "MISSING_REQUIRED_UPPERBODY_VISIBILITY",
            "paths": {**paths, "newRigGeneration": "DENY"},
            "fails": ["MISSING_REQUIRED_UPPERBODY_VISIBILITY"],
            "limitations": [],
            "homepageReadyLimited": False,
            "groundTruthRequiredForAccuracy": True,
            "evidenceFlags": {
                "head": head_ok,
                "torso": torso_ok,
                "arms": arms_ok,
                "hands": hand_geom or hand_bones,
                "face": face_ok,
                "eyes": eye_ok,
            },
        }

    paths["newRigGeneration"] = "ELIGIBLE_CLONE_ONLY"

    # Hands
    if hand_geom or hand_bones:
        if finger_bones or (hand_l > 0.002 and hand_r > 0.002):
            paths["handGesturePath"] = "ELIGIBLE_BASIC_GESTURE"
        else:
            paths["handGesturePath"] = "ELIGIBLE_PALM_LIMITED"
            limitations.append("HAND_DETAIL_LIMITED")
    else:
        paths["handGesturePath"] = "ABSTAIN_HAND_GESTURE_PATH"
        limitations.append("ABSTAIN_HAND_GESTURE_PATH")

    # Face / eye — v0.3/v0.4 attachment only in later gates
    if face_ok:
        paths["facePath"] = "REST_FALLBACK_OR_READONLY_ATTACHMENT"
    else:
        paths["facePath"] = "REST_FALLBACK"
        limitations.append("MISSING_FACE_EVIDENCE_REST_FALLBACK")

    if eye_ok:
        paths["eyePath"] = "HEAD_AIM_PLUS_OPTIONAL_EYE_ATTACHMENT"
    else:
        paths["eyePath"] = "HEAD_AIM_ONLY_WITH_LIMITATION"
        limitations.append("MISSING_EYE_EVIDENCE_HEAD_AIM_ONLY")

    if not gt_manual:
        paths["accuracyClaim"] = "REVIEW_REQUIRED_NO_ACCURACY_CLAIM"
        limitations.append("GROUND_TRUTH_REQUIRED_FOR_ACCURACY_CLAIMS")
        # Meshy bones present ≠ GT
        if bones.get("boneCount", 0) > 0:
            limitations.append("EXISTING_ARMATURE_NON_AUTHORITATIVE_NOT_GT")

    # Classification
    homepage_ready = False
    if paths["handGesturePath"] == "ABSTAIN_HAND_GESTURE_PATH" and not (head_ok and torso_ok):
        classification = "ABSTAIN"
        reason = "INSUFFICIENT_LANDMARK_EVIDENCE"
    elif not gt_manual:
        classification = "REVIEW_REQUIRED"
        reason = "NO_MANUAL_GROUND_TRUTH_FOR_ACCURACY"
        homepage_ready = True
    else:
        classification = "HOMEPAGE_READY_LIMITED"
        reason = "ELIGIBLE_WITH_GT"
        homepage_ready = True
        paths["accuracyClaim"] = "ALLOWED_WHEN_EVALUATED_AGAINST_GT"

    if height < 0.5 or verts < 2000:
        limitations.append("LOW_RESOLUTION_OR_SHORT_BOUNDS")

    return {
        "classification": classification,
        "reason": reason,
        "paths": paths,
        "fails": fails,
        "limitations": limitations,
        "homepageReadyLimited": homepage_ready if classification not in ("INELIGIBLE", "ABSTAIN") else False,
        "groundTruthRequiredForAccuracy": not gt_manual,
        "newNativeRigGenerationPossible": paths["newRigGeneration"] == "ELIGIBLE_CLONE_ONLY",
        "evidenceFlags": {
            "head": bool(head_ok),
            "torso": bool(torso_ok),
            "arms": bool(arms_ok),
            "hands": bool(hand_geom or hand_bones),
            "face": bool(face_ok),
            "eyes": bool(eye_ok),
            "fingerBones": bool(finger_bones),
        },
    }


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not GATE1_STATUS.is_file():
        raise SystemExit("Gate1 status missing — register Gate1 first")
    g1 = json.loads(GATE1_STATUS.read_text(encoding="utf-8"))
    if g1.get("parameterHash") != GATE1_HASH or g1.get("V07_GATE1") != "PASS":
        raise SystemExit("Gate1 not PASS/LOCKED with expected hash")

    source_path: Path | None = None
    source_kind = ""
    source_sha = ""
    fbx_path: Path | None = None
    extract = out_dir / "_extract"

    if args.zip:
        source_path = Path(args.zip)
        if not source_path.is_absolute():
            source_path = ROOT / source_path
        source_kind = "zip"
        source_sha = _sha(source_path)
        if extract.exists():
            shutil.rmtree(extract)
        extract.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source_path, "r") as zf:
            zf.extractall(extract)
        fbx_path = _find_fbx(extract)
        if fbx_path is None:
            raise SystemExit(f"No FBX in zip: {source_path}")
    elif args.fbx:
        source_path = Path(args.fbx)
        if not source_path.is_absolute():
            source_path = ROOT / source_path
        source_kind = "fbx"
        source_sha = _sha(source_path)
        fbx_path = source_path
    else:
        raise SystemExit("Provide --zip or --fbx")

    fbx_sha = _sha(fbx_path)
    pre_source_sha = source_sha

    _reset()
    _import_fbx(fbx_path)

    mesh_objs = _meshes()
    arm_objs = _armatures()
    bounds = _world_bounds(mesh_objs)
    vstats = _vertex_stats(mesh_objs)
    dens = _sample_region_density(mesh_objs, bounds)
    bone_ev = _bone_name_hints(arm_objs)
    vg = _has_vgroups(mesh_objs)

    # Manual GT annotations not present in Gate2 inputs by default
    manual_gt = False

    evidence = {
        "schema": "NURION_V07_LANDMARK_EVIDENCE",
        "label": args.label,
        "homepagePrimaryCandidate": bool(args.homepage_primary),
        "source": {
            "kind": source_kind,
            "path": (
                str(source_path.relative_to(ROOT)).replace("\\", "/")
                if str(source_path).startswith(str(ROOT))
                else str(source_path)
            ),
            "sha256": source_sha,
            "fbxPath": str(fbx_path),
            "fbxSha256": fbx_sha,
        },
        "vertexStats": vstats,
        "bounds": bounds,
        "regionDensity": dens,
        "existingArmatureEvidence": bone_ev,
        "existingWeightEvidence": vg,
        "meshyBonesAsGroundTruth": "DENY",
        "meshyWeightsAsGroundTruth": "DENY",
        "manualGroundTruthPresent": manual_gt,
        "evaluatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
    }

    verdict = _classify(evidence)
    evidence["classification"] = verdict["classification"]
    evidence["paths"] = verdict["paths"]
    evidence["limitations"] = verdict["limitations"]
    evidence["evidenceFlags"] = verdict.get("evidenceFlags")

    # Post hash — source must be unchanged
    post_source_sha = _sha(source_path)
    mutation = 0 if pre_source_sha == post_source_sha else 1

    asset_status = {
        "schema": "NURION_V07_GATE2_ASSET_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 2,
        "name": "ASSET_ELIGIBILITY_AND_LANDMARK_EVIDENCE",
        "label": args.label,
        "gate1ParameterHash": GATE1_HASH,
        "classification": verdict["classification"],
        "reason": verdict["reason"],
        "homepageReadyLimited": verdict.get("homepageReadyLimited", False),
        "newNativeRigGenerationPossible": verdict.get("newNativeRigGenerationPossible", False),
        "groundTruthRequiredForAccuracy": verdict.get("groundTruthRequiredForAccuracy", True),
        "paths": verdict["paths"],
        "limitations": verdict["limitations"],
        "fails": verdict["fails"],
        "sourceMutation": mutation,
        "armatureGenerated": False,
        "weightsGenerated": False,
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "artifacts": {
            "evidence": "V07_LANDMARK_EVIDENCE.json",
            "eligibility": "V07_ASSET_ELIGIBILITY.json",
        },
    }

    eligibility = {
        "schema": "NURION_V07_ASSET_ELIGIBILITY",
        "label": args.label,
        "assetEligibleForHomepageRigPipeline": verdict.get("newNativeRigGenerationPossible", False)
        and verdict["classification"] != "INELIGIBLE",
        "classification": verdict["classification"],
        "reason": verdict["reason"],
        "evaluationAllowed": verdict["classification"] != "INELIGIBLE",
        "autoRigAllowed": False,
        "nativeHomepageRigGenerationAllowed": verdict.get("newNativeRigGenerationPossible", False),
        "handGesturePath": verdict["paths"].get("handGesturePath"),
        "facePath": verdict["paths"].get("facePath"),
        "eyePath": verdict["paths"].get("eyePath"),
        "accuracyClaim": verdict["paths"].get("accuracyClaim"),
        "existingRigAuthoritative": False,
        "checks": {
            "HAS_MESH": vstats["meshCount"] >= 1,
            "HAS_UPPERBODY_EVIDENCE": bool((verdict.get("evidenceFlags") or {}).get("torso"))
            and bool((verdict.get("evidenceFlags") or {}).get("head")),
            "HAND_EVIDENCE": bool((verdict.get("evidenceFlags") or {}).get("hands")),
            "FACE_EVIDENCE": bool((verdict.get("evidenceFlags") or {}).get("face")),
            "EYE_EVIDENCE": bool((verdict.get("evidenceFlags") or {}).get("eyes")),
            "MANUAL_GT": manual_gt,
            "SOURCE_UNCHANGED": mutation == 0,
            "MESHY_GT_DENIED": True,
        },
        "limitations": verdict["limitations"],
        "fails": verdict["fails"],
    }

    _write(out_dir / "V07_LANDMARK_EVIDENCE.json", evidence)
    _write(out_dir / "V07_ASSET_ELIGIBILITY.json", eligibility)
    _write(out_dir / "V07_GATE2_ASSET_STATUS.json", asset_status)

    print(json.dumps({
        "label": args.label,
        "classification": verdict["classification"],
        "hand": verdict["paths"].get("handGesturePath"),
        "sourceMutation": mutation,
    }, ensure_ascii=False))
    return 0 if mutation == 0 and not verdict["fails"] else (0 if verdict["classification"] != "INELIGIBLE" else 2)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
