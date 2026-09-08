"""NURION Parametric Head Candidate A Derived Head v2 Oral Eye Neck Boundary Repair And QA GO."""
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
from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import EXP_G5, sha256_file
from nurion_qp_geometry_face_v2.nurion_derived_head_v2_repair import load_v1_and_repair, write_v2_bundle

COMMAND = "NURION Parametric Head Candidate A Derived Head v2 Oral Eye Neck Boundary Repair And QA GO"
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
V1_DIR = CAND / "derived_v1"
V1_SKIN = V1_DIR / "NURION_DerivedHead_v1_skin.obj"
CORR_V1 = V1_DIR / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json"
PRIOR_RECEIPT = CAND / "V07_QP_DERIVED_HEAD_CLEANUP_QA_RERENDER_RECEIPT.json"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_derived_head_neutral_gray_qa_render.py"
MPFB2_COMMIT = "437dd513888a92399d1d3200d2e80859fae55abc"

GRAY_VIEWS = ("front", "left", "right", "top", "bottom")
WIRE_QUAD_VIEWS = ("front", "left", "right")
MOUTH_VIEWS = ("mouth_open_front", "mouth_open_left", "mouth_open_interior")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"derived_v2_repair_qa_{run_id}"
    cap = out / "captures"
    cap.mkdir(parents=True, exist_ok=True)
    v2_dir = CAND / "derived_v2"
    v2_dir.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        write_json(out / "RECEIPT.json", {"verdict": "SEALED_BASELINE_MUTATION_DENY"})
        return 2
    if not V1_SKIN.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "V1_SKIN_MISSING"})
        return 2

    v1_sha = sha256_file(V1_SKIN)
    result = load_v1_and_repair(V1_DIR, CORR_V1 if CORR_V1.is_file() else None)
    header = [
        "# NURION Derived Head v2 boundary repair from v1",
        f"# Source: makehumancommunity/mpfb2@{MPFB2_COMMIT}",
        f"# PriorV1SkinSha256: {v1_sha}",
        f"# RunId: {run_id}",
    ]
    assets = write_v2_bundle(v2_dir, result, v1_sha, header)

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
            f"--skin-obj={v2_dir / 'NURION_DerivedHead_v2_skin.obj'}",
            f"--oral-tongue={v2_dir / 'NURION_DerivedHead_v2_oral_tongue.obj'}",
            f"--oral-teeth-upper={v2_dir / 'NURION_DerivedHead_v2_oral_teeth_upper.obj'}",
            f"--oral-teeth-lower={v2_dir / 'NURION_DerivedHead_v2_oral_teeth_lower.obj'}",
            f"--rig-joints={v2_dir / 'NURION_DerivedHead_v2_rig_joints.obj'}",
            f"--out-dir={cap}",
            "--label=DERIVED_HEAD_V2",
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
        required.append(cap / f"DERIVED_HEAD_V2_gray_{v}.png")
    for v in WIRE_QUAD_VIEWS:
        required.append(cap / f"DERIVED_HEAD_V2_wire_quad_{v}.png")
    required.append(cap / f"DERIVED_HEAD_V2_wire_tri_note_front.png")
    for v in MOUTH_VIEWS:
        required.append(cap / f"DERIVED_HEAD_V2_{v}.png")
    missing = [str(p.relative_to(ROOT)).replace("\\", "/") for p in required if not p.is_file()]
    if missing:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "missing": missing})
        return 2

    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    for p in required:
        (pres / p.name).write_bytes(p.read_bytes())

    corr_v1 = json.loads(CORR_V1.read_text(encoding="utf-8")) if CORR_V1.is_file() else {}
    inherited = {
        "correspondenceLostInheritedFrom478Gate": 11,
        "unsupportedTotalInherited": 21,
        "remappingNewLossDuringV2Repair": result.meta["correspondenceDelta"].get("remappingNewLoss", 0),
        "unsupportedDelta": result.meta["correspondenceDelta"].get("unsupportedDelta", 0),
        "forcedSingleVertexMapping": "DENY",
    }

    bm = result.boundary_map
    loop_rows = "".join(
        f"<li><code>{e['loopId']}</code> — {e['role']} ({e['edgeCount']} edges)</li>"
        for e in bm.get("entries", [])
    )

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Derived Head v2 Repair QA</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}}
img{{width:100%;background:#111;border-radius:.35rem}}
code{{color:#9cdcfe;font-size:.85rem}}
</style></head><body>
<h1>Derived Head v2 — Boundary Repair QA</h1>
<span class="badge">QA_RERENDER_COMPLETE_AWAITING_HUMAN</span>
<span class="badge">Prior: QA_REWORK_REQUIRED_BOUNDARY_AND_ORAL_TOPOLOGY</span>
<span class="badge">v1 baseline preserved — not discarded</span>
<span class="badge">Production NO-GO</span>
<h3>Mesh hash</h3>
<ul>
<li>v1 skin before: <code>{v1_sha}</code></li>
<li>v2 skin after: <code>{assets['skinSha256']}</code></li>
<li>oral outer loops: {bm.get('oralOuterLoops')} (expected 1)</li>
<li>oral inner loops: {bm.get('oralInnerLoops')} (expected 1)</li>
<li>unique boundary IDs: {bm.get('uniqueLoopIdCount')} / {bm.get('loopCount')}</li>
<li>468 inherited lost/unsupported: 11 / 21 — v2 delta unsupported: {inherited['unsupportedDelta']}</li>
</ul>
<h3>Skin boundary loops (eyelash helper excluded)</h3>
<ul>{loop_rows}</ul>
<h3>Gray skin-only</h3><div class="grid">
<img src="DERIVED_HEAD_V2_gray_front.png"/><img src="DERIVED_HEAD_V2_gray_left.png"/><img src="DERIVED_HEAD_V2_gray_right.png"/>
<img src="DERIVED_HEAD_V2_gray_top.png"/><img src="DERIVED_HEAD_V2_gray_bottom.png"/><img src="DERIVED_HEAD_V2_mouth_open_front.png"/>
</div>
<h3>Wire quad</h3><div class="grid">
<img src="DERIVED_HEAD_V2_wire_quad_front.png"/><img src="DERIVED_HEAD_V2_wire_quad_left.png"/><img src="DERIVED_HEAD_V2_wire_quad_right.png"/>
</div>
<h3>Mouth-open (front / left / interior)</h3><div class="grid">
<img src="DERIVED_HEAD_V2_mouth_open_front.png"/><img src="DERIVED_HEAD_V2_mouth_open_left.png"/><img src="DERIVED_HEAD_V2_mouth_open_interior.png"/>
</div>
<p>Identity fitting / P001 / 사람 유사성: HOLD / DENY</p>
</body></html>
"""
    desk_path = pres / "DERIVED_HEAD_V2_REPAIR_QA_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")

    prior = {}
    if PRIOR_RECEIPT.is_file():
        prior = json.loads(PRIOR_RECEIPT.read_text(encoding="utf-8"))

    receipt = {
        "schema": "NURION_V07_DERIVED_HEAD_V2_REPAIR_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "QA_RERENDER_COMPLETE_AWAITING_HUMAN",
        "priorQaVerdict": prior.get("verdict", "QA_REWORK_REQUIRED_BOUNDARY_AND_ORAL_TOPOLOGY"),
        "assetDisposition": {
            "v1": "REWORK_BASELINE_NOT_DISCARDED",
            "v2": "REPAIR_CANDIDATE_AWAITING_HUMAN",
        },
        "meshHash": {
            "v1SkinBefore": v1_sha,
            "v2SkinAfter": assets["skinSha256"],
        },
        "repair": result.meta,
        "boundaryLoopMap": str((v2_dir / "BOUNDARY_LOOP_MAP.json").relative_to(ROOT)).replace("\\", "/"),
        "inheritedCorrespondenceLimits": inherited,
        "identityFitting": "HOLD_UNTIL_QA_PASS",
        "p001Reapply": "HOLD_UNTIL_QA_PASS",
        "humanSimilarityEval": "DENY",
        "forcedPass": "DENY",
        "production": "NO-GO",
        "reviewDesk": str(desk_path.relative_to(ROOT)).replace("\\", "/"),
        "missing": missing,
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_DERIVED_HEAD_V2_REPAIR_QA_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_DERIVED_HEAD_V2_REPAIR_QA_RECEIPT.json", receipt)
    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": "QA_RERENDER_COMPLETE_AWAITING_HUMAN",
            "derivedHead": "NURION_DerivedHead_v2_skin",
            "v1SkinSha256": v1_sha,
            "v2SkinSha256": assets["skinSha256"],
            "priorQaVerdict": receipt["priorQaVerdict"],
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
                "boundaryLoops": {
                    "count": bm.get("loopCount"),
                    "unique": bm.get("uniqueLoopIdCount"),
                    "oralOuter": bm.get("oralOuterLoops"),
                    "oralInner": bm.get("oralInnerLoops"),
                },
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
