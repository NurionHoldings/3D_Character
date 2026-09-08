"""v1 weighted jaw/lip morph + eyelid morph QA with close-up cameras."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--skin-obj", required=True)
    ap.add_argument("--rig-obj", required=True)
    ap.add_argument("--weight-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default="V1_WEIGHTED")
    ap.add_argument("--resolution", type=int, default=1280)
    ap.add_argument("--meta-json", required=True)
    return ap.parse_args(argv)


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b)


def _gray(name):
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
    verts, groups = [], {}
    cur = "default"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            a = line.split()
            verts.append((float(a[1]), float(a[2]), float(a[3])))
        elif line.startswith("g ") or line.startswith("o "):
            cur = line[2:].strip() or "default"
            groups.setdefault(cur, [])
        elif line.startswith("f "):
            idxs = []
            for tok in line.split()[1:]:
                idxs.append(int(tok.split("/")[0]) - 1)
            groups.setdefault(cur, []).append(idxs)
    return verts, groups


def _load_mesh(path, group, gray, coll, name):
    verts, groups = _parse_obj(path)
    faces = groups.get(group, []) if group else []
    polys = [tuple(f) for f in faces if len(f) >= 3]
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


def _apply_weighted_jaw(obj, weights: dict[int, float], pivot: Vector, angle_deg: float):
    mesh = obj.data
    mw = 0
    angle_rad = math.radians(angle_deg)
    for vi, w in weights.items():
        if w < 1e-6 or vi >= len(mesh.vertices):
            continue
        v = mesh.vertices[vi]
        rel = v.co - pivot
        partial = angle_rad * w
        c, s = math.cos(partial), math.sin(partial)
        y, z = float(rel.y), float(rel.z)
        v.co = pivot + Vector((rel.x, c * y - s * z, s * y + c * z))
        mw += 1
    mesh.update()
    return mw


def _apply_eyelid_morph(obj, basis_coords, eyelid_weights, eyelid_spec, side: str, open_pct: float):
    mesh = obj.data
    side_prefix = "LEFT" if side == "L" else "RIGHT"
    for part, sign in (("UPPER", -1.0), ("LOWER", 1.0)):
        key = f"{side_prefix}_{part}"
        spec = eyelid_spec[key]
        weights = {int(k): float(v) for k, v in eyelid_weights.get(key, {}).items()}
        center = Vector(spec["center"])
        max_deg = float(spec["maxDeg"])
        t = (open_pct - 0.5) * 2.0
        angle_rad = math.radians(sign * max_deg * t)
        for vi, w in weights.items():
            if vi >= len(mesh.vertices):
                continue
            basis = basis_coords[vi]
            rel = basis - center
            c, s = math.cos(angle_rad * w), math.sin(angle_rad * w)
            y, z = float(rel.y), float(rel.z)
            mesh.vertices[vi].co = center + Vector((rel.x, c * y - s * z, s * y + c * z))
    mesh.update()


def _setup_rig(rig_path, gray, coll, head_root, jaw_empty):
    groups = {
        "upper": ["helper-upper-teeth"],
        "lower": ["helper-lower-teeth", "helper-tongue"],
        "eye_l": ["helper-l-eyelashes-1", "helper-l-eyelashes-2"],
        "eye_r": ["helper-r-eyelashes-1", "helper-r-eyelashes-2"],
        "eyeball_l": ["helper-l-eye"],
        "eyeball_r": ["helper-r-eye"],
    }
    objs = {}
    for names in groups.values():
        for g in names:
            objs[g] = _load_mesh(rig_path, g, gray, coll, g)
    for g in groups["upper"] + groups["eyeball_l"] + groups["eyeball_r"]:
        objs[g].parent = head_root
    for g in groups["lower"]:
        o = objs[g]
        o.parent = jaw_empty
        o.matrix_parent_inverse = jaw_empty.matrix_world.inverted()
    eye_pivots = {}
    for side, x_sign, keys in (("L", -1, groups["eye_l"]), ("R", 1, groups["eye_r"])):
        ep = bpy.data.objects.new(f"EyePivot_{side}", None)
        coll.objects.link(ep)
        ep.location = Vector((0.308 * x_sign, 7.284, 1.245))
        ep.parent = head_root
        eye_pivots[side] = ep
        for g in keys:
            o = objs[g]
            o.parent = ep
            o.matrix_parent_inverse = ep.matrix_world.inverted()
    return objs, eye_pivots


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


def _lights(target, span=0.5):
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)

    def add(n, loc, e):
        d = bpy.data.lights.new(n, "AREA")
        d.energy = e
        d.size = 1.2
        o = bpy.data.objects.new(n, d)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add("Key", (target.x + 0.1, target.y - 0.8, target.z + 0.15), 80)
    add("Fill", (target.x - 0.15, target.y - 0.6, target.z), 40)


def _render_cam(cam, sc, cam_loc, target, path, lens=105):
    cam.data.lens = lens
    cam.location = cam_loc
    _look_at(cam, target)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main() -> int:
    args = _parse()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    wdata = json.loads(Path(args.weight_json).read_text(encoding="utf-8"))
    pivot = Vector(wdata["jawPivot"])
    weights = {int(k): float(v) for k, v in wdata["weights"].items()}
    eyelid_weights = wdata.get("eyelidWeights", {})
    eyelid_spec = wdata.get("eyelidMorphSpec", {})

    _clear()
    coll = bpy.context.scene.collection
    gray = _gray("G")

    head_root = bpy.data.objects.new("HeadRoot", None)
    coll.objects.link(head_root)
    jaw_empty = bpy.data.objects.new("JawPivot", None)
    coll.objects.link(jaw_empty)
    jaw_empty.location = pivot
    jaw_empty.parent = head_root

    skin_basis = _load_mesh(Path(args.skin_obj), "NurionHeadSkin", gray, coll, "SkinBasis")
    skin_basis.parent = head_root
    skin_basis_coords = [v.co.copy() for v in skin_basis.data.vertices]

    rig_objs, eye_pivots = _setup_rig(Path(args.rig_obj), gray, coll, head_root, jaw_empty)

    _setup_scene(args.resolution)
    cam_d = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_d)
    coll.objects.link(cam)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene

    mouth_target = Vector((0.0, 6.68, 1.32))
    eye_l_target = Vector((-0.308, 7.284, 1.36))
    eye_r_target = Vector((0.308, 7.284, 1.36))
    _lights(mouth_target, 0.45)

    captures = []

    def set_mouth(angle, show_oral=False):
        skin_basis.hide_render = angle > 0.01
        if angle > 0.01:
            if not hasattr(set_mouth, "skin_open") or set_mouth.skin_open is None:
                set_mouth.skin_open = skin_basis.copy()
                set_mouth.skin_open.data = skin_basis.data.copy()
                set_mouth.skin_open.name = "SkinOpen"
                coll.objects.link(set_mouth.skin_open)
                set_mouth.skin_open.parent = head_root
            else:
                for i, v in enumerate(skin_basis.data.vertices):
                    set_mouth.skin_open.data.vertices[i].co = v.co.copy()
                set_mouth.skin_open.data.update()
            _apply_weighted_jaw(set_mouth.skin_open, weights, pivot, angle)
            set_mouth.skin_open.hide_render = False
        elif hasattr(set_mouth, "skin_open") and set_mouth.skin_open:
            set_mouth.skin_open.hide_render = True
        jaw_empty.rotation_euler = (math.radians(angle), 0, 0)
        rig_objs["helper-upper-teeth"].hide_render = not show_oral
        rig_objs["helper-lower-teeth"].hide_render = not show_oral
        rig_objs["helper-tongue"].hide_render = not show_oral
        for g in rig_objs:
            if "eyelash" in g:
                rig_objs[g].hide_render = True

    set_mouth.skin_open = None

    for angle, tag in ((0, "closed"), (12, "half"), (24, "open")):
        set_mouth(angle, show_oral=angle >= 12)
        for view, loc_fn in (
            ("front", lambda t: Vector((t.x, t.y - 0.55, t.z))),
            ("left", lambda t: Vector((t.x + 0.38, t.y - 0.22, t.z + 0.02))),
        ):
            p = out / f"{args.label}_mouth_{tag}_{view}"
            _render_cam(cam, sc, loc_fn(mouth_target), mouth_target, p, lens=110)
            captures.append(p.name + ".png")

    set_mouth(24, show_oral=True)
    interior_cam = Vector((0.0, 6.55, 1.18))
    p = out / f"{args.label}_mouth_interior"
    _render_cam(cam, sc, interior_cam, Vector((0.0, 6.72, 1.25)), p, lens=95)
    captures.append(p.name + ".png")

    def set_eye(side, open_pct):
        skin_basis.hide_render = True
        if hasattr(set_mouth, "skin_open") and set_mouth.skin_open:
            set_mouth.skin_open.hide_render = True
        jaw_empty.rotation_euler = (0, 0, 0)
        if not hasattr(set_eye, "skin_eye") or set_eye.skin_eye is None:
            set_eye.skin_eye = skin_basis.copy()
            set_eye.skin_eye.data = skin_basis.data.copy()
            set_eye.skin_eye.name = "SkinEye"
            coll.objects.link(set_eye.skin_eye)
            set_eye.skin_eye.parent = head_root
        for i, co in enumerate(skin_basis_coords):
            set_eye.skin_eye.data.vertices[i].co = co.copy()
        set_eye.skin_eye.data.update()
        if eyelid_weights and eyelid_spec:
            _apply_eyelid_morph(set_eye.skin_eye, skin_basis_coords, eyelid_weights, eyelid_spec, side, open_pct)
        set_eye.skin_eye.hide_render = False
        for g, o in rig_objs.items():
            if "eyelash" in g:
                show = (side == "L" and g.startswith("helper-l")) or (side == "R" and g.startswith("helper-r"))
                o.hide_render = not show
            elif "eye" in g and "eyelash" not in g:
                show = (side == "L" and g == "helper-l-eye") or (side == "R" and g == "helper-r-eye")
                o.hide_render = not show
            else:
                o.hide_render = True
        for s, ep in eye_pivots.items():
            t = (open_pct - 0.5) * 2.0
            deg = math.radians(-14.0 * t) if s == side else 0.0
            ep.rotation_euler = (deg, 0, 0)

    set_eye.skin_eye = None

    for side, tag in (("L", "left"), ("R", "right")):
        target = eye_l_target if side == "L" else eye_r_target
        for pct, state in ((0.0, "closed"), (0.5, "half"), (1.0, "open")):
            set_eye(side, pct)
            p = out / f"{args.label}_eye_{tag}_{state}"
            _render_cam(cam, sc, Vector((target.x, target.y - 0.42, target.z)), target, p, lens=115)
            captures.append(p.name + ".png")

    meta = {
        "schema": "NURION_V07_V1_WEIGHTED_MORPH_QA_META",
        "weightMap": args.weight_json,
        "jawAnglesRendered": [0, 12, 24],
        "eyeOpenStates": ["closed", "half", "open"],
        "rigidLowerLipOnly": "REJECTED",
        "captures": captures,
        "production": "NO-GO",
    }
    Path(args.meta_json).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{args.label}.blend"))
    print(json.dumps(meta, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
