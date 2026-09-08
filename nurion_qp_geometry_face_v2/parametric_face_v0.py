"""Gate 6 parametric fit + albedo prep for NURION_PARAMETRIC_FACE_V0."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


ID_AXES = (
    "ID_FaceOutline",
    "ID_Eye",
    "ID_Nose",
    "ID_Mouth",
    "ID_Jaw",
    "ID_Cheek",
    "ID_Hairline",
)


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _round6(x: float) -> float:
    return float(f"{x:.6f}")


@dataclass(frozen=True)
class ParametricFit:
    identity_values: dict[str, float]
    geometry_ratios: dict[str, float]
    pose: dict[str, float]
    face_bbox_norm: tuple[float, float, float, float]  # x0,y0,x1,y1 in 0..1
    disclosures: tuple[str, ...]


def _lm(arr: np.ndarray, idx: int) -> np.ndarray:
    return arr[idx]


def fit_parametric_from_478(landmarks: np.ndarray) -> ParametricFit:
    """Deterministic ratio→ID_* fit. No seed noise. Not a research 3DMM."""
    lm = np.asarray(landmarks, dtype=np.float64)
    if lm.shape != (478, 3) or not np.isfinite(lm).all():
        raise ValueError("LANDMARKS_MUST_BE_478x3_FINITE")

    left_eye, right_eye = _lm(lm, 33), _lm(lm, 263)
    nose = _lm(lm, 1)
    chin = _lm(lm, 152)
    forehead = _lm(lm, 10)
    mouth_l, mouth_r = _lm(lm, 61), _lm(lm, 291)
    jaw_l, jaw_r = _lm(lm, 234), _lm(lm, 454)
    cheek_l, cheek_r = _lm(lm, 234), _lm(lm, 454)

    iod = float(np.linalg.norm(right_eye[:2] - left_eye[:2])) + 1e-8
    face_len = float(np.linalg.norm(chin[:2] - forehead[:2])) + 1e-8
    face_w = float(np.linalg.norm(jaw_r[:2] - jaw_l[:2])) + 1e-8
    nose_len = float(np.linalg.norm(nose[:2] - ((left_eye + right_eye) * 0.5)[:2])) + 1e-8
    mouth_w = float(np.linalg.norm(mouth_r[:2] - mouth_l[:2])) + 1e-8
    cheek_w = float(np.linalg.norm(cheek_r[:2] - cheek_l[:2])) + 1e-8
    forehead_h = float(abs(((left_eye + right_eye) * 0.5)[1] - forehead[1])) + 1e-8

    ratios = {
        "FACE_WIDTH_TO_LENGTH": face_w / face_len,
        "INTEROCULAR_TO_FACE_WIDTH": iod / face_w,
        "NOSE_LENGTH_TO_FACE_LENGTH": nose_len / face_len,
        "MOUTH_WIDTH_TO_FACE_WIDTH": mouth_w / face_w,
        "JAW_WIDTH_TO_CHEEKBONE_WIDTH": face_w / cheek_w,
        "FOREHEAD_HEIGHT_TO_FACE_LENGTH": forehead_h / face_len,
        "NATURAL_LEFT_RIGHT_ASYMMETRY": float(abs(left_eye[1] - right_eye[1]) / iod),
    }

    # Pose proxies from landmark geometry (normalized image space).
    eye_mid = (left_eye + right_eye) * 0.5
    roll = float(np.degrees(np.arctan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0])))
    yaw = float(np.degrees(np.arctan2((nose[0] - eye_mid[0]), iod)))
    pitch = float(np.degrees(np.arctan2((nose[1] - eye_mid[1]), iod)))
    pose = {"rollDeg": _round6(roll), "yawDeg": _round6(yaw), "pitchDeg": _round6(pitch)}

    values = {
        "ID_FaceOutline": _round6(_clamp01(0.15 + 0.75 * ratios["FACE_WIDTH_TO_LENGTH"])),
        "ID_Eye": _round6(_clamp01(0.10 + 0.95 * ratios["INTEROCULAR_TO_FACE_WIDTH"])),
        "ID_Nose": _round6(_clamp01(0.10 + 0.95 * ratios["NOSE_LENGTH_TO_FACE_LENGTH"])),
        "ID_Mouth": _round6(_clamp01(0.10 + 0.95 * ratios["MOUTH_WIDTH_TO_FACE_WIDTH"])),
        "ID_Jaw": _round6(_clamp01(0.10 + 0.85 * ratios["JAW_WIDTH_TO_CHEEKBONE_WIDTH"])),
        "ID_Cheek": _round6(_clamp01(0.20 + 0.60 * (1.0 - min(ratios["NATURAL_LEFT_RIGHT_ASYMMETRY"], 0.2) / 0.2))),
        "ID_Hairline": _round6(_clamp01(0.15 + 0.85 * ratios["FOREHEAD_HEIGHT_TO_FACE_LENGTH"])),
    }

    xs = lm[:, 0]
    ys = lm[:, 1]
    pad = 0.04
    bbox = (
        _clamp01(float(xs.min()) - pad),
        _clamp01(float(ys.min()) - pad),
        _clamp01(float(xs.max()) + pad),
        _clamp01(float(ys.max()) + pad),
    )

    return ParametricFit(
        identity_values=values,
        geometry_ratios={k: _round6(v) for k, v in ratios.items()},
        pose=pose,
        face_bbox_norm=bbox,
        disclosures=(
            "NURION_PARAMETRIC_FACE_V0_NOT_RESEARCH_3DMM",
            "DETERMINISTIC_RATIO_FIT_NO_SEED",
            "PHOTOREAL_AUTOMATIC_PASS_DENY",
        ),
    )


def write_face_albedo_crop(image_path: Path, bbox_norm: tuple[float, float, float, float], out_path: Path) -> dict[str, Any]:
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    x0, y0, x1, y1 = bbox_norm
    left, top = int(x0 * w), int(y0 * h)
    right, bottom = int(x1 * w), int(y1 * h)
    left, top = max(0, left), max(0, top)
    right, bottom = min(w, max(left + 1, right)), min(h, max(top + 1, bottom))
    crop = img.crop((left, top, right, bottom)).resize((1024, 1024), Image.Resampling.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out_path, format="PNG")
    arr = np.asarray(crop, dtype=np.float32)
    return {
        "path": str(out_path),
        "bytes": out_path.stat().st_size,
        "meanRgb": [float(x) for x in arr.mean(axis=(0, 1))],
        "stdRgb": [float(x) for x in arr.std(axis=(0, 1))],
        "bboxPixels": [left, top, right, bottom],
    }


def mild_polish_identity(values: dict[str, float], strength: float = 0.18) -> dict[str, float]:
    """Weak polish toward mean — preview only, not beautify claim."""
    mean = 0.45
    out = {}
    for k, v in values.items():
        out[k] = _round6(_clamp01(v * (1.0 - strength) + mean * strength))
    return out
