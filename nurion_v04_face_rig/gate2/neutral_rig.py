"""Build neutral face rig candidate armature + limited face weights on clone."""

from __future__ import annotations

from typing import Dict, List, Tuple

from mathutils import Vector

from .parameters import GATE2_PARAMETERS


def _ensure_collection(name: str):
    import bpy

    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def build_neutral_rig(landmarks: Dict[str, Vector], axes, cand_mesh=None) -> Dict:
    import bpy
    from mathutils import Matrix

    col = _ensure_collection(GATE2_PARAMETERS["collections"]["rig"])
    arm_data = bpy.data.armatures.new("NURION_NeutralFaceRigCandidate_Data")
    arm_obj = bpy.data.objects.new("NURION_NeutralFaceRigCandidate", arm_data)
    col.objects.link(arm_obj)
    # Match candidate mesh transform so armature modifier deforms in-place
    if cand_mesh is not None:
        arm_obj.matrix_world = cand_mesh.matrix_world.copy()
    else:
        arm_obj.matrix_world = Matrix.Identity(4)

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    inv = arm_obj.matrix_world.inverted()

    def add_bone(name: str, head: Vector, tip_offset: Vector, parent=None):
        b = eb.new(name)
        b.head = inv @ head
        tail = head + tip_offset
        if (tail - head).length < 1e-6:
            tail = head + axes.up * (max(axes.head_height, 1e-4) * 0.03)
        b.tail = inv @ tail
        if parent is not None:
            b.parent = eb[parent]
        return b

    hh = max(axes.head_height, 1e-4)
    add_bone("face.root", landmarks["head.origin"], axes.up * (hh * 0.05))
    jaw_delta = landmarks["jaw.center"] - landmarks["jaw.hinge"]
    if jaw_delta.length < 1e-6:
        jaw_delta = -axes.up * (hh * 0.08)
    add_bone("jaw", landmarks["jaw.hinge"], jaw_delta.normalized() * (hh * 0.08), "face.root")
    add_bone("lip.upper.center", landmarks["lip.upper.center"], axes.up * (hh * 0.03), "face.root")
    add_bone("lip.lower.center", landmarks["lip.lower.center"], -axes.up * (hh * 0.03), "face.root")
    add_bone("mouth.corner.L", landmarks["mouth.corner.L"], -axes.right * (hh * 0.03), "face.root")
    add_bone("mouth.corner.R", landmarks["mouth.corner.R"], axes.right * (hh * 0.03), "face.root")
    add_bone("cheek.L", landmarks["cheek.L"], -axes.right * (hh * 0.03), "face.root")
    add_bone("cheek.R", landmarks["cheek.R"], axes.right * (hh * 0.03), "face.root")
    for side in ("L", "R"):
        for part in ("inner", "mid", "outer"):
            key = f"brow.{part}.{side}"
            add_bone(key, landmarks[key], axes.up * (hh * 0.025), "face.root")

    bpy.ops.object.mode_set(mode="OBJECT")
    for b in arm_data.bones:
        b.use_deform = b.name != "face.root"
    bone_names = [b.name for b in arm_data.bones]
    return {"armature": arm_obj.name, "bones": bone_names, "armatureObject": arm_obj}


