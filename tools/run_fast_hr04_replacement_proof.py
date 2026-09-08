#!/usr/bin/env python3
"""FAST-HR04 — structural regression and Blink-only browser proof."""

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
BASE_GLB = WORK / "identity_locked/FAST-03B_identity_neutral.glb"
OUTPUT_GLB = WORK / "output/FAST-HR03_donor_blink.glb"
PORT = int(os.environ.get("FAST_HR_PROOF_PORT", "8781"))
BASE_URL = f"http://127.0.0.1:{PORT}"


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_fast02():
    spec = importlib.util.spec_from_file_location("fast02", FAST02)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_server():
    for _ in range(80):
        try:
            return json.load(urllib.request.urlopen(f"{BASE_URL}/api/config", timeout=2))
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("replacement proof server did not start")


def named_mesh_index(gltf, name: str):
    for node in gltf["nodes"]:
        if node.get("name") == name and "mesh" in node:
            return node["mesh"]
    raise KeyError(name)


def animation_signature(gltf):
    signatures = []
    for animation in gltf.get("animations", []):
        channels = []
        for channel in animation["channels"]:
            target = channel["target"]
            node_name = gltf["nodes"][target["node"]].get("name", "")
            channels.append((node_name, target["path"]))
        signatures.append(
            {
                "name": animation.get("name", ""),
                "channelTargets": sorted(channels),
                "channelCount": len(channels),
            }
        )
    return signatures


