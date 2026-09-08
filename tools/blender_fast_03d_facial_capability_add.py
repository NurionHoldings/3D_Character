#!/usr/bin/env python3
"""FAST-03D — extract presentation morph deltas + bone specs (Blender headless)."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = __import__("sys").argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--input-glb", type=Path, required=True)
    p.add_argument("--membership-json", type=Path, required=True)
    p.add_argument("--morph-json", type=Path, required=True)
    p.add_argument("--bones-json", type=Path, required=True)
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def import_glb(path: Path):
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(path))
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    mesh_obj = next((o for o in bpy.data.objects if o.type == "MESH"), None)
    if arm is None or mesh_obj is None:
        raise RuntimeError("GLB missing armature or mesh")
    return arm, mesh_obj


def load_membership(path: Path) -> dict[str, list[int]]:
    return json.loads(path.read_text(encoding="utf-8"))["vertexMembership"]


def region_indices(membership: dict[str, list[int]], *names: str) -> set[int]:
    out: set[int] = set()
    for n in names:
        out.update(membership.get(n, []))
    return out


def head_bone(arm):
    for b in arm.data.bones:
        if b.name.lower() == "head":
            return b
    raise RuntimeError("Head bone missing")


def classify_presentation_zones(obj, membership: dict[str, list[int]]) -> dict[str, set[int]]:
    face = region_indices(membership, "FACE_IDENTITY_REGION")
    coords = {i: Vector(obj.data.vertices[i].co) for i in face}
    ys = [coords[i].y for i in face]
    xs = [coords[i].x for i in face]
    y_min, y_max = min(ys), max(ys)
    x_mid = (min(xs) + max(xs)) * 0.5
    y_jaw = y_min + (y_max - y_min) * 0.35
    y_eye = y_min + (y_max - y_min) * 0.72
    mouth = {i for i in face if coords[i].y <= y_jaw}
    eyes_l = {i for i in face if coords[i].y >= y_eye and coords[i].x < x_mid - 0.005}
    eyes_r = {i for i in face if coords[i].y >= y_eye and coords[i].x > x_mid + 0.005}
    eyelids_l = {i for i in eyes_l if coords[i].y >= y_min + (y_max - y_min) * 0.78}
    eyelids_r = {i for i in eyes_r if coords[i].y >= y_min + (y_max - y_min) * 0.78}
    smile = {i for i in mouth if abs(coords[i].x) >= 0.015}
    return {
        "mouth": mouth,
        "eyes_l": eyes_l,
        "eyes_r": eyes_r,
        "eyelids_l": eyelids_l,
        "eyelids_r": eyelids_r,
        "smile": smile,
        "face": face,
    }


def build_shape_keys(obj, zones: dict[str, set[int]]) -> list[str]:
    if not obj.data.shape_keys:
        obj.shape_key_add(name="Basis", from_mix=False)
    basis = obj.data.shape_keys.key_blocks["Basis"]

    def add(name: str, deltas: dict[int, Vector]):
        sk = obj.shape_key_add(name=name, from_mix=False)
        for vi, delta in deltas.items():
            sk.data[vi].co = basis.data[vi].co + delta

    def delta_for(idxs: set[int], vec: Vector) -> dict[int, Vector]:
        return {i: vec.copy() for i in idxs}

    smile_d: dict[int, Vector] = {}
    for i in zones["smile"]:
        x = obj.data.vertices[i].co.x
        smile_d[i] = Vector((0.006 if x > 0 else -0.006, 0.005, 0.002))

    specs = [
        ("PRES_JawOpen", delta_for(zones["mouth"], Vector((0.0, -0.018, 0.004)))),
        ("PRES_Blink_L", delta_for(zones["eyelids_l"], Vector((0.0, -0.012, 0.0)))),
        ("PRES_Blink_R", delta_for(zones["eyelids_r"], Vector((0.0, -0.012, 0.0)))),
        ("PRES_Viseme_A", delta_for(zones["mouth"], Vector((0.0, -0.008, 0.012)))),
        ("PRES_Viseme_E", delta_for(zones["mouth"], Vector((0.0, -0.004, 0.006)))),
        ("PRES_Viseme_O", delta_for(zones["mouth"], Vector((0.0, -0.010, 0.018)))),
        ("PRES_Viseme_M", delta_for(zones["mouth"], Vector((0.0, 0.002, -0.004)))),
        ("PRES_SmileMild", smile_d),
    ]
    names = []
    for name, deltas in specs:
        add(name, deltas)
        names.append(name)
    return names


def morph_deltas_json(obj, shape_names: list[str]) -> dict:
    basis = obj.data.shape_keys.key_blocks["Basis"]
    n = len(obj.data.vertices)
    out: dict = {"vertexCount": n, "shapeKeys": {}}
    for name in shape_names:
        kb = obj.data.shape_keys.key_blocks[name]
        deltas = []
        for i in range(n):
            d = kb.data[i].co - basis.data[i].co
            if d.length > 1e-9:
                deltas.append([i, float(d.x), float(d.y), float(d.z)])
        out["shapeKeys"][name] = deltas
    return out


def bone_specs(arm) -> list[dict]:
    hb = head_bone(arm)
    head_world = arm.matrix_world @ hb.head
    specs = [
        ("NURION_Jaw", Vector((0.0, -0.03, 0.04)), Vector((0.0, -0.08, 0.06))),
        ("NURION_Eye_L", Vector((-0.035, 0.04, 0.06)), Vector((-0.035, 0.04, 0.08))),
        ("NURION_Eye_R", Vector((0.035, 0.04, 0.06)), Vector((0.035, 0.04, 0.08))),
        ("NURION_Eyelid_L", Vector((-0.035, 0.055, 0.065)), Vector((-0.035, 0.05, 0.07))),
        ("NURION_Eyelid_R", Vector((0.035, 0.055, 0.065)), Vector((0.035, 0.05, 0.07))),
    ]
    bones = []
    for name, head, tail in specs:
        bones.append(
            {
                "name": name,
                "parent": hb.name,
                "headLocal": [float(x) for x in head],
                "tailLocal": [float(x) for x in tail],
            }
        )
    return bones


def main():
    args = parse_args()
    membership = load_membership(args.membership_json)
    arm, mesh_obj = import_glb(args.input_glb)
    zones = classify_presentation_zones(mesh_obj, membership)
    shape_names = build_shape_keys(mesh_obj, zones)
    morph = morph_deltas_json(mesh_obj, shape_names)
    morph["presentationZones"] = {k: len(v) for k, v in zones.items()}
    bones = {"addedBones": bone_specs(arm), "existingBoneCount": len(arm.data.bones)}
    args.morph_json.parent.mkdir(parents=True, exist_ok=True)
    args.morph_json.write_text(json.dumps(morph, indent=2), encoding="utf-8")
    args.bones_json.write_text(json.dumps(bones, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
