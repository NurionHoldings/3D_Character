"""Low-amplitude diagnostic poses on candidate rig; always return to Neutral."""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .face_clone import snapshot_mesh_vertices, snapshots_equal
from .parameters import GATE2_PARAMETERS


def _pose_bone(arm_obj, name: str):
    return arm_obj.pose.bones.get(name)


def reset_pose(arm_obj) -> None:
    from mathutils import Matrix

    for pb in arm_obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    arm_obj.update_tag()


def apply_diagnostic_poses(arm_obj, axes, head_height: float) -> Dict:
    """Apply sequential low-amp poses; return per-pose deform metrics; reset neutral."""
    import bpy

    amp = GATE2_PARAMETERS["diagnosticAmplitudes"]
    hh = max(float(head_height), 1e-4)
    cand = bpy.data.objects.get("NURION_FaceCandidate")
    if cand is None:
        raise RuntimeError("NURION_FaceCandidate missing")

    neutral = snapshot_mesh_vertices(cand)

    def eval_snap():
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        ev = cand.evaluated_get(deps)
        me = ev.to_mesh()
        try:
            return [(float(v.co.x), float(v.co.y), float(v.co.z)) for v in me.vertices]
        finally:
            ev.to_mesh_clear()

    def max_drift(a, b):
        m = 0.0
        for p, q in zip(a, b):
            d = math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)
            if d > m:
                m = d
        return m

    results = {}
    # Jaw open 10%: small downward translate in bone local Y (stable vs rotation axis ambiguity)
    reset_pose(arm_obj)
    pb = _pose_bone(arm_obj, "jaw")
    if pb:
        pb.location = (0.0, amp["jawOpen"] * 0.10 * hh, 0.0)
    bpy.context.view_layer.update()
    results["jawOpen"] = {"maxDriftEU": max_drift(neutral, eval_snap()) / hh}

    reset_pose(arm_obj)
    for name, sign in (("mouth.corner.L", -1.0), ("mouth.corner.R", 1.0)):
        pb = _pose_bone(arm_obj, name)
        if pb:
            pb.location = (sign * amp["corner"] * 0.08 * hh, 0.0, amp["corner"] * 0.03 * hh)
    bpy.context.view_layer.update()
    results["corners"] = {"maxDriftEU": max_drift(neutral, eval_snap()) / hh}

    reset_pose(arm_obj)
    for name, zsign in (("lip.upper.center", 1.0), ("lip.lower.center", -1.0)):
        pb = _pose_bone(arm_obj, name)
        if pb:
            pb.location = (0.0, 0.0, zsign * amp["lip"] * 0.06 * hh)
    bpy.context.view_layer.update()
    results["lips"] = {"maxDriftEU": max_drift(neutral, eval_snap()) / hh}

    reset_pose(arm_obj)
    for name, sign in (("cheek.L", -1.0), ("cheek.R", 1.0)):
        pb = _pose_bone(arm_obj, name)
        if pb:
            pb.location = (sign * amp["cheek"] * 0.06 * hh, amp["cheek"] * 0.03 * hh, 0.0)
    bpy.context.view_layer.update()
    results["cheeks"] = {"maxDriftEU": max_drift(neutral, eval_snap()) / hh}

    reset_pose(arm_obj)
    for side in ("L", "R"):
        for part in ("inner", "mid", "outer"):
            pb = _pose_bone(arm_obj, f"brow.{part}.{side}")
            if pb:
                pb.location = (0.0, 0.0, amp["brow"] * 0.05 * hh)
    bpy.context.view_layer.update()
    results["brows"] = {"maxDriftEU": max_drift(neutral, eval_snap()) / hh}

    reset_pose(arm_obj)
    bpy.context.view_layer.update()
    after = eval_snap()
    mesh_rest = snapshot_mesh_vertices(cand)
    return_error = max_drift(neutral, after) / hh
    rest_identical = snapshots_equal(neutral, mesh_rest, eps=1e-9)

    # Low-amp: measurable deformation, controlled (< 25% head height for low-intensity probes)
    low_amp_ok = all(1e-8 < v["maxDriftEU"] < 0.25 for v in results.values())
    # Neutral return: residual below 1e-4 head-height units (float eval tolerance)
    neutral_ok = return_error <= 1e-4

    return {
        "poses": results,
        "neutralReturnErrorEU": return_error,
        "neutralMeshDatablockUnchanged": rest_identical,
        "lowAmplitudeDeform": "PASS" if low_amp_ok else "FAIL",
        "neutralReturn": "PASS" if neutral_ok else "FAIL",
    }
