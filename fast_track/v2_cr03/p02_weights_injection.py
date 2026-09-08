"""CR03-P02 — Morph-Weight Animation Injection ONLY.

Creates actual GLB animation sampler/channel with path=weights.
Does NOT mutate morph POSITION / BODY / create new morph geometry.
Structural success ≠ temporal vertex PASS (that is P03).
"""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import numpy as np

from fast_track.adaptation.glb_io import load_gltf_document, write_minimal_glb
from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.change_control import require_human_spec_gate, require_no_upstream_mutation
from fast_track.v2_cr03.pins import (
    APPROVED_SPEC_DIGEST,
    COMPONENT_FLOAT,
    CR,
    CR02_R2_DERIVED_SHA,
    MESH_NODE_NAME,
    MORPH_INDEX_MAP,
    REQUIRED_MORPHS,
    TALKING_ANIMATION_NAME,
    TALKING_TIMELINE,
    TYPE_SCALAR,
)

REPORT_SCHEMA = "NURION_V2_CR03_P02_MORPH_WEIGHT_ANIMATION_INJECTION_V1"


def _append_buffer_data(blob: bytearray, data: bytes) -> tuple[int, int]:
    while len(blob) % 4:
        blob.append(0)
    offset = len(blob)
    blob.extend(data)
    while len(blob) % 4:
        blob.append(0)
    return offset, len(data)


def _accessor_raw_bytes(blob: bytes, gltf: dict, accessor_idx: int) -> bytes:
    acc = gltf["accessors"][accessor_idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    off = (bv.get("byteOffset") or 0) + (acc.get("byteOffset") or 0)
    ctype = acc["componentType"]
    typ = acc["type"]
    count = acc["count"]
    comp_bytes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}[ctype]
    comps = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[typ]
    elem = comps * comp_bytes
    length = count * elem
    stride = bv.get("byteStride") or elem
    if stride == elem:
        return bytes(blob[off : off + length])
    out = bytearray()
    for i in range(count):
        o = off + i * stride
        out.extend(blob[o : o + elem])
    return bytes(out)


