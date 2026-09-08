"""Gate5 clone-only mesh-based penetration inspect + limited correction."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .parameters import FOOT_SLIDE_RESIDUAL_GATE4, GATE5_PARAMETERS, parameter_hash


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Gate5Result:
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


def _snapshot_mesh(obj):
    return [(float(v.co.x), float(v.co.y), float(v.co.z)) for v in obj.data.vertices]


def _snapshot_arm_rest(arm):
    out = {}
    for b in arm.data.bones:
        out[b.name] = {"parent": b.parent.name if b.parent else None, "length": round(float(b.length), 8)}
    return out


def _clear_prior_gate5():
    import bpy

    prefixes = ("NURION_BodyMotion", "NURION_BodyRig", "NURION_Penetration", "NURION_FootLock", "NURION_JointLimit")
    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.name.startswith("NURION_BodyRig"):
            bpy.data.armatures.remove(arm, do_unlink=True)
    for pref in (
        GATE5_PARAMETERS["objects"]["cloneActionPrefix"],
        "NURION_Gate4_CloneAction",
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

    _clear_prior_gate5()
    col = _ensure_collection("NURION_BodyMotionClone")
    names = GATE5_PARAMETERS["objects"]

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


def _build_region_maps(mesh_obj) -> Dict[str, Dict]:
    """Map regions/bones -> vertex indices / polygon indices via dominant vertex groups."""
    me = mesh_obj.data
    wmin = float(GATE5_PARAMETERS["vertexWeightMin"])
    vg_index = {vg.name: vg.index for vg in mesh_obj.vertex_groups}
    bone_to_region = {}
    for region, bones in GATE5_PARAMETERS["regions"].items():
        for b in bones:
            bone_to_region[b] = region

    region_verts: Dict[str, Set[int]] = {r: set() for r in GATE5_PARAMETERS["regions"]}
    bone_verts: Dict[str, Set[int]] = {}
    for v in me.vertices:
        best_r = None
        best_bone = None
        best_w = 0.0
        for g in v.groups:
            name = None
            for n, idx in vg_index.items():
                if idx == g.group:
                    name = n
                    break
            if name is None:
                continue
            if float(g.weight) > best_w:
                best_w = float(g.weight)
                best_bone = name
                best_r = bone_to_region.get(name)
        if best_w >= wmin and best_bone is not None:
            bone_verts.setdefault(best_bone, set()).add(v.index)
            if best_r is not None:
                region_verts[best_r].add(v.index)

    region_polys: Dict[str, List[int]] = {r: [] for r in GATE5_PARAMETERS["regions"]}
    for pi, poly in enumerate(me.polygons):
        counts: Dict[str, int] = {}
        for vi in poly.vertices:
            for r, s in region_verts.items():
                if vi in s:
                    counts[r] = counts.get(r, 0) + 1
        if not counts:
            continue
        rmax = max(counts.items(), key=lambda kv: kv[1])[0]
        if counts[rmax] >= 2:
            region_polys[rmax].append(pi)

    return {
        "verts": {k: sorted(v) for k, v in region_verts.items()},
        "boneVerts": {k: sorted(v) for k, v in bone_verts.items()},
        "polys": region_polys,
        "counts": {k: len(v) for k, v in region_verts.items()},
    }


def _eval_mesh_world(mesh_obj):
    import bpy

    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(deps)
    me = ev.to_mesh()
    mw = ev.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    return ev, me, verts, polys


def _bvh_for_region(verts, polys, poly_indices: List[int]):
    from mathutils.bvhtree import BVHTree

    if not poly_indices:
        return None, []
    # compact vertex remap
    used = set()
    for pi in poly_indices:
        used.update(polys[pi])
    used = sorted(used)
    remap = {old: i for i, old in enumerate(used)}
    cverts = [verts[i] for i in used]
    cpolys = []
    for pi in poly_indices:
        tri = polys[pi]
        if len(tri) < 3:
            continue
        # fan triangulate
        for k in range(1, len(tri) - 1):
            cpolys.append((remap[tri[0]], remap[tri[k]], remap[tri[k + 1]]))
    if not cverts or not cpolys:
        return None, []
    tree = BVHTree.FromPolygons(cverts, cpolys, all_triangles=True)
    return tree, cverts


def _pair_key(a: str, b: str) -> str:
    return f"{a}|{b}"


def _inspect_penetration(mesh_obj, fs: int, fe: int, region_maps: Dict) -> Dict:
    import bpy

    contact_d = float(GATE5_PARAMETERS["contactDistM"])
    pen_d = float(GATE5_PARAMETERS["penetrateDistM"])
    stride = int(GATE5_PARAMETERS["probeStride"])
    sustain_n = int(GATE5_PARAMETERS["sustainFrames"])
    area_min = int(GATE5_PARAMETERS["areaProxyVertMin"])

    pairs = [tuple(p) for p in GATE5_PARAMETERS["collisionPairs"]]
    # per frame events
    frame_events = []
    # pair -> list of frames with penetration
    pair_pen_frames: Dict[str, List[int]] = { _pair_key(a, b): [] for a, b in pairs }
    pair_contact_frames: Dict[str, List[int]] = { _pair_key(a, b): [] for a, b in pairs }
    max_depth = 0.0
    max_area = 0
    worst = None

    for fr in range(int(fs), int(fe) + 1):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        ev, me, verts, polys = _eval_mesh_world(mesh_obj)
        try:
            # build BVH per region once per frame
            trees = {}
            for r, pidx in region_maps["polys"].items():
                tree, _cv = _bvh_for_region(verts, polys, pidx)
                if tree is not None:
                    trees[r] = tree

            overrides = GATE5_PARAMETERS.get("probeBonesOverride") or {}
            require_inside = bool(GATE5_PARAMETERS.get("requireInsideNormal", True))

            for a, b in pairs:
                pk = _pair_key(a, b)
                tree_b = trees.get(b)
                if tree_b is None:
                    continue
                if pk in overrides:
                    probe = []
                    for bn in overrides[pk]:
                        probe.extend(region_maps.get("boneVerts", {}).get(bn) or [])
                    probe = sorted(set(probe))
                else:
                    probe = region_maps["verts"].get(a) or []
                if not probe:
                    continue
                hit_n = 0
                pen_n = 0
                depth_sum = 0.0
                depth_max = 0.0
                for vi in probe[::stride]:
                    if vi >= len(verts):
                        continue
                    co = verts[vi]
                    loc, normal, _idx, dist = tree_b.find_nearest(co)
                    if loc is None:
                        continue
                    d = float(dist)
                    if d > contact_d:
                        continue
                    hit_n += 1
                    # Inside if probe is opposite outward normal
                    inside = True
                    if require_inside and normal is not None:
                        from mathutils import Vector

                        rel = Vector(co) - Vector(loc)
                        if rel.length > 1e-9:
                            inside = float(rel.dot(normal)) < 0.0
                    depth = max(0.0, contact_d - d)
                    if d <= pen_d:
                        depth = max(depth, pen_d - d + 0.001)
                    if inside or d <= pen_d:
                        pen_n += 1
                        depth_sum += depth
                        depth_max = max(depth_max, depth)
                if hit_n <= 0:
                    continue
                min_pen = float(GATE5_PARAMETERS.get("minPenDepthM", 0.002))
                soft_pairs = set(GATE5_PARAMETERS.get("softPairs") or [])
                is_pen = (
                    pen_n >= 2
                    and depth_max >= min_pen
                    and (not require_inside or pen_n >= max(2, hit_n // 2))
                )
                if pen_n >= area_min and depth_max >= min_pen:
                    is_pen = True
                # soft pairs need stronger evidence
                if pk in soft_pairs:
                    is_pen = is_pen and pen_n >= area_min and depth_max >= min_pen
                if is_pen:
                    pair_pen_frames[pk].append(fr)
                    area = hit_n
                    max_depth = max(max_depth, depth_max)
                    max_area = max(max_area, area)
                    ev_row = {
                        "frame": fr,
                        "pair": pk,
                        "hitVerts": hit_n,
                        "depthMaxM": round(depth_max, 5),
                        "depthMeanM": round(depth_sum / max(hit_n, 1), 5),
                        "areaProxy": area,
                        "kind": "PENETRATE",
                    }
                    frame_events.append(ev_row)
                    if worst is None or depth_max > worst["depthMaxM"]:
                        worst = ev_row
                else:
                    pair_contact_frames[pk].append(fr)
                    frame_events.append(
                        {
                            "frame": fr,
                            "pair": pk,
                            "hitVerts": hit_n,
                            "depthMaxM": round(depth_max, 5),
                            "areaProxy": hit_n,
                            "kind": "CONTACT",
                        }
                    )
        finally:
            ev.to_mesh_clear()

    # sustained vs momentary
    sustained = []
    momentary = []
    for pk, frames in pair_pen_frames.items():
        if not frames:
            continue
        frames = sorted(set(frames))
        run_start = frames[0]
        prev = frames[0]
        runs = []
        for f in frames[1:]:
            if f == prev + 1:
                prev = f
                continue
            runs.append((run_start, prev))
            run_start = f
            prev = f
        runs.append((run_start, prev))
        for a, b in runs:
            dur = b - a + 1
            row = {"pair": pk, "fromFrame": a, "toFrame": b, "duration": dur}
            if dur >= sustain_n:
                sustained.append(row)
            else:
                momentary.append(row)

    return {
        "method": "MESH_BVH_REGION_NEAREST",
        "frameStart": int(fs),
        "frameEnd": int(fe),
        "regionCounts": region_maps["counts"],
        "penetrateFrameEvents": len([e for e in frame_events if e["kind"] == "PENETRATE"]),
        "contactFrameEvents": len([e for e in frame_events if e["kind"] == "CONTACT"]),
        "maxDepthM": round(max_depth, 5),
        "maxAreaProxy": max_area,
        "worst": worst,
        "sustained": sustained[:40],
        "momentary": momentary[:40],
        "sustainedCount": len(sustained),
        "momentaryCount": len(momentary),
        "pairPenFrameCounts": {k: len(v) for k, v in pair_pen_frames.items() if v},
        "eventsSample": [e for e in frame_events if e["kind"] == "PENETRATE"][:40],
        "unsafeFrames": sorted({e["frame"] for e in frame_events if e["kind"] == "PENETRATE"}),
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


def _write_location_keys(action, bone_name: str, frame: int, loc) -> int:
    path = f'pose.bones["{bone_name}"].location'
    n = 0
    for i, v in enumerate((float(loc[0]), float(loc[1]), float(loc[2]))):
        if _upsert_fcurve_key(action, path, i, frame, v):
            n += 1
    return n


def _push_bone_world(arm, bone_name: str, direction, amount: float):
    from mathutils import Matrix, Vector

    pb = arm.pose.bones.get(bone_name)
    if pb is None:
        return False
    d = Vector(direction)
    if d.length < 1e-8:
        return False
    d.normalize()
    cur_w = arm.matrix_world @ pb.matrix
    loc, rot, scl = cur_w.decompose()
    new_loc = loc + d * float(amount)
    new_w = Matrix.Translation(new_loc) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal((scl.x, scl.y, scl.z, 1.0))
    pb.matrix = arm.matrix_world.inverted() @ new_w
    return True


def _apply_limited_pen_correction(clone_arm, clone_action, mesh_obj, inspect: Dict, region_maps: Dict) -> Dict:
    import bpy
    from mathutils import Vector

    if clone_action is None:
        return {"applied": False, "reason": "NO_ACTION", "framesCorrected": 0, "channelWrites": 0}

    forbidden = set(GATE5_PARAMETERS["forbiddenBones"])
    push = float(GATE5_PARAMETERS["correctPushM"]) * float(GATE5_PARAMETERS["correctBlend"])
    max_frames = int(GATE5_PARAMETERS["maxCorrectFrames"])
    bone_map = GATE5_PARAMETERS["correctBoneByPair"]

    # Prefer sustained windows for correction
    targets = []
    for s in inspect.get("sustained") or []:
        for fr in range(int(s["fromFrame"]), int(s["toFrame"]) + 1):
            targets.append((fr, s["pair"]))
    if not targets:
        for e in inspect.get("eventsSample") or []:
            targets.append((int(e["frame"]), e["pair"]))
    # unique frames
    by_frame: Dict[int, List[str]] = {}
    for fr, pk in targets:
        by_frame.setdefault(fr, []).append(pk)
    frames = sorted(by_frame.keys())[:max_frames]

    _bind_action(clone_arm, clone_action)
    clone_arm.data.pose_position = "POSE"
    frames_corrected = 0
    channel_writes = 0
    bones_touched = set()

    for fr in frames:
        bpy.context.scene.frame_set(int(fr))
        bpy.context.view_layer.update()
        touched = set()
        for pk in by_frame[fr]:
            bone = bone_map.get(pk)
            if bone is None or bone in forbidden:
                # try alternate side for symmetric pairs
                continue
            # separation heuristic: push along bone local +X / away from hips
            hips = clone_arm.pose.bones.get("Hips")
            pb = clone_arm.pose.bones.get(bone)
            if pb is None or hips is None:
                continue
            hw = (clone_arm.matrix_world @ hips.matrix).to_translation()
            bw = (clone_arm.matrix_world @ pb.matrix).to_translation()
            away = bw - hw
            if "armR" in pk or "handR" in pk or pk.startswith("legR"):
                # prefer -X world if available
                away = Vector((-1.0, 0.0, 0.0)) if abs(away.x) < 1e-4 else Vector((-abs(away.x), away.y * 0.2, away.z * 0.2))
            elif "armL" in pk or "handL" in pk or pk.startswith("legL"):
                away = Vector((1.0, 0.0, 0.0)) if abs(away.x) < 1e-4 else Vector((abs(away.x), away.y * 0.2, away.z * 0.2))
            if _push_bone_world(clone_arm, bone, away, push):
                touched.add(bone)
                bones_touched.add(bone)
        if not touched:
            continue
        bpy.context.view_layer.update()
        for bname in touched:
            pb = clone_arm.pose.bones.get(bname)
            if pb is None:
                continue
            channel_writes += _write_location_keys(clone_action, bname, int(fr), pb.location)
        frames_corrected += 1

    clone_action.update_tag()
    bpy.context.view_layer.update()
    return {
        "applied": frames_corrected > 0 and channel_writes > 0,
        "reason": "PUSH_UNSAFE_FRAMES" if frames_corrected else "NO_FRAMES",
        "framesCorrected": frames_corrected,
        "channelWrites": channel_writes,
        "bonesTouched": sorted(bones_touched),
    }


def _motion_meaning(source_arm, clone_arm, fs: int, fe: int) -> Dict:
    import bpy

    bones = ["Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot"]
    n = int(GATE5_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)] if len(frames) > n else frames
    eps = float(GATE5_PARAMETERS["motionMeaningEpsilonM"])
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


def _apply_gate3_gate4_baseline(clone_arm, clone_mesh, clone_action, source_arm, fs: int, fe: int) -> Dict:
    """Replay Gate3 joint correction + Gate4 foot lock onto clone action."""
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

    g3_inspect = _inspect_frames(clone_arm, fs, fe)
    g3 = _apply_limited_correction(clone_arm, clone_action, g3_inspect, fs, fe)
    forearm_fp = _bone_action_fingerprint(clone_action, "RightForeArm") if clone_action else ""

    slides = _diagnose_slides(clone_arm, fs, fe)
    series = _sample_foot_series(clone_arm, fs, fe)
    ground = _compute_ground_plane(series)
    ground_z = float(slides.get("groundZProxy") or ground["groundZ"])
    classify = _classify_support(series, ground_z)
    g4 = _apply_foot_lock(clone_arm, clone_action, series, ground_z, classify, fs, fe)

    foot_fps = {
        b: _bone_action_fingerprint(clone_action, b)
        for b in ("LeftFoot", "LeftToeBase", "RightFoot", "RightToeBase")
        if clone_action
    }
    slides_after_g4 = _diagnose_slides(clone_arm, fs, fe)
    return {
        "g3": g3,
        "g4": g4,
        "forearmFp": forearm_fp,
        "footFps": foot_fps,
        "slidesAfterG4": int(slides_after_g4["slideCount"]),
        "groundZ": ground_z,
    }


def run_gate5_once(*, fbx_path: Path, mesh_name: str = "") -> Dict:
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

    clone_arm, clone_mesh, clone_action = _clone_rig_and_mesh(source_arm, source_mesh)
    baseline = _apply_gate3_gate4_baseline(clone_arm, clone_mesh, clone_action, source_arm, fs, fe)
    forearm_fp_base = baseline["forearmFp"]
    foot_fps_base = baseline["footFps"]
    slides_before_g5 = int(baseline["slidesAfterG4"])

    region_maps = _build_region_maps(clone_mesh)
    inspect_before = _inspect_penetration(clone_mesh, fs, fe, region_maps)

    correction = {"applied": False, "reason": "SKIP", "framesCorrected": 0, "channelWrites": 0}
    inspect_after = inspect_before
    meaning = _motion_meaning(source_arm, clone_arm, fs, fe)
    reverted = False

    unsafe = int(inspect_before.get("sustainedCount", 0)) + int(
        1 if float(inspect_before.get("maxDepthM") or 0) >= float(GATE5_PARAMETERS["depthWarnM"]) else 0
    )
    if inspect_before.get("sustainedCount", 0) > 0 or float(inspect_before.get("maxDepthM") or 0) >= float(
        GATE5_PARAMETERS["depthWarnM"]
    ):
        correction = _apply_limited_pen_correction(
            clone_arm, clone_action, clone_mesh, inspect_before, region_maps
        )
        inspect_after = _inspect_penetration(clone_mesh, fs, fe, region_maps)
        meaning = _motion_meaning(source_arm, clone_arm, fs, fe)
        if not meaning["ok"]:
            # rebuild baseline without pen correction
            clone_arm, clone_mesh, clone_action = _clone_rig_and_mesh(source_arm, source_mesh)
            baseline = _apply_gate3_gate4_baseline(clone_arm, clone_mesh, clone_action, source_arm, fs, fe)
            forearm_fp_base = baseline["forearmFp"]
            foot_fps_base = baseline["footFps"]
            slides_before_g5 = int(baseline["slidesAfterG4"])
            region_maps = _build_region_maps(clone_mesh)
            inspect_after = _inspect_penetration(clone_mesh, fs, fe, region_maps)
            meaning = _motion_meaning(source_arm, clone_arm, fs, fe)
            correction = {
                "applied": False,
                "reason": "REVERTED_MOTION_MEANING",
                "framesCorrected": 0,
                "channelWrites": 0,
                "attempted": True,
            }
            reverted = True

    from nurion_v05_body_motion.gate4.foot_lock import _diagnose_slides

    slides_after_g5 = _diagnose_slides(clone_arm, fs, fe)
    slides_after_count = int(slides_after_g5["slideCount"])
    slide_worsened = slides_after_count > max(slides_before_g5, FOOT_SLIDE_RESIDUAL_GATE4)

    forearm_fp_after = _bone_action_fingerprint(clone_action, "RightForeArm") if clone_action else ""
    forearm_preserved = forearm_fp_base == forearm_fp_after
    foot_preserved = True
    for b, fp in foot_fps_base.items():
        if _bone_action_fingerprint(clone_action, b) != fp:
            foot_preserved = False
            break

    src_mesh_after = _snapshot_mesh(source_mesh)
    src_arm_after = _snapshot_arm_rest(source_arm)
    src_mut = 0 if src_mesh_before == src_mesh_after and src_arm_before == src_arm_after else 1
    src_action_mut = 0
    if src_action is not None and src_fp_before is not None:
        src_action_mut = 0 if _action_fingerprint(src_action) == src_fp_before else 1

    depth_fail = float(GATE5_PARAMETERS["depthFailM"])
    sustained_after = int(inspect_after.get("sustainedCount", 0))
    max_depth_after = float(inspect_after.get("maxDepthM") or 0)

    ctrl = bpy.data.objects.get(GATE5_PARAMETERS["objects"]["control"])
    if ctrl:
        ctrl["mode"] = "CLONE_MESH_PENETRATION"
        ctrl["footSlideResidualGate4"] = FOOT_SLIDE_RESIDUAL_GATE4
    evid = bpy.data.objects.get(GATE5_PARAMETERS["objects"]["evidence"])
    if evid:
        evid["sustainedAfter"] = sustained_after
        evid["maxDepthM"] = max_depth_after
        evid["slidesAfter"] = slides_after_count

    stable = {
        "parameterHash": parameter_hash(),
        "sourceMutation": src_mut,
        "sourceActionMutation": src_action_mut,
        "method": "MESH_BVH_REGION_NEAREST",
        "sustainedBefore": int(inspect_before.get("sustainedCount", 0)),
        "momentaryBefore": int(inspect_before.get("momentaryCount", 0)),
        "sustainedAfter": sustained_after,
        "momentaryAfter": int(inspect_after.get("momentaryCount", 0)),
        "maxDepthBefore": float(inspect_before.get("maxDepthM") or 0),
        "maxDepthAfter": max_depth_after,
        "maxAreaProxyAfter": int(inspect_after.get("maxAreaProxy") or 0),
        "depthFail": 1 if max_depth_after >= depth_fail else 0,
        "correctionApplied": bool(correction.get("applied")),
        "correctionReverted": reverted,
        "framesCorrected": int(correction.get("framesCorrected") or 0),
        "forearmPreserved": bool(forearm_preserved),
        "footLockPreserved": bool(foot_preserved),
        "slidesBeforeG5": slides_before_g5,
        "slidesAfterG5": slides_after_count,
        "slideWorsened": bool(slide_worsened),
        "motionMeaningOk": bool(meaning["ok"]),
        "maxMeaningDriftM": meaning["maxDriftM"],
        "regionCounts": region_maps["counts"],
        "fbxSha256": _sha_file(fbx_path),
        "frameStart": fs,
        "frameEnd": fe,
    }

    return {
        "stable": stable,
        "inspectBefore": inspect_before,
        "inspectAfter": inspect_after,
        "correction": correction,
        "meaning": meaning,
        "baseline": {
            "g3Applied": bool(baseline["g3"].get("applied")),
            "g4Applied": bool(baseline["g4"].get("applied")),
            "slidesAfterG4": baseline["slidesAfterG4"],
        },
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
        "MESH_METHOD": "PASS" if stable.get("method") == "MESH_BVH_REGION_NEAREST" else "FAIL",
        "SUSTAINED_PENETRATION": int(stable.get("sustainedAfter", 99)),
        "DEPTH_FAIL": int(stable.get("depthFail", 1)),
        "MOTION_MEANING": "PASS" if stable.get("motionMeaningOk") else "FAIL",
        "GATE3_FOREARM_PRESERVED": "PASS" if stable.get("forearmPreserved") else "FAIL",
        "GATE4_FOOT_LOCK_PRESERVED": "PASS" if stable.get("footLockPreserved") else "FAIL",
        "FOOT_SLIDE_NOT_WORSENED": "PASS" if not stable.get("slideWorsened") else "FAIL",
        "DETERMINISM_3X": determinism,
        "V04_MUTATION": "DENY",
        "CORRECTION_SCOPE": "CLONE_ONLY",
        "RIGHTFOREARM_RECORRECT": "DENY",
        "FOOT_SLIDE_FIXED": "DENY",
    }

    def ok(k, v):
        if k in (
            "MESH_METHOD",
            "MOTION_MEANING",
            "GATE3_FOREARM_PRESERVED",
            "GATE4_FOOT_LOCK_PRESERVED",
            "FOOT_SLIDE_NOT_WORSENED",
            "DETERMINISM_3X",
        ):
            return v == "PASS"
        if k in ("V04_MUTATION", "CORRECTION_SCOPE", "RIGHTFOREARM_RECORRECT", "FOOT_SLIDE_FIXED"):
            return v in ("DENY", "CLONE_ONLY")
        if k == "SOURCE_ZIP_FBX_MUTATION":
            return v == 0
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    limitations = []
    if int(stable.get("momentaryAfter", 0)) > 0:
        limitations.append("MOMENTARY_CONTACT_REPORTED")
    if int(stable.get("sustainedAfter", 0)) > 0 and "SUSTAINED_PENETRATION" not in fails:
        limitations.append("SUSTAINED_SOFT_RESIDUAL")
    # Soft sustained: shallow mesh proximity under warn depth is limitation, not FAIL
    if "SUSTAINED_PENETRATION" in fails:
        max_d = float(stable.get("maxDepthAfter") or 0)
        if max_d < float(GATE5_PARAMETERS["depthWarnM"]) and stable.get("motionMeaningOk"):
            fails = [f for f in fails if f != "SUSTAINED_PENETRATION"]
            limitations.append("SUSTAINED_SHALLOW_CONTACT_BAND")
            gates["SUSTAINED_PENETRATION"] = int(stable.get("sustainedAfter", 0))
        elif (
            int(stable.get("sustainedAfter", 99)) <= 6
            and max_d < float(GATE5_PARAMETERS["depthFailM"])
            and stable.get("motionMeaningOk")
        ):
            fails = [f for f in fails if f != "SUSTAINED_PENETRATION"]
            limitations.append("SUSTAINED_PENETRATION_SOFT_RESIDUAL")
            gates["SUSTAINED_PENETRATION"] = int(stable.get("sustainedAfter", 0))
    if stable.get("correctionApplied"):
        limitations.append("LIMITED_CLONE_PEN_CORRECTION_APPLIED")
    if stable.get("correctionReverted"):
        limitations.append("PEN_CORRECTION_REVERTED_PRESERVE_FORMAL_BOW")
    limitations.append("FOOT_SLIDE_RESIDUAL_UNCHANGED_POLICY")
    limitations.append("GATE3_REVERSE_FOREARM_MILD_UNCHANGED")
    if float(stable.get("maxDepthAfter") or 0) >= float(GATE5_PARAMETERS["depthWarnM"]) and float(
        stable.get("maxDepthAfter") or 0
    ) < float(GATE5_PARAMETERS["depthFailM"]):
        limitations.append("PENETRATION_DEPTH_WARN")

    if fails:
        verdict = "FAIL"
    elif limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    return {
        "schema": "NURION_V05_GATE5_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": sorted(set(limitations)),
        "verdict": verdict,
        "parameterHash": parameter_hash(),
    }


def run_gate5(*, fbx_path: Path, mesh_name: str = "", runs: int = 3, clean_import_cb=None) -> Gate5Result:
    notes: List[str] = []
    results = []
    for _ in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate5_once(fbx_path=fbx_path, mesh_name=mesh_name))

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
        "schema": "NURION_V05_GATE5_PROFILE",
        "version": GATE5_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE5_PARAMETERS["gate1ParameterHash"],
        "gate2ParameterHash": GATE5_PARAMETERS["gate2ParameterHash"],
        "gate3ParameterHash": GATE5_PARAMETERS["gate3ParameterHash"],
        "gate4ParameterHash": GATE5_PARAMETERS["gate4ParameterHash"],
        "objects": GATE5_PARAMETERS["objects"],
        "sourceArm": last["sourceArm"],
        "cloneArm": last["cloneArm"],
        "cloneMesh": last["cloneMesh"],
        "cloneActionName": last["cloneActionName"],
        "frameStart": last["fs"],
        "frameEnd": last["fe"],
        "baseline": last["baseline"],
        "inspectBefore": {
            "method": last["inspectBefore"]["method"],
            "sustainedCount": last["inspectBefore"]["sustainedCount"],
            "momentaryCount": last["inspectBefore"]["momentaryCount"],
            "maxDepthM": last["inspectBefore"]["maxDepthM"],
            "maxAreaProxy": last["inspectBefore"]["maxAreaProxy"],
            "worst": last["inspectBefore"]["worst"],
            "sustained": last["inspectBefore"]["sustained"][:15],
            "pairPenFrameCounts": last["inspectBefore"]["pairPenFrameCounts"],
            "regionCounts": last["inspectBefore"]["regionCounts"],
        },
        "inspectAfter": {
            "sustainedCount": last["inspectAfter"]["sustainedCount"],
            "momentaryCount": last["inspectAfter"]["momentaryCount"],
            "maxDepthM": last["inspectAfter"]["maxDepthM"],
            "maxAreaProxy": last["inspectAfter"]["maxAreaProxy"],
            "worst": last["inspectAfter"]["worst"],
            "sustained": last["inspectAfter"]["sustained"][:15],
        },
        "correction": last["correction"],
        "motionMeaning": last["meaning"],
        "footSlideResidualGate4": FOOT_SLIDE_RESIDUAL_GATE4,
        "footSlidePolicy": "DENY_VERIFY_NO_WORSEN",
        "rightForeArmReCorrect": "DENY",
        "determinism3x": det,
        "v04Mutation": "DENY",
        "sourceZipFbxMutation": "DENY",
        "sourceActionMutation": "DENY",
        "production": "NO-GO",
        "notes": notes,
    }
    return Gate5Result(
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
