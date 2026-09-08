"""v0.4 Gate 5A — Offline Speech Alignment."""

from .integration import run_gate5a
from .parameters import GATE5A_PARAMETERS, parameter_hash

__all__ = ["run_gate5a", "GATE5A_PARAMETERS", "parameter_hash"]
