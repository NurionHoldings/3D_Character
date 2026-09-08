"""Energy-based VAD (silence / speech segments)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .parameters import GATE5A_PARAMETERS


def detect_segments(energies: List[float], centers_ms: List[int]) -> Dict:
    floor = float(GATE5A_PARAMETERS["vadEnergyFloor"])
    min_speech = int(GATE5A_PARAMETERS["vadMinSpeechMs"])
    min_sil = int(GATE5A_PARAMETERS["vadMinSilenceMs"])
    hop = int(GATE5A_PARAMETERS["hopMs"])

    if not energies:
        return {"speech": [], "silence": [], "speechMask": []}

    mask = [e >= floor for e in energies]
    # morph: close gaps shorter than min_sil, drop speech shorter than min_speech
    # first: fill short silence holes inside speech
    i = 0
    while i < len(mask):
        if mask[i]:
            i += 1
            continue
        j = i
        while j < len(mask) and not mask[j]:
            j += 1
        dur = (j - i) * hop
        left_speech = i > 0 and mask[i - 1]
        right_speech = j < len(mask) and mask[j]
        if left_speech and right_speech and dur < min_sil:
            for k in range(i, j):
                mask[k] = True
        i = j

    # drop short speech islands
    i = 0
    while i < len(mask):
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < len(mask) and mask[j]:
            j += 1
        dur = (j - i) * hop
        if dur < min_speech:
            for k in range(i, j):
                mask[k] = False
        i = j

    def _runs(want: bool) -> List[Dict]:
        out = []
        i = 0
        while i < len(mask):
            if mask[i] != want:
                i += 1
                continue
            j = i
            while j < len(mask) and mask[j] == want:
                j += 1
            start = max(0, centers_ms[i] - hop // 2)
            end = centers_ms[j - 1] + hop // 2
            out.append({"startMs": int(start), "endMs": int(end)})
            i = j
        return out

    return {"speech": _runs(True), "silence": _runs(False), "speechMask": mask}
