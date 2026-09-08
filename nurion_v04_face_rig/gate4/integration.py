"""Gate 4 orchestrator — Phoneme Timing & Coarticulation on clone candidate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .coarticulation import blend_axes_at_ms, enforce_min_hold, validate_order
from .parameters import GATE4_PARAMETERS, parameter_hash
from .timing_checks import detect_abrupt_pops, sample_timeline_semantics
from .timelines import all_timelines
from .validator import build_validation, verify_upstream


def _sha_json(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class Gate4Result:
    role: str
    asset: str
    profile: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def _create_objects() -> Dict:
    import bpy

    names = GATE4_PARAMETERS["objects"]
    for n in names.values():
        old = bpy.data.objects.get(n)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
    out = {}
    for key, n in names.items():
        obj = bpy.data.objects.new(n, None)
        obj.empty_display_type = "PLAIN_AXES"
        bpy.context.collection.objects.link(obj)
        out[key] = n
    return out


def _build_stack(mesh_name: str = ""):
    import bpy

    from nurion_universal_eye.gate1.universal_face_basis import build_universal_face_basis

    from ..gate2.face_clone import create_face_candidate, snapshot_mesh_vertices
    from ..gate2.face_guides import compute_landmarks, create_guides
    from ..gate2.neutral_rig import assign_limited_weights, build_neutral_rig
    from ..gate3.viseme_axes import mouth_unit, reset_pose

    basis = build_universal_face_basis(mesh_name=mesh_name or "")
    source = bpy.data.objects.get(basis.mesh_name)
    src_before = snapshot_mesh_vertices(source)
    clone = create_face_candidate(source)
    cand = clone["candidateObject"]
    landmarks = compute_landmarks(cand, basis.axes, basis.axes.head_height)
    create_guides(landmarks, basis.axes)
    rig = build_neutral_rig(landmarks, basis.axes, cand_mesh=cand)
    arm = bpy.data.objects.get(rig["armature"])
    assign_limited_weights(cand, arm, landmarks, basis.axes)
    reset_pose(arm)
    bpy.context.view_layer.update()
    src_after = snapshot_mesh_vertices(source)
    return {
        "basis": basis,
        "source": source,
        "cand": cand,
        "arm": arm,
        "landmarks": landmarks,
        "mu": mouth_unit(landmarks),
        "src_before": src_before,
        "src_after": src_after,
    }


def run_gate4_once(*, mesh_name: str = "", root: Optional[Path] = None) -> Dict:
    import bpy

    from ..gate3.viseme_axes import apply_axes, reset_pose
    from ..gate3.viseme_metrics import eval_world_verts, max_drift, measure_state, snapshot_local

    root = Path(root) if root else Path(__file__).resolve().parents[2]
    stack = _build_stack(mesh_name=mesh_name)
    objs = _create_objects()
    timelines = all_timelines()
    min_hold = int(GATE4_PARAMETERS["minConsonantHoldMs"])
    limits = GATE4_PARAMETERS["axisLimitsMU"]

    order_agg = {"phonemeOrderError": 0, "timelineOverlapConflict": 0, "missingShortPhoneme": 0}
    fps_reports = []
    pop_reports = []
    weight_overflow = 0
    safety = {"lipIntersection": 0, "lipOrderInversion": 0, "nonMouthLeak": 0, "weightOverflow": 0}
    sentence_summaries = []
    primaries_seen = set()

    cand = stack["cand"]
    arm = stack["arm"]
    basis = stack["basis"]
    landmarks = stack["landmarks"]
    mu = stack["mu"]
    rest_local = snapshot_local(cand)
    rest_world = eval_world_verts(cand)
    jaw = arm.data.bones.get("jaw")
    jaw_head = tuple(jaw.head_local) if jaw else None
    jaw_tail = tuple(jaw.tail_local) if jaw else None

    for name, doc in timelines.items():
        phonemes = enforce_min_hold(list(doc["phonemes"]), min_hold)
        order = validate_order(phonemes)
        for k in order_agg:
            order_agg[k] += order[k]

        fps = sample_timeline_semantics(phonemes, GATE4_PARAMETERS["fpsSet"])
        fps_reports.append({"sentence": name, **fps})
        pops = detect_abrupt_pops(phonemes)
        pop_reports.append({"sentence": name, **pops})

        # sample midpoints + a few transitions for safety
        sample_ms = []
        for p in phonemes:
            sample_ms.append(0.5 * (p["startMs"] + p["endMs"]))
            sample_ms.append(float(p["startMs"]))
        sample_ms = sorted(set(int(x) for x in sample_ms))

        sentence_primary = []
        for t in sample_ms:
            axes, meta = blend_axes_at_ms(phonemes, float(t))
            if meta.get("weightOverflow"):
                weight_overflow += 1
            primaries_seen.add(meta.get("primary"))
            sentence_primary.append(meta.get("primary"))
            apply_axes(arm, axes, mu, limits)
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
            safety["lipIntersection"] = max(safety["lipIntersection"], m.get("lipSelfIntersection", 0))
            safety["lipOrderInversion"] = max(safety["lipOrderInversion"], m.get("lipOrderInversion", 0))
            safety["nonMouthLeak"] = max(safety["nonMouthLeak"], 1 if m.get("nonMouthLeak", 0) > 0 else 0)
            if m.get("nonMouthLeak", 0) > 0 or m.get("lipOrderInversion", 0) > 0:
                # restore previous safe REST axes
                reset_pose(arm)
                bpy.context.view_layer.update()

        sentence_summaries.append(
            {
                "name": name,
                "phonemeCount": len(phonemes),
                "primaries": sentence_primary[:12],
                "fpsStatus": fps["status"],
                "popCount": pops["abruptTransitionPop"],
            }
        )

    safety["weightOverflow"] = weight_overflow

    # final REST
    reset_pose(arm)
    bpy.context.view_layer.update()
    after_local = snapshot_local(cand)
    rest_err = max_drift(rest_local, after_local) / max(mu, 1e-6)

    fps_all = {
        "status": "PASS" if all(r["status"] == "PASS" for r in fps_reports) else "FAIL",
        "fpsSemanticMismatches": sum(r["fpsSemanticMismatches"] for r in fps_reports),
        "reports": fps_reports,
    }
    pops_all = {
        "abruptTransitionPop": sum(r["abruptTransitionPop"] for r in pop_reports),
        "status": "PASS" if all(r["status"] == "PASS" for r in pop_reports) else "FAIL",
        "reports": pop_reports,
    }

    readability = "PASS" if len(primaries_seen) >= 4 else "FAIL"
    hashes = verify_upstream(root)
    src_mut = 0 if max_drift(stack["src_before"], stack["src_after"]) < 1e-9 else 1

    validation = build_validation(
        source_mutation=src_mut,
        order=order_agg,
        fps=fps_all,
        pops=pops_all,
        safety=safety,
        rest_return_error=rest_err,
        hashes=hashes,
        readability=readability,
    )

    profile = {
        "schema": "NURION_V04_GATE4_PROFILE",
        "version": GATE4_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "objects": objs,
        "mouthUnit": mu,
        "sentences": sentence_summaries,
        "primariesSeen": sorted(primaries_seen),
        "audioFeatureExtraction": "INACTIVE",
        "speechToPhoneme": "INACTIVE",
        "realTimeLipSync": "HOLD",
        "sourceRigApplication": "DENY",
    }
    stable = {
        "parameterHash": parameter_hash(),
        "verdict": validation["verdict"],
        "order": order_agg,
        "fpsStatus": fps_all["status"],
        "popCount": pops_all["abruptTransitionPop"],
        "primariesSeen": sorted(primaries_seen),
        "restReturnError": round(rest_err, 8),
        "safety": safety,
    }
    return {"profile": profile, "validation": validation, "stable": stable}


def run_gate4(
    *,
    root: Optional[Path] = None,
    role: str = "DEVELOPMENT",
    asset: str = "tennis",
    mesh_name: str = "",
    runs: int = 3,
    clean_import_cb=None,
) -> Gate4Result:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    notes: List[str] = []
    results = []
    for _ in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate4_once(mesh_name=mesh_name, root=root))

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

    return Gate4Result(
        role=role,
        asset=asset,
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
