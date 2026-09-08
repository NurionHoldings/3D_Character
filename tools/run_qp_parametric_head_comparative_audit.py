"""NURION Parametric Head Asset Acquisition Gate — Candidate A MakeHuman CC0 vs Candidate B FLAME 2023 Open Comparative Audit GO.

No face renders. License + topology + commercial rights comparative audit only.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
BETA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_beta1"
ALPHA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_alpha"
GATE6 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate6"

COMMAND = (
    "NURION Parametric Head Asset Acquisition Gate Candidate A MakeHuman CC0 "
    "And Candidate B FLAME 2023 Open Comparative Audit GO"
)

LICENSE_SOURCES = [
    {
        "id": "MPFB_LICENSE_MD",
        "url": "https://raw.githubusercontent.com/makehumancommunity/mpfb2/master/LICENSE.md",
        "file": "license_mirrors/MPFB_LICENSE.md",
    },
    {
        "id": "MPFB_LICENSE_ASSETS_MD",
        "url": "https://raw.githubusercontent.com/makehumancommunity/mpfb2/master/LICENSE.ASSETS.md",
        "file": "license_mirrors/MPFB_LICENSE.ASSETS.md",
    },
    {
        "id": "MPFB_FAQ_SELL_MODELS",
        "url": "https://static.makehumancommunity.org/mpfb/faq/can_i_sell_models.html",
        "file": "license_mirrors/MPFB_FAQ_can_i_sell_models.html",
    },
    {
        "id": "CC0_1_0_LEGALCODE",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt",
        "file": "license_mirrors/CC0_1_0_legalcode.txt",
    },
    {
        "id": "FLAME_TEXTURE_LICENSE_PAGE",
        "url": "https://flame.is.tue.mpg.de/texturelicense.html",
        "file": "license_mirrors/FLAME_texturelicense.html",
    },
]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def fetch_and_pin(item: dict, out_root: Path) -> dict:
    path = out_root / item["file"]
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(item["url"], headers={"User-Agent": "NURION-AssetAudit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        path.write_bytes(raw)
        return {
            "id": item["id"],
            "url": item["url"],
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
            "fetchStatus": "OK",
        }
    except Exception as exc:  # noqa: BLE001
        note = f"FETCH_FAIL:{type(exc).__name__}:{exc}"
        path.write_text(note + "\n", encoding="utf-8")
        return {
            "id": item["id"],
            "url": item["url"],
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_text(note),
            "bytes": 0,
            "fetchStatus": "FAIL",
            "error": note,
        }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ACQ / "runs" / f"comparative_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    # --- Preserve ellipsoid as rejected evidence only ---
    rejected = {
        "schema": "NURION_V07_QP_REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE_V1",
        "assetId": "NURION_PARAMETRIC_HEAD_V1",
        "status": "REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE",
        "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
        "identityPass": "DENY",
        "betaPass": "DENY",
        "humanEvaluation": "DENY",
        "production": "NO-GO",
        "wireframeEvidenceRun": "beta1_1_headonly_20260816T093137Z",
        "class": "HIGH_DENSITY_SPHERICAL_ELLIPSOID_TRI_MESH",
        "updatedAt": now,
    }
    write_json(ACQ / "V07_QP_REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE.json", rejected)
    write_json(BETA / "V07_QP_REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE.json", rejected)

    pins = [fetch_and_pin(item, out) for item in LICENSE_SOURCES]
    write_json(out / "LICENSE_MIRROR_SHA256.json", {"pinnedAt": now, "pins": pins})
    pins_by_id = {p["id"]: p for p in pins}

    # --- Candidate comparative cards (no mesh download / no render) ---
    candidate_a = {
        "id": "CANDIDATE_A_MAKEHUMAN_MPFB_CORE_CC0",
        "name": "MakeHuman / MPFB Core",
        "licenseShape": "CC0_1_0_UNIVERSAL_CORE_ASSETS",
        "licenseCode": "MPFB_SOURCE_GPLv3_SEPARATE_FROM_ASSETS",
        "commercialUseCoreAssets": "PASS_DECLARED_CC0",
        "saasOrCharacterGeneratorUse": "PASS_DECLARED_ALLOWED_BUILD_OWN_GENERATOR",
        "attributionRequired": "NO_FOR_CC0_CORE_ASSETS",
        "officialTextureRisk": "THIRD_PARTY_SKINS_MUST_BE_VETTED_SEPARATELY",
        "anatomyFit": "HUMAN_BASE_MESH_WITH_TARGETS_EXPECTED",
        "shapeExpressionJaw": "TARGETS_AND_MODIFIERS_AVAILABLE_QUALITY_TBD",
        "mediapipe478Correspondence": "NOT_BUILT_REQUIRES_NURION_DEV",
        "faceQualityVsPhotoreal": "REQUIRES_EXTRA_DEV",
        "nonCommercialTextureMixRisk": "LOW_IF_ONLY_CC0_CORE_USED",
        "meshPinned": False,
        "licenseMirrors": [
            pins_by_id.get("MPFB_LICENSE_MD"),
            pins_by_id.get("MPFB_LICENSE_ASSETS_MD"),
            pins_by_id.get("MPFB_FAQ_SELL_MODELS"),
            pins_by_id.get("CC0_1_0_LEGALCODE"),
        ],
        "sources": [
            "https://static.makehumancommunity.org/mpfb/faq/can_i_sell_models.html",
            "https://github.com/makehumancommunity/mpfb2/blob/master/LICENSE.md",
            "https://static.makehumancommunity.org/about/license.html",
        ],
        "preRenderGateChecks": {
            "modelLicenseSha256Pinned": bool(pins_by_id.get("MPFB_LICENSE_ASSETS_MD", {}).get("fetchStatus") == "OK"),
            "anatomicalEdgeLoopsVerifiedOnPinnedMesh": False,
            "closedEyelidsOralSeparatedEyeballsVerified": False,
            "shapeExpressionJawParamsVerified": False,
            "mediapipe478CorrespondencePossible": "UNKNOWN_PENDING_MESH",
            "glbCommercialDistributeSaasRights": "PASS_DECLARED_FOR_CC0_CORE_OUTPUT",
            "nonCommercialTextureMix": "DENY_MUST_REMAIN_ZERO",
        },
        "eligibleForImmediatePass": False,
        "blockersToPass": [
            "PIN_BASE_MESH_AND_TARGETS_SHA256",
            "TOPOLOGY_AUDIT_EDGE_LOOPS_EYE_NOSE_MOUTH_JAW",
            "BUILD_OR_VALIDATE_478_CORRESPONDENCE",
            "CONFIRM_NO_NON_CC0_THIRD_PARTY_ASSETS_IN_EXPORT",
        ],
    }

    candidate_b = {
        "id": "CANDIDATE_B_FLAME_2023_OPEN",
        "name": "FLAME 2023 Open",
        "licenseShape": "CC_BY_4_0_MODEL_OPEN",
        "licenseTextureOfficial": "CC_BY_NC_SA_4_0_FORBIDDEN_IN_COMMERCIAL_PRODUCT",
        "commercialUseShape": "PASS_WITH_CC_BY_ATTRIBUTION",
        "saasOrCharacterGeneratorUse": "PASS_SHAPE_WITH_ATTRIBUTION_IF_TERMS_MET",
        "attributionRequired": "YES_CC_BY_4_0",
        "officialTextureRisk": "BLOCKER_DO_NOT_MIX_OFFICIAL_FLAME_TEXTURE",
        "anatomyFit": "STRONG_FACE_SHAPE_EXPRESSION_JAW_STRUCTURE",
        "shapeExpressionJaw": "NATIVE_PARAMETRIC_BASIS",
        "mediapipe478Correspondence": "FEASIBLE_BUT_MUST_BE_BUILT_AND_VALIDATED",
        "faceQualityVsPhotoreal": "STRONG_GEOMETRIC_PRIOR",
        "nonCommercialTextureMixRisk": "HIGH_IF_OFFICIAL_TEXTURE_IMPORTED",
        "meshPinned": False,
        "licenseMirrors": [pins_by_id.get("FLAME_TEXTURE_LICENSE_PAGE")],
        "sources": [
            "https://flame.is.tue.mpg.de/",
            "https://flame.is.tue.mpg.de/texturelicense.html",
        ],
        "preRenderGateChecks": {
            "modelLicenseSha256Pinned": False,  # model license PDF/html requires operator login download
            "anatomicalEdgeLoopsVerifiedOnPinnedMesh": False,
            "closedEyelidsOralSeparatedEyeballsVerified": False,
            "shapeExpressionJawParamsVerified": False,
            "mediapipe478CorrespondencePossible": "LIKELY_YES_PENDING_MESH",
            "glbCommercialDistributeSaasRights": "PASS_SHAPE_ONLY_WITH_ATTRIBUTION_OPERATOR_CONFIRM",
            "nonCommercialTextureMix": "DENY_MUST_REMAIN_ZERO_NO_OFFICIAL_TEXTURE",
        },
        "eligibleForImmediatePass": False,
        "blockersToPass": [
            "OPERATOR_DOWNLOAD_FLAME2023_OPEN_PKL_AND_PIN_SHA256",
            "PIN_MODEL_LICENSE_TEXT_SHA256_FROM_OFFICIAL_PAGE",
            "HARD_DENY_OFFICIAL_FLAME_TEXTURE_IMPORT",
            "TOPOLOGY_AUDIT_ON_PINNED_MESH",
            "BUILD_478_CORRESPONDENCE",
            "PROVIDE_NURION_OR_CC0_COMMERCIAL_ALBEDO_PIPELINE",
        ],
    }

    excluded = {
        "id": "EXCLUDED_REALLUSION_CHARACTER_CREATOR",
        "status": "EXCLUDED_WITHOUT_WRITTEN_CONTRACT",
        "reason": "Current EULA constrains character-generation systems/tools; unsafe as SaaS head base without separate written agreement",
        "sourceNote": "Reallusion EULA — operator legal review required before any reconsideration",
    }

    # Comparative scoring (higher better). No PASS either until mesh pinned + topology audit.
    scores = {
        "CANDIDATE_A_MAKEHUMAN_MPFB_CORE_CC0": {
            "commercialClarity": 5,
            "saasGeneratorFit": 5,
            "anatomyParametricStrength": 3,
            "expressionJawNative": 3,
            "478Effort": 2,
            "textureContaminationControl": 4,
            "attributionOpsBurden": 5,
            "speedToFirstEligibleBase": 4,
            "total": 31,
        },
        "CANDIDATE_B_FLAME_2023_OPEN": {
            "commercialClarity": 4,  # shape OK with BY; texture hard NC trap
            "saasGeneratorFit": 4,
            "anatomyParametricStrength": 5,
            "expressionJawNative": 5,
            "478Effort": 3,
            "textureContaminationControl": 2,  # high process risk
            "attributionOpsBurden": 3,
            "speedToFirstEligibleBase": 3,
            "total": 29,
        },
    }

    recommendation = {
        "primaryTrack": "CANDIDATE_A_MAKEHUMAN_MPFB_CORE_CC0",
        "parallelTrack": "CANDIDATE_B_FLAME_2023_OPEN_SHAPE_ONLY",
        "rationale": [
            "MakeHuman/MPFB core CC0 maximizes commercial SaaS / character-generator clarity and GLB redistribute rights",
            "FLAME 2023 Open shape is strong parametric anatomy but official texture is CC BY-NC-SA — hard DENY mix",
            "Recommended: acquire/pin MakeHuman base mesh first for product path; optionally pin FLAME Open shape for research-grade geometry priors without NC textures",
            "Reallusion/CC excluded without written contract",
            "Rejected ellipsoid remains evidence only — do not iterate renders",
        ],
        "gatePassCondition": "AT_LEAST_ONE_CANDIDATE_MESH_AND_LICENSE_SHA256_PINNED_AND_TOPOLOGY_CHECKLIST_TRUE_AND_NO_NC_TEXTURE",
    }

    # Neither candidate fully passes pre-render gate yet (meshes not pinned)
    verdict = "COMPARATIVE_AUDIT_COMPLETE_HOLD_PENDING_PINNED_ELIGIBLE_MESH"
    face_render = "HOLD_NO_NEW_FACE_RENDER"

    registry = {
        "schema": "NURION_V07_QP_PARAMETRIC_HEAD_CANDIDATE_REGISTRY_V1",
        "updatedAt": now,
        "selectedEligibleId": None,
        "rejectedEvidence": rejected,
        "excluded": [excluded],
        "candidates": [
            {
                "id": candidate_a["id"],
                "class": "MAKEHUMAN_MPFB_CORE_CC0",
                "status": "REGISTERED_PENDING_MESH_PIN",
                "meshPath": None,
                "licensePath": str(out / "license_mirrors/MPFB_LICENSE.ASSETS.md"),
                "correspondence478Path": None,
                "topologyChecklist": {k: False for k in json.loads((ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_CONTRACT.json").read_text(encoding="utf-8"))["requiredTopology"]},
                "licenseChecklist": {
                    "COMMERCIAL_USE_RIGHT": True,
                    "MODIFY_RIGHT": True,
                    "DISTRIBUTE_OR_EMBED_RIGHT_DECLARED": True,
                    "SOURCE_FILE_SHA256": False,
                    "LICENSE_FILE_SHA256": pins_by_id.get("MPFB_LICENSE_ASSETS_MD", {}).get("fetchStatus") == "OK",
                },
                "denyIfTrue": {
                    "isSphericalEllipsoidWithoutFacialEdgeLoops": False,
                    "isMediaPipe854RenderSurface": False,
                    "isResearchOnlyWithoutCommercialRights": False,
                },
            },
            {
                "id": candidate_b["id"],
                "class": "FLAME_2023_OPEN_SHAPE",
                "status": "REGISTERED_PENDING_MESH_PIN",
                "meshPath": None,
                "licensePath": None,
                "correspondence478Path": None,
                "topologyChecklist": {k: False for k in json.loads((ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_CONTRACT.json").read_text(encoding="utf-8"))["requiredTopology"]},
                "licenseChecklist": {
                    "COMMERCIAL_USE_RIGHT": True,
                    "MODIFY_RIGHT": True,
                    "DISTRIBUTE_OR_EMBED_RIGHT_DECLARED": True,
                    "SOURCE_FILE_SHA256": False,
                    "LICENSE_FILE_SHA256": False,
                },
                "denyIfTrue": {
                    "isSphericalEllipsoidWithoutFacialEdgeLoops": False,
                    "isMediaPipe854RenderSurface": False,
                    "isResearchOnlyWithoutCommercialRights": False,
                    "officialFlameTextureImported": None,
                },
                "hardDeny": ["OFFICIAL_FLAME_TEXTURE_CC_BY_NC_SA"],
            },
        ],
        "note": "Comparative audit registered candidates. No eligible mesh pinned yet. No face renders until Acquisition Gate PASS.",
    }
    write_json(ACQ / "V07_QP_PARAMETRIC_HEAD_CANDIDATE_REGISTRY.json", registry)

    receipt = {
        "schema": "NURION_V07_QP_PARAMETRIC_HEAD_COMPARATIVE_AUDIT_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "faceRender": face_render,
        "newFaceRendersCreated": 0,
        "rejectedSphere": rejected,
        "candidateA": candidate_a,
        "candidateB": candidate_b,
        "excluded": excluded,
        "scores": scores,
        "recommendation": recommendation,
        "licensePins": pins,
        "preRenderValidationRequired": [
            "MODEL_AND_LICENSE_SHA256_PINNED",
            "ANATOMICAL_EDGE_LOOPS_EYE_NOSE_MOUTH_JAW",
            "CLOSED_EYELIDS_ORAL_SEPARATED_EYEBALLS",
            "SHAPE_EXPRESSION_JAW_PARAMS",
            "MEDIAPIPE_478_CORRESPONDENCE_FEASIBILITY",
            "GLB_COMMERCIAL_DISTRIBUTE_AND_SAAS_RIGHTS",
            "NONCOMMERCIAL_TEXTURE_MIX_ZERO",
        ],
        "holds": {
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "DENY",
            "identityPass": "DENY",
            "betaPass": "DENY",
            "arkaonLearningInclusion": "HOLD",
        },
        "forcedPass": "DENY",
        "production": "NO-GO",
        "next": "PIN_CANDIDATE_A_MAKEHUMAN_BASE_MESH_SHA256_THEN_TOPOLOGY_AUDIT_OR_PIN_FLAME_OPEN_SHAPE_WITHOUT_NC_TEXTURE",
    }
    raw = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_PARAMETRIC_HEAD_COMPARATIVE_AUDIT_RECEIPT.json", receipt)
    write_json(ACQ / "V07_QP_PARAMETRIC_HEAD_COMPARATIVE_AUDIT_RECEIPT.json", receipt)

    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "schema": "NURION_V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS_V1",
            "status": verdict,
            "prior": "ASSET_INELIGIBLE_PARAMETRIC_HEAD_NOT_AVAILABLE",
            "rejectedSphere": "REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE",
            "LOCKED_HOLD": True,
            "updatedAt": now,
            "lastRunId": run_id,
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "DENY",
            "identityPass": "DENY",
            "betaPass": "DENY",
            "forcedPass": "DENY",
            "production": "NO-GO",
            "primaryTrack": recommendation["primaryTrack"],
            "parallelTrack": recommendation["parallelTrack"],
            "next": receipt["next"],
        },
    )

    write_json(
        BETA / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
        {
            "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS_V1",
            "status": "REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE",
            "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
            "assetAcquisition": verdict,
            "LOCKED": True,
            "updatedAt": now,
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "DENY",
            "identityPass": "DENY",
            "betaPass": "DENY",
            "forcedPass": "DENY",
            "production": "NO-GO",
            "arkaonLearningInclusion": "HOLD",
            "next": receipt["next"],
        },
    )

    alpha_path = ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS.json"
    if alpha_path.is_file():
        alpha = json.loads(alpha_path.read_text(encoding="utf-8"))
        alpha.update(
            {
                "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
                "parametricHeadAsset": "REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE",
                "faceGeneration": "HOLD",
                "humanEvaluation": "DENY",
                "identityPass": "DENY",
                "betaPass": "DENY",
                "production": "NO-GO",
                "updatedAt": now,
                "next": receipt["next"],
            }
        )
        write_json(alpha_path, alpha)

    write_json(
        GATE6 / "V07_QP_GF_FACE_V2_GATE6_COMMERCIAL_MODEL_REGISTRY.json",
        {
            "schema": "NURION_V07_QP_GF_FACE_V2_GATE6_COMMERCIAL_MODEL_REGISTRY_V2",
            "updatedAt": now,
            "commercialClearance": "DENY_PENDING_PINNED_ELIGIBLE_HEAD",
            "rejected": ["NURION_PARAMETRIC_HEAD_V1"],
            "excluded": ["REALLUSION_CHARACTER_CREATOR_WITHOUT_WRITTEN_CONTRACT"],
            "candidatesUnderAudit": [candidate_a["id"], candidate_b["id"]],
            "primaryTrack": recommendation["primaryTrack"],
            "production": "NO-GO",
        },
    )

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Head Asset Comparative Audit</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1.2rem;line-height:1.45}}
.badge{{display:inline-block;margin:.2rem .35rem .2rem 0;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #444;padding:.55rem .7rem;vertical-align:top}}
th{{background:#222}}
</style></head><body>
<h1>Candidate A MakeHuman CC0 vs Candidate B FLAME 2023 Open</h1>
<span class="badge">{verdict}</span>
<span class="badge">새 얼굴 렌더 0</span>
<span class="badge">타원 Head = REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE</span>
<span class="badge">Production NO-GO</span>
<h2>비교</h2>
<table>
<tr><th>항목</th><th>A MakeHuman/MPFB Core</th><th>B FLAME 2023 Open</th></tr>
<tr><td>형상 라이선스</td><td>CC0 코어 자산</td><td>CC-BY-4.0 (귀속)</td></tr>
<tr><td>공식 텍스처</td><td>코어 skins CC0 / 3rd-party 별도 검증</td><td>CC BY-NC-SA → 상업 혼입 금지</td></tr>
<tr><td>SaaS·캐릭터 생성기</td><td>명시적으로 자체 생성기 구축 가능</td><td>형상 OK(귀속), 텍스처 NC 트랩</td></tr>
<tr><td>해부·표정·턱</td><td>베이스+타깃 (품질 추가 개발)</td><td>강점 (native parametric)</td></tr>
<tr><td>478 대응</td><td>별도 개발 필요</td><td>가능하나 구축·검증 필요</td></tr>
<tr><td>점수(내부)</td><td>{scores[candidate_a['id']]['total']}</td><td>{scores[candidate_b['id']]['total']}</td></tr>
</table>
<p><b>권장 primary:</b> {recommendation['primaryTrack']}<br/>
<b>병렬:</b> {recommendation['parallelTrack']} (공식 텍스처 없이 형상만)</p>
<p>Reallusion/Character Creator: 서면 계약 없이 제외.</p>
<p>PASS 조건: 메시+라이선스 SHA-256 고정 + topology 체크리스트 + NC 텍스처 0. 그 전 얼굴 렌더 HOLD.</p>
</body></html>
"""
    desk_path = ACQ / "COMPARATIVE_AUDIT_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")
    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "verdict": verdict,
                "rejectedSphere": "REJECTED_NON_PARAMETRIC_SPHERE_EVIDENCE",
                "primaryTrack": recommendation["primaryTrack"],
                "parallelTrack": recommendation["parallelTrack"],
                "newFaceRendersCreated": 0,
                "faceGeneration": "HOLD",
                "production": "NO-GO",
                "desk": str(desk_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 2  # HOLD — not PASS until mesh pinned


if __name__ == "__main__":
    raise SystemExit(main())
