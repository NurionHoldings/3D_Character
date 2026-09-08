"""NURION Unified Character Animation Runtime v0.6.

Binds sealed v0.3 / v0.4 / v0.5 baselines as read-only dependencies.
Does not mutate sealed packages or clear inherited limitations.
"""

bl_info = {
    "name": "NURION Unified Character Animation Runtime v0.6",
    "author": "NURION",
    "version": (0, 6, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > NURION",
    "description": "Limited-domain unified runtime (SEALED_WITH_LIMITATIONS). Production NO-GO.",
    "category": "Animation",
}

__version__ = "0.6.0"
TRACK = "Unified Character Animation Runtime"
PRODUCT = "NURION Unified Character Animation Runtime"


def register():
    from . import gate6

    gate6.register()


def unregister():
    from . import gate6

    gate6.unregister()
