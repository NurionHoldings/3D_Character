"""Load Gate6 frozen human timelines — preserve limitation metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def load_gate6_timelines(timelines_dir: Path) -> Dict[str, Dict]:
    """
    Load frozen Gate6 human_gate4_timelines without reinterpretation.
    Preserves rule / alignedSymbol / intensityTier for REST fallback propagation.
    """
    out: Dict[str, Dict] = {}
    for path in sorted(Path(timelines_dir).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        phonemes = []
        for p in doc.get("phonemes") or []:
            row = {
                "symbol": str(p["symbol"]),
                "startMs": int(p["startMs"]),
                "endMs": int(p["endMs"]),
                "confidence": float(p.get("confidence", 1.0)),
            }
            if "alignmentConfidence" in p:
                row["alignmentConfidence"] = float(p["alignmentConfidence"])
            if "alignedSymbol" in p:
                row["alignedSymbol"] = str(p["alignedSymbol"])
            if "intensityTier" in p:
                row["intensityTier"] = str(p["intensityTier"])
            if "rule" in p:
                row["rule"] = str(p["rule"])
            phonemes.append(row)
        out[path.stem] = {
            "name": doc.get("name", path.stem),
            "source": doc.get("source", "FORCED_ALIGNMENT"),
            "durationMs": int(doc.get("durationMs", phonemes[-1]["endMs"] if phonemes else 0)),
            "phonemes": phonemes,
            "lowConfidenceSegments": list(doc.get("lowConfidenceSegments") or []),
            "path": str(path).replace("\\", "/"),
        }
    return out
