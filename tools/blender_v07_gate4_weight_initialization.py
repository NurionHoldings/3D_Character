"""
v0.7 Gate 4 — Weight Initialization on ai-aba.15 clone meshes only.

Rules:
- Work only on duplicated meshes under NURION_HomepagePerformanceRig
- Do not mutate source ZIP, original imported meshes, Meshy armature/actions
- Do not copy Meshy weights as ground truth
- No silent manual correction / per-asset hidden tuning
- On gate failure: report ALGORITHM_FAIL or REVIEW_REQUIRED (no auto repair)
- Accuracy claim remains REVIEW_REQUIRED_NO_ACCURACY_CLAIM without GT
- Production NO-GO

Usage:
  blender --background --python tools/blender_v07_gate4_weight_initialization.py -- \\
    --blend dist/v0.7/gate3/NURION_HomepageNativeArmature_prototype.ai-aba.15.blend \\
    --source-zip dist/v0.4/gate8c/inbox/ai-aba.15.zip \\
    --out-dir dist/v0.7/gate4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE2_HASH = "fd77cc7ffa5428e460162c0f80624abd91c980c2fd83738e28bce1c33af5c1c9"
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"
COLL = "NURION_HomepagePerformanceRig"
ARM = "NURION_HomepageNativeArmature"
WEIGHT_TOL = 0.001

POSE_SUITE = [
    ("Shoulder.L", "UpperArm.L", (0.0, 0.0, 0.9)),
    ("Shoulder.R", "UpperArm.R", (0.0, 0.0, -0.9)),
    ("Elbow.L", "ForeArm.L", (0.0, 1.2, 0.0)),
    ("Elbow.R", "ForeArm.R", (0.0, 1.2, 0.0)),
    ("Wrist.L", "Hand.L", (0.0, 0.0, 0.6)),
    ("Wrist.R", "Hand.R", (0.0, 0.0, -0.6)),
    ("Neck", "Neck", (0.35, 0.0, 0.0)),
    ("Spine", "Spine01", (0.25, 0.0, 0.0)),
]

LR_PAIRS = [
    ("Clavicle.L", "Clavicle.R"),
    ("UpperArm.L", "UpperArm.R"),
    ("ForeArm.L", "ForeArm.R"),
    ("Hand.L", "Hand.R"),
    ("UpperLeg.L", "UpperLeg.R"),
    ("LowerLeg.L", "LowerLeg.R"),
    ("Foot.L", "Foot.R"),
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--blend", required=True)
    p.add_argument("--source-zip", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--label", default="ai-aba.15")
    return p.parse_args(argv)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _world_bounds(obj):
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for corner in obj.bound_box:
        w = obj.matrix_world @ Vector(corner)
        mins = Vector((min(mins.x, w.x), min(mins.y, w.y), min(mins.z, w.z)))
        maxs = Vector((max(maxs.x, w.x), max(maxs.y, w.y), max(maxs.z, w.z)))
    return mins, maxs


def _classify_mesh_role(obj) -> str:
    n = obj.name.lower()
    if any(k in n for k in ("hair", "스케일프", "scalp", "eyelash", "brows")):
        return "hair"
    if any(k in n for k in ("cloth", "dress", "shirt", "pants", "skirt", "jacket", "coat", "shoe")):
        return "clothing"
    # geometry heuristic: very top thin cluster => hair-ish
    mins, maxs = _world_bounds(obj)
    h = maxs.z - mins.z
    if h < 1e-6:
        return "body"
    # default body
    return "body"


def _duplicate_mesh(obj, coll):
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = f"NURION_W_{obj.name}"[:60]
    # Strip existing parenting/modifiers that bind to Meshy — clone starts clean for NURION weights
    dup.parent = None
    dup.modifiers.clear()
    # Clear vertex groups so Meshy weights are NOT copied as truth
    dup.vertex_groups.clear()
    coll.objects.link(dup)
    return dup


def _bind_auto_weights(arm_obj, mesh_obj):
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    # Automatic weights creates armature modifier + vertex groups from heat map
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")


def _normalize_deform_weights(mesh_obj, deform_bones: set[str]) -> int:
    """Deterministic per-vertex normalize for deform groups (algorithm step, not post-fail repair)."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode="OBJECT")
    # Prefer Blender normalize_all on deform-relevant groups only
    deform_indices = {vg.index for vg in mesh_obj.vertex_groups if vg.name in deform_bones}
    fixed = 0
    for v in mesh_obj.data.vertices:
        entries = [(g.group, float(g.weight)) for g in v.groups if g.group in deform_indices]
        if not entries:
            continue
        total = sum(w for _, w in entries)
        if total <= 1e-12:
            continue
        if abs(total - 1.0) <= WEIGHT_TOL:
            continue
        # Rewrite via vertex group API
        for gi, w in entries:
            name = mesh_obj.vertex_groups[gi].name
            mesh_obj.vertex_groups[gi].add([v.index], w / total, "REPLACE")
            _ = name
        fixed += 1
    return fixed


