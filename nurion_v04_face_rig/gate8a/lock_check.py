"""Gate8A lock verification."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict

from .parameters import (
    GATE1_FROZEN,
    GATE2_FROZEN,
    GATE3_FROZEN,
    GATE4_FROZEN,
    GATE5A1_FROZEN,
    GATE5A2_FROZEN,
    GATE5B_FROZEN,
    GATE6_FROZEN,
    GATE7_FROZEN,
    V03_RC1_SHA256,
)


def verify_all_locked(root: Path) -> Dict:
    from nurion_v04_face_rig.gate1.parameters import parameter_hash as g1
    from nurion_v04_face_rig.gate2.parameters import parameter_hash as g2
    from nurion_v04_face_rig.gate3.parameters import parameter_hash as g3
    from nurion_v04_face_rig.gate4.parameters import parameter_hash as g4
    from nurion_v04_face_rig.gate5a.parameters import parameter_hash as g5a1
    from nurion_v04_face_rig.gate5a2.parameters import parameter_hash as g5a2
    from nurion_v04_face_rig.gate5b.parameters import parameter_hash as g5b
    from nurion_v04_face_rig.gate6.parameters import parameter_hash as g6
    from nurion_v04_face_rig.gate7.parameters import parameter_hash as g7

    pkg = Path(root) / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
    v03 = hashlib.sha256(pkg.read_bytes()).hexdigest() if pkg.exists() else ""
    pairs = {
        "v03": (v03, V03_RC1_SHA256),
        "gate1": (g1(), GATE1_FROZEN),
        "gate2": (g2(), GATE2_FROZEN),
        "gate3": (g3(), GATE3_FROZEN),
        "gate4": (g4(), GATE4_FROZEN),
        "gate5a1": (g5a1(), GATE5A1_FROZEN),
        "gate5a2": (g5a2(), GATE5A2_FROZEN),
        "gate5b": (g5b(), GATE5B_FROZEN),
        "gate6": (g6(), GATE6_FROZEN),
        "gate7": (g7(), GATE7_FROZEN),
    }
    status = {k: ("UNCHANGED" if a == b else "CHANGED") for k, (a, b) in pairs.items()}
    status["gateParamChange"] = 0 if all(v == "UNCHANGED" for v in status.values()) else 1
    status["hashes"] = {k: a for k, (a, b) in pairs.items()}
    return status
