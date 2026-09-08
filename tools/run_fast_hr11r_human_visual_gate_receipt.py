#!/usr/bin/env python3
"""FAST-HR11R — quality-patch human visual gate receipt (TALKING HOLD until ACCEPT)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
EVIDENCE = WORK / "evidence"
VIS = EVIDENCE / "FAST-HR11R_visual"
RECEIPT = EVIDENCE / "FAST-HR11R_human_visual_gate_receipt.json"
PRIOR = EVIDENCE / "FAST-HR11_human_visual_gate_receipt.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    videos = {
        "neutral_to_softsmile": EVIDENCE / "FAST-HR11R_neutral_to_softsmile.mp4",
        "happy_speaking": EVIDENCE / "FAST-HR11R_happy_speaking.mp4",
        "concerned_speaking": EVIDENCE / "FAST-HR11R_concerned_speaking.mp4",
        "surprised_speaking": EVIDENCE / "FAST-HR11R_surprised_speaking.mp4",
        "listening_to_speaking": EVIDENCE / "FAST-HR11R_listening_to_speaking.mp4",
        "speaking_to_neutral": EVIDENCE / "FAST-HR11R_speaking_to_neutral.mp4",
    }
    manifest = json.loads((VIS / "frames/render_manifest.json").read_text(encoding="utf-8"))

    criteria = {
        "01_noFaceCollapse": "PENDING_HUMAN",
        "02_smileAsymmetryNatural": "PENDING_HUMAN",
        "03_blinkTimingNatural": "PENDING_HUMAN",
        "04_noEyeballLeakDuringBlink": "PATCHED_AWAITING_HUMAN",
        "05_browNoOverInvasion": "PENDING_HUMAN",
        "06_smileSurvivesSpeech": "PATCHED_AWAITING_HUMAN",
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
        "priorHumanVerdict": "B_CONDITIONAL_FAIL",
        "qualityPatch": {
            "blinkPeakClosure": "firmer final-close + combined Eye_Blink at peak; L/R equal seal",
            "happySpeechSmile": "speech-class attenuation — MBP keep≈0.48; open/A-EI keep≈0.84",
            "forbidden": [
                "HR05-HR10 architecture",
                "FACE Canonical",
                "LipSync ownership",
                "Composition ownership policy",
                "Eye Calibration",
                "Body Motion",
                "PRES legacy contract",
            ],
        },
        "observations": [
            "HR11 CONDITIONAL FAIL items only: blink peak leak + Happy non-MBP smile retention.",
            "MBP smile attenuation intentionally retained (speech closure priority).",
            "Ownership policy schema unchanged; attenuation magnitudes only.",
            "Await etherean frame review of Blink-clear sequence + Happy+Speaking; regress other 4.",
        ],
        "recommendation": "Do not enable TALKING. Await human ACCEPT. On FAIL: quality-only retune again — do not reopen HR05~HR10.",
    }

    receipt = {
        "receiptId": f"FAST-HR11R_human_visual_gate_{ts}",
        "stage": "FAST-HR11R_QUALITY_PATCH_HUMAN_VISUAL_GATE",
        "status": "HUMAN_VISUAL_REVIEW_REQUIRED",
        "talking_status": "HOLD",
        "face_product_lock": "NOT_DECLARED",
        "prior": {
            "stage": "FAST-HR11",
            "humanVerdict": "B_CONDITIONAL_FAIL",
            "receipt": str(PRIOR) if PRIOR.exists() else None,
        },
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
        "focusReverify": ["neutral_to_softsmile", "happy_speaking"],
        "regressionCheck": [
            "concerned_speaking",
            "surprised_speaking",
            "listening_to_speaking",
            "speaking_to_neutral",
        ],
        "criteria": criteria,
        "agentVisualPrecheck": agent,
        "artifacts": {
            "timelines": str(VIS / "timelines.json"),
            "frameManifest": str(VIS / "frames/render_manifest.json"),
            "videos": {k: str(v) for k, v in videos.items() if v.exists()},
            "videoSha256": {k: sha256(v) for k, v in videos.items() if v.exists()},
            "keyframeSamples": {k: row.get("keyframes") for k, row in manifest.items()},
        },
        "passCondition": {
            "required": "human reviewer = ACCEPT on blink leak + Happy smile retention + no regression on other 4",
            "onPass": ["HR11 PASS", "TALKING GO", "FACE PRODUCT LOCK"],
            "onFail": ["TALKING HOLD", "quality-only correction", "HR11R re-run"],
            "doNotReopen": ["HR05", "HR06", "HR07", "HR08", "HR09", "HR10"],
        },
        "next": "Human reviewer ACCEPT or FAIL with criterion notes on patched items 04 and 06",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"receipt": str(RECEIPT), "status": receipt["status"], "talking": "HOLD"},
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
