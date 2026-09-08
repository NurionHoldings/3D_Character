"""Offline smoke test (no Blender) for profile/source logic used in v0.1 practical flow."""

from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _install_mathutils_stub() -> None:
    if "mathutils" in sys.modules:
        return

    class Vector(list):
        def __init__(self, values=(0.0, 0.0, 0.0)):
            super().__init__(float(v) for v in values)

        @property
        def x(self):
            return self[0]

        @property
        def y(self):
            return self[1]

        @property
        def z(self):
            return self[2]

        def copy(self):
            return Vector(self)

        def __add__(self, other):
            return Vector((self[0] + other[0], self[1] + other[1], self[2] + other[2]))

        def __mul__(self, scale):
            return Vector((self[0] * scale, self[1] * scale, self[2] * scale))

        def __rmul__(self, scale):
            return self.__mul__(scale)

    module = types.ModuleType("mathutils")
    module.Vector = Vector
    sys.modules["mathutils"] = module


def main() -> int:
    _install_mathutils_stub()

    from nurion_character_landmarker.core.sources import ESTIMATED, MANUAL, MEASURED, review_required
    from nurion_character_landmarker.profiles.nurion_landmark_profile import (
        load_profile,
        save_profile,
    )
    from tools.pack_addon_zip import pack

    assert review_required(ESTIMATED, 0.9) is True
    assert review_required(MEASURED, 1.0) is False
    assert review_required(MANUAL, 1.0) is False

    example = ROOT / "examples" / "nurion-character-profile.json"
    profile = load_profile(example)
    assert profile.schema == "NURION_CHARACTER_PROFILE"
    assert any(lm["name"] == "elbow.L" for lm in profile.landmarks)
    elbow = next(lm for lm in profile.landmarks if lm["name"] == "elbow.L")
    assert elbow["source"] == "ESTIMATED"
    assert elbow["reviewRequired"] is True
    assert "source" in elbow and "confidence" in elbow

    points = profile.landmark_points()
    assert "elbow.L" in points
    assert points["elbow.L"].source == ESTIMATED

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "nurion-character-profile.json"
        save_profile(profile, out)
        roundtrip = load_profile(out)
        assert roundtrip.character_id == profile.character_id
        assert len(roundtrip.landmarks) == len(profile.landmarks)

    zip_path = pack()
    assert zip_path.exists()

    print("OFFLINE SMOKE OK")
    print(f"example landmarks: {len(profile.landmarks)}")
    print(f"zip: {zip_path}")
    print(json.dumps({"elbow.L": elbow}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
