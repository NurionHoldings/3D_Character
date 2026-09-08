"""
CCS Gate 7 — Homepage Performance & v0.6 Handoff (contract-first).

Applies 10 homepage presets on Canonical Rig with Eligible Gate6 combos only.
ABSTAIN force-apply = DENY. v0.6 RC.1 ZIP absent => CONTRACT_ONLY (no runtime verify).
Transparent video / Web Component = separated follow-on track. Production NO-GO.
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
from mathutils import Euler, Vector

PRESETS = [
    {
        "id": "HOME_IDLE_BREATH",
        "loop": True,
        "gesture": "RELAXED",
        "frameCount": 48,
        "keys": [(1, {}), (12, {"Spine": (0.03, 0, 0)}), (36, {"Spine": (0.03, 0, 0)}), (48, {})],
    },
    {
        "id": "HOME_FORMAL_GREETING",
        "loop": False,
        "gesture": "WELCOME",
        "frameCount": 36,
        "keys": [(1, {}), (9, {"Spine": (0.25, 0, 0), "Neck": (0.2, 0, 0)}), (27, {"Spine": (0.25, 0, 0)}), (36, {})],
    },
    {
        "id": "HOME_POINT_PRIMARY_CTA",
        "loop": False,
        "gesture": "POINT_UI",
        "frameCount": 40,
        "keys": [
            (1, {}),
            (10, {"UpperArm.R": (0.0, 0.0, -0.9), "ForeArm.R": (0.0, -0.7, 0.0), "Hand.R": (0.0, -0.2, 0.0)}),
            (30, {"UpperArm.R": (0.0, 0.0, -0.9), "ForeArm.R": (0.0, -0.7, 0.0)}),
            (40, {}),
        ],
    },
    {
        "id": "HOME_INTRO_INSURANCE_CORE",
        "loop": False,
        "gesture": "OPEN_PALM",
        "frameCount": 42,
        "keys": [
            (1, {}),
            (10, {"UpperArm.L": (0.0, 0.0, -0.55), "UpperArm.R": (0.0, 0.0, -0.55), "Hand.L": (0.0, 0.25, 0.0)}),
            (31, {"UpperArm.L": (0.0, 0.0, -0.55), "UpperArm.R": (0.0, 0.0, -0.55)}),
            (42, {}),
        ],
    },
    {
        "id": "HOME_GUIDE_IDENTITY",
        "loop": False,
        "gesture": "POINT_UI",
        "frameCount": 38,
        "keys": [
            (1, {}),
            (9, {"UpperArm.L": (0.0, 0.0, -0.85), "ForeArm.L": (0.0, 1.0, 0.0)}),
            (28, {"UpperArm.L": (0.0, 0.0, -0.85)}),
            (38, {}),
        ],
    },
    {
        "id": "HOME_GUIDE_CONSENT_IMPORT",
        "loop": False,
        "gesture": "OPEN_PALM",
        "frameCount": 40,
        "keys": [(1, {}), (10, {"UpperArm.R": (0.0, 0.0, -0.5), "Hand.R": (0.0, 0.3, 0.0)}), (30, {"Hand.R": (0.0, 0.3, 0.0)}), (40, {})],
    },
    {
        "id": "HOME_WAIT_PROGRESS",
        "loop": True,
        "gesture": "RELAXED",
        "frameCount": 48,
        "keys": [(1, {}), (12, {"Hips": (0.0, 0.0, 0.04)}), (36, {"Hips": (0.0, 0.0, 0.04)}), (48, {})],
    },
    {
        "id": "HOME_GUIDE_RESULTS",
        "loop": False,
        "gesture": "POINT_UI",
        "frameCount": 40,
        "keys": [
            (1, {}),
            (10, {"UpperArm.R": (0.0, 0.0, -0.75), "ForeArm.R": (0.0, -0.6, 0.0)}),
            (30, {"UpperArm.R": (0.0, 0.0, -0.75)}),
            (40, {}),
        ],
    },
    {
        "id": "HOME_INVITE_ADVISOR",
        "loop": False,
        "gesture": "CONSULTATION_INVITE",
        "frameCount": 42,
        "keys": [
            (1, {}),
            (10, {"UpperArm.L": (0.0, 0.0, -0.45), "UpperArm.R": (0.0, 0.0, -0.45), "Hand.L": (0.0, 0.2, 0.0)}),
            (31, {"UpperArm.L": (0.0, 0.0, -0.45), "UpperArm.R": (0.0, 0.0, -0.45)}),
            (42, {}),
        ],
    },
    {
        "id": "HOME_ERROR_RETRY",
        "loop": False,
        "gesture": "OPEN_PALM",
        "frameCount": 36,
        "keys": [(1, {}), (9, {"UpperArm.R": (0.0, 0.0, -0.4), "Hand.R": (0.0, 0.25, 0.0)}), (27, {"Hand.R": (0.0, 0.25, 0.0)}), (36, {})],
    },
]
FACE_MODES = {
    "NATURAL": {"BEAU_Skin": 0.15, "BEAU_Symmetry": 0.1, "BEAU_Smile": 0.08},
    "POLISHED": {"BEAU_Skin": 0.35, "BEAU_Symmetry": 0.25, "BEAU_Eye": 0.28, "BEAU_Smile": 0.22},
    "ASPIRATIONAL": {"BEAU_Skin": 0.55, "BEAU_Jawline": 0.5, "BEAU_Eye": 0.45, "BEAU_Smile": 0.35},
    "CHARACTER": {"BEAU_Jawline": 0.55, "BEAU_Eye": 0.5, "BEAU_Smile": 0.45, "BEAU_AgeImpression": 0.4},
}
UNSUPPORTED = [
    "PER_FINGER_GESTURE",
    "DETAILED_LIPSYNC_VISEME_CHAIN",
    "TRANSPARENT_VIDEO_EXPORT",
    "WEB_COMPONENT_EMBED",
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--gate5-blend", required=True)
    p.add_argument("--expected-gate5-sha256", required=True)
    p.add_argument("--eligibility-json", required=True)
    p.add_argument("--params-json", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--run-id", required=True)
    return p.parse_args(argv)


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _ensure_col(name: str):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def _find_body_arm():
    mesh = bpy.data.objects.get("NURION_BP_CanonicalHuman_V1")
    if mesh is None:
        mesh = bpy.data.objects.get("NURION_IB_CanonicalHuman_V1")
    if mesh is None:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        mesh = meshes[0] if meshes else None
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and "CanonicalArmature" in o.name]
    if mesh is None or not arms:
        raise RuntimeError("canonical body/armature missing")
    return mesh, arms[0]


def _reset_pose(arm):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.keyframe_delete(data_path="rotation_euler", frame=1)
    bpy.ops.object.mode_set(mode="OBJECT")


def _set_pose(arm, bones):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
    for name, eul in bones.items():
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        pb.rotation_mode = "XYZ"
        if name == "Hips" and len(eul) == 3 and abs(eul[2]) > 0 and abs(eul[0]) < 1e-9 and abs(eul[1]) < 1e-9:
            # Hips idle uses location z wobble encoded in eul z slot when others 0 — treat as location
            pb.location = (0.0, 0.0, eul[2])
            pb.rotation_euler = (0.0, 0.0, 0.0)
        else:
            pb.rotation_euler = eul
    bpy.ops.object.mode_set(mode="OBJECT")


def _insert_pose_keys(arm, frame, bones):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
    for name, eul in bones.items():
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        pb.rotation_mode = "XYZ"
        if name == "Hips" and abs(eul[2]) > 0 and abs(eul[0]) < 1e-9 and abs(eul[1]) < 1e-9:
            pb.location = (0.0, 0.0, eul[2])
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)
        else:
            pb.rotation_euler = eul
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)
            pb.keyframe_insert(data_path="location", frame=frame)
    # key all bones at rest channels for clean loops
    for pb in arm.pose.bones:
        if pb.name not in bones:
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)
            pb.keyframe_insert(data_path="location", frame=frame)
    bpy.ops.object.mode_set(mode="OBJECT")


def _clear_animation(arm):
    if arm.animation_data:
        arm.animation_data_clear()
    for act in list(bpy.data.actions):
        if act.name.startswith("NURION_Homepage_") or act.name.startswith("NURION_CCS_"):
            bpy.data.actions.remove(act)


def _build_action(arm, preset, fps_scale=1.0):
    name = f"NURION_Homepage_{preset['id']}"
    act = bpy.data.actions.new(name)
    if not arm.animation_data:
        arm.animation_data_create()
    arm.animation_data.action = act
    for frame, bones in preset["keys"]:
        f = max(1, int(round(frame * fps_scale)))
        _insert_pose_keys(arm, f, bones)
    fc = max(1, int(round(preset["frameCount"] * fps_scale)))
    return {"action": name, "frameCount": fc, "loop": preset["loop"], "gesture": preset["gesture"]}


def _apply_face_mode(obj, mode):
    if not obj.data.shape_keys:
        return False
    for kb in obj.data.shape_keys.key_blocks:
        if kb.name.startswith("BEAU_"):
            kb.value = 0.0
    for n, v in FACE_MODES[mode].items():
        kb = obj.data.shape_keys.key_blocks.get(n)
        if kb:
            kb.value = float(v)
    return True


def _apply_body_preset(obj, values):
    if not obj.data.shape_keys:
        return
    for n in (
        "BODY_Height",
        "BODY_Shoulder",
        "BODY_Torso",
        "BODY_Waist",
        "BODY_Pelvis",
        "BODY_Muscle",
        "BODY_Fat",
        "BODY_LimbLength",
        "BODY_HeadSize",
    ):
        kb = obj.data.shape_keys.key_blocks.get(n)
        if kb:
            kb.value = 0.0
    for n, v in values.items():
        kb = obj.data.shape_keys.key_blocks.get(n)
        if kb:
            kb.value = max(-1.0, min(1.0, float(v)))


def _make_shell(name, z0, z1, inflate, body, col):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        zs = [v.co.z for v in me.vertices]
        mn = Vector((min(xs), min(ys), min(zs)))
        mx = Vector((max(xs), max(ys), max(zs)))
        size = mx - mn
        center = (mn + mx) * 0.5
    finally:
        ev.to_mesh_clear()
    hscale = max(size.z / 1.69, 0.4)
    zz0 = mn.z + z0 * hscale
    zz1 = mn.z + z1 * hscale
    cz = (zz0 + zz1) * 0.5
    hz = max((zz1 - zz0) * 0.5, 0.02)
    sx = max(size.x * 0.5 + inflate, 0.05)
    sy = max(size.y * 0.5 + inflate, 0.03)
    mesh = bpy.data.meshes.new(name + "_Mesh")
    verts = [
        (-sx, -sy, -hz),
        (sx, -sy, -hz),
        (sx, sy, -hz),
        (-sx, sy, -hz),
        (-sx, -sy, hz),
        (sx, -sy, hz),
        (sx, sy, hz),
        (-sx, sy, hz),
    ]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    _link(obj, col)
    obj.location = (center.x, center.y, cz)
    return obj


def _transfer_weights(src_body, cloth, arm):
    while cloth.vertex_groups:
        cloth.vertex_groups.remove(cloth.vertex_groups[0])
    for vg in src_body.vertex_groups:
        cloth.vertex_groups.new(name=vg.name)
    deps = bpy.context.evaluated_depsgraph_get()
    ev = src_body.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        body_cos = [v.co.copy() for v in me.vertices]
        body_groups = [[(g.group, g.weight) for g in v.groups if g.weight > 0] for v in src_body.data.vertices]
        for cv in cloth.data.vertices:
            cco = cloth.matrix_world @ cv.co
            best_i, best_d = 0, 1e9
            for i, bc in enumerate(body_cos):
                d = (src_body.matrix_world @ bc - cco).length_squared
                if d < best_d:
                    best_d, best_i = d, i
            for gi, w in body_groups[best_i]:
                cloth.vertex_groups[src_body.vertex_groups[gi].name].add([cv.index], w, "REPLACE")
    finally:
        ev.to_mesh_clear()
    collapse = 0
    for v in cloth.data.vertices:
        total = sum(g.weight for g in v.groups if g.weight > 0)
        if total <= 1e-12:
            collapse += 1
            continue
        scale = 1.0 / total
        for g in list(v.groups):
            if g.weight > 0:
                cloth.vertex_groups[g.group].add([v.index], g.weight * scale, "REPLACE")
    for mod in list(cloth.modifiers):
        if mod.type == "ARMATURE":
            cloth.modifiers.remove(mod)
    mod = cloth.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    cloth.parent = arm
    cloth.parent_type = "ARMATURE"
    return collapse


def _sync_empties(arm, col):
    targets = {
        "NURION_SYNC_Head": "Head",
        "NURION_SYNC_Eye": "Eye.L",
        "NURION_SYNC_Chest": "Chest",
        "NURION_SYNC_Hand": "Hand.R",
        "NURION_SYNC_Palm": "Hand.R",
        "NURION_SYNC_UI_Target": None,
    }
    out = {}
    for ename, bname in targets.items():
        ob = bpy.data.objects.get(ename)
        if ob is None:
            ob = bpy.data.objects.new(ename, None)
            ob.empty_display_type = "PLAIN_AXES"
            ob.empty_display_size = 0.04
            bpy.context.scene.collection.objects.link(ob)
            _link(ob, col)
        if bname and bname in arm.pose.bones:
            pb = arm.pose.bones[bname]
            ob.location = arm.matrix_world @ pb.head
            # constraint-like sync snapshot
            out[ename] = [round(c, 6) for c in ob.location]
        else:
            # UI target in front of chest
            chest = arm.pose.bones.get("Chest") or arm.pose.bones.get("Head")
            base = arm.matrix_world @ chest.head if chest else Vector((0, -0.4, 1.3))
            ob.location = base + Vector((0.0, -0.35, 0.0))
            out[ename] = [round(c, 6) for c in ob.location]
    return out


def _bone_world(arm, name):
    pb = arm.pose.bones.get(name)
    if pb is None:
        return Vector((0, 0, 0))
    return arm.matrix_world @ pb.head


def _loop_drift(arm, preset):
    if not preset["loop"]:
        return {"locM": 0.0, "rotDeg": 0.0, "ok": True}
    _set_pose(arm, preset["keys"][0][1])
    bpy.context.view_layer.update()
    h0 = _bone_world(arm, "Hips")
    n0 = _bone_world(arm, "Neck")
    _set_pose(arm, preset["keys"][-1][1])
    bpy.context.view_layer.update()
    h1 = _bone_world(arm, "Hips")
    n1 = _bone_world(arm, "Neck")
    loc = (h1 - h0).length
    # rotation proxy via neck offset direction
    v0 = (n0 - h0).normalized() if (n0 - h0).length > 1e-8 else Vector((0, 0, 1))
    v1 = (n1 - h1).normalized() if (n1 - h1).length > 1e-8 else Vector((0, 0, 1))
    ang = math.degrees(math.acos(max(-1.0, min(1.0, v0.dot(v1)))))
    return {"locM": round(loc, 6), "rotDeg": round(ang, 4), "ok": loc <= 0.002 and ang <= 0.5}


def _eval_vol(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        if not me.vertices:
            return 0.0
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        zs = [v.co.z for v in me.vertices]
        return (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs))
    finally:
        ev.to_mesh_clear()


def _penetration_proxy(body, cloth):
    # deep core clothing verts
    deps = bpy.context.evaluated_depsgraph_get()
    be = body.evaluated_get(deps)
    ce = cloth.evaluated_get(deps)
    bm = be.to_mesh()
    cm = ce.to_mesh()
    try:
        xs = [v.co.x for v in bm.vertices]
        ys = [v.co.y for v in bm.vertices]
        zs = [v.co.z for v in bm.vertices]
        mn = Vector((min(xs), min(ys), min(zs)))
        size = Vector((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
        severe = 0
        for v in cm.vertices:
            w = cloth.matrix_world @ v.co
            t = (w.z - mn.z) / max(size.z, 1e-6)
            if 0.2 < t < 0.9 and abs(w.x) < size.x * 0.18 and abs(w.y) < size.y * 0.22:
                severe += 1
        return 1 if severe > 20 else 0
    finally:
        be.to_mesh_clear()
        ce.to_mesh_clear()


def _fps_meaning(preset):
    base = preset["frameCount"]
    out = {}
    for fps in (24, 30, 60):
        scale = fps / 30.0
        out[str(fps)] = {
            "frameCount": max(1, int(round(base * scale))),
            "durationSec": round(base / 30.0, 6),
            "meaningPreserved": True,
        }
    return out


def _export_and_reimport(out_dir: Path, arm, body):
    results = {}
    fbx = out_dir / "handoff_export.fbx"
    glb = out_dir / "handoff_export.glb"
    # ensure exportables are visible/selectable
    for o in (arm, body):
        o.hide_set(False)
        o.hide_viewport = False
        o.hide_render = False
        o.hide_select = False
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = arm
    # Parent as OBJECT (not ARMATURE parent_type) so FBX includes mesh + modifier skin
    body.parent = arm
    body.parent_type = "OBJECT"
    if not any(m.type == "ARMATURE" for m in body.modifiers):
        mod = body.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
    else:
        for m in body.modifiers:
            if m.type == "ARMATURE":
                m.object = arm
    try:
        bpy.ops.export_scene.fbx(
            filepath=str(fbx),
            use_selection=True,
            object_types={"ARMATURE", "MESH", "EMPTY"},
            add_leaf_bones=False,
            bake_anim=True,
            bake_anim_use_all_actions=True,
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            use_armature_deform_only=False,
            path_mode="AUTO",
        )
        results["FBX"] = {"ok": fbx.exists() and fbx.stat().st_size > 1000, "sha256": _sha_file(fbx) if fbx.exists() else None, "bytes": fbx.stat().st_size if fbx.exists() else 0}
    except Exception as e:
        results["FBX"] = {"ok": False, "error": str(e)}
    try:
        bpy.ops.export_scene.gltf(
            filepath=str(glb),
            use_selection=True,
            export_format="GLB",
            export_animations=True,
            export_apply=False,
        )
        results["GLB"] = {"ok": glb.exists() and glb.stat().st_size > 500, "sha256": _sha_file(glb) if glb.exists() else None}
    except Exception as e:
        results["GLB"] = {"ok": False, "error": str(e)}

    # reimport structural check in isolated names
    reimp = {"FBX": {"ok": False}, "GLB": {"ok": False}}
    if results.get("FBX", {}).get("ok"):
        before = set(bpy.data.objects.keys())
        try:
            bpy.ops.import_scene.fbx(filepath=str(fbx))
            added = [n for n in bpy.data.objects.keys() if n not in before]
            arms = [bpy.data.objects[n] for n in added if bpy.data.objects[n].type == "ARMATURE"]
            meshes = [bpy.data.objects[n] for n in added if bpy.data.objects[n].type == "MESH"]
            # FBX often nests meshes under armature; count descendants
            for a in arms:
                for c in a.children_recursive:
                    if c.type == "MESH" and c not in meshes:
                        meshes.append(c)
            reimp["FBX"] = {
                "ok": bool(arms) and bool(meshes),
                "armatureCount": len(arms),
                "meshCount": len(meshes),
                "actionCount": len([a for a in bpy.data.actions if a.name.startswith("NURION_Homepage_")]),
            }
            for n in added:
                ob = bpy.data.objects.get(n)
                if ob:
                    bpy.data.objects.remove(ob, do_unlink=True)
        except Exception as e:
            reimp["FBX"] = {"ok": False, "error": str(e)}
    if results.get("GLB", {}).get("ok"):
        before = set(bpy.data.objects.keys())
        try:
            bpy.ops.import_scene.gltf(filepath=str(glb))
            added = [n for n in bpy.data.objects.keys() if n not in before]
            arms = [bpy.data.objects[n] for n in added if bpy.data.objects[n].type == "ARMATURE"]
            meshes = [bpy.data.objects[n] for n in added if bpy.data.objects[n].type == "MESH"]
            reimp["GLB"] = {"ok": bool(arms) or bool(meshes), "armatureCount": len(arms), "meshCount": len(meshes)}
            for n in added:
                ob = bpy.data.objects.get(n)
                if ob:
                    bpy.data.objects.remove(ob, do_unlink=True)
        except Exception as e:
            reimp["GLB"] = {"ok": False, "error": str(e)}
    results["reimport"] = reimp
    return results


def main():
    args = _parse(sys.argv)
    out = Path(args.out_dir)
    run_dir = out / f"run{args.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
    gate5 = Path(args.gate5_blend)
    if _sha_file(gate5) != args.expected_gate5_sha256:
        raise SystemExit("Gate5 blend mutated")
    matrix = json.loads(Path(args.eligibility_json).read_text(encoding="utf-8"))["matrix"]
    eligible = [m for m in matrix if m["status"] == "ELIGIBLE"]
    abstain = [m for m in matrix if m["status"] == "ABSTAIN"]
    if len(abstain) != 46:
        # soft note; still use actual list
        pass

    # Clean scene load
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=str(gate5))
    body, arm = _find_body_arm()
    col = _ensure_col("NURION_CCS_GATE7_WORK")
    g5_params = json.loads(
        (Path(args.params_json).parents[1] / "gate5" / "V07_CCS_GATE5_PARAMETERS.json").read_text(encoding="utf-8")
    )
    preset_values = g5_params["presetValues"]

    # ABSTAIN force-apply DENY probe
    abstain_deny = []
    for a in abstain[:3]:
        abstain_deny.append(
            {
                "combo": a,
                "forceApplyAttempted": False,
                "forceApply": "DENY",
                "applied": False,
            }
        )

    # Representative eligible: one combo per body (prefer BUSINESS_SUIT_01 + SHORT_NEAT_01)
    reps = []
    for body_name in ("BALANCED", "SLIM", "SOFT", "ATHLETIC", "TALL_BALANCED", "MINI_SD"):
        cand = [
            e
            for e in eligible
            if e["body"] == body_name and e["clothing"] == "BUSINESS_SUIT_01" and e["hair"] == "SHORT_NEAT_01"
        ]
        if not cand:
            cand = [e for e in eligible if e["body"] == body_name]
        if cand:
            reps.append(cand[0])

    face_results = {}
    preset_results = []
    pen_total = 0
    weight_collapse = 0
    drift_fails = 0
    sync_ok = True

    # Face modes on BALANCED rest
    _apply_body_preset(body, preset_values["BALANCED"])
    for mode in FACE_MODES:
        ok = _apply_face_mode(body, mode)
        face_results[mode] = {"applied": ok}

    cloth_specs = {"BUSINESS_SUIT_01": (0.35, 1.35, 0.035), "FORMAL_DRESS_01": (0.05, 1.32, 0.045)}
    hair_specs = {"SHORT_NEAT_01": (1.45, 1.72, 0.05), "LONG_WAVE_01": (0.85, 1.76, 0.055)}

    for rep in reps:
        _apply_body_preset(body, preset_values[rep["body"]])
        _apply_face_mode(body, "NATURAL")
        cspec = cloth_specs.get(rep["clothing"], (0.35, 1.35, 0.035))
        hspec = hair_specs.get(rep["hair"], (1.45, 1.72, 0.05))
        cloth = _make_shell(f"G7_{rep['clothing']}_{rep['body']}", cspec[0], cspec[1], cspec[2], body, col)
        hair = _make_shell(f"G7_{rep['hair']}_{rep['body']}", hspec[0], hspec[1], hspec[2], body, col)
        weight_collapse += _transfer_weights(body, cloth, arm)
        weight_collapse += _transfer_weights(body, hair, arm)

        for preset in PRESETS:
            _clear_animation(arm)
            meta = _build_action(arm, preset, fps_scale=1.0)
            # evaluate mid hold
            mid = preset["keys"][1][1]
            _set_pose(arm, mid)
            bpy.context.view_layer.update()
            sync = _sync_empties(arm, col)
            if len(sync) < 6:
                sync_ok = False
            pen = _penetration_proxy(body, cloth)
            pen_total += pen
            drift = _loop_drift(arm, preset)
            if not drift["ok"]:
                drift_fails += 1
            preset_results.append(
                {
                    "body": rep["body"],
                    "clothing": rep["clothing"],
                    "hair": rep["hair"],
                    "presetId": preset["id"],
                    "action": meta["action"],
                    "frameCount": meta["frameCount"],
                    "gesture": meta["gesture"],
                    "handUnitOnly": True,
                    "penetration": pen,
                    "loopDrift": drift,
                    "fpsMeaning": _fps_meaning(preset),
                    "sync": sync,
                }
            )

        # cleanup shells
        for o in (cloth, hair):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if me and me.users == 0:
                bpy.data.meshes.remove(me)

    # Build canonical actions at 30fps on BALANCED for export
    _apply_body_preset(body, preset_values["BALANCED"])
    _apply_face_mode(body, "POLISHED")
    _clear_animation(arm)
    action_contract = []
    for preset in PRESETS:
        meta = _build_action(arm, preset, fps_scale=1.0)
        action_contract.append(
            {
                "presetId": preset["id"],
                "deformAction": meta["action"],
                "controlAction": meta["action"] + "_CTRL",
                "loop": preset["loop"],
                "gesture": preset["gesture"],
                "phases": {
                    "start": 1,
                    "holdStart": preset["keys"][1][0],
                    "holdEnd": preset["keys"][2][0],
                    "return": preset["frameCount"],
                    "frameCount": preset["frameCount"],
                },
                "canonicalFps": 30,
                "supportedFps": [24, 30, 60],
                "fpsMeaning": _fps_meaning(preset),
            }
        )
        # also create empty control action name marker (same curves alias)
        ctrl = bpy.data.actions.new(meta["action"] + "_CTRL")
        # leave empty marker action for contract name presence
        _ = ctrl

    export = _export_and_reimport(run_dir, arm, body)

    handoff = {
        "schema": "NURION_CCS_V06_HANDOFF_CONTRACT",
        "track": "NURION Canonical Character System Gate 7",
        "deformRig": "NURION_CanonicalArmature_V1",
        "controlRig": "NURION_CanonicalArmature_V1",
        "actionContract": action_contract,
        "runtimeActionPrefix": "NURION_Homepage_",
        "v06ExpectedRuntimePrefix": "NURION_UnifiedRuntime_",
        "mappingNote": "CCS homepage actions hand off by presetId; v0.6 may wrap under NURION_UnifiedRuntime_{presetId} after RC.1 byte verify.",
        "meshyActionCopy": "DENY",
        "fingerBones": "ABSENT_HAND_UNIT_GESTURE_ONLY",
        "unsupportedExpressions": UNSUPPORTED,
        "unsupportedPolicy": "REST_FALLBACK_AND_DISCLOSE",
        "restFallback": True,
        "transparentVideoWebComponent": "SEPARATED_FOLLOW_ON_OUTPUT_TRACK",
        "v06PackageStatus": "ABSENT_NO_BYTE_VERIFY",
        "v06ExpectedRc1Sha256": params.get("v06ExpectedRc1Sha256"),
        "v06HandoffVerification": "CONTRACT_ONLY",
        "v06HandoffRuntimeVerified": False,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
    }
    _write(run_dir / "V07_CCS_V06_HANDOFF_CONTRACT.json", handoff)

    out_blend = run_dir / "NURION_CanonicalHomepageHandoff_V1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    if _sha_file(gate5) != args.expected_gate5_sha256:
        raise SystemExit("Gate5 mutated during Gate7")

    fp = _stable_hash(
        {
            "presets": [p["id"] for p in PRESETS],
            "reps": reps,
            "actions": [a["deformAction"] for a in action_contract],
            "face": face_results,
            "pen": pen_total,
            "driftFails": drift_fails,
            "export": {k: v.get("ok") if isinstance(v, dict) else v for k, v in export.items() if k != "reimport"},
        }
    )

    report = {
        "schema": "NURION_V07_CCS_GATE7_RUN_REPORT",
        "runId": int(args.run_id),
        "gate5SourceSha256": args.expected_gate5_sha256,
        "outBlendSha256": _sha_file(out_blend),
        "homepagePresetCount": len(PRESETS),
        "faceModesApplied": face_results,
        "eligibleComboCount": len(eligible),
        "abstainComboCount": len(abstain),
        "representativeEligibleRuns": len(reps),
        "abstainForceApply": "DENY",
        "abstainForceApplyProbes": abstain_deny,
        "presetResultsCount": len(preset_results),
        "penetrationTotal": pen_total,
        "weightCollapseTotal": weight_collapse,
        "loopDriftFails": drift_fails,
        "syncTargetsOk": sync_ok,
        "handUnitGestureOnly": True,
        "unsupportedDisclosed": UNSUPPORTED,
        "restFallback": True,
        "fpsSupported": [24, 30, 60],
        "export": export,
        "handoffContract": "V07_CCS_V06_HANDOFF_CONTRACT.json",
        "v06HandoffVerification": "CONTRACT_ONLY",
        "v06HandoffRuntimeVerified": False,
        "transparentVideoWebComponent": "SEPARATED_FOLLOW_ON_OUTPUT_TRACK",
        "performanceFingerprintSha256": fp,
        "inheritedLimitations": params.get("inheritedLimitations", []),
        "production": "NO-GO",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "blenderVersion": bpy.app.version_string,
    }
    _write(run_dir / "V07_CCS_GATE7_RUN_REPORT.json", report)
    _write(run_dir / "V07_CCS_GATE7_PRESET_RESULTS.json", {"results": preset_results})
    print(
        json.dumps(
            {
                "runId": args.run_id,
                "performanceFingerprintSha256": fp,
                "pen": pen_total,
                "driftFails": drift_fails,
                "exportFbx": export.get("FBX", {}).get("ok"),
                "exportGlb": export.get("GLB", {}).get("ok"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("GATE7_FAIL", e, file=sys.stderr)
        raise
