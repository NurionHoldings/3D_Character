"""CR01-P02 — Flexible Torso Chain Discovery (topology-first)."""

from __future__ import annotations

from typing import Any

REPORT_SCHEMA = "NURION_V2_CR01_TORSO_CHAIN_DISCOVERY_V1"

SHOULDER_TOKENS = ("shoulder", "clavicle", "collar")
NECK_TOKENS = ("neck",)
HEAD_TOKENS = ("head",)
PELVIS_TOKENS = ("hips", "pelvis", "hip")
LEG_TOKENS = ("upleg", "thigh", "upperleg", "leg")


def _norm(name: str | None) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _token_hit(name: str | None, tokens: tuple[str, ...]) -> bool:
    n = _norm(name)
    return any(t in n for t in tokens)


def _is_ancestor(parent: dict[int, int | None], anc: int, desc: int) -> bool:
    cur: int | None = desc
    guard = 0
    while cur is not None and guard < 10_000:
        if cur == anc:
            return True
        nxt = parent.get(cur)
        if nxt == cur:
            break
        cur = nxt
        guard += 1
    return False


def _path_from_ancestor(parent: dict[int, int | None], anc: int, desc: int) -> list[int] | None:
    if not _is_ancestor(parent, anc, desc):
        return None
    path: list[int] = []
    cur: int | None = desc
    while cur is not None:
        path.append(cur)
        if cur == anc:
            break
        cur = parent.get(cur)
    path.reverse()
    return path


def _lca(parent: dict[int, int | None], a: int, b: int) -> int | None:
    anc_a = set()
    cur: int | None = a
    while cur is not None:
        anc_a.add(cur)
        cur = parent.get(cur)
    cur = b
    while cur is not None:
        if cur in anc_a:
            return cur
        cur = parent.get(cur)
    return None


def _is_left_shoulder(name: str | None) -> bool:
    n = _norm(name)
    if "right" in n:
        return False
    return "left" in n or n.endswith("l")


def _is_right_shoulder(name: str | None) -> bool:
    n = _norm(name)
    if "left" in n:
        return False
    return "right" in n or n.endswith("r")


