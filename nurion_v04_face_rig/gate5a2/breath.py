"""Breath / low-energy non-speech separation for Gate5A.2."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .parameters import GATE5A2_PARAMETERS


def classify_energy_regions(
    energies: List[float],
    centers_ms: List[int],
    speech_segments: List[Dict],
) -> Dict:
    """
    Split frames into speech / breath / silence.
    Breath: inside or near speech timeline but energy below breath threshold for >= breathMinMs.
    """
    if not energies or not centers_ms:
        return {"speechMs": [], "breathSegments": [], "silenceMs": []}

    peak = max(energies) if energies else 1.0
    breath_thr = float(GATE5A2_PARAMETERS["breathEnergyRatio"]) * max(peak, 1e-6)
    speech_floor = float(GATE5A2_PARAMETERS["vadEnergyFloor"])
    min_breath = int(GATE5A2_PARAMETERS["breathMinMs"])
    hop = int(GATE5A2_PARAMETERS["hopMs"])

    # speech mask from VAD segments
    speech_mask = [False] * len(centers_ms)
    for seg in speech_segments:
        for i, c in enumerate(centers_ms):
            if int(seg["startMs"]) <= c < int(seg["endMs"]):
                speech_mask[i] = True

    labels = []
    for i, e in enumerate(energies):
        if not speech_mask[i] and e < speech_floor:
            labels.append("SIL")
        elif e < breath_thr:
            labels.append("BREATH")
        else:
            labels.append("SPEECH")

    # morph short BREATH inside SPEECH (< min) back to SPEECH (consonant dips)
    i = 0
    while i < len(labels):
        if labels[i] != "BREATH":
            i += 1
            continue
        j = i
        while j < len(labels) and labels[j] == "BREATH":
            j += 1
        dur = (j - i) * hop
        left = i > 0 and labels[i - 1] == "SPEECH"
        right = j < len(labels) and labels[j] == "SPEECH"
        if dur < min_breath and (left or right):
            for k in range(i, j):
                labels[k] = "SPEECH"
        i = j

    breath_segments: List[Dict] = []
    speech_ms: List[int] = []
    i = 0
    while i < len(labels):
        lab = labels[i]
        j = i
        while j < len(labels) and labels[j] == lab:
            j += 1
        start = max(0, centers_ms[i] - hop // 2)
        end = centers_ms[j - 1] + hop // 2
        if lab == "BREATH":
            if end - start >= min_breath:
                breath_segments.append({"startMs": int(start), "endMs": int(end), "kind": "BREATH"})
            else:
                # too short → keep as speech mass
                for ms in range(int(start), int(end)):
                    speech_ms.append(ms)
        elif lab == "SPEECH":
            for ms in range(int(start), int(end)):
                speech_ms.append(ms)
        i = j

    speech_ms = sorted(set(speech_ms))
    return {"speechMs": speech_ms, "breathSegments": breath_segments, "labels": labels}
