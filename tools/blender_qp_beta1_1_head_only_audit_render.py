"""Beta 1.1 head-only scene: isolate Head collection, audit objects, true parametric depth renders.

Outputs ONLY: wireframe, front, left45, right45. No body / hair cube / outfit shells.
Camera + lights FIXED; head rotates for ±45.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


REQUIRED_PARTS = ("ParamHeadV1", "Eye_L", "Eye_R", "Eyelid_L", "Eyelid_R", "Lips", "OralCavity")


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", required=True)
    ap.add_argument("--albedo", required=True)
    ap.add_argument("--corr-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default="HEAD")
    ap.add_argument("--resolution", type=int, default=1024)
    ap.add_argument("--audit-json", required=True)
    return ap.parse_args(argv)


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b)
    for c in list(bpy.data.collections):
        if c.name != "Collection":
            bpy.data.collections.remove(c)


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
    return obj, len(faces)


def _frontal_uv(mesh):
    coords = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    xs = [v.x for v in coords]
    zs = [v.z for v in coords]
    xmin, xmax = min(xs) - 1e-3, max(xs) + 1e-3
    zmin, zmax = min(zs) - 1e-3, max(zs) + 1e-3
    dx = max(xmax - xmin, 1e-6)
    dz = max(zmax - zmin, 1e-6)
    me = mesh.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv_layer = me.uv_layers.active
    # Continuous frontal atlas: same vertex → same UV on every loop (no FaceMesh per-tri shatter)
    vert_uv = {}
    for vi, v in enumerate(me.vertices):
        w = mesh.matrix_world @ v.co
        vert_uv[vi] = ((w.x - xmin) / dx, (w.z - zmin) / dz)
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uv_layer.data[li].uv = vert_uv[vi]

    # Continuity: per-vertex UV variance across loops must be ~0
    from collections import defaultdict

    acc = defaultdict(list)
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uv = uv_layer.data[li].uv
            acc[vi].append((float(uv.x), float(uv.y)))
    max_uv_break = 0.0
    for samples in acc.values():
        if len(samples) < 2:
            continue
        xs_ = [s[0] for s in samples]
        ys_ = [s[1] for s in samples]
        max_uv_break = max(max_uv_break, max(xs_) - min(xs_), max(ys_) - min(ys_))

    # Stretch: median-centered ratio on mid-face triangles only (exclude poles)
    stretches = []
    for poly in me.polygons:
        center = mesh.matrix_world @ (sum((me.vertices[i].co for i in poly.vertices), Vector((0, 0, 0))) / len(poly.vertices))
        # mid-face band
        if abs(center.z - (zmin + zmax) * 0.5) > dz * 0.35:
            continue
        loops = list(poly.loop_indices)
        if len(loops) < 3:
            continue
        w0 = mesh.matrix_world @ me.vertices[me.loops[loops[0]].vertex_index].co
        w1 = mesh.matrix_world @ me.vertices[me.loops[loops[1]].vertex_index].co
        uv0 = uv_layer.data[loops[0]].uv
        uv1 = uv_layer.data[loops[1]].uv
        wlen = (w1 - w0).length + 1e-8
        ulen = ((uv1.x - uv0.x) ** 2 + (uv1.y - uv0.y) ** 2) ** 0.5 + 1e-8
        stretches.append(ulen / wlen)
    if stretches:
        stretches.sort()
        lo = stretches[max(0, int(len(stretches) * 0.1))]
        hi = stretches[min(len(stretches) - 1, int(len(stretches) * 0.9))]
        stretch_ratio = float(hi / (lo + 1e-8))
    else:
        stretch_ratio = 1.0
    return stretch_ratio, float(max_uv_break)


def _skin_mat(name, albedo: Path | None = None, color=(0.82, 0.68, 0.60, 1.0)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    if albedo is not None:
        nodes.clear()
        out = nodes.new("ShaderNodeOutputMaterial")
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        tex = nodes.new("ShaderNodeTexImage")
        img = bpy.data.images.load(str(Path(albedo).resolve()))
        img.colorspace_settings.name = "sRGB"
        tex.image = img
        tex.extension = "CLIP"
        uv = nodes.new("ShaderNodeUVMap")
        links.new(uv.outputs["UV"], tex.inputs["Vector"])
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    elif bsdf:
        bsdf.inputs["Base Color"].default_value = color
    if bsdf:
        bsdf.inputs["Roughness"].default_value = 0.48
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def _aabb(obj):
    coords = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in coords]
    ys = [v.y for v in coords]
    zs = [v.z for v in coords]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _aabb_intersect(a, b) -> bool:
    return not (a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2] or a[5] < b[4] or b[5] < a[4])


def _is_cube_like(obj) -> bool:
    name = obj.name.lower()
    if any(k in name for k in ("cube", "plane", "debug", "mask", "shell", "hair", "outfit", "block")):
        return True
    if obj.type != "MESH":
        return False
    # 8 verts typical of unsubdivided cube
    return len(obj.data.vertices) <= 12 and len(obj.data.polygons) <= 12


def _link_head(obj, head_coll):
    head_coll.objects.link(obj)
    if obj.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(obj)


def _add_eye_stack(name_prefix: str, surface: Vector, radius: float, head_coll):
    """Eyeball deep in socket (+Y); eyelid covers from front."""
    eye_center = surface + Vector((0.0, radius * 1.85, 0.0))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 0.92, location=eye_center, segments=20, ring_count=14)
    eye = bpy.context.active_object
    eye.name = name_prefix
    eye.data.materials.append(_skin_mat(name_prefix + "Mat", color=(0.86, 0.87, 0.88, 1.0)))
    _link_head(eye, head_coll)

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius * 0.38, location=eye_center + Vector((0.0, -radius * 0.5, 0.0)), segments=12, ring_count=8
    )
    iris = bpy.context.active_object
    iris.name = name_prefix + "_Iris"
    iris.data.materials.append(_skin_mat(iris.name + "Mat", color=(0.12, 0.16, 0.22, 1.0)))
    _link_head(iris, head_coll)

    lid_loc = surface + Vector((0.0, radius * 0.25, radius * 0.35))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.05, location=lid_loc, segments=16, ring_count=10)
    lid = bpy.context.active_object
    lid.name = name_prefix.replace("Eye", "Eyelid")
    lid.scale = Vector((1.05, 0.35, 0.55))
    lid.data.materials.append(_skin_mat(lid.name + "Mat", color=(0.80, 0.64, 0.56, 1.0)))
    _link_head(lid, head_coll)
    return eye, lid, iris


def _add_lips_oral(corr, head, head_coll, span: float):
    V = head.data.vertices
    mw = head.matrix_world
    up = mw @ V[int(corr["LIP_UPPER"])].co
    lo = mw @ V[int(corr["LIP_LOWER"])].co
    ml = mw @ V[int(corr["MOUTH_L"])].co
    mr = mw @ V[int(corr["MOUTH_R"])].co
    mid = (up + lo) * 0.5
    width = max((mr - ml).length, span * 0.10)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=mid + Vector((0.0, -span * 0.008, 0.0)), segments=24, ring_count=14)
    lips = bpy.context.active_object
    lips.name = "Lips"
    lips.scale = Vector((width * 0.42, span * 0.012, span * 0.016))
    lips.data.materials.append(_skin_mat("LipsMat", color=(0.55, 0.22, 0.26, 1.0)))
    _link_head(lips, head_coll)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=mid + Vector((0.0, span * 0.045, 0.0)), segments=16, ring_count=10)
    oral = bpy.context.active_object
    oral.name = "OralCavity"
    oral.scale = Vector((width * 0.28, span * 0.03, span * 0.012))
    oral.data.materials.append(_skin_mat("OralMat", color=(0.18, 0.05, 0.05, 1.0)))
    _link_head(oral, head_coll)
    return lips, oral


def run_audit(head, head_coll, triangle_count: int, uv_stretch: float, uv_break: float, corr) -> dict:
    failures = []
    renderable = [o for o in bpy.data.objects if o.type == "MESH" and o.hide_render is False]
    not_in_head = [o.name for o in renderable if o.name not in {x.name for x in head_coll.objects}]
    if not_in_head:
        failures.append(f"RENDERABLE_OUTSIDE_HEAD_COLLECTION:{not_in_head}")

    face_bb = _aabb(head)
    pad = 0.02
    face_bb = (
        face_bb[0] - pad,
        face_bb[1] + pad,
        face_bb[2] - pad,
        face_bb[3] + pad,
        face_bb[4] - pad,
        face_bb[5] + pad,
    )
    allowed = set(REQUIRED_PARTS) | {head.name, "Eye_L_Iris", "Eye_R_Iris"}
    penetrators = []
    for o in renderable:
        if o.name in allowed or o.name.startswith("Eye_") or o.name.startswith("Eyelid_"):
            continue
        if _is_cube_like(o) and _aabb_intersect(face_bb, _aabb(o)):
            penetrators.append({"name": o.name, "verts": len(o.data.vertices), "polys": len(o.data.polygons)})
    if penetrators:
        failures.append(f"FACE_BB_PENETRATING_CUBE_PLANE:{penetrators}")

    if triangle_count == 854:
        failures.append("FACEMESH_854_TRIANGLE_FINAL_RENDER")
    if triangle_count < 2000:
        failures.append(f"PARAMETRIC_TOPOLOGY_TOO_COARSE:{triangle_count}")

    names = {o.name for o in renderable}
    for req in REQUIRED_PARTS:
        if req not in names:
            failures.append(f"MISSING_PART:{req}")

    for side in ("L", "R"):
        eye = bpy.data.objects.get(f"Eye_{side}")
        lid = bpy.data.objects.get(f"Eyelid_{side}")
        if eye and lid:
            if eye.location.y <= lid.location.y:
                failures.append(f"EYE_NOT_BEHIND_LID:{side}:eyeY={eye.location.y:.4f}:lidY={lid.location.y:.4f}")

    V = head.data.vertices
    nose_y = (head.matrix_world @ V[int(corr["NOSE"])].co).y
    lip_y = (
        (head.matrix_world @ V[int(corr["LIP_UPPER"])].co).y
        + (head.matrix_world @ V[int(corr["LIP_LOWER"])].co).y
    ) * 0.5
    chin_y = (head.matrix_world @ V[int(corr["CHIN"])].co).y
    if not (nose_y < lip_y):
        failures.append(f"DEPTH_ORDER_NOSE_LIP:noseY={nose_y:.4f}:lipY={lip_y:.4f}")
    if not (nose_y < chin_y + 0.05):
        failures.append(f"DEPTH_ORDER_NOSE_CHIN:noseY={nose_y:.4f}:chinY={chin_y:.4f}")

    # FaceMesh shatter signature: per-vertex UV break across loops
    if uv_break > 1e-4:
        failures.append(f"UV_DISCONTINUITY_PER_VERTEX:{uv_break:.6f}")
    if uv_stretch > 8.0:
        failures.append(f"UV_STRETCH_RATIO_HIGH:{uv_stretch:.2f}")

    gray_bar_suspects = [
        o.name
        for o in bpy.data.objects
        if o.type == "MESH" and any(k in o.name.lower() for k in ("hair", "outfit", "shell", "mask", "debug"))
    ]

    return {
        "pass": len(failures) == 0,
        "failures": failures,
        "triangleCount": triangle_count,
        "facemesh854Used": triangle_count == 854,
        "uvStretchRatio": uv_stretch,
        "uvDiscontinuity": uv_break,
        "renderableMeshes": sorted(names),
        "headCollection": head_coll.name,
        "depth": {"noseY": nose_y, "lipY": lip_y, "chinY": chin_y},
        "grayBarSuspectsInScene": gray_bar_suspects,
        "priorGrayBarObject": "Beta1Hair_SHORT_NEAT_01",
        "priorGrayBarMechanism": "Hair proxy CUBE scaled through face AABB in beta1 visual assembly",
        "fullBodyAssembly": "DENY",
    }


def main() -> int:
    args = _parse()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    corr = json.loads(Path(args.corr_json).read_text(encoding="utf-8"))
    _clear()

    head_coll = bpy.data.collections.new("HeadOnly")
    bpy.context.scene.collection.children.link(head_coll)

    head, tri_count = _load_obj(Path(args.obj))
    head_coll.objects.link(head)
    bpy.context.view_layer.objects.active = head
    head.select_set(True)
    bpy.ops.object.shade_smooth()

    stretch, uv_break = _frontal_uv(head)
    head.data.materials.clear()
    head.data.materials.append(_skin_mat("HeadAlbedo", albedo=Path(args.albedo)))

    coords = [head.matrix_world @ v.co for v in head.data.vertices]
    xs = [v.x for v in coords]
    ys = [v.y for v in coords]
    zs = [v.z for v in coords]
    target = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.55))
    span = max(max(xs) - min(xs), max(zs) - min(zs), 0.35)

    for side, key in (("L", "L_EYE"), ("R", "R_EYE")):
        surface = head.matrix_world @ head.data.vertices[int(corr[key])].co
        _add_eye_stack(f"Eye_{side}", surface, span * 0.028, head_coll)

    _add_lips_oral(corr, head, head_coll, span)

    # Hide anything not in HeadOnly from render (belt-and-suspenders)
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name not in {x.name for x in head_coll.objects}:
            o.hide_render = True
            o.hide_viewport = True

    audit = run_audit(head, head_coll, tri_count, stretch, uv_break, corr)
    Path(args.audit_json).write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not audit["pass"]:
        print(json.dumps({"verdict": "AUTO_AUDIT_FAIL", "audit": audit}, ensure_ascii=False))
        return 3

    # Fixed lights + camera — DO NOT move with head yaw
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

    add_light("K", (target.x + 0.45 * span, target.y - 1.3 * span, target.z + 0.35 * span), 140)
    add_light("F", (target.x - 0.55 * span, target.y - 1.0 * span, target.z + 0.1 * span), 50)
    add_light("R", (target.x, target.y + 1.1 * span, target.z + 0.25 * span), 60)

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.14, 0.15, 0.16, 1.0)
        bg.inputs[1].default_value = 0.35

    cam_data = bpy.data.cameras.new("FaceCamFixed")
    cam_data.lens = 85
    cam = bpy.data.objects.new("FaceCamFixed", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    dist = span * 2.5
    cam.location = target + Vector((0.0, -dist, 0.04 * span))
    _look_at(cam, target)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.image_settings.file_format = "PNG"

    # Parent anatomical parts to head for yaw
    for o in list(head_coll.objects):
        if o != head:
            o.parent = head

    captures = []

    # Wireframe: EEVEE + Wireframe modifier on head only (WORKBENCH display_type does not affect render)
    hide_parts = [o for o in head_coll.objects if o != head]
    for o in hide_parts:
        o.hide_render = True
    wf = head.modifiers.new(name="HeadWire", type="WIREFRAME")
    wf.thickness = 0.004
    wf.use_replace = True
    # Neutral wire material
    wmat = bpy.data.materials.new("WireMat")
    wmat.use_nodes = True
    wb = wmat.node_tree.nodes.get("Principled BSDF")
    if wb:
        wb.inputs["Base Color"].default_value = (0.85, 0.85, 0.88, 1.0)
        wb.inputs["Roughness"].default_value = 1.0
    head.data.materials.clear()
    head.data.materials.append(wmat)
    scene.render.engine = "BLENDER_EEVEE"
    path = out / f"{args.label}_head_wireframe"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    captures.append(f"{path.name}.png")
    head.modifiers.remove(wf)
    head.data.materials.clear()
    head.data.materials.append(_skin_mat("HeadAlbedo", albedo=Path(args.albedo)))
    for o in hide_parts:
        o.hide_render = False

    for view, yaw_deg in (("head_front", 0.0), ("head_left45", 45.0), ("head_right45", -45.0)):
        head.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
        bpy.context.view_layer.update()
        path = out / f"{args.label}_{view}"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        captures.append(f"{path.name}.png")

    head.rotation_euler = (0.0, 0.0, 0.0)
    blend_out = out / f"{args.label}_HeadOnly.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))

    meta = {
        "modelId": "NURION_PARAMETRIC_HEAD_V1_1",
        "directFaceMeshRender": "DENY",
        "fullBodyAssembly": "DENY",
        "cameraLights": "FIXED",
        "headYawForViews": True,
        "captures": captures,
        "auditPass": True,
        "triangleCount": tri_count,
        "grayBarExcluded": True,
        "production": "NO-GO",
    }
    (out / f"{args.label}_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
