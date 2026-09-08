#!/usr/bin/env python3
"""FAST-06R1.5 — topology-aware upper-eyelid surface-following morph rebuild."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
import numpy as np


def args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input-glb", type=Path, required=True)
    p.add_argument("--base-morph-json", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    p.add_argument("--forensic-json", type=Path, required=True)
    return p.parse_args(argv)


def gltf_delta(delta_world: np.ndarray) -> np.ndarray:
    return np.array([delta_world[0], delta_world[2], -delta_world[1]], dtype=np.float64)


def smoothstep01(value: float) -> float:
    t = min(1.0, max(0.0, value))
    return t * t * (3.0 - 2.0 * t)


def rows(deltas: dict[int, np.ndarray]):
    return [[i, float(d[0]), float(d[1]), float(d[2])] for i, d in sorted(deltas.items())]


def main():
    a = args()
    base = json.loads(a.base_morph_json.read_text(encoding="utf-8"))

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(a.input_glb))
    obj = next(o for o in bpy.data.objects if o.type == "MESH")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    world = np.array([tuple(evaluated.matrix_world @ v.co) for v in evaluated_mesh.vertices])

    specs = {
        "PRES_Blink_L": {"cx": 0.132, "rx": 0.034},
        "PRES_Blink_R": {"cx": 0.041, "rx": 0.036},
    }
    closed_arc_height = 0.003
    sphere_center_y = -0.137
    sphere_radius = 0.039

    forensic_eyes = {}
    for name, spec in specs.items():
        cx = spec["cx"]
        old_rows = base["shapeKeys"][name]
        upper_seed_ids = [int(row[0]) for row in old_rows if float(row[2]) < -1e-5]
        lower_seed_ids = [int(row[0]) for row in old_rows if float(row[2]) > 1e-5]
        # Upper lid travels down to the lower lash line; lower-lid vertices stay fixed.
        seam_z = float(np.quantile(world[lower_seed_ids, 2], 0.10))
        rx = max(spec["rx"], max(abs(float(world[i, 0]) - cx) for i in upper_seed_ids) * 1.02)
        deltas: dict[int, np.ndarray] = {}
        moved = []
        anchors = []
        excluded_lower = list(lower_seed_ids)

        for vi in upper_seed_ids:
            x, y, z = world[vi]
            u = (x - cx) / rx
            if abs(u) > 1.0:
                continue

            # Inner/outer canthus remain exact anchors.
            lid_weight = smoothstep01((0.92 - abs(u)) / 0.72)
            if lid_weight <= 1e-6:
                anchors.append(int(vi))
                continue

            closed_z = seam_z + closed_arc_height * (1.0 - u * u)
            dz = lid_weight * (closed_z - z)

            # Follow the estimated eyeball sphere toward its front tangent.
            radial_sq = max(
                1e-8,
                sphere_radius * sphere_radius
                - (x - cx) * (x - cx)
                - (closed_z - seam_z) * (closed_z - seam_z),
            )
            sphere_y = sphere_center_y - math.sqrt(radial_sq)
            dy_surface = min(0.002, max(-0.008, sphere_y - y))
            dy = lid_weight * dy_surface

            delta = gltf_delta(np.array([0.0, dy, dz], dtype=np.float64))
            if np.linalg.norm(delta) > 1e-9:
                deltas[int(vi)] = delta
                moved.append(
                    {
                        "vertexId": int(vi),
                        "worldNeutral": [float(x), float(y), float(z)],
                        "u": float(u),
                        "lidWeight": float(lid_weight),
                        "worldDelta": [0.0, float(dy), float(dz)],
                    }
                )

        base["shapeKeys"][name] = rows(deltas)
        forensic_eyes[name] = {
            "centerX": cx,
            "radiusX": rx,
            "closedSeamZ": seam_z,
            "upperLidMovedVertexCount": len(deltas),
            "upperLidMovedVertexIds": sorted(deltas),
            "canthusAnchorVertexIds": sorted(set(anchors)),
            "lowerLidExcludedVertexIds": sorted(set(excluded_lower)),
            "movedVertices": moved,
        }

    base["revision"] = "FAST-06R1.5_ANATOMICAL_EYELID_SURFACE_FOLLOWING"
    base["blinkContract"] = {
        "upperLidOnly": True,
        "lowerLidMovement": 0.0,
        "canthusAnchored": True,
        "eyeballSurfaceFollowing": True,
        "leftRightTimingOwnedBySingleSynchronizedRuntimeWeight": True,
    }
    base["presentationZones"]["blinkLeftVertexCount"] = len(base["shapeKeys"]["PRES_Blink_L"])
    base["presentationZones"]["blinkRightVertexCount"] = len(base["shapeKeys"]["PRES_Blink_R"])

    forensic = {
        "revision": base["revision"],
        "method": "open upper-lid arc extraction + fixed canthi + estimated eyeball sphere tangent",
        "parameters": {
            "closedArcHeight": closed_arc_height,
            "sphereCenterY": sphere_center_y,
            "sphereRadius": sphere_radius,
            "upperContourSource": "R1.4 vertices whose closure delta moved downward",
            "seamSource": "10th percentile lower lash line; lower-lid vertices remain unchanged",
        },
        "eyes": forensic_eyes,
        "lockedActuatorsPreservedFrom": str(a.base_morph_json),
        "nonBlinkMorphsExact": True,
    }
    a.output_json.write_text(json.dumps(base, indent=2), encoding="utf-8")
    a.forensic_json.write_text(json.dumps(forensic, indent=2), encoding="utf-8")
    evaluated.to_mesh_clear()


if __name__ == "__main__":
    main()
