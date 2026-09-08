"""Gate 6 — Blender user workflow operators."""

from .parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETER_HASH_FROZEN,
    GATE6_PARAMETERS,
    parameter_hash,
)
from .workflow import WorkflowEngine, run_policy_scenarios

__all__ = [
    "GATE1_PARAMETER_HASH_FROZEN",
    "GATE2_PARAMETER_HASH_FROZEN",
    "GATE3_PARAMETER_HASH_FROZEN",
    "GATE4_PARAMETER_HASH_FROZEN",
    "GATE5_PARAMETER_HASH_FROZEN",
    "GATE6_PARAMETERS",
    "parameter_hash",
    "WorkflowEngine",
    "run_policy_scenarios",
    "register",
    "unregister",
]


def register():
    from . import operators, panel

    operators.register()
    panel.register()


def unregister():
    from . import operators, panel

    panel.unregister()
    operators.unregister()
