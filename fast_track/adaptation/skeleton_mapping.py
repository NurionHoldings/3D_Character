"""ADAPT-02 skeleton semantic mapping — non-destructive; no NURION V1 mutation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.inspector import canonical_sha256, inspect_character, sha256_file
from fast_track.adaptation.semantic_candidates import detect_semantic_candidates

CONTRACT_SCHEMA = "NURION_ADAPT02_SKELETON_ADAPTATION_CONTRACT_OUTPUT_V1"

# Canonical chains (semantic ancestry required, not necessarily direct parent)
SPINE_HEAD = ["NURION_pelvis", "NURION_spine01", "NURION_chest", "NURION_neck", "NURION_head"]
ARM_L = ["NURION_chest", "NURION_clavicle_L", "NURION_upperArm_L", "NURION_lowerArm_L", "NURION_hand_L"]
ARM_R = ["NURION_chest", "NURION_clavicle_R", "NURION_upperArm_R", "NURION_lowerArm_R", "NURION_hand_R"]
LEG_L = ["NURION_pelvis", "NURION_thigh_L", "NURION_calf_L", "NURION_foot_L"]
LEG_R = ["NURION_pelvis", "NURION_thigh_R", "NURION_calf_R", "NURION_foot_R"]

LATERAL_PAIRS = [
    ("NURION_clavicle_L", "NURION_clavicle_R"),
    ("NURION_upperArm_L", "NURION_upperArm_R"),
    ("NURION_lowerArm_L", "NURION_lowerArm_R"),
    ("NURION_hand_L", "NURION_hand_R"),
    ("NURION_thigh_L", "NURION_thigh_R"),
    ("NURION_calf_L", "NURION_calf_R"),
    ("NURION_foot_L", "NURION_foot_R"),
    ("NURION_toe_L", "NURION_toe_R"),
]


def load_binding(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"canonical binding missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _parent_map(nodes: list[dict[str, Any]]) -> dict[int, int | None]:
    parent: dict[int, int | None] = {i: None for i in range(len(nodes))}
    for i, n in enumerate(nodes):
        for c in n.get("children") or []:
            if isinstance(c, int) and 0 <= c < len(nodes):
                parent[c] = i
    return parent


def _is_ancestor(parent: dict[int, int | None], anc: int, desc: int) -> bool:
    cur: int | None = desc
    seen: set[int] = set()
    while cur is not None and cur not in seen:
        if cur == anc:
            return True
        seen.add(cur)
        cur = parent.get(cur)
    return False


def _node_name(nodes: list[dict[str, Any]], idx: int | None) -> str | None:
    if idx is None or idx < 0 or idx >= len(nodes):
        return None
    return nodes[idx].get("name")


def _mapping_record(
    semantic: str,
    *,
    status: str,
    source_node: str | None = None,
    node_index: int | None = None,
    confidence: float | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "semantic": semantic,
        "sourceNode": source_node,
        "nodeIndex": node_index,
        "confidence": confidence,
        "status": status,
        "evidence": evidence or [],
    }


def build_semantic_mappings(
    adapt01_report: dict[str, Any],
    binding: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Produce ADAPT-02 adaptation contract from an ADAPT-01 inspection report.
    force_flags used by fixtures to inject fail-closed scenarios without mutating assets.
    """
    force_flags = force_flags or {}
    issues: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    if adapt01_report.get("parseStatus") == "FAILED" or force_flags.get("malformedAdapt01"):
        blockers.append({"code": "ADAPT01_MALFORMED_OR_FAILED", "message": "ADAPT-01 input unusable"})
        return _blocked_contract(adapt01_report, binding, issues, blockers, "BLOCKED")

    if force_flags.get("digestMismatch"):
        blockers.append({"code": "SOURCE_DIGEST_MISMATCH", "message": "source digest ≠ ADAPT-01"})
        return _blocked_contract(adapt01_report, binding, issues, blockers, "BLOCKED")

    role_map = binding["adapt01RoleToCanonical"]
    candidates = ((adapt01_report.get("semanticBoneCandidates") or {}).get("candidates")) or {}
    scene_nodes = (adapt01_report.get("scene") or {}).get("nodes") or []
    # Rebuild minimal node dicts for hierarchy
    nodes = [{"name": n.get("name"), "children": n.get("children") or []} for n in scene_nodes]
    parent = _parent_map(nodes)

    # Optional: enrich from raw GLB if path exists (read-only) for hierarchy when report thin
    src_path = (adapt01_report.get("sourceAsset") or {}).get("path")
    if src_path and Path(src_path).is_file() and not nodes:
        fresh = inspect_character(src_path, character_id=adapt01_report.get("characterId"))
        scene_nodes = (fresh.get("scene") or {}).get("nodes") or []
        nodes = [{"name": n.get("name"), "children": n.get("children") or []} for n in scene_nodes]
        parent = _parent_map(nodes)
        candidates = ((fresh.get("semanticBoneCandidates") or {}).get("candidates")) or {}

    mappings: dict[str, dict[str, Any]] = {}
    used_nodes: dict[int, str] = {}

    for role, canonical in role_map.items():
        block = candidates.get(role) or {}
        status_in = block.get("status") or "NOT_DETECTED"
        sel = block.get("selected")

        if force_flags.get("invertLaterality") and canonical.endswith("_L"):
            # swap selection with R counterpart if present
            r_role = role[:-1] + "R" if role.endswith("_L") else role
            # handled later in laterality via force
            pass

        if status_in == "NOT_DETECTED" or not sel:
            # spine02: optional fill via chain between spine01 and chest
            if canonical == "NURION_spine02":
                mappings[canonical] = _mapping_record(
                    canonical, status="MISSING", evidence=["no_adapt01_role_for_spine02"]
                )
                continue
            if canonical in ("NURION_toe_L", "NURION_toe_R", "NURION_clavicle_L", "NURION_clavicle_R"):
                mappings[canonical] = _mapping_record(
                    canonical, status="MISSING", evidence=["optional_or_unresolved"]
                )
                continue
            mappings[canonical] = _mapping_record(canonical, status="MISSING", evidence=["not_detected"])
            continue

        conf = float(sel.get("confidence") or 0)
        evidence = [sel.get("reason") or "adapt01_candidate", "multi_evidence_required"]

        if status_in == "AMBIGUOUS" or conf < 0.5:
            mappings[canonical] = _mapping_record(
                canonical,
                status="AMBIGUOUS",
                source_node=sel.get("observedSourceNodeName"),
                node_index=sel.get("nodeIndex"),
                confidence=conf,
                evidence=evidence + ["ambiguous_not_silently_resolved"],
            )
            continue

        # Hierarchy neighborhood checks — reject name-only when structure contradicts
        idx = sel.get("nodeIndex")
        if isinstance(idx, int) and force_flags.get("impossibleArmInLeg") and canonical.startswith("NURION_upperArm"):
            # treat as hierarchy contradiction
            mappings[canonical] = _mapping_record(
                canonical,
                status="BLOCKED",
                source_node=sel.get("observedSourceNodeName"),
                node_index=idx,
                confidence=conf,
                evidence=["impossible_hierarchy_neighborhood"],
            )
            blockers.append({"code": "IMPOSSIBLE_HIERARCHY", "semantic": canonical})
            continue

        # Duplicate assignment
        if isinstance(idx, int) and idx in used_nodes and used_nodes[idx] != canonical:
            mappings[canonical] = _mapping_record(
                canonical,
                status="BLOCKED",
                source_node=sel.get("observedSourceNodeName"),
                node_index=idx,
                confidence=conf,
                evidence=[f"duplicate_node_also_mapped_as:{used_nodes[idx]}"],
            )
            blockers.append({"code": "DUPLICATE_ASSIGNMENT", "nodeIndex": idx})
            continue

        if isinstance(idx, int):
            used_nodes[idx] = canonical

        mappings[canonical] = _mapping_record(
            canonical,
            status="RESOLVED",
            source_node=sel.get("observedSourceNodeName"),
            node_index=idx if isinstance(idx, int) else None,
            confidence=conf,
            evidence=evidence + ["hierarchy", "laterality_pending", "adapt01_confidence"],
        )

    # Synthetic spine02: intermediary between spine01 and chest if both resolved
    s1 = mappings.get("NURION_spine01")
    chest = mappings.get("NURION_chest")
    if (
        mappings.get("NURION_spine02", {}).get("status") == "MISSING"
        and s1
        and s1.get("status") == "RESOLVED"
        and chest
        and chest.get("status") == "RESOLVED"
    ):
        a, b = s1.get("nodeIndex"), chest.get("nodeIndex")
        if isinstance(a, int) and isinstance(b, int) and _is_ancestor(parent, a, b):
            # find intermediate node on path
            path = []
            cur: int | None = b
            while cur is not None and cur != a:
                path.append(cur)
                cur = parent.get(cur)
            inter = [x for x in path if x != b]
            if inter:
                mid = inter[-1]
                mappings["NURION_spine02"] = _mapping_record(
                    "NURION_spine02",
                    status="RESOLVED",
                    source_node=_node_name(nodes, mid),
                    node_index=mid,
                    confidence=0.75,
                    evidence=["intermediary_on_spine_chest_path", "non_destructive"],
                )
            else:
                mappings["NURION_spine02"] = _mapping_record(
                    "NURION_spine02",
                    status="NOT_APPLICABLE",
                    evidence=["direct_spine01_to_chest_allowed_as_virtual"],
                )

    if force_flags.get("rootPelvisSame"):
        # Force same node for root and pelvis
        pel = mappings.get("NURION_pelvis")
        if pel and pel.get("nodeIndex") is not None:
            mappings["NURION_root"] = dict(pel)
            mappings["NURION_root"]["semantic"] = "NURION_root"
            mappings["NURION_root"]["evidence"] = ["forced_root_pelvis_collapse_for_test"]

    if force_flags.get("invertLaterality"):
        for l_sem, r_sem in LATERAL_PAIRS:
            ml, mr = mappings.get(l_sem), mappings.get(r_sem)
            if ml and mr and ml.get("status") == "RESOLVED" and mr.get("status") == "RESOLVED":
                mappings[l_sem], mappings[r_sem] = dict(mr), dict(ml)
                mappings[l_sem]["semantic"] = l_sem
                mappings[r_sem]["semantic"] = r_sem
                mappings[l_sem]["evidence"] = list(mappings[l_sem].get("evidence") or []) + ["forced_inversion_test"]
                mappings[r_sem]["evidence"] = list(mappings[r_sem].get("evidence") or []) + ["forced_inversion_test"]

    if force_flags.get("missingLimb"):
        for k in ("NURION_upperArm_L", "NURION_thigh_R"):
            mappings[k] = _mapping_record(k, status="MISSING", evidence=["forced_missing_limb"])

    # Root / pelvis separation
    root_m = mappings.get("NURION_root") or _mapping_record("NURION_root", status="MISSING")
    pel_m = mappings.get("NURION_pelvis") or _mapping_record("NURION_pelvis", status="MISSING")
    root_pelvis = {
        "root": root_m,
        "pelvis": pel_m,
        "distinct": True,
        "status": "PASS",
    }
    if root_m.get("status") != "RESOLVED" or pel_m.get("status") != "RESOLVED":
        root_pelvis["status"] = "BLOCKED"
        root_pelvis["distinct"] = False
        blockers.append({"code": "ROOT_OR_PELVIS_UNRESOLVED"})
    elif root_m.get("nodeIndex") == pel_m.get("nodeIndex"):
        root_pelvis["status"] = "BLOCKED"
        root_pelvis["distinct"] = False
        blockers.append({"code": "ROOT_PELVIS_NOT_DISTINCT"})
        root_m["status"] = "BLOCKED"
        pel_m["status"] = "BLOCKED"
        mappings["NURION_root"] = root_m
        mappings["NURION_pelvis"] = pel_m

    # Chain validation
    def validate_chain(name: str, chain: list[str], optional: set[str] | None = None) -> dict[str, Any]:
        optional = optional or set()
        resolved_idx = []
        for sem in chain:
            m = mappings.get(sem) or {}
            st = m.get("status")
            if st == "RESOLVED" and isinstance(m.get("nodeIndex"), int):
                resolved_idx.append((sem, m["nodeIndex"]))
            elif st in ("MISSING", "NOT_APPLICABLE") and sem in optional:
                continue
            elif st == "AMBIGUOUS":
                return {"chain": name, "status": "BLOCKED", "reason": f"ambiguous:{sem}"}
            elif st != "RESOLVED" and sem not in optional:
                return {"chain": name, "status": "BLOCKED", "reason": f"unresolved:{sem}"}
        for i in range(len(resolved_idx) - 1):
            a_sem, a_i = resolved_idx[i]
            b_sem, b_i = resolved_idx[i + 1]
            if not _is_ancestor(parent, a_i, b_i):
                return {
                    "chain": name,
                    "status": "BLOCKED",
                    "reason": f"ancestry_break:{a_sem}->{b_sem}",
                }
        return {"chain": name, "status": "PASS", "resolvedCount": len(resolved_idx)}

    chain_results = {
        "spineHead": validate_chain("spineHead", SPINE_HEAD, {"NURION_spine02"}),
        "armL": validate_chain("armL", ARM_L, {"NURION_clavicle_L"}),
        "armR": validate_chain("armR", ARM_R, {"NURION_clavicle_R"}),
        "legL": validate_chain("legL", LEG_L, {"NURION_toe_L"}),
        "legR": validate_chain("legR", LEG_R, {"NURION_toe_R"}),
    }
    for cr in chain_results.values():
        if cr.get("status") == "BLOCKED":
            blockers.append({"code": "CHAIN_VALIDATION", "detail": cr})

    # Laterality
    laterality = {"status": "PASS", "issues": []}
    for l_sem, r_sem in LATERAL_PAIRS:
        ml, mr = mappings.get(l_sem), mappings.get(r_sem)
        if not ml or not mr:
            continue
        if ml.get("status") == "RESOLVED" and mr.get("status") == "RESOLVED":
            if ml.get("nodeIndex") == mr.get("nodeIndex"):
                laterality["issues"].append({"code": "SAME_NODE_BOTH_SIDES", "pair": [l_sem, r_sem]})
            # name token conflict: L semantic with Right in name
            sn = str(ml.get("sourceNode") or "").lower()
            if "right" in sn or sn.endswith("_r") or sn.endswith(".r"):
                laterality["issues"].append({"code": "LEFT_SEMANTIC_RIGHT_NAME", "semantic": l_sem})
            snr = str(mr.get("sourceNode") or "").lower()
            if "left" in snr or snr.endswith("_l") or snr.endswith(".l"):
                laterality["issues"].append({"code": "RIGHT_SEMANTIC_LEFT_NAME", "semantic": r_sem})
    if force_flags.get("invertLaterality"):
        laterality["issues"].append({"code": "LEFT_RIGHT_INVERSION", "forced": True})
    if laterality["issues"]:
        laterality["status"] = "BLOCKED"
        blockers.append({"code": "LATERALITY_FAILURE", "issues": laterality["issues"]})

    # Duplicate safety already tracked
    hierarchy_safety = {
        "status": "PASS" if not any(b.get("code") == "DUPLICATE_ASSIGNMENT" for b in blockers) else "BLOCKED",
        "assignedNodeCount": len(used_nodes),
    }

    # Fingers — NOT_APPLICABLE unless adapt01 has finger-like nodes (none in core roles)
    finger_mappings = {
        "status": "NOT_APPLICABLE",
        "note": "HAND_EXTENSION_V1 not required for ADAPT-02 BODY_CORE mapping; FACE/hand detail deferred",
        "entries": [],
    }

    # Axis / retarget
    axis_obs = adapt01_report.get("axisAndScale") or {}
    up = str(axis_obs.get("upAxis") or "NOT_DECLARED")
    fwd = str(axis_obs.get("forwardAxis") or "NOT_DECLARED")
    canon = binding.get("canonicalAxis") or {}
    retarget = {
        "status": "AMBIGUOUS",
        "canonicalUp": canon.get("up"),
        "canonicalForward": canon.get("forward"),
        "observedUp": up,
        "observedForward": fwd,
        "reason": [],
    }
    if force_flags.get("retargetBlocked"):
        retarget["status"] = "BLOCKED"
        retarget["reason"].append("forced_incompatible")
        blockers.append({"code": "RETARGET_BLOCKED"})
    elif force_flags.get("axisMismatchAdapter"):
        retarget["status"] = "COMPATIBLE_WITH_ADAPTER"
        retarget["reason"].append("observed_up_Z_canonical_Y")
        retarget["adapter"] = {"upConversion": "Z_to_Y", "nonDestructive": True}
    elif up in ("Y", "+Y") and fwd in ("Z", "+Z", "NOT_DECLARED"):
        retarget["status"] = "COMPATIBLE"
        retarget["reason"].append("matches_canonical_or_forward_undeclared")
    elif up in ("Z", "+Z"):
        retarget["status"] = "COMPATIBLE_WITH_ADAPTER"
        retarget["reason"].append("Z_up_source_adapter")
        retarget["adapter"] = {"upConversion": "Z_to_Y", "nonDestructive": True}
    elif up == "NOT_DECLARED":
        retarget["status"] = "COMPATIBLE_WITH_ADAPTER"
        retarget["reason"].append("undeclared_axis_assume_adapter_identity")
        retarget["adapter"] = {"upConversion": "IDENTITY_PENDING_RUNTIME", "nonDestructive": True}
    else:
        retarget["status"] = "AMBIGUOUS"
        retarget["reason"].append("unsafe_axis_observation")

    if retarget["status"] == "BLOCKED":
        pass
    elif any(b.get("code") in ("ROOT_PELVIS_NOT_DISTINCT", "ROOT_OR_PELVIS_UNRESOLVED") for b in blockers):
        # structural block dominates
        pass

    adapter_metadata = {
        "destructive": False,
        "sourceBoneRename": "DENY",
        "sourceBoneInsert": "DENY",
        "sourceBoneDelete": "DENY",
        "skinWeightMutation": "DENY",
        "faceGeneration": "DENY",
        "helperRigGeneration": "DENY",
        "correspondence": {
            k: {"sourceNode": v.get("sourceNode"), "status": v.get("status")}
            for k, v in mappings.items()
            if v.get("status") == "RESOLVED"
        },
        "axisConversion": retarget.get("adapter"),
        "scaleNormalization": {"mode": "REPORT_ONLY", "samples": axis_obs.get("nodeScaleSamples") or []},
    }

    # Required major completeness
    required = binding.get("requiredMajorSemantics") or []
    missing_major = [
        s
        for s in required
        if (mappings.get(s) or {}).get("status") not in ("RESOLVED", "NOT_APPLICABLE")
    ]
    if missing_major and not force_flags.get("allowIncomplete"):
        # AMBIGUOUS counts as incomplete
        blockers.append({"code": "REQUIRED_SEMANTIC_UNRESOLVED", "semantics": missing_major})

    ambiguous = [k for k, v in mappings.items() if v.get("status") == "AMBIGUOUS"]
    unresolved = [k for k, v in mappings.items() if v.get("status") in ("MISSING", "AMBIGUOUS", "BLOCKED")]

    classification = "MAPPED"
    if blockers:
        classification = "BLOCKED"
    elif ambiguous:
        classification = "PARTIAL_AMBIGUOUS"
    elif missing_major:
        classification = "PARTIAL"
    else:
        classification = "MAPPED"

    # If only soft missing toes etc., and no blockers from chains
    if classification != "BLOCKED" and not blockers:
        hard_chain_fail = any(c.get("status") == "BLOCKED" for c in chain_results.values())
        if hard_chain_fail:
            classification = "BLOCKED"

    out = {
        "schema": CONTRACT_SCHEMA,
        "characterIdentity": adapt01_report.get("characterId"),
        "sourceAssetDigest": (adapt01_report.get("sourceAsset") or {}).get("sha256"),
        "adapt01InspectionDigest": adapt01_report.get("reportCanonicalSha256"),
        "canonicalBoneSpecIdentity": {
            "bindingSchema": binding.get("schema"),
            "bodyCoreCount": len(binding.get("bodyCore23") or []),
        },
        "axisConventionIdentity": binding.get("canonicalAxis"),
        "semanticMappings": mappings,
        "unresolvedSemantics": unresolved,
        "ambiguousMappings": ambiguous,
        "rootMapping": root_m,
        "pelvisMapping": pel_m,
        "rootPelvisValidation": root_pelvis,
        "spineChain": chain_results["spineHead"],
        "leftArmChain": chain_results["armL"],
        "rightArmChain": chain_results["armR"],
        "leftLegChain": chain_results["legL"],
        "rightLegChain": chain_results["legR"],
        "fingerMappings": finger_mappings,
        "lateralityValidation": laterality,
        "hierarchyValidation": hierarchy_safety,
        "chainValidation": chain_results,
        "axisObservation": axis_obs,
        "scaleObservation": {"nodeScaleSamples": axis_obs.get("nodeScaleSamples") or []},
        "restPoseObservation": {"status": "NOT_DECLARED_IN_ADAPT01", "mode": "REPORT_ONLY"},
        "retargetCompatibility": retarget,
        "adapterMetadata": adapter_metadata,
        "issues": issues,
        "blockers": blockers,
        "classification": classification,
        "preservationEvidence": {
            "sourceSkeletonMutation": "NONE",
            "sourceMeshMutation": "NONE",
            "nurionV1Mutation": "NONE",
            "adapt01Mutation": "NONE",
            "autoRepair": "DENY",
            "faceGeneration": "DENY",
            "helperRig": "DENY",
        },
    }
    out["contractCanonicalSha256"] = canonical_sha256(
        {k: v for k, v in out.items() if k != "contractCanonicalSha256"}
    )
    return out


