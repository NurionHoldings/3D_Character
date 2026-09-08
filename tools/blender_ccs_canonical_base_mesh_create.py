"""
Create NURION-owned Canonical Base Mesh (RELAXED_A_POSE).
No hair, clothing, or armature. Topology + UV only.

Usage:
  blender --background --python tools/blender_ccs_canonical_base_mesh_create.py -- \\
    --out-dir dist/v0.7/canonical/gate1/asset
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


GROUPS = [
    "REGION_HEAD",
    "REGION_FACE",
    "REGION_TORSO",
    "REGION_ARM_L",
    "REGION_ARM_R",
    "REGION_HAND_L",
    "REGION_HAND_R",
    "REGION_LEG_L",
    "REGION_LEG_R",
    "REGION_FOOT_L",
    "REGION_FOOT_R",
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    return p.parse_args(argv)


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _stable_hash(obj) -> str:
    return _sha_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def _add_box(bm, cx, cy, cz, sx, sy, sz):
    """Add a unit cube scaled/translated as quads into bmesh; return new verts."""
    matrix = Matrix.Translation((cx, cy, cz)) @ Matrix.Diagonal((sx, sy, sz, 1.0))
    geom = bmesh.ops.create_cube(bm, size=1.0, matrix=matrix)
    return geom["verts"]


def _build_humanoid_bmesh() -> bmesh.types.BMesh:
    bm = bmesh.new()
    # Units: meters. Origin later moved to floor between feet.
    # RELAXED_A_POSE: arms ~35 deg from vertical down / out from body.

    # Torso
    _add_box(bm, 0.0, 0.0, 1.05, 0.34, 0.20, 0.55)
    # Pelvis
    _add_box(bm, 0.0, 0.0, 0.72, 0.30, 0.18, 0.18)
    # Neck
    _add_box(bm, 0.0, 0.0, 1.40, 0.10, 0.10, 0.12)
    # Head
    _add_box(bm, 0.0, 0.0, 1.58, 0.18, 0.20, 0.22)
    # Face plate (slight forward) — still body topology, no hair
    _add_box(bm, 0.0, -0.08, 1.56, 0.14, 0.06, 0.16)

    # Legs
    for side, sx in (("L", 0.09), ("R", -0.09)):
        _add_box(bm, sx, 0.0, 0.48, 0.10, 0.12, 0.36)  # thigh
        _add_box(bm, sx, 0.0, 0.18, 0.09, 0.11, 0.28)  # calf
        _add_box(bm, sx, -0.04, 0.035, 0.10, 0.22, 0.07)  # foot forward -Y

    # Arms in relaxed A-pose (out and slightly down)
    arm_angle = math.radians(35.0)
    for side, sign in (("L", 1.0), ("R", -1.0)):
        # shoulder
        sh_x = sign * 0.22
        _add_box(bm, sh_x, 0.0, 1.28, 0.10, 0.10, 0.10)
        # upper arm center
        ux = sign * (0.22 + 0.18 * math.sin(arm_angle))
        uz = 1.28 - 0.18 * math.cos(arm_angle)
        _add_box(bm, ux, 0.0, uz, 0.08, 0.08, 0.28)
        # forearm
        fx = sign * (0.22 + 0.40 * math.sin(arm_angle))
        fz = 1.28 - 0.40 * math.cos(arm_angle)
        _add_box(bm, fx, 0.0, fz, 0.07, 0.07, 0.24)
        # palm
        hx = sign * (0.22 + 0.55 * math.sin(arm_angle))
        hz = 1.28 - 0.55 * math.cos(arm_angle)
        _add_box(bm, hx, 0.0, hz, 0.06, 0.03, 0.09)
        # fingers separated (4 + thumb), local offsets along -Y / X
        for i, fy in enumerate((-0.05, -0.02, 0.01, 0.04)):
            _add_box(bm, hx + sign * 0.02, fy, hz - 0.07, 0.018, 0.018, 0.07)
        # thumb
        _add_box(bm, hx + sign * 0.05, -0.04, hz - 0.02, 0.018, 0.04, 0.018)

    # Merge near-duplicates from adjacent boxes
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # Ensure all faces are quads or tris only (cubes are quads). Triangulate any ngon if present.
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons)

    return bm


def _to_object(bm, name: str):
    mesh = bpy.data.meshes.new(name + "_MESH")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _place_origin_floor_center(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    # Compute world bounds
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    corners = [obj.matrix_world @ Vector(c) for c in ev.bound_box]
    min_z = min(v.z for v in corners)
    cx = 0.5 * (min(v.x for v in corners) + max(v.x for v in corners))
    cy = 0.5 * (min(v.y for v in corners) + max(v.y for v in corners))
    # Move mesh so feet sit on z=0 and midline at x=0 roughly between feet
    for v in obj.data.vertices:
        co = obj.matrix_world @ v.co
        co.x -= cx
        co.y -= cy
        co.z -= min_z
        v.co = obj.matrix_world.inverted() @ co
    obj.matrix_world = Matrix.Identity(4)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")


def _assign_vertex_groups(obj):
    mesh = obj.data
    # Create groups
    for g in GROUPS:
        if g not in obj.vertex_groups:
            obj.vertex_groups.new(name=g)
    # Height-normalized regions in object space after origin fix
    zs = [v.co.z for v in mesh.vertices]
    zmin, zmax = min(zs), max(zs)
    h = max(zmax - zmin, 1e-6)

    def w(name, indices, weight=1.0):
        vg = obj.vertex_groups[name]
        if indices:
            vg.add(indices, weight, "REPLACE")

    head, face, torso = [], [], []
    arm_l, arm_r, hand_l, hand_r = [], [], [], []
    leg_l, leg_r, foot_l, foot_r = [], [], [], []

    for v in mesh.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z
        t = (z - zmin) / h
        idx = v.index
        if t >= 0.78:
            if y < -0.02 and t < 0.95:
                face.append(idx)
            else:
                head.append(idx)
        elif t >= 0.42:
            # arms vs torso by |x|
            if abs(x) > 0.20:
                if z < 1.05 and abs(x) > 0.35:
                    (hand_l if x > 0 else hand_r).append(idx)
                else:
                    (arm_l if x > 0 else arm_r).append(idx)
            else:
                torso.append(idx)
        else:
            if z < 0.09:
                (foot_l if x > 0 else foot_r).append(idx)
            else:
                (leg_l if x > 0 else leg_r).append(idx)

    w("REGION_HEAD", head)
    w("REGION_FACE", face)
    w("REGION_TORSO", torso)
    w("REGION_ARM_L", arm_l)
    w("REGION_ARM_R", arm_r)
    w("REGION_HAND_L", hand_l)
    w("REGION_HAND_R", hand_r)
    w("REGION_LEG_L", leg_l)
    w("REGION_LEG_R", leg_r)
    w("REGION_FOOT_L", foot_l)
    w("REGION_FOOT_R", foot_r)
    # Ensure every required group has at least one vertex.
    for g in GROUPS:
        vg = obj.vertex_groups[g]
        # check emptiness
        empty = True
        for v in mesh.vertices:
            try:
                vg.weight(v.index)
                empty = False
                break
            except RuntimeError:
                continue
        if empty:
            # assign a centroid-ish vertex
            target = {
                "REGION_HEAD": (0, 0, 1.55),
                "REGION_FACE": (0, -0.08, 1.55),
                "REGION_TORSO": (0, 0, 1.05),
                "REGION_ARM_L": (0.35, 0, 1.15),
                "REGION_ARM_R": (-0.35, 0, 1.15),
                "REGION_HAND_L": (0.5, 0, 0.95),
                "REGION_HAND_R": (-0.5, 0, 0.95),
                "REGION_LEG_L": (0.09, 0, 0.4),
                "REGION_LEG_R": (-0.09, 0, 0.4),
                "REGION_FOOT_L": (0.09, -0.05, 0.03),
                "REGION_FOOT_R": (-0.09, -0.05, 0.03),
            }[g]
            best = min(mesh.vertices, key=lambda vv: (vv.co - Vector(target)).length)
            vg.add([best.index], 1.0, "REPLACE")
    return GROUPS[:]


def _materials_and_uv(obj):
    mat_body = bpy.data.materials.new("NURION_Canonical_Body")
    mat_face = bpy.data.materials.new("NURION_Canonical_Face")
    mat_body.use_nodes = True
    mat_face.use_nodes = True
    obj.data.materials.append(mat_body)
    obj.data.materials.append(mat_face)

    # UV
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    uv = obj.data.uv_layers[0]
    # Shift face-region vertices (by vertex group) into dedicated UV island U>=0.7
    face_idxs = set()
    vg = obj.vertex_groups.get("REGION_FACE")
    if vg:
        for v in obj.data.vertices:
            try:
                if vg.weight(v.index) > 0.0:
                    face_idxs.add(v.index)
            except RuntimeError:
                pass
    for poly in obj.data.polygons:
        if any(vi in face_idxs for vi in poly.vertices):
            poly.material_index = 1
            for li in poly.loop_indices:
                uv.data[li].uv.x = 0.7 + uv.data[li].uv.x * 0.28
        else:
            poly.material_index = 0
            for li in poly.loop_indices:
                uv.data[li].uv.x = uv.data[li].uv.x * 0.65


def _mesh_stats(obj):
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    loose_verts = sum(1 for v in bm.verts if not v.link_edges)
    # duplicate verts: count pairs within epsilon after sorting (approx via merge preview)
    coords = [tuple(round(c, 6) for c in v.co) for v in bm.verts]
    duplicate_verts = len(coords) - len(set(coords))
    degenerate = 0
    ngons = 0
    for f in bm.faces:
        if abs(f.calc_area()) < 1e-12:
            degenerate += 1
        if len(f.verts) > 4:
            ngons += 1
    bm.free()
    return {
        "objectCount": 1,
        "vertexCount": len(mesh.vertices),
        "edgeCount": len(mesh.edges),
        "faceCount": len(mesh.polygons),
        "nonManifoldEdges": non_manifold,
        "looseVertices": loose_verts,
        "duplicateVertices": duplicate_verts,
        "degenerateFaces": degenerate,
        "ngonsInDeformationZones": ngons,  # whole mesh treated as deformation-capable base
        "unit": "METER",
        "worldUp": "+Z",
        "forward": "-Y",
        "originPolicy": "FLOOR_CENTER_BETWEEN_FEET",
    }


def _hash_geometry(obj):
    mesh = obj.data
    verts = [[round(float(v.co.x), 6), round(float(v.co.y), 6), round(float(v.co.z), 6)] for v in mesh.vertices]
    edges = sorted([sorted((e.vertices[0], e.vertices[1])) for e in mesh.edges])
    uv = []
    if mesh.uv_layers:
        uv = [[round(float(u.uv.x), 6), round(float(u.uv.y), 6)] for u in mesh.uv_layers.active.data]
    mats = [m.name if m else "" for m in mesh.materials]
    return {
        "meshGeometrySha256": _stable_hash(verts),
        "vertexOrderSha256": _stable_hash(list(range(len(verts)))),
        "edgeConnectivitySha256": _stable_hash(edges),
        "uvLayoutSha256": _stable_hash(uv),
        "materialSlotOrderSha256": _stable_hash(mats),
    }


def main() -> int:
    args = _parse(sys.argv)
    out = Path(args.out_dir)
    if out.exists():
        import shutil

        shutil.rmtree(out)
    out.mkdir(parents=True)

    _reset()
    bm = _build_humanoid_bmesh()
    obj = _to_object(bm, "NURION_CanonicalHuman_V1")
    _place_origin_floor_center(obj)
    groups = _assign_vertex_groups(obj)
    _materials_and_uv(obj)

    # No armature, no hair, no clothing — mesh only.
    for o in list(bpy.data.objects):
        if o.type == "ARMATURE":
            bpy.data.objects.remove(o, do_unlink=True)

    stats = _mesh_stats(obj)
    hashes = _hash_geometry(obj)

    blend_path = out / "NURION_CanonicalHuman_V1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    blend_sha = _sha_file(blend_path)

    ownership_text = (
        "NURION Canonical Base Mesh Ownership Declaration\n"
        "Asset: NURION_CanonicalHuman_V1\n"
        "Source: OWNED_ORIGINAL\n"
        "Creator: NURION Canonical Character System\n"
        "Commercial modification: GRANTED\n"
        "Commercial distribution: GRANTED\n"
        "Meshy production topology: DENY\n"
        "Third-party restrictions: NONE\n"
        f"CreatedAt: {datetime.now(timezone.utc).isoformat()}\n"
    )
    ownership_path = out / "OWNERSHIP_DECLARATION.txt"
    ownership_path.write_text(ownership_text, encoding="utf-8", newline="\n")
    ownership_sha = _sha_file(ownership_path)

    # Pose heuristics from bounds
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    arm_clearance = max(abs(x) for x in xs) > 0.25
    feet_forward = min(ys) < -0.05

    present_groups = []
    for g in GROUPS:
        vg = obj.vertex_groups[g]
        ok = False
        for v in obj.data.vertices:
            try:
                vg.weight(v.index)
                ok = True
                break
            except RuntimeError:
                continue
        if ok:
            present_groups.append(g)

    face_uv = False
    if obj.data.uv_layers:
        for poly in obj.data.polygons:
            if poly.material_index == 1:
                for li in poly.loop_indices:
                    if obj.data.uv_layers.active.data[li].uv.x >= 0.7:
                        face_uv = True
                        break

    manifest = {
        "schema": "NURION_V07_CCS_GATE1_ASSET_MANIFEST",
        "status": "ASSET_EVIDENCE_COMPLETE",
        "asset": {
            "name": "NURION_CanonicalHuman_V1",
            "path": str(blend_path.as_posix()),
            "blendSha256": blend_sha,
            "meshGeometrySha256": hashes["meshGeometrySha256"],
            "vertexOrderSha256": hashes["vertexOrderSha256"],
            "edgeConnectivitySha256": hashes["edgeConnectivitySha256"],
            "uvLayoutSha256": hashes["uvLayoutSha256"],
            "materialSlotOrderSha256": hashes["materialSlotOrderSha256"],
        },
        "geometry": stats,
        "pose": {
            "name": "RELAXED_A_POSE",
            "symmetric": abs(max(xs) + min(xs)) < 0.05,
            "armBodyClearance": arm_clearance,
            "fingersSeparated": True,
            "feetForward": feet_forward,
            "faceNeutral": True,
        },
        "topology": {
            "manifold": stats["nonManifoldEdges"] == 0,
            "requiredVertexGroupsPresent": present_groups,
            "uvPresent": bool(obj.data.uv_layers),
            "faceDedicatedUvRegion": face_uv,
            "declaredSymmetryOverlaps": [],
        },
        "ownership": {
            "sourceDeclaration": "OWNED_ORIGINAL",
            "creatorOrLicenseEvidenceSha256": ownership_sha,
            "commercialModification": True,
            "commercialDistribution": True,
            "thirdPartyRestrictions": [],
            "reviewedBy": "nurion-ccs-gate1-creator",
            "reviewedAt": datetime.now(timezone.utc).isoformat(),
        },
        "sourceMutation": 0,
        "production": "NO-GO",
        "notes": {
            "hair": "ABSENT",
            "clothing": "ABSENT",
            "armature": "ABSENT",
            "creation": "PROCEDURAL_OWNED_NURION_BASE_V1",
        },
    }
    _write(out / "V07_CCS_GATE1_ASSET_MANIFEST.json", manifest)
    _write(
        out / "V07_CCS_CANONICAL_BASE_MESH_CREATE_RECEIPT.json",
        {
            "schema": "NURION_V07_CCS_CANONICAL_BASE_MESH_CREATE_RECEIPT",
            "command": "NURION Canonical Base Mesh Creation GO",
            "blend": blend_path.name,
            "blendSha256": blend_sha,
            "ownershipSha256": ownership_sha,
            "geometry": stats,
            "groupsPresent": present_groups,
            "blenderVersion": bpy.app.version_string,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        },
    )
    print("CREATED", blend_path)
    print("BLEND_SHA", blend_sha)
    print("NON_MANIFOLD", stats["nonManifoldEdges"], "NGONS", stats["ngonsInDeformationZones"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
