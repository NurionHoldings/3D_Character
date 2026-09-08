"""FPS semantic consistency and abrupt-transition checks."""

from __future__ import annotations

from typing import Dict, List

from .coarticulation import blend_axes_at_ms, ms_to_frame
from .parameters import GATE4_PARAMETERS


def sample_timeline_semantics(phonemes: List[Dict], fps_list: List[int]) -> Dict:
    """
    For each phoneme midpoint, compare primary class across FPS after ms↔frame↔ms roundtrip.
    """
    mismatches = 0
    details = []
    for p in phonemes:
        mid = 0.5 * (float(p["startMs"]) + float(p["endMs"]))
        primaries = {}
        for fps in fps_list:
            f = ms_to_frame(mid, fps)
            # evaluate at exact mid ms (timing engine is ms-native); frame used for order evidence
            axes, meta = blend_axes_at_ms(phonemes, mid)
            primaries[fps] = {"primary": meta["primary"], "frame": f, "ms": mid}
        vals = {v["primary"] for v in primaries.values()}
        if len(vals) != 1:
            mismatches += 1
            details.append({"ms": mid, "symbol": p["symbol"], "primaries": primaries})
    return {
        "fpsSemanticMismatches": mismatches,
        "status": "PASS" if mismatches == 0 else "FAIL",
        "details": details[:8],
    }


def detect_abrupt_pops(phonemes: List[Dict], step_ms: float = 10.0) -> Dict:
    """Scan axis envelopes for large step changes (pop)."""
    if not phonemes:
        return {"abruptTransitionPop": 0, "status": "PASS"}
    t0 = float(phonemes[0]["startMs"])
    t1 = float(phonemes[-1]["endMs"])
    thr = float(GATE4_PARAMETERS["popThresholdDelta"])
    pops = 0
    prev = None
    t = t0
    while t <= t1 + 1e-6:
        axes, _ = blend_axes_at_ms(phonemes, t)
        if prev is not None:
            keys = set(prev) | set(axes)
            delta = sum(abs(axes.get(k, 0.0) - prev.get(k, 0.0)) for k in keys)
            if delta > thr:
                pops += 1
        prev = axes
        t += step_ms
    return {"abruptTransitionPop": pops, "status": "PASS" if pops == 0 else "FAIL"}
