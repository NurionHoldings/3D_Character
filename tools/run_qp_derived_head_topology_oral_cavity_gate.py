"""NURION Parametric Head Candidate A Derived Head Topology And Oral Cavity Gate GO.

Structure-only. No face renders. Sealed hm08 + Gate5 mutation must remain 0.
"""
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
from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import (
    EXPECTED_HM08_SHA,
    EXP_G5,
    derive_head,
    mesh_quality,
    parse_obj,
    sha256_file,
    transfer_correspondence,
    write_obj,
)

COMMAND = "NURION Parametric Head Candidate A Derived Head Topology And Oral Cavity Gate GO"
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
RAW = CAND / "raw"
MESH = RAW / "mpfb2_437dd513_base.obj"
REGION = CAND / "HEAD_REGION_MAP.json"
CORR = CAND / "MEDIAPIPE_478_CORRESPONDENCE.json"
MPFB2_COMMIT = "437dd513888a92399d1d3200d2e80859fae55abc"

ALLOWED = {
    "PASS_DERIVED_HEAD_TOPOLOGY_PENDING_QA_RENDER",
    "PASS_WITH_TOPOLOGY_LIMITATIONS",
    "TOPOLOGY_REWORK_REQUIRED",
    "ALGORITHM_FAIL",
    "SEALED_BASELINE_MUTATION_DENY",
}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def decide(meta: dict, quality: dict, transferred: dict) -> tuple[str, list[str]]:
    reasons = []
    if meta["oralFacesRemoved"] < 1:
        reasons.append("ORAL_OPENING_CUT_WEAK_OR_ZERO")
    if meta["boundaryLoopCount"] < 1:
        reasons.append("NO_BOUNDARY_AFTER_DERIVATION")
    if meta["neckRegionKept"] < 10:
        reasons.append("NECK_JOIN_TOO_SMALL")
    if meta["jawRegionKept"] < 50:
        reasons.append("JAW_REGION_TOO_SMALL")
    if meta["noseRegionKept"] < 20:
        reasons.append("NOSE_REGION_TOO_SMALL")
    if meta["eyelidRegionKept"] < 20:
        reasons.append("EYELID_REGION_TOO_SMALL")
    if quality["nonManifoldEdges"] > 0:
        reasons.append(f"NON_MANIFOLD:{quality['nonManifoldEdges']}")
    if quality["triCount"] > 0 and quality["quadCount"] == 0:
        reasons.append("LOST_QUAD_TOPOLOGY")
    lost = transferred.get("lostMappings", 0)
    if lost > 80:
        reasons.append(f"CORRESPONDENCE_LOSS_HIGH:{lost}")
    tc = transferred.get("typeCounts") or {}
    supported = tc.get("VERTEX", 0) + tc.get("EDGE", 0) + tc.get("FACE_BARYCENTRIC", 0)
    if supported < 350:
        reasons.append(f"SUPPORTED_468_TOO_LOW:{supported}")

    hard = [r for r in reasons if r.startswith("NON_MANIFOLD") or r.startswith("SUPPORTED_468") or r == "NO_BOUNDARY_AFTER_DERIVATION"]
    if hard and (quality["nonManifoldEdges"] > 50 or supported < 200):
        return "ALGORITHM_FAIL", reasons
    if reasons and any(
        r.startswith("ORAL_") or r.startswith("NECK_") or r.startswith("CORRESPONDENCE_LOSS") for r in reasons
    ):
        if meta["oralFacesRemoved"] >= 1 and meta["boundaryLoopCount"] >= 1 and supported >= 350:
            return "PASS_WITH_TOPOLOGY_LIMITATIONS", reasons
        return "TOPOLOGY_REWORK_REQUIRED", reasons
    if reasons:
        return "PASS_WITH_TOPOLOGY_LIMITATIONS", reasons
    return "PASS_DERIVED_HEAD_TOPOLOGY_PENDING_QA_RENDER", reasons


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"derived_head_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    # Sealed baselines must not mutate
    if not MESH.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "MESH_MISSING"})
        return 2
    hm08_sha = sha256_file(MESH)
    g5 = gate5_parameter_hash()
    sealed = {
        "hm08Sha256": hm08_sha,
        "hm08Expected": EXPECTED_HM08_SHA,
        "hm08Unchanged": hm08_sha == EXPECTED_HM08_SHA,
        "gate5Hash": g5,
        "gate5Expected": EXP_G5,
        "gate5Unchanged": g5 == EXP_G5,
        "sealedBaselineMutation": "ZERO" if hm08_sha == EXPECTED_HM08_SHA and g5 == EXP_G5 else "DETECT",
    }
    if sealed["sealedBaselineMutation"] != "ZERO":
        receipt = {
            "verdict": "SEALED_BASELINE_MUTATION_DENY",
            "sealed": sealed,
            "newFaceRendersCreated": 0,
            "production": "NO-GO",
        }
        write_json(out / "RECEIPT.json", receipt)
        write_json(CAND / "V07_QP_DERIVED_HEAD_TOPOLOGY_GATE_RECEIPT.json", receipt)
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        return 2

    regions = json.loads(REGION.read_text(encoding="utf-8"))["regions"]
    corr = json.loads(CORR.read_text(encoding="utf-8"))
    src = parse_obj(MESH)
    derived, meta, old_to_new = derive_head(src, regions)
    quality = mesh_quality(derived)
    transferred = transfer_correspondence(corr, old_to_new)

    header = [
        "# NURION Derived Head Base v0 from MakeHuman/MPFB hm08",
        f"# Source: makehumancommunity/mpfb2@{MPFB2_COMMIT}",
        f"# SourcePath: src/mpfb/data/3dobjs/base.obj",
        f"# SourceMeshSha256: {EXPECTED_HM08_SHA}",
        "# SourceAssetLicense: CC0 1.0 Universal (MakeHuman/MPFB core assets)",
        "# DerivedAsset: NURION_OWNED_DERIVATIVE_WITH_CC0_LINEAGE",
        "# Gate: Derived Head Topology And Oral Cavity — structure only, no render",
        f"# RunId: {run_id}",
    ]
    asset_path = CAND / "derived" / "NURION_DerivedHead_v0.obj"
    write_obj(asset_path, derived, header)
    derived_sha = sha256_file(asset_path)

    # Confirm source file still unchanged after write
    sealed_after = sha256_file(MESH)
    if sealed_after != EXPECTED_HM08_SHA:
        write_json(
            out / "RECEIPT.json",
            {"verdict": "SEALED_BASELINE_MUTATION_DENY", "reason": "HM08_CHANGED_AFTER_DERIVATION"},
        )
        return 2

    write_json(out / "DERIVATION_META.json", meta)
    write_json(out / "MESH_QUALITY.json", quality)
    write_json(out / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json", transferred)
    write_json(CAND / "derived" / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json", transferred)
    write_json(CAND / "derived" / "MESH_QUALITY.json", quality)

    verdict, reasons = decide(meta, quality, transferred)
    assert verdict in ALLOWED

    lineage = {
        "schema": "NURION_V07_DERIVED_HEAD_CC0_LINEAGE_RECEIPT_V1",
        "derivedAssetId": "NURION_DerivedHead_v0",
        "derivedPath": str(asset_path.relative_to(ROOT)).replace("\\", "/"),
        "derivedSha256": derived_sha,
        "source": {
            "repo": "makehumancommunity/mpfb2",
            "commit": MPFB2_COMMIT,
            "path": "src/mpfb/data/3dobjs/base.obj",
            "meshSha256": EXPECTED_HM08_SHA,
            "license": "CC0_1_0_UNIVERSAL",
            "licenseFile": "raw/LICENSE.ASSETS.md",
        },
        "lineageStatement": (
            "NURION DerivedHead v0 is a derivative of MakeHuman/MPFB hm08 core assets "
            "released under CC0 1.0. NURION claims ownership of the derived topology "
            "edits (head extraction, oral opening, correspondence transfer) while "
            "preserving CC0 lineage from the source basemesh."
        ),
        "reuseForbidden": ["NURION_PARAMETRIC_HEAD_V1_ELLIPSOID"],
        "issuedAt": now,
    }
    write_json(out / "CC0_LINEAGE_RECEIPT.json", lineage)
    write_json(CAND / "derived" / "CC0_LINEAGE_RECEIPT.json", lineage)
    write_json(ACQ / "V07_QP_DERIVED_HEAD_CC0_LINEAGE_RECEIPT.json", lineage)

    receipt = {
        "schema": "NURION_V07_DERIVED_HEAD_TOPOLOGY_ORAL_CAVITY_GATE_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "allowedVerdicts": sorted(ALLOWED),
        "reasons": reasons,
        "sealedBaselines": sealed,
        "derivation": meta,
        "quality": quality,
        "correspondenceTransfer": {
            "typeCounts": transferred.get("typeCounts"),
            "lostMappings": transferred.get("lostMappings"),
            "forcedSingleVertexMapping": "DENY",
        },
        "derivedAsset": {
            "path": str(asset_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": derived_sha,
        },
        "lineageReceipt": str((CAND / "derived" / "CC0_LINEAGE_RECEIPT.json").relative_to(ROOT)).replace("\\", "/"),
        "newFaceRendersCreated": 0,
        "qaRenderPolicy": {
            "thisGate": "DENY_NO_RENDER",
            "afterPass": "ALLOW_NEUTRAL_GRAY_FRONT_SIDE_WIREFRAME_QA_ONLY",
        },
        "holds": {
            "faceGenerationProduct": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "production": "NO-GO",
            "arkaonLearningInclusion": "HOLD",
        },
        "forcedPass": "DENY",
        "production": "NO-GO",
        "next": (
            "NEUTRAL_GRAY_QA_RENDER_FRONT_SIDE_WIREFRAME_GO"
            if verdict.startswith("PASS")
            else "REWORK_ORAL_NECK_OR_CORRESPONDENCE_TRANSFER"
        ),
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_DERIVED_HEAD_TOPOLOGY_GATE_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_DERIVED_HEAD_TOPOLOGY_GATE_RECEIPT.json", receipt)
    write_json(ACQ / "V07_QP_DERIVED_HEAD_TOPOLOGY_GATE_RECEIPT.json", receipt)

    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": verdict,
            "derivedHead": "NURION_DerivedHead_v0",
            "derivedSha256": derived_sha,
            "hm08Unchanged": True,
            "faceGeneration": "HOLD",
            "qaRenderAllowed": verdict.startswith("PASS"),
            "production": "NO-GO",
            "updatedAt": now,
            "lastRunId": run_id,
            "next": receipt["next"],
        },
    )

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Derived Head Topology Gate</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1.2rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
code{{color:#9cdcfe}}
</style></head><body>
<h1>Derived Head Topology And Oral Cavity</h1>
<span class="badge">{verdict}</span>
<span class="badge">렌더 0</span>
<span class="badge">hm08 변이 0</span>
<span class="badge">Production NO-GO</span>
<ul>
<li>derived SHA-256: <code>{derived_sha}</code></li>
<li>oral faces removed: {meta['oralFacesRemoved']}</li>
<li>boundary loops: {meta['boundaryLoopCount']}</li>
<li>verts/faces: {meta['vertexCount']} / {meta['faceCount']}</li>
<li>non-manifold edges: {quality['nonManifoldEdges']}</li>
<li>478 transfer lost: {transferred.get('lostMappings')}</li>
<li>types: {json.dumps(transferred.get('typeCounts'), ensure_ascii=False)}</li>
</ul>
<p>통과 후 허용: 중립 회색 정면·측면·와이어프레임 QA 렌더만.</p>
</body></html>
"""
    desk_path = CAND / "derived" / "DERIVED_HEAD_TOPOLOGY_DESK.html"
    desk_path.parent.mkdir(parents=True, exist_ok=True)
    desk_path.write_text(desk, encoding="utf-8")
    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "verdict": verdict,
                "reasons": reasons,
                "derivedSha256": derived_sha,
                "hm08Unchanged": True,
                "oralFacesRemoved": meta["oralFacesRemoved"],
                "boundaryLoopCount": meta["boundaryLoopCount"],
                "correspondence": transferred.get("typeCounts"),
                "lostMappings": transferred.get("lostMappings"),
                "newFaceRendersCreated": 0,
                "production": "NO-GO",
                "next": receipt["next"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict.startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
