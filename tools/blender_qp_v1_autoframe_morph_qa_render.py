"""v1 morph QA rerender — world-space auto framing, visibility smoke, no weight changes."""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

BG_RGB = (0.14, 0.14, 0.15)
BG_TOL = 0.028
FILL_MIN = 0.65
FILL_MAX = 0.88
FILL_TARGET = 0.75
MAX_BG_RATIO = 0.52
SMOKE_RES = 384
FINAL_RES_DEFAULT = 1280


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--skin-obj", required=True)
    ap.add_argument("--rig-obj", required=True)
    ap.add_argument("--weight-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default="V1_AUTOFRAME")
    ap.add_argument("--resolution", type=int, default=FINAL_RES_DEFAULT)
    ap.add_argument("--meta-json", required=True)
    ap.add_argument("--visibility-json", required=True)
    return ap.parse_args(argv)


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b)


def _flat_mat(name, rgb=(0.64, 0.64, 0.64)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*rgb, 1.0)
    emit.inputs["Strength"].default_value = 1.0
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(emit.outputs[0], out.inputs[0])
    return mat


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
            idxs = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
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
    mesh.update()


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


def _setup_scene(res, smoke=False):
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
        if smoke:
            bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
            bg.inputs[1].default_value = 1.0
        else:
            bg.inputs[0].default_value = (*BG_RGB, 1.0)
            bg.inputs[1].default_value = 0.55


def _lights(target):
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)

    def add(n, loc, e):
        d = bpy.data.lights.new(n, "AREA")
        d.energy = e
        d.size = 1.4
        o = bpy.data.objects.new(n, d)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add("Key", (target.x + 0.08, target.y - 0.55, target.z + 0.18), 95)
    add("Fill", (target.x - 0.12, target.y - 0.45, target.z + 0.04), 48)
    add("Rim", (target.x * 0.4, target.y + 0.15, target.z + 0.22), 28)


def _extract_region_shell(source_obj, region_fn, coll, name, gray, parent):
    mesh = source_obj.data
    vert_map: dict[int, int] = {}
    new_verts: list[Vector] = []
    polys = []
    for poly in mesh.polygons:
        if not all(region_fn(mesh.vertices[vi].co) for vi in poly.vertices):
            continue
        face = []
        for vi in poly.vertices:
            if vi not in vert_map:
                vert_map[vi] = len(new_verts)
                new_verts.append(mesh.vertices[vi].co.copy())
            face.append(vert_map[vi])
        polys.append(tuple(face))
    new_mesh = bpy.data.meshes.new(name[:63])
    new_mesh.from_pydata(new_verts, [], polys)
    new_mesh.update()
    obj = bpy.data.objects.new(name[:63], new_mesh)
    coll.objects.link(obj)
    obj.parent = parent
    new_mesh.materials.append(gray)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)
    return obj, vert_map


def _sync_shell_from_source(shell, source_obj, vert_map):
    for src_i, dst_i in vert_map.items():
        shell.data.vertices[dst_i].co = source_obj.data.vertices[src_i].co.copy()
    shell.data.update()


def _mouth_region(v: Vector) -> bool:
    return 6.38 <= v.y <= 6.95 and 1.0 <= v.z <= 1.58 and -0.52 <= v.x <= 0.52


def _eye_region(v: Vector, side: str) -> bool:
    if side == "L":
        return -0.48 <= v.x <= -0.1 and 7.02 <= v.y <= 7.5 and 1.1 <= v.z <= 1.52
    return 0.1 <= v.x <= 0.48 and 7.02 <= v.y <= 7.5 and 1.1 <= v.z <= 1.52


def _interior_region(v: Vector) -> bool:
    return 6.42 <= v.y <= 6.92 and 1.05 <= v.z <= 1.55 and -0.38 <= v.x <= 0.38


