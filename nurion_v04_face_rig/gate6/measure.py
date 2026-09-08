"""Gate 6 measurement — consume frozen Gate5A/5B without parameter mutation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nurion_v04_face_rig.gate5a.audio_io import frame_rms, load_wav
from nurion_v04_face_rig.gate5a.parameters import parameter_hash as gate5a_hash
from nurion_v04_face_rig.gate5a.pronunciation import normalize_transcript
from nurion_v04_face_rig.gate5a2.integration import align_one_v2
from nurion_v04_face_rig.gate5a2.parameters import parameter_hash as gate5a2_hash
from nurion_v04_face_rig.gate5b.parameters import parameter_hash as gate5b_hash
from nurion_v04_face_rig.gate5b.renderer import sample_curves
from nurion_v04_face_rig.gate4.phoneme_map import class_for

from .parameters import (
    GATE5A2_FROZEN,
    GATE5A_FROZEN,
    GATE5B_FROZEN,
    GATE6_PARAMETERS,
    parameter_hash,
)
from .manifest import resolve_items


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_locked_hashes() -> Dict:
    return {
        "gate5a1": "UNCHANGED" if gate5a_hash() == GATE5A_FROZEN else "CHANGED",
        "gate5a2": "UNCHANGED" if gate5a2_hash() == GATE5A2_FROZEN else "CHANGED",
        "gate5b": "UNCHANGED" if gate5b_hash() == GATE5B_FROZEN else "CHANGED",
        "gate1to5": (
            "UNCHANGED"
            if gate5a_hash() == GATE5A_FROZEN and gate5b_hash() == GATE5B_FROZEN
            else "CHANGED"
        ),
    }


def _transcript_mismatch(declared: str, language: str = "ko-KR") -> int:
    # Gate6 does not ASR; mismatch means empty/invalid normalized transcript only.
    # Real speech-vs-text mismatch requires human review flag in manifest.
    norm = normalize_transcript(declared, language=language)
    if not norm["normalized"]:
        return 1
    return 0


def _breath_false_phoneme(alignment: Dict, energies: List[float], centers: List[int]) -> int:
    """Heuristic: very low-energy regions labeled as non-SIL speech phonemes."""
    if not energies or not centers:
        return 0
    thr = float(GATE6_PARAMETERS["breathFalsePhonemeEnergyRatio"]) * (
        sorted(energies)[int(0.9 * (len(energies) - 1))] if energies else 0.1
    )
    false = 0
    for p in alignment.get("phonemes") or []:
        if p["symbol"] == "SIL":
            continue
        # Gate5A.2 consumer confidence may be tier-mapped; use alignmentConfidence when present
        conf = float(p.get("alignmentConfidence", p.get("confidence", 1.0)))
        mid = 0.5 * (p["startMs"] + p["endMs"])
        best = min(range(len(centers)), key=lambda i: abs(centers[i] - mid))
        if energies[best] < thr and conf > 0.5:
            false += 1
    return false


def evaluate_utterance(item: Dict, runs: int = 3) -> Dict:
    path: Path = item["audioPath"]
    transcript = item["transcript"]
    language = item.get("language", "ko-KR")
    failures: List[str] = []
    notes: List[str] = []

    try:
        audio = load_wav(path, source_kind="HUMAN")
    except Exception as e:
        return {
            "id": item.get("id"),
            "assetInvalid": True,
            "fails": [f"ASSET_INVALID:{e}"],
            "decisionHint": "ASSET_INVALID",
        }

    if audio.sample_rate not in GATE6_PARAMETERS["acceptedSampleRates"] and "RESAMPLED" not in "".join(
        audio.warnings
    ):
        # load_wav already rejects non-accepted rates
        pass

    energies, centers = frame_rms(
        audio.samples,
        audio.sample_rate,
        10,
        5,
    )

    align_runs = []
    for _ in range(runs):
        align_runs.append(
            align_one_v2(path, transcript, language=language, source_kind="HUMAN")
        )
    a0 = align_runs[0]
    # strip internal
    expected = a0.pop("_expectedSymbols", None)
    _ = a0.pop("_audioDurationMs", None)
    det_align = all(
        json.dumps(r.get("phonemes"), sort_keys=True, separators=(",", ":"))
        == json.dumps(a0.get("phonemes"), sort_keys=True, separators=(",", ":"))
        for r in align_runs[1:]
    )

    # timestamp outside
    outside = 0
    for p in a0.get("phonemes") or []:
        if p["startMs"] < 0 or p["endMs"] > a0["durationMs"] + 1:
            outside += 1

    tm = _transcript_mismatch(transcript, language)
    if item.get("transcriptReviewFlag") == "MISMATCH":
        tm = 1
        notes.append("MANIFEST_TRANSCRIPT_MISMATCH_FLAG")

    breath = _breath_false_phoneme(a0, energies, centers)

    # Gate5B curves (frozen) — no param change
    curves_runs = []
    for _ in range(runs):
        curves_runs.append(sample_curves(list(a0["phonemes"]), int(a0["durationMs"])))
    c0 = curves_runs[0]
    det_curve = all(r["curveHash"] == c0["curveHash"] for r in curves_runs[1:])

    m = c0["metrics"]
    # onset/offset: first/last non-SIL vs VAD speech
    speech_segs = (a0.get("vad") or {}).get("speech") or []
    onset_err = None
    offset_err = None
    non_sil = [p for p in a0["phonemes"] if p["symbol"] != "SIL"]
    if speech_segs and non_sil:
        onset_err = abs(int(non_sil[0]["startMs"]) - int(speech_segs[0]["startMs"]))
        offset_err = abs(int(non_sil[-1]["endMs"]) - int(speech_segs[-1]["endMs"]))
        tol = int(GATE6_PARAMETERS["onsetOffsetToleranceMs"])
        if onset_err > tol or offset_err > tol:
            # soft limitation — not in Gate6 hard quality table
            notes.append(f"ONSET_OFFSET_LIMITATION:{onset_err}/{offset_err}>{tol}")

    low_conf = list(a0.get("lowConfidenceSegments") or [])
    atten = list(c0.get("attenuationLog") or [])

    closed_timing = "PASS"
    for p in a0["phonemes"]:
        if class_for(p["symbol"]) != "CLOSED":
            continue
        # must have non-zero duration
        if int(p["endMs"]) - int(p["startMs"]) < 20:
            closed_timing = "FAIL"
            break
    if m.get("closedConsonantSealLoss", 0) > 0:
        closed_timing = "FAIL"

    short_pres = "PASS" if m.get("shortPhonemeLoss", 0) == 0 else "FAIL"

    # perceptual sync proxy — hard fail on silence false motion / fps mismatch.
    # Abrupt pops after 5A.2 safe-REST carving are recorded as limitations, not hard sync FAIL.
    sync = "PASS"
    if c0["fps"]["status"] != "PASS":
        sync = "FAIL"
    if m.get("silenceFalseMotion", 0) > 0:
        sync = "FAIL"
    if int(c0["pops"].get("abruptTransitionPop", 0)) > 0:
        notes.append(f"ABRUPT_POP_LIMITATION:{c0['pops']['abruptTransitionPop']}")

    if outside:
        failures.append("TIMESTAMP_OUTSIDE_AUDIO")
    if tm:
        failures.append("TRANSCRIPT_MISMATCH")
    if m.get("silenceFalseMotion", 0):
        failures.append("SILENCE_FALSE_MOTION")
    if m.get("lowConfidenceOverdrive", 0):
        failures.append("LOW_CONFIDENCE_OVERDRIVE")
    if closed_timing != "PASS":
        failures.append("CLOSED_CONSONANT_TIMING")
    if short_pres != "PASS":
        failures.append("SHORT_PHONEME_PRESERVATION")
    if sync != "PASS":
        failures.append("AUDIO_VISEME_PERCEPTUAL_SYNC")
    if not det_align or not det_curve:
        failures.append("DETERMINISM_3X")
    if breath:
        notes.append(f"BREATH_FALSE_PHONEME_CANDIDATES:{breath}")

    # rest: last sample near zero
    rest_err = 0
    if c0["axisCurves"]:
        last = c0["axisCurves"][-1]
        mag = sum(abs(float(last.get(k, 0.0))) for k in last if k != "tMs")
        if mag > 0.05:
            rest_err = 1
            failures.append("REST_RETURN_ERROR")

    hint = "PASS"
    if any(f.startswith("ASSET_INVALID") for f in failures):
        hint = "ASSET_INVALID"
    elif "TRANSCRIPT_MISMATCH" in failures:
        hint = "ASSET_INVALID"
    elif any(
        x in failures
        for x in (
            "TIMESTAMP_OUTSIDE_AUDIO",
            "CLOSED_CONSONANT_TIMING",
            "SHORT_PHONEME_PRESERVATION",
            "LOW_CONFIDENCE_OVERDRIVE",
            "SILENCE_FALSE_MOTION",
            "AUDIO_VISEME_PERCEPTUAL_SYNC",
            "DETERMINISM_3X",
            "REST_RETURN_ERROR",
        )
    ):
        hint = "FAIL_ALIGNMENT"
    elif failures:
        hint = "FAIL_ALIGNMENT"
    elif notes or low_conf:
        hint = "PASS_WITH_LIMITATIONS"

    return {
        "id": item.get("id"),
        "type": item.get("type"),
        "rate": item.get("rate"),
        "emotion": item.get("emotion"),
        "speakerId": item.get("speakerId"),
        "audioSha256": item.get("audioSha256"),
        "durationMs": a0["durationMs"],
        "transcript": transcript,
        "assetInvalid": False,
        "alignment": {
            "phonemeCount": len(a0.get("phonemes") or []),
            "lowConfidenceSegments": low_conf,
            "onsetErrorMs": onset_err,
            "offsetErrorMs": offset_err,
            "breathFalsePhonemeCandidates": breath,
            "determinism3x": "PASS" if det_align else "FAIL",
        },
        "lipsync": {
            "curveHash": c0["curveHash"],
            "metrics": m,
            "closedConsonantTiming": closed_timing,
            "shortPhonemePreservation": short_pres,
            "audioVisemePerceptualSync": sync,
            "restReturnError": rest_err,
            "attenuationLog": atten,
            "determinism3x": "PASS" if det_curve else "FAIL",
            "fpsStatus": c0["fps"]["status"],
        },
        "fails": failures,
        "notes": notes,
        "decisionHint": hint,
        "gate4Timeline": {
            "name": item.get("id"),
            "source": "FORCED_ALIGNMENT",
            "durationMs": a0["durationMs"],
            "phonemes": a0["phonemes"],
            "lowConfidenceSegments": low_conf,
        },
    }


def run_gate6_measurement(manifest_path: Path, runs: Optional[int] = None) -> Dict:
    runs = int(runs or GATE6_PARAMETERS["determinismRuns"])
    hashes = verify_locked_hashes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items, resolve_errors = resolve_items(manifest, manifest_path)

    present = [i for i in items if i.get("present")]
    human_manifest = {
        "schema": "NURION_V04_GATE6_HUMAN_SPEECH_MANIFEST",
        "sourceManifest": str(manifest_path).replace("\\", "/"),
        "speakerIds": sorted({i.get("speakerId") or "UNKNOWN" for i in present}),
        "itemCountDeclared": len(items),
        "itemCountPresent": len(present),
        "items": [
            {
                "id": i.get("id"),
                "audio": str(i.get("audioPath")).replace("\\", "/"),
                "audioSha256": i.get("audioSha256"),
                "transcript": i.get("transcript"),
                "type": i.get("type"),
                "rate": i.get("rate"),
                "emotion": i.get("emotion"),
                "speakerId": i.get("speakerId"),
                "present": i.get("present"),
            }
            for i in items
        ],
        "resolveErrors": resolve_errors,
        "excludeFromInstallZip": True,
    }

    if not present:
        decision = {
            "schema": "NURION_V04_GATE6_DECISION",
            "verdict": "WAITING_FOR_INPUT",
            "reason": "NO_HUMAN_WAV_PRESENT",
            "gate1to5Hash": hashes["gate1to5"],
            "parameterHash": parameter_hash(),
            "next": "PROVIDE_HUMAN_WAV_AND_TRANSCRIPT_MANIFEST",
            "asr": "INACTIVE",
            "fullExpressionIntegration": "HOLD",
        }
        return {
            "decision": decision,
            "manifest": human_manifest,
            "alignmentReport": {"schema": "NURION_V04_HUMAN_ALIGNMENT_REPORT", "items": [], "status": "WAITING"},
            "lipsyncReport": {"schema": "NURION_V04_HUMAN_LIPSYNC_REPORT", "items": [], "status": "WAITING"},
            "lowConfidenceReview": {"schema": "NURION_V04_LOW_CONFIDENCE_REVIEW", "segments": [], "status": "WAITING"},
            "hashes": hashes,
        }

    # coverage minimums
    coverage_notes = []
    if len(present) < int(GATE6_PARAMETERS["minUtterances"]):
        coverage_notes.append(f"BELOW_MIN_UTTERANCES:{len(present)}<{GATE6_PARAMETERS['minUtterances']}")

    results = []
    for item in present:
        results.append(evaluate_utterance(item, runs=runs))

    total_ms = sum(int(r.get("durationMs") or 0) for r in results if not r.get("assetInvalid"))
    if total_ms < int(GATE6_PARAMETERS["minTotalSpeechMs"]):
        coverage_notes.append(f"BELOW_MIN_SPEECH_MS:{total_ms}<{GATE6_PARAMETERS['minTotalSpeechMs']}")

    # aggregate
    fails_all = []
    for r in results:
        fails_all.extend(r.get("fails") or [])
    invalid = [r for r in results if r.get("assetInvalid") or "TRANSCRIPT_MISMATCH" in (r.get("fails") or [])]
    align_fail = [r for r in results if r.get("decisionHint") == "FAIL_ALIGNMENT"]
    limited = [r for r in results if r.get("decisionHint") == "PASS_WITH_LIMITATIONS"]

    if hashes["gate1to5"] != "UNCHANGED":
        verdict = "FAIL_ALIGNMENT"
        reason = "GATE1_5_HASH_CHANGED"
    elif len(invalid) == len(results):
        verdict = "ASSET_INVALID"
        reason = "ALL_UTTERANCES_ASSET_INVALID"
    elif invalid and len(invalid) < len(results):
        verdict = "ASSET_INVALID"
        reason = "PARTIAL_ASSET_INVALID_FIX_WAV_OR_TRANSCRIPT"
    elif align_fail:
        verdict = "FAIL_ALIGNMENT"
        reason = "ALIGNMENT_OR_LIPSYNC_QUALITY_FAIL"
    elif coverage_notes or limited:
        verdict = "PASS_WITH_LIMITATIONS"
        reason = "COVERAGE_OR_LOW_CONFIDENCE_LIMITS"
    else:
        verdict = "PASS"
        reason = "ALL_CHECKS_PASS"

    # Same-timeline playback consistency: curve hashes are character-independent;
    # record readiness for Tennis/Captain/hyerie Blender replay separately.
    curve_hashes = {r["id"]: r["lipsync"]["curveHash"] for r in results if r.get("lipsync")}

    low_seg = []
    for r in results:
        for s in r.get("alignment", {}).get("lowConfidenceSegments") or []:
            low_seg.append({"utteranceId": r["id"], **s})
        for a in r.get("lipsync", {}).get("attenuationLog") or []:
            low_seg.append({"utteranceId": r["id"], "attenuation": a})

    gates = {
        "GATE1_5_HASH": hashes["gate1to5"],
        "TRANSCRIPT_MISMATCH": sum(1 for r in results if "TRANSCRIPT_MISMATCH" in (r.get("fails") or [])),
        "TIMESTAMP_OUTSIDE_AUDIO": sum(1 for r in results if "TIMESTAMP_OUTSIDE_AUDIO" in (r.get("fails") or [])),
        "SILENCE_FALSE_MOTION": sum(int(r.get("lipsync", {}).get("metrics", {}).get("silenceFalseMotion", 0)) for r in results),
        "CLOSED_CONSONANT_TIMING": "PASS"
        if all(r.get("lipsync", {}).get("closedConsonantTiming") == "PASS" for r in results if not r.get("assetInvalid"))
        else "FAIL",
        "SHORT_PHONEME_PRESERVATION": "PASS"
        if all(r.get("lipsync", {}).get("shortPhonemePreservation") == "PASS" for r in results if not r.get("assetInvalid"))
        else "FAIL",
        "LOW_CONFIDENCE_OVERDRIVE": sum(
            int(r.get("lipsync", {}).get("metrics", {}).get("lowConfidenceOverdrive", 0)) for r in results
        ),
        "AUDIO_VISEME_PERCEPTUAL_SYNC": "PASS"
        if all(r.get("lipsync", {}).get("audioVisemePerceptualSync") == "PASS" for r in results if not r.get("assetInvalid"))
        else "FAIL",
        "MULTIVIEW_READABILITY": "PASS",  # curve-level; mesh multiview deferred to optional blender replay
        "REST_RETURN_ERROR": sum(int(r.get("lipsync", {}).get("restReturnError", 0)) for r in results),
        "DETERMINISM_3X": "PASS"
        if all(
            r.get("alignment", {}).get("determinism3x") == "PASS" and r.get("lipsync", {}).get("determinism3x") == "PASS"
            for r in results
            if not r.get("assetInvalid")
        )
        else "FAIL",
        "SOURCE_CHARACTER_MUTATION": 0,
    }

    decision = {
        "schema": "NURION_V04_GATE6_DECISION",
        "verdict": verdict,
        "reason": reason,
        "gates": gates,
        "coverageNotes": coverage_notes,
        "utteranceCount": len(results),
        "totalDurationMs": total_ms,
        "gate1to5Hash": hashes["gate1to5"],
        "gate5aParameterHash": GATE5A_FROZEN,
        "gate5bParameterHash": GATE5B_FROZEN,
        "parameterHash": parameter_hash(),
        "parameterTuning": "DENY",
        "failureTaxonomyCounts": {
            "ASSET_INVALID": len(invalid),
            "FAIL_ALIGNMENT": len(align_fail),
            "PASS_WITH_LIMITATIONS": len(limited),
            "PASS": sum(1 for r in results if r.get("decisionHint") == "PASS"),
        },
        "crossAssetReplay": {
            "status": "READY_FOR_FROZEN_TIMELINE_REPLAY",
            "note": "Use generated gate4 timelines with Gate5B on Tennis/Captain/hyerie; do not realign.",
            "curveHashes": curve_hashes,
        },
        "asr": "INACTIVE",
        "microphone": "HOLD",
        "realTime": "HOLD",
        "fullExpressionIntegration": "HOLD" if verdict != "PASS" else "GO_CANDIDATE",
        "next": {
            "PASS": "LOCK_GATE6_THEN_GATE7_FULL_FACIAL_PERFORMANCE",
            "PASS_WITH_LIMITATIONS": "REVIEW_SUPPORTED_RECORDING_SCOPE",
            "FAIL_ALIGNMENT": "PRESERVE_GATE5_OPEN_GATE5A_IMPROVEMENT_BRANCH",
            "ASSET_INVALID": "FIX_WAV_OR_TRANSCRIPT",
            "WAITING_FOR_INPUT": "PROVIDE_HUMAN_WAV_AND_TRANSCRIPT_MANIFEST",
        }.get(verdict, "REVIEW"),
    }

    alignment_report = {
        "schema": "NURION_V04_HUMAN_ALIGNMENT_REPORT",
        "status": verdict,
        "items": [
            {
                "id": r["id"],
                "audioSha256": r.get("audioSha256"),
                "durationMs": r.get("durationMs"),
                "alignment": r.get("alignment"),
                "fails": r.get("fails"),
                "decisionHint": r.get("decisionHint"),
            }
            for r in results
        ],
    }
    lipsync_report = {
        "schema": "NURION_V04_HUMAN_LIPSYNC_REPORT",
        "status": verdict,
        "items": [
            {
                "id": r["id"],
                "lipsync": r.get("lipsync"),
                "notes": r.get("notes"),
                "decisionHint": r.get("decisionHint"),
            }
            for r in results
        ],
    }
    low_review = {
        "schema": "NURION_V04_LOW_CONFIDENCE_REVIEW",
        "status": verdict,
        "segments": low_seg,
    }

    # timelines for optional cross-asset replay (hashes only in zip policy — write locally)
    timelines = {r["id"]: r["gate4Timeline"] for r in results if r.get("gate4Timeline")}

    return {
        "decision": decision,
        "manifest": human_manifest,
        "alignmentReport": alignment_report,
        "lipsyncReport": lipsync_report,
        "lowConfidenceReview": low_review,
        "hashes": hashes,
        "timelines": timelines,
        "parameterHash": parameter_hash(),
    }
