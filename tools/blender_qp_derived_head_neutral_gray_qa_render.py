"""Neutral Gray QA rerender for NURION DerivedHead v1 — skin-only, quad wire, fixed cameras."""
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
    ap.add_argument("--rig-obj", default="")
    ap.add_argument("--oral-tongue", default="")
    ap.add_argument("--oral-teeth-upper", default="")
    ap.add_argument("--oral-teeth-lower", default="")
    ap.add_argument("--rig-joints", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default="DERIVED_HEAD_V1")
    ap.add_argument("--resolution", type=int, default=1280)
    ap.add_argument("--meta-json", required=True)
    return ap.parse_args(argv)


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b)


def _look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Z").to_euler()


def _gray_mat(name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.64, 0.64, 0.64, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.0
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.0
    return mat


def _wire_mat(name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.88, 0.88, 0.88, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
    return mat


def _parse_obj(path: Path):
    verts: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    group_faces: dict[str, list[list[tuple[int, int | None]]]] = {}
    current = "default"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            a = line.split()
            verts.append((float(a[1]), float(a[2]), float(a[3])))
        elif line.startswith("vt "):
            a = line.split()
            uvs.append((float(a[1]), float(a[2])))
        elif line.startswith("g ") or line.startswith("o "):
            current = line[2:].strip() or "default"
            group_faces.setdefault(current, [])
        elif line.startswith("f "):
            idxs = []
            for tok in line.split()[1:]:
                p = tok.split("/")
                vi = int(p[0]) - 1
                ti = int(p[1]) - 1 if len(p) > 1 and p[1] else None
                idxs.append((vi, ti))
            group_faces.setdefault(current, []).append(idxs)
    return verts, uvs, group_faces


def _load_group_objects(path: Path, gray_mat, coll, include_groups: set[str] | None, exclude_groups: set[str] | None):
    verts, uvs, group_faces = _parse_obj(path)
    objects = {}
    for gname, faces in group_faces.items():
        if include_groups is not None and gname not in include_groups:
            continue
        if exclude_groups and gname in exclude_groups:
            continue
        if not faces:
            continue
        polys = []
        for face in faces:
            if len(face) < 3:
                continue
            polys.append(tuple(vi for vi, _ in face))
        mesh = bpy.data.meshes.new(gname[:63])
        mesh.from_pydata(verts, [], polys)
        mesh.update()
        if uvs:
            uv_layer = mesh.uv_layers.new(name="UVMap")
            for poly, face in zip(mesh.polygons, faces):
                if len(face) < 3:
                    continue
                for li, (_vi, ti) in zip(poly.loop_indices, face):
                    if ti is not None and ti < len(uvs):
                        uv_layer.data[li].uv = uvs[ti]
        obj = bpy.data.objects.new(gname[:63], mesh)
        coll.objects.link(obj)
        mesh.materials.append(gray_mat)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
        objects[gname] = obj
    return objects


def _join_objects(objects: dict, name: str):
    if not objects:
        return None
    items = list(objects.values())
    bpy.ops.object.select_all(action="DESELECT")
    for o in items:
        o.select_set(True)
    bpy.context.view_layer.objects.active = items[0]
    if len(items) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    return joined


def _bbox_from_objects(objects: list):
    pts = []
    for o in objects:
        if o is None or o.hide_render:
            continue
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    if not pts:
        return Vector((0, 7, 0.6)), 1.0
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    center = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5))
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.35)
    return center, span


