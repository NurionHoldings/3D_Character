"""Self-contained profile validation for the installable landmarker add-on."""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

SCHEMA = "NURION_CHARACTER_PROFILE"
VERSIONS = frozenset(("0.1.0", "0.2.0-alpha.2"))
MAX_PROFILE_BYTES = 2 * 1024 * 1024
MAX_LANDMARKS = 512
MAX_ABS_METERS = 100_000.0


class ContractViolation(ValueError):
    pass


def _fail(code: str) -> None:
    raise ContractViolation(code)


def _finite(value: Any, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(code)
    try:
        number = float(value)
    except (OverflowError, ValueError):
        _fail(code)
    if not math.isfinite(number) or abs(number) > MAX_ABS_METERS:
        _fail(code)
    return number


def _vector(value: Any, code: str) -> None:
    if not isinstance(value, list) or len(value) != 3:
        _fail(code)
    for part in value:
        _finite(part, code)


def normalize_landmarks(raw: Any) -> list[dict]:
    """Normalize legacy dict notation before validation, without Blender imports."""
    if isinstance(raw, dict):
        normalized = []
        for name, value in raw.items():
            if isinstance(value, dict):
                entry = dict(value)
                entry.setdefault("name", name)
            else:
                entry = {"name": name, "position": value, "source": "ESTIMATED", "confidence": 0.5, "reviewRequired": True}
            normalized.append(entry)
        return normalized
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    _fail("PROFILE_LANDMARKS_INVALID")


def normalize_and_validate(data: Any) -> dict:
    if not isinstance(data, Mapping):
        _fail("PROFILE_NOT_OBJECT")
    doc = dict(data)
    doc["landmarks"] = normalize_landmarks(doc.get("landmarks"))
    if doc.get("schema") != SCHEMA:
        _fail("PROFILE_SCHEMA_UNSUPPORTED")
    if doc.get("version") not in VERSIONS:
        _fail("PROFILE_VERSION_UNSUPPORTED")
    character_id = doc.get("characterId")
    if not isinstance(character_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,95}", character_id):
        _fail("PROFILE_CHARACTER_ID_INVALID")
    for key in ("characterHeight", "width"):
        value = _finite(doc.get(key), f"PROFILE_{key.upper()}_INVALID")
        if value <= 0:
            _fail(f"PROFILE_{key.upper()}_INVALID")
    _finite(doc.get("floorZ"), "PROFILE_FLOORZ_INVALID")
    _vector(doc.get("center"), "PROFILE_CENTER_INVALID")
    if doc.get("forwardAxis") not in {"+X", "-X", "+Y", "-Y", "+Z", "-Z"}:
        _fail("PROFILE_FORWARD_AXIS_INVALID")
    landmarks = doc["landmarks"]
    if len(landmarks) > MAX_LANDMARKS:
        _fail("PROFILE_LANDMARK_COUNT_EXCEEDED")
    names = set()
    for entry in landmarks:
        name = entry.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,95}", name):
            _fail("PROFILE_LANDMARK_NAME_INVALID")
        if name in names:
            _fail("PROFILE_LANDMARK_NAME_DUPLICATE")
        names.add(name)
        _vector(entry.get("position"), "PROFILE_LANDMARK_VECTOR_INVALID")
        confidence = _finite(entry.get("confidence"), "PROFILE_LANDMARK_CONFIDENCE_INVALID")
        if not 0.0 <= confidence <= 1.0:
            _fail("PROFILE_LANDMARK_CONFIDENCE_RANGE")
    return doc
