"""v0.3a Face Landmark Detection (Alpha1: core 13 points)."""

from .keys import ALPHA1_CORE_KEYS, FACE_LANDMARK_KEYS, FACE_LANDMARK_KEYS_FULL
from .parameters import FACE_ALPHA1_PARAMETER_HASH, FACE_ALPHA1_PARAMETERS, parameter_hash

__all__ = [
    "ALPHA1_CORE_KEYS",
    "FACE_LANDMARK_KEYS",
    "FACE_LANDMARK_KEYS_FULL",
    "FACE_ALPHA1_PARAMETERS",
    "FACE_ALPHA1_PARAMETER_HASH",
    "parameter_hash",
]


def __getattr__(name: str):
    if name == "correct_face_landmarks":
        from .correct import correct_face_landmarks

        return correct_face_landmarks
    raise AttributeError(name)