def _setup_scene(res: int):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("QAGrayWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.14, 0.14, 0.15, 1.0)
        bg.inputs[1].default_value = 0.55


def _add_lights(target: Vector, span: float):
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    def add(name, loc, energy):
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.size = 2.0
        o = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add("Key", (target.x + 0.2 * span, target.y - 1.4 * span, target.z + 0.25 * span), 90)
    add("Fill", (target.x - 0.35 * span, target.y - 1.1 * span, target.z + 0.05 * span), 45)
    add("TopFill", (target.x, target.y - 0.4 * span, target.z + 1.2 * span), 35)


CAMERA_VIEWS = {
    "front": {"offset": (0.0, -1.0, 0.02), "note": "MakeHuman front = -Y"},
    "left": {"offset": (1.0, -0.12, 0.02), "note": "Character left = +X"},
    "right": {"offset": (-1.0, -0.12, 0.02), "note": "Character right = -X"},
    "top": {"offset": (0.0, -0.38, 0.94), "note": "Top oblique toward front for craniofacial structure"},
    "bottom": {"offset": (0.0, -0.38, -0.94), "note": "Bottom oblique toward front for neck/oral underside"},
    "mouth_open_front": {"offset": (0.0, -0.96, 0.04), "note": "Front with jaw open"},
    "mouth_open_left": {"offset": (0.92, -0.28, 0.03), "note": "Left side mouth open"},
    "mouth_open_interior": {"offset": (0.0, -0.55, -0.72), "note": "Low frontal interior into oral cavity"},
}


def _render_view(target, span, cam, scene, out_path: Path, view: str):
    spec = CAMERA_VIEWS.get(view, CAMERA_VIEWS["front"])
    ox, oy, oz = spec["offset"]
    dist = span * 2.35
    cam.location = target + Vector((ox * dist, oy * dist, oz * dist))
    _look_at(cam, target)
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)


def _oral_rig_groups():
    return {
        "helper-tongue",
        "helper-upper-teeth",
        "helper-lower-teeth",
        "joint-jaw",
        "joint-tongue-1",
        "joint-tongue-2",
        "joint-tongue-3",
        "joint-tongue-4",
    }


def _apply_mouth_open_objs(objects: dict, pivot: Vector, lower_keys: set[str], angle_deg: float = 20.0) -> dict:
    rot = Matrix.Rotation(math.radians(angle_deg), 4, "X")
    moved = []
    for k in lower_keys:
        o = objects.get(k)
        if not o:
            continue
        loc = o.matrix_world.translation.copy()
        rel = loc - pivot
        o.matrix_world.translation = pivot + rot @ rel
        o.matrix_world = o.matrix_world @ rot
        moved.append(k)
    return {"pivot": [float(pivot.x), float(pivot.y), float(pivot.z)], "angleDeg": angle_deg, "movedGroups": moved}


def _load_oral_v2(args, gray, coll):
    oral = {}
    paths = {
        "oral_tongue": args.oral_tongue,
        "oral_teeth_upper": args.oral_teeth_upper,
        "oral_teeth_lower": args.oral_teeth_lower,
    }
    for _name, p in paths.items():
        if not p:
            continue
        path = Path(p)
        if not path.is_file():
            continue
        objs = _load_group_objects(path, gray, coll, None, None)
        oral.update(objs)
    if args.rig_joints:
        joints = _load_group_objects(Path(args.rig_joints), gray, coll, {"joint-jaw", "joint-mouth"}, None)
        for k, o in joints.items():
            o.hide_render = True
            oral[k] = o
    return oral


def _render_wire_quad(obj, target, span, cam, scene, out_path: Path, view: str):
    wf = obj.modifiers.new(name="QuadWire", type="WIREFRAME")
    wf.thickness = 0.0025
    wf.use_replace = True
    obj.data.materials.clear()
    obj.data.materials.append(_wire_mat("QuadWire"))
    _render_view(target, span, cam, scene, out_path, view)
    obj.modifiers.remove(wf)
    obj.data.materials.clear()
    obj.data.materials.append(bpy.data.materials.get("NeutralGray") or _gray_mat("NeutralGrayRestore"))


def _render_wire_triangulated(obj, target, span, cam, scene, out_path: Path, view: str):
    tri = obj.modifiers.new(name="TriForRender", type="TRIANGULATE")
    wf = obj.modifiers.new(name="TriWire", type="WIREFRAME")
    wf.thickness = 0.0025
    wf.use_replace = True
    obj.data.materials.clear()
    obj.data.materials.append(_wire_mat("TriWire"))
    _render_view(target, span, cam, scene, out_path, view)
    obj.modifiers.remove(wf)
    obj.modifiers.remove(tri)
    obj.data.materials.clear()
    obj.data.materials.append(bpy.data.materials.get("NeutralGray") or _gray_mat("NeutralGrayRestore"))


