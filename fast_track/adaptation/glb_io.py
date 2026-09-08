"""Read-only GLB/GLTF loader for ADAPT-01. Never writes source assets."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any


class ParseError(Exception):
    """Fail-closed parse failure."""


def load_gltf_document(path: Path) -> tuple[dict[str, Any], bytes | None, str]:
    """
    Load GLB or .gltf JSON. Returns (gltf_dict, bin_blob_or_None, format_tag).
    Does not modify the file on disk.
    """
    if not path.is_file():
        raise ParseError(f"missing asset: {path}")
    suffix = path.suffix.lower()
    data = path.read_bytes()
    if suffix == ".glb":
        return _parse_glb_bytes(data)
    if suffix in (".gltf", ".json"):
        try:
            gltf = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ParseError(f"invalid glTF JSON: {e}") from e
        if not isinstance(gltf, dict):
            raise ParseError("glTF root must be object")
        return gltf, None, "gltf"
    raise ParseError(f"unsupported format for ADAPT-01 canonical path: {suffix or '(none)'}")


def _parse_glb_bytes(data: bytes) -> tuple[dict[str, Any], bytes | None, str]:
    if len(data) < 12 or data[:4] != b"glTF":
        raise ParseError("not a GLB (missing glTF magic)")
    version, total_len = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise ParseError(f"unsupported glTF container version: {version}")
    if total_len > len(data):
        raise ParseError("GLB declared length exceeds file size")
    offset = 12
    gltf: dict[str, Any] | None = None
    bin_blob: bytes | None = None
    while offset + 8 <= len(data) and offset < total_len:
        chunk_len, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        if offset + chunk_len > len(data):
            raise ParseError("GLB chunk overruns file")
        chunk = data[offset : offset + chunk_len]
        offset += chunk_len
        if chunk_type == b"JSON":
            try:
                text = chunk.decode("utf-8").rstrip(" \t\r\n\0")
                gltf = json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise ParseError(f"invalid GLB JSON chunk: {e}") from e
        elif chunk_type == b"BIN\x00":
            bin_blob = chunk
    if gltf is None:
        raise ParseError("GLB missing JSON chunk")
    if not isinstance(gltf, dict):
        raise ParseError("GLB JSON root must be object")
    return gltf, bin_blob, "glb"


def write_minimal_glb(gltf: dict[str, Any], bin_blob: bytes = b"") -> bytes:
    """Fixture helper only — never used on production candidate sources."""
    json_bytes = json.dumps(gltf, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    while len(json_bytes) % 4:
        json_bytes += b" "
    bin_pad = bin_blob
    while len(bin_pad) % 4:
        bin_pad += b"\x00"
    chunks = bytearray()
    chunks += struct.pack("<I4s", len(json_bytes), b"JSON")
    chunks += json_bytes
    if bin_pad:
        chunks += struct.pack("<I4s", len(bin_pad), b"BIN\x00")
        chunks += bin_pad
    total = 12 + len(chunks)
    return struct.pack("<4sII", b"glTF", 2, total) + bytes(chunks)
