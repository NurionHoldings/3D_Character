"""Model-agnostic geometry-first analysis core for Gate 3.

The injected backend owns face detection and dense landmark inference.  This
module never infers face existence from skin colour, image mean, or centre
occupancy and never downloads a model at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image


BRANCHES = ("ORIGINAL_RGB", "LUMINANCE", "GRAYSCALE", "GRAYSCALE_CLAHE")
LEFT_EYE, RIGHT_EYE = 33, 263
FOREHEAD, CHIN, NOSE = 10, 152, 1
CHEEK_L, CHEEK_R = 234, 454
MOUTH_L, MOUTH_R = 61, 291
JAW_L, JAW_R = 172, 397


class DenseFaceBackend(Protocol):
    name: str

    def infer(self, image: np.ndarray, branch: str) -> np.ndarray | None:
        """Return exactly 478 normalized x/y/z landmarks or None."""


@dataclass(frozen=True)
class AnalysisResult:
    outcome: str
    successful_branches: tuple[str, ...]
    landmarks: np.ndarray | None
    geometry: dict[str, float]
    pose: dict[str, float]
    median_branch_disagreement: float | None
    p95_branch_disagreement: float | None
    skin_policy: str
    disclosures: tuple[str, ...]


def _to_rgb_array(image: Image.Image | np.ndarray) -> np.ndarray:
    if isinstance(image, Image.Image):
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    else:
        arr = np.asarray(image)
        if arr.ndim == 2:
            rgb = np.repeat(arr[..., None], 3, axis=2)
        elif arr.ndim == 3 and arr.shape[2] in (3, 4):
            rgb = arr[..., :3]
        else:
            raise ValueError("UNSUPPORTED_IMAGE_SHAPE")
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    if min(rgb.shape[:2]) < 64:
        raise ValueError("IMAGE_TOO_SMALL")
    return rgb.copy()


def _gray(rgb: np.ndarray) -> np.ndarray:
    return np.clip(0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2], 0, 255).astype(np.uint8)


def _equalize(gray: np.ndarray) -> np.ndarray:
    # Deterministic global equalization used as a dependency-free CLAHE proxy
    # in synthetic validation. Production backend must provide pinned CLAHE.
    hist = np.bincount(gray.ravel(), minlength=256)
    cdf = hist.cumsum()
    nonzero = cdf[cdf > 0]
    if not len(nonzero) or cdf[-1] == nonzero[0]:
        return gray.copy()
    lut = np.clip((cdf - nonzero[0]) * 255.0 / (cdf[-1] - nonzero[0]), 0, 255).astype(np.uint8)
    return lut[gray]


def make_representations(image: Image.Image | np.ndarray) -> dict[str, np.ndarray]:
    rgb = _to_rgb_array(image)
    gray = _gray(rgb)
    luminance = np.repeat(gray[..., None], 3, axis=2)
    equalized = np.repeat(_equalize(gray)[..., None], 3, axis=2)
    return {
        "ORIGINAL_RGB": rgb,
        "LUMINANCE": luminance,
        "GRAYSCALE": luminance.copy(),
        "GRAYSCALE_CLAHE": equalized,
    }


def _validate_landmarks(points: np.ndarray | None) -> np.ndarray | None:
    if points is None:
        return None
    value = np.asarray(points, dtype=np.float64)
    if value.shape != (478, 3) or not np.isfinite(value).all():
        return None
    if (value[:, :2] < -0.1).any() or (value[:, :2] > 1.1).any():
        return None
    return value


def _normalize(points: np.ndarray) -> tuple[np.ndarray, float]:
    eye_mid = (points[LEFT_EYE] + points[RIGHT_EYE]) / 2.0
    iod = float(np.linalg.norm(points[RIGHT_EYE, :2] - points[LEFT_EYE, :2]))
    if iod <= 1e-8:
        raise ValueError("DEGENERATE_INTEROCULAR_DISTANCE")
    return (points - eye_mid) / iod, iod


def _distance(points: np.ndarray, a: int, b: int) -> float:
    return float(np.linalg.norm(points[a, :2] - points[b, :2]))


def _geometry(points: np.ndarray) -> dict[str, float]:
    face_length = _distance(points, FOREHEAD, CHIN)
    face_width = _distance(points, CHEEK_L, CHEEK_R)
    if min(face_length, face_width) <= 1e-8:
        raise ValueError("DEGENERATE_FACE_GEOMETRY")
    return {
        "FACE_WIDTH_TO_LENGTH": face_width / face_length,
        "INTEROCULAR_TO_FACE_WIDTH": _distance(points, LEFT_EYE, RIGHT_EYE) / face_width,
        "NOSE_LENGTH_TO_FACE_LENGTH": _distance(points, (LEFT_EYE), NOSE) / face_length,
        "MOUTH_WIDTH_TO_FACE_WIDTH": _distance(points, MOUTH_L, MOUTH_R) / face_width,
        "JAW_WIDTH_TO_CHEEKBONE_WIDTH": _distance(points, JAW_L, JAW_R) / face_width,
        "FOREHEAD_HEIGHT_TO_FACE_LENGTH": _distance(points, FOREHEAD, LEFT_EYE) / face_length,
        "VERTICAL_EYE_NOSE_MOUTH_SPACING": abs(points[NOSE, 1] - points[MOUTH_L:MOUTH_R + 1:230, 1].mean()) / face_length,
        "NATURAL_LEFT_RIGHT_ASYMMETRY": abs(_distance(points, NOSE, CHEEK_L) - _distance(points, NOSE, CHEEK_R)) / face_width,
    }


def _pose(points: np.ndarray) -> dict[str, float]:
    eye_delta = points[RIGHT_EYE, :2] - points[LEFT_EYE, :2]
    roll = float(np.degrees(np.arctan2(eye_delta[1], eye_delta[0])))
    eye_mid = (points[LEFT_EYE, :2] + points[RIGHT_EYE, :2]) / 2.0
    yaw_proxy = float((points[NOSE, 0] - eye_mid[0]) * 30.0)
    pitch_proxy = float((points[NOSE, 1] - eye_mid[1]) * 20.0)
    return {"ROLL_DEG": roll, "YAW_PROXY_DEG": yaw_proxy, "PITCH_PROXY_DEG": pitch_proxy}


class GeometryFirstAnalyzer:
    def __init__(self, backend: DenseFaceBackend):
        self.backend = backend

    def analyze(self, image: Image.Image | np.ndarray) -> AnalysisResult:
        reps = make_representations(image)
        normalized: list[np.ndarray] = []
        names: list[str] = []
        for branch in BRANCHES:
            points = _validate_landmarks(self.backend.infer(reps[branch], branch))
            if points is not None:
                try:
                    points, _ = _normalize(points)
                except ValueError:
                    continue
                normalized.append(points)
                names.append(branch)

        base_disclosures = (
            "GEOMETRY_FIRST_NOT_FACE_AUTHENTICATION",
            "AUTOMATIC_HUMAN_LIKENESS_PASS_DENIED",
            "SKIN_TONE_NOT_USED_AS_FACE_EXISTENCE_GATE",
        )
        if not normalized:
            return AnalysisResult("ABSTAIN_RECAPTURE", (), None, {}, {}, None, None,
                                  "NOT_EVALUATED", base_disclosures + ("NO_VALID_DENSE_GEOMETRY",))

        stack = np.stack(normalized)
        consensus = np.median(stack, axis=0)
        errors = np.linalg.norm(stack[:, :, :2] - consensus[None, :, :2], axis=2).ravel()
        median = float(np.median(errors))
        p95 = float(np.percentile(errors, 95))
        if len(normalized) == 1:
            outcome = "GEOMETRY_REVIEW_REQUIRED"
        elif median > 0.025 or p95 > 0.06:
            outcome = "ABSTAIN_RECAPTURE"
        else:
            outcome = "GEOMETRY_CONFIDENT"
        if outcome == "ABSTAIN_RECAPTURE":
            return AnalysisResult(outcome, tuple(names), None, {}, {}, median, p95,
                                  "NOT_EVALUATED", base_disclosures + ("BRANCH_CONFLICT",))
        return AnalysisResult(
            outcome, tuple(names), consensus, _geometry(consensus), _pose(consensus), median, p95,
            "SKIN_TONE_UNCERTAIN_NEUTRAL_PLACEHOLDER",
            base_disclosures + ("NEUTRAL_PLACEHOLDER_IS_NOT_OBSERVED_SKIN",),
        )
