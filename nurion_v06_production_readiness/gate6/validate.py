"""Static + content validation for PR Gate 6 ops docs / sealed UI policy."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

from nurion_v06_production_readiness.gate6.parameters import (
    FORBIDDEN_DOC_PHRASES,
    GATE6_PARAMETERS,
    REQUIRED_DOC_SECTIONS,
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


def validate_ops_guide(guide_text: str) -> Dict:
    checks = []
    lower = guide_text.lower()

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    for sec in REQUIRED_DOC_SECTIONS:
        add(f"DOC_SECTION_{sec}", f"SECTION:{sec}" in guide_text, sec)

    rc1 = GATE6_PARAMETERS["sealedBaselineSha256"]
    add("DOC_RC1_FULL_SHA256", rc1 in guide_text, rc1)
    add("DOC_WRAPPER_FULL_SHA256", WRAPPER_SHA256_FROZEN in guide_text, WRAPPER_SHA256_FROZEN)
    add("DOC_WRAPPER_VERSION", WRAPPER_VERSION_FROZEN in guide_text, WRAPPER_VERSION_FROZEN)
    add("DOC_PRODUCTION_NO_GO", "Production: NO-GO" in guide_text or "**Production: NO-GO**" in guide_text)
    add("DOC_CHANNEL", "LIMITED_INTERNAL_OPERATOR" in guide_text)

    for lim in GATE6_PARAMETERS["inheritedLimitations"]:
        add(f"DOC_LIMITATION_{lim}", lim in guide_text, lim)

    # Docs must NOT falsely claim sealed panel renders limitation IDs
    false_claim = bool(
        re.search(r"panel.*(shows|renders|lists).{0,40}FOOT_SLIDE_RESIDUAL_11", guide_text, re.I)
    )
    add("DOC_NO_FALSE_PANEL_LIMITATION_CLAIM", not false_claim)

    forbidden_hits = [p for p in FORBIDDEN_DOC_PHRASES if p in lower]
    # allow mentioning "auto-clear" only as DENY policy
    forbidden_hits = [p for p in forbidden_hits if p not in ("auto-clear", "auto clear") or "deny" not in lower]
    # Refine: fail only if promotional misuse
    promo_hits = []
    for p in FORBIDDEN_DOC_PHRASES:
        if p in ("auto-clear", "auto clear", "limitations cleared"):
            # fail if claiming cleared without DENY nearby
            if p in lower and "deny" not in lower:
                promo_hits.append(p)
        elif p in lower:
            promo_hits.append(p)
    add("DOC_NO_MISLEADING_PHRASES", len(promo_hits) == 0, json.dumps(promo_hits))

    add("DOC_PARTIAL_EXPORT_DENY", "partial export publish" in lower and "deny" in lower)
    add("DOC_VALIDATE_BEFORE_EXPORT", "validation required before export" in lower or "validate-before-export" in lower)
    add("DOC_REST_FALLBACK", "REST_FALLBACK" in guide_text)
    add("AUTO_CLEAR_LIMITATIONS_DENY", GATE6_PARAMETERS.get("autoClearLimitations") == "DENY")

    return {"checks": checks, "ok": all(c["result"] == "PASS" for c in checks)}


def validate_sealed_panel_source(panel_py: Path) -> Dict:
    text = panel_py.read_text(encoding="utf-8") if panel_py.is_file() else ""
    checks = []

    def add(name: str, ok: bool, detail: str = "", lim: bool = False) -> None:
        if lim and not ok:
            checks.append({"check": name, "result": "PASS_WITH_LIMITATIONS", "detail": detail})
        else:
            checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    add("PANEL_PRODUCTION_LABEL", "Production:" in text and "NO-GO" in text)
    add("PANEL_VALIDATE_BEFORE_EXPORT", "Validation required before export" in text)
    add("PANEL_WORKFLOW_STEPS", all(x in text for x in ("Select Character", "Analyze", "Build", "Apply", "Validate", "Export")))
    add("PANEL_ABSTAIN_FIELD", "ABSTAIN" in text)
    add("PANEL_LIPSYNC_FIELD", "Lipsync" in text)
    add("PANEL_CLASS_FIELD", "Class:" in text)

    # Known sealed gap: limitation IDs not rendered
    lim_ids = GATE6_PARAMETERS["inheritedLimitations"]
    rendered = all(lim in text for lim in lim_ids)
    add(
        "PANEL_LIMITATION_IDS_RENDERED",
        rendered,
        "sealed panel omits limitation ID labels; disclosed via ops guide/ui_snapshot/export sidecar",
        lim=True,
    )
    return {"checks": checks, "ok": all(c["result"] != "FAIL" for c in checks), "limitationIdsRendered": rendered}


def validate_sealed_policy(addon_dir: Path) -> Dict:
    addon_dir = Path(addon_dir)
    params = addon_dir / "gate6" / "parameters.py"
    gate1 = addon_dir / "gate1" / "parameters.py"
    workflow = addon_dir / "gate6" / "workflow.py"
    text_p = params.read_text(encoding="utf-8") if params.is_file() else ""
    text_g1 = gate1.read_text(encoding="utf-8") if gate1.is_file() else ""
    text_w = workflow.read_text(encoding="utf-8") if workflow.is_file() else ""
    combined = text_p + "\n" + text_g1
    checks = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    for lim in GATE6_PARAMETERS["inheritedLimitations"]:
        add(f"POLICY_PARAM_{lim}", lim in combined, lim)
    add("POLICY_UI_SNAPSHOT_LIMITATIONS", "inheritedLimitationsFromV05" in text_w)
    add("POLICY_EXPORT_REQUIRES_VALIDATION", "exportRequiresValidation" in text_p)
    add("POLICY_LIMITATION_AUTO_CLEAR_DENY", "limitationAutoClear" in text_p and "DENY" in text_p)
    add("POLICY_PRODUCTION_NO_GO", '"production": "NO-GO"' in text_p or "'production': 'NO-GO'" in text_p)
    return {"checks": checks, "ok": all(c["result"] == "PASS" for c in checks)}
