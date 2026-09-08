"""Beta1 Parametric Head Replacement: continuous UV project + recessed eyes + face cameras."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


FACE_VIEWS = (("face_front", 0.0), ("face_left45", 45.0), ("face_right45", -45.0))


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", required=True)
    ap.add_argument("--albedo", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--corr-json", required=True)
    ap.add_argument("--resolution", type=int, default=1024)
    return ap.parse_args(argv)


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b)


def _look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Z").to_euler()


def _load_obj(path: Path):
    verts, uvs, faces = [], [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            p = line.split()
            verts.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("vt "):
            p = line.split()
            uvs.append((float(p[1]), float(p[2])))
        elif line.startswith("f "):
            idx = []
            for tok in line.split()[1:]:
                a = tok.split("/")
                vi = int(a[0]) - 1
                ti = int(a[1]) - 1 if len(a) > 1 and a[1] else vi
                idx.append((vi, ti))
            if len(idx) >= 3:
                faces.append(idx[:3])
    mesh = bpy.data.meshes.new("ParamHeadV1")
    mesh.from_pydata(verts, [], [(f[0][0], f[1][0], f[2][0]) for f in faces])
    mesh.update()
    if uvs:
        uv = mesh.uv_layers.new(name="UVMap")
        for poly, face in zip(mesh.polygons, faces):
            for li, (_vi, ti) in zip(poly.loop_indices, face):
                uv.data[li].uv = uvs[ti]
    obj = bpy.data.objects.new("ParamHeadV1", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _frontal_project_uv(mesh, target: Vector, span: float) -> None:
    """Background-safe continuous frontal UV (no VIEW_3D ops). One continuous map — not per-triangle FaceMesh."""
    coords = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    xs = [v.x for v in coords]
    zs = [v.z for v in coords]
    xmin, xmax = min(xs), max(xs)
    zmin, zmax = min(zs), max(zs)
    # Slight pad so face crop fills the albedo without edge clipping
    pad_x = max((xmax - xmin) * 0.04, 1e-4)
    pad_z = max((zmax - zmin) * 0.04, 1e-4)
    xmin -= pad_x
    xmax += pad_x
    zmin -= pad_z
    zmax += pad_z
    dx = max(xmax - xmin, 1e-6)
    dz = max(zmax - zmin, 1e-6)

    me = mesh.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv_layer = me.uv_layers.active
    # Per-loop UV from vertex world XZ → continuous atlas (same UVs share across triangles)
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            w = mesh.matrix_world @ me.vertices[vi].co
            u = (w.x - xmin) / dx
            v = (w.z - zmin) / dz
            uv_layer.data[li].uv = (u, v)


def _project_albedo(mesh, albedo: Path, target: Vector, span: float):
    """Apply continuous frontal UV + single albedo image (no MediaPipe tessellation texture)."""
    img = bpy.data.images.load(str(Path(albedo).resolve()))
    img.colorspace_settings.name = "sRGB"
    _frontal_project_uv(mesh, target, span)

    mat = bpy.data.materials.new("ParamHeadAlbedo")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "CLIP"
    uv = nodes.new("ShaderNodeUVMap")
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.52
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.08
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mesh.data.materials.clear()
    mesh.data.materials.append(mat)
    return None


def _deepen_sockets(mesh, corr: dict) -> None:
    """Push local verts into sockets (+Y). No floating white spheres on the face plane."""
    for key in ("L_EYE", "R_EYE"):
        idx = int(corr[key])
        center = mesh.data.vertices[idx].co.copy()
        for v in mesh.data.vertices:
            d = (v.co - center).length
            if d < 0.085:
                w = math.exp(-(d * d) / (2 * 0.035 * 0.035))
                v.co.y += 0.045 * w  # into head
                v.co.z += 0.004 * w
    mesh.data.update()


def _recessed_eyes(mesh, corr: dict):
    """Eyeballs fully inside sockets. No surface discs/tori that read as floating eye blobs."""
    _deepen_sockets(mesh, corr)
    created = []
    coords = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    xs = [v.x for v in coords]
    span = max(max(xs) - min(xs), 0.3)
    radius = span * 0.028
    for name, key in (("Eye_L", "L_EYE"), ("Eye_R", "R_EYE")):
        idx = int(corr[key])
        surface = mesh.matrix_world @ mesh.data.vertices[idx].co
        center = surface + Vector((0.0, radius * 1.6, 0.0))  # deep +Y into head
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=center, segments=18, ring_count=12)
        eye = bpy.context.active_object
        eye.name = name
        mat = bpy.data.materials.new(name + "Mat")
        mat.use_nodes = True
        b = mat.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Base Color"].default_value = (0.82, 0.83, 0.84, 1.0)
            b.inputs["Roughness"].default_value = 0.22
        eye.data.materials.append(mat)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=radius * 0.45,
            location=center + Vector((0.0, -radius * 0.4, 0.0)),
            segments=12,
            ring_count=8,
        )
        iris = bpy.context.active_object
        iris.name = name + "_Iris"
        im = bpy.data.materials.new(name + "Iris")
        im.use_nodes = True
        ib = im.node_tree.nodes.get("Principled BSDF")
        if ib:
            ib.inputs["Base Color"].default_value = (0.14, 0.18, 0.24, 1.0)
        iris.data.materials.append(im)
        created.extend([eye.name, iris.name])
    return created


def main() -> int:
    args = _parse()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    corr = json.loads(Path(args.corr_json).read_text(encoding="utf-8"))
    _clear()
    mesh = _load_obj(Path(args.obj))
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    bpy.ops.object.shade_smooth()

    coords = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    xs = [v.x for v in coords]
    ys = [v.y for v in coords]
    zs = [v.z for v in coords]
    target = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.55))
    span = max(max(xs) - min(xs), max(zs) - min(zs), 0.35)

    _project_albedo(mesh, Path(args.albedo), target, span)
    eyes = _recessed_eyes(mesh, corr)

    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    def add_light(name, loc, energy):
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.size = 1.5
        o = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add_light("K", (target.x + 0.45 * span, target.y - 1.3 * span, target.z + 0.35 * span), 150)
    add_light("F", (target.x - 0.55 * span, target.y - 1.0 * span, target.z + 0.1 * span), 55)
    add_light("R", (target.x, target.y + 1.2 * span, target.z + 0.25 * span), 70)

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.14, 0.15, 0.16, 1.0)
        bg.inputs[1].default_value = 0.35

    cam_data = bpy.data.cameras.new("FaceCam")
    cam_data.lens = 85
    cam = bpy.data.objects.new("FaceCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.image_settings.file_format = "PNG"

    dist = span * 2.5
    captures = []
    for view, yaw_deg in FACE_VIEWS:
        yaw = math.radians(yaw_deg)
        cam.location = target + Vector((math.sin(yaw) * dist, -math.cos(yaw) * dist, 0.04 * span))
        _look_at(cam, target)
        path = out / f"{args.label}_{view}"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        captures.append(f"{path.name}.png")

    blend_out = out / f"{args.label}_ParamHeadV1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))

    meta = {
        "modelId": "NURION_PARAMETRIC_HEAD_V1",
        "directFaceMeshRender": "DENY",
        "mediapipeZAsDepth": "DENY",
        "uvMode": "CONTINUOUS_FRONTAL_XZ_ATLAS",
        "eyes": eyes,
        "captures": captures,
        "blend": str(blend_out),
        "label": args.label,
        "production": "NO-GO",
    }
    (out / f"{args.label}_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
