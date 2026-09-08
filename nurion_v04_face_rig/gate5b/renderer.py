"""Render lip-sync curves / Blender diagnostic Action from Gate5A timelines."""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Tuple

from nurion_v04_face_rig.gate4.coarticulation import blend_axes_at_ms, ms_to_frame
from nurion_v04_face_rig.gate4.parameters import GATE4_PARAMETERS
from nurion_v04_face_rig.gate4.phoneme_map import class_for
from nurion_v04_face_rig.gate4.timing_checks import detect_abrupt_pops, sample_timeline_semantics

from .confidence_policy import prepare_solver_phonemes
from .parameters import GATE5B_PARAMETERS


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _axis_mag(axes: Dict[str, float]) -> float:
    return sum(abs(float(v)) for v in axes.values())


def _apply_insufficient_safe_jaw(axes: Dict[str, float], solver: List[Dict], t_ms: float) -> Dict[str, float]:
    for p in solver:
        if p.get("_tier") != "INSUFFICIENT" or p["symbol"] == "SIL":
            continue
        if float(p["startMs"]) <= t_ms <= float(p["endMs"]):
            jaw = float(p.get("_safeJaw", GATE5B_PARAMETERS["insufficientSafeJaw"]))
            return {"jawOpen": jaw} if not axes else axes
    return axes


def _in_silence(phonemes: List[Dict], t_ms: float) -> bool:
    for p in phonemes:
        if p["symbol"] == "SIL" and float(p["startMs"]) <= t_ms < float(p["endMs"]):
            return True
    return False


def _near_speech_boundary(phonemes: List[Dict], t_ms: float) -> bool:
    """Allow Gate4 seal/anticipation/release only within locked Gate4 windows."""
    ant = float(GATE4_PARAMETERS["anticipationMs"])
    rel = float(GATE4_PARAMETERS["releaseMs"])
    for p in phonemes:
        if p["symbol"] == "SIL":
            continue
        s, e = float(p["startMs"]), float(p["endMs"])
        if (s - ant) <= t_ms < s or e < t_ms <= (e + rel):
            return True
    return False


def _resolve_axes_at(
    original_phonemes: List[Dict], solver: List[Dict], t_ms: float
) -> Tuple[Dict[str, float], Dict]:
    axes, meta = blend_axes_at_ms(solver, float(t_ms))
    axes = _apply_insufficient_safe_jaw(axes, solver, float(t_ms))
    # Strict silence interior → REST (boundary anticipation/release still allowed)
    if _in_silence(original_phonemes, t_ms) and not _near_speech_boundary(original_phonemes, t_ms):
        return {}, {"primary": "REST", "sources": [], "weightSum": 0.0, "weightOverflow": 0}
    return axes, meta


def resolve_axes_at(
    original_phonemes: List[Dict], solver: List[Dict], t_ms: float
) -> Tuple[Dict[str, float], Dict]:
    return _resolve_axes_at(original_phonemes, solver, t_ms)


