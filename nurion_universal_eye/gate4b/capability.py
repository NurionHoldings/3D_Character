"""Classify blink capability: NATIVE_LID / PROCEDURAL_LID_PROXY / BLINK_INELIGIBLE."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .parameters import GATE4B_PARAMETERS


def _name_hits(name: str, hints: List[str]) -> bool:
    n = name.lower().replace(" ", "").replace("-", "").replace(".", "")
    return any(h.replace("_", "") in n for h in hints)


def detect_native_lid() -> Dict:
    import bpy

    hints_b = GATE4B_PARAMETERS["capability"]["nativeBoneNameHints"]
    hints_s = GATE4B_PARAMETERS["capability"]["nativeShapeKeyHints"]
    bones: List[str] = []
    shapes: List[str] = []
    for arm in bpy.data.objects:
        if arm.type != "ARMATURE" or arm.data is None:
            continue
        for b in arm.data.bones:
            if _name_hits(b.name, hints_b):
                bones.append(f"{arm.name}:{b.name}")
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.data is None or obj.data.shape_keys is None:
            continue
        for kb in obj.data.shape_keys.key_blocks:
            if kb.name == "Basis":
                continue
            if _name_hits(kb.name, hints_s):
                shapes.append(f"{obj.name}:{kb.name}")
    return {
        "nativeBones": bones,
        "nativeShapeKeys": shapes,
        "hasNative": bool(bones or shapes),
    }


def classify_blink_capability(planes: Dict) -> Tuple[str, Dict]:
    """Return (mode, evidence). Prefer procedural when no trustworthy native lid."""
    native = detect_native_lid()
    evidence = {"native": native, "aperture": {}}
    ok_sides = []
    for side, plane in planes.items():
        inner = plane.aperture_inner
        outer = plane.aperture_outer
        span = (outer - inner).length
        eu = float(plane.eye_unit)
        ok = span > eu * 0.25 and float(plane.height) > eu * 0.20 and float(plane.width) > eu * 0.35
        evidence["aperture"][side] = {
            "span": round(float(span), 6),
            "width": round(float(plane.width), 6),
            "height": round(float(plane.height), 6),
            "eligible": bool(ok),
        }
        if ok:
            ok_sides.append(side)

    if len(ok_sides) < 2:
        return "BLINK_INELIGIBLE", evidence

    prefer_proc = bool(GATE4B_PARAMETERS["capability"]["preferProceduralWhenNoNative"])
    # Tennis/Captain: procedural unless native is explicitly preferred.
    # Future native-lid characters use the same BlinkControl interface on a separate path.
    if native["hasNative"] and not prefer_proc:
        return "NATIVE_LID", evidence
    return "PROCEDURAL_LID_PROXY", evidence
