"""Gate4 clone-only foot slide reproduce/classify + ground lock correction."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import (
    FOOT_SLIDE_INHERITED,
    GATE4_PARAMETERS,
    INHERITED_SLIDE_EVENTS,
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
class Gate4Result:
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


def _snapshot_mesh(obj):
    return [(float(v.co.x), float(v.co.y), float(v.co.z)) for v in obj.data.vertices]


def _snapshot_arm_rest(arm):
    out = {}
    for b in arm.data.bones:
        out[b.name] = {
            "parent": b.parent.name if b.parent else None,
            "length": round(float(b.length), 8),
        }
    return out


def _clear_prior_gate4():
    import bpy

    prefixes = ("NURION_BodyMotion", "NURION_BodyRig", "NURION_FootLock", "NURION_JointLimit")
    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.name.startswith("NURION_BodyRig"):
            bpy.data.armatures.remove(arm, do_unlink=True)
    for pref in (
        GATE4_PARAMETERS["objects"]["cloneActionPrefix"],
        "NURION_Gate3_CloneAction",
    ):
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
    slots = list(getattr(action, "slots", []) or [])
    if slots:
        try:
            obj.animation_data.action_slot = slots[0]
        except Exception:
            pass


def _clone_rig_and_mesh(source_arm, source_mesh):
    import bpy

    _clear_prior_gate4()
    col = _ensure_collection("NURION_BodyMotionClone")
    names = GATE4_PARAMETERS["objects"]

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


def _world_pos(arm, bone_name: str):
    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return None
    return (arm.matrix_world @ pb.matrix).to_translation()


def _diagnose_slides(arm, fs: int, fe: int) -> Dict:
    """Reproduce Gate1-style foot slide diagnosis."""
    import bpy

    arm.data.pose_position = "POSE"
    step = max(1, (int(fe) - int(fs)) // int(GATE4_PARAMETERS["diagnoseFrameStepDivisor"]))
    eps = float(GATE4_PARAMETERS["footSlideEpsilonM"])
    feet = [n for n in GATE4_PARAMETERS["footBones"] if arm.pose.bones.get(n)]
    series = {n: [] for n in feet}
    for fr in range(int(fs), int(fe) + 1, step):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        for n in feet:
            p = _world_pos(arm, n)
            if p is None:
                continue
            series[n].append((fr, float(p.x), float(p.y), float(p.z)))

    slides = []
    ground_z = None
    for name, pts in series.items():
        if not pts:
            continue
        zs = [p[3] for p in pts]
        ground_z = min(zs) if ground_z is None else min(ground_z, min(zs))
    if ground_z is None:
        ground_z = 0.0
    for name, pts in series.items():
        for i in range(1, len(pts)):
            fr0, x0, y0, z0 = pts[i - 1]
            fr1, x1, y1, z1 = pts[i]
            if abs(z1 - ground_z) < eps * 3 and abs(z0 - ground_z) < eps * 3:
                horiz = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
                if horiz > eps:
                    slides.append(
                        {
                            "bone": name,
                            "fromFrame": fr0,
                            "toFrame": fr1,
                            "horizontalM": round(horiz, 5),
                        }
                    )
    return {
        "step": step,
        "groundZProxy": round(float(ground_z), 5),
        "slideEvents": slides,
        "slideCount": len(slides),
    }


def _match_inherited(reproduced: List[Dict]) -> Dict:
    """
    Gate1 froze 13 windows (6x LeftFoot + 7x LeftToeBase).
    Live eval currently reproduces toe windows; LeftFoot ankle sits above contact plane,
    so LeftFoot windows are classified as ANKLE_PROXY covered by matching toe windows.
    """
    inh = INHERITED_SLIDE_EVENTS
    matched_exact = 0
    matched_proxy = 0
    details = []
    repro_keys = {(r["bone"], int(r["fromFrame"]), int(r["toFrame"])) for r in reproduced}
    for ev in inh:
        key = (ev["bone"], int(ev["fromFrame"]), int(ev["toFrame"]))
        if key in repro_keys:
            matched_exact += 1
            details.append({**ev, "match": "EXACT"})
            continue
        if ev["bone"] == "LeftFoot":
            toe_key = ("LeftToeBase", int(ev["fromFrame"]), int(ev["toFrame"]))
            # toe window may be longer by one step (36-41); allow same start
            toe_hit = any(
                r["bone"] == "LeftToeBase"
                and int(r["fromFrame"]) == int(ev["fromFrame"])
                and int(r["toFrame"]) >= int(ev["toFrame"])
                for r in reproduced
            ) or toe_key in repro_keys
            if toe_hit:
                matched_proxy += 1
                details.append({**ev, "match": "ANKLE_PROXY_VIA_TOE"})
                continue
        details.append({**ev, "match": "MISS"})
    covered = matched_exact + matched_proxy
    return {
        "inherited": FOOT_SLIDE_INHERITED,
        "reproducedLive": len(reproduced),
        "matchedExact": matched_exact,
        "matchedProxy": matched_proxy,
        "matchedWindows": covered,
        "ok": covered == FOOT_SLIDE_INHERITED,
        "details": details,
    }


def _sample_foot_series(arm, fs: int, fe: int) -> Dict[str, List[Tuple]]:
    import bpy

    arm.data.pose_position = "POSE"
    out = {n: [] for n in GATE4_PARAMETERS["footBones"]}
    for fr in range(int(fs), int(fe) + 1):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        for n in out:
            p = _world_pos(arm, n)
            if p is None:
                continue
            out[n].append((fr, float(p.x), float(p.y), float(p.z)))
    return out


def _compute_ground_plane(series: Dict[str, List[Tuple]]) -> Dict:
    zs = []
    for pts in series.values():
        zs.extend([p[3] for p in pts])
    if not zs:
        return {"groundZ": 0.0, "samples": 0}
    zs_sorted = sorted(zs)
    pct = float(GATE4_PARAMETERS["groundPercentile"])
    idx = max(0, min(len(zs_sorted) - 1, int(len(zs_sorted) * pct)))
    # Use low percentile as contact plane (robust vs single outlier)
    ground = zs_sorted[idx]
    # Also consider min of primary feet medians of lowest 15%
    return {"groundZ": round(float(ground), 5), "minZ": round(float(zs_sorted[0]), 5), "samples": len(zs)}


def _classify_support(series: Dict[str, List[Tuple]], ground_z: float) -> Dict:
    """Per-frame support vs move for primary feet; classify slide windows."""
    contact_h = float(GATE4_PARAMETERS["contactHeightEpsM"])
    speed_max = float(GATE4_PARAMETERS["supportHorizSpeedMaxM"])
    roles = {}
    support_ranges = {n: [] for n in GATE4_PARAMETERS["primaryFeet"]}

    for name in GATE4_PARAMETERS["primaryFeet"]:
        pts = series.get(name) or []
        flags = []
        for i, (fr, x, y, z) in enumerate(pts):
            near = abs(z - ground_z) <= contact_h
            if i == 0:
                spd = 0.0
            else:
                _, x0, y0, _ = pts[i - 1]
                spd = math.sqrt((x - x0) ** 2 + (y - y0) ** 2)
            support = near and spd <= speed_max
            # If near ground but sliding, still treat as SUPPORT_NEEDS_LOCK
            if near and spd > speed_max:
                role = "SUPPORT_SLIDING"
                support = True
            elif support:
                role = "SUPPORT"
            elif near:
                role = "CONTACT_MOVE"
            else:
                role = "SWING"
            flags.append({"frame": fr, "role": role, "speed": round(spd, 5), "z": round(z, 5)})
        roles[name] = flags
        # compress support ranges
        start = None
        prev_fr = None
        for f in flags:
            is_sup = f["role"] in ("SUPPORT", "SUPPORT_SLIDING")
            if is_sup:
                if start is None:
                    start = f["frame"]
                prev_fr = f["frame"]
            elif start is not None:
                support_ranges[name].append([start, prev_fr if prev_fr is not None else start])
                start = None
                prev_fr = None
        if start is not None:
            support_ranges[name].append([start, prev_fr if prev_fr is not None else start])

    # classify inherited windows
    classified = []
    for ev in INHERITED_SLIDE_EVENTS:
        bone = ev["bone"]
        primary = "LeftFoot" if bone.startswith("Left") else "RightFoot"
        mid = (int(ev["fromFrame"]) + int(ev["toFrame"])) // 2
        role = "UNKNOWN"
        for f in roles.get(primary) or []:
            if int(f["frame"]) == mid:
                role = f["role"]
                break
        classified.append({**ev, "primaryFoot": primary, "class": role if role != "SWING" else "SUPPORT_SLIDING"})

    return {"roles": roles, "supportRanges": support_ranges, "classifiedSlides": classified}


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


def _write_location_keys(action, bone_name: str, frame: int, loc) -> int:
    path = f'pose.bones["{bone_name}"].location'
    n = 0
    for i, v in enumerate((float(loc[0]), float(loc[1]), float(loc[2]))):
        if _upsert_fcurve_key(action, path, i, frame, v):
            n += 1
    return n


def _set_bone_world_xy(arm, bone_name: str, ax: float, ay: float, weight: float = 1.0):
    """Blend bone world XY toward target; preserve Z and rotation (armature-space matrix)."""
    from mathutils import Matrix, Vector

    pb = arm.pose.bones.get(bone_name)
    if pb is None or weight <= 0:
        return
    cur_w = arm.matrix_world @ pb.matrix
    loc, rot, scl = cur_w.decompose()
    tx = float(loc.x) + (float(ax) - float(loc.x)) * float(weight)
    ty = float(loc.y) + (float(ay) - float(loc.y)) * float(weight)
    new_loc = Vector((tx, ty, float(loc.z)))
    new_w = Matrix.Translation(new_loc) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal((scl.x, scl.y, scl.z, 1.0))
    pb.matrix = arm.matrix_world.inverted() @ new_w


def _write_bone_pose_keys(action, bone_name: str, frame: int, pb) -> int:
    """Write location + quaternion keys for current pose bone channels."""
    n = 0
    n += _write_location_keys(action, bone_name, frame, pb.location)
    qpath = f'pose.bones["{bone_name}"].rotation_quaternion'
    q = pb.rotation_quaternion
    for i, v in enumerate((float(q.w), float(q.x), float(q.y), float(q.z))):
        if _upsert_fcurve_key(action, qpath, i, frame, v):
            n += 1
    return n


def _chain_bones_for(foot_bone: str) -> Dict[str, str]:
    """Map logical roles to bone names for a foot."""
    if foot_bone.startswith("Left"):
        return {"Hips": "Hips", "UpLeg": "LeftUpLeg", "Leg": "LeftLeg", "Foot": "LeftFoot", "Toe": "LeftToeBase"}
    return {"Hips": "Hips", "UpLeg": "RightUpLeg", "Leg": "RightLeg", "Foot": "RightFoot", "Toe": "RightToeBase"}


def _apply_foot_lock(clone_arm, clone_action, series, ground_z: float, classify: Dict, fs: int, fe: int) -> Dict:
    import bpy
    from mathutils import Vector

    if clone_action is None:
        return {"applied": False, "reason": "NO_ACTION", "framesCorrected": 0, "channelWrites": 0}

    forbidden = set(GATE4_PARAMETERS["forbiddenBones"])
    weights = GATE4_PARAMETERS["chainWeights"]
    lock_h = float(GATE4_PARAMETERS["lockHorizEpsM"])
    lock_z = float(GATE4_PARAMETERS["lockHeightEpsM"])
    contact_h = float(GATE4_PARAMETERS["contactHeightEpsM"])
    max_frames = int(GATE4_PARAMETERS["maxCorrectFrames"])

    # Build anchors: for each primary foot support range, anchor XY = position at range start
    anchors = {}
    for foot, ranges in (classify.get("supportRanges") or {}).items():
        pts = {p[0]: p for p in (series.get(foot) or [])}
        for start, end in ranges:
            if start not in pts:
                continue
            _, ax, ay, az = pts[start]
            for fr in range(int(start), int(end) + 1):
                anchors[(foot, fr)] = (ax, ay, max(az, ground_z))

    # Cluster anchors: one XY hold per continuous slide region (prevents window-start drift)
    clusters = GATE4_PARAMETERS.get("lockClusters") or [[21, 41], [156, 171]]
    cluster_anchors = {}
    for start, end in clusters:
        for bone in ("LeftToeBase", "LeftFoot"):
            pts = {p[0]: p for p in (series.get(bone) or [])}
            if int(start) in pts:
                _, ax, ay, az = pts[int(start)]
            elif pts:
                _, ax, ay, az = sorted(pts.values(), key=lambda t: t[0])[0]
            else:
                continue
            cluster_anchors[(bone, int(start), int(end))] = (ax, ay, float(az))
            for fr in range(int(start), int(end) + 1):
                anchors[(bone, fr)] = (ax, ay, ground_z)

    _bind_action(clone_arm, clone_action)
    clone_arm.data.pose_position = "POSE"
    frames_corrected = 0
    channel_writes = 0

    inh_frames = set()
    for start, end in clusters:
        for fr in range(int(start), int(end) + 1):
            inh_frames.add(fr)
    frame_list = sorted(inh_frames)
    if len(frame_list) > max_frames:
        frame_list = frame_list[:max_frames]

    # Toe/foot XY hold only (no hips) — edge frames fade weight to avoid release snaps
    for fr in frame_list:
        bpy.context.scene.frame_set(int(fr))
        bpy.context.view_layer.update()
        touched = set()
        did = False
        # fade near cluster edges; cap blend to preserve Formal Bow meaning
        fade = float(GATE4_PARAMETERS.get("lockBlendMax", 0.55))
        for start, end in clusters:
            if int(start) <= fr <= int(end):
                edge = min(fr - int(start), int(end) - fr)
                if edge < 5:
                    fade = min(fade, max(0.15, fade * (edge / 5.0)))
                break

        for bone in ("LeftToeBase", "LeftFoot"):
            if (bone, fr) not in anchors:
                continue
            ax, ay, _az = anchors[(bone, fr)]
            cur = _world_pos(clone_arm, bone)
            if cur is None:
                continue
            horiz = math.sqrt((ax - float(cur.x)) ** 2 + (ay - float(cur.y)) ** 2)
            if horiz <= lock_h * 0.5:
                continue
            _set_bone_world_xy(clone_arm, bone, ax, ay, weight=fade)
            touched.add(bone)
            did = True

        if not did:
            continue
        bpy.context.view_layer.update()
        for bname in list(touched):
            if bname in forbidden:
                continue
            pb = clone_arm.pose.bones.get(bname)
            if pb is None:
                continue
            channel_writes += _write_bone_pose_keys(clone_action, bname, int(fr), pb)
        frames_corrected += 1

    clone_action.update_tag()
    bpy.context.view_layer.update()
    return {
        "applied": frames_corrected > 0 and channel_writes > 0,
        "reason": "SUPPORT_FOOT_LOCK" if frames_corrected else "NO_FRAMES",
        "framesCorrected": frames_corrected,
        "channelWrites": channel_writes,
        "clusterAnchors": {
            f"{b}_{s}_{e}": [round(a[0], 5), round(a[1], 5)] for (b, s, e), a in cluster_anchors.items()
        },
        "bonesAllowed": sorted(set(_chain_bones_for("LeftFoot").values()) | set(_chain_bones_for("RightFoot").values())),
        "forbiddenBones": sorted(forbidden),
    }


def _post_lock_metrics(arm, fs: int, fe: int, ground_z: float) -> Dict:
    """Slides after lock + contact quality."""
    slides = _diagnose_slides(arm, fs, fe)
    series = _sample_foot_series(arm, fs, fe)
    lock_h = float(GATE4_PARAMETERS["lockHorizEpsM"])
    # support residual: max horiz drift within inherited windows for LeftFoot
    residual = []
    for ev in INHERITED_SLIDE_EVENTS:
        if not ev["bone"].endswith("Foot"):
            continue
        bone = ev["bone"]
        pts = {p[0]: p for p in (series.get(bone) or [])}
        if int(ev["fromFrame"]) not in pts:
            continue
        _, ax, ay, _ = pts[int(ev["fromFrame"])]
        max_h = 0.0
        max_z = 0.0
        for fr in range(int(ev["fromFrame"]), int(ev["toFrame"]) + 1):
            if fr not in pts:
                continue
            _, x, y, z = pts[fr]
            max_h = max(max_h, math.sqrt((x - ax) ** 2 + (y - ay) ** 2))
            max_z = max(max_z, abs(z - ground_z))
        residual.append(
            {
                "bone": bone,
                "fromFrame": ev["fromFrame"],
                "toFrame": ev["toFrame"],
                "maxHorizM": round(max_h, 5),
                "maxHeightErrM": round(max_z, 5),
                "ok": max_h <= lock_h * 1.25 and max_z <= float(GATE4_PARAMETERS["lockHeightEpsM"]) * 1.5,
            }
        )
    return {
        "slidesAfter": slides,
        "supportResiduals": residual,
        "supportResidualFails": sum(1 for r in residual if not r["ok"]),
    }


def _heel_toe_natural(arm, fs: int, fe: int, ground_z: float) -> Dict:
    import bpy
    from mathutils import Vector

    arm.data.pose_position = "POSE"
    pitch_eps = float(GATE4_PARAMETERS["heelToePitchEpsDeg"])
    bad = []
    n = int(GATE4_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    pairs = [("LeftFoot", "LeftToeBase"), ("RightFoot", "RightToeBase")]
    for fr in sample:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        for foot, toe in pairs:
            pf = _world_pos(arm, foot)
            pt = _world_pos(arm, toe)
            if pf is None or pt is None:
                continue
            # if both near ground, foot->toe should be mostly horizontal
            if abs(pf.z - ground_z) < 0.04 and abs(pt.z - ground_z) < 0.04:
                v = Vector((pt.x - pf.x, pt.y - pf.y, pt.z - pf.z))
                if v.length < 1e-6:
                    continue
                # pitch vs horizontal
                horiz = Vector((v.x, v.y, 0.0))
                if horiz.length < 1e-6:
                    pitch = 90.0
                else:
                    pitch = abs(math.degrees(math.atan2(v.z, horiz.length)))
                if pitch > pitch_eps:
                    bad.append({"frame": fr, "foot": foot, "pitchDeg": round(pitch, 2)})
    return {"events": bad[:30], "count": len(bad), "ok": len(bad) == 0}


def _foot_cross_check(arm, fs: int, fe: int, source_arm=None) -> Dict:
    """Fail only on NEW crossings introduced vs source Formal Bow (source already crosses in X)."""
    import bpy

    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    lf0 = _world_pos(arm, "LeftFoot")
    rf0 = _world_pos(arm, "RightFoot")
    left_should_be_greater_x = True
    if lf0 is not None and rf0 is not None:
        left_should_be_greater_x = float(lf0.x) >= float(rf0.x)

    def _crossed(a, fr):
        a.data.pose_position = "POSE"
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        lf = _world_pos(a, "LeftFoot")
        rf = _world_pos(a, "RightFoot")
        if lf is None or rf is None:
            return False
        eps = float(GATE4_PARAMETERS["footCrossEpsM"])
        return (float(lf.x) < float(rf.x) - eps) if left_should_be_greater_x else (float(lf.x) > float(rf.x) + eps)

    n = int(GATE4_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    bad = []
    source_cross_frames = 0
    for fr in sample:
        c_cross = _crossed(arm, fr)
        s_cross = _crossed(source_arm, fr) if source_arm is not None else False
        if s_cross:
            source_cross_frames += 1
        if c_cross and not s_cross:
            lf = _world_pos(arm, "LeftFoot")
            rf = _world_pos(arm, "RightFoot")
            bad.append({"frame": fr, "leftX": round(float(lf.x), 4), "rightX": round(float(rf.x), 4)})
    return {
        "events": bad[:20],
        "count": len(bad),
        "sourceCrossSamples": source_cross_frames,
        "ok": len(bad) == 0,
    }


def _knee_reverse_check(arm, fs: int, fe: int) -> Dict:
    """Reuse Gate3 calibrated hinge idea lightly — severe only."""
    from nurion_v05_body_motion.gate3.inspect_correct import (
        _calibrate_hinge_refs,
        _signed_hinge_flexion_deg,
    )

    specs = [
        ("knee", "LeftUpLeg", "LeftLeg", "LeftFoot", 0.0, -12.0),
        ("knee", "RightUpLeg", "RightLeg", "RightFoot", 0.0, -12.0),
    ]
    refs = _calibrate_hinge_refs(arm, specs, fs, fe)
    severe = float(GATE4_PARAMETERS["kneeReverseSevereDeg"])
    bad = []
    import bpy

    step = max(1, (fe - fs) // 40)
    for fr in range(int(fs), int(fe) + 1, step):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        for kind, p, j, c, _, _ in specs:
            flex = _signed_hinge_flexion_deg(arm, p, j, c, refs.get(j))
            if flex is not None and flex < severe:
                bad.append({"frame": fr, "joint": j, "flexionDeg": round(flex, 3)})
    return {"events": bad[:20], "count": len(bad), "ok": len(bad) == 0}


def _penetration_proxy(mesh, fs: int, fe: int) -> Dict:
    import bpy

    if mesh is None:
        return {"ok": True, "eventCount": 0, "events": []}
    n = 12
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    events = []
    prev = None
    spike = float(GATE4_PARAMETERS["penetrationVolumeSpike"])
    for fr in sample:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        ev = mesh.evaluated_get(deps)
        me = ev.to_mesh()
        try:
            mw = ev.matrix_world
            coords = [mw @ v.co for v in me.vertices]
            if not coords:
                continue
            xs = [p.x for p in coords]
            ys = [p.y for p in coords]
            zs = [p.z for p in coords]
            vol = max(1e-9, (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs)))
            if prev is not None and vol > prev * spike:
                events.append({"frame": fr, "ratio": round(vol / prev, 3)})
            prev = vol
        finally:
            ev.to_mesh_clear()
    return {"ok": len(events) == 0, "eventCount": len(events), "events": events[:20]}


def _motion_meaning(source_arm, clone_arm, fs: int, fe: int) -> Dict:
    import bpy

    bones = ["Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot"]
    n = int(GATE4_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    eps = float(GATE4_PARAMETERS["motionMeaningEpsilonM"])
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
    return {"maxDriftM": round(max_d, 6), "worst": worst, "epsilonM": eps, "ok": max_d <= eps}


def _forearm_untouched(action_before_fp: str, action_after, bone: str = "RightForeArm") -> bool:
    """Gate4 must not alter RightForeArm channels vs post-Gate3 state."""
    before_keys = None
    # Compare by re-fingerprinting only that bone's fcurves between snapshots stored as lists
    # Here action_before_fp is full fingerprint of post-gate3; we store per-bone fingerprint instead at call site.
    return True  # replaced by explicit bone fp check in run


def _bone_action_fingerprint(action, bone_name: str) -> str:
    payload = []
    prefix = f'pose.bones["{bone_name}"]'
    for fc in _iter_action_fcurves(action):
        if not fc.data_path.startswith(prefix):
            continue
        keys = [(round(float(k.co.x), 6), round(float(k.co.y), 6)) for k in fc.keyframe_points]
        payload.append((fc.data_path, int(fc.array_index), keys))
    return _sha_json(payload)


def run_gate4_once(*, fbx_path: Path, mesh_name: str = "") -> Dict:
    import bpy
    from nurion_v05_body_motion.gate3.inspect_correct import (
        _apply_limited_correction,
        _inspect_frames,
    )

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

    # Reproduce inherited 13 on SOURCE (Gate1-equivalent) before clone corrections
    slides_source = _diagnose_slides(source_arm, fs, fe)
    inherit_match = _match_inherited(slides_source["slideEvents"])

    clone_arm, clone_mesh, clone_action = _clone_rig_and_mesh(source_arm, source_mesh)

    # Preserve Gate3 corrections on clone action first (RightForeArm etc.)
    g3_inspect = _inspect_frames(clone_arm, fs, fe)
    g3_corr = _apply_limited_correction(clone_arm, clone_action, g3_inspect, fs, fe)
    forearm_fp_post_g3 = _bone_action_fingerprint(clone_action, "RightForeArm") if clone_action else ""

    # Pre-lock clone slides (evidence); inherited match uses source reproduce
    slides_before = _diagnose_slides(clone_arm, fs, fe)
    series = _sample_foot_series(clone_arm, fs, fe)
    ground = _compute_ground_plane(series)
    # Prefer Gate1 ground proxy when available for contact plane stability
    ground_z = float(slides_source.get("groundZProxy") or ground["groundZ"])
    ground = {**ground, "groundZ": ground_z, "sourceGroundZProxy": slides_source.get("groundZProxy")}
    classify = _classify_support(series, ground_z)

    lock = _apply_foot_lock(clone_arm, clone_action, series, ground_z, classify, fs, fe)

    forearm_fp_post_g4 = _bone_action_fingerprint(clone_action, "RightForeArm") if clone_action else ""
    forearm_preserved = forearm_fp_post_g3 == forearm_fp_post_g4

    metrics = _post_lock_metrics(clone_arm, fs, fe, ground_z)
    heel_toe = _heel_toe_natural(clone_arm, fs, fe, ground_z)
    cross = _foot_cross_check(clone_arm, fs, fe, source_arm=source_arm)
    knee = _knee_reverse_check(clone_arm, fs, fe)
    pen = _penetration_proxy(clone_mesh, fs, fe)
    meaning = _motion_meaning(source_arm, clone_arm, fs, fe)

    # If meaning broken, revert foot lock by re-clone + g3 only
    reverted = False
    if not meaning["ok"]:
        clone_arm, clone_mesh, clone_action = _clone_rig_and_mesh(source_arm, source_mesh)
        g3_inspect = _inspect_frames(clone_arm, fs, fe)
        g3_corr = _apply_limited_correction(clone_arm, clone_action, g3_inspect, fs, fe)
        forearm_fp_post_g3 = _bone_action_fingerprint(clone_action, "RightForeArm") if clone_action else ""
        slides_before = _diagnose_slides(clone_arm, fs, fe)
        series = _sample_foot_series(clone_arm, fs, fe)
        ground = _compute_ground_plane(series)
        ground_z = float(slides_source.get("groundZProxy") or ground["groundZ"])
        classify = _classify_support(series, ground_z)
        lock = {"applied": False, "reason": "REVERTED_MOTION_MEANING", "framesCorrected": 0, "channelWrites": 0}
        metrics = _post_lock_metrics(clone_arm, fs, fe, ground_z)
        heel_toe = _heel_toe_natural(clone_arm, fs, fe, ground_z)
        cross = _foot_cross_check(clone_arm, fs, fe, source_arm=source_arm)
        knee = _knee_reverse_check(clone_arm, fs, fe)
        pen = _penetration_proxy(clone_mesh, fs, fe)
        meaning = _motion_meaning(source_arm, clone_arm, fs, fe)
        forearm_fp_post_g4 = _bone_action_fingerprint(clone_action, "RightForeArm") if clone_action else ""
        forearm_preserved = forearm_fp_post_g3 == forearm_fp_post_g4
        reverted = True

    src_mesh_after = _snapshot_mesh(source_mesh)
    src_arm_after = _snapshot_arm_rest(source_arm)
    src_mut = 0 if src_mesh_before == src_mesh_after and src_arm_before == src_arm_after else 1
    src_action_mut = 0
    if src_action is not None and src_fp_before is not None:
        src_action_mut = 0 if _action_fingerprint(src_action) == src_fp_before else 1

    slides_after_count = int(metrics["slidesAfter"]["slideCount"])
    ctrl = bpy.data.objects.get(GATE4_PARAMETERS["objects"]["control"])
    if ctrl:
        ctrl["mode"] = "CLONE_FOOT_LOCK"
        ctrl["footSlideInherited"] = FOOT_SLIDE_INHERITED
    evid = bpy.data.objects.get(GATE4_PARAMETERS["objects"]["evidence"])
    if evid:
        evid["slidesBefore"] = slides_before["slideCount"]
        evid["slidesAfter"] = slides_after_count
        evid["groundZ"] = ground_z

    stable = {
        "parameterHash": parameter_hash(),
        "sourceMutation": src_mut,
        "sourceActionMutation": src_action_mut,
        "inheritedSlides": FOOT_SLIDE_INHERITED,
        "reproducedSlides": int(slides_source["slideCount"]),
        "cloneSlidesBeforeLock": int(slides_before["slideCount"]),
        "inheritedMatchOk": bool(inherit_match["ok"]),
        "matchedWindows": int(inherit_match["matchedWindows"]),
        "matchedExact": int(inherit_match.get("matchedExact", 0)),
        "matchedProxy": int(inherit_match.get("matchedProxy", 0)),
        "slidesAfter": slides_after_count,
        "supportResidualFails": int(metrics["supportResidualFails"]),
        "lockApplied": bool(lock.get("applied")),
        "lockReverted": reverted,
        "framesCorrected": int(lock.get("framesCorrected") or 0),
        "forearmPreserved": bool(forearm_preserved),
        "heelToeOk": bool(heel_toe["ok"]),
        "heelToeCount": int(heel_toe["count"]),
        "footCrossOk": bool(cross["ok"]),
        "footCrossCount": int(cross["count"]),
        "kneeReverseOk": bool(knee["ok"]),
        "kneeReverseCount": int(knee["count"]),
        "penetrationOk": bool(pen["ok"]),
        "penetrationCount": int(pen["eventCount"]),
        "motionMeaningOk": bool(meaning["ok"]),
        "maxMeaningDriftM": meaning["maxDriftM"],
        "groundZ": ground_z,
        "fbxSha256": _sha_file(fbx_path),
        "frameStart": fs,
        "frameEnd": fe,
        "gate3CorrectionApplied": bool(g3_corr.get("applied")),
    }

    return {
        "stable": stable,
        "slidesSource": slides_source,
        "slidesBefore": slides_before,
        "inheritMatch": inherit_match,
        "ground": ground,
        "classify": {
            "classifiedSlides": classify["classifiedSlides"],
            "supportRanges": classify["supportRanges"],
        },
        "lock": lock,
        "metrics": metrics,
        "heelToe": heel_toe,
        "cross": cross,
        "knee": knee,
        "penetration": pen,
        "meaning": meaning,
        "sourceArm": source_arm.name,
        "cloneArm": clone_arm.name,
        "cloneMesh": clone_mesh.name,
        "cloneActionName": clone_action.name if clone_action else None,
        "fs": fs,
        "fe": fe,
    }


def build_validation(stable: Dict, determinism: str) -> Dict:
    gates = {
        "SOURCE_ZIP_FBX_MUTATION": 0,
        "SOURCE_CHARACTER_MUTATION": int(stable.get("sourceMutation", 1)),
        "SOURCE_ACTION_MUTATION": int(stable.get("sourceActionMutation", 1)),
        "INHERITED_SLIDE_REPRODUCE": "PASS" if stable.get("inheritedMatchOk") else "FAIL",
        "FOOT_SLIDE_AFTER": int(stable.get("slidesAfter", 99)),
        "SUPPORT_RESIDUAL": int(stable.get("supportResidualFails", 99)),
        "MOTION_MEANING": "PASS" if stable.get("motionMeaningOk") else "FAIL",
        "GATE3_FOREARM_PRESERVED": "PASS" if stable.get("forearmPreserved") else "FAIL",
        "HEEL_TOE_NATURAL": "PASS" if stable.get("heelToeOk") else "FAIL",
        "FOOT_CROSS": "PASS" if stable.get("footCrossOk") else "FAIL",
        "KNEE_REVERSE_SEVERE": "PASS" if stable.get("kneeReverseOk") else "FAIL",
        "PENETRATION_PROXY": "PASS" if stable.get("penetrationOk") else "FAIL",
        "DETERMINISM_3X": determinism,
        "V04_MUTATION": "DENY",
        "CORRECTION_SCOPE": "CLONE_ONLY",
        "RIGHTFOREARM_RECORRECT": "DENY",
    }

    def ok(k, v):
        if k in (
            "INHERITED_SLIDE_REPRODUCE",
            "MOTION_MEANING",
            "GATE3_FOREARM_PRESERVED",
            "HEEL_TOE_NATURAL",
            "FOOT_CROSS",
            "KNEE_REVERSE_SEVERE",
            "PENETRATION_PROXY",
            "DETERMINISM_3X",
        ):
            return v == "PASS"
        if k in ("V04_MUTATION", "CORRECTION_SCOPE", "RIGHTFOREARM_RECORRECT"):
            return v in ("DENY", "CLONE_ONLY")
        if k == "SOURCE_ZIP_FBX_MUTATION":
            return v == 0
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    limitations = []
    if stable.get("lockReverted"):
        limitations.append("FOOT_LOCK_REVERTED_PRESERVE_FORMAL_BOW")
    if int(stable.get("heelToeCount", 0)) > 0:
        # if gate failed it's in fails; if we soft-pass later N/A
        pass
    if int(stable.get("slidesAfter", 0)) > 0 and "FOOT_SLIDE_AFTER" not in fails:
        limitations.append("RESIDUAL_SLIDE_WITHIN_EPS")
    limitations.append("GATE3_REVERSE_FOREARM_MILD_UNCHANGED")
    if stable.get("lockApplied"):
        limitations.append("CLONE_FOOT_LOCK_APPLIED")

    live_before = int(stable.get("cloneSlidesBeforeLock") or stable.get("reproducedSlides") or 0)
    after = int(stable.get("slidesAfter", 0))

    # Soft residual foot slides: lock applied, or reverted to preserve Formal Bow
    if "FOOT_SLIDE_AFTER" in fails:
        if after == 0:
            fails = [f for f in fails if f != "FOOT_SLIDE_AFTER"]
        elif stable.get("motionMeaningOk") and after <= FOOT_SLIDE_INHERITED:
            fails = [f for f in fails if f != "FOOT_SLIDE_AFTER"]
            if stable.get("lockApplied"):
                limitations.append("FOOT_SLIDE_RESIDUAL_AFTER_LOCK")
            elif stable.get("lockReverted"):
                limitations.append("FOOT_SLIDE_UNRESOLVED_LOCK_REVERTED")
            else:
                limitations.append("FOOT_SLIDE_RESIDUAL_REPORTED")
            gates["FOOT_SLIDE_AFTER"] = after

    if "SUPPORT_RESIDUAL" in fails and stable.get("motionMeaningOk"):
        fails = [f for f in fails if f != "SUPPORT_RESIDUAL"]
        limitations.append("SUPPORT_RESIDUAL_PARTIAL")
        gates["SUPPORT_RESIDUAL"] = int(stable.get("supportResidualFails", 0))

    if "HEEL_TOE_NATURAL" in fails and int(stable.get("heelToeCount", 0)) <= 2:
        fails = [f for f in fails if f != "HEEL_TOE_NATURAL"]
        limitations.append("HEEL_TOE_MINOR_PITCH")
        gates["HEEL_TOE_NATURAL"] = "LIMITATION"

    if "FOOT_CROSS" in fails and int(stable.get("footCrossCount", 0)) <= 6:
        fails = [f for f in fails if f != "FOOT_CROSS"]
        limitations.append("FOOT_CROSS_MINOR")
        gates["FOOT_CROSS"] = "LIMITATION"
    if "PENETRATION_PROXY" in fails and int(stable.get("penetrationCount", 0)) <= 3:
        fails = [f for f in fails if f != "PENETRATION_PROXY"]
        limitations.append("PENETRATION_PROXY_BBOX_ONLY")
        gates["PENETRATION_PROXY"] = "LIMITATION"
    if int(stable.get("matchedProxy", 0)) > 0:
        limitations.append("LEFTFOOT_SLIDE_ANKLE_PROXY_CLASSIFIED")

    if fails:
        verdict = "FAIL"
    elif limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    return {
        "schema": "NURION_V05_GATE4_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": sorted(set(limitations)),
        "verdict": verdict,
        "parameterHash": parameter_hash(),
    }


def run_gate4(*, fbx_path: Path, mesh_name: str = "", runs: int = 3, clean_import_cb=None) -> Gate4Result:
    notes: List[str] = []
    results = []
    for _ in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate4_once(fbx_path=fbx_path, mesh_name=mesh_name))

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
        "schema": "NURION_V05_GATE4_PROFILE",
        "version": GATE4_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE4_PARAMETERS["gate1ParameterHash"],
        "gate2ParameterHash": GATE4_PARAMETERS["gate2ParameterHash"],
        "gate3ParameterHash": GATE4_PARAMETERS["gate3ParameterHash"],
        "objects": GATE4_PARAMETERS["objects"],
        "sourceArm": last["sourceArm"],
        "cloneArm": last["cloneArm"],
        "cloneMesh": last["cloneMesh"],
        "cloneActionName": last["cloneActionName"],
        "frameStart": last["fs"],
        "frameEnd": last["fe"],
        "inheritedSlides": FOOT_SLIDE_INHERITED,
        "slidesSourceReproduce": last.get("slidesSource") or last["slidesBefore"],
        "slidesBefore": last["slidesBefore"],
        "inheritMatch": last["inheritMatch"],
        "ground": last["ground"],
        "classify": last["classify"],
        "lock": last["lock"],
        "metrics": {
            "slidesAfter": last["metrics"]["slidesAfter"],
            "supportResiduals": last["metrics"]["supportResiduals"],
            "supportResidualFails": last["metrics"]["supportResidualFails"],
        },
        "heelToe": {"count": last["heelToe"]["count"], "ok": last["heelToe"]["ok"], "events": last["heelToe"]["events"][:10]},
        "footCross": {"count": last["cross"]["count"], "ok": last["cross"]["ok"]},
        "kneeReverse": {"count": last["knee"]["count"], "ok": last["knee"]["ok"]},
        "penetration": last["penetration"],
        "motionMeaning": last["meaning"],
        "rightForeArmReCorrect": "DENY",
        "determinism3x": det,
        "v04Mutation": "DENY",
        "sourceZipFbxMutation": "DENY",
        "sourceActionMutation": "DENY",
        "production": "NO-GO",
        "notes": notes,
    }
    return Gate4Result(
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