def sample_curves(original_phonemes: List[Dict], duration_ms: int) -> Dict:
    """Sample viseme/axis curves. Does not mutate original_phonemes list items."""
    solver, atten_log = prepare_solver_phonemes(original_phonemes)
    step = int(GATE5B_PARAMETERS["sampleStepMs"])
    fps_set = list(GATE5B_PARAMETERS["fpsSet"])
    render_fps = int(GATE5B_PARAMETERS["renderFps"])

    times = list(range(0, max(duration_ms, 0) + 1, step))
    if not times or times[-1] != duration_ms:
        times.append(int(duration_ms))

    viseme_weights: List[Dict] = []
    axis_curves: List[Dict] = []
    alignment_rows: List[Dict] = []
    silence_false = 0
    weight_overflow = 0
    overdrive = 0
    seal_loss = 0
    short_loss = 0

    # short phoneme coverage: each non-SIL must have a sample in its window with primary match or weight
    covered = {i: False for i, p in enumerate(original_phonemes) if p["symbol"] != "SIL"}

    for t in times:
        axes, meta = _resolve_axes_at(original_phonemes, solver, float(t))
        if meta.get("weightOverflow"):
            weight_overflow += 1
        primary = meta.get("primary") or "REST"
        sources = meta.get("sources") or []

        mag = _axis_mag(axes)
        if (
            _in_silence(original_phonemes, float(t))
            and not _near_speech_boundary(original_phonemes, float(t))
            and mag > float(GATE5B_PARAMETERS["silenceMotionEpsilon"])
        ):
            silence_false += 1

        # low-confidence overdrive
        for p in solver:
            if p["symbol"] == "SIL":
                continue
            if p["startMs"] <= t <= p["endMs"] and p.get("_tier") in ("LOW", "INSUFFICIENT"):
                if mag > float(GATE5B_PARAMETERS["lowConfidenceOverdriveScale"]):
                    overdrive += 1
                break

        viseme_weights.append(
            {
                "tMs": t,
                "primary": primary,
                "sources": sources,
                "weightSum": round(float(meta.get("weightSum", 0.0)), 5),
            }
        )
        axis_curves.append({"tMs": t, **{k: round(float(v), 5) for k, v in axes.items()}})

        for i, p in enumerate(original_phonemes):
            if p["symbol"] == "SIL":
                continue
            if p["startMs"] <= t <= p["endMs"]:
                if primary == class_for(p["symbol"]) or any(s.get("class") == class_for(p["symbol"]) for s in sources):
                    covered[i] = True
                elif mag > 1e-4:
                    covered[i] = True

    short_loss = sum(1 for ok in covered.values() if not ok)

    # closed consonant seal at midpoints
    for p in original_phonemes:
        if class_for(p["symbol"]) != "CLOSED":
            continue
        mid = 0.5 * (p["startMs"] + p["endMs"])
        axes, _ = _resolve_axes_at(original_phonemes, solver, float(mid))
        # find tier for this phoneme
        tier = "HIGH"
        for sp in solver:
            if sp["startMs"] == p["startMs"] and sp["symbol"] == p["symbol"]:
                tier = sp.get("_tier", "HIGH")
                break
        need = float(GATE5B_PARAMETERS["sealMinLipClose"])
        if tier == "INSUFFICIENT":
            continue
        if tier == "LOW":
            need *= 0.4
        elif tier == "MEDIUM":
            need *= 0.7
        if float(axes.get("lipClose", 0.0)) < need - 1e-6:
            seal_loss += 1

    # phoneme-viseme alignment table (midpoint)
    for p in original_phonemes:
        mid = 0.5 * (p["startMs"] + p["endMs"])
        axes, meta = _resolve_axes_at(original_phonemes, solver, float(mid))
        alignment_rows.append(
            {
                "symbol": p["symbol"],
                "startMs": p["startMs"],
                "endMs": p["endMs"],
                "confidence": p.get("confidence"),
                "class": class_for(p["symbol"]),
                "primaryAtMid": meta.get("primary"),
                "axesAtMid": {k: round(float(v), 5) for k, v in axes.items()},
            }
        )

    fps = sample_timeline_semantics(solver, fps_set)
    pops = detect_abrupt_pops(solver)

    # action range
    action_end_frame = ms_to_frame(duration_ms, render_fps)
    action_range = {"startFrame": 0, "endFrame": action_end_frame, "fps": render_fps, "durationMs": duration_ms}

    # keyframes for action (control props)
    keyframes = []
    for row in axis_curves:
        fr = ms_to_frame(row["tMs"], render_fps)
        keyframes.append({"frame": fr, "axes": {k: v for k, v in row.items() if k != "tMs"}})

    curve_hash = _sha_json({"viseme": viseme_weights, "axes": axis_curves, "action": action_range})

    return {
        "solverPhonemeCount": len(solver),
        "attenuationLog": atten_log,
        "visemeWeightCurve": viseme_weights,
        "axisCurves": axis_curves,
        "alignmentTable": alignment_rows,
        "fps": fps,
        "pops": pops,
        "actionRange": action_range,
        "keyframes": keyframes,
        "curveHash": curve_hash,
        "metrics": {
            "silenceFalseMotion": silence_false,
            "weightOverflow": weight_overflow,
            "lowConfidenceOverdrive": overdrive,
            "closedConsonantSealLoss": seal_loss,
            "shortPhonemeLoss": short_loss,
        },
    }


