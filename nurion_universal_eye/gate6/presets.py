"""Beauty color presets — separated from engine gaze/blink coordinates."""

from __future__ import annotations

from typing import Dict

# Teal/cyan ABA-leaning candidates; NATURAL is the universal engine default.
COLOR_PRESETS: Dict[str, Dict] = {
    "NATURAL": {
        "label": "realistic_low_emission",
        "sclera": (0.92, 0.93, 0.94),
        "irisInner": (0.22, 0.42, 0.48),
        "irisOuter": (0.12, 0.28, 0.34),
        "limbal": (0.05, 0.08, 0.10),
        "pupil": (0.02, 0.02, 0.03),
        "corneaTint": (0.85, 0.92, 0.95),
        "catchlight": (0.98, 0.99, 1.0),
        "roughnessIris": 0.45,
        "roughnessCornea": 0.08,
        "clearcoat": 0.35,
    },
    "LUMINOUS": {
        "label": "clear_luminous_iris",
        "sclera": (0.94, 0.96, 0.97),
        "irisInner": (0.28, 0.62, 0.70),
        "irisOuter": (0.14, 0.40, 0.52),
        "limbal": (0.06, 0.12, 0.16),
        "pupil": (0.015, 0.02, 0.03),
        "corneaTint": (0.90, 0.96, 0.99),
        "catchlight": (1.0, 1.0, 1.0),
        "roughnessIris": 0.32,
        "roughnessCornea": 0.05,
        "clearcoat": 0.55,
    },
    "AI_PREMIUM": {
        "label": "restrained_teal_ai",
        "sclera": (0.90, 0.93, 0.95),
        "irisInner": (0.18, 0.55, 0.62),
        "irisOuter": (0.08, 0.32, 0.42),
        "limbal": (0.04, 0.10, 0.14),
        "pupil": (0.02, 0.025, 0.035),
        "corneaTint": (0.82, 0.94, 0.96),
        "catchlight": (0.95, 0.98, 1.0),
        "roughnessIris": 0.38,
        "roughnessCornea": 0.06,
        "clearcoat": 0.48,
    },
}


def get_preset(name: str) -> Dict:
    key = str(name).upper()
    if key not in COLOR_PRESETS:
        raise ValueError(f"Unknown beauty preset: {name}")
    return COLOR_PRESETS[key]
