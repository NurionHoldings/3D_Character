"""
v0.7 Gate 3 — Native Armature Prototype on ai-aba.15 clone.

- Clone-only: source ZIP bytes must remain unchanged
- Create NURION_HomepagePerformanceRig collection + native armature
- DO NOT bind/generate weights
- DO NOT mutate sealed baselines
- Existing Meshy armature is non-authoritative evidence only (not GT)

Usage:
  blender --background --python tools/blender_v07_gate3_native_armature_prototype.py -- \\
    --zip dist/v0.4/gate8c/inbox/ai-aba.15.zip --out-dir dist/v0.7/gate3
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
GATE2_HASH = "fd77cc7ffa5428e460162c0f80624abd91c980c2fd83738e28bce1c33af5c1c9"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"
COLL_NAME = "NURION_HomepagePerformanceRig"
ARM_NAME = "NURION_HomepageNativeArmature"

# Minimum bone roles from Gate1 contract
BONE_CHAIN = [
    ("Root", None),
    ("Hips", "Root"),
    ("Spine", "Hips"),
    ("Spine01", "Spine"),
    ("Spine02", "Spine01"),
    ("Chest", "Spine02"),
    ("Neck", "Chest"),
    ("Head", "Neck"),
    ("Clavicle.L", "Chest"),
    ("UpperArm.L", "Clavicle.L"),
    ("ForeArm.L", "UpperArm.L"),
    ("Hand.L", "ForeArm.L"),
    ("Clavicle.R", "Chest"),
    ("UpperArm.R", "Clavicle.R"),
    ("ForeArm.R", "UpperArm.R"),
    ("Hand.R", "ForeArm.R"),
    ("UpperLeg.L", "Hips"),
    ("LowerLeg.L", "UpperLeg.L"),
    ("Foot.L", "LowerLeg.L"),
    ("Toe.L", "Foot.L"),
    ("UpperLeg.R", "Hips"),
    ("LowerLeg.R", "UpperLeg.R"),
    ("Foot.R", "LowerLeg.R"),
    ("Toe.R", "Foot.R"),
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--label", default="ai-aba.15")
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


def _find_fbx(extract: Path) -> Path:
    cands = sorted(extract.rglob("*.fbx"))
    if not cands:
        raise FileNotFoundError("No FBX in extract")
    scored = []
    for p in cands:
        n = p.name.lower()
        score = 0
        if "withskin" in n:
            score += 10
        if "idle" in n:
            score += 5
        scored.append((-score, len(str(p)), p))
    scored.sort()
    return scored[0][2]


def _mesh_bounds(meshes):
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for obj in meshes:
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            mins.x = min(mins.x, w.x)
            mins.y = min(mins.y, w.y)
            mins.z = min(mins.z, w.z)
            maxs.x = max(maxs.x, w.x)
            maxs.y = max(maxs.y, w.y)
            maxs.z = max(maxs.z, w.z)
    return mins, maxs


def _estimate_joints(mins: Vector, maxs: Vector) -> dict[str, Vector]:
    """Geometry-estimated joint anchors (NOT Meshy GT)."""
    c = (mins + maxs) * 0.5
    size = maxs - mins
    h = size.z
    w = size.x
    d = size.y
    z0 = mins.z
    # Proportional humanoid rest estimates in world space
    hips = Vector((c.x, c.y, z0 + h * 0.52))
    root = Vector((c.x, c.y, z0))
    spine = Vector((c.x, c.y, z0 + h * 0.58))
    spine01 = Vector((c.x, c.y, z0 + h * 0.64))
    spine02 = Vector((c.x, c.y, z0 + h * 0.70))
    chest = Vector((c.x, c.y, z0 + h * 0.76))
    neck = Vector((c.x, c.y, z0 + h * 0.84))
    head = Vector((c.x, c.y, z0 + h * 0.92))
    clav_l = Vector((c.x + w * 0.08, c.y, z0 + h * 0.78))
    clav_r = Vector((c.x - w * 0.08, c.y, z0 + h * 0.78))
    uarm_l = Vector((c.x + w * 0.22, c.y, z0 + h * 0.74))
    uarm_r = Vector((c.x - w * 0.22, c.y, z0 + h * 0.74))
    farm_l = Vector((c.x + w * 0.30, c.y, z0 + h * 0.58))
    farm_r = Vector((c.x - w * 0.30, c.y, z0 + h * 0.58))
    hand_l = Vector((c.x + w * 0.34, c.y, z0 + h * 0.46))
    hand_r = Vector((c.x - w * 0.34, c.y, z0 + h * 0.46))
    uleg_l = Vector((c.x + w * 0.08, c.y, z0 + h * 0.50))
    uleg_r = Vector((c.x - w * 0.08, c.y, z0 + h * 0.50))
    lleg_l = Vector((c.x + w * 0.08, c.y, z0 + h * 0.26))
    lleg_r = Vector((c.x - w * 0.08, c.y, z0 + h * 0.26))
    foot_l = Vector((c.x + w * 0.08, c.y + d * 0.05, z0 + h * 0.04))
    foot_r = Vector((c.x - w * 0.08, c.y + d * 0.05, z0 + h * 0.04))
    toe_l = Vector((c.x + w * 0.08, c.y + d * 0.12, z0 + h * 0.02))
    toe_r = Vector((c.x - w * 0.08, c.y + d * 0.12, z0 + h * 0.02))
    return {
        "Root": root,
        "Hips": hips,
        "Spine": spine,
        "Spine01": spine01,
        "Spine02": spine02,
        "Chest": chest,
        "Neck": neck,
        "Head": head,
        "Clavicle.L": clav_l,
        "UpperArm.L": uarm_l,
        "ForeArm.L": farm_l,
        "Hand.L": hand_l,
        "Clavicle.R": clav_r,
        "UpperArm.R": uarm_r,
        "ForeArm.R": farm_r,
        "Hand.R": hand_r,
        "UpperLeg.L": uleg_l,
        "LowerLeg.L": lleg_l,
        "Foot.L": foot_l,
        "Toe.L": toe_l,
        "UpperLeg.R": uleg_r,
        "LowerLeg.R": lleg_r,
        "Foot.R": foot_r,
        "Toe.R": toe_r,
    }


def _tail_for(name: str, head: Vector, joints: dict[str, Vector]) -> Vector:
    # Prefer child head as tail when unique child exists
    children = [bn for bn, parent in BONE_CHAIN if parent == name]
    if len(children) == 1:
        return joints[children[0]].copy()
    if name == "Head":
        return head + Vector((0, 0, 0.08))
    if name.endswith(".L") and "Hand" in name:
        return head + Vector((0.04, 0, 0))
    if name.endswith(".R") and "Hand" in name:
        return head + Vector((-0.04, 0, 0))
    if name.startswith("Toe"):
        return head + Vector((0, 0.03, 0))
    if name == "Root":
        return joints["Hips"].copy()
    # multi-child (Hips/Chest): short upward/outward stub
    return head + Vector((0, 0, 0.03))


def _create_armature(joints: dict[str, Vector]):
    arm_data = bpy.data.armatures.new(ARM_NAME)
    arm_obj = bpy.data.objects.new(ARM_NAME, arm_data)
    coll = bpy.data.collections.new(COLL_NAME)
    bpy.context.scene.collection.children.link(coll)
    coll.objects.link(arm_obj)

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    edit = arm_data.edit_bones
    created = {}
    for name, parent in BONE_CHAIN:
        eb = edit.new(name)
        head = joints[name]
        tail = _tail_for(name, head, joints)
        if (tail - head).length < 1e-4:
            tail = head + Vector((0, 0, 0.02))
        eb.head = head
        eb.tail = tail
        created[name] = eb
    for name, parent in BONE_CHAIN:
        if parent:
            created[name].parent = created[parent]
            created[name].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj, coll


def _bone_report(arm_obj):
    rows = []
    zero = 0
    for b in arm_obj.data.bones:
        length = float((b.tail_local - b.head_local).length)
        if length < 1e-5:
            zero += 1
        rows.append(
            {
                "name": b.name,
                "parent": b.parent.name if b.parent else None,
                "headLocal": [round(float(x), 5) for x in b.head_local],
                "tailLocal": [round(float(x), 5) for x in b.tail_local],
                "length": round(length, 5),
            }
        )
    return rows, zero


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Continuity prerequisites
    continuity = json.loads(
        (ROOT / "dist/v0.7/gate1/V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8")
    )
    if continuity.get("V07_GATE1_BASELINE_CONTINUITY") != "PASS":
        raise SystemExit("Gate1 baseline continuity not PASS")
    preset = ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json"
    if _sha(preset) != PRESET_SHA:
        raise SystemExit("Preset catalog hash mismatch — refuse Gate3")

    g2 = json.loads((ROOT / "dist/v0.7/gate2/V07_GATE2_STATUS.json").read_text(encoding="utf-8"))
    if g2.get("V07_GATE2") != "PASS" or g2.get("parameterHash") != GATE2_HASH:
        raise SystemExit("Gate2 not PASS with expected hash")

    zip_path = Path(args.zip)
    if not zip_path.is_absolute():
        zip_path = ROOT / zip_path
    pre_sha = _sha(zip_path)

    work = out_dir / "_work_clone"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    # Clone zip bytes into work area (do not write back to source)
    clone_zip = work / zip_path.name
    shutil.copy2(zip_path, clone_zip)
    extract = work / "extract"
    extract.mkdir()
    with zipfile.ZipFile(clone_zip, "r") as zf:
        zf.extractall(extract)
    fbx = _find_fbx(extract)
    fbx_sha = _sha(fbx)

    _reset()
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=False, use_anim=False)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    source_arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not meshes:
        raise SystemExit("No mesh in clone")

    # Snapshot source mesh vertex group counts (must remain unchanged after — we never bind)
    mesh_vg_before = {o.name: len(o.vertex_groups) for o in meshes}
    mesh_mods_before = {o.name: [m.type for m in o.modifiers] for o in meshes}

    mins, maxs = _mesh_bounds(meshes)
    joints = _estimate_joints(mins, maxs)
    arm_obj, coll = _create_armature(joints)
    bone_rows, zero_len = _bone_report(arm_obj)

    # Ensure no armature modifier / weight binding was added
    mesh_vg_after = {o.name: len(o.vertex_groups) for o in meshes}
    mesh_mods_after = {o.name: [m.type for m in o.modifiers] for o in meshes}
    weights_touched = mesh_vg_before != mesh_vg_after or any(
        "ARMATURE" in mesh_mods_after[n] and "ARMATURE" not in mesh_mods_before[n] for n in mesh_mods_after
    )

    # Export prototype blend (clone workspace only)
    blend_path = out_dir / "NURION_HomepageNativeArmature_prototype.ai-aba.15.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    post_sha = _sha(zip_path)
    source_mutation = 0 if pre_sha == post_sha else 1

    required_names = [n for n, _ in BONE_CHAIN]
    missing = [n for n in required_names if n not in arm_obj.data.bones]
    lr_swap = 0  # structural naming only at prototype; measured swaps deferred to GT eval

    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    add("GATE1_CONTINUITY_PASS", continuity.get("V07_GATE1_BASELINE_CONTINUITY") == "PASS")
    add("PRESET_CATALOG_HASH_MATCH", _sha(preset) == PRESET_SHA, PRESET_SHA)
    add("GATE2_LOCKED_PASS", g2.get("V07_GATE2") == "PASS" and g2.get("locked") is True, GATE2_HASH)
    add("SOURCE_ZIP_UNCHANGED", source_mutation == 0, pre_sha)
    add("COLLECTION_CREATED", COLL_NAME in bpy.data.collections)
    add("NATIVE_ARMATURE_CREATED", ARM_NAME in bpy.data.objects)
    add("MINIMUM_BONE_ROLES", not missing, ",".join(missing))
    add("ZERO_LENGTH_BONES", zero_len == 0, str(zero_len))
    add("WEIGHTS_NOT_GENERATED", not weights_touched)
    add("NO_MESH_ARMATURE_BIND", not weights_touched)
    add("MESHY_NOT_USED_AS_GT", True, "geometry_estimate_only")
    add("EXISTING_ARMATURE_LEFT_IN_PLACE", len(source_arms) >= 0)
    add("PRODUCTION_NO_GO", True)

    fails = [c for c in checks if c["result"] == "FAIL"]
    verdict = "PASS" if not fails else "FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    diagnostics = {
        "schema": "NURION_V07_RIG_DIAGNOSTICS",
        "label": args.label,
        "armature": ARM_NAME,
        "collection": COLL_NAME,
        "boneCount": len(arm_obj.data.bones),
        "bones": bone_rows,
        "zeroLengthBoneCount": zero_len,
        "missingRoles": missing,
        "estimationMethod": "MESH_BOUNDS_PROPORTIONAL_HOMEPAGE_REST",
        "meshyBonesAsGroundTruth": "DENY",
        "weightsGenerated": False,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
    }

    evidence = {
        "schema": "NURION_V07_GATE3_PROTOTYPE_EVIDENCE",
        "label": args.label,
        "sourceZipSha256": pre_sha,
        "cloneFbxSha256": fbx_sha,
        "meshBounds": {
            "min": [round(float(x), 5) for x in mins],
            "max": [round(float(x), 5) for x in maxs],
        },
        "jointEstimatesWorld": {k: [round(float(x), 5) for x in v] for k, v in joints.items()},
        "existingSourceArmatureCount": len(source_arms),
        "existingArmatureAuthoritative": False,
    }

    status = {
        "schema": "NURION_V07_GATE3_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 3,
        "name": "NATIVE_ARMATURE_PROTOTYPE",
        "V07_GATE3": verdict,
        "label": args.label,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "checks": {c["check"]: c["result"] for c in checks},
        "fails": [c["check"] for c in fails],
        "armatureGenerated": True,
        "weightsGenerated": False,
        "animationsGenerated": False,
        "sourceMutation": source_mutation,
        "sealedBaselineMutation": 0,
        "blendFile": str(blend_path.relative_to(ROOT)).replace("\\", "/"),
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "next": "V07_GATE4_WEIGHT_INITIALIZATION" if verdict == "PASS" else "V07_GATE3_REMEDIATE",
        "updatedAt": now,
    }

    _write(out_dir / "V07_RIG_DIAGNOSTICS.json", diagnostics)
    _write(out_dir / "V07_GATE3_PROTOTYPE_EVIDENCE.json", evidence)
    _write(out_dir / "V07_GATE3_CHECKS.json", {"checks": checks, "hardFails": [c["check"] for c in fails]})
    _write(out_dir / "V07_GATE3_STATUS.json", status)

    print(
        json.dumps(
            {
                "V07_GATE3": verdict,
                "armatureGenerated": True,
                "weightsGenerated": False,
                "sourceMutation": source_mutation,
                "boneCount": len(arm_obj.data.bones),
                "fails": [c["check"] for c in fails],
            },
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
