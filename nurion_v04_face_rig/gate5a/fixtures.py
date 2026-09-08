"""Diagnostic utterance fixtures + deterministic synthetic WAV generator."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Tuple

from .audio_io import write_pcm16_mono_wav
from .parameters import GATE5A_PARAMETERS

# (id, transcript, approx speech ms, pause pattern)
DIAGNOSTIC_SET: List[Dict] = [
    {"id": "바보", "transcript": "바보", "speechMs": 480, "rate": "NORMAL", "kind": "WORD"},
    {"id": "미소", "transcript": "미소", "speechMs": 420, "rate": "NORMAL", "kind": "WORD"},
    {"id": "보험", "transcript": "보험", "speechMs": 450, "rate": "NORMAL", "kind": "WORD"},
    {"id": "분석", "transcript": "분석", "speechMs": 480, "rate": "NORMAL", "kind": "WORD"},
    {"id": "안녕하세요", "transcript": "안녕하세요", "speechMs": 860, "rate": "NORMAL", "kind": "SENTENCE"},
    {
        "id": "보험을_분석해_드릴게요",
        "transcript": "보험을 분석해 드릴게요",
        "speechMs": 1500,
        "rate": "NORMAL",
        "kind": "SENTENCE",
    },
    {
        "id": "고객님의_보험_가입_내용을_확인하겠습니다",
        "transcript": "고객님의 보험 가입 내용을 확인하겠습니다",
        "speechMs": 2200,
        "rate": "NORMAL",
        "kind": "ABA",
    },
    {
        "id": "insurance-check",
        "transcript": "안녕하세요. 고객님의 보험을 분석해 드릴게요.",
        "speechMs": 2400,
        "rate": "NORMAL",
        "kind": "SENTENCE",
        "midPauseMs": 180,
    },
    {
        "id": "안녕하세요_fast",
        "transcript": "안녕하세요",
        "speechMs": 520,
        "rate": "FAST",
        "kind": "RATE_VARIANT",
    },
    {
        "id": "안녕하세요_slow",
        "transcript": "안녕하세요",
        "speechMs": 1400,
        "rate": "SLOW",
        "kind": "RATE_VARIANT",
    },
    {
        "id": "보험_with_pause",
        "transcript": "보험. 분석",
        "speechMs": 900,
        "rate": "NORMAL",
        "kind": "PAUSE",
        "midPauseMs": 220,
    },
]


def _synth_utterance(speech_ms: int, mid_pause_ms: int = 0, sr: int = 16000) -> List[float]:
    """
    Deterministic speech-shaped noise bursts (not TTS).
    Recorded as sourceKind=SYNTHETIC.
    """
    lead = int(GATE5A_PARAMETERS["padLeadMs"])
    trail = int(GATE5A_PARAMETERS["padTrailMs"])
    total_ms = lead + speech_ms + trail + (mid_pause_ms if mid_pause_ms else 0)
    n = int(sr * total_ms / 1000.0)
    out = [0.0] * n

    def fill_burst(t0_ms: int, t1_ms: int, seed: int) -> None:
        i0 = int(sr * t0_ms / 1000.0)
        i1 = int(sr * t1_ms / 1000.0)
        length = max(1, i1 - i0)
        for k in range(length):
            t = k / float(sr)
            # envelope
            env = math.sin(math.pi * (k + 0.5) / length)
            # deterministic pseudo noise from LCG
            seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
            noise = ((seed / 0x7FFFFFFF) * 2.0 - 1.0) * 0.35
            tone = 0.25 * math.sin(2 * math.pi * 180 * t) + 0.15 * math.sin(2 * math.pi * 320 * t)
            out[i0 + k] = max(-1.0, min(1.0, env * (tone + noise)))

    if mid_pause_ms and speech_ms > mid_pause_ms + 100:
        half = (speech_ms - mid_pause_ms) // 2
        fill_burst(lead, lead + half, seed=7)
        fill_burst(lead + half + mid_pause_ms, lead + speech_ms + mid_pause_ms, seed=13)
    else:
        fill_burst(lead, lead + speech_ms, seed=11)
    return out


def ensure_synthetic_fixtures(audio_dir: Path) -> List[Dict]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    sr = int(GATE5A_PARAMETERS["targetSampleRate"])
    for item in DIAGNOSTIC_SET:
        path = audio_dir / f"{item['id']}.wav"
        samples = _synth_utterance(
            int(item["speechMs"]),
            mid_pause_ms=int(item.get("midPauseMs") or 0),
            sr=sr,
        )
        write_pcm16_mono_wav(path, samples, sample_rate=sr)
        manifest.append(
            {
                **item,
                "audio": str(path).replace("\\", "/"),
                "language": "ko-KR",
                "sourceKind": "SYNTHETIC",
            }
        )
    return manifest
