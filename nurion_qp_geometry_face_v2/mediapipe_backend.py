"""Pinned offline MediaPipe Face Landmarker backend for Geometry-First v2."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

EXP_LM = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
EXP_DET = "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MediaPipeLandmarkerBackend:
    name = "MEDIAPIPE_FACE_LANDMARKER_FLOAT16_V1_OFFLINE"

    def __init__(self, model_path: Path, *, expected_sha256: str = EXP_LM):
        path = Path(model_path)
        got = sha256_file(path)
        if got != expected_sha256:
            raise RuntimeError(f"LANDMARKER_SHA_MISMATCH:{got}")
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core import base_options as base_options_module

        options = vision.FaceLandmarkerOptions(
            base_options=base_options_module.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def infer(self, image: np.ndarray, branch: str) -> np.ndarray | None:
        from mediapipe import Image as MpImage
        from mediapipe import ImageFormat

        rgb = np.ascontiguousarray(image[..., :3].astype(np.uint8))
        result = self._landmarker.detect(MpImage(image_format=ImageFormat.SRGB, data=rgb))
        if not result.face_landmarks:
            return None
        landmarks = result.face_landmarks[0]
        if len(landmarks) != 478:
            return None
        return np.array([[p.x, p.y, p.z] for p in landmarks], dtype=np.float64)
