"""Load frozen Gate5A timelines without mutation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def load_gate5a_timelines(timelines_dir: Path) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for path in sorted(timelines_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        # defensive copy — never mutate file contents in memory shared refs
        phonemes = [
            {
                "symbol": str(p["symbol"]),
                "startMs": int(p["startMs"]),
                "endMs": int(p["endMs"]),
                "confidence": float(p.get("confidence", 1.0)),
            }
            for p in doc.get("phonemes") or []
        ]
        out[path.stem] = {
            "name": doc.get("name", path.stem),
            "source": doc.get("source", "FORCED_ALIGNMENT"),
            "durationMs": int(doc.get("durationMs", phonemes[-1]["endMs"] if phonemes else 0)),
            "phonemes": phonemes,
            "lowConfidenceSegments": list(doc.get("lowConfidenceSegments") or []),
            "path": str(path).replace("\\", "/"),
        }
    return out


def load_alignments(align_dir: Path) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    if not align_dir.exists():
        return out
    for path in sorted(align_dir.glob("*.json")):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return out
