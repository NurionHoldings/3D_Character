"""
Export 10-point Alpha2 surface GT with faceIndex + barycentric + UV binding.

Prefer --blend (edited annotation scene). Re-importing FBX alone cannot carry manual guides.

Usage:
  blender --background --python tools/blender_export_surface_gt.py -- \\
    --blend dist/v0.3/face/alpha2/annotations/tennis-surface-gt-edit.blend \\
    --out dist/v0.3/face/alpha2/annotations/face-surface-gt.json --label tennis
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
SURFACE_KEYS = [
    "eye.inner.L", "eye.inner.R",
    "eye.outer.L", "eye.outer.R",
    "eyelid.upper.L", "eyelid.upper.R",
    "eyelid.lower.L", "eyelid.lower.R",
    "iris.visualCenter.L", "iris.visualCenter.R",
]
REQUIRED_FIELDS = (
    "faceIndex",
    "triangleVertices",
    "barycentric",
    "uv",
    "positionWorld",
    "positionHeadLocal",
    "predictionHidden",
    "snapToPrediction",
)


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--blend", default="", help="Edited .blend with NURION_FACE_* guides")
    p.add_argument("--fbx", default="", help="Optional FBX if not using --blend")
    p.add_argument("--out", required=True)
    p.add_argument("--label", default="surface-gt")
    p.add_argument("--mesh", default="")
    return p.parse_args(argv)


def _barycentric(p: Vector, a: Vector, b: Vector, c: Vector) -> Tuple[float, float, float]:
    v0, v1, v2 = b - a, c - a, p - a
    d00 = v0.dot(v0)
    d01 = v0.dot(v1)
    d11 = v1.dot(v1)
    d20 = v2.dot(v0)
    d21 = v2.dot(v1)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-18:
        return (1.0, 0.0, 0.0)
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    return (float(u), float(v), float(w))


def _bind_to_mesh(mesh_obj, world_point: Vector) -> Optional[dict]:
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(deps)
    me = eval_obj.to_mesh()
    try:
        mw = eval_obj.matrix_world.copy()
        me.transform(mw)
        me.calc_loop_triangles()
        bvh = BVHTree.FromPolygons(
            [v.co.copy() for v in me.vertices],
            [tuple(tri.vertices) for tri in me.loop_triangles],
        )
        loc, _normal, index, dist = bvh.find_nearest(world_point)
        if loc is None or index is None:
            return None
        tri = me.loop_triangles[index]
        vids = list(tri.vertices)
        a = me.vertices[vids[0]].co
        b = me.vertices[vids[1]].co
        c = me.vertices[vids[2]].co
        bu, bv, bw = _barycentric(loc, a, b, c)

        uv = None
        uv_layer = me.uv_layers.active
        if uv_layer is not None and len(tri.loops) >= 3:
            # Interpolate UVs from loop corners using barycentric weights.
            uvs = []
            for loop_i in tri.loops[:3]:
                uv_co = uv_layer.data[loop_i].uv
                uvs.append(Vector((float(uv_co.x), float(uv_co.y))))
            uv_vec = uvs[0] * bu + uvs[1] * bv + uvs[2] * bw
            uv = [round(float(uv_vec.x), 6), round(float(uv_vec.y), 6)]
        if uv is None:
            # Fallback: project unavailable — mark invalid for Alpha2 surface GT.
            return None

        return {
            "objectName": mesh_obj.name,
            "faceIndex": int(index),
            "triangleVertices": [int(x) for x in vids],
            "barycentric": [round(bu, 6), round(bv, 6), round(bw, 6)],
            "uv": uv,
            "surfaceDistanceMm": round(float(dist) * 1000.0, 3),
            "positionWorldBound": [round(float(x), 6) for x in loc],
        }
    finally:
        eval_obj.to_mesh_clear()


def _collect_guides() -> Dict[str, Vector]:
    out: Dict[str, Vector] = {}
    prefixes = ("NURION_FACE_", "NURION_GT_")
    for obj in bpy.data.objects:
        if obj.hide_get() and obj.get("nurion_domain") != "surface_gt":
            # Still allow hidden GT guides if domain tagged.
            pass
        for pref in prefixes:
            if obj.name.startswith(pref):
                key = obj.name[len(pref) :]
                if key in SURFACE_KEYS:
                    out[key] = obj.matrix_world.translation.copy()
                break
        if "nurion_landmark" in obj and str(obj["nurion_landmark"]) in SURFACE_KEYS:
            out[str(obj["nurion_landmark"])] = obj.matrix_world.translation.copy()
    return out


def _validate_entry(entry: dict) -> List[str]:
    missing = []
    for f in REQUIRED_FIELDS:
        if f not in entry or entry[f] is None:
            missing.append(f)
        elif f == "uv" and (not isinstance(entry[f], list) or len(entry[f]) != 2):
            missing.append("uv")
        elif f == "barycentric" and (not isinstance(entry[f], list) or len(entry[f]) != 3):
            missing.append("barycentric")
        elif f == "triangleVertices" and (not isinstance(entry[f], list) or len(entry[f]) != 3):
            missing.append("triangleVertices")
    if entry.get("predictionHidden") is not True:
        missing.append("predictionHidden!=true")
    if entry.get("snapToPrediction") is not False:
        missing.append("snapToPrediction!=false")
    return missing


def main() -> int:
    args = _parse(sys.argv)
    out = Path(args.out)
    blend = Path(args.blend) if args.blend else None
    fbx = Path(args.fbx) if args.fbx else None

    if blend and blend.exists():
        bpy.ops.wm.open_mainfile(filepath=str(blend))
    elif fbx and fbx.exists():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    else:
        raise RuntimeError("Provide --blend (preferred) or --fbx")

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if arms:
        arms[0].data.pose_position = "REST"
        bpy.context.view_layer.update()

    for name in ("NURION_Eyeball.L", "NURION_Eyeball.R"):
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_set(True)
            obj.hide_viewport = True
            obj.hide_render = True

    meshes = sorted(
        [
            o
            for o in bpy.data.objects
            if o.type == "MESH" and not o.name.startswith("NURION_")
        ],
        key=lambda o: len(o.data.vertices),
        reverse=True,
    )
    mesh = bpy.data.objects.get(args.mesh) if args.mesh else (meshes[0] if meshes else None)
    if mesh is None:
        raise RuntimeError("No char mesh (expected char1)")

    guides = _collect_guides()
    if len(guides) < 10:
        raise RuntimeError(
            f"Need 10 surface GT guides (found {len(guides)}): {sorted(set(SURFACE_KEYS) - set(guides))}"
        )

    sys.path.insert(0, str(ROOT))
    from nurion_character_landmarker.core.face.region import evaluate_face_region
    from nurion_character_landmarker.core.face.spaces import build_head_frame
    from nurion_character_landmarker.core.transform_normalize import build_world_mesh_view

    view = build_world_mesh_view(mesh)
    region = evaluate_face_region(mesh, view=view, forward_axis="+Y")
    frame = region.headFrame
    if frame is None:
        height = float((view.bounds_max - view.bounds_min).z)
        frame = build_head_frame(
            head_center=view.center,
            forward_axis="+Y",
            head_height=height * 0.22,
            body=None,
        )

    landmarks = []
    invalid = []
    for name in SURFACE_KEYS:
        world = guides[name]
        bind = _bind_to_mesh(mesh, world)
        if bind is None:
            invalid.append({"name": name, "reason": "SURFACE_BIND_FAILED_OR_NO_UV"})
            landmarks.append({"name": name, "annotated": False})
            continue
        bound = Vector(bind["positionWorldBound"])
        local = frame.to_local(bound)
        entry = {
            "name": name,
            "gtMethod": "MANUAL_TEXTURE_SURFACE",
            "source": "MANUAL",
            "confidence": 1.0,
            "reviewRequired": False,
            "annotated": True,
            "predictionHidden": True,
            "snapToPrediction": False,
            "objectName": bind["objectName"],
            "faceIndex": bind["faceIndex"],
            "triangleVertices": bind["triangleVertices"],
            "barycentric": bind["barycentric"],
            "uv": bind["uv"],
            "surfaceDistanceMm": bind["surfaceDistanceMm"],
            "positionWorld": bind["positionWorldBound"],
            "positionHeadLocal": [round(float(x), 6) for x in local],
        }
        miss = _validate_entry(entry)
        if miss:
            invalid.append({"name": name, "reason": "MISSING_FIELDS", "fields": miss})
            entry["annotated"] = False
        landmarks.append(entry)

    annotated = [e for e in landmarks if e.get("annotated")]
    doc = {
        "schema": "NURION_FACE_SURFACE_GROUND_TRUTH",
        "version": "0.3.0-alpha.2",
        "characterId": args.label,
        "meshName": mesh.name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "predictionHiddenDuringAnnotation": True,
        "snapToPrediction": False,
        "eyeballsHiddenDuringAnnotation": True,
        "keys": SURFACE_KEYS,
        "annotatedCount": len(annotated),
        "validSurfaceBoundCount": len(annotated),
        "invalid": invalid,
        "headFrame": {
            "origin": [round(float(x), 6) for x in frame.origin],
            "forward": [round(float(x), 6) for x in frame.forward],
            "right": [round(float(x), 6) for x in frame.right],
            "up": [round(float(x), 6) for x in frame.up],
            "headHeight": round(float(frame.head_height), 6),
        },
        "landmarks": landmarks,
        "note": (
            "iris.visualCenter is texture visual center on mesh surface, not geometric eyeball center. "
            "Guides must be fixed to char1 surface."
        ),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ok = len(annotated) == 10 and not invalid
    summary = {
        "wrote": str(out),
        "annotatedCount": len(annotated),
        "valid": ok,
        "failClass": None if ok else "SURFACE_GT_INVALID",
        "invalid": invalid,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if ok else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
