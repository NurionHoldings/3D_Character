"""NURION Parametric Head Asset Acquisition Commercial License And Topology Gate GO.

Does NOT generate faces, bodies, or human A/B. Evaluates whether an eligible
commercial/NURION-owned parametric head asset is registered and topology-checked.
Until PASS: face generation / body assembly / human eval remain HOLD.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT / "tools"))

from write_qp_asset_ineligible_parametric_head import main as write_ineligible

COMMAND = "NURION Parametric Head Asset Acquisition Commercial License And Topology Gate GO"
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
BETA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_beta1"

REQUIRED_TOPOLOGY = [
    "QUAD_CENTRIC_HUMAN_FACE_TOPOLOGY",
    "EYELID_AND_ORBIT",
    "NOSE_ALA_NOSTRIL",
    "LIP_INNER_OUTER_AND_ORAL_OPENING",
    "EAR_STRUCTURE",
    "JAW_CHEEKBONE_TEMPLE_CONTROL",
    "NECK_JOIN",
    "CONTINUOUS_UV",
    "IDENTITY_SHAPE_BASIS",
    "EXPRESSION_BASIS",
    "JAW_AND_EYE_JOINTS",
    "MEDIAPIPE_478_CORRESPONDENCE_TABLE",
]

REQUIRED_LICENSE = [
    "COMMERCIAL_USE_RIGHT",
    "MODIFY_RIGHT",
    "DISTRIBUTE_OR_EMBED_RIGHT_DECLARED",
    "SOURCE_FILE_SHA256",
    "LICENSE_FILE_SHA256",
]

INELIGIBLE_IDS = {
    "NURION_PARAMETRIC_HEAD_V1",
    "NURION_PARAMETRIC_FACE_V0",
    "MEDIAPIPE_FACEMESH_854",
}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_templates() -> None:
    contract = {
        "schema": "NURION_V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_CONTRACT_V1",
        "command": COMMAND,
        "purpose": "Acquire eligible human-face parametric head before any further face render or body bind",
        "requiredTopology": REQUIRED_TOPOLOGY,
        "requiredLicense": REQUIRED_LICENSE,
        "ineligibleClasses": [
            "SPHERICAL_ELLIPSOID_TRI_MESH",
            "MEDIAPIPE_TRACKING_MESH_AS_RENDER_SURFACE",
            "PHOTO_ON_BALLOON",
            "RESEARCH_ONLY_3DMM_WITHOUT_COMMERCIAL_RIGHTS",
        ],
        "ineligibleAssetIds": sorted(INELIGIBLE_IDS),
        "paths": {
            "path1_commercial": "Acquire verified commercial parametric head; reuse 478 correspondence + fit/rig/export",
            "path2_nurion_owned": "Commission NURION-owned head base (neutral adult, eyes/teeth/tongue/oral, hairline, shape keys, neck join)",
            "recommended": "Commercial external for product Alpha; parallel NURION-owned; swap when validated",
        },
        "holdsUntilPass": [
            "FACE_GENERATION",
            "FULL_BODY_ASSEMBLY",
            "HUMAN_EVALUATION",
            "BETA_PASS",
            "ARKAON_LEARNING_INCLUSION",
        ],
        "production": "NO-GO_UNTIL_ASSET_PASS",
    }
    write_json(ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_CONTRACT.json", contract)

    registry_path = ACQ / "V07_QP_PARAMETRIC_HEAD_CANDIDATE_REGISTRY.json"
    if not registry_path.is_file():
        write_json(
            registry_path,
            {
                "schema": "NURION_V07_QP_PARAMETRIC_HEAD_CANDIDATE_REGISTRY_V1",
                "candidates": [],
                "selectedEligibleId": None,
                "note": "Register candidates with meshPath, licensePath, topologyChecklist, rights, sha256 fields. Ellipsoid NURION_PARAMETRIC_HEAD_V1 must never be selected.",
            },
        )

    checklist_template = {
        "schema": "NURION_V07_QP_PARAMETRIC_HEAD_TOPOLOGY_CHECKLIST_TEMPLATE_V1",
        "instructions": "Operator/artist fills per candidate. All requiredTopology keys must be true for eligibility.",
        "requiredTopology": {k: False for k in REQUIRED_TOPOLOGY},
        "requiredLicense": {k: False for k in REQUIRED_LICENSE},
        "denyIfTrue": {
            "isSphericalEllipsoidWithoutFacialEdgeLoops": None,
            "isMediaPipe854RenderSurface": None,
            "isResearchOnlyWithoutCommercialRights": None,
        },
    }
    write_json(ACQ / "V07_QP_PARAMETRIC_HEAD_TOPOLOGY_CHECKLIST_TEMPLATE.json", checklist_template)


def evaluate_candidate(c: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    cid = str(c.get("id") or "")
    if cid in INELIGIBLE_IDS:
        failures.append(f"INELIGIBLE_ASSET_ID:{cid}")
    if c.get("class") in (
        "SPHERICAL_ELLIPSOID_TRI_MESH",
        "MEDIAPIPE_TRACKING_MESH_AS_RENDER_SURFACE",
        "PHOTO_ON_BALLOON",
    ):
        failures.append(f"INELIGIBLE_CLASS:{c.get('class')}")

    topo = c.get("topologyChecklist") or {}
    for key in REQUIRED_TOPOLOGY:
        if not topo.get(key):
            failures.append(f"TOPOLOGY_MISSING:{key}")

    lic = c.get("licenseChecklist") or {}
    for key in REQUIRED_LICENSE:
        if not lic.get(key):
            failures.append(f"LICENSE_MISSING:{key}")

    mesh = Path(str(c.get("meshPath") or ""))
    license_f = Path(str(c.get("licensePath") or ""))
    if not mesh.is_file():
        failures.append("MESH_FILE_ABSENT")
    else:
        expected = c.get("meshSha256")
        actual = sha256_file(mesh)
        if expected and expected != actual:
            failures.append("MESH_SHA256_MISMATCH")
        c = {**c, "meshSha256Computed": actual}
    if not license_f.is_file():
        failures.append("LICENSE_FILE_ABSENT")
    else:
        expected = c.get("licenseSha256")
        actual = sha256_file(license_f)
        if expected and expected != actual:
            failures.append("LICENSE_SHA256_MISMATCH")
        c = {**c, "licenseSha256Computed": actual}

    corr = Path(str(c.get("correspondence478Path") or ""))
    if not corr.is_file():
        failures.append("CORRESPONDENCE_478_ABSENT")

    deny = c.get("denyIfTrue") or {}
    for k, v in deny.items():
        if v is True:
            failures.append(f"DENY_FLAG:{k}")

    return {"id": cid, "eligible": len(failures) == 0, "failures": failures, "candidate": c}


def main() -> int:
    write_ineligible()
    ensure_templates()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ACQ / "runs" / run_id
    out.mkdir(parents=True, exist_ok=True)

    registry = json.loads((ACQ / "V07_QP_PARAMETRIC_HEAD_CANDIDATE_REGISTRY.json").read_text(encoding="utf-8"))
    candidates = list(registry.get("candidates") or [])
    evaluations = [evaluate_candidate(c) for c in candidates]
    eligible = [e for e in evaluations if e["eligible"]]

    # Explicitly mark built-in ellipsoid as reviewed-ineligible (evidence lock)
    ellipsoid_lock = {
        "id": "NURION_PARAMETRIC_HEAD_V1",
        "eligible": False,
        "failures": [
            "INELIGIBLE_ASSET_ID:NURION_PARAMETRIC_HEAD_V1",
            "INELIGIBLE_CLASS:SPHERICAL_ELLIPSOID_TRI_MESH",
            "WIREFRAME_EVIDENCE:NO_ANATOMICAL_EDGE_LOOPS",
        ],
        "evidenceRun": "beta1_1_headonly_20260816T093137Z",
    }

    if not candidates:
        verdict = "ASSET_ACQUISITION_GATE_HOLD_NO_CANDIDATE_REGISTERED"
    elif not eligible:
        verdict = "ASSET_ACQUISITION_GATE_FAIL_NO_ELIGIBLE_ASSET"
    else:
        verdict = "ASSET_ACQUISITION_GATE_PASS"
        registry["selectedEligibleId"] = eligible[0]["id"]
        write_json(ACQ / "V07_QP_PARAMETRIC_HEAD_CANDIDATE_REGISTRY.json", registry)

    receipt = {
        "schema": "NURION_V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "priorVerdict": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
        "ellipsoidIneligible": ellipsoid_lock,
        "candidateCount": len(candidates),
        "eligibleCount": len(eligible),
        "evaluations": evaluations,
        "holds": {
            "faceGeneration": "HOLD" if verdict != "ASSET_ACQUISITION_GATE_PASS" else "RELEASE_TO_FIT_ENGINE",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "betaPass": "DENY",
            "arkaonLearningInclusion": "HOLD",
        },
        "forcedPass": "DENY",
        "production": "NO-GO" if verdict != "ASSET_ACQUISITION_GATE_PASS" else "NO-GO_PENDING_FIT_GATE",
        "next": (
            "REGISTER_COMMERCIAL_OR_NURION_OWNED_HEAD_IN_CANDIDATE_REGISTRY"
            if verdict != "ASSET_ACQUISITION_GATE_PASS"
            else "BIND_478_CORRESPONDENCE_AND_RESUME_HEAD_ONLY_FIT"
        ),
        "operatorActions": [
            "Acquire commercial parametric head OR commission NURION-owned base",
            "Fill topology + license checklists",
            "Place mesh + license files; record SHA-256",
            "Provide MediaPipe 478 correspondence table",
            "Re-run this Gate GO — do not resume face/body renders before PASS",
        ],
    }
    raw = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()

    write_json(out / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_RECEIPT.json", receipt)
    write_json(ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_RECEIPT.json", receipt)
    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "schema": "NURION_V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS_V1",
            "status": verdict,
            "LOCKED_HOLD": verdict != "ASSET_ACQUISITION_GATE_PASS",
            "updatedAt": now,
            "lastRunId": run_id,
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "forcedPass": "DENY",
            "production": "NO-GO",
            "selectedEligibleId": registry.get("selectedEligibleId"),
            "next": receipt["next"],
        },
    )

    # Keep beta status aligned
    write_json(
        BETA / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
        {
            "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS_V1",
            "status": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
            "assetAcquisitionGate": verdict,
            "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
            "LOCKED": True,
            "updatedAt": now,
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "betaPass": "DENY",
            "forcedPass": "DENY",
            "production": "NO-GO",
            "arkaonLearningInclusion": "HOLD",
            "next": receipt["next"],
        },
    )

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Parametric Head Asset Acquisition Gate</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1.25rem}}
.badge{{display:inline-block;margin:.2rem .35rem .2rem 0;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.8rem;color:#c4a574}}
li{{margin:.35rem 0}}
code{{color:#9cdcfe}}
</style></head><body>
<h1>Parametric Head Asset Acquisition Gate</h1>
<p>렌더 개발 HOLD. 핵심은 얼굴 기준 자산 확보.</p>
<span class="badge">{verdict}</span>
<span class="badge">NURION_PARAMETRIC_HEAD_V1 = INELIGIBLE</span>
<span class="badge">Production NO-GO</span>
<span class="badge">강제 PASS 금지</span>
<h2>중단</h2>
<ul>
<li>타원 Head 수정 / UV 반복 / 눈·입 primitive 조정</li>
<li>전신 재결합 / A/B 사람 평가 / Beta PASS / ARKAON 학습 산입</li>
</ul>
<h2>필요 조건</h2>
<ul>
<li>사람 얼굴 quad topology · 눈꺼풀·안와·코·입술·구강·귀·턱 · 목 접합</li>
<li>Identity / Expression basis · 턱·안구 관절 · 연속 UV · 478 대응표</li>
<li>상업 사용·수정·배포 권리 · 원본+라이선스 SHA-256</li>
</ul>
<h2>등록</h2>
<p>후보: <code>dist/v0.7/product/quick_profile/parametric_head_asset_acquisition/V07_QP_PARAMETRIC_HEAD_CANDIDATE_REGISTRY.json</code></p>
<p>후보 0명 → HOLD. 통과 전 얼굴 생성·전신·사람평가 HOLD.</p>
</body></html>
"""
    desk_path = ACQ / "ASSET_ACQUISITION_GATE_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")
    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "verdict": verdict,
                "prior": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
                "candidates": len(candidates),
                "eligible": len(eligible),
                "faceGeneration": "HOLD",
                "production": "NO-GO",
                "desk": str(desk_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "ASSET_ACQUISITION_GATE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
