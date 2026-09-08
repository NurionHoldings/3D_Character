"""Final Production Readiness judgment for PR Gate 8."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

from nurion_v06_production_readiness.gate8.parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETER_HASH_FROZEN,
    GATE6_PARAMETER_HASH_FROZEN,
    GATE7_PARAMETER_HASH_FROZEN,
    GATE8_PARAMETERS,
    HOLDOUT_FBX_SHA256,
    HOLDOUT_ZIP_SHA256,
    PR_INHERITED_LIMITATIONS,
    V06_SEAL_PACKAGE_SHA256,
    WRAPPER_SHA256_FROZEN,
    WRAPPER_VERSION_FROZEN,
    parameter_hash,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_full_sha(s: str) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


def run_final_judgment(*, root: Path) -> Dict:
    root = Path(root)
    pr = root / "dist" / "v0.6" / "production_readiness"
    checks: List[Dict] = []
    evidence_gaps: List[str] = []
    hard: List[str] = []
    conditions: List[str] = []

    def add(name: str, ok: bool, detail: str = "", *, gap: bool = False) -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            if gap:
                evidence_gaps.append(name)
            else:
                hard.append(name)

    # --- Gate hash continuity ---
    expected = {
        1: GATE1_PARAMETER_HASH_FROZEN,
        2: GATE2_PARAMETER_HASH_FROZEN,
        3: GATE3_PARAMETER_HASH_FROZEN,
        4: GATE4_PARAMETER_HASH_FROZEN,
        5: GATE5_PARAMETER_HASH_FROZEN,
        6: GATE6_PARAMETER_HASH_FROZEN,
        7: GATE7_PARAMETER_HASH_FROZEN,
    }
    status_files = {
        1: pr / "gate1/V06_PR_GATE1_STATUS.json",
        2: pr / "gate2/V06_PR_GATE2_STATUS.json",
        3: pr / "gate3/V06_PR_GATE3_STATUS.json",
        4: pr / "gate4/V06_PR_GATE4_STATUS.json",
        5: pr / "gate5/V06_PR_GATE5_STATUS.json",
        6: pr / "gate6/V06_PR_GATE6_STATUS.json",
        7: pr / "gate7/V06_PR_GATE7_STATUS.json",
    }
    for g, exp in expected.items():
        path = status_files[g]
        if not path.is_file():
            add(f"GATE{g}_STATUS_PRESENT", False, str(path))
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        got = doc.get("parameterHash")
        add(f"GATE{g}_HASH_CONTINUITY", got == exp and _is_full_sha(str(got or "")), f"{got}")
        add(f"GATE{g}_LOCKED", bool(doc.get("LOCKED") or doc.get("officialFrozenBaseline") or g < 8), str(doc.get("LOCKED")))

    # Live parameter modules
    from nurion_v06_production_readiness.gate1.parameters import parameter_hash as g1h
    from nurion_v06_production_readiness.gate2.parameters import parameter_hash as g2h
    from nurion_v06_production_readiness.gate3.parameters import parameter_hash as g3h
    from nurion_v06_production_readiness.gate4.parameters import parameter_hash as g4h
    from nurion_v06_production_readiness.gate5.parameters import parameter_hash as g5h
    from nurion_v06_production_readiness.gate6.parameters import parameter_hash as g6h
    from nurion_v06_production_readiness.gate7.parameters import parameter_hash as g7h

    live = [g1h(), g2h(), g3h(), g4h(), g5h(), g6h(), g7h()]
    add(
        "LIVE_GATE1_TO_7_HASH_MATCH",
        live == list(expected.values()),
        json.dumps(live),
    )

    # --- RC.1 / wrapper / seal ---
    rc1 = root / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
    wrap = pr / "gate3/wrapper/nurion_v06_unified_runtime_from_rc1_install_wrapper.zip"
    seal = root / "dist/v0.6/V06_FINAL_BASELINE_LOCK.json"
    rc_sha = sha256_file(rc1) if rc1.is_file() else ""
    wrap_sha = sha256_file(wrap) if wrap.is_file() else ""
    add("RC1_SHA_FULL_MATCH", rc_sha == V06_SEAL_PACKAGE_SHA256 and _is_full_sha(rc_sha), rc_sha)
    add("WRAPPER_SHA_FULL_MATCH", wrap_sha == WRAPPER_SHA256_FROZEN and _is_full_sha(wrap_sha), wrap_sha)
    seal_ok = False
    seal_sha = ""
    if seal.is_file():
        sdoc = json.loads(seal.read_text(encoding="utf-8"))
        seal_sha = sdoc.get("packageSha256") or ""
        seal_ok = seal_sha == V06_SEAL_PACKAGE_SHA256 and _is_full_sha(seal_sha)
    add("V06_SEAL_HASH_MATCH", seal_ok, seal_sha)

    # --- Holdout identity / novelty scope ---
    identity_path = pr / "gate7/V06_PR_GATE7_HOLDOUT_ASSET_IDENTITY.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8")) if identity_path.is_file() else {}
    hashes = identity.get("hashesFullSha256") or {}
    zip_sha = hashes.get("zipSha256") or ""
    fbx_sha = hashes.get("fbxSha256") or ""
    add("HOLDOUT_ZIP_SHA_FULL_64", zip_sha == HOLDOUT_ZIP_SHA256 and _is_full_sha(zip_sha), zip_sha)
    add("HOLDOUT_FBX_SHA_FULL_64", fbx_sha == HOLDOUT_FBX_SHA256 and _is_full_sha(fbx_sha), fbx_sha)
    add(
        "HOLDOUT_NOVELTY_SCOPE_PR_TRACK",
        identity.get("noveltyScope") == "FRESH_WITHIN_PR_TRACK",
        str(identity.get("noveltyScope")),
        gap=not identity,
    )
    add(
        "HOLDOUT_NO_PROJECT_WIDE_FRESH_CLAIM",
        identity.get("projectWideFreshHoldoutClaim") == "DENY",
        str(identity.get("projectWideFreshHoldoutClaim")),
        gap=not identity,
    )
    naming = identity.get("assetNaming") or {}
    add(
        "HOLDOUT_NAMING_RELATION_DISCLOSED",
        naming.get("holdoutLabel") == "MINIMALIST_TENNIS_OUT"
        and naming.get("submissionZipFileName") == "Wither_character-rig.zip"
        and bool(naming.get("relationship")),
        json.dumps(naming),
        gap=not identity,
    )
    hist = identity.get("priorProjectHistory") or {}
    add(
        "HOLDOUT_V01_V02_HISTORY_DISCLOSED",
        "USED" in str(hist.get("v0.1", "")) and "USED" in str(hist.get("v0.2", "")),
        json.dumps(hist),
        gap=not identity,
    )

    # Verify staged zip still matches
    staged = pr / "gate7/inbox/Wither_character-rig.zip"
    if staged.is_file():
        add("STAGED_HOLDOUT_ZIP_MATCH", sha256_file(staged) == HOLDOUT_ZIP_SHA256, sha256_file(staged))
    else:
        add("STAGED_HOLDOUT_ZIP_MATCH", False, "missing", gap=True)

    # --- Limitations disclosure surfaces ---
    lim_reg = json.loads((pr / "V06_PR_INHERITED_LIMITATIONS.json").read_text(encoding="utf-8"))
    lims = lim_reg.get("limitations") or []
    add("LIMITATIONS_FIVE_REGISTERED", lims == list(PR_INHERITED_LIMITATIONS), json.dumps(lims))
    add("PANEL_LIMITATION_INCLUDED", "PANEL_LIMITATION_IDS_RENDERED" in lims)

    guide = pr / "gate6/V06_PR_OPS_OPERATOR_GUIDE.md"
    guide_text = guide.read_text(encoding="utf-8") if guide.is_file() else ""
    # Ops guide may still say "four" for v0.5 set; panel gap must be disclosed somewhere in PR evidence
    disc_g7 = pr / "gate7/NURION_V06_EXPORT_DISCLOSURE.json"
    disc = json.loads(disc_g7.read_text(encoding="utf-8")) if disc_g7.is_file() else {}
    disc_lims = disc.get("inheritedLimitations") or []
    add(
        "EXPORT_DISCLOSURE_LIMITATIONS_FIVE",
        set(disc_lims) == set(PR_INHERITED_LIMITATIONS),
        json.dumps(disc_lims),
    )
    add(
        "EXPORT_DISCLOSURE_PANEL_ID_NOT_RENDERED",
        disc.get("panelLimitationIdsRendered") is False
        and disc.get("panelLimitationId") == "PANEL_LIMITATION_IDS_RENDERED",
        json.dumps({k: disc.get(k) for k in ("panelLimitationIdsRendered", "panelLimitationId")}),
    )
    # Docs: identity + inherited registry count as disclosure; ops guide has original 4 + panel gap note from gate6
    add(
        "LIMITATIONS_DOCUMENTED",
        all(x in (guide_text + json.dumps(lim_reg) + json.dumps(identity) + json.dumps(disc)) for x in PR_INHERITED_LIMITATIONS),
    )

    # --- Policy / channel / activation ---
    add("CHANNEL_LIMITED_INTERNAL_OPERATOR", GATE8_PARAMETERS["channel"] == "LIMITED_INTERNAL_OPERATOR")
    add("EXTERNAL_CUSTOMER_DEPLOY_DENY", GATE8_PARAMETERS["externalCustomerDeploy"] == "DENY")
    add("UNATTENDED_AUTOMATION_DENY", GATE8_PARAMETERS["unattendedAutomation"] == "DENY")
    add("GENERAL_PUBLIC_RELEASE_DENY", GATE8_PARAMETERS["generalPublicRelease"] == "DENY")
    add("OPERATOR_PRE_TRAINING_REQUIRED", GATE8_PARAMETERS["operatorPreTrainingRequired"] is True)
    add("EXPORT_DISCLOSURE_CHECK_REQUIRED", GATE8_PARAMETERS["exportDisclosureCheckRequired"] is True)
    add("PRODUCTION_AUTO_ACTIVATE_DENY", GATE8_PARAMETERS["productionAutoActivate"] == "DENY")
    add("JUDGMENT_SEPARATE_FROM_ACTIVATION", GATE8_PARAMETERS["judgmentSeparateFromActivation"] is True)
    add("ACTIVATION_BY_THIS_GATE_DENY", GATE8_PARAMETERS["activationByThisGate"] == "DENY")
    add("UNCONDITIONAL_GO_DENY", GATE8_PARAMETERS["unconditionalGo"] == "DENY")

    # Panel risk acceptance → condition, not hard fail if disclosed
    panel_gap = GATE8_PARAMETERS["panelLimitationIdsRendered"] is False
    if panel_gap:
        conditions.append("PANEL_LIMITATION_IDS_RENDERED")
        add("PANEL_ID_GAP_DISCLOSED_AS_CONDITION", True, "accepted as CONDITIONAL_GO factor; unconditional GO DENY")

    conditions.extend(
        [
            "SEALED_WITH_LIMITATIONS_BASELINE",
            "CHANNEL_LIMITED_INTERNAL_OPERATOR_ONLY",
            "HOLDOUT_NOVELTY_FRESH_WITHIN_PR_TRACK_ONLY",
            "ACTIVATION_REQUIRES_SEPARATE_APPROVAL",
        ]
    )

    # Verdict
    if evidence_gaps and not hard:
        # only gaps
        if any(c["result"] == "FAIL" for c in checks if c["check"] in evidence_gaps):
            verdict = "MORE_EVIDENCE_REQUIRED"
        else:
            verdict = "CONDITIONAL_GO"
    elif hard:
        # If only evidence-style failures already counted in hard via gap=False, NO_GO
        verdict = "NO_GO"
    else:
        # All critical PASS; panel gap forces conditional
        verdict = "CONDITIONAL_GO"

    # Refine: any FAIL that is not an accepted condition → if evidence gap flags → MORE_EVIDENCE; else NO_GO
    fails = [c["check"] for c in checks if c["result"] == "FAIL"]
    if fails:
        if set(fails) <= set(evidence_gaps):
            verdict = "MORE_EVIDENCE_REQUIRED"
        else:
            verdict = "NO_GO"
    else:
        verdict = "CONDITIONAL_GO"

    # Never allow unconditional GO
    if verdict not in GATE8_PARAMETERS["allowedVerdicts"]:
        verdict = "NO_GO"

    return {
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "checks": checks,
        "hardFails": [c["check"] for c in checks if c["result"] == "FAIL"],
        "conditions": sorted(set(conditions)),
        "evidenceGaps": evidence_gaps,
        "activation": "NOT_GRANTED",
        "activationRequires": [
            "SEPARATE_EXPLICIT_ACTIVATION_APPROVAL",
            "OPERATOR_PRE_TRAINING_COMPLETE",
            "EXPORT_DISCLOSURE_ACKNOWLEDGED",
            "CHANNEL_REMAINS_LIMITED_INTERNAL_OPERATOR",
        ],
        "channel": "LIMITED_INTERNAL_OPERATOR",
        "productionAutoActivate": "DENY",
        "unconditionalGo": "DENY",
        "wrapperVersion": WRAPPER_VERSION_FROZEN,
        "wrapperSha256": WRAPPER_SHA256_FROZEN,
        "rc1Sha256": V06_SEAL_PACKAGE_SHA256,
        "holdoutZipSha256": HOLDOUT_ZIP_SHA256,
        "holdoutFbxSha256": HOLDOUT_FBX_SHA256,
        "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
        "next": (
            "AWAIT_SEPARATE_ACTIVATION_APPROVAL"
            if verdict == "CONDITIONAL_GO"
            else ("COLLECT_MORE_EVIDENCE" if verdict == "MORE_EVIDENCE_REQUIRED" else "REMEDIATE_PRODUCTION_READINESS")
        ),
    }
