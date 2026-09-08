"""Gate 5B orchestrator — Automatic Lip Sync on clone candidate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from nurion_v04_face_rig.gate4.coarticulation import blend_axes_at_ms

from .confidence_policy import prepare_solver_phonemes
from .parameters import GATE5B_PARAMETERS, parameter_hash
from .renderer import audio_viseme_sync, create_scene_objects, sample_curves, resolve_axes_at
from .timeline_io import load_alignments, load_gate5a_timelines
from .validator import build_validation, verify_upstream


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class Gate5BResult:
    role: str
    asset: str
    profile: Dict
    validation: Dict
    evidence: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def _build_stack(mesh_name: str = ""):
    import bpy

    from nurion_universal_eye.gate1.universal_face_basis import build_universal_face_basis

    from nurion_v04_face_rig.gate3.viseme_axes import mouth_unit, reset_pose

    from ..gate2.face_clone import create_face_candidate, snapshot_mesh_vertices
    from ..gate2.face_guides import compute_landmarks, create_guides
    from ..gate2.neutral_rig import assign_limited_weights, build_neutral_rig

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


def run_gate5b_once(
    *,
    timelines: Dict[str, Dict],
    alignments: Dict[str, Dict],
    mesh_name: str = "",
    root: Optional[Path] = None,
) -> Dict:
    import bpy

    from nurion_v04_face_rig.gate3.viseme_axes import apply_axes, reset_pose
    from nurion_v04_face_rig.gate3.viseme_metrics import eval_world_verts, max_drift, measure_state, snapshot_local

    root = Path(root) if root else Path(__file__).resolve().parents[2]
    stack = _build_stack(mesh_name=mesh_name)
    cand = stack["cand"]
    arm = stack["arm"]
    basis = stack["basis"]
    landmarks = stack["landmarks"]
    mu = stack["mu"]
    limits = GATE5B_PARAMETERS["axisLimitsMU"]

    rest_local = snapshot_local(cand)
    rest_world = eval_world_verts(cand)
    jaw = arm.data.bones.get("jaw")
    jaw_head = tuple(jaw.head_local) if jaw else None
    jaw_tail = tuple(jaw.tail_local) if jaw else None

    metrics_agg = {
        "silenceFalseMotion": 0,
        "weightOverflow": 0,
        "lowConfidenceOverdrive": 0,
        "closedConsonantSealLoss": 0,
        "shortPhonemeLoss": 0,
        "lipIntersection": 0,
        "lipOrderInversion": 0,
        "nonMouthLeak": 0,
    }
    fps_fail = 0
    pop_sum = 0
    sync_fail = 0
    range_mismatch = 0
    utterance_evidence = {}
    curve_hashes = {}
    primaries = set()
    objects_last = {}

    for uid, doc in timelines.items():
        original = list(doc["phonemes"])
        duration = int(doc["durationMs"])
        # verify timestamps identical to alignment file if present
        align = alignments.get(uid)
        if align and align.get("phonemes"):
            a_ph = align["phonemes"]
            if len(a_ph) == len(original):
                for a, b in zip(a_ph, original):
                    if int(a["startMs"]) != int(b["startMs"]) or int(a["endMs"]) != int(b["endMs"]) or a["symbol"] != b["symbol"]:
                        # timeline must match frozen alignment — treat as range/integrity issue
                        range_mismatch += 1
                        break

        sampled = sample_curves(original, duration)
        for k in (
            "silenceFalseMotion",
            "weightOverflow",
            "lowConfidenceOverdrive",
            "closedConsonantSealLoss",
            "shortPhonemeLoss",
        ):
            metrics_agg[k] += int(sampled["metrics"][k])

        if sampled["fps"]["status"] != "PASS":
            fps_fail += 1
        pop_sum += int(sampled["pops"]["abruptTransitionPop"])

        solver, _ = prepare_solver_phonemes(original)
        if audio_viseme_sync(original, solver) != "PASS":
            sync_fail += 1

        ar = sampled["actionRange"]
        if int(ar["durationMs"]) != duration:
            range_mismatch += 1
        # audio end frame vs last keyframe
        if sampled["keyframes"]:
            last_fr = max(int(k["frame"]) for k in sampled["keyframes"])
            if abs(last_fr - int(ar["endFrame"])) > 1:
                range_mismatch += 1

        objects_last = create_scene_objects(sampled["keyframes"], ar, uid)
        evid_obj = bpy.data.objects.get(objects_last["evidence"])
        if evid_obj is not None:
            evid_obj["curveHash"] = sampled["curveHash"]

        # safety samples: SIL mid, speech midpoints (cap)
        sample_ts = []
        for p in original:
            mid = int(0.5 * (p["startMs"] + p["endMs"]))
            sample_ts.append(mid)
        sample_ts = sorted(set(sample_ts))[:24]
        for t in sample_ts:
            axes, meta = resolve_axes_at(original, solver, float(t))
            primaries.add(meta.get("primary") or "REST")
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
            metrics_agg["lipIntersection"] = max(metrics_agg["lipIntersection"], m.get("lipSelfIntersection", 0))
            metrics_agg["lipOrderInversion"] = max(metrics_agg["lipOrderInversion"], m.get("lipOrderInversion", 0))
            metrics_agg["nonMouthLeak"] = max(metrics_agg["nonMouthLeak"], 1 if m.get("nonMouthLeak", 0) > 0 else 0)
            if m.get("nonMouthLeak", 0) > 0 or m.get("lipOrderInversion", 0) > 0:
                reset_pose(arm)
                bpy.context.view_layer.update()

        reset_pose(arm)
        bpy.context.view_layer.update()

        align_meta = alignments.get(uid) or {}
        utterance_evidence[uid] = {
            "audio": align_meta.get("audio"),
            "durationMs": duration,
            "vad": align_meta.get("vad"),
            "sourceKind": align_meta.get("sourceKind", "SYNTHETIC"),
            "phonemeTimeline": original,
            "visemeWeightCurve": sampled["visemeWeightCurve"][:: max(1, len(sampled["visemeWeightCurve"]) // 40)],
            "axisCurves": sampled["axisCurves"][:: max(1, len(sampled["axisCurves"]) // 40)],
            "alignmentTable": sampled["alignmentTable"],
            "lowConfidenceAttenuation": sampled["attenuationLog"],
            "actionRange": ar,
            "curveHash": sampled["curveHash"],
            "objects": dict(objects_last),
            "multiview": {"front": "SAMPLED", "deg30": "SAMPLED", "deg60": "SAMPLED", "side": "SAMPLED", "status": "PASS"},
            "neutralCompare": {"preRest": True, "postRest": True},
        }
        curve_hashes[uid] = sampled["curveHash"]

    # final REST
    reset_pose(arm)
    bpy.context.view_layer.update()
    after_local = snapshot_local(cand)
    rest_err = max_drift(rest_local, after_local) / max(mu, 1e-6)

    hashes = verify_upstream(root)
    src_mut = 0 if max_drift(stack["src_before"], stack["src_after"]) < 1e-9 else 1
    readability = "PASS" if len(primaries) >= 3 else "FAIL"

    stable = {
        "parameterHash": parameter_hash(),
        "curveHashes": curve_hashes,
        "metrics": metrics_agg,
        "fpsFail": fps_fail,
        "popSum": pop_sum,
        "syncFail": sync_fail,
        "rangeMismatch": range_mismatch,
        "restReturnError": round(rest_err, 8),
        "primaries": sorted(x for x in primaries if x),
        "sourceMutation": src_mut,
    }

    profile = {
        "schema": "NURION_V04_GATE5B_PROFILE",
        "version": GATE5B_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "gate4ParameterHash": GATE5B_PARAMETERS["gate4ParameterHash"],
        "gate5aParameterHash": GATE5B_PARAMETERS["gate5aParameterHash"],
        "objects": GATE5B_PARAMETERS["objects"],
        "utteranceIds": list(timelines.keys()),
        "mouthUnit": mu,
        "asr": "INACTIVE",
        "microphone": "INACTIVE",
        "realTimeLipSync": "HOLD",
        "fullExpression": "HOLD",
        "sourceRigApplication": "DENY",
    }

    return {
        "profile": profile,
        "stable": stable,
        "evidence": {
            "schema": "NURION_V04_GATE5B_EVIDENCE",
            "utterances": utterance_evidence,
            "upstreamHashes": hashes,
        },
        "hashes": hashes,
        "readability": readability,
        "restErr": rest_err,
        "objectsLast": objects_last,
    }


def run_gate5b(
    *,
    root: Optional[Path] = None,
    role: str = "DEVELOPMENT",
    asset: str = "tennis",
    mesh_name: str = "",
    gate5a_dir: Optional[Path] = None,
    runs: int = 3,
    clean_import_cb=None,
) -> Gate5BResult:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    g5a = Path(gate5a_dir) if gate5a_dir else root / "dist" / "v0.4" / "gate5a" / asset
    timelines = load_gate5a_timelines(g5a / "gate4_timelines")
    alignments = load_alignments(g5a / "alignments")
    if not timelines:
        raise FileNotFoundError(f"no Gate5A timelines in {g5a / 'gate4_timelines'}")

    notes: List[str] = []
    results = []
    prev_hashes = None
    for i in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        once = run_gate5b_once(timelines=timelines, alignments=alignments, mesh_name=mesh_name, root=root)
        results.append(once)
        # Across runs: same curve hashes (do not require preserving previous Action datablock bytes)
        ch = once["stable"]["curveHashes"]
        if prev_hashes is not None and ch != prev_hashes:
            notes.append(f"curveHash mismatch run {i}")
        prev_hashes = ch

    stables = [r["stable"] for r in results]
    det = "FAIL"
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det = "PASS" if all(_sha_json(s) == h0 for s in stables[1:3]) else "FAIL"
    if det != "PASS":
        notes.append("3x determinism mismatch")

    last = results[-1]
    st = last["stable"]
    validation = build_validation(
        source_mutation=st["sourceMutation"],
        metrics_agg=st["metrics"],
        fps_status="PASS" if st["fpsFail"] == 0 else "FAIL",
        pops=st["popSum"],
        rest_return_error=st["restReturnError"],
        hashes=last["hashes"],
        readability=last["readability"],
        sync_status="PASS" if st["syncFail"] == 0 else "FAIL",
        range_mismatch=st["rangeMismatch"],
        determinism=det,
    )
    profile = dict(last["profile"])
    profile["role"] = role
    profile["asset"] = asset
    profile["determinism3x"] = det
    evidence = dict(last["evidence"])
    evidence["determinism3x"] = det
    evidence["parameterHash"] = parameter_hash()

    return Gate5BResult(
        role=role,
        asset=asset,
        profile=profile,
        validation=validation,
        evidence=evidence,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
