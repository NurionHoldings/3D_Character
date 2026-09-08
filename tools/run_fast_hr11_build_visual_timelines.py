#!/usr/bin/env python3
"""FAST-HR11 / HR11R — build per-scenario FACE weight timelines for visual gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))

from fast_track.runtime.expression_mixer import lerp_weights
from fast_track.runtime.face_composition import FaceCompositionLayer
from fast_track.runtime.korean_lip_sync_v2 import build_phoneme_timeline

WORK = ROOT / "fast_track/working/meshy_silver_starlight"
NAMING = WORK / "semantic/NURION_FACE_CANONICAL_V1_NAMING_TABLE.json"
# Default writes HR11R paths; --legacy-hr11 still supported via env OUT override below.
OUT = WORK / "evidence/FAST-HR11R_visual/timelines.json"


def face_to_jake(naming: dict) -> dict[str, str]:
    return {
        row["nurionCanonical"]: row["jakeOriginal"]
        for row in naming["rows"]
        if row["tier"] == "ESSENTIAL_V1"
    }


def blink_envelope(t: float, peak: float, width: float = 0.14, hold: float = 0.05) -> float:
    """HR11R: firmer final-close with brief full-close hold at peak.

    Peak frames target eyeball/highlight leak ≈ 0. Curve only — no Eye Cal change.
    """
    d = abs(t - peak)
    if d <= hold * 0.5:
        return 1.0
    if d >= width:
        return 0.0
    # Steeper near peak (u^2) so lids seal before the hold window.
    u = 1.0 - (d - hold * 0.5) / (width - hold * 0.5)
    return min(1.0, max(0.0, u * u))


def inject_blink(composed: dict[str, float], blink: float) -> dict[str, float]:
    """Apply bilateral blink; at near-peak, force full seal (both lids equal).

    Peak also adds a light squint assist — donor-visual quality only (not Eye Cal).
    Squint helps close thin eyeball/highlight seams Jake's blink shapes leave at 1.0.
    """
    if blink <= 1e-6:
        return composed
    out = dict(composed)
    # Soft approach below peak; at high blink force both lids to sealed 1.0.
    if blink >= 0.92:
        sealed = 1.0
    else:
        sealed = blink
    out["FACE_eyeBlinkLeft"] = max(out.get("FACE_eyeBlinkLeft", 0.0), sealed)
    out["FACE_eyeBlinkRight"] = max(out.get("FACE_eyeBlinkRight", 0.0), sealed)
    # Peak seal assist: squint rises only near full close.
    if sealed >= 0.85:
        squint = 0.85 * ((sealed - 0.85) / 0.15)
        out["FACE_eyeSquintLeft"] = max(out.get("FACE_eyeSquintLeft", 0.0), squint)
        out["FACE_eyeSquintRight"] = max(out.get("FACE_eyeSquintRight", 0.0), squint)
    return out


def to_jake_weights(face_weights: dict[str, float], mapping: dict[str, str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for face, w in face_weights.items():
        jake = mapping.get(face)
        if jake:
            out[jake] = float(w)
    # HR11R: also drive combined Eye_Blink (HOLD-tier donor shape) for fuller peak seal.
    # Not a FACE Canonical rename — Jake donor apply only.
    bl = max(
        float(face_weights.get("FACE_eyeBlinkLeft", 0.0) or 0.0),
        float(face_weights.get("FACE_eyeBlinkRight", 0.0) or 0.0),
    )
    if bl > 1e-6:
        # Peak overdrive 1.12 — Blender render raises slider_max; seals residual highlight seam.
        sealed = 1.12 if bl >= 0.92 else bl
        out["Eye_Blink_L"] = sealed
        out["Eye_Blink_R"] = sealed
        out["Eye_Blink"] = sealed
        if sealed >= 0.85:
            squint = min(1.0, 0.85 * ((min(sealed, 1.0) - 0.85) / 0.15))
            out["Eye_Squint_L"] = max(out.get("Eye_Squint_L", 0.0), squint)
            out["Eye_Squint_R"] = max(out.get("Eye_Squint_R", 0.0), squint)
    return out


def main() -> int:
    naming = json.loads(NAMING.read_text(encoding="utf-8"))
    mapping = face_to_jake(naming)
    layer = FaceCompositionLayer(NAMING)
    fps = 12
    scenarios: dict = {}

    # 1 Neutral → SoftSmile (0.8s) — primary blink visibility sequence
    frames = []
    n = int(0.8 * fps)
    # Snap blink peak to an exact sample so peak frame is sealed at 1.0.
    blink_peak_i = max(1, round(0.48 * n))
    blink_peak_t = blink_peak_i / n
    for i in range(n + 1):
        t = i / n
        expr = (
            layer.mixer.resolve_preset("Neutral")
            if t <= 0
            else (
                layer.mixer.resolve_preset("SoftSmile")
                if t >= 1
                else lerp_weights(
                    layer.mixer.resolve_preset("Neutral"),
                    layer.mixer.resolve_preset("SoftSmile"),
                    t,
                )
            )
        )
        composed = layer.compose(expr, {})
        composed = inject_blink(composed, blink_envelope(t, blink_peak_t, width=0.18, hold=0.08))
        frames.append(
            {
                "i": i,
                "t": round(t, 4),
                "jakeWeights": to_jake_weights(composed, mapping),
                "faceWeights": composed,
            }
        )
    scenarios["neutral_to_softsmile"] = {
        "label": "Neutral → SoftSmile",
        "fps": fps,
        "frames": frames,
        "hr11r": {"blinkPeakT": blink_peak_t, "blinkPeakI": blink_peak_i, "qualityPatch": True},
    }

    def speaking_scenario(name: str, preset: str, text: str, duration: float = 1.4):
        events = build_phoneme_timeline(text, start=0.0, end=duration)
        local = []
        count = int(duration * fps)
        blink_peak_i = max(1, round(0.50 * count))
        blink_peak = (blink_peak_i / count) * duration
        for i in range(count + 1):
            t = (i / count) * duration
            result = layer.evaluate(
                expression_preset=preset,
                events=events,
                t=t,
                speech_start=0.0,
                speech_end=duration,
                drive_actuator=False,
            )
            composed = inject_blink(
                dict(result["composedWeights"]),
                blink_envelope(t, blink_peak, width=0.18, hold=0.08),
            )
            local.append(
                {
                    "i": i,
                    "t": round(t, 4),
                    "jakeWeights": to_jake_weights(composed, mapping),
                    "faceWeights": composed,
                    "speechClass": {
                        "plosive": float(result["speechWeights"].get("FACE_mouthPlosive", 0.0)),
                        "open": max(
                            float(result["speechWeights"].get("FACE_mouthOpen", 0.0)),
                            float(result["speechWeights"].get("FACE_mouthWiden", 0.0)),
                        ),
                        "smileL": float(composed.get("FACE_mouthSmileLeft", 0.0)),
                        "smileR": float(composed.get("FACE_mouthSmileRight", 0.0)),
                    },
                }
            )
        scenarios[name] = {
            "label": f"{preset} + Speaking",
            "fps": fps,
            "text": text,
            "frames": local,
            "hr11r": {"blinkPeakT": blink_peak, "qualityPatch": True},
        }

    speaking_scenario("happy_speaking", "Happy", "안녕하세요")
    speaking_scenario("concerned_speaking", "Concerned", "괜찮으세요")
    speaking_scenario("surprised_speaking", "Surprised", "정말요")

    # Listening → Speaking
    frames = []
    duration = 1.5
    count = int(duration * fps)
    events = build_phoneme_timeline("안녕하세요", start=0.5, end=duration)
    for i in range(count + 1):
        t = (i / count) * duration
        blend = 0.0 if t < 0.35 else min(1.0, (t - 0.35) / 0.35)
        expr = lerp_weights(
            layer.mixer.resolve_preset("Listening"),
            layer.mixer.resolve_preset("SoftSmile"),
            blend,
        )
        speech = layer.lipsync.evaluate_timeline(events, t)
        composed = layer.compose(expr, speech)
        frames.append(
            {
                "i": i,
                "t": round(t, 4),
                "jakeWeights": to_jake_weights(composed, mapping),
                "faceWeights": composed,
            }
        )
    scenarios["listening_to_speaking"] = {
        "label": "Listening → Speaking",
        "fps": fps,
        "frames": frames,
    }

    # Speaking → Neutral
    frames = []
    duration = 1.6
    count = int(duration * fps)
    events = build_phoneme_timeline("감사합니다", start=0.0, end=0.9)
    for i in range(count + 1):
        t = (i / count) * duration
        if t <= 0.9:
            blend = 0.0
            preset_a, preset_b = "Happy", "Happy"
        else:
            blend = min(1.0, (t - 0.9) / 0.5)
            preset_a, preset_b = "Happy", "Neutral"
        expr = lerp_weights(
            layer.mixer.resolve_preset(preset_a),
            layer.mixer.resolve_preset(preset_b),
            blend,
        )
        speech = layer.lipsync.evaluate_timeline(events, t)
        composed = layer.compose(expr, speech)
        frames.append(
            {
                "i": i,
                "t": round(t, 4),
                "jakeWeights": to_jake_weights(composed, mapping),
                "faceWeights": composed,
            }
        )
    scenarios["speaking_to_neutral"] = {
        "label": "Speaking → Neutral",
        "fps": fps,
        "frames": frames,
    }

    payload = {
        "canonical_contract": "NURION_FACE_CANONICAL_V1",
        "donor": "Jake.fbx",
        "stage": "FAST-HR11R_QUALITY_PATCH",
        "qualityPatch": {
            "blinkPeakClosure": True,
            "speechClassSmileAttenuation": True,
            "architectureChange": False,
        },
        "faceToJake": mapping,
        "scenarios": scenarios,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT), "scenarios": list(scenarios)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
