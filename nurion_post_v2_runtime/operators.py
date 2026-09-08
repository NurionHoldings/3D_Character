"""Optional Blender operators with new IDs; never register into v0.6."""

from __future__ import annotations

try:  # Package/import checks must work without Blender.
    import bpy
except ImportError:  # pragma: no cover
    bpy = None

from .blender_adapter import import_transaction
from .state_machine import PostV2RuntimeEngine

_ENGINE = PostV2RuntimeEngine()

if bpy is not None:  # pragma: no cover - exercised only in Blender CI.
    class NURION_OT_post_v2_precheck_import(bpy.types.Operator):
        bl_idname = "nurion_post_v2.precheck_import"
        bl_label = "Post-V2 Precheck and Import"

        def execute(self, context):
            selected = _ENGINE.precheck_fbx(context.scene.nurion_post_v2_character_path)
            if not selected["ok"]:
                self.report({"ERROR"}, selected["abort"])
                return {"CANCELLED"}
            imported = import_transaction(bpy, selected["precheck"]["path"])
            committed = _ENGINE.record_import(imported)
            if not committed["ok"]:
                self.report({"ERROR"}, committed["abort"])
                return {"CANCELLED"}
            committed = _ENGINE.select_commit()
            if not committed["ok"]:
                self.report({"ERROR"}, committed["abort"])
                return {"CANCELLED"}
            return {"FINISHED"}

    CLASSES = (NURION_OT_post_v2_precheck_import,)

    def register():
        bpy.types.Scene.nurion_post_v2_character_path = bpy.props.StringProperty(subtype="FILE_PATH")
        for cls in CLASSES:
            bpy.utils.register_class(cls)

    def unregister():
        for cls in reversed(CLASSES):
            bpy.utils.unregister_class(cls)
        del bpy.types.Scene.nurion_post_v2_character_path
else:
    CLASSES = ()

    def register():
        raise RuntimeError("BLENDER_UNAVAILABLE")

    def unregister():
        return None
