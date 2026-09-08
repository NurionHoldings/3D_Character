"""Read-only mesh / topology diagnostics for v0.4 Gate 1."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


def _name_hit(name: str, hints: List[str]) -> bool:
    n = name.lower().replace(" ", "").replace("_", "").replace("-", "")
    for h in hints:
        hh = h.lower().replace(" ", "").replace("_", "").replace("-", "")
        if hh and hh in n:
            return True
    return False


def list_character_meshes() -> List:
    import bpy

    return [
        o
        for o in bpy.data.objects
        if o.type == "MESH" and not o.name.startswith("NURION_")
    ]


def classify_face_body_topology(mesh_obj, axes, head_height: float) -> Dict:
    """Unified vs separate face mesh relative to body."""
    import bpy
    from mathutils import Vector

    meshes = list_character_meshes()
    head_origin = axes.origin
    face_candidates = []
    body_candidates = []
    for m in meshes:
        # centroid
        deps = bpy.context.evaluated_depsgraph_get()
        ev = m.evaluated_get(deps)
        me = ev.to_mesh()
        try:
            mw = ev.matrix_world
            if not me.vertices:
                continue
            acc = Vector((0.0, 0.0, 0.0))
            for v in me.vertices:
                acc += mw @ v.co
            c = acc / len(me.vertices)
        finally:
            ev.to_mesh_clear()
        local = axes.matrix_world_inv @ c
        # head band in head-local up
        if float(local.z) > -0.15 * head_height:
            face_candidates.append(m.name)
        else:
            body_candidates.append(m.name)

    primary = mesh_obj.name
    separate_face = len(face_candidates) >= 2 and any(n != primary for n in face_candidates)
    # If only one mesh covers both → UNIFIED
    if len(meshes) == 1:
        topology = "UNIFIED_FACE_BODY_MESH"
    elif separate_face and primary in face_candidates and any(n not in face_candidates for n in [m.name for m in meshes]):
        topology = "SEPARATE_FACE_MESH"
    else:
        topology = "UNIFIED_OR_MULTI_PART"

    return {
        "faceBodyTopology": topology,
        "meshCount": len(meshes),
        "primaryMesh": primary,
        "faceCandidateMeshes": face_candidates,
        "bodyCandidateMeshes": body_candidates,
        "vertexCount": len(mesh_obj.data.vertices),
        "faceRegion": "RESOLVED" if face_candidates or len(meshes) >= 1 else "FAIL",
    }


def invent_shape_keys(mesh_obj) -> Dict:
    kb = mesh_obj.data.shape_keys
    keys = []
    if kb is not None:
        for kb_block in kb.key_blocks:
            keys.append(
                {
                    "name": kb_block.name,
                    "mute": bool(kb_block.mute),
                    "relativeKey": kb_block.relative_key.name if kb_block.relative_key else None,
                }
            )
    return {
        "present": bool(keys),
        "count": len(keys),
        "keys": keys,
        "status": "INVENTORIED",
    }


def classify_oral_geometry(mesh_obj, axes, head_height: float, hints: Dict) -> Dict:
    """Teeth/tongue as separate meshes or inferred inner cavity verts."""
    import bpy
    from mathutils import Vector

    meshes = list_character_meshes()
    teeth_meshes = [m.name for m in meshes if _name_hit(m.name, hints.get("teeth", []))]
    tongue_meshes = [m.name for m in meshes if _name_hit(m.name, hints.get("tongue", []))]

    # Sample verts near mouth (lower-mid face, forward)
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(deps)
    me = ev.to_mesh()
    mouth_band = 0
    inward = 0
    try:
        mw = ev.matrix_world
        for v in me.vertices:
            w = mw @ v.co
            loc = axes.matrix_world_inv @ w
            # mouth band: mid-lower face forward
            if -0.05 * head_height < float(loc.z) < 0.35 * head_height and float(loc.y) > -0.05 * head_height:
                mouth_band += 1
                if float(loc.y) < 0.12 * head_height:
                    inward += 1
    finally:
        ev.to_mesh_clear()

    if teeth_meshes:
        teeth_class = "SEPARATE_MESH"
    elif inward > 50:
        teeth_class = "POSSIBLE_INNER_GEOMETRY"
    else:
        teeth_class = "ABSENT_OR_UNCLEAR"

    if tongue_meshes:
        tongue_class = "SEPARATE_MESH"
    else:
        tongue_class = "ABSENT_OR_UNCLEAR"

    return {
        "teeth": {"class": teeth_class, "meshes": teeth_meshes},
        "tongue": {"class": tongue_class, "meshes": tongue_meshes},
        "mouthBandVertexCount": mouth_band,
        "inwardMouthVertexCount": inward,
        "status": "CLASSIFIED",
    }


def head_weight_linkage(mesh_obj, bone_names: List[str]) -> Dict:
    """Whether head-related vertex groups exist and bind to armature."""
    import bpy

    vgs = [g.name for g in mesh_obj.vertex_groups]
    head_groups = []
    for g in vgs:
        gl = g.lower()
        if any(h in gl for h in ("head", "neck", "skull")):
            head_groups.append(g)
        for bn in bone_names:
            if bn.lower() == gl or bn.lower() in gl:
                if bn not in head_groups:
                    head_groups.append(g)

    armature_mods = [m for m in mesh_obj.modifiers if m.type == "ARMATURE"]
    arm_ok = False
    arm_name = None
    for mod in armature_mods:
        if getattr(mod, "object", None) is not None:
            arm_ok = True
            arm_name = mod.object.name
            break

    # Sample weight presence on head groups
    weighted = 0
    if head_groups and mesh_obj.vertex_groups:
        idxs = [mesh_obj.vertex_groups.find(n) for n in head_groups]
        idxs = [i for i in idxs if i >= 0]
        for v in mesh_obj.data.vertices[: min(5000, len(mesh_obj.data.vertices))]:
            for gi in idxs:
                try:
                    w = mesh_obj.vertex_groups[gi].weight(v.index)
                except RuntimeError:
                    continue
                if w > 1e-4:
                    weighted += 1
                    break

    linked = arm_ok and (bool(head_groups) or bool(vgs))
    return {
        "armatureModifier": arm_ok,
        "armatureObject": arm_name,
        "vertexGroupCount": len(vgs),
        "headRelatedGroups": head_groups[:40],
        "sampledWeightedVerts": weighted,
        "headParent": "RESOLVED" if linked else "FAIL",
        "status": "RESOLVED" if linked else "UNRESOLVED",
    }
