"""CR03-P01 — Runtime Talking Contract / Morph Binding Inspection (read-only).

Consumes CR02 R2 derived GLB. Does not mutate morph POSITION or create animation.
Binds VISEME_AA/OH/EE names to primitive target indices and inventories weights channels.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.change_control import require_human_spec_gate, require_no_upstream_mutation
from fast_track.v2_cr02.facial_deformation import _read_f32_vec3

REPORT_SCHEMA = "NURION_V2_CR03_P01_MORPH_BINDING_INSPECTION_V1"
CR = "V2-CR-03"
APPROVED_SPEC_DIGEST = "3e3885335bcfd8489209a302852230ae6cdd55da89fb8328048f82d8fe4a206c"
CR02_R2_DERIVED_SHA = "1ee90420ba39cc2e74de6624230538f4416d39ec7b34656e5b175a776c171cdd"
REQUIRED_MORPHS = ("VISEME_AA", "VISEME_OH", "VISEME_EE")
ACTIVATION_THRESHOLD = 1e-4


def _max_norm(a: np.ndarray) -> float:
    if len(a) == 0:
        return 0.0
    return float(np.linalg.norm(a, axis=1).max())


def _inventory_weights_channels(gltf: dict[str, Any]) -> dict[str, Any]:
    anims = gltf.get("animations") or []
    weights_channels: list[dict[str, Any]] = []
    for ai, anim in enumerate(anims):
        name = anim.get("name")
        for ci, ch in enumerate(anim.get("channels") or []):
            target = ch.get("target") or {}
            if target.get("path") == "weights":
                weights_channels.append(
                    {
                        "animationIndex": ai,
                        "animationName": name,
                        "channelIndex": ci,
                        "node": target.get("node"),
                        "sampler": ch.get("sampler"),
                    }
                )
    return {
        "animationCount": len(anims),
        "animationNames": [a.get("name") for a in anims],
        "weightsChannelCount": len(weights_channels),
        "weightsChannels": weights_channels,
        "talkingWeightsChannelPresent": False,  # P01: not yet injected
    }


def inspect_morph_binding(
    *,
    input_glb: Path,
    track: dict[str, Any],
    spec_path: Path,
    expected_sha: str = CR02_R2_DERIVED_SHA,
) -> dict[str, Any]:
    require_no_upstream_mutation(track)
    gate_digest = require_human_spec_gate(
        track,
        expected_change_request=CR,
        spec_path=spec_path,
    )
    if gate_digest != APPROVED_SPEC_DIGEST:
        raise PermissionError(
            f"SPEC_DIGEST_MISMATCH → IMPLEMENTATION DENIED "
            f"(gate={gate_digest}, pin={APPROVED_SPEC_DIGEST})"
        )

    input_glb = Path(input_glb)
    before = input_glb.read_bytes()
    input_sha = sha256_file(input_glb)
    blockers: list[dict[str, Any]] = []

    if input_sha != expected_sha:
        blockers.append(
            {
                "code": "CR02_R2_INPUT_SHA_MISMATCH",
                "got": input_sha,
                "want": expected_sha,
            }
        )

    gltf, blob, _ = load_gltf_document(input_glb)
    after_load = input_glb.read_bytes()
    if after_load != before:
        blockers.append({"code": "INPUT_MUTATED_BY_LOAD"})

    mesh = (gltf.get("meshes") or [None])[0]
    if not mesh:
        blockers.append({"code": "NO_MESH"})
        return _fail_report(input_sha, gate_digest, blockers, {})

    prim = (mesh.get("primitives") or [None])[0]
    if not prim:
        blockers.append({"code": "NO_PRIMITIVE"})
        return _fail_report(input_sha, gate_digest, blockers, {})

    targets = prim.get("targets") or []
    names = list((mesh.get("extras") or {}).get("targetNames") or [])
    if len(names) != len(targets):
        blockers.append(
            {
                "code": "TARGET_NAMES_LENGTH_MISMATCH",
                "names": len(names),
                "targets": len(targets),
            }
        )
        names = names[: len(targets)] + [
            f"target_{i}" for i in range(len(names), len(targets))
        ]

    if blob is None:
        blockers.append({"code": "MISSING_BIN"})
        return _fail_report(input_sha, gate_digest, blockers, {"targetNames": names})

    base = _read_f32_vec3(blob, gltf, prim["attributes"]["POSITION"])
    deltas: list[np.ndarray] = []
    for t in targets:
        if "POSITION" not in t:
            blockers.append({"code": "MORPH_MISSING_POSITION_ACCESSOR", "target": t})
            deltas.append(np.zeros_like(base))
        else:
            deltas.append(_read_f32_vec3(blob, gltf, t["POSITION"]))

    morph_index_map: dict[str, dict[str, Any]] = {}
    for req in REQUIRED_MORPHS:
        if req not in names:
            blockers.append({"code": "REQUIRED_MORPH_MISSING", "morph": req})
            continue
        idx = names.index(req)
        # Ambiguous duplicate names → fail-closed
        if names.count(req) != 1:
            blockers.append(
                {
                    "code": "NON_DETERMINISTIC_MORPH_ORDERING",
                    "morph": req,
                    "count": names.count(req),
                }
            )
        d = deltas[idx]
        max_delta = _max_norm(d)
        morph_index_map[req] = {
            "name": req,
            "targetIndex": idx,
            "positionAccessor": targets[idx].get("POSITION"),
            "maxMorphDelta": max_delta,
            "activationReady": max_delta > ACTIVATION_THRESHOLD,
        }
        if max_delta <= ACTIVATION_THRESHOLD:
            blockers.append(
                {
                    "code": "MORPH_DELTA_BELOW_ACTIVATION",
                    "morph": req,
                    "maxMorphDelta": max_delta,
                }
            )

    # Distinct static deltas (CR02 property — binding readiness, not CR03 temporal PASS)
    distinct: dict[str, Any] = {}
    if all(m in morph_index_map for m in REQUIRED_MORPHS):
        aa = deltas[morph_index_map["VISEME_AA"]["targetIndex"]]
        oh = deltas[morph_index_map["VISEME_OH"]["targetIndex"]]
        ee = deltas[morph_index_map["VISEME_EE"]["targetIndex"]]
        distinct = {
            "AA_vs_OH": _max_norm(aa - oh),
            "AA_vs_EE": _max_norm(aa - ee),
            "OH_vs_EE": _max_norm(oh - ee),
        }
        if any(v <= ACTIVATION_THRESHOLD for v in distinct.values()):
            blockers.append({"code": "VISEME_DELTAS_NOT_DISTINCT", "detail": distinct})

    weights_inv = _inventory_weights_channels(gltf)
    # P01 expects no talking weights channel yet — presence of *any* weights is noted
    # but CR03 talking injection is still a P02 gap.
    # Explicit: even if stray weights exist, TALKING sequence is unproven until P02/P03
    weights_inv["talkingWeightsChannelPresent"] = False
    weights_inv["cr03TalkingAnimationGap"] = True

    if "Jaw_Mouth" in names:
        jaw_independence = {
            "Jaw_Mouth_targetIndex": names.index("Jaw_Mouth"),
            "rule": "Jaw_Mouth = CR02 CONSUME ONLY ≠ TALKING PASS",
            "TALKING": "timed VISEME_AA/OH/EE morph-weight orchestration (P02+)",
        }
    else:
        jaw_independence = {"Jaw_Mouth": "ABSENT_ON_MESH", "rule": "still ≠ TALKING"}

    # FACE_Rig_Root / node extras skim (non-mutating)
    face_interface = None
    for ni, node in enumerate(gltf.get("nodes") or []):
        extras = node.get("extras") or {}
        if extras.get("nurionSemantic") == "FACE_Rig_Root":
            face_interface = {
                "nodeIndex": ni,
                "name": node.get("name"),
                "drivesMorphTargets": extras.get("drivesMorphTargets"),
            }
            break
    if face_interface is None:
        blockers.append({"code": "FACE_RIG_ROOT_INTERFACE_MISSING"})

    after = input_glb.read_bytes()
    if after != before:
        blockers.append({"code": "INPUT_MUTATED_AFTER_INSPECTION"})

    input_morph_semantic = canonical_sha256(
        {
            "targetNames": names,
            "morphIndexMap": {
                k: {"targetIndex": v["targetIndex"], "positionAccessor": v["positionAccessor"]}
                for k, v in morph_index_map.items()
            },
            "meshPrimitive": 0,
        }
    )

    contract = {
        "sequenceSemantics": "NEUTRAL → AA → transition → OH → transition → EE → NEUTRAL",
        "requiredMorphsBound": list(REQUIRED_MORPHS),
        "morphIndexMap": morph_index_map,
        "timingPolicy": "sequence semantics fixed; duration/key timing = deterministic params at P02",
        "notYetProven": [
            "time-varying weights in GLB",
            "temporal vertex deformation",
            "neutral restoration via animation",
        ],
    }

    status = "PASS" if not blockers else "BLOCKED"
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "changeRequestId": CR,
        "stage": "CR03-P01",
        "status": status,
        "gate": {
            "humanSpecGate": "ENFORCED",
            "approvedSpecDigest": gate_digest,
            "pin": APPROVED_SPEC_DIGEST,
        },
        "input": {
            "path": str(input_glb).replace("\\", "/"),
            "sha256": input_sha,
            "expectedSha256": expected_sha,
            "immutable": after == before,
        },
        "targetNames": names,
        "morphCount": len(targets),
        "morphIndexMap": morph_index_map,
        "visemeDistinctness": distinct,
        "weightsAnimationInventory": weights_inv,
        "talkingFunctionalContract": contract,
        "independence": jaw_independence,
        "faceRigRoot": face_interface,
        "provenance": {
            "cr02R2DerivedSha256": input_sha,
            "inputMorphSemanticDigest": input_morph_semantic,
            "approvedSpecDigest": gate_digest,
        },
        "authorizedMutationScopeNote": "P01 read-only — no animation injection; P02 creates weights channels",
        "blockers": blockers,
        "next": "CR03-P02 Morph-Weight Animation Injection" if status == "PASS" else "Resolve blockers",
    }
    return report


def _fail_report(
    input_sha: str,
    gate_digest: str,
    blockers: list[dict[str, Any]],
    extra: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA,
        "changeRequestId": CR,
        "stage": "CR03-P01",
        "status": "BLOCKED",
        "gate": {"approvedSpecDigest": gate_digest},
        "input": {"sha256": input_sha},
        "blockers": blockers,
        **extra,
    }


def write_report(report: dict[str, Any], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return sha256_file(path)
