#!/usr/bin/env python3
"""FAST-06R1 — capture 3-scene framing evidence (FULL / TALKING / RETURN)."""

from __future__ import annotations

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
PORT = int(os.environ.get("FAST06_PORT", "8778"))
BASE = f"http://127.0.0.1:{PORT}"


def wait_for_server(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/config", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> int:
    from playwright.sync_api import sync_playwright

    from fast_track.runtime.camera_contract import CAM_FULL, CAM_UPPER

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = EVIDENCE / "FAST-06R1_visual_framing"
    out_dir.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=str(ROOT),
        env={**os.environ, "FAST06_PORT": str(PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    shots: dict[str, str] = {}

    try:
        if not wait_for_server():
            raise RuntimeError(f"Server failed on port {PORT}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(BASE, wait_until="load", timeout=60000)
            page.wait_for_selector("#boot-msg", state="hidden", timeout=60000)
            page.wait_for_function(
                "() => document.getElementById('status-badge')?.textContent === 'READY'",
                timeout=60000,
            )
            time.sleep(0.4)

            full_path = out_dir / "FAST-06R1_01_FULL_IDLE.png"
            page.screenshot(path=str(full_path), full_page=True)
            shots["fullIdle"] = str(full_path)

            page.locator('button[data-menu="company_intro"]').click()
            page.wait_for_function(
                "() => document.getElementById('state-overlay')?.textContent?.includes('TALKING')",
                timeout=60000,
            )
            time.sleep(0.6)
            talk_path = out_dir / "FAST-06R1_02_TALKING_UPPER.png"
            page.screenshot(path=str(talk_path), full_page=True)
            shots["talkingUpper"] = str(talk_path)

            page.wait_for_function(
                "() => document.getElementById('status-badge')?.textContent === 'READY'",
                timeout=120000,
            )
            time.sleep(0.5)
            ret_path = out_dir / "FAST-06R1_03_RETURN_FULL_IDLE.png"
            page.screenshot(path=str(ret_path), full_page=True)
            shots["returnFullIdle"] = str(ret_path)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    receipt = {
        "receiptId": f"FAST-06R1_framing_{ts}",
        "timestampUtc": ts,
        "stage": "FAST-06R1",
        "verdict": "FRAMING_CORRECTION_APPLIED",
        "humanVisualReview": "PENDING_USER_VIDEO",
        "classification": {
            "primary": "VISUAL_PRESENTATION_CAMERA_FRAMING_INSUFFICIENT",
            "secondary": "FACIAL_PRESENTATION_READABILITY_INSUFFICIENT",
        },
        "lockedUnchanged": [
            "Identity Path A",
            "FAST-03D Morph",
            "FAST-04 Lip Sync",
            "Base Rig / Skin / UV / Materials",
        ],
        "changes": {
            "CAM_UPPER": CAM_UPPER.to_dict(),
            "CAM_FULL": CAM_FULL.to_dict(),
            "presentationZoomDurationSec": 1.05,
            "presentationLayerOnly": True,
        },
        "previousCamUpper": {
            "location": [0.0, 1.48, 1.65],
            "target": [0.0, 1.45, 0.0],
            "fov_deg": 32.0,
        },
        "threeSceneEvidence": shots,
        "nextStep": "User records short video: FULL_IDLE → TALKING (face readable) → RETURN",
    }
    receipt_path = EVIDENCE / "FAST-06R1_framing_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"receipt": str(receipt_path), "shots": shots}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
