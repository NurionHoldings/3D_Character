"""Deterministic serialization helpers for landmark result hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Iterable

from .landmark_engine import LandmarkPoint


def serialize_landmarks_for_hash(landmarks: Dict[str, LandmarkPoint], names: Iterable[str] | None = None) -> str:
    keys = sorted(names) if names is not None else sorted(landmarks.keys())
    payload = []
    for key in keys:
        point = landmarks.get(key)
        if point is None:
            continue
        payload.append(
            {
                "name": point.name,
                "position": [
                    round(float(point.position.x), 6),
                    round(float(point.position.y), 6),
                    round(float(point.position.z), 6),
                ],
                "source": point.source,
                "confidence": round(float(point.confidence), 4),
                "reviewRequired": bool(point.review_required),
            }
        )
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def landmarks_sha256(landmarks: Dict[str, LandmarkPoint], names: Iterable[str] | None = None) -> str:
    return sha256_text(serialize_landmarks_for_hash(landmarks, names))
