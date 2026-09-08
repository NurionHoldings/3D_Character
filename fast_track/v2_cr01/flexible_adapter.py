"""V2-CR-01 Flexible Semantic Adapter orchestrator — P01…P04 + result package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.v2_cr01.retarget_safety import validate_retarget_safety
from fast_track.v2_cr01.semantic_assignment import assign_semantics
from fast_track.v2_cr01.skeleton_inspection import inspect_skeleton
from fast_track.v2_cr01.torso_chain import discover_torso_chain

REPORT_SCHEMA = "NURION_V2_CR01_FLEXIBLE_ADAPTER_RESULT_V1"


def run_flexible_adapter(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    before = path.read_bytes()
    source_sha = sha256_file(path)

    p01 = inspect_skeleton(path)
    p02 = discover_torso_chain(p01) if p01.get("status") == "PASS" else {
        "schema": "NURION_V2_CR01_TORSO_CHAIN_DISCOVERY_V1",
        "stage": "CR01-P02",
        "status": "BLOCKED",
        "blockers": [{"code": "UPSTREAM_P01_BLOCKED"}],
        "anchors": {},
        "orderedTorsoChain": [],
        "orderedTorsoChainIndices": [],
        "ambiguities": [],
    }
    p03 = assign_semantics(p01, p02) if p02.get("status") == "PASS" else {
        "schema": "NURION_V2_CR01_SEMANTIC_ASSIGNMENT_V1",
        "stage": "CR01-P03",
        "status": "BLOCKED",
        "semanticAssignments": {},
        "intermediateBones": [],
        "unusedPreservedBones": [],
        "blockers": [{"code": "UPSTREAM_P02_BLOCKED"}],
        "ambiguities": [],
        "adapterDigest": None,
    }
    p04 = validate_retarget_safety(p01, p03) if p03.get("status") == "PASS" else {
        "schema": "NURION_V2_CR01_RETARGET_SAFETY_V1",
        "stage": "CR01-P04",
        "status": "BLOCKED",
        "chainValidation": {},
        "blockers": [{"code": "UPSTREAM_P03_BLOCKED"}],
    }

    after = path.read_bytes()
    preserved = before == after and source_sha == sha256_file(path)

    stages = {
        "CR01-P01": p01.get("status"),
        "CR01-P02": p02.get("status"),
        "CR01-P03": p03.get("status"),
        "CR01-P04": p04.get("status"),
    }
    overall = "PASS" if all(v == "PASS" for v in stages.values()) and preserved else "BLOCKED"

    mapping_view = {
        k: v.get("sourceBone")
        for k, v in (p03.get("semanticAssignments") or {}).items()
        if v.get("status") == "RESOLVED"
    }
    chest = (p03.get("semanticAssignments") or {}).get("NURION_chest") or {}

    result = {
        "schema": REPORT_SCHEMA,
        "changeRequestId": "V2-CR-01",
        "engineV1": "CLOSED / PASS / CONSUME ONLY",
        "v2Engine": "NOT OPEN",
        "sourceIdentity": {
            "path": str(path),
            "sha256": source_sha,
            "byteLength": len(before),
        },
        "sourceSkeletonDigest": p01.get("sourceSkeletonDigest"),
        "orderedBodyChains": {
            "torso": p02.get("orderedTorsoChain"),
            "chainValidation": p04.get("chainValidation"),
        },
        "semanticAssignments": p03.get("semanticAssignments"),
        "mappingView": mapping_view,
        "chestEvidence": chest.get("evidence"),
        "intermediateBones": p03.get("intermediateBones"),
        "unusedPreservedBones": p03.get("unusedPreservedBones"),
        "assignmentEvidence": {
            k: v.get("evidence") for k, v in (p03.get("semanticAssignments") or {}).items()
        },
        "ambiguities": (p02.get("ambiguities") or []) + (p03.get("ambiguities") or []),
        "blockedReasons": (p01.get("blockers") or [])
        + (p02.get("blockers") or [])
        + (p03.get("blockers") or [])
        + (p04.get("blockers") or []),
        "retargetCompatibility": p04,
        "sourcePreservation": {
            "bytesUnchanged": preserved,
            "sourceAssetSha256Before": source_sha,
            "sourceAssetSha256After": sha256_file(path),
        },
        "adapterDigest": p03.get("adapterDigest"),
        "stages": stages,
        "status": overall,
        "stagesDetail": {"P01": p01, "P02": p02, "P03": p03, "P04": p04},
        "policy": {
            "idle15Hardcoding": "DENY",
            "expectedMappingAsOracleOnly": True,
            "topologyEvidenceRequired": True,
        },
    }
    # Recompute top-level digest excluding path/local noise
    result["semanticAdapterDigest"] = canonical_sha256(
        {
            "sourceSha256": source_sha,
            "sourceSkeletonDigest": result["sourceSkeletonDigest"],
            "orderedTorsoChain": p02.get("orderedTorsoChain"),
            "semanticAssignments": {
                k: {
                    "sourceBone": v.get("sourceBone"),
                    "evidence": v.get("evidence"),
                    "classification": v.get("classification"),
                    "status": v.get("status"),
                }
                for k, v in sorted((p03.get("semanticAssignments") or {}).items())
            },
            "intermediateBones": p03.get("intermediateBones"),
            "chainValidation": p04.get("chainValidation"),
        }
    )
    return result
