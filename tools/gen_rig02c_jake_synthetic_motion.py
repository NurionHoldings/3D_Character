#!/usr/bin/env python3
"""
Build synthetic Jake motion fixtures for RIG-02C numerical proof.

Jake.fbx embedded Take is near-static at cleared rest; synthetic locals exercise
collapse / axis / translation without requiring additional CC motion clips.
"""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
FIX = ROOT / "fast_track/working/meshy_silver_starlight/evidence/rig02c_fixtures"
EXTRACT = FIX / "jake_cc_pose_extract.json"


def q_axis_angle(axis: str, deg: float) -> list[float]:
    half = math.radians(deg) * 0.5
    c, s = math.cos(half), math.sin(half)
    if axis == "x":
        return [c, s, 0.0, 0.0]
    if axis == "y":
        return [c, 0.0, s, 0.0]
    if axis == "z":
        return [c, 0.0, 0.0, s]
    raise ValueError(axis)


def main() -> int:
    base = json.loads(EXTRACT.read_text(encoding="utf-8"))
    rest = base["restLocals"]

    def frame_from(overrides: dict, frame_id: int) -> dict:
        locals_map = copy.deepcopy(rest)
        for bone, bl in overrides.items():
            locals_map[bone] = {
                "rotation_wxyz": bl.get("rotation_wxyz", rest[bone]["rotation_wxyz"]),
                "translation": bl.get("translation", rest[bone]["translation"]),
            }
        return {"frame": frame_id, "locals": locals_map, "kind": "synthetic"}

    frames = [
        frame_from({}, 0),  # pure rest
        frame_from(
            {
                "CC_Base_NeckTwist01": {"rotation_wxyz": q_axis_angle("x", 20.0)},
                "CC_Base_NeckTwist02": {"rotation_wxyz": q_axis_angle("y", 15.0)},
            },
            1,
        ),
        frame_from(
            {
                "CC_Base_BoneRoot": {"translation": [0.0, 0.0, 2.0]},
                "CC_Base_Hip": {"translation": [1.0, 0.5, 0.0], "rotation_wxyz": q_axis_angle("y", 10.0)},
                "CC_Base_L_Upperarm": {"rotation_wxyz": q_axis_angle("x", -25.0)},
                "CC_Base_R_Upperarm": {"rotation_wxyz": q_axis_angle("x", -25.0)},
            },
            2,
        ),
        frame_from(
            {
                "CC_Base_Waist": {"rotation_wxyz": q_axis_angle("z", 8.0)},
                "CC_Base_Spine01": {"rotation_wxyz": q_axis_angle("x", 5.0)},
                "CC_Base_Spine02": {"rotation_wxyz": q_axis_angle("x", 5.0)},
                "CC_Base_NeckTwist01": {"rotation_wxyz": q_axis_angle("z", 12.0)},
                "CC_Base_NeckTwist02": {"rotation_wxyz": q_axis_angle("x", -8.0)},
                "CC_Base_Head": {"rotation_wxyz": q_axis_angle("y", 6.0)},
            },
            3,
        ),
    ]

    out = {
        "clipId": "jake_cc_synthetic_motion_v1",
        "basedOnExtract": str(EXTRACT),
        "product_use": False,
        "purpose": "RIG-02C numerical gates — collapse, translation axis remap, limb motion",
        "restLocals": rest,
        "hierarchyParent": base["hierarchyParent"],
        "frames": frames,
    }
    path = FIX / "jake_cc_synthetic_motion.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(path), "frames": len(frames)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
