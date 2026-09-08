"""WAV PCM integrity, decode, and normalization."""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from .parameters import GATE5A_PARAMETERS


@dataclass
class AudioBuffer:
    path: str
    sample_rate: int
    channels: int
    sample_width: int
    duration_ms: int
    samples: List[float]  # mono float -1..1 at target rate
    source_kind: str  # SYNTHETIC | HUMAN | UNKNOWN
    warnings: List[str]


def _resample_linear(samples: List[float], src_rate: int, dst_rate: int) -> List[float]:
    if src_rate == dst_rate or not samples:
        return list(samples)
    ratio = dst_rate / float(src_rate)
    out_len = max(1, int(round(len(samples) * ratio)))
    out: List[float] = []
    for i in range(out_len):
        src = i / ratio
        i0 = int(math.floor(src))
        i1 = min(i0 + 1, len(samples) - 1)
        t = src - i0
        out.append(samples[i0] * (1.0 - t) + samples[i1] * t)
    return out


def load_wav(path: Path, source_kind: str = "UNKNOWN") -> AudioBuffer:
    warnings: List[str] = []
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)

    if width != 2:
        raise ValueError(f"WAV must be 16-bit PCM, got sample_width={width}")
    if channels not in (1, 2):
        raise ValueError(f"WAV channels must be 1 or 2, got {channels}")
    if rate not in GATE5A_PARAMETERS["acceptedSampleRates"]:
        raise ValueError(
            f"sample rate {rate} not in accepted {GATE5A_PARAMETERS['acceptedSampleRates']}"
        )

    count = len(raw) // 2
    ints = struct.unpack("<" + "h" * count, raw)
    if channels == 2:
        mono = [(ints[i] + ints[i + 1]) * 0.5 / 32768.0 for i in range(0, count, 2)]
        warnings.append("STEREO_DOWNMIXED_TO_MONO")
    else:
        mono = [v / 32768.0 for v in ints]

    target = int(GATE5A_PARAMETERS["targetSampleRate"])
    if rate != target:
        mono = _resample_linear(mono, rate, target)
        warnings.append(f"RESAMPLED_{rate}_TO_{target}")

    # Peak + gentle RMS normalize (deterministic, no AGC loop)
    peak = max((abs(x) for x in mono), default=0.0)
    if peak > 1e-8:
        mono = [x / peak * 0.95 for x in mono]
    else:
        warnings.append("NEAR_SILENT_AUDIO")

    duration_ms = int(round(1000.0 * len(mono) / float(target)))
    return AudioBuffer(
        path=str(path).replace("\\", "/"),
        sample_rate=target,
        channels=1,
        sample_width=2,
        duration_ms=duration_ms,
        samples=mono,
        source_kind=source_kind,
        warnings=warnings,
    )


def write_pcm16_mono_wav(path: Path, samples: List[float], sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(
        struct.pack("<h", max(-32767, min(32767, int(round(max(-1.0, min(1.0, s)) * 32767.0)))))
        for s in samples
    )
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)


def frame_rms(samples: List[float], sample_rate: int, frame_ms: int, hop_ms: int) -> Tuple[List[float], List[int]]:
    frame = max(1, int(sample_rate * frame_ms / 1000.0))
    hop = max(1, int(sample_rate * hop_ms / 1000.0))
    energies: List[float] = []
    centers_ms: List[int] = []
    if not samples:
        return energies, centers_ms
    i = 0
    while i + frame <= len(samples):
        chunk = samples[i : i + frame]
        e = math.sqrt(sum(x * x for x in chunk) / float(len(chunk)))
        energies.append(e)
        centers_ms.append(int(round(1000.0 * (i + frame * 0.5) / float(sample_rate))))
        i += hop
    return energies, centers_ms