def _morph_position_digests(blob: bytes, gltf: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, pin in MORPH_INDEX_MAP.items():
        raw = _accessor_raw_bytes(blob, gltf, pin["positionAccessor"])
        out[name] = hashlib.sha256(raw).hexdigest()
    return out


def _base_skin_digests(blob: bytes, gltf: dict) -> dict[str, str]:
    prim = gltf["meshes"][0]["primitives"][0]
    attrs = prim["attributes"]
    dig: dict[str, str] = {
        "POSITION": hashlib.sha256(_accessor_raw_bytes(blob, gltf, attrs["POSITION"])).hexdigest()
    }
    if "JOINTS_0" in attrs:
        dig["JOINTS_0"] = hashlib.sha256(
            _accessor_raw_bytes(blob, gltf, attrs["JOINTS_0"])
        ).hexdigest()
    if "WEIGHTS_0" in attrs:
        dig["WEIGHTS_0"] = hashlib.sha256(
            _accessor_raw_bytes(blob, gltf, attrs["WEIGHTS_0"])
        ).hexdigest()
    return dig


def _weight_vector(morph_count: int, aa: float, oh: float, ee: float) -> list[float]:
    w = [0.0] * morph_count
    w[MORPH_INDEX_MAP["VISEME_AA"]["targetIndex"]] = float(aa)
    w[MORPH_INDEX_MAP["VISEME_OH"]["targetIndex"]] = float(oh)
    w[MORPH_INDEX_MAP["VISEME_EE"]["targetIndex"]] = float(ee)
    return w


def _verify_binding(gltf: dict[str, Any], blob: bytes) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    mesh = gltf["meshes"][0]
    names = list((mesh.get("extras") or {}).get("targetNames") or [])
    targets = mesh["primitives"][0].get("targets") or []
    for name, pin in MORPH_INDEX_MAP.items():
        idx = pin["targetIndex"]
        if idx >= len(names) or names[idx] != name:
            blockers.append({"code": "MORPH_INDEX_MISMATCH", "morph": name, "names": names})
        if idx >= len(targets):
            blockers.append({"code": "TARGET_MISSING", "morph": name})
            continue
        got_acc = targets[idx].get("POSITION")
        if got_acc != pin["positionAccessor"]:
            blockers.append(
                {
                    "code": "POSITION_ACCESSOR_MISMATCH",
                    "morph": name,
                    "got": got_acc,
                    "want": pin["positionAccessor"],
                }
            )
    return blockers


def inject_talking_weights_animation(
    *,
    input_glb: Path,
    output_glb: Path,
    track: dict[str, Any],
    spec_path: Path,
) -> dict[str, Any]:
    require_no_upstream_mutation(track)
    gate_digest = require_human_spec_gate(
        track, expected_change_request=CR, spec_path=spec_path
    )
    if gate_digest != APPROVED_SPEC_DIGEST:
        raise PermissionError(f"SPEC_DIGEST_MISMATCH → IMPLEMENTATION DENIED")

    input_glb = Path(input_glb)
    output_glb = Path(output_glb)
    before = input_glb.read_bytes()
    input_sha = sha256_file(input_glb)
    blockers: list[dict[str, Any]] = []

    if input_sha != CR02_R2_DERIVED_SHA:
        blockers.append(
            {"code": "CR02_R2_INPUT_SHA_MISMATCH", "got": input_sha, "want": CR02_R2_DERIVED_SHA}
        )

    gltf, bin_blob, _ = load_gltf_document(input_glb)
    if bin_blob is None:
        blockers.append({"code": "MISSING_BIN"})
        return {"status": "BLOCKED", "blockers": blockers}

    blockers.extend(_verify_binding(gltf, bin_blob))
    morph_digests_before = _morph_position_digests(bin_blob, gltf)
    skin_before = _base_skin_digests(bin_blob, gltf)

    if blockers:
        return {"status": "BLOCKED", "blockers": blockers, "inputSha256": input_sha}

    gltf = copy.deepcopy(gltf)
    mesh = gltf["meshes"][0]
    morph_count = len(mesh["primitives"][0].get("targets") or [])
    if morph_count < 9:
        blockers.append({"code": "UNEXPECTED_MORPH_COUNT", "count": morph_count})
        return {"status": "BLOCKED", "blockers": blockers, "inputSha256": input_sha}

    nodes = gltf.get("nodes") or []
    mesh_node = next((i for i, n in enumerate(nodes) if n.get("name") == MESH_NODE_NAME), None)
    if mesh_node is None:
        mesh_node = next((i for i, n in enumerate(nodes) if n.get("mesh") == 0), None)
    if mesh_node is None:
        blockers.append({"code": "MESH_NODE_NOT_FOUND"})
        return {"status": "BLOCKED", "blockers": blockers, "inputSha256": input_sha}

    # --- Build deterministic weight keyframes (full morph weight vectors) ---
    times = np.asarray([t[0] for t in TALKING_TIMELINE], dtype=np.float32)
    weight_rows: list[list[float]] = []
    for _t, aa, oh, ee in TALKING_TIMELINE:
        weight_rows.append(_weight_vector(morph_count, aa, oh, ee))
    weights = np.asarray(weight_rows, dtype=np.float32)  # (N, morph_count)

    blob = bytearray(bin_blob)
    accessors = list(gltf.get("accessors") or [])
    buffer_views = list(gltf.get("bufferViews") or [])

    t_raw = times.tobytes(order="C")
    t_off, t_len = _append_buffer_data(blob, t_raw)
    t_bv = len(buffer_views)
    buffer_views.append({"buffer": 0, "byteOffset": t_off, "byteLength": t_len})
    t_acc = len(accessors)
    accessors.append(
        {
            "bufferView": t_bv,
            "componentType": COMPONENT_FLOAT,
            "count": int(times.shape[0]),
            "type": TYPE_SCALAR,
            "max": [float(times.max())],
            "min": [float(times.min())],
        }
    )

    w_raw = weights.tobytes(order="C")
    w_off, w_len = _append_buffer_data(blob, w_raw)
    w_bv = len(buffer_views)
    buffer_views.append({"buffer": 0, "byteOffset": w_off, "byteLength": w_len})
    w_acc = len(accessors)
    accessors.append(
        {
            "bufferView": w_bv,
            "componentType": COMPONENT_FLOAT,
            "count": int(weights.shape[0] * morph_count),
            "type": TYPE_SCALAR,
            "max": [float(weights.max())],
            "min": [float(weights.min())],
        }
    )

    gltf["accessors"] = accessors
    gltf["bufferViews"] = buffer_views
    gltf["buffers"][0]["byteLength"] = len(blob)

    anims = list(gltf.get("animations") or [])
    sampler_idx = 0
    talking_anim = {
        "name": TALKING_ANIMATION_NAME,
        "samplers": [{"input": t_acc, "interpolation": "LINEAR", "output": w_acc}],
        "channels": [
            {
                "sampler": sampler_idx,
                "target": {"node": mesh_node, "path": "weights"},
            }
        ],
        "extras": {
            "nurionCr03": True,
            "sequence": "NEUTRAL→AA→OH→EE→NEUTRAL",
            "morphIndexMap": MORPH_INDEX_MAP,
            "timeline": [
                {"t": t, "VISEME_AA": aa, "VISEME_OH": oh, "VISEME_EE": ee}
                for t, aa, oh, ee in TALKING_TIMELINE
            ],
        },
    }
    talking_anim_index = len(anims)
    anims.append(talking_anim)
    gltf["animations"] = anims

    gltf.setdefault("extras", {})["NURION_V2_CR03_P02"] = {
        "mechanism": "MORPH_WEIGHT_ANIMATION_INJECTION",
        "talkingAnimationName": TALKING_ANIMATION_NAME,
        "talkingAnimationIndex": talking_anim_index,
        "targetNode": mesh_node,
        "targetNodeName": nodes[mesh_node].get("name"),
        "morphIndexMap": MORPH_INDEX_MAP,
        "inputSha256": input_sha,
        "approvedSpecDigest": gate_digest,
        "note": "Structural injection only — temporal vertex proof is CR03-P03",
    }

    # Ensure mesh default weights remain neutral
    gltf["meshes"][0]["weights"] = [0.0] * morph_count

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_glb.write_bytes(write_minimal_glb(gltf, bytes(blob)))

    # Input immutability
    if input_glb.read_bytes() != before:
        blockers.append({"code": "INPUT_MUTATED"})

    # Reload derived — structural verification
    g2, b2, _ = load_gltf_document(output_glb)
    assert b2 is not None
    morph_after = _morph_position_digests(b2, g2)
    skin_after = _base_skin_digests(b2, g2)
    if morph_after != morph_digests_before:
        blockers.append({"code": "CR02_MORPH_POSITION_MUTATION", "before": morph_digests_before, "after": morph_after})
    if skin_after != skin_before:
        blockers.append({"code": "BODY_SKIN_MUTATION", "before": skin_before, "after": skin_after})

    # Find talking weights channel
    anim = (g2.get("animations") or [])[talking_anim_index]
    if anim.get("name") != TALKING_ANIMATION_NAME:
        blockers.append({"code": "TALKING_ANIM_NAME_MISMATCH"})
    ch = (anim.get("channels") or [None])[0]
    if not ch or (ch.get("target") or {}).get("path") != "weights":
        blockers.append({"code": "NO_WEIGHTS_ANIMATION_CHANNEL"})
    if (ch.get("target") or {}).get("node") != mesh_node:
        blockers.append({"code": "ANIMATION_TARGETS_WRONG_MESH_NODE"})

    samp = anim["samplers"][ch["sampler"]]
    t_acc_i = samp["input"]
    w_acc_i = samp["output"]
    t_vals = np.frombuffer(_accessor_raw_bytes(b2, g2, t_acc_i), dtype="<f4").copy()
    w_flat = np.frombuffer(_accessor_raw_bytes(b2, g2, w_acc_i), dtype="<f4").copy()
    if len(w_flat) != len(TALKING_TIMELINE) * morph_count:
        blockers.append(
            {
                "code": "WEIGHT_OUTPUT_COUNT_MISMATCH",
                "got": len(w_flat),
                "want": len(TALKING_TIMELINE) * morph_count,
            }
        )
    w_mat = w_flat.reshape(len(TALKING_TIMELINE), morph_count)

    # Sequence check Neutral→AA→OH→EE→Neutral via pinned indices
    ia, io, ie = (
        MORPH_INDEX_MAP["VISEME_AA"]["targetIndex"],
        MORPH_INDEX_MAP["VISEME_OH"]["targetIndex"],
        MORPH_INDEX_MAP["VISEME_EE"]["targetIndex"],
    )
    expected = np.asarray([[aa, oh, ee] for _t, aa, oh, ee in TALKING_TIMELINE], dtype=np.float32)
    got = w_mat[:, [ia, io, ie]]
    if not np.allclose(got, expected, atol=1e-6):
        blockers.append({"code": "WEIGHT_KEYFRAMES_MISMATCH", "got": got.tolist(), "want": expected.tolist()})
    if not np.allclose(t_vals, np.asarray([t[0] for t in TALKING_TIMELINE], dtype=np.float32), atol=1e-6):
        blockers.append({"code": "TIMESTAMP_MISMATCH", "got": t_vals.tolist()})

    timeline_digest = canonical_sha256(
        [{"t": t, "AA": aa, "OH": oh, "EE": ee} for t, aa, oh, ee in TALKING_TIMELINE]
    )
    sampler_digest = canonical_sha256(
        {"inputAccessor": t_acc_i, "outputAccessor": w_acc_i, "interpolation": samp.get("interpolation")}
    )
    channel_digest = canonical_sha256(
        {"path": "weights", "node": mesh_node, "sampler": ch["sampler"], "animationIndex": talking_anim_index}
    )

    weights_channels = 0
    for a in g2.get("animations") or []:
        for c in a.get("channels") or []:
            if (c.get("target") or {}).get("path") == "weights":
                weights_channels += 1

    if weights_channels < 1:
        blockers.append({"code": "WEIGHTS_CHANNEL_COUNT_ZERO"})

    status = "PASS" if not blockers else "BLOCKED"
    derived_sha = sha256_file(output_glb)

    report = {
        "schema": REPORT_SCHEMA,
        "changeRequestId": CR,
        "stage": "CR03-P02",
        "status": status,
        "role": "STRUCTURAL_INJECTION_ONLY — not temporal vertex PASS",
        "gate": {"approvedSpecDigest": gate_digest},
        "input": {"sha256": input_sha, "immutable": input_glb.read_bytes() == before},
        "derived": {
            "path": str(output_glb).replace("\\", "/"),
            "sha256": derived_sha,
            "byteLength": output_glb.stat().st_size,
            "determinismNote": "GLB byte SHA is observed; SoT digests = timeline/sampler/channel + morph POSITION pins",
        },
        "talkingAnimationName": TALKING_ANIMATION_NAME,
        "talkingAnimationIndex": talking_anim_index,
        "targetMeshIdentity": {
            "nodeIndex": mesh_node,
            "nodeName": nodes[mesh_node].get("name"),
            "meshIndex": 0,
        },
        "morphIndexMap": MORPH_INDEX_MAP,
        "timeline": [
            {"t": t, "VISEME_AA": aa, "VISEME_OH": oh, "VISEME_EE": ee}
            for t, aa, oh, ee in TALKING_TIMELINE
        ],
        "structure": {
            "weightsChannelCount": weights_channels,
            "timestampAccessor": t_acc_i,
            "weightOutputAccessor": w_acc_i,
            "timestamps": t_vals.tolist(),
            "visemeWeightRows": got.tolist(),
            "sequence": "NEUTRAL→AA→OH→EE→NEUTRAL",
        },
        "preservation": {
            "morphPositionDigests": morph_after,
            "skinDigests": skin_after,
            "morphPositionUnchanged": morph_after == morph_digests_before,
            "skinUnchanged": skin_after == skin_before,
        },
        "provenance": {
            "cr02R2DerivedSha256": input_sha,
            "timelineDigest": timeline_digest,
            "animationSamplerDigest": sampler_digest,
            "animationChannelDigest": channel_digest,
            "derivedAssetSha256": derived_sha,
        },
        "blockers": blockers,
        "next": "CR03-P03 Temporal Vertex-Deformation Proof"
        if status == "PASS"
        else "STOP — fail-closed",
    }
    return report
