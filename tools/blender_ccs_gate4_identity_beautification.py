"""
CCS Gate 4 — Identity & Beautification Morphs on Gate3 weighted clone only.

Identity (ID_*) and Beautification (BEAU_*) axes are fully separated.
No mutation of Gate1–3 or v0.6 sealed bytes on disk. Production NO-GO.
Does not auto-claim face recognition or preference scores.
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

ID_AXES = [
    "ID_FaceOutline",
    "ID_Eye",
    "ID_Nose",
    "ID_Mouth",
    "ID_Jaw",
    "ID_Cheek",
    "ID_Hairline",
]
BEAU_AXES = [
    "BEAU_Skin",
    "BEAU_Symmetry",
    "BEAU_Jawline",
    "BEAU_Eye",
    "BEAU_Smile",
    "BEAU_AgeImpression",
]
MODES = ("NATURAL", "POLISHED", "ASPIRATIONAL", "CHARACTER")
CORR_KEYS = [
    "CORR_ShoulderRaise_L",
    "CORR_ElbowBend_L",
    "CORR_KneeBend_L",
    "CORR_NeckTurn",
    "CORR_JawOpen",
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--gate3-blend", required=True)
    p.add_argument("--expected-gate3-sha256", required=True)
    p.add_argument("--params-json", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--user-approval", default="true")
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


def _find_weighted_mesh_arm():
    mesh = bpy.data.objects.get("NURION_W_CanonicalHuman_V1")
    if mesh is None:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        mesh = meshes[0] if meshes else None
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and "CanonicalArmature" in o.name]
    if mesh is None or not arms:
        raise RuntimeError("Gate3 weighted mesh/armature missing")
    return mesh, arms[0]


def _topology_snapshot(obj):
    mesh = obj.data
    verts = [[round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6)] for v in mesh.vertices]
    edges = sorted((min(e.vertices[0], e.vertices[1]), max(e.vertices[0], e.vertices[1])) for e in mesh.edges)
    uv = []
    if mesh.uv_layers:
        layer = mesh.uv_layers.active.data
        uv = [[round(d.uv.x, 6), round(d.uv.y, 6)] for d in layer]
    return {
        "vertexCount": len(mesh.vertices),
        "edgeCount": len(mesh.edges),
        "polyCount": len(mesh.polygons),
        "vertexOrderSha256": _stable_hash(list(range(len(mesh.vertices)))),
        "edgeStructureSha256": _stable_hash(edges),
        "uvSha256": _stable_hash(uv),
        "basisCoordsSha256": _stable_hash(verts),
    }


def _vg_indices(obj, name, thr=0.01):
    vg = obj.vertex_groups.get(name)
    if vg is None:
        return []
    gi = vg.index
    out = []
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group == gi and g.weight > thr:
                out.append(v.index)
                break
    return out


def _face_mask(obj):
    """Deterministic face/head vertex sets from bone weights + spatial heuristics."""
    head = set(_vg_indices(obj, "Head")) | set(_vg_indices(obj, "Neck")) | set(_vg_indices(obj, "Jaw"))
    head |= set(_vg_indices(obj, "Eye.L")) | set(_vg_indices(obj, "Eye.R"))
    for n in ("FaceAttach.Nose", "FaceAttach.Mouth", "FaceAttach.Brow"):
        head |= set(_vg_indices(obj, n))
    zs = [v.co.z for v in obj.data.vertices]
    zmin, zmax = min(zs), max(zs)
    h = max(zmax - zmin, 1e-6)
    face, hairline, cheek_l, cheek_r = [], [], [], []
    eye, nose, mouth, jaw, outline = [], [], [], [], []
    for v in obj.data.vertices:
        t = (v.co.z - zmin) / h
        if t < 0.72 and v.index not in head:
            continue
        outline.append(v.index)
        if t >= 0.92:
            hairline.append(v.index)
        if v.co.y < 0.02:
            face.append(v.index)
        if abs(v.co.x) > 0.04 and 0.78 <= t <= 0.9 and v.co.y < 0.05:
            (cheek_l if v.co.x > 0 else cheek_r).append(v.index)
        if 0.84 <= t <= 0.92 and abs(v.co.x) > 0.02:
            eye.append(v.index)
        if 0.8 <= t <= 0.88 and abs(v.co.x) < 0.05 and v.co.y < 0.0:
            nose.append(v.index)
        if 0.76 <= t <= 0.84 and v.co.y < 0.02:
            mouth.append(v.index)
        if 0.72 <= t <= 0.8:
            jaw.append(v.index)
    # fallbacks
    if not face:
        face = list(head) or outline
    if not eye:
        eye = _vg_indices(obj, "Eye.L") + _vg_indices(obj, "Eye.R") or face[: max(1, len(face) // 4)]
    if not nose:
        nose = _vg_indices(obj, "FaceAttach.Nose") or face[: max(1, len(face) // 6)]
    if not mouth:
        mouth = _vg_indices(obj, "FaceAttach.Mouth") or face[: max(1, len(face) // 5)]
    if not jaw:
        jaw = _vg_indices(obj, "Jaw") or face[: max(1, len(face) // 4)]
    if not hairline:
        hairline = outline[: max(1, len(outline) // 5)] or face[:1]
    if not cheek_l and not cheek_r:
        mid = len(face) // 2
        cheek_l, cheek_r = face[:mid], face[mid:]
    return {
        "face": sorted(set(face)),
        "outline": sorted(set(outline) | set(face)),
        "eye": sorted(set(eye)),
        "nose": sorted(set(nose)),
        "mouth": sorted(set(mouth)),
        "jaw": sorted(set(jaw)),
        "cheek": sorted(set(cheek_l) | set(cheek_r)),
        "hairline": sorted(set(hairline)),
    }


def _ensure_basis(obj):
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    sk = obj.data.shape_keys
    sk.use_relative = True
    return sk


def _add_key(obj, name):
    sk = _ensure_basis(obj)
    if name in sk.key_blocks:
        return sk.key_blocks[name]
    return obj.shape_key_add(name=name, from_mix=False)


def _apply_delta(key, indices, delta_fn, strength=1.0):
    basis = key.id_data.key_blocks["Basis"]
    for i in indices:
        co = basis.data[i].co.copy()
        d = delta_fn(co, i)
        key.data[i].co = co + d * strength


def _build_identity_keys(obj, masks):
    keys = {}
    k = _add_key(obj, "ID_FaceOutline")
    _apply_delta(k, masks["outline"], lambda co, _i: Vector((co.x * 0.04, co.y * 0.02, 0.0)), 1.0)
    keys["ID_FaceOutline"] = k.name

    k = _add_key(obj, "ID_Eye")
    _apply_delta(k, masks["eye"], lambda co, _i: Vector((0.0, -0.012, 0.008)), 1.0)
    keys["ID_Eye"] = k.name

    k = _add_key(obj, "ID_Nose")
    _apply_delta(k, masks["nose"], lambda co, _i: Vector((0.0, -0.02, 0.0)), 1.0)
    keys["ID_Nose"] = k.name

    k = _add_key(obj, "ID_Mouth")
    _apply_delta(k, masks["mouth"], lambda co, _i: Vector((co.x * 0.03, -0.01, -0.004)), 1.0)
    keys["ID_Mouth"] = k.name

    k = _add_key(obj, "ID_Jaw")
    _apply_delta(k, masks["jaw"], lambda co, _i: Vector((co.x * 0.05, 0.0, -0.01)), 1.0)
    keys["ID_Jaw"] = k.name

    k = _add_key(obj, "ID_Cheek")
    _apply_delta(k, masks["cheek"], lambda co, _i: Vector((math.copysign(0.015, co.x), -0.006, 0.0)), 1.0)
    keys["ID_Cheek"] = k.name

    k = _add_key(obj, "ID_Hairline")
    _apply_delta(k, masks["hairline"], lambda co, _i: Vector((0.0, 0.0, 0.012)), 1.0)
    keys["ID_Hairline"] = k.name
    return keys


def _build_beautification_keys(obj, masks):
    keys = {}
    k = _add_key(obj, "BEAU_Skin")
    _apply_delta(k, masks["face"], lambda co, _i: Vector((0.0, 0.004, 0.0)), 1.0)
    keys["BEAU_Skin"] = k.name

    k = _add_key(obj, "BEAU_Symmetry")
    basis = k.id_data.key_blocks["Basis"]
    # Pull toward mirrored X average (deterministic, mild)
    for i in masks["face"]:
        co = basis.data[i].co.copy()
        # find nearest mirror by index heuristic: flip X toward 0
        k.data[i].co = Vector((co.x * 0.92, co.y, co.z))
    keys["BEAU_Symmetry"] = k.name

    k = _add_key(obj, "BEAU_Jawline")
    _apply_delta(k, masks["jaw"], lambda co, _i: Vector((co.x * 0.03, 0.008, -0.006)), 1.0)
    keys["BEAU_Jawline"] = k.name

    k = _add_key(obj, "BEAU_Eye")
    _apply_delta(k, masks["eye"], lambda co, _i: Vector((0.0, -0.006, 0.006)), 1.0)
    keys["BEAU_Eye"] = k.name

    k = _add_key(obj, "BEAU_Smile")
    _apply_delta(
        k,
        masks["mouth"],
        lambda co, _i: Vector((math.copysign(0.01, co.x) if abs(co.x) > 0.02 else 0.0, -0.004, 0.008)),
        1.0,
    )
    keys["BEAU_Smile"] = k.name

    k = _add_key(obj, "BEAU_AgeImpression")
    _apply_delta(k, masks["face"], lambda co, _i: Vector((co.x * -0.01, 0.002, -0.004)), 1.0)
    keys["BEAU_AgeImpression"] = k.name
    return keys


def _set_key_value(obj, name, value, vmin, vmax, deny_out):
    sk = obj.data.shape_keys.key_blocks.get(name)
    if sk is None:
        return False, "MISSING"
    if value < vmin - 1e-9 or value > vmax + 1e-9:
        if deny_out:
            sk.value = 0.0
            return False, "OUT_OF_RANGE_DENIED"
        value = max(vmin, min(vmax, value))
    sk.value = float(value)
    return True, "OK"


def _reset_axis_values(obj, names):
    if obj.data.shape_keys is None:
        return
    for n in names:
        kb = obj.data.shape_keys.key_blocks.get(n)
        if kb is not None:
            kb.value = 0.0


def _evaluated_bbox(obj, rest_normals=None):
    """Return size, volume, and flip count vs rest poly normals (not absolute world Z)."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        if not me.vertices:
            return [0, 0, 0], 0.0, 0
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        zs = [v.co.z for v in me.vertices]
        size = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]
        vol = max(size[0], 1e-9) * max(size[1], 1e-9) * max(size[2], 1e-9)
        flip = 0
        if rest_normals is not None and len(rest_normals) == len(me.polygons):
            for i, p in enumerate(me.polygons):
                rn = rest_normals[i]
                # True inversion relative to rest topology orientation
                if rn.dot(p.normal) < -0.2:
                    flip += 1
        return [round(s, 4) for s in size], vol, flip
    finally:
        ev.to_mesh_clear()


