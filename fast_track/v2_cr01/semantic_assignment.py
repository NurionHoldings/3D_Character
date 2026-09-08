"""CR01-P03 — Semantic Assignment from ordered torso chain + topology evidence."""

from __future__ import annotations

from typing import Any

from fast_track.adaptation.inspector import canonical_sha256

REPORT_SCHEMA = "NURION_V2_CR01_SEMANTIC_ASSIGNMENT_V1"

ARM_L_HINTS = ("leftarm", "leftupperarm", "upperarml", "arml")
ARM_R_HINTS = ("rightarm", "rightupperarm", "upperarmr", "armr")
FOREARM_L = ("leftforearm", "leftlowerarm", "lowerarml", "forearml")
FOREARM_R = ("rightforearm", "rightlowerarm", "lowerarmr", "forearmr")
HAND_L = ("lefthand", "handl")
HAND_R = ("righthand", "handr")
THIGH_L = ("leftupleg", "leftthigh", "thighl", "uplegl")
THIGH_R = ("rightupleg", "rightthigh", "thighr", "uplegr")
CALF_L = ("leftleg", "leftcalf", "calfl", "lowerlegl")
CALF_R = ("rightleg", "rightcalf", "calfr", "lowerlegr")
FOOT_L = ("leftfoot", "footl")
FOOT_R = ("rightfoot", "footr")
TOE_L = ("lefttoe", "toel")
TOE_R = ("righttoe", "toer")


def _norm(name: str | None) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _hit(name: str | None, tokens: tuple[str, ...]) -> bool:
    n = _norm(name)
    return any(t in n for t in tokens)


def _is_ancestor(parent: dict[int, int | None], anc: int, desc: int) -> bool:
    cur: int | None = desc
    while cur is not None:
        if cur == anc:
            return True
        cur = parent.get(cur)
    return False


def _assignment(
    semantic: str,
    *,
    source_index: int | None,
    source_name: str | None,
    confidence: float,
    evidence: list[str],
    classification: str = "CANONICAL_BOUND",
) -> dict[str, Any]:
    return {
        "semantic": semantic,
        "sourceBone": source_name,
        "sourceIndex": source_index,
        "confidence": confidence,
        "evidence": evidence,
        "classification": classification,
        "status": "RESOLVED" if source_index is not None else "MISSING",
    }


