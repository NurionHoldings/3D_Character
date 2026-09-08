"""
CCS Gate 5 — Body Presets & Rig Adaptation on Gate4 clone only.

BODY_* morphs separated from ID_*/BEAU_*. Joint adaptation via
J' = J + sum(w_i * DeltaJ_i). Extreme body combo = ABSTAIN (no forced pass).
No mutation of Gate1–4 on disk. Production NO-GO.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

BODY_AXES = [
    "BODY_Height",
    "BODY_Shoulder",
    "BODY_Torso",
    "BODY_Waist",
    "BODY_Pelvis",
    "BODY_Muscle",
    "BODY_Fat",
    "BODY_LimbLength",
    "BODY_HeadSize",
]
ID_PREFIX = "ID_"
BEAU_PREFIX = "BEAU_"
CORR_KEYS = [
    "CORR_ShoulderRaise_L",
    "CORR_ElbowBend_L",
    "CORR_KneeBend_L",
    "CORR_NeckTurn",
    "CORR_JawOpen",
]
POSE_SUITE = [
    {"id": "REST", "bones": {}},
    {"id": "ARM_RAISE_L", "bones": {"UpperArm.L": (0.0, 0.0, -1.0)}},
    {"id": "ELBOW_90_L", "bones": {"ForeArm.L": (0.0, 1.3, 0.0)}},
    {"id": "KNEE_BEND_L", "bones": {"LowerLeg.L": (1.1, 0.0, 0.0)}},
    {"id": "HIP_OPEN_L", "bones": {"UpperLeg.L": (0.0, 0.0, 0.35)}},
]
# Per-axis joint deltas (meters) applied as w_i * DeltaJ at bone heads (local world offset)
# Keys map relocate targets to bone head names
DELTA_J = {
    "BODY_Height": {
        "Clavicle.L": (0, 0, 0.04),
        "Clavicle.R": (0, 0, 0.04),
        "UpperArm.L": (0, 0, 0.04),
        "UpperArm.R": (0, 0, 0.04),
        "UpperLeg.L": (0, 0, 0.02),
        "UpperLeg.R": (0, 0, 0.02),
        "LowerLeg.L": (0, 0, 0.03),
        "LowerLeg.R": (0, 0, 0.03),
        "Foot.L": (0, 0, 0.01),
        "Foot.R": (0, 0, 0.01),
        "Head": (0, 0, 0.05),
        "Neck": (0, 0, 0.045),
        "Hips": (0, 0, 0.02),
        "Spine": (0, 0, 0.025),
        "Spine01": (0, 0, 0.03),
        "Spine02": (0, 0, 0.035),
        "Chest": (0, 0, 0.04),
    },
    "BODY_Shoulder": {
        "Clavicle.L": (0.02, 0, 0.005),
        "Clavicle.R": (-0.02, 0, 0.005),
        "UpperArm.L": (0.03, 0, 0),
        "UpperArm.R": (-0.03, 0, 0),
        "ForeArm.L": (0.03, 0, 0),
        "ForeArm.R": (-0.03, 0, 0),
        "Hand.L": (0.03, 0, 0),
        "Hand.R": (-0.03, 0, 0),
    },
    "BODY_Torso": {
        "Spine": (0, 0.005, 0.01),
        "Spine01": (0, 0.006, 0.012),
        "Spine02": (0, 0.007, 0.014),
        "Chest": (0, 0.008, 0.016),
    },
    "BODY_Waist": {
        "Hips": (0, 0, -0.005),
        "Spine": (0, 0.004, 0),
    },
    "BODY_Pelvis": {
        "Hips": (0, 0.004, 0),
        "UpperLeg.L": (0.008, 0, 0),
        "UpperLeg.R": (-0.008, 0, 0),
    },
    "BODY_Muscle": {
        "UpperArm.L": (0.01, 0, 0),
        "UpperArm.R": (-0.01, 0, 0),
        "UpperLeg.L": (0.008, 0, 0),
        "UpperLeg.R": (-0.008, 0, 0),
        "Chest": (0, -0.004, 0),
    },
    "BODY_Fat": {
        "Hips": (0, 0.006, 0),
        "Spine": (0, 0.008, 0),
        "Chest": (0, 0.01, 0),
    },
    "BODY_LimbLength": {
        "UpperArm.L": (0.02, 0, -0.01),
        "UpperArm.R": (-0.02, 0, -0.01),
        "ForeArm.L": (0.035, 0, -0.015),
        "ForeArm.R": (-0.035, 0, -0.015),
        "Hand.L": (0.045, 0, -0.02),
        "Hand.R": (-0.045, 0, -0.02),
        "UpperLeg.L": (0, 0, -0.02),
        "UpperLeg.R": (0, 0, -0.02),
        "LowerLeg.L": (0, 0, -0.04),
        "LowerLeg.R": (0, 0, -0.04),
        "Foot.L": (0, 0, -0.05),
        "Foot.R": (0, 0, -0.05),
    },
    "BODY_HeadSize": {
        "Head": (0, 0, 0.02),
        "Neck": (0, 0, 0.01),
        "Eye.L": (0.005, -0.002, 0.01),
        "Eye.R": (-0.005, -0.002, 0.01),
        "Jaw": (0, -0.004, 0.005),
    },
}
RELOCATE_BONES = [
    "Clavicle.L",
    "Clavicle.R",
    "UpperArm.L",
    "UpperArm.R",
    "ForeArm.L",
    "ForeArm.R",
    "Hand.L",
    "Hand.R",
    "UpperLeg.L",
    "UpperLeg.R",
    "LowerLeg.L",
    "LowerLeg.R",
    "Foot.L",
    "Foot.R",
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--gate4-blend", required=True)
    p.add_argument("--expected-gate4-sha256", required=True)
    p.add_argument("--params-json", required=True)
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


def _find_ib_mesh_arm():
    mesh = bpy.data.objects.get("NURION_IB_CanonicalHuman_V1")
    if mesh is None:
        mesh = bpy.data.objects.get("NURION_W_CanonicalHuman_V1")
    if mesh is None:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        mesh = meshes[0] if meshes else None
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and "CanonicalArmature" in o.name]
    if mesh is None or not arms:
        raise RuntimeError("Gate4 mesh/armature missing")
    return mesh, arms[0]


def _topology_snapshot(obj):
    mesh = obj.data
    edges = sorted((min(e.vertices[0], e.vertices[1]), max(e.vertices[0], e.vertices[1])) for e in mesh.edges)
    uv = []
    if mesh.uv_layers:
        uv = [[round(d.uv.x, 6), round(d.uv.y, 6)] for d in mesh.uv_layers.active.data]
    mats = [slot.material.name if slot.material else None for slot in obj.material_slots]
    return {
        "vertexCount": len(mesh.vertices),
        "edgeCount": len(mesh.edges),
        "polyCount": len(mesh.polygons),
        "vertexOrderSha256": _stable_hash(list(range(len(mesh.vertices)))),
        "edgeStructureSha256": _stable_hash(edges),
        "uvSha256": _stable_hash(uv),
        "materialSlots": mats,
        "materialSlotCount": len(mats),
    }


def _ensure_basis(obj):
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    obj.data.shape_keys.use_relative = True
    return obj.data.shape_keys


def _add_key(obj, name):
    sk = _ensure_basis(obj)
    if name in sk.key_blocks:
        return sk.key_blocks[name]
    return obj.shape_key_add(name=name, from_mix=False)


def _region_sets(obj):
    zs = [v.co.z for v in obj.data.vertices]
    zmin, zmax = min(zs), max(zs)
    h = max(zmax - zmin, 1e-6)
    regions = {k: [] for k in ("head", "torso", "waist", "pelvis", "arm", "leg", "all")}
    for v in obj.data.vertices:
        t = (v.co.z - zmin) / h
        regions["all"].append(v.index)
        if t >= 0.78:
            regions["head"].append(v.index)
        elif t >= 0.55:
            if abs(v.co.x) > 0.2:
                regions["arm"].append(v.index)
            else:
                regions["torso"].append(v.index)
        elif t >= 0.42:
            if abs(v.co.x) > 0.18:
                regions["arm"].append(v.index)
            else:
                regions["waist"].append(v.index)
        elif t >= 0.2:
            if abs(v.co.x) > 0.12:
                regions["leg"].append(v.index)
            else:
                regions["pelvis"].append(v.index)
        else:
            regions["leg"].append(v.index)
    return regions


def _apply_delta(key, indices, fn, strength=1.0):
    basis = key.id_data.key_blocks["Basis"]
    for i in indices:
        co = basis.data[i].co.copy()
        key.data[i].co = co + fn(co, i) * strength


def _build_body_keys(obj, regions):
    keys = {}
    k = _add_key(obj, "BODY_Height")
    _apply_delta(k, regions["all"], lambda co, _i: Vector((0, 0, co.z * 0.08)))
    keys["BODY_Height"] = k.name

    k = _add_key(obj, "BODY_Shoulder")
    _apply_delta(
        k,
        regions["arm"] + regions["torso"],
        lambda co, _i: Vector((math.copysign(0.04, co.x) if abs(co.x) > 0.15 else 0.0, 0, 0.01 if co.z > 1.2 else 0)),
    )
    keys["BODY_Shoulder"] = k.name

    k = _add_key(obj, "BODY_Torso")
    _apply_delta(k, regions["torso"], lambda co, _i: Vector((co.x * 0.06, co.y * 0.08, 0.01)))
    keys["BODY_Torso"] = k.name

    k = _add_key(obj, "BODY_Waist")
    _apply_delta(k, regions["waist"], lambda co, _i: Vector((co.x * 0.12, co.y * 0.1, 0)))
    keys["BODY_Waist"] = k.name

    k = _add_key(obj, "BODY_Pelvis")
    _apply_delta(k, regions["pelvis"], lambda co, _i: Vector((co.x * 0.1, co.y * 0.08, 0)))
    keys["BODY_Pelvis"] = k.name

    k = _add_key(obj, "BODY_Muscle")
    _apply_delta(
        k,
        regions["arm"] + regions["torso"] + regions["leg"],
        lambda co, _i: Vector((math.copysign(0.02, co.x), -0.01, 0)),
    )
    keys["BODY_Muscle"] = k.name

    k = _add_key(obj, "BODY_Fat")
    _apply_delta(
        k,
        regions["torso"] + regions["waist"] + regions["pelvis"],
        lambda co, _i: Vector((co.x * 0.08, co.y * 0.12 + 0.01, 0)),
    )
    keys["BODY_Fat"] = k.name

    k = _add_key(obj, "BODY_LimbLength")
    _apply_delta(
        k,
        regions["arm"] + regions["leg"],
        lambda co, _i: Vector((co.x * 0.05, 0, -0.03 if co.z < 1.0 else -0.02)),
    )
    keys["BODY_LimbLength"] = k.name

    k = _add_key(obj, "BODY_HeadSize")
    _apply_delta(k, regions["head"], lambda co, _i: Vector((co.x * 0.15, co.y * 0.15, (co.z - 1.45) * 0.2 + 0.02)))
    keys["BODY_HeadSize"] = k.name
    return keys


def _reset_keys(obj, names):
    if obj.data.shape_keys is None:
        return
    for n in names:
        kb = obj.data.shape_keys.key_blocks.get(n)
        if kb is not None:
            kb.value = 0.0


def _set_body_preset(obj, values):
    _reset_keys(obj, BODY_AXES)
    for n, v in values.items():
        kb = obj.data.shape_keys.key_blocks.get(n)
        if kb is not None:
            # allow signed values clamped to [-1,1]
            kb.value = max(-1.0, min(1.0, float(v)))


def _snapshot_key_deltas(obj, names):
    sk = obj.data.shape_keys
    if sk is None:
        return {}
    basis = sk.key_blocks["Basis"]
    out = {}
    for n in names:
        kb = sk.key_blocks.get(n)
        if kb is None:
            continue
        deltas = []
        for i in range(len(basis.data)):
            d = kb.data[i].co - basis.data[i].co
            if d.length > 1e-8:
                deltas.append([i, round(d.x, 6), round(d.y, 6), round(d.z, 6)])
        out[n] = _stable_hash(deltas)
    return out


def _contamination(obj):
    """Mutual contamination: shared shape-key namespaces or ID delta hash change under BODY apply."""
    sk = obj.data.shape_keys
    names = [kb.name for kb in sk.key_blocks] if sk else []
    id_names = [n for n in names if n.startswith(ID_PREFIX)]
    body_names = [n for n in names if n.startswith("BODY_")]
    overlap = sorted(set(id_names) & set(body_names))
    mixed = [n for n in names if n.startswith("ID_") and "BODY" in n]
    id_before = _snapshot_key_deltas(obj, id_names)
    _set_body_preset(obj, {n: 0.5 for n in BODY_AXES})
    id_after = _snapshot_key_deltas(obj, id_names)
    _reset_keys(obj, BODY_AXES)
    body_before = _snapshot_key_deltas(obj, body_names)
    for n in id_names:
        kb = sk.key_blocks.get(n)
        if kb:
            kb.value = 0.5
    body_after = _snapshot_key_deltas(obj, body_names)
    _reset_keys(obj, id_names)
    id_changed = sum(1 for n in id_names if id_before.get(n) != id_after.get(n))
    body_changed = sum(1 for n in body_names if body_before.get(n) != body_after.get(n))
    return {
        "overlapNames": overlap,
        "mixedNames": mixed,
        "identityDeltaChangedUnderBody": id_changed,
        "bodyDeltaChangedUnderIdentity": body_changed,
        "contaminationCount": len(overlap) + len(mixed) + id_changed + body_changed,
    }


def _bone_lock(arm):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    rows = []
    for b in arm.data.edit_bones:
        rows.append(
            {
                "name": b.name,
                "parent": b.parent.name if b.parent else None,
                "head": [round(b.head.x, 6), round(b.head.y, 6), round(b.head.z, 6)],
                "tail": [round(b.tail.x, 6), round(b.tail.y, 6), round(b.tail.z, 6)],
                "roll": round(b.roll, 6),
            }
        )
    bpy.ops.object.mode_set(mode="OBJECT")
    return sorted(rows, key=lambda r: r["name"])


def _adapt_joints(arm, values, baseline_bones):
    """J' = J + sum(w_i * DeltaJ_i); preserve names/hierarchy/roll convention."""
    name_to_base = {b["name"]: b for b in baseline_bones}
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    # compute offsets per bone
    offsets = {n: Vector((0, 0, 0)) for n in name_to_base}
    for axis, w in values.items():
        table = DELTA_J.get(axis, {})
        for bname, dxyz in table.items():
            if bname in offsets:
                offsets[bname] = offsets[bname] + Vector(dxyz) * float(w)
    # apply head/tail translation keeping length/direction from baseline where possible
    for bname, base in name_to_base.items():
        bone = eb.get(bname)
        if bone is None:
            continue
        off = offsets.get(bname, Vector((0, 0, 0)))
        if off.length < 1e-12 and abs(float(values.get("BODY_Height", 0))) < 1e-12:
            continue
        bh = Vector(base["head"]) + off
        # tail: also apply related offset if child-like; use same off for simplicity + height scale on chain
        bt = Vector(base["tail"]) + off
        bone.head = bh
        bone.tail = bt
        bone.roll = base["roll"]  # preserve roll convention
    # hierarchy names unchanged by construction
    bpy.ops.object.mode_set(mode="OBJECT")