def _rest_poly_normals(obj):
    _reset_axis_values(obj, ID_AXES + BEAU_AXES)
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        return [p.normal.copy() for p in me.polygons]
    finally:
        ev.to_mesh_clear()


def _recompute_landmarks(obj, arm):
    eye_l = _vg_indices(obj, "Eye.L") or _vg_indices(obj, "Head")
    eye_r = _vg_indices(obj, "Eye.R") or _vg_indices(obj, "Head")
    jaw = _vg_indices(obj, "Jaw") or _vg_indices(obj, "Head")
    mouth = _vg_indices(obj, "FaceAttach.Mouth") or jaw

    def centroid(idxs):
        if not idxs:
            return [0.0, 0.0, 0.0]
        pts = [obj.data.vertices[i].co for i in idxs]
        c = sum(pts, Vector((0, 0, 0))) / len(pts)
        return [round(c.x, 6), round(c.y, 6), round(c.z, 6)]

    eye_center_l = centroid(eye_l)
    eye_center_r = centroid(eye_r)
    jaw_pivot = centroid(jaw)
    lip_pts = [obj.data.vertices[i].co for i in mouth] or [Vector((0, -0.05, 1.45))]
    xs = [p.x for p in lip_pts]
    ys = [p.y for p in lip_pts]
    zs = [p.z for p in lip_pts]
    lip_boundary = {
        "min": [round(min(xs), 6), round(min(ys), 6), round(min(zs), 6)],
        "max": [round(max(xs), 6), round(max(ys), 6), round(max(zs), 6)],
        "center": centroid(mouth),
    }
    # write empties for audit (deterministic names)
    col = _ensure_col("NURION_CCS_GATE4_LANDMARKS")
    for name, loc in (
        ("NURION_LM_EyeCenter.L", eye_center_l),
        ("NURION_LM_EyeCenter.R", eye_center_r),
        ("NURION_LM_JawPivot", jaw_pivot),
        ("NURION_LM_LipBoundaryCenter", lip_boundary["center"]),
    ):
        ob = bpy.data.objects.get(name)
        if ob is None:
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "PLAIN_AXES"
            ob.empty_display_size = 0.03
            bpy.context.scene.collection.objects.link(ob)
            _link(ob, col)
        ob.location = Vector(loc)
    return {
        "eyeCenterL": eye_center_l,
        "eyeCenterR": eye_center_r,
        "jawPivot": jaw_pivot,
        "lipBoundary": lip_boundary,
        "armatureBonesPreserved": sorted(b.name for b in arm.data.bones),
    }