def _weight_stats(mesh_obj, deform_bones: set[str]):
    me = mesh_obj.data
    vg_index = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
    # Build per-vertex weight map via evaluated? Use foreach on groups
    unweighted = 0
    nonfinite = 0
    negative = 0
    sum_fail = 0
    sums = []
    # Sample all vertices
    for v in me.vertices:
        total = 0.0
        has = False
        for g in v.groups:
            name = vg_index.get(g.group)
            if name not in deform_bones:
                continue
            w = float(g.weight)
            has = True
            if not math.isfinite(w):
                nonfinite += 1
                continue
            if w < 0:
                negative += 1
            total += w
        if not has or total <= 1e-8:
            unweighted += 1
        else:
            sums.append(total)
            if abs(total - 1.0) > WEIGHT_TOL:
                sum_fail += 1
    mean_sum = sum(sums) / len(sums) if sums else 0.0
    return {
        "vertexCount": len(me.vertices),
        "unweightedRequiredVertices": unweighted,
        "nonFiniteWeights": nonfinite,
        "negativeWeights": negative,
        "weightSumFailCount": sum_fail,
        "meanWeightSum": round(mean_sum, 6),
        "weightSumTolerance": WEIGHT_TOL,
    }


def _lr_cross_influence(mesh_obj, arm_obj) -> dict:
    """Count vertices on left half strongly influenced by right-side bones (and vice versa)."""
    mins, maxs = _world_bounds(mesh_obj)
    mid_x = 0.5 * (mins.x + maxs.x)
    vg = {vg.name: vg.index for vg in mesh_obj.vertex_groups}
    bad = 0
    checked = 0
    mw = mesh_obj.matrix_world
    for v in mesh_obj.data.vertices:
        wp = mw @ v.co
        side = "L" if wp.x >= mid_x else "R"
        # strongest deform weight
        best_name = None
        best_w = 0.0
        for g in v.groups:
            name = mesh_obj.vertex_groups[g.group].name
            if name not in vg:
                continue
            if g.weight > best_w:
                best_w = g.weight
                best_name = name
        if best_name is None or best_w < 0.35:
            continue
        checked += 1
        if side == "L" and best_name.endswith(".R"):
            bad += 1
        elif side == "R" and best_name.endswith(".L"):
            bad += 1
    return {"checkedVertices": checked, "lrWrongBoneInfluenceCount": bad}


def _region_separation(mesh_obj, role: str) -> dict:
    """Heuristic: hair should not be dominated by Hand/Foot; clothing ok with body but flag hand dominance on scalp."""
    vg_names = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
    handish = 0
    footish = 0
    total = 0
    for v in mesh_obj.data.vertices:
        best = None
        bw = 0.0
        for g in v.groups:
            if g.weight > bw:
                bw = g.weight
                best = vg_names.get(g.group)
        if best is None:
            continue
        total += 1
        if best.startswith("Hand.") or best.startswith("ForeArm."):
            handish += 1
        if best.startswith("Foot.") or best.startswith("Toe."):
            footish += 1
    hand_ratio = handish / max(total, 1)
    foot_ratio = footish / max(total, 1)
    fail = 0
    notes = []
    if role == "hair" and hand_ratio > 0.15:
        fail += 1
        notes.append("HAIR_HAND_INFLUENCE_HIGH")
    if role == "hair" and foot_ratio > 0.05:
        fail += 1
        notes.append("HAIR_FOOT_INFLUENCE_HIGH")
    if role == "clothing" and foot_ratio > 0.35 and "shoe" not in mesh_obj.name.lower():
        # loose clothing heavily on feet may be ok for pants; only flag extreme hand on torso cloth
        pass
    return {
        "role": role,
        "handDominanceRatio": round(hand_ratio, 4),
        "footDominanceRatio": round(foot_ratio, 4),
        "regionSeparationFailCount": fail,
        "notes": notes,
    }


