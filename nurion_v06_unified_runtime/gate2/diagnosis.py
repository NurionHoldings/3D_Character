"""v0.6 Gate 2 — read-only automatic asset diagnosis (FULL / LIMITED / INELIGIBLE)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from nurion_v06_unified_runtime.gate1.abstain import classify_abstain
from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as gate1_parameter_hash

from .parameters import GATE1_PARAMETER_HASH_FROZEN, GATE2_PARAMETERS, parameter_hash


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _compact(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _bone_name_class(name: str) -> str:
    n = _compact(name)
    rules = [
        ("hips", "hip"),
        ("hip", "hip"),
        ("pelvis", "hip"),
        ("spine", "spine"),
        ("chest", "spine"),
        ("neck", "neck"),
        ("head", "neck"),
        ("clavicle", "shoulder"),
        ("shoulder", "shoulder"),
        ("upperarm", "shoulder"),
        ("forearm", "elbow"),
        ("lowerarm", "elbow"),
        ("elbow", "elbow"),
        ("hand", "wrist"),
        ("wrist", "wrist"),
        ("thigh", "hip"),
        ("upleg", "hip"),
        ("calf", "knee"),
        ("lowerleg", "knee"),
        ("knee", "knee"),
        ("foot", "ankle"),
        ("ankle", "ankle"),
        ("toe", "ankle"),
        ("arm", "shoulder"),
        ("leg", "knee"),
    ]
    for key, cls in rules:
        if key in n:
            if key == "arm" and ("fore" in n or "lower" in n):
                return "elbow"
            if key == "leg" and ("up" in n or "thigh" in n):
                return "hip"
            return cls
    return "other"


def _hint_hit(name: str, hints: Sequence[str]) -> bool:
    c = _compact(name)
    return any(h.replace("_", "") in c for h in hints)


def _detect_motion_presets(action_names: Sequence[str], fbx_name: str) -> Dict:
    hints = GATE2_PARAMETERS["motionPresetHints"]
    found = []
    blob_names = list(action_names) + [fbx_name]
    for name in blob_names:
        c = _compact(name)
        if any(h.replace("_", "") in c for h in hints if "formal" in h or "bow" in h):
            if "Formal_Bow" not in found and ("formal" in c or ("bow" in c and "gentleman" not in c)):
                if "formal" in c or "formalbow" in c:
                    found.append("Formal_Bow")
        if "idle" in c and "Idle" not in found:
            found.append("Idle")
        if "gentleman" in c and "Gentlemans_Bow" not in found:
            found.append("Gentlemans_Bow")
    # FBX filename Formal_Bow fallback
    fc = _compact(fbx_name)
    if "formalbow" in fc or ("formal" in fc and "bow" in fc):
        if "Formal_Bow" not in found:
            found.append("Formal_Bow")
    if "idle" in fc and "Idle" not in found:
        found.append("Idle")
    if "gentleman" in fc and "Gentlemans_Bow" not in found:
        found.append("Gentlemans_Bow")
    return {
        "detectedPresets": found,
        "hasMotionPreset": len(found) > 0,
        "actionNames": list(action_names),
    }


def _lr_balance(bone_names: Sequence[str]) -> Dict:
    left = [n for n in bone_names if re.search(r"(^|[_.\s])l($|[_.\s])|left", n.lower())]
    right = [n for n in bone_names if re.search(r"(^|[_.\s])r($|[_.\s])|right", n.lower())]
    return {
        "leftCount": len(left),
        "rightCount": len(right),
        "balancedHint": abs(len(left) - len(right)) <= max(2, int(0.25 * max(len(left), len(right), 1))),
    }


@dataclass
class Gate2Result:
    profile: Dict
    classification: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    source_mutation: int = 0


def _inventory() -> Dict:
    import bpy

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    skinned = []
    for m in meshes:
        for mod in m.modifiers:
            if mod.type == "ARMATURE" and getattr(mod, "object", None) is not None:
                skinned.append(m.name)
                break
        if m.parent and m.parent.type == "ARMATURE" and m.vertex_groups:
            if m.name not in skinned:
                skinned.append(m.name)
    actions = [a.name for a in bpy.data.actions]
    return {
        "armatureCount": len(arms),
        "meshCount": len(meshes),
        "skinnedMeshes": skinned,
        "actions": actions,
        "armatureNames": [a.name for a in arms],
        "meshNames": [m.name for m in meshes],
    }


def _analyze_armature(arm) -> Dict:
    bones = list(arm.data.bones)
    classes: Dict[str, List[str]] = {}
    for b in bones:
        classes.setdefault(_bone_name_class(b.name), []).append(b.name)
    zero_len = [b.name for b in bones if b.length < 1e-6]
    required = GATE2_PARAMETERS["coreBoneClassesRequired"]
    core_ok = all(len(classes.get(c) or []) > 0 for c in required)
    # bilateral arms/legs soft check
    shoulders = classes.get("shoulder") or []
    knees = classes.get("knee") or []
    lr = _lr_balance([b.name for b in bones])
    face_bones = [b.name for b in bones if _hint_hit(b.name, GATE2_PARAMETERS["faceBoneHints"])]
    eye_bones = [b.name for b in bones if _hint_hit(b.name, GATE2_PARAMETERS["eyeBoneHints"])]
    head_bones = [b.name for b in bones if "head" in _compact(b.name) or _bone_name_class(b.name) == "neck"]
    return {
        "name": arm.name,
        "boneCount": len(bones),
        "classCounts": {k: len(v) for k, v in sorted(classes.items())},
        "zeroLengthBones": zero_len,
        "coreBonesOk": core_ok,
        "requiredClasses": required,
        "lr": lr,
        "faceBones": face_bones[:40],
        "eyeBones": eye_bones[:40],
        "headBones": head_bones[:20],
        "hasFaceBones": len(face_bones) > 0,
        "hasEyeBones": len(eye_bones) > 0,
        "hasHeadOrNeck": len(head_bones) > 0,
        "autoMappableHint": core_ok and lr.get("balancedHint", False) and len(zero_len) == 0,
    }


def _analyze_meshes(mesh_names: Sequence[str]) -> Dict:
    import bpy

    face_meshes = []
    eye_meshes = []
    for name in mesh_names:
        if _hint_hit(name, GATE2_PARAMETERS["eyeMeshHints"]):
            eye_meshes.append(name)
        if _hint_hit(name, ["face", "head", "mouth", "teeth"] + GATE2_PARAMETERS["faceBoneHints"]):
            face_meshes.append(name)
    # topology light stats
    stats = []
    for name in list(mesh_names)[:8]:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH" or obj.data is None:
            continue
        me = obj.data
        stats.append(
            {
                "name": name,
                "verts": len(me.vertices),
                "polys": len(me.polygons),
            }
        )
    return {
        "faceMeshes": face_meshes,
        "eyeMeshes": eye_meshes,
        "hasFaceMeshHint": len(face_meshes) > 0,
        "hasEyeMeshHint": len(eye_meshes) > 0,
        "meshStats": stats,
    }


def run_gate2_diagnosis(
    *,
    fbx_path: Path,
    label: str,
    zip_sha256: str = "",
    fbx_sha256: str = "",
    sibling_zip_mix: bool = False,
    baseline_hash_ok: bool = True,
    runs: int = 3,
    clean_import_cb=None,
) -> Gate2Result:
    """Diagnose one imported character. Source FBX must not be written."""
    import bpy

    notes: List[str] = []
    if gate1_parameter_hash() != GATE1_PARAMETER_HASH_FROZEN:
        notes.append("Gate1 parameter hash drift — DENY")
        return Gate2Result(
            profile={},
            classification={
                "classification": "INELIGIBLE",
                "runtimeAction": "ABSTAIN",
                "triggeredRules": ["SEALED_BASELINE_HASH_MISMATCH"],
                "reasons": ["GATE1_PARAMETER_HASH_MISMATCH"],
            },
            verdict="FAIL",
            notes=notes,
            parameter_hash=parameter_hash(),
        )

    fingerprints = []
    last_profile = None
    for i in range(max(1, int(runs))):
        if clean_import_cb is not None:
            clean_import_cb()
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(
                filepath=str(fbx_path),
                automatic_bone_orientation=True,
                use_anim=True,
            )
            bpy.context.view_layer.update()

        inv = _inventory()
        arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
        arm_info = _analyze_armature(arms[0]) if arms else {
            "name": None,
            "boneCount": 0,
            "classCounts": {},
            "zeroLengthBones": [],
            "coreBonesOk": False,
            "requiredClasses": GATE2_PARAMETERS["coreBoneClassesRequired"],
            "lr": {"leftCount": 0, "rightCount": 0, "balancedHint": False},
            "faceBones": [],
            "eyeBones": [],
            "hasFaceBones": False,
            "hasEyeBones": False,
            "autoMappableHint": False,
        }
        mesh_info = _analyze_meshes(inv.get("meshNames") or [])
        motion = _detect_motion_presets(inv.get("actions") or [], Path(fbx_path).name)

        has_armature = int(inv.get("armatureCount") or 0) > 0
        has_skinned = len(inv.get("skinnedMeshes") or []) > 0
        # Meshy bipeds often ship a single skinned mesh without named face/eye bones.
        # Gate1 allows EYE_EVIDENCE_OR_V03_COMPAT and FACE_RIG_OR_MESH_PATH.
        v03_compat = bool(arm_info.get("hasHeadOrNeck") and has_skinned)
        face_path_ok = bool(
            arm_info.get("hasFaceBones")
            or mesh_info.get("hasFaceMeshHint")
            or v03_compat
        )
        eye_path_ok = bool(
            arm_info.get("hasEyeBones")
            or mesh_info.get("hasEyeMeshHint")
            or v03_compat
        )
        # lipsync still requires mouth/jaw style evidence — do not invent from head alone
        lipsync_ok = bool(
            any(_hint_hit(n, ["jaw", "mouth", "lip", "viseme"]) for n in (arm_info.get("faceBones") or []))
            or any(_hint_hit(n, ["mouth", "lip", "teeth"]) for n in (mesh_info.get("faceMeshes") or []))
        )
        zero_crit = len(arm_info.get("zeroLengthBones") or []) > 0 and not arm_info.get("coreBonesOk")
        # zero-length on non-critical may still allow LIMITED; critical if core missing OR many zeros
        if len(arm_info.get("zeroLengthBones") or []) >= 3:
            zero_crit = True

        classification = classify_abstain(
            has_armature=has_armature,
            has_skinned_mesh=has_skinned,
            core_bones_ok=bool(arm_info.get("coreBonesOk")),
            zero_length_critical=bool(zero_crit),
            sibling_zip_mix=bool(sibling_zip_mix),
            baseline_hash_ok=bool(baseline_hash_ok),
            has_motion_preset=bool(motion.get("hasMotionPreset")),
            face_path_ok=face_path_ok,
            eye_path_ok=eye_path_ok,
            lipsync_ok=lipsync_ok,
            auto_mappable=bool(arm_info.get("autoMappableHint")),
            manual_mapping_required=False if arm_info.get("autoMappableHint") else not bool(arm_info.get("coreBonesOk")),
        )

        reasons = list(classification.get("triggeredRules") or [])
        path_status = {
            "body": "OK" if has_armature and has_skinned and arm_info.get("coreBonesOk") else "ABSTAIN",
            "face": "OK" if face_path_ok else "ABSTAIN",
            "eye": "OK" if eye_path_ok else "ABSTAIN",
            "lipsync": "OK" if lipsync_ok else "ABSTAIN",
            "motionPreset": "OK" if motion.get("hasMotionPreset") else "ABSTAIN",
        }

        profile = {
            "label": label,
            "run": i + 1,
            "fbx": str(fbx_path).replace("\\", "/"),
            "zipSha256": zip_sha256,
            "fbxSha256": fbx_sha256 or (sha256_file(Path(fbx_path)) if Path(fbx_path).is_file() else ""),
            "inventory": inv,
            "armature": arm_info,
            "meshes": mesh_info,
            "motion": motion,
            "v03CompatCandidate": v03_compat,
            "pathStatus": path_status,
            "classification": classification["classification"],
            "runtimeAction": classification["runtimeAction"],
            "abstainReasons": reasons,
            "inheritedLimitationsFromV05": list(GATE2_PARAMETERS["inheritedLimitationsFromV05"]),
            "limitationAutoClear": "DENY",
            "sourceMutation": 0,
            "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        }
        last_profile = profile
        fingerprints.append(
            hashlib.sha256(
                (
                    f"{profile['classification']}|{sorted(reasons)}|{sorted(motion.get('detectedPresets') or [])}|"
                    f"{arm_info.get('boneCount')}|{len(inv.get('skinnedMeshes') or [])}"
                ).encode("utf-8")
            ).hexdigest()
        )

    determinism = "PASS" if len(set(fingerprints)) == 1 else "FAIL"
    if determinism == "FAIL":
        notes.append("diagnosis fingerprint mismatch across runs")

    assert last_profile is not None
    cls = last_profile["classification"]
    # Gate verdict for track progress: diagnosis gate passes if classifier ran deterministically
    # and produced a valid label (including INELIGIBLE ABSTAIN outcomes).
    if determinism != "PASS":
        verdict = "FAIL"
    elif cls in ("FULL", "LIMITED", "INELIGIBLE"):
        verdict = "PASS_WITH_LIMITATIONS" if cls != "FULL" else "PASS"
        # INELIGIBLE asset diagnosis is still a successful diagnosis outcome
        if cls == "INELIGIBLE":
            verdict = "PASS"
            notes.append("asset classified INELIGIBLE — unified runtime must ABSTAIN")
        elif cls == "LIMITED":
            notes.append("asset classified LIMITED — disclose path abstains and v0.5 limitations")
    else:
        verdict = "FAIL"

    result_class = {
        "classification": cls,
        "runtimeAction": last_profile["runtimeAction"],
        "triggeredRules": last_profile["abstainReasons"],
        "pathStatus": last_profile["pathStatus"],
        "abstainReasons": last_profile["abstainReasons"],
        "inheritedLimitationsFromV05": last_profile["inheritedLimitationsFromV05"],
        "determinism": determinism,
        "determinismFingerprints": fingerprints,
    }

    return Gate2Result(
        profile=last_profile,
        classification=result_class,
        verdict=verdict,
        notes=notes,
        parameter_hash=parameter_hash(),
        source_mutation=0,
    )


def pick_primary_fbx(extract_dir: Path) -> Optional[Path]:
    paths = sorted(list(extract_dir.rglob("*.fbx")) + list(extract_dir.rglob("*.FBX")))
    if not paths:
        return None

    def score(p: Path) -> Tuple[int, str]:
        n = p.name.lower()
        s = 0
        if "withskin" in n or "with_skin" in n:
            s += 80
        if "formal" in n and "bow" in n:
            s += 60
        if "idle" in n:
            s += 40
        if "gentleman" in n:
            s += 40
        if "biped" in n:
            s += 10
        return (-s, str(p).lower())

    return sorted(paths, key=score)[0]
