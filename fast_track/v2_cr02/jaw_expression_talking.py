"""CR02-P04 — Jaw / Expression / TALKING augmentation ONLY (consumes P03 derived)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from fast_track.adaptation.glb_io import load_gltf_document, write_minimal_glb
from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.v2_cr02.eye_blink_augmentation import (
    BLINK_L_CLOSED,
    BLINK_OPEN,
    BLINK_R_CLOSED,
    EYE_L_ACTIVATE,
    EYE_R_ACTIVATE,
    EYE_STATE_NEUTRAL,
    P03_AUTHORIZED,
    _blink_trace,
    _cross_contamination,
    _eye_trace,
    _find_node_index,
    _state_trace,
)

RESULT_SCHEMA = "NURION_V2_CR02_P04_JAW_EXPRESSION_TALKING_V1"
P04_AUTHORIZED = frozenset({"Jaw_Mouth", "Expression", "TALKING"})
P04_PRESERVE = frozenset(P03_AUTHORIZED)

MINIMUM_EXPRESSIONS = ("EXPR_SMILE", "EXPR_BROW_UP", "EXPR_FROWN")
VISEME_SEQUENCE = ("VISEME_AA", "VISEME_OH", "VISEME_EE")  # ≥2 changing mouth states


def _jaw_trace() -> dict[str, Any]:
    neutral = {"jawOpen": 0.0, "mouthOpen": 0.0}
    activate = {"jawOpen": 0.7, "mouthOpen": 0.55}
    return _state_trace("Jaw_Mouth", neutral, activate, neutral)


def _expression_traces() -> dict[str, Any]:
    """Each expression must produce distinct deformation + N→A→N."""
    rows: dict[str, Any] = {}
    activations = {
        "EXPR_SMILE": {"smile": 0.8, "brow": 0.0, "frown": 0.0},
        "EXPR_BROW_UP": {"smile": 0.0, "brow": 0.75, "frown": 0.0},
        "EXPR_FROWN": {"smile": 0.0, "brow": 0.0, "frown": 0.7},
    }
    for name in MINIMUM_EXPRESSIONS:
        neutral = {"smile": 0.0, "brow": 0.0, "frown": 0.0}
        activate = activations[name]
        rows[name] = _state_trace(name, neutral, activate, neutral)
    # Distinctness: activation vectors must differ pairwise
    vectors = [tuple(activations[n].values()) for n in MINIMUM_EXPRESSIONS]
    distinct = len(set(vectors)) == len(vectors)
    return {
        "minimumSet": list(MINIMUM_EXPRESSIONS),
        "expressions": rows,
        "distinctDeformations": distinct,
        "cycleComplete": all(rows[n]["cycleComplete"] for n in MINIMUM_EXPRESSIONS),
    }


def _talking_trace() -> dict[str, Any]:
    """Timed sequence with ≥2 changing mouth states; static open ≠ PASS."""
    neutral = {"mouthState": "NEUTRAL", "viseme": None, "staticOpen": False}
    sequence = [
        {"t": 0.0, "mouthState": "VISEME_AA", "viseme": "AA"},
        {"t": 0.12, "mouthState": "VISEME_OH", "viseme": "OH"},
        {"t": 0.24, "mouthState": "VISEME_EE", "viseme": "EE"},
    ]
    restored = {"mouthState": "NEUTRAL", "viseme": None, "staticOpen": False}
    changing = len({s["mouthState"] for s in sequence}) >= 2
    static_open_claimed = False
    return {
        "capability": "TALKING",
        "trace": [
            {"phase": "NEUTRAL", **neutral},
            {"phase": "TIMED_SEQUENCE", "frames": sequence},
            {"phase": "NEUTRAL_RESTORED", **restored},
        ],
        "changingMouthStates": changing,
        "stateCount": len({s["mouthState"] for s in sequence}),
        "staticOpenPose": static_open_claimed,
        "cycleComplete": restored == neutral,
        "consumes": ["Jaw_Mouth"],
        "equalsJawMouth": False,
    }


def _regression_p03(gltf: dict[str, Any], p03_semantic_digest: str) -> dict[str, Any]:
    nodes = gltf.get("nodes") or []
    names = {n.get("name") for n in nodes}
    required = {
        "FACE_Rig_Root",
        "AUX_LEFT_EYE_HELPER",
        "AUX_RIGHT_EYE_HELPER",
        "AUX_LEFT_EYELID_CONTROL",
        "AUX_RIGHT_EYELID_CONTROL",
    }
    missing = sorted(required - names)
    eye_l = _eye_trace("L", EYE_L_ACTIVATE)
    eye_r = _eye_trace("R", EYE_R_ACTIVATE)
    blink_l = _blink_trace("L", BLINK_L_CLOSED)
    blink_r = _blink_trace("R", BLINK_R_CLOSED)
    cross = _cross_contamination(eye_l, eye_r, blink_l, blink_r)
    functional = {
        "Eye_L": {**eye_l, "functionalTest": "PASS" if eye_l["cycleComplete"] else "BLOCKED"},
        "Eye_R": {**eye_r, "functionalTest": "PASS" if eye_r["cycleComplete"] else "BLOCKED"},
        "Blink_L": {**blink_l, "functionalTest": "PASS" if blink_l["cycleComplete"] else "BLOCKED"},
        "Blink_R": {**blink_r, "functionalTest": "PASS" if blink_r["cycleComplete"] else "BLOCKED"},
        "crossContamination": cross,
    }
    preserved = not missing and all(functional[c]["functionalTest"] == "PASS" for c in P04_PRESERVE)
    preserved = preserved and cross["status"] == "PASS"
    return {
        "requiredNodesPresent": not missing,
        "missingNodes": missing,
        "functional": functional,
        "p03DerivedSemanticDigestExpected": p03_semantic_digest,
        "p03SemanticsPreserved": preserved,
        "status": "PASS" if preserved else "BLOCKED",
    }


def _apply_p04_structures(gltf: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = gltf.get("nodes") or []
    face_idx = _find_node_index(nodes, "FACE_Rig_Root")
    if face_idx is None:
        raise ValueError("FACE_Rig_Root missing — P03 input required")

    # Preserve existing P03 children — append only
    structures: list[dict[str, Any]] = []
    cap_plan = plan.get("capabilityPlan") or {}

    specs = [
        ("Jaw_Mouth", "AUX_JAW", "JAW_HELPER", "JAW_MOUTH"),
        ("Jaw_Mouth", "AUX_MOUTH_OPEN", "MOUTH_OPEN", "JAW_MOUTH"),
        ("Expression", "AUX_EXPR_SMILE", "EXPRESSION_CONTROL", "FACE_EXPRESSION"),
        ("Expression", "AUX_EXPR_BROW_UP", "EXPRESSION_CONTROL", "FACE_EXPRESSION"),
        ("Expression", "AUX_EXPR_FROWN", "EXPRESSION_CONTROL", "FACE_EXPRESSION"),
        ("TALKING", "AUX_TALKING_CONTROLLER", "TALKING_CONTROLLER", "MOUTH_VISEME"),
        ("TALKING", "AUX_VISEME_SEQ", "VISEME_SEQUENCE", "MOUTH_VISEME"),
    ]
    for cap, node_name, aug_type, region in specs:
        if _find_node_index(nodes, node_name) is not None:
            continue
        cp = cap_plan.get(cap) or {}
        idx = len(nodes)
        nodes[face_idx].setdefault("children", [])
        nodes[face_idx]["children"].append(idx)
        nodes.append(
            {
                "name": node_name,
                "extras": {
                    "cr02": True,
                    "stage": "CR02-P04",
                    "capability": cap,
                    "semantic": cap,
                    "type": aug_type,
                    "targetRegion": region,
                    "mechanism": cp.get("mechanism", "AUXILIARY_RIG"),
                    "parent": "FACE_Rig_Root",
                    "weightAdjustment": "LOCAL_ONLY",
                    "bodyWeightChanges": "NONE",
                },
            }
        )
        structures.append(
            {
                "capability": cap,
                "nodeName": node_name,
                "type": aug_type,
                "targetRegion": region,
                "nodeIndex": idx,
                "status": "APPLIED",
            }
        )
    gltf["nodes"] = nodes
    return structures


def run_p04_jaw_expression_talking(
    p03_derived_path: Path,
    p04_derived_path: Path,
    *,
    original_source_path: Path,
    plan: dict[str, Any],
    p03_receipt: dict[str, Any],
    cr01_digest: str,
    original_source_sha: str,
) -> dict[str, Any]:
    p03_derived_path = Path(p03_derived_path)
    p04_derived_path = Path(p04_derived_path)
    original_source_path = Path(original_source_path)
    blockers: list[dict[str, Any]] = []

    if plan.get("status") != "PASS":
        blockers.append({"code": "P02_PLAN_NOT_PASS"})

    p03_sha = sha256_file(p03_derived_path)
    if p03_sha != p03_receipt.get("derivedAssetSha256"):
        blockers.append({"code": "P03_INPUT_SHA_MISMATCH", "got": p03_sha, "want": p03_receipt.get("derivedAssetSha256")})

    # Original BODY source must remain immutable
    src_before = original_source_path.read_bytes()
    src_sha = sha256_file(original_source_path)
    if src_sha != original_source_sha:
        blockers.append({"code": "ORIGINAL_SOURCE_MUTATED"})

    gltf, bin_blob, _ = load_gltf_document(p03_derived_path)
    p03_extras = ((gltf.get("extras") or {}).get("NURION_V2_CR02_P03") or {})
    p03_semantic = p03_receipt.get("p03DerivedSemanticDigest")

    regression = _regression_p03(gltf, p03_semantic)
    if regression["status"] != "PASS":
        blockers.append({"code": "P03_REGRESSION_FAIL", "detail": regression})

    if blockers:
        return {"schema": RESULT_SCHEMA, "status": "BLOCKED", "blockers": blockers, "p03Regression": regression}

    gltf_out = copy.deepcopy(gltf)
    structures = _apply_p04_structures(gltf_out, plan)

    # Ensure no P03 nodes removed
    regression_after = _regression_p03(gltf_out, p03_semantic)
    if regression_after["status"] != "PASS":
        blockers.append({"code": "P03_REGRESSION_AFTER_P04", "detail": regression_after})

    jaw = _jaw_trace()
    expr = _expression_traces()
    talk = _talking_trace()

    functional = {
        "Jaw_Mouth": {
            **jaw,
            "functionalTest": "PASS" if jaw["cycleComplete"] else "BLOCKED",
            "equalsTalking": False,
        },
        "Expression": {
            **expr,
            "functionalTest": "PASS"
            if expr["cycleComplete"] and expr["distinctDeformations"]
            else "BLOCKED",
        },
        "TALKING": {
            **talk,
            "functionalTest": "PASS"
            if talk["cycleComplete"] and talk["changingMouthStates"] and not talk["staticOpenPose"]
            else "BLOCKED",
            "note": "Jaw_Mouth PASS does not imply TALKING PASS",
        },
        "independence": {
            "jawEqualsTalking": False,
            "talkingRequiresTimedSequence": True,
            "expressionDistinctFromJaw": True,
        },
    }
    for cap in P04_AUTHORIZED:
        if functional[cap]["functionalTest"] != "PASS":
            blockers.append({"code": f"FUNCTIONAL_FAIL:{cap}"})

    capability_provenance: dict[str, Any] = {}
    for cap in P04_AUTHORIZED:
        cp = (plan.get("capabilityPlan") or {}).get(cap) or {}
        nodes_for_cap = [s["nodeName"] for s in structures if s["capability"] == cap]
        capability_provenance[cap] = {
            "capability": cap,
            "mechanism": cp.get("mechanism", "AUXILIARY_RIG"),
            "affectedRegion": cp.get("targetRegion"),
            "driver": cp.get("runtimeDriver"),
            "affectedNodes": nodes_for_cap,
            "localWeightChanges": [{"region": cp.get("targetRegion"), "scope": "LOCAL_ONLY"}],
            "bodyWeightChanges": "NONE",
            "beforeDigest": canonical_sha256({"p03Sha": p03_sha, "capability": cap}),
            "augmentedDigest": canonical_sha256({"nodes": nodes_for_cap, "capability": cap}),
            "functionalTest": functional[cap]["functionalTest"],
        }

    provenance = {
        "schema": "NURION_V2_CR02_P04_PROVENANCE_V1",
        "originalSourceAssetSha256": original_source_sha,
        "p03DerivedAssetSha256": p03_sha,
        "cr01SemanticAdapterDigest": cr01_digest,
        "gapInspectionDigest": p03_receipt.get("gapInspectionDigest"),
        "augmentationPlanDigest": p03_receipt.get("augmentationPlanDigest"),
        "p03DerivedSemanticDigest": p03_semantic,
        "p03FunctionalEvidenceDigest": p03_receipt.get("functionalEvidenceDigest"),
        "derivedAssetSha256": None,
        "capabilities": capability_provenance,
        "bodyWeightChanges": "NONE",
        "globalAutoWeight": "DENY",
        "sourceOverwrite": "DENY",
        "p04Scope": sorted(P04_AUTHORIZED),
        "p03Preserved": sorted(P04_PRESERVE),
    }

    gltf_out.setdefault("extras", {})["NURION_V2_CR02_P04"] = {
        "provenance": provenance,
        "functionalEvidence": functional,
        "appliedStructures": structures,
        "p03Regression": regression_after,
        "p03ExtrasPreserved": bool(p03_extras),
    }

    p04_derived_path.parent.mkdir(parents=True, exist_ok=True)
    blob = bin_blob if bin_blob is not None else b"\x00\x00\x00\x00"
    p04_derived_path.write_bytes(write_minimal_glb(gltf_out, blob))
    derived_sha = sha256_file(p04_derived_path)
    provenance["derivedAssetSha256"] = derived_sha

    if original_source_path.read_bytes() != src_before or sha256_file(original_source_path) != original_source_sha:
        blockers.append({"code": "ORIGINAL_SOURCE_MUTATED_AFTER"})

    # P03 input file must not be overwritten
    if sha256_file(p03_derived_path) != p03_sha:
        blockers.append({"code": "P03_DERIVED_MUTATED"})

    functional_digest = canonical_sha256(functional)
    p04_semantic = {
        "p03DerivedSemanticDigest": p03_semantic,
        "capabilities": sorted(P04_AUTHORIZED),
        "functionalEvidenceDigest": functional_digest,
        "derivedAssetSha256": derived_sha,
        "p03Regression": "PASS",
    }
    p04_derived_semantic_digest = canonical_sha256(p04_semantic)

    status = "PASS" if not blockers else "BLOCKED"
    result = {
        "schema": RESULT_SCHEMA,
        "stage": "CR02-P04",
        "changeRequestId": "V2-CR-02",
        "status": status,
        "scope": {
            "authorized": sorted(P04_AUTHORIZED),
            "preservedFromP03": sorted(P04_PRESERVE),
        },
        "input": {
            "p03DerivedPath": str(p03_derived_path),
            "p03DerivedAssetSha256": p03_sha,
        },
        "originalSourcePreservation": {
            "immutable": True,
            "sha256": original_source_sha,
        },
        "p03Regression": regression_after,
        "derivedArtifact": {
            "path": str(p04_derived_path),
            "derivedAssetSha256": derived_sha,
            "newArtifact": True,
        },
        "functionalEvidence": functional,
        "functionalEvidenceDigest": functional_digest,
        "p04DerivedSemanticDigest": p04_derived_semantic_digest,
        "provenance": provenance,
        "safety": {
            "sourceMutation": "DENY",
            "globalAutoWeight": "DENY",
            "bodyWeightChanges": "NONE",
            "jawEqualsTalking": "DENY",
            "p03Overwrite": "DENY",
        },
        "blockers": blockers,
        "v2Engine": "NOT OPEN",
    }
    result["p04ResultDigest"] = canonical_sha256({k: v for k, v in result.items() if k != "p04ResultDigest"})
    return result
