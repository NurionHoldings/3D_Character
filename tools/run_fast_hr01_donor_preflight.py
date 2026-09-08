#!/usr/bin/env python3
"""FAST-HR01 — HM08 DerivedHead v1 MVP donor preflight STOP GATE."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
CANDIDATE = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition/candidate_a_makehuman_hm08"
DONOR = CANDIDATE / "derived_v1_basis_nd/NURION_DerivedHead_v1_basis_skin.obj"
RIG = CANDIDATE / "derived_v1_basis_nd/NURION_DerivedHead_v1_basis_rig_helpers.obj"
BOUNDARY = CANDIDATE / "derived_v1_basis_nd/BOUNDARY_LOOP_MAP.json"
MORPH_SPEC = CANDIDATE / "derived_v1_basis_nd/MORPH_SPEC.json"
NUMERIC = CANDIDATE / "derived_v1_basis_nd/NUMERIC_VALIDATION.json"
REGIONS = CANDIDATE / "HEAD_REGION_MAP.json"
WEIGHTS = CANDIDATE / "derived_v1_weights/JAW_LIP_WEIGHT_MAP.json"
DEFORM = CANDIDATE / "derived_v1_weights/DEFORM_NUMERIC_VALIDATION.json"
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
RECEIPT = WORK / "evidence/FAST-HR01_donor_preflight_receipt.json"
EXPECTED_SHA = "9066b8bebbf33ead9b39e403ecd59604e7bb3947cea401c3c94b1b6065307243"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj_counts(path: Path):
    vertices = faces = 0
    groups: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            vertices += 1
        elif line.startswith("f "):
            faces += 1
        elif line.startswith("g "):
            groups.update(line.split()[1:])
    return vertices, faces, sorted(groups)


def main():
    boundary = read(BOUNDARY)
    morph = read(MORPH_SPEC)
    numeric = read(NUMERIC)
    regions = read(REGIONS)
    weights = read(WEIGHTS)
    deform = read(DEFORM)
    vertex_count, face_count, _ = obj_counts(DONOR)
    _, _, rig_groups = obj_counts(RIG)

    loop_ids = {row["loopId"]: row for row in boundary["entries"]}
    required_rig_groups = {
        "joint-l-upperlid",
        "joint-l-lowerlid",
        "joint-r-upperlid",
        "joint-r-lowerlid",
        "helper-l-eyelashes-1",
        "helper-l-eyelashes-2",
        "helper-r-eyelashes-1",
        "helper-r-eyelashes-2",
    }
    eyelid_weights = weights.get("eyelidWeights", {})
    gates = {
        "donorShaPinned": sha256(DONOR) == EXPECTED_SHA,
        "numericTopologyPass": numeric.get("pass") is True,
        "vertexCountExact": vertex_count == numeric.get("vertexCount") == 4261,
        "faceCountExact": face_count == numeric.get("faceCount") == 4152,
        "manifold": numeric.get("nonManifoldEdges") == 0,
        "neckBoundary58": loop_ids.get("BND_NECK_CUT", {}).get("vertexCount") == 58,
        "oralOuterBoundary70": loop_ids.get("BND_ORAL_OPENING_OUTER", {}).get("vertexCount") == 70,
        "oralInnerBoundary64": loop_ids.get("BND_ORAL_OPENING_INNER", {}).get("vertexCount") == 64,
        "eyelidRegionReady": len(regions["regions"].get("EYELID", [])) >= 158,
        "lipRegionReady": len(regions["regions"].get("LIPS", [])) >= 838,
        "fourEyelidWeightFields": set(eyelid_weights) == {
            "LEFT_UPPER",
            "LEFT_LOWER",
            "RIGHT_UPPER",
            "RIGHT_LOWER",
        }
        and all(len(v) > 0 for v in eyelid_weights.values()),
        "eyelidRigHelpersPresent": required_rig_groups.issubset(set(rig_groups)),
        "jawDeformNumericPass": deform.get("pass") is True,
        "blinkMorphContractPresent": morph["morphs"]["eyeBlinkOpen"]["method"]
        == "HELPER_EYELID_MORPH_ONLY",
        "jawMorphContractPresent": morph["morphs"]["jawOpen"]["method"] == "RIG_JOINT_ROTATION",
    }
    passed = all(gates.values())
    receipt = {
        "receiptId": f"FAST-HR01_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "stage": "FAST_HEAD_REPLACEMENT_DONOR_PREFLIGHT",
        "verdict": "PASS_MVP_DONOR_PREFLIGHT" if passed else "FAIL_STOP",
        "productionEligibility": "NOT_ASSERTED",
        "knownDisclosure": "Existing broad semantic QA SAFE_ABORT remains; this gate is limited to MVP eyelid/lip/neck topology.",
        "donor": {
            "path": str(DONOR),
            "sha256": sha256(DONOR),
            "vertexCount": vertex_count,
            "faceCount": face_count,
        },
        "gates": gates,
        "eyelidWeightCounts": {k: len(v) for k, v in eyelid_weights.items()},
        "rigHelperGroups": sorted(required_rig_groups),
        "boundaryLoops": {
            key: {
                "vertexCount": row.get("vertexCount", row.get("partitionVertexCount")),
                "role": row["role"],
            }
            for key, row in loop_ids.items()
        },
        "nextStage": "HEAD_ASSEMBLY" if passed else "SELECT_NEW_DONOR",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"verdict": receipt["verdict"], "receipt": str(RECEIPT)}, ensure_ascii=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
