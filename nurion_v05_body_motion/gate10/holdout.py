"""Gate 10 Fresh Holdout validation — frozen RC.1, no tuning."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .eligibility import (
    extract_holdout_zip,
    pick_formal_bow_model,
    pre_import_eligibility,
    sha256_file,
)
from .parameters import (
    GATE10_PARAMETERS,
    INHERITED_LIMITATIONS,
    V04_RC1_SHA256,
    V05_RC1_PACKAGE,
    V05_RC1_SHA256,
    parameter_hash,
)


def _sha_json(doc) -> str:
    import json

    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class Gate10Result:
    verdict: str
    report: Dict
    validation: Dict
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def verify_rc_packages(root: Path) -> Dict:
    v05 = root / "dist/v0.5/gate9/package" / V05_RC1_PACKAGE
    v04 = root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
    out = {"ok": True, "checks": {}}
    if not v05.exists():
        out["ok"] = False
        out["checks"]["v05Rc1"] = False
        out["v05Sha"] = ""
    else:
        d = sha256_file(v05)
        out["checks"]["v05Rc1"] = d == V05_RC1_SHA256
        out["v05Sha"] = d
        if d != V05_RC1_SHA256:
            out["ok"] = False
    if not v04.exists():
        out["ok"] = False
        out["checks"]["v04Rc1"] = False
        out["v04Sha"] = ""
    else:
        d = sha256_file(v04)
        out["checks"]["v04Rc1"] = d == V04_RC1_SHA256
        out["v04Sha"] = d
        if d != V04_RC1_SHA256:
            out["ok"] = False
    return out


def verify_frozen_g1_g9(root: Path) -> Dict:
    from nurion_v05_body_motion.gate9.packaging import verify_frozen_hashes
    from nurion_v05_body_motion.gate9.parameters import parameter_hash as g9

    base = verify_frozen_hashes(root)
    g9_ok = g9() == GATE10_PARAMETERS["gate9ParameterHash"]
    checks = dict(base.get("checks") or {})
    checks["gate9"] = g9_ok
    return {"ok": bool(base.get("ok")) and g9_ok, "checks": checks}


def _scene_eligibility_after_import() -> Dict:
    import bpy

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    actions = list(bpy.data.actions)
    notes = []
    gates = {
        "ARMATURE": "PASS" if arms else "FAIL",
        "MESH": "PASS" if meshes else "FAIL",
        "ACTION": "PASS" if actions else "FAIL",
    }
    if not arms:
        notes.append("no armature")
    if not meshes:
        notes.append("no mesh")
    if not actions:
        notes.append("no Formal Bow action")
    return {"ok": all(v == "PASS" for v in gates.values()), "gates": gates, "notes": notes}


def classify_verdict(
    *,
    eligible: bool,
    frozen_ok: bool,
    rc_ok: bool,
    det: str,
    fp: Dict,
    hard_fails: List[str],
) -> str:
    if not eligible:
        return "ASSET_INELIGIBLE"
    if not frozen_ok or not rc_ok or hard_fails or det != "PASS":
        return "ALGORITHM_FAIL"
    # Never auto-upgrade to clean pass while inherited limitations exist
    slides = int(fp.get("slidesFinal") or 0)
    depth = float(fp.get("maxDepthM") or 0)
    extra_lim = slides > 0 or depth > 0
    if extra_lim or INHERITED_LIMITATIONS:
        # Holdout algorithm OK with disclosed limitations
        if slides > 11 or depth > float(GATE10_PARAMETERS["shallowContactDepthMaxM"]) + 1e-9:
            return "PASS_WITH_LIMITATIONS"
        return "PASS_WITH_LIMITATIONS"
    return "HOLDOUT_PASS"


def run_gate10_holdout(
    *,
    zip_path: Path,
    root: Path,
    mesh_name: str = "char1",
    work_dir: Path,
    runs: int = 3,
    clean_import_cb=None,
) -> Gate10Result:
    notes: List[str] = []
    root = Path(root)
    zip_path = Path(zip_path)
    work_dir = Path(work_dir)

    frozen = verify_frozen_g1_g9(root)
    if not frozen["ok"]:
        notes.append(f"frozen G1–9 fail: {frozen['checks']}")
    rc = verify_rc_packages(root)
    if not rc["ok"]:
        notes.append("RC package hash fail — REPACK DENY")

    extract = extract_holdout_zip(zip_path, work_dir)
    model = pick_formal_bow_model(extract)
    eligibility = pre_import_eligibility(zip_path, extract, model)
    notes.extend(eligibility.get("notes") or [])

    if not eligibility["ok"] or model is None:
        validation = {
            "schema": "NURION_V05_GATE10_VALIDATION",
            "verdict": "ASSET_INELIGIBLE",
            "fails": eligibility.get("fails") or ["MODEL_PRESENT"],
            "limitations": list(INHERITED_LIMITATIONS) + ["ASSET_INELIGIBLE"],
            "parameterHash": parameter_hash(),
        }
        report = {
            "schema": "NURION_V05_GATE10_HOLDOUT_REPORT",
            "verdict": "ASSET_INELIGIBLE",
            "eligibility": eligibility,
            "extract": extract,
            "frozenHashes": frozen,
            "rcPackages": rc,
            "notes": notes,
            "inheritedLimitations": INHERITED_LIMITATIONS,
            "v05Rc1Sha256": V05_RC1_SHA256,
            "v05Rc1Repack": "DENY",
            "parameterTuning": 0,
            "manualCorrection": 0,
            "supportedDomain": "LIMITED",
            "production": "NO-GO",
            "sealed": False,
            "next": "SUBMIT_NEW_HOLDOUT_ASSET",
        }
        return Gate10Result(
            verdict="ASSET_INELIGIBLE",
            report=report,
            validation=validation,
            notes=notes,
            parameter_hash=parameter_hash(),
        )

    zip_sha_before = eligibility["zipSha256"]
    model_sha_before = eligibility["modelSha256"]

    results = []
    hard_fails: List[str] = []
    try:
        for i in range(int(runs)):
            if clean_import_cb is None:
                raise RuntimeError("clean_import_cb required")
            clean_import_cb(model)
            scene_el = _scene_eligibility_after_import()
            if not scene_el["ok"]:
                hard_fails.append("SCENE_STRUCTURE")
                notes.extend(scene_el["notes"])
                break
            from nurion_v05_body_motion.gate8.pipeline import run_clean_pipeline_once

            results.append(
                run_clean_pipeline_once(
                    fbx_path=model,
                    mesh_name=mesh_name,
                    root=root,
                    seed_mode=False,
                )
            )
    except Exception as exc:  # noqa: BLE001
        hard_fails.append("PIPELINE_EXCEPTION")
        notes.append(str(exc))

    # Mutation checks
    zip_sha_after = sha256_file(zip_path)
    model_sha_after = sha256_file(model)
    if zip_sha_after != zip_sha_before or model_sha_after != model_sha_before:
        hard_fails.append("SOURCE_MUTATION")
        notes.append("source ZIP/FBX mutated during holdout")
    if sha256_file(root / "dist/v0.5/gate9/package" / V05_RC1_PACKAGE) != V05_RC1_SHA256:
        hard_fails.append("V05_RC1_MUTATION")
        notes.append("v0.5 RC.1 mutated")
    if sha256_file(root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip") != V04_RC1_SHA256:
        hard_fails.append("V04_RC1_MUTATION")
        notes.append("v0.4 RC.1 mutated")

    det = "FAIL"
    hashes = []
    fp = {}
    if results:
        hashes = [r["determinismHash"] for r in results]
        det = "PASS" if len(hashes) >= 3 and all(h == hashes[0] for h in hashes[1:3]) else "FAIL"
        fp = results[-1]["fingerprint"]
        if not fp.get("boneMappingOk"):
            hard_fails.append("BONE_MAPPING")
        if int(fp.get("lrSwapCount") or 0) != 0:
            hard_fails.append("LR_SWAP")
        if fp.get("axisFailChains"):
            hard_fails.append("AXIS_ERROR")
        if not fp.get("fpsMeaningOk"):
            hard_fails.append("FPS_MEANING")
        if not fp.get("faceBindOk"):
            hard_fails.append("FACE_EYE_LIPSYNC")
        if int(fp.get("lipIntersection") or 0) or int(fp.get("lipOrderInversion") or 0):
            hard_fails.append("JAW_LIP_COLLISION")
        if int(fp.get("silenceFalseMotion") or 0):
            hard_fails.append("SILENCE_FALSE_MOUTH")
        if int(fp.get("sourceActionMutation") or 0) or int(fp.get("gate6BodyMutation") or 0):
            hard_fails.append("ACTION_MUTATION")
        if not fp.get("shallowContactOk"):
            hard_fails.append("SHALLOW_CONTACT")
        if det != "PASS":
            hard_fails.append("DETERMINISM_3X")

    verdict = classify_verdict(
        eligible=True,
        frozen_ok=frozen["ok"],
        rc_ok=rc["ok"],
        det=det,
        fp=fp,
        hard_fails=sorted(set(hard_fails)),
    )

    limitations = list(INHERITED_LIMITATIONS)
    limitations.append("LIMITED_DOMAIN")
    limitations.append("V05_RC_NOT_SEALED")
    if fp:
        if int(fp.get("slidesFinal") or 0) > 0:
            limitations.append(f"HOLDOUT_FOOT_SLIDE_{int(fp['slidesFinal'])}")
        if float(fp.get("maxDepthM") or 0) > 0:
            limitations.append("HOLDOUT_SHALLOW_CONTACT_BODYTYPE")
    # Explicit: do not hide seed limitations
    limitations.append("SEED_LIMITATIONS_NOT_AUTO_CLEARED")

    gates = {
        "V05_RC1_REPACK": "DENY",
        "FROZEN_HASHES_G1_G9": "PASS" if frozen["ok"] else "FAIL",
        "V05_RC1_IMMUTABLE": "PASS" if rc["checks"].get("v05Rc1") else "FAIL",
        "V04_RC1_IMMUTABLE": "PASS" if rc["checks"].get("v04Rc1") else "FAIL",
        "ASSET_ELIGIBILITY": "PASS",
        "FORMAL_BOW_CLEAN_IMPORT": "PASS" if results else "FAIL",
        "BONE_MAPPING": "PASS" if fp.get("boneMappingOk") else "FAIL",
        "LR_SWAP_AXIS": "PASS" if fp and int(fp.get("lrSwapCount") or 0) == 0 and not fp.get("axisFailChains") else "FAIL",
        "JOINT_FOOT_PENETRATION_PIPELINE": "PASS" if results and "PIPELINE_EXCEPTION" not in hard_fails else "FAIL",
        "FACE_EYE_WORD_CONFIRM_SYNC": "PASS" if fp.get("faceBindOk") else "FAIL",
        "FPS_24_30_60": "PASS" if fp.get("fpsMeaningOk") else "FAIL",
        "DETERMINISM_3X": det,
        "SOURCE_MUTATION": 0 if "SOURCE_MUTATION" not in hard_fails else 1,
        "PARAMETER_TUNING": 0,
        "MANUAL_CORRECTION": 0,
        "SUPPORTED_DOMAIN": "LIMITED",
        "PRODUCTION": "NO-GO",
        "SEALED": False,
        "FORCE_FULL_PASS": "DENY",
    }

    validation = {
        "schema": "NURION_V05_GATE10_VALIDATION",
        "verdict": verdict,
        "gates": gates,
        "fails": sorted(set(hard_fails)),
        "limitations": sorted(set(limitations)),
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "parameterHash": parameter_hash(),
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
    }

    report = {
        "schema": "NURION_V05_GATE10_HOLDOUT_REPORT",
        "version": GATE10_PARAMETERS["version"],
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "label": "ai-baeby",
        "character": "ai-baeby",
        "meshyName": "Lightning_Pilot",
        "animation": "Formal_Bow",
        "zipName": zip_path.name,
        "zipSha256": zip_sha_after,
        "modelSha256": model_sha_after,
        "modelPath": str(model).replace("\\", "/"),
        "v05Rc1Package": V05_RC1_PACKAGE,
        "v05Rc1Sha256": V05_RC1_SHA256,
        "v05Rc1Repack": "DENY",
        "v04Rc1Sha256": V04_RC1_SHA256,
        "eligibility": eligibility,
        "frozenHashes": frozen,
        "rcPackages": rc,
        "determinism3x": det,
        "determinismHashes": hashes,
        "fingerprint": fp,
        "bodyTypeDependency": {
            "slidesFinal": fp.get("slidesFinal"),
            "maxDepthM": fp.get("maxDepthM"),
            "keysFinalTotal": (fp.get("keysFinal") or {}).get("totalKeys") if fp else None,
            "frameRange": [fp.get("frameStart"), fp.get("frameEnd")] if fp else None,
            "speechWindow": fp.get("speechWindow"),
        },
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "limitations": sorted(set(limitations)),
        "parameterTuning": 0,
        "manualCorrection": 0,
        "siblingZipMix": "DENY",
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "finalSeal": "HOLD",
        "notes": notes,
        "next": "FINAL_SEAL_REVIEW" if verdict in ("HOLDOUT_PASS", "PASS_WITH_LIMITATIONS") else "HOLDOUT_FIX",
    }
    return Gate10Result(
        verdict=verdict,
        report=report,
        validation=validation,
        notes=notes,
        parameter_hash=parameter_hash(),
    )
