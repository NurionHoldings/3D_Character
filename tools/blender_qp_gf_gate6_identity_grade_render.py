"""Gate 6 Blender: textured landmark head + metric eyeballs + matched views."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


VIEWS = (("front", 0.0), ("left45", 45.0), ("right45", -45.0))


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", required=True)
    ap.add_argument("--albedo", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--draft-label", default="NATURAL")
    ap.add_argument("--eye-l", required=True, help="x,y,z")
    ap.add_argument("--eye-r", required=True, help="x,y,z")
    ap.add_argument("--resolution", type=int, default=1024)
    return ap.parse_args(argv)


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for b in list(coll):
            coll.remove(b)


def _look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Z").to_euler()


def _parse_vec(s: str) -> Vector:
    parts = s.replace(",", ";").split(";")
    x, y, z = [float(p) for p in parts]
    return Vector((x, y, z))


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
    mesh = bpy.data.meshes.new("TexturedLandmarkHead")
    mesh.from_pydata(verts, [], [(f[0][0], f[1][0], f[2][0]) for f in faces])
    mesh.update()
    if uvs:
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for poly, face in zip(mesh.polygons, faces):
            for li, (_vi, ti) in zip(poly.loop_indices, face):
                uv_layer.data[li].uv = uvs[ti]
    obj = bpy.data.objects.new("TexturedLandmarkHead", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _material(mesh, albedo: Path):
    img = bpy.data.images.load(str(albedo.resolve()))
    img.colorspace_settings.name = "sRGB"
    mat = bpy.data.materials.new("FaceAlbedo")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    uv = nodes.new("ShaderNodeUVMap")
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.2
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mesh.data.materials.clear()
    mesh.data.materials.append(mat)


def _eye(name: str, loc: Vector, radius: float):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=24, ring_count=16)
    eye = bpy.context.active_object
    eye.name = name
    mat = bpy.data.materials.new(name + "Mat")
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.95, 0.96, 0.97, 1.0)
        b.inputs["Roughness"].default_value = 0.12
    eye.data.materials.append(mat)
    iris_loc = loc + Vector((0.0, -radius * 0.55, 0.0))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 0.4, location=iris_loc, segments=16, ring_count=10)
    iris = bpy.context.active_object
    iris.name = name + "_Iris"
    im = bpy.data.materials.new(name + "Iris")
    im.use_nodes = True
    ib = im.node_tree.nodes.get("Principled BSDF")
    if ib:
        ib.inputs["Base Color"].default_value = (0.15, 0.2, 0.28, 1.0)
    iris.data.materials.append(im)
    return [eye.name, iris.name]


def main() -> int:
    args = _parse()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _clear()
    mesh = _load_obj(Path(args.obj))
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    bpy.ops.object.shade_smooth()
    _material(mesh, Path(args.albedo))

    eye_l = _parse_vec(args.eye_l)
    eye_r = _parse_vec(args.eye_r)
    iod = (eye_l - eye_r).length
    radius = max(0.03, iod * 0.18)
    eyeballs = _eye("Gate6Eye_L", eye_l + Vector((0.0, -radius * 0.15, 0.0)), radius)
    eyeballs += _eye("Gate6Eye_R", eye_r + Vector((0.0, -radius * 0.15, 0.0)), radius)

    coords = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    xs = [v.x for v in coords]
    ys = [v.y for v in coords]
    zs = [v.z for v in coords]
    target = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.55))
    span = max(max(xs) - min(xs), max(zs) - min(zs), 0.35)
    dist = span * 2.55

    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    def add_light(name, loc, energy):
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.size = 1.4
        o = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add_light("K", (target.x + 0.5 * span, target.y - 1.3 * span, target.z + 0.35 * span), 160)
    add_light("F", (target.x - 0.55 * span, target.y - 1.0 * span, target.z + 0.1 * span), 65)
    add_light("R", (target.x, target.y + 1.2 * span, target.z + 0.2 * span), 80)

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.12, 0.13, 0.14, 1.0)
        bg.inputs[1].default_value = 0.35

    cam_data = bpy.data.cameras.new("Gate6Cam")
    cam_data.lens = 85
    cam = bpy.data.objects.new("Gate6Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.image_settings.file_format = "PNG"

    rendered = []
    for view, yaw_deg in VIEWS:
        yaw = math.radians(yaw_deg)
        cam.location = target + Vector((math.sin(yaw) * dist, -math.cos(yaw) * dist, 0.04 * span))
        _look_at(cam, target)
        out = out_dir / f"{args.draft_label}_{view}"
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        rendered.append(f"{out.name}.png")

    meta = {
        "meshName": mesh.name,
        "vertexCount": len(mesh.data.vertices),
        "photoTexture": True,
        "uvMode": "LANDMARK_IMAGE_XY",
        "eyeballs": eyeballs,
        "rendered": rendered,
        "draftLabel": args.draft_label,
        "modelId": "NURION_PARAMETRIC_FACE_V0_TEXTURED_LANDMARK_HEAD",
    }
    (out_dir / f"{args.draft_label}_render_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
