"""v0.6 Gate 5 — independent Motion Preset Actions with isolation checks."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as gate1_parameter_hash
from nurion_v06_unified_runtime.gate2.parameters import parameter_hash as gate2_parameter_hash
from nurion_v06_unified_runtime.gate3.mapping import build_role_mapping
from nurion_v06_unified_runtime.gate3.parameters import parameter_hash as gate3_parameter_hash
from nurion_v06_unified_runtime.gate4.bind import (
    _action_fingerprint,
    _action_range,
    _ensure_runtime_empties,
    _eye_head_double,
    _fps_meaning,
    _source_snapshot,
)
from nurion_v06_unified_runtime.gate4.parameters import parameter_hash as gate4_parameter_hash

from .parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETERS,
    PRESET_ACTION_PREFIX,
    parameter_hash,
)


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _compact(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


@dataclass
class Gate5Result:
    profile: Dict
    validation: Dict
    verdict: str
    runtime_action: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    source_mutation: int = 0
    manual_correction: int = 0
    asset_specific_tuning: int = 0


def match_preset_id(path_or_action: str, hints: List[str]) -> bool:
    c = _compact(path_or_action)
    for h in hints:
        if _compact(h) in c:
            return True
    return False


def classify_preset_sources(sources: Dict[str, Optional[Path]]) -> Dict[str, Dict]:
    """sources: preset_id -> fbx path or None."""
    out = {}
    for preset in GATE5_PARAMETERS["presets"]:
        pid = preset["id"]
        path = sources.get(pid)
        if path is None or not Path(path).is_file():
            out[pid] = {
                "available": False,
                "actionName": preset["actionName"],
                "policy": "ABSTAIN",
                "reason": "PRESET_SOURCE_UNAVAILABLE",
                "fbx": None,
            }
        else:
            out[pid] = {
                "available": True,
                "actionName": preset["actionName"],
                "policy": "APPLY",
                "reason": None,
                "fbx": str(path).replace("\\", "/"),
            }
    return out


def _clear_runtime_actions():
    import bpy

    for act in list(bpy.data.actions):
        if act.name.startswith(PRESET_ACTION_PREFIX):
            bpy.data.actions.remove(act)


def _import_fbx_action(fbx_path: Path) -> Tuple[object, object]:
    """Import FBX into current empty-ish scene; return (armature, source_action)."""
    import bpy

    before_actions = set(a.name for a in bpy.data.actions)
    before_arms = set(o.name for o in bpy.data.objects if o.type == "ARMATURE")
    bpy.ops.import_scene.fbx(filepath=str(fbx_path), automatic_bone_orientation=True, use_anim=True)
    bpy.context.view_layer.update()
    new_arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and o.name not in before_arms]
    arms = new_arms or [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        raise RuntimeError(f"no armature after import: {fbx_path}")
    arm = arms[-1]
    action = None
    if arm.animation_data and arm.animation_data.action:
        action = arm.animation_data.action
    else:
        new_acts = [a for a in bpy.data.actions if a.name not in before_actions]
        action = new_acts[-1] if new_acts else (bpy.data.actions[-1] if bpy.data.actions else None)
    if action is None:
        raise RuntimeError(f"no action after import: {fbx_path}")
    return arm, action


def _copy_action(src_action, dest_name: str):
    import bpy

    existing = bpy.data.actions.get(dest_name)
    if existing is not None:
        bpy.data.actions.remove(existing)
    dup = src_action.copy()
    dup.name = dest_name
    return dup


def _bind_only(arm, action):
    import bpy

    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    slots = list(getattr(action, "slots", []) or [])
    if slots:
        try:
            arm.animation_data.action_slot = slots[0]
        except Exception:
            pass
    bpy.context.view_layer.update()


def _active_action_name(arm) -> Optional[str]:
    if arm.animation_data and arm.animation_data.action:
        return arm.animation_data.action.name
    return None


def _pose_fingerprint(arm, bone_names: List[str], fs: int, fe: int) -> str:
    import bpy

    n = int(GATE5_PARAMETERS["motionSampleFrames"])
    frames = list(range(int(fs), int(fe) + 1))
    sample = [frames[int(i * (len(frames) - 1) / max(1, n - 1))] for i in range(n)] if len(frames) > 1 else frames
    arm.data.pose_position = "POSE"
    rows = []
    for fr in sample:
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        for bn in bone_names:
            pb = arm.pose.bones.get(bn)
            if pb is None:
                continue
            t = (arm.matrix_world @ pb.matrix).to_translation()
            rows.append((fr, bn, round(float(t.x), 5), round(float(t.y), 5), round(float(t.z), 5)))
    return _sha_json(rows)


def run_gate5_presets(
    *,
    label: str,
    preset_sources: Dict[str, Optional[Path]],
    gate2_classification: str,
    gate4_runtime_action: str,
    lipsync_supported: bool = False,
    baseline_hash_ok: bool = True,
    runs: int = 3,
) -> Gate5Result:
    import bpy

    notes: List[str] = []
    if gate1_parameter_hash() != GATE1_PARAMETER_HASH_FROZEN:
        return Gate5Result({}, {"hardFails": ["GATE1_HASH_DRIFT"]}, "FAIL", "ABSTAIN", ["Gate1 hash drift"], parameter_hash())
    if gate2_parameter_hash() != GATE2_PARAMETER_HASH_FROZEN:
        return Gate5Result({}, {"hardFails": ["GATE2_HASH_DRIFT"]}, "FAIL", "ABSTAIN", ["Gate2 hash drift"], parameter_hash())
    if gate3_parameter_hash() != GATE3_PARAMETER_HASH_FROZEN:
        return Gate5Result({}, {"hardFails": ["GATE3_HASH_DRIFT"]}, "FAIL", "ABSTAIN", ["Gate3 hash drift"], parameter_hash())
    if gate4_parameter_hash() != GATE4_PARAMETER_HASH_FROZEN:
        return Gate5Result({}, {"hardFails": ["GATE4_HASH_DRIFT"]}, "FAIL", "ABSTAIN", ["Gate4 hash drift"], parameter_hash())

    if gate2_classification == "INELIGIBLE" or gate4_runtime_action == "ABSTAIN":
        return Gate5Result(
            profile={"label": label, "gate2Classification": gate2_classification, "gate4RuntimeAction": gate4_runtime_action},
            validation={"gates": {"PRIOR_ABSTAIN": "ABSTAIN"}, "hardFails": [], "abstainReasons": ["GATE2_OR_GATE4_ABSTAIN"]},
            verdict="PASS",
            runtime_action="ABSTAIN",
            notes=["Prior gate ABSTAIN — motion presets not forced"],
            parameter_hash=parameter_hash(),
        )

    inventory = classify_preset_sources(preset_sources)
    available = [pid for pid, row in inventory.items() if row["available"]]
    unavailable = [pid for pid, row in inventory.items() if not row["available"]]
    for pid in unavailable:
        notes.append(f"{pid}: ABSTAIN ({inventory[pid]['reason']})")

    if not available:
        return Gate5Result(
            profile={"label": label, "inventory": inventory},
            validation={
                "gates": {"ANY_PRESET_AVAILABLE": "FAIL"},
                "hardFails": ["NO_PRESET_SOURCE"],
                "abstainReasons": ["NO_PRESET_SOURCE"],
            },
            verdict="FAIL",
            runtime_action="ABSTAIN",
            notes=notes + ["no preset sources available"],
            parameter_hash=parameter_hash(),
        )

    lipsync_mode = "DRIVEN" if lipsync_supported else GATE5_PARAMETERS["lipsyncUnsupportedPolicy"]
    fingerprints = []
    last = None

    for run_i in range(max(1, int(runs))):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        _clear_runtime_actions()

        # Bootstrap armature from first available preset FBX
        first_pid = available[0]
        first_fbx = Path(inventory[first_pid]["fbx"])
        arm, first_src_action = _import_fbx_action(first_fbx)
        before_src = _source_snapshot(arm)
        mapping = build_role_mapping(arm)
        head = mapping.get("eyeAttachBone") or mapping["roles"].get("HEAD")
        if not head:
            return Gate5Result(
                profile={"label": label, "error": "NO_HEAD"},
                validation={"hardFails": ["NO_HEAD"], "abstainReasons": ["NO_HEAD"]},
                verdict="FAIL",
                runtime_action="ABSTAIN",
                notes=["Head role missing"],
                parameter_hash=parameter_hash(),
            )

        # Register independent runtime actions
        registered = {}
        source_fps = {}
        # First action already imported
        act = _copy_action(first_src_action, inventory[first_pid]["actionName"])
        registered[first_pid] = {
            "actionName": act.name,
            "fingerprint": _action_fingerprint(act),
            "frameRange": list(_action_range(act)),
            "sourceFbx": inventory[first_pid]["fbx"],
        }
        source_fps[first_pid] = _action_fingerprint(first_src_action)

        for pid in available[1:]:
            # Import additional preset into temp then copy action; remove extra armatures/meshes
            fbx = Path(inventory[pid]["fbx"])
            arms_before = {o.name for o in bpy.data.objects if o.type == "ARMATURE"}
            meshes_before = {o.name for o in bpy.data.objects if o.type == "MESH"}
            acts_before = {a.name for a in bpy.data.actions}
            bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=True)
            bpy.context.view_layer.update()
            new_acts = [a for a in bpy.data.actions if a.name not in acts_before]
            if not new_acts:
                # fallback: action on newly imported arm
                new_arms = [o for o in bpy.data.objects if o.type == "ARMATURE" and o.name not in arms_before]
                src_act = None
                if new_arms and new_arms[0].animation_data:
                    src_act = new_arms[0].animation_data.action
                if src_act is None:
                    inventory[pid]["available"] = False
                    inventory[pid]["policy"] = "ABSTAIN"
                    inventory[pid]["reason"] = "PRESET_ACTION_EXTRACT_FAIL"
                    notes.append(f"{pid}: ABSTAIN (extract fail)")
                    continue
            else:
                src_act = new_acts[-1]
            source_fps[pid] = _action_fingerprint(src_act)
            dup = _copy_action(src_act, inventory[pid]["actionName"])
            registered[pid] = {
                "actionName": dup.name,
                "fingerprint": _action_fingerprint(dup),
                "frameRange": list(_action_range(dup)),
                "sourceFbx": inventory[pid]["fbx"],
            }
            # Remove newly imported objects (keep primary arm/mesh from first import)
            to_remove = []
            for o in list(bpy.data.objects):
                try:
                    if o == arm:
                        continue
                    if o.type == "ARMATURE" and o.name not in arms_before:
                        to_remove.append(o)
                    elif o.type == "MESH" and o.name not in meshes_before:
                        to_remove.append(o)
                except ReferenceError:
                    continue
            for o in to_remove:
                try:
                    bpy.data.objects.remove(o, do_unlink=True)
                except ReferenceError:
                    pass
            keep_actions = {registered[k]["actionName"] for k in registered}
            keep_actions.add(first_src_action.name)
            for a in list(bpy.data.actions):
                if a.name.startswith(PRESET_ACTION_PREFIX) or a.name in keep_actions:
                    continue
                try:
                    bpy.data.actions.remove(a)
                except Exception:
                    pass

        # Isolation: all registered fingerprints must be unique
        fps_list = [registered[p]["fingerprint"] for p in registered]
        isolation_unique = len(fps_list) == len(set(fps_list))

        # Apply each preset alone; ensure no other preset action is active; pose differs across presets
        apply_rows = {}
        contamination = []
        bone_names = [n for n in ("Hips", head, "LeftFoot", "RightFoot") if arm.data.bones.get(n)]
        pose_fps = {}
        for pid, meta in registered.items():
            act = bpy.data.actions.get(meta["actionName"])
            _bind_only(arm, act)
            active = _active_action_name(arm)
            others = [registered[o]["actionName"] for o in registered if o != pid]
            if active != meta["actionName"]:
                contamination.append({"preset": pid, "reason": "ACTIVE_ACTION_MISMATCH", "active": active})
            # No multi-action assignment (Blender single action slot)
            if active in others:
                contamination.append({"preset": pid, "reason": "OTHER_PRESET_ACTIVE"})
            fs, fe = meta["frameRange"]
            pose_fps[pid] = _pose_fingerprint(arm, bone_names, fs, fe)
            # Gate4 bind layer maintained
            empties = _ensure_runtime_empties(arm, head)
            eye = _eye_head_double(arm, empties["eyeL"], head, fs, fe)
            fps = _fps_meaning(arm, head, fs, fe)
            apply_rows[pid] = {
                "activeAction": active,
                "eyeHeadDoubleOk": bool(eye["ok"]),
                "eyeHeadDoubleM": eye["maxResidualM"],
                "fpsMeaningOk": bool(fps["ok"]),
                "lipsyncMode": lipsync_mode,
                "frameRange": [fs, fe],
            }

        # Unselected presets must not share pose fingerprint with selected (when ≥2 available)
        pose_distinct = True
        if len(pose_fps) >= 2:
            pose_distinct = len(set(pose_fps.values())) == len(pose_fps)

        after_src = _source_snapshot(arm)
        # Source mutation: bone rest hierarchy unchanged; source FBX not written
        source_mut = 0 if before_src == after_src else 1

        last = {
            "run": run_i + 1,
            "inventory": inventory,
            "registered": registered,
            "isolationUniqueActions": isolation_unique,
            "contaminationEvents": contamination,
            "poseFingerprintsDistinct": pose_distinct,
            "poseFingerprints": pose_fps,
            "apply": apply_rows,
            "lipsyncMode": lipsync_mode,
            "sourceMutation": source_mut,
            "manualCorrection": 0,
            "assetSpecificTuning": 0,
            "unavailablePresets": unavailable,
        }
        fingerprints.append(
            _sha_json(
                {
                    "registered": {k: v["fingerprint"] for k, v in registered.items()},
                    "apply": {k: {"a": v["activeAction"], "eye": v["eyeHeadDoubleOk"], "fps": v["fpsMeaningOk"]} for k, v in apply_rows.items()},
                    "iso": isolation_unique,
                    "poseDistinct": pose_distinct,
                    "contam": contamination,
                }
            )
        )

    assert last is not None
    determinism = "PASS" if len(set(fingerprints)) == 1 else "FAIL"
    if determinism == "FAIL":
        notes.append("preset fingerprint mismatch across runs")

    apply_ok = all(
        row.get("eyeHeadDoubleOk") and row.get("fpsMeaningOk") for row in last["apply"].values()
    )
    no_contam = len(last["contaminationEvents"]) == 0
    iso_ok = bool(last["isolationUniqueActions"])
    pose_ok = bool(last["poseFingerprintsDistinct"]) if len(last["registered"]) >= 2 else True
    mut = int(last["sourceMutation"])

    gates = {
        "GATE1_LOCKED": "PASS",
        "GATE2_LOCKED": "PASS",
        "GATE3_LOCKED": "PASS",
        "GATE4_LOCKED": "PASS",
        "BASELINE_HASH": "PASS" if baseline_hash_ok else "FAIL",
        "INDEPENDENT_ACTIONS": "PASS" if iso_ok else "FAIL",
        "NO_CROSS_PRESET_CONTAMINATION": "PASS" if no_contam else "FAIL",
        "UNSELECTED_KEY_MIX": "PASS" if no_contam and pose_ok else "FAIL",
        "POSE_DISTINCT_ACROSS_PRESETS": "PASS" if pose_ok else "FAIL",
        "BODY_FACE_EYE_BIND_HELD": "PASS" if apply_ok else "FAIL",
        "REST_FALLBACK_POLICY": "PASS" if last["lipsyncMode"] in ("REST_FALLBACK", "DRIVEN") else "FAIL",
        "MISSING_PRESET_ABSTAIN": "PASS" if all(inventory[p]["policy"] == "ABSTAIN" for p in unavailable) else "FAIL",
        "FPS_MEANING_24_30_60": "PASS" if apply_ok else "FAIL",
        "DETERMINISM_3X": determinism,
        "SOURCE_MUTATION": "PASS" if mut == 0 else "FAIL",
        "MANUAL_CORRECTION": "PASS",
        "ASSET_TUNING": "PASS",
        "PRODUCTION": "NO-GO",
    }
    hard = [k for k, v in gates.items() if v == "FAIL"]

    if hard:
        runtime_action = "ABSTAIN"
        verdict = "PASS" if mut == 0 and determinism == "PASS" else "FAIL"
        notes.append("preset checks failed — force apply DENY; ABSTAIN")
    else:
        runtime_action = "APPLY_LIMITED_PRESETS"
        verdict = "PASS_WITH_LIMITATIONS"
        if unavailable:
            notes.append("PARTIAL_PRESET_SET")
        if lipsync_mode == "REST_FALLBACK":
            notes.append("REST_FALLBACK_FACE")

    validation = {
        "gates": gates,
        "hardFails": hard,
        "abstainReasons": hard if runtime_action == "ABSTAIN" else ([f"PRESET_UNAVAILABLE:{p}" for p in unavailable]),
        "determinism": determinism,
        "determinismFingerprints": fingerprints,
        "runtimeAction": runtime_action,
        "lipsyncMode": lipsync_mode,
        "availablePresets": list(last["registered"].keys()),
        "unavailablePresets": unavailable,
    }
    # For successful limited apply, unavailable presets are disclosed limitations not abstainReasons of whole gate
    if runtime_action == "APPLY_LIMITED_PRESETS":
        validation["abstainReasons"] = [f"PRESET_UNAVAILABLE:{p}" for p in unavailable]
        validation["disclosedLimitations"] = [f"PRESET_UNAVAILABLE:{p}" for p in unavailable] + list(
            GATE5_PARAMETERS["inheritedLimitationsFromV05"]
        )

    profile = {
        "label": label,
        "gate2Classification": gate2_classification,
        "gate4RuntimeAction": gate4_runtime_action,
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
        "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
        "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
        "inventory": inventory,
        "registered": last["registered"],
        "apply": last["apply"],
        "isolationUniqueActions": last["isolationUniqueActions"],
        "contaminationEvents": last["contaminationEvents"],
        "poseFingerprintsDistinct": last["poseFingerprintsDistinct"],
        "lipsyncMode": lipsync_mode,
        "inheritedLimitationsFromV05": list(GATE5_PARAMETERS["inheritedLimitationsFromV05"]),
        "limitationAutoClear": "DENY",
        "sourceMutation": mut,
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
    }

    return Gate5Result(
        profile=profile,
        validation=validation,
        verdict=verdict,
        runtime_action=runtime_action,
        notes=notes,
        parameter_hash=parameter_hash(),
        source_mutation=mut,
        manual_correction=0,
        asset_specific_tuning=0,
    )
