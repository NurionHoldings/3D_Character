"""Gate2 clone-only bone axis & hierarchy normalization."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import FOOT_SLIDE_INHERITED, GATE2_PARAMETERS, parameter_hash


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Gate2Result:
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
            "head": (round(float(b.head_local.x), 8), round(float(b.head_local.y), 8), round(float(b.head_local.z), 8)),
            "tail": (round(float(b.tail_local.x), 8), round(float(b.tail_local.y), 8), round(float(b.tail_local.z), 8)),
            "use_connect": bool(b.use_connect),
        }
    return out


def _clear_prior_gate2():
    import bpy

    prefixes = ("NURION_BodyMotion", "NURION_BodyRig", "NURION_BodyAxis")
    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.name.startswith("NURION_BodyRig"):
            bpy.data.armatures.remove(arm, do_unlink=True)
    for col_name in ("NURION_BodyMotionClone",):
        col = bpy.data.collections.get(col_name)
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


def _clone_rig_and_mesh(source_arm, source_mesh):
    """Duplicate armature + mesh into clone collection. Source objects untouched."""
    import bpy

    _clear_prior_gate2()
    col = _ensure_collection("NURION_BodyMotionClone")
    names = GATE2_PARAMETERS["objects"]

    # Duplicate armature
    arm_data = source_arm.data.copy()
    arm_data.name = "NURION_BodyRigClone_Data"
    clone_arm = bpy.data.objects.new(names["candidateArmature"], arm_data)
    clone_arm.matrix_world = source_arm.matrix_world.copy()
    col.objects.link(clone_arm)

    # Duplicate mesh
    mesh_data = source_mesh.data.copy()
    mesh_data.name = "NURION_BodyMotionCandidate_Mesh"
    clone_mesh = bpy.data.objects.new(names["candidateMesh"], mesh_data)
    clone_mesh.matrix_world = source_mesh.matrix_world.copy()
    col.objects.link(clone_mesh)

    # Preserve world transform while parenting to clone armature
    mw = clone_mesh.matrix_world.copy()
    clone_mesh.parent = clone_arm
    clone_mesh.matrix_world = mw
    for mod in list(clone_mesh.modifiers):
        clone_mesh.modifiers.remove(mod)
    mod = clone_mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = clone_arm
    # Copy vertex groups already exist on duplicated mesh data

    # Copy animation action + Blender 4.4+/5.x action slot (slot required or clone stays at rest)
    if source_arm.animation_data and source_arm.animation_data.action:
        if clone_arm.animation_data is None:
            clone_arm.animation_data_create()
        clone_arm.animation_data.action = source_arm.animation_data.action
        src_slot = getattr(source_arm.animation_data, "action_slot", None)
        if src_slot is not None:
            try:
                clone_arm.animation_data.action_slot = src_slot
            except Exception:
                action = source_arm.animation_data.action
                slots = getattr(action, "slots", None)
                if slots and len(slots) > 0:
                    clone_arm.animation_data.action_slot = slots[0]

    # Control / evidence empties
    for key in ("control", "evidence"):
        n = names[key]
        obj = bpy.data.objects.new(n, None)
        obj.empty_display_type = "PLAIN_AXES"
        col.objects.link(obj)

    bpy.context.view_layer.update()
    return clone_arm, clone_mesh


def _chain_continuity(arm, chain: List[str]) -> Dict:
    missing = [n for n in chain if arm.data.bones.get(n) is None]
    breaks = []
    for i in range(1, len(chain)):
        child = arm.data.bones.get(chain[i])
        parent = arm.data.bones.get(chain[i - 1])
        if child is None or parent is None:
            continue
        if child.parent is None or child.parent.name != parent.name:
            # allow non-direct if intermediate? for declared chain must be direct
            breaks.append({"child": chain[i], "expectedParent": chain[i - 1], "actualParent": child.parent.name if child.parent else None})
    return {"chain": chain, "missing": missing, "breaks": breaks, "ok": not missing and not breaks}


def _axis_align_score(arm, chain: List[str]) -> Dict:
    """Bone Y (length) direction should roughly align with head→child head."""
    import mathutils

    dots = []
    abnormal = []
    for i in range(len(chain) - 1):
        a = arm.data.bones.get(chain[i])
        b = arm.data.bones.get(chain[i + 1])
        if a is None or b is None:
            continue
        y_axis = (a.tail_local - a.head_local).normalized()
        to_child = (b.head_local - a.head_local)
        if to_child.length < 1e-8:
            continue
        to_child.normalize()
        d = float(y_axis.dot(to_child))
        dots.append({"from": chain[i], "to": chain[i + 1], "dot": round(d, 5)})
        if d < float(GATE2_PARAMETERS["axisDotMin"]):
            abnormal.append({"from": chain[i], "to": chain[i + 1], "dot": round(d, 5)})
    return {"dots": dots, "abnormal": abnormal, "ok": len(abnormal) == 0}


def _lr_swap_check(arm) -> Dict:
    """At REST, Left* bones should not sit on the right of Right* (character local +X = left in Blender FBX often)."""
    import bpy

    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    swaps = []
    details = []
    # Use armature local X of head
    for left_n, right_n in GATE2_PARAMETERS["lrPairs"]:
        lb = arm.data.bones.get(left_n)
        rb = arm.data.bones.get(right_n)
        if lb is None or rb is None:
            continue
        lx = float(lb.head_local.x)
        rx = float(rb.head_local.x)
        # Meshy/Blender: typically Left has +X, Right has -X (or reverse). Detect inconsistency of sign pattern.
        details.append({"pair": [left_n, right_n], "leftX": round(lx, 5), "rightX": round(rx, 5)})
        # Swap if left and right are on wrong sides relative to each other vs naming
        # Accept either convention globally; detect crossed pair: leftX and rightX inverted vs majority
    # Majority vote for Left X sign
    left_xs = [d["leftX"] for d in details]
    if left_xs:
        prefer_left_positive = sum(1 for x in left_xs if x > 0) >= sum(1 for x in left_xs if x < 0)
        for d in details:
            left_ok = (d["leftX"] > d["rightX"]) if prefer_left_positive else (d["leftX"] < d["rightX"])
            # also require opposite sides of mid roughly
            if not left_ok:
                swaps.append(d)
    return {"pairsChecked": len(details), "swaps": swaps, "ok": len(swaps) == 0, "details": details}


def _normalize_clone_rolls(clone_arm) -> Dict:
    """Safe roll normalization toward child on clone edit bones only."""
    import bpy

    bpy.context.view_layer.objects.active = clone_arm
    clone_arm.select_set(True)
    # Enter edit mode and recalculate rolls aligned to child / global Y fallback
    changed = 0
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        ebones = clone_arm.data.edit_bones
        for chain in GATE2_PARAMETERS["chains"].values():
            for i in range(len(chain) - 1):
                eb = ebones.get(chain[i])
                child = ebones.get(chain[i + 1])
                if eb is None or child is None:
                    continue
                before = float(eb.roll)
                # Align roll so bone Z aims consistently; use Blender helper via vector
                direction = (child.head - eb.head).normalized()
                if direction.length > 1e-8:
                    eb.align_roll(direction)
                after = float(eb.roll)
                if abs(after - before) > 1e-6:
                    changed += 1
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    return {"rollsAdjusted": changed}


def _rest_immutable(before: Dict, after: Dict) -> Dict:
    length_breaks = []
    parent_breaks = []
    for name, a in before.items():
        b = after.get(name)
        if b is None:
            parent_breaks.append({"bone": name, "reason": "MISSING_AFTER"})
            continue
        if a["parent"] != b["parent"]:
            parent_breaks.append({"bone": name, "before": a["parent"], "after": b["parent"]})
        rel = abs(a["length"] - b["length"]) / max(a["length"], 1e-8)
        if rel > float(GATE2_PARAMETERS["lengthRelEps"]) and abs(a["length"] - b["length"]) > 1e-7:
            length_breaks.append({"bone": name, "before": a["length"], "after": b["length"]})
    return {
        "parentBreaks": parent_breaks,
        "lengthBreaks": length_breaks,
        "ok": not parent_breaks and not length_breaks,
    }


def _motion_drift(source_arm, clone_arm, frame_start: int, frame_end: int) -> Dict:
    import bpy

    bones = ["Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot"]
    n = int(GATE2_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(frame_start), int(frame_end) + 1))
    if len(frames) > n:
        sample = [frames[int(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
    else:
        sample = frames
    eps = float(GATE2_PARAMETERS["motionDriftEpsilonM"])
    max_drift = 0.0
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
            sw = source_arm.matrix_world @ sp.matrix
            cw = clone_arm.matrix_world @ cp.matrix
            s = sw.to_translation()
            c = cw.to_translation()
            d = math.sqrt((s.x - c.x) ** 2 + (s.y - c.y) ** 2 + (s.z - c.z) ** 2)
            if d > max_drift:
                max_drift = d
                worst = {"frame": fr, "bone": bn, "driftM": round(d, 6)}
    return {
        "maxDriftM": round(max_drift, 6),
        "worst": worst,
        "epsilonM": eps,
        "ok": max_drift <= eps,
        "samples": len(sample),
    }


def run_gate2_once(*, fbx_path: Path, mesh_name: str = "") -> Dict:
    import bpy

    # Identify source objects
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not arms or not meshes:
        raise RuntimeError("source armature/mesh missing")
    source_arm = arms[0]
    source_mesh = bpy.data.objects.get(mesh_name) if mesh_name else None
    if source_mesh is None:
        # prefer skinned
        source_mesh = meshes[0]
        for m in meshes:
            for mod in m.modifiers:
                if mod.type == "ARMATURE":
                    source_mesh = m
                    break

    src_mesh_before = _snapshot_mesh(source_mesh)
    src_arm_before = _snapshot_arm_rest(source_arm)

    # Bind action on source (preserve existing slot if present)
    if bpy.data.actions:
        if source_arm.animation_data is None:
            source_arm.animation_data_create()
        action = bpy.data.actions[0]
        source_arm.animation_data.action = action
        if getattr(source_arm.animation_data, "action_slot", None) is None:
            slots = getattr(action, "slots", None)
            if slots and len(slots) > 0:
                try:
                    source_arm.animation_data.action_slot = slots[0]
                except Exception:
                    pass
        fs = int(action.frame_range[0])
        fe = int(action.frame_range[1])
    else:
        fs, fe = 1, 231

    clone_arm, clone_mesh = _clone_rig_and_mesh(source_arm, source_mesh)
    clone_rest_before = _snapshot_arm_rest(clone_arm)

    chains = GATE2_PARAMETERS["chains"]
    axis_gate = set(GATE2_PARAMETERS["axisGateChains"])
    continuity = {k: _chain_continuity(clone_arm, v) for k, v in chains.items()}
    axis = {k: _axis_align_score(clone_arm, v) for k, v in chains.items()}
    lr = _lr_swap_check(clone_arm)
    # restore pose evaluation after REST check
    clone_arm.data.pose_position = "POSE"
    source_arm.data.pose_position = "POSE"

    # Roll normalize only for limb-axis failures; discard if Formal Bow drift exceeds tolerance
    abnormal_before = sum(len(axis[k]["abnormal"]) for k in axis_gate if k in axis)
    norm = {"rollsAdjusted": 0, "applied": False, "reverted": False}
    if abnormal_before > 0:
        norm = _normalize_clone_rolls(clone_arm)
        norm["applied"] = True
        drift_try = _motion_drift(source_arm, clone_arm, fs, fe)
        if not drift_try["ok"]:
            clone_arm, clone_mesh = _clone_rig_and_mesh(source_arm, source_mesh)
            clone_rest_before = _snapshot_arm_rest(clone_arm)
            continuity = {k: _chain_continuity(clone_arm, v) for k, v in chains.items()}
            axis = {k: _axis_align_score(clone_arm, v) for k, v in chains.items()}
            lr = _lr_swap_check(clone_arm)
            clone_arm.data.pose_position = "POSE"
            source_arm.data.pose_position = "POSE"
            norm = {"rollsAdjusted": 0, "applied": False, "reverted": True, "reason": "MOTION_DRIFT_AFTER_ROLL"}

    clone_rest_after = _snapshot_arm_rest(clone_arm)
    rest_immut = _rest_immutable(clone_rest_before, clone_rest_after)
    axis_after = {k: _axis_align_score(clone_arm, v) for k, v in chains.items()}
    drift = _motion_drift(source_arm, clone_arm, fs, fe)

    src_mesh_after = _snapshot_mesh(source_mesh)
    src_arm_after = _snapshot_arm_rest(source_arm)
    src_mut = 0 if src_mesh_before == src_mesh_after and src_arm_before == src_arm_after else 1

    hierarchy_breaks = sum(len(v["breaks"]) + len(v["missing"]) for v in continuity.values())
    abnormal_axis = sum(len(axis_after[k]["abnormal"]) for k in axis_gate if k in axis_after)
    spine_axis_notes = axis_after.get("spine", {}).get("abnormal", [])
    lr_swaps = len(lr["swaps"])

    ctrl = bpy.data.objects.get(GATE2_PARAMETERS["objects"]["control"])
    if ctrl:
        ctrl["mode"] = "CLONE_AXIS_NORMALIZE"
        ctrl["footSlideInherited"] = FOOT_SLIDE_INHERITED
    evid = bpy.data.objects.get(GATE2_PARAMETERS["objects"]["evidence"])
    if evid:
        evid["hierarchyBreaks"] = hierarchy_breaks
        evid["lrSwaps"] = lr_swaps
        evid["abnormalAxis"] = abnormal_axis

    stable = {
        "parameterHash": parameter_hash(),
        "hierarchyBreaks": hierarchy_breaks,
        "lrSwaps": lr_swaps,
        "abnormalAxis": abnormal_axis,
        "spineAxisAbnormal": len(spine_axis_notes),
        "sourceMutation": src_mut,
        "restImmutableOk": rest_immut["ok"],
        "motionDriftOk": drift["ok"],
        "maxDriftM": drift["maxDriftM"],
        "rollsAdjusted": norm["rollsAdjusted"],
        "footSlideInherited": FOOT_SLIDE_INHERITED,
        "fbxSha256": _sha_file(fbx_path),
    }
    return {
        "stable": stable,
        "continuity": continuity,
        "axisBefore": axis,
        "axisAfter": axis_after,
        "lr": lr,
        "normalize": norm,
        "restImmutable": rest_immut,
        "motionDrift": drift,
        "frameStart": fs,
        "frameEnd": fe,
        "sourceArm": source_arm.name,
        "cloneArm": clone_arm.name,
        "cloneMesh": clone_mesh.name,
        "srcMut": src_mut,
    }


def build_validation(stable: Dict, determinism: str) -> Dict:
    gates = {
        "SOURCE_ZIP_FBX_MUTATION": 0,  # enforced externally + src mut
        "SOURCE_CHARACTER_MUTATION": int(stable.get("sourceMutation", 1)),
        "HIERARCHY_BREAK": int(stable.get("hierarchyBreaks", 1)),
        "LR_SWAP": int(stable.get("lrSwaps", 1)),
        "ABNORMAL_AXIS": int(stable.get("abnormalAxis", 1)),
        "REST_PARENT_LENGTH_IMMUTABLE": "PASS" if stable.get("restImmutableOk") else "FAIL",
        "MOTION_DRIFT": "PASS" if stable.get("motionDriftOk") else "FAIL",
        "FOOT_SLIDE_FIXED": "DENY_INHERITED",
        "FOOT_SLIDE_INHERITED": int(stable.get("footSlideInherited", FOOT_SLIDE_INHERITED)),
        "DETERMINISM_3X": determinism,
        "V04_MUTATION": "DENY",
    }

    def ok(k, v):
        if k in ("REST_PARENT_LENGTH_IMMUTABLE", "MOTION_DRIFT", "DETERMINISM_3X"):
            return v == "PASS"
        if k in ("FOOT_SLIDE_FIXED", "V04_MUTATION"):
            return v in ("DENY_INHERITED", "DENY")
        if k == "FOOT_SLIDE_INHERITED":
            return v == FOOT_SLIDE_INHERITED
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    # limitations: roll adjustments are OK; foot slide inherited is expected
    limitations = []
    if gates["FOOT_SLIDE_INHERITED"] > 0:
        limitations.append("FOOT_SLIDE_INHERITED_TO_GATE3")
    if int(stable.get("rollsAdjusted", 0)) > 0:
        limitations.append("CLONE_ROLL_NORMALIZED")
    if int(stable.get("spineAxisAbnormal", 0)) > 0:
        limitations.append("SPINE_ROOT_AXIS_NONCOLINEAR_REPORTED")

    if fails:
        verdict = "FAIL"
    elif limitations:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    return {
        "schema": "NURION_V05_GATE2_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": limitations,
        "verdict": verdict,
        "parameterHash": parameter_hash(),
    }


def run_gate2(
    *,
    fbx_path: Path,
    mesh_name: str = "",
    runs: int = 3,
    clean_import_cb=None,
) -> Gate2Result:
    notes: List[str] = []
    results = []
    for i in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(run_gate2_once(fbx_path=fbx_path, mesh_name=mesh_name))

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
        "schema": "NURION_V05_GATE2_PROFILE",
        "version": GATE2_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE2_PARAMETERS["gate1ParameterHash"],
        "objects": GATE2_PARAMETERS["objects"],
        "sourceArm": last["sourceArm"],
        "cloneArm": last["cloneArm"],
        "cloneMesh": last["cloneMesh"],
        "frameStart": last["frameStart"],
        "frameEnd": last["frameEnd"],
        "continuity": last["continuity"],
        "axisAfter": last["axisAfter"],
        "lr": {"ok": last["lr"]["ok"], "swaps": last["lr"]["swaps"], "pairsChecked": last["lr"]["pairsChecked"]},
        "normalize": last["normalize"],
        "restImmutable": last["restImmutable"],
        "motionDrift": last["motionDrift"],
        "footSlideInherited": FOOT_SLIDE_INHERITED,
        "footSlideFix": "DENY_INHERIT_TO_GATE3",
        "determinism3x": det,
        "v04Mutation": "DENY",
        "sourceZipFbxMutation": "DENY",
        "production": "NO-GO",
        "notes": notes,
    }
    return Gate2Result(
        profile=profile,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
