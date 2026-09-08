"""Mouth Unit and viseme axis application on Gate2 candidate rig."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from mathutils import Matrix, Vector

from .parameters import GATE3_PARAMETERS


def mouth_unit(landmarks: Dict[str, Vector]) -> float:
    a = landmarks["mouth.corner.L"]
    b = landmarks["mouth.corner.R"]
    return max(float((a - b).length), 1e-6)


def reset_pose(arm_obj) -> None:
    for pb in arm_obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    arm_obj.update_tag()


def _pb(arm_obj, name: str):
    return arm_obj.pose.bones.get(name)


def apply_axes(arm_obj, axes_amt: Dict[str, float], mu: float, limits: Dict[str, float]) -> Dict[str, float]:
    """Apply normalized axis amounts (0..1 recipes * limits in MU) to candidate bones."""
    import bpy

    reset_pose(arm_obj)
    applied = {}

    def lim(name: str, v: float) -> float:
        m = float(limits.get(name, 0.0))
        return max(-m, min(m, float(v) * m))

    jaw = lim("jawOpen", axes_amt.get("jawOpen", 0.0))
    wide = lim("lipWide", axes_amt.get("lipWide", 0.0))
    round_ = lim("lipRound", axes_amt.get("lipRound", 0.0))
    close = lim("lipClose", axes_amt.get("lipClose", 0.0))
    up = lim("upperLipRaise", axes_amt.get("upperLipRaise", 0.0))
    low = lim("lowerLipDrop", axes_amt.get("lowerLipDrop", 0.0))
    pull = lim("cornerPull", axes_amt.get("cornerPull", 0.0))
    teeth = lim("teethApproach", axes_amt.get("teethApproach", 0.0))

    # jaw open → translate along bone +Y (candidate local)
    pb = _pb(arm_obj, "jaw")
    if pb and abs(jaw) > 1e-8:
        pb.location = (0.0, jaw * mu, 0.0)
    applied["jawOpen"] = jaw

    # lips vertical
    pb = _pb(arm_obj, "lip.upper.center")
    if pb:
        z = up * mu - close * 0.28 * mu - teeth * 0.15 * mu
        # round advances slightly on Y
        pb.location = (0.0, round_ * 0.35 * mu, z)
    applied["upper"] = up

    pb = _pb(arm_obj, "lip.lower.center")
    if pb:
        z = -low * mu + close * 0.28 * mu
        pb.location = (0.0, round_ * 0.25 * mu, z)
    applied["lower"] = low

    # corners: wide expands, round contracts, pull raises slightly
    for name, sign in (("mouth.corner.L", -1.0), ("mouth.corner.R", 1.0)):
        pb = _pb(arm_obj, name)
        if not pb:
            continue
        x = sign * (wide * mu - round_ * 0.65 * mu)
        z = pull * 0.35 * mu - close * 0.15 * mu
        y = round_ * 0.2 * mu
        pb.location = (x, y, z)
    applied["lipWide"] = wide
    applied["lipRound"] = round_
    applied["lipClose"] = close
    applied["cornerPull"] = pull
    applied["teethApproach"] = teeth

    bpy.context.view_layer.update()
    return applied


def recipe_for(name: str, tongue_available: bool) -> Tuple[str, Dict[str, float]]:
    base = GATE3_PARAMETERS["baseRecipes"]
    vowels = GATE3_PARAMETERS["vowelRecipes"]
    if name == "TONGUE_PROXY" and not tongue_available:
        # limited jaw/lip proxy — do not claim real tongue
        return "TONGUE_LIMITED", dict(base.get("TONGUE_PROXY") or {})
    if name in base:
        return name, dict(base[name])
    if name in vowels:
        return name, dict(vowels[name])
    return name, {}
