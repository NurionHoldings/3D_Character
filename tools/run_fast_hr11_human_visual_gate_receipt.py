#!/usr/bin/env python3
"""FAST-HR11 — finalize human visual gate receipt from rendered evidence."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
EVIDENCE = WORK / "evidence"
VIS = EVIDENCE / "FAST-HR11_visual"
RECEIPT = EVIDENCE / "FAST-HR11_human_visual_gate_receipt.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    videos = {
        "neutral_to_softsmile": EVIDENCE / "FAST-HR11_neutral_to_softsmile.mp4",
        "happy_speaking": EVIDENCE / "FAST-HR11_happy_speaking.mp4",
        "concerned_speaking": EVIDENCE / "FAST-HR11_concerned_speaking.mp4",
        "surprised_speaking": EVIDENCE / "FAST-HR11_surprised_speaking.mp4",
        "listening_to_speaking": EVIDENCE / "FAST-HR11_listening_to_speaking.mp4",
        "speaking_to_neutral": EVIDENCE / "FAST-HR11_speaking_to_neutral.mp4",
    }
    manifest = json.loads((VIS / "frames/render_manifest.json").read_text(encoding="utf-8"))

    criteria = {
        "01_noFaceCollapse": "PENDING_HUMAN",
        "02_smileAsymmetryNatural": "PENDING_HUMAN",
        "03_blinkTimingNatural": "PENDING_HUMAN",
        "04_noEyeballLeakDuringBlink": "AGENT_CONCERN",
        "05_browNoOverInvasion": "PENDING_HUMAN",
        "06_smileSurvivesSpeech": "AGENT_CONCERN",
        "07_mbpClosureVisible": "PENDING_HUMAN",
        "08_ouPuckerNotExcessive": "PENDING_HUMAN",
        "09_jawOpenNotDetached": "PENDING_HUMAN",
        "10_cheekRaiseConnectedToSmile": "PENDING_HUMAN",
        "11_listeningToSpeakingSmooth": "PENDING_HUMAN",
        "12_speakingToNeutralNatural": "PENDING_HUMAN",
        "13_emotionSpeechNoFight": "PENDING_HUMAN",
        "14_notMechanicalOverall": "PENDING_HUMAN",
        "15_identityMaintained": "PASS_STRUCTURAL",
        "16_eyeCalibrationUntouched": "PASS_STRUCTURAL",
        "17_bodyMotionUnaffected": "PASS_STRUCTURAL",
        "18_humanReviewerAccept": "PENDING",
    }

    agent = {
        "verdict": "HUMAN_VISUAL_REVIEW_REQUIRED",
        "observations": [
            "Blink-closed frames show a bright lid seam / possible eyeball highlight leak (criterion 04).",
            "Some Happy+Speaking early frames read closer to Neutral mouth than clear smile under bright frontal light (criterion 06 readability concern).",
            "Speaking→Neutral end frame returns to clean closed-mouth Neutral (positive for criterion 12).",
            "HR05~HR10 structural contracts remain untouched; HR11 is visual-quality only.",
        ],
        "recommendation": "Do not enable TALKING. Await human ACCEPT/FAIL. If FAIL, adjust weight/timing/attenuation only — do not reopen HR05~HR10 architecture.",
    }

    receipt = {
        "receiptId": f"FAST-HR11_human_visual_gate_{ts}",
        "stage": "FAST-HR11_HUMAN_VISUAL_GATE",
        "status": "HUMAN_VISUAL_REVIEW_REQUIRED",
        "talking_status": "HOLD",
        "face_product_lock": "NOT_DECLARED",
        "canonical_contract": "NURION_FACE_CANONICAL_V1",
        "renderDonor": {
            "asset": "fast_track/assets/external/hr05_jake/Jake.fbx",
            "role": "HR05 facial reference/donor visual proxy",
            "product_use": False,
            "attribution": "Canino3d / CC BY",
        },
        "scenarios": [
            "Neutral → SoftSmile",
            "Happy + Speaking",
            "Concerned + Speaking",
            "Surprised + Speaking",
            "Listening → Speaking",
            "Speaking → Neutral",
        ],
        "criteria": criteria,
        "agentVisualPrecheck": agent,
        "artifacts": {
            "timelines": str(VIS / "timelines.json"),
            "frameManifest": str(VIS / "frames/render_manifest.json"),
            "videos": {k: str(v) for k, v in videos.items() if v.exists()},
            "videoSha256": {k: sha256(v) for k, v in videos.items() if v.exists()},
            "keyframeSamples": {
                k: row.get("keyframes") for k, row in manifest.items()
            },
        },
        "passCondition": {
            "required": "human reviewer = ACCEPT on all visual criteria",
            "onPass": ["TALKING GO", "FACE PRODUCT LOCK"],
            "onFail": ["TALKING HOLD", "quality-only correction", "HR11 re-run"],
            "doNotReopen": ["HR05", "HR06", "HR07", "HR08", "HR09", "HR10"],
        },
        "next": "Human reviewer ACCEPT or FAIL with criterion notes",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(RECEIPT), "status": receipt["status"], "talking": "HOLD"}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