def audio_viseme_sync(original: List[Dict], solver: List[Dict]) -> str:
    lag = int(GATE5B_PARAMETERS["syncMaxPrimaryLagMs"])
    for p in original:
        if p["symbol"] == "SIL":
            continue
        mid = 0.5 * (p["startMs"] + p["endMs"])
        _, meta = blend_axes_at_ms(solver, float(mid))
        want = class_for(p["symbol"])
        primary = meta.get("primary")
        sources = meta.get("sources") or []
        ok = primary == want or any(s.get("class") == want for s in sources)
        if not ok and want == "RESTRICTED":
            ok = True
        if not ok:
            found = False
            for dt in (-lag, lag):
                _, m2 = blend_axes_at_ms(solver, float(mid + dt))
                pr = m2.get("primary")
                src = m2.get("sources") or []
                if pr == want or any(s.get("class") == want for s in src):
                    found = True
                    break
            if not found and want not in ("RESTRICTED", "REST"):
                return "FAIL"
    return "PASS"


def create_scene_objects(keyframes: List[Dict], action_range: Dict, utterance_id: str) -> Dict:
    """Create control/evidence empties and a diagnostic Action on the control (clone-only scene)."""
    import bpy

    names = GATE5B_PARAMETERS["objects"]
    # Remove previous diagnostic objects/actions with same names (verify overwrite avoidance via hash compare externally)
    for n in names.values():
        if n == names["action"]:
            continue
        old = bpy.data.objects.get(n)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)

    ctrl = bpy.data.objects.new(names["control"], None)
    ctrl.empty_display_type = "CUBE"
    ctrl.empty_display_size = 0.05
    bpy.context.collection.objects.link(ctrl)
    ctrl["utteranceId"] = utterance_id
    ctrl["actionStart"] = int(action_range["startFrame"])
    ctrl["actionEnd"] = int(action_range["endFrame"])

    axis_names = [
        "jawOpen",
        "lipWide",
        "lipRound",
        "lipClose",
        "upperLipRaise",
        "lowerLipDrop",
        "cornerPull",
        "teethApproach",
    ]
    for a in axis_names:
        if a not in ctrl:
            ctrl[a] = 0.0

    # Action: recreate with fixed name for evidence; caller compares hashes across runs instead of preserving old bytes
    act_name = names["action"]
    existing = bpy.data.actions.get(act_name)
    if existing is not None:
        bpy.data.actions.remove(existing)
    action = bpy.data.actions.new(act_name)
    ctrl.animation_data_create()
    ctrl.animation_data.action = action

    # Build fcurves via keyframe_insert
    for kf in keyframes:
        fr = int(kf["frame"])
        axes = kf.get("axes") or {}
        for a in axis_names:
            ctrl[a] = float(axes.get(a, 0.0))
            ctrl.keyframe_insert(data_path=f'["{a}"]', frame=fr)

    evid = bpy.data.objects.new(names["evidence"], None)
    evid.empty_display_type = "PLAIN_AXES"
    bpy.context.collection.objects.link(evid)
    evid["utteranceId"] = utterance_id
    evid["curveHash"] = ""
    evid["actionFrameEnd"] = int(action_range["endFrame"])

    return {
        "control": names["control"],
        "action": act_name,
        "evidence": names["evidence"],
        "keyframeCount": len(keyframes),
    }