def _framing_bounds(skin_obj, basis_coords, region_fn, extras=None, extras_only=False):
    bpy.context.view_layer.update()
    co_min = Vector((1e18, 1e18, 1e18))
    co_max = Vector((-1e18, -1e18, -1e18))
    found = False

    def absorb(world_co: Vector):
        nonlocal found, co_min, co_max
        found = True
        co_min = Vector((min(co_min[i], world_co[i]) for i in range(3)))
        co_max = Vector((max(co_max[i], world_co[i]) for i in range(3)))

    if skin_obj is not None and not extras_only:
        mw = skin_obj.matrix_world
        for co in basis_coords:
            if region_fn(co):
                absorb(mw @ Vector(co))
    if extras:
        for obj in extras:
            if obj.hide_render or obj.type != "MESH":
                continue
            mw = obj.matrix_world
            for corner in obj.bound_box:
                absorb(mw @ Vector(corner))
    if not found:
        return None, None
    return co_min, co_max


def _view_direction(mode: str) -> Vector:
    if mode == "front":
        return Vector((0.0, -1.0, 0.0))
    if mode == "left":
        return Vector((0.72, -0.68, 0.06)).normalized()
    if mode == "interior":
        return Vector((0.0, -1.0, -0.12)).normalized()
    raise ValueError(mode)


def _camera_fov(cam, sc):
    sensor = cam.data.sensor_width
    lens = cam.data.lens
    fov_h = 2.0 * math.atan(sensor / (2.0 * lens))
    aspect = sc.render.resolution_x / max(sc.render.resolution_y, 1)
    fov_v = 2.0 * math.atan(math.tan(fov_h / 2.0) / aspect)
    return fov_h, fov_v


def _distance_for_fill(cam, sc, span_x: float, span_y: float, span_z: float, mode: str, fill: float):
    _, fov_v = _camera_fov(cam, sc)
    fov_h, _ = _camera_fov(cam, sc)
    if mode == "front":
        plane_w, plane_h = span_x, span_z
    elif mode == "left":
        plane_w = math.hypot(span_x, span_y)
        plane_h = span_z
    else:
        plane_w, plane_h = span_x, span_z
    dist_v = (plane_h / (fill * 2.0 * math.tan(fov_v / 2.0))) if plane_h > 1e-6 else 0.35
    dist_h = (plane_w / (fill * 2.0 * math.tan(fov_h / 2.0))) if plane_w > 1e-6 else 0.35
    return max(dist_v, dist_h, 0.18) * 1.06


def _place_camera(cam, sc, center: Vector, co_min: Vector, co_max: Vector, mode: str):
    extent = co_max - co_min
    span_x = max(extent.x, 0.04)
    span_y = max(extent.y, 0.04)
    span_z = max(extent.z, 0.04)
    view_dir = _view_direction(mode)
    if mode == "left":
        ortho_span = max(math.hypot(span_x, span_y), span_z)
    else:
        ortho_span = max(span_x, span_z)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(ortho_span / FILL_TARGET, 0.08)
    dist = 2.5 if mode != "interior" else 1.2
    cam.location = center - view_dir * dist
    _look_at(cam, center)
    cam.data.clip_start = 0.001
    cam.data.clip_end = 100.0
    return dist


def _read_render_rgb(sc, tmp_name="nurion_autoframe_smoke.png"):
    tmp = Path(tempfile.gettempdir()) / tmp_name
    sc.render.filepath = str(tmp)
    bpy.ops.render.render(write_still=True)
    if not tmp.is_file():
        return None
    img = bpy.data.images.load(str(tmp))
    try:
        iw, ih = img.size
        if iw == 0 or ih == 0:
            return None
        px = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
        return px[:, :, :3]
    finally:
        bpy.data.images.remove(img)
        try:
            if tmp.name.startswith("nurion_smoke_") and tmp.exists():
                pass
            else:
                tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _resolve_render_path(path: Path) -> Path:
    if path.is_file():
        return path
    png = path if path.suffix.lower() == ".png" else path.with_suffix(".png")
    return png if png.is_file() else path


def _load_rgb_path(path: Path):
    path = _resolve_render_path(path)
    if not path.is_file():
        return None
    img = bpy.data.images.load(str(path))
    try:
        iw, ih = img.size
        if iw == 0 or ih == 0:
            return None
        px = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
        return px[:, :, :3]
    finally:
        bpy.data.images.remove(img)


