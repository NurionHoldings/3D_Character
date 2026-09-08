"""v0.6 Gate 3 — automatic Meshy→standard role bone mapping (read-only on source)."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as gate1_parameter_hash
from nurion_v06_unified_runtime.gate2.parameters import parameter_hash as gate2_parameter_hash

from .parameters import (
    AXIS_GATE_CHAINS,
    CHAINS,
    EYE_ATTACH_ROLE,
    EYE_BONE_ALIASES,
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETERS,
    LR_ROLE_PAIRS,
    REQUIRED_BODY_ROLES,
    ROLE_ALIASES,
    parameter_hash,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Gate3Result:
    profile: Dict
    validation: Dict
    mapping: Dict
    verdict: str
    runtime_action: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    source_mutation: int = 0
    manual_mapping: int = 0
    asset_specific_tuning: int = 0


def _resolve_role(bone_names: List[str], role: str) -> Optional[str]:
    aliases = ROLE_ALIASES.get(role) or []
    lower_map = {n.lower(): n for n in bone_names}
    for alias in aliases:
        if alias in bone_names:
            return alias
        hit = lower_map.get(alias.lower())
        if hit is not None:
            return hit
    return None


def build_role_mapping(arm) -> Dict:
    names = [b.name for b in arm.data.bones]
    roles: Dict[str, Optional[str]] = {}
    for role in ROLE_ALIASES:
        roles[role] = _resolve_role(names, role)

    eye_bones = []
    lower_map = {n.lower(): n for n in names}
    for alias in EYE_BONE_ALIASES:
        if alias in names:
            eye_bones.append(alias)
        elif alias.lower() in lower_map:
            eye_bones.append(lower_map[alias.lower()])

    mapped_required = [r for r in REQUIRED_BODY_ROLES if roles.get(r)]
    missing_required = [r for r in REQUIRED_BODY_ROLES if not roles.get(r)]
    eye_attach = roles.get(EYE_ATTACH_ROLE)

    return {
        "roles": roles,
        "requiredMappedCount": len(mapped_required),
        "requiredCount": len(REQUIRED_BODY_ROLES),
        "missingRequiredRoles": missing_required,
        "bodyCoreOk": len(missing_required) == 0,
        "eyeBonesNamed": eye_bones,
        "eyeAttachBone": eye_attach,
        "eyeAttachRole": EYE_ATTACH_ROLE,
        "eyeNamedPresent": len(eye_bones) > 0,
        "manualMappingCount": 0,
        "assetSpecificTuningCount": 0,
    }


def _chain_parent_ok(arm, role_map: Dict[str, Optional[str]], chain_roles: List[str]) -> Dict:
    """Allow skipped optional unmapped roles; remaining mapped bones must keep ancestor order."""
    mapped = [(r, role_map[r]) for r in chain_roles if role_map.get(r)]
    missing_optional = [r for r in chain_roles if not role_map.get(r)]
    breaks = []
    for i in range(1, len(mapped)):
        child_role, child_name = mapped[i]
        parent_role, parent_name = mapped[i - 1]
        child = arm.data.bones.get(child_name)
        parent = arm.data.bones.get(parent_name)
        if child is None or parent is None:
            breaks.append({"childRole": child_role, "reason": "BONE_MISSING"})
            continue
        # Walk parents until root; parent_name must be an ancestor
        cur = child.parent
        found = False
        while cur is not None:
            if cur.name == parent_name:
                found = True
                break
            cur = cur.parent
        if not found:
            breaks.append(
                {
                    "childRole": child_role,
                    "child": child_name,
                    "expectedAncestorRole": parent_role,
                    "expectedAncestor": parent_name,
                    "actualParent": child.parent.name if child.parent else None,
                }
            )
    return {
        "roles": chain_roles,
        "mapped": mapped,
        "unmappedOptional": missing_optional,
        "breaks": breaks,
        "ok": len(breaks) == 0 and len(mapped) >= 2,
    }


def _axis_align_score(arm, bone_names: List[str]) -> Dict:
    """Colinearity score along a chain using rest bone directions."""
    from mathutils import Vector

    dirs = []
    for name in bone_names:
        b = arm.data.bones.get(name)
        if b is None or b.length < 1e-8:
            continue
        d = (b.tail_local - b.head_local).normalized()
        dirs.append(d)
    if len(dirs) < 2:
        return {"ok": False, "minDot": 0.0, "reason": "CHAIN_TOO_SHORT"}
    min_dot = 1.0
    for i in range(1, len(dirs)):
        min_dot = min(min_dot, float(dirs[i - 1].dot(dirs[i])))
    return {
        "ok": min_dot >= float(GATE3_PARAMETERS["axisDotMin"]),
        "minDot": round(min_dot, 6),
        "threshold": float(GATE3_PARAMETERS["axisDotMin"]),
    }


def _lr_check(arm, role_map: Dict[str, Optional[str]]) -> Dict:
    """Accept either Left=+X or Left=-X convention via majority vote (v0.5-compatible)."""
    details = []
    for l_role, r_role in LR_ROLE_PAIRS:
        ln = role_map.get(l_role)
        rn = role_map.get(r_role)
        if not ln or not rn:
            details.append({"pair": [l_role, r_role], "status": "SKIP_UNMAPPED"})
            continue
        lb = arm.data.bones.get(ln)
        rb = arm.data.bones.get(rn)
        if lb is None or rb is None:
            details.append({"pair": [l_role, r_role], "status": "MISSING"})
            continue
        lx = float(lb.head_local.x)
        rx = float(rb.head_local.x)
        len_rel = abs(lb.length - rb.length) / max(lb.length, rb.length, 1e-9)
        details.append(
            {
                "pair": [l_role, r_role],
                "bones": [ln, rn],
                "leftX": round(lx, 5),
                "rightX": round(rx, 5),
                "lengthRelDiff": round(len_rel, 5),
                "lengthOk": len_rel <= 0.35,
                "status": "PENDING",
            }
        )

    compared = [d for d in details if d.get("status") == "PENDING"]
    left_xs = [d["leftX"] for d in compared]
    prefer_left_positive = True
    if left_xs:
        prefer_left_positive = sum(1 for x in left_xs if x > 0) >= sum(1 for x in left_xs if x < 0)

    fails = []
    for d in compared:
        side_ok = (d["leftX"] > d["rightX"]) if prefer_left_positive else (d["leftX"] < d["rightX"])
        d["sideOk"] = side_ok
        d["convention"] = "LEFT_POSITIVE_X" if prefer_left_positive else "LEFT_NEGATIVE_X"
        ok = side_ok and bool(d.get("lengthOk"))
        d["status"] = "PASS" if ok else "FAIL"
        if not ok:
            fails.append(d)

    return {
        "pairs": details,
        "failCount": len(fails),
        "ok": len(fails) == 0,
        "convention": "LEFT_POSITIVE_X" if prefer_left_positive else "LEFT_NEGATIVE_X",
    }


def _rest_scale_checks(arm) -> Dict:
    import bpy

    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    zero = [b.name for b in arm.data.bones if b.length < 1e-6]
    scales = []
    non_uniform = []
    for pb in arm.pose.bones:
        sx, sy, sz = float(pb.scale.x), float(pb.scale.y), float(pb.scale.z)
        scales.append({"bone": pb.name, "scale": [sx, sy, sz]})
        if max(abs(sx - 1.0), abs(sy - 1.0), abs(sz - 1.0)) > float(GATE3_PARAMETERS["scaleUniformEps"]):
            # REST pose bone scale should stay ~1; report mild deviations
            if max(abs(sx - 1.0), abs(sy - 1.0), abs(sz - 1.0)) > 0.05:
                non_uniform.append(pb.name)
    # Armature object scale
    ox, oy, oz = [float(v) for v in arm.scale]
    obj_uniform = abs(ox - oy) < 1e-4 and abs(oy - oz) < 1e-4
    return {
        "posePosition": arm.data.pose_position,
        "zeroLengthBones": zero,
        "objectScale": [round(ox, 6), round(oy, 6), round(oz, 6)],
        "objectScaleUniform": obj_uniform,
        "nonUniformPoseBones": non_uniform[:20],
        "restOk": arm.data.pose_position == "REST" and len(zero) == 0,
    }


def _connection_points(role_map: Dict, eye_bones: List[str]) -> Dict:
    body_root = role_map.get("HIPS")
    head = role_map.get("HEAD")
    neck = role_map.get("NECK")
    return {
        "bodyRoot": body_root,
        "head": head,
        "neck": neck,
        "eyeAttach": head,
        "eyeNamedBones": eye_bones,
        "bodyHeadLinkOk": bool(body_root and head and neck),
        "headEyeLinkOk": bool(head),  # named eyes optional; Head is attach
        "namedEyeBonesOk": len(eye_bones) > 0,
        "eyePathNote": "NAMED_EYE_ABSENT_USE_HEAD_ATTACH" if head and not eye_bones else "NAMED_EYE_PRESENT" if eye_bones else "NO_HEAD",
    }


def run_gate3_mapping(
    *,
    fbx_path: Path,
    label: str,
    gate2_classification: str,
    zip_sha256: str = "",
    fbx_sha256: str = "",
    baseline_hash_ok: bool = True,
    runs: int = 3,
    clean_import_cb=None,
) -> Gate3Result:
    import bpy

    notes: List[str] = []
    if gate1_parameter_hash() != GATE1_PARAMETER_HASH_FROZEN:
        return Gate3Result(
            profile={},
            validation={"hardFails": ["GATE1_HASH_DRIFT"]},
            mapping={},
            verdict="FAIL",
            runtime_action="ABSTAIN",
            notes=["Gate1 parameter hash drift"],
            parameter_hash=parameter_hash(),
        )
    if gate2_parameter_hash() != GATE2_PARAMETER_HASH_FROZEN:
        return Gate3Result(
            profile={},
            validation={"hardFails": ["GATE2_HASH_DRIFT"]},
            mapping={},
            verdict="FAIL",
            runtime_action="ABSTAIN",
            notes=["Gate2 parameter hash drift"],
            parameter_hash=parameter_hash(),
        )

    if gate2_classification == "INELIGIBLE":
        return Gate3Result(
            profile={
                "label": label,
                "gate2Classification": gate2_classification,
                "sourceMutation": 0,
            },
            validation={
                "gates": {"GATE2_INELIGIBLE": "ABSTAIN"},
                "hardFails": [],
                "abstainReasons": ["GATE2_INELIGIBLE"],
            },
            mapping={"bodyCoreOk": False, "manualMappingCount": 0, "assetSpecificTuningCount": 0},
            verdict="PASS",
            runtime_action="ABSTAIN",
            notes=["Gate2 INELIGIBLE — mapping ABSTAIN without force apply"],
            parameter_hash=parameter_hash(),
        )

    fingerprints = []
    last = None
    for i in range(max(1, int(runs))):
        if clean_import_cb is not None:
            clean_import_cb()
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=str(fbx_path), automatic_bone_orientation=True, use_anim=True)
            bpy.context.view_layer.update()

        arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
        if not arms:
            last = {
                "run": i + 1,
                "mapping": {"bodyCoreOk": False, "missingRequiredRoles": list(REQUIRED_BODY_ROLES)},
                "connections": {},
                "hierarchy": {},
                "axis": {},
                "lr": {"ok": False},
                "restScale": {"restOk": False},
            }
            fingerprints.append("NO_ARMATURE")
            continue

        arm = arms[0]
        # Snapshot source rest to prove no mutation (compare before/after)
        before = {b.name: (round(b.length, 8), b.parent.name if b.parent else None) for b in arm.data.bones}
        mapping = build_role_mapping(arm)
        role_map = mapping["roles"]

        hierarchy = {name: _chain_parent_ok(arm, role_map, roles) for name, roles in CHAINS.items()}
        axis = {}
        for name in AXIS_GATE_CHAINS:
            bone_names = [role_map[r] for r in CHAINS[name] if role_map.get(r)]
            axis[name] = _axis_align_score(arm, bone_names)
        lr = _lr_check(arm, role_map)
        rest_scale = _rest_scale_checks(arm)
        connections = _connection_points(role_map, mapping["eyeBonesNamed"])

        after = {b.name: (round(b.length, 8), b.parent.name if b.parent else None) for b in arm.data.bones}
        source_mutation = 0 if before == after else 1

        last = {
            "run": i + 1,
            "armature": arm.name,
            "mapping": mapping,
            "hierarchy": hierarchy,
            "axis": axis,
            "lr": lr,
            "restScale": rest_scale,
            "connections": connections,
            "sourceMutation": source_mutation,
        }
        fingerprints.append(
            hashlib.sha256(
                json_fingerprint(mapping, hierarchy, axis, lr, connections).encode("utf-8")
            ).hexdigest()
        )

    assert last is not None
    determinism = "PASS" if len(set(fingerprints)) == 1 else "FAIL"
    if determinism == "FAIL":
        notes.append("mapping fingerprint mismatch across runs")

    mapping = last["mapping"]
    hierarchy_ok = all(v.get("ok") for v in last["hierarchy"].values())
    axis_ok = all(v.get("ok") for v in last["axis"].values())
    lr_ok = bool(last["lr"].get("ok"))
    rest_ok = bool(last["restScale"].get("restOk"))
    conn_ok = bool(last["connections"].get("bodyHeadLinkOk")) and bool(last["connections"].get("headEyeLinkOk"))
    mut = int(last.get("sourceMutation") or 0)

    gates = {
        "GATE1_LOCKED": "PASS",
        "GATE2_LOCKED": "PASS",
        "BASELINE_HASH": "PASS" if baseline_hash_ok else "FAIL",
        "BODY_CORE_ROLES": "PASS" if mapping.get("bodyCoreOk") else "FAIL",
        "HIERARCHY_CHAINS": "PASS" if hierarchy_ok else "FAIL",
        "AXIS_LIMBS": "PASS" if axis_ok else "FAIL",
        "LR_SIDEDNESS": "PASS" if lr_ok else "FAIL",
        "REST_POSE_SCALE": "PASS" if rest_ok else "FAIL",
        "BODY_HEAD_EYE_LINKS": "PASS" if conn_ok else "FAIL",
        "MANUAL_MAPPING": "PASS" if mapping.get("manualMappingCount", 0) == 0 else "FAIL",
        "ASSET_TUNING": "PASS" if mapping.get("assetSpecificTuningCount", 0) == 0 else "FAIL",
        "SOURCE_MUTATION": "PASS" if mut == 0 else "FAIL",
        "DETERMINISM_3X": determinism,
        "NAMED_EYE_BONES": "PASS" if mapping.get("eyeNamedPresent") else "LIMITATION",
    }

    hard = [k for k, v in gates.items() if v == "FAIL"]
    mapping_sufficient = not hard and mapping.get("bodyCoreOk")

    if not baseline_hash_ok:
        runtime_action = "ABSTAIN"
        abstain = ["SEALED_BASELINE_HASH_MISMATCH"]
        verdict = "FAIL"
    elif not mapping_sufficient:
        runtime_action = "ABSTAIN"
        abstain = hard + (mapping.get("missingRequiredRoles") or [])
        # Diagnosis gate can still PASS if ABSTAIN is correct outcome (insufficient map)
        verdict = "PASS" if mut == 0 and determinism == "PASS" and mapping.get("manualMappingCount", 0) == 0 else "FAIL"
        notes.append("mapping insufficient — force apply DENY; ABSTAIN")
    else:
        runtime_action = "APPLY_LIMITED_MAPPING"
        abstain = []
        if gates["NAMED_EYE_BONES"] == "LIMITATION":
            abstain.append("NAMED_EYE_ABSENT_HEAD_ATTACH")
            notes.append("named eye bones absent — Eye attach = Head")
        verdict = "PASS_WITH_LIMITATIONS" if abstain or gate2_classification == "LIMITED" else "PASS"

    profile = {
        "label": label,
        "fbx": str(fbx_path).replace("\\", "/"),
        "zipSha256": zip_sha256,
        "fbxSha256": fbx_sha256 or (sha256_file(Path(fbx_path)) if Path(fbx_path).is_file() else ""),
        "gate2Classification": gate2_classification,
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
        "runs": last,
        "inheritedLimitationsFromV05": list(GATE3_PARAMETERS["inheritedLimitationsFromV05"]),
        "limitationAutoClear": "DENY",
        "sourceMutation": mut,
        "manualMappingCount": 0,
        "assetSpecificTuningCount": 0,
    }

    validation = {
        "gates": gates,
        "hardFails": hard,
        "abstainReasons": abstain,
        "mappingSufficient": mapping_sufficient,
        "determinism": determinism,
        "determinismFingerprints": fingerprints,
        "runtimeAction": runtime_action,
    }

    return Gate3Result(
        profile=profile,
        validation=validation,
        mapping=mapping,
        verdict=verdict,
        runtime_action=runtime_action,
        notes=notes,
        parameter_hash=parameter_hash(),
        source_mutation=mut,
        manual_mapping=0,
        asset_specific_tuning=0,
    )


def json_fingerprint(mapping, hierarchy, axis, lr, connections) -> str:
    import json

    doc = {
        "roles": mapping.get("roles"),
        "missing": mapping.get("missingRequiredRoles"),
        "hier": {k: v.get("ok") for k, v in hierarchy.items()},
        "axis": {k: v.get("minDot") for k, v in axis.items()},
        "lrOk": lr.get("ok"),
        "conn": connections,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))
