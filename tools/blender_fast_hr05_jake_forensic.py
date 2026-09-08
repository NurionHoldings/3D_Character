#!/usr/bin/env python3
"""FAST-HR05 — Jake.fbx facial donor forensic (technical; GREEN requires pinned license)."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy


def parse_args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", type=Path, required=True)
    p.add_argument("--out-json", type=Path, required=True)
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images, bpy.data.actions):
        for block in list(coll):
            coll.remove(block)


def shape_key_names(obj):
    if not obj.data or not obj.data.shape_keys:
        return []
    return [kb.name for kb in obj.data.shape_keys.key_blocks]


def classify_shape(name: str) -> str:
    n = name.lower()
    rules = [
        ("blink", "EYE_BLINK"),
        ("squint", "EYE_SQUINT"),
        ("wide", "EYE_WIDE"),
        ("brow", "BROW"),
        ("cheek", "CHEEK"),
        ("smile", "MOUTH_SMILE"),
        ("frown", "MOUTH_FROWN"),
        ("pucker", "MOUTH_PUCKER"),
        ("funnel", "MOUTH_PUCKER"),
        ("jaw", "JAW"),
        ("open", "MOUTH_OPEN"),
        ("viseme", "SPEECH_VISEME"),
        ("aa", "SPEECH_VISEME"),
        ("ee", "SPEECH_VISEME"),
        ("ih", "SPEECH_VISEME"),
        ("oh", "SPEECH_VISEME"),
        ("ou", "SPEECH_VISEME"),
        ("mbp", "SPEECH_PLOSIVE"),
        ("fv", "SPEECH_DENTAL"),
        ("dimple", "DIMPLE"),
        ("nose", "NOSE"),
        ("tongue", "TONGUE"),
        ("eye", "EYE_OTHER"),
        ("mouth", "MOUTH_OTHER"),
        ("lip", "MOUTH_OTHER"),
    ]
    for token, label in rules:
        if token in n:
            return label
    return "OTHER"


def essential_coverage(shape_names: list[str]) -> dict:
    joined = " | ".join(shape_names).lower()
    checks = {
        "eyeBlinkLeft": any(x in joined for x in ("eyeblinkleft", "blink_l", "blinkleft", "blink.l")),
        "eyeBlinkRight": any(x in joined for x in ("eyeblinkright", "blink_r", "blinkright", "blink.r")),
        "jawOpen": any(x in joined for x in ("jawopen", "mouthopen", "jaw_open", "mouth_open")),
        "mouthSmileLeft": any(x in joined for x in ("mouthsmileleft", "smile_l", "smileleft", "smile.l")),
        "mouthSmileRight": any(x in joined for x in ("mouthsmileright", "smile_r", "smileright", "smile.r")),
        "browPresent": "brow" in joined,
        "squintPresent": "squint" in joined,
        "cheekPresent": "cheek" in joined,
        "visemeOrSpeechPresent": any(x in joined for x in ("viseme", "aa", "ee", "oh", "ou", "mbp", "fv")),
    }
    return checks


def main():
    args = parse_args()
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(args.fbx), automatic_bone_orientation=True)

    meshes = []
    armatures = []
    all_shapes = []
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            sk = shape_key_names(obj)
            all_shapes.extend([s for s in sk if s != "Basis"])
            meshes.append(
                {
                    "name": obj.name,
                    "vertexCount": len(obj.data.vertices),
                    "polygonCount": len(obj.data.polygons),
                    "shapeKeyCount": max(0, len(sk) - (1 if "Basis" in sk else 0)),
                    "shapeKeys": sk,
                    "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
                    "parent": obj.parent.name if obj.parent else None,
                    "parentType": obj.parent_type,
                    "parentBone": obj.parent_bone or None,
                }
            )
        elif obj.type == "ARMATURE":
            bone_names = [b.name for b in obj.data.bones]
            faceish = [
                b
                for b in bone_names
                if any(k in b.lower() for k in ("eye", "lid", "jaw", "mouth", "brow", "cheek", "face", "head", "tongue", "teeth"))
            ]
            armatures.append(
                {
                    "name": obj.name,
                    "boneCount": len(bone_names),
                    "bones": bone_names,
                    "faceRelatedBones": faceish,
                }
            )

    class_counts = {}
    classified = []
    for name in all_shapes:
        label = classify_shape(name)
        class_counts[label] = class_counts.get(label, 0) + 1
        classified.append({"name": name, "class": label})

    coverage = essential_coverage(all_shapes)
    whitelist_candidates = [
        row["name"]
        for row in classified
        if row["class"]
        in {
            "EYE_BLINK",
            "EYE_SQUINT",
            "EYE_WIDE",
            "BROW",
            "CHEEK",
            "MOUTH_SMILE",
            "MOUTH_FROWN",
            "MOUTH_PUCKER",
            "JAW",
            "MOUTH_OPEN",
            "SPEECH_VISEME",
            "SPEECH_PLOSIVE",
            "SPEECH_DENTAL",
            "MOUTH_OTHER",
            "EYE_OTHER",
        }
    ]

    report = {
        "stage": "FAST-HR05_JAKE_FACIAL_DONOR_FORENSIC",
        "assetPath": str(args.fbx),
        "meshCount": len(meshes),
        "armatureCount": len(armatures),
        "totalShapeKeysExcludingBasis": len(all_shapes),
        "uniqueShapeKeys": sorted(set(all_shapes)),
        "shapeClassCounts": class_counts,
        "classifiedShapes": classified,
        "essentialCoverage": coverage,
        "whitelistCandidates": sorted(set(whitelist_candidates)),
        "meshes": meshes,
        "armatures": armatures,
        "legacyAdapterReminder": {
            "PRES_SmileMild": ["FACE_mouthSmileLeft", "FACE_mouthSmileRight"],
            "renameToPresSmile": "DENY",
        },
        "canonicalTarget": "NURION FACE Canonical v1",
        "productUse": False,
        "assetRole": "HR05 facial reference/donor",
    }

    # Technical readiness for continuing forensic analysis (not GREEN license gate).
    technical_pass = (
        report["totalShapeKeysExcludingBasis"] > 0
        and coverage.get("eyeBlinkLeft")
        and coverage.get("eyeBlinkRight")
        and coverage.get("jawOpen")
    )
    report["technicalForensicVerdict"] = "PASS_FACIAL_READY_CANDIDATE" if technical_pass else "HOLD_INSUFFICIENT_FACIAL_SHAPES"
    report["officialGreenStart"] = False
    report["officialGreenBlockedBy"] = "LICENSE_PROVENANCE_NOT_PINNED"

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(args.out_json),
        "shapeCount": report["totalShapeKeysExcludingBasis"],
        "technicalForensicVerdict": report["technicalForensicVerdict"],
        "essentialCoverage": coverage,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
