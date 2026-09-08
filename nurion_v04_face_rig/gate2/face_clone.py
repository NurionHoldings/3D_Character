"""Clone face candidate mesh into isolated collection (source untouched)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .parameters import GATE2_PARAMETERS


def _ensure_collection(name: str):
    import bpy

    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def snapshot_mesh_vertices(mesh_obj) -> List[Tuple[float, float, float]]:
    return [(float(v.co.x), float(v.co.y), float(v.co.z)) for v in mesh_obj.data.vertices]


def snapshots_equal(a, b, eps: float = 1e-9) -> bool:
    if len(a) != len(b):
        return False
    for p, q in zip(a, b):
        if abs(p[0] - q[0]) > eps or abs(p[1] - q[1]) > eps or abs(p[2] - q[2]) > eps:
            return False
    return True


def clear_prior_nurion_gate2():
    import bpy

    names = set(GATE2_PARAMETERS["collections"].values())
    # remove objects in those collections / NURION_Face* names
    for obj in list(bpy.data.objects):
        if obj.name.startswith("NURION_Face") or obj.name.startswith("NURION_NeutralFace") or obj.name.startswith(
            "NURION_FG_"
        ):
            bpy.data.objects.remove(obj, do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.name.startswith("NURION_NeutralFace"):
            bpy.data.armatures.remove(arm, do_unlink=True)
    for col_name in names:
        col = bpy.data.collections.get(col_name)
        if col is not None:
            for obj in list(col.objects):
                col.objects.unlink(obj)
            # keep empty collections for reuse


def create_face_candidate(source_mesh) -> Dict:
    """Duplicate source mesh into NURION_FaceCandidate; strip source armature binding."""
    import bpy

    clear_prior_nurion_gate2()
    cand_col = _ensure_collection(GATE2_PARAMETERS["collections"]["candidate"])
    guide_col = _ensure_collection(GATE2_PARAMETERS["collections"]["guides"])
    rig_col = _ensure_collection(GATE2_PARAMETERS["collections"]["rig"])

    src_snap = snapshot_mesh_vertices(source_mesh)

    # Duplicate data + object
    new_mesh = source_mesh.data.copy()
    new_mesh.name = "NURION_FaceCandidate_Mesh"
    cand = bpy.data.objects.new("NURION_FaceCandidate", new_mesh)
    cand_col.objects.link(cand)
    cand.matrix_world = source_mesh.matrix_world.copy()

    # Remove modifiers / clear vertex groups on candidate only
    for mod in list(cand.modifiers):
        cand.modifiers.remove(mod)
    cand.vertex_groups.clear()
    if cand.parent is not None:
        cand.parent = None
        cand.matrix_world = source_mesh.matrix_world.copy()

    cand_snap = snapshot_mesh_vertices(cand)
    identical = snapshots_equal(src_snap, cand_snap, eps=1e-9)

    return {
        "sourceName": source_mesh.name,
        "candidateName": cand.name,
        "sourceVertexCount": len(src_snap),
        "candidateVertexCount": len(cand_snap),
        "neutralIdenticalAtCreate": identical,
        "sourceSnapshot": src_snap,
        "collections": {
            "candidate": cand_col.name,
            "guides": guide_col.name,
            "rig": rig_col.name,
        },
        "candidateObject": cand,
    }
