#!/usr/bin/env python3
"""Protected SoT hash freeze for RIG-02 (mutation DENY)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"

# Frozen at RIG-02A open — FAIL if RIG-02 mutates these files.
PROTECTED_SOT_SHA256 = {
    "NURION_BODY_CANONICAL_BONE_SPEC_V1.json": "c73b5c540e29fcbf4ef4477c51f869eead9640194cec21110c6d60e55d1f900a",
    "NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json": "19da5a00f4943a144426efaf675d364f64d244773dc60ede7db81be5bb8c6d9a",
    "NURION_FACE_PRODUCT_LOCK_V1.json": "07830e1c34ce79b1d9ff9fc15a8b456ef7e3438d05ae7709d3515c00baebcf06",
    "NURION_BODY_PRODUCT_LOCK_V1.json": "9e0dd3a4170ed48b362d6c1ad1b452567238fda87ec4e56b45a8a87ee5c431ed",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_protected_sot_unchanged() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, expected in PROTECTED_SOT_SHA256.items():
        path = SEM / name
        got = sha256_file(path)
        if got != expected:
            raise AssertionError(f"PROTECTED SoT mutated: {name} expected={expected} got={got}")
        out[name] = got
    return out
