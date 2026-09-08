"""Gate 5 — Motion Preset."""

from .parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETERS,
    parameter_hash,
)
from .presets import Gate5Result, classify_preset_sources, run_gate5_presets

__all__ = [
    "GATE1_PARAMETER_HASH_FROZEN",
    "GATE2_PARAMETER_HASH_FROZEN",
    "GATE3_PARAMETER_HASH_FROZEN",
    "GATE4_PARAMETER_HASH_FROZEN",
    "GATE5_PARAMETERS",
    "parameter_hash",
    "Gate5Result",
    "classify_preset_sources",
    "run_gate5_presets",
]