def assign_limited_weights(cand_mesh, arm_obj, landmarks: Dict[str, Vector], axes) -> Dict:
    """Face-only soft weights; teeth/inward and non-face → 0."""
    import bpy
    from mathutils import Vector

    wp = GATE2_PARAMETERS["weight"]
    hh = max(axes.head_height, 1e-4)
    inv = axes.matrix_world_inv

    # Ensure armature modifier
    for mod in list(cand_mesh.modifiers):
        cand_mesh.modifiers.remove(mod)
    cand_mesh.vertex_groups.clear()
    mod = cand_mesh.modifiers.new(name="NURION_FaceCandidate_Armature", type="ARMATURE")
    mod.object = arm_obj
    # Modifier only — no object parenting (avoids double transform)

    # Create groups for deform bones (skip face.root)
    deform_bones = [n for n in GATE2_PARAMETERS["bones"]]
    groups = {n: cand_mesh.vertex_groups.new(name=n) for n in deform_bones}

    radii = {
        "jaw": wp["jawRadiusEU"] * hh,
        "lip.upper.center": wp["lipRadiusEU"] * hh,
        "lip.lower.center": wp["lipRadiusEU"] * hh,
        "mouth.corner.L": wp["cornerRadiusEU"] * hh,
        "mouth.corner.R": wp["cornerRadiusEU"] * hh,
        "cheek.L": wp["cheekRadiusEU"] * hh,
        "cheek.R": wp["cheekRadiusEU"] * hh,
    }
    for n in deform_bones:
        if n.startswith("brow."):
            radii[n] = wp["browRadiusEU"] * hh

    bone_pos = {
        "jaw": landmarks["jaw.center"],
        "lip.upper.center": landmarks["lip.upper.center"],
        "lip.lower.center": landmarks["lip.lower.center"],
        "mouth.corner.L": landmarks["mouth.corner.L"],
        "mouth.corner.R": landmarks["mouth.corner.R"],
        "cheek.L": landmarks["cheek.L"],
        "cheek.R": landmarks["cheek.R"],
    }
    for n in deform_bones:
        if n.startswith("brow."):
            bone_pos[n] = landmarks[n]

    mw = cand_mesh.matrix_world
    non_face_leak = 0
    teeth_leak = 0
    weighted = 0

    # Face region gate in head-local
    for v in cand_mesh.data.vertices:
        wpos = mw @ v.co
        loc = inv @ wpos
        # non-face: outside head frontal band
        is_face = (
            abs(loc.x) < 0.42 * hh
            and -0.15 * hh < loc.y < 0.55 * hh
            and -0.2 * hh < loc.z < 0.75 * hh
        )
        # teeth/inward cavity
        is_teeth = is_face and loc.y < wp["teethInwardYEU"] * hh and -0.05 * hh < loc.z < 0.28 * hh

        influences: List[Tuple[str, float]] = []
        if is_face and not is_teeth:
            for bn, center in bone_pos.items():
                d = (wpos - center).length
                r = radii[bn]
                if d >= r:
                    continue
                w = (1.0 - d / r) ** 2
                if w > 1e-4:
                    influences.append((bn, w))
            influences.sort(key=lambda t: -t[1])
            influences = influences[: int(wp["maxInfluenceBones"])]
            s = sum(w for _, w in influences) or 1.0
            for bn, w in influences:
                groups[bn].add([v.index], w / s, "REPLACE")
            if influences:
                weighted += 1
        else:
            # explicitly ensure zero — no groups added
            if is_teeth:
                # if somehow later assigned, count as leak when checking
                pass

    # Leak audit
    for v in cand_mesh.data.vertices:
        wpos = mw @ v.co
        loc = inv @ wpos
        is_face = (
            abs(loc.x) < 0.42 * hh
            and -0.15 * hh < loc.y < 0.55 * hh
            and -0.2 * hh < loc.z < 0.75 * hh
        )
        is_teeth = is_face and loc.y < wp["teethInwardYEU"] * hh and -0.05 * hh < loc.z < 0.28 * hh
        total = 0.0
        for g in cand_mesh.vertex_groups:
            try:
                total += g.weight(v.index)
            except RuntimeError:
                pass
        if total > GATE2_PARAMETERS["tolerances"]["nonFaceWeightLeakMax"] + 1e-8:
            if not is_face:
                non_face_leak += 1
            if is_teeth:
                teeth_leak += 1

    bpy.context.view_layer.update()
    return {
        "weightedVertexCount": weighted,
        "nonFaceWeightLeak": non_face_leak,
        "teethWeightLeak": teeth_leak,
        "deformBones": deform_bones,
    }
