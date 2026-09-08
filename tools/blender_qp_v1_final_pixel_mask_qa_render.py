"""v1 anatomical-context QA — final 1280px object-ID mask occupancy, no weight changes."""
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

VALID_PASS_INDEX = 1
OCC_MIN = 0.65
OCC_MAX = 0.85
OCC_TARGET = 0.75
FINAL_RES = 1280
MAX_FRAME_ITERS = 24


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--skin-obj", required=True)
    ap.add_argument("--rig-obj", required=True)
    ap.add_argument("--weight-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default="V1_FPIX")
    ap.add_argument("--resolution", type=int, default=FINAL_RES)
    ap.add_argument("--meta-json", required=True)
    ap.add_argument("--validation-json", required=True)
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


def _mask_mat(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    emit.inputs["Strength"].default_value = 1.0
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(emit.outputs[0], out.inputs[0])
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


def _setup_scene(res):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    vl = bpy.context.view_layer
    vl.use_pass_object_index = True
    w = bpy.data.worlds.new("QA")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
        bg.inputs[1].default_value = 1.0


def _lights(target):
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)

    def add(n, loc, e):
        d = bpy.data.lights.new(n, "AREA")
        d.energy = e
        d.size = 1.6
        o = bpy.data.objects.new(n, d)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add("Key", (target.x + 0.06, target.y - 0.45, target.z + 0.12), 90)
    add("Fill", (target.x - 0.10, target.y - 0.35, target.z), 45)


def _mouth_framing(v: Vector) -> bool:
    return 6.02 <= v.y <= 7.10 and 0.72 <= v.z <= 1.74 and -0.68 <= v.x <= 0.68


def _eye_framing(v: Vector, side: str) -> bool:
    if side == "L":
        return -0.66 <= v.x <= 0.10 and 6.78 <= v.y <= 7.72 and 0.88 <= v.z <= 1.66
    return -0.10 <= v.x <= 0.66 and 6.78 <= v.y <= 7.72 and 0.88 <= v.z <= 1.66


def _interior_framing(v: Vector) -> bool:
    return 6.35 <= v.y <= 6.98 and 1.02 <= v.z <= 1.58 and -0.42 <= v.x <= 0.42


def _framing_bounds(skin_obj, basis_coords, region_fn, extras=None, extras_only=False):
    bpy.context.view_layer.update()
    co_min = Vector((1e18, 1e18, 1e18))
    co_max = Vector((-1e18, -1e18, -1e18))
    found = False

    def absorb(wc: Vector):
        nonlocal found, co_min, co_max
        found = True
        co_min = Vector((min(co_min[i], wc[i]) for i in range(3)))
        co_max = Vector((max(co_max[i], wc[i]) for i in range(3)))

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
        return Vector((0.70, -0.72, 0.05)).normalized()
    if mode == "interior":
        return Vector((0.0, -0.92, -0.08)).normalized()
    raise ValueError(mode)


def _nudge_camera_to_mask(cam, mask: np.ndarray, center: Vector, mode: str, dist: float):
    h, w = mask.shape
    ys, xs = np.where(mask > 0.5)
    if len(xs) == 0:
        return center
    cx_px = (float(xs.min()) + float(xs.max())) / 2.0
    cy_px = (float(ys.min()) + float(ys.max())) / 2.0
    dx = (cx_px - w / 2.0) / w
    dy = (cy_px - h / 2.0) / h
    scale = float(cam.data.ortho_scale)
    if mode == "front":
        shift = Vector((dx * scale * 0.95, 0.0, -dy * scale * 0.95))
    elif mode == "left":
        shift = Vector((dx * scale * 0.65, dx * scale * 0.45, -dy * scale * 0.95))
    else:
        shift = Vector((dx * scale * 0.5, dy * scale * 0.2, -dy * scale * 0.8))
    center = center + shift
    view_dir = _view_direction(mode)
    cam.location = center - view_dir * dist
    _look_at(cam, center)
    return center


def _place_camera(cam, center: Vector, co_min: Vector, co_max: Vector, mode: str):
    extent = co_max - co_min
    span_x = max(extent.x, 0.05)
    span_y = max(extent.y, 0.05)
    span_z = max(extent.z, 0.05)
    if mode == "left":
        ortho_span = max(math.hypot(span_x, span_y), span_z) * 0.92
    else:
        ortho_span = max(span_x, span_z)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(ortho_span / OCC_TARGET, 0.12)
    dist = 2.8 if mode != "interior" else 1.4
    view_dir = _view_direction(mode)
    cam.location = center - view_dir * dist
    _look_at(cam, center)
    cam.data.clip_start = 0.001
    cam.data.clip_end = 120.0
    return dist


def _resolve_png(path: Path) -> Path:
    if path.is_file():
        return path
    png = path.with_suffix(".png")
    return png if png.is_file() else path


def _load_mask(path: Path) -> np.ndarray | None:
    path = _resolve_png(path)
    if not path.is_file():
        return None
    img = bpy.data.images.load(str(path))
    try:
        iw, ih = img.size
        if iw == 0 or ih == 0:
            return None
        px = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
        return px[:, :, 0]
    finally:
        bpy.data.images.remove(img)


def _measure_mask(mask: np.ndarray) -> dict:
    if mask is None:
        return {"pass": False, "reason": "NO_MASK"}
    h, w = mask.shape
    fg = mask > 0.5
    if not fg.any():
        return {"pass": False, "reason": "EMPTY_MASK", "widthFrac": 0.0, "heightFrac": 0.0}
    ys, xs = np.where(fg)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    wf = float(bbox[2] - bbox[0] + 1) / float(w)
    hf = float(bbox[3] - bbox[1] + 1) / float(h)
    ok = OCC_MIN <= wf <= OCC_MAX and OCC_MIN <= hf <= OCC_MAX
    return {
        "pass": ok,
        "widthFrac": wf,
        "heightFrac": hf,
        "fgPixelRatio": float(fg.mean()),
        "bbox": bbox,
        "reason": None if ok else "FINAL_MASK_OCCUPANCY",
    }


def _diff_mask_bbox(a: np.ndarray, b: np.ndarray) -> list[int] | None:
    if a is None or b is None:
        return None
    diff = np.abs(a - b) > 0.08
    if not diff.any():
        return None
    ys, xs = np.where(diff)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _tag_valid(objs):
    for o in objs:
        o.pass_index = VALID_PASS_INDEX


def _render_index_mask(sc, cam, valid_objs, mask_mat, gray_mats, path: Path, res: int) -> np.ndarray | None:
    saved = {}
    for o in valid_objs:
        saved[o.name] = [s.material for s in o.material_slots]
        while len(o.material_slots) < 1:
            o.data.materials.append(mask_mat)
        o.material_slots[0].material = mask_mat
        o.pass_index = VALID_PASS_INDEX
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    mask = _load_mask(path)
    for o, mats in saved.items():
        obj = bpy.data.objects.get(o)
        if not obj:
            continue
        for i, mat in enumerate(mats):
            if i < len(obj.material_slots):
                obj.material_slots[i].material = mat
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = False
    return mask


def _render_beauty(sc, cam, path: Path, res: int, center: Vector):
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.14, 0.14, 0.15, 1.0)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    _lights(center)
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def _objects_world_bounds(objects):
    bpy.context.view_layer.update()
    co_min = Vector((1e18, 1e18, 1e18))
    co_max = Vector((-1e18, -1e18, -1e18))
    found = False

    def absorb(wc: Vector):
        nonlocal found, co_min, co_max
        found = True
        co_min = Vector((min(co_min[i], wc[i]) for i in range(3)))
        co_max = Vector((max(co_max[i], wc[i]) for i in range(3)))

    for obj in objects:
        if obj.hide_render or obj.type != "MESH":
            continue
        mw = obj.matrix_world
        for v in obj.data.vertices:
            absorb(mw @ v.co)
    if not found:
        return None, None
    return co_min, co_max