def main() -> int:
    args = _parse()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _clear()

    coll = bpy.context.scene.collection
    gray = _gray_mat("NeutralGray")

    skin_objs = _load_group_objects(Path(args.skin_obj), gray, coll, None, None)
    skin = _join_objects(skin_objs, "NurionHeadSkinQA")
    if skin is None:
        raise RuntimeError("NO_SKIN_MESH")

    rig_objs = {}
    oral_v2 = {}
    if args.oral_tongue or args.oral_teeth_lower:
        oral_v2 = _load_oral_v2(args, gray, coll)
    elif args.rig_obj:
        rig_objs = _load_group_objects(
            Path(args.rig_obj),
            gray,
            coll,
            _oral_rig_groups(),
            {"helper-l-eye", "helper-r-eye"},
        )
        for name in list(rig_objs.keys()):
            if name.startswith("joint-"):
                rig_objs[name].hide_render = True

    visible = [skin]
    target, span = _bbox_from_objects(visible)
    _setup_scene(args.resolution)
    _add_lights(target, span)

    cam_data = bpy.data.cameras.new("QACam")
    cam_data.lens = 85
    cam = bpy.data.objects.new("QACam", cam_data)
    coll.objects.link(cam)
    bpy.context.scene.camera = cam
    scene = bpy.context.scene

    captures = []
    for view in ("front", "left", "right", "top", "bottom"):
        path = out / f"{args.label}_gray_{view}"
        _render_view(target, span, cam, scene, path, view)
        captures.append(f"{path.name}.png")

    for view in ("front", "left", "right"):
        path = out / f"{args.label}_wire_quad_{view}"
        _render_wire_quad(skin, target, span, cam, scene, path, view)
        captures.append(f"{path.name}.png")

    path = out / f"{args.label}_wire_tri_note_front"
    _render_wire_triangulated(skin, target, span, cam, scene, path, "front")
    captures.append(f"{path.name}.png")

    pivot = target + Vector((0.0, 0.0, -0.08))
    mouth_objects = oral_v2 if oral_v2 else rig_objs
    for k in ("joint-jaw", "joint-mouth"):
        if k in mouth_objects:
            pivot = mouth_objects[k].matrix_world.translation.copy()
            break
    if not oral_v2 and not any(k in mouth_objects for k in ("joint-jaw", "joint-mouth")):
        pivot = target + Vector((0.0, -0.05, -0.12))

    lower_keys = (
        {"NurionOralTeethLower", "NurionOralTongue"}
        if oral_v2
        else {k for k in _oral_rig_groups() if "lower" in k or "tongue" in k or k == "joint-jaw"}
    )
    for o in mouth_objects.values():
        o.hide_render = False
    mouth_meta = _apply_mouth_open_objs(mouth_objects, pivot, lower_keys)
    visible_mouth = [skin] + [o for n, o in mouth_objects.items() if not n.startswith("joint-")]
    target_m, span_m = _bbox_from_objects(visible_mouth)
    for view in ("mouth_open_front", "mouth_open_left", "mouth_open_interior"):
        path = out / f"{args.label}_{view}"
        _render_view(target_m, span_m, cam, scene, path, view)
        captures.append(f"{path.name}.png")

    blend_out = out / f"{args.label}_NeutralGrayQA.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))

    meta = {
        "modelId": "NURION_DerivedHead_v1_skin",
        "material": "UNIFORM_NEUTRAL_GRAY",
        "textureProjection": "DENY",
        "hair": "DENY",
        "beautification": "DENY",
        "photoProjection": "DENY",
        "qaScope": "SKIN_ONLY_NO_JOINT_CUBES_NO_EYE_SQUARES",
        "wireQuad": "SOURCE_QUAD_CAGE",
        "wireTriNote": "RENDER_TRIANGULATION_PREVIEW_ONLY",
        "cameraAxes": CAMERA_VIEWS,
        "captures": captures,
        "mouthOpen": mouth_meta,
        "blend": str(blend_out),
        "production": "NO-GO",
    }
    Path(args.meta_json).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
