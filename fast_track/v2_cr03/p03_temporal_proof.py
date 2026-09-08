"""CR03-P03 — Temporal Vertex-Deformation Proof from GLB weights animation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.change_control import require_human_spec_gate, require_no_upstream_mutation
from fast_track.v2_cr03.glb_measure import (
    accessor_raw_bytes,
    canonical_sha256,
    read_f32_vec3,
    sha256_file,
)
from fast_track.v2_cr03.pins import (
    ACTIVATION_THRESHOLD,
    APPROVED_SPEC_DIGEST,
    CR,
    MORPH_INDEX_MAP,
    RESTORATION_TOLERANCE,
    TALKING_ANIMATION_NAME,
    TALKING_TIMELINE,
)

REPORT_SCHEMA = "NURION_V2_CR03_P03_TEMPORAL_VERTEX_DEFORMATION_V1"


def _max_norm(a: np.ndarray) -> float:
    if len(a) == 0:
        return 0.0
    return float(np.linalg.norm(a, axis=1).max())


def prove_temporal_vertex_deformation(
    *,
    derived_glb: Path,
    track: dict[str, Any],
    spec_path: Path,
) -> dict[str, Any]:
    require_no_upstream_mutation(track)
    gate_digest = require_human_spec_gate(
        track, expected_change_request=CR, spec_path=spec_path
    )
    if gate_digest != APPROVED_SPEC_DIGEST:
        raise PermissionError("SPEC_DIGEST_MISMATCH → IMPLEMENTATION DENIED")

    derived_glb = Path(derived_glb)
    blockers: list[dict[str, Any]] = []
    gltf, blob, _ = load_gltf_document(derived_glb)
    if blob is None:
        return {"status": "BLOCKED", "blockers": [{"code": "MISSING_BIN"}]}

    anims = gltf.get("animations") or []
    talking_idx = next(
        (i for i, a in enumerate(anims) if a.get("name") == TALKING_ANIMATION_NAME), None
    )
    if talking_idx is None:
        blockers.append({"code": "TALKING_ANIM_MISSING"})
        return {"status": "BLOCKED", "blockers": blockers}

    anim = anims[talking_idx]
    ch = next(
        (c for c in (anim.get("channels") or []) if (c.get("target") or {}).get("path") == "weights"),
        None,
    )
    if ch is None:
        blockers.append({"code": "NO_WEIGHTS_ANIMATION_CHANNEL"})
        return {"status": "BLOCKED", "blockers": blockers}
    if (ch.get("target") or {}).get("path") != "weights":
        blockers.append({"code": "ANIMATION_METADATA_ONLY"})

    samp = anim["samplers"][ch["sampler"]]
    t_vals = np.frombuffer(accessor_raw_bytes(blob, gltf, samp["input"]), dtype="<f4").copy()
    w_flat = np.frombuffer(accessor_raw_bytes(blob, gltf, samp["output"]), dtype="<f4").copy()

    mesh = gltf["meshes"][0]
    prim = mesh["primitives"][0]
    targets = prim.get("targets") or []
    morph_count = len(targets)
    if len(w_flat) != len(t_vals) * morph_count:
        blockers.append(
            {
                "code": "WEIGHT_OUTPUT_COUNT_MISMATCH",
                "got": len(w_flat),
                "want": len(t_vals) * morph_count,
            }
        )
        return {"status": "BLOCKED", "blockers": blockers}

    w_mat = w_flat.reshape(len(t_vals), morph_count)
    base = read_f32_vec3(blob, gltf, prim["attributes"]["POSITION"])
    deltas = [read_f32_vec3(blob, gltf, t["POSITION"]) for t in targets]

    ia = MORPH_INDEX_MAP["VISEME_AA"]["targetIndex"]
    io = MORPH_INDEX_MAP["VISEME_OH"]["targetIndex"]
    ie = MORPH_INDEX_MAP["VISEME_EE"]["targetIndex"]
    d_aa, d_oh, d_ee = deltas[ia], deltas[io], deltas[ie]

    frames: list[dict[str, Any]] = []
    positions: list[np.ndarray] = []
    for fi, t in enumerate(t_vals.tolist()):
        w = w_mat[fi]
        # V(t) = V0 + sum_i Δi * wi(t)  — full morph sum; talking uses AA/OH/EE
        vt = base.copy()
        for mi in range(morph_count):
            wi = float(w[mi])
            if wi != 0.0:
                vt = vt + deltas[mi] * wi
        # Equivalent talking-only form for report
        vt_talk = base + d_aa * float(w[ia]) + d_oh * float(w[io]) + d_ee * float(w[ie])
        if not np.allclose(vt, vt_talk, atol=1e-7):
            # Other morph weights must stay 0 in our timeline
            blockers.append({"code": "NON_VISEME_WEIGHTS_ACTIVE", "frame": fi, "weights": w.tolist()})
        max_d = _max_norm(vt - base)
        frames.append(
            {
                "t": t,
                "wAA": float(w[ia]),
                "wOH": float(w[io]),
                "wEE": float(w[ie]),
                "maxVertexDeltaFromBase": max_d,
            }
        )
        positions.append(vt)

    # State frames: 0 neutral, 1 AA, 2 OH, 3 EE, 4 neutral
    if len(positions) < 5:
        blockers.append({"code": "INSUFFICIENT_KEYFRAMES", "count": len(positions)})

    v0, v_aa, v_oh, v_ee, v_end = positions[0], positions[1], positions[2], positions[3], positions[4]
    dist = {
        "AA_vs_OH": _max_norm(v_aa - v_oh),
        "AA_vs_EE": _max_norm(v_aa - v_ee),
        "OH_vs_EE": _max_norm(v_oh - v_ee),
    }
    for k, v in dist.items():
        if v <= ACTIVATION_THRESHOLD:
            blockers.append({"code": "STATES_NOT_DISTINCT", "pair": k, "maxDelta": v})

    peak = {
        "AA": frames[1]["maxVertexDeltaFromBase"],
        "OH": frames[2]["maxVertexDeltaFromBase"],
        "EE": frames[3]["maxVertexDeltaFromBase"],
    }
    for name, val in peak.items():
        if val <= ACTIVATION_THRESHOLD:
            blockers.append({"code": "ACTIVATION_BELOW_THRESHOLD", "state": name, "maxDelta": val})

    start_err = _max_norm(v0 - base)
    end_err = _max_norm(v_end - base)
    if start_err > RESTORATION_TOLERANCE:
        blockers.append({"code": "START_NEUTRAL_FAILURE", "error": start_err})
    if end_err > RESTORATION_TOLERANCE:
        blockers.append({"code": "END_NEUTRAL_RESTORATION_FAILURE", "error": end_err})

    # Timeline alignment
    expected_t = [row[0] for row in TALKING_TIMELINE]
    if not np.allclose(t_vals, np.asarray(expected_t, dtype=np.float32), atol=1e-6):
        blockers.append({"code": "TIMESTAMP_MISMATCH"})

    proof_digest = canonical_sha256(
        {
            "frames": frames,
            "distinctness": dist,
            "startRestoreError": start_err,
            "endRestoreError": end_err,
            "formula": "V(t)=V0+dAA*wAA+dOH*wOH+dEE*wEE",
        }
    )

    status = "PASS" if not blockers else "BLOCKED"
    return {
        "schema": REPORT_SCHEMA,
        "changeRequestId": CR,
        "stage": "CR03-P03",
        "status": status,
        "derivedSha256": sha256_file(derived_glb),
        "gate": {"approvedSpecDigest": gate_digest},
        "talkingAnimationIndex": talking_idx,
        "frames": frames,
        "stateDistinctness": dist,
        "peakActivation": peak,
        "restoration": {
            "startError": start_err,
            "endError": end_err,
            "tolerance": RESTORATION_TOLERANCE,
        },
        "thresholds": {
            "activationThreshold": ACTIVATION_THRESHOLD,
            "restorationTolerance": RESTORATION_TOLERANCE,
        },
        "runtimeVertexProofDigest": proof_digest,
        "blockers": blockers,
        "next": "CR03-P04 Idle + TALKING Coexistence / Regression"
        if status == "PASS"
        else "STOP — fail-closed",
    }