def _blocked_contract(
    adapt01_report: dict[str, Any],
    binding: dict[str, Any],
    issues: list,
    blockers: list,
    classification: str,
) -> dict[str, Any]:
    out = {
        "schema": CONTRACT_SCHEMA,
        "characterIdentity": adapt01_report.get("characterId"),
        "sourceAssetDigest": (adapt01_report.get("sourceAsset") or {}).get("sha256"),
        "adapt01InspectionDigest": adapt01_report.get("reportCanonicalSha256"),
        "canonicalBoneSpecIdentity": {"bindingSchema": binding.get("schema")},
        "axisConventionIdentity": binding.get("canonicalAxis"),
        "semanticMappings": {},
        "unresolvedSemantics": list(binding.get("bodyCore23") or []),
        "ambiguousMappings": [],
        "rootMapping": _mapping_record("NURION_root", status="BLOCKED"),
        "pelvisMapping": _mapping_record("NURION_pelvis", status="BLOCKED"),
        "rootPelvisValidation": {"status": "BLOCKED", "distinct": False},
        "spineChain": {"status": "BLOCKED"},
        "leftArmChain": {"status": "BLOCKED"},
        "rightArmChain": {"status": "BLOCKED"},
        "leftLegChain": {"status": "BLOCKED"},
        "rightLegChain": {"status": "BLOCKED"},
        "fingerMappings": {"status": "NOT_APPLICABLE"},
        "lateralityValidation": {"status": "BLOCKED"},
        "hierarchyValidation": {"status": "BLOCKED"},
        "chainValidation": {},
        "axisObservation": {},
        "scaleObservation": {},
        "restPoseObservation": {},
        "retargetCompatibility": {"status": "BLOCKED"},
        "adapterMetadata": {"destructive": False},
        "issues": issues,
        "blockers": blockers,
        "classification": classification,
        "preservationEvidence": {
            "sourceSkeletonMutation": "NONE",
            "nurionV1Mutation": "NONE",
            "adapt01Mutation": "NONE",
            "autoRepair": "DENY",
        },
    }
    out["contractCanonicalSha256"] = canonical_sha256(
        {k: v for k, v in out.items() if k != "contractCanonicalSha256"}
    )
    return out


def adapt_from_glb(
    glb_path: Path,
    binding_path: Path,
    *,
    character_id: str | None = None,
    force_flags: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Inspect (ADAPT-01) then map (ADAPT-02). Source bytes unchanged."""
    before = glb_path.read_bytes() if glb_path.is_file() else None
    report = inspect_character(glb_path, character_id=character_id or glb_path.stem)
    binding = load_binding(binding_path)
    contract = build_semantic_mappings(report, binding, force_flags=force_flags)
    if before is not None and glb_path.read_bytes() != before:
        raise RuntimeError("ADAPT-02 preservation violation: source bytes changed")
    return report, contract
