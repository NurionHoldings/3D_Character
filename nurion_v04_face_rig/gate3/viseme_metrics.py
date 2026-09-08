"""Viseme safety metrics on candidate mesh."""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from mathutils import Vector

from .parameters import GATE3_PARAMETERS


def eval_world_verts(mesh_obj) -> List[Vector]:
    import bpy

    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        mw = ev.matrix_world
        return [mw @ v.co for v in me.vertices]
    finally:
        ev.to_mesh_clear()


def snapshot_local(mesh_obj) -> List[Tuple[float, float, float]]:
    return [(float(v.co.x), float(v.co.y), float(v.co.z)) for v in mesh_obj.data.vertices]


def max_drift(a, b) -> float:
    m = 0.0
    for p, q in zip(a, b):
        d = math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)
        if d > m:
            m = d
    return m


def measure_state(
    *,
    cand,
    arm,
    axes,
    landmarks: Dict[str, Vector],
    rest_local,
    rest_world: List[Vector],
    mu: float,
    jaw_rest_head,
    jaw_rest_tail,
) -> Dict:
    import bpy

    bpy.context.view_layer.update()
    world = eval_world_verts(cand)
    inv = axes.matrix_world_inv
    hh = max(float(axes.head_height), 1e-4)

    # lip centers from landmarks + current corner guides approx via nearest verts
    def nearest(target: Vector):
        best = None
        bd = 1e9
        for p in world:
            d = (p - target).length
            if d < bd:
                bd = d
                best = p
        return best

    # Use weighted bone locations as proxies for lip order
    pb_u = arm.pose.bones.get("lip.upper.center")
    pb_l = arm.pose.bones.get("lip.lower.center")
    # world positions of bone heads
    upper_w = arm.matrix_world @ pb_u.head if pb_u else landmarks["lip.upper.center"]
    lower_w = arm.matrix_world @ pb_l.head if pb_l else landmarks["lip.lower.center"]
    # Actually pose bones: matrix @ (0,0,0) in bone space
    if pb_u:
        upper_w = arm.matrix_world @ pb_u.matrix @ Vector((0, 0, 0))
    if pb_l:
        lower_w = arm.matrix_world @ pb_l.matrix @ Vector((0, 0, 0))
    u_loc = inv @ upper_w
    l_loc = inv @ lower_w
    lip_order_inversion = 1 if float(u_loc.z) < float(l_loc.z) - 1e-5 else 0
    # self intersection proxy: upper below lower after close-heavy poses
    lip_intersection = 1 if float(u_loc.z) < float(l_loc.z) else 0

    # Forbidden regions: neck / eyes / ears / nose — cheek/jaw/lip/brow face motion is allowed
    non_mouth_leak = 0
    face_tear = 0
    moved = []
    min_move = 0.002 * mu
    for i, (rw, cw) in enumerate(zip(rest_world, world)):
        d = (rw - cw).length
        if d < min_move:
            continue
        loc = inv @ cw
        forbidden = False
        # neck
        if float(loc.z) < -0.22 * hh:
            forbidden = True
        # ears
        if abs(float(loc.x)) > 0.40 * hh:
            forbidden = True
        # eyes
        if 0.48 * hh < float(loc.z) < 0.72 * hh and abs(float(loc.x)) < 0.22 * hh and float(loc.y) > 0.0:
            forbidden = True
        # nose tip
        if abs(float(loc.x)) < 0.07 * hh and 0.24 * hh < float(loc.z) < 0.40 * hh and float(loc.y) > 0.22 * hh:
            forbidden = True
        if forbidden:
            non_mouth_leak += 1
        moved.append(d / mu)
        if d / mu > 1.2:
            face_tear += 1

    # corners L/R from pose bone channels (stable distinctness signal)
    pb_cl = arm.pose.bones.get("mouth.corner.L")
    pb_cr = arm.pose.bones.get("mouth.corner.R")
    pb_jaw = arm.pose.bones.get("jaw")
    lr_swap = 0
    if pb_cl and pb_cr:
        cl = arm.matrix_world @ pb_cl.matrix.to_translation()
        cr = arm.matrix_world @ pb_cr.matrix.to_translation()
        lr_swap = 1 if float((inv @ cl).x) >= float((inv @ cr).x) else 0

    # jaw axis drift (edit bone rest)
    jaw = arm.data.bones.get("jaw")
    jaw_axis_drift = 0.0
    if jaw is not None and jaw_rest_head is not None:
        jaw_axis_drift = max(
            (Vector(jaw.head_local) - Vector(jaw_rest_head)).length,
            (Vector(jaw.tail_local) - Vector(jaw_rest_tail)).length,
        )

    # signature: measured pose channels + mouth opening proxy
    sig = [
        round(float(pb_jaw.location.y) / mu if pb_jaw else 0.0, 5),
        round(float(pb_cr.location.x) / mu if pb_cr else 0.0, 5),
        round(float(pb_u.location.z) / mu if pb_u else 0.0, 5),
        round(float(pb_l.location.z) / mu if pb_l else 0.0, 5),
        round(float(u_loc.z - l_loc.z) / mu, 5),
        round(max(moved) if moved else 0.0, 5),
    ]

    return {
        "nonMouthLeak": non_mouth_leak,
        "lipOrderInversion": lip_order_inversion,
        "lipSelfIntersection": lip_intersection,
        "faceSurfaceTearing": face_tear,
        "lrSwap": lr_swap,
        "jawAxisDrift": jaw_axis_drift,
        "maxMoveMU": max(moved) if moved else 0.0,
        "signature": sig,
        "upperLowerDeltaZ_MU": float(u_loc.z - l_loc.z) / mu,
    }


def create_control_objects(tongue_mode: str) -> Dict:
    import bpy

    # Empty control + evidence collection markers
    for name in GATE3_PARAMETERS["objects"].values():
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)

    ctrl = bpy.data.objects.new(GATE3_PARAMETERS["objects"]["control"], None)
    ctrl.empty_display_type = "CUBE"
    ctrl.empty_display_size = 0.05
    bpy.context.collection.objects.link(ctrl)
    ctrl["visemeState"] = "REST"
    ctrl["tongueMode"] = tongue_mode
    ctrl["audioInput"] = "INACTIVE"
    ctrl["automaticLipSync"] = "HOLD"

    basis = bpy.data.objects.new(GATE3_PARAMETERS["objects"]["basis"], None)
    basis.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(basis)

    evidence = bpy.data.objects.new(GATE3_PARAMETERS["objects"]["evidence"], None)
    evidence.empty_display_type = "SPHERE"
    evidence.empty_display_size = 0.02
    bpy.context.collection.objects.link(evidence)

    return {
        "control": ctrl.name,
        "basis": basis.name,
        "evidence": evidence.name,
        "tongueMode": tongue_mode,
    }
