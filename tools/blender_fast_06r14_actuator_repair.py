#!/usr/bin/env python3
"""FAST-06R1.4-A — rebuild presentation-only morph deltas on visible face ROI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import bpy
import numpy as np


ACTUATORS = (
    "PRES_JawOpen",
    "PRES_Blink_L",
    "PRES_Blink_R",
    "PRES_Viseme_A",
    "PRES_Viseme_E",
    "PRES_Viseme_O",
    "PRES_Viseme_M",
    "PRES_SmileMild",
)


def args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input-glb", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    p.add_argument("--forensic-json", type=Path, required=True)
    return p.parse_args(argv)


def gltf_delta_from_blender_world(delta: np.ndarray) -> np.ndarray:
    """glTF Y-up to Blender Z-up inverse for direction vectors."""
    return np.array([delta[0], delta[2], -delta[1]], dtype=np.float64)


def ellipse_mask(world: np.ndarray, cx: float, cz: float, rx: float, rz: float, front_y: float):
    ellipse = ((world[:, 0] - cx) / rx) ** 2 + ((world[:, 2] - cz) / rz) ** 2
    return (ellipse <= 1.0) & (world[:, 1] < front_y)


def add_delta(store: dict[int, np.ndarray], vi: int, world_delta: tuple[float, float, float]):
    d = gltf_delta_from_blender_world(np.array(world_delta, dtype=np.float64))
    if np.linalg.norm(d) > 1e-9:
        store[int(vi)] = d


def rows(store: dict[int, np.ndarray]):
    return [[i, float(d[0]), float(d[1]), float(d[2])] for i, d in sorted(store.items())]


def main():
    a = args()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(a.input_glb))
    obj = next(o for o in bpy.data.objects if o.type == "MESH")

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    world = np.array([tuple(evaluated.matrix_world @ v.co) for v in evaluated_mesh.vertices])

    # Fixed presentation ROIs measured on the visible, skin-evaluated neutral face.
    mouth_cx, mouth_cz = 0.083, 1.402
    mouth_mask = ellipse_mask(world, mouth_cx, mouth_cz, 0.061, 0.027, -0.088)
    mouth_ids = np.where(mouth_mask)[0]

    eye_specs = {
        # Character left is viewer right.
        "PRES_Blink_L": (0.132, 1.466),
        "PRES_Blink_R": (0.041, 1.466),
    }
    eye_ids = {
        name: np.where(ellipse_mask(world, cx, cz, 0.032, 0.024, -0.082))[0]
        for name, (cx, cz) in eye_specs.items()
    }

    shape: dict[str, dict[int, np.ndarray]] = {name: {} for name in ACTUATORS}

    for vi in mouth_ids:
        x, y, z = world[vi]
        sx = 1.0 if x >= mouth_cx else -1.0
        rel_x = min(1.0, abs(x - mouth_cx) / 0.061)
        rel_z = z - mouth_cz

        # Readable jaw: lower contour drops; upper lip lifts slightly.
        jaw_z = -0.018 * (0.72 + 0.28 * (1.0 - rel_x)) if rel_z <= 0.002 else 0.004
        add_delta(shape["PRES_JawOpen"], vi, (sx * 0.001, -0.002, jaw_z))

        # A: tall open oval, distinct from jaw by inward horizontal shaping.
        a_z = -0.015 if rel_z <= 0.0 else 0.008
        add_delta(shape["PRES_Viseme_A"], vi, (-sx * 0.003 * rel_x, -0.002, a_z))

        # E: wide, shallow opening.
        e_z = -0.004 if rel_z <= 0.0 else 0.002
        add_delta(shape["PRES_Viseme_E"], vi, (sx * 0.007 * (0.45 + rel_x), -0.001, e_z))

        # O: rounded/puckered, pushed toward camera.
        o_z = -0.008 if rel_z <= 0.0 else 0.006
        add_delta(shape["PRES_Viseme_O"], vi, (-sx * 0.009 * rel_x, -0.004, o_z))

        # M: lips converge toward the mouth center.
        m_z = -rel_z * 0.82
        add_delta(shape["PRES_Viseme_M"], vi, (-sx * 0.002 * rel_x, -0.0005, m_z))

        # Mild smile: corners raise and widen; center remains stable.
        if rel_x >= 0.20:
            strength = (rel_x - 0.20) / 0.80
            add_delta(
                shape["PRES_SmileMild"],
                vi,
                (sx * 0.008 * strength, -0.001, 0.014 * strength),
            )

    for name, ids in eye_ids.items():
        _, center_z = eye_specs[name]
        for vi in ids:
            x, y, z = world[vi]
            # Strong debug close at 1.0: collapse eyelid ROI to one horizontal seam.
            close_z = center_z - z
            add_delta(shape[name], vi, (0.0, -0.0015, close_z))

    out = {
        "vertexCount": len(obj.data.vertices),
        "revision": "FAST-06R1.4_PRESENTATION_MORPH_VISIBILITY",
        "neutralContract": "weight=0 exact identity parity; additive targets only",
        "shapeKeys": {name: rows(shape[name]) for name in ACTUATORS},
        "presentationZones": {
            "mouthVertexCount": int(len(mouth_ids)),
            "blinkLeftVertexCount": int(len(eye_ids["PRES_Blink_L"])),
            "blinkRightVertexCount": int(len(eye_ids["PRES_Blink_R"])),
        },
    }
    forensic = {
        "revision": out["revision"],
        "selectionSpace": "skin-evaluated neutral world coordinates",
        "mouth": {
            "center": [mouth_cx, mouth_cz],
            "radius": [0.061, 0.027],
            "frontYMax": -0.088,
            "vertexIds": [int(i) for i in mouth_ids],
            "worldBounds": [
                world[mouth_ids].min(axis=0).tolist(),
                world[mouth_ids].max(axis=0).tolist(),
            ],
        },
        "eyes": {
            name: {
                "center": [cx, cz],
                "radius": [0.032, 0.024],
                "frontYMax": -0.082,
                "vertexIds": [int(i) for i in eye_ids[name]],
                "worldBounds": [
                    world[eye_ids[name]].min(axis=0).tolist(),
                    world[eye_ids[name]].max(axis=0).tolist(),
                ],
            }
            for name, (cx, cz) in eye_specs.items()
        },
        "oldSelectionFinding": {
            "jawVisemeSmile": "mislocalized to lower neck/shoulder region",
            "blink": "mislocalized to hair/non-eyelid vertices",
        },
    }
    a.output_json.parent.mkdir(parents=True, exist_ok=True)
    a.output_json.write_text(json.dumps(out, indent=2), encoding="utf-8")
    a.forensic_json.parent.mkdir(parents=True, exist_ok=True)
    a.forensic_json.write_text(json.dumps(forensic, indent=2), encoding="utf-8")
    evaluated.to_mesh_clear()


if __name__ == "__main__":
    main()