def assign_semantics(inspection: dict[str, Any], torso: dict[str, Any]) -> dict[str, Any]:
    skel = inspection.get("skeleton") or {}
    nodes = skel.get("nodes") or []
    parent: dict[int, int | None] = {int(k): v for k, v in (skel.get("parentMap") or {}).items()}
    skin = set(skel.get("skinJoints") or [])
    chain = list(torso.get("orderedTorsoChainIndices") or [])
    anchors = torso.get("anchors") or {}
    blockers = list(torso.get("blockers") or [])
    ambiguities = list(torso.get("ambiguities") or [])

    def name_of(i: int | None) -> str | None:
        if i is None or not (0 <= i < len(nodes)):
            return None
        return nodes[i].get("name")

    assignments: dict[str, dict[str, Any]] = {}
    intermediate: list[dict[str, Any]] = []
    unused: list[dict[str, Any]] = []

    if torso.get("status") == "BLOCKED" or blockers:
        return {
            "schema": REPORT_SCHEMA,
            "stage": "CR01-P03",
            "status": "BLOCKED",
            "semanticAssignments": {},
            "intermediateBones": [],
            "unusedPreservedBones": [],
            "blockers": blockers or [{"code": "UPSTREAM_TORSO_BLOCKED"}],
            "ambiguities": ambiguities,
            "adapterDigest": None,
        }

    pelvis_i = anchors.get("pelvisIndex")
    chest_i = anchors.get("chestCandidateIndex")
    neck_i = anchors.get("neckIndex")
    head_i = anchors.get("headIndex")
    ls_i = anchors.get("leftShoulderIndex")
    rs_i = anchors.get("rightShoulderIndex")
    chest_ev = list(anchors.get("chestEvidence") or [])

    # Root: armature/scene root distinct from pelvis
    root_i = None
    if pelvis_i is not None:
        cur = parent.get(pelvis_i)
        # walk to topmost ancestor
        while cur is not None and parent.get(cur) is not None:
            cur = parent.get(cur)
        root_i = cur if cur is not None and cur != pelvis_i else None
        if root_i is None:
            # try named armature among roots
            for r in skel.get("rootIndices") or []:
                if r != pelvis_i:
                    root_i = r
                    break

    if root_i is None or root_i == pelvis_i:
        blockers.append({"code": "ROOT_PELVIS_CONFLATION"})
    else:
        assignments["NURION_root"] = _assignment(
            "NURION_root",
            source_index=root_i,
            source_name=name_of(root_i),
            confidence=0.9,
            evidence=["SKELETON_ROOT_DISTINCT_FROM_PELVIS", "HIERARCHY_ANCESTOR"],
        )

    assignments["NURION_pelvis"] = _assignment(
        "NURION_pelvis",
        source_index=pelvis_i,
        source_name=name_of(pelvis_i),
        confidence=0.95,
        evidence=["PELVIS_ANCHOR", "LEG_BRANCH_PARENT" if pelvis_i is not None else "PELVIS_TOKEN"],
    )

    assignments["NURION_chest"] = _assignment(
        "NURION_chest",
        source_index=chest_i,
        source_name=name_of(chest_i),
        confidence=0.98 if "BILATERAL_SHOULDER_ATTACHMENT" in chest_ev else 0.7,
        evidence=chest_ev or ["CHEST_UNRESOLVED"],
    )

    if neck_i is not None:
        assignments["NURION_neck"] = _assignment(
            "NURION_neck",
            source_index=neck_i,
            source_name=name_of(neck_i),
            confidence=0.95,
            evidence=["NECK_ON_TORSO_CHAIN", "HEAD_DESCENDANT_PATH"],
        )
    if head_i is not None:
        assignments["NURION_head"] = _assignment(
            "NURION_head",
            source_index=head_i,
            source_name=name_of(head_i),
            confidence=0.95,
            evidence=["HEAD_TERMINAL", "UNDER_NECK_OR_CHEST"],
        )

    # Internal spine bones between pelvis and chest on ordered chain
    if pelvis_i is not None and chest_i is not None and chain:
        try:
            pi = chain.index(pelvis_i)
            ci = chain.index(chest_i)
        except ValueError:
            pi, ci = -1, -1
        if pi >= 0 and ci > pi:
            internals = chain[pi + 1 : ci]
            # Assign spine01 = first internal, spine02 = second if present; rest INTERMEDIATE_PRESERVED
            if internals:
                assignments["NURION_spine01"] = _assignment(
                    "NURION_spine01",
                    source_index=internals[0],
                    source_name=name_of(internals[0]),
                    confidence=0.92,
                    evidence=["ORDERED_TORSO_CHAIN", "BETWEEN_PELVIS_AND_CHEST", "SPINE_SLOT_1"],
                )
            if len(internals) >= 2:
                assignments["NURION_spine02"] = _assignment(
                    "NURION_spine02",
                    source_index=internals[1],
                    source_name=name_of(internals[1]),
                    confidence=0.9,
                    evidence=["ORDERED_TORSO_CHAIN", "BETWEEN_PELVIS_AND_CHEST", "SPINE_SLOT_2"],
                )
            for extra in internals[2:]:
                intermediate.append(
                    {
                        "index": extra,
                        "name": name_of(extra),
                        "classification": "INTERMEDIATE_PRESERVED",
                        "evidence": ["EXTRA_TORSO_NODE", "SEMANTIC_ABSORBED"],
                    }
                )
            # If only one internal, spine02 N/A
            if len(internals) == 1:
                assignments["NURION_spine02"] = {
                    "semantic": "NURION_spine02",
                    "sourceBone": None,
                    "sourceIndex": None,
                    "confidence": 1.0,
                    "evidence": ["NO_SECOND_INTERNAL_SPINE", "NOT_APPLICABLE"],
                    "classification": "UNUSED_BUT_PRESERVED",
                    "status": "NOT_APPLICABLE",
                }

    # Clavicles / arms / legs via topology under chest / pelvis
    if ls_i is not None:
        assignments["NURION_clavicle_L"] = _assignment(
            "NURION_clavicle_L",
            source_index=ls_i,
            source_name=name_of(ls_i),
            confidence=0.95,
            evidence=["LEFT_SHOULDER_ANCHOR", "UNDER_CHEST"],
        )
    if rs_i is not None:
        assignments["NURION_clavicle_R"] = _assignment(
            "NURION_clavicle_R",
            source_index=rs_i,
            source_name=name_of(rs_i),
            confidence=0.95,
            evidence=["RIGHT_SHOULDER_ANCHOR", "UNDER_CHEST"],
        )

    def find_descendant(start: int | None, tokens: tuple[str, ...]) -> int | None:
        if start is None:
            return None
        hits = []
        for i, n in enumerate(nodes):
            if i in skin or True:
                if _hit(n.get("name"), tokens) and _is_ancestor(parent, start, i):
                    hits.append(i)
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            # prefer closest (shortest path)
            def depth(idx: int) -> int:
                d = 0
                cur: int | None = idx
                while cur is not None and cur != start:
                    cur = parent.get(cur)
                    d += 1
                return d

            hits.sort(key=depth)
            return hits[0]
        return None

    limb_map = [
        ("NURION_upperArm_L", ls_i, ARM_L_HINTS),
        ("NURION_lowerArm_L", ls_i, FOREARM_L),
        ("NURION_hand_L", ls_i, HAND_L),
        ("NURION_upperArm_R", rs_i, ARM_R_HINTS),
        ("NURION_lowerArm_R", rs_i, FOREARM_R),
        ("NURION_hand_R", rs_i, HAND_R),
        ("NURION_thigh_L", pelvis_i, THIGH_L),
        ("NURION_calf_L", pelvis_i, CALF_L),
        ("NURION_foot_L", pelvis_i, FOOT_L),
        ("NURION_toe_L", pelvis_i, TOE_L),
        ("NURION_thigh_R", pelvis_i, THIGH_R),
        ("NURION_calf_R", pelvis_i, CALF_R),
        ("NURION_foot_R", pelvis_i, FOOT_R),
        ("NURION_toe_R", pelvis_i, TOE_R),
    ]
    for sem, start, tokens in limb_map:
        idx = find_descendant(start, tokens)
        if idx is not None:
            assignments[sem] = _assignment(
                sem,
                source_index=idx,
                source_name=name_of(idx),
                confidence=0.9,
                evidence=["LIMB_TOPOLOGY_DESCENDANT", "NAME_HINT_SECONDARY"],
            )

    # Laterality safety
    for l_sem, r_sem in (
        ("NURION_upperArm_L", "NURION_upperArm_R"),
        ("NURION_thigh_L", "NURION_thigh_R"),
        ("NURION_clavicle_L", "NURION_clavicle_R"),
    ):
        ml, mr = assignments.get(l_sem), assignments.get(r_sem)
        if ml and mr and ml.get("sourceIndex") is not None and ml.get("sourceIndex") == mr.get("sourceIndex"):
            blockers.append({"code": "LEFT_RIGHT_CONTRADICTION", "pair": [l_sem, r_sem]})

    # Unused preserved: nodes not assigned
    assigned_idx = {a.get("sourceIndex") for a in assignments.values() if a.get("sourceIndex") is not None}
    for inter in intermediate:
        assigned_idx.add(inter["index"])
    for i, n in enumerate(nodes):
        if i not in assigned_idx and i in skin:
            unused.append(
                {
                    "index": i,
                    "name": n.get("name"),
                    "classification": "UNUSED_BUT_PRESERVED",
                }
            )

    status = "BLOCKED" if blockers else "PASS"
    digest_payload = {
        "sourceSha256": (inspection.get("sourceIdentity") or {}).get("sha256"),
        "sourceSkeletonDigest": inspection.get("sourceSkeletonDigest"),
        "orderedTorsoChain": torso.get("orderedTorsoChain"),
        "semanticAssignments": {
            k: {
                "sourceBone": v.get("sourceBone"),
                "sourceIndex": v.get("sourceIndex"),
                "evidence": v.get("evidence"),
                "classification": v.get("classification"),
                "status": v.get("status"),
            }
            for k, v in sorted(assignments.items())
        },
        "intermediateBones": intermediate,
    }
    adapter_digest = canonical_sha256(digest_payload)

    return {
        "schema": REPORT_SCHEMA,
        "stage": "CR01-P03",
        "status": status,
        "semanticAssignments": assignments,
        "intermediateBones": intermediate,
        "unusedPreservedBones": unused,
        "ambiguities": ambiguities,
        "blockers": blockers,
        "adapterDigest": adapter_digest,
        "digestPayload": digest_payload,
    }
