"""v0.4 Gate 5A.2 — Human Speech Alignment Improvement."""

from .parameters import GATE5A2_PARAMETERS, parameter_hash

__all__ = ["GATE5A2_PARAMETERS", "parameter_hash", "run_jobs"]


def run_jobs(*args, **kwargs):
    from .integration import run_jobs as _run

    return _run(*args, **kwargs)
