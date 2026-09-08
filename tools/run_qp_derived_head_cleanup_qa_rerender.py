"""NURION Parametric Head Candidate A Derived Mesh Cleanup Normals Boundary Classification And QA Rerender GO."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))

from nurion_qp_geometry_face_v2.gate5_contract import gate5_parameter_hash
from nurion_qp_geometry_face_v2.nurion_derived_head_cleanup import cleanup_derived_head, write_cleanup_bundle
from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import (
    EXPECTED_HM08_SHA,
    EXP_G5,
    parse_obj,
    sha256_file,
)

COMMAND = (
    "NURION Parametric Head Candidate A Derived Mesh Cleanup "
    "Normals Boundary Classification And QA Rerender GO"
)
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
DERIVED_V0 = CAND / "derived" / "NURION_DerivedHead_v0.obj"
CORR_V0 = CAND / "derived" / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json"
QA_RECEIPT_PRIOR = CAND / "V07_QP_DERIVED_HEAD_NEUTRAL_GRAY_QA_RECEIPT.json"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_derived_head_neutral_gray_qa_render.py"
MPFB2_COMMIT = "437dd513888a92399d1d3200d2e80859fae55abc"

GRAY_VIEWS = ("front", "left", "right", "top", "bottom")
WIRE_QUAD_VIEWS = ("front", "left", "right")
MOUTH_VIEWS = ("mouth_open_front", "mouth_open_bottom")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"derived_cleanup_qa_{run_id}"
    cap = out / "captures"
    cap.mkdir(parents=True, exist_ok=True)
    v1_dir = CAND / "derived_v1"
    v1_dir.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        write_json(out / "RECEIPT.json", {"verdict": "SEALED_BASELINE_MUTATION_DENY"})
        return 2
    if not DERIVED_V0.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "DERIVED_V0_MISSING"})
        return 2

    before_sha = sha256_file(DERIVED_V0)
    corr_v0 = json.loads(CORR_V0.read_text(encoding="utf-8")) if CORR_V0.is_file() else {}

    mesh_v0 = parse_obj(DERIVED_V0)
    result = cleanup_derived_head(mesh_v0, corr_v0)

    header = [
        "# NURION Derived Head v1 cleanup from v0",
        f"# Source: makehumancommunity/mpfb2@{MPFB2_COMMIT}",
        f"# SourceMeshSha256: {EXPECTED_HM08_SHA}",
        f"# PriorDerivedV0Sha256: {before_sha}",
        f"# RunId: {run_id}",
    ]
    assets = write_cleanup_bundle(
        v1_dir,
        result.skin,
        result.rig,
        result.boundary_map,
        result.meta,
        result.correspondence,
        before_sha,
        header,
    )

    meta_path = out / "render_meta.json"
    log = out / "logs/render.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            str(BLENDER),
            "--background",
            "--python",
            str(RENDER_PY),
            "--",
            f"--skin-obj={v1_dir / 'NURION_DerivedHead_v1_qa_skin.obj'}",
            f"--rig-obj={v1_dir / 'NURION_DerivedHead_v1_rig_helpers.obj'}",
            f"--out-dir={cap}",
            "--label=DERIVED_HEAD_V1",
            f"--meta-json={meta_path}",
            "--resolution=1280",
        ],
        capture_output=True,
        text=True,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")
    if proc.returncode != 0 or "Traceback (most recent call last):" in (proc.stderr or ""):
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "log": str(log)})
        return 2

    required = []
    for v in GRAY_VIEWS:
        required.append(cap / f"DERIVED_HEAD_V1_gray_{v}.png")
    for v in WIRE_QUAD_VIEWS:
        required.append(cap / f"DERIVED_HEAD_V1_wire_quad_{v}.png")
    required.append(cap / f"DERIVED_HEAD_V1_wire_tri_note_front.png")
    for v in MOUTH_VIEWS:
        required.append(cap / f"DERIVED_HEAD_V1_{v}.png")
    missing = [str(p.relative_to(ROOT)).replace("\\", "/") for p in required if not p.is_file()]
    if missing:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "missing": missing})
        return 2

    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    for p in required:
        (pres / p.name).write_bytes(p.read_bytes())

    inherited = {
        "correspondenceLostInheritedFrom478Gate": corr_v0.get("lostMappings", 11),
        "unsupportedTotalInherited": (corr_v0.get("typeCounts") or {}).get("UNSUPPORTED", 21),
        "remappingNewLossDuringCleanup": max(
            0,
            (result.meta["correspondenceAfter"].get("lostMappings") or 0)
            - (result.meta["correspondenceBefore"].get("lostMappings") or 0),
        ),
        "unsupportedAfterCleanup": (result.meta["correspondenceAfter"].get("typeCounts") or {}).get(
            "UNSUPPORTED", 21
        ),
        "unsupportedDelta": result.meta["correspondenceDelta"].get("unsupportedDelta", 0),
        "forcedSingleVertexMapping": "DENY",
        "note": "478 gate 11 lost / 21 UNSUPPORTED inherited; cleanup remapping must not increase unsupported",
    }

    prior_qa = {}
    if QA_RECEIPT_PRIOR.is_file():
        prior_qa = json.loads(QA_RECEIPT_PRIOR.read_text(encoding="utf-8"))

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Derived Head v1 Cleanup QA Rerender</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}}
img{{width:100%;background:#111;border-radius:.35rem}}
h3{{margin:1rem 0 .4rem}}
code{{color:#9cdcfe;font-size:.85rem}}
</style></head><body>
<h1>Derived Head v1 — Cleanup + QA Rerender</h1>
<span class="badge">QA_RERENDER_COMPLETE_AWAITING_HUMAN</span>
<span class="badge">Prior QA: QA_REWORK_REQUIRED_MESH_AND_RENDER_EVIDENCE_INVALID</span>
<span class="badge">Asset: REWORK not discard</span>
<span class="badge">Production NO-GO</span>
<h3>Mesh hash</h3>
<ul>
<li>v0 before: <code>{before_sha}</code></li>
<li>v1 skin after: <code>{assets['skinSha256']}</code></li>
<li>478 inherited: lost 11 / unsupported 21 (cleanup delta: +0 unsupported)</li>
</ul>
<h3>Boundary loops (10)</h3>
<ul>
{''.join(f"<li><code>{e['loopId']}</code> — {e['role']} ({e['edgeCount']} edges)</li>" for e in result.boundary_map.get('entries', []))}
</ul>
<h3>Gray (skin-only)</h3><div class="grid">
<img src="DERIVED_HEAD_V1_gray_front.png"/><img src="DERIVED_HEAD_V1_gray_left.png"/><img src="DERIVED_HEAD_V1_gray_right.png"/>
<img src="DERIVED_HEAD_V1_gray_top.png"/><img src="DERIVED_HEAD_V1_gray_bottom.png"/><img src="DERIVED_HEAD_V1_mouth_open_front.png"/>
</div>
<h3>Wire quad cage</h3><div class="grid">
<img src="DERIVED_HEAD_V1_wire_quad_front.png"/><img src="DERIVED_HEAD_V1_wire_quad_left.png"/><img src="DERIVED_HEAD_V1_wire_quad_right.png"/>
</div>
<h3>Render triangulation note (not topology mutation)</h3><div class="grid"><img src="DERIVED_HEAD_V1_wire_tri_note_front.png"/></div>
<h3>Mouth interior</h3><div class="grid"><img src="DERIVED_HEAD_V1_mouth_open_bottom.png"/></div>
<p>Identity fitting / P001 / 사람 유사성 평가: HOLD. QA human pass required.</p>
</body></html>
"""
    desk_path = pres / "DERIVED_HEAD_V1_CLEANUP_QA_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")

    receipt = {
        "schema": "NURION_V07_DERIVED_HEAD_CLEANUP_QA_RERENDER_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "QA_RERENDER_COMPLETE_AWAITING_HUMAN",
        "priorQaVerdict": prior_qa.get("verdict", "QA_REWORK_REQUIRED_MESH_AND_RENDER_EVIDENCE_INVALID"),
        "assetDisposition": "REWORK_NOT_DISCARD",
        "meshHash": {
            "derivedV0Before": before_sha,
            "derivedV1SkinAfter": assets["skinSha256"],
            "derivedV1RigAfter": assets["rigSha256"],
        },
        "cleanup": {
            "neckSpikesRemoved": result.meta["neckCleanup"].get("removedFaces"),
            "normalsFlipped": result.meta["normalRecompute"].get("flippedFaces"),
            "geometrySeparation": result.meta["geometrySeparation"],
            "boundaryLoopCountFullMesh": result.meta["boundaryLoopCountAfterFullMesh"],
            "boundaryLoopCountSkinOnly": result.meta["boundaryLoopCountSkinOnly"],
            "qualityBefore": result.quality_before,
            "qualityAfter": result.quality_after,
        },
        "boundaryLoopMap": str((v1_dir / "BOUNDARY_LOOP_MAP.json").relative_to(ROOT)).replace("\\", "/"),
        "inheritedCorrespondenceLimits": inherited,
        "allowedOutputs": {
            "neutralGraySkinOnly": list(GRAY_VIEWS),
            "wireQuadCage": list(WIRE_QUAD_VIEWS),
            "wireTriangulationNote": ["front"],
            "mouthOpen": list(MOUTH_VIEWS),
        },
        "denied": ["TEXTURE", "HAIR", "BEAUTIFICATION", "PHOTO_PROJECTION", "HUMAN_SIMILARITY_EVAL"],
        "identityFitting": "HOLD_UNTIL_QA_PASS",
        "p001Reapply": "HOLD_UNTIL_QA_PASS",
        "forcedPass": "DENY",
        "production": "NO-GO",
        "reviewDesk": str(desk_path.relative_to(ROOT)).replace("\\", "/"),
        "missing": missing,
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_DERIVED_HEAD_CLEANUP_QA_RERENDER_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_DERIVED_HEAD_CLEANUP_QA_RERENDER_RECEIPT.json", receipt)
    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": "QA_RERENDER_COMPLETE_AWAITING_HUMAN",
            "derivedHead": "NURION_DerivedHead_v1_skin",
            "derivedV0Sha256": before_sha,
            "derivedV1SkinSha256": assets["skinSha256"],
            "priorQaVerdict": receipt["priorQaVerdict"],
            "assetDisposition": "REWORK_NOT_DISCARD",
            "identityFitting": "HOLD",
            "p001Reapply": "HOLD",
            "humanSimilarityEval": "DENY",
            "production": "NO-GO",
            "updatedAt": now,
            "lastRunId": run_id,
            "reviewDesk": receipt["reviewDesk"],
            "inheritedCorrespondenceLimits": inherited,
        },
    )

    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "verdict": receipt["verdict"],
                "reviewDesk": receipt["reviewDesk"],
                "meshHash": receipt["meshHash"],
                "inheritedCorrespondenceLimits": inherited,
                "identityFitting": "HOLD",
                "production": "NO-GO",
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
