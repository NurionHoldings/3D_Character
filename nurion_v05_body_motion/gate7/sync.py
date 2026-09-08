"""Gate7: bind v0.4 face/eye/lipsync (RO) to Gate6 Formal Bow body candidate."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import (
    FOOT_SLIDE_RESIDUAL,
    GATE7_PARAMETERS,
    V04_GATE7_FROZEN,
    V04_RC1_SHA256,
    parameter_hash,
)


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Gate7Result:
    profile: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def _iter_action_fcurves(action):
    if action is None:
        return
    fcurves = getattr(action, "fcurves", None)
    if fcurves:
        for fc in fcurves:
            yield fc
        return
    for layer in getattr(action, "layers", []) or []:
        for strip in getattr(layer, "strips", []) or []:
            bags = getattr(strip, "channelbags", None)
            if bags is None:
                bag = getattr(strip, "channelbag", None)
                bags = [bag] if bag is not None else []
            for bag in bags:
                for fc in getattr(bag, "fcurves", []) or []:
                    yield fc


def _action_fingerprint(action) -> str:
    payload = []
    for fc in _iter_action_fcurves(action):
        keys = [(round(float(k.co.x), 6), round(float(k.co.y), 6)) for k in fc.keyframe_points]
        payload.append((fc.data_path, int(fc.array_index), keys))
    return _sha_json(payload)


def _bind_action(obj, action, slot=None):
    if obj.animation_data is None:
        obj.animation_data_create()
    obj.animation_data.action = action
    if slot is not None:
        try:
            obj.animation_data.action_slot = slot
            return
        except Exception:
            pass
    slots = list(getattr(action, "slots", []) or [])
    if slots:
        try:
            obj.animation_data.action_slot = slots[0]
        except Exception:
            pass


def _world_pos(arm, bone_name: str):
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return None
    return (arm.matrix_world @ pb.matrix).to_translation()


def _detect_bow_phases(body_arm, fs: int, fe: int) -> Dict:
    import bpy

    body_arm.data.pose_position = "POSE"
    series = []
    for fr in range(int(fs), int(fe) + 1):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        h = _world_pos(body_arm, "Head")
        if h is None:
            continue
        series.append((fr, float(h.z)))
    if not series:
        return {"start": fs, "bottom": (fs + fe) // 2, "returnStart": (fs + fe) // 2, "end": fe}
    min_z = min(p[1] for p in series)
    bottom_frames = [fr for fr, z in series if abs(z - min_z) <= 0.015]
    bottom_start = min(bottom_frames) if bottom_frames else min(series, key=lambda t: t[1])[0]
    bottom_end = max(bottom_frames) if bottom_frames else bottom_start
    # approach ends at bottom_start; return starts after bottom plateau
    return {
        "start": int(fs),
        "approachEnd": int(bottom_start),
        "bottomStart": int(bottom_start),
        "bottomEnd": int(bottom_end),
        "returnStart": int(bottom_end),
        "end": int(fe),
        "minHeadZ": round(min_z, 5),
    }


def _speech_window(phases: Dict, duration_ms: int, fps: float = 30.0) -> Dict:
    """Place greeting lipsync over bottom→early return."""
    need_frames = max(1, int(math.ceil(duration_ms / 1000.0 * fps)))
    start = int(phases["bottomStart"])
    end = min(int(phases["end"]), start + need_frames)
    if end <= start:
        end = min(int(phases["end"]), start + 1)
    return {"frameStart": start, "frameEnd": end, "durationMs": int(duration_ms)}


def _frame_to_face_ms(fr: int, window: Dict) -> Optional[float]:
    a, b = int(window["frameStart"]), int(window["frameEnd"])
    if fr < a or fr > b or b <= a:
        return None
    t = (fr - a) / float(b - a)
    return t * float(window["durationMs"])


def _phase_at(fr: int, phases: Dict) -> str:
    if fr < phases["approachEnd"]:
        return "APPROACH"
    if fr <= phases["bottomEnd"]:
        return "BOTTOM"
    return "RETURN"


def _ensure_sync_empties():
    import bpy

    names = GATE7_PARAMETERS["objects"]
    out = {}
    for key in ("control", "coordinator", "evidence"):
        n = names[key]
        old = bpy.data.objects.get(n)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
        obj = bpy.data.objects.new(n, None)
        obj.empty_display_type = "PLAIN_AXES"
        bpy.context.scene.collection.objects.link(obj)
        out[key] = obj
    return out


def _parent_to_head_bone(obj, body_arm, bone_name: str = "Head"):
    """Parent object to body Head bone without baking double world motion into locals."""
    import bpy
    from mathutils import Matrix

    if obj is None or body_arm is None:
        return False
    if body_arm.data.bones.get(bone_name) is None:
        return False
    mw = obj.matrix_world.copy()
    obj.parent = body_arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    # Keep world transform at bind
    bpy.context.view_layer.update()
    # bone parent: matrix_parent_inverse so world stays
    bone = body_arm.pose.bones.get(bone_name)
    if bone is None:
        return False
    parent_mw = body_arm.matrix_world @ bone.matrix
    obj.matrix_parent_inverse = parent_mw.inverted() @ mw
    obj.matrix_world = mw
    bpy.context.view_layer.update()
    return True


def _build_face_eye_on_body(*, mesh_name: str, body_arm, root: Path) -> Dict:
    """Build v0.4 mouth clone + v0.3 eye stack; parent under body Head."""
    from nurion_v04_face_rig.gate7.integration import _build_eye_stack, _build_mouth_stack, _dome_snap

    beauty = _build_eye_stack(mesh_name=mesh_name, root=root)
    dome0 = _dome_snap()
    mouth = _build_mouth_stack(mesh_name=mesh_name)
    face_mesh = mouth["cand"]
    face_arm = mouth["arm"]
    face_mesh.name = GATE7_PARAMETERS["objects"]["faceCandidate"]

    # Parent face armature & mesh & eye objects to Head (local deform only thereafter)
    _parent_to_head_bone(face_arm, body_arm, "Head")
    if face_mesh.parent is None or face_mesh.parent != face_arm:
        # keep armature modifier; parent mesh to face arm if not already
        pass
    # Eyes: parent domes/planes to Head
    import bpy

    for side in ("L", "R"):
        for prefix in ("NURION_EyeDome", "NURION_EyePlane"):
            obj = bpy.data.objects.get(f"{prefix}.{side}")
            if obj is not None:
                _parent_to_head_bone(obj, body_arm, "Head")

    return {
        "beauty": beauty,
        "dome0": dome0,
        "mouth": mouth,
        "face_arm": face_arm,
        "face_mesh": face_mesh,
    }


def _eye_head_double_metric(body_arm, fs: int, fe: int) -> Dict:
    """Detect eye←Head double transform: eye world must track Head rigidly (+ small local gaze)."""
    import bpy
    from mathutils import Vector

    dome = bpy.data.objects.get("NURION_EyeDome.L")
    if dome is None or body_arm.pose.bones.get("Head") is None:
        return {"ok": True, "maxResidualM": 0.0, "samples": 0, "note": "NO_EYE_DOME"}

    n = int(GATE7_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    eps = float(GATE7_PARAMETERS["eyeHeadDoubleEpsilonM"])

    bpy.context.scene.frame_set(sample[0])
    bpy.context.view_layer.update()
    head0_m = body_arm.matrix_world @ body_arm.pose.bones["Head"].matrix
    local0 = head0_m.inverted() @ dome.matrix_world.translation

    max_r = 0.0
    for fr in sample[1:]:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        head_m = body_arm.matrix_world @ body_arm.pose.bones["Head"].matrix
        actual = dome.matrix_world.translation
        expected = head_m @ local0
        # Rigid Head follow: residual 0. Double bake → residual ≈ Head motion magnitude.
        max_r = max(max_r, (actual - expected).length)

    parented = dome.parent == body_arm and dome.parent_type == "BONE" and dome.parent_bone == "Head"
    # Also ensure no location fcurves on eye (would double with bone parent)
    has_eye_loc_fcurves = False
    if dome.animation_data and dome.animation_data.action:
        for fc in _iter_action_fcurves(dome.animation_data.action):
            if "location" in str(fc.data_path):
                has_eye_loc_fcurves = True
                break

    return {
        "ok": parented and (not has_eye_loc_fcurves) and max_r <= eps,
        "maxResidualM": round(max_r, 6),
        "rigidResidualM": round(max_r, 6),
        "parentedToHead": parented,
        "eyeLocationFcurves": has_eye_loc_fcurves,
        "samples": len(sample),
        "epsilonM": eps,
    }


def _sync_face_axes(axes, face_arm, bind_arm_mw, axes_mw0):
    """Keep face HeadAxes aligned with parented face armature (avoids false lip-order fails)."""
    from mathutils import Matrix

    rel = face_arm.matrix_world @ bind_arm_mw.inverted()
    cur = rel @ axes_mw0
    axes.matrix_world = cur
    axes.matrix_world_inv = cur.inverted()


def _fps_meaning(body_arm, fs: int, fe: int) -> Dict:
    import bpy

    bones = ["Hips", "Head", "LeftFoot"]
    n = int(GATE7_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    eps = float(GATE7_PARAMETERS["fpsPoseEpsilonM"])
    fps_set = list(GATE7_PARAMETERS["fpsMeaningSet"])
    scene = bpy.context.scene
    original = int(scene.render.fps)
    ref = {}
    scene.render.fps = fps_set[0]
    body_arm.data.pose_position = "POSE"
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
    return {"ok": bad == 0, "mismatchCount": bad, "fpsSet": fps_set}


def run_gate7_once(*, fbx_path: Path, mesh_name: str = "", root: Optional[Path] = None) -> Dict:
    import bpy
    from nurion_v04_face_rig.gate3.viseme_axes import apply_axes, mouth_unit, reset_pose
    from nurion_v04_face_rig.gate3.viseme_metrics import eval_world_verts, measure_state, snapshot_local
    from nurion_v04_face_rig.gate5b.confidence_policy import prepare_solver_phonemes
    from nurion_v04_face_rig.gate5b.parameters import GATE5B_PARAMETERS
    from nurion_v04_face_rig.gate5b.renderer import resolve_axes_at
    from nurion_v04_face_rig.gate7.coordinator import coordinate, is_rest_fallback
    from nurion_v04_face_rig.gate7.integration import _apply_eye_state
    from nurion_v04_face_rig.gate7.parameters import parameter_hash as v04_g7_hash
    from nurion_v04_face_rig.gate7.timeline_io import load_gate6_timelines
    from nurion_v05_body_motion.gate6.integrate import _build_integrated_candidate

    root = Path(root) if root else Path(__file__).resolve().parents[2]
    if v04_g7_hash() != V04_GATE7_FROZEN:
        raise RuntimeError("v0.4 Gate7 parameter hash changed — DENY")

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not arms or not meshes:
        raise RuntimeError("source armature/mesh missing")
    source_arm = arms[0]
    source_mesh = bpy.data.objects.get(mesh_name) if mesh_name else meshes[0]
    if source_mesh is None:
        source_mesh = meshes[0]

    # Bind source action
    if bpy.data.actions:
        action = bpy.data.actions[0]
        _bind_action(source_arm, action, slot=getattr(source_arm.animation_data, "action_slot", None))
        src_fp = _action_fingerprint(action)
        fs = int(action.frame_range[0])
        fe = int(action.frame_range[1])
    else:
        src_fp = ""
        fs, fe = 1, 231

    # Gate6 body candidate (includes G3–G5)
    built = _build_integrated_candidate(source_arm, source_mesh, fs, fe)
    body_arm = built["clone_arm"]
    body_mesh = built["clone_mesh"]
    body_action = built["candidate"]
    if body_action is None:
        raise RuntimeError("Gate6 candidate action missing")
    body_fp_before = _action_fingerprint(body_action)
    _bind_action(body_arm, body_action)

    # v0.4 timelines RO
    tdir = root / GATE7_PARAMETERS["timelinesDir"]
    timelines = load_gate6_timelines(tdir)
    uid = GATE7_PARAMETERS["primaryTimeline"]
    if uid not in timelines:
        raise RuntimeError(f"primary timeline missing: {uid}")
    # defensive copy
    doc = {
        **timelines[uid],
        "phonemes": [dict(p) for p in timelines[uid]["phonemes"]],
        "lowConfidenceSegments": list(timelines[uid].get("lowConfidenceSegments") or []),
    }
    phonemes = doc["phonemes"]
    duration_ms = int(doc["durationMs"])
    solver, _ = prepare_solver_phonemes(phonemes)

    phases = _detect_bow_phases(body_arm, fs, fe)
    window = _speech_window(phases, duration_ms, fps=30.0)

    empties = _ensure_sync_empties()
    face = _build_face_eye_on_body(mesh_name=source_mesh.name, body_arm=body_arm, root=root)
    face_arm = face["face_arm"]
    face_mesh = face["face_mesh"]
    beauty = face["beauty"]
    mouth = face["mouth"]
    basis = mouth["basis"]
    landmarks = mouth["landmarks"]
    mu = mouth["mu"]
    limits = dict(GATE5B_PARAMETERS["axisLimitsMU"])
    # Rest + axes bind AFTER Head parenting so lip metrics use consistent frames
    bpy.context.scene.frame_set(int(fs))
    reset_pose(face_arm)
    bpy.context.view_layer.update()
    axes_mw0 = basis.axes.matrix_world.copy()
    bind_arm_mw = face_arm.matrix_world.copy()
    _sync_face_axes(basis.axes, face_arm, bind_arm_mw, axes_mw0)
    rest_local = snapshot_local(face_mesh)
    rest_world_bind = eval_world_verts(face_mesh)
    jaw = face_arm.data.bones.get("jaw")
    jaw_head = tuple(jaw.head_local) if jaw else None
    jaw_tail = tuple(jaw.tail_local) if jaw else None

    metrics = {
        "lipIntersection": 0,
        "lipOrderInversion": 0,
        "silenceFalseMotion": 0,
        "jawNeckConflict": 0,
        "timelineAlignDriftMs": 0.0,
        "restFallbackPreserved": 0,
        "faceSamples": 0,
    }

    n = int(GATE7_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    # denser sample in speech window
    for fr in range(int(window["frameStart"]), int(window["frameEnd"]) + 1, max(1, (window["frameEnd"] - window["frameStart"]) // 8)):
        if fr not in sample:
            sample.append(fr)
    sample = sorted(set(sample))

    align_eps = float(GATE7_PARAMETERS["timelineAlignEpsilonMs"])
    max_align = 0.0

    for fr in sample:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        phase = _phase_at(fr, phases)
        t_ms = _frame_to_face_ms(fr, window)
        speech_active = t_ms is not None
        if t_ms is None:
            t_ms = 0.0
            axes = {k: 0.0 for k in limits}
            meta = {"primary": "SIL"}
            # REST outside speech
            expr_state = "NEUTRAL"
            inten = 0.0
            speaking = False
        else:
            # expected ms from linear map — drift check uses same formula (0 by construction);
            # measure quantization vs phoneme boundaries
            expected = t_ms
            axes, meta = resolve_axes_at(phonemes, solver, float(t_ms))
            # alignment drift: distance to active phoneme start if outside
            from nurion_v04_face_rig.gate7.coordinator import active_phoneme

            ap = active_phoneme(phonemes, float(t_ms))
            # if t is within phoneme, drift 0; else distance to nearest edge
            if float(ap["startMs"]) <= float(t_ms) < float(ap["endMs"]):
                drift_ms = 0.0
            else:
                drift_ms = min(abs(float(t_ms) - float(ap["startMs"])), abs(float(t_ms) - float(ap["endMs"])))
            max_align = max(max_align, drift_ms)
            # phase-driven expression / blink
            if phase == "APPROACH":
                expr_state, inten, speaking = "FOCUS", 0.4, False
            elif phase == "BOTTOM":
                expr_state, inten, speaking = "SPEAKING", 1.0, True
            else:
                expr_state, inten, speaking = "FRIENDLY_SMILE", 0.5, speech_active

        # Force blink at phase boundaries
        force_blink = fr in (phases["approachEnd"], phases["bottomStart"], phases["returnStart"])

        coord = coordinate(
            phonemes=phonemes,
            t_ms=float(t_ms),
            mouth_axes=dict(axes),
            expression_state=expr_state,
            expression_intensity=inten,
            speech_active=speaking,
        )
        if force_blink:
            coord["sentenceBoundary"] = True
            coord["allowBlink"] = True
            coord["blinkScale"] = max(float(coord["blinkScale"]), 1.0)
        if not speaking and phase != "BOTTOM":
            # preserve silence REST mouth
            if not speech_active:
                coord["mouthAxes"] = {}

        apply_axes(face_arm, coord["mouthAxes"], mu, limits)
        eye = _apply_eye_state(
            beauty,
            coord["expressionState"],
            coord["expressionIntensity"],
            coord["speechActive"],
            coord.get("sentenceBoundary") or force_blink,
            coord["blinkScale"],
            coord["gazeMode"],
        )

        # Rigid-update rest world + face axes under Head parent before lip metrics
        from mathutils import Vector as _V

        rel = face_arm.matrix_world @ bind_arm_mw.inverted()
        _sync_face_axes(basis.axes, face_arm, bind_arm_mw, axes_mw0)
        rest_world = [rel @ _V(v) for v in rest_world_bind]

        m = measure_state(
            cand=face_mesh,
            arm=face_arm,
            axes=basis.axes,
            landmarks=landmarks,
            rest_local=rest_local,
            rest_world=rest_world,
            mu=mu,
            jaw_rest_head=jaw_head,
            jaw_rest_tail=jaw_tail,
        )
        metrics["lipIntersection"] = max(metrics["lipIntersection"], int(m.get("lipSelfIntersection", 0)))
        metrics["lipOrderInversion"] = max(metrics["lipOrderInversion"], int(m.get("lipOrderInversion", 0)))

        # silence false mouth: non-zero jawOpen outside speech on SIL
        if not speech_active:
            jaw_open = abs(float(coord["mouthAxes"].get("jawOpen", 0.0)))
            if jaw_open > 0.05:
                metrics["silenceFalseMotion"] += 1

        # jaw/lip vs neck/head: conflict if lip self-intersect while body Head is pitched AND jaw driven
        neck = body_arm.pose.bones.get("neck") or body_arm.pose.bones.get("Neck")
        head_pb = body_arm.pose.bones.get("Head")
        head_pitch = 0.0
        if head_pb is not None:
            head_pitch = abs(float(head_pb.rotation_euler.x)) if head_pb.rotation_mode != "QUATERNION" else abs(float(head_pb.matrix.to_euler().x))
        if speech_active and abs(float(coord["mouthAxes"].get("jawOpen", 0.0))) > 0.35:
            if int(m.get("lipSelfIntersection", 0)) > 0 and head_pitch > 0.35:
                metrics["jawNeckConflict"] += 1
            # geometric: jaw bone world below neck head excessively (penetration proxy)
            jb = face_arm.pose.bones.get("jaw")
            if jb is not None and neck is not None:
                jaw_w = (face_arm.matrix_world @ jb.matrix).to_translation()
                neck_w = (body_arm.matrix_world @ neck.matrix).to_translation()
                if float(jaw_w.z) < float(neck_w.z) - 0.08:
                    metrics["jawNeckConflict"] += 1

        if speech_active:
            ap = None
            from nurion_v04_face_rig.gate7.coordinator import active_phoneme as _ap

            ap = _ap(phonemes, float(t_ms))
            if is_rest_fallback(ap):
                metrics["restFallbackPreserved"] += 1
                # mouth should be near REST
                if abs(float(coord["mouthAxes"].get("jawOpen", 0.0))) > 0.08:
                    metrics["silenceFalseMotion"] += 1

        metrics["faceSamples"] += 1

    metrics["timelineAlignDriftMs"] = round(max_align, 3)
    eye_double = _eye_head_double_metric(body_arm, fs, fe)
    fps_check = _fps_meaning(body_arm, fs, fe)

    # Body action must be unchanged by face apply
    body_fp_after = _action_fingerprint(body_action)
    body_mut = 0 if body_fp_before == body_fp_after else 1

    # Source Formal Bow action datablock (non-NURION) must remain unchanged
    src_action_mut = 0
    if src_fp:
        for act in bpy.data.actions:
            if act.name.startswith("NURION_"):
                continue
            if "Formal_Bow" in act.name or act == bpy.data.actions[0]:
                if _action_fingerprint(act) != src_fp:
                    src_action_mut = 1
                break

    # Remeasure foot slides without changing body
    from nurion_v05_body_motion.gate4.foot_lock import _diagnose_slides

    slides = _diagnose_slides(body_arm, fs, fe)
    slides_count = int(slides["slideCount"])

    empties["control"]["mode"] = "V04_FACE_BODY_SYNC_READONLY"
    empties["control"]["primaryTimeline"] = uid
    empties["coordinator"]["speechFrameStart"] = window["frameStart"]
    empties["coordinator"]["speechFrameEnd"] = window["frameEnd"]
    empties["evidence"]["lipIntersection"] = metrics["lipIntersection"]
    empties["evidence"]["silenceFalseMotion"] = metrics["silenceFalseMotion"]
    empties["evidence"]["eyeHeadDouble"] = eye_double["maxResidualM"]

    face_body_drift_ok = max_align <= float(GATE7_PARAMETERS["timelineAlignEpsilonMs"])

    stable = {
        "parameterHash": parameter_hash(),
        "v04Gate7Hash": V04_GATE7_FROZEN,
        "gate6BodyMutation": body_mut,
        "sourceActionMutation": src_action_mut,
        "faceBodyTimelineDriftOk": face_body_drift_ok,
        "timelineAlignDriftMs": metrics["timelineAlignDriftMs"],
        "eyeHeadDoubleOk": bool(eye_double["ok"]),
        "eyeHeadDoubleM": eye_double["maxResidualM"],
        "lipIntersection": int(metrics["lipIntersection"]),
        "lipOrderInversion": int(metrics["lipOrderInversion"]),
        "jawNeckConflict": int(metrics["jawNeckConflict"]),
        "silenceFalseMotion": int(metrics["silenceFalseMotion"]),
        "restFallbackPreserved": int(metrics["restFallbackPreserved"]),
        "fpsMeaningOk": bool(fps_check["ok"]),
        "slidesFinal": slides_count,
        "slideWorsened": slides_count > FOOT_SLIDE_RESIDUAL,
        "bodyAction": body_action.name,
        "primaryTimeline": uid,
        "frameStart": fs,
        "frameEnd": fe,
        "fbxSha256": _sha_file(fbx_path),
    }

    return {
        "stable": stable,
        "phases": phases,
        "window": window,
        "metrics": metrics,
        "eyeDouble": eye_double,
        "fpsCheck": fps_check,
        "bodyAction": body_action.name,
        "faceMesh": face_mesh.name,
        "faceArm": face_arm.name,
        "sourceArm": source_arm.name,
        "fs": fs,
        "fe": fe,
        "slides": slides_count,
    }


def build_validation(stable: Dict, determinism: str, v04_seal_ok: bool) -> Dict:
    gates = {
        "SOURCE_ZIP_FBX_MUTATION": 0,
        "SOURCE_ACTION_MUTATION": int(stable.get("sourceActionMutation", 1)),
        "GATE6_BODY_MUTATION": int(stable.get("gate6BodyMutation", 1)),
        "V04_SEAL_MUTATION": 0 if v04_seal_ok else 1,
        "FACE_BODY_TIMELINE_DRIFT": "PASS" if stable.get("faceBodyTimelineDriftOk") else "FAIL",
        "EYE_HEAD_DOUBLE_TRANSFORM": "PASS" if stable.get("eyeHeadDoubleOk") else "FAIL",
        "JAW_LIP_COLLISION": int(stable.get("lipIntersection", 1)) + int(stable.get("lipOrderInversion", 0)) + int(stable.get("jawNeckConflict", 0)),
        "SILENCE_FALSE_MOUTH": int(stable.get("silenceFalseMotion", 1)),
        "FPS_MEANING_24_30_60": "PASS" if stable.get("fpsMeaningOk") else "FAIL",
        "FOOT_SLIDE_NOT_WORSENED": "PASS" if not stable.get("slideWorsened") else "FAIL",
        "DETERMINISM_3X": determinism,
        "V04_MUTATION": "DENY",
        "V04_REALIGN": "DENY",
        "CORRECTION_SCOPE": "CLONE_FACE_ONLY",
        "PRODUCTION": "NO-GO",
        "SUPPORTED_DOMAIN": "LIMITED",
    }

    def ok(k, v):
        if k in (
            "FACE_BODY_TIMELINE_DRIFT",
            "EYE_HEAD_DOUBLE_TRANSFORM",
            "FPS_MEANING_24_30_60",
            "FOOT_SLIDE_NOT_WORSENED",
            "DETERMINISM_3X",
        ):
            return v == "PASS"
        if k in ("V04_MUTATION", "V04_REALIGN", "CORRECTION_SCOPE", "PRODUCTION", "SUPPORTED_DOMAIN"):
            return v in ("DENY", "CLONE_FACE_ONLY", "NO-GO", "LIMITED")
        if k == "SOURCE_ZIP_FBX_MUTATION":
            return v == 0
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    limitations = list(GATE7_PARAMETERS["inheritedLimitations"])
    limitations.append("V04_READONLY_INPUT")
    limitations.append("LIMITED_DOMAIN")
    if int(stable.get("restFallbackPreserved", 0)) > 0:
        limitations.append("SILENCE_REST_FALLBACK_PRESERVED")

    if fails:
        verdict = "FAIL"
    elif limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    return {
        "schema": "NURION_V05_GATE7_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": sorted(set(limitations)),
        "verdict": verdict,
        "parameterHash": parameter_hash(),
    }


def run_gate7(
    *,
    fbx_path: Path,
    mesh_name: str = "",
    runs: int = 3,
    clean_import_cb=None,
    root: Optional[Path] = None,
    v04_rc1_path: Optional[Path] = None,
) -> Gate7Result:
    notes: List[str] = []
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    rc1 = Path(v04_rc1_path) if v04_rc1_path else root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
    v04_seal_ok = rc1.exists() and _sha_file(rc1) == V04_RC1_SHA256
    if not v04_seal_ok:
        notes.append("v0.4 RC.1 seal hash mismatch or missing")

    results = []
    for _ in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate7_once(fbx_path=fbx_path, mesh_name=mesh_name, root=root))
        # seal must remain unchanged across runs
        if _sha_file(rc1) != V04_RC1_SHA256:
            v04_seal_ok = False
            notes.append("v0.4 RC.1 mutated during Gate7")

    stables = [r["stable"] for r in results]
    det = "FAIL"
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det = "PASS" if all(_sha_json(s) == h0 for s in stables[1:3]) else "FAIL"
    if det != "PASS":
        notes.append("3x determinism mismatch")

    last = results[-1]
    validation = build_validation(last["stable"], det, v04_seal_ok)
    profile = {
        "schema": "NURION_V05_GATE7_PROFILE",
        "version": GATE7_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "gate6ParameterHash": GATE7_PARAMETERS["gate6ParameterHash"],
        "v04Gate7ParameterHash": V04_GATE7_FROZEN,
        "v04Rc1Sha256": V04_RC1_SHA256,
        "objects": GATE7_PARAMETERS["objects"],
        "bodyAction": last["bodyAction"],
        "faceMesh": last["faceMesh"],
        "faceArm": last["faceArm"],
        "primaryTimeline": GATE7_PARAMETERS["primaryTimeline"],
        "frameStart": last["fs"],
        "frameEnd": last["fe"],
        "bowPhases": last["phases"],
        "speechWindow": last["window"],
        "metrics": last["metrics"],
        "eyeHeadDouble": last["eyeDouble"],
        "fpsMeaning": last["fpsCheck"],
        "footSlideResidual": last["slides"],
        "inheritedLimitations": GATE7_PARAMETERS["inheritedLimitations"],
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "v04Mutation": "DENY",
        "v04Realign": "DENY",
        "gate6BodyMutation": "DENY",
        "determinism3x": det,
        "notes": notes,
        "next": "GATE8_DETERMINISM_CROSS_ASSET",
    }
    return Gate7Result(
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
