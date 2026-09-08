#!/usr/bin/env python3
"""Canonical bone constants — BODY Core v1 only (no donor names)."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
SPEC = ROOT / "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json"

TRANSLATION_OWNERS = frozenset({"NURION_root", "NURION_pelvis"})


def load_core_bones(spec_path: Path = SPEC) -> list[str]:
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    bones = list(data["tiers"]["BODY_CORE_V1"]["bones"])
    if len(bones) != 23:
        raise ValueError(f"BODY_CORE_V1 must be 23 bones, got {len(bones)}")
    return bones


def load_core_hierarchy(spec_path: Path = SPEC) -> dict[str, list[str]]:
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    return dict(data["tiers"]["BODY_CORE_V1"]["hierarchy"])
