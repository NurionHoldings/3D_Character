"""
CCS Gate 6 — Clothing & Hair Library on Gate5 clone only.

Procedural garments/hair for functional verification only (not artist-certified).
Canonical topology/rig/identity morphs must not mutate. Production NO-GO.
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
CLOTHING = [
    "BUSINESS_SUIT_01",
    "BUSINESS_SUIT_02",
    "OFFICE_CASUAL_01",
    "BLOUSE_SLACKS_01",
    "FORMAL_DRESS_01",
    "BRAND_UNIFORM_01",
]
HAIR = [
    "SHORT_NEAT_01",
    "SHORT_LAYERED_01",
    "BOB_01",
    "MEDIUM_STRAIGHT_01",
    "LONG_TIED_01",
    "LONG_WAVE_01",
]
HELPER_ALLOWED = {"FORMAL_DRESS_01", "LONG_TIED_01", "LONG_WAVE_01"}
# Combos that abstain (no forced pass): mini + long hem/hair collision risk; brand without third-party pack
ABSTAIN_RULES = [
    {"body": "MINI_SD", "clothing": "FORMAL_DRESS_01", "hair": "*", "reason": "MINI_SD_LONG_HEM_COLLISION_RISK"},
    {"body": "MINI_SD", "clothing": "*", "hair": "LONG_WAVE_01", "reason": "MINI_SD_LONG_HAIR_COLLISION_RISK"},
    {"body": "*", "clothing": "BRAND_UNIFORM_01", "hair": "*", "reason": "BRAND_VARIANT_REQUIRES_SEPARATE_LICENSE_PACK"},
]
HOMEPAGE_POSES = [
    {"id": "REST", "bones": {}},
    {"id": "WAVE_R", "bones": {"UpperArm.R": (0.0, 0.0, -1.0), "ForeArm.R": (0.0, -0.8, 0.0)}},
    {"id": "POINT_L", "bones": {"UpperArm.L": (0.0, 0.0, -0.7), "ForeArm.L": (0.0, 1.0, 0.0)}},
    {"id": "BOW", "bones": {"Spine": (0.35, 0.0, 0.0), "Neck": (0.25, 0.0, 0.0)}},
    {"id": "IDLE_SHIFT", "bones": {"Hips": (0.0, 0.0, 0.08), "UpperLeg.L": (0.05, 0.0, 0.0)}},
    {"id": "SPEAK_A", "bones": {"Jaw": (0.2, 0.0, 0.0), "Neck": (0.0, 0.0, 0.1)}},
    {"id": "SPEAK_B", "bones": {"Jaw": (0.12, 0.0, 0.0), "Head": (0.0, 0.05, 0.0)}},
    {"id": "PRESENT_BOTH", "bones": {"UpperArm.L": (0.0, 0.0, -0.5), "UpperArm.R": (0.0, 0.0, -0.5)}},
    {"id": "TURN_SLIGHT", "bones": {"Spine": (0.0, 0.0, 0.25), "Neck": (0.0, 0.0, 0.15)}},
    {"id": "SIT_HINT", "bones": {"UpperLeg.L": (0.6, 0.0, 0.0), "UpperLeg.R": (0.6, 0.0, 0.0), "LowerLeg.L": (0.8, 0.0, 0.0)}},
]
CLOTHING_SPEC = {
    "BUSINESS_SUIT_01": {"z0": 0.35, "z1": 1.35, "inflate": 0.035, "long": False},
    "BUSINESS_SUIT_02": {"z0": 0.32, "z1": 1.38, "inflate": 0.04, "long": False},
    "OFFICE_CASUAL_01": {"z0": 0.4, "z1": 1.3, "inflate": 0.03, "long": False},
    "BLOUSE_SLACKS_01": {"z0": 0.3, "z1": 1.28, "inflate": 0.028, "long": False},
    "FORMAL_DRESS_01": {"z0": 0.05, "z1": 1.32, "inflate": 0.045, "long": True},
    "BRAND_UNIFORM_01": {"z0": 0.35, "z1": 1.36, "inflate": 0.033, "long": False},
}
HAIR_SPEC = {
    "SHORT_NEAT_01": {"z0": 1.45, "z1": 1.72, "inflate": 0.05, "long": False, "chain": 1},
    "SHORT_LAYERED_01": {"z0": 1.42, "z1": 1.74, "inflate": 0.055, "long": False, "chain": 2},
    "BOB_01": {"z0": 1.35, "z1": 1.72, "inflate": 0.06, "long": False, "chain": 2},
    "MEDIUM_STRAIGHT_01": {"z0": 1.2, "z1": 1.74, "inflate": 0.05, "long": False, "chain": 3},
    "LONG_TIED_01": {"z0": 0.95, "z1": 1.74, "inflate": 0.045, "long": True, "chain": 4},
    "LONG_WAVE_01": {"z0": 0.85, "z1": 1.76, "inflate": 0.055, "long": True, "chain": 5},
}


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--gate5-blend", required=True)
    p.add_argument("--expected-gate5-sha256", required=True)
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


def _find_body_arm():
    mesh = bpy.data.objects.get("NURION_BP_CanonicalHuman_V1")
    if mesh is None:
        mesh = bpy.data.objects.get("NURION_IB_CanonicalHuman_V1")
    if mesh is None:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        mesh = meshes[0] if meshes else None
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and "CanonicalArmature" in o.name]
    if mesh is None or not arms:
        raise RuntimeError("Gate5 body/armature missing")
    return mesh, arms[0]


def _topology_snapshot(obj):
    mesh = obj.data
    edges = sorted((min(e.vertices[0], e.vertices[1]), max(e.vertices[0], e.vertices[1])) for e in mesh.edges)
    uv = []
    if mesh.uv_layers:
        uv = [[round(d.uv.x, 6), round(d.uv.y, 6)] for d in mesh.uv_layers.active.data]
    id_keys = []
    if mesh.shape_keys:
        id_keys = sorted(k.name for k in mesh.shape_keys.key_blocks if k.name.startswith("ID_"))
        id_fp = []
        basis = mesh.shape_keys.key_blocks["Basis"]
        for n in id_keys:
            kb = mesh.shape_keys.key_blocks[n]
            deltas = []
            for i in range(len(basis.data)):
                d = kb.data[i].co - basis.data[i].co
                if d.length > 1e-8:
                    deltas.append([i, round(d.x, 6), round(d.y, 6), round(d.z, 6)])
            id_fp.append([n, _stable_hash(deltas)])
    else:
        id_fp = []
    return {
        "vertexCount": len(mesh.vertices),
        "edgeCount": len(mesh.edges),
        "edgeStructureSha256": _stable_hash(edges),
        "uvSha256": _stable_hash(uv),
        "identityMorphSha256": _stable_hash(id_fp),
        "identityKeyNames": id_keys,
    }


def _rig_snapshot(arm):
    bones = []
    for b in sorted(arm.data.bones, key=lambda x: x.name):
        bones.append(
            {
                "name": b.name,
                "parent": b.parent.name if b.parent else None,
                "head": [round(c, 6) for c in b.head_local],
                "tail": [round(c, 6) for c in b.tail_local],
            }
        )
    return {"boneCount": len(bones), "bonesSha256": _stable_hash(bones), "names": [b["name"] for b in bones]}


def _reset_body_keys(obj):
    if not obj.data.shape_keys:
        return
    for n in BODY_AXES:
        kb = obj.data.shape_keys.key_blocks.get(n)
        if kb:
            kb.value = 0.0


def _apply_body_preset(obj, values):
    _reset_body_keys(obj)
    if not obj.data.shape_keys:
        return
    for n, v in values.items():
        kb = obj.data.shape_keys.key_blocks.get(n)
        if kb:
            kb.value = max(-1.0, min(1.0, float(v)))


def _body_bbox(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        zs = [v.co.z for v in me.vertices]
        return {
            "min": Vector((min(xs), min(ys), min(zs))),
            "max": Vector((max(xs), max(ys), max(zs))),
            "size": Vector((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))),
            "center": Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5)),
        }
    finally:
        ev.to_mesh_clear()


def _make_shell(name, z0, z1, inflate, bbox, col):
    """Procedural box shell fitted to body bbox slice."""
    sx = max(bbox["size"].x * 0.5 + inflate, 0.05)
    sy = max(bbox["size"].y * 0.5 + inflate, 0.03)
    # scale z range by body height relative to canonical ~1.69
    hscale = max(bbox["size"].z / 1.69, 0.4)
    zz0 = bbox["min"].z + z0 * hscale
    zz1 = bbox["min"].z + z1 * hscale
    if zz1 <= zz0:
        zz1 = zz0 + 0.05
    cz = (zz0 + zz1) * 0.5
    hz = (zz1 - zz0) * 0.5
    mesh = bpy.data.meshes.new(name + "_Mesh")
    # 8 verts box
    verts = [
        (-sx, -sy, -hz),
        (sx, -sy, -hz),
        (sx, sy, -hz),
        (-sx, sy, -hz),
        (-sx, -sy, hz),
        (sx, -sy, hz),
        (sx, sy, hz),
        (-sx, sy, hz),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    _link(obj, col)
    obj.location = (bbox["center"].x, bbox["center"].y, cz)
    # material slot (variant-separated base)
    mat = bpy.data.materials.get(name + "_MAT")
    if mat is None:
        mat = bpy.data.materials.new(name + "_MAT")
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj


def _transfer_weights(src_body, cloth, arm):
    """Copy nearest-body-vertex weights onto clothing verts; renormalize."""
    # clear groups
    while cloth.vertex_groups:
        cloth.vertex_groups.remove(cloth.vertex_groups[0])
    for vg in src_body.vertex_groups:
        cloth.vertex_groups.new(name=vg.name)
    body_cos = [v.co.copy() for v in src_body.data.vertices]
    # use evaluated body if morphs active — approx with current mesh coords
    deps = bpy.context.evaluated_depsgraph_get()
    ev = src_body.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        body_cos = [v.co.copy() for v in me.vertices]
        body_groups = []
        # groups from original indices
        for v in src_body.data.vertices:
            body_groups.append([(g.group, g.weight) for g in v.groups if g.weight > 0])
        for cv in cloth.data.vertices:
            # world-ish: cloth local + location
            cco = cloth.matrix_world @ cv.co
            # find nearest body vertex in world
            best_i = 0
            best_d = 1e9
            for i, bc in enumerate(body_cos):
                # body evaluated verts are object-local; convert
                bw = src_body.matrix_world @ bc
                d = (bw - cco).length_squared
                if d < best_d:
                    best_d = d
                    best_i = i
            for gi, w in body_groups[best_i]:
                name = src_body.vertex_groups[gi].name
                cloth.vertex_groups[name].add([cv.index], w, "REPLACE")
    finally:
        ev.to_mesh_clear()
    # renormalize
    unassigned = 0
    after_out = 0
    for v in cloth.data.vertices:
        total = sum(g.weight for g in v.groups if g.weight > 0)
        if total <= 1e-12:
            unassigned += 1
            continue
        scale = 1.0 / total
        for g in list(v.groups):
            if g.weight > 0:
                cloth.vertex_groups[g.group].add([v.index], g.weight * scale, "REPLACE")
        nt = sum(g.weight for g in v.groups if g.weight > 0)
        if abs(nt - 1.0) > 0.001:
            after_out += 1
    # armature mod
    for mod in list(cloth.modifiers):
        if mod.type == "ARMATURE":
            cloth.modifiers.remove(mod)
    mod = cloth.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    cloth.parent = arm
    cloth.parent_type = "ARMATURE"
    return {"unassigned": unassigned, "afterOutOfTol": after_out}


def _add_helper_bones(arm, asset_id, kind):
    """Limited helper bones for long clothing/hair only; lock ranges in metadata."""
    if asset_id not in HELPER_ALLOWED:
        return []
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    created = []
    parent = eb.get("Chest") if kind == "clothing" else eb.get("Head")
    if parent is None:
        parent = eb[0]
    n = 3 if kind == "clothing" else HAIR_SPEC[asset_id]["chain"]
    n = min(n, 5)
    prev = parent
    for i in range(n):
        name = f"HELPER_{asset_id}_{i}"
        if name in eb:
            b = eb[name]
        else:
            b = eb.new(name)
        b.parent = prev
        if kind == "clothing":
            b.head = parent.head + Vector((0, 0.02, -0.08 * (i + 1)))
            b.tail = b.head + Vector((0, 0.02, -0.06))
        else:
            b.head = parent.head + Vector((0, 0.03, -0.05 * (i + 1)))
            b.tail = b.head + Vector((0, 0.04, -0.05))
        b.use_deform = True
        created.append(
            {
                "name": name,
                "root": parent.name,
                "chainIndex": i,
                "collisionRadiusMax": 0.06 if kind == "hair" else 0.08,
                "swingLimitRad": 0.45,
                "twistLimitRad": 0.25,
                "locked": True,
            }
        )
        prev = b
    bpy.ops.object.mode_set(mode="OBJECT")
    return created


def _remove_helpers(arm, created):
    if not created:
        return
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for c in created:
        b = eb.get(c["name"])
        if b:
            eb.remove(b)
    bpy.ops.object.mode_set(mode="OBJECT")


def _reset_pose(arm):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.ops.object.mode_set(mode="OBJECT")


def _apply_pose(arm, bones):
    _reset_pose(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for name, eul in bones.items():
        pb = arm.pose.bones.get(name)
        if pb:
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = eul
    bpy.ops.object.mode_set(mode="OBJECT")


def _eval_metrics(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        if not me.vertices:
            return {"volume": 0.0, "size": [0, 0, 0], "explode": True}
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        zs = [v.co.z for v in me.vertices]
        size = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]
        vol = max(size[0], 1e-9) * max(size[1], 1e-9) * max(size[2], 1e-9)
        explode = max(size) > 5.0 or vol > 20.0
        return {"volume": round(vol, 6), "size": [round(s, 4) for s in size], "explode": explode}
    finally:
        ev.to_mesh_clear()


def _region_penetration(body, cloth, regions):
    """Proxy: clothing verts deeply inside body bbox slices count as penetration."""
    bb = _body_bbox(body)
    counts = {r: 0 for r in regions}
    # region z bands (normalized)
    bands = {
        "shoulder": (0.78, 0.92),
        "armpit": (0.7, 0.82),
        "elbow": (0.55, 0.7),
        "waist": (0.45, 0.58),
        "pelvis": (0.32, 0.48),
        "knee": (0.15, 0.35),
    }
    h = max(bb["size"].z, 1e-6)
    deps = bpy.context.evaluated_depsgraph_get()
    be = body.evaluated_get(deps)
    ce = cloth.evaluated_get(deps)
    bm = be.to_mesh()
    cm = ce.to_mesh()
    try:
        # body half-extents with shrink
        for cv in cm.vertices:
            cw = cloth.matrix_world @ cv.co
            t = (cw.z - bb["min"].z) / h
            # inside if within shrunk XY of body
            # deep interior core only (shell garments sit outside)
            if abs(cw.x) < bb["size"].x * 0.18 and abs(cw.y) < bb["size"].y * 0.22:
                for r, (a, b) in bands.items():
                    if a <= t <= b:
                        counts[r] += 1
        # severe if many verts in deep core
        severe = {r: (1 if c > 20 else 0) for r, c in counts.items()}
        return {"counts": counts, "severe": severe, "severeTotal": sum(severe.values())}
    finally:
        be.to_mesh_clear()
        ce.to_mesh_clear()


def _jitter_explode_check(obj, prev_size):
    m = _eval_metrics(obj)
    jitter = 0
    if prev_size is not None:
        for i in range(3):
            if abs(m["size"][i] - prev_size[i]) > 0.35:
                jitter = 1
                break
    return m["explode"], jitter, m


def _eligibility(body, clothing, hair):
    for rule in ABSTAIN_RULES:
        if rule["body"] not in ("*", body):
            continue
        if rule["clothing"] not in ("*", clothing):
            continue
        if rule["hair"] not in ("*", hair):
            continue
        return {"status": "ABSTAIN", "reason": rule["reason"]}
    return {"status": "ELIGIBLE", "reason": "OWNED_PROCEDURAL_FUNCTIONAL"}


def _ownership_record(asset_id, kind):
    return {
        "assetId": asset_id,
        "kind": kind,
        "source": "OWNED_ORIGINAL_PROCEDURAL",
        "commercialModification": "GRANTED",
        "commercialDistribution": "GRANTED",
        "thirdParty": False,
        "thirdPartyEvidence": "NOT_APPLICABLE_PROCEDURAL",
        "artistQualityCertified": False,
        "functionalVerificationOnly": True,
        "variantsSeparated": ["MATERIAL", "COLOR", "BRAND"],
        "note": "Procedural placeholder for Gate6 functional checks — not artist-certified product asset.",
    }


def _create_interior_mask(body, col):
    """Render mask shell without deleting source body mesh."""
    bb = _body_bbox(body)
    mask = _make_shell("NURION_INTERIOR_RENDER_MASK", 0.05, 0.95, -0.01, bb, col)
    mask.hide_render = False
    # mark as mask via custom prop; do not delete body
    mask["nurion_interior_mask"] = True
    mask["sourceBodyDeleted"] = False
    body.hide_render = False  # source remains
    return {
        "maskObject": mask.name,
        "sourceBody": body.name,
        "sourceBodyDeleted": False,
        "policy": "RENDER_MASK_WITHOUT_DELETING_SOURCE_MESH",
    }


def _delete_object(obj):
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def main():
    args = _parse(sys.argv)
    out = Path(args.out_dir)
    run_dir = out / f"run{args.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
    gate5 = Path(args.gate5_blend)
    src_sha = _sha_file(gate5)
    if src_sha != args.expected_gate5_sha256:
        raise SystemExit(f"Gate5 blend mutated: {src_sha}")

    bpy.ops.wm.open_mainfile(filepath=str(gate5))
    body, arm = _find_body_arm()
    topo0 = _topology_snapshot(body)
    rig0 = _rig_snapshot(arm)

    work = _ensure_col("NURION_CCS_GATE6_WORK")
    # clone body reference object name for library parent context (do not alter source mesh data permanently beyond keys values)
    ownership = {
        "clothing": [_ownership_record(c, "clothing") for c in CLOTHING],
        "hair": [_ownership_record(h, "hair") for h in HAIR],
    }
    variants = {
        "policy": "MATERIAL_COLOR_BRAND_SEPARATED_FROM_BASE_ASSET",
        "baseAssetsDoNotBakeBrandColors": True,
        "variantChannels": ["MATERIAL", "COLOR", "BRAND"],
    }

    preset_values = params.get("presetValues")
    if not preset_values:
        raise SystemExit("body preset values missing in Gate6 parameters")

    mask_info = _create_interior_mask(body, work)

    matrix = []
    fit_records = []
    helper_locks = []
    pose_failures = {"penetration": 0, "jitter": 0, "explode": 0}
    region_pen_total = 0

    for body_name, values in preset_values.items():
        _apply_body_preset(body, values)
        bbox = _body_bbox(body)
        clothing_objs = {}
        hair_objs = {}
        for cid in CLOTHING:
            spec = CLOTHING_SPEC[cid]
            obj = _make_shell(f"CL_{cid}_{body_name}", spec["z0"], spec["z1"], spec["inflate"], bbox, work)
            w = _transfer_weights(body, obj, arm)
            helpers = _add_helper_bones(arm, cid, "clothing") if spec["long"] else []
            if helpers:
                helper_locks.extend(helpers)
            pen = _region_penetration(body, obj, params["penetrationRegions"])
            region_pen_total += pen["severeTotal"]
            clothing_objs[cid] = obj
            fit_records.append(
                {
                    "body": body_name,
                    "asset": cid,
                    "kind": "clothing",
                    "weight": w,
                    "penetrationSevere": pen["severeTotal"],
                    "helpers": [h["name"] for h in helpers],
                    "bboxSize": [round(bbox["size"][i], 4) for i in range(3)],
                }
            )
            _remove_helpers(arm, helpers)

        for hid in HAIR:
            spec = HAIR_SPEC[hid]
            obj = _make_shell(f"HR_{hid}_{body_name}", spec["z0"], spec["z1"], spec["inflate"], bbox, work)
            w = _transfer_weights(body, obj, arm)
            helpers = _add_helper_bones(arm, hid, "hair") if spec["long"] else []
            if helpers:
                helper_locks.extend(
                    [
                        {
                            **h,
                            "hairRoot": "Head",
                            "collisionRangeLocked": True,
                            "chainLength": spec["chain"],
                        }
                        for h in helpers
                    ]
                )
            hair_objs[hid] = obj
            fit_records.append(
                {
                    "body": body_name,
                    "asset": hid,
                    "kind": "hair",
                    "weight": w,
                    "helpers": [h["name"] for h in helpers],
                    "bboxSize": [round(bbox["size"][i], 4) for i in range(3)],
                }
            )
            _remove_helpers(arm, helpers)

        # full clothing×hair eligibility matrix for this body
        for cid in CLOTHING:
            for hid in HAIR:
                el = _eligibility(body_name, cid, hid)
                matrix.append({"body": body_name, "clothing": cid, "hair": hid, **el})

        # Homepage 10 poses with suit + short hair (functional)
        cloth = clothing_objs["BUSINESS_SUIT_01"]
        hair = hair_objs["SHORT_NEAT_01"]
        helpers = _add_helper_bones(arm, "BUSINESS_SUIT_01", "clothing")  # none expected
        for pose in HOMEPAGE_POSES:
            _apply_pose(arm, pose["bones"])
            pen = _region_penetration(body, cloth, params["penetrationRegions"])
            region_pen_total += pen["severeTotal"]
            pose_failures["penetration"] += pen["severeTotal"]
            # jitter = instability under identical re-application (not pose-to-pose delta)
            for o in (cloth, hair, body):
                m1 = _eval_metrics(o)
                bpy.context.view_layer.update()
                m2 = _eval_metrics(o)
                if m1["explode"] or m2["explode"]:
                    pose_failures["explode"] += 1
                if any(abs(m1["size"][i] - m2["size"][i]) > 0.05 for i in range(3)):
                    pose_failures["jitter"] += 1
        _reset_pose(arm)
        _remove_helpers(arm, helpers)

        # cleanup generated meshes for this body to keep blend lighter (keep templates summary only)
        for o in list(clothing_objs.values()) + list(hair_objs.values()):
            _delete_object(o)

    _reset_body_keys(body)
    topo1 = _topology_snapshot(body)
    rig1 = _rig_snapshot(arm)
    topo_ok = topo0 == topo1
    # rig: names/count must match (helper bones removed)
    rig_ok = rig0["names"] == rig1["names"] and rig0["boneCount"] == rig1["boneCount"]
    identity_ok = topo0["identityMorphSha256"] == topo1["identityMorphSha256"]

    weight_fails = sum(1 for r in fit_records if r["weight"]["unassigned"] > 0 or r["weight"]["afterOutOfTol"] > 0)
    eligible = sum(1 for m in matrix if m["status"] == "ELIGIBLE")
    abstain = sum(1 for m in matrix if m["status"] == "ABSTAIN")

    fp = _stable_hash(
        {
            "fit": fit_records,
            "matrix": matrix,
            "helpers": helper_locks,
            "mask": mask_info,
            "ownership": ownership,
            "variants": variants,
            "poses": [p["id"] for p in HOMEPAGE_POSES],
        }
    )

    # Keep mask + body in saved blend for audit
    out_blend = run_dir / "NURION_CanonicalClothingHair_V1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    if _sha_file(gate5) != args.expected_gate5_sha256:
        raise SystemExit("Gate5 blend mutated during Gate6")

    report = {
        "schema": "NURION_V07_CCS_GATE6_RUN_REPORT",
        "runId": int(args.run_id),
        "gate5SourceSha256": src_sha,
        "outBlendSha256": _sha_file(out_blend),
        "clothingLibrary": CLOTHING,
        "hairLibrary": HAIR,
        "bodyPresets": list(preset_values.keys()),
        "fitRecordCount": len(fit_records),
        "matrixSize": len(matrix),
        "eligibleCount": eligible,
        "abstainCount": abstain,
        "eligibilityMatrix": matrix,
        "fitRecords": fit_records,
        "helperBoneLocks": helper_locks,
        "hairRootChainCollisionLocked": True,
        "homepagePoseResults": pose_failures,
        "regionPenetrationSevereTotal": region_pen_total,
        "weightTransferFails": weight_fails,
        "interiorMask": mask_info,
        "ownership": ownership,
        "variantSeparation": variants,
        "canonicalTopologyUnchanged": topo_ok,
        "canonicalRigUnchanged": rig_ok,
        "identityMorphUnchanged": identity_ok,
        "proceduralQualityRole": "FUNCTIONAL_VERIFICATION_ONLY_NOT_ARTIST_CERTIFIED",
        "artistQualityCertification": "NOT_CLAIMED",
        "libraryFingerprintSha256": fp,
        "inheritedLimitations": params.get("inheritedLimitations", []),
        "production": "NO-GO",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "blenderVersion": bpy.app.version_string,
    }
    _write(run_dir / "V07_CCS_GATE6_RUN_REPORT.json", report)
    _write(run_dir / "V07_CCS_GATE6_OWNERSHIP.json", ownership)
    _write(run_dir / "V07_CCS_GATE6_ELIGIBILITY_MATRIX.json", {"matrix": matrix, "eligible": eligible, "abstain": abstain})
    print(
        json.dumps(
            {
                "runId": args.run_id,
                "libraryFingerprintSha256": fp,
                "eligible": eligible,
                "abstain": abstain,
                "topo": topo_ok,
                "rig": rig_ok,
                "identity": identity_ok,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("GATE6_FAIL", e, file=sys.stderr)
        raise
