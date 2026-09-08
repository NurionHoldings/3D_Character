"""v0.4 Gate 8C — Fresh Holdout Validation."""

from .parameters import GATE8C_PARAMETERS, RC1_PACKAGE, RC1_SHA256, parameter_hash
from .holdout_validation import HoldoutResult, run_fresh_holdout

__all__ = [
    "GATE8C_PARAMETERS",
    "RC1_PACKAGE",
    "RC1_SHA256",
    "parameter_hash",
    "HoldoutResult",
    "run_fresh_holdout",
]
