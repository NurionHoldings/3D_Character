"""Blender-side runtime isolation helpers for Gate 6 workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


RUNTIME_COLLECTION = "NURION_UnifiedRuntime"
RUNTIME_ACTION_PREFIX = "NURION_UnifiedRuntime_"


def ensure_runtime_collection():
    import bpy

    col = bpy.data.collections.get(RUNTIME_COLLECTION)
    if col is None:
        col = bpy.data.collections.new(RUNTIME_COLLECTION)
        bpy.context.scene.collection.children.link(col)
    return col


def clear_runtime_layer():
    import bpy

    col = bpy.data.collections.get(RUNTIME_COLLECTION)
    if col is not None:
        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    for act in list(bpy.data.actions):
        if act.name.startswith(RUNTIME_ACTION_PREFIX):
            try:
                bpy.data.actions.remove(act)
            except Exception:
                pass


def build_runtime_from_active(*, preset_action_names: List[str]) -> Dict:
    """Clone active armature/mesh into runtime collection; leave sources untouched."""
    import bpy

    clear_runtime_layer()
    col = ensure_runtime_collection()
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and not o.name.startswith("NURION_")]
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("NURION_")]
    if not arms:
        return {"ok": False, "reason": "NO_SOURCE_ARMATURE"}
    src_arm = arms[0]
    src_mesh = meshes[0] if meshes else None

    arm_data = src_arm.data.copy()
    arm_data.name = "NURION_UnifiedRuntime_Arm_Data"
    clone_arm = bpy.data.objects.new("NURION_UnifiedRuntime_Armature", arm_data)
    clone_arm.matrix_world = src_arm.matrix_world.copy()
    col.objects.link(clone_arm)

    clone_mesh = None
    if src_mesh is not None:
        mesh_data = src_mesh.data.copy()
        mesh_data.name = "NURION_UnifiedRuntime_Mesh"
        clone_mesh = bpy.data.objects.new("NURION_UnifiedRuntime_Mesh", mesh_data)
        clone_mesh.matrix_world = src_mesh.matrix_world.copy()
        col.objects.link(clone_mesh)
        mw = clone_mesh.matrix_world.copy()
        clone_mesh.parent = clone_arm
        clone_mesh.matrix_world = mw
        for mod in list(clone_mesh.modifiers):
            clone_mesh.modifiers.remove(mod)
        mod = clone_mesh.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = clone_arm

    # Ensure named runtime actions exist (copies of current action if needed)
    created = []
    src_action = src_arm.animation_data.action if src_arm.animation_data else None
    for name in preset_action_names:
        if bpy.data.actions.get(name) is None and src_action is not None:
            dup = src_action.copy()
            dup.name = name
            created.append(name)
    bpy.context.view_layer.update()
    return {
        "ok": True,
        "armature": clone_arm.name,
        "mesh": None if clone_mesh is None else clone_mesh.name,
        "collection": RUNTIME_COLLECTION,
        "actionsCreated": created,
        "sourceArmature": src_arm.name,
    }


def _ensure_eye_empties(arm, head_bone: str) -> Dict:
    """Create Eye.L/R empties under Head without clearing the runtime armature."""
    import bpy

    from nurion_v06_unified_runtime.gate4.bind import _parent_to_head

    col = ensure_runtime_collection()
    out = {}
    for key, name in (("eyeL", "NURION_UnifiedRuntime_Eye.L"), ("eyeR", "NURION_UnifiedRuntime_Eye.R")):
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = "PLAIN_AXES"
        col.objects.link(obj)
        out[key] = obj
    bpy.context.view_layer.update()
    head_pb = arm.pose.bones.get(head_bone)
    if head_pb is not None:
        head_w = (arm.matrix_world @ head_pb.matrix).to_translation()
        out["eyeL"].location = (head_w.x + 0.02, head_w.y + 0.05, head_w.z + 0.05)
        out["eyeR"].location = (head_w.x - 0.02, head_w.y + 0.05, head_w.z + 0.05)
        bpy.context.view_layer.update()
    _parent_to_head(out["eyeL"], arm, head_bone)
    _parent_to_head(out["eyeR"], arm, head_bone)
    return out


def apply_runtime_preset(preset_action_name: str, fps: int) -> Dict:
    import bpy

    arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
    act = bpy.data.actions.get(preset_action_name)
    if arm is None:
        return {"ok": False, "reason": "RUNTIME_ARMATURE_MISSING"}
    if act is None:
        return {"ok": False, "reason": f"RUNTIME_ACTION_MISSING:{preset_action_name}"}
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    slots = list(getattr(act, "slots", []) or [])
    if slots:
        try:
            arm.animation_data.action_slot = slots[0]
        except Exception:
            pass
    bpy.context.scene.render.fps = int(fps)
    bpy.context.view_layer.update()
    from nurion_v06_unified_runtime.gate3.mapping import build_role_mapping

    # Re-fetch arm by name after updates
    arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
    if arm is None:
        return {"ok": False, "reason": "RUNTIME_ARMATURE_MISSING"}
    mapping = build_role_mapping(arm)
    head = mapping.get("eyeAttachBone") or mapping["roles"].get("HEAD") or "Head"
    _ensure_eye_empties(arm, head)
    return {"ok": True, "activeAction": act.name, "fps": int(fps), "head": head}


def validate_runtime(fps: int) -> Dict:
    import bpy

    from nurion_v06_unified_runtime.gate4.bind import _action_range, _eye_head_double, _fps_meaning

    arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
    eye = bpy.data.objects.get("NURION_UnifiedRuntime_Eye.L")
    if arm is None:
        return {"ok": False, "reason": "RUNTIME_ARMATURE_MISSING"}
    act = arm.animation_data.action if arm.animation_data else None
    if act is None:
        return {"ok": False, "reason": "NO_ACTIVE_ACTION"}
    if not act.name.startswith(RUNTIME_ACTION_PREFIX):
        return {"ok": False, "reason": "ACTIVE_ACTION_NOT_RUNTIME_ISOLATED"}
    fs, fe = _action_range(act)
    head = "Head"
    eye_m = _eye_head_double(arm, eye, head, fs, fe) if eye else {"ok": False, "maxResidualM": 999.0}
    bpy.context.scene.render.fps = int(fps)
    fps_m = _fps_meaning(arm, head, fs, fe)
    # Source objects must still exist and not be renamed away
    sources = [o for o in bpy.data.objects if o.type == "ARMATURE" and not o.name.startswith("NURION_")]
    ok = bool(eye_m.get("ok")) and bool(fps_m.get("ok")) and len(sources) >= 1
    return {
        "ok": ok,
        "eyeHeadDoubleOk": bool(eye_m.get("ok")),
        "eyeHeadDoubleM": eye_m.get("maxResidualM"),
        "fpsMeaningOk": bool(fps_m.get("ok")),
        "activeAction": act.name,
        "sourceArmatureCount": len(sources),
        "runtimeCollectionPresent": bpy.data.collections.get(RUNTIME_COLLECTION) is not None,
    }


def export_runtime(path: Path, fmt: str = "FBX") -> Dict:
    import bpy

    from nurion_v06_unified_runtime.gate4.bind import _action_range

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
    mesh = bpy.data.objects.get("NURION_UnifiedRuntime_Mesh")
    if arm is None:
        return {"ok": False, "reason": "RUNTIME_ARMATURE_MISSING"}
    act = arm.animation_data.action if arm.animation_data else None
    if act is not None:
        fs, fe = _action_range(act)
        bpy.context.scene.frame_start = int(fs)
        bpy.context.scene.frame_end = int(fe)
    # Deselect all, select runtime only
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    if mesh is not None:
        mesh.select_set(True)
    for eye_name in ("NURION_UnifiedRuntime_Eye.L", "NURION_UnifiedRuntime_Eye.R"):
        eye = bpy.data.objects.get(eye_name)
        if eye is not None:
            eye.select_set(True)
    bpy.context.view_layer.objects.active = arm
    fmt = fmt.upper()
    if fmt == "GLB":
        bpy.ops.export_scene.gltf(
            filepath=str(path),
            use_selection=True,
            export_format="GLB",
            export_animations=True,
            export_frame_range=True,
            export_animation_mode="ACTIONS",
            export_anim_single_armature=True,
            export_optimize_animation_size=False,
        )
    else:
        bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, add_leaf_bones=False)
    return {"ok": path.is_file(), "path": str(path).replace("\\", "/"), "format": fmt}
