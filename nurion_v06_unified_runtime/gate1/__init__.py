"""Gate 1 — Unified contract and I/O specification."""

from .parameters import GATE1_PARAMETERS, parameter_hash
from .contract import build_contract, validate_sealed_baselines
from .abstain import ABSTAIN_RULES, classify_abstain

__all__ = [
    "GATE1_PARAMETERS",
    "parameter_hash",
    "build_contract",
    "validate_sealed_baselines",
    "ABSTAIN_RULES",
    "classify_abstain",
]
