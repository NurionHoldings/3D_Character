#!/usr/bin/env python3
"""FAST-06R1.5 Blink-only technical proof; Human Visual remains HOLD."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
EVIDENCE = WORK / "evidence"
SERVER = ROOT / "tools/run_fast_06_presentation_server.py"
FAST02 = ROOT / "tools/fast_02_semantic_partition_audit.py"
NEUTRAL = WORK / "identity_locked/FAST-03B_identity_neutral.glb"
OUTPUT = WORK / "output/FAST-03D_presentation_rig.glb"
BASE_MORPH = WORK / "semantic/FAST-03D_morph_deltas_R1.4.json"
MORPH = WORK / "semantic/FAST-03D_morph_deltas.json"
FORENSIC = EVIDENCE / "FAST-06R1.5_eyelid_forensic.json"
PORT = int(os.environ.get("FAST06_PORT", "8779"))
BASE = f"http://127.0.0.1:{PORT}"


def load_fast02():
    spec = importlib.util.spec_from_file_location("fast02", FAST02)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_server():
    for _ in range(60):
        try:
            return json.load(urllib.request.urlopen(f"{BASE}/api/config", timeout=2))
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("presentation server did not start")


def neutral_parity():
    f2 = load_fast02()
    g0, b0 = f2.load_glb(NEUTRAL)
    g1, b1 = f2.load_glb(OUTPUT)
    p0 = f2.read_accessor(g0, b0, g0["meshes"][0]["primitives"][0]["attributes"]["POSITION"])
    p1 = f2.read_accessor(g1, b1, g1["meshes"][0]["primitives"][0]["attributes"]["POSITION"])
    return {
        "globalMaxDisplacement": float(np.max(np.linalg.norm(p1 - p0, axis=1))),
        "vertexCountMatch": len(p0) == len(p1),
        "skinJointCountMatch": len(g0["skins"][0]["joints"]) == len(g1["skins"][0]["joints"]),
        "materialJsonExact": g0.get("materials", []) == g1.get("materials", []),
        "animationJsonExact": g0.get("animations", []) == g1.get("animations", []),
    }


def main():
    from playwright.sync_api import sync_playwright

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = EVIDENCE / "FAST-06R1.5_blink_debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=str(ROOT),
        env={**os.environ, "FAST06_PORT": str(PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    shots = {}
    stages = {}
    try:
        config = wait_server()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"{BASE}/?debug=blink", wait_until="load", timeout=60000)
            page.wait_for_selector("#boot-msg", state="hidden", timeout=60000)

            poses = [
                ("NeutralStart", 0.0, "Neutral"),
                ("Closing", 0.5, "BlinkClosing"),
                ("Closed", 1.0, "BlinkClosed"),
                ("Reopening", 0.5, "BlinkReopening"),
                ("NeutralReturn", 0.0, "Neutral"),
            ]
            page.wait_for_function("() => window.__morphProbe != null", timeout=12000)
            page.wait_for_timeout(500)
            for label, weight, debug_label in poses:
                stages[label] = page.evaluate(
                    "([weight, label]) => window.__setBlinkDebugPose(weight, label)",
                    [weight, debug_label],
                )
                page.wait_for_timeout(100)
                path = out_dir / f"FAST-06R1.5_{label.lower()}.png"
                page.screenshot(path=str(path), full_page=True)
                shots[label] = str(path)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    old = json.loads(BASE_MORPH.read_text(encoding="utf-8"))
    new = json.loads(MORPH.read_text(encoding="utf-8"))
    forensic = json.loads(FORENSIC.read_text(encoding="utf-8"))
    non_blink = [name for name in old["shapeKeys"] if not name.startswith("PRES_Blink_")]
    non_blink_exact = all(old["shapeKeys"][name] == new["shapeKeys"][name] for name in non_blink)

    synchronized = True
    for stage in stages.values():
        values = {a["name"]: a["rendererInfluence"] for a in stage["presActuators"]}
        synchronized &= values["PRES_Blink_L"] == values["PRES_Blink_R"]

    parity = neutral_parity()
    technical_gate = {
        "r15RevisionLoaded": new.get("revision") == "FAST-06R1.5_ANATOMICAL_EYELID_SURFACE_FOLLOWING",
        "nonBlinkMorphsExactR14": non_blink_exact,
        "upperLidOnly": new["blinkContract"]["upperLidOnly"] is True,
        "lowerLidMovementZero": new["blinkContract"]["lowerLidMovement"] == 0.0,
        "canthusAnchored": new["blinkContract"]["canthusAnchored"] is True,
        "surfaceFollowing": new["blinkContract"]["eyeballSurfaceFollowing"] is True,
        "leftRightWeightsSynchronized": synchronized,
        "closeDuration160ms": stages["Closing"]["closeDurationMs"] == 160,
        "reopenDuration240ms": stages["Reopening"]["reopenDurationMs"] == 240,
        "neutralBaseExact": parity["globalMaxDisplacement"] == 0.0,
        "lockedStructureUnchanged": all(
            parity[k]
            for k in (
                "vertexCountMatch",
                "skinJointCountMatch",
                "materialJsonExact",
                "animationJsonExact",
            )
        ),
    }
    receipt = {
        "receiptId": f"FAST-06R1.5_blink_only_{ts}",
        "timestampUtc": ts,
        "stage": "FAST-06R1.5",
        "verdict": (
            "TECHNICAL_PROOF_READY__HUMAN_VISUAL_HOLD"
            if all(technical_gate.values())
            else "TECHNICAL_HOLD"
        ),
        "scope": "Blink L/R morph deltas + Blink-only presentation interpolation",
        "talkingStatus": "HOLD",
        "agentVisualPrecheck": {
            "verdict": "HOLD",
            "observation": "At closed weight 1.0 one eye remains visibly open while the opposite eyelid compresses.",
            "classification": "CURRENT_HEAD_TOPOLOGY_INSUFFICIENT_FOR_SYMMETRIC_UPPER_LID_ONLY_BLINK",
        },
        "technicalGate": technical_gate,
        "neutralParity": parity,
        "blinkTopology": {
            name: {
                "upperLidMovedVertexCount": row["upperLidMovedVertexCount"],
                "canthusAnchorVertexCount": len(row["canthusAnchorVertexIds"]),
                "lowerLidExcludedVertexCount": len(row["lowerLidExcludedVertexIds"]),
            }
            for name, row in forensic["eyes"].items()
        },
        "timing": {
            "closeMs": 160,
            "closedHoldMs": 80,
            "reopenMs": 240,
            "leftRightSource": "single synchronized weight",
        },
        "artifacts": {
            "outputGlb": str(OUTPUT),
            "outputGlbSha256": sha256(OUTPUT),
            "morphJson": str(MORPH),
            "morphJsonSha256": sha256(MORPH),
            "forensic": str(FORENSIC),
            "screenshots": shots,
            "debugUrl": "http://127.0.0.1:8766/?debug=blink",
        },
        "decisionGate": {
            "humanVisualPass": "Proceed to Talking",
            "humanVisualHold": "Stop current-head facialization and enter Head Replacement Lane",
        },
    }
    path = EVIDENCE / "FAST-06R1.5_blink_only_receipt.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"receipt": str(path), "technicalGate": technical_gate}, ensure_ascii=True))
    return 0 if all(technical_gate.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
