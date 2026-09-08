"""Gate 5A integration — offline forced alignment pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .audio_io import frame_rms, load_wav
from .contract import build_alignment_document, to_gate4_timeline
from .forced_align import forced_align
from .parameters import GATE5A_PARAMETERS, parameter_hash
from .pronunciation import apply_pronunciation, normalize_transcript
from .vad import detect_segments
from .validator import validate_alignment


@dataclass
class Gate5AResult:
    verdict: str
    parameter_hash: str
    alignments: Dict[str, Dict]
    gate4_timelines: Dict[str, Dict]
    validation: Dict
    profile: Dict
    notes: List[str]


def align_one(
    audio_path: Path,
    transcript: str,
    language: str = "ko-KR",
    source_kind: str = "UNKNOWN",
) -> Dict:
    audio = load_wav(audio_path, source_kind=source_kind)
    energies, centers = frame_rms(
        audio.samples,
        audio.sample_rate,
        int(GATE5A_PARAMETERS["frameMs"]),
        int(GATE5A_PARAMETERS["hopMs"]),
    )
    vad = detect_segments(energies, centers)
    norm = normalize_transcript(transcript, language=language)
    pron = apply_pronunciation(norm["normalized"])
    pron["normalized"] = norm["normalized"]
    aligned = forced_align(
        pron["tokens"],
        energies,
        centers,
        vad["speech"],
        audio.duration_ms,
    )
    doc = build_alignment_document(
        audio_path=audio.path,
        transcript=transcript,
        language=language,
        duration_ms=audio.duration_ms,
        phonemes=aligned["phonemes"],
        low_confidence=aligned["lowConfidenceSegments"],
        source_kind=source_kind,
        warnings=list(audio.warnings),
        pronunciation=pron,
        vad=vad,
    )
    doc["_expectedSymbols"] = pron["phonemes"]
    doc["_audioDurationMs"] = audio.duration_ms
    return doc


def run_gate5a(
    jobs: List[Dict],
    runs: Optional[int] = None,
) -> Gate5AResult:
    runs = int(runs or GATE5A_PARAMETERS["determinismRuns"])
    notes: List[str] = []
    alignments: Dict[str, Dict] = {}
    gate4: Dict[str, Dict] = {}
    per_item_val: Dict[str, Dict] = {}

    det_ok = True
    for job in jobs:
        jid = job["id"]
        path = Path(job["audio"])
        transcript = job["transcript"]
        language = job.get("language", "ko-KR")
        kind = job.get("sourceKind", "UNKNOWN")

        results = []
        for _ in range(runs):
            results.append(align_one(path, transcript, language=language, source_kind=kind))
        # determinism: identical phoneme timing JSON
        payload0 = json.dumps(results[0]["phonemes"], sort_keys=True, separators=(",", ":"))
        for r in results[1:]:
            if json.dumps(r["phonemes"], sort_keys=True, separators=(",", ":")) != payload0:
                det_ok = False
                notes.append(f"DETERMINISM_FAIL:{jid}")
                break

        doc = results[0]
        expected = doc.pop("_expectedSymbols", None)
        duration = doc.pop("_audioDurationMs", doc["durationMs"])
        val = validate_alignment(doc, duration, expected_symbols=expected)
        per_item_val[jid] = val
        alignments[jid] = doc
        gate4[jid] = to_gate4_timeline(jid, doc)

    fails = []
    gates_agg = {
        "SOURCE_MUTATION": 0,
        "GATE1_4_HASH": "UNCHANGED",
        "AUDIO_DURATION_MISMATCH": 0,
        "PHONEME_ORDER_ERROR": 0,
        "TIMESTAMP_OUTSIDE_AUDIO": 0,
        "SHORT_PHONEME_LOSS": 0,
        "SILENCE_FALSE_MOTION": 0,
        "LOW_CONFIDENCE_OVERDRIVE": 0,
        "DETERMINISM_3X": "PASS" if det_ok else "FAIL",
    }
    for jid, val in per_item_val.items():
        g = val["gates"]
        for k in (
            "AUDIO_DURATION_MISMATCH",
            "PHONEME_ORDER_ERROR",
            "TIMESTAMP_OUTSIDE_AUDIO",
            "SHORT_PHONEME_LOSS",
        ):
            gates_agg[k] = max(gates_agg[k], int(g.get(k, 0)))
        if g.get("GATE1_4_HASH") != "UNCHANGED":
            gates_agg["GATE1_4_HASH"] = "CHANGED"
        fails.extend([f"{jid}:{f}" for f in val.get("fails") or []])

    if gates_agg["DETERMINISM_3X"] != "PASS":
        fails.append("DETERMINISM_3X")
    if gates_agg["GATE1_4_HASH"] != "UNCHANGED":
        fails.append("GATE1_4_HASH")

    hard = [
        "AUDIO_DURATION_MISMATCH",
        "PHONEME_ORDER_ERROR",
        "TIMESTAMP_OUTSIDE_AUDIO",
        "SHORT_PHONEME_LOSS",
    ]
    verdict = "PASS"
    if fails or gates_agg["DETERMINISM_3X"] != "PASS" or gates_agg["GATE1_4_HASH"] != "UNCHANGED":
        for k in hard:
            if gates_agg[k]:
                verdict = "FAIL"
                break
        if gates_agg["DETERMINISM_3X"] != "PASS" or gates_agg["GATE1_4_HASH"] != "UNCHANGED":
            verdict = "FAIL"
        if fails and verdict == "PASS":
            verdict = "FAIL"

    validation = {
        "schema": "NURION_V04_GATE5A_VALIDATION",
        "verdict": verdict,
        "gates": gates_agg,
        "fails": sorted(set(fails)),
        "items": per_item_val,
        "gate5b": "HOLD",
    }
    profile = {
        "schema": "NURION_V04_GATE5A_PROFILE",
        "parameterHash": parameter_hash(),
        "alignerModel": GATE5A_PARAMETERS["alignerModel"],
        "alignerModelVersion": GATE5A_PARAMETERS["alignerModelVersion"],
        "koreanPronunciationRuleset": GATE5A_PARAMETERS["koreanPronunciationRuleset"],
        "audioDecoder": GATE5A_PARAMETERS["audioDecoder"],
        "normalizationPolicy": GATE5A_PARAMETERS["normalizationPolicy"],
        "jobCount": len(jobs),
        "utteranceIds": [j["id"] for j in jobs],
        "sourceKinds": sorted({j.get("sourceKind", "UNKNOWN") for j in jobs}),
    }
    return Gate5AResult(
        verdict=verdict,
        parameter_hash=parameter_hash(),
        alignments=alignments,
        gate4_timelines=gate4,
        validation=validation,
        profile=profile,
        notes=notes,
    )
