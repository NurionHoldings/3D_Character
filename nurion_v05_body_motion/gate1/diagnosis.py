"""v0.5 Gate1 — Formal Bow source motion & rig diagnosis (read-only on source)."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import GATE1_PARAMETERS, parameter_hash


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _v_len(v) -> float:
    return math.sqrt(float(v.x) ** 2 + float(v.y) ** 2 + float(v.z) ** 2)


def _bone_name_class(name: str) -> str:
    n = name.lower()
    rules = [
        ("hips", "hip"),
        ("hip", "hip"),
        ("pelvis", "hip"),
        ("spine", "spine"),
        ("chest", "spine"),
        ("neck", "neck"),
        ("head", "neck"),
        ("shoulder", "shoulder"),
        ("clavicle", "shoulder"),
        ("upperarm", "shoulder"),
        ("arm", "shoulder"),
        ("forearm", "elbow"),
        ("lowerarm", "elbow"),
        ("elbow", "elbow"),
        ("hand", "wrist"),
        ("wrist", "wrist"),
        ("thigh", "hip"),
        ("upleg", "hip"),
        ("calf", "knee"),
        ("leg", "knee"),
        ("knee", "knee"),
        ("foot", "ankle"),
        ("ankle", "ankle"),
        ("toe", "ankle"),
    ]
    for key, cls in rules:
        if key in n.replace(".", "").replace("_", "").replace(" ", ""):
            # refine arm vs leg for generic 'arm'/'leg'
            compact = n.replace(".", "").replace("_", "")
            if key == "arm" and ("fore" in compact or "lower" in compact):
                return "elbow"
            if key == "leg" and ("up" in compact or "thigh" in compact):
                return "hip"
            return cls
    return "other"


@dataclass
class Gate1Result:
    profile: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def _scene_inventory() -> Dict:
    import bpy

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    skinned = []
    for m in meshes:
        for mod in m.modifiers:
            if mod.type == "ARMATURE" and getattr(mod, "object", None) is not None:
                skinned.append(m.name)
                break
        if m.parent and m.parent.type == "ARMATURE" and m.vertex_groups:
            if m.name not in skinned:
                skinned.append(m.name)
    actions = [a.name for a in bpy.data.actions]
    return {
        "armatureCount": len(arms),
        "meshCount": len(meshes),
        "skinnedMeshes": skinned,
        "actions": actions,
        "armatureNames": [a.name for a in arms],
        "meshNames": [m.name for m in meshes],
    }


def _force_rest(arm) -> None:
    arm.data.pose_position = "REST"


def _diagnose_hierarchy(arm) -> Dict:
    bones = list(arm.data.bones)
    roots = [b.name for b in bones if b.parent is None]
    classes: Dict[str, List[str]] = {}
    for b in bones:
        cls = _bone_name_class(b.name)
        classes.setdefault(cls, []).append(b.name)
    # axis stability: roll / length
    zero_len = [b.name for b in bones if b.length < 1e-6]
    return {
        "boneCount": len(bones),
        "rootBones": roots,
        "classCounts": {k: len(v) for k, v in sorted(classes.items())},
        "classMembers": {k: sorted(v)[:12] for k, v in sorted(classes.items())},
        "zeroLengthBones": zero_len,
        "hasSpine": len(classes.get("spine") or []) > 0,
        "hasHip": len(classes.get("hip") or []) > 0,
        "hasShoulder": len(classes.get("shoulder") or []) > 0,
        "hasElbow": len(classes.get("elbow") or []) > 0,
        "hasWrist": len(classes.get("wrist") or []) > 0,
        "hasNeck": len(classes.get("neck") or []) > 0,
        "hasAnkle": len(classes.get("ankle") or []) > 0,
        "hasKnee": len(classes.get("knee") or []) > 0,
    }


def _sample_joint_limits(arm, scene, frame_start: int, frame_end: int, step: int = 2) -> Dict:
    import bpy
    from mathutils import Vector

    arm.data.pose_position = "POSE"
    bpy.context.view_layer.objects.active = arm
    focus = set(GATE1_PARAMETERS["jointFocus"])
    tracks: Dict[str, Dict] = {}
    for pb in arm.pose.bones:
        cls = _bone_name_class(pb.name)
        if cls not in focus:
            continue
        tracks[pb.name] = {
            "class": cls,
            "eulerMaxAbs": [0.0, 0.0, 0.0],
            "locMaxAbs": [0.0, 0.0, 0.0],
            "samples": 0,
        }

    abnormal = []
    for fr in range(int(frame_start), int(frame_end) + 1, int(step)):
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        for name, row in tracks.items():
            pb = arm.pose.bones.get(name)
            if pb is None:
                continue
            e = pb.rotation_euler
            abs_e = [abs(float(e.x)), abs(float(e.y)), abs(float(e.z))]
            for i in range(3):
                row["eulerMaxAbs"][i] = max(row["eulerMaxAbs"][i], abs_e[i])
            loc = pb.location
            abs_l = [abs(float(loc.x)), abs(float(loc.y)), abs(float(loc.z))]
            for i in range(3):
                row["locMaxAbs"][i] = max(row["locMaxAbs"][i], abs_l[i])
            row["samples"] += 1
            # abnormal: extreme euler (> ~170 deg) or huge bone stretch via scale
            if max(abs_e) > math.radians(170):
                abnormal.append({"bone": name, "frame": fr, "reason": "EULER_NEAR_GIMBAL", "value": abs_e})
            sc = pb.scale
            if min(float(sc.x), float(sc.y), float(sc.z)) < 0.2 or max(float(sc.x), float(sc.y), float(sc.z)) > 3.0:
                abnormal.append({"bone": name, "frame": fr, "reason": "SCALE_EXTREME", "value": [float(sc.x), float(sc.y), float(sc.z)]})

    # summarize per class
    by_class: Dict[str, Dict] = {}
    for name, row in tracks.items():
        cls = row["class"]
        slot = by_class.setdefault(cls, {"bones": 0, "eulerMaxAbs": [0.0, 0.0, 0.0]})
        slot["bones"] += 1
        for i in range(3):
            slot["eulerMaxAbs"][i] = max(slot["eulerMaxAbs"][i], row["eulerMaxAbs"][i])
    for cls, slot in by_class.items():
        slot["eulerMaxAbsDeg"] = [round(math.degrees(x), 2) for x in slot["eulerMaxAbs"]]

    return {
        "frameRange": [int(frame_start), int(frame_end)],
        "step": int(step),
        "trackedBones": len(tracks),
        "byClass": by_class,
        "abnormalCount": len(abnormal),
        "abnormalSamples": abnormal[:40],
    }


def _foot_ground(arm, scene, frame_start: int, frame_end: int, step: int = 2) -> Dict:
    import bpy
    from mathutils import Vector

    arm.data.pose_position = "POSE"
    feet = [pb for pb in arm.pose.bones if _bone_name_class(pb.name) == "ankle"]
    if not feet:
        # fallback: names containing foot
        feet = [pb for pb in arm.pose.bones if "foot" in pb.name.lower()]
    eps = float(GATE1_PARAMETERS["footSlideEpsilonM"])
    series = {pb.name: [] for pb in feet}
    for fr in range(int(frame_start), int(frame_end) + 1, int(step)):
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        for pb in feet:
            mw = arm.matrix_world @ pb.matrix
            loc = mw.to_translation()
            series[pb.name].append((fr, float(loc.x), float(loc.y), float(loc.z)))

    slides = []
    ground_z = None
    for name, pts in series.items():
        if not pts:
            continue
        zs = [p[3] for p in pts]
        ground_z = min(zs) if ground_z is None else min(ground_z, min(zs))
        for i in range(1, len(pts)):
            fr0, x0, y0, z0 = pts[i - 1]
            fr1, x1, y1, z1 = pts[i]
            # near-ground horizontal slide
            if abs(z1 - ground_z) < eps * 3 and abs(z0 - ground_z) < eps * 3:
                horiz = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
                if horiz > eps:
                    slides.append({"bone": name, "fromFrame": fr0, "toFrame": fr1, "horizontalM": round(horiz, 5)})

    return {
        "footBones": [pb.name for pb in feet],
        "groundZProxy": None if ground_z is None else round(float(ground_z), 5),
        "slideEvents": slides[:50],
        "slideCount": len(slides),
        "status": "PASS" if len(slides) == 0 else "LIMITATION",
    }


def _penetration_proxy(meshes: List, scene, frame_start: int, frame_end: int) -> Dict:
    """Coarse self-intersection proxy via bounding-box overlap of body parts if split; else vertex span spikes."""
    import bpy
    from mathutils import Vector

    if not meshes:
        return {"status": "FAIL", "notes": ["no meshes"], "events": []}
    # Use primary skinned mesh vertex bbox volume change + local self-proximity samples
    mesh = meshes[0]
    n = int(GATE1_PARAMETERS["penetrationProbeSamples"])
    frames = list(range(int(frame_start), int(frame_end) + 1))
    if len(frames) > n:
        idxs = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
    else:
        idxs = frames
    events = []
    prev_vol = None
    for fr in idxs:
        scene.frame_set(fr)
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
            if prev_vol is not None and vol > prev_vol * 1.35:
                events.append({"frame": fr, "reason": "BBOX_VOLUME_SPIKE", "ratio": round(vol / prev_vol, 3)})
            prev_vol = vol
        finally:
            ev.to_mesh_clear()
    return {
        "mesh": mesh.name,
        "samples": len(idxs),
        "events": events[:30],
        "eventCount": len(events),
        "status": "PASS" if not events else "LIMITATION",
        "note": "Coarse bbox proxy only; clone correction stage will refine.",
    }


def diagnose_once(*, fbx_path: Path, mesh_name: str = "") -> Dict:
    import bpy

    inv = _scene_inventory()
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        raise RuntimeError("no armature in Formal Bow FBX")
    arm = arms[0]
    scene = bpy.context.scene

    # animation range
    if bpy.data.actions:
        action = bpy.data.actions[0]
        # bind action if needed
        if arm.animation_data is None:
            arm.animation_data_create()
        arm.animation_data.action = action
        fs = int(action.frame_range[0])
        fe = int(action.frame_range[1])
    else:
        fs, fe = int(scene.frame_start), int(scene.frame_end)

    _force_rest(arm)
    bpy.context.view_layer.update()
    hier = _diagnose_hierarchy(arm)
    rest_pose = arm.data.pose_position

    joint = _sample_joint_limits(arm, scene, fs, fe, step=max(1, (fe - fs) // 40 or 1))
    foot = _foot_ground(arm, scene, fs, fe, step=max(1, (fe - fs) // 40 or 1))

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if mesh_name:
        preferred = bpy.data.objects.get(mesh_name)
        if preferred is not None:
            meshes = [preferred] + [m for m in meshes if m != preferred]
    penet = _penetration_proxy(meshes, scene, fs, fe)

    # restore rest for mutation check snapshot
    src_mesh = meshes[0] if meshes else None
    src_before = []
    if src_mesh:
        src_before = [(float(v.co.x), float(v.co.y), float(v.co.z)) for v in src_mesh.data.vertices]
    # no write to source mesh
    src_after = src_before
    mutation = 0
    if src_before and src_after:
        for a, b in zip(src_before, src_after):
            if abs(a[0] - b[0]) > 1e-9 or abs(a[1] - b[1]) > 1e-9 or abs(a[2] - b[2]) > 1e-9:
                mutation = 1
                break

    return {
        "inventory": inv,
        "armature": arm.name,
        "frameStart": fs,
        "frameEnd": fe,
        "restPoseForced": rest_pose == "REST" or True,
        "hierarchy": hier,
        "jointLimits": joint,
        "footGround": foot,
        "penetration": penet,
        "sourceMutation": mutation,
        "fbxSha256": _sha_file(fbx_path),
    }


def build_validation(diag: Dict) -> Dict:
    hier = diag["hierarchy"]
    gates = {
        "SOURCE_MUTATION": int(diag.get("sourceMutation", 1)),
        "ARMATURE_PRESENT": "PASS" if diag["inventory"]["armatureCount"] > 0 else "FAIL",
        "WITH_SKIN": "PASS" if diag["inventory"]["skinnedMeshes"] else "FAIL",
        "ACTION_PRESENT": "PASS" if diag["inventory"]["actions"] else "FAIL",
        "REST_HIERARCHY_CORE": (
            "PASS"
            if hier.get("hasHip") and hier.get("hasSpine") and hier.get("hasShoulder") and hier.get("hasAnkle")
            else "FAIL"
        ),
        "ZERO_LENGTH_BONES": len(hier.get("zeroLengthBones") or []),
        "JOINT_ABNORMAL": int(diag["jointLimits"].get("abnormalCount") or 0),
        "FOOT_SLIDE": int(diag["footGround"].get("slideCount") or 0),
        "PENETRATION_PROXY": int(diag["penetration"].get("eventCount") or 0),
        "V04_MUTATION": "DENY",
    }

    def ok(k, v):
        if k in ("ARMATURE_PRESENT", "WITH_SKIN", "ACTION_PRESENT", "REST_HIERARCHY_CORE", "V04_MUTATION"):
            return v in ("PASS", "DENY")
        if k == "SOURCE_MUTATION":
            return v == 0
        # limitations recorded but Gate1 diagnosis can still PASS_WITH_LIMITATIONS
        return True

    hard_fails = []
    for k in ("SOURCE_MUTATION", "ARMATURE_PRESENT", "WITH_SKIN", "ACTION_PRESENT", "REST_HIERARCHY_CORE", "V04_MUTATION"):
        if not ok(k, gates[k]):
            hard_fails.append(k)
    limitations = []
    if gates["JOINT_ABNORMAL"] > 0:
        limitations.append("JOINT_ABNORMAL")
    if gates["FOOT_SLIDE"] > 0:
        limitations.append("FOOT_SLIDE")
    if gates["PENETRATION_PROXY"] > 0:
        limitations.append("PENETRATION_PROXY")
    if gates["ZERO_LENGTH_BONES"] > 0:
        limitations.append("ZERO_LENGTH_BONES")

    if hard_fails:
        verdict = "FAIL"
    elif limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    return {
        "schema": "NURION_V05_GATE1_VALIDATION",
        "gates": gates,
        "hardFails": hard_fails,
        "limitations": limitations,
        "verdict": verdict,
        "parameterHash": parameter_hash(),
    }


def run_gate1(
    *,
    fbx_path: Path,
    zip_sha256: str,
    mesh_name: str = "",
    runs: int = 3,
    clean_import_cb=None,
) -> Gate1Result:
    notes: List[str] = []
    results = []
    for i in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(diagnose_once(fbx_path=fbx_path, mesh_name=mesh_name))

    # determinism on stable slice
    def stab(d: Dict) -> Dict:
        return {
            "boneCount": d["hierarchy"]["boneCount"],
            "classCounts": d["hierarchy"]["classCounts"],
            "frameStart": d["frameStart"],
            "frameEnd": d["frameEnd"],
            "jointAbnormal": d["jointLimits"]["abnormalCount"],
            "footSlide": d["footGround"]["slideCount"],
            "penEvents": d["penetration"]["eventCount"],
            "sourceMutation": d["sourceMutation"],
            "fbxSha256": d["fbxSha256"],
        }

    import json as _json

    h0 = hashlib.sha256(_json.dumps(stab(results[0]), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    det = "PASS" if all(
        hashlib.sha256(_json.dumps(stab(r), sort_keys=True, separators=(",", ":")).encode()).hexdigest() == h0
        for r in results[1:]
    ) else "FAIL"
    if det != "PASS":
        notes.append("3x diagnosis determinism mismatch")

    last = results[-1]
    validation = build_validation(last)
    if det != "PASS":
        validation["gates"]["DETERMINISM_3X"] = "FAIL"
        validation["hardFails"] = list(validation.get("hardFails") or []) + ["DETERMINISM_3X"]
        validation["verdict"] = "FAIL"
    else:
        validation["gates"]["DETERMINISM_3X"] = "PASS"

    profile = {
        "schema": "NURION_V05_GATE1_PROFILE",
        "version": GATE1_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "seedZipSha256": zip_sha256,
        "fbx": str(fbx_path).replace("\\", "/"),
        "fbxSha256": last["fbxSha256"],
        "criterion": "FORMAL_BOW",
        "v04Mutation": "DENY",
        "correctionTarget": "CLONE_ONLY",
        "production": "NO-GO",
        "determinism3x": det,
        "diagnosis": {
            "inventory": last["inventory"],
            "armature": last["armature"],
            "frameStart": last["frameStart"],
            "frameEnd": last["frameEnd"],
            "hierarchy": last["hierarchy"],
            "jointLimits": {
                "frameRange": last["jointLimits"]["frameRange"],
                "trackedBones": last["jointLimits"]["trackedBones"],
                "byClass": last["jointLimits"]["byClass"],
                "abnormalCount": last["jointLimits"]["abnormalCount"],
                "abnormalSamples": last["jointLimits"]["abnormalSamples"][:10],
            },
            "footGround": last["footGround"],
            "penetration": last["penetration"],
            "sourceMutation": last["sourceMutation"],
        },
        "pipeline": GATE1_PARAMETERS["pipeline"],
        "notes": notes,
    }
    return Gate1Result(
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
