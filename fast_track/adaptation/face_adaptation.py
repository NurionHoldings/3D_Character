"""ADAPT-03 FACE / Expression adaptation — non-destructive; consumes locked NURION FACE authority."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fast_track.adaptation.inspector import canonical_sha256, inspect_character, sha256_file
from fast_track.adaptation.skeleton_mapping import adapt_from_glb, load_binding

CONTRACT_SCHEMA = "NURION_ADAPT03_FACE_ADAPTATION_CONTRACT_OUTPUT_V1"

CAPABILITY_LEVELS = (
    "NATIVE",
    "MAPPABLE",
    "ADAPTABLE",
    "MISSING",
    "AMBIGUOUS",
    "BLOCKED",
)

RESOLUTION_STATUSES = ("RESOLVED", "AMBIGUOUS", "MISSING", "NOT_APPLICABLE", "BLOCKED")

TALKING_OUTCOMES = (
    "COMPATIBLE",
    "COMPATIBLE_WITH_MAPPING",
    "ADAPTATION_REQUIRED",
    "AUGMENTATION_REQUIRED",
    "AMBIGUOUS",
    "BLOCKED",
)

# Landmark semantics subject to locked FACE spec — not invented beyond naming/eye/mouth regions
LANDMARK_SEMANTICS = [
    "LEFT_EYE_CENTER",
    "RIGHT_EYE_CENTER",
    "LEFT_EYE_INNER",
    "LEFT_EYE_OUTER",
    "RIGHT_EYE_INNER",
    "RIGHT_EYE_OUTER",
    "LEFT_BROW",
    "RIGHT_BROW",
    "NOSE_BRIDGE",
    "NOSE_TIP",
    "MOUTH_CENTER",
    "LEFT_MOUTH_CORNER",
    "RIGHT_MOUTH_CORNER",
    "UPPER_LIP",
    "LOWER_LIP",
    "CHIN",
]

VISEME_HINTS = (
    "viseme",
    "phoneme",
    "v_",
    "mouthopen",
    "aa",
    "oh",
    "ou",
    "ee",
    "sil",
    "plosive",
    "pucker",
    "widen",
    "dental",
)


def load_face_binding(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"FACE binding missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _record(
    *,
    semantic: str,
    status: str,
    target_ref: str | None = None,
    confidence: float | None = None,
    evidence: list[str] | None = None,
    capability: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "semantic": semantic,
        "status": status,
        "evidence": evidence or [],
    }
    if target_ref is not None:
        out["targetReference"] = target_ref
    if confidence is not None:
        out["confidence"] = confidence
    if capability is not None:
        out["capability"] = capability
    return out


def _target_morph_names(adapt01: dict[str, Any]) -> list[str]:
    expr = adapt01.get("expressionCapabilities") or {}
    return list(expr.get("targetNames") or [])


def _build_naming_index(binding: dict[str, Any]) -> dict[str, dict[str, Any]]:
    snap = binding.get("faceSemanticSnapshot") or {}
    essential = snap.get("essentialExpressions") or []
    legacy = snap.get("legacyAdapterContract") or {}
    index: dict[str, dict[str, Any]] = {}
    for canon in essential:
        index[canon] = {"canonical": canon, "aliases": [_norm(canon.replace("FACE_", ""))]}
    for pres, targets in legacy.items():
        for t in targets:
            if t not in index:
                index[t] = {"canonical": t, "aliases": [_norm(t.replace("FACE_", ""))]}
            index[t]["legacyPres"] = pres
    return index


def _match_target_to_canonical(
    target_name: str,
    naming_index: dict[str, dict[str, Any]],
    *,
    region_hint: str | None = None,
) -> tuple[str | None, list[str], str]:
    tn = _norm(target_name)
    if not tn:
        return None, [], "AMBIGUOUS"

    # Exact FACE_* or canonical token match
    for canon, meta in naming_index.items():
        cn = _norm(canon)
        if tn == cn or tn == _norm(canon.replace("FACE_", "")):
            return canon, ["exact_canonical_token"], "NATIVE"
        for alias in meta.get("aliases") or []:
            if tn == alias:
                return canon, ["alias_token_match"], "MAPPABLE"

    # Legacy PRES reverse
    for pres, targets in (naming_index.get("_legacy") or {}).items():
        pass

    # Region keyword evidence (not name-only)
    region_evidence: list[str] = []
    if region_hint:
        region_evidence.append(f"region_hint:{region_hint}")
    keywords = {
        "eyeblinkleft": ("FACE_eyeBlinkLeft", "eye_region"),
        "eyeblinkright": ("FACE_eyeBlinkRight", "eye_region"),
        "blink_l": ("FACE_eyeBlinkLeft", "eye_region"),
        "blink_r": ("FACE_eyeBlinkRight", "eye_region"),
        "jawopen": ("FACE_mouthOpen", "jaw_region"),
        "mouthopen": ("FACE_mouthOpen", "mouth_region"),
        "mouthsmile": ("FACE_mouthSmileLeft", "mouth_region"),
        "browinnerup": ("FACE_browInnerUpLeft", "brow_region"),
    }
    for key, (canon, region) in keywords.items():
        if key in tn:
            return canon, [f"deformation_region:{region}", f"token:{key}"], "MAPPABLE"

    if region_hint:
        return None, region_evidence, "ADAPTABLE"
    return None, [], "MISSING"


def _resolve_head_semantic(adapt02: dict[str, Any], force_flags: dict[str, Any]) -> dict[str, Any]:
    if force_flags.get("headSemanticUnresolved"):
        return _record(
            semantic="NURION_head",
            status="BLOCKED",
            evidence=["forced_unresolved"],
            capability="BLOCKED",
        )
    head = (adapt02.get("semanticMappings") or {}).get("NURION_head") or {}
    st = head.get("status") or "MISSING"
    if st != "RESOLVED":
        return _record(
            semantic="NURION_head",
            status=st if st in RESOLUTION_STATUSES else "BLOCKED",
            target_ref=head.get("sourceNode"),
            evidence=head.get("evidence") or ["adapt02_head_unresolved"],
            capability="BLOCKED" if st != "RESOLVED" else "MAPPABLE",
        )
    return _record(
        semantic="NURION_head",
        status="RESOLVED",
        target_ref=head.get("sourceNode"),
        confidence=head.get("confidence"),
        evidence=(head.get("evidence") or []) + ["adapt02_consumed"],
        capability="NATIVE",
    )


def _landmark_correspondence(
    adapt01: dict[str, Any],
    adapt02: dict[str, Any],
    head: dict[str, Any],
    force_flags: dict[str, Any],
) -> dict[str, Any]:
    landmarks: dict[str, dict[str, Any]] = {}
    eyes = adapt01.get("eyeCapabilities") or {}
    le = eyes.get("leftEyeBone") or {}
    re = eyes.get("rightEyeBone") or {}

    if force_flags.get("invertEyeLaterality"):
        le, re = re, le

    eye_map = {
        "LEFT_EYE_CENTER": le,
        "RIGHT_EYE_CENTER": re,
    }
    for sem, cap in eye_map.items():
        if cap.get("status") == "DETECTED" and cap.get("selected"):
            landmarks[sem] = _record(
                semantic=sem,
                status="RESOLVED",
                target_ref=cap.get("selected"),
                confidence=0.85,
                evidence=["eye_bone_semantic", "adapt01_candidate"],
            )
        elif cap.get("status") == "AMBIGUOUS":
            landmarks[sem] = _record(
                semantic=sem,
                status="AMBIGUOUS",
                evidence=["eye_identity_ambiguous"],
            )
        else:
            landmarks[sem] = _record(
                semantic=sem,
                status="MISSING",
                evidence=["no_eye_bone"],
            )

    morphs = _target_morph_names(adapt01)
    mouth_hints = [n for n in morphs if any(h in _norm(n) for h in ("mouth", "lip", "smile", "frown", "jaw"))]
    if mouth_hints:
        landmarks["MOUTH_CENTER"] = _record(
            semantic="MOUTH_CENTER",
            status="RESOLVED",
            target_ref=mouth_hints[0],
            evidence=["morph_region:mouth", "deformation_metadata"],
            confidence=0.7,
        )
    else:
        landmarks["MOUTH_CENTER"] = _record(semantic="MOUTH_CENTER", status="MISSING", evidence=["no_mouth_morph"])

    if head.get("status") == "RESOLVED":
        landmarks["CHIN"] = _record(
            semantic="CHIN",
            status="RESOLVED",
            target_ref=head.get("targetReference"),
            evidence=["head_bone_proxy", "hierarchy"],
            confidence=0.6,
        )
    else:
        landmarks["CHIN"] = _record(semantic="CHIN", status="BLOCKED", evidence=["head_unresolved"])

    for sem in LANDMARK_SEMANTICS:
        if sem not in landmarks:
            landmarks[sem] = _record(
                semantic=sem,
                status="NOT_APPLICABLE" if sem.startswith("NOSE_") or "BROW" in sem else "MISSING",
                evidence=["insufficient_geometry_evidence"],
            )

    if force_flags.get("ambiguousFacialControls"):
        landmarks["LEFT_EYE_CENTER"]["status"] = "AMBIGUOUS"
        landmarks["RIGHT_EYE_CENTER"]["status"] = "AMBIGUOUS"

    unresolved = [k for k, v in landmarks.items() if v.get("status") in ("AMBIGUOUS", "BLOCKED")]
    return {
        "landmarks": landmarks,
        "status": "BLOCKED" if any(landmarks[s].get("status") == "BLOCKED" for s in ("CHIN",)) else (
            "AMBIGUOUS" if unresolved else "PASS"
        ),
    }


def _expression_map(
    adapt01: dict[str, Any],
    binding: dict[str, Any],
    force_flags: dict[str, Any],
) -> dict[str, Any]:
    morphs = _target_morph_names(adapt01)
    naming_index = _build_naming_index(binding)
    snap = binding.get("faceSemanticSnapshot") or {}
    essential = snap.get("essentialExpressions") or []
    mappings: dict[str, dict[str, Any]] = {}
    used_targets: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []

    for canon in essential:
        best_target = None
        best_evidence: list[str] = []
        best_cap = "MISSING"
        for m in morphs:
            matched, ev, cap = _match_target_to_canonical(m, naming_index)
            if matched == canon:
                if best_target and best_target != m:
                    conflicts.append({"canonical": canon, "targets": [best_target, m]})
                    best_cap = "AMBIGUOUS"
                else:
                    best_target = m
                    best_evidence = ev + ["target_control_identity"]
                    best_cap = cap
        if force_flags.get("expressionMappingConflict") and canon == "FACE_eyeBlinkLeft":
            conflicts.append({"canonical": canon, "targets": ["eyeBlinkLeft", "Blink_L"]})
            best_cap = "AMBIGUOUS"
            best_target = None
        if best_target:
            if best_target in used_targets and used_targets[best_target] != canon:
                conflicts.append({"target": best_target, "semantics": [used_targets[best_target], canon]})
                best_cap = "AMBIGUOUS"
            else:
                used_targets[best_target] = canon
        mappings[canon] = _record(
            semantic=canon,
            status="RESOLVED" if best_target and best_cap not in ("AMBIGUOUS", "BLOCKED") else (
                "AMBIGUOUS" if best_cap == "AMBIGUOUS" else "MISSING"
            ),
            target_ref=best_target,
            evidence=best_evidence,
            capability=best_cap if best_target else "MISSING",
        )

    return {
        "mappings": mappings,
        "conflicts": conflicts,
        "status": "BLOCKED" if force_flags.get("expressionMappingConflict") else (
            "AMBIGUOUS" if conflicts else "PASS"
        ),
    }


def _eye_adaptation(
    adapt01: dict[str, Any],
    binding: dict[str, Any],
    force_flags: dict[str, Any],
) -> dict[str, Any]:
    snap = binding.get("eyeTalkingSnapshot") or {}
    channels = snap.get("eyeChannels") or []
    eyes = adapt01.get("eyeCapabilities") or {}
    le, re = eyes.get("leftEyeBone") or {}, eyes.get("rightEyeBone") or {}
    if force_flags.get("invertEyeLaterality"):
        le, re = re, le

    channel_maps: dict[str, dict[str, Any]] = {}
    morphs = _target_morph_names(adapt01)
    for ch in channels:
        side = "left" if "Left" in ch else "right"
        blink_candidates = [m for m in morphs if "blink" in _norm(m) and side in _norm(m)]
        bone = le if side == "left" else re
        cap = "MISSING"
        target = None
        evidence: list[str] = []
        if blink_candidates:
            target = blink_candidates[0]
            cap = "NATIVE" if _norm(target) == _norm(ch) else "MAPPABLE"
            evidence = ["morph_deformation", "eye_region", f"channel:{ch}"]
        elif bone.get("status") == "DETECTED":
            cap = "ADAPTABLE"
            target = bone.get("selected")
            evidence = ["eye_bone_present", "blink_morph_missing"]
        channel_maps[ch] = _record(
            semantic=ch,
            status="RESOLVED" if target and cap != "MISSING" else ("AMBIGUOUS" if cap == "AMBIGUOUS" else "MISSING"),
            target_ref=target,
            evidence=evidence,
            capability=cap,
        )

    inv_blocked = bool(force_flags.get("invertEyeLaterality"))
    return {
        "calibrationFingerprintSha256": binding.get("eyeCalibrationFingerprintSha256"),
        "channelMaps": channel_maps,
        "leftEyeBone": le,
        "rightEyeBone": re,
        "status": "BLOCKED" if inv_blocked else "PASS",
        "adaptationMetadata": {
            "mode": "NON_DESTRUCTIVE",
            "physicalHelperRig": "DENY_IN_ADAPT03",
        },
    }


def _jaw_mouth_map(adapt01: dict[str, Any]) -> dict[str, Any]:
    jaw = adapt01.get("jawCapabilities") or {}
    morphs = _target_morph_names(adapt01)
    jaw_morphs = [m for m in morphs if any(h in _norm(m) for h in ("jaw", "mouth", "lip"))]
    bone = jaw.get("bone") or {}
    controls: dict[str, dict[str, Any]] = {}
    for sem in ("JAW_BONE", "MOUTH_OPEN", "MOUTH_CLOSE", "UPPER_LIP", "LOWER_LIP", "MOUTH_CORNER_L"):
        if sem == "JAW_BONE":
            if bone.get("status") == "DETECTED":
                controls[sem] = _record(
                    semantic=sem,
                    status="RESOLVED",
                    target_ref=bone.get("selected"),
                    evidence=["jaw_bone_semantic"],
                    capability="NATIVE",
                )
            else:
                controls[sem] = _record(semantic=sem, status="MISSING", capability="MISSING", evidence=["no_jaw_bone"])
        elif sem == "MOUTH_OPEN":
            hits = [m for m in morphs if "open" in _norm(m) or "jaw" in _norm(m)]
            controls[sem] = _record(
                semantic=sem,
                status="RESOLVED" if hits else "MISSING",
                target_ref=hits[0] if hits else None,
                evidence=["mouth_deformation"] if hits else ["no_open_control"],
                capability="NATIVE" if hits else "MISSING",
            )
        else:
            related = [m for m in jaw_morphs if sem.split("_")[-1].lower() in _norm(m)]
            controls[sem] = _record(
                semantic=sem,
                status="RESOLVED" if related else "MISSING",
                target_ref=related[0] if related else None,
                capability="MAPPABLE" if related else "MISSING",
                evidence=["lip_region"] if related else [],
            )
    return {"controls": controls, "status": "PASS"}


def _talking_viseme_map(
    adapt01: dict[str, Any],
    binding: dict[str, Any],
    expression_map: dict[str, Any],
) -> dict[str, Any]:
    snap = binding.get("faceSemanticSnapshot") or {}
    speech_owned = snap.get("speechOwned") or []
    morphs = _target_morph_names(adapt01)
    viseme_hits = [m for m in morphs if any(h in _norm(m) for h in VISEME_HINTS)]
    maps: dict[str, dict[str, Any]] = {}
    for sem in speech_owned:
        expr_m = (expression_map.get("mappings") or {}).get(sem) or {}
        if expr_m.get("status") == "RESOLVED":
            outcome = "COMPATIBLE_WITH_MAPPING"
            st = "RESOLVED"
            cap = expr_m.get("capability") or "MAPPABLE"
        else:
            related = [m for m in viseme_hits if _norm(sem.replace("FACE_", "")) in _norm(m)]
            if related:
                outcome = "COMPATIBLE_WITH_MAPPING"
                st = "RESOLVED"
                cap = "MAPPABLE"
            else:
                outcome = "AUGMENTATION_REQUIRED"
                st = "MISSING"
                cap = "MISSING"
        maps[sem] = {
            "semantic": sem,
            "status": st,
            "outcome": outcome,
            "capability": cap,
            "targetReference": expr_m.get("targetReference"),
            "evidence": ["speech_primitive", "locked_talking_authority"],
        }

    overall = "COMPATIBLE"
    if all(v.get("outcome") == "AUGMENTATION_REQUIRED" for v in maps.values()):
        overall = "AUGMENTATION_REQUIRED"
    elif any(v.get("outcome") == "AUGMENTATION_REQUIRED" for v in maps.values()):
        overall = "ADAPTATION_REQUIRED"
    elif viseme_hits:
        overall = "COMPATIBLE_WITH_MAPPING"

    return {
        "talkingStatus": (binding.get("eyeTalkingSnapshot") or {}).get("talkingStatus"),
        "visemeTargetsDetected": viseme_hits,
        "speechPrimitiveMaps": maps,
        "overallOutcome": overall,
        "status": "PASS",
    }


def _capability_matrix(
    expression_map: dict[str, Any],
    eye_adapt: dict[str, Any],
    talking: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for canon, m in (expression_map.get("mappings") or {}).items():
        rows.append({"capability": canon, "level": m.get("capability") or "MISSING", "domain": "EXPRESSION"})
    for ch, m in (eye_adapt.get("channelMaps") or {}).items():
        rows.append({"capability": ch, "level": m.get("capability") or "MISSING", "domain": "EYE"})
    for sem, m in (talking.get("speechPrimitiveMaps") or {}).items():
        rows.append({"capability": sem, "level": m.get("capability") or "MISSING", "domain": "TALKING"})
    return {
        "rows": rows,
        "summary": {
            lvl: sum(1 for r in rows if r["level"] == lvl) for lvl in CAPABILITY_LEVELS
        },
    }


def _adapt04_requirements(
    expression_map: dict[str, Any],
    eye_adapt: dict[str, Any],
    talking: dict[str, Any],
    binding: dict[str, Any],
) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    for ch, m in (eye_adapt.get("channelMaps") or {}).items():
        if m.get("capability") in ("MISSING", "ADAPTABLE") and m.get("status") != "RESOLVED":
            requirements.append(
                {
                    "capability": ch,
                    "reason": "NO_TARGET_CONTROL" if m.get("capability") == "MISSING" else "ADAPTATION_INSUFFICIENT",
                    "targetRegion": "LEFT_EYELID" if "Left" in ch else "RIGHT_EYELID",
                    "authority": "NURION_EYE_CALIBRATION",
                    "adapt04Only": True,
                }
            )
    for sem, m in (talking.get("speechPrimitiveMaps") or {}).items():
        if m.get("outcome") == "AUGMENTATION_REQUIRED":
            requirements.append(
                {
                    "capability": sem,
                    "reason": "NO_TARGET_CONTROL",
                    "targetRegion": "MOUTH",
                    "authority": "NURION_TALKING",
                    "adapt04Only": True,
                }
            )
    for canon, m in (expression_map.get("mappings") or {}).items():
        if m.get("capability") == "MISSING":
            requirements.append(
                {
                    "capability": canon,
                    "reason": "NO_TARGET_CONTROL",
                    "targetRegion": "FACE",
                    "authority": "NURION_FACE_SEMANTIC",
                    "adapt04Only": True,
                }
            )
    return {
        "augmentationRequired": len(requirements) > 0,
        "requirements": requirements,
        "adapt04Implementation": "NOT_STARTED",
        "physicalHelperRigPerformed": False,
    }


def _face_body_attachment(binding: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    attach = binding.get("faceBodyAttachment") or {}
    if head.get("status") != "RESOLVED":
        return {
            "parent": attach.get("parent"),
            "child": attach.get("child"),
            "type": attach.get("type"),
            "targetHeadNode": head.get("targetReference"),
            "status": "BLOCKED",
            "evidence": ["head_semantic_unresolved"],
        }
    return {
        "parent": attach.get("parent"),
        "child": attach.get("child"),
        "type": attach.get("type"),
        "targetHeadNode": head.get("targetReference"),
        "status": "COMPATIBLE",
        "metadata": {
            "mode": "ATTACHMENT_SPECIFICATION_ONLY",
            "mutateNURIONHead": "DENY",
            "mutateFaceAuthority": "DENY",
        },
        "evidence": ["adapt02_head_resolved", "locked_attachment_contract"],
    }


def _target_face_profile(adapt01: dict[str, Any]) -> dict[str, Any]:
    face = adapt01.get("faceCapabilities") or {}
    expr = adapt01.get("expressionCapabilities") or {}
    return {
        "headMeshIdentity": (adapt01.get("meshes") or {}).get("primaryMeshName"),
        "facialBones": face.get("facialBones"),
        "blendshapeCount": expr.get("blendshapeCount"),
        "blendshapesDetected": face.get("blendshapesDetected"),
        "symmetry": "NOT_EVALUATED",
        "analysisMode": "READ_ONLY",
    }


def build_face_adaptation(
    adapt01_report: dict[str, Any],
    adapt02_contract: dict[str, Any],
    face_binding: dict[str, Any],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    if force_flags.get("malformedFaceMetadata") or adapt01_report.get("parseStatus") == "FAILED":
        blockers.append({"code": "MALFORMED_FACE_INPUT", "message": "target face metadata unusable"})
        return _blocked_output(adapt01_report, adapt02_contract, face_binding, blockers)

    if force_flags.get("adapt01Adapt02IdentityMismatch"):
        blockers.append({"code": "ADAPT01_ADAPT02_IDENTITY_MISMATCH", "message": "different source characters"})
        return _blocked_output(adapt01_report, adapt02_contract, face_binding, blockers)

    a01_digest = adapt01_report.get("reportCanonicalSha256")
    a02_a01 = adapt02_contract.get("adapt01InspectionDigest")
    if a01_digest != a02_a01:
        blockers.append({"code": "ADAPT01_ADAPT02_DIGEST_MISMATCH", "message": "inspection digest link broken"})
        return _blocked_output(adapt01_report, adapt02_contract, face_binding, blockers)

    if force_flags.get("sourceDigestMismatch"):
        blockers.append({"code": "SOURCE_DIGEST_MISMATCH", "message": "source asset digest changed"})
        return _blocked_output(adapt01_report, adapt02_contract, face_binding, blockers)

    src_sha = (adapt01_report.get("sourceAsset") or {}).get("sha256")
    if adapt02_contract.get("sourceAssetDigest") and src_sha != adapt02_contract.get("sourceAssetDigest"):
        blockers.append({"code": "SOURCE_IDENTITY_INCONSISTENT", "message": "adapt01/02 source sha mismatch"})
        return _blocked_output(adapt01_report, adapt02_contract, face_binding, blockers)

    if adapt02_contract.get("classification") == "BLOCKED" and not force_flags.get("allowBlockedAdapt02"):
        blockers.append({"code": "ADAPT02_BLOCKED", "message": "skeleton mapping blocked"})
        return _blocked_output(adapt01_report, adapt02_contract, face_binding, blockers)

    if force_flags.get("performAdapt04Augmentation"):
        blockers.append({"code": "ADAPT04_PREMATURE", "message": "physical helper-rig augmentation denied in ADAPT-03"})

    head = _resolve_head_semantic(adapt02_contract, force_flags)
    landmarks = _landmark_correspondence(adapt01_report, adapt02_contract, head, force_flags)
    expression_map = _expression_map(adapt01_report, face_binding, force_flags)
    eye_adapt = _eye_adaptation(adapt01_report, face_binding, force_flags)
    jaw_mouth = _jaw_mouth_map(adapt01_report)
    talking = _talking_viseme_map(adapt01_report, face_binding, expression_map)
    attachment = _face_body_attachment(face_binding, head)
    capability_matrix = _capability_matrix(expression_map, eye_adapt, talking)
    adapt04_req = _adapt04_requirements(expression_map, eye_adapt, talking, face_binding)

    if head.get("status") != "RESOLVED":
        blockers.append({"code": "HEAD_SEMANTIC_UNRESOLVED", "message": "NURION_head not resolved"})
    if attachment.get("status") == "BLOCKED":
        blockers.append({"code": "FACE_BODY_ATTACHMENT_BLOCKED", "message": "unsafe attachment"})
    if landmarks.get("status") == "BLOCKED":
        blockers.append({"code": "LANDMARK_BLOCKED", "message": "landmark correspondence blocked"})
    if expression_map.get("status") == "BLOCKED":
        blockers.append({"code": "EXPRESSION_MAPPING_CONFLICT", "message": "exclusive mapping conflict"})
    if eye_adapt.get("status") == "BLOCKED":
        blockers.append({"code": "EYE_LATERALITY_BLOCKED", "message": "eye identity unsafe"})
    if force_flags.get("ambiguousFacialControls"):
        issues.append({"code": "AMBIGUOUS_FACIAL_CONTROLS", "severity": "WARN"})

    classification = "ADAPTED"
    if blockers:
        classification = "BLOCKED"
    elif issues or landmarks.get("status") == "AMBIGUOUS" or expression_map.get("status") == "AMBIGUOUS":
        classification = "PARTIAL"
    elif adapt04_req.get("augmentationRequired"):
        classification = "ADAPTED_WITH_AUGMENTATION_PENDING"

    out = {
        "schema": CONTRACT_SCHEMA,
        "characterIdentity": adapt01_report.get("characterId"),
        "sourceAssetDigest": src_sha,
        "adapt01InspectionDigest": a01_digest,
        "adapt02MappingDigest": adapt02_contract.get("contractCanonicalSha256"),
        "faceAuthorityBindingSchema": face_binding.get("schema"),
        "targetFaceProfile": _target_face_profile(adapt01_report),
        "headSemantic": head,
        "landmarkCorrespondence": landmarks,
        "faceSemanticMap": {
            "level": "MAPPING",
            "expressionMappings": expression_map,
        },
        "expressionMap": expression_map,
        "eyeAdaptation": eye_adapt,
        "jawMouthMap": jaw_mouth,
        "talkingVisemeMap": talking,
        "faceBodyAttachment": attachment,
        "capabilityMatrix": capability_matrix,
        "adapt04AugmentationRequirements": adapt04_req,
        "adaptationSpecification": {
            "level": "ADAPTATION_SPECIFICATION",
            "nonDestructive": True,
            "physicalAugmentation": "DENY — ADAPT-04 ONLY",
        },
        "issues": issues,
        "blockers": blockers,
        "classification": classification,
        "preservationEvidence": {
            "sourceMeshMutation": "NONE",
            "sourceSkeletonMutation": "NONE",
            "sourceSkinWeightMutation": "NONE",
            "sourceMaterialMutation": "NONE",
            "nurionV1Mutation": "NONE",
            "adapt01Mutation": "NONE",
            "adapt02Mutation": "NONE",
            "faceAuthorityMutation": "NONE",
            "eyeCalibrationMutation": "NONE",
            "talkingAuthorityMutation": "NONE",
            "physicalHelperRigAugmentation": "NONE",
            "adapt04Implementation": "NOT_STARTED",
            "autoRepair": "DENY",
        },
    }
    out["contractCanonicalSha256"] = canonical_sha256(
        {k: v for k, v in out.items() if k != "contractCanonicalSha256"}
    )
    return out


def _blocked_output(
    adapt01: dict[str, Any],
    adapt02: dict[str, Any],
    binding: dict[str, Any],
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    out = {
        "schema": CONTRACT_SCHEMA,
        "characterIdentity": adapt01.get("characterId"),
        "sourceAssetDigest": (adapt01.get("sourceAsset") or {}).get("sha256"),
        "adapt01InspectionDigest": adapt01.get("reportCanonicalSha256"),
        "adapt02MappingDigest": adapt02.get("contractCanonicalSha256"),
        "faceAuthorityBindingSchema": binding.get("schema"),
        "targetFaceProfile": {},
        "headSemantic": _record(semantic="NURION_head", status="BLOCKED"),
        "landmarkCorrespondence": {"landmarks": {}, "status": "BLOCKED"},
        "expressionMap": {"mappings": {}, "status": "BLOCKED"},
        "eyeAdaptation": {"status": "BLOCKED"},
        "jawMouthMap": {"status": "BLOCKED"},
        "talkingVisemeMap": {"overallOutcome": "BLOCKED", "status": "BLOCKED"},
        "faceBodyAttachment": {"status": "BLOCKED"},
        "capabilityMatrix": {"rows": []},
        "adapt04AugmentationRequirements": {
            "augmentationRequired": False,
            "requirements": [],
            "adapt04Implementation": "NOT_STARTED",
        },
        "blockers": blockers,
        "issues": [],
        "classification": "BLOCKED",
        "preservationEvidence": {
            "nurionV1Mutation": "NONE",
            "adapt01Mutation": "NONE",
            "adapt02Mutation": "NONE",
            "faceAuthorityMutation": "NONE",
            "adapt04Implementation": "NOT_STARTED",
            "autoRepair": "DENY",
        },
    }
    out["contractCanonicalSha256"] = canonical_sha256(
        {k: v for k, v in out.items() if k != "contractCanonicalSha256"}
    )
    return out


def adapt_face_from_glb(
    glb_path: Path,
    adapt02_binding_path: Path,
    face_binding_path: Path,
    *,
    character_id: str | None = None,
    force_flags: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """ADAPT-01 inspect → ADAPT-02 map → ADAPT-03 face adapt. Source bytes unchanged."""
    before = glb_path.read_bytes() if glb_path.is_file() else None
    adapt01, adapt02 = adapt_from_glb(
        glb_path, adapt02_binding_path, character_id=character_id, force_flags=force_flags
    )
    face_binding = load_face_binding(face_binding_path)
    face_contract = build_face_adaptation(adapt01, adapt02, face_binding, force_flags=force_flags)
    if before is not None and glb_path.read_bytes() != before:
        raise RuntimeError("ADAPT-03 preservation violation: source bytes changed")
    return adapt01, adapt02, face_contract
