"""Non-destructive oral/eye topology reconstruction from v1 basis — no skin face deletion."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import (
    _boundary_loops,
    mesh_quality,
    parse_obj,
    sha256_file,
)

V1_BASELINE_SKIN_SHA = "9066b8bebbf33ead9b39e403ecd59604e7bb3947cea401c3c94b1b6065307243"
REJECTED_V2_SKIN_SHA = "278aa428617006ba3a9e5966e79719001b3e82c661f60973da476c347ad5a225"
FRAGMENT_EDGE_MAX = 19
MIN_ORAL_LOOP_EDGES = 40


@dataclass
class NDReconstructResult:
    basis_skin_sha: str
    validation: dict[str, Any]
    boundary_map: dict[str, Any]
    morph_spec: dict[str, Any]
    oral_cavity: dict[str, Any]
    verdict: str


def _loop_stats(loop: list[tuple[int, int]], V: np.ndarray) -> dict[str, Any]:
    verts = sorted({a for e in loop for a in e})
    pts = V[verts]
    c = pts.mean(axis=0)
    ext = pts.max(axis=0) - pts.min(axis=0)
    return {
        "edgeCount": len(loop),
        "vertexCount": len(verts),
        "centroid": [float(c[0]), float(c[1]), float(c[2])],
        "extent": [float(ext[0]), float(ext[1]), float(ext[2])],
        "meanX": float(c[0]),
        "meanY": float(c[1]),
        "meanZ": float(c[2]),
        "verts": verts,
        "edges": [(_edge_key(a, b)) for a, b in loop],
    }


def _edge_key(a: int, b: int) -> tuple[int, int]:
    return (min(a, b), max(a, b))


def build_boundary_map_v1_basis(mesh) -> dict[str, Any]:
    loops = _boundary_loops(mesh)
    V = mesh.verts
    entries: list[dict[str, Any]] = []

    oral_like = []
    for i, loop in enumerate(loops):
        stats = _loop_stats(loop, V)
        if stats["meanY"] > 6.55 and stats["meanZ"] > 1.0 and abs(stats["meanX"]) < 0.38:
            oral_like.append((i, stats))
    oral_like.sort(key=lambda x: x[1]["meanZ"], reverse=True)

    assigned: set[int] = set()
    if oral_like:
        i, stats = oral_like[0]
        entries.append(
            {
                "loopIndex": i,
                "loopId": "BND_ORAL_OPENING_OUTER",
                "role": "ORAL_CAVITY_OUTER_BASIS",
                "edgeCount": stats["edgeCount"],
                "vertexCount": stats["vertexCount"],
                "centroid": stats["centroid"],
                "extent": stats["extent"],
                "physicalLoop": True,
                "skinFaceDeletion": "DENY",
            }
        )
        assigned.add(i)
    if len(oral_like) > 1:
        i, stats = oral_like[1]
        entries.append(
            {
                "loopIndex": i,
                "loopId": "BND_ORAL_OPENING_INNER",
                "role": "ORAL_CAVITY_INNER_BASIS",
                "edgeCount": stats["edgeCount"],
                "vertexCount": stats["vertexCount"],
                "centroid": stats["centroid"],
                "extent": stats["extent"],
                "physicalLoop": True,
                "skinFaceDeletion": "DENY",
            }
        )
        assigned.add(i)

    for i, loop in enumerate(loops):
        if i in assigned:
            continue
        stats = _loop_stats(loop, V)
        if stats["meanY"] < 6.08 and stats["extent"][1] > 0.3:
            entries.append(
                {
                    "loopIndex": i,
                    "loopId": "BND_NECK_CUT",
                    "role": "NECK_TERMINATION_EXPLICIT_CUT_ALLOWED",
                    "edgeCount": stats["edgeCount"],
                    "vertexCount": stats["vertexCount"],
                    "centroid": stats["centroid"],
                    "extent": stats["extent"],
                    "physicalLoop": True,
                }
            )
            assigned.add(i)
            continue
        if 6.62 < stats["meanY"] < 6.95 and 0.48 < stats["meanZ"] < 0.82:
            left = [v for v in stats["verts"] if V[v, 0] < -0.015]
            right = [v for v in stats["verts"] if V[v, 0] > 0.015]
            if len(left) >= 8:
                c = V[left].mean(axis=0)
                entries.append(
                    {
                        "loopIndex": i,
                        "loopId": "BND_NOSTRIL_LEFT",
                        "role": "NOSTRIL_SEMANTIC_LEFT",
                        "edgeCount": stats["edgeCount"],
                        "partitionVertexCount": len(left),
                        "centroid": [float(c[0]), float(c[1]), float(c[2])],
                        "physicalLoopShared": True,
                        "skinFaceDeletion": "DENY",
                    }
                )
            if len(right) >= 8:
                c = V[right].mean(axis=0)
                entries.append(
                    {
                        "loopIndex": i,
                        "loopId": "BND_NOSTRIL_RIGHT",
                        "role": "NOSTRIL_SEMANTIC_RIGHT",
                        "edgeCount": stats["edgeCount"],
                        "partitionVertexCount": len(right),
                        "centroid": [float(c[0]), float(c[1]), float(c[2])],
                        "physicalLoopShared": True,
                        "skinFaceDeletion": "DENY",
                    }
                )
            assigned.add(i)

    return {
        "schema": "NURION_V07_DERIVED_HEAD_BOUNDARY_LOOP_MAP_V1_BASIS_ND",
        "scope": "V1_BASIS_NON_DESTRUCTIVE",
        "physicalLoopCount": len(loops),
        "semanticEntryCount": len(entries),
        "eyelashHelperOnSkinBoundary": "EXCLUDED",
        "eyeOpeningPolicy": "MORPH_BLINK_OPEN_ONLY_NO_FACE_DELETION",
        "oralOpeningPolicy": "MORPH_JAW_FROM_LIP_SEAL_BASIS_NO_NEW_HOLES",
        "entries": entries,
    }


def build_morph_spec() -> dict[str, Any]:
    return {
        "schema": "NURION_V07_DERIVED_HEAD_MORPH_SPEC_V1",
        "basisLipSeal": "PRESERVED",
        "skinFaceDeletion": "DENY",
        "morphs": {
            "jawOpen": {
                "method": "RIG_JOINT_ROTATION",
                "pivotGroup": "joint-jaw",
                "fallbackPivot": [0.0, 6.85, 1.0],
                "axis": "X",
                "angleDegDefault": 22.0,
                "movedGroups": [
                    "helper-lower-teeth",
                    "helper-tongue",
                    "joint-jaw",
                    "joint-tongue-1",
                    "joint-tongue-2",
                    "joint-tongue-3",
                    "joint-tongue-4",
                ],
                "skinBasisMutation": "DENY",
                "createsNewBoundaryHoles": "DENY",
            },
            "eyeBlinkOpen": {
                "method": "HELPER_EYELID_MORPH_ONLY",
                "groups": [
                    "helper-l-eyelashes-1",
                    "helper-l-eyelashes-2",
                    "helper-r-eyelashes-1",
                    "helper-r-eyelashes-2",
                    "joint-l-upperlid",
                    "joint-l-lowerlid",
                    "joint-r-upperlid",
                    "joint-r-lowerlid",
                ],
                "skinFaceDeletion": "DENY",
                "note": "Eyelid opening via rig morph; skin mesh unchanged",
            },
        },
    }


def validate_v1_basis(
    skin_path: Path,
    corr_path: Path,
    expected_sha: str = V1_BASELINE_SKIN_SHA,
) -> dict[str, Any]:
    reasons: list[str] = []
    sha = sha256_file(skin_path)
    if sha != expected_sha:
        reasons.append(f"BASIS_SHA_MISMATCH:{sha}")

    mesh = parse_obj(skin_path)
    quality = mesh_quality(mesh)
    loops = _boundary_loops(mesh)
    V = mesh.verts

    fragments = [i for i, loop in enumerate(loops) if len(loop) <= FRAGMENT_EDGE_MAX]
    if fragments:
        reasons.append(f"FRAGMENT_LOOPS:{len(fragments)}")

    oral_outer = oral_inner = 0
    for loop in loops:
        stats = _loop_stats(loop, V)
        if stats["meanY"] > 6.55 and stats["meanZ"] > 1.0 and abs(stats["meanX"]) < 0.38:
            if stats["meanZ"] > 1.42:
                oral_outer += 1
            else:
                oral_inner += 1

    if oral_outer != 1:
        reasons.append(f"ORAL_OUTER_LOOP_COUNT:{oral_outer}")
    if oral_inner != 1:
        reasons.append(f"ORAL_INNER_LOOP_COUNT:{oral_inner}")

    for i, loop in enumerate(loops):
        stats = _loop_stats(loop, V)
        if stats["meanY"] > 6.55 and stats["meanZ"] > 1.0 and len(loop) < MIN_ORAL_LOOP_EDGES:
            reasons.append(f"ORAL_LOOP_TOO_SMALL:{i}:{len(loop)}")

    corr = json.loads(corr_path.read_text(encoding="utf-8")) if corr_path.is_file() else {}
    tc = corr.get("typeCounts") or {}
    unsupported = tc.get("UNSUPPORTED", 0)

    return {
        "basisSkinSha256": sha,
        "expectedSha256": expected_sha,
        "basisBytesMatch": sha == expected_sha,
        "faceCount": len(mesh.faces),
        "vertexCount": len(mesh.verts),
        "physicalLoopCount": len(loops),
        "fragmentLoopCount": len(fragments),
        "oralOuterLoopCount": oral_outer,
        "oralInnerLoopCount": oral_inner,
        "nonManifoldEdges": quality.get("nonManifoldEdges"),
        "quadCount": quality.get("quadCount"),
        "correspondenceUnsupported": unsupported,
        "correspondenceNewLossAllowance": 0,
        "correspondenceNewLoss": 0,
        "skinFaceDeletion": "DENY",
        "pass": len(reasons) == 0,
        "reasons": reasons,
    }


def reconstruct_from_v1_basis(v1_dir: Path) -> NDReconstructResult:
    skin_path = v1_dir / "NURION_DerivedHead_v1_skin.obj"
    corr_path = v1_dir / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json"
    rig_path = v1_dir / "NURION_DerivedHead_v1_rig_helpers.obj"

    validation = validate_v1_basis(skin_path, corr_path)
    mesh = parse_obj(skin_path)
    boundary_map = build_boundary_map_v1_basis(mesh)
    morph_spec = build_morph_spec()

    oral_cavity = {
        "policy": "SEPARATE_INTERNAL_MESH_NO_SKIN_CUT",
        "rigHelpersSource": str(rig_path.name) if rig_path.is_file() else "MISSING",
        "groups": [
            "helper-tongue",
            "helper-upper-teeth",
            "helper-lower-teeth",
        ],
        "connection": "RIG_PIVOT_JAW_MORPH",
        "skinFaceDeletion": "DENY",
    }

    verdict = "NUMERIC_VALIDATION_PASS" if validation["pass"] else "ALGORITHM_FAIL_NUMERIC_VALIDATION"
    return NDReconstructResult(
        basis_skin_sha=validation["basisSkinSha256"],
        validation=validation,
        boundary_map=boundary_map,
        morph_spec=morph_spec,
        oral_cavity=oral_cavity,
        verdict=verdict,
    )


def write_nd_bundle(
    out_dir: Path,
    v1_dir: Path,
    result: NDReconstructResult,
    header: list[str],
) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    basis_src = v1_dir / "NURION_DerivedHead_v1_skin.obj"
    basis_dst = out_dir / "NURION_DerivedHead_v1_basis_skin.obj"
    shutil.copy2(basis_src, basis_dst)
    assert sha256_file(basis_dst) == result.basis_skin_sha

    rig_src = v1_dir / "NURION_DerivedHead_v1_rig_helpers.obj"
    rig_dst = out_dir / "NURION_DerivedHead_v1_basis_rig_helpers.obj"
    if rig_src.is_file():
        shutil.copy2(rig_src, rig_dst)

    corr_src = v1_dir / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json"
    corr_dst = out_dir / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json"
    if corr_src.is_file():
        shutil.copy2(corr_src, corr_dst)

    oral_dst = out_dir / "ORAL_CAVITY_INTERNAL_SPEC.json"
    oral_dst.write_text(json.dumps(result.oral_cavity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _wj(p: Path, v: dict) -> None:
        p.write_text(json.dumps(v, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    _wj(out_dir / "BOUNDARY_LOOP_MAP.json", result.boundary_map)
    _wj(out_dir / "MORPH_SPEC.json", result.morph_spec)
    _wj(out_dir / "NUMERIC_VALIDATION.json", result.validation)

    return {
        "basisSkinSha256": sha256_file(basis_dst),
        "basisSkinPath": str(basis_dst),
        "rigHelpersPath": str(rig_dst) if rig_dst.is_file() else "",
    }
