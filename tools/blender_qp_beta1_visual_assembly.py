"""Beta 1 visual assembly: bind textured face head + keep hair/outfit + dual cameras.

Does not mutate sealed canonical blends. Operates on Alpha-assembled work copies only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


FACE_VIEWS = (("face_front", 0.0), ("face_left45", 45.0), ("face_right45", -45.0))
BODY_VIEWS = (("body_front", 0.0), ("body_left45", 35.0), ("body_right45", -35.0))


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--face-obj", required=True)
    ap.add_argument("--albedo", required=True)
    ap.add_argument("--eye-l", required=True)
    ap.add_argument("--eye-r", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--resolution", type=int, default=1024)
    return ap.parse_args(argv)


def _look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Z").to_euler()


def _parse_vec(s: str) -> Vector:
    parts = s.replace(",", ";").split(";")
    return Vector(tuple(float(p) for p in parts))


def _find_body():
    for name in ("NURION_BP_CanonicalHuman_V1", "NURION_W_CanonicalHuman_V1"):
        o = bpy.data.objects.get(name)
        if o and o.type == "MESH":
            return o
    return next(o for o in bpy.data.objects if o.type == "MESH")


def _head_bone_world(arm):
    if arm is None:
        return None
    bpy.context.view_layer.update()
    for bname in ("Head", "head", "GT_Head"):
        if bname in arm.pose.bones:
            return arm.matrix_world @ arm.pose.bones[bname].head
        pb = arm.pose.bones.get(bname)
        if pb:
            return arm.matrix_world @ pb.head
    # bone data names
    for bone in arm.data.bones:
        if "head" in bone.name.lower() and "helper" not in bone.name.lower():
            pb = arm.pose.bones.get(bone.name)
            if pb:
                return arm.matrix_world @ pb.head
    return None


def _skin_mat(name="Beta1Skin"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.86, 0.70, 0.60, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.48
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
        if "Subsurface Weight" in bsdf.inputs:
            bsdf.inputs["Subsurface Weight"].default_value = 0.15
    return mat


def _load_face(path: Path):
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
    mesh = bpy.data.meshes.new("Beta1FaceHead")
    mesh.from_pydata(verts, [], [(f[0][0], f[1][0], f[2][0]) for f in faces])
    mesh.update()
    if uvs:
        uv = mesh.uv_layers.new(name="UVMap")
        for poly, face in zip(mesh.polygons, faces):
            for li, (_vi, ti) in zip(poly.loop_indices, face):
                uv.data[li].uv = uvs[ti]
    obj = bpy.data.objects.new("Beta1FaceHead", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _face_material(mesh, albedo: Path):
    img = bpy.data.images.load(str(Path(albedo).resolve()))
    img.colorspace_settings.name = "sRGB"

    # Continuous frontal XZ atlas — matches Beta1 param-head albedo crop (not FaceMesh per-tri UV)
    coords = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    xs = [v.x for v in coords]
    zs = [v.z for v in coords]
    xmin, xmax = min(xs), max(xs)
    zmin, zmax = min(zs), max(zs)
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
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            w = mesh.matrix_world @ me.vertices[vi].co
            uv_layer.data[li].uv = ((w.x - xmin) / dx, (w.z - zmin) / dz)

    mat = bpy.data.materials.new("Beta1FaceAlbedo")
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
    bsdf.inputs["Roughness"].default_value = 0.5
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mesh.data.materials.clear()
    mesh.data.materials.append(mat)


def _add_eye(name, loc, radius):
    # Place eyeball center INTO the head (+Y) so it does not protrude past the face plane
    deep = loc + Vector((0.0, radius * 1.2, 0.0))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=deep, segments=24, ring_count=16)
    eye = bpy.context.active_object
    eye.name = name
    mat = bpy.data.materials.new(name + "Mat")
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (0.88, 0.89, 0.90, 1.0)
        b.inputs["Roughness"].default_value = 0.15
    eye.data.materials.append(mat)
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius * 0.4, location=deep + Vector((0, -radius * 0.5, 0)), segments=16, ring_count=10
    )
    iris = bpy.context.active_object
    iris.name = name + "_Iris"
    im = bpy.data.materials.new(name + "Iris")
    im.use_nodes = True
    ib = im.node_tree.nodes.get("Principled BSDF")
    if ib:
        ib.inputs["Base Color"].default_value = (0.18, 0.24, 0.32, 1.0)
    iris.data.materials.append(im)
    return [eye, iris]


def _shell(name, center, size, color):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    mat = bpy.data.materials.new(name + "Mat")
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*color, 1.0)
        b.inputs["Roughness"].default_value = 0.55
        if "Metallic" in b.inputs:
            b.inputs["Metallic"].default_value = 0.0
    obj.data.materials.append(mat)
    return obj


def _shrink_block_head(body):
    """Collapse high-Z head cuboid toward neck so face head can replace it."""
    coords = [v.co.copy() for v in body.data.vertices]
    zs = [c.z for c in coords]
    zmax, zmin = max(zs), min(zs)
    thresh = zmin + (zmax - zmin) * 0.78
    neck = Vector((0.0, 0.0, thresh))
    for v in body.data.vertices:
        if v.co.z >= thresh:
            v.co = v.co.lerp(neck, 0.92)
    body.data.update()


def main() -> int:
    args = _parse()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend)))

    body = _find_body()
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    arm = arms[0] if arms else None

    # Body skin
    skin = _skin_mat()
    body.data.materials.clear()
    body.data.materials.append(skin)
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    bpy.ops.object.shade_smooth()
    _shrink_block_head(body)

    # Face head
    face = _load_face(Path(args.face_obj))
    _face_material(face, Path(args.albedo))
    bpy.context.view_layer.objects.active = face
    face.select_set(True)
    bpy.ops.object.shade_smooth()

    head_w = _head_bone_world(arm)
    body_bb = [body.matrix_world @ Vector(c) for c in body.bound_box]
    if head_w is None:
        zs = [v.z for v in body_bb]
        xs = [v.x for v in body_bb]
        ys = [v.y for v in body_bb]
        head_w = Vector((sum(xs) / 8, min(ys) - 0.02, max(zs) - 0.08))

    face_span = max((max(v.co.x for v in face.data.vertices) - min(v.co.x for v in face.data.vertices)), 0.2)
    body_head_w = max(max(v.x for v in body_bb) - min(v.x for v in body_bb), 0.15) * 0.55
    scale = body_head_w / face_span
    face.scale = (scale, scale, scale)
    face.location = head_w + Vector((0.0, -0.02, 0.02))
    bpy.context.view_layer.update()

    # Eyes: texture carries lids; deep spheres only (no surface bars)
    eye_l = _parse_vec(args.eye_l)
    eye_r = _parse_vec(args.eye_r)
    iod = (eye_l - eye_r).length
    radius = max(0.008, iod * scale * 0.12)
    eyes = []
    for name, local in (("Beta1Eye_L", eye_l), ("Beta1Eye_R", eye_r)):
        wloc = face.matrix_world @ local
        created = _add_eye(name, wloc, radius)
        for o in created:
            o.parent = face
        eyes.extend(created)

    # Hair + outfit shells (kept, not deleted)
    bb = body_bb
    cx = sum(v.x for v in bb) / 8
    cy = sum(v.y for v in bb) / 8
    cz0 = min(v.z for v in bb)
    cz1 = max(v.z for v in bb)
    h = cz1 - cz0
    hair = _shell(
        "Beta1Hair_SHORT_NEAT_01",
        Vector((cx, cy - 0.02, cz0 + h * 0.92)),
        Vector((body_head_w * 1.15, 0.18, 0.14)),
        (0.08, 0.06, 0.05),
    )
    suit = _shell(
        "Beta1Outfit_BUSINESS_SUIT_01",
        Vector((cx, cy, cz0 + h * 0.48)),
        Vector(((max(v.x for v in bb) - min(v.x for v in bb)) * 0.62, 0.16, h * 0.38)),
        (0.18, 0.22, 0.28),
    )

    # Clear lights
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    def add_light(name, loc, energy):
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.size = 1.6
        o = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        return o

    face_target = face.matrix_world.translation + Vector((0, 0, 0.02))
    body_target = Vector((cx, cy, cz0 + h * 0.55))
    add_light("K", (face_target.x + 0.5, face_target.y - 1.2, face_target.z + 0.4), 160)
    add_light("F", (face_target.x - 0.6, face_target.y - 0.9, face_target.z + 0.1), 60)
    add_light("R", (face_target.x, face_target.y + 1.1, face_target.z + 0.2), 70)

    world = bpy.data.worlds.new("Beta1World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.12, 0.13, 0.14, 1.0)
        bg.inputs[1].default_value = 0.4

    cam_data = bpy.data.cameras.new("Beta1Cam")
    cam_data.lens = 70
    cam = bpy.data.objects.new("Beta1Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.image_settings.file_format = "PNG"

    captures = []
    # Face cameras
    face_dist = max(body_head_w * 3.2, 0.55)
    for view, yaw_deg in FACE_VIEWS:
        yaw = math.radians(yaw_deg)
        cam.location = face_target + Vector((math.sin(yaw) * face_dist, -math.cos(yaw) * face_dist, 0.03))
        _look_at(cam, face_target)
        path = out / f"{args.label}_{view}"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        captures.append(f"{path.name}.png")

    # Full-body homepage cameras
    body_dist = max(h * 2.2, 2.4)
    cam_data.lens = 50
    for view, yaw_deg in BODY_VIEWS:
        yaw = math.radians(yaw_deg)
        cam.location = body_target + Vector((math.sin(yaw) * body_dist, -math.cos(yaw) * body_dist, h * 0.05))
        _look_at(cam, body_target)
        path = out / f"{args.label}_{view}"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        captures.append(f"{path.name}.png")

    # Save assembled blend + glb
    blend_out = out / f"{args.label}_Beta1_Visual.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))
    glb_out = out / f"{args.label}_Beta1_Visual.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb_out), export_format="GLB", use_selection=False)

    meta = {
        "label": args.label,
        "bodyMesh": body.name,
        "faceHead": face.name,
        "hair": hair.name,
        "outfit": suit.name,
        "eyes": [e.name for e in eyes],
        "captures": captures,
        "blend": str(blend_out),
        "glb": str(glb_out),
        "blockHeadCollapsed": True,
        "production": "NO-GO",
    }
    (out / f"{args.label}_beta1_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
