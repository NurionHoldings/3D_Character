"""Generate official PR Gate 6 operator documentation (PR track; does not mutate RC.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from nurion_v06_production_readiness.gate6.parameters import (
    ERROR_CATALOG,
    GATE5_HARNESS_CORRECTIONS,
    GATE6_PARAMETERS,
    WRAPPER_SHA256_FROZEN,
    WRAPPER_VERSION_FROZEN,
)


def build_ops_guide_markdown() -> str:
    lims = GATE6_PARAMETERS["inheritedLimitations"]
    rc1 = GATE6_PARAMETERS["sealedBaselineSha256"]
    lines = [
        "# NURION v0.6 — Limited Internal Operator Guide",
        "",
        "<!-- SECTION:INSTALL_UPDATE_REMOVE_WRAPPER -->",
        "## Install / Update / Remove (bl_info install wrapper)",
        "",
        "Sealed RC.1 ZIP is **not** a Blender top-level add-on layout. Operators install the",
        f"**separate ops component** `bl_info` wrapper `{WRAPPER_VERSION_FROZEN}`.",
        "",
        f"- Wrapper version: `{WRAPPER_VERSION_FROZEN}`",
        f"- Wrapper SHA-256: `{WRAPPER_SHA256_FROZEN}`",
        f"- Target RC.1 SHA-256: `{rc1}`",
        "- RC.1 repack / in-place repair: **DENY**",
        "",
        "### Install",
        "1. Blender 5.0.1 → Edit → Preferences → Add-ons → Install…",
        "2. Select `nurion_v06_unified_runtime_from_rc1_install_wrapper.zip`",
        "3. Enable **NURION Unified Character Animation Runtime v0.6 RC.1**",
        "4. Open View3D → Sidebar → **NURION**",
        "",
        "### Update",
        "Re-install the **same hash-locked** wrapper ZIP with overwrite. Do not rebuild from",
        "mutated RC.1. Wrapper hash must remain frozen unless a new wrapper version is formally approved.",
        "",
        "### Remove",
        "Disable add-on, then Remove. User export artifacts outside the add-on folder must be preserved.",
        "",
        "<!-- SECTION:FIXED_WORKFLOW_VALIDATE_BEFORE_EXPORT -->",
        "## Fixed workflow & Validate-before-Export",
        "",
        "Mandatory order (out-of-order → SAFE_ABORT):",
        "1. Select Character",
        "2. Analyze Asset",
        "3. Build Unified Runtime",
        "4. Apply Motion Preset",
        "5. Validate Runtime",
        "6. Export",
        "",
        "Panel label: **Validation required before export**. Unvalidated export is CANCELLED.",
        "Partial export publish: **DENY**.",
        "",
        "<!-- SECTION:CLASSIFICATION_LIMITED_INELIGIBLE_ABSTAIN -->",
        "## LIMITED / INELIGIBLE / ABSTAIN",
        "",
        "| Class | Meaning | Runtime action |",
        "|-------|---------|----------------|",
        "| LIMITED | Supported with public disclosures | APPLY_LIMITED |",
        "| INELIGIBLE | Not eligible for unified runtime | ABSTAIN (force apply DENY) |",
        "| ABSTAIN | Operator-visible refusal (preset/path/class) | Do not force; disclose reason |",
        "",
        "Channel: **LIMITED_INTERNAL_OPERATOR** only.",
        "",
        "<!-- SECTION:REST_FALLBACK_AND_UNSUPPORTED_PRESETS -->",
        "## REST_FALLBACK & unsupported presets",
        "",
        "- Lipsync timeline unsupported → **REST_FALLBACK** (UI Lipsync field).",
        "- Unavailable presets (e.g. Gentlemans_Bow when missing) → apply **ABSTAIN** / DENY force apply.",
        "- Select an available preset, re-Validate, then Export.",
        "",
        "<!-- SECTION:INHERITED_LIMITATIONS_FOUR -->",
        "## Inherited limitations (4) — public, auto-clear DENY",
        "",
        "These IDs must remain operator-visible. They are **not** auto-cleared.",
        "",
    ]
    for i, lim in enumerate(lims, 1):
        lines.append(f"{i}. `{lim}`")
    lines.extend(
        [
            "",
            "### Disclosure surfaces (accurate; no misleading UI claims)",
            "",
            "1. **This Ops Guide** (authoritative operator text)",
            "2. **Policy/report** `ui_snapshot.inheritedLimitationsFromV05` (engine)",
            "3. **Export disclosure sidecar** `NURION_V06_EXPORT_DISCLOSURE.json` written beside exports",
            "4. **Sealed** `GATE6_PARAMETERS.inheritedLimitationsFromV05`",
            "",
            "Sealed Blender panel Status shows Production / Class / Lipsync / ABSTAIN / Validate.",
            "It does **not** render the four limitation ID strings as labels",
            f"(`sealedPanelLimitationIdRender={GATE6_PARAMETERS['sealedPanelLimitationIdRender']}`).",
            "Auto-fix of sealed RC.1/wrapper to add panel labels: **DENY**.",
            "",
            "<!-- SECTION:PARTIAL_EXPORT_DENY_AND_RETRY -->",
            "## Partial Export DENY & safe retry",
            "",
            "1. If Export cancels (validation missing/fail): delete any temp probe files; publish folder must stay empty.",
            "2. Fix cause (order, validate, preset).",
            "3. Re-run from the failed step or full Select→…→Validate→Export.",
            "4. Never copy partial/temp outputs into release folders.",
            "",
            "<!-- SECTION:ERROR_CODES_OPERATOR_ACTIONS -->",
            "## Error codes → operator action → diagnosis log",
            "",
            "| Code | Operator action | Diagnosis log |",
            "|------|-----------------|---------------|",
        ]
    )
    for row in ERROR_CATALOG:
        lines.append(f"| `{row['code']}` | {row['operatorAction']} | {row['logHint']} |")
    lines.extend(
        [
            "",
            "<!-- SECTION:RC1_WRAPPER_FULL_SHA256 -->",
            "## RC.1 & wrapper identity (full SHA-256)",
            "",
            f"- RC.1 package: `NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip`",
            f"- RC.1 SHA-256: `{rc1}`",
            f"- Wrapper version: `{WRAPPER_VERSION_FROZEN}`",
            f"- Wrapper SHA-256: `{WRAPPER_SHA256_FROZEN}`",
            "",
            "<!-- SECTION:PRODUCTION_NO_GO_CHANNEL -->",
            "## Production status & channel",
            "",
            "- **Production: NO-GO** (panel + policy; auto-advance DENY)",
            "- **Channel: LIMITED_INTERNAL_OPERATOR**",
            "- Sealed verdict remains SEALED_WITH_LIMITATIONS",
            "",
            "## Gate 5 harness accuracy notes (not product fixes)",
            "",
        ]
    )
    for h in GATE5_HARNESS_CORRECTIONS:
        lines.append(f"- `{h['id']}`: {h['summary']} (productMutation={h['productMutation']})")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_ops_artifacts(out_dir: Path) -> Dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    guide = build_ops_guide_markdown()
    guide_path = out_dir / "V06_PR_OPS_OPERATOR_GUIDE.md"
    guide_path.write_text(guide, encoding="utf-8")
    errors_path = out_dir / "V06_PR_ERROR_CATALOG.json"
    import json

    errors_path.write_text(json.dumps({"errors": ERROR_CATALOG}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    harness_path = out_dir / "V06_PR_GATE5_HARNESS_CORRECTIONS.json"
    harness_path.write_text(
        json.dumps({"corrections": GATE5_HARNESS_CORRECTIONS, "productMutation": "DENY"}, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return {
        "guide": str(guide_path).replace("\\", "/"),
        "errorCatalog": str(errors_path).replace("\\", "/"),
        "harnessCorrections": str(harness_path).replace("\\", "/"),
        "guideChars": len(guide),
    }
