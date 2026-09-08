"""Minimal GLB measurement helpers for CR03 audit (no inspector/classifier deps)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from fast_track.v2_cr03.pins import COMPONENT_FLOAT, MORPH_INDEX_MAP

COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COMPS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_dumps(obj).encode("utf-8")).hexdigest()


def accessor_raw_bytes(blob: bytes, gltf: dict, accessor_idx: int) -> bytes:
    acc = gltf["accessors"][accessor_idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    off = (bv.get("byteOffset") or 0) + (acc.get("byteOffset") or 0)
    ctype = acc["componentType"]
    typ = acc["type"]
    count = acc["count"]
    elem = TYPE_COMPS[typ] * COMPONENT_SIZE[ctype]
    length = count * elem
    stride = bv.get("byteStride") or elem
    if stride == elem:
        return bytes(blob[off : off + length])
    out = bytearray()
    for i in range(count):
        o = off + i * stride
        out.extend(blob[o : o + elem])
    return bytes(out)


def read_f32_vec3(blob: bytes, gltf: dict, accessor_idx: int) -> np.ndarray:
    acc = gltf["accessors"][accessor_idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    off = (bv.get("byteOffset") or 0) + (acc.get("byteOffset") or 0)
    count = acc["count"]
    stride = bv.get("byteStride") or 12
    if stride == 12:
        return np.frombuffer(blob[off : off + count * 12], dtype="<f4").reshape(count, 3).copy()
    out = np.zeros((count, 3), dtype=np.float32)
    for i in range(count):
        o = off + i * stride
        out[i] = np.frombuffer(blob[o : o + 12], dtype="<f4")
    return out


def morph_position_digests(blob: bytes, gltf: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, pin in MORPH_INDEX_MAP.items():
        raw = accessor_raw_bytes(blob, gltf, pin["positionAccessor"])
        out[name] = hashlib.sha256(raw).hexdigest()
    return out


def base_skin_digests(blob: bytes, gltf: dict) -> dict[str, str]:
    prim = gltf["meshes"][0]["primitives"][0]
    attrs = prim["attributes"]
    dig: dict[str, str] = {
        "POSITION": hashlib.sha256(accessor_raw_bytes(blob, gltf, attrs["POSITION"])).hexdigest()
    }
    for key in ("JOINTS_0", "WEIGHTS_0"):
        if key in attrs:
            dig[key] = hashlib.sha256(accessor_raw_bytes(blob, gltf, attrs[key])).hexdigest()
    return dig


# Keep pin import used (COMPONENT_FLOAT reserved for callers)
_ = COMPONENT_FLOAT
