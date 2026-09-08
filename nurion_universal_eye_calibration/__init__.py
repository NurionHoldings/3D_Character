from __future__ import annotations

bl_info = {
    "name": "NURION Universal Eye Calibration",
    "author": "NURION",
    "version": (0, 3, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > NURION",
    "description": "Universal Eye Calibration v0.3.0-rc.1 (Gate1–6). RELEASE CANDIDATE — not SEALED.",
    "category": "Object",
    "docurl": "",
}

import sys
from pathlib import Path

_ADDON_ROOT = Path(__file__).resolve().parent
if str(_ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(_ADDON_ROOT))

from . import operators, panel


def register():
    operators.register()
    panel.register()


def unregister():
    panel.unregister()
    operators.unregister()


if __name__ == "__main__":
    register()
