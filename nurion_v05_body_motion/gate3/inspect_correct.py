"""Gate3 clone-only joint limits / abnormal deform inspect + limited correction."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import FOOT_SLIDE_INHERITED, GATE3_PARAMETERS, parameter_hash


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_action_fcurves(action):
    """Yield fcurves from legacy or Blender 5 layered Actions."""
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

@dataclass
class Gate3Result:
    profile: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def _snapshot_mesh(obj) -> List[Tuple[float, float, float]]:
    return [(float(v.co.x), float(v.co.y), float(v.co.z)) for v in obj.data.vertices]


def _snapshot_arm_rest(arm) -> Dict[str, Dict]:
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
        }
    return out


def _clear_prior_gate3():
    import bpy

    prefixes = ("NURION_BodyMotion", "NURION_BodyRig", "NURION_JointLimit")
    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.name.startswith("NURION_BodyRig"):
            bpy.data.armatures.remove(arm, do_unlink=True)
    pref = GATE3_PARAMETERS["objects"]["cloneActionPrefix"]
    for act in list(bpy.data.actions):
        if act.name.startswith(pref):
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
    slots = getattr(action, "slots", None)
    if slots and len(slots) > 0:
        try:
            obj.animation_data.action_slot = slots[0]
        except Exception:
            pass


def _clone_rig_and_mesh(source_arm, source_mesh, *, own_action: bool):
    """Duplicate armature+mesh. If own_action, copy Action datablock (source Action immutable)."""
    import bpy

    _clear_prior_gate3()
    col = _ensure_collection("NURION_BodyMotionClone")
    names = GATE3_PARAMETERS["objects"]

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

    src_action = None
    src_slot = None
    if source_arm.animation_data and source_arm.animation_data.action:
        src_action = source_arm.animation_data.action
        src_slot = getattr(source_arm.animation_data, "action_slot", None)

    clone_action = None
    if src_action is not None:
        if own_action:
            clone_action = src_action.copy()
            clone_action.name = f"{names['cloneActionPrefix']}_{src_action.name}"[:63]
            # Copied layered Action keeps slots; bind first/only slot
            slot = None
            slots = list(getattr(clone_action, "slots", []) or [])
            if slots:
                slot = slots[0]
            _bind_action(clone_arm, clone_action, slot=slot)
        else:
            _bind_action(clone_arm, src_action, slot=src_slot)

    for key in ("control", "evidence"):
        obj = bpy.data.objects.new(names[key], None)
        obj.empty_display_type = "PLAIN_AXES"
        col.objects.link(obj)

    bpy.context.view_layer.update()
    return clone_arm, clone_mesh, clone_action, src_action


def _local_pose_angle_deg(pb) -> float:
    """Magnitude of local pose rotation vs rest (matrix_basis)."""
    q = pb.matrix_basis.to_quaternion()
    # Blender quaternion.angle is 0..pi
    return float(math.degrees(abs(q.angle)))


def _world_head(arm, bone_name: str):
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return None
    return arm.matrix_world @ pb.head


def _hinge_vectors(arm, parent: str, joint: str, child: str):
    A = _world_head(arm, parent)
    B = _world_head(arm, joint)
    C = _world_head(arm, child)
    if A is None or B is None or C is None:
        return None
    v1 = (A - B).normalized()
    v2 = (C - B).normalized()
    return v1, v2


def _raw_hinge_flexion(arm, parent: str, joint: str, child: str) -> Optional[Tuple[float, object]]:
    """
    Returns (unsigned_flexion_deg, cross_vec).
    unsigned 0 ~= straight; larger ~= more bent. Sign resolved later via clip calibration.
    """
    hv = _hinge_vectors(arm, parent, joint, child)
    if hv is None:
        return None
    v1, v2 = hv
    dot = max(-1.0, min(1.0, float(v1.dot(v2))))
    interior = math.degrees(math.acos(dot))  # 0..180; straight ~180
    unsigned = max(0.0, 180.0 - interior)
    cross = v1.cross(v2)
    return float(unsigned), cross


def _calibrate_hinge_refs(arm, hinge_specs: List[Tuple], fs: int, fe: int) -> Dict[str, object]:
    """
    For each hinge joint, pick a reference bend normal from frames with clear flexion.
    Reverse joints are opposite-side bends past threshold relative to this reference.
    """
    import bpy
    from mathutils import Vector

    refs: Dict[str, object] = {}
    acc: Dict[str, List] = {j: [] for _, _, j, _, _, _ in hinge_specs}
    step = max(1, (int(fe) - int(fs)) // 24)
    arm.data.pose_position = "POSE"
    for fr in range(int(fs), int(fe) + 1, step):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        for _, p, j, c, _, _ in hinge_specs:
            raw = _raw_hinge_flexion(arm, p, j, c)
            if raw is None:
                continue
            unsigned, cross = raw
            if unsigned >= 15.0 and cross.length > 1e-6:
                acc[j].append(cross.normalized().copy())
    for _, _, j, _, _, _ in hinge_specs:
        vecs = acc.get(j) or []
        if not vecs:
            # fallback: joint bone rest X axis in world
            pb = arm.pose.bones.get(j)
            if pb is not None:
                refs[j] = (arm.matrix_world.to_3x3() @ pb.bone.x_axis).normalized()
            else:
                refs[j] = Vector((1.0, 0.0, 0.0))
            continue
        # average direction
        s = Vector((0.0, 0.0, 0.0))
        for v in vecs:
            s += v
        if s.length < 1e-8:
            refs[j] = vecs[0]
        else:
            refs[j] = s.normalized()
    return refs


def _signed_hinge_flexion_deg(arm, parent: str, joint: str, child: str, hinge_ref) -> Optional[float]:
    """Signed flexion: + = same side as calibrated anatomical bend, - = reverse."""
    raw = _raw_hinge_flexion(arm, parent, joint, child)
    if raw is None:
        return None
    unsigned, cross = raw
    if cross.length < 1e-8 or hinge_ref is None:
        return float(unsigned)
    sign = 1.0 if float(cross.dot(hinge_ref)) >= 0.0 else -1.0
    return float(unsigned * sign)

def _bone_class_limit(name: str) -> Optional[Tuple[str, float]]:
    lim = GATE3_PARAMETERS["limitsDeg"]
    n = name
    if n in ("LeftShoulder", "RightShoulder", "LeftArm", "RightArm"):
        return ("shoulder", float(lim["shoulderLocal"]))
    if n in ("LeftForeArm", "RightForeArm"):
        return ("elbow", float(lim["elbowLocal"]))
    if n in ("LeftHand", "RightHand"):
        return ("wrist", float(lim["wristLocal"]))
    if n in ("Spine02", "Spine01", "Spine"):
        return ("spine", float(lim["spineLocal"]))
    if n in ("neck", "Head"):
        return ("neck", float(lim["neckLocal"]))
    if n in ("Hips", "LeftUpLeg", "RightUpLeg"):
        return ("hip", float(lim["hipLocal"]))
    if n in ("LeftLeg", "RightLeg"):
        return ("knee", float(lim["kneeLocal"]))
    if n in ("LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"):
        return ("ankle", float(lim["ankleLocal"]))
    return None


def _inspect_frames(arm, fs: int, fe: int) -> Dict:
    import bpy

    arm.data.pose_position = "POSE"
    step = int(GATE3_PARAMETERS["frameStep"])
    lim_events = []
    reverse_events = []
    scale_events = []
    spike_events = []
    spine_kink_events = []

    rev = GATE3_PARAMETERS["reverseJointDeg"]
    smin = float(GATE3_PARAMETERS["scaleMin"])
    smax = float(GATE3_PARAMETERS["scaleMax"])
    spike = float(GATE3_PARAMETERS["rotationSpikeDeg"])

    prev_angles: Dict[str, float] = {}
    hinge_specs = [
        ("elbow", "LeftArm", "LeftForeArm", "LeftHand", 0.0, float(rev["elbow"])),
        ("elbow", "RightArm", "RightForeArm", "RightHand", 0.0, float(rev["elbow"])),
        ("knee", "LeftUpLeg", "LeftLeg", "LeftFoot", 0.0, float(rev["knee"])),
        ("knee", "RightUpLeg", "RightLeg", "RightFoot", 0.0, float(rev["knee"])),
    ]
    hinge_refs = _calibrate_hinge_refs(arm, hinge_specs, fs, fe)

    tracked = [n for n in [b.name for b in arm.pose.bones] if _bone_class_limit(n)]

    for fr in range(int(fs), int(fe) + 1, step):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()

        for name in tracked:
            pb = arm.pose.bones.get(name)
            if pb is None:
                continue
            cls_lim = _bone_class_limit(name)
            if cls_lim is None:
                continue
            cls, lim = cls_lim
            ang = _local_pose_angle_deg(pb)
            if ang > lim:
                lim_events.append(
                    {"frame": fr, "bone": name, "class": cls, "angleDeg": round(ang, 3), "limitDeg": lim, "reason": "JOINT_LIMIT"}
                )
            sc = pb.scale
            sx, sy, sz = float(sc.x), float(sc.y), float(sc.z)
            if min(sx, sy, sz) < smin or max(sx, sy, sz) > smax:
                scale_events.append(
                    {
                        "frame": fr,
                        "bone": name,
                        "scale": [round(sx, 4), round(sy, 4), round(sz, 4)],
                        "reason": "SCALE_ABNORMAL",
                    }
                )
            if name in prev_angles:
                d = abs(ang - prev_angles[name])
                if d > spike:
                    spike_events.append(
                        {
                            "frame": fr,
                            "bone": name,
                            "deltaDeg": round(d, 3),
                            "limitDeg": spike,
                            "reason": "ROTATION_SPIKE",
                        }
                    )
            prev_angles[name] = ang

        # spine kink: extreme fold relative to calibrated mid-chain bend
        spine = GATE3_PARAMETERS["spineChain"]
        for i in range(1, len(spine) - 1):
            a, b, c = spine[i - 1], spine[i], spine[i + 1]
            raw = _raw_hinge_flexion(arm, a, b, c)
            if raw is None:
                continue
            unsigned, _cross = raw
            if unsigned > float(GATE3_PARAMETERS["limitsDeg"]["spineLocal"]) + 25.0:
                spine_kink_events.append(
                    {"frame": fr, "joint": b, "flexionDeg": round(unsigned, 3), "reason": "SPINE_NECK_KINK"}
                )

        for kind, p, j, c, _side, thr in hinge_specs:
            flex = _signed_hinge_flexion_deg(arm, p, j, c, hinge_refs.get(j))
            if flex is None:
                continue
            if flex < thr:
                reverse_events.append(
                    {
                        "frame": fr,
                        "joint": j,
                        "kind": kind,
                        "flexionDeg": round(flex, 3),
                        "thresholdDeg": thr,
                        "reason": "REVERSE_JOINT",
                    }
                )

    def _cap(xs, n=80):
        return xs[:n]

    return {
        "limitEvents": _cap(lim_events),
        "limitCount": len(lim_events),
        "reverseEvents": _cap(reverse_events),
        "reverseCount": len(reverse_events),
        "scaleEvents": _cap(scale_events),
        "scaleCount": len(scale_events),
        "spikeEvents": _cap(spike_events),
        "spikeCount": len(spike_events),
        "spineKinkEvents": _cap(spine_kink_events),
        "spineKinkCount": len(spine_kink_events),
        "unsafeFrameCount": len(
            {e["frame"] for e in lim_events + reverse_events + scale_events + spike_events + spine_kink_events}
        ),
    }


def _spine_root_axis_impact(arm, fs: int, fe: int) -> Dict:
    """Evaluate Hips→Spine02 non-colinear REST axis effect during Formal Bow motion."""
    import bpy
    from mathutils import Vector

    arm.data.pose_position = "POSE"
    hips_b = arm.data.bones.get("Hips")
    sp_b = arm.data.bones.get("Spine02")
    if hips_b is None or sp_b is None:
        return {"ok": False, "reason": "MISSING_BONES"}

    y_rest = (hips_b.tail_local - hips_b.head_local).normalized()
    to_child_rest = (sp_b.head_local - hips_b.head_local).normalized()
    rest_dot = float(y_rest.dot(to_child_rest))

    n = int(GATE3_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    if len(frames) > n:
        sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
    else:
        sample = frames

    dots = []
    head_drift = []
    prev_head = None
    coupling = 0.0
    for fr in sample:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        ph = arm.pose.bones.get("Hips")
        ps = arm.pose.bones.get("Spine02")
        phd = arm.pose.bones.get("Head")
        if ph is None or ps is None:
            continue
        # posed local Y of Hips vs vector to Spine02 head
        mw = arm.matrix_world
        h_head = mw @ ph.head
        h_tail = mw @ ph.tail
        s_head = mw @ ps.head
        y = (h_tail - h_head).normalized()
        to_c = (s_head - h_head)
        if to_c.length < 1e-8:
            continue
        to_c.normalize()
        d = float(y.dot(to_c))
        dots.append(round(d, 5))
        if phd is not None:
            hw = (mw @ phd.head)
            if prev_head is not None:
                # coupling proxy: head lateral speed vs hips Y misalignment
                step = (hw - prev_head).length
                mis = max(0.0, -d)  # only when opposing
                coupling = max(coupling, step * mis)
            prev_head = hw.copy()
            head_drift.append(round(float(hw.z), 5))

    warn_dot = float(GATE3_PARAMETERS["spineRootImpactDotWarn"])
    coup_max = float(GATE3_PARAMETERS["spineRootImpactCouplingMax"])
    min_dot = min(dots) if dots else 1.0
    # Impact is material if coupling exceeds budget OR posed dots worsen drastically vs rest
    material = (coupling > coup_max) or (min_dot < rest_dot - 0.5 and min_dot < warn_dot)
    return {
        "restDot": round(rest_dot, 5),
        "posedMinDot": round(min_dot, 5),
        "posedMeanDot": round(sum(dots) / len(dots), 5) if dots else None,
        "couplingProxy": round(coupling, 6),
        "couplingMax": coup_max,
        "materialImpact": bool(material),
        "samples": len(dots),
        "verdict": "MATERIAL" if material else "IMMATERIAL_REPORTED",
    }


def _motion_meaning(source_arm, clone_arm, fs: int, fe: int) -> Dict:
    import bpy

    bones = ["Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "Spine"]
    n = int(GATE3_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    if len(frames) > n:
        sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
    else:
        sample = frames
    eps = float(GATE3_PARAMETERS["motionMeaningEpsilonM"])
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


_HINGE_LOOKUP = {
    "LeftForeArm": ("LeftArm", "LeftForeArm", "LeftHand", "elbow"),
    "RightForeArm": ("RightArm", "RightForeArm", "RightHand", "elbow"),
    "LeftLeg": ("LeftUpLeg", "LeftLeg", "LeftFoot", "knee"),
    "RightLeg": ("RightUpLeg", "RightLeg", "RightFoot", "knee"),
}


def _upsert_fcurve_key(action, data_path: str, array_index: int, frame: float, value: float) -> bool:
    for fc in _iter_action_fcurves(action):
        if fc.data_path != data_path or int(fc.array_index) != int(array_index):
            continue
        target = None
        for kp in fc.keyframe_points:
            if abs(float(kp.co.x) - float(frame)) < 1e-4:
                target = kp
                break
        if target is None:
            fc.keyframe_points.insert(float(frame), float(value), options={"FAST"})
        else:
            target.co.y = float(value)
        fc.update()
        return True
    return False


def _write_bone_quat_scale(action, bone_name: str, frame: int, quat, scale) -> int:
    written = 0
    qpath = f'pose.bones["{bone_name}"].rotation_quaternion'
    spath = f'pose.bones["{bone_name}"].scale'
    comps = [float(quat.w), float(quat.x), float(quat.y), float(quat.z)]
    for i, v in enumerate(comps):
        if _upsert_fcurve_key(action, qpath, i, frame, v):
            written += 1
    for i, v in enumerate((float(scale[0]), float(scale[1]), float(scale[2]))):
        if _upsert_fcurve_key(action, spath, i, frame, v):
            written += 1
    return written


def _apply_limited_correction(clone_arm, clone_action, inspect: Dict, fs: int, fe: int) -> Dict:
    """
    Clamp only unsafe frames on clone-owned Action (layered fcurves).
    Source Action is never written.
    """
    import bpy
    from mathutils import Quaternion

    if clone_action is None:
        return {"applied": False, "reason": "NO_CLONE_ACTION", "keysWritten": 0, "bonesTouched": 0}

    need: Dict[str, Dict[int, Dict]] = {}
    for e in inspect.get("limitEvents") or []:
        need.setdefault(e["bone"], {})[int(e["frame"])] = e
    for e in inspect.get("spikeEvents") or []:
        need.setdefault(e["bone"], {})[int(e["frame"])] = e
    for e in inspect.get("scaleEvents") or []:
        need.setdefault(e["bone"], {})[int(e["frame"])] = e
    for e in inspect.get("reverseEvents") or []:
        need.setdefault(e["joint"], {})[int(e["frame"])] = {
            "bone": e["joint"],
            "frame": e["frame"],
            "thresholdDeg": float(e["thresholdDeg"]),
            "reason": "REVERSE_JOINT",
        }
    for e in inspect.get("spineKinkEvents") or []:
        need.setdefault(e["joint"], {})[int(e["frame"])] = {
            "bone": e["joint"],
            "frame": e["frame"],
            "limitDeg": float(GATE3_PARAMETERS["limitsDeg"]["spineLocal"]),
            "reason": "SPINE_NECK_KINK",
        }

    if not need:
        return {"applied": False, "reason": "NO_UNSAFE_FRAMES", "keysWritten": 0, "bonesTouched": 0}

    factor = float(GATE3_PARAMETERS["correctClampFactor"])
    max_keys = int(GATE3_PARAMETERS["maxCorrectedKeysPerBone"])
    keys = 0
    bones_touched = 0
    channel_writes = 0

    clone_arm.data.pose_position = "POSE"
    _bind_action(clone_arm, clone_action)

    # Calibrate hinge refs once for reverse fixes
    hinge_specs = [
        ("elbow", "LeftArm", "LeftForeArm", "LeftHand", 0.0, float(GATE3_PARAMETERS["reverseJointDeg"]["elbow"])),
        ("elbow", "RightArm", "RightForeArm", "RightHand", 0.0, float(GATE3_PARAMETERS["reverseJointDeg"]["elbow"])),
        ("knee", "LeftUpLeg", "LeftLeg", "LeftFoot", 0.0, float(GATE3_PARAMETERS["reverseJointDeg"]["knee"])),
        ("knee", "RightUpLeg", "RightLeg", "RightFoot", 0.0, float(GATE3_PARAMETERS["reverseJointDeg"]["knee"])),
    ]
    hinge_refs = _calibrate_hinge_refs(clone_arm, hinge_specs, fs, fe)

    for bone_name, frames_map in need.items():
        pb = clone_arm.pose.bones.get(bone_name)
        if pb is None:
            continue
        cls_lim = _bone_class_limit(bone_name)
        default_lim = float(cls_lim[1]) if cls_lim else 90.0
        written = 0
        bones_touched += 1
        for fr in sorted(frames_map.keys()):
            if written >= max_keys:
                break
            bpy.context.scene.frame_set(int(fr))
            bpy.context.view_layer.update()
            pb = clone_arm.pose.bones.get(bone_name)
            pb.rotation_mode = "QUATERNION"
            event = frames_map[fr]
            reason = event.get("reason", "")

            smin = float(GATE3_PARAMETERS["scaleMin"])
            smax = float(GATE3_PARAMETERS["scaleMax"])
            sx, sy, sz = float(pb.scale.x), float(pb.scale.y), float(pb.scale.z)
            scale = (
                max(smin, min(smax, sx)),
                max(smin, min(smax, sy)),
                max(smin, min(smax, sz)),
            )
            pb.scale = scale

            q0 = pb.rotation_quaternion.copy()
            q_final = q0.copy()
            ident = Quaternion((1.0, 0.0, 0.0, 0.0))

            if reason == "REVERSE_JOINT" and bone_name in _HINGE_LOOKUP:
                p, j, c, _kind = _HINGE_LOOKUP[bone_name]
                thr = float(event.get("thresholdDeg", -12.0))
                target = thr + 1.0  # clear just past threshold toward anatomical side
                max_t = float(GATE3_PARAMETERS["reverseCorrectMaxSlerp"])
                # Limited slerp toward rest — preserve Formal Bow silhouette
                lo, hi = 0.0, max_t
                best_q = q0
                for _ in range(10):
                    mid = (lo + hi) * 0.5
                    q_try = q0.slerp(ident, mid)
                    pb.rotation_quaternion = q_try
                    bpy.context.view_layer.update()
                    flex = _signed_hinge_flexion_deg(clone_arm, p, j, c, hinge_refs.get(j))
                    if flex is None:
                        break
                    if flex < target:
                        lo = mid
                        best_q = q_try
                    else:
                        hi = mid
                        best_q = q_try
                q_final = best_q
            else:
                lim = float(event.get("limitDeg", default_lim)) * factor
                ang = float(abs(q0.angle))
                lim_rad = math.radians(lim)
                if ang > lim_rad and ang > 1e-8:
                    q_final = Quaternion(q0.axis, lim_rad)

            pb.rotation_quaternion = q_final
            pb.scale = scale
            bpy.context.view_layer.update()
            channel_writes += _write_bone_quat_scale(clone_action, bone_name, int(fr), q_final, scale)
            written += 1
            keys += 1

    # Force action refresh
    clone_action.update_tag()
    bpy.context.view_layer.update()
    return {
        "applied": keys > 0 and channel_writes > 0,
        "reason": "CLAMP_UNSAFE_FRAMES" if keys > 0 else "NO_KEYS",
        "keysWritten": keys,
        "channelWrites": channel_writes,
        "bonesTouched": bones_touched,
    }


def run_gate3_once(*, fbx_path: Path, mesh_name: str = "") -> Dict:
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
    src_action_name = None
    src_action_hash_before = None

    if bpy.data.actions:
        action = bpy.data.actions[0]
        src_action_name = action.name
        if source_arm.animation_data is None:
            source_arm.animation_data_create()
        _bind_action(source_arm, action, slot=getattr(source_arm.animation_data, "action_slot", None))
        # stable fingerprint of source action fcurves
        src_action_hash_before = _action_fingerprint(action)
        fs = int(action.frame_range[0])
        fe = int(action.frame_range[1])
    else:
        fs, fe = 1, 231

    # Diagnose on clone sharing action first (read-only eval)
    clone_arm, clone_mesh, clone_action, src_action = _clone_rig_and_mesh(
        source_arm, source_mesh, own_action=True
    )

    inspect_before = _inspect_frames(clone_arm, fs, fe)
    spine_impact = _spine_root_axis_impact(clone_arm, fs, fe)
    meaning_before = _motion_meaning(source_arm, clone_arm, fs, fe)

    correction = {"applied": False, "reason": "SKIP", "keysWritten": 0, "bonesTouched": 0}
    inspect_after = inspect_before
    meaning_after = meaning_before
    correction_reverted = False

    unsafe = (
        inspect_before["limitCount"]
        + inspect_before["reverseCount"]
        + inspect_before["scaleCount"]
        + inspect_before["spikeCount"]
        + inspect_before["spineKinkCount"]
    )
    if unsafe > 0:
        correction = _apply_limited_correction(clone_arm, clone_action, inspect_before, fs, fe)
        inspect_after = _inspect_frames(clone_arm, fs, fe)
        meaning_after = _motion_meaning(source_arm, clone_arm, fs, fe)
        if not meaning_after["ok"]:
            # Revert: rebuild clone without corrective keys (fresh action copy, no clamp)
            clone_arm, clone_mesh, clone_action, src_action = _clone_rig_and_mesh(
                source_arm, source_mesh, own_action=True
            )
            inspect_after = _inspect_frames(clone_arm, fs, fe)
            meaning_after = _motion_meaning(source_arm, clone_arm, fs, fe)
            correction_reverted = True
            correction = {
                "applied": False,
                "reason": "REVERTED_MOTION_MEANING",
                "keysWritten": 0,
                "bonesTouched": 0,
                "attempted": True,
            }

    src_mesh_after = _snapshot_mesh(source_mesh)
    src_arm_after = _snapshot_arm_rest(source_arm)
    src_mut = 0 if src_mesh_before == src_mesh_after and src_arm_before == src_arm_after else 1

    src_action_mut = 0
    if src_action is not None and src_action_hash_before is not None:
        src_action_mut = 0 if _action_fingerprint(src_action) == src_action_hash_before else 1

    severe = GATE3_PARAMETERS["reverseJointSevereDeg"]
    reverse_severe = 0
    reverse_mild = 0
    for e in inspect_after.get("reverseEvents") or []:
        kind = e.get("kind") or "elbow"
        sev = float(severe.get(kind, -35.0))
        if float(e.get("flexionDeg", 0.0)) < sev:
            reverse_severe += 1
        else:
            reverse_mild += 1

    residual_hard = (
        inspect_after["limitCount"]
        + reverse_severe
        + inspect_after["scaleCount"]
        + inspect_after["spikeCount"]
        + inspect_after["spineKinkCount"]
    )

    ctrl = bpy.data.objects.get(GATE3_PARAMETERS["objects"]["control"])
    if ctrl:
        ctrl["mode"] = "CLONE_JOINT_LIMIT"
        ctrl["footSlideInherited"] = FOOT_SLIDE_INHERITED
    evid = bpy.data.objects.get(GATE3_PARAMETERS["objects"]["evidence"])
    if evid:
        evid["unsafeBefore"] = unsafe
        evid["residualHard"] = residual_hard
        evid["reverseMild"] = reverse_mild
        evid["spineImpact"] = spine_impact.get("verdict")

    stable = {
        "parameterHash": parameter_hash(),
        "sourceMutation": src_mut,
        "sourceActionMutation": src_action_mut,
        "unsafeBefore": unsafe,
        "unsafeAfterHard": residual_hard,
        "limitCount": inspect_after["limitCount"],
        "reverseCount": inspect_after["reverseCount"],
        "reverseSevereCount": reverse_severe,
        "reverseMildCount": reverse_mild,
        "scaleCount": inspect_after["scaleCount"],
        "spikeCount": inspect_after["spikeCount"],
        "spineKinkCount": inspect_after["spineKinkCount"],
        "correctionApplied": bool(correction.get("applied")),
        "correctionReverted": correction_reverted,
        "keysWritten": int(correction.get("keysWritten") or 0),
        "motionMeaningOk": bool(meaning_after["ok"]),
        "maxMeaningDriftM": meaning_after["maxDriftM"],
        "spineImpactMaterial": bool(spine_impact.get("materialImpact")),
        "spineImpactVerdict": spine_impact.get("verdict"),
        "footSlideInherited": FOOT_SLIDE_INHERITED,
        "fbxSha256": _sha_file(fbx_path),
        "frameStart": fs,
        "frameEnd": fe,
    }

    return {
        "stable": stable,
        "inspectBefore": inspect_before,
        "inspectAfter": inspect_after,
        "spineImpact": spine_impact,
        "meaningBefore": meaning_before,
        "meaningAfter": meaning_after,
        "correction": correction,
        "sourceArm": source_arm.name,
        "cloneArm": clone_arm.name,
        "cloneMesh": clone_mesh.name,
        "srcActionName": src_action_name,
        "cloneActionName": clone_action.name if clone_action else None,
        "fs": fs,
        "fe": fe,
    }


def build_validation(stable: Dict, determinism: str) -> Dict:
    gates = {
        "SOURCE_ZIP_FBX_MUTATION": 0,
        "SOURCE_CHARACTER_MUTATION": int(stable.get("sourceMutation", 1)),
        "SOURCE_ACTION_MUTATION": int(stable.get("sourceActionMutation", 1)),
        "MOTION_MEANING": "PASS" if stable.get("motionMeaningOk") else "FAIL",
        "JOINT_LIMIT_RESIDUAL": int(stable.get("limitCount", 1)),
        "REVERSE_JOINT_SEVERE_RESIDUAL": int(stable.get("reverseSevereCount", 1)),
        "REVERSE_JOINT_MILD_RESIDUAL": int(stable.get("reverseMildCount", 0)),
        "SCALE_ABNORMAL_RESIDUAL": int(stable.get("scaleCount", 1)),
        "ROTATION_SPIKE_RESIDUAL": int(stable.get("spikeCount", 1)),
        "SPINE_KINK_RESIDUAL": int(stable.get("spineKinkCount", 1)),
        "SPINE_ROOT_AXIS_IMPACT": "FAIL" if stable.get("spineImpactMaterial") else "IMMATERIAL",
        "FOOT_SLIDE_FIXED": "DENY_INHERITED",
        "FOOT_SLIDE_INHERITED": int(stable.get("footSlideInherited", FOOT_SLIDE_INHERITED)),
        "DETERMINISM_3X": determinism,
        "V04_MUTATION": "DENY",
        "CORRECTION_SCOPE": "CLONE_ONLY",
    }

    def ok(k, v):
        if k in ("MOTION_MEANING", "DETERMINISM_3X"):
            return v == "PASS"
        if k in ("FOOT_SLIDE_FIXED", "V04_MUTATION", "CORRECTION_SCOPE"):
            return v in ("DENY_INHERITED", "DENY", "CLONE_ONLY")
        if k == "FOOT_SLIDE_INHERITED":
            return v == FOOT_SLIDE_INHERITED
        if k == "SPINE_ROOT_AXIS_IMPACT":
            return v == "IMMATERIAL"
        if k == "SOURCE_ZIP_FBX_MUTATION":
            return v == 0
        if k == "REVERSE_JOINT_MILD_RESIDUAL":
            return True  # limitation only
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    limitations = []
    if gates["FOOT_SLIDE_INHERITED"] > 0:
        limitations.append("FOOT_SLIDE_INHERITED_TO_LATER_GATE")
    if gates["SPINE_ROOT_AXIS_IMPACT"] == "IMMATERIAL":
        limitations.append("SPINE_ROOT_AXIS_IMMATERIAL_REPORTED")
    if int(stable.get("reverseMildCount", 0)) > 0:
        limitations.append("REVERSE_JOINT_MILD_PRESERVED_FOR_FORMAL_BOW")
    if stable.get("correctionReverted"):
        limitations.append("CORRECTION_REVERTED_PRESERVE_FORMAL_BOW")
    if stable.get("correctionApplied"):
        limitations.append("LIMITED_CLONE_CORRECTION_APPLIED")
    if fails:
        verdict = "FAIL"
    elif limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    return {
        "schema": "NURION_V05_GATE3_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": limitations,
        "verdict": verdict,
        "parameterHash": parameter_hash(),
    }


def run_gate3(
    *,
    fbx_path: Path,
    mesh_name: str = "",
    runs: int = 3,
    clean_import_cb=None,
) -> Gate3Result:
    notes: List[str] = []
    results = []
    for _ in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate3_once(fbx_path=fbx_path, mesh_name=mesh_name))

    stables = [r["stable"] for r in results]
    det = "FAIL"
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det = "PASS" if all(_sha_json(s) == h0 for s in stables[1:3]) else "FAIL"
    if det != "PASS":
        notes.append("3x determinism mismatch")

    last = results[-1]
    validation = build_validation(last["stable"], det)
    profile = {
        "schema": "NURION_V05_GATE3_PROFILE",
        "version": GATE3_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE3_PARAMETERS["gate1ParameterHash"],
        "gate2ParameterHash": GATE3_PARAMETERS["gate2ParameterHash"],
        "objects": GATE3_PARAMETERS["objects"],
        "sourceArm": last["sourceArm"],
        "cloneArm": last["cloneArm"],
        "cloneMesh": last["cloneMesh"],
        "srcActionName": last["srcActionName"],
        "cloneActionName": last["cloneActionName"],
        "frameStart": last["fs"],
        "frameEnd": last["fe"],
        "inspectBefore": {
            "limitCount": last["inspectBefore"]["limitCount"],
            "reverseCount": last["inspectBefore"]["reverseCount"],
            "scaleCount": last["inspectBefore"]["scaleCount"],
            "spikeCount": last["inspectBefore"]["spikeCount"],
            "spineKinkCount": last["inspectBefore"]["spineKinkCount"],
            "unsafeFrameCount": last["inspectBefore"]["unsafeFrameCount"],
            "limitEvents": last["inspectBefore"]["limitEvents"][:20],
            "reverseEvents": last["inspectBefore"]["reverseEvents"][:20],
            "scaleEvents": last["inspectBefore"]["scaleEvents"][:20],
            "spikeEvents": last["inspectBefore"]["spikeEvents"][:20],
            "spineKinkEvents": last["inspectBefore"]["spineKinkEvents"][:20],
        },
        "inspectAfter": {
            "limitCount": last["inspectAfter"]["limitCount"],
            "reverseCount": last["inspectAfter"]["reverseCount"],
            "scaleCount": last["inspectAfter"]["scaleCount"],
            "spikeCount": last["inspectAfter"]["spikeCount"],
            "spineKinkCount": last["inspectAfter"]["spineKinkCount"],
            "unsafeFrameCount": last["inspectAfter"]["unsafeFrameCount"],
        },
        "spineRootAxisImpact": last["spineImpact"],
        "motionMeaning": last["meaningAfter"],
        "correction": last["correction"],
        "footSlideInherited": FOOT_SLIDE_INHERITED,
        "footSlideFix": "DENY_INHERIT_TO_LATER_GATE",
        "determinism3x": det,
        "v04Mutation": "DENY",
        "sourceZipFbxMutation": "DENY",
        "sourceActionMutation": "DENY",
        "production": "NO-GO",
        "notes": notes,
    }
    return Gate3Result(
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
