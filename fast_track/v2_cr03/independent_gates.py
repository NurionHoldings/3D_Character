"""CR03 independent gates — recompute from GLB only (do not trust report PASS)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.v2_cr03.glb_measure import sha256_file
from fast_track.v2_cr03.p03_temporal_proof import prove_temporal_vertex_deformation
from fast_track.v2_cr03.p04_regression import run_idle_talking_regression
from fast_track.v2_cr03.pins import APPROVED_SPEC_DIGEST, CR02_R2_DERIVED_SHA


def run_cr03_independent_gates(
    *,
    input_glb: Path,
    derived_glb: Path,
    track: dict[str, Any],
    spec_path: Path,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    gates: dict[str, Any] = {}

    in_sha = sha256_file(input_glb)
    g01 = in_sha == CR02_R2_DERIVED_SHA
    gates["CR03-G01"] = {"status": "PASS" if g01 else "BLOCKED", "inputSha256": in_sha}
    if not g01:
        blockers.append({"code": "G01_INPUT_SHA"})

    approved = (track.get("humanSpecGate") or {}).get("approvedSpecDigest")
    g02 = approved == APPROVED_SPEC_DIGEST
    gates["CR03-G02"] = {"status": "PASS" if g02 else "BLOCKED", "approvedSpecDigest": approved}
    if not g02:
        blockers.append({"code": "G02_SPEC_DIGEST"})

    # Temporal proof (reads GLB)
    p03 = prove_temporal_vertex_deformation(
        derived_glb=derived_glb, track=track, spec_path=spec_path
    )
    gates["CR03-G10"] = {
        "status": p03["status"],
        "runtimeVertexProofDigest": p03.get("runtimeVertexProofDigest"),
        "peakActivation": p03.get("peakActivation"),
        "stateDistinctness": p03.get("stateDistinctness"),
        "restoration": p03.get("restoration"),
    }
    if p03["status"] != "PASS":
        blockers.append({"code": "G10_TEMPORAL_VERTEX", "detail": p03.get("blockers")})

    p04 = run_idle_talking_regression(
        input_glb=input_glb, derived_glb=derived_glb, track=track, spec_path=spec_path
    )
    gates["CR03-G15"] = {
        "status": p04["status"],
        "regressionDigest": p04.get("regressionDigest"),
        "coexistence": p04.get("coexistence"),
    }
    if p04["status"] != "PASS":
        blockers.append({"code": "G15_REGRESSION", "detail": p04.get("blockers")})

    gates["CR03-G20"] = {
        "status": "HUMAN_FINAL_ONLY",
        "note": "Agent must not declare Human PASS",
    }

    status = "PASS" if not blockers else "BLOCKED"
    return {
        "schema": "NURION_V2_CR03_INDEPENDENT_GATE_MATRIX_V1",
        "changeRequestId": "V2-CR-03",
        "status": status,
        "derivedSha256": sha256_file(derived_glb),
        "gates": gates,
        "blockers": blockers,
        "independentRunner": "measures GLB weights animation + V(t) — does not trust report PASS fields",
        "agentCeiling": "READY_FOR_HUMAN_AUDIT",
        "CR03-G20": "HUMAN_FINAL_ONLY",
    }