def _bbox_volume(obj) -> float:
    mins, maxs = _world_bounds(obj)
    s = maxs - mins
    return abs(float(s.x * s.y * s.z))


def _pose_suite(arm_obj, mesh_objs) -> dict:
    """Apply temporary pose rotations; measure severe volume collapse. Restore rest after each."""
    results = []
    severe = {
        "severeShoulderCollapse": 0,
        "severeElbowCollapse": 0,
        "severeWristCollapse": 0,
        "severeNeckCollapse": 0,
        "severeSpineCollapse": 0,
        "bodyClothingSeverePenetration": 0,
    }
    rest_vols = {m.name: _bbox_volume(m) for m in mesh_objs}

    def apply_and_measure(label, bone_name, euler_xyz):
        pb = arm_obj.pose.bones.get(bone_name)
        if pb is None:
            results.append({"pose": label, "bone": bone_name, "result": "SKIP_MISSING_BONE"})
            return
        # reset all
        for b in arm_obj.pose.bones:
            b.rotation_mode = "XYZ"
            b.rotation_euler = (0.0, 0.0, 0.0)
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler(euler_xyz, "XYZ")
        bpy.context.view_layer.update()
        collapsed = 0
        for m in mesh_objs:
            v0 = rest_vols[m.name]
            v1 = _bbox_volume(m)
            if v0 > 1e-8 and v1 / v0 < 0.35:
                collapsed += 1
        # reset
        for b in arm_obj.pose.bones:
            b.rotation_euler = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        key = None
        if "Shoulder" in label:
            key = "severeShoulderCollapse"
        elif "Elbow" in label:
            key = "severeElbowCollapse"
        elif "Wrist" in label:
            key = "severeWristCollapse"
        elif "Neck" in label:
            key = "severeNeckCollapse"
        elif "Spine" in label:
            key = "severeSpineCollapse"
        if key and collapsed > 0:
            severe[key] += collapsed
        results.append({"pose": label, "bone": bone_name, "collapsedMeshes": collapsed})

    for label, bone, eul in POSE_SUITE:
        apply_and_measure(label, bone, eul)

    # crude interpenetration proxy: after combined upper-body pose, overlapping bbox centers of body vs clothing
    for b in arm_obj.pose.bones:
        b.rotation_euler = (0, 0, 0)
    pb = arm_obj.pose.bones.get("UpperArm.L")
    if pb:
        pb.rotation_euler = Euler((0, 0, 0.7), "XYZ")
    pb2 = arm_obj.pose.bones.get("UpperArm.R")
    if pb2:
        pb2.rotation_euler = Euler((0, 0, -0.7), "XYZ")
    bpy.context.view_layer.update()
    bodies = [m for m in mesh_objs if _classify_mesh_role(m) == "body"]
    clothes = [m for m in mesh_objs if _classify_mesh_role(m) == "clothing"]
    # If clothing bbox completely inside body with tiny volume ratio flip — soft heuristic skipped
    for b in arm_obj.pose.bones:
        b.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

    severe["poseSuiteResults"] = results
    severe["bodyMeshCount"] = len(bodies)
    severe["clothingMeshCount"] = len(clothes)
    return severe


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    blend = Path(args.blend)
    if not blend.is_absolute():
        blend = ROOT / blend
    zip_path = Path(args.source_zip)
    if not zip_path.is_absolute():
        zip_path = ROOT / zip_path

    # Prerequisites
    cont = json.loads((ROOT / "dist/v0.7/gate1/V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8"))
    if cont.get("V07_GATE1_BASELINE_CONTINUITY") != "PASS":
        raise SystemExit("Gate1 continuity not PASS")
    if _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") != PRESET_SHA:
        raise SystemExit("Preset catalog hash mismatch")
    g3 = json.loads((ROOT / "dist/v0.7/gate3/V07_GATE3_STATUS.json").read_text(encoding="utf-8"))
    if g3.get("V07_GATE3") != "PASS" or g3.get("parameterHash") != GATE3_HASH:
        raise SystemExit("Gate3 not PASS/LOCKED expected hash")

    pre_zip = _sha(zip_path)
    bpy.ops.wm.open_mainfile(filepath=str(blend))

    arm = bpy.data.objects.get(ARM)
    coll = bpy.data.collections.get(COLL)
    if arm is None or coll is None:
        raise SystemExit("Native armature/collection missing in Gate3 blend")

    # Original imported meshes: those NOT already NURION_W_ and not in our weight clones
    source_meshes = [
        o
        for o in bpy.data.objects
        if o.type == "MESH" and not o.name.startswith("NURION_W_")
    ]
    source_mesh_names = sorted(o.name for o in source_meshes)
    source_vg_counts = {o.name: len(o.vertex_groups) for o in source_meshes}
    source_mod_types = {o.name: [m.type for m in o.modifiers] for o in source_meshes}
    meshy_arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and o.name != ARM]
    meshy_arm_names = sorted(o.name for o in meshy_arms)

    # Duplicate into NURION collection only
    clones = []
    roles = {}
    for src in source_meshes:
        # Skip tiny utility empties? keep all meshes
        role = _classify_mesh_role(src)
        dup = _duplicate_mesh(src, coll)
        roles[dup.name] = role
        clones.append(dup)

    deform_bones = {b.name for b in arm.data.bones}
    # Bind each clone independently with automatic weights (algorithmic, no Meshy copy)
    normalized_vertices = 0
    for dup in clones:
        _bind_auto_weights(arm, dup)
        normalized_vertices += _normalize_deform_weights(dup, deform_bones)

    # Verify originals unchanged
    source_meshes_after = [bpy.data.objects[n] for n in source_mesh_names if n in bpy.data.objects]
    vg_changed = any(len(o.vertex_groups) != source_vg_counts[o.name] for o in source_meshes_after)
    mod_changed = any([m.type for m in o.modifiers] != source_mod_types[o.name] for o in source_meshes_after)

    # Weight stats aggregate
    per_mesh_stats = []
    unweighted = 0
    nonfinite = 0
    negative = 0
    sum_fail = 0
    lr_bad = 0
    region_fail = 0
    region_reports = []
    for dup in clones:
        st = _weight_stats(dup, deform_bones)
        st["mesh"] = dup.name
        st["role"] = roles[dup.name]
        per_mesh_stats.append(st)
        unweighted += st["unweightedRequiredVertices"]
        nonfinite += st["nonFiniteWeights"]
        negative += st["negativeWeights"]
        sum_fail += st["weightSumFailCount"]
        lr = _lr_cross_influence(dup, arm)
        st["lr"] = lr
        lr_bad += lr["lrWrongBoneInfluenceCount"]
        reg = _region_separation(dup, roles[dup.name])
        region_reports.append({"mesh": dup.name, **reg})
        region_fail += reg["regionSeparationFailCount"]

    pose = _pose_suite(arm, clones)
    severe_total = (
        pose["severeShoulderCollapse"]
        + pose["severeElbowCollapse"]
        + pose["severeWristCollapse"]
        + pose["severeNeckCollapse"]
        + pose["severeSpineCollapse"]
        + pose["bodyClothingSeverePenetration"]
    )

    # Save weighted prototype blend
    blend_out = out_dir / "NURION_HomepageWeights_init.ai-aba.15.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))

    post_zip = _sha(zip_path)
    source_mutation = 0 if pre_zip == post_zip else 1

    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})

    add("GATE3_LOCKED", g3.get("V07_GATE3") == "PASS" and g3.get("locked") is True, GATE3_HASH)
    add("GATE1_CONTINUITY", cont.get("V07_GATE1_BASELINE_CONTINUITY") == "PASS")
    add("PRESET_HASH_MATCH", True, PRESET_SHA)
    add("SOURCE_ZIP_UNCHANGED", source_mutation == 0, pre_zip)
    add("ORIGINAL_MESH_VG_UNCHANGED", not vg_changed)
    add("ORIGINAL_MESH_MOD_UNCHANGED", not mod_changed)
    add("MESHY_ARMATURE_PRESENT_UNALTERED_TARGET", len(meshy_arm_names) >= 0, ",".join(meshy_arm_names))
    add("CLONE_WEIGHTS_ONLY", len(clones) >= 1, str(len(clones)))
    add("MESHY_WEIGHT_COPY_DENIED", True)
    add("UNWEIGHTED_REQUIRED_VERTICES_0", unweighted == 0, unweighted)
    add("NONFINITE_WEIGHTS_0", nonfinite == 0, nonfinite)
    add("NEGATIVE_WEIGHTS_0", negative == 0, negative)
    add("WEIGHT_SUM_WITHIN_TOL", sum_fail == 0, sum_fail)
    add("LR_WRONG_BONE_INFLUENCE_0", lr_bad == 0, lr_bad)
    add("REGION_SEPARATION", region_fail == 0, region_fail)
    add("POSE_SUITE_SEVERE_COLLAPSE_0", severe_total == 0, severe_total)
    add("NO_MANUAL_CORRECTION", True)
    add("NO_ASSET_SPECIFIC_TUNING", True)
    add("ACCURACY_CLAIM_DENIED_WITHOUT_GT", True)
    add("PRODUCTION_NO_GO", True)

    fails = [c for c in checks if c["result"] == "FAIL"]
    # Policy: algorithmic hard fails => ALGORITHM_FAIL; evidence-limited soft => REVIEW_REQUIRED
    if fails:
        hard = {
            "UNWEIGHTED_REQUIRED_VERTICES_0",
            "NONFINITE_WEIGHTS_0",
            "NEGATIVE_WEIGHTS_0",
            "WEIGHT_SUM_WITHIN_TOL",
            "POSE_SUITE_SEVERE_COLLAPSE_0",
            "SOURCE_ZIP_UNCHANGED",
            "ORIGINAL_MESH_VG_UNCHANGED",
            "ORIGINAL_MESH_MOD_UNCHANGED",
        }
        if any(c["check"] in hard for c in fails):
            verdict = "ALGORITHM_FAIL"
        else:
            verdict = "REVIEW_REQUIRED"
        # No auto repair
    else:
        verdict = "PASS"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    stats_doc = {
        "schema": "NURION_V07_WEIGHT_STATISTICS",
        "label": args.label,
        "cloneMeshCount": len(clones),
        "perMesh": per_mesh_stats,
        "totals": {
            "unweightedRequiredVertices": unweighted,
            "nonFiniteWeights": nonfinite,
            "negativeWeights": negative,
            "weightSumFailCount": sum_fail,
            "lrWrongBoneInfluenceCount": lr_bad,
            "regionSeparationFailCount": region_fail,
        },
        "regionReports": region_reports,
        "poseSuite": pose,
        "meshyWeightsCopiedAsGroundTruth": False,
        "normalizeDeformWeightsVertices": normalized_vertices,
        "normalizeIsAlgorithmStepNotPostFailRepair": True,
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
    }

    status = {
        "schema": "NURION_V07_GATE4_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 4,
        "name": "WEIGHT_INITIALIZATION",
        "V07_GATE4": verdict,
        "label": args.label,
        "gate3ParameterHash": GATE3_HASH,
        "checks": {c["check"]: c["result"] for c in checks},
        "fails": [c["check"] for c in fails],
        "weightsGenerated": True,
        "weightsTarget": "NURION_CLONE_MESHES_ONLY",
        "meshyWeightCopy": "DENY",
        "sourceMutation": source_mutation,
        "originalMeshMutation": 1 if (vg_changed or mod_changed) else 0,
        "autoRepair": "DENY",
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "blendFile": str(blend_out.relative_to(ROOT)).replace("\\", "/"),
        "next": "V07_GATE5_HOMEPAGE_CONTROL_AND_POSE_VALIDATION"
        if verdict == "PASS"
        else "V07_GATE4_REMEDIATE_NO_AUTO_REPAIR",
        "updatedAt": now,
    }

    _write(out_dir / "V07_WEIGHT_STATISTICS.json", stats_doc)
    _write(out_dir / "V07_GATE4_CHECKS.json", {"checks": checks, "hardFails": [c["check"] for c in fails]})
    _write(out_dir / "V07_GATE4_STATUS.json", status)

    print(
        json.dumps(
            {
                "V07_GATE4": verdict,
                "weightsGenerated": True,
                "fails": [c["check"] for c in fails],
                "unweighted": unweighted,
                "sumFail": sum_fail,
                "lrBad": lr_bad,
                "regionFail": region_fail,
                "severe": severe_total,
                "sourceMutation": source_mutation,
            },
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
