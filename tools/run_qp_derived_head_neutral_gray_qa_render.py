"""NURION Parametric Head Candidate A Neutral Gray QA Render Front Side Wireframe GO."""
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
from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import EXPECTED_HM08_SHA, EXP_G5, sha256_file

COMMAND = "NURION Parametric Head Candidate A Neutral Gray QA Render Front Side Wireframe GO"
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
DERIVED = CAND / "derived" / "NURION_DerivedHead_v0.obj"
TOPOLOGY_RECEIPT = CAND / "V07_QP_DERIVED_HEAD_TOPOLOGY_GATE_RECEIPT.json"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_derived_head_neutral_gray_qa_render.py"

GRAY_VIEWS = ("front", "left", "right", "top", "bottom")
WIRE_VIEWS = ("front", "left", "right")
MOUTH_VIEWS = ("mouth_open_front", "mouth_open_bottom")

QA_CHECKLIST = [
    "NOT_SPHERE_OR_ELLIPSOID_ANATOMICAL_CRANIOFACIAL",
    "FOREHEAD_NOSE_MOUTH_CHIN_PROTRUSION_FRONT_AND_SIDES",
    "EYELID_CLOSED_LOOPS_AND_EYE_SOCKETS",
    "LIP_SEAL_AND_ORAL_CAVITY_OPEN",
    "EAR_ALA_JAW_EDGE_FLOW",
    "NECK_CUT_AND_10_BOUNDARY_LOOPS_INTENT",
    "WIREFRAME_STRETCH_POLES_ASYMMETRY",
]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"neutral_gray_qa_{run_id}"
    cap = out / "captures"
    cap.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        write_json(out / "RECEIPT.json", {"verdict": "SEALED_BASELINE_MUTATION_DENY"})
        return 2
    if not DERIVED.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "DERIVED_HEAD_MISSING"})
        return 2
    if not TOPOLOGY_RECEIPT.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "TOPOLOGY_GATE_RECEIPT_MISSING"})
        return 2

    topo = json.loads(TOPOLOGY_RECEIPT.read_text(encoding="utf-8"))
    if topo.get("verdict") != "PASS_DERIVED_HEAD_TOPOLOGY_PENDING_QA_RENDER":
        write_json(out / "RECEIPT.json", {"verdict": "ABSTAIN", "reason": "TOPOLOGY_GATE_NOT_READY"})
        return 2

    derived_sha = sha256_file(DERIVED)
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
            f"--obj={DERIVED}",
            f"--out-dir={cap}",
            "--label=DERIVED_HEAD",
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
        required.append(cap / f"DERIVED_HEAD_gray_{v}.png")
    for v in WIRE_VIEWS:
        required.append(cap / f"DERIVED_HEAD_wire_{v}.png")
    for v in MOUTH_VIEWS:
        required.append(cap / f"DERIVED_HEAD_{v}.png")
    missing = [str(p.relative_to(ROOT)).replace("\\", "/") for p in required if not p.is_file()]
    if missing:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "missing": missing})
        return 2

    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    for p in required:
        dst = pres / p.name
        dst.write_bytes(p.read_bytes())

    corr_limits = topo.get("correspondenceTransfer") or {}
    inherited = {
        "correspondenceLost": corr_limits.get("lostMappings", 11),
        "unsupportedTotal": (corr_limits.get("typeCounts") or {}).get("UNSUPPORTED", 21),
        "forcedSingleVertexMapping": "DENY",
        "note": "Inherited from Region/478 Gate — not cleared by QA render",
    }

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Neutral Gray QA — Derived Head</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}}
img{{width:100%;background:#111;border-radius:.35rem}}
h3{{margin:1rem 0 .4rem}}
</style></head><body>
<h1>Neutral Gray QA — NURION DerivedHead v0</h1>
<span class="badge">QA_RENDER_COMPLETE_AWAITING_HUMAN</span>
<span class="badge">텍스처·헤어·미화·사진 DENY</span>
<span class="badge">468 손실 11 / UNSUPPORTED 21 계승</span>
<span class="badge">Production NO-GO</span>
<h3>Gray</h3><div class="grid">
<img src="DERIVED_HEAD_gray_front.png"/><img src="DERIVED_HEAD_gray_left.png"/><img src="DERIVED_HEAD_gray_right.png"/>
<img src="DERIVED_HEAD_gray_top.png"/><img src="DERIVED_HEAD_gray_bottom.png"/><img src="DERIVED_HEAD_mouth_open_front.png"/>
</div>
<h3>Wireframe</h3><div class="grid">
<img src="DERIVED_HEAD_wire_front.png"/><img src="DERIVED_HEAD_wire_left.png"/><img src="DERIVED_HEAD_wire_right.png"/>
</div>
<h3>Mouth interior</h3><div class="grid"><img src="DERIVED_HEAD_mouth_open_bottom.png"/></div>
<h3>Human checklist</h3>
<ul>
<li>구·타원이 아닌 해부학적 두개·안면인가</li>
<li>정면/측면 이마·코·입·턱 돌출</li>
<li>눈꺼풀 폐곡선·안구 소켓</li>
<li>입술 폐합·구강 내부 개방</li>
<li>귀·콧방울·턱선 edge flow</li>
<li>목 절단·10 boundary loop 의도</li>
<li>와이어 늘어짐·pole·비대칭</li>
</ul>
<p>QA 통과 전 Identity fitting / P001 재적용 HOLD.</p>
</body></html>
"""
    desk_path = pres / "NEUTRAL_GRAY_QA_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")

    receipt = {
        "schema": "NURION_V07_DERIVED_HEAD_NEUTRAL_GRAY_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "QA_RENDER_COMPLETE_AWAITING_HUMAN",
        "priorTopologyVerdict": topo.get("verdict"),
        "derivedAsset": {
            "path": str(DERIVED.relative_to(ROOT)).replace("\\", "/"),
            "sha256": derived_sha,
        },
        "hm08Sha256Unchanged": EXPECTED_HM08_SHA,
        "inheritedCorrespondenceLimits": inherited,
        "allowedOutputs": {
            "neutralGray": list(GRAY_VIEWS),
            "wireframe": list(WIRE_VIEWS),
            "mouthOpen": list(MOUTH_VIEWS),
        },
        "denied": ["TEXTURE", "HAIR", "BEAUTIFICATION", "PHOTO_PROJECTION"],
        "humanQaChecklist": QA_CHECKLIST,
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
    write_json(out / "V07_QP_DERIVED_HEAD_NEUTRAL_GRAY_QA_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_DERIVED_HEAD_NEUTRAL_GRAY_QA_RECEIPT.json", receipt)
    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": "QA_RENDER_COMPLETE_AWAITING_HUMAN",
            "derivedHead": "NURION_DerivedHead_v0",
            "derivedSha256": derived_sha,
            "identityFitting": "HOLD",
            "p001Reapply": "HOLD",
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
                "outputs": len(required),
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
