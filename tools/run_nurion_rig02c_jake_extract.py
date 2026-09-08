#!/usr/bin/env python3
"""Run Blender Jake CC pose extract for RIG-02C fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools/blender_rig02c_jake_pose_extract.py"
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
FIX = EV / "rig02c_fixtures"
JAKE = ROOT / "fast_track/assets/external/hr05_jake/Jake.fbx"


def main() -> int:
    FIX.mkdir(parents=True, exist_ok=True)
    if not JAKE.exists():
        raise SystemExit(f"missing Jake.fbx: {JAKE}")
    out = FIX / "jake_cc_pose_extract.json"
    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(SCRIPT),
        "--",
        "--fbx",
        str(JAKE),
        "--out-json",
        str(out),
        "--clip-id",
        "jake_cc_embedded",
        "--frame-samples",
        "1,10,20,30,40",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        raise SystemExit(
            f"blender failed: {proc.returncode}\nSTDOUT:\n{(proc.stdout or '')[-2500:]}\nSTDERR:\n{(proc.stderr or '')[-2500:]}"
        )
    data = json.loads(out.read_text(encoding="utf-8"))
    summary = {
        "stage": "NURION-RIG-02C_JAKE_POSE_EXTRACT",
        "out": str(out),
        "frames": len(data["frames"]),
        "dominantUp": data["restPoseProbe"]["dominantUpAxis"],
        "actions": data.get("actions"),
        "neckParents": data.get("neckCollapseParents"),
        "stdoutTail": (proc.stdout or "")[-800:],
    }
    (EV / "NURION-RIG-02C_jake_pose_extract_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
