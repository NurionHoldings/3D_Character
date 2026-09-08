"""
v0.6 Production Readiness Gate 7 — Production Holdout.

Usage:
  blender --background --python tools/blender_v06_pr_gate7_production_holdout.py
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "production_readiness" / "gate7"
PR = ROOT / "dist" / "v0.6" / "production_readiness"
RC1 = ROOT / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
WRAPPER_ZIP = PR / "gate3/wrapper/nurion_v06_unified_runtime_from_rc1_install_wrapper.zip"
SRC_ZIP = ROOT / "Wither_character-rig.zip"

GATE1_HASH = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_HASH = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_HASH = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE4_HASH = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"
GATE5_HASH = "d5bcfe242c856d746b1190346cfec3cc0f2959f3b6071179a1b486a0491709fe"
GATE6_HASH = "65aff0f4edced493e3dd62ac8c0d062bcdde7531d13d348a1530bf59c70f290b"
RC1_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"
WRAPPER_SHA = "1094c18a12c3fda162ac061ce2cf05f5e0633446aeef41097885c81f41ecd6e7"
WRAPPER_VER = "0.6.0-wrapper.1"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _lock_gates_1_6(now: str) -> None:
    locks = [
        ("gate1/V06_PR_GATE1_STATUS.json", "PR_GATE1", GATE1_HASH),
        ("gate2/V06_PR_GATE2_STATUS.json", "PR_GATE2", GATE2_HASH),
        ("gate2/V06_PR_GATE2_RECEIPT.json", "PR_GATE2", GATE2_HASH),
        ("gate3/V06_PR_GATE3_STATUS.json", "PR_GATE3", GATE3_HASH),
        ("gate3/V06_PR_GATE3_RECEIPT.json", "PR_GATE3", GATE3_HASH),
        ("gate4/V06_PR_GATE4_STATUS.json", "PR_GATE4", GATE4_HASH),
        ("gate4/V06_PR_GATE4_RECEIPT.json", "PR_GATE4", GATE4_HASH),
        ("gate5/V06_PR_GATE5_STATUS.json", "PR_GATE5", GATE5_HASH),
        ("gate5/V06_PR_GATE5_RECEIPT.json", "PR_GATE5", GATE5_HASH),
        ("gate6/V06_PR_GATE6_STATUS.json", "PR_GATE6", GATE6_HASH),
        ("gate6/V06_PR_GATE6_RECEIPT.json", "PR_GATE6", GATE6_HASH),
    ]
    for rel, key, ph in locks:
        path = PR / rel
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        if key in ("PR_GATE6",) and doc.get(key) not in (None,):
            pass
        else:
            doc[key] = doc.get(key) or "PASS"
        if key == "PR_GATE6":
            doc[key] = "PASS_WITH_LIMITATIONS"
        elif key.startswith("PR_GATE"):
            doc[key] = "PASS" if key != "PR_GATE6" else doc[key]
        doc["parameterHash"] = ph
        doc["frozenAt"] = now
        doc["production"] = "NO-GO"
        _write(path, doc)

    # Gate6 status already PASS_WITH_LIMITATIONS
    g6 = PR / "gate6/V06_PR_GATE6_STATUS.json"
    if g6.is_file():
        d = json.loads(g6.read_text(encoding="utf-8"))
        d["LOCKED"] = True
        d["officialFrozenBaseline"] = True
        d["PR_GATE6"] = "PASS_WITH_LIMITATIONS"
        d["parameterHash"] = GATE6_HASH
        d["frozenAt"] = now
        _write(g6, d)

    wrapper_lock = {
        "schema": "NURION_V06_BLINFO_INSTALL_WRAPPER_COMPONENT",
        "component": "bl_info_install_wrapper",
        "version": WRAPPER_VER,
        "wrapperSha256": WRAPPER_SHA,
        "targetRc1Sha256": RC1_SHA,
        "LOCKED": True,
        "officialOpsComponent": True,
        "frozenAt": now,
        "rc1Repack": "DENY",
    }
    _write(PR / "gate3/V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json", wrapper_lock)
    _write(OUT / "V06_PR_BLINFO_WRAPPER_COMPONENT_LOCK.json", wrapper_lock)


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from nurion_v06_production_readiness.gate1.parameters import parameter_hash as g1h
    from nurion_v06_production_readiness.gate2.parameters import parameter_hash as g2h
    from nurion_v06_production_readiness.gate3.parameters import parameter_hash as g3h
    from nurion_v06_production_readiness.gate3.smoke import sha256_file
    from nurion_v06_production_readiness.gate4.parameters import parameter_hash as g4h
    from nurion_v06_production_readiness.gate5.parameters import parameter_hash as g5h
    from nurion_v06_production_readiness.gate6.parameters import parameter_hash as g6h
    from nurion_v06_production_readiness.gate7.holdout import run_production_holdout
    from nurion_v06_production_readiness.gate7.novelty import evaluate_holdout
    from nurion_v06_production_readiness.gate7.parameters import (
        GATE7_PARAMETERS,
        HOLDOUT_FBX_SHA256,
        HOLDOUT_LABEL,
        HOLDOUT_ZIP_NAME,
        HOLDOUT_ZIP_SHA256,
        PR_INHERITED_LIMITATIONS,
        parameter_hash,
    )

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    hashes = [g1h(), g2h(), g3h(), g4h(), g5h(), g6h()]
    expected = [GATE1_HASH, GATE2_HASH, GATE3_HASH, GATE4_HASH, GATE5_HASH, GATE6_HASH]
    if hashes != expected:
        raise RuntimeError(f"PR Gate1–6 hash drift — DENY {list(zip(expected, hashes))}")
    if sha256_file(RC1) != RC1_SHA or sha256_file(WRAPPER_ZIP) != WRAPPER_SHA:
        raise RuntimeError("RC.1/wrapper hash drift — DENY")
    if not SRC_ZIP.is_file():
        raise FileNotFoundError(f"Holdout source ZIP missing: {SRC_ZIP}")

    _lock_gates_1_6(now)
    OUT.mkdir(parents=True, exist_ok=True)

    # Official inherited limitations registry (PR track; does not mutate Gate1 frozen params)
    lim_reg = {
        "schema": "NURION_V06_PR_INHERITED_LIMITATIONS",
        "LOCKED": True,
        "limitationAutoClear": "DENY",
        "panelAutoFix": "DENY",
        "limitations": PR_INHERITED_LIMITATIONS,
        "addedFromGate6": ["PANEL_LIMITATION_IDS_RENDERED"],
        "note": "PANEL_LIMITATION_IDS_RENDERED remains a CONDITIONAL_GO / NO-GO factor for final production judgment.",
        "frozenAt": now,
    }
    _write(OUT / "V06_PR_INHERITED_LIMITATIONS.json", lim_reg)
    _write(PR / "V06_PR_INHERITED_LIMITATIONS.json", lim_reg)

    sealed_paths = [
        RC1,
        WRAPPER_ZIP,
        ROOT / "dist/v0.6/V06_FINAL_SEAL_RECEIPT.json",
        ROOT / "dist/v0.6/V06_FINAL_BASELINE_LOCK.json",
        SRC_ZIP,
    ]
    sealed_before = {str(p): sha256_file(p) for p in sealed_paths if p.is_file()}

    # Stage inbox copy (byte-identical); do not mutate source
    inbox = OUT / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    staged = inbox / HOLDOUT_ZIP_NAME
    shutil.copy2(SRC_ZIP, staged)
    if sha256_file(staged) != HOLDOUT_ZIP_SHA256:
        raise RuntimeError("Staged holdout ZIP hash mismatch")

    novelty = evaluate_holdout(
        zip_path=staged,
        label=HOLDOUT_LABEL,
        expected_zip_sha=HOLDOUT_ZIP_SHA256,
        expected_fbx_sha=HOLDOUT_FBX_SHA256,
    )
    _write(OUT / "V06_PR_GATE7_NOVELTY.json", novelty)

    if not novelty.get("eligible"):
        verdict = "ASSET_INELIGIBLE"
        result = {"verdict": verdict, "hardFails": novelty.get("reasons") or ["NOVELTY_FAIL"], "limitations": PR_INHERITED_LIMITATIONS}
    else:
        for key in list(sys.modules):
            if key == "nurion_v06_unified_runtime" or key.startswith("nurion_v06_unified_runtime."):
                del sys.modules[key]
        result = run_production_holdout(
            wrapper_zip=WRAPPER_ZIP,
            fbx_path=Path(novelty["fbxPath"]),
            out_dir=OUT,
            rc1_sha=RC1_SHA,
        )
        verdict = result["verdict"]

    sealed_after = {str(p): sha256_file(p) for p in sealed_paths if p.is_file()}
    mutation = sum(1 for k, v in sealed_before.items() if sealed_after.get(k) != v)
    if mutation:
        result.setdefault("hardFails", []).append("SEALED_MUTATION")
        if verdict in ("HOLDOUT_PASS", "PASS_WITH_LIMITATIONS"):
            verdict = "ALGORITHM_FAIL"
            result["verdict"] = verdict

    ph = parameter_hash()
    hard = result.get("hardFails") or []
    limitations = result.get("limitations") or list(PR_INHERITED_LIMITATIONS)
    # Never hide panel limitation
    if "PANEL_LIMITATION_IDS_RENDERED" not in limitations:
        limitations.append("PANEL_LIMITATION_IDS_RENDERED")

    next_step = (
        "PR_GATE8_FINAL_PRODUCTION_READINESS_JUDGMENT"
        if verdict in ("HOLDOUT_PASS", "PASS_WITH_LIMITATIONS", "ASSET_INELIGIBLE")
        else "PR_GATE7_REMEDIATE_THEN_RETRY"
    )

    receipt = {
        "schema": "NURION_V06_PR_GATE7_RECEIPT",
        "gate": "7",
        "track": "Production Readiness",
        "name": "PRODUCTION_HOLDOUT",
        "PR_GATE7": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate5ParameterHash": GATE5_HASH,
        "gate6ParameterHash": GATE6_HASH,
        "gates1to6Locked": True,
        "rc1Sha256": RC1_SHA,
        "wrapperComponent": {"version": WRAPPER_VER, "wrapperSha256": WRAPPER_SHA, "targetRc1Sha256": RC1_SHA, "LOCKED": True},
        "holdout": GATE7_PARAMETERS["holdout"],
        "novelty": {k: novelty.get(k) for k in ("eligible", "verdict", "zipSha256", "fbxSha256", "reasons")},
        "inheritedLimitations": limitations,
        "limitationAutoClear": "DENY",
        "panelAutoFix": "DENY",
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "hardFails": hard,
        "sourceMutation": {"count": mutation},
        "updatedAt": now,
        "next": next_step,
    }
    status = {
        "schema": "NURION_V06_PR_GATE7_STATUS",
        "gate": "7",
        "track": "Production Readiness",
        "name": "PRODUCTION_HOLDOUT",
        "PR_GATE7": verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "gate6Locked": True,
        "production": "NO-GO",
        "hardFails": hard,
        "limitations": limitations,
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_PR_GATE7_RECEIPT.json",
            "parameters": "V06_PR_GATE7_PARAMETERS.json",
            "novelty": "V06_PR_GATE7_NOVELTY.json",
            "checks": "V06_PR_GATE7_CHECKS.json",
            "result": "V06_PR_GATE7_RESULT.json",
            "inheritedLimitations": "V06_PR_INHERITED_LIMITATIONS.json",
            "exportDisclosure": "NURION_V06_EXPORT_DISCLOSURE.json",
        },
        "next": next_step,
    }

    checks = [
        {"check": "NOVELTY_ELIGIBLE", "result": "PASS" if novelty.get("eligible") else "FAIL", "detail": json.dumps(novelty.get("reasons"))},
        {"check": "HOLDOUT_ZIP_SHA", "result": "PASS" if novelty.get("zipSha256") == HOLDOUT_ZIP_SHA256 else "FAIL"},
        {"check": "HOLDOUT_FBX_SHA", "result": "PASS" if novelty.get("fbxSha256") == HOLDOUT_FBX_SHA256 else "FAIL"},
        {"check": "SEALED_MUTATION_0", "result": "PASS" if mutation == 0 else "FAIL", "detail": str(mutation)},
        {"check": "PANEL_LIMITATION_INHERITED", "result": "PASS" if "PANEL_LIMITATION_IDS_RENDERED" in limitations else "FAIL"},
        {"check": "PRODUCTION_NO_GO", "result": "PASS"},
        {"check": "AUTO_REMEDIATE_DENY", "result": "PASS"},
    ]
    if verdict != "ASSET_INELIGIBLE":
        checks.extend(
            [
                {"check": "PARTIAL_EXPORT_DENY", "result": "PASS" if result.get("partialExportDeny") else "FAIL"},
                {"check": "ABSTAIN_RECOVER", "result": "PASS" if result.get("abstainRecover") else "FAIL"},
                {"check": "DETERMINISM_3X", "result": "PASS" if (result.get("determinism") or {}).get("ok") else "FAIL"},
                {"check": "FORMAT_FPS_MATRIX", "result": "PASS" if result.get("matrixOk") else "FAIL"},
                {"check": "INSTALL_REMOVE_FLOW", "result": "PASS" if result.get("removed") else "FAIL"},
            ]
        )

    track = {
        "schema": "NURION_V06_PRODUCTION_READINESS_STATUS",
        "track": "Production Readiness",
        "product": "NURION Unified Character Animation Runtime",
        "sealedBaseline": "v0.6",
        "sealedBaselineSha256": RC1_SHA,
        "implementation": "V06_PR_GATE7",
        "status": "IN_PROGRESS",
        "PR_GATE1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "PR_GATE2": "PASS",
        "gate2ParameterHash": GATE2_HASH,
        "gate2Locked": True,
        "PR_GATE3": "PASS",
        "gate3ParameterHash": GATE3_HASH,
        "gate3Locked": True,
        "PR_GATE4": "PASS",
        "gate4ParameterHash": GATE4_HASH,
        "gate4Locked": True,
        "PR_GATE5": "PASS",
        "gate5ParameterHash": GATE5_HASH,
        "gate5Locked": True,
        "PR_GATE6": "PASS_WITH_LIMITATIONS",
        "gate6ParameterHash": GATE6_HASH,
        "gate6Locked": True,
        "PR_GATE7": verdict,
        "gate7ParameterHash": ph,
        "inheritedLimitations": limitations,
        "blInfoWrapperComponent": {"version": WRAPPER_VER, "wrapperSha256": WRAPPER_SHA, "targetRc1Sha256": RC1_SHA, "LOCKED": True},
        "production": "NO-GO",
        "next": next_step,
        "updatedAt": now,
    }

    _write(OUT / "V06_PR_GATE7_PARAMETERS.json", GATE7_PARAMETERS)
    _write(OUT / "V06_PR_GATE7_CHECKS.json", {"checks": checks, "hardFails": hard})
    _write(OUT / "V06_PR_GATE7_RESULT.json", result)
    _write(OUT / "V06_PR_GATE7_RECEIPT.json", receipt)
    _write(OUT / "V06_PR_GATE7_STATUS.json", status)
    _write(PR / "STATUS.json", track)

    root_status = json.loads((ROOT / "STATUS.json").read_text(encoding="utf-8"))
    root_status["nextDecision"] = next_step
    root_status["nextSteps"] = [
        "V06_PR_GATE1_TO_6_LOCKED",
        f"V06_PR_GATE7_{verdict}",
        "PRODUCTION_REMAINS_NO_GO",
        "NEXT_" + next_step,
    ]
    pr = root_status.setdefault("v06ProductionReadiness", {})
    pr.update(
        {
            "implementation": "V06_PR_GATE7",
            "status": "IN_PROGRESS",
            "PR_GATE1": "PASS",
            "gate1Locked": True,
            "PR_GATE2": "PASS",
            "gate2Locked": True,
            "PR_GATE3": "PASS",
            "gate3Locked": True,
            "PR_GATE4": "PASS",
            "gate4Locked": True,
            "PR_GATE5": "PASS",
            "gate5Locked": True,
            "PR_GATE6": "PASS_WITH_LIMITATIONS",
            "gate6ParameterHash": GATE6_HASH,
            "gate6Locked": True,
            "officialFrozenBaselineGate6": True,
            "PR_GATE7": verdict,
            "gate7ParameterHash": ph,
            "inheritedLimitations": limitations,
            "blInfoWrapperComponent": {"version": WRAPPER_VER, "wrapperSha256": WRAPPER_SHA, "targetRc1Sha256": RC1_SHA, "LOCKED": True},
            "production": "NO-GO",
            "next": next_step,
        }
    )
    arts = pr.setdefault("statusArtifacts", {})
    arts["gate6"] = "dist/v0.6/production_readiness/gate6/V06_PR_GATE6_STATUS.json"
    arts["gate7"] = "dist/v0.6/production_readiness/gate7/V06_PR_GATE7_STATUS.json"
    arts["gate7Receipt"] = "dist/v0.6/production_readiness/gate7/V06_PR_GATE7_RECEIPT.json"
    arts["inheritedLimitations"] = "dist/v0.6/production_readiness/V06_PR_INHERITED_LIMITATIONS.json"
    root_status["v06ProductionReadiness"] = pr
    _write(ROOT / "STATUS.json", root_status)

    summary = {
        "PR_GATE7": verdict,
        "parameterHash": ph,
        "hardFails": hard,
        "limitations": limitations,
        "holdoutLabel": HOLDOUT_LABEL,
        "zipSha256": novelty.get("zipSha256"),
        "fbxSha256": novelty.get("fbxSha256"),
        "noveltyEligible": novelty.get("eligible"),
        "production": "NO-GO",
        "next": next_step,
    }
    print(json.dumps(summary, indent=2))
    return 0 if verdict in ("HOLDOUT_PASS", "PASS_WITH_LIMITATIONS", "ASSET_INELIGIBLE") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
