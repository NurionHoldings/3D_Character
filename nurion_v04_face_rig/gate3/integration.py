"""Gate 3 orchestrator — Viseme Shape Basis on Gate2 clone candidate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .parameters import GATE3_PARAMETERS, parameter_hash
from .validator import build_validation, verify_upstream_hashes
from .viseme_axes import apply_axes, mouth_unit, recipe_for, reset_pose
from .viseme_evidence import multiview_readability
from .viseme_metrics import (
    create_control_objects,
    eval_world_verts,
    max_drift,
    measure_state,
    snapshot_local,
)


def _sha_json(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class Gate3Result:
    role: str
    asset: str
    profile: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def _build_gate2_stack(mesh_name: str = ""):
    """Build Gate2 clone/guides/rig without mutating Gate2 locked sources beyond import."""
    import bpy

    from nurion_universal_eye.gate1.universal_face_basis import build_universal_face_basis

    from ..gate2.face_clone import create_face_candidate, snapshot_mesh_vertices
    from ..gate2.face_guides import compute_landmarks, create_guides
    from ..gate2.neutral_rig import assign_limited_weights, build_neutral_rig

    basis = build_universal_face_basis(mesh_name=mesh_name or "")
    source = bpy.data.objects.get(basis.mesh_name)
    if source is None:
        raise RuntimeError("source mesh missing")
    src_before = snapshot_mesh_vertices(source)
    clone = create_face_candidate(source)
    cand = clone["candidateObject"]
    landmarks = compute_landmarks(cand, basis.axes, basis.axes.head_height)
    guides = create_guides(landmarks, basis.axes)
    rig = build_neutral_rig(landmarks, basis.axes, cand_mesh=cand)
    arm = bpy.data.objects.get(rig["armature"])
    weights = assign_limited_weights(cand, arm, landmarks, basis.axes)
    reset_pose(arm)
    bpy.context.view_layer.update()
    src_after = snapshot_mesh_vertices(source)
    return {
        "basis": basis,
        "source": source,
        "src_before": src_before,
        "src_after": src_after,
        "cand": cand,
        "arm": arm,
        "landmarks": landmarks,
        "guides": guides,
        "weights": weights,
    }


def run_gate3_once(*, mesh_name: str = "", root: Optional[Path] = None) -> Dict:
    import bpy

    root = Path(root) if root else Path(__file__).resolve().parents[2]
    stack = _build_gate2_stack(mesh_name=mesh_name)
    basis = stack["basis"]
    cand = stack["cand"]
    arm = stack["arm"]
    landmarks = stack["landmarks"]
    mu = mouth_unit(landmarks)

    # tongue availability from gate1-style oral inward verts
    tongue_available = False
    oral_inward = 0
    inv = basis.axes.matrix_world_inv
    hh = basis.axes.head_height
    for p in eval_world_verts(cand):
        loc = inv @ p
        if abs(loc.x) < 0.12 * hh and loc.y < 0.08 * hh and -0.02 * hh < loc.z < 0.22 * hh:
            oral_inward += 1
    tongue_mode = "AVAILABLE" if tongue_available else "LIMITED_NO_FAKE_TONGUE_MESH"

    controls = create_control_objects(tongue_mode)
    rest_local = snapshot_local(cand)
    rest_world = eval_world_verts(cand)
    jaw = arm.data.bones.get("jaw")
    jaw_head = tuple(jaw.head_local) if jaw else None
    jaw_tail = tuple(jaw.tail_local) if jaw else None

    limits = GATE3_PARAMETERS["axisLimitsMU"]
    state_metrics: Dict[str, Dict] = {}
    signatures: Dict[str, List[float]] = {}
    applied_log = []

    prev_pass_pose = {}
    for name in GATE3_PARAMETERS["sequence"]:
        label, recipe = recipe_for(name, tongue_available=False)
        try:
            apply_axes(arm, recipe, mu, limits)
            ctrl = bpy.data.objects.get(controls["control"])
            if ctrl:
                ctrl["visemeState"] = label
            m = measure_state(
                cand=cand,
                arm=arm,
                axes=basis.axes,
                landmarks=landmarks,
                rest_local=rest_local,
                rest_world=rest_world,
                mu=mu,
                jaw_rest_head=jaw_head,
                jaw_rest_tail=jaw_tail,
            )
            # auto restore only on critical safety violations
            critical = (
                m["nonMouthLeak"] > 0
                or m["lipOrderInversion"] > 0
                or m["faceSurfaceTearing"] > 0
                or m["lipSelfIntersection"] > 0
            )
            if critical:
                apply_axes(arm, prev_pass_pose, mu, limits)
                m["autoRestored"] = True
                m["failedRecipe"] = label
            else:
                prev_pass_pose = dict(recipe)
                m["autoRestored"] = False
            state_metrics[label] = m
            signatures[label] = m["signature"]
            applied_log.append({"state": label, "recipe": recipe, "autoRestored": m["autoRestored"]})
        except Exception as exc:  # noqa: BLE001
            apply_axes(arm, prev_pass_pose, mu, limits)
            state_metrics[label] = {"error": str(exc), "nonMouthLeak": 99}
            applied_log.append({"state": label, "error": str(exc)})

    # final REST
    reset_pose(arm)
    bpy.context.view_layer.update()
    after_local = snapshot_local(cand)
    rest_err = max_drift(rest_local, after_local) / mu
    # also evaluated
    after_world = eval_world_verts(cand)
    rest_err = max(rest_err, max((a - b).length for a, b in zip(rest_world, after_world)) / mu)

    readability = multiview_readability(signatures, GATE3_PARAMETERS["multiviewYawDeg"])
    hashes = verify_upstream_hashes(root)
    src_mut = 0 if stack["src_before"] == stack["src_after"] else 1
    # float-safe source compare
    if src_mut == 1:
        src_mut = 0 if max_drift(stack["src_before"], stack["src_after"]) < 1e-9 else 1

    jaw_drift = 0.0
    if jaw is not None and jaw_head is not None:
        from mathutils import Vector

        jaw_drift = max(
            (Vector(jaw.head_local) - Vector(jaw_head)).length,
            (Vector(jaw.tail_local) - Vector(jaw_tail)).length,
        )

    validation = build_validation(
        source_mutation=src_mut,
        rest_return_error_mu=rest_err,
        jaw_axis_drift=jaw_drift,
        state_metrics=state_metrics,
        readability=readability,
        hashes=hashes,
        tongue_mode=tongue_mode,
    )

    profile = {
        "schema": "NURION_V04_GATE3_PROFILE",
        "version": GATE3_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "mouthUnit": mu,
        "tongueMode": tongue_mode,
        "oralInwardVertexCount": oral_inward,
        "controls": controls,
        "sequence": GATE3_PARAMETERS["sequence"],
        "applied": applied_log,
        "stateMetrics": {k: {kk: vv for kk, vv in v.items() if kk != "error"} for k, v in state_metrics.items()},
        "audioInput": "INACTIVE",
        "automaticLipSync": "HOLD",
        "sourceRigApplication": "DENY",
    }
    stable = {
        "parameterHash": parameter_hash(),
        "mouthUnitRound": round(mu, 6),
        "tongueMode": tongue_mode,
        "verdict": validation["verdict"],
        "signatures": signatures,
        "restReturnErrorMU": round(rest_err, 8),
        "nonMouthLeakMax": validation["gates"]["NON_MOUTH_VERTEX_LEAK"],
        "lipOrderInversion": validation["gates"]["LIP_ORDER_INVERSION"],
    }
    return {"profile": profile, "validation": validation, "stable": stable}


def run_gate3(
    *,
    root: Optional[Path] = None,
    role: str = "DEVELOPMENT",
    asset: str = "tennis",
    mesh_name: str = "",
    runs: int = 3,
    clean_import_cb=None,
) -> Gate3Result:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    notes: List[str] = []
    results = []
    for _ in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate3_once(mesh_name=mesh_name, root=root))

    stables = [r["stable"] for r in results]
    det = "FAIL"
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det = "PASS" if all(_sha_json(s) == h0 for s in stables[1:3]) else "FAIL"
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

    return Gate3Result(
        role=role,
        asset=asset,
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
