"""Output contracts for Gate 5A and Gate 4 input adapter."""

from __future__ import annotations

from typing import Dict, List

from .parameters import (
    ALIGNER_MODEL,
    ALIGNER_MODEL_VERSION,
    AUDIO_DECODER,
    KOREAN_PRONUNCIATION_RULESET,
    NORMALIZATION_POLICY,
)


def build_alignment_document(
    *,
    audio_path: str,
    transcript: str,
    language: str,
    duration_ms: int,
    phonemes: List[Dict],
    low_confidence: List[Dict],
    source_kind: str,
    warnings: List[str],
    pronunciation: Dict,
    vad: Dict,
) -> Dict:
    return {
        "source": "FORCED_ALIGNMENT",
        "language": language,
        "audio": audio_path,
        "transcript": transcript,
        "durationMs": int(duration_ms),
        "phonemes": phonemes,
        "lowConfidenceSegments": low_confidence,
        "sourceKind": source_kind,
        "alignerModel": ALIGNER_MODEL,
        "alignerModelVersion": ALIGNER_MODEL_VERSION,
        "koreanPronunciationRuleset": KOREAN_PRONUNCIATION_RULESET,
        "audioDecoder": AUDIO_DECODER,
        "normalizationPolicy": NORMALIZATION_POLICY,
        "pronunciation": {
            "normalized": pronunciation.get("normalized"),
            "phonemeSymbols": pronunciation.get("phonemes"),
            "uncertainRules": pronunciation.get("uncertainRules"),
        },
        "vad": {"speech": vad.get("speech"), "silence": vad.get("silence")},
        "warnings": warnings,
    }


def to_gate4_timeline(name: str, alignment: Dict) -> Dict:
    """Gate 4 input contract — same shape as synthetic timelines."""
    return {
        "name": name,
        "source": "FORCED_ALIGNMENT",
        "durationMs": alignment["durationMs"],
        "phonemes": [
            {
                "symbol": p["symbol"],
                "startMs": int(p["startMs"]),
                "endMs": int(p["endMs"]),
                "confidence": float(p["confidence"]),
            }
            for p in alignment["phonemes"]
        ],
        "lowConfidenceSegments": list(alignment.get("lowConfidenceSegments") or []),
    }
