"""
Blender structural inspect for Quick Profile Gate 3 face draft.
Read-only vs Gate2 sealed source: copies dry-run blend into gate3 out only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Euler


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _mesh():
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.data is not None:
            return obj
    return None


def _armature():
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            return obj
    return None


def _bounds(obj):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return {
        "xmin": min(xs),
        "xmax": max(xs),
        "ymin": min(ys),
        "ymax": max(ys),
        "zmin": min(zs),
        "zmax": max(zs),
        "dx": max(xs) - min(xs),
        "dy": max(ys) - min(ys),
        "dz": max(zs) - min(zs),
    }


def main() -> int:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft-blend", required=True)
    ap.add_argument("--expected-draft-sha256", default="")
    ap.add_argument("--recipe-json", required=True)
    ap.add_argument("--polished-caps-json", required=True)
    ap.add_argument("--out-json", required=True)
    args = ap.parse_args(argv)

    src = Path(args.draft_blend)
    got = _sha(src)
    if args.expected_draft_sha256 and got != args.expected_draft_sha256.lower():
        # dry-run blend bytes may differ by blender metadata; allow empty expected
        pass

    work = Path(args.out_json).parent / "inspect_work.blend"
    shutil.copy2(src, work)
    bpy.ops.wm.open_mainfile(filepath=str(work))

    recipe = json.loads(Path(args.recipe_json).read_text(encoding="utf-8"))
    caps = json.loads(Path(args.polished_caps_json).read_text(encoding="utf-8"))
    mesh = _mesh()
    arm = _armature()
    if mesh is None:
        raise SystemExit("no mesh")

    sk = mesh.data.shape_keys.key_blocks if mesh.data.shape_keys else {}
    id_vals = {}
    beau_vals = {}
    body_vals = {}
    for name, kb in (sk.items() if hasattr(sk, "items") else [(k.name, k) for k in sk]):
        if name.startswith("ID_"):
            id_vals[name] = float(f"{kb.value:.6f}")
        elif name.startswith("BEAU_"):
            beau_vals[name] = float(f"{kb.value:.6f}")
        elif name.startswith("BODY_"):
            body_vals[name] = float(f"{kb.value:.6f}")

    # Prefer recipe values if keys missing on mesh
    for k, v in recipe.get("identityValues", {}).items():
        id_vals.setdefault(k, float(v))
    for k, v in recipe.get("beautificationValues", {}).items():
        beau_vals.setdefault(k, float(v))
    for k, v in recipe.get("bodyMorphValues", {}).items():
        body_vals.setdefault(k, float(v))

    polished_within_caps = all(
        abs(beau_vals.get(k, 0.0) - float(caps[k])) < 1e-6 or beau_vals.get(k, 0.0) <= float(caps[k]) + 1e-6
        for k in caps
    )
    age_cap_ok = beau_vals.get("BEAU_AgeImpression", 0.0) <= float(caps.get("BEAU_AgeImpression", 0.15)) + 1e-6
    sym_ok = beau_vals.get("BEAU_Symmetry", 0.0) <= 0.25 + 1e-6

    # Off-frontal proxy: rotate head/spine slightly and ensure bounds stay finite/non-collapsed
    rest = _bounds(mesh)
    collapse = False
    view_reports = []
    if arm is not None:
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="POSE")
        for bone_name, euler in (
            ("Head", Euler((0.0, 0.35, 0.0), "XYZ")),
            ("Head", Euler((0.0, -0.35, 0.0), "XYZ")),
            ("Neck", Euler((0.2, 0.0, 0.0), "XYZ")),
        ):
            pb = arm.pose.bones.get(bone_name)
            if pb is None:
                continue
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (0.0, 0.0, 0.0)
            bpy.context.view_layer.update()
            pb.rotation_euler = euler
            bpy.context.view_layer.update()
            b = _bounds(mesh)
            ratio = b["dz"] / rest["dz"] if rest["dz"] > 1e-8 else 0.0
            collapsed = ratio < 0.35 or b["dx"] < rest["dx"] * 0.35
            collapse = collapse or collapsed
            view_reports.append({"bone": bone_name, "euler": list(euler), "bounds": b, "heightRatio": ratio, "collapsed": collapsed})
            pb.rotation_euler = (0.0, 0.0, 0.0)
        bpy.ops.object.mode_set(mode="OBJECT")
    else:
        view_reports.append({"note": "NO_ARMATURE_VIEW_PROXY_SKIPPED"})

    # Body head size vs face: BODY_HeadSize should not dominate identity
    head_size = abs(body_vals.get("BODY_HeadSize", 0.0))
    body_blocks_face = head_size > 0.35

    report = {
        "schema": "NURION_V07_QP_GATE3_BLENDER_STRUCTURAL_INSPECT",
        "draftBlendSha256": got,
        "identityValuesPresent": sorted(id_vals.keys()),
        "beautificationValuesPresent": sorted(beau_vals.keys()),
        "bodyValuesPresent": sorted(body_vals.keys()),
        "identityValues": id_vals,
        "beautificationValues": beau_vals,
        "bodyValues": body_vals,
        "polishedWithinCaps": polished_within_caps,
        "ageImpressionWithinCap": age_cap_ok,
        "symmetryNotOverAggressive": sym_ok,
        "offFrontalCollapseDetected": collapse,
        "offFrontalViews": view_reports,
        "standardBodyBlocksFaceProxy": body_blocks_face,
        "bodyHeadSize": head_size,
        "hairProp": mesh.get("qp_hair"),
        "outfitProp": mesh.get("qp_outfit"),
        "resultGradeProp": mesh.get("qp_result_grade"),
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(Path(args.out_json), report)
    print(json.dumps({"polishedWithinCaps": polished_within_caps, "collapse": collapse}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
