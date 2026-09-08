"""FAST-04 — Facial performance runtime orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fast_track.runtime.actuator_runtime import ActuatorRuntime, ALL_ACTUATORS
from fast_track.runtime.coarticulation import blend_cues_at
from fast_track.runtime.lip_sync_resolver import resolve_cues
from fast_track.runtime.narration_timeline import NarrationTimeline, build_timeline, detect_speech_segments, read_wav_mono, rms_envelope
from fast_track.runtime.secondary_motion import SecondaryMotionLayer


class FacialPerformanceRuntime:
    """Audio-master-clock narration → morph actuator runtime."""

    def __init__(
        self,
        morph_json: Path,
        audio_path: Path,
        transcript: str,
    ):
        self.actuators = ActuatorRuntime(morph_json)
        self.audio_path = audio_path
        self.transcript = transcript

        samples, sr = read_wav_mono(audio_path)
        self.duration = len(samples) / sr
        times, rms = rms_envelope(samples, sr)
        segments = detect_speech_segments(times, rms)
        cues = resolve_cues(transcript, segments)
        self.timeline = build_timeline(audio_path, cues, transcript)
        speech_end = segments[-1].end if segments else self.duration
        speech_start = segments[0].start if segments else 0.0
        self.secondary = SecondaryMotionLayer(speech_start, speech_end)

    def sample(self, t: float) -> dict[str, float]:
        speech_end = self.timeline.segments[-1].end if self.timeline.segments else self.duration
        speech_start = self.timeline.segments[0].start if self.timeline.segments else 0.0
        mouth, _clamped = blend_cues_at(self.timeline.cues, t, self.audio_path, speech_start, speech_end)
        weights = {k: 0.0 for k in ALL_ACTUATORS}
        weights.update(mouth)
        weights = self.secondary.apply_to_weights(weights, t)
        return weights

    def apply_at(self, t: float, base_positions) -> tuple[dict[str, float], Any]:
        weights = self.sample(t)
        self.actuators.reset_all()
        for k, w in weights.items():
            self.actuators.set_weight(k, w)
        deformed = self.actuators.apply_to_base(base_positions)
        return weights, deformed

    def simulate(self, fps: float = 30.0) -> list[dict[str, Any]]:
        dt = 1.0 / fps
        frames: list[dict[str, Any]] = []
        t = 0.0
        clamp_events = 0
        while t <= self.duration + dt:
            speech_end = self.timeline.segments[-1].end if self.timeline.segments else self.duration
            speech_start = self.timeline.segments[0].start if self.timeline.segments else 0.0
            mouth, clamped = blend_cues_at(self.timeline.cues, t, self.audio_path, speech_start, speech_end)
            if clamped:
                clamp_events += 1
            w = self.secondary.apply_to_weights({**{k: 0.0 for k in ALL_ACTUATORS}, **mouth}, t)
            frames.append({"timeSec": round(t, 4), "weights": w, "clampEvent": clamped})
            t += dt
        self._clamp_events = clamp_events
        return frames

    def post_narration_neutral_check(self, fps: float = 30.0, tail_sec: float = 0.25) -> dict[str, Any]:
        """All presentation weights must be exact zero after narration ends."""
        t0 = self.duration + tail_sec
        samples = [self.sample(t0 + i * 0.01) for i in range(5)]
        max_w = max(max(abs(w) for w in s.values()) for s in samples)
        return {
            "checkTimeSec": t0,
            "maxAbsWeight": max_w,
            "pass": max_w == 0.0,
            "contract": "POST_NARRATION_NEUTRAL_PARITY_EXACT_ZERO",
        }

    def export_timeline(self, path: Path) -> None:
        path.write_text(json.dumps(self.timeline.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