def structural_regression():
    f2 = load_fast02()
    g0, b0 = f2.load_glb(BASE_GLB)
    g1, b1 = f2.load_glb(OUTPUT_GLB)
    m0 = named_mesh_index(g0, "char1")
    m1 = named_mesh_index(g1, "char1")
    p0 = g0["meshes"][m0]["primitives"][0]
    p1 = g1["meshes"][m1]["primitives"][0]

    attrs = {}
    for name in ("POSITION", "NORMAL", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"):
        if name not in p0["attributes"] or name not in p1["attributes"]:
            attrs[name] = {"presentBoth": False, "exact": False}
            continue
        a = f2.read_accessor(g0, b0, p0["attributes"][name])
        b = f2.read_accessor(g1, b1, p1["attributes"][name])
        attrs[name] = {
            "presentBoth": True,
            "shapeMatch": a.shape == b.shape,
            "exact": a.shape == b.shape and np.array_equal(a, b),
            "maxAbsDelta": float(np.max(np.abs(a.astype(np.float64) - b.astype(np.float64))))
            if a.shape == b.shape
            else None,
        }

    base_positions = f2.read_accessor(g0, b0, p0["attributes"]["POSITION"]).astype(np.float64)
    output_positions = f2.read_accessor(g1, b1, p1["attributes"]["POSITION"]).astype(np.float64)
    unique_base = np.unique(base_positions, axis=0)
    unique_output = np.unique(output_positions, axis=0)

    def directed_max_nearest(source, target):
        maximum = 0.0
        for start in range(0, len(source), 128):
            chunk = source[start : start + 128]
            distance = np.linalg.norm(chunk[:, None, :] - target[None, :, :], axis=2)
            maximum = max(maximum, float(np.min(distance, axis=1).max()))
        return maximum

    position_surface_error = max(
        directed_max_nearest(unique_base, unique_output),
        directed_max_nearest(unique_output, unique_base),
    )
    base_uv = f2.read_accessor(g0, b0, p0["attributes"]["TEXCOORD_0"])
    output_uv = f2.read_accessor(g1, b1, p1["attributes"]["TEXCOORD_0"])
    uv_set_exact = np.array_equal(
        np.unique(base_uv, axis=0),
        np.unique(output_uv, axis=0),
    )

    joints0 = [g0["nodes"][i].get("name", "") for i in g0["skins"][0]["joints"]]
    joints1 = [g1["nodes"][i].get("name", "") for i in g1["skins"][0]["joints"]]
    nodes1 = {n.get("name") for n in g1["nodes"]}
    return {
        "char1Attributes": attrs,
        "char1PositionsExact": attrs["POSITION"]["exact"],
        "char1UvExact": attrs["TEXCOORD_0"]["exact"],
        "char1PositionSurfaceMaxError": position_surface_error,
        "char1GeometryParityWithinExporterEpsilon": position_surface_error <= 1e-6,
        "char1UvValueSetExact": uv_set_exact,
        "exportRepresentationDisclosure": (
            "Blender re-export splits 14 seam vertices; in-scene recipient positions are unmodified "
            "and the bidirectional surface error is measured independently."
        ),
        "skinJointNamesExact": joints0 == joints1,
        "skinJointCountBase": len(joints0),
        "skinJointCountOutput": len(joints1),
        "animationSignatureExact": animation_signature(g0) == animation_signature(g1),
        "animationSignatureBase": animation_signature(g0),
        "animationSignatureOutput": animation_signature(g1),
        "requiredReplacementNodesPresent": {
            "NURION_FaceHead",
            "NURION_Eyelid_L",
            "NURION_Eyelid_R",
            "NURION_Eye_L",
            "NURION_Eye_R",
        }.issubset(nodes1),
    }


def main():
    from playwright.sync_api import sync_playwright

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = EVIDENCE / "FAST-HR04_blink_debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "FAST06_PORT": str(PORT),
        "NURION_PRESENTATION_GLB": str(OUTPUT_GLB),
        "NURION_PRESENTATION_LAYER": "FAST-HR04_HEAD_REPLACEMENT",
    }
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    stages, screenshots = {}, {}
    try:
        config = wait_server()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"{BASE_URL}/?debug=blink", wait_until="load", timeout=60000)
            page.wait_for_selector("#boot-msg", state="hidden", timeout=60000)
            page.wait_for_function("() => window.__morphProbe?.allBlinkPresent === true", timeout=20000)
            for label, weight, debug_label in (
                ("NeutralStart", 0.0, "Neutral"),
                ("Closing160ms", 0.5, "BlinkClosing"),
                ("Closed", 1.0, "BlinkClosed"),
                ("Reopening240ms", 0.5, "BlinkReopening"),
                ("NeutralReturn", 0.0, "Neutral"),
            ):
                stages[label] = page.evaluate(
                    "([weight, label]) => window.__setBlinkDebugPose(weight, label)",
                    [weight, debug_label],
                )
                page.wait_for_timeout(120)
                path = out_dir / f"FAST-HR04_{label.lower()}.png"
                page.screenshot(path=str(path), full_page=True)
                screenshots[label] = str(path)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    regression = structural_regression()
    closed_probe = stages["Closed"]
    registry_names = {row["meshName"] for row in closed_probe["presentationMeshRegistry"]}
    closed_values = {row["name"]: row["rendererInfluence"] for row in closed_probe["presActuators"]}
    neutral_return_values = {
        row["name"]: row["rendererInfluence"] for row in stages["NeutralReturn"]["presActuators"]
    }
    technical_gate = {
        "replacementLayerLoaded": config["presentationLayer"] == "FAST-HR04_HEAD_REPLACEMENT",
        "multiplePresentationMeshesBound": closed_probe["presentationMeshCount"] >= 3,
        "donorAndEyelidsRegistered": {
            "NURION_FaceHead",
            "NURION_Eyelid_L",
            "NURION_Eyelid_R",
        }.issubset(registry_names),
        "bilateralBlinkTargetsPresent": closed_probe["allBlinkPresent"] is True,
        "closedWeightsSynchronized": closed_values["PRES_Blink_L"] == closed_values["PRES_Blink_R"] == 1.0,
        "neutralReturnExact": neutral_return_values["PRES_Blink_L"]
        == neutral_return_values["PRES_Blink_R"]
        == 0.0,
        "closeDuration160ms": stages["Closing160ms"]["closeDurationMs"] == 160,
        "reopenDuration240ms": stages["Reopening240ms"]["reopenDurationMs"] == 240,
        "char1GeometryParityWithinExporterEpsilon": regression[
            "char1GeometryParityWithinExporterEpsilon"
        ],
        "char1UvValueSetExact": regression["char1UvValueSetExact"],
        "skinJointNamesExact": regression["skinJointNamesExact"],
        "animationSignatureExact": regression["animationSignatureExact"],
        "replacementNodesPresent": regression["requiredReplacementNodesPresent"],
    }
    receipt = {
        "receiptId": f"FAST-HR04_{ts}",
        "stage": "FAST_HEAD_REPLACEMENT_BLINK_STOP_GATE",
        "technicalVerdict": "PASS" if all(technical_gate.values()) else "HOLD",
        "humanVisualVerdict": "HOLD_SELECT_NEW_DONOR",
        "talkingStatus": "HOLD",
        "classification": "DONOR_HELPER_EYELID_SURFACE_NOT_PRODUCT_READY",
        "agentVisualPrecheck": {
            "bilateralClosure": "TECHNICALLY_DRIVEN",
            "canthus": "PROCEDURAL_HELPER_ANCHORED",
            "cheekBrowDeformation": "NONE_FROM_BLINK_HELPER",
            "naturalSeam": "FAIL",
            "neutralReturn": "PASS",
            "observation": (
                "HM08 basis skin exposes no integrated product-ready open upper-lid surface. "
                "The helper eyelid remains visibly detached/polygonal in neutral and closed poses."
            ),
        },
        "technicalGate": technical_gate,
        "structuralRegression": regression,
        "browserProbe": closed_probe,
        "artifacts": {
            "outputGlb": str(OUTPUT_GLB),
            "outputGlbSha256": sha256(OUTPUT_GLB),
            "screenshots": screenshots,
            "debugUrl": f"http://127.0.0.1:{PORT}/?debug=blink",
        },
        "decision": "STOP_HM08_INTEGRATION_AND_SELECT_NEW_FACIAL_READY_DONOR",
    }
    receipt_path = EVIDENCE / "FAST-HR04_head_replacement_blink_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "receipt": str(receipt_path),
                "technicalVerdict": receipt["technicalVerdict"],
                "humanVisualVerdict": receipt["humanVisualVerdict"],
            }
        )
    )
    return 0 if all(technical_gate.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
