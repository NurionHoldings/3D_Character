"""Gate 2 orchestrator — Procedural Face Guide & Neutral Rig Candidate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .diagnostic_poses import apply_diagnostic_poses
from .face_clone import create_face_candidate, snapshot_mesh_vertices
from .face_guides import compute_landmarks, create_guides
from .neutral_rig import assign_limited_weights, build_neutral_rig
from .parameters import GATE2_PARAMETERS, parameter_hash
from .validator import (
    build_gate_report,
    validate_bone_hierarchy,
    validate_guides_inside_face,
    validate_lr_swap,
    verify_hashes,
)


def _sha_json(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class Gate2Result:
    role: str
    asset: str
    profile: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def run_gate2_once(*, mesh_name: str = "", root: Optional[Path] = None) -> Dict:
    import bpy

    from nurion_universal_eye.gate1.universal_face_basis import build_universal_face_basis

    root = Path(root) if root else Path(__file__).resolve().parents[2]
    basis = build_universal_face_basis(mesh_name=mesh_name or "")
    source = bpy.data.objects.get(basis.mesh_name)
    if source is None or source.type != "MESH":
        raise RuntimeError("source mesh missing")

    src_before = snapshot_mesh_vertices(source)
    basis_before = basis.axes

    clone = create_face_candidate(source)
    cand = clone["candidateObject"]
    landmarks = compute_landmarks(cand, basis.axes, basis.axes.head_height)
    guides = create_guides(landmarks, basis.axes)
    rig = build_neutral_rig(landmarks, basis.axes, cand_mesh=cand)
    arm = bpy.data.objects.get(rig["armature"])
    weights = assign_limited_weights(cand, arm, landmarks, basis.axes)
    poses = apply_diagnostic_poses(arm, basis.axes, basis.axes.head_height)

    src_after = snapshot_mesh_vertices(source)
    # rebuild basis after to ensure no drift from our ops (should be identical)
    basis2 = build_universal_face_basis(mesh_name=mesh_name or "")
    hashes = verify_hashes(root)
    guide_val = validate_guides_inside_face(landmarks, basis.axes, basis.axes.head_height)
    lr_val = validate_lr_swap(landmarks, basis.axes)
    hierarchy = validate_bone_hierarchy(arm)
    validation = build_gate_report(
        source_before=src_before,
        source_after=src_after,
        clone_info=clone,
        guide_val=guide_val,
        lr_val=lr_val,
        hierarchy=hierarchy,
        weights=weights,
        poses=poses,
        hashes=hashes,
        basis_before=basis_before,
        basis_after=basis2.axes,
    )

    lm_out = {k: [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)] for k, v in landmarks.items()}
    profile = {
        "schema": "NURION_V04_GATE2_PROFILE",
        "version": GATE2_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "sourceMesh": source.name,
        "candidateMesh": cand.name,
        "armature": rig["armature"],
        "bones": rig["bones"],
        "guides": guides,
        "landmarksWorld": lm_out,
        "weights": {k: weights[k] for k in ("weightedVertexCount", "nonFaceWeightLeak", "teethWeightLeak", "deformBones")},
        "visemeGeneration": "DENY",
        "lipSyncGeneration": "DENY",
        "sourceMutation": validation["gates"]["SOURCE_MUTATION"],
    }
    # strip non-serializable
    clone_pub = {k: v for k, v in clone.items() if k != "candidateObject" and k != "sourceSnapshot"}
    return {
        "profile": profile,
        "validation": validation,
        "clone": clone_pub,
        "stable": {
            "parameterHash": parameter_hash(),
            "bones": sorted(rig["bones"]),
            "weightedVertexCount": weights["weightedVertexCount"],
            "nonFaceWeightLeak": weights["nonFaceWeightLeak"],
            "teethWeightLeak": weights["teethWeightLeak"],
            "guideOutsideFace": guide_val["guideOutsideFace"],
            "lrSwap": lr_val["lrSwap"],
            "verdict": validation["verdict"],
            "lowAmplitudeDeform": poses.get("lowAmplitudeDeform"),
            "neutralReturn": poses.get("neutralReturn"),
        },
    }


def run_gate2(
    *,
    root: Optional[Path] = None,
    role: str = "DEVELOPMENT",
    asset: str = "tennis",
    mesh_name: str = "",
    runs: int = 3,
    clean_import_cb=None,
) -> Gate2Result:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    notes: List[str] = []
    results = []
    for _ in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate2_once(mesh_name=mesh_name, root=root))

    stables = [r["stable"] for r in results]
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det = "PASS" if all(_sha_json(s) == h0 for s in stables[1:3]) else "FAIL"
    else:
        det = "FAIL"
        notes.append("insufficient runs")
    if det != "PASS":
        notes.append("3x determinism mismatch")

    last = results[-1]
    validation = dict(last["validation"])
    validation["gates"] = dict(validation["gates"])
    validation["gates"]["DETERMINISM_3X"] = det
    if det != "PASS":
        validation["fails"] = list(validation.get("fails") or []) + ["DETERMINISM_3X"]
        validation["verdict"] = "FAIL"

    profile = dict(last["profile"])
    profile["role"] = role
    profile["asset"] = asset
    profile["determinism3x"] = det
    profile["validation"] = validation

    return Gate2Result(
        role=role,
        asset=asset,
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
