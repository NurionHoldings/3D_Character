"""CR01-P04 — Retarget safety validation (consume locked BODY axis authority read-only)."""

from __future__ import annotations

from typing import Any

REPORT_SCHEMA = "NURION_V2_CR01_RETARGET_SAFETY_V1"

SPINE_HEAD = ["NURION_pelvis", "NURION_spine01", "NURION_chest", "NURION_neck", "NURION_head"]
ARM_L = ["NURION_chest", "NURION_clavicle_L", "NURION_upperArm_L", "NURION_lowerArm_L", "NURION_hand_L"]
ARM_R = ["NURION_chest", "NURION_clavicle_R", "NURION_upperArm_R", "NURION_lowerArm_R", "NURION_hand_R"]
LEG_L = ["NURION_pelvis", "NURION_thigh_L", "NURION_calf_L", "NURION_foot_L"]
LEG_R = ["NURION_pelvis", "NURION_thigh_R", "NURION_calf_R", "NURION_foot_R"]


def _is_ancestor(parent: dict[int, int | None], anc: int, desc: int) -> bool:
    cur: int | None = desc
    while cur is not None:
        if cur == anc:
            return True
        cur = parent.get(cur)
    return False


def validate_retarget_safety(inspection: dict[str, Any], assignment: dict[str, Any]) -> dict[str, Any]:
    skel = inspection.get("skeleton") or {}
    parent: dict[int, int | None] = {int(k): v for k, v in (skel.get("parentMap") or {}).items()}
    assigns = assignment.get("semanticAssignments") or {}
    blockers: list[dict[str, Any]] = []

    root = assigns.get("NURION_root") or {}
    pelvis = assigns.get("NURION_pelvis") or {}
    if root.get("status") == "RESOLVED" and pelvis.get("status") == "RESOLVED":
        if root.get("sourceIndex") == pelvis.get("sourceIndex"):
            blockers.append({"code": "ROOT_PELVIS_NOT_DISTINCT"})
    else:
        blockers.append({"code": "ROOT_OR_PELVIS_UNRESOLVED"})

    def chain_status(name: str, chain: list[str], optional: set[str] | None = None) -> dict[str, Any]:
        optional = optional or set()
        resolved = []
        for sem in chain:
            m = assigns.get(sem) or {}
            st = m.get("status")
            if st == "RESOLVED" and isinstance(m.get("sourceIndex"), int):
                resolved.append((sem, m["sourceIndex"]))
            elif st in ("MISSING", "NOT_APPLICABLE") and sem in optional:
                continue
            elif st != "RESOLVED" and sem not in optional:
                return {"chain": name, "status": "BLOCKED", "reason": f"unresolved:{sem}"}
        for i in range(len(resolved) - 1):
            a_sem, a_i = resolved[i]
            b_sem, b_i = resolved[i + 1]
            if not _is_ancestor(parent, a_i, b_i):
                return {"chain": name, "status": "BLOCKED", "reason": f"ancestry_break:{a_sem}->{b_sem}"}
        return {"chain": name, "status": "PASS", "resolvedCount": len(resolved)}

    chains = {
        "spineHead": chain_status("spineHead", SPINE_HEAD, {"NURION_spine01", "NURION_spine02", "NURION_neck"}),
        "armL": chain_status("armL", ARM_L, {"NURION_clavicle_L"}),
        "armR": chain_status("armR", ARM_R, {"NURION_clavicle_R"}),
        "legL": chain_status("legL", LEG_L, {"NURION_toe_L"}),
        "legR": chain_status("legR", LEG_R, {"NURION_toe_R"}),
    }
    # Re-validate spine with spine02 optional always
    chains["spineHead"] = chain_status(
        "spineHead",
        ["NURION_pelvis", "NURION_spine01", "NURION_chest", "NURION_neck", "NURION_head"],
        {"NURION_spine01", "NURION_neck"},
    )
    # Better: pelvis → spine01 → chest → neck → head with spine01 optional if missing
    def spine_flex() -> dict[str, Any]:
        order = ["NURION_pelvis", "NURION_spine01", "NURION_spine02", "NURION_chest", "NURION_neck", "NURION_head"]
        return chain_status("spineHead", order, {"NURION_spine01", "NURION_spine02", "NURION_neck"})

    chains["spineHead"] = spine_flex()

    for cr in chains.values():
        if cr.get("status") == "BLOCKED":
            blockers.append({"code": "CHAIN_VALIDATION", "detail": cr})

    status = "BLOCKED" if blockers else "PASS"
    return {
        "schema": REPORT_SCHEMA,
        "stage": "CR01-P04",
        "status": status,
        "chainValidation": chains,
        "invariants": {
            "rootNeqPelvis": root.get("sourceIndex") != pelvis.get("sourceIndex"),
            "protectedInvariant": "NURION_root ≠ NURION_pelvis",
        },
        "blockers": blockers,
        "axisRetarget": {
            "authority": "CONSUME_ONLY",
            "note": "Prototype records compatibility of semantic ancestry; full axis math deferred to V2 pipeline if opened",
            "status": "PASS" if status == "PASS" else "BLOCKED",
        },
    }
