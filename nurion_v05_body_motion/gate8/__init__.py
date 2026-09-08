"""v0.5 Gate 8 — Determinism (8A) & Cross-Asset (8B)."""

from .cross_asset import Gate8BResult, combine_gate8_verdict, run_gate8b
from .parameters import GATE8_PARAMETERS, parameter_hash
from .regression import Gate8AResult, run_gate8a

__all__ = [
    "GATE8_PARAMETERS",
    "parameter_hash",
    "Gate8AResult",
    "Gate8BResult",
    "run_gate8a",
    "run_gate8b",
    "combine_gate8_verdict",
]