def discover_torso_chain(inspection: dict[str, Any]) -> dict[str, Any]:
    """Discover ordered pelvis→head torso chain using topology (not name tables)."""
    skel = inspection.get("skeleton") or {}
    nodes = skel.get("nodes") or []
    parent_raw = skel.get("parentMap") or {}
    parent: dict[int, int | None] = {int(k): v for k, v in parent_raw.items()}
    skin_joints = set(skel.get("skinJoints") or [])

    blockers: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []

    def name_of(i: int) -> str | None:
        return nodes[i]["name"] if 0 <= i < len(nodes) else None

    # Candidate pools (hints only — topology decides)
    pelvis_cands = [
        i
        for i, n in enumerate(nodes)
        if _token_hit(n.get("name"), PELVIS_TOKENS) and (i in skin_joints or True)
    ]
    # Prefer skin-joint pelvis; fall back to name hits
    pelvis_cands = [i for i in pelvis_cands if i in skin_joints] or pelvis_cands

    # Structural pelvis: node with ≥2 leg-like children and spine-like child
    structural_pelvis = []
    for i, n in enumerate(nodes):
        kids = n.get("childIndices") or []
        leg_kids = [c for c in kids if _token_hit(name_of(c), LEG_TOKENS) or _token_hit(name_of(c), ("foot",))]
        # also count UpLeg naming
        if len(leg_kids) >= 2:
            structural_pelvis.append(i)
    for i in structural_pelvis:
        if i not in pelvis_cands:
            pelvis_cands.append(i)

    shoulder_cands = [
        i for i, n in enumerate(nodes) if _token_hit(n.get("name"), SHOULDER_TOKENS) and i in skin_joints
    ] or [i for i, n in enumerate(nodes) if _token_hit(n.get("name"), SHOULDER_TOKENS)]

    # Split L/R by token
    left_shoulders = [i for i in shoulder_cands if _is_left_shoulder(name_of(i))]
    right_shoulders = [i for i in shoulder_cands if _is_right_shoulder(name_of(i))]

    neck_cands = [i for i, n in enumerate(nodes) if _token_hit(n.get("name"), NECK_TOKENS)]
    head_cands = [
        i
        for i, n in enumerate(nodes)
        if _token_hit(n.get("name"), HEAD_TOKENS) and "end" not in _norm(n.get("name")) and "front" not in _norm(n.get("name"))
    ]

    if not pelvis_cands:
        blockers.append({"code": "NO_PELVIS_CANDIDATE"})
    elif len(pelvis_cands) > 1 and len(set(pelvis_cands)) > 1:
        # Prefer structural + name intersection
        both = [i for i in pelvis_cands if i in structural_pelvis and _token_hit(name_of(i), PELVIS_TOKENS)]
        if len(both) == 1:
            pelvis_cands = both
        elif len(structural_pelvis) == 1:
            pelvis_cands = structural_pelvis
        else:
            ambiguities.append({"code": "MULTIPLE_PELVIS_CANDIDATES", "candidates": pelvis_cands})
            blockers.append({"code": "MULTIPLE_PELVIS_CANDIDATES", "candidates": pelvis_cands})

    if len(left_shoulders) != 1 or len(right_shoulders) != 1:
        if len(shoulder_cands) < 2:
            blockers.append({"code": "SHOULDERS_MISSING", "found": shoulder_cands})
        else:
            ambiguities.append(
                {
                    "code": "SHOULDER_SIDE_AMBIGUOUS",
                    "left": left_shoulders,
                    "right": right_shoulders,
                    "all": shoulder_cands,
                }
            )
            blockers.append(
                {
                    "code": "SHOULDER_SIDE_AMBIGUOUS",
                    "left": left_shoulders,
                    "right": right_shoulders,
                    "all": shoulder_cands,
                }
            )

    if not neck_cands and not head_cands:
        blockers.append({"code": "NECK_HEAD_MISSING"})

    pelvis_idx = pelvis_cands[0] if pelvis_cands and not any(b.get("code") == "MULTIPLE_PELVIS_CANDIDATES" for b in blockers) else None
    ls = left_shoulders[0] if len(left_shoulders) == 1 else None
    rs = right_shoulders[0] if len(right_shoulders) == 1 else None

    chest_candidate = None
    chest_evidence: list[str] = []
    if (
        pelvis_idx is not None
        and ls is not None
        and rs is not None
        and not any(b.get("code") == "SHOULDER_SIDE_AMBIGUOUS" for b in blockers)
    ):
        lca = _lca(parent, ls, rs)
        if lca is None:
            blockers.append({"code": "SHOULDERS_ON_UNRELATED_BRANCHES"})
        elif not _is_ancestor(parent, pelvis_idx, lca):
            blockers.append({"code": "SHOULDER_LCA_NOT_UNDER_PELVIS", "lca": lca})
        else:
            chest_candidate = lca
            chest_evidence = [
                "BILATERAL_SHOULDER_ATTACHMENT",
                "CENTRAL_TORSO_CHAIN",
                "ABOVE_PELVIS",
            ]

    head_idx = None
    neck_idx = None
    if head_cands:
        # prefer head under chest/pelvis
        for h in head_cands:
            if chest_candidate is not None and _is_ancestor(parent, chest_candidate, h):
                head_idx = h
                break
            if pelvis_idx is not None and _is_ancestor(parent, pelvis_idx, h):
                head_idx = h
                break
        if head_idx is None and len(head_cands) == 1:
            head_idx = head_cands[0]
        elif head_idx is None and len(head_cands) > 1:
            ambiguities.append({"code": "MULTIPLE_HEAD_CANDIDATES", "candidates": head_cands})
            blockers.append({"code": "MULTIPLE_HEAD_CANDIDATES"})

    if neck_cands:
        for n in neck_cands:
            if head_idx is not None and (_is_ancestor(parent, n, head_idx) or parent.get(head_idx) == n):
                neck_idx = n
                break
            if chest_candidate is not None and _is_ancestor(parent, chest_candidate, n):
                neck_idx = n
                break
        if neck_idx is None and len(neck_cands) == 1:
            neck_idx = neck_cands[0]

    if chest_candidate is not None and neck_idx is not None:
        if _is_ancestor(parent, chest_candidate, neck_idx) or chest_candidate == neck_idx:
            chest_evidence.append("NECK_DESCENDANT")
        else:
            # neck not under chest — try re-evaluate
            blockers.append({"code": "NECK_OUTSIDE_TORSO_CHAIN", "chest": chest_candidate, "neck": neck_idx})

    if chest_candidate is not None and head_idx is not None:
        if _is_ancestor(parent, chest_candidate, head_idx):
            if "NECK_DESCENDANT" not in chest_evidence:
                chest_evidence.append("NECK_DESCENDANT")  # head under chest implies neck path
        else:
            blockers.append({"code": "HEAD_OUTSIDE_TORSO_CHAIN", "chest": chest_candidate, "head": head_idx})

    ordered_chain: list[int] = []
    if pelvis_idx is not None and head_idx is not None:
        path = _path_from_ancestor(parent, pelvis_idx, head_idx)
        if path:
            ordered_chain = path
        else:
            blockers.append({"code": "DISCONNECTED_TORSO_CHAIN"})
    elif pelvis_idx is not None and neck_idx is not None:
        path = _path_from_ancestor(parent, pelvis_idx, neck_idx)
        if path:
            ordered_chain = path
        else:
            blockers.append({"code": "DISCONNECTED_TORSO_CHAIN"})

    if chest_candidate is not None and ordered_chain and chest_candidate not in ordered_chain:
        blockers.append({"code": "CHEST_NOT_ON_TORSO_CHAIN", "chest": chest_candidate})

    if chest_candidate is not None and ordered_chain and chest_candidate in ordered_chain:
        chest_evidence.append("CANONICAL_ORDER_VALID")

    status = "BLOCKED" if blockers else "PASS"
    return {
        "schema": REPORT_SCHEMA,
        "stage": "CR01-P02",
        "status": status,
        "anchors": {
            "pelvisIndex": pelvis_idx,
            "pelvisName": name_of(pelvis_idx) if pelvis_idx is not None else None,
            "leftShoulderIndex": ls,
            "leftShoulderName": name_of(ls) if ls is not None else None,
            "rightShoulderIndex": rs,
            "rightShoulderName": name_of(rs) if rs is not None else None,
            "chestCandidateIndex": chest_candidate,
            "chestCandidateName": name_of(chest_candidate) if chest_candidate is not None else None,
            "chestEvidence": chest_evidence,
            "neckIndex": neck_idx,
            "neckName": name_of(neck_idx) if neck_idx is not None else None,
            "headIndex": head_idx,
            "headName": name_of(head_idx) if head_idx is not None else None,
        },
        "orderedTorsoChain": [
            {"index": i, "name": name_of(i)} for i in ordered_chain
        ],
        "orderedTorsoChainIndices": ordered_chain,
        "ambiguities": ambiguities,
        "blockers": blockers,
    }