def _render_to_buffer(sc, tmp_name="nurion_autoframe_smoke.png"):
    return _read_render_rgb(sc, tmp_name)


def _analyze_rgb(rgb: np.ndarray, smoke=False) -> dict:
    if rgb is None:
        return {"pass": False, "reason": "NO_RENDER"}
    lum = rgb.mean(axis=2)
    if smoke:
        is_bg = lum < 0.06
    else:
        bg = np.array(BG_RGB, dtype=np.float32)
        is_bg = (lum < 0.24) | np.all(np.abs(rgb - bg) < BG_TOL, axis=2)
    bg_ratio = float(is_bg.mean())
    fg = ~is_bg
    if not fg.any():
        return {
            "pass": False,
            "bgRatio": bg_ratio,
            "occupancy": 0.0,
            "fgPixelRatio": 0.0,
            "fgBbox": None,
            "depthSpread": 0.0,
            "reason": "NO_FOREGROUND",
        }
    ys, xs = np.where(fg)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    h, w = rgb.shape[:2]
    bbox_area = float((bbox[2] - bbox[0] + 1) * (bbox[3] - bbox[1] + 1))
    occupancy = bbox_area / float(w * h)
    fg_ratio = float(fg.mean())
    depth_spread = float(np.std(lum[fg]))
    ok = (
        bg_ratio <= MAX_BG_RATIO
        and FILL_MIN <= occupancy <= FILL_MAX
        and fg_ratio >= 0.08
    )
    return {
        "pass": ok,
        "bgRatio": bg_ratio,
        "occupancy": occupancy,
        "fgPixelRatio": fg_ratio,
        "fgBbox": bbox,
        "depthSpread": depth_spread,
        "reason": None if ok else "VISIBILITY_THRESH",
    }


def _diff_bbox(a: np.ndarray, b: np.ndarray) -> list[int] | None:
    if a is None or b is None:
        return None
    diff = np.linalg.norm(a - b, axis=2) > 0.012
    if not diff.any():
        return None
    ys, xs = np.where(diff)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _apply_smoke_materials(coll, flat, store: dict):
    for obj in coll.objects:
        if obj.type != "MESH" or obj.hide_render:
            continue
        store[id(obj)] = [slot.material for slot in obj.material_slots]
        if not obj.material_slots:
            obj.data.materials.append(flat)
        else:
            obj.material_slots[0].material = flat


def _restore_materials(coll, store: dict):
    for obj in coll.objects:
        if id(obj) not in store:
            continue
        mats = store[id(obj)]
        for i, mat in enumerate(mats):
            if i < len(obj.material_slots):
                obj.material_slots[i].material = mat


