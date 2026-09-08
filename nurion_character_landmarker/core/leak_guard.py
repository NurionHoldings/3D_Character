"""Prevent Ground-Truth bone coordinates from leaking into generation paths."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, List


@dataclass
class LeakGuardState:
    generation_active: bool = False
    gt_access_attempts: List[str] = field(default_factory=list)


_STATE = LeakGuardState()


class GroundTruthLeakError(RuntimeError):
    """Raised when evaluation-only GT bone access occurs during generation."""


@contextmanager
def generation_scope(label: str = "geometry_correction") -> Iterator[None]:
    previous = _STATE.generation_active
    _STATE.generation_active = True
    try:
        yield
    finally:
        _STATE.generation_active = previous


def is_generation_active() -> bool:
    return _STATE.generation_active


def note_gt_access(reason: str) -> None:
    _STATE.gt_access_attempts.append(reason)
    if _STATE.generation_active:
        raise GroundTruthLeakError(f"Ground Truth access during generation: {reason}")


def reset_gt_access_log() -> None:
    _STATE.gt_access_attempts.clear()


def gt_access_log() -> List[str]:
    return list(_STATE.gt_access_attempts)


def assert_no_gt_parameters(**kwargs) -> None:
    forbidden = ("armature", "arm", "bones", "bone_map", "ground_truth", "gt", "truth")
    for key, value in kwargs.items():
        key_l = key.lower()
        if any(token in key_l for token in forbidden) and value is not None:
            raise GroundTruthLeakError(f"Forbidden GT parameter in generation API: {key}")
        # Duck-type: Blender armature object
        if value is not None and getattr(value, "type", None) == "ARMATURE":
            raise GroundTruthLeakError(f"Armature object passed to generation API via {key}")