def _frame_and_capture(
    sc,
    cam,
    mask_mat,
    valid_objs,
    skin_obj,
    basis_coords,
    region_fn,
    mode: str,
    beauty_path: Path,
    res: int,
    extras=None,
    extras_only=False,
    locked_cam=None,
    use_object_bounds=False,
):
    if use_object_bounds:
        co_min, co_max = _objects_world_bounds(valid_objs)
    else:
        co_min, co_max = _framing_bounds(skin_obj, basis_coords, region_fn, extras, extras_only)
    if co_min is None:
        return {"pass": False, "reason": "EMPTY_BOUNDS", "safeAbort": True}
    center = (co_min + co_max) / 2.0
    if locked_cam:
        cam.location = Vector(locked_cam["location"])
        cam.rotation_euler = locked_cam["rotation"]
        cam.data.ortho_scale = float(locked_cam["ortho_scale"])
        dist = float(locked_cam.get("distance", 2.8))
    else:
        dist = _place_camera(cam, center, co_min, co_max, mode)
    tmp_mask = Path(tempfile.gettempdir()) / f"nurion_fpix_{beauty_path.stem}.png"
    metrics = {"pass": False, "reason": "MASK_FAIL", "safeAbort": True}
    last_m = {"widthFrac": 0.0, "heightFrac": 0.0}
    if locked_cam:
        mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp_mask, res)
        m = _measure_mask(mask)
        if not m.get("pass"):
            out_m = {k: v for k, v in m.items()}
            out_m["pass"] = False
            out_m["safeAbort"] = True
            return out_m
        metrics = dict(m)
        metrics["orthoScale"] = float(cam.data.ortho_scale)
        metrics["cameraLocation"] = [float(x) for x in cam.location]
        metrics["cameraRotation"] = [float(x) for x in cam.rotation_euler]
        metrics["distance"] = dist
        metrics["maskPath"] = str(tmp_mask)
        metrics["maskArray"] = mask
    else:
        lo = float(cam.data.ortho_scale) * 0.35
        hi = max(float(cam.data.ortho_scale) * 5.0, 6.0)
        best = None
        best_mask = None
        for _ in range(22):
            mid = (lo + hi) / 2.0
            cam.data.ortho_scale = mid
            view_dir = _view_direction(mode)
            cam.location = center - view_dir * dist
            _look_at(cam, center)
            mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp_mask, res)
            if mask is not None:
                center = _nudge_camera_to_mask(cam, mask, center, mode, dist)
                mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp_mask, res)
            m = _measure_mask(mask)
            last_m = m
            wf = float(m.get("widthFrac", 0.0))
            hf = float(m.get("heightFrac", 0.0))
            min_f = min(wf, hf)
            max_f = max(wf, hf)
            if m.get("pass"):
                best = dict(m)
                best_mask = mask
                best["orthoScale"] = mid
                break
            if min_f < OCC_MIN:
                hi = mid
            elif max_f > OCC_MAX:
                lo = mid
            elif hf < wf:
                hi = mid
            else:
                lo = mid
        if best is None:
            out_m = {k: v for k, v in last_m.items() if k != "maskArray"}
            out_m["pass"] = False
            out_m["safeAbort"] = True
            out_m["reason"] = out_m.get("reason") or "FINAL_MASK_OCCUPANCY"
            return out_m
        metrics = best
        cam.data.ortho_scale = float(best["orthoScale"])
        metrics["cameraLocation"] = [float(x) for x in cam.location]
        metrics["cameraRotation"] = [float(x) for x in cam.rotation_euler]
        metrics["distance"] = dist
        metrics["maskPath"] = str(tmp_mask)
        metrics["maskArray"] = best_mask
    _render_beauty(sc, cam, beauty_path, res, center)
    metrics["beautyPath"] = str(_resolve_png(beauty_path))
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
    mask_mat = _mask_mat("ObjID")

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

    shots: dict[str, dict] = {}
    morph_masks: dict[str, np.ndarray] = {}
    camera_lock: dict[str, dict] = {}
    captures: list[str] = []
    safe_abort = False

    def _abort(msg, key):
        nonlocal safe_abort
        safe_abort = True
        shots[key] = {"pass": False, "reason": msg, "safeAbort": True}

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
            skin_basis.hide_render = False
        jaw_empty.rotation_euler = (math.radians(angle), 0, 0)
        rig_objs["helper-upper-teeth"].hide_render = not show_oral
        rig_objs["helper-lower-teeth"].hide_render = not show_oral
        rig_objs["helper-tongue"].hide_render = not show_oral
        for g, o in rig_objs.items():
            if "eyelash" in g or g.endswith("-eye"):
                o.hide_render = True

    set_mouth.skin_open = None

    def mouth_valid(show_oral):
        skin = set_mouth.skin_open if show_oral else skin_basis
        objs = [skin]
        if show_oral:
            objs.extend(
                [
                    rig_objs["helper-upper-teeth"],
                    rig_objs["helper-lower-teeth"],
                    rig_objs["helper-tongue"],
                ]
            )
        return objs, skin

    oral = [
        rig_objs["helper-upper-teeth"],
        rig_objs["helper-lower-teeth"],
        rig_objs["helper-tongue"],
    ]

    for angle, tag in ((0, "closed"), (12, "half"), (24, "open")):
        show_oral = angle >= 12
        set_mouth(angle, show_oral=show_oral)
        valid, skin = mouth_valid(show_oral)
        for view in ("front", "left"):
            key = f"mouth_{tag}_{view}"
            cam_key = f"mouth_{view}"
            locked = camera_lock.get(cam_key)
            if tag != "closed" and cam_key not in camera_lock:
                _abort("CAMERA_LOCK_MISSING", key)
                break
            p = out / f"{args.label}_{key}"
            m = _frame_and_capture(
                sc,
                cam,
                mask_mat,
                valid,
                skin_basis,
                skin_basis_coords,
                _mouth_framing,
                view,
                p,
                args.resolution,
                extras=oral if show_oral else None,
                locked_cam=locked,
            )
            if tag == "closed" and m.get("pass") and cam_key not in camera_lock:
                camera_lock[cam_key] = {
                    "location": [float(x) for x in cam.location],
                    "rotation": [float(x) for x in cam.rotation_euler],
                    "ortho_scale": float(m["orthoScale"]),
                    "distance": float(m.get("distance", 2.8)),
                }
            if not m.get("pass"):
                shots[key] = {k: v for k, v in m.items() if k != "maskArray"}
                safe_abort = True
                break
            shots[key] = {k: v for k, v in m.items() if k != "maskArray"}
            morph_masks[key] = m.get("maskArray")
            captures.append(_resolve_png(p).name)
        if safe_abort:
            break
    if not safe_abort:
        set_mouth(24, show_oral=True)
        valid, skin = mouth_valid(True)
        key = "mouth_interior"
        p = out / f"{args.label}_{key}"
        m = _frame_and_capture(
            sc,
            cam,
            mask_mat,
            valid,
            skin_basis,
            skin_basis_coords,
            _interior_framing,
            "interior",
            p,
            args.resolution,
            extras=oral,
        )
        if not m.get("pass"):
            shots[key] = {k: v for k, v in m.items() if k != "maskArray"}
            safe_abort = True
        else:
            shots[key] = {k: v for k, v in m.items() if k != "maskArray"}
            captures.append(_resolve_png(p).name)

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

    if not safe_abort:
        for side, tag in (("L", "left"), ("R", "right")):
            region = lambda v, s=side: _eye_framing(v, s)
            eyeball = rig_objs["helper-l-eye" if side == "L" else "helper-r-eye"]
            lashes = [
                rig_objs[f"helper-{'l' if side == 'L' else 'r'}-eyelashes-1"],
                rig_objs[f"helper-{'l' if side == 'L' else 'r'}-eyelashes-2"],
            ]
            cam_key = f"eye_{tag}"
            for pct, state in ((0.0, "closed"), (0.5, "half"), (1.0, "open")):
                set_eye(side, pct)
                valid = [set_eye.skin_eye, eyeball] + lashes
                key = f"eye_{tag}_{state}"
                locked = camera_lock.get(cam_key)
                if state != "closed" and cam_key not in camera_lock:
                    _abort("CAMERA_LOCK_MISSING", key)
                    break
                p = out / f"{args.label}_{key}"
                m = _frame_and_capture(
                    sc,
                    cam,
                    mask_mat,
                    valid,
                    skin_basis,
                    skin_basis_coords,
                    region,
                    "front",
                    p,
                    args.resolution,
                    locked_cam=locked,
                    use_object_bounds=True,
                )
                if state == "closed" and m.get("pass") and cam_key not in camera_lock:
                    camera_lock[cam_key] = {
                        "location": m["cameraLocation"],
                        "rotation": m["cameraRotation"],
                        "ortho_scale": float(m["orthoScale"]),
                        "distance": float(m.get("distance", 2.8)),
                    }
                if not m.get("pass"):
                    shots[key] = {k: v for k, v in m.items() if k != "maskArray"}
                    safe_abort = True
                    break
                shots[key] = {k: v for k, v in m.items() if k != "maskArray"}
                morph_masks[key] = m.get("maskArray")
                captures.append(_resolve_png(p).name)
            if safe_abort:
                break

    morph_diff = {
        "mouth_front": {
            "bbox": _diff_mask_bbox(
                morph_masks.get("mouth_closed_front"), morph_masks.get("mouth_open_front")
            ),
            "pass": _diff_mask_bbox(
                morph_masks.get("mouth_closed_front"), morph_masks.get("mouth_open_front")
            )
            is not None,
        },
        "mouth_left": {
            "bbox": _diff_mask_bbox(
                morph_masks.get("mouth_closed_left"), morph_masks.get("mouth_open_left")
            ),
            "pass": _diff_mask_bbox(
                morph_masks.get("mouth_closed_left"), morph_masks.get("mouth_open_left")
            )
            is not None,
        },
        "eye_left": {
            "bbox": _diff_mask_bbox(morph_masks.get("eye_left_closed"), morph_masks.get("eye_left_open")),
            "pass": _diff_mask_bbox(morph_masks.get("eye_left_closed"), morph_masks.get("eye_left_open"))
            is not None,
        },
        "eye_right": {
            "bbox": _diff_mask_bbox(morph_masks.get("eye_right_closed"), morph_masks.get("eye_right_open")),
            "pass": _diff_mask_bbox(morph_masks.get("eye_right_closed"), morph_masks.get("eye_right_open"))
            is not None,
        },
    }

    all_pass = (
        not safe_abort
        and len(shots) >= 13
        and all(s.get("pass") for s in shots.values())
        and all(v.get("pass") for v in morph_diff.values())
    )

    if safe_abort or not all_pass:
        for c in list(out.glob(f"{args.label}_*.png")):
            try:
                c.unlink(missing_ok=True)
            except OSError:
                pass
        captures = []

    report = {
        "schema": "NURION_V07_V1_FINAL_PIXEL_MASK_VALIDATION_V1",
        "pass": all_pass,
        "safeAbort": safe_abort or not all_pass,
        "thresholds": {"widthFracMin": OCC_MIN, "widthFracMax": OCC_MAX, "heightFracMin": OCC_MIN, "heightFracMax": OCC_MAX},
        "validation": "FINAL_1280_OBJECT_ID_MASK",
        "regionShells": "REJECTED",
        "anatomicalContext": True,
        "shots": shots,
        "morphDiff": morph_diff,
        "cameraLocks": list(camera_lock.keys()),
    }
    Path(args.validation_json).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    meta = {
        "schema": "NURION_V07_V1_FPIX_MORPH_QA_META",
        "weightMap": args.weight_json,
        "pass": all_pass,
        "safeAbort": safe_abort,
        "captures": captures,
        "production": "NO-GO",
    }
    Path(args.meta_json).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if all_pass:
        bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{args.label}.blend"))
    print(json.dumps({"pass": all_pass, "safeAbort": safe_abort, "captures": len(captures)}, ensure_ascii=True))
    return 0 if all_pass else 4


if __name__ == "__main__":
    raise SystemExit(main())
