"""FAST-04B — Narration timeline contract (audio master clock)."""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VisemeCue:
    start: float
    peak: float
    end: float
    viseme: str
    weight: float
    source: str = "resolver"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpeechSegment:
    start: float
    end: float
    rms_peak: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NarrationTimeline:
    audio_path: str
    sample_rate: int
    duration_sec: float
    transcript: str
    segments: list[SpeechSegment]
    cues: list[VisemeCue]
    clock: str = "AUDIO_MASTER"

    def to_dict(self) -> dict[str, Any]:
        return {
            "audioPath": self.audio_path,
            "sampleRate": self.sample_rate,
            "durationSec": self.duration_sec,
            "transcript": self.transcript,
            "clock": self.clock,
            "speechSegments": [s.to_dict() for s in self.segments],
            "visemeCues": [c.to_dict() for c in self.cues],
            "cueCount": len(self.cues),
        }


def read_wav_mono(path: Path) -> tuple["np.ndarray", int]:
    import numpy as np

    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        sw = wf.getsampwidth()
        ch = wf.getnchannels()
        raw = wf.readframes(n)
    if sw == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif sw == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sw}")
    if ch > 1:
        samples = samples.reshape(-1, ch).mean(axis=1)
    return samples, sr


def rms_envelope(samples: np.ndarray, sr: int, window_ms: float = 20.0) -> tuple[np.ndarray, np.ndarray]:
    import numpy as np

    win = max(1, int(sr * window_ms / 1000.0))
    n = len(samples)
    times = np.arange(n) / sr
    sq = samples.astype(np.float64) ** 2
    kernel = np.ones(win) / win
    rms = np.sqrt(np.convolve(sq, kernel, mode="same"))
    return times, rms


def detect_speech_segments(times: np.ndarray, rms: np.ndarray, threshold_ratio: float = 0.12) -> list[SpeechSegment]:
    import numpy as np

    peak = float(np.max(rms)) if len(rms) else 0.0
    if peak <= 1e-9:
        return []
    thr = peak * threshold_ratio
    active = rms >= thr
    segments: list[SpeechSegment] = []
    i = 0
    while i < len(active):
        if not active[i]:
            i += 1
            continue
        j = i
        while j < len(active) and active[j]:
            j += 1
        seg_rms = rms[i:j]
        segments.append(
            SpeechSegment(
                start=float(times[i]),
                end=float(times[min(j, len(times) - 1)]),
                rms_peak=float(np.max(seg_rms)),
            )
        )
        i = j
    return segments


def build_timeline(audio_path: Path, cues: list[VisemeCue], transcript: str) -> NarrationTimeline:
    samples, sr = read_wav_mono(audio_path)
    duration = len(samples) / sr
    times, rms = rms_envelope(samples, sr)
    segments = detect_speech_segments(times, rms)
    return NarrationTimeline(
        audio_path=str(audio_path),
        sample_rate=sr,
        duration_sec=duration,
        transcript=transcript,
        segments=segments,
        cues=cues,
    )
