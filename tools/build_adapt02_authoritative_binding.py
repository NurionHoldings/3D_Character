#!/usr/bin/env python3
"""Generate ADAPT-02 authoritative binding + snapshots + provenance receipt from locked upstream."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.authoritative_binding import (
    AUTHORITATIVE_AXIS_REL,
    AUTHORITATIVE_AXIS_SHA256,
    AUTHORITATIVE_BODY_SPEC_ID,
    AUTHORITATIVE_BODY_SPEC_REL,
    AUTHORITATIVE_BODY_SPEC_SHA256,
    AUTHORITATIVE_AXIS_ID,
    derive_from_upstream_files,
    snapshot_digest,
)
from fast_track.adaptation.inspector import sha256_file

SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
EV = ROOT / "fast_track/working/adaptation_engine_v1/evidence"


def main() -> None:
    bone_path = ROOT / AUTHORITATIVE_BODY_SPEC_REL
    axis_path = ROOT / AUTHORITATIVE_AXIS_REL
    derived = derive_from_upstream_files(bone_path, axis_path)

    body_snap_path = SEM / "NURION_ADAPT02_BODY_CORE_SNAPSHOT_V1.json"
    axis_snap_path = SEM / "NURION_ADAPT02_AXIS_SNAPSHOT_V1.json"
    body_snap_path.write_text(
        json.dumps(derived["bodyCoreSnapshot"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    axis_snap_path.write_text(
        json.dumps(derived["axisSnapshot"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    body_snap = derived["bodyCoreSnapshot"]
    axis_snap = derived["axisSnapshot"]

    binding = {
        "schema": "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1",
        "revision": "R2",
        "role": "CONSUME_ONLY cryptographically pinned snapshot binding for ADAPT-02",
        "upstream": derived["upstream"],
        "snapshot": derived["snapshot"],
        "bodyCore23": body_snap["bones"],
        "hierarchy": body_snap["hierarchy"],
        "adapt01RoleToCanonical": {
            "root": "NURION_root",
            "pelvis": "NURION_pelvis",
            "spine": "NURION_spine01",
            "chest": "NURION_chest",
            "neck": "NURION_neck",
            "head": "NURION_head",
            "clavicle_L": "NURION_clavicle_L",
            "clavicle_R": "NURION_clavicle_R",
            "upperArm_L": "NURION_upperArm_L",
            "upperArm_R": "NURION_upperArm_R",
            "lowerArm_L": "NURION_lowerArm_L",
            "lowerArm_R": "NURION_lowerArm_R",
            "hand_L": "NURION_hand_L",
            "hand_R": "NURION_hand_R",
            "thigh_L": "NURION_thigh_L",
            "thigh_R": "NURION_thigh_R",
            "calf_L": "NURION_calf_L",
            "calf_R": "NURION_calf_R",
            "foot_L": "NURION_foot_L",
            "foot_R": "NURION_foot_R",
            "toe_L": "NURION_toe_L",
            "toe_R": "NURION_toe_R",
        },
        "requiredMajorSemantics": [
            "NURION_root",
            "NURION_pelvis",
            "NURION_spine01",
            "NURION_chest",
            "NURION_neck",
            "NURION_head",
            "NURION_upperArm_L",
            "NURION_upperArm_R",
            "NURION_thigh_L",
            "NURION_thigh_R",
        ],
        "canonicalAxis": {
            "up": axis_snap["up"],
            "forward": axis_snap["forward"],
            "right": axis_snap["right"],
            "handedness": axis_snap["handedness"],
        },
        "invariants": {
            "rootPelvisDistinct": True,
            "rootPelvisNeverMerge": body_snap["invariants"]["rootPelvisNeverMerge"],
            "faceRigCreation": "DENY_IN_ADAPT02",
        },
    }
    binding_path = SEM / "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1.json"
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    provenance = {
        "schema": "NURION_ADAPT02_UPSTREAM_PROVENANCE_RECEIPT_V1",
        "revision": "R2",
        "derivation": "READ_ONLY_EXTRACT",
        "generatedFromMonorepo": True,
        "upstream": derived["upstream"],
        "snapshot": derived["snapshot"],
        "observedUpstreamSha256": derived["observedUpstreamSha256"],
        "snapshotFileSha256": {
            "bodyCoreSnapshot": sha256_file(body_snap_path),
            "axisSnapshot": sha256_file(axis_snap_path),
        },
        "bindingSha256": sha256_file(binding_path),
        "policy": "Pins must match authoritative_binding.AUTHORITATIVE_* constants; mismatch = FAIL CLOSED",
        "nurionV1Mutation": "NONE",
        "autoRepair": "DENY",
    }
    prov_path = EV / "NURION-ADAPT-02_UPSTREAM_PROVENANCE_RECEIPT.json"
    prov_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "bodyCanonicalSpecSha256": AUTHORITATIVE_BODY_SPEC_SHA256,
                "axisRetargetConventionSha256": AUTHORITATIVE_AXIS_SHA256,
                "bodyCoreDigest": derived["snapshot"]["bodyCoreDigest"],
                "axisConventionDigest": derived["snapshot"]["axisConventionDigest"],
                "binding": str(binding_path),
                "provenance": str(prov_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