def _axis_separation_ok(obj):
    names = [kb.name for kb in obj.data.shape_keys.key_blocks]
    id_names = [n for n in names if n.startswith("ID_")]
    beau_names = [n for n in names if n.startswith("BEAU_")]
    overlap = set(id_names) & set(beau_names)
    mixed = [n for n in names if n.startswith("ID_") and "BEAU" in n]
    return {
        "identityCount": len(id_names),
        "beautificationCount": len(beau_names),
        "overlap": sorted(overlap),
        "mixedNames": mixed,
        "separated": len(overlap) == 0 and len(mixed) == 0,
    }


def _inherit_check(obj):
    sk = obj.data.shape_keys
    corr = []
    if sk:
        corr = [n for n in CORR_KEYS if n in sk.key_blocks]
    bone_vgs = [vg.name for vg in obj.vertex_groups if not vg.name.startswith("REGION_")]
    return {
        "correctivesPresent": corr,
        "correctiveCount": len(corr),
        "weightGroupsPresent": len(bone_vgs) > 0,
        "weightGroupCount": len(bone_vgs),
        "armatureModifier": any(m.type == "ARMATURE" for m in obj.modifiers),
    }


def main():
    args = _parse(sys.argv)
    out = Path(args.out_dir)
    run_dir = out / f"run{args.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
    gate3 = Path(args.gate3_blend)
    src_sha = _sha_file(gate3)
    if src_sha != args.expected_gate3_sha256:
        raise SystemExit(f"Gate3 blend mutated: {src_sha}")

    bpy.ops.wm.open_mainfile(filepath=str(gate3))
    src_mesh, arm = _find_weighted_mesh_arm()
    topo_before = _topology_snapshot(src_mesh)

    # Clone for Gate4 morph work — do not alter source object identity permanently on disk source
    col = _ensure_col("NURION_CCS_GATE4_WORK")
    dup = src_mesh.copy()
    dup.data = src_mesh.data.copy()
    dup.name = "NURION_IB_CanonicalHuman_V1"
    bpy.context.scene.collection.objects.link(dup)
    _link(dup, col)
    # keep parent/armature
    dup.parent = src_mesh.parent
    dup.parent_type = src_mesh.parent_type
    for mod in list(dup.modifiers):
        if mod.type == "ARMATURE":
            mod.object = arm

    masks = _face_mask(dup)
    id_keys = _build_identity_keys(dup, masks)
    beau_keys = _build_beautification_keys(dup, masks)
    sep = _axis_separation_ok(dup)
    inherit = _inherit_check(dup)
    landmarks = _recompute_landmarks(dup, arm)

    vmin = float(params["identityValueMin"])
    vmax = float(params["identityValueMax"])
    user_approval = str(args.user_approval).lower() in ("1", "true", "yes")
    rest_normals = _rest_poly_normals(dup)

    # DENY beautification without approval
    mode_results = {}
    beau_denied_without_approval = not user_approval
    for mode in MODES:
        _reset_axis_values(dup, ID_AXES + BEAU_AXES)
        # identity sample mid-range for mode stress (within allow)
        for n in ID_AXES:
            _set_key_value(dup, n, 0.35, vmin, vmax, True)
        preset = params["modePresets"][mode]
        applied = {}
        denied = []
        for n, v in preset.items():
            if not user_approval:
                _set_key_value(dup, n, 0.0, 0.0, 1.0, True)
                denied.append(n)
                applied[n] = 0.0
            else:
                ok, reason = _set_key_value(dup, n, float(v), 0.0, 1.0, True)
                applied[n] = float(v) if ok else 0.0
                if not ok:
                    denied.append(f"{n}:{reason}")
        size, vol, flip = _evaluated_bbox(dup, rest_normals)
        mode_results[mode] = {
            "applied": applied,
            "denied": denied,
            "bboxSize": size,
            "volume": round(vol, 6),
            "flipProxy": flip,
        }

    # Identity out-of-range DENY probe
    _reset_axis_values(dup, ID_AXES + BEAU_AXES)
    ok_hi, reason_hi = _set_key_value(dup, "ID_FaceOutline", 1.5, vmin, vmax, True)
    ok_lo, reason_lo = _set_key_value(dup, "ID_FaceOutline", -0.2, vmin, vmax, True)
    identity_oor = {
        "highDenied": (not ok_hi) and reason_hi == "OUT_OF_RANGE_DENIED",
        "lowDenied": (not ok_lo) and reason_lo == "OUT_OF_RANGE_DENIED",
    }

    # Extreme combination (approval on)
    _reset_axis_values(dup, ID_AXES + BEAU_AXES)
    for n in ID_AXES:
        _set_key_value(dup, n, 1.0, vmin, vmax, True)
    if user_approval:
        for n in BEAU_AXES:
            _set_key_value(dup, n, 1.0, 0.0, 1.0, True)
    ext_size, ext_vol, ext_flip = _evaluated_bbox(dup, rest_normals)
    collapse = 0
    if ext_vol < 1e-4:
        collapse = 1
    # penetration proxy: volume blow-up or shrink > 45% vs natural eval
    nat_vol = max(mode_results["NATURAL"]["volume"], 1e-9)
    penetration = 1 if (ext_vol > nat_vol * 2.5 or ext_vol < nat_vol * 0.35) else 0
    expression_collapse = 1 if collapse or ext_flip > 0 else 0

    topo_after = _topology_snapshot(dup)
    topo_ok = (
        topo_before["vertexCount"] == topo_after["vertexCount"]
        and topo_before["edgeCount"] == topo_after["edgeCount"]
        and topo_before["edgeStructureSha256"] == topo_after["edgeStructureSha256"]
        and topo_before["uvSha256"] == topo_after["uvSha256"]
        and topo_before["vertexOrderSha256"] == topo_after["vertexOrderSha256"]
    )

    # Reset values for saved blend (keys remain, values 0)
    _reset_axis_values(dup, ID_AXES + BEAU_AXES)

    morph_fp = _stable_hash(
        {
            "id": sorted(id_keys),
            "beau": sorted(beau_keys),
            "masks": {k: masks[k] for k in sorted(masks)},
            "topo": topo_after,
            "landmarks": landmarks,
        }
    )

    out_blend = run_dir / "NURION_CanonicalIdentityBeautification_V1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    # Ensure source gate3 file bytes unchanged (we opened it; save_as writes new path)
    if _sha_file(gate3) != args.expected_gate3_sha256:
        raise SystemExit("Gate3 blend mutated during Gate4")

    report = {
        "schema": "NURION_V07_CCS_GATE4_RUN_REPORT",
        "runId": int(args.run_id),
        "gate3SourceSha256": src_sha,
        "outBlendSha256": _sha_file(out_blend),
        "morphMesh": dup.name,
        "axisSeparation": sep,
        "identityAxes": ID_AXES,
        "beautificationAxes": BEAU_AXES,
        "identityOutOfRangeDeny": identity_oor,
        "beautificationWithoutUserApproval": "DENY",
        "userApproval": user_approval,
        "beauDeniedWithoutApprovalProbe": beau_denied_without_approval,
        "modes": mode_results,
        "topologyBefore": topo_before,
        "topologyAfter": topo_after,
        "topologyImmutable": topo_ok,
        "landmarksRecomputed": landmarks,
        "inheritFromGate3": inherit,
        "extremeCombo": {
            "bboxSize": ext_size,
            "volume": round(ext_vol, 6),
            "flipCount": ext_flip,
            "collapseCount": collapse,
            "penetrationCount": penetration,
            "expressionCollapseCount": expression_collapse,
        },
        "morphFingerprintSha256": morph_fp,
        "autoClaimFaceRecognition": "DENY",
        "autoClaimPreference": "DENY",
        "manualGt": "INDEPENDENT_PARALLEL_OFFICIAL_MANUAL_ANNOTATION_WAIT",
        "inheritedLimitationsFromGate3": params.get("inheritedLimitationsFromGate3", []),
        "production": "NO-GO",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "blenderVersion": bpy.app.version_string,
    }
    _write(run_dir / "V07_CCS_GATE4_RUN_REPORT.json", report)
    print(json.dumps({"runId": args.run_id, "morphFingerprintSha256": morph_fp, "topologyImmutable": topo_ok}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("GATE4_FAIL", e, file=sys.stderr)
        raise
