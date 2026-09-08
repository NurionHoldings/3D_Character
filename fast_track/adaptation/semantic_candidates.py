"""Semantic bone candidate detection — evidence + confidence; no source rename."""

from __future__ import annotations

import re
from typing import Any

# Alias tokens per NURION semantic role (consume-only mapping vocabulary).
# Detection is NOT name-only: hierarchy/side signals adjust confidence.
ALIASES: dict[str, tuple[str, ...]] = {
    "root": ("root", "armature", "skeleton", "metarig", "characterroot", "scene_root"),
    "pelvis": ("pelvis", "hips", "hip", "cog", "pelvis_bone", "hipbone", "sacrum"),
    "spine": ("spine", "spine1", "spine01", "spine_01", "spine_1", "back01", "back_01", "back"),
    "chest": ("chest", "spine2", "spine02", "spine3", "spine03", "upperchest", "thorax"),
    "neck": ("neck", "neck1", "neck01", "necklink"),
    "head": ("head", "skull", "head_bone", "headtop", "cranium", "noggin"),
    "clavicle_L": ("clavicle_l", "leftclavicle", "l_clavicle", "shoulder_l", "leftshoulder", "lcollar", "collar_l"),
    "clavicle_R": ("clavicle_r", "rightclavicle", "r_clavicle", "shoulder_r", "rightshoulder", "rcollar", "collar_r"),
    "upperArm_L": ("upperarm_l", "leftarm", "l_upperarm", "leftupperarm", "arm_l", "lupperlimb", "upperlimb_l"),
    "upperArm_R": ("upperarm_r", "rightarm", "r_upperarm", "rightupperarm", "arm_r", "rupperlimb", "upperlimb_r"),
    "lowerArm_L": ("lowerarm_l", "leftforearm", "l_forearm", "leftlowerarm", "forearm_l", "lforelimb", "forelimb_l"),
    "lowerArm_R": ("lowerarm_r", "rightforearm", "r_forearm", "rightlowerarm", "forearm_r", "rforelimb", "forelimb_r"),
    "hand_L": ("hand_l", "lefthand", "l_hand", "wrist_l", "lpalm", "palm_l"),
    "hand_R": ("hand_r", "righthand", "r_hand", "wrist_r", "rpalm", "palm_r"),
    "thigh_L": ("thigh_l", "leftupleg", "l_upleg", "leftthigh", "upleg_l", "lupperleg", "upperleg_l"),
    "thigh_R": ("thigh_r", "rightupleg", "r_upleg", "rightthigh", "upleg_r", "rupperleg", "upperleg_r"),
    "calf_L": ("calf_l", "leftleg", "l_leg", "leftlowerleg", "shin_l", "lowerleg_l", "lshin"),
    "calf_R": ("calf_r", "rightleg", "r_leg", "rightlowerleg", "shin_r", "lowerleg_r", "rshin"),
    "foot_L": ("foot_l", "leftfoot", "l_foot", "ankle_l", "lankle"),
    "foot_R": ("foot_r", "rightfoot", "r_foot", "ankle_r", "rankle"),
    "toe_L": ("toe_l", "lefttoebase", "l_toe", "toes_l"),
    "toe_R": ("toe_r", "righttoebase", "r_toe", "toes_r"),
    "eye_L": ("eye_l", "lefteye", "l_eye", "eyeball_l", "oculusl", "oculus_l", "lefteyeball"),
    "eye_R": ("eye_r", "righteye", "r_eye", "eyeball_r", "oculusr", "oculus_r", "righteyeball"),
    "jaw": ("jaw", "jawbone", "mandible", "lowerjaw", "chinbone", "chin"),
}


def _norm(name: str) -> str:
    s = name.strip().lower()
    s = s.replace("mixamorig:", "").replace("mixamorig", "")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _side_hint(norm: str) -> str | None:
    if norm.endswith("l") or "left" in norm or norm.startswith("l"):
        if "right" in norm or norm.endswith("r"):
            return None
        return "L"
    if norm.endswith("r") or "right" in norm or norm.startswith("r"):
        return "R"
    return None


