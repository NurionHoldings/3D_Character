#!/usr/bin/env python3
"""Patch identity-neutral GLB with presentation morph targets + additive bones (no regression)."""

from __future__ import annotations

import copy
import json
import struct
from pathlib import Path
from typing import Any

import numpy as np

COMPONENT_TYPE = {
    5126: (4, np.float32),
}


def load_glb(path: Path) -> tuple[dict[str, Any], bytearray, bytes]:
    data = path.read_bytes()
    offset = 12
    gltf = None
    bin_blob = bytearray()
    while offset + 8 <= len(data):
        ln, ty = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunk = data[offset : offset + ln]
        offset += ln
        if ty == b"JSON":
            gltf = json.loads(chunk.decode("utf-8"))
        elif ty == b"BIN\x00":
            bin_blob = bytearray(chunk)
    if gltf is None:
        raise ValueError("missing json")
    return gltf, bin_blob, data


def pad4(n: int) -> int:
    return (4 - n % 4) % 4


def append_bin(bin_blob: bytearray, payload: bytes) -> tuple[int, int]:
    off = len(bin_blob)
    bin_blob.extend(payload)
    pad = pad4(len(payload))
    bin_blob.extend(b"\x00" * pad)
    return off, len(payload) + pad


def write_glb(gltf: dict, bin_blob: bytes | bytearray, out: Path) -> None:
    jb = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    jb += b" " * pad4(len(jb))
    bb = bytes(bin_blob)
    bb += b"\x00" * pad4(len(bb))
    total = 12 + 8 + len(jb) + 8 + len(bb)
    with out.open("wb") as f:
        f.write(b"glTF")
        f.write(struct.pack("<II", 2, total))
        f.write(struct.pack("<I4s", len(jb), b"JSON"))
        f.write(jb)
        f.write(struct.pack("<I4s", len(bb), b"BIN\x00"))
        f.write(bb)


def read_acc(gltf, bin_blob, idx) -> np.ndarray:
    acc = gltf["accessors"][idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    _, dt = COMPONENT_TYPE[acc["componentType"]]
    n = acc["count"]
    comp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[acc["type"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    raw = bin_blob[start : start + n * 4 * comp]
    arr = np.frombuffer(raw, dtype=dt)
    return arr.reshape(n, comp) if comp > 1 else arr


def patch_glb(
    source_glb: Path,
    morph_json: Path,
    bones_json: Path,
    output_glb: Path,
) -> dict[str, Any]:
    gltf, bin_blob, _ = load_glb(source_glb)
    morph = json.loads(morph_json.read_text(encoding="utf-8"))
    bones = json.loads(bones_json.read_text(encoding="utf-8"))
    n_verts = morph["vertexCount"]

    prim = gltf["meshes"][0]["primitives"][0]
    pos_idx = prim["attributes"]["POSITION"]
    base_pos = read_acc(gltf, bin_blob, pos_idx)
    if len(base_pos) != n_verts:
        raise RuntimeError(f"Vertex count mismatch: glb={len(base_pos)} morph={n_verts}")

    targets = []
    target_names = []
    for name, deltas in morph["shapeKeys"].items():
        delta_arr = np.zeros((n_verts, 3), dtype=np.float32)
        for item in deltas:
            vi, x, y, z = item
            delta_arr[int(vi)] = [x, y, z]
        off, length = append_bin(bin_blob, delta_arr.tobytes())
        bv_idx = len(gltf["bufferViews"])
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": length})
        acc_idx = len(gltf["accessors"])
        gltf["accessors"].append(
            {"bufferView": bv_idx, "componentType": 5126, "count": n_verts, "type": "VEC3"}
        )
        targets.append({"POSITION": acc_idx})
        target_names.append(name)

    prim["targets"] = targets
    if "extras" not in gltf["meshes"][0]:
        gltf["meshes"][0]["extras"] = {}
    gltf["meshes"][0]["extras"]["targetNames"] = target_names

    nodes = gltf["nodes"]
    skins = gltf["skins"]
    head_node_idx = None
    for i, j in enumerate(skins[0]["joints"]):
        if gltf["nodes"][j].get("name", "").lower() == "head":
            head_node_idx = j
            break
    if head_node_idx is None:
        for i, n in enumerate(nodes):
            if n.get("name", "").lower() == "head":
                head_node_idx = i
                break
    if head_node_idx is None:
        raise RuntimeError("Head node not found")

    added_node_indices = []
    for spec in bones["addedBones"]:
        node_idx = len(nodes)
        nodes.append(
            {
                "name": spec["name"],
                "translation": spec["headLocal"],
                "rotation": [0, 0, 0, 1],
                "scale": [1, 1, 1],
                "children": [],
            }
        )
        added_node_indices.append(node_idx)
        if "children" not in nodes[head_node_idx]:
            nodes[head_node_idx]["children"] = []
        nodes[head_node_idx]["children"].append(node_idx)

    # bones are presentation-only nodes; NOT added to skin.joints — zero skin mutation
    meta = {
        "morphTargetCount": len(target_names),
        "morphTargetNames": target_names,
        "addedPresentationBones": [b["name"] for b in bones["addedBones"]],
        "skinJointCountUnchanged": len(skins[0]["joints"]),
        "basePositionAccessorUnchanged": pos_idx,
    }
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    write_glb(gltf, bin_blob, output_glb)
    return meta


if __name__ == "__main__":
    import sys

    patch_glb(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
