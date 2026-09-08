"""v0.4 Gate 8A — Full Limited Integration Regression."""

from .parameters import GATE8A_PARAMETERS, parameter_hash
from .regression import Gate8AResult, run_gate8a

__all__ = ["GATE8A_PARAMETERS", "parameter_hash", "Gate8AResult", "run_gate8a"]
