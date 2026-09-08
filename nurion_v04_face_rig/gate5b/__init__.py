"""v0.4 Gate 5B — Automatic Lip Sync Rendering."""

from .parameters import GATE5B_PARAMETERS, parameter_hash

__all__ = ["GATE5B_PARAMETERS", "parameter_hash", "run_gate5b"]


def run_gate5b(*args, **kwargs):
    from .integration import run_gate5b as _run

    return _run(*args, **kwargs)
