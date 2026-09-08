#!/usr/bin/env python3
"""Run Blender MJN pose extract for RIG-02B fixtures (Idle + Formal Bow)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools/blender_rig02b_mjn_pose_extract.py"
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
FIX = EV / "rig02b_fixtures"

IDLE = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
BOW = ROOT / (
    "dist/v0.5/gate1/_extract/ai-aba.bow/Meshy_AI_Silver_Starlight_Sent_biped/"
    "Meshy_AI_Silver_Starlight_Sent_biped_Animation_Formal_Bow_withSkin.fbx"
)


def run_one(asset: Path, clip_id: str, out_name: str, frames: str) -> dict:
    out = FIX / out_name
    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(SCRIPT),
        "--",
        "--asset",
        str(asset),
        "--out-json",
        str(out),
        "--clip-id",
        clip_id,
        "--frame-samples",
        frames,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        raise SystemExit(
            f"blender failed {clip_id}: {proc.returncode}\nSTDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
        )
    data = json.loads(out.read_text(encoding="utf-8"))
    return {
        "clipId": clip_id,
        "out": str(out),
        "frames": len(data["frames"]),
        "dominantUp": data["restPoseProbe"]["dominantUpAxis"],
        "stdoutTail": (proc.stdout or "")[-500:],
    }


def main() -> int:
    FIX.mkdir(parents=True, exist_ok=True)
    if not IDLE.exists():
        raise SystemExit(f"missing Idle: {IDLE}")
    if not BOW.exists():
        raise SystemExit(f"missing Bow: {BOW}")
    results = [
        run_one(IDLE, "mjn_idle_15", "mjn_idle_15_pose_extract.json", "1,8,15,30,45"),
        run_one(BOW, "mjn_formal_bow", "mjn_formal_bow_pose_extract.json", "1,10,20,30,40"),
    ]
    summary = {
        "stage": "NURION-RIG-02B_MJN_POSE_EXTRACT",
        "results": results,
    }
    (EV / "NURION-RIG-02B_mjn_pose_extract_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
