"""Gate 8 — Fresh Holdout and RC candidate."""

from .parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETER_HASH_FROZEN,
    GATE6_PARAMETER_HASH_FROZEN,
    GATE7_PARAMETER_HASH_FROZEN,
    GATE8_PARAMETERS,
    HOLDOUT_LABEL,
    HOLDOUT_ZIP_SHA256,
    parameter_hash,
)
from .holdout import Gate8Result, run_gate8_holdout
from .novelty import evaluate_novelty, extract_withskin_fbx
from .rc_candidate import build_rc_candidate

__all__ = [
    "GATE1_PARAMETER_HASH_FROZEN",
    "GATE2_PARAMETER_HASH_FROZEN",
    "GATE3_PARAMETER_HASH_FROZEN",
    "GATE4_PARAMETER_HASH_FROZEN",
    "GATE5_PARAMETER_HASH_FROZEN",
    "GATE6_PARAMETER_HASH_FROZEN",
    "GATE7_PARAMETER_HASH_FROZEN",
    "GATE8_PARAMETERS",
    "HOLDOUT_LABEL",
    "HOLDOUT_ZIP_SHA256",
    "parameter_hash",
    "Gate8Result",
    "run_gate8_holdout",
    "evaluate_novelty",
    "extract_withskin_fbx",
    "build_rc_candidate",
]
