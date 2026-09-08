"""Read-only Limited Internal Production Activation Review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List

from nurion_v06_production_readiness.activation_review.parameters import (
    ACTIVATION_REVIEW_PARAMETERS,
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETER_HASH_FROZEN,
    GATE6_PARAMETER_HASH_FROZEN,
    GATE7_PARAMETER_HASH_FROZEN,
    GATE8_PARAMETER_HASH_FROZEN,
    parameter_hash,
)
from nurion_v06_production_readiness.gate7.parameters import (
    HOLDOUT_FBX_SHA256,
    HOLDOUT_ZIP_SHA256,
    PR_INHERITED_LIMITATIONS,
)
from nurion_v06_production_readiness.gate8.parameters import (
    V06_SEAL_PACKAGE_SHA256,
    WRAPPER_SHA256_FROZEN,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _full_sha(s: object) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


def run_activation_review(*, root: Path) -> Dict:
    root = Path(root)
    pr = root / "dist" / "v0.6" / "production_readiness"
    checks: List[Dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    # Mode guards
    add("MODE_READ_ONLY_REVIEW", ACTIVATION_REVIEW_PARAMETERS["mode"] == "READ_ONLY_REVIEW")
    add("THIS_COMMAND_DOES_NOT_ACTIVATE", ACTIVATION_REVIEW_PARAMETERS["thisCommandActivatesProduction"] == "DENY")
    add("ACTIVATION_STILL_NOT_GRANTED", ACTIVATION_REVIEW_PARAMETERS["activation"] == "NOT_GRANTED")
    add("ACTIVATION_EXECUTION_NOT_STARTED", ACTIVATION_REVIEW_PARAMETERS["activationExecution"] == "NOT_STARTED")
    add("DEPLOY_DENY", ACTIVATION_REVIEW_PARAMETERS["deploy"] == "DENY")
    add("CONDITION_CHANGE_DENY", ACTIVATION_REVIEW_PARAMETERS["conditionChange"] == "DENY")
    add("LIMITATION_CLEAR_DENY", ACTIVATION_REVIEW_PARAMETERS["limitationClear"] == "DENY")
    add("UNCONDITIONAL_GO_DENY", ACTIVATION_REVIEW_PARAMETERS["unconditionalGo"] == "DENY")

    # Freeze Gate8 / Gate7
    g8 = json.loads((pr / "gate8/V06_PR_GATE8_STATUS.json").read_text(encoding="utf-8"))
    g7 = json.loads((pr / "gate7/V06_PR_GATE7_STATUS.json").read_text(encoding="utf-8"))
    g8r = json.loads((pr / "gate8/V06_PR_GATE8_RECEIPT.json").read_text(encoding="utf-8"))
    add("GATE8_CONDITIONAL_GO", g8.get("PR_GATE8") == "CONDITIONAL_GO")
    add("GATE8_HASH_FROZEN", g8.get("parameterHash") == GATE8_PARAMETER_HASH_FROZEN and _full_sha(g8.get("parameterHash")))
    add("GATE7_HOLDOUT_PASS", g7.get("PR_GATE7") == "HOLDOUT_PASS")
    add("GATE7_HASH_FROZEN", g7.get("parameterHash") == GATE7_PARAMETER_HASH_FROZEN and _full_sha(g7.get("parameterHash")))
    add("GATE8_ACTIVATION_NOT_GRANTED", g8r.get("activation") == "NOT_GRANTED")

    # Continuity of all PR hashes on disk
    expected = {
        1: GATE1_PARAMETER_HASH_FROZEN,
        2: GATE2_PARAMETER_HASH_FROZEN,
        3: GATE3_PARAMETER_HASH_FROZEN,
        4: GATE4_PARAMETER_HASH_FROZEN,
        5: GATE5_PARAMETER_HASH_FROZEN,
        6: GATE6_PARAMETER_HASH_FROZEN,
        7: GATE7_PARAMETER_HASH_FROZEN,
        8: GATE8_PARAMETER_HASH_FROZEN,
    }
    for g, exp in expected.items():
        path = pr / f"gate{g}/V06_PR_GATE{g}_STATUS.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        add(f"GATE{g}_HASH_CONTINUITY", doc.get("parameterHash") == exp, str(doc.get("parameterHash")))

    # Live module hashes Gate1–8
    from nurion_v06_production_readiness.gate1.parameters import parameter_hash as g1h
    from nurion_v06_production_readiness.gate2.parameters import parameter_hash as g2h
    from nurion_v06_production_readiness.gate3.parameters import parameter_hash as g3h
    from nurion_v06_production_readiness.gate4.parameters import parameter_hash as g4h
    from nurion_v06_production_readiness.gate5.parameters import parameter_hash as g5h
    from nurion_v06_production_readiness.gate6.parameters import parameter_hash as g6h
    from nurion_v06_production_readiness.gate7.parameters import parameter_hash as g7h
    from nurion_v06_production_readiness.gate8.parameters import parameter_hash as g8h

    live = [g1h(), g2h(), g3h(), g4h(), g5h(), g6h(), g7h(), g8h()]
    add("LIVE_GATE1_TO_8_HASH_MATCH", live == list(expected.values()), json.dumps(live))

    # Artifact hashes
    rc1 = root / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
    wrap = pr / "gate3/wrapper/nurion_v06_unified_runtime_from_rc1_install_wrapper.zip"
    seal = root / "dist/v0.6/V06_FINAL_BASELINE_LOCK.json"
    rc_sha = sha256_file(rc1)
    wrap_sha = sha256_file(wrap)
    seal_sha = json.loads(seal.read_text(encoding="utf-8")).get("packageSha256")
    add("RC1_SHA_MATCH", rc_sha == V06_SEAL_PACKAGE_SHA256 and _full_sha(rc_sha), rc_sha)
    add("WRAPPER_SHA_MATCH", wrap_sha == WRAPPER_SHA256_FROZEN and _full_sha(wrap_sha), wrap_sha)
    add("SEAL_SHA_MATCH", seal_sha == V06_SEAL_PACKAGE_SHA256 and _full_sha(seal_sha), str(seal_sha))

    # Holdout identity
    identity = json.loads((pr / "gate7/V06_PR_GATE7_HOLDOUT_ASSET_IDENTITY.json").read_text(encoding="utf-8"))
    h = identity.get("hashesFullSha256") or {}
    add("HOLDOUT_ZIP_FULL_64", h.get("zipSha256") == HOLDOUT_ZIP_SHA256 and _full_sha(h.get("zipSha256")), h.get("zipSha256"))
    add("HOLDOUT_FBX_FULL_64", h.get("fbxSha256") == HOLDOUT_FBX_SHA256 and _full_sha(h.get("fbxSha256")), h.get("fbxSha256"))
    add("NOVELTY_FRESH_WITHIN_PR_TRACK", identity.get("noveltyScope") == "FRESH_WITHIN_PR_TRACK")
    add("NO_PROJECT_WIDE_FRESH_CLAIM", identity.get("projectWideFreshHoldoutClaim") == "DENY")
    hist = identity.get("priorProjectHistory") or {}
    add("V01_V02_HISTORY_PUBLIC", "USED" in str(hist.get("v0.1", "")) and "USED" in str(hist.get("v0.2", "")))
    naming = identity.get("assetNaming") or {}
    add(
        "WITHER_MINIMALIST_NAMING_PUBLIC",
        naming.get("submissionZipFileName") == "Wither_character-rig.zip"
        and naming.get("holdoutLabel") == "MINIMALIST_TENNIS_OUT",
        json.dumps(naming),
    )

    # Limitations immutable (5) — compare registry to frozen list; no clear
    lim_reg = json.loads((pr / "V06_PR_INHERITED_LIMITATIONS.json").read_text(encoding="utf-8"))
    lims = lim_reg.get("limitations") or []
    add("LIMITATIONS_FIVE_UNCHANGED", lims == list(PR_INHERITED_LIMITATIONS), json.dumps(lims))
    add("LIMITATION_AUTO_CLEAR_DENY", lim_reg.get("limitationAutoClear") == "DENY")
    add("PANEL_AUTO_FIX_DENY", lim_reg.get("panelAutoFix") == "DENY")
    add("PANEL_LIMITATION_STILL_PRESENT", "PANEL_LIMITATION_IDS_RENDERED" in lims)

    # Conditions from Gate8 receipt frozen — must still all be present; no removals
    conds = set(g8r.get("conditions") or [])
    required = set(ACTIVATION_REVIEW_PARAMETERS["requiredConditionsFrozen"])
    add("CONDITIONS_UNCHANGED_SUPERSET", required <= conds, json.dumps(sorted(conds)))
    add("CHANNEL_LIMITED_INTERNAL", g8r.get("channel") == "LIMITED_INTERNAL_OPERATOR")
    add("EXTERNAL_DEPLOY_DENY", g8r.get("externalCustomerDeploy") == "DENY")
    add("UNATTENDED_DENY", g8r.get("unattendedAutomation") == "DENY")
    add("PUBLIC_RELEASE_DENY", g8r.get("generalPublicRelease") == "DENY")

    # Operator brief present
    brief_path = pr / "gate8/V06_PR_CONDITIONAL_GO_OPERATOR_BRIEF.json"
    brief_ok = brief_path.is_file()
    add("OPERATOR_BRIEF_PRESENT", brief_ok, str(brief_path))

    # Export disclosure still lists 5 limitations
    disc = json.loads((pr / "gate7/NURION_V06_EXPORT_DISCLOSURE.json").read_text(encoding="utf-8"))
    add(
        "EXPORT_DISCLOSURE_LIMITATIONS_FIVE",
        set(disc.get("inheritedLimitations") or []) == set(PR_INHERITED_LIMITATIONS),
        json.dumps(disc.get("inheritedLimitations")),
    )
    add("EXPORT_DISCLOSURE_PANEL_NOT_RENDERED", disc.get("panelLimitationIdsRendered") is False)

    fails = [c["check"] for c in checks if c["result"] == "FAIL"]
    if fails:
        verdict = "REVIEW_DENY" if any(x.startswith("GATE") or "HASH" in x or "SHA" in x for x in fails) else "MORE_EVIDENCE_REQUIRED"
        # Prefer REVIEW_DENY for integrity fails
        integrity = [x for x in fails if "HASH" in x or "SHA" in x or x.startswith("GATE") or "UNCHANGED" in x]
        verdict = "REVIEW_DENY" if integrity else "MORE_EVIDENCE_REQUIRED"
    else:
        verdict = "REVIEW_PASS_AWAIT_ACTIVATION_EXECUTION_GO"

    return {
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "checks": checks,
        "hardFails": fails,
        "mode": "READ_ONLY_REVIEW",
        "activation": "NOT_GRANTED",
        "activationExecution": "NOT_STARTED",
        "deploy": "DENY",
        "conditionChange": "DENY",
        "limitationClear": "DENY",
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "conditionsFrozen": sorted(required),
        "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
        "next": (
            "AWAIT_ACTIVATION_EXECUTION_GO"
            if verdict == "REVIEW_PASS_AWAIT_ACTIVATION_EXECUTION_GO"
            else ("REMEDIATE_THEN_REREVIEW" if verdict == "REVIEW_DENY" else "COLLECT_MORE_EVIDENCE")
        ),
        "note": (
            "This review does not activate production. "
            "A separate explicit Activation Execution GO is required after REVIEW_PASS."
        ),
    }
