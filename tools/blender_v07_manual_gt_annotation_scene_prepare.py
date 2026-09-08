"""
v0.7 Manual GT — Annotation Scene Prepare (no GT points).

Clean-import mesh only; hide/disable all armatures, modifiers, actions;
create orthographic + perspective cameras; lock transform/mesh hashes;
emit leak-guard evidence. Does NOT invent or place GT joint coordinates.

Usage:
  blender --background --python tools/blender_v07_manual_gt_annotation_scene_prepare.py -- \\
    --zip <source.zip> --label <label> --out-dir dist/v0.7/manual_gt/scenes/<label>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Euler, Vector

CAMERA_SPECS = [
    ("CAM_FRONT_ORTHO", "FRONT_ORTHO", (0.0, -3.5, 0.9), (math.radians(90), 0.0, 0.0), True),
    ("CAM_LEFT_ORTHO", "LEFT_ORTHO", (-3.5, 0.0, 0.9), (math.radians(90), 0.0, math.radians(90)), True),
    ("CAM_RIGHT_ORTHO", "RIGHT_ORTHO", (3.5, 0.0, 0.9), (math.radians(90), 0.0, math.radians(-90)), True),
    ("CAM_BACK_ORTHO", "BACK_ORTHO", (0.0, 3.5, 0.9), (math.radians(90), 0.0, math.radians(180)), True),
    ("CAM_TOP_ORTHO", "TOP_ORTHO", (0.0, 0.0, 4.0), (0.0, 0.0, 0.0), True),
    ("CAM_PERSPECTIVE_CONFIRM", "PERSPECTIVE_CONFIRM", (2.4, -2.8, 1.6), (math.radians(70), 0.0, math.radians(35)), False),
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--expected-zip-sha256", default="")
    p.add_argument("--expected-fbx-sha256", default="")
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


def _stable_hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _ensure_collection(name: str):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _link_exclusive(obj, target_col):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    target_col.objects.link(obj)


def _find_fbx(extract: Path) -> Path:
    cands = sorted(extract.rglob("*.fbx"))
    if not cands:
        raise FileNotFoundError("no fbx in zip")
    scored = []
    for p in cands:
        n = p.name.lower()
        score = 0
        if "withskin" in n or "texture" in n:
            score += 8
        if "idle" in n:
            score += 3
        scored.append((-score, len(str(p)), p))
    scored.sort()
    return scored[0][2]


def _import_fbx(fbx: Path):
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(
        filepath=str(fbx),
        automatic_bone_orientation=True,
        use_anim=False,
        ignore_leaf_bones=False,
    )
    return [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before]


def _mesh_bounds(meshes):
    mins = [1e9, 1e9, 1e9]
    maxs = [-1e9, -1e9, -1e9]
    for obj in meshes:
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            for i in range(3):
                mins[i] = min(mins[i], float(w[i]))
                maxs[i] = max(maxs[i], float(w[i]))
    size = [maxs[i] - mins[i] for i in range(3)]
    center = [(mins[i] + maxs[i]) * 0.5 for i in range(3)]
    return {
        "min": [round(v, 6) for v in mins],
        "max": [round(v, 6) for v in maxs],
        "size": [round(v, 6) for v in size],
        "center": [round(v, 6) for v in center],
        "heightM": round(size[2], 6),
    }


def _disable_animation():
    scene = bpy.context.scene
    scene.frame_set(1)
    if scene.animation_data:
        scene.animation_data_clear()
    for obj in bpy.data.objects:
        if obj.animation_data:
            obj.animation_data_clear()
        if obj.type == "ARMATURE" and obj.data:
            arm = obj.data
            if getattr(arm, "animation_data", None):
                arm.animation_data_clear()
            for bone in obj.pose.bones:
                bone.matrix_basis.identity()
    for action in list(bpy.data.actions):
        action.use_fake_user = False
        bpy.data.actions.remove(action)


def _apply_leak_guard(meshes, armatures, other_non_mesh):
    mesh_col = _ensure_collection("NURION_GT_MESH")
    hidden_col = _ensure_collection("NURION_GT_HIDDEN_RIGS")
    cam_col = _ensure_collection("NURION_GT_CAMERAS")
    floor_col = _ensure_collection("NURION_GT_REFERENCE")
    a_col = _ensure_collection("NURION_GT_ANNOTATOR_A")
    b_col = _ensure_collection("NURION_GT_ANNOTATOR_B")
    # Keep empty annotator collections for later independent empties; no points now.
    a_col.hide_viewport = False
    b_col.hide_viewport = False
    a_col.hide_render = False
    b_col.hide_render = False

    for obj in meshes:
        _link_exclusive(obj, mesh_col)
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.hide_select = False
        for mod in obj.modifiers:
            # Armature / deform must not drive annotation mesh.
            if mod.type in {"ARMATURE", "MESH_DEFORM", "SURFACE_DEFORM", "LATTICE", "HOOK"}:
                mod.show_viewport = False
                mod.show_render = False
                mod.show_in_editmode = False
            # Strip NURION guide-like custom properties visibility if any.
        # Clear vertex-group driven display noise is unnecessary; leave data intact.

    for obj in armatures:
        _link_exclusive(obj, hidden_col)
        obj.hide_set(True)
        obj.hide_viewport = True
        obj.hide_render = True
        obj.hide_select = True
        if obj.type == "ARMATURE":
            obj.data.pose_position = "REST"

    for obj in other_non_mesh:
        name_l = obj.name.lower()
        # Hide landmarks/guides/controls/diagnostics by name heuristics + non-mesh leftovers.
        is_guide = any(
            k in name_l
            for k in (
                "landmark",
                "guide",
                "control",
                "nurion_v0",
                "empt",
                "target",
                "pole",
                "ik_",
                "ui_",
            )
        )
        if obj.type != "MESH" or is_guide:
            _link_exclusive(obj, hidden_col)
            obj.hide_set(True)
            obj.hide_viewport = True
            obj.hide_render = True
            obj.hide_select = True

    # Floor plane (reference only)
    bpy.ops.mesh.primitive_plane_add(size=4.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.active_object
    floor.name = "GT_FLOOR_PLANE"
    _link_exclusive(floor, floor_col)
    floor.hide_select = True

    # World axes empty (display only)
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    axes = bpy.context.active_object
    axes.name = "GT_WORLD_AXES"
    axes.empty_display_size = 0.25
    _link_exclusive(axes, floor_col)
    axes.hide_select = True

    return {
        "meshCollection": mesh_col.name,
        "hiddenCollection": hidden_col.name,
        "cameraCollection": cam_col.name,
        "referenceCollection": floor_col.name,
        "annotatorA": a_col.name,
        "annotatorB": b_col.name,
    }


def _place_cameras(center, height):
    cam_col = _ensure_collection("NURION_GT_CAMERAS")
    cx, cy, cz = center
    # Scale camera distance by character height.
    scale = max(height, 1.0)
    created = []
    for name, role, loc, rot, ortho in CAMERA_SPECS:
        bpy.ops.object.camera_add()
        cam = bpy.context.active_object
        cam.name = name
        cam.data.name = name + "_DATA"
        # Offset relative to mesh center; TOP uses Z.
        if role == "TOP_ORTHO":
            cam.location = (cx, cy, cz + 2.2 * scale)
        elif role == "FRONT_ORTHO":
            cam.location = (cx, cy - 2.2 * scale, cz)
        elif role == "BACK_ORTHO":
            cam.location = (cx, cy + 2.2 * scale, cz)
        elif role == "LEFT_ORTHO":
            cam.location = (cx - 2.2 * scale, cy, cz)
        elif role == "RIGHT_ORTHO":
            cam.location = (cx + 2.2 * scale, cy, cz)
        else:
            cam.location = (cx + 1.5 * scale, cy - 1.8 * scale, cz + 0.4 * scale)
        cam.rotation_euler = Euler(rot)
        cam.data.type = "ORTHO" if ortho else "PERSP"
        if ortho:
            cam.data.ortho_scale = max(1.8, height * 1.35)
        else:
            cam.data.lens = 50.0
        _link_exclusive(cam, cam_col)
        created.append({"name": cam.name, "role": role, "ortho": ortho})
    return created


def _world_matrix_payload(meshes):
    rows = []
    for obj in sorted(meshes, key=lambda o: o.name):
        m = obj.matrix_world
        rows.append(
            {
                "object": obj.name,
                "matrix": [round(m[i][j], 8) for i in range(4) for j in range(4)],
            }
        )
    return rows


def _mesh_geometry_payload(meshes):
    deps = bpy.context.evaluated_depsgraph_get()
    rows = []
    for obj in sorted(meshes, key=lambda o: o.name):
        ev = obj.evaluated_get(deps)
        me = ev.to_mesh()
        try:
            verts = []
            for v in me.vertices:
                co = obj.matrix_world @ v.co
                verts.append([round(float(co.x), 6), round(float(co.y), 6), round(float(co.z), 6)])
            rows.append(
                {
                    "object": obj.name,
                    "vertexCount": len(verts),
                    "vertices": verts,
                }
            )
        finally:
            ev.to_mesh_clear()
    return rows


def _leak_guard_state(meshes, armatures):
    armature_visible = []
    for obj in armatures:
        visible = (not obj.hide_viewport) and (not obj.hide_get())
        selectable = not obj.hide_select
        if visible or selectable:
            armature_visible.append(obj.name)
    mod_active = []
    for obj in meshes:
        for mod in obj.modifiers:
            if mod.type == "ARMATURE" and (mod.show_viewport or mod.show_render):
                mod_active.append(f"{obj.name}:{mod.name}")
    # GT empties must not exist yet.
    gt_points = [
        o.name
        for o in bpy.data.objects
        if o.type == "EMPTY" and o.name.startswith("GT_JOINT_")
    ]
    guide_visible = []
    for obj in bpy.data.objects:
        nl = obj.name.lower()
        if any(k in nl for k in ("landmark", "nurion_homepage", "guide", "controlrig")):
            if (not obj.hide_viewport) and (not obj.hide_get()):
                guide_visible.append(obj.name)
    return {
        "allArmaturesHidden": len(armature_visible) == 0,
        "armatureVisibleOrSelectable": armature_visible,
        "allArmatureModifiersDisabled": len(mod_active) == 0,
        "activeArmatureModifiers": mod_active,
        "allActionsDisabled": len(bpy.data.actions) == 0,
        "actionCount": len(bpy.data.actions),
        "v02LandmarksHidden": len(guide_visible) == 0,
        "v07GuidesAndControlsHidden": len(guide_visible) == 0,
        "visibleGuideLikeObjects": guide_visible,
        "gtJointPointsPlaced": len(gt_points),
        "gtJointPointNames": gt_points,
        "gtLeak": "PASS" if not armature_visible and not mod_active and not gt_points else "FAIL",
    }


def _render_evidence(out_dir: Path, cameras, center):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out_dir / "_tmp")
    evidence_dir = out_dir / "leak_guard"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for cam_info in cameras:
        cam = bpy.data.objects.get(cam_info["name"])
        if cam is None:
            continue
        scene.camera = cam
        # Aim perspective loosely at center.
        if not cam_info["ortho"]:
            direction = Vector(center) - cam.location
            if direction.length > 1e-6:
                cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        path = evidence_dir / f"{cam_info['role']}.png"
        scene.render.filepath = str(path.with_suffix(""))
        bpy.ops.render.render(write_still=True)
        # Blender appends extension.
        png = path if path.exists() else Path(str(path) + ".png")
        if not png.exists():
            # workbench may write exactly filepath + .png
            cand = Path(scene.render.filepath + ".png")
            if cand.exists():
                png = cand
                if png != path:
                    shutil.move(str(png), str(path))
                    png = path
        if png.exists():
            files.append({"role": cam_info["role"], "path": str(png.relative_to(out_dir)).replace("\\", "/"), "sha256": _sha(png)})
    return files


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    zip_path = Path(args.zip)
    if not zip_path.is_file():
        raise SystemExit(f"missing zip: {zip_path}")
    zip_sha = _sha(zip_path)
    if args.expected_zip_sha256 and zip_sha != args.expected_zip_sha256.lower():
        raise SystemExit(f"zip sha mismatch: {zip_sha}")

    extract = out_dir / "_extract"
    extract.mkdir()
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract)
    fbx = _find_fbx(extract)
    fbx_sha = _sha(fbx)
    if args.expected_fbx_sha256 and fbx_sha != args.expected_fbx_sha256.lower():
        raise SystemExit(f"fbx sha mismatch: {fbx_sha}")

    # Preserve sealed source copy (read-only identity); do not mutate original zip.
    sealed_zip = out_dir / "source" / zip_path.name
    sealed_zip.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, sealed_zip)

    _reset_scene()
    imported = _import_fbx(fbx)
    _disable_animation()

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    other = [o for o in bpy.data.objects if o.type not in {"MESH", "ARMATURE"}]

    if not meshes:
        raise SystemExit("no mesh after import")

    cols = _apply_leak_guard(meshes, armatures, other)
    # Re-collect after linking.
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name != "GT_FLOOR_PLANE"]
    bounds = _mesh_bounds(meshes)
    cameras = _place_cameras(bounds["center"], bounds["heightM"])

    world_payload = _world_matrix_payload(meshes)
    mesh_payload = _mesh_geometry_payload(meshes)
    # Hash without embedding full vertex arrays in status (store separately).
    world_matrix_sha = _stable_hash(world_payload)
    mesh_geometry_sha = _stable_hash(
        [{"object": r["object"], "vertexCount": r["vertexCount"], "vertices": r["vertices"]} for r in mesh_payload]
    )
    _write(out_dir / "WORLD_MATRIX_LOCK.json", {"schema": "NURION_V07_GT_WORLD_MATRIX_LOCK", "rows": world_payload, "sha256": world_matrix_sha})
    # Compact mesh lock: hash only + counts (full verts are huge; store hash of verts).
    mesh_lock = {
        "schema": "NURION_V07_GT_MESH_GEOMETRY_LOCK",
        "objects": [{"object": r["object"], "vertexCount": r["vertexCount"]} for r in mesh_payload],
        "sha256": mesh_geometry_sha,
    }
    _write(out_dir / "MESH_GEOMETRY_LOCK.json", mesh_lock)
    # Optional binary-ish dump of vertex hash chain for audit without full dump in STATUS.
    vert_hash_chain = []
    for r in mesh_payload:
        vert_hash_chain.append(
            {
                "object": r["object"],
                "vertexCount": r["vertexCount"],
                "verticesSha256": _stable_hash(r["vertices"]),
            }
        )
    _write(out_dir / "MESH_VERTEX_HASH_CHAIN.json", {"rows": vert_hash_chain, "aggregateSha256": mesh_geometry_sha})

    leak = _leak_guard_state(meshes, armatures)
    evidence_files = _render_evidence(out_dir, cameras, bounds["center"])
    evidence_receipt = {
        "schema": "NURION_V07_GT_LEAK_GUARD_EVIDENCE",
        "label": args.label,
        "leakGuard": leak,
        "screenshots": evidence_files,
        "collections": cols,
        "cameras": cameras,
        "gtPointsPlaced": 0,
        "coordinateInvention": "DENY",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    evidence_sha = _stable_hash(evidence_receipt)
    evidence_receipt["evidenceReceiptSha256"] = evidence_sha
    _write(out_dir / "LEAK_GUARD_EVIDENCE.json", evidence_receipt)

    blend_path = out_dir / f"NURION_ManualGT_Annotation_{args.label}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    scene_receipt = {
        "schema": "NURION_V07_MANUAL_GT_ANNOTATION_SCENE_RECEIPT",
        "label": args.label,
        "status": "SCENE_PREPARED_WAITING_FOR_MANUAL_ANNOTATIONS",
        "blenderVersion": bpy.app.version_string,
        "pose": "NEUTRAL_REST",
        "source": {
            "zipFileName": zip_path.name,
            "sourceZipSha256": zip_sha,
            "fbxRelative": str(fbx.relative_to(extract)).replace("\\", "/"),
            "sourceFbxSha256": fbx_sha,
            "sealedZipCopy": str(sealed_zip.relative_to(out_dir)).replace("\\", "/"),
            "sealedZipSha256": _sha(sealed_zip),
        },
        "locks": {
            "worldMatrixSha256": world_matrix_sha,
            "meshGeometrySha256": mesh_geometry_sha,
            "evidenceReceiptSha256": evidence_sha,
        },
        "leakGuard": leak,
        "bounds": bounds,
        "meshCount": len(meshes),
        "armatureCountHidden": len(armatures),
        "cameras": [c["role"] for c in cameras],
        "collections": cols,
        "gtPointsPlaced": 0,
        "annotationCompleted": False,
        "accuracy": "NOT_VALIDATED",
        "finalSeal": "HOLD_FOR_MANUAL_GT",
        "production": "NO-GO",
        "sourceMutation": 0,
        "sealedBaselineMutation": 0,
        "blendFile": blend_path.name,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if leak["gtLeak"] != "PASS":
        scene_receipt["status"] = "SCENE_PREPARE_FAILED_LEAK_GUARD"
        scene_receipt["gtLeak"] = "GT_LEAK_CONTAMINATED"
    _write(out_dir / "V07_MANUAL_GT_ANNOTATION_SCENE_RECEIPT.json", scene_receipt)

    # Empty annotation stub from template fields (still not GT).
    stub = {
        "schema": "NURION_V07_MANUAL_GT_ANNOTATION",
        "track": "NURION Homepage Performance Rig v0.7",
        "asset": {
            "label": args.label,
            "sourceZipSha256": zip_sha,
            "sourceFbxSha256": fbx_sha,
            "meshGeometrySha256": mesh_geometry_sha,
            "worldMatrixSha256": world_matrix_sha,
            "blenderVersion": bpy.app.version_string,
            "pose": "NEUTRAL_REST",
        },
        "leakGuard": {
            "allArmaturesHidden": leak["allArmaturesHidden"],
            "allArmatureModifiersDisabled": leak["allArmatureModifiersDisabled"],
            "allActionsDisabled": leak["allActionsDisabled"],
            "v02LandmarksHidden": leak["v02LandmarksHidden"],
            "v07GuidesAndControlsHidden": leak["v07GuidesAndControlsHidden"],
            "evidenceReceiptSha256": evidence_sha,
            "gtLeak": leak["gtLeak"],
        },
        "annotation": {
            "unit": "meter",
            "space": "WORLD",
            "annotatorA": None,
            "annotatorB": None,
            "adjudicator": None,
            "startedAt": None,
            "sealedAt": None,
            "points": [],
            "note": "SCENE_PREPARED_POINTS_NOT_PLACED",
        },
        "status": "SCENE_PREPARED_EMPTY_ANNOTATION_NOT_GROUND_TRUTH",
        "production": "NO-GO",
    }
    _write(out_dir / "V07_MANUAL_GT_ANNOTATION_STUB.json", stub)
    return 0 if leak["gtLeak"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc)
        raise
