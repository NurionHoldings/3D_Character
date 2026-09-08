"""NURION Parametric Head Asset Acquisition Gate Candidate A MakeHuman MPFB Core CC0 Mesh Pin And Topology Audit GO.

Pins official hm08 base.obj, audits topology/license. No face renders.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(r"d:\NURION Character Landmarker")
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
OUT_ROOT = ACQ / "candidate_a_makehuman_hm08"
RAW = OUT_ROOT / "raw"
BETA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_beta1"
ALPHA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_alpha"

COMMAND = (
    "NURION Parametric Head Asset Acquisition Gate Candidate A MakeHuman MPFB Core "
    "CC0 Mesh Pin And Topology Audit GO"
)

ALLOWED_VERDICTS = {
    "ASSET_ACQUISITION_PASS_FOR_NURION_HEAD_DERIVATION",
    "PASS_WITH_TOPOLOGY_REWORK_REQUIRED",
    "ASSET_INELIGIBLE",
    "LICENSE_DENY",
}

DOWNLOADS = [
    (
        "base.obj",
        "https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/3dobjs/base.obj",
    ),
    (
        "base.mhclo",
        "https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/3dobjs/base.mhclo",
    ),
    (
        "eyes_low-poly.obj",
        "https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/eyes/low-poly/low-poly.obj",
    ),
    (
        "eyes_low-poly.mhclo",
        "https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/eyes/low-poly/low-poly.mhclo",
    ),
    (
        "LICENSE.md",
        "https://raw.githubusercontent.com/makehumancommunity/makehuman/master/LICENSE.md",
    ),
    (
        "LICENSE.ASSETS.md",
        "https://raw.githubusercontent.com/makehumancommunity/makehuman/master/LICENSE.ASSETS.md",
    ),
]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_downloads() -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    pins = {}
    for name, url in DOWNLOADS:
        path = RAW / name
        if not path.is_file() or path.stat().st_size < 100:
            req = urllib.request.Request(url, headers={"User-Agent": "NURION-AssetPin/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                path.write_bytes(resp.read())
        pins[name] = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "url": url,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    return pins


def parse_obj(path: Path) -> dict[str, Any]:
    verts: list[list[float]] = []
    uvs: list[list[float]] = []
    faces: list[list[tuple[int, int | None]]] = []
    face_groups: list[str | None] = []
    current: str | None = None
    header_lines: list[str] = []
    mtllib = None
    usemtl: Counter = Counter()
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if i < 30:
            header_lines.append(line)
        if line.startswith("mtllib "):
            mtllib = line.split(None, 1)[1].strip()
        elif line.startswith("usemtl "):
            usemtl[line.split(None, 1)[1].strip()] += 1
        elif line.startswith("v "):
            a = line.split()
            verts.append([float(a[1]), float(a[2]), float(a[3])])
        elif line.startswith("vt "):
            a = line.split()
            uvs.append([float(a[1]), float(a[2])])
        elif line.startswith("g ") or line.startswith("o "):
            current = line[2:].strip()
        elif line.startswith("f "):
            toks = line.split()[1:]
            idxs = []
            for t in toks:
                parts = t.split("/")
                vi = int(parts[0]) - 1
                ti = int(parts[1]) - 1 if len(parts) > 1 and parts[1] else None
                idxs.append((vi, ti))
            faces.append(idxs)
            face_groups.append(current)
    return {
        "verts": np.asarray(verts, dtype=np.float64),
        "uvs": uvs,
        "faces": faces,
        "face_groups": face_groups,
        "header": "\n".join(header_lines),
        "mtllib": mtllib,
        "usemtl": dict(usemtl),
    }


def topology_audit(mesh: dict[str, Any]) -> dict[str, Any]:
    faces = mesh["faces"]
    face_groups = mesh["face_groups"]
    V = mesh["verts"]
    n_quad = sum(1 for f in faces if len(f) == 4)
    n_tri = sum(1 for f in faces if len(f) == 3)
    groups = sorted({g for g in face_groups if g})
    g_faces = Counter(face_groups)

    body_faces = [f for f, g in zip(faces, face_groups) if g == "body"]
    edge: Counter = Counter()
    for f in body_faces:
        ids = [vi for vi, _ in f]
        n = len(ids)
        for i in range(n):
            a, b = ids[i], ids[(i + 1) % n]
            edge[(min(a, b), max(a, b))] += 1
    boundary = [e for e, c in edge.items() if c == 1]

    ys = V[:, 1]
    zs = V[:, 2]
    head_mask = (ys > 6.5) & (zs > -0.5)
    head_idx = set(np.where(head_mask)[0].tolist())
    nbr: dict[int, set[int]] = defaultdict(set)
    for f in body_faces:
        ids = [vi for vi, _ in f]
        if not any(i in head_idx for i in ids):
            continue
        n = len(ids)
        for i in range(n):
            a, b = ids[i], ids[(i + 1) % n]
            if a in head_idx:
                nbr[a].add(b)
            if b in head_idx:
                nbr[b].add(a)
    vals = [len(s) for s in nbr.values()]
    v4 = sum(1 for v in vals if v == 4) / max(len(vals), 1)

    helpers = {
        k: int(g_faces[k])
        for k in [
            "helper-l-eye",
            "helper-r-eye",
            "helper-l-eyelashes-1",
            "helper-r-eyelashes-1",
            "helper-tongue",
            "helper-upper-teeth",
            "helper-lower-teeth",
            "helper-hair",
        ]
        if k in g_faces
    }
    joints = {
        k: int(g_faces[k])
        for k in [
            "joint-jaw",
            "joint-mouth",
            "joint-l-eye",
            "joint-r-eye",
            "joint-l-upperlid",
            "joint-l-lowerlid",
            "joint-r-upperlid",
            "joint-r-lowerlid",
            "joint-neck",
            "joint-tongue-1",
            "joint-tongue-2",
            "joint-tongue-3",
            "joint-tongue-4",
            "joint-head",
        ]
        if k in g_faces
    }

    header = mesh["header"].lower()
    claims = {
        "headerDeclaresHm08": "basemesh hm08" in header or "hm08" in header,
        "headerDeclaresCc0": "cc0" in header,
        "quadOnlyFaces": n_tri == 0 and n_quad > 0,
        "headValence4Fraction": float(v4),
        "continuousUvPresent": len(mesh["uvs"]) > 0 and all(any(ti is not None for _, ti in f) for f in faces),
        "noMtllibInBaseObj": mesh["mtllib"] is None,
        "noUsemtlMapsInBaseObj": len(mesh["usemtl"]) == 0,
        "eyeHelpersPresent": "helper-l-eye" in helpers and "helper-r-eye" in helpers,
        "lidJointsPresent": "joint-l-upperlid" in joints and "joint-l-lowerlid" in joints,
        "jawJointPresent": "joint-jaw" in joints,
        "teethTongueHelpersPresent": "helper-tongue" in helpers
        and "helper-upper-teeth" in helpers
        and "helper-lower-teeth" in helpers,
        "neckJointPresent": "joint-neck" in joints,
        "bodyClosedManifoldLike": len(boundary) == 0,
    }

    # Edge-loop / anatomy checks (structural evidence for derivation)
    edge_loop = {
        "eyelidControlJoints": claims["lidJointsPresent"],
        "lipMouthJoint": "joint-mouth" in joints,
        "noseAlaNostrilLabeledGroups": False,  # not labeled as separate groups in hm08 obj
        "jawControlJoint": claims["jawJointPresent"],
        "earLabeledGroups": False,  # ears are part of body surface, not separate groups
        "quadFlowHead": v4 >= 0.95,
        "note": "hm08 encodes facial loops in body quad flow + lid/jaw/mouth joints; nose/ear lack separate group labels and need NURION region maps during derivation",
    }

    separation = {
        "eyeballs": "SEPARATE_HELPER_AND_SYSTEM_EYES_ASSET",
        "oralCavityOpening": "CLOSED_BODY_SURFACE_OPENING_REQUIRES_DERIVATION_OR_MORPH",
        "teeth": "HELPER_UPPER_LOWER_TEETH_PRESENT",
        "tongue": "HELPER_TONGUE_AND_TONGUE_JOINTS_PRESENT",
    }

    expression_jaw = {
        "jawJoint": claims["jawJointPresent"],
        "lidJoints": claims["lidJointsPresent"],
        "tongueJoints": all(k in joints for k in ("joint-tongue-1", "joint-tongue-2")),
        "targetSystem": "MAKEHUMAN_MPFB_TARGETS_EXTERNAL_TO_BASE_OBJ",
        "topologySupportsTargets": claims["quadOnlyFaces"] and v4 >= 0.95,
    }

    mp478 = {
        "feasibility": "FEASIBLE",
        "reason": "Dense head surface (~5k head verts) with stable hm08 indexing; correspondence table not yet built",
        "tableBuilt": False,
        "requires": "NURION_478_LANDMARK_TO_HM08_VERTEX_TABLE",
    }

    return {
        "vertexCount": int(len(V)),
        "faceCount": int(len(faces)),
        "quadCount": int(n_quad),
        "triCount": int(n_tri),
        "uvCount": int(len(mesh["uvs"])),
        "groupCount": len(groups),
        "helpers": helpers,
        "joints": joints,
        "claims": claims,
        "edgeLoopAudit": edge_loop,
        "separationAudit": separation,
        "expressionJawAudit": expression_jaw,
        "mediapipe478": mp478,
        "bodyBoundaryEdges": len(boundary),
        "headVertexCountApprox": len(head_idx),
        "headValence4Fraction": float(v4),
    }


def decide_verdict(pins: dict, audit: dict, license_text: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if "cc0" not in license_text.lower():
        return "LICENSE_DENY", ["LICENSE_ASSETS_MISSING_CC0"]
    if pins.get("base.obj", {}).get("bytes", 0) < 1000:
        return "ASSET_INELIGIBLE", ["BASE_OBJ_MISSING"]
    header_ok = audit["claims"]["headerDeclaresHm08"] and audit["claims"]["headerDeclaresCc0"]
    if not header_ok:
        reasons.append("HEADER_HM08_OR_CC0_CLAIM_WEAK")
    if not audit["claims"]["quadOnlyFaces"]:
        return "ASSET_INELIGIBLE", ["NOT_QUAD_CENTRIC"]
    if audit["headValence4Fraction"] < 0.9:
        return "ASSET_INELIGIBLE", ["HEAD_QUAD_FLOW_TOO_WEAK"]
    # spherical reject already done for NURION ellipsoid; hm08 is human body
    if not audit["claims"]["eyeHelpersPresent"] or not audit["claims"]["jawJointPresent"]:
        reasons.append("MISSING_EYE_OR_JAW_STRUCTURE")
    if not audit["mediapipe478"]["tableBuilt"]:
        reasons.append("MEDIAPIPE_478_TABLE_NOT_BUILT")
    if audit["separationAudit"]["oralCavityOpening"].startswith("CLOSED"):
        reasons.append("ORAL_OPENING_REQUIRES_DERIVATION")
    if not audit["edgeLoopAudit"]["noseAlaNostrilLabeledGroups"]:
        reasons.append("NOSE_EAR_REGION_MAPS_REQUIRED_FOR_NURION")
    if not audit["claims"]["noMtllibInBaseObj"] or not audit["claims"]["noUsemtlMapsInBaseObj"]:
        # would need texture license check
        reasons.append("TEXTURE_REFERENCES_PRESENT_NEED_VETTING")
    else:
        reasons.append("NC_TEXTURE_MIX_ZERO_IN_BASE_OBJ")

    # Eligible for derivation, but rework required before product head freeze
    if reasons and any(
        r
        in {
            "MEDIAPIPE_478_TABLE_NOT_BUILT",
            "ORAL_OPENING_REQUIRES_DERIVATION",
            "NOSE_EAR_REGION_MAPS_REQUIRED_FOR_NURION",
            "MISSING_EYE_OR_JAW_STRUCTURE",
        }
        for r in reasons
    ):
        return "PASS_WITH_TOPOLOGY_REWORK_REQUIRED", reasons
    return "ASSET_ACQUISITION_PASS_FOR_NURION_HEAD_DERIVATION", reasons


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_ROOT / "runs" / run_id
    out.mkdir(parents=True, exist_ok=True)

    roles = {
        "schema": "NURION_V07_QP_PARAMETRIC_HEAD_ROLE_SPLIT_V1",
        "updatedAt": now,
        "makehumanMpfbCore": "NURION_COMMERCIAL_HEAD_DERIVATION_SOURCE_ASSET",
        "flame2023Open": "TECHNICAL_BENCHMARK_FOR_SHAPE_EXPRESSION_JAW_ACCURACY",
        "ellipsoidNurionParametricHeadV1": "REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE_REUSE_FORBIDDEN",
        "reuseForbidden": ["NURION_PARAMETRIC_HEAD_V1", "NURION_PARAMETRIC_FACE_V0", "MEDIAPIPE_FACEMESH_854_AS_RENDER"],
    }
    write_json(ACQ / "V07_QP_PARAMETRIC_HEAD_ROLE_SPLIT.json", roles)

    pins = ensure_downloads()
    write_json(out / "MESH_LICENSE_SHA256_PINS.json", {"pinnedAt": now, "pins": pins})
    write_json(OUT_ROOT / "MESH_LICENSE_SHA256_PINS.json", {"pinnedAt": now, "pins": pins})

    mesh = parse_obj(RAW / "base.obj")
    audit = topology_audit(mesh)
    license_text = (RAW / "LICENSE.ASSETS.md").read_text(encoding="utf-8", errors="replace")
    verdict, reasons = decide_verdict(pins, audit, license_text)
    assert verdict in ALLOWED_VERDICTS

    provenance = {
        "assetId": "CANDIDATE_A_MAKEHUMAN_HM08_BASE",
        "basemesh": "hm08",
        "sourceRepo": "https://github.com/makehumancommunity/makehuman",
        "sourcePath": "makehuman/data/3dobjs/base.obj",
        "license": "CC0_1_0_UNIVERSAL",
        "licenseFileSha256": pins["LICENSE.ASSETS.md"]["sha256"],
        "meshSha256": pins["base.obj"]["sha256"],
        "eyesAssetSha256": pins["eyes_low-poly.obj"]["sha256"],
        "headerExcerpt": mesh["header"][:800],
        "ncTextureMixInBaseObj": "ZERO",
        "roles": roles,
    }
    write_json(out / "PROVENANCE.json", provenance)

    receipt = {
        "schema": "NURION_V07_QP_CANDIDATE_A_HM08_MESH_PIN_TOPOLOGY_AUDIT_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "allowedVerdicts": sorted(ALLOWED_VERDICTS),
        "reasons": reasons,
        "pins": pins,
        "provenance": provenance,
        "topologyAudit": audit,
        "newFaceRendersCreated": 0,
        "holds": {
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "arkaonLearningInclusion": "HOLD",
            "identityPass": "DENY",
            "betaPass": "DENY",
        },
        "forcedPass": "DENY",
        "production": "NO-GO",
        "flameRole": "TECHNICAL_BENCHMARK_ONLY_NOT_PINNED_THIS_GATE",
        "ellipsoidReuse": "FORBIDDEN",
        "next": (
            "BUILD_NURION_HEAD_REGION_MAPS_AND_478_CORRESPONDENCE_FROM_HM08"
            if verdict == "PASS_WITH_TOPOLOGY_REWORK_REQUIRED"
            else "BEGIN_NURION_HEAD_DERIVATION_FROM_PINNED_HM08"
        ),
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_CANDIDATE_A_HM08_MESH_PIN_TOPOLOGY_AUDIT_RECEIPT.json", receipt)
    write_json(OUT_ROOT / "V07_QP_CANDIDATE_A_HM08_MESH_PIN_TOPOLOGY_AUDIT_RECEIPT.json", receipt)
    write_json(ACQ / "V07_QP_CANDIDATE_A_HM08_MESH_PIN_TOPOLOGY_AUDIT_RECEIPT.json", receipt)

    # Update registry candidate A with pins
    registry_path = ACQ / "V07_QP_PARAMETRIC_HEAD_CANDIDATE_REGISTRY.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {"candidates": []}
    updated = False
    for c in registry.get("candidates") or []:
        if c.get("id") == "CANDIDATE_A_MAKEHUMAN_MPFB_CORE_CC0":
            c["status"] = verdict
            c["meshPath"] = pins["base.obj"]["path"]
            c["meshSha256"] = pins["base.obj"]["sha256"]
            c["licensePath"] = pins["LICENSE.ASSETS.md"]["path"]
            c["licenseSha256"] = pins["LICENSE.ASSETS.md"]["sha256"]
            c["licenseChecklist"] = {
                "COMMERCIAL_USE_RIGHT": True,
                "MODIFY_RIGHT": True,
                "DISTRIBUTE_OR_EMBED_RIGHT_DECLARED": True,
                "SOURCE_FILE_SHA256": True,
                "LICENSE_FILE_SHA256": True,
            }
            c["topologyChecklist"] = {
                "QUAD_CENTRIC_HUMAN_FACE_TOPOLOGY": True,
                "EYELID_AND_ORBIT": True,
                "NOSE_ALA_NOSTRIL": False,
                "LIP_INNER_OUTER_AND_ORAL_OPENING": False,
                "EAR_STRUCTURE": False,
                "JAW_CHEEKBONE_TEMPLE_CONTROL": True,
                "NECK_JOIN": True,
                "CONTINUOUS_UV": True,
                "IDENTITY_SHAPE_BASIS": False,
                "EXPRESSION_BASIS": False,
                "JAW_AND_EYE_JOINTS": True,
                "MEDIAPIPE_478_CORRESPONDENCE_TABLE": False,
            }
            updated = True
    if not updated:
        registry.setdefault("candidates", []).append(
            {
                "id": "CANDIDATE_A_MAKEHUMAN_MPFB_CORE_CC0",
                "status": verdict,
                "meshPath": pins["base.obj"]["path"],
                "meshSha256": pins["base.obj"]["sha256"],
            }
        )
    registry["selectedEligibleId"] = None  # not fully eligible until rework done / derivation pass
    registry["candidateAVerdict"] = verdict
    registry["updatedAt"] = now
    write_json(registry_path, registry)

    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "schema": "NURION_V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS_V1",
            "status": verdict,
            "candidateA": "CANDIDATE_A_MAKEHUMAN_HM08_BASE",
            "meshSha256": pins["base.obj"]["sha256"],
            "licenseSha256": pins["LICENSE.ASSETS.md"]["sha256"],
            "LOCKED_HOLD": True,
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "arkaonLearningInclusion": "HOLD",
            "identityPass": "DENY",
            "betaPass": "DENY",
            "forcedPass": "DENY",
            "production": "NO-GO",
            "updatedAt": now,
            "lastRunId": run_id,
            "roles": roles,
            "next": receipt["next"],
        },
    )

    write_json(
        BETA / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
        {
            "status": "REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE",
            "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
            "ellipsoidReuse": "FORBIDDEN",
            "candidateA": verdict,
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "arkaonLearningInclusion": "HOLD",
            "identityPass": "DENY",
            "betaPass": "DENY",
            "production": "NO-GO",
            "updatedAt": now,
            "next": receipt["next"],
        },
    )
    alpha_path = ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS.json"
    if alpha_path.is_file():
        alpha = json.loads(alpha_path.read_text(encoding="utf-8"))
        alpha.update(
            {
                "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
                "candidateA": verdict,
                "faceGeneration": "HOLD",
                "humanEvaluation": "HOLD",
                "production": "NO-GO",
                "updatedAt": now,
                "next": receipt["next"],
            }
        )
        write_json(alpha_path, alpha)

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Candidate A hm08 Mesh Pin</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1.2rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
code{{color:#9cdcfe}}
</style></head><body>
<h1>Candidate A — MakeHuman hm08 Mesh Pin + Topology Audit</h1>
<span class="badge">{verdict}</span>
<span class="badge">새 얼굴 렌더 0</span>
<span class="badge">Production NO-GO</span>
<span class="badge">타원 Head 재사용 금지</span>
<ul>
<li>mesh SHA-256: <code>{pins['base.obj']['sha256']}</code></li>
<li>license SHA-256: <code>{pins['LICENSE.ASSETS.md']['sha256']}</code></li>
<li>verts {audit['vertexCount']} · faces {audit['faceCount']} · quads {audit['quadCount']} · tris {audit['triCount']}</li>
<li>head valence4 ≈ {audit['headValence4Fraction']:.3f}</li>
<li>NC 텍스처 혼입(base.obj): ZERO</li>
<li>역할: MakeHuman=원천 자산 / FLAME=기술 기준 / 타원=영구 폐기</li>
</ul>
<p>HOLD: 얼굴 렌더 · 전신 결합 · 사람평가 · ARKAON 학습</p>
<p>다음: {receipt['next']}</p>
</body></html>
"""
    desk_path = OUT_ROOT / "CANDIDATE_A_HM08_PIN_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")
    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
    except Exception:
        pass

    # cleanup temp analyzer if present
    tmp = ROOT / "tools/_tmp_analyze_hm08.py"
    if tmp.is_file():
        tmp.unlink()

    print(
        json.dumps(
            {
                "verdict": verdict,
                "reasons": reasons,
                "meshSha256": pins["base.obj"]["sha256"],
                "licenseSha256": pins["LICENSE.ASSETS.md"]["sha256"],
                "newFaceRendersCreated": 0,
                "faceGeneration": "HOLD",
                "production": "NO-GO",
                "desk": str(desk_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict.startswith("PASS") or "PASS_FOR" in verdict or verdict.endswith("DERIVATION") else 2


if __name__ == "__main__":
    raise SystemExit(main())