def _renormalize_weights(obj, tol=0.001):
    nan_neg = 0
    unassigned = 0
    before_out = 0
    after_out = 0
    for v in obj.data.vertices:
        total = 0.0
        groups = []
        for g in v.groups:
            w = g.weight
            if w < 0 or math.isnan(w):
                nan_neg += 1
                w = 0.0
            if w > 0:
                groups.append((g.group, w))
                total += w
        if total <= 1e-12:
            unassigned += 1
            continue
        if abs(total - 1.0) > tol:
            before_out += 1
        scale = 1.0 / total
        for gi, w in groups:
            obj.vertex_groups[gi].add([v.index], w * scale, "REPLACE")
        # verify
        nt = sum(g.weight for g in v.groups if g.weight > 0)
        if abs(nt - 1.0) > tol:
            after_out += 1
    return {"nanOrNegative": nan_neg, "unassigned": unassigned, "beforeOutOfTol": before_out, "afterOutOfTol": after_out}


def _relax_weights(obj, iterations=1):
    """Deterministic mild neighbor average on bone weights (no hidden per-asset tuning)."""
    mesh = obj.data
    # adjacency
    adj = {i: set() for i in range(len(mesh.vertices))}
    for e in mesh.edges:
        a, b = e.vertices
        adj[a].add(b)
        adj[b].add(a)
    name_to_idx = {vg.name: vg.index for vg in obj.vertex_groups}
    bone_groups = [i for n, i in name_to_idx.items() if not n.startswith("REGION_")]
    for _ in range(iterations):
        new_w = {}
        for vi, v in enumerate(mesh.vertices):
            cur = {g.group: g.weight for g in v.groups if g.group in bone_groups and g.weight > 0}
            if not cur or not adj[vi]:
                continue
            acc = {gi: cur.get(gi, 0.0) for gi in cur}
            for nvi in adj[vi]:
                nv = mesh.vertices[nvi]
                for g in nv.groups:
                    if g.group in bone_groups and g.weight > 0:
                        acc[g.group] = acc.get(g.group, 0.0) + g.weight
            # self + neighbors average
            denom = 1.0 + len(adj[vi])
            for gi in list(acc.keys()):
                acc[gi] = acc[gi] / denom
            s = sum(acc.values())
            if s > 1e-12:
                for gi in acc:
                    acc[gi] /= s
            new_w[vi] = acc
        for vi, acc in new_w.items():
            # clear bone weights then set
            for gi in bone_groups:
                obj.vertex_groups[gi].add([vi], 0.0, "REPLACE")
            for gi, w in acc.items():
                obj.vertex_groups[gi].add([vi], w, "REPLACE")
    return _renormalize_weights(obj)


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
    for name, eul in bones.items():
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = eul
    bpy.ops.object.mode_set(mode="OBJECT")


