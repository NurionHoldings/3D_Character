#!/usr/bin/env python3
"""FAST-06R1.3-A — Browser morph binding proof (char1 + material.morphTargets)."""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
EVIDENCE = WORK / "evidence"
SERVER = ROOT / "tools/run_fast_06_presentation_server.py"
PORT = int(os.environ.get("FAST06_PORT", "8777"))
BASE = f"http://127.0.0.1:{PORT}"


def main() -> int:
    from playwright.sync_api import sync_playwright

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = EVIDENCE / "FAST-06R1.3_morph_probe"
    out_dir.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=str(ROOT),
        env={**os.environ, "FAST06_PORT": str(PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    shots: dict[str, str] = {}
    probe: dict = {}

    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"{BASE}/api/config", timeout=2)
                break
            except Exception:
                time.sleep(0.25)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"{BASE}/?debug=morph", wait_until="load", timeout=60000)
            page.wait_for_selector("#boot-msg", state="hidden", timeout=60000)
            time.sleep(0.5)
            probe = page.evaluate("() => window.__morphProbe")
            page.screenshot(path=str(out_dir / "FAST-06R1.3_debug_neutral_start.png"), full_page=True)
            shots["neutralStart"] = str(out_dir / "FAST-06R1.3_debug_neutral_start.png")

            for label, wait_key in [
                ("JawOpen", "JawOpen"),
                ("Blink", "Blink"),
                ("SmileMild", "SmileMild"),
                ("Viseme_A", "Viseme_A"),
            ]:
                deadline = time.time() + 8
                while time.time() < deadline:
                    snap = page.evaluate("() => window.__morphProbe")
                    if snap.get("debugLabel") == wait_key:
                        break
                    time.sleep(0.15)
                time.sleep(0.35)
                fname = out_dir / f"FAST-06R1.3_debug_{wait_key.lower()}.png"
                page.screenshot(path=str(fname), full_page=True)
                shots[wait_key] = str(fname)
                probe = page.evaluate("() => window.__morphProbe")

            browser.close()
    finally:
        proc.terminate()

    gate = {
        "char1MeshFound": probe.get("meshName") == "char1",
        "allPresInDictionary": probe.get("allPresPresent") is True,
        "materialMorphTargetsEnabled": any(probe.get("materialMorphTargetsEnabled") or []),
        "rendererInfluenceNonZero": any(
            (a.get("rendererInfluence") or 0) > 0
            for a in probe.get("presActuators", [])
            if probe.get("debugLabel") in ("JawOpen", "Viseme_A", "SmileMild", "Blink")
        ),
    }
    receipt = {
        "receiptId": f"FAST-06R1.3_morph_binding_{ts}",
        "timestampUtc": ts,
        "stage": "FAST-06R1.3-A",
        "verdict": "MORPH_BINDING_FIX_APPLIED" if all(gate.values()) else "MORPH_BINDING_INVESTIGATION",
        "rootCause": "material.morphTargets was not enabled on char1 Material_1 — morphTargetInfluences ignored by GPU shader",
        "fix": "enableMorphMaterials(char1) + explicit char1 bind + morphTargetInfluencesNeedUpdate",
        "gate": gate,
        "morphProbe": probe,
        "screenshots": shots,
        "debugUrl": f"{BASE}/?debug=morph",
        "presentationUrl": BASE,
    }
    receipt_path = EVIDENCE / "FAST-06R1.3_morph_binding_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"receipt": str(receipt_path), "gate": gate}, ensure_ascii=True))
    return 0 if all(gate.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