def _auto_frame_render(
    cam,
    sc,
    coll,
    smoke_flat,
    skin_obj,
    basis_coords,
    region_fn,
    mode: str,
    path: Path | None,
    smoke_only: bool,
    final_res: int,
    extras=None,
    extras_only=False,
    smoke_tag="smoke",
):
    co_min, co_max = _framing_bounds(skin_obj, basis_coords, region_fn, extras if extras_only else None, extras_only)
    if co_min is None:
        return {"pass": False, "reason": "EMPTY_BOUNDS"}
    center = (co_min + co_max) / 2.0
    if not smoke_only:
        _lights(center)
    saved_res = (sc.render.resolution_x, sc.render.resolution_y)
    sc.render.resolution_x = SMOKE_RES if smoke_only else final_res
    sc.render.resolution_y = SMOKE_RES if smoke_only else final_res
    dist = _place_camera(cam, sc, center, co_min, co_max, mode)
    smoke_tmp = f"nurion_smoke_{smoke_tag}.png"
    rgb = None
    metrics = {"pass": False, "reason": "SMOKE_FAIL"}
    mat_store: dict[int, list] = {}
    world_bg = sc.world.node_tree.nodes.get("Background") if sc.world else None
    saved_bg = tuple(world_bg.inputs[0].default_value) if world_bg else None
    if smoke_only and world_bg:
        world_bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
        world_bg.inputs[1].default_value = 1.0
        _apply_smoke_materials(coll, smoke_flat, mat_store)
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.hide_render = True
    for _ in range(12):
        rgb = _render_to_buffer(sc, smoke_tmp)
        metrics = _analyze_rgb(rgb, smoke=smoke_only)
        occ = metrics.get("occupancy", 0.0)
        bg = metrics.get("bgRatio", 1.0)
        if FILL_MIN <= occ <= FILL_MAX and bg <= MAX_BG_RATIO:
            break
        view_dir = _view_direction(mode)
        if occ < FILL_MIN:
            cam.data.ortho_scale *= 0.84
        elif occ > FILL_MAX:
            cam.data.ortho_scale *= 1.12
        elif bg > MAX_BG_RATIO:
            cam.data.ortho_scale *= 0.9
        else:
            cam.data.ortho_scale *= 1.03
        cam.location = center - view_dir * dist
        _look_at(cam, center)
    if smoke_only:
        _restore_materials(coll, mat_store)
        if world_bg and saved_bg:
            world_bg.inputs[0].default_value = saved_bg
            world_bg.inputs[1].default_value = 0.55
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.hide_render = False
    if not smoke_only and path is not None:
        _lights(center)
    metrics["cameraDistance"] = dist
    metrics["targetCenter"] = [float(center.x), float(center.y), float(center.z)]
    metrics["worldBoundsMin"] = [float(co_min.x), float(co_min.y), float(co_min.z)]
    metrics["worldBoundsMax"] = [float(co_max.x), float(co_max.y), float(co_max.z)]
    metrics["smokeTmp"] = smoke_tmp
    metrics["orthoScale"] = float(cam.data.ortho_scale)
    if not smoke_only and path is not None:
        sc.render.resolution_x = final_res
        sc.render.resolution_y = final_res
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        metrics["final"] = _analyze_rgb(_load_rgb_path(path))
    sc.render.resolution_x, sc.render.resolution_y = saved_res
    return metrics


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

    mouth_shell, mouth_vmap = _extract_region_shell(
        skin_basis, _mouth_region, coll, "MouthShell", gray, head_root
    )
    mouth_shell.hide_render = True
    eye_shells: dict[str, bpy.types.Object] = {}
    eye_vmaps: dict[str, dict[int, int]] = {}
    for side in ("L", "R"):
        fn = lambda v, s=side: _eye_region(v, s)
        sh, vm = _extract_region_shell(skin_basis, fn, coll, f"EyeShell_{side}", gray, head_root)
        sh.hide_render = True
        eye_shells[side] = sh
        eye_vmaps[side] = vm

    def _hide_all_shells():
        mouth_shell.hide_render = True
        for sh in eye_shells.values():
            sh.hide_render = True

    smoke_flat = _flat_mat("SmokeFlat")

    _setup_scene(args.resolution, smoke=False)
    cam_d = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_d)
    coll.objects.link(cam)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene

    captures: list[str] = []
    visibility: dict[str, dict] = {}
    morph_diff: dict[str, dict] = {}

    def visible_objects():
        return [o for o in coll.objects if o.type == "MESH" and not o.hide_render]

    def set_mouth(angle, show_oral=False):
        skin_basis.hide_render = True
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
            set_mouth.skin_open.hide_render = True
            src = set_mouth.skin_open
        else:
            if hasattr(set_mouth, "skin_open") and set_mouth.skin_open:
                set_mouth.skin_open.hide_render = True
            src = skin_basis
        jaw_empty.rotation_euler = (math.radians(angle), 0, 0)
        rig_objs["helper-upper-teeth"].hide_render = not show_oral
        rig_objs["helper-lower-teeth"].hide_render = not show_oral
        rig_objs["helper-tongue"].hide_render = not show_oral
        for g in rig_objs:
            if "eyelash" in g or g.endswith("-eye"):
                rig_objs[g].hide_render = True
        _hide_all_shells()
        _sync_shell_from_source(mouth_shell, src, mouth_vmap)
        mouth_shell.hide_render = False

    set_mouth.skin_open = None

    mouth_smoke_rgb: dict[str, np.ndarray] = {}
    oral_extras = lambda: [
        rig_objs["helper-upper-teeth"],
        rig_objs["helper-lower-teeth"],
        rig_objs["helper-tongue"],
    ]
    for angle, tag in ((0, "closed"), (12, "half"), (24, "open")):
        set_mouth(angle, show_oral=angle >= 12)
        skin = set_mouth.skin_open if angle > 0.01 else skin_basis
        extras = oral_extras() if angle >= 12 else None
        for view in ("front", "left"):
            key = f"mouth_{tag}_{view}"
            smoke = _auto_frame_render(
                cam,
                sc,
                coll,
                smoke_flat,
                skin_basis,
                skin_basis_coords,
                _mouth_region,
                view,
                None,
                True,
                args.resolution,
                extras=extras,
                smoke_tag=key,
            )
            mouth_smoke_rgb[key] = _load_rgb_path(Path(tempfile.gettempdir()) / smoke.get("smokeTmp", ""))
            if not smoke.get("pass"):
                visibility[key] = smoke
                continue
            p = out / f"{args.label}_{key}"
            final = _auto_frame_render(
                cam,
                sc,
                coll,
                smoke_flat,
                skin_basis,
                skin_basis_coords,
                _mouth_region,
                view,
                p,
                False,
                args.resolution,
                extras=extras,
                smoke_tag=f"{key}_final",
            )
            visibility[key] = {
                "pass": bool(smoke.get("pass")),
                "smoke": smoke,
                "finalPreview": final.get("final", final),
            }
            captures.append(_resolve_render_path(p).name)

    set_mouth(24, show_oral=True)
    _hide_all_shells()
    mouth_shell.hide_render = True
    interior_key = "mouth_interior"
    smoke = _auto_frame_render(
        cam,
        sc,
        coll,
        smoke_flat,
        None,
        skin_basis_coords,
        _interior_region,
        "interior",
        None,
        True,
        args.resolution,
        extras=oral_extras(),
        extras_only=True,
        smoke_tag=interior_key,
    )
    if smoke.get("pass"):
        p = out / f"{args.label}_{interior_key}"
        final = _auto_frame_render(
            cam,
            sc,
            coll,
            smoke_flat,
            None,
            skin_basis_coords,
            _interior_region,
            "interior",
            p,
            False,
            args.resolution,
            extras=oral_extras(),
            extras_only=True,
            smoke_tag=f"{interior_key}_final",
        )
        visibility[interior_key] = {
            "pass": bool(smoke.get("pass")),
            "smoke": smoke,
            "finalPreview": final.get("final", final),
        }
        captures.append(_resolve_render_path(p).name)
    else:
        visibility[interior_key] = smoke

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
        set_eye.skin_eye.hide_render = True
        _hide_all_shells()
        _sync_shell_from_source(eye_shells[side], set_eye.skin_eye, eye_vmaps[side])
        eye_shells[side].hide_render = False
        for g, o in rig_objs.items():
            if "eyelash" in g:
                show = (side == "L" and g.startswith("helper-l")) or (side == "R" and g.startswith("helper-r"))
                o.hide_render = not show
            elif g.endswith("-eye"):
                show = (side == "L" and g == "helper-l-eye") or (side == "R" and g == "helper-r-eye")
                o.hide_render = not show
            else:
                o.hide_render = True
        for s, ep in eye_pivots.items():
            t = (open_pct - 0.5) * 2.0
            deg = math.radians(-14.0 * t) if s == side else 0.0
            ep.rotation_euler = (deg, 0, 0)

    set_eye.skin_eye = None

    eye_smoke_rgb: dict[str, np.ndarray] = {}
    for side, tag in (("L", "left"), ("R", "right")):
        region = lambda v, s=side: _eye_region(v, s)
        eye_extra = [rig_objs["helper-l-eye" if side == "L" else "helper-r-eye"]]
        for pct, state in ((0.0, "closed"), (0.5, "half"), (1.0, "open")):
            set_eye(side, pct)
            key = f"eye_{tag}_{state}"
            smoke = _auto_frame_render(
                cam,
                sc,
                coll,
                smoke_flat,
                skin_basis,
                skin_basis_coords,
                region,
                "front",
                None,
                True,
                args.resolution,
                extras=eye_extra,
                smoke_tag=key,
            )
            eye_smoke_rgb[key] = _load_rgb_path(Path(tempfile.gettempdir()) / smoke.get("smokeTmp", ""))
            if not smoke.get("pass"):
                visibility[key] = smoke
                continue
            p = out / f"{args.label}_{key}"
            final = _auto_frame_render(
                cam,
                sc,
                coll,
                smoke_flat,
                skin_basis,
                skin_basis_coords,
                region,
                "front",
                p,
                False,
                args.resolution,
                extras=eye_extra,
                smoke_tag=f"{key}_final",
            )
            visibility[key] = {
                "pass": bool(smoke.get("pass")),
                "smoke": smoke,
                "finalPreview": final.get("final", final),
            }
            captures.append(_resolve_render_path(p).name)

    morph_diff["mouth_front"] = {
        "bbox": _diff_bbox(mouth_smoke_rgb.get("mouth_closed_front"), mouth_smoke_rgb.get("mouth_open_front")),
        "pass": _diff_bbox(mouth_smoke_rgb.get("mouth_closed_front"), mouth_smoke_rgb.get("mouth_open_front"))
        is not None,
    }
    morph_diff["mouth_left"] = {
        "bbox": _diff_bbox(mouth_smoke_rgb.get("mouth_closed_left"), mouth_smoke_rgb.get("mouth_open_left")),
        "pass": _diff_bbox(mouth_smoke_rgb.get("mouth_closed_left"), mouth_smoke_rgb.get("mouth_open_left"))
        is not None,
    }
    morph_diff["eye_left"] = {
        "bbox": _diff_bbox(eye_smoke_rgb.get("eye_left_closed"), eye_smoke_rgb.get("eye_left_open")),
        "pass": _diff_bbox(eye_smoke_rgb.get("eye_left_closed"), eye_smoke_rgb.get("eye_left_open")) is not None,
    }
    morph_diff["eye_right"] = {
        "bbox": _diff_bbox(eye_smoke_rgb.get("eye_right_closed"), eye_smoke_rgb.get("eye_right_open")),
        "pass": _diff_bbox(eye_smoke_rgb.get("eye_right_closed"), eye_smoke_rgb.get("eye_right_open")) is not None,
    }

    all_pass = all(v.get("pass") for v in visibility.values()) and all(v.get("pass") for v in morph_diff.values())

    vis_report = {
        "schema": "NURION_V07_V1_AUTOFRAME_VISIBILITY_V1",
        "pass": all_pass,
        "thresholds": {
            "occupancyMin": FILL_MIN,
            "occupancyMax": FILL_MAX,
            "maxBgRatio": MAX_BG_RATIO,
            "smokeResolution": SMOKE_RES,
        },
        "shots": visibility,
        "morphDiff": morph_diff,
        "hardcodedCamera": False,
        "framing": "WORLD_BOUNDS_HEADROOT",
    }
    Path(args.visibility_json).write_text(json.dumps(vis_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    meta = {
        "schema": "NURION_V07_V1_AUTOFRAME_MORPH_QA_META",
        "weightMap": args.weight_json,
        "visibilityPass": all_pass,
        "jawAnglesRendered": [0, 12, 24],
        "eyeOpenStates": ["closed", "half", "open"],
        "captures": captures,
        "production": "NO-GO",
    }
    Path(args.meta_json).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{args.label}.blend"))
    print(json.dumps({"visibilityPass": all_pass, "captures": len(captures)}, ensure_ascii=True))
    for pat in ("nurion_smoke_*.png",):
        for f in Path(tempfile.gettempdir()).glob(pat):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
    return 0 if all_pass else 3


if __name__ == "__main__":
    raise SystemExit(main())
