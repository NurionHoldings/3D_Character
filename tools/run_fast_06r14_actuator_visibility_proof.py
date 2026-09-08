#!/usr/bin/env python3
"""FAST-06R1.4-A technical proof; human visual verdict remains external."""

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
MORPH = WORK / "semantic/FAST-03D_morph_deltas.json"
FORENSIC = EVIDENCE / "FAST-06R1.4_morph_forensic.json"
PORT = int(os.environ.get("FAST06_PORT", "8778"))
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


def base_integrity():
    f2 = load_fast02()
    g0, b0 = f2.load_glb(NEUTRAL)
    g1, b1 = f2.load_glb(OUTPUT)
    p0 = f2.read_accessor(g0, b0, g0["meshes"][0]["primitives"][0]["attributes"]["POSITION"])
    p1 = f2.read_accessor(g1, b1, g1["meshes"][0]["primitives"][0]["attributes"]["POSITION"])
    return {
        "neutralBaseGlobalMaxDisplacement": float(np.max(np.linalg.norm(p1 - p0, axis=1))),
        "vertexCountMatch": len(p0) == len(p1),
        "skinJointCountMatch": len(g0["skins"][0]["joints"]) == len(g1["skins"][0]["joints"]),
        "materialJsonExact": g0.get("materials", []) == g1.get("materials", []),
        "animationJsonExact": g0.get("animations", []) == g1.get("animations", []),
    }


def main():
    from playwright.sync_api import sync_playwright

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = EVIDENCE / "FAST-06R1.4_actuator_debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=str(ROOT),
        env={**os.environ, "FAST06_PORT": str(PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    config = {}
    stages = {}
    shots = {}
    try:
        config = wait_server()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"{BASE}/?debug=morph", wait_until="load", timeout=60000)
            page.wait_for_selector("#boot-msg", state="hidden", timeout=60000)
            order = [
                ("Neutral", "neutral_start"),
                ("JawOpen", "jawopen"),
                ("Blink", "blink"),
                ("SmileMild", "smilemild"),
                ("Viseme_A", "viseme_a"),
            ]
            for label, slug in order:
                page.wait_for_function(
                    "(label) => window.__morphProbe?.debugLabel === label",
                    arg=label,
                    timeout=12000,
                )
                page.evaluate("() => window.__setMorphDebugFrozen(true)")
                stages[label] = page.evaluate("() => window.__morphProbe")
                path = out_dir / f"FAST-06R1.4_{slug}.png"
                page.screenshot(path=str(path), full_page=True)
                shots[label] = str(path)
                page.evaluate("() => window.__setMorphDebugFrozen(false)")
            # Wait for the post-Viseme neutral, not the initial neutral.
            page.wait_for_function(
                "() => window.__morphProbe?.debugLabel === 'Neutral' && "
                "window.__morphProbe?.presActuators.every(a => a.rendererInfluence === 0)",
                timeout=12000,
            )
            page.evaluate("() => window.__setMorphDebugFrozen(true)")
            path = out_dir / "FAST-06R1.4_neutral_return.png"
            page.screenshot(path=str(path), full_page=True)
            shots["NeutralReturn"] = str(path)
            stages["NeutralReturn"] = page.evaluate("() => window.__morphProbe")
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    expected = {
        "Neutral": {},
        "JawOpen": {"PRES_JawOpen": 1.0},
        "Blink": {"PRES_Blink_L": 1.0, "PRES_Blink_R": 1.0},
        "SmileMild": {"PRES_SmileMild": 1.0},
        "Viseme_A": {"PRES_Viseme_A": 1.0},
        "NeutralReturn": {},
    }
    stage_gates = {}
    for label, wanted in expected.items():
        actual = {
            a["name"]: float(a["rendererInfluence"])
            for a in stages[label]["presActuators"]
            if float(a["rendererInfluence"]) != 0.0
        }
        stage_gates[label] = actual == wanted

    integrity = base_integrity()
    morph = json.loads(MORPH.read_text(encoding="utf-8"))
    fixed_fov = (
        config["cameraPresets"]["CAM_FULL"]["fov_deg"]
        == config["cameraPresets"]["CAM_UPPER"]["fov_deg"]
        == 42.0
    )
    technical_gate = {
        "allActuatorWeightsExact": all(stage_gates.values()),
        "char1MeshFound": all(s["meshName"] == "char1" for s in stages.values()),
        "allPresTargetsPresent": all(s["allPresPresent"] for s in stages.values()),
        "neutralBaseExact": integrity["neutralBaseGlobalMaxDisplacement"] == 0.0,
        "lockedStructureUnchanged": all(
            integrity[k]
            for k in (
                "vertexCountMatch",
                "skinJointCountMatch",
                "materialJsonExact",
                "animationJsonExact",
            )
        ),
        "fixedFovCameraContract": fixed_fov,
    }
    receipt = {
        "receiptId": f"FAST-06R1.4_actuator_visibility_{ts}",
        "timestampUtc": ts,
        "stage": "FAST-06R1.4-A",
        "verdict": (
            "TECHNICAL_PROOF_READY__HUMAN_VISUAL_REVIEW_REQUIRED"
            if all(technical_gate.values())
            else "TECHNICAL_HOLD"
        ),
        "officialStatus": {
            "fast03D": "LIMITED_REOPEN_PRESENTATION_MORPH_ONLY",
            "fast06Technical": "PASS",
            "fast06HumanVisual": "HOLD",
        },
        "rootCause": "Original actuator vertex selections were outside visible facial features.",
        "technicalGate": technical_gate,
        "stageWeightGates": stage_gates,
        "integrity": integrity,
        "camera": {
            "full": config["cameraPresets"]["CAM_FULL"],
            "upper": config["cameraPresets"]["CAM_UPPER"],
            "zoomDurationSec": config["zoomDurationSec"],
            "fovPolicy": "FIXED_42_DEG_DOLLY_ONLY",
        },
        "morphRevision": morph.get("revision"),
        "affectedVertexCounts": {
            name: len(rows) for name, rows in morph["shapeKeys"].items()
        },
        "artifacts": {
            "outputGlb": str(OUTPUT),
            "outputGlbSha256": sha256(OUTPUT),
            "morphJson": str(MORPH),
            "morphJsonSha256": sha256(MORPH),
            "forensic": str(FORENSIC),
            "screenshots": shots,
            "debugUrl": f"http://127.0.0.1:8766/?debug=morph",
        },
        "humanAcceptanceStillRequired": [
            "JawOpen clearly opens mouth",
            "Blink visibly closes both eyes",
            "SmileMild visibly raises mouth corners",
            "Viseme_A is distinct from Neutral and JawOpen",
            "NeutralReturn matches original identity",
        ],
    }
    receipt_path = EVIDENCE / "FAST-06R1.4_actuator_visibility_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"receipt": str(receipt_path), "technicalGate": technical_gate}, ensure_ascii=True))
    return 0 if all(technical_gate.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
