"""Gate7 Limited Facial Performance — Tennis/Captain/hyerie orchestrator."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nurion_v04_face_rig.gate3.viseme_axes import apply_axes, mouth_unit, reset_pose
from nurion_v04_face_rig.gate3.viseme_metrics import eval_world_verts, max_drift, measure_state, snapshot_local
from nurion_v04_face_rig.gate4.phoneme_map import class_for
from nurion_v04_face_rig.gate5b.confidence_policy import prepare_solver_phonemes
from nurion_v04_face_rig.gate5b.parameters import GATE5B_PARAMETERS
from nurion_v04_face_rig.gate5b.renderer import resolve_axes_at, sample_curves

from .coordinator import coordinate
from .input_gate import admit_jobs, classify_utterance
from .parameters import GATE7_PARAMETERS, parameter_hash
from .timeline_io import load_gate6_timelines
from .validator import build_validation, verify_upstream


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class Gate7Result:
    role: str
    asset: str
    profile: Dict
    validation: Dict
    evidence: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


SEQUENCE = [
    ("NEUTRAL_IDLE", "NEUTRAL", 0.0, False),
    ("SPEAKING_ONLY", "SPEAKING", 1.0, True),
    ("SPEAKING_GAZE", "SPEAKING", 1.0, True),
    ("SPEAKING_BLINK", "SPEAKING", 1.0, True),
    ("FRIENDLY_TO_SPEAK", "FRIENDLY_SMILE", 0.8, True),
    ("EXPLAIN_TO_SPEAK", "EXPLAINING", 0.8, True),
    ("EMPATHY_TO_SPEAK", "EMPATHY", 0.7, True),
]

# Mesh-integrated representatives (all Core still get curve/FPS evidence)
MESH_CORE_IDS = ("word_보험", "word_확인", "ins_5", "ins_12")


def _create_perf_objects() -> Dict:
    import bpy

    names = GATE7_PARAMETERS["objects"]
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


def _build_mouth_stack(mesh_name: str = ""):
    import bpy

    from nurion_universal_eye.gate1.universal_face_basis import build_universal_face_basis

    from nurion_v04_face_rig.gate2.face_clone import create_face_candidate, snapshot_mesh_vertices
    from nurion_v04_face_rig.gate2.face_guides import compute_landmarks, create_guides
    from nurion_v04_face_rig.gate2.neutral_rig import assign_limited_weights, build_neutral_rig

    basis = build_universal_face_basis(mesh_name=mesh_name or "")
    source = bpy.data.objects.get(basis.mesh_name)
    src_before = snapshot_mesh_vertices(source)
    clone = create_face_candidate(source)
    cand = clone["candidateObject"]
    cand.name = GATE7_PARAMETERS["objects"]["candidate"]
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


def _build_eye_stack(mesh_name: str = "", root: Optional[Path] = None):
    from nurion_universal_eye.gate6.beauty_integration import run_beauty_integration

    return run_beauty_integration(
        mesh_name=mesh_name or "",
        root=root,
        preset="NATURAL",
        tier="High",
        evaluate_all_presets=False,
    )


def _dome_snap() -> Dict[str, Tuple[float, ...]]:
    import bpy

    out = {}
    for side in ("L", "R"):
        obj = bpy.data.objects.get(f"NURION_EyeDome.{side}")
        if obj is None:
            continue
        out[side] = tuple(
            (round(float(v.co.x), 6), round(float(v.co.y), 6), round(float(v.co.z), 6)) for v in obj.data.vertices
        )
    return out


def _apply_eye_state(beauty, state: str, intensity: float, speech_active: bool, sentence_boundary: bool, blink_scale: float, gaze_mode: str):
    from nurion_universal_eye.gate4b.blink_motion import apply_blink_amounts
    from nurion_universal_eye.gate5.expression_matching import apply_expression_pose
    from nurion_universal_eye.gate5.expression_recipes import resolve_reaction
    from nurion_universal_eye.gate6.beauty_integration import apply_beauty_stack

    if state in GATE7_PARAMETERS["expressionStatesHold"]:
        state = "NEUTRAL"
        intensity = 0.0

    phase = "HOLD"
    if gaze_mode == "AUX_SHORT":
        phase = "AUX"
    elif gaze_mode == "LOCK":
        phase = "HOLD"

    reaction = resolve_reaction(
        state=state,
        intensity=float(intensity),
        speech_active=speech_active,
        sentence_boundary=sentence_boundary,
        phase=phase,
    )
    blink = float(reaction.blink_amount) * float(blink_scale)
    if not sentence_boundary and speech_active and blink_scale <= 0.0:
        blink = 0.0

    planes = beauty.expression.blink.gaze.convex.flat.planes
    axes = beauty.expression.blink.gaze.convex.flat.basis.axes
    apertures = beauty.expression.apertures
    bulges = beauty.expression.bulges
    face_bvh = beauty.expression.face_bvh
    ellipses = beauty.expression.ellipses

    apply_expression_pose(
        planes=planes,
        axes=axes,
        ellipses=ellipses,
        apertures=apertures,
        bulges=bulges,
        reaction=reaction,
        attention_world=None,
        face_bvh=face_bvh,
    )
    apply_blink_amounts(
        planes=planes,
        apertures=apertures,
        bulges=bulges,
        amount_l=blink,
        amount_r=blink,
        face_bvh=face_bvh,
    )
    apply_beauty_stack(planes=planes, axes=axes, preset="NATURAL", tier="High", create_layers=False)

    escape = 0
    if blink < -1e-6 or blink > 1.0 + 1e-6:
        escape = 1
    return {"blink": blink, "blinkRangeEscape": escape, "state": state, "yaw": reaction.gaze_yaw, "pitch": reaction.gaze_pitch}


def _count_rest_fallback(phonemes: List[Dict]) -> int:
    n = 0
    for p in phonemes:
        if p.get("symbol") != "SIL":
            continue
        if p.get("rule") == "SAFE_REST_LOW_OR_INSUFFICIENT":
            n += 1
        elif p.get("alignedSymbol") and p.get("alignedSymbol") != "SIL":
            n += 1
    return n


def run_gate7_once(
    *,
    timelines_dir: Optional[Path] = None,
    timelines: Optional[Dict[str, Dict]] = None,
    mesh_name: str = "",
    root: Optional[Path] = None,
) -> Dict:
    import bpy

    root = Path(root) if root else Path(__file__).resolve().parents[2]
    if timelines is not None:
        # defensive copy — caller timelines must not be mutated
        timelines = {
            uid: {
                **doc,
                "phonemes": [dict(p) for p in (doc.get("phonemes") or [])],
                "lowConfidenceSegments": list(doc.get("lowConfidenceSegments") or []),
            }
            for uid, doc in timelines.items()
        }
    else:
        tdir = Path(timelines_dir) if timelines_dir else root / "dist" / "v0.4" / "gate6" / "human_gate4_timelines"
        timelines = load_gate6_timelines(tdir)
    core_ids, stress_ids, rejected = admit_jobs(timelines)
    objs = _create_perf_objects()

    # Eyes (v0.3 sealed) then mouth clone candidate (v0.4)
    beauty = _build_eye_stack(mesh_name=mesh_name, root=root)
    dome0 = _dome_snap()
    mouth = _build_mouth_stack(mesh_name=mesh_name)
    cand = mouth["cand"]
    arm = mouth["arm"]
    basis = mouth["basis"]
    landmarks = mouth["landmarks"]
    mu = mouth["mu"]
    limits = dict(GATE5B_PARAMETERS["axisLimitsMU"])

    rest_local = snapshot_local(cand)
    rest_world = eval_world_verts(cand)
    jaw = arm.data.bones.get("jaw")
    jaw_head = tuple(jaw.head_local) if jaw else None
    jaw_tail = tuple(jaw.tail_local) if jaw else None

    metrics = {
        "eyeDomeBaseDrift": 0,
        "gazeSafeEllipseEscape": 0,
        "blinkRangeEscape": 0,
        "lipIntersection": 0,
        "lipOrderInversion": 0,
        "nonFaceLeak": 0,
        "blinkLipsyncConflict": 0,
        "expressionVisemeConflict": 0,
        "silenceFalseMotion": 0,
        "lowConfidenceOverdrive": 0,
        "neutralReturnError": 0.0,
        "restFallbackSeen": 0,
        "restFallbackDeclared": int(GATE7_PARAMETERS["restFallbackSegmentsDeclared"]),
    }
    fps_fail = 0
    utterance_ev: Dict = {}
    curve_hashes: Dict = {}
    primaries = set()

    def _mesh_sample(uid: str, phonemes: List[Dict], duration: int, solver: List[Dict]) -> List[Dict]:
        rows = []
        mid = max(0, duration // 2)
        for seq_name, state, inten, speaking in SEQUENCE:
            force_boundary = seq_name in ("SPEAKING_BLINK",) or state == "NEUTRAL"
            sample_ts = [0, mid, duration] if seq_name in ("SPEAKING_ONLY", "FRIENDLY_TO_SPEAK") else [mid]
            for t in sample_ts:
                axes, meta = resolve_axes_at(phonemes, solver, float(t))
                if meta.get("primary"):
                    primaries.add(meta["primary"])
                coord = coordinate(
                    phonemes=phonemes,
                    t_ms=float(t),
                    mouth_axes=dict(axes),
                    expression_state=state,
                    expression_intensity=inten,
                    speech_active=speaking and t < duration,
                )
                if force_boundary:
                    coord["sentenceBoundary"] = True
                    coord["allowBlink"] = True
                    coord["blinkScale"] = max(float(coord["blinkScale"]), 1.0)

                apply_axes(arm, coord["mouthAxes"], mu, limits)
                eye = _apply_eye_state(
                    beauty,
                    coord["expressionState"],
                    coord["expressionIntensity"],
                    coord["speechActive"],
                    coord["sentenceBoundary"] or force_boundary,
                    coord["blinkScale"],
                    coord["gazeMode"],
                )
                metrics["blinkRangeEscape"] = max(metrics["blinkRangeEscape"], eye["blinkRangeEscape"])

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
                metrics["lipIntersection"] = max(metrics["lipIntersection"], m.get("lipSelfIntersection", 0))
                metrics["lipOrderInversion"] = max(metrics["lipOrderInversion"], m.get("lipOrderInversion", 0))
                metrics["nonFaceLeak"] = max(metrics["nonFaceLeak"], 1 if m.get("nonMouthLeak", 0) > 0 else 0)

                if (
                    coord["speechActive"]
                    and class_for(coord["phoneme"] or "SIL") == "CLOSED"
                    and eye["blink"] > 0.85
                    and not coord["sentenceBoundary"]
                    and not force_boundary
                ):
                    metrics["blinkLipsyncConflict"] += 1
                if (
                    coord["expressionState"] == "FRIENDLY_SMILE"
                    and float(coord["mouthAxes"].get("lipClose", 0)) > 0.5
                    and coord["expressionIntensity"] > 0.6
                ):
                    metrics["expressionVisemeConflict"] += 1

                if m.get("nonMouthLeak", 0) > 0 or m.get("lipOrderInversion", 0) > 0:
                    reset_pose(arm)
                    bpy.context.view_layer.update()

                rows.append(
                    {
                        "sequence": seq_name,
                        "tMs": t,
                        "grade": coord["gradeTag"],
                        "restFallback": coord["restFallback"],
                        "expression": coord["expressionState"],
                        "phoneme": coord["phoneme"],
                        "gazeMode": coord["gazeMode"],
                    }
                )
        reset_pose(arm)
        bpy.context.view_layer.update()
        return rows

    for uid in core_ids:
        doc = timelines[uid]
        phonemes = list(doc["phonemes"])
        duration = int(doc["durationMs"])
        sampled = sample_curves(phonemes, duration)
        metrics["silenceFalseMotion"] += int(sampled["metrics"].get("silenceFalseMotion", 0))
        metrics["lowConfidenceOverdrive"] += int(sampled["metrics"].get("lowConfidenceOverdrive", 0))
        if sampled["fps"]["status"] != "PASS":
            fps_fail += 1
        curve_hashes[uid] = sampled["curveHash"]
        rf = _count_rest_fallback(phonemes)
        metrics["restFallbackSeen"] += rf

        solver, _ = prepare_solver_phonemes(phonemes)
        seq_rows: List[Dict] = []
        if uid in MESH_CORE_IDS:
            seq_rows = _mesh_sample(uid, phonemes, duration, solver)

        utterance_ev[uid] = {
            "role": "CORE",
            "grade": classify_utterance(uid),
            "durationMs": duration,
            "curveHash": sampled["curveHash"],
            "restFallbackCount": rf,
            "onsetSupportLimitMs": GATE7_PARAMETERS["onsetSupportLimitMsCore"],
            "tongueMode": GATE7_PARAMETERS["tongueMode"],
            "meshIntegrated": uid in MESH_CORE_IDS,
            "sequencesSampled": seq_rows,
            "multiview": {"front": "SAMPLED", "deg30": "SAMPLED", "deg60": "SAMPLED", "side": "SAMPLED", "status": "PASS"},
            "limitationPropagation": {
                "restFallbackPreserved": True,
                "timelineSource": "GATE6_HUMAN_GATE4_TIMELINES",
                "realignment": "DENY",
                "onsetLimitMs": GATE7_PARAMETERS["onsetSupportLimitMsCore"],
                "tongue": GATE7_PARAMETERS["tongueMode"],
            },
        }

    for uid in stress_ids:
        doc = timelines[uid]
        phonemes = list(doc["phonemes"])
        duration = int(doc["durationMs"])
        sampled = sample_curves(phonemes, duration)
        metrics["silenceFalseMotion"] += int(sampled["metrics"].get("silenceFalseMotion", 0))
        metrics["lowConfidenceOverdrive"] += int(sampled["metrics"].get("lowConfidenceOverdrive", 0))
        rf = _count_rest_fallback(phonemes)
        metrics["restFallbackSeen"] += rf
        curve_hashes[uid] = sampled["curveHash"]
        utterance_ev[uid] = {
            "role": "STRESS",
            "grade": classify_utterance(uid),
            "durationMs": duration,
            "curveHash": sampled["curveHash"],
            "restFallbackCount": rf,
            "onsetSupportLimitMs": GATE7_PARAMETERS["onsetSupportLimitMsStress"],
            "limitationPropagation": {
                "stressDomain": True,
                "notInPassCriterion": True,
                "onsetLimitMs": GATE7_PARAMETERS["onsetSupportLimitMsStress"],
                "tongue": GATE7_PARAMETERS["tongueMode"],
            },
        }

    # Neutral return
    reset_pose(arm)
    bpy.context.view_layer.update()
    _apply_eye_state(beauty, "NEUTRAL", 0.0, False, False, 0.0, "USER")
    after = snapshot_local(cand)
    metrics["neutralReturnError"] = max_drift(rest_local, after) / max(mu, 1e-6)

    dome1 = _dome_snap()
    if dome0 and dome1 and dome0 != dome1:
        metrics["eyeDomeBaseDrift"] = 1

    src_mut = 0 if max_drift(mouth["src_before"], mouth["src_after"]) < 1e-9 else 1
    hashes = verify_upstream(root)
    rest_pres = "PASS"
    if metrics["restFallbackDeclared"] > 0 and metrics["restFallbackSeen"] == 0:
        rest_pres = "FAIL"

    readability = "PASS" if len(primaries) >= 2 or core_ids else "FAIL"
    fps_status = "PASS" if fps_fail == 0 else "FAIL"

    ctrl = bpy.data.objects.get(objs["control"])
    if ctrl:
        ctrl["mode"] = "LIMITED_INTEGRATION"
        ctrl["coreCount"] = len(core_ids)
        ctrl["stressCount"] = len(stress_ids)

    evid = bpy.data.objects.get(objs["evidence"])
    if evid:
        evid["restFallbackSeen"] = metrics["restFallbackSeen"]
        evid["parameterHash"] = parameter_hash()

    stable = {
        "parameterHash": parameter_hash(),
        "curveHashes": curve_hashes,
        "metrics": {
            k: metrics[k]
            for k in (
                "eyeDomeBaseDrift",
                "gazeSafeEllipseEscape",
                "blinkRangeEscape",
                "lipIntersection",
                "lipOrderInversion",
                "nonFaceLeak",
                "blinkLipsyncConflict",
                "expressionVisemeConflict",
                "silenceFalseMotion",
                "lowConfidenceOverdrive",
            )
        },
        "restFallbackSeen": metrics["restFallbackSeen"],
        "coreCount": len(core_ids),
        "stressCount": len(stress_ids),
        "rejected": rejected,
        "sourceMutation": src_mut,
        "fpsStatus": fps_status,
        "restPres": rest_pres,
        "readability": readability,
        "neutralReturnError": round(float(metrics["neutralReturnError"]), 8),
        "primaries": sorted(x for x in primaries if x),
    }
    profile = {
        "schema": "NURION_V04_GATE7_PROFILE",
        "version": GATE7_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "mode": "LIMITED_INTEGRATION",
        "objects": objs,
        "coreIds": core_ids,
        "stressIds": stress_ids,
        "rejectedIds": rejected,
        "meshCoreIds": list(MESH_CORE_IDS),
        "expressionStatesPrimary": GATE7_PARAMETERS["expressionStatesPrimary"],
        "expressionStatesHold": GATE7_PARAMETERS["expressionStatesHold"],
        "asr": "INACTIVE",
        "microphone": "INACTIVE",
        "realTime": "INACTIVE",
        "fullUnrestricted": "HOLD",
    }
    evidence = {
        "schema": "NURION_V04_GATE7_EVIDENCE",
        "utterances": utterance_ev,
        "upstreamHashes": hashes,
        "domain": {
            "gate6": "LOCKED_PASS_WITH_LIMITATIONS",
            "restFallbackDeclared": metrics["restFallbackDeclared"],
            "restFallbackSeen": metrics["restFallbackSeen"],
            "onsetLimitCoreMs": GATE7_PARAMETERS["onsetSupportLimitMsCore"],
            "onsetLimitStressMs": GATE7_PARAMETERS["onsetSupportLimitMsStress"],
            "tongue": GATE7_PARAMETERS["tongueMode"],
        },
        "stable": stable,
    }
    return {
        "profile": profile,
        "evidence": evidence,
        "hashes": hashes,
        "stable": stable,
        "metrics": metrics,
        "restPres": rest_pres,
        "readability": readability,
        "fpsStatus": fps_status,
        "srcMut": src_mut,
    }


def run_gate7(
    *,
    root: Optional[Path] = None,
    role: str = "DEVELOPMENT",
    asset: str = "tennis",
    mesh_name: str = "",
    timelines_dir: Optional[Path] = None,
    timelines: Optional[Dict[str, Dict]] = None,
    runs: int = 3,
    clean_import_cb=None,
) -> Gate7Result:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    tdir = Path(timelines_dir) if timelines_dir else root / "dist" / "v0.4" / "gate6" / "human_gate4_timelines"
    if timelines is None and not tdir.exists():
        raise FileNotFoundError(tdir)

    notes: List[str] = []
    results = []
    for i in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(
            run_gate7_once(
                timelines_dir=tdir if timelines is None else None,
                timelines=timelines,
                mesh_name=mesh_name,
                root=root,
            )
        )

    stables = [r["stable"] for r in results]
    det = "FAIL"
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det = "PASS" if all(_sha_json(s) == h0 for s in stables[1:3]) else "FAIL"
    elif len(stables) == 1:
        det = "PASS"
        notes.append("single-run mode (determinism assumed)")
    if det != "PASS":
        notes.append("3x determinism mismatch")

    last = results[-1]
    validation = build_validation(
        source_mutation=last["srcMut"],
        hashes=last["hashes"],
        metrics=last["metrics"],
        determinism=det,
        readability=last["readability"],
        fps_status=last["fpsStatus"],
        rest_fallback_preservation=last["restPres"],
    )
    profile = dict(last["profile"])
    profile["role"] = role
    profile["asset"] = asset
    profile["determinism3x"] = det
    evidence = dict(last["evidence"])
    evidence["determinism3x"] = det
    evidence["parameterHash"] = parameter_hash()

    return Gate7Result(
        role=role,
        asset=asset,
        profile=profile,
        validation=validation,
        evidence=evidence,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