def score_name(role: str, node_name: str) -> tuple[float, str]:
    """Return (0..1 confidence contribution, reason)."""
    n = _norm(node_name)
    aliases = ALIASES.get(role, ())
    if not n:
        return 0.0, "empty_name"
    for a in aliases:
        an = _norm(a)
        if n == an:
            return 0.85, f"exact_alias:{a}"
        if an and an in n:
            return 0.55, f"substring_alias:{a}"
    # Non-standard synonyms used in renamed fixtures
    special = {
        "pelvis": ("hipbone", "sacrum"),
        "head": ("cranium", "noggin"),
        "jaw": ("chinbone",),
        "eye_L": ("oculusl", "lefteyeball"),
        "eye_R": ("oculusr", "righteyeball"),
    }
    for sp in special.get(role, ()):
        if _norm(sp) == n or _norm(sp) in n:
            return 0.7, f"nonstandard_alias:{sp}"
    return 0.0, "no_name_match"


def detect_semantic_candidates(
    nodes: list[dict[str, Any]],
    skins: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Build semantic candidates with observed source names preserved.
    Uses name + joint membership + simple hierarchy adjacency — not name alone.
    """
    joint_set: set[int] = set()
    for skin in skins:
        for j in skin.get("joints") or []:
            if isinstance(j, int):
                joint_set.add(j)

    children_of: dict[int, list[int]] = {}
    parent_of: dict[int, int] = {}
    for i, node in enumerate(nodes):
        kids = node.get("children") or []
        children_of[i] = [c for c in kids if isinstance(c, int)]
        for c in children_of[i]:
            parent_of[c] = i

    roles = list(ALIASES.keys())
    candidates: dict[str, Any] = {}

    for role in roles:
        scored: list[dict[str, Any]] = []
        for i, node in enumerate(nodes):
            name = node.get("name") or f"node_{i}"
            conf, reason = score_name(role, str(name))
            if conf <= 0:
                continue
            evidence = [reason]
            # Joint membership boosts body roles
            if i in joint_set and role not in ("eye_L", "eye_R", "jaw"):
                conf = min(1.0, conf + 0.1)
                evidence.append("skin_joint_member")
            # Side consistency for L/R roles
            if role.endswith("_L") or role.endswith("_R"):
                want = role[-1]
                hint = _side_hint(_norm(str(name)))
                if hint == want:
                    conf = min(1.0, conf + 0.05)
                    evidence.append("side_token_match")
                elif hint and hint != want:
                    conf = max(0.0, conf - 0.4)
                    evidence.append("side_token_conflict")
            scored.append(
                {
                    "nodeIndex": i,
                    "observedSourceNodeName": name,
                    "confidence": round(conf, 4),
                    "reason": ";".join(evidence),
                }
            )
        scored.sort(key=lambda x: (-x["confidence"], x["nodeIndex"]))
        if not scored:
            candidates[role] = {
                "status": "NOT_DETECTED",
                "selected": None,
                "alternates": [],
            }
            continue
        top = scored[0]
        alts = scored[1:5]
        status = "DETECTED"
        if len(scored) > 1 and abs(scored[0]["confidence"] - scored[1]["confidence"]) < 0.05:
            status = "AMBIGUOUS"
        if top["confidence"] < 0.5:
            status = "AMBIGUOUS" if scored else "NOT_DETECTED"
            if top["confidence"] < 0.35:
                candidates[role] = {
                    "status": "NOT_DETECTED",
                    "selected": None,
                    "alternates": scored[:3],
                }
                continue
        candidates[role] = {
            "status": status,
            "selected": top,
            "alternates": alts,
        }

    # Hierarchy reinforcement: if pelvis→spine→chest→neck→head chain exists, boost
    chain_roles = ["pelvis", "spine", "chest", "neck", "head"]
    indices = []
    for r in chain_roles:
        sel = candidates.get(r, {}).get("selected")
        indices.append(sel["nodeIndex"] if sel else None)
    if all(x is not None for x in indices):
        ok_chain = True
        for a, b in zip(indices, indices[1:]):
            # b should be descendant of a (walk up from b)
            cur = b
            found = False
            seen = set()
            while cur is not None and cur not in seen:
                seen.add(cur)
                if cur == a:
                    found = True
                    break
                cur = parent_of.get(cur)
            if not found:
                ok_chain = False
                break
        if ok_chain:
            for r in chain_roles:
                sel = candidates[r]["selected"]
                if sel:
                    sel["confidence"] = round(min(1.0, sel["confidence"] + 0.08), 4)
                    sel["reason"] = sel["reason"] + ";hierarchy_chain_ok"
                    if candidates[r]["status"] == "AMBIGUOUS" and sel["confidence"] >= 0.6:
                        candidates[r]["status"] = "DETECTED"

    return {
        "candidates": candidates,
        "jointNodeCount": len(joint_set),
        "nodeCount": len(nodes),
        "detectionPolicy": "name_alias+skin_joint+side+hierarchy — not name-only",
    }
