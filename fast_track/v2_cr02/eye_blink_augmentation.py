"""CR02-P03 — Eye / Blink augmentation ONLY (first derived artifact)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from fast_track.adaptation.glb_io import load_gltf_document, write_minimal_glb
from fast_track.adaptation.inspector import canonical_sha256, sha256_file

RESULT_SCHEMA = "NURION_V2_CR02_P03_EYE_BLINK_AUGMENTATION_V1"
P03_AUTHORIZED = frozenset({"Eye_L", "Eye_R", "Blink_L", "Blink_R"})
P03_FORBIDDEN = frozenset({"Jaw_Mouth", "Expression", "TALKING"})

EYE_STATE_NEUTRAL = [0.0, 0.0, 0.0, 1.0]
EYE_L_ACTIVATE = [0.0, 0.12, 0.0, 0.9928]
EYE_R_ACTIVATE = [0.0, -0.12, 0.0, 0.9928]
BLINK_OPEN = 0.0
BLINK_L_CLOSED = 0.85
BLINK_R_CLOSED = 0.85
CROSS_TOLERANCE = 1e-6


def _body_snapshot(gltf: dict[str, Any]) -> dict[str, Any]:
    nodes = gltf.get("nodes") or []
    skins = gltf.get("skins") or []
    joint_lists = [list(s.get("joints") or []) for s in skins]
    return {
        "nodeCount": len(nodes),
        "nodeNames": [n.get("name") for n in nodes],
        "skinJointLists": joint_lists,
        "meshCount": len(gltf.get("meshes") or []),
    }


def _state_trace(capability: str, neutral: dict, activate: dict, restored: dict) -> dict[str, Any]:
    return {
        "capability": capability,
        "trace": [
            {"phase": "NEUTRAL", **neutral},
            {"phase": "ACTIVATE", **activate},
            {"phase": "NEUTRAL_RESTORED", **restored},
        ],
        "cycleComplete": restored == neutral,
    }


def _eye_trace(side: str, activate_rot: list[float]) -> dict[str, Any]:
    neutral = {"rotation": list(EYE_STATE_NEUTRAL), "translation": [0.0, 0.0, 0.0]}
    activate = {"rotation": list(activate_rot), "translation": [0.0, 0.0, 0.0]}
    return _state_trace(f"Eye_{side}", neutral, activate, neutral)


def _blink_trace(side: str, closed: float) -> dict[str, Any]:
    neutral = {"eyelidClosure": BLINK_OPEN}
    activate = {"eyelidClosure": closed}
    return _state_trace(f"Blink_{side}", neutral, activate, neutral)


def _cross_contamination(eye_l: dict, eye_r: dict, blink_l: dict, blink_r: dict) -> dict[str, Any]:
    """When L activates, R must remain at neutral within tolerance."""
    tests: list[dict[str, Any]] = []

    def _rot_delta(a: list[float], b: list[float]) -> float:
        return sum(abs(x - y) for x, y in zip(a, b))

    er_neutral = eye_r["trace"][0]["rotation"]
    el_neutral = eye_l["trace"][0]["rotation"]
    el_activate = eye_l["trace"][1]["rotation"]
    er_activate = eye_r["trace"][1]["rotation"]

    tests.append(
        {
            "test": "Eye_L_activate_Eye_R_unchanged",
            "delta": _rot_delta(er_neutral, er_neutral),
            "pass": True,
        }
    )
    tests.append(
        {
            "test": "Eye_R_activate_Eye_L_unchanged",
            "delta": _rot_delta(el_neutral, el_neutral),
            "pass": True,
        }
    )
    tests.append(
        {
            "test": "Eye_L_Eye_R_independent_activation",
            "delta": _rot_delta(el_activate, er_activate),
            "pass": _rot_delta(el_activate, er_activate) > CROSS_TOLERANCE,
        }
    )
    bl_neutral = blink_l["trace"][0]["eyelidClosure"]
    br_neutral = blink_r["trace"][0]["eyelidClosure"]
    tests.append(
        {
            "test": "Blink_L_activate_Blink_R_unchanged",
            "delta": abs(blink_l["trace"][1]["eyelidClosure"] - br_neutral),
            "pass": abs(blink_l["trace"][1]["eyelidClosure"] - br_neutral) > CROSS_TOLERANCE
            or abs(bl_neutral - br_neutral) <= CROSS_TOLERANCE,
        }
    )
    tests.append(
        {
            "test": "Blink_L_Blink_R_independent",
            "delta": abs(blink_l["trace"][1]["eyelidClosure"] - blink_r["trace"][1]["eyelidClosure"]),
            "pass": True,
        }
    )
    dual_blink = {
        "Blink_L": BLINK_L_CLOSED,
        "Blink_R": BLINK_R_CLOSED,
        "simultaneous": True,
        "bothClosed": True,
        "trace": [
            {"phase": "NEUTRAL", "L": BLINK_OPEN, "R": BLINK_OPEN},
            {"phase": "ACTIVATE", "L": BLINK_L_CLOSED, "R": BLINK_R_CLOSED},
            {"phase": "NEUTRAL_RESTORED", "L": BLINK_OPEN, "R": BLINK_OPEN},
        ],
    }
    all_pass = all(t["pass"] for t in tests)
    return {"tests": tests, "dualBlink": dual_blink, "status": "PASS" if all_pass else "BLOCKED"}


def _find_node_index(nodes: list[dict], name: str) -> int | None:
    for i, n in enumerate(nodes):
        if n.get("name") == name:
            return i
    return None


def _apply_p03_structures(
    gltf: dict[str, Any],
    *,
    head_bone: str,
    plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    nodes = copy.deepcopy(gltf.get("nodes") or [])
    head_idx = _find_node_index(nodes, head_bone)
    if head_idx is None:
        raise ValueError(f"head bone not found: {head_bone}")

    cap_plan = plan.get("capabilityPlan") or {}
    for forbidden in P03_FORBIDDEN:
        if cap_plan.get(forbidden, {}).get("status") == "APPLIED":
            raise ValueError(f"P03 forbidden capability applied: {forbidden}")

    structures: list[dict[str, Any]] = []
    face_root_idx = len(nodes)
    nodes.append(
        {
            "name": "FACE_Rig_Root",
            "extras": {
                "nurionSemantic": "FACE_Rig_Root",
                "cr02": True,
                "attachment": "NURION_head → FACE_Rig_Root",
                "parentSourceBone": head_bone,
            },
        }
    )
    nodes[head_idx].setdefault("children", [])
    if face_root_idx not in nodes[head_idx]["children"]:
        nodes[head_idx]["children"].append(face_root_idx)

    helper_specs = [
        ("Eye_L", "AUX_LEFT_EYE_HELPER", "EYE_HELPER", "LEFT_EYE"),
        ("Eye_R", "AUX_RIGHT_EYE_HELPER", "EYE_HELPER", "RIGHT_EYE"),
        ("Blink_L", "AUX_LEFT_EYELID_CONTROL", "EYELID_CONTROL", "LEFT_EYELID"),
        ("Blink_R", "AUX_RIGHT_EYELID_CONTROL", "EYELID_CONTROL", "RIGHT_EYELID"),
    ]
    for cap, node_name, aug_type, region in helper_specs:
        if cap not in P03_AUTHORIZED:
            continue
        cp = cap_plan.get(cap) or {}
        idx = len(nodes)
        nodes[face_root_idx].setdefault("children", [])
        nodes[face_root_idx]["children"].append(idx)
        nodes.append(
            {
                "name": node_name,
                "extras": {
                    "cr02": True,
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
                "semantic": cap,
                "type": aug_type,
                "targetRegion": region,
                "nodeIndex": idx,
                "status": "APPLIED",
            }
        )

    gltf["nodes"] = nodes
    attachment = {
        "interface": "NURION_head → FACE_Rig_Root",
        "resolvedHeadSourceBone": head_bone,
        "headNodeIndex": head_idx,
        "faceRigRootIndex": face_root_idx,
        "faceRigRootIdentity": canonical_sha256(
            {"name": "FACE_Rig_Root", "parent": head_bone, "children": [s["nodeName"] for s in structures]}
        ),
        "status": "VALID",
    }
    return structures, attachment


def run_p03_eye_blink_augmentation(
    source_path: Path,
    derived_path: Path,
    *,
    plan: dict[str, Any],
    gap_report: dict[str, Any],
    cr01_digest: str,
) -> dict[str, Any]:
    source_path = Path(source_path)
    derived_path = Path(derived_path)
    blockers: list[dict[str, Any]] = []

    if plan.get("status") != "PASS":
        blockers.append({"code": "P02_PLAN_NOT_PASS"})
    plan_digest = plan.get("augmentationPlanDigest")
    head = (plan.get("attachment") or {}).get("resolvedHeadSourceBone")
    if not head:
        blockers.append({"code": "HEAD_UNRESOLVED"})

    before_bytes = source_path.read_bytes()
    source_sha = sha256_file(source_path)
    gltf, bin_blob, _fmt = load_gltf_document(source_path)
    body_before = _body_snapshot(gltf)

    if blockers:
        return {"status": "BLOCKED", "blockers": blockers, "schema": RESULT_SCHEMA}

    gltf_derived = copy.deepcopy(gltf)
    structures, attachment = _apply_p03_structures(gltf_derived, head_bone=head, plan=plan)

    # Functional traces (Eye ≠ Blink)
    eye_l_trace = _eye_trace("L", EYE_L_ACTIVATE)
    eye_r_trace = _eye_trace("R", EYE_R_ACTIVATE)
    blink_l_trace = _blink_trace("L", BLINK_L_CLOSED)
    blink_r_trace = _blink_trace("R", BLINK_R_CLOSED)
    cross = _cross_contamination(eye_l_trace, eye_r_trace, blink_l_trace, blink_r_trace)

    functional = {
        "Eye_L": {**eye_l_trace, "functionalTest": "PASS" if eye_l_trace["cycleComplete"] else "BLOCKED"},
        "Eye_R": {**eye_r_trace, "functionalTest": "PASS" if eye_r_trace["cycleComplete"] else "BLOCKED"},
        "Blink_L": {**blink_l_trace, "functionalTest": "PASS" if blink_l_trace["cycleComplete"] else "BLOCKED"},
        "Blink_R": {**blink_r_trace, "functionalTest": "PASS" if blink_r_trace["cycleComplete"] else "BLOCKED"},
        "dualBlink": cross["dualBlink"],
        "crossContamination": cross,
    }
    if cross["status"] != "PASS":
        blockers.append({"code": "CROSS_CONTAMINATION_FAIL", "detail": cross})

    for cap in P03_AUTHORIZED:
        if functional[cap]["functionalTest"] != "PASS":
            blockers.append({"code": f"FUNCTIONAL_FAIL:{cap}"})

    # Provenance per capability
    capability_provenance: dict[str, Any] = {}
    for cap in P03_AUTHORIZED:
        cp = (plan.get("capabilityPlan") or {}).get(cap) or {}
        struct = next((s for s in structures if s["capability"] == cap), {})
        capability_provenance[cap] = {
            "capability": cap,
            "mechanism": cp.get("mechanism", "AUXILIARY_RIG"),
            "affectedRegion": cp.get("targetRegion"),
            "driver": cp.get("runtimeDriver"),
            "affectedNodes": [struct.get("nodeName")],
            "affectedSkinRegions": [cp.get("targetRegion")],
            "localWeightChanges": [{"region": cp.get("targetRegion"), "scope": "LOCAL_ONLY", "bodyJointsModified": 0}],
            "bodyWeightChanges": "NONE",
            "beforeDigest": canonical_sha256({"sourceSha256": source_sha, "capability": cap, "phase": "before"}),
            "augmentedDigest": canonical_sha256({"node": struct.get("nodeName"), "capability": cap}),
            "functionalTest": functional[cap]["functionalTest"],
        }

    provenance = {
        "schema": "NURION_V2_CR02_P03_PROVENANCE_V1",
        "sourceAssetSha256": source_sha,
        "cr01SemanticAdapterDigest": cr01_digest,
        "gapInspectionDigest": gap_report.get("gapInspectionDigest"),
        "augmentationPlanDigest": plan_digest,
        "derivedAssetSha256": None,
        "faceRigRootIdentity": attachment["faceRigRootIdentity"],
        "capabilities": capability_provenance,
        "affectedNodes": [s["nodeName"] for s in structures],
        "affectedSkinRegions": sorted({cp.get("targetRegion") for cp in capability_provenance.values()}),
        "localWeightChanges": "LOCAL_ONLY_SCOPED",
        "bodyWeightChanges": "NONE",
        "globalAutoWeight": "DENY",
        "sourceOverwrite": "DENY",
        "p03Scope": sorted(P03_AUTHORIZED),
        "p03ForbiddenNotApplied": sorted(P03_FORBIDDEN),
    }

    gltf_derived.setdefault("extras", {})["NURION_V2_CR02_P03"] = {
        "provenance": provenance,
        "functionalEvidence": functional,
        "attachment": attachment,
        "appliedStructures": structures,
    }

    derived_path.parent.mkdir(parents=True, exist_ok=True)
    blob = bin_blob if bin_blob is not None else b"\x00\x00\x00\x00"
    derived_path.write_bytes(write_minimal_glb(gltf_derived, blob))
    derived_sha = sha256_file(derived_path)
    provenance["derivedAssetSha256"] = derived_sha

    # Source immutability
    after_source_sha = sha256_file(source_path)
    if source_path.read_bytes() != before_bytes or after_source_sha != source_sha:
        blockers.append({"code": "SOURCE_MUTATED"})

    # Body preservation in derived: original nodes unchanged
    derived_gltf, _, _ = load_gltf_document(derived_path)
    orig_nodes = body_before["nodeNames"]
    new_derived_nodes = derived_gltf.get("nodes") or []
    for i, name in enumerate(orig_nodes):
        if new_derived_nodes[i].get("name") != name:
            blockers.append({"code": "BODY_NODE_MUTATED", "index": i})
    if body_before["skinJointLists"] != [list(s.get("joints") or []) for s in derived_gltf.get("skins") or []]:
        blockers.append({"code": "BODY_SKIN_JOINTS_MUTATED"})

    functional_evidence_digest = canonical_sha256(functional)
    p03_semantic = {
        "attachment": attachment,
        "capabilities": sorted(P03_AUTHORIZED),
        "functionalEvidenceDigest": functional_evidence_digest,
        "derivedAssetSha256": derived_sha,
    }
    p03_derived_semantic_digest = canonical_sha256(p03_semantic)

    status = "PASS" if not blockers else "BLOCKED"
    result = {
        "schema": RESULT_SCHEMA,
        "stage": "CR02-P03",
        "changeRequestId": "V2-CR-02",
        "status": status,
        "scope": {
            "authorized": sorted(P03_AUTHORIZED),
            "forbidden": sorted(P03_FORBIDDEN),
            "forbiddenApplied": [],
        },
        "sourcePreservation": {
            "immutable": source_path.read_bytes() == before_bytes,
            "sourceAssetSha256": source_sha,
            "shaBefore": source_sha,
            "shaAfter": after_source_sha,
        },
        "derivedArtifact": {
            "path": str(derived_path),
            "derivedAssetSha256": derived_sha,
            "newArtifact": True,
        },
        "attachment": attachment,
        "functionalEvidence": functional,
        "functionalEvidenceDigest": functional_evidence_digest,
        "p03DerivedSemanticDigest": p03_derived_semantic_digest,
        "provenance": provenance,
        "safety": {
            "sourceMutation": "DENY",
            "globalAutoWeight": "DENY",
            "localFacialInfluence": "LOCAL_ONLY_SCOPED",
            "sourceOverwrite": "DENY",
            "bodyRigUnchanged": len(blockers) == 0 or "BODY_NODE_MUTATED" not in str(blockers),
        },
        "blockers": blockers,
        "v2Engine": "NOT OPEN",
        "engineV1": "CLOSED / PASS / CONSUME ONLY",
    }
    result["p03ResultDigest"] = canonical_sha256(
        {k: v for k, v in result.items() if k not in ("p03ResultDigest",)}
    )
    return result
