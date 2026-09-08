"""Portable, fail-closed contracts for Post-V2 runtime I/O and timing."""

from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path
from typing import Any

MAX_FBX_BYTES = 512 * 1024 * 1024
ALLOWED_FPS = frozenset((24, 30, 60))


class ContractViolation(ValueError):
    pass


def _fail(code: str) -> None:
    raise ContractViolation(code)


def _path(value: str | Path) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        _fail("EMPTY_PATH")
    try:
        return Path(value).expanduser()
    except (OSError, OverflowError, ValueError):
        _fail("INVALID_PATH")


def _resolved(value: str | Path) -> Path:
    try:
        return _path(value).resolve(strict=False)
    except (OSError, OverflowError, ValueError):
        _fail("INVALID_PATH")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, OverflowError):
        _fail("INPUT_NOT_READABLE")
    return digest.hexdigest()


def validate_fbx_input(path: str | Path, *, max_bytes: int = MAX_FBX_BYTES) -> dict:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        _fail("INVALID_FBX_LIMIT")
    candidate = _resolved(path)
    if candidate.suffix.lower() != ".fbx":
        _fail("INPUT_EXTENSION_DENIED")
    try:
        stat = candidate.stat()
    except (OSError, OverflowError):
        _fail("INPUT_NOT_READABLE")
    if not candidate.is_file() or stat.st_size <= 0:
        _fail("INPUT_NOT_REGULAR_FILE")
    if stat.st_size > max_bytes:
        _fail("INPUT_TOO_LARGE")
    if not os.access(candidate, os.R_OK):
        _fail("INPUT_NOT_READABLE")
    return {"path": candidate, "size": stat.st_size, "sha256": sha256_file(candidate)}


def validate_timing(*, fps: Any, dt: Any, frame_start: Any, frame_end: Any) -> dict:
    def finite(value: Any, code: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(code)
        number = float(value)
        if not math.isfinite(number):
            _fail(code)
        return number

    f = finite(fps, "FPS_NOT_FINITE")
    if f != int(f) or int(f) not in ALLOWED_FPS:
        _fail("UNSUPPORTED_FPS")
    delta = finite(dt, "DT_NOT_FINITE")
    if delta <= 0 or not math.isclose(delta, 1.0 / f, rel_tol=1e-9, abs_tol=1e-12):
        _fail("DT_FPS_MISMATCH")
    start, end = finite(frame_start, "FRAME_START_NOT_FINITE"), finite(frame_end, "FRAME_END_NOT_FINITE")
    if start != int(start) or end != int(end) or end < start:
        _fail("INVALID_FRAME_RANGE")
    return {"fps": int(f), "dt": delta, "frameStart": int(start), "frameEnd": int(end)}


def validate_export_target(path: str | Path, *, fmt: str, root: str | Path) -> Path:
    suffix = {"FBX": ".fbx", "GLB": ".glb"}.get(str(fmt).upper())
    if suffix is None:
        _fail("EXPORT_FORMAT_DENIED")
    raw_root, raw_candidate = _path(root), _path(path)
    if raw_root.is_symlink():
        _fail("EXPORT_ROOT_SYMLINK_DENIED")
    root_resolved, candidate = _resolved(raw_root), _resolved(raw_candidate)
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        _fail("EXPORT_ROOT_DENIED")
    if candidate == root_resolved or candidate.suffix.lower() != suffix:
        _fail("EXPORT_EXTENSION_DENIED")
    # Existing target or any existing parent symlink is rejected before write.
    current = raw_candidate
    while current != raw_root and current != current.parent:
        if current.exists() and current.is_symlink():
            _fail("EXPORT_SYMLINK_DENIED")
        current = current.parent
    if candidate.exists() or raw_candidate.exists():
        _fail("EXPORT_TARGET_EXISTS")
    return candidate


def identifier(value: Any, *, code: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,95}", value):
        _fail(code)
    return value
