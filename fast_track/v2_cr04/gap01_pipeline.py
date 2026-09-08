"""CR04-GAP-01 pipeline — resolved facial regions + talking on preserved Sporty pin.

Does NOT modify CR02 source. Consumes CR02 build_morph_deltas / write_deformed_glb / measure_cycle.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.change_control import require_human_spec_gate, require_no_upstream_mutation
from fast_track.v2_cr01.flexible_adapter import run_flexible_adapter
from fast_track.v2_cr02.facial_deformation import (
    VERTEX_DELTA_THRESHOLD,
    _read_f32_vec3,
    _read_f32_vec4,
    _read_u8_vec4,
    apply_weights,
    build_morph_deltas,
    measure_cycle,
    write_deformed_glb,
)
from fast_track.v2_cr03.glb_measure import base_skin_digests, canonical_sha256, sha256_file
from fast_track.v2_cr04.facial_region_resolve import (
    resolve_head_joint_local_index,
    select_facial_vertices_resolved,
)
from fast_track.v2_cr04.fasttrack import inject_talking_by_name, prove_temporal
from fast_track.v2_cr04.pins import (
    ACTIVATION_THRESHOLD,
    APPROVED_SPEC_DIGEST as CR04_SPEC_DIGEST,
    SECOND_ASSET_SHA,
)

GAP01_CR = "V2-CR-04-GAP-01"
GAP01_APPROVED_SPEC = "PENDING_SET_AFTER_APPROVE"  # filled by runner from track


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, obj: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return sha256_file(path)


def _ast_calls_cr02_select_facial(text: str) -> bool:
    """True iff source imports or calls CR02 select_facial_vertices (not *_resolved)."""
    import ast

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "v2_cr02" in mod and "facial_deformation" in mod:
                for alias in node.names:
                    if alias.name == "select_facial_vertices":
                        return True
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "select_facial_vertices":
                return True
            if isinstance(fn, ast.Attribute) and fn.attr == "select_facial_vertices":
                return True
    return False


def _ast_assigns_forbidden_facial_sot(text: str) -> list[dict[str, Any]]:
    """Detect HEAD_SKIN_LOCAL / FACE_Y_MIN bindings in CR04 modules (AST, not string docs)."""
    import ast

    hits: list[dict[str, Any]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [{"code": "CR04_PARSE_FAIL"}]
    forbidden = {"HEAD_SKIN_LOCAL", "FACE_Y_MIN"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in forbidden:
                    hits.append({"code": "CR04_EMBEDS_IDLE15_FACIAL_SOT", "name": t.id, "line": getattr(node, "lineno", None)})
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in forbidden:
                hits.append(
                    {
                        "code": "CR04_EMBEDS_IDLE15_FACIAL_SOT",
                        "name": node.target.id,
                        "line": getattr(node, "lineno", None),
                    }
                )
    return hits


def expanded_hardcoding_scan(repo_root: Path) -> dict[str, Any]:
    """GAP-01 scan: CR04 consume path must not use Idle_15 facial SoT; CR02 literals documented historical."""
    blockers: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []

    cr02 = repo_root / "fast_track" / "v2_cr02" / "facial_deformation.py"
    text_cr02 = cr02.read_text(encoding="utf-8")
    # Document CR02 historical Idle_15 facial SoT (unchanged / CONSUME ONLY) — not a CR04 SoT.
    _cr02_head = "HEAD_SKIN_LOCAL" + " = " + "21"
    _cr02_ymin = "FACE_Y_MIN" + " = " + "1.28"
    if _cr02_head in text_cr02 and _cr02_ymin in text_cr02:
        notes.append(
            {
                "file": "fast_track/v2_cr02/facial_deformation.py",
                "disposition": "HISTORICAL_CR02_CONSUME_ONLY_UNCHANGED",
                "literals": ["HEAD_SKIN_LOCAL=21", "FACE_Y_MIN=1.28"],
                "rule": "CR02 source may retain Idle_15 facial SoT; CR04-GAP-01 must not import/call select_facial_vertices",
            }
        )
    else:
        notes.append({"file": str(cr02), "disposition": "UNEXPECTED_CR02_LITERAL_CHANGE"})

    for rel in (
        "fast_track/v2_cr04/facial_region_resolve.py",
        "fast_track/v2_cr04/gap01_pipeline.py",
        "fast_track/v2_cr04/fasttrack.py",
    ):
        path = repo_root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if _ast_calls_cr02_select_facial(text):
            blockers.append({"code": "CR04_CALLS_CR02_SELECT_FACIAL", "file": rel})
        for hit in _ast_assigns_forbidden_facial_sot(text):
            blockers.append({**hit, "file": rel})

    res = (repo_root / "fast_track/v2_cr04/facial_region_resolve.py").read_text(encoding="utf-8")
    if re.search(r"head_local_index\s*=\s*21\b", res) or re.search(r"HEAD_SKIN_LOCAL\s*=\s*21\b", res):
        blockers.append({"code": "RESOLVER_HARDCODES_21"})
    if "FACE_Y_MIN" in res and re.search(r"FACE_Y_MIN\s*=", res):
        blockers.append({"code": "RESOLVER_EMBEDS_FACE_Y_MIN"})

    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "notes": notes,
        "blockers": blockers,
        "covers": [
            "v2_cr04 facial consume path (AST import/call + assignment)",
            "documents CR02 historical literals without treating them as CR04 SoT",
        ],
    }


def run_gap01(
    *,
    track: dict[str, Any],
    spec_path: Path,
    roots: dict,
    approved_gap01_digest: str,
) -> dict[str, Any]:
    require_no_upstream_mutation(track)
    # Parent CR04 gate still required
    parent_track_path = Path(roots["semantic"]) / "NURION_ADAPTATION_ENGINE_V2_CR04_TRACK_V1.json"
    parent = json.loads(parent_track_path.read_text(encoding="utf-8"))
    # Normalize parent for gate: may be HUMAN_AUDIT_BLOCKED — still need GRANTED for corrective
    gate_track = {
        "changeRequest": GAP01_CR,
        "status": track.get("status"),
        "implementationAuthority": track.get("implementationAuthority"),
        "humanSpecGate": track.get("humanSpecGate"),
        "upstream": track.get("upstream") or parent.get("upstream"),
        "engineV2": track.get("engineV2", "NOT_OPEN"),
    }
    digest = require_human_spec_gate(
        gate_track, expected_change_request=GAP01_CR, spec_path=spec_path
    )
    if digest != approved_gap01_digest:
        raise PermissionError("GAP01 SPEC_DIGEST_MISMATCH")

    baseline = Path(roots["baseline"])
    derived_dir = Path(roots["derived"])
    rep = Path(roots["reports"])
    ev = Path(roots["evidence"])
    derived_dir.mkdir(parents=True, exist_ok=True)
    rep.mkdir(parents=True, exist_ok=True)

    before = baseline.read_bytes()
    if sha256_file(baseline) != SECOND_ASSET_SHA:
        return {"status": "BLOCKED", "blockers": [{"code": "SPORTY_PIN_MISMATCH"}]}

    cr01 = run_flexible_adapter(baseline)
    if cr01.get("status") != "PASS":
        return {"status": "BLOCKED", "blockers": [{"code": "CR01_FAIL"}]}
    if baseline.read_bytes() != before:
        return {"status": "BLOCKED", "blockers": [{"code": "SOURCE_MUTATED"}]}

    gltf, blob, _ = load_gltf_document(baseline)
    assert blob is not None
    skin_joints = list((gltf.get("skins") or [{}])[0].get("joints") or [])
    head_res = resolve_head_joint_local_index(
        nodes=list(gltf.get("nodes") or []),
        skin_joints=skin_joints,
        nurion_head_name=(cr01.get("mappingView") or {}).get("NURION_head"),
    )

    prim = gltf["meshes"][0]["primitives"][0]
    pos = _read_f32_vec3(blob, gltf, prim["attributes"]["POSITION"])
    joints = _read_u8_vec4(blob, gltf, prim["attributes"]["JOINTS_0"])
    weights = _read_f32_vec4(blob, gltf, prim["attributes"]["WEIGHTS_0"])
    regions = select_facial_vertices_resolved(
        pos, joints, weights, head_res["headJointLocalIndex"]
    )
    for key in ("eye_l", "eye_r", "mouth", "jaw"):
        if int(regions[key].sum()) < 5:
            return {
                "status": "BLOCKED",
                "blockers": [{"code": f"REGION_TOO_SMALL:{key}", "count": int(regions[key].sum())}],
                "headResolve": head_res,
            }

    deltas = build_morph_deltas(pos, regions)
    morph_order = [
        "Blink_L",
        "Blink_R",
        "Jaw_Mouth",
        "EXPR_SMILE",
        "EXPR_BROW_UP",
        "EXPR_FROWN",
        "VISEME_AA",
        "VISEME_OH",
        "VISEME_EE",
    ]
    face_derived = derived_dir / "SECOND_ASSET_GAP01_facial_deformation.glb"
    write_meta = write_deformed_glb(baseline, face_derived, deltas=deltas, morph_order=morph_order)
    if baseline.read_bytes() != before:
        return {"status": "BLOCKED", "blockers": [{"code": "SOURCE_MUTATED_BY_WRITE"}]}

    functional = {
        "Blink_L": measure_cycle(pos, deltas, "Blink_L", {"Blink_L": 1.0}),
        "Blink_R": measure_cycle(pos, deltas, "Blink_R", {"Blink_R": 1.0}),
        "Jaw_Mouth": measure_cycle(pos, deltas, "Jaw_Mouth", {"Jaw_Mouth": 1.0}),
        "VISEME_AA": measure_cycle(pos, deltas, "VISEME_AA", {"VISEME_AA": 1.0}),
        "VISEME_OH": measure_cycle(pos, deltas, "VISEME_OH", {"VISEME_OH": 1.0}),
        "VISEME_EE": measure_cycle(pos, deltas, "VISEME_EE", {"VISEME_EE": 1.0}),
    }
    blockers = []
    for name, row in functional.items():
        if row["functionalTest"] != "PASS":
            blockers.append({"code": f"FUNCTIONAL_FAIL:{name}", "row": row})

    talk_derived = derived_dir / "SECOND_ASSET_GAP01_talking_weights.glb"
    inj = inject_talking_by_name(input_glb=face_derived, output_glb=talk_derived)
    temporal = prove_temporal(talk_derived, inj["morphIndexMap"])
    if temporal["status"] != "PASS":
        blockers.extend(temporal.get("blockers") or [{"code": "TEMPORAL_FAIL"}])

    # BODY preservation vs baseline
    g_out, b_out, _ = load_gltf_document(talk_derived)
    assert b_out is not None
    if base_skin_digests(blob, gltf) != base_skin_digests(b_out, g_out):
        blockers.append({"code": "BODY_SKIN_REGRESSION"})

    scan = expanded_hardcoding_scan(Path(roots["repoRoot"]))
    if scan["status"] != "PASS":
        blockers.extend(scan["blockers"])

    # Coincidence guard: record resolved index; must come from resolver not literal 21 assignment
    if head_res["hardcodedIdle15Index21"] != "NOT_USED":
        blockers.append({"code": "HARDCODED_21_USED"})

    status = "PASS" if not blockers else "BLOCKED"
    final_sha = sha256_file(talk_derived)
    semantic = canonical_sha256(
        {
            "gap01": True,
            "secondAssetSha": SECOND_ASSET_SHA,
            "headResolve": head_res,
            "faceDerived": write_meta["derivedSha256"],
            "talkDerived": final_sha,
            "runtimeProofDigest": temporal.get("runtimeVertexProofDigest") or temporal.get("runtimeProofDigest"),
            "scan": scan["status"],
        }
    )
    report = {
        "schema": "NURION_V2_CR04_GAP01_R3_PROOF_V1",
        "status": status,
        "secondAssetSha256": SECOND_ASSET_SHA,
        "headResolve": head_res,
        "regionCounts": {k: int(v.sum()) for k, v in regions.items() if hasattr(v, "sum") and getattr(v, "dtype", None) == bool},
        "facialDerivedSha256": write_meta["derivedSha256"],
        "talkingDerivedSha256": final_sha,
        "functional": {k: v.get("functionalTest") for k, v in functional.items()},
        "temporal": temporal,
        "hardcodingScan": scan,
        "finalCandidateSemanticDigest": semantic,
        "blockers": blockers,
        "didNotCall": "v2_cr02.select_facial_vertices",
        "consumed": ["build_morph_deltas", "write_deformed_glb", "measure_cycle", "CR03 talking inject mechanism"],
        "upstreamReopen": "DENY",
    }
    _write_json(rep / "V2_CR04_GAP01_R3_proof.json", report)

    if status == "PASS":
        ready = {
            "receiptId": "NURION-V2-CR04_R3_READY_FOR_HUMAN_AUDIT",
            "changeRequestId": "V2-CR-04",
            "corrective": GAP01_CR,
            "status": "READY_FOR_HUMAN_AUDIT",
            "declaredAtUtc": _utc(),
            "secondAssetSha256": SECOND_ASSET_SHA,
            "derivedSha256": final_sha,
            "facialDerivedSha256": write_meta["derivedSha256"],
            "headJointLocalIndexResolved": head_res["headJointLocalIndex"],
            "headResolveProvenance": head_res["resolver"],
            "finalCandidateSemanticDigest": semantic,
            "runtimeProofDigest": temporal.get("runtimeProofDigest"),
            "hardcodingScan": "PASS",
            "agentCeiling": "READY_FOR_HUMAN_AUDIT",
            "CR04-P07": "HUMAN_FINAL_ONLY",
            "CR04-G20": "HUMAN_FINAL_ONLY",
            "engineV2": "NOT_OPEN",
            "note": "GAP-01 resolved facial regions; CR02 Idle_15 literals unused by CR04 consume path",
        }
        _write_json(ev / "NURION-V2-CR04_R3_READY_FOR_HUMAN_AUDIT_receipt.json", ready)

    return {
        "status": "READY_FOR_HUMAN_AUDIT" if status == "PASS" else "BLOCKED",
        "report": report,
        "derivedSha256": final_sha if status == "PASS" else None,
        "headResolve": head_res,
        "blockers": blockers,
    }
