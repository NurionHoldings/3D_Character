bl_info = {
    "name": "NURION Character Landmarker",
    "author": "NURION",
    "version": (0, 3, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > NURION",
    "description": (
        "NURION Character Landmarker v0.3.0-alpha.2 — "
        "Meshy Eye Proxy + Procedural Eyeball (NURION_EYE_PROXY_V1). "
        "Alpha1 (native eyeball domain) remains frozen separately. "
        "v0.1/v0.2 SEALED artifacts are immutable read-only baselines."
    ),
    "category": "Rigging",
    "doc_url": "",
    "tracker_url": "",
}


def _reload_modules():
    """Support disable/reinstall and Blender Reload Scripts without stale code."""
    import importlib
    import sys

    prefix = __name__ + "."
    names = [name for name in list(sys.modules) if name == __name__ or name.startswith(prefix)]
    for name in sorted(names, key=lambda n: n.count("."), reverse=True):
        module = sys.modules.get(name)
        if module is None or name == __name__:
            continue
        try:
            importlib.reload(module)
        except Exception:
            pass


def register():
    from . import diagnostics
    from . import operators
    from . import ui as ui_module

    if any(k.startswith(__name__ + ".") for k in list(__import__("sys").modules)):
        _reload_modules()
        from . import diagnostics
        from . import operators
        from . import ui as ui_module

    try:
        operators.register()
        ui_module.register()
    except Exception as exc:
        try:
            diagnostics.report_exception("addon_register", exc)
        except Exception:
            pass
        raise


def unregister():
    from . import diagnostics
    from . import operators
    from . import ui as ui_module

    try:
        ui_module.unregister()
    except Exception as exc:
        try:
            diagnostics.report_exception("addon_unregister_ui", exc)
        except Exception:
            pass
    try:
        operators.unregister()
    except Exception as exc:
        try:
            diagnostics.report_exception("addon_unregister_ops", exc)
        except Exception:
            pass


if __name__ == "__main__":
    register()
