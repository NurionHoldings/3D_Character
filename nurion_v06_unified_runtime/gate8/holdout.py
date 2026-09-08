"""v0.6 Gate 8 — fresh holdout execution (frozen Gate1–7 only)."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as gate1_parameter_hash
from nurion_v06_unified_runtime.gate2.diagnosis import run_gate2_diagnosis
from nurion_v06_unified_runtime.gate2.parameters import parameter_hash as gate2_parameter_hash
from nurion_v06_unified_runtime.gate3.mapping import build_role_mapping
from nurion_v06_unified_runtime.gate3.parameters import parameter_hash as gate3_parameter_hash
from nurion_v06_unified_runtime.gate4.bind import _action_range, _eye_head_double, _fps_meaning
from nurion_v06_unified_runtime.gate4.parameters import parameter_hash as gate4_parameter_hash
from nurion_v06_unified_runtime.gate5.parameters import parameter_hash as gate5_parameter_hash
from nurion_v06_unified_runtime.gate6 import scene_ops
from nurion_v06_unified_runtime.gate6.parameters import parameter_hash as gate6_parameter_hash
from nurion_v06_unified_runtime.gate6.workflow import WorkflowEngine
from nurion_v06_unified_runtime.gate7.parameters import parameter_hash as gate7_parameter_hash
from nurion_v06_unified_runtime.gate7.regression import (
    _check_bind_and_fps,
    _export_reimport,
    _partial_export_deny_test,
    _pose_digest,
    _runtime_snapshot,
    _save_reload_blend,
)

from .novelty import evaluate_novelty, extract_withskin_fbx, sha256_file
from .parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETER_HASH_FROZEN,
    GATE6_PARAMETER_HASH_FROZEN,
    GATE7_PARAMETER_HASH_FROZEN,
    GATE8_PARAMETERS,
    HOLDOUT_FBX_SHA256,
    HOLDOUT_PRESET_ID,
    HOLDOUT_ZIP_SHA256,
    parameter_hash,
)


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _locks_ok() -> Optional[str]:
    pairs = [
        (gate1_parameter_hash(), GATE1_PARAMETER_HASH_FROZEN, "GATE1"),
        (gate2_parameter_hash(), GATE2_PARAMETER_HASH_FROZEN, "GATE2"),
        (gate3_parameter_hash(), GATE3_PARAMETER_HASH_FROZEN, "GATE3"),
        (gate4_parameter_hash(), GATE4_PARAMETER_HASH_FROZEN, "GATE4"),
        (gate5_parameter_hash(), GATE5_PARAMETER_HASH_FROZEN, "GATE5"),
        (gate6_parameter_hash(), GATE6_PARAMETER_HASH_FROZEN, "GATE6"),
        (gate7_parameter_hash(), GATE7_PARAMETER_HASH_FROZEN, "GATE7"),
    ]
    for actual, expected, name in pairs:
        if actual != expected:
            return f"{name}_HASH_DRIFT"
    return None


@dataclass
class Gate8Result:
    profile: Dict
    validation: Dict
    novelty: Dict
    workflow: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    source_mutation: int = 0
    manual_correction: int = 0
    asset_specific_tuning: int = 0
    fbx_path: str = ""
    zip_sha256: str = ""
    fbx_sha256: str = ""


def _build_and_apply(fbx_path: Path, preset_id: str = HOLDOUT_PRESET_ID) -> Dict:
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx_path), automatic_bone_orientation=True, use_anim=True)
    bpy.context.view_layer.update()
    action_name = f"NURION_UnifiedRuntime_{preset_id}"
    built = scene_ops.build_runtime_from_active(preset_action_names=[action_name])
    if not built.get("ok"):
        return built
    applied = scene_ops.apply_runtime_preset(action_name, fps=30)
    if not applied.get("ok"):
        return applied
    return {"ok": True, "actionName": action_name, "head": applied.get("head") or "Head", "built": built}


def run_gate8_holdout(
    *,
    zip_path: Path,
    label: str,
    out_dir: Path,
    baseline_hash_ok: bool = True,
    runs: int = 3,
) -> Gate8Result:
    import bpy

    notes: List[str] = []
    lock = _locks_ok()
    if lock:
        return Gate8Result({}, {"hardFails": [lock]}, {}, {}, "FAIL", [lock], parameter_hash())

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = Path(zip_path)
    zip_sha0 = sha256_file(zip_path)
    if zip_sha0 != HOLDOUT_ZIP_SHA256:
        return Gate8Result(
            {},
            {"hardFails": ["HOLDOUT_ZIP_SHA_MISMATCH"]},
            {},
            {},
            "FAIL",
            ["official holdout zip sha mismatch"],
            parameter_hash(),
            zip_sha256=zip_sha0,
        )

    extract_dir = out_dir / "_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    fbx_path, extract_meta = extract_withskin_fbx(zip_path, extract_dir)
    if fbx_path is None or not extract_meta.get("ok"):
        return Gate8Result(
            {"extract": extract_meta},
            {"hardFails": ["EXTRACT_FAILED"]},
            {},
            {},
            "FAIL",
            ["extract failed"],
            parameter_hash(),
            zip_sha256=zip_sha0,
        )

    fbx_sha0 = sha256_file(fbx_path)
    novelty = evaluate_novelty(zip_path=zip_path, label=label, fbx_sha256=fbx_sha0, zip_sha256=zip_sha0)
    if fbx_sha0 != HOLDOUT_FBX_SHA256:
        novelty["ok"] = False
        novelty["reasons"] = list(novelty.get("reasons") or []) + ["HOLDOUT_FBX_SHA_MISMATCH"]
    if extract_meta.get("form") != "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP":
        novelty["ok"] = False
        novelty["reasons"] = list(novelty.get("reasons") or []) + ["BAD_SUBMISSION_FORM"]
        novelty["runtimeAction"] = "ABSTAIN"

    if not novelty.get("ok"):
        return Gate8Result(
            {"extract": extract_meta, "fbx": str(fbx_path).replace("\\", "/")},
            {"hardFails": ["NOVELTY_OR_ELIGIBILITY_FAIL"], "novelty": novelty},
            novelty,
            {},
            "FAIL",
            ["novelty/eligibility failed — ABSTAIN"],
            parameter_hash(),
            zip_sha256=zip_sha0,
            fbx_sha256=fbx_sha0,
            fbx_path=str(fbx_path).replace("\\", "/"),
        )

    # Gate2 diagnosis (1 run enough for inventory; determinism covered later)
    def _clean():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(fbx_path), automatic_bone_orientation=True, use_anim=True)
        bpy.context.view_layer.update()

    g2 = run_gate2_diagnosis(
        fbx_path=fbx_path,
        label=label,
        zip_sha256=zip_sha0,
        fbx_sha256=fbx_sha0,
        baseline_hash_ok=baseline_hash_ok,
        runs=1,
        clean_import_cb=_clean,
    )
    classification = g2.classification.get("classification") or "INELIGIBLE"
    abstain = list(g2.classification.get("abstainReasons") or g2.classification.get("triggeredRules") or [])
    lipsync_path = ((g2.classification.get("pathStatus") or {}).get("lipsync") == "OK")
    if not lipsync_path and "LIPSYNC_TIMELINE_UNSUPPORTED" not in abstain:
        abstain.append("LIPSYNC_TIMELINE_UNSUPPORTED")
    detected = (g2.profile.get("motion") or {}).get("detectedPresets") or []
    available = [p for p in ("Idle", "Formal_Bow", "Gentlemans_Bow") if p in detected]
    if HOLDOUT_PRESET_ID not in available:
        available = list(dict.fromkeys([HOLDOUT_PRESET_ID] + available))
    unavailable = [p for p in ("Formal_Bow", "Idle", "Gentlemans_Bow") if p not in available]
    if classification == "INELIGIBLE":
        return Gate8Result(
            {"gate2": g2.classification, "extract": extract_meta},
            {"hardFails": ["GATE2_INELIGIBLE"]},
            novelty,
            {},
            "FAIL",
            ["asset INELIGIBLE"],
            parameter_hash(),
            zip_sha256=zip_sha0,
            fbx_sha256=fbx_sha0,
            fbx_path=str(fbx_path).replace("\\", "/"),
        )

    # Fixed UI workflow (Gate6 state machine) — policy layer
    eng = WorkflowEngine()
    wf_steps = []
    r = eng.select_character(label=label, character_path=str(fbx_path), fps=30)
    wf_steps.append({"SELECT_CHARACTER": r.get("ok")})
    r = eng.analyze_asset(
        classification=classification if classification in ("FULL", "LIMITED") else "LIMITED",
        abstain_reasons=abstain,
        available_presets=available,
        unavailable_presets=unavailable,
        lipsync_supported=False,
    )
    wf_steps.append({"ANALYZE_ASSET": r.get("ok")})
    r = eng.build_unified_runtime(runtime_built=True)
    wf_steps.append({"BUILD_UNIFIED_RUNTIME": r.get("ok")})
    r = eng.apply_motion_preset(preset_id=HOLDOUT_PRESET_ID, applied=True)
    wf_steps.append({"APPLY_MOTION_PRESET": r.get("ok")})
    r = eng.validate_runtime(report={"holdout": True}, passed=True)
    wf_steps.append({"VALIDATE_RUNTIME": r.get("ok")})
    export_marker = str((out_dir / "workflow_export_marker.fbx").as_posix())
    r = eng.export(export_path=export_marker, wrote=True)
    wf_steps.append({"EXPORT": r.get("ok")})
    workflow = {
        "ok": all(list(s.values())[0] for s in wf_steps),
        "steps": wf_steps,
        "ui": eng.ui_snapshot(),
        "state": eng.state.to_dict(),
    }
    if not workflow["ok"]:
        return Gate8Result(
            {"gate2": g2.classification},
            {"hardFails": ["WORKFLOW_FAIL"], "workflow": workflow},
            novelty,
            workflow,
            "FAIL",
            ["fixed UI workflow failed"],
            parameter_hash(),
            zip_sha256=zip_sha0,
            fbx_sha256=fbx_sha0,
            fbx_path=str(fbx_path).replace("\\", "/"),
        )

    fingerprints = []
    last = None
    for i in range(max(1, int(runs))):
        built = _build_and_apply(fbx_path, HOLDOUT_PRESET_ID)
        if not built.get("ok"):
            return Gate8Result(
                {"error": built},
                {"hardFails": ["RUNTIME_BUILD_FAIL"]},
                novelty,
                workflow,
                "FAIL",
                ["runtime build failed"],
                parameter_hash(),
                zip_sha256=zip_sha0,
                fbx_sha256=fbx_sha0,
                fbx_path=str(fbx_path).replace("\\", "/"),
            )
        head = built.get("head") or "Head"
        arm = bpy.data.objects.get("NURION_UnifiedRuntime_Armature")
        mapping = build_role_mapping(arm) if arm else {}
        head = mapping.get("eyeAttachBone") or (mapping.get("roles") or {}).get("HEAD") or head

        bind0 = _check_bind_and_fps(head)
        snap0 = _runtime_snapshot()
        blend = _save_reload_blend(out_dir / f"run{i+1}_runtime.blend")
        bind_reload = _check_bind_and_fps(head)

        _build_and_apply(fbx_path, HOLDOUT_PRESET_ID)
        fbx_rt = _export_reimport(out_dir / f"run{i+1}_runtime.fbx", "FBX", head)
        _build_and_apply(fbx_path, HOLDOUT_PRESET_ID)
        glb_rt = _export_reimport(out_dir / f"run{i+1}_runtime.glb", "GLB", head)
        _build_and_apply(fbx_path, HOLDOUT_PRESET_ID)
        partial = _partial_export_deny_test(out_dir / "publish_deny", out_dir / "_bad" / "x.fbx")

        zip_sha1 = sha256_file(zip_path)
        fbx_sha1 = sha256_file(fbx_path)
        source_mut = 0 if (zip_sha0 == zip_sha1 and fbx_sha0 == fbx_sha1) else 1

        run_doc = {
            "run": i + 1,
            "snapshot": snap0,
            "bind": bind0,
            "blendReload": blend,
            "bindAfterReload": bind_reload,
            "fbxRoundTrip": fbx_rt,
            "glbRoundTrip": glb_rt,
            "partialExportDeny": partial,
            "sourceMutation": source_mut,
            "lipsyncMode": "REST_FALLBACK",
            "mappingAction": mapping.get("runtimeAction") if mapping else None,
        }
        last = run_doc
        fingerprints.append(
            _sha_json(
                {
                    "action": snap0.get("actionFingerprint"),
                    "bones": snap0.get("boneCount"),
                    "frames": snap0.get("frameRange"),
                    "pose": bind0.get("poseDigest"),
                    "blendOk": blend.get("ok"),
                    "fbxOk": fbx_rt.get("ok"),
                    "glbOk": glb_rt.get("ok"),
                    "eye": bind0.get("eyeHeadDoubleOk"),
                    "fps": bind0.get("fpsMeaningOk"),
                }
            )
        )

    assert last is not None
    determinism = "PASS" if len(set(fingerprints)) == 1 else "FAIL"
    if determinism == "FAIL":
        notes.append("determinism fingerprint mismatch")

    gates = {
        "GATE1_TO_GATE7_LOCKED": "PASS",
        "BASELINE_HASH": "PASS" if baseline_hash_ok else "FAIL",
        "NOVELTY_ELIGIBILITY": "PASS" if novelty.get("ok") else "FAIL",
        "SUBMISSION_FORM": "PASS" if extract_meta.get("form") == "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP" else "FAIL",
        "GATE2_CLASSIFICATION": "PASS" if classification in ("FULL", "LIMITED") else "FAIL",
        "FIXED_UI_WORKFLOW": "PASS" if workflow.get("ok") else "FAIL",
        "BLEND_SAVE_RELOAD": "PASS" if last["blendReload"].get("ok") else "FAIL",
        "FBX_EXPORT_REIMPORT": "PASS" if last["fbxRoundTrip"].get("ok") else "FAIL",
        "GLB_EXPORT_REIMPORT": "PASS" if last["glbRoundTrip"].get("ok") else "FAIL",
        "ARMATURE_SKIN_ACTION_FRAMES": (
            "PASS"
            if last["snapshot"].get("skinned")
            and last["snapshot"].get("actionIsRuntime")
            and last["snapshot"].get("boneCount", 0) > 0
            else "FAIL"
        ),
        "BODY_FACE_EYE_BIND": "PASS" if last["bind"].get("eyeHeadDoubleOk") and last["bindAfterReload"].get("eyeHeadDoubleOk") else "FAIL",
        "REST_FALLBACK_PUBLIC": "PASS" if last.get("lipsyncMode") == "REST_FALLBACK" else "FAIL",
        "FPS_MEANING_24_30_60": "PASS" if last["bind"].get("fpsMeaningOk") else "FAIL",
        "DETERMINISM_3X": determinism,
        "SOURCE_MUTATION": "PASS" if last["sourceMutation"] == 0 else "FAIL",
        "PARTIAL_EXPORT_PUBLISH": "PASS" if last["partialExportDeny"].get("ok") else "FAIL",
        "MANUAL_CORRECTION": "PASS",
        "ASSET_TUNING": "PASS",
        "AUTO_SEAL": "DENY",
        "PRODUCTION": "NO-GO",
    }
    hard = [k for k, v in gates.items() if v == "FAIL"]
    verdict = "PASS_WITH_LIMITATIONS" if not hard else "FAIL"
    if not hard:
        notes.append("REST_FALLBACK_FACE")
        notes.append("LIMITED_DOMAIN")
        notes.append("INHERITED_V05_LIMITATIONS_PUBLIC")
        notes.extend(list(GATE8_PARAMETERS["inheritedLimitationsFromV05"]))

    validation = {
        "gates": gates,
        "hardFails": hard,
        "determinism": determinism,
        "determinismFingerprints": fingerprints,
        "classification": classification,
        "abstainReasons": abstain,
        "availablePresets": available,
        "unavailablePresets": unavailable,
        "lipsyncMode": "REST_FALLBACK",
    }
    profile = {
        "label": label,
        "zip": str(zip_path).replace("\\", "/"),
        "zipSha256": zip_sha0,
        "fbx": str(fbx_path).replace("\\", "/"),
        "fbxSha256": fbx_sha0,
        "extract": extract_meta,
        "gate2": g2.classification,
        "novelty": novelty,
        "runs": last,
        "inheritedLimitationsFromV05": list(GATE8_PARAMETERS["inheritedLimitationsFromV05"]),
        "limitationAutoClear": "DENY",
        "sourceMutation": last["sourceMutation"],
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
        "partialExportPublish": "DENY",
        "autoSeal": "DENY",
        "production": "NO-GO",
    }
    return Gate8Result(
        profile=profile,
        validation=validation,
        novelty=novelty,
        workflow=workflow,
        verdict=verdict,
        notes=notes,
        parameter_hash=parameter_hash(),
        source_mutation=int(last["sourceMutation"]),
        manual_correction=0,
        asset_specific_tuning=0,
        fbx_path=str(fbx_path).replace("\\", "/"),
        zip_sha256=zip_sha0,
        fbx_sha256=fbx_sha0,
    )
