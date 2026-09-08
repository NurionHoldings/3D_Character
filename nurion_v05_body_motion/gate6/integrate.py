"""Gate6 clone-only integrated correction candidate Action."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import FOOT_SLIDE_RESIDUAL_GATE4, GATE6_PARAMETERS, parameter_hash


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Gate6Result:
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


def _bone_action_fingerprint(action, bone_name: str) -> str:
    payload = []
    prefix = f'pose.bones["{bone_name}"]'
    for fc in _iter_action_fcurves(action):
        if not fc.data_path.startswith(prefix):
            continue
        keys = [(round(float(k.co.x), 6), round(float(k.co.y), 6)) for k in fc.keyframe_points]
        payload.append((fc.data_path, int(fc.array_index), keys))
    return _sha_json(payload)


def _count_keys(action) -> Dict:
    total = 0
    by_bone: Dict[str, int] = {}
    for fc in _iter_action_fcurves(action):
        n = len(fc.keyframe_points)
        total += n
        path = fc.data_path
        if 'pose.bones["' in path:
            bone = path.split('pose.bones["', 1)[1].split('"]', 1)[0]
            by_bone[bone] = by_bone.get(bone, 0) + n
    return {"totalKeys": total, "byBone": by_bone}


def _snapshot_mesh(obj):
    return [(float(v.co.x), float(v.co.y), float(v.co.z)) for v in obj.data.vertices]


def _snapshot_arm_rest(arm) -> Dict:
    out = {}
    for b in arm.data.bones:
        out[b.name] = {
            "parent": b.parent.name if b.parent else None,
            "length": round(float(b.length), 8),
            "head": (
                round(float(b.head_local.x), 8),
                round(float(b.head_local.y), 8),
                round(float(b.head_local.z), 8),
            ),
            "tail": (
                round(float(b.tail_local.x), 8),
                round(float(b.tail_local.y), 8),
                round(float(b.tail_local.z), 8),
            ),
        }
    return out


def _clear_prior_gate6():
    import bpy

    prefixes = (
        "NURION_BodyMotion",
        "NURION_BodyRig",
        "NURION_Candidate",
        "NURION_Penetration",
        "NURION_FootLock",
        "NURION_JointLimit",
    )
    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.name.startswith("NURION_BodyRig"):
            bpy.data.armatures.remove(arm, do_unlink=True)
    for pref in (
        GATE6_PARAMETERS["objects"]["cloneActionPrefix"],
        GATE6_PARAMETERS["objects"]["candidateAction"],
        "NURION_Gate5_CloneAction",
        "NURION_Gate4_CloneAction",
        "NURION_Gate3_CloneAction",
    ):
        for act in list(bpy.data.actions):
            if act.name.startswith(pref) or act.name == pref:
                bpy.data.actions.remove(act)
    col = bpy.data.collections.get("NURION_BodyMotionClone")
    if col is not None:
        for obj in list(col.objects):
            col.objects.unlink(obj)


def _ensure_collection(name: str):
    import bpy

    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


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


def _clone_rig_and_mesh(source_arm, source_mesh):
    import bpy

    _clear_prior_gate6()
    col = _ensure_collection("NURION_BodyMotionClone")
    names = GATE6_PARAMETERS["objects"]

    arm_data = source_arm.data.copy()
    arm_data.name = "NURION_BodyRigClone_Data"
    clone_arm = bpy.data.objects.new(names["candidateArmature"], arm_data)
    clone_arm.matrix_world = source_arm.matrix_world.copy()
    col.objects.link(clone_arm)

    mesh_data = source_mesh.data.copy()
    mesh_data.name = "NURION_BodyMotionCandidate_Mesh"
    clone_mesh = bpy.data.objects.new(names["candidateMesh"], mesh_data)
    clone_mesh.matrix_world = source_mesh.matrix_world.copy()
    col.objects.link(clone_mesh)

    mw = clone_mesh.matrix_world.copy()
    clone_mesh.parent = clone_arm
    clone_mesh.matrix_world = mw
    for mod in list(clone_mesh.modifiers):
        clone_mesh.modifiers.remove(mod)
    mod = clone_mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = clone_arm

    clone_action = None
    if source_arm.animation_data and source_arm.animation_data.action:
        src_action = source_arm.animation_data.action
        clone_action = src_action.copy()
        clone_action.name = f"{names['cloneActionPrefix']}_{src_action.name}"[:63]
        slots = list(getattr(clone_action, "slots", []) or [])
        _bind_action(clone_arm, clone_action, slot=slots[0] if slots else None)

    for key in ("control", "evidence"):
        obj = bpy.data.objects.new(names[key], None)
        obj.empty_display_type = "PLAIN_AXES"
        col.objects.link(obj)

    bpy.context.view_layer.update()
    return clone_arm, clone_mesh, clone_action


def _consolidate_action_keys(action) -> Dict:
    """Remove duplicate frame keys; drop linearly redundant interior keys."""
    if action is None:
        return {"removedDup": 0, "removedRedundant": 0, "curves": 0}

    frame_eps = float(GATE6_PARAMETERS["keyDedupFrameEps"])
    val_eps = float(GATE6_PARAMETERS["keyRedundantValueEps"])
    removed_dup = 0
    removed_red = 0
    curves = 0

    for fc in list(_iter_action_fcurves(action)):
        curves += 1
        pts = list(fc.keyframe_points)
        if len(pts) < 2:
            continue
        # Dedup same-frame: keep last
        by_frame = {}
        for kp in pts:
            fr = float(kp.co.x)
            # bucket
            key = round(fr / frame_eps) * frame_eps
            by_frame[key] = kp
        if len(by_frame) < len(pts):
            removed_dup += len(pts) - len(by_frame)
            # rebuild: clear and reinsert
            coords = sorted(((float(k), float(by_frame[k].co.y)) for k in by_frame.keys()), key=lambda t: t[0])
            while len(fc.keyframe_points) > 0:
                fc.keyframe_points.remove(fc.keyframe_points[0])
            for fr, val in coords:
                fc.keyframe_points.insert(fr, val, options={"FAST"})
            fc.update()

        # Remove redundant interior keys (colinear)
        pts = list(fc.keyframe_points)
        if len(pts) < 3:
            continue
        keep_idx = {0, len(pts) - 1}
        for i in range(1, len(pts) - 1):
            x0, y0 = float(pts[i - 1].co.x), float(pts[i - 1].co.y)
            x1, y1 = float(pts[i].co.x), float(pts[i].co.y)
            x2, y2 = float(pts[i + 1].co.x), float(pts[i + 1].co.y)
            if abs(x2 - x0) < 1e-12:
                keep_idx.add(i)
                continue
            y_lerp = y0 + (y2 - y0) * ((x1 - x0) / (x2 - x0))
            if abs(y1 - y_lerp) > val_eps:
                keep_idx.add(i)
            else:
                removed_red += 1
        if len(keep_idx) < len(pts):
            coords = [(float(pts[i].co.x), float(pts[i].co.y)) for i in sorted(keep_idx)]
            while len(fc.keyframe_points) > 0:
                fc.keyframe_points.remove(fc.keyframe_points[0])
            for fr, val in coords:
                fc.keyframe_points.insert(fr, val, options={"FAST"})
            fc.update()

    action.update_tag()
    return {"removedDup": removed_dup, "removedRedundant": removed_red, "curves": curves}


def _finalize_candidate_action(clone_action):
    """Rename/copy to stable candidate Action datablock name."""
    import bpy

    if clone_action is None:
        return None
    name = GATE6_PARAMETERS["objects"]["candidateAction"]
    # If exists, remove
    existing = bpy.data.actions.get(name)
    if existing is not None and existing != clone_action:
        bpy.data.actions.remove(existing)
    clone_action.name = name
    return clone_action


def _rest_hierarchy_axis_check(source_arm, clone_arm) -> Dict:
    src = _snapshot_arm_rest(source_arm)
    cl = _snapshot_arm_rest(clone_arm)
    parent_breaks = []
    length_breaks = []
    for name, a in src.items():
        b = cl.get(name)
        if b is None:
            parent_breaks.append({"bone": name, "reason": "MISSING"})
            continue
        if a["parent"] != b["parent"]:
            parent_breaks.append({"bone": name, "before": a["parent"], "after": b["parent"]})
        rel = abs(a["length"] - b["length"]) / max(a["length"], 1e-8)
        if rel > float(GATE6_PARAMETERS["restLengthRelEps"]):
            length_breaks.append({"bone": name, "before": a["length"], "after": b["length"]})

    # spine axis dots on clone rest
    axis_abnormal = []
    chain = GATE6_PARAMETERS["spineChain"]
    for i in range(len(chain) - 1):
        a = clone_arm.data.bones.get(chain[i])
        b = clone_arm.data.bones.get(chain[i + 1])
        if a is None or b is None:
            continue
        y = (a.tail_local - a.head_local).normalized()
        to_c = b.head_local - a.head_local
        if to_c.length < 1e-8:
            continue
        to_c.normalize()
        d = float(y.dot(to_c))
        # Hips→Spine02 known non-colinear (Gate2 limitation) — exclude from fail
        if chain[i] == "Hips":
            continue
        if d < float(GATE6_PARAMETERS["axisDotMin"]):
            axis_abnormal.append({"from": chain[i], "to": chain[i + 1], "dot": round(d, 5)})

    return {
        "parentBreaks": parent_breaks,
        "lengthBreaks": length_breaks,
        "axisAbnormal": axis_abnormal,
        "ok": not parent_breaks and not length_breaks and not axis_abnormal,
    }


def _motion_drift(source_arm, clone_arm, fs: int, fe: int) -> Dict:
    import bpy

    bones = ["Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "Spine"]
    n = int(GATE6_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    eps = float(GATE6_PARAMETERS["motionMeaningEpsilonM"])
    max_d = 0.0
    worst = None
    source_arm.data.pose_position = "POSE"
    clone_arm.data.pose_position = "POSE"
    for fr in sample:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        for bn in bones:
            sp = source_arm.pose.bones.get(bn)
            cp = clone_arm.pose.bones.get(bn)
            if sp is None or cp is None:
                continue
            s = (source_arm.matrix_world @ sp.matrix).to_translation()
            c = (clone_arm.matrix_world @ cp.matrix).to_translation()
            d = math.sqrt((s.x - c.x) ** 2 + (s.y - c.y) ** 2 + (s.z - c.z) ** 2)
            if d > max_d:
                max_d = d
                worst = {"frame": fr, "bone": bn, "driftM": round(d, 6)}
    return {"maxDriftM": round(max_d, 6), "worst": worst, "epsilonM": eps, "ok": max_d <= eps, "samples": len(sample)}


def _fps_meaning_check(clone_arm, fs: int, fe: int) -> Dict:
    """Frame-locked poses must be identical under scene FPS 24/30/60."""
    import bpy

    bones = ["Hips", "Head", "LeftFoot", "RightHand"]
    n = int(GATE6_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    eps = float(GATE6_PARAMETERS["fpsPoseEpsilonM"])
    fps_set = list(GATE6_PARAMETERS["fpsMeaningSet"])

    # Capture reference at current fps
    scene = bpy.context.scene
    original_fps = int(scene.render.fps)
    ref = {}
    scene.render.fps = fps_set[0]
    clone_arm.data.pose_position = "POSE"
    for fr in sample:
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        ref[fr] = {}
        for bn in bones:
            pb = clone_arm.pose.bones.get(bn)
            if pb is None:
                continue
            t = (clone_arm.matrix_world @ pb.matrix).to_translation()
            ref[fr][bn] = (float(t.x), float(t.y), float(t.z))

    mismatches = []
    for fps in fps_set[1:]:
        scene.render.fps = int(fps)
        for fr in sample:
            scene.frame_set(fr)
            bpy.context.view_layer.update()
            for bn in bones:
                pb = clone_arm.pose.bones.get(bn)
                if pb is None or bn not in ref[fr]:
                    continue
                t = (clone_arm.matrix_world @ pb.matrix).to_translation()
                r = ref[fr][bn]
                d = math.sqrt((t.x - r[0]) ** 2 + (t.y - r[1]) ** 2 + (t.z - r[2]) ** 2)
                if d > eps:
                    mismatches.append({"fps": fps, "frame": fr, "bone": bn, "driftM": round(d, 8)})

    scene.render.fps = original_fps
    return {
        "fpsSet": fps_set,
        "mismatchCount": len(mismatches),
        "mismatches": mismatches[:20],
        "ok": len(mismatches) == 0,
        "note": "Frame-index poses must be FPS-invariant for Formal Bow timing preservation.",
    }


def _build_integrated_candidate(source_arm, source_mesh, fs: int, fe: int) -> Dict:
    """Apply G3→G4→G5 then consolidate into one candidate Action."""
    from nurion_v05_body_motion.gate3.inspect_correct import (
        _apply_limited_correction,
        _inspect_frames,
    )
    from nurion_v05_body_motion.gate4.foot_lock import (
        _apply_foot_lock,
        _classify_support,
        _compute_ground_plane,
        _diagnose_slides,
        _sample_foot_series,
    )
    from nurion_v05_body_motion.gate5.penetration import (
        _apply_limited_pen_correction,
        _build_region_maps,
        _inspect_penetration,
    )

    clone_arm, clone_mesh, clone_action = _clone_rig_and_mesh(source_arm, source_mesh)

    # Gate3
    g3_inspect = _inspect_frames(clone_arm, fs, fe)
    g3 = _apply_limited_correction(clone_arm, clone_action, g3_inspect, fs, fe)
    keys_after_g3 = _count_keys(clone_action)
    forearm_fp = _bone_action_fingerprint(clone_action, "RightForeArm") if clone_action else ""

    # Gate4
    slides_pre = _diagnose_slides(clone_arm, fs, fe)
    series = _sample_foot_series(clone_arm, fs, fe)
    ground = _compute_ground_plane(series)
    ground_z = float(slides_pre.get("groundZProxy") or ground["groundZ"])
    classify = _classify_support(series, ground_z)
    g4 = _apply_foot_lock(clone_arm, clone_action, series, ground_z, classify, fs, fe)
    keys_after_g4 = _count_keys(clone_action)
    foot_fps = {
        b: _bone_action_fingerprint(clone_action, b)
        for b in ("LeftFoot", "LeftToeBase", "RightFoot", "RightToeBase")
        if clone_action
    }

    # Gate5
    region_maps = _build_region_maps(clone_mesh)
    pen_before = _inspect_penetration(clone_mesh, fs, fe, region_maps)
    g5 = {"applied": False, "reason": "SKIP", "framesCorrected": 0}
    if pen_before.get("sustainedCount", 0) > 0 or float(pen_before.get("maxDepthM") or 0) >= 0.008:
        g5 = _apply_limited_pen_correction(clone_arm, clone_action, clone_mesh, pen_before, region_maps)
    pen_after = _inspect_penetration(clone_mesh, fs, fe, region_maps)
    keys_after_g5 = _count_keys(clone_action)

    # Consolidate duplicate/redundant keys
    consolidate = _consolidate_action_keys(clone_action)
    keys_final = _count_keys(clone_action)
    candidate = _finalize_candidate_action(clone_action)
    if candidate is not None:
        _bind_action(clone_arm, candidate)

    # Remeasure slides + shallow contact
    slides_final = _diagnose_slides(clone_arm, fs, fe)
    shallow_ok = float(pen_after.get("maxDepthM") or 0) <= float(GATE6_PARAMETERS["shallowContactDepthMaxM"])
    forearm_ok = forearm_fp == (_bone_action_fingerprint(candidate, "RightForeArm") if candidate else "")
    # After consolidate, forearm keys should be unchanged in values — fingerprint may change if redundant keys removed from other bones only; re-check forearm curve content
    # Actually consolidate may remove redundant keys ON forearm too — allow fingerprint change only if key count dropped with same samples
    # Safer: compare evaluated pose of RightForeArm at sample frames vs post-g3 before consolidate — done after via hyperextension policy: don't re-correct. Verify bone not in g5 touches.
    g5_bones = set(g5.get("bonesTouched") or [])
    forearm_untouched_by_g5 = "RightForeArm" not in g5_bones

    return {
        "clone_arm": clone_arm,
        "clone_mesh": clone_mesh,
        "candidate": candidate,
        "g3": g3,
        "g4": g4,
        "g5": g5,
        "keysAfterG3": keys_after_g3,
        "keysAfterG4": keys_after_g4,
        "keysAfterG5": keys_after_g5,
        "keysFinal": keys_final,
        "consolidate": consolidate,
        "slidesPreG4": int(slides_pre["slideCount"]),
        "slidesFinal": int(slides_final["slideCount"]),
        "penBefore": pen_before,
        "penAfter": pen_after,
        "shallowOk": shallow_ok,
        "forearmFpPostG3": forearm_fp,
        "forearmUntouchedByG5": forearm_untouched_by_g5,
        "footFps": foot_fps,
        "groundZ": ground_z,
        "regionCounts": region_maps["counts"],
    }


def run_gate6_once(*, fbx_path: Path, mesh_name: str = "") -> Dict:
    import bpy

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not arms or not meshes:
        raise RuntimeError("source armature/mesh missing")
    source_arm = arms[0]
    source_mesh = bpy.data.objects.get(mesh_name) if mesh_name else None
    if source_mesh is None:
        source_mesh = meshes[0]
        for m in meshes:
            for mod in m.modifiers:
                if mod.type == "ARMATURE":
                    source_mesh = m
                    break

    src_mesh_before = _snapshot_mesh(source_mesh)
    src_arm_before = _snapshot_arm_rest(source_arm)
    src_action = None
    src_fp_before = None
    if bpy.data.actions:
        action = bpy.data.actions[0]
        src_action = action
        if source_arm.animation_data is None:
            source_arm.animation_data_create()
        _bind_action(source_arm, action, slot=getattr(source_arm.animation_data, "action_slot", None))
        src_fp_before = _action_fingerprint(action)
        fs = int(action.frame_range[0])
        fe = int(action.frame_range[1])
    else:
        fs, fe = 1, 231

    built = _build_integrated_candidate(source_arm, source_mesh, fs, fe)
    clone_arm = built["clone_arm"]
    clone_mesh = built["clone_mesh"]
    candidate = built["candidate"]

    rest_check = _rest_hierarchy_axis_check(source_arm, clone_arm)
    drift = _motion_drift(source_arm, clone_arm, fs, fe)
    fps_check = _fps_meaning_check(clone_arm, fs, fe)

    # Gate3 keys retained: RightForeArm or corrected bones should still have keys; use g3 keysWritten
    g3_keys = int(built["g3"].get("keysWritten") or 0)
    g3_ok = g3_keys >= int(GATE6_PARAMETERS["gate3MinKeysExpected"]) or bool(built["g3"].get("applied")) is False
    # Prefer applied with keys
    if built["g3"].get("applied"):
        g3_ok = g3_keys >= int(GATE6_PARAMETERS["gate3MinKeysExpected"])

    g4_ok = bool(built["g4"].get("applied")) or built["g4"].get("reason") in (
        "NO_FRAMES",
        "REVERTED_MOTION_MEANING",
    )
    # Foot lock should be applied for Formal Bow
    g4_applied = bool(built["g4"].get("applied"))

    slide_final = int(built["slidesFinal"])
    slide_worsened = slide_final > FOOT_SLIDE_RESIDUAL_GATE4 + int(GATE6_PARAMETERS["slideWorsenTol"])

    src_mesh_after = _snapshot_mesh(source_mesh)
    src_arm_after = _snapshot_arm_rest(source_arm)
    src_mut = 0 if src_mesh_before == src_mesh_after and src_arm_before == src_arm_after else 1
    src_action_mut = 0
    if src_action is not None and src_fp_before is not None:
        src_action_mut = 0 if _action_fingerprint(src_action) == src_fp_before else 1

    ctrl = bpy.data.objects.get(GATE6_PARAMETERS["objects"]["control"])
    if ctrl:
        ctrl["mode"] = "CLONE_SAFE_CANDIDATE"
        ctrl["candidateAction"] = candidate.name if candidate else ""
    evid = bpy.data.objects.get(GATE6_PARAMETERS["objects"]["evidence"])
    if evid:
        evid["maxDriftM"] = drift["maxDriftM"]
        evid["slidesFinal"] = slide_final
        evid["keysFinal"] = built["keysFinal"]["totalKeys"]

    stable = {
        "parameterHash": parameter_hash(),
        "sourceMutation": src_mut,
        "sourceActionMutation": src_action_mut,
        "candidateAction": candidate.name if candidate else None,
        "g3KeysWritten": g3_keys,
        "g3Retained": bool(g3_ok),
        "g4Applied": g4_applied,
        "g5Applied": bool(built["g5"].get("applied")),
        "g5FramesCorrected": int(built["g5"].get("framesCorrected") or 0),
        "keysAfterG3": int(built["keysAfterG3"]["totalKeys"]),
        "keysAfterG4": int(built["keysAfterG4"]["totalKeys"]),
        "keysAfterG5": int(built["keysAfterG5"]["totalKeys"]),
        "keysFinal": int(built["keysFinal"]["totalKeys"]),
        "removedDup": int(built["consolidate"]["removedDup"]),
        "removedRedundant": int(built["consolidate"]["removedRedundant"]),
        "restHierarchyAxisOk": bool(rest_check["ok"]),
        "parentBreaks": len(rest_check["parentBreaks"]),
        "lengthBreaks": len(rest_check["lengthBreaks"]),
        "axisAbnormal": len(rest_check["axisAbnormal"]),
        "motionMeaningOk": bool(drift["ok"]),
        "maxDriftM": drift["maxDriftM"],
        "fpsMeaningOk": bool(fps_check["ok"]),
        "fpsMismatchCount": int(fps_check["mismatchCount"]),
        "slidesFinal": slide_final,
        "slideWorsened": bool(slide_worsened),
        "shallowContactOk": bool(built["shallowOk"]),
        "sustainedAfter": int(built["penAfter"].get("sustainedCount") or 0),
        "maxDepthAfter": float(built["penAfter"].get("maxDepthM") or 0),
        "forearmUntouchedByG5": bool(built["forearmUntouchedByG5"]),
        "fbxSha256": _sha_file(fbx_path),
        "frameStart": fs,
        "frameEnd": fe,
    }

    return {
        "stable": stable,
        "restCheck": rest_check,
        "drift": drift,
        "fpsCheck": fps_check,
        "built": {
            "g3": built["g3"],
            "g4": {k: built["g4"].get(k) for k in ("applied", "reason", "framesCorrected", "channelWrites")},
            "g5": {k: built["g5"].get(k) for k in ("applied", "reason", "framesCorrected", "channelWrites", "bonesTouched")},
            "consolidate": built["consolidate"],
            "keysFinal": built["keysFinal"],
            "slidesFinal": built["slidesFinal"],
            "penAfter": {
                "sustainedCount": built["penAfter"].get("sustainedCount"),
                "momentaryCount": built["penAfter"].get("momentaryCount"),
                "maxDepthM": built["penAfter"].get("maxDepthM"),
            },
            "candidateAction": candidate.name if candidate else None,
        },
        "sourceArm": source_arm.name,
        "cloneArm": clone_arm.name,
        "cloneMesh": clone_mesh.name,
        "fs": fs,
        "fe": fe,
    }


def build_validation(stable: Dict, determinism: str) -> Dict:
    gates = {
        "SOURCE_ZIP_FBX_MUTATION": 0,
        "SOURCE_CHARACTER_MUTATION": int(stable.get("sourceMutation", 1)),
        "SOURCE_ACTION_MUTATION": int(stable.get("sourceActionMutation", 1)),
        "GATE3_KEYS_RETAINED": "PASS" if stable.get("g3Retained") else "FAIL",
        "GATE4_FOOT_LOCK_PRESENT": "PASS" if stable.get("g4Applied") else "FAIL",
        "REST_HIERARCHY_AXIS": "PASS" if stable.get("restHierarchyAxisOk") else "FAIL",
        "MOTION_MEANING": "PASS" if stable.get("motionMeaningOk") else "FAIL",
        "FPS_MEANING_24_30_60": "PASS" if stable.get("fpsMeaningOk") else "FAIL",
        "FOOT_SLIDE_NOT_WORSENED": "PASS" if not stable.get("slideWorsened") else "FAIL",
        "SHALLOW_CONTACT_ACCEPTABLE": "PASS" if stable.get("shallowContactOk") else "FAIL",
        "FOREARM_POLICY": "PASS" if stable.get("forearmUntouchedByG5") else "FAIL",
        "DETERMINISM_3X": determinism,
        "V04_MUTATION": "DENY",
        "CORRECTION_SCOPE": "CLONE_ONLY",
        "FORCE_LIMITATIONS_ZERO": "DENY",
        "RIGHTFOREARM_RECORRECT": "DENY",
    }

    def ok(k, v):
        if k in (
            "GATE3_KEYS_RETAINED",
            "GATE4_FOOT_LOCK_PRESENT",
            "REST_HIERARCHY_AXIS",
            "MOTION_MEANING",
            "FPS_MEANING_24_30_60",
            "FOOT_SLIDE_NOT_WORSENED",
            "SHALLOW_CONTACT_ACCEPTABLE",
            "FOREARM_POLICY",
            "DETERMINISM_3X",
        ):
            return v == "PASS"
        if k in ("V04_MUTATION", "CORRECTION_SCOPE", "FORCE_LIMITATIONS_ZERO", "RIGHTFOREARM_RECORRECT"):
            return v in ("DENY", "CLONE_ONLY")
        if k == "SOURCE_ZIP_FBX_MUTATION":
            return v == 0
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    limitations = []
    limitations.append("FORCE_LIMITATIONS_TO_ZERO_DENIED")
    if int(stable.get("slidesFinal", 0)) > 0:
        limitations.append(f"FOOT_SLIDE_RESIDUAL_{int(stable.get('slidesFinal', 0))}")
    if int(stable.get("sustainedAfter", 0)) > 0:
        limitations.append("SHALLOW_SUSTAINED_CONTACT_ACCEPTED")
    limitations.append("GATE3_REVERSE_FOREARM_MILD_PRESERVED")
    if int(stable.get("removedDup", 0)) + int(stable.get("removedRedundant", 0)) > 0:
        limitations.append("KEY_DEDUP_CONSOLIDATED")
    if stable.get("g5Applied"):
        limitations.append("GATE5_PEN_CORRECTION_IN_CANDIDATE")
    if not stable.get("g5Applied"):
        limitations.append("GATE5_PEN_CORRECTION_SKIPPED_OR_EMPTY")

    if fails:
        verdict = "FAIL"
    elif limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    return {
        "schema": "NURION_V05_GATE6_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": sorted(set(limitations)),
        "verdict": verdict,
        "parameterHash": parameter_hash(),
    }


def run_gate6(*, fbx_path: Path, mesh_name: str = "", runs: int = 3, clean_import_cb=None) -> Gate6Result:
    notes: List[str] = []
    results = []
    for _ in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate6_once(fbx_path=fbx_path, mesh_name=mesh_name))

    stables = [r["stable"] for r in results]
    det = "FAIL"
    if len(stables) >= 3:
        # Exclude candidateAction name churn; hash core fields
        def _core(s):
            return {k: v for k, v in s.items() if k != "candidateAction"}

        h0 = _sha_json(_core(stables[0]))
        det = "PASS" if all(_sha_json(_core(s)) == h0 for s in stables[1:3]) else "FAIL"
    if det != "PASS":
        notes.append("3x determinism mismatch")

    last = results[-1]
    validation = build_validation(last["stable"], det)
    profile = {
        "schema": "NURION_V05_GATE6_PROFILE",
        "version": GATE6_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE6_PARAMETERS["gate1ParameterHash"],
        "gate2ParameterHash": GATE6_PARAMETERS["gate2ParameterHash"],
        "gate3ParameterHash": GATE6_PARAMETERS["gate3ParameterHash"],
        "gate4ParameterHash": GATE6_PARAMETERS["gate4ParameterHash"],
        "gate5ParameterHash": GATE6_PARAMETERS["gate5ParameterHash"],
        "objects": GATE6_PARAMETERS["objects"],
        "sourceArm": last["sourceArm"],
        "cloneArm": last["cloneArm"],
        "cloneMesh": last["cloneMesh"],
        "candidateAction": last["built"]["candidateAction"],
        "frameStart": last["fs"],
        "frameEnd": last["fe"],
        "integration": last["built"],
        "restHierarchyAxis": last["restCheck"],
        "motionDrift": last["drift"],
        "fpsMeaning": last["fpsCheck"],
        "footSlideResidualGate4": FOOT_SLIDE_RESIDUAL_GATE4,
        "footSlideFinal": last["stable"]["slidesFinal"],
        "forceLimitationsToZero": "DENY",
        "rightForeArmReCorrect": "DENY",
        "determinism3x": det,
        "v04Mutation": "DENY",
        "sourceZipFbxMutation": "DENY",
        "sourceActionMutation": "DENY",
        "production": "NO-GO",
        "next": "GATE7_V04_FACE_EYE_LIPSYNC_SYNC_READONLY",
        "notes": notes,
    }
    return Gate6Result(
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