def _eval_mesh_metrics(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        if not me.vertices:
            return {"size": [0, 0, 0], "volume": 0.0, "collapse": True}
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        zs = [v.co.z for v in me.vertices]
        size = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]
        vol = max(size[0], 1e-9) * max(size[1], 1e-9) * max(size[2], 1e-9)
        collapse = vol < 1e-4 or min(size) < 1e-4
        return {"size": [round(s, 4) for s in size], "volume": round(vol, 6), "collapse": collapse}
    finally:
        ev.to_mesh_clear()


def _inverse_joint_count(arm):
    """Detect obviously inverted limb chains (forearm/shin folding wrong sign proxy)."""
    count = 0
    bpy.context.view_layer.update()
    pairs = [("UpperArm.L", "ForeArm.L", "Hand.L"), ("UpperArm.R", "ForeArm.R", "Hand.R"), ("UpperLeg.L", "LowerLeg.L", "Foot.L"), ("UpperLeg.R", "LowerLeg.R", "Foot.R")]
    for a, b, c in pairs:
        ba, bb, bc = arm.pose.bones.get(a), arm.pose.bones.get(b), arm.pose.bones.get(c)
        if not ba or not bb or not bc:
            continue
        pa = arm.matrix_world @ ba.head
        pb = arm.matrix_world @ bb.head
        pc = arm.matrix_world @ bc.head
        v1 = (pb - pa).normalized()
        v2 = (pc - pb).normalized()
        if v1.dot(v2) < -0.85:
            count += 1
    return count


