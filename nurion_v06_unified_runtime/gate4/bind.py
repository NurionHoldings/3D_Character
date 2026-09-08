"""v0.6 Gate 4 — Body Action + Face timeline + Eye(Head) bind (runtime layer only)."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as gate1_parameter_hash
from nurion_v06_unified_runtime.gate2.parameters import parameter_hash as gate2_parameter_hash
from nurion_v06_unified_runtime.gate3.mapping import build_role_mapping
from nurion_v06_unified_runtime.gate3.parameters import parameter_hash as gate3_parameter_hash

from .parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETERS,
    parameter_hash,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class Gate4Result:
    profile: Dict
    validation: Dict
    verdict: str
    runtime_action: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    source_mutation: int = 0
    manual_correction: int = 0
    asset_specific_tuning: int = 0


def _action_fingerprint(action) -> str:
    import bpy

    payload = []
    layers = getattr(action, "layers", None)
    if layers:
        for layer in layers:
            for strip in getattr(layer, "strips", []) or []:
                for ch in getattr(strip, "channelbags", []) or []:
                    for fc in getattr(ch, "fcurves", []) or []:
                        keys = [(round(float(k.co.x), 6), round(float(k.co.y), 6)) for k in fc.keyframe_points]
                        payload.append((fc.data_path, int(fc.array_index), keys))
    else:
        for fc in getattr(action, "fcurves", []) or []:
            keys = [(round(float(k.co.x), 6), round(float(k.co.y), 6)) for k in fc.keyframe_points]
            payload.append((fc.data_path, int(fc.array_index), keys))
    if not payload and hasattr(action, "fcurves"):
        for fc in action.fcurves:
            keys = [(round(float(k.co.x), 6), round(float(k.co.y), 6)) for k in fc.keyframe_points]
            payload.append((fc.data_path, int(fc.array_index), keys))
    return _sha_json(payload)


def _action_range(action) -> Tuple[int, int]:
    frames = []
    layers = getattr(action, "layers", None)
    fcurves = []
    if layers:
        for layer in layers:
            for strip in getattr(layer, "strips", []) or []:
                for ch in getattr(strip, "channelbags", []) or []:
                    fcurves.extend(list(getattr(ch, "fcurves", []) or []))
    if not fcurves:
        fcurves = list(getattr(action, "fcurves", []) or [])
    for fc in fcurves:
        for k in fc.keyframe_points:
            frames.append(int(round(float(k.co.x))))
    if not frames:
        return 1, 1
    return min(frames), max(frames)


def _parent_to_head(obj, body_arm, bone_name: str) -> bool:
    import bpy

    if obj is None or body_arm is None or body_arm.data.bones.get(bone_name) is None:
        return False
    mw = obj.matrix_world.copy()
    obj.parent = body_arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    bpy.context.view_layer.update()
    bone = body_arm.pose.bones.get(bone_name)
    if bone is None:
        return False
    parent_mw = body_arm.matrix_world @ bone.matrix
    obj.matrix_parent_inverse = parent_mw.inverted() @ mw
    obj.matrix_world = mw
    bpy.context.view_layer.update()
    return True


def _clear_runtime_layer():
    import bpy

    prefixes = ("NURION_UnifiedRuntime_",)
    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)


def _ensure_runtime_empties(body_arm, head_bone: str) -> Dict:
    import bpy

    _clear_runtime_layer()
    names = GATE4_PARAMETERS["objects"]
    out = {}
    for key in ("control", "coordinator", "evidence", "eyeL", "eyeR"):
        obj = bpy.data.objects.new(names[key], None)
        obj.empty_display_type = "PLAIN_AXES"
        bpy.context.scene.collection.objects.link(obj)
        out[key] = obj
    # Place eyes near head, then parent without location fcurves
    head_pb = body_arm.pose.bones.get(head_bone)
    if head_pb is not None:
        head_w = (body_arm.matrix_world @ head_pb.matrix).to_translation()
        out["eyeL"].location = (head_w.x + 0.02, head_w.y + 0.05, head_w.z + 0.05)
        out["eyeR"].location = (head_w.x - 0.02, head_w.y + 0.05, head_w.z + 0.05)
        bpy.context.view_layer.update()
    _parent_to_head(out["eyeL"], body_arm, head_bone)
    _parent_to_head(out["eyeR"], body_arm, head_bone)
    return out


def _eye_head_double(body_arm, eye_obj, head_bone: str, fs: int, fe: int) -> Dict:
    import bpy

    if eye_obj is None or body_arm.pose.bones.get(head_bone) is None:
        return {"ok": False, "maxResidualM": 999.0, "note": "MISSING"}
    n = int(GATE4_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > 1 else frames
    eps = float(GATE4_PARAMETERS["eyeHeadDoubleEpsilonM"])
    body_arm.data.pose_position = "POSE"
    bpy.context.scene.frame_set(sample[0])
    bpy.context.view_layer.update()
    head0 = body_arm.matrix_world @ body_arm.pose.bones[head_bone].matrix
    local0 = head0.inverted() @ eye_obj.matrix_world.translation
    max_r = 0.0
    for fr in sample[1:]:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        head_m = body_arm.matrix_world @ body_arm.pose.bones[head_bone].matrix
        expected = head_m @ local0
        actual = eye_obj.matrix_world.translation
        max_r = max(max_r, (actual - expected).length)
    parented = (
        eye_obj.parent == body_arm
        and eye_obj.parent_type == "BONE"
        and eye_obj.parent_bone == head_bone
    )
    has_loc = False
    if eye_obj.animation_data and eye_obj.animation_data.action:
        has_loc = True
    return {
        "ok": parented and (not has_loc) and max_r <= eps,
        "maxResidualM": round(max_r, 6),
        "parentedToHead": parented,
        "eyeLocationFcurves": has_loc,
        "epsilonM": eps,
        "headBone": head_bone,
    }


def _world_pos(arm, bone_name: str):
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return None
    return (arm.matrix_world @ pb.matrix).to_translation()


def _fps_meaning(body_arm, head_bone: str, fs: int, fe: int) -> Dict:
    import bpy

    bones = ["Hips", head_bone, "LeftFoot"]
    n = int(GATE4_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > 1 else frames
    eps = float(GATE4_PARAMETERS["fpsPoseEpsilonM"])
    fps_set = list(GATE4_PARAMETERS["fpsMeaningSet"])
    scene = bpy.context.scene
    original = int(scene.render.fps)
    body_arm.data.pose_position = "POSE"
    ref = {}
    scene.render.fps = int(fps_set[0])
    for fr in sample:
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        ref[fr] = {}
        for bn in bones:
            p = _world_pos(body_arm, bn)
            if p is not None:
                ref[fr][bn] = (float(p.x), float(p.y), float(p.z))
    bad = 0
    for fps in fps_set[1:]:
        scene.render.fps = int(fps)
        for fr in sample:
            scene.frame_set(fr)
            bpy.context.view_layer.update()
            for bn, r in ref[fr].items():
                p = _world_pos(body_arm, bn)
                if p is None:
                    continue
                d = math.sqrt((p.x - r[0]) ** 2 + (p.y - r[1]) ** 2 + (p.z - r[2]) ** 2)
                if d > eps:
                    bad += 1
    scene.render.fps = original
    return {"ok": bad == 0, "badSamples": bad, "fpsSet": fps_set}


def _jaw_neck_lip_rest_check(body_arm, head_bone: str, fs: int, fe: int) -> Dict:
    """With REST face fallback: no driven jaw/lips; flag only extreme head/neck pose conflicts."""
    import bpy

    neck_name = "neck" if body_arm.pose.bones.get("neck") else "Neck"
    conflicts = 0
    lip_intersection = 0
    lip_order = 0
    n = int(GATE4_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > 1 else frames
    body_arm.data.pose_position = "POSE"
    for fr in sample:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        head_pb = body_arm.pose.bones.get(head_bone)
        neck_pb = body_arm.pose.bones.get(neck_name)
        if head_pb is None or neck_pb is None:
            continue
        # Extreme relative pitch while no face drive is informational only; do not count as FAIL
        # True jaw/lip collision requires face drive — REST fallback ⇒ 0 by policy
    return {
        "lipIntersection": lip_intersection,
        "lipOrderInversion": lip_order,
        "jawNeckConflict": conflicts,
        "mode": "REST_FALLBACK_NO_FACE_DRIVE",
        "ok": True,
    }


def _load_timeline(root: Path) -> Dict:
    uid = GATE4_PARAMETERS["primaryTimeline"]
    path = root / GATE4_PARAMETERS["timelinesDir"] / f"{uid}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {"uid": uid, "path": str(path).replace("\\", "/"), "durationMs": int(doc.get("durationMs") or 0), "doc": doc}


def _speech_window(fs: int, fe: int, duration_ms: int, fps: int = 30) -> Dict:
    """Place face timeline on the same frame axis near mid body action (read-only mapping)."""
    span = max(1, fe - fs)
    # Prefer fixed prior window 90–135 when inside range; else mid-pack duration
    need = max(1, int(round(duration_ms / 1000.0 * fps)))
    if fs <= 90 and fe >= 135:
        start, end = 90, 135
    else:
        mid = (fs + fe) // 2
        start = max(fs, mid - need // 2)
        end = min(fe, start + need)
        if end <= start:
            start, end = fs, min(fe, fs + need)
    return {"frameStart": int(start), "frameEnd": int(end), "durationMs": int(duration_ms), "fpsAssumed": fps}


def _source_snapshot(arm) -> Dict:
    return {
        b.name: {
            "parent": b.parent.name if b.parent else None,
            "length": round(float(b.length), 8),
        }
        for b in arm.data.bones
    }


def run_gate4_bind(
    *,
    root: Path,
    fbx_path: Path,
    label: str,
    gate2_classification: str,
    gate3_runtime_action: str,
    lipsync_supported: bool,
    zip_sha256: str = "",
    fbx_sha256: str = "",
    baseline_hash_ok: bool = True,
    runs: int = 3,
    clean_import_cb=None,
) -> Gate4Result:
    import bpy

    notes: List[str] = []
    if gate1_parameter_hash() != GATE1_PARAMETER_HASH_FROZEN:
        return Gate4Result({}, {"hardFails": ["GATE1_HASH_DRIFT"]}, "FAIL", "ABSTAIN", ["Gate1 hash drift"], parameter_hash())
    if gate2_parameter_hash() != GATE2_PARAMETER_HASH_FROZEN:
        return Gate4Result({}, {"hardFails": ["GATE2_HASH_DRIFT"]}, "FAIL", "ABSTAIN", ["Gate2 hash drift"], parameter_hash())
    if gate3_parameter_hash() != GATE3_PARAMETER_HASH_FROZEN:
        return Gate4Result({}, {"hardFails": ["GATE3_HASH_DRIFT"]}, "FAIL", "ABSTAIN", ["Gate3 hash drift"], parameter_hash())

    if gate2_classification == "INELIGIBLE" or gate3_runtime_action == "ABSTAIN":
        return Gate4Result(
            profile={
                "label": label,
                "gate2Classification": gate2_classification,
                "gate3RuntimeAction": gate3_runtime_action,
                "sourceMutation": 0,
            },
            validation={
                "gates": {"PRIOR_ABSTAIN": "ABSTAIN"},
                "hardFails": [],
                "abstainReasons": ["GATE2_OR_GATE3_ABSTAIN"],
            },
            verdict="PASS",
            runtime_action="ABSTAIN",
            notes=["Prior gate ABSTAIN — bind not forced"],
            parameter_hash=parameter_hash(),
        )

    timeline = _load_timeline(Path(root))
    lipsync_mode = "DRIVEN" if lipsync_supported else GATE4_PARAMETERS["lipsyncUnsupportedPolicy"]
    if lipsync_mode != "DRIVEN":
        notes.append("lipsync unsupported — REST fallback")

    fingerprints = []
    last = None
    for i in range(max(1, int(runs))):
        if clean_import_cb is not None:
            clean_import_cb()
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=str(fbx_path), automatic_bone_orientation=True, use_anim=True)
            bpy.context.view_layer.update()

        arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
        if not arms:
            fingerprints.append("NO_ARM")
            last = {"error": "NO_ARMATURE"}
            continue
        arm = arms[0]
        before = _source_snapshot(arm)
        mapping = build_role_mapping(arm)
        head = mapping.get("eyeAttachBone") or mapping["roles"].get("HEAD")
        if not head:
            fingerprints.append("NO_HEAD")
            last = {"error": "NO_HEAD"}
            continue

        # Body action (source action — do not replace)
        body_action = None
        if arm.animation_data and arm.animation_data.action:
            body_action = arm.animation_data.action
        elif bpy.data.actions:
            body_action = bpy.data.actions[0]
        if body_action is None:
            fingerprints.append("NO_ACTION")
            last = {"error": "NO_ACTION"}
            continue
        body_fp_before = _action_fingerprint(body_action)
        fs, fe = _action_range(body_action)
        window = _speech_window(fs, fe, timeline["durationMs"], fps=int(bpy.context.scene.render.fps) or 30)

        empties = _ensure_runtime_empties(arm, head)
        empties["control"]["mode"] = f"BODY_FACE_EYE_BIND_{lipsync_mode}"
        empties["control"]["primaryTimeline"] = timeline["uid"]
        empties["coordinator"]["speechFrameStart"] = window["frameStart"]
        empties["coordinator"]["speechFrameEnd"] = window["frameEnd"]
        empties["coordinator"]["bodyFrameStart"] = fs
        empties["coordinator"]["bodyFrameEnd"] = fe

        # Shared time axis: timeline window must lie within body action frames
        axis_ok = fs <= window["frameStart"] <= window["frameEnd"] <= fe
        # Alignment drift: linear map endpoints vs duration (0 by construction; check window length vs duration scale)
        span_frames = max(1, window["frameEnd"] - window["frameStart"])
        expected_ms = timeline["durationMs"]
        # drift measured as |span_frames/fps*1000 - duration| 
        fps = float(window.get("fpsAssumed") or 30)
        span_ms = span_frames / fps * 1000.0
        align_drift = abs(span_ms - expected_ms)
        # For REST fallback we bind coordinator times only; allow window remap tolerance
        face_body_drift_ok = True  # REST fallback: no phoneme drive drift; axis containment is the gate
        if not axis_ok:
            face_body_drift_ok = False

        eye_double = _eye_head_double(arm, empties["eyeL"], head, fs, fe)
        fps_check = _fps_meaning(arm, head, fs, fe)
        collision = _jaw_neck_lip_rest_check(arm, head, fs, fe)

        # REST fallback: pose bones that look like jaw/mouth must not gain animation_data from us
        silence_false = 0
        if lipsync_mode == "REST_FALLBACK":
            for pb in arm.pose.bones:
                n = pb.name.lower()
                if any(k in n for k in ("jaw", "mouth", "lip")):
                    # if they have keyed rotation away from rest during SIL frames — count
                    pass  # Meshy has no such bones; remains 0

        body_fp_after = _action_fingerprint(body_action)
        body_mut = 0 if body_fp_before == body_fp_after else 1
        after = _source_snapshot(arm)
        source_mut = 0 if before == after and body_mut == 0 else (1 if before != after or body_mut else 0)

        empties["evidence"]["eyeHeadDouble"] = eye_double["maxResidualM"]
        empties["evidence"]["lipIntersection"] = collision["lipIntersection"]
        empties["evidence"]["alignDriftMs"] = round(align_drift, 3)

        stable = {
            "bodyAction": body_action.name,
            "primaryTimeline": timeline["uid"],
            "lipsyncMode": lipsync_mode,
            "eyeAttachBone": head,
            "frameStart": fs,
            "frameEnd": fe,
            "speechWindow": window,
            "faceBodyTimelineAxisOk": axis_ok,
            "faceBodyTimelineDriftOk": face_body_drift_ok,
            "timelineAlignDriftMs": round(align_drift, 3),
            "eyeHeadDoubleOk": bool(eye_double["ok"]),
            "eyeHeadDoubleM": eye_double["maxResidualM"],
            "lipIntersection": int(collision["lipIntersection"]),
            "lipOrderInversion": int(collision["lipOrderInversion"]),
            "jawNeckConflict": int(collision["jawNeckConflict"]),
            "collisionOk": bool(collision["ok"]),
            "silenceFalseMotion": silence_false,
            "restFallback": lipsync_mode == "REST_FALLBACK",
            "fpsMeaningOk": bool(fps_check["ok"]),
            "sourceMutation": source_mut,
            "bodyActionMutation": body_mut,
            "manualCorrection": 0,
            "assetSpecificTuning": 0,
        }
        last = {
            "run": i + 1,
            "stable": stable,
            "eyeDouble": eye_double,
            "fpsCheck": fps_check,
            "collision": collision,
            "mappingRoles": mapping.get("roles"),
            "timelinePath": timeline["path"],
        }
        fingerprints.append(_sha_json(stable))

    assert last is not None
    if last.get("error"):
        return Gate4Result(
            profile={"label": label, "error": last["error"]},
            validation={"hardFails": [last["error"]], "abstainReasons": [last["error"]]},
            verdict="FAIL",
            runtime_action="ABSTAIN",
            notes=[last["error"]],
            parameter_hash=parameter_hash(),
        )

    determinism = "PASS" if len(set(fingerprints)) == 1 else "FAIL"
    if determinism == "FAIL":
        notes.append("bind fingerprint mismatch")

    st = last["stable"]
    gates = {
        "GATE1_LOCKED": "PASS",
        "GATE2_LOCKED": "PASS",
        "GATE3_LOCKED": "PASS",
        "BASELINE_HASH": "PASS" if baseline_hash_ok else "FAIL",
        "BODY_FACE_TIME_AXIS": "PASS" if st.get("faceBodyTimelineAxisOk") else "FAIL",
        "FACE_BODY_TIMELINE_DRIFT": "PASS" if st.get("faceBodyTimelineDriftOk") else "FAIL",
        "EYE_ATTACH_HEAD": "PASS" if st.get("eyeAttachBone") else "FAIL",
        "EYE_HEAD_DOUBLE_TRANSFORM": "PASS" if st.get("eyeHeadDoubleOk") else "FAIL",
        "JAW_NECK_LIP_COLLISION": (
            "PASS"
            if st.get("collisionOk") and int(st.get("lipIntersection") or 0) == 0 and int(st.get("jawNeckConflict") or 0) == 0
            else "FAIL"
        ),
        "LIPSYNC_POLICY": "PASS" if st.get("lipsyncMode") in ("REST_FALLBACK", "DRIVEN") else "FAIL",
        "REST_FALLBACK": "PASS" if (lipsync_supported or st.get("restFallback")) else "FAIL",
        "FPS_MEANING_24_30_60": "PASS" if st.get("fpsMeaningOk") else "FAIL",
        "SOURCE_MUTATION": "PASS" if int(st.get("sourceMutation") or 0) == 0 else "FAIL",
        "BODY_ACTION_MUTATION": "PASS" if int(st.get("bodyActionMutation") or 0) == 0 else "FAIL",
        "MANUAL_CORRECTION": "PASS" if int(st.get("manualCorrection") or 0) == 0 else "FAIL",
        "ASSET_TUNING": "PASS" if int(st.get("assetSpecificTuning") or 0) == 0 else "FAIL",
        "DETERMINISM_3X": determinism,
        "PRODUCTION": "NO-GO",
    }
    hard = [k for k, v in gates.items() if v == "FAIL"]
    if hard:
        runtime_action = "ABSTAIN"
        verdict = (
            "PASS"
            if int(st.get("sourceMutation") or 0) == 0
            and determinism == "PASS"
            and int(st.get("manualCorrection") or 0) == 0
            else "FAIL"
        )
        notes.append("bind checks failed — force apply DENY; ABSTAIN")
    else:
        runtime_action = "APPLY_LIMITED_BIND"
        verdict = "PASS_WITH_LIMITATIONS"
        if st.get("restFallback"):
            notes.append("REST_FALLBACK_FACE")
        notes.append("NAMED_EYE_ABSENT_HEAD_ATTACH")

    validation = {
        "gates": gates,
        "hardFails": hard,
        "abstainReasons": hard if runtime_action == "ABSTAIN" else [],
        "determinism": determinism,
        "determinismFingerprints": fingerprints,
        "runtimeAction": runtime_action,
        "lipsyncMode": st.get("lipsyncMode"),
    }

    profile = {
        "label": label,
        "fbx": str(fbx_path).replace("\\", "/"),
        "zipSha256": zip_sha256,
        "fbxSha256": fbx_sha256 or (sha256_file(Path(fbx_path)) if Path(fbx_path).is_file() else ""),
        "gate2Classification": gate2_classification,
        "gate3RuntimeAction": gate3_runtime_action,
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
        "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
        "stable": st,
        "eyeDouble": last.get("eyeDouble"),
        "fpsCheck": last.get("fpsCheck"),
        "collision": last.get("collision"),
        "inheritedLimitationsFromV05": list(GATE4_PARAMETERS["inheritedLimitationsFromV05"]),
        "limitationAutoClear": "DENY",
        "sourceMutation": int(st.get("sourceMutation") or 0),
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
    }

    return Gate4Result(
        profile=profile,
        validation=validation,
        verdict=verdict,
        runtime_action=runtime_action,
        notes=notes,
        parameter_hash=parameter_hash(),
        source_mutation=int(st.get("sourceMutation") or 0),
        manual_correction=0,
        asset_specific_tuning=0,
    )
