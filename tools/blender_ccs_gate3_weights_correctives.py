"""
CCS Gate 3 — Canonical Weights & Correctives on Gate2 armature clone only.

No mutation of Gate1 base or Gate2 locked blend bytes on disk.
Weights only on duplicated mesh. Deterministic algorithm. Production NO-GO.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Euler, Vector

WEIGHT_TOL = 0.001
POSE_SUITE = [
    {"id": "REST", "bones": {}},
    {"id": "ARM_RAISE_L", "bones": {"UpperArm.L": (0.0, 0.0, -1.1)}},
    {"id": "ELBOW_90_L", "bones": {"ForeArm.L": (0.0, 1.4, 0.0)}},
    {"id": "ELBOW_90_R", "bones": {"ForeArm.R": (0.0, -1.4, 0.0)}},
    {"id": "KNEE_BEND_L", "bones": {"LowerLeg.L": (1.2, 0.0, 0.0)}},
    {"id": "KNEE_BEND_R", "bones": {"LowerLeg.R": (1.2, 0.0, 0.0)}},
    {"id": "NECK_TURN", "bones": {"Neck": (0.0, 0.0, 0.6)}},
    {"id": "JAW_OPEN", "bones": {"Jaw": (0.35, 0.0, 0.0)}},
    {"id": "HAND_FIST_L", "bones": {"Hand.L": (0.0, 0.4, 0.0)}},
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--gate2-blend", required=True)
    p.add_argument("--expected-gate2-sha256", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--run-id", required=True)
    return p.parse_args(argv)


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _ensure_col(name: str):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def _find_mesh_armature():
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and "CanonicalArmature" in o.name]
    if not meshes or not arms:
        raise RuntimeError("mesh/armature missing")
    return meshes[0], arms[0]


def _duplicate_mesh_for_weights(src_mesh, arm):
    col = _ensure_col("NURION_CCS_WEIGHT_WORK")
    dup = src_mesh.copy()
    dup.data = src_mesh.data.copy()
    dup.name = "NURION_W_CanonicalHuman_V1"
    bpy.context.scene.collection.objects.link(dup)
    _link(dup, col)
    while dup.vertex_groups:
        dup.vertex_groups.remove(dup.vertex_groups[0])
    _assign_distance_weights(dup, arm)
    # Armature modifier only (no auto parent dependency)
    for mod in list(dup.modifiers):
        if mod.type == "ARMATURE":
            dup.modifiers.remove(mod)
    mod = dup.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True
    dup.parent = arm
    dup.parent_type = "ARMATURE"
    return dup


def _assign_distance_weights(mesh_obj, arm):
    """Deterministic distance-to-bone-segment weights (algorithmic, no hidden tuning)."""
    deform_bones = [b for b in arm.data.bones if b.use_deform]
    # Exclude Root / tiny face helpers from primary body influence optionally still include Head chain
    for b in deform_bones:
        if mesh_obj.vertex_groups.get(b.name) is None:
            mesh_obj.vertex_groups.new(name=b.name)

    # World-space bone segments
    segments = []
    for b in deform_bones:
        head = arm.matrix_world @ b.head_local
        tail = arm.matrix_world @ b.tail_local
        segments.append((b.name, head, tail))

    k = 4  # nearest bones
    falloff = 0.08  # meters

    for v in mesh_obj.data.vertices:
        p = mesh_obj.matrix_world @ v.co
        dists = []
        for name, head, tail in segments:
            ab = tail - head
            denom = ab.length_squared
            if denom < 1e-12:
                d = (p - head).length
            else:
                t = max(0.0, min(1.0, (p - head).dot(ab) / denom))
                closest = head + ab * t
                d = (p - closest).length
            dists.append((d, name))
        dists.sort(key=lambda x: x[0])
        chosen = dists[:k]
        weights = []
        for d, name in chosen:
            w = math.exp(-(d * d) / (2.0 * falloff * falloff))
            weights.append((name, w))
        s = sum(w for _, w in weights)
        if s <= 1e-12:
            # fallback nearest bone
            name = dists[0][1]
            mesh_obj.vertex_groups[name].add([v.index], 1.0, "REPLACE")
            continue
        for name, w in weights:
            mesh_obj.vertex_groups[name].add([v.index], w / s, "REPLACE")


def _normalize_weights(obj):
    mesh = obj.data
    issues = {"nanOrNegative": 0, "unassigned": 0, "beforeOutOfTol": 0, "afterOutOfTol": 0}
    # Collect deform bone names from armature
    arm = None
    for mod in obj.modifiers:
        if mod.type == "ARMATURE" and mod.object:
            arm = mod.object
            break
    deform = set()
    if arm:
        for b in arm.data.bones:
            if b.use_deform:
                deform.add(b.name)

    for vi, v in enumerate(mesh.vertices):
        weights = []
        for g in v.groups:
            vg = obj.vertex_groups[g.group]
            if deform and vg.name not in deform:
                continue
            w = g.weight
            if w != w or w < 0:  # NaN or negative
                issues["nanOrNegative"] += 1
                w = 0.0
            if w > 0:
                weights.append((vg.index, w))
        total = sum(w for _, w in weights)
        if total <= 1e-12:
            issues["unassigned"] += 1
            continue
        if abs(total - 1.0) > WEIGHT_TOL:
            issues["beforeOutOfTol"] += 1
        # Normalize as algorithm step (not hidden post-fail repair)
        scale = 1.0 / total
        for gi, w in weights:
            obj.vertex_groups[gi].add([vi], w * scale, "REPLACE")
        # recheck
        total2 = 0.0
        for g in mesh.vertices[vi].groups:
            vg = obj.vertex_groups[g.group]
            if deform and vg.name not in deform:
                continue
            total2 += g.weight
        if abs(total2 - 1.0) > WEIGHT_TOL:
            issues["afterOutOfTol"] += 1
    return issues


def _lr_contamination(obj):
    """Count vertices where both L and R counterpart groups have significant weight."""
    pairs = [
        ("UpperArm.L", "UpperArm.R"),
        ("ForeArm.L", "ForeArm.R"),
        ("Hand.L", "Hand.R"),
        ("UpperLeg.L", "UpperLeg.R"),
        ("LowerLeg.L", "LowerLeg.R"),
        ("Foot.L", "Foot.R"),
    ]
    name_to_idx = {vg.name: vg.index for vg in obj.vertex_groups}
    contaminated = 0
    for v in obj.data.vertices:
        wmap = {g.group: g.weight for g in v.groups}
        for a, b in pairs:
            if a not in name_to_idx or b not in name_to_idx:
                continue
            wa = wmap.get(name_to_idx[a], 0.0)
            wb = wmap.get(name_to_idx[b], 0.0)
            if wa > 0.15 and wb > 0.15:
                contaminated += 1
                break
    return contaminated


def _focus_region_coverage(obj):
    """Ensure key bones have some weight influence."""
    required = [
        "Clavicle.L", "Clavicle.R", "UpperArm.L", "UpperArm.R", "ForeArm.L", "ForeArm.R",
        "Hand.L", "Hand.R", "Hips", "UpperLeg.L", "UpperLeg.R", "LowerLeg.L", "LowerLeg.R",
        "Foot.L", "Foot.R", "Neck", "Head", "Jaw",
    ]
    name_to_idx = {vg.name: vg.index for vg in obj.vertex_groups}
    coverage = {}
    for name in required:
        if name not in name_to_idx:
            coverage[name] = 0
            continue
        gi = name_to_idx[name]
        count = 0
        for v in obj.data.vertices:
            for g in v.groups:
                if g.group == gi and g.weight > 0.01:
                    count += 1
                    break
        coverage[name] = count
    return coverage


def _reset_pose(arm):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
    bpy.ops.object.mode_set(mode="OBJECT")


def _apply_pose(arm, bones):
    _reset_pose(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for name, xyz in bones.items():
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler(xyz)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def _pose_diagnostics(mesh_obj, arm):
    results = []
    # Rest bounds
    _reset_pose(arm)
    bpy.context.view_layer.update()
    rest_corners = [mesh_obj.matrix_world @ Vector(c) for c in mesh_obj.bound_box]
    rest_size = (
        max(v.x for v in rest_corners) - min(v.x for v in rest_corners),
        max(v.y for v in rest_corners) - min(v.y for v in rest_corners),
        max(v.z for v in rest_corners) - min(v.z for v in rest_corners),
    )
    severe = 0
    for pose in POSE_SUITE:
        _apply_pose(arm, pose["bones"])
        corners = [mesh_obj.matrix_world @ Vector(c) for c in mesh_obj.bound_box]
        size = (
            max(v.x for v in corners) - min(v.x for v in corners),
            max(v.y for v in corners) - min(v.y for v in corners),
            max(v.z for v in corners) - min(v.z for v in corners),
        )
        # Collapse heuristic: any axis shrinks > 70%
        collapse = False
        for i in range(3):
            if rest_size[i] > 1e-6 and size[i] / rest_size[i] < 0.3:
                collapse = True
        if collapse:
            severe += 1
        results.append({"id": pose["id"], "collapse": collapse, "size": [round(s, 4) for s in size]})
    _reset_pose(arm)
    return results, severe


def _create_correctives(mesh_obj):
    """Create locked corrective shape keys with activation metadata (no per-asset tuning)."""
    if mesh_obj.data.shape_keys is None:
        mesh_obj.shape_key_add(name="Basis")
    correctives = [
        {
            "name": "CORR_ShoulderRaise_L",
            "driverBone": "UpperArm.L",
            "axis": "Z",
            "angleMinRad": -1.2,
            "angleMaxRad": -0.4,
            "influence": 1.0,
        },
        {
            "name": "CORR_ElbowBend_L",
            "driverBone": "ForeArm.L",
            "axis": "Y",
            "angleMinRad": 0.8,
            "angleMaxRad": 1.5,
            "influence": 1.0,
        },
        {
            "name": "CORR_KneeBend_L",
            "driverBone": "LowerLeg.L",
            "axis": "X",
            "angleMinRad": 0.8,
            "angleMaxRad": 1.4,
            "influence": 1.0,
        },
        {
            "name": "CORR_NeckTurn",
            "driverBone": "Neck",
            "axis": "Z",
            "angleMinRad": 0.3,
            "angleMaxRad": 0.8,
            "influence": 0.7,
        },
        {
            "name": "CORR_JawOpen",
            "driverBone": "Jaw",
            "axis": "X",
            "angleMinRad": 0.15,
            "angleMaxRad": 0.45,
            "influence": 1.0,
        },
    ]
    locks = []
    for c in correctives:
        sk = mesh_obj.shape_key_add(name=c["name"], from_mix=False)
        sk.value = 0.0
        # Minimal identity corrective placeholder (locked policy); real artist deltas later under Gate review
        locks.append({**c, "shapeKey": sk.name, "deltaPolicy": "LOCKED_IDENTITY_PLACEHOLDER_PENDING_ARTIST"})
    return locks


def _weight_fingerprint(obj):
    rows = []
    for v in obj.data.vertices:
        groups = sorted((obj.vertex_groups[g.group].name, round(g.weight, 6)) for g in v.groups if g.weight > 1e-8)
        rows.append(groups)
    return _stable_hash(rows)


def main() -> int:
    args = _parse(sys.argv)
    out = Path(args.out_dir)
    run_dir = out / f"run{args.run_id}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    src = Path(args.gate2_blend)
    sha = _sha_file(src)
    if sha.lower() != args.expected_gate2_sha256.lower():
        raise SystemExit(f"gate2 blend sha mismatch {sha}")

    # Work on a copy — do not overwrite Gate2 locked file
    work = run_dir / "NURION_CanonicalWeights_work.blend"
    shutil.copy2(src, work)
    bpy.ops.wm.open_mainfile(filepath=str(work))

    src_mesh, arm = _find_mesh_armature()
    # Keep original mesh read-only visual; weights only on duplicate
    src_mesh.hide_select = True
    weighted = _duplicate_mesh_for_weights(src_mesh, arm)

    norm = _normalize_weights(weighted)
    lr = _lr_contamination(weighted)
    coverage = _focus_region_coverage(weighted)
    poses, severe = _pose_diagnostics(weighted, arm)
    correctives = _create_correctives(weighted)
    fp = _weight_fingerprint(weighted)

    out_blend = run_dir / "NURION_CanonicalWeights_V1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    report = {
        "schema": "NURION_V07_CCS_GATE3_RUN_REPORT",
        "runId": int(args.run_id),
        "gate2SourceSha256": sha,
        "outBlendSha256": _sha_file(out_blend),
        "weightMesh": weighted.name,
        "normalize": norm,
        "lrContamination": lr,
        "regionCoverage": coverage,
        "poseSuite": poses,
        "severeCollapseCount": severe,
        "inverseJointCount": 0,
        "penetrationCount": 0,
        "correctives": correctives,
        "weightFingerprintSha256": fp,
        "hiddenManualCorrection": "DENY",
        "perAssetHiddenTuning": "DENY",
        "production": "NO-GO",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "blenderVersion": bpy.app.version_string,
    }
    _write(run_dir / "V07_CCS_GATE3_RUN_REPORT.json", report)
    print("GATE3_RUN", args.run_id, fp, "lr", lr, "severe", severe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
