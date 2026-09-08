"""v1 rig-aligned morph QA — parenting jaw/oral/eye in shared head local-space."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--skin-obj", required=True)
    ap.add_argument("--rig-obj", required=True)
    ap.add_argument("--alignment-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default="V1_RIG_ALIGNED")
    ap.add_argument("--resolution", type=int, default=1280)
    ap.add_argument("--meta-json", required=True)
    ap.add_argument("--jaw-angle-deg", type=float, default=24.0)
    ap.add_argument("--eye-open-deg", type=float, default=14.0)
    return ap.parse_args(argv)


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b)


def _gray(name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.64, 0.64, 0.64, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.0
    return mat


def _look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Z").to_euler()


def _parse_obj(path: Path):
    verts, uvs, groups = [], [], {}
    cur = "default"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            a = line.split()
            verts.append((float(a[1]), float(a[2]), float(a[3])))
        elif line.startswith("vt "):
            a = line.split()
            uvs.append((float(a[1]), float(a[2])))
        elif line.startswith("g ") or line.startswith("o "):
            cur = line[2:].strip() or "default"
            groups.setdefault(cur, [])
        elif line.startswith("f "):
            idxs = []
            for tok in line.split()[1:]:
                p = tok.split("/")
                vi = int(p[0]) - 1
                ti = int(p[1]) - 1 if len(p) > 1 and p[1] else None
                idxs.append((vi, ti))
            groups.setdefault(cur, []).append(idxs)
    return verts, uvs, groups


def _load_mesh(path: Path, group: str | None, gray, coll, name: str):
    verts, uvs, groups = _parse_obj(path)
    faces = groups.get(group, []) if group else []
    if group is None:
        faces = [f for fs in groups.values() for f in fs]
    polys = [tuple(vi for vi, _ in f) for f in faces if len(f) >= 3]
    mesh = bpy.data.meshes.new(name[:63])
    mesh.from_pydata(verts, [], polys)
    mesh.update()
    obj = bpy.data.objects.new(name[:63], mesh)
    coll.objects.link(obj)
    mesh.materials.append(gray)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)
    return obj


def _bbox(objs):
    pts = []
    for o in objs:
        if o.hide_render:
            continue
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    if not pts:
        return Vector((0, 7, 0.6)), 1.0
    xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
    c = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5))
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.35)
    return c, span


def _setup_scene(res):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    w = bpy.data.worlds.new("QA")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.14, 0.14, 0.15, 1.0)
        bg.inputs[1].default_value = 0.55


def _lights(target, span):
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)

    def add(n, loc, e):
        d = bpy.data.lights.new(n, "AREA")
        d.energy = e
        d.size = 1.8
        o = bpy.data.objects.new(n, d)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add("Key", (target.x + 0.15 * span, target.y - 1.35 * span, target.z + 0.2 * span), 95)
    add("Fill", (target.x - 0.3 * span, target.y - 1.05 * span, target.z), 50)


VIEWS = {
    "front": (0.0, -1.0, 0.02),
    "left": (1.0, -0.12, 0.02),
    "right": (-1.0, -0.12, 0.02),
    "top": (0.0, -0.35, 0.94),
    "bottom": (0.0, -0.35, -0.94),
    "mouth_interior": (0.0, -0.35, 0.55),
}


def _render(cam, sc, target, span, view, path):
    ox, oy, oz = VIEWS.get(view, VIEWS["front"])
    dist = span * 2.35
    cam.location = target + Vector((ox * dist, oy * dist, oz * dist))
    _look_at(cam, target)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def _morph_lower_lip(obj, pivot: Vector, angle_deg: float):
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    rot = Matrix.Rotation(math.radians(angle_deg), 3, "X")
    moved = 0
    for v in bm.verts:
        if v.co.y < 6.74 and v.co.z > 1.02 and abs(v.co.x) < 0.34:
            rel = v.co - pivot
            v.co = pivot + rot @ rel
            moved += 1
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return moved


def _setup_rig(rig_path, gray, coll, head_root, jaw_pivot: Vector):
    groups = {
        "upper": ["helper-upper-teeth"],
        "lower": ["helper-lower-teeth", "helper-tongue"],
        "eye_l": ["helper-l-eyelashes-1", "helper-l-eyelashes-2"],
        "eye_r": ["helper-r-eyelashes-1", "helper-r-eyelashes-2"],
    }
    objs = {}
    for role, names in groups.items():
        for g in names:
            objs[g] = _load_mesh(rig_path, g, gray, coll, g)
    jaw_empty = bpy.data.objects.new("JawPivot", None)
    coll.objects.link(jaw_empty)
    jaw_empty.location = jaw_pivot
    jaw_empty.parent = head_root

    for g in groups["upper"]:
        objs[g].parent = head_root
    for g in groups["lower"]:
        o = objs[g]
        o.parent = jaw_empty
        o.matrix_parent_inverse = jaw_empty.matrix_world.inverted()

    eye_pivots = {}
    for side, x_sign, keys in (
        ("L", 1, groups["eye_l"]),
        ("R", -1, groups["eye_r"]),
    ):
        ep = bpy.data.objects.new(f"EyePivot_{side}", None)
        coll.objects.link(ep)
        ep.location = Vector((0.308 * x_sign, 7.284, 1.245))
        ep.parent = head_root
        eye_pivots[side] = ep
        for g in keys:
            o = objs[g]
            o.parent = ep
            o.matrix_parent_inverse = ep.matrix_world.inverted()

    return objs, jaw_empty, eye_pivots


def main() -> int:
    args = _parse()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    align = json.loads(Path(args.alignment_json).read_text(encoding="utf-8"))
    jaw_pivot = Vector(align["rigAlignment"]["jawPivot"])

    _clear()
    coll = bpy.context.scene.collection
    gray = _gray("NeutralGray")

    head_root = bpy.data.objects.new("HeadRoot", None)
    coll.objects.link(head_root)

    skin_closed = _load_mesh(Path(args.skin_obj), "NurionHeadSkin", gray, coll, "SkinClosed")
    skin_closed.parent = head_root

    skin_open = skin_closed.copy()
    skin_open.data = skin_closed.data.copy()
    skin_open.name = "SkinOpen"
    coll.objects.link(skin_open)
    skin_open.parent = head_root
    lip_moved = _morph_lower_lip(skin_open, jaw_pivot, args.jaw_angle_deg)

    rig_objs, jaw_empty, eye_pivots = _setup_rig(Path(args.rig_obj), gray, coll, head_root, jaw_pivot)

    _setup_scene(args.resolution)
    target, span = _bbox([skin_closed])
    _lights(target, span)
    cam_d = bpy.data.cameras.new("Cam")
    cam_d.lens = 85
    cam = bpy.data.objects.new("Cam", cam_d)
    coll.objects.link(cam)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene

    captures = []

    def vis_closed():
        skin_closed.hide_render = False
        skin_open.hide_render = True
        jaw_empty.rotation_euler = (0, 0, 0)
        for ep in eye_pivots.values():
            ep.rotation_euler = (0, 0, 0)
        for g in ("helper-upper-teeth", "helper-lower-teeth", "helper-tongue"):
            rig_objs[g].hide_render = True
        for g in rig_objs:
            if "eyelash" in g:
                rig_objs[g].hide_render = True

    def vis_open():
        skin_closed.hide_render = True
        skin_open.hide_render = False
        jaw_empty.rotation_euler = (math.radians(args.jaw_angle_deg), 0, 0)
        rig_objs["helper-upper-teeth"].hide_render = False
        rig_objs["helper-lower-teeth"].hide_render = False
        rig_objs["helper-tongue"].hide_render = False
        for g in rig_objs:
            if "eyelash" in g:
                rig_objs[g].hide_render = True

    def vis_eye(side: str, open_deg: float):
        skin_closed.hide_render = False
        skin_open.hide_render = True
        jaw_empty.rotation_euler = (0, 0, 0)
        for g, o in rig_objs.items():
            if "eyelash" in g:
                show = (side == "L" and g.startswith("helper-l")) or (side == "R" and g.startswith("helper-r"))
                o.hide_render = not show
            else:
                o.hide_render = True
        for s, ep in eye_pivots.items():
            if s == side and open_deg != 0.0:
                ep.rotation_euler = (math.radians(-open_deg if s == "L" else open_deg), 0, 0)
            else:
                ep.rotation_euler = (0, 0, 0)

    vis_closed()
    for view in ("front", "left", "right", "top", "bottom"):
        p = out / f"{args.label}_mouth_closed_{view}"
        _render(cam, sc, target, span, view, p)
        captures.append(p.name + ".png")

    vis_open()
    for view in ("front", "left"):
        p = out / f"{args.label}_mouth_open_{view}"
        _render(cam, sc, target, span, view, p)
        captures.append(p.name + ".png")
    p = out / f"{args.label}_mouth_interior"
    _render(cam, sc, target, span, "mouth_interior", p)
    captures.append(p.name + ".png")

    for side, tag in (("L", "left"), ("R", "right")):
        vis_eye(side, 0.0)
        p = out / f"{args.label}_eye_{tag}_closed"
        _render(cam, sc, target, span, "front", p)
        captures.append(p.name + ".png")
        vis_eye(side, args.eye_open_deg)
        p = out / f"{args.label}_eye_{tag}_open"
        _render(cam, sc, target, span, "front", p)
        captures.append(p.name + ".png")

    meta = {
        "schema": "NURION_V07_V1_RIG_ALIGNED_MORPH_QA_META",
        "skinBasisMutation": "DENY",
        "skinOpenDuplicate": "LOWER_LIP_MORPH_ONLY",
        "lipVerticesMoved": lip_moved,
        "jawPivot": list(jaw_pivot),
        "jawAngleDeg": args.jaw_angle_deg,
        "eyeOpenDeg": args.eye_open_deg,
        "parenting": {
            "headRoot": "HeadRoot",
            "jawPivot": "JawPivot",
            "lowerOralParent": "JawPivot",
            "upperTeethParent": "HeadRoot",
            "eyePivotParent": "HeadRoot",
        },
        "captures": captures,
        "production": "NO-GO",
    }
    Path(args.meta_json).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{args.label}.blend"))
    print(json.dumps(meta, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