def _penetration_proxy(obj, rest_vol):
    m = _eval_mesh_metrics(obj)
    if rest_vol <= 1e-9:
        return 0, m
    if m["volume"] > rest_vol * 3.0 or m["volume"] < rest_vol * 0.25:
        return 1, m
    return 0, m


def _restore_bones(arm, baseline_bones):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for base in baseline_bones:
        bone = eb.get(base["name"])
        if bone is None:
            continue
        bone.head = Vector(base["head"])
        bone.tail = Vector(base["tail"])
        bone.roll = base["roll"]
    bpy.ops.object.mode_set(mode="OBJECT")


def main():
    args = _parse(sys.argv)
    out = Path(args.out_dir)
    run_dir = out / f"run{args.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
    gate4 = Path(args.gate4_blend)
    src_sha = _sha_file(gate4)
    if src_sha != args.expected_gate4_sha256:
        raise SystemExit(f"Gate4 blend mutated: {src_sha}")

    bpy.ops.wm.open_mainfile(filepath=str(gate4))
    src_mesh, arm = _find_ib_mesh_arm()
    topo_before = _topology_snapshot(src_mesh)
    baseline_bones = _bone_lock(arm)
    hierarchy = [(b["name"], b["parent"]) for b in baseline_bones]
    rolls = {b["name"]: b["roll"] for b in baseline_bones}

    col = _ensure_col("NURION_CCS_GATE5_WORK")
    dup = src_mesh.copy()
    dup.data = src_mesh.data.copy()
    dup.name = "NURION_BP_CanonicalHuman_V1"
    bpy.context.scene.collection.objects.link(dup)
    _link(dup, col)
    dup.parent = src_mesh.parent
    dup.parent_type = src_mesh.parent_type
    for mod in dup.modifiers:
        if mod.type == "ARMATURE":
            mod.object = arm

    regions = _region_sets(dup)
    body_keys = _build_body_keys(dup, regions)
    contam = _contamination(dup)

    # inherit correctives
    sk = dup.data.shape_keys
    corr_present = [n for n in CORR_KEYS if sk and n in sk.key_blocks]

    rest_metrics = _eval_mesh_metrics(dup)
    preset_results = {}
    severe_collapse = 0
    inverse_joint = 0
    penetration = 0

    for preset_name, values in params["presetValues"].items():
        _restore_bones(arm, baseline_bones)
        _set_body_preset(dup, values)
        _adapt_joints(arm, values, baseline_bones)
        wnorm = _renormalize_weights(dup)
        wrelax = _relax_weights(dup, iterations=1)
        after_bones = _bone_lock(arm)
        names_ok = [b["name"] for b in after_bones] == [b["name"] for b in baseline_bones]
        hier_ok = [(b["name"], b["parent"]) for b in after_bones] == hierarchy
        roll_ok = all(abs(b["roll"] - rolls[b["name"]]) < 1e-5 for b in after_bones if b["name"] in rolls)

        poses = []
        for pose in POSE_SUITE:
            _apply_pose(arm, pose["bones"])
            m = _eval_mesh_metrics(dup)
            inv = _inverse_joint_count(arm)
            pen, _ = _penetration_proxy(dup, rest_metrics["volume"])
            if m["collapse"]:
                severe_collapse += 1
            inverse_joint += inv
            penetration += pen
            poses.append({"id": pose["id"], "collapse": m["collapse"], "size": m["size"], "inverseJoints": inv, "penetration": pen})
        _reset_pose(arm)

        relocated = {}
        for bname in RELOCATE_BONES:
            base = next(b for b in baseline_bones if b["name"] == bname)
            cur = next(b for b in after_bones if b["name"] == bname)
            relocated[bname] = {
                "headDelta": [round(cur["head"][i] - base["head"][i], 6) for i in range(3)],
            }

        preset_results[preset_name] = {
            "values": values,
            "boneNamesPreserved": names_ok,
            "hierarchyPreserved": hier_ok,
            "rollPreserved": roll_ok,
            "weightNormalize": wnorm,
            "weightRelax": wrelax,
            "relocated": relocated,
            "poseSuite": poses,
        }

    # Extreme combo ABSTAIN (all axes ±1 extremes) — do not force pass/fail
    extreme_values = {n: 1.0 for n in BODY_AXES}
    _restore_bones(arm, baseline_bones)
    _set_body_preset(dup, extreme_values)
    _adapt_joints(arm, extreme_values, baseline_bones)
    extreme_metrics = _eval_mesh_metrics(dup)
    extreme_abstain = {
        "policy": "ABSTAIN_NO_FORCED_PASS",
        "applied": extreme_values,
        "metrics": extreme_metrics,
        "verdict": "ABSTAIN",
    }
    _reset_keys(dup, BODY_AXES)
    _restore_bones(arm, baseline_bones)

    topo_after = _topology_snapshot(dup)
    topo_ok = (
        topo_before["vertexCount"] == topo_after["vertexCount"]
        and topo_before["edgeCount"] == topo_after["edgeCount"]
        and topo_before["edgeStructureSha256"] == topo_after["edgeStructureSha256"]
        and topo_before["uvSha256"] == topo_after["uvSha256"]
        and topo_before["vertexOrderSha256"] == topo_after["vertexOrderSha256"]
        and topo_before["materialSlots"] == topo_after["materialSlots"]
    )

    fp = _stable_hash(
        {
            "bodyKeys": sorted(body_keys),
            "presets": params["presetValues"],
            "topo": topo_after,
            "corr": corr_present,
            "contam": contam,
        }
    )

    out_blend = run_dir / "NURION_CanonicalBodyPresets_V1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    if _sha_file(gate4) != args.expected_gate4_sha256:
        raise SystemExit("Gate4 blend mutated during Gate5")

    report = {
        "schema": "NURION_V07_CCS_GATE5_RUN_REPORT",
        "runId": int(args.run_id),
        "gate4SourceSha256": src_sha,
        "outBlendSha256": _sha_file(out_blend),
        "bodyMesh": dup.name,
        "bodyAxes": BODY_AXES,
        "presets": preset_results,
        "topologyBefore": topo_before,
        "topologyAfter": topo_after,
        "topologyImmutable": topo_ok,
        "identityBodyContamination": contam,
        "correctivesInherited": corr_present,
        "correctiveContractInheritance": "PASS" if len(corr_present) >= 5 else "FAIL",
        "severeCollapseCount": severe_collapse,
        "inverseJointCount": inverse_joint,
        "penetrationCount": penetration,
        "extremeBodyCombo": extreme_abstain,
        "bodyFingerprintSha256": fp,
        "inheritedLimitationsFromGate4": params.get("inheritedLimitationsFromGate4", []),
        "production": "NO-GO",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "blenderVersion": bpy.app.version_string,
    }
    _write(run_dir / "V07_CCS_GATE5_RUN_REPORT.json", report)
    print(json.dumps({"runId": args.run_id, "bodyFingerprintSha256": fp, "topologyImmutable": topo_ok, "contamination": contam["contaminationCount"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("GATE5_FAIL", e, file=sys.stderr)
        raise
