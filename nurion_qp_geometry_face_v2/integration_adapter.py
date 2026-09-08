"""Isolated Gate 4 adapter: Geometry-First v2 beside frozen Identity Core.

Does not mutate tools/nurion_quick_profile_core.py or the Gate 3 runner.
Legacy skin/center heuristics are never used as an existence gate on this path.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from .analyzer import AnalysisResult, DenseFaceBackend, GeometryFirstAnalyzer
from .gate4_contract import GATE4_CONTRACT

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from nurion_quick_profile_core import (  # noqa: E402
    DISCLOSURE,
    USER_DISCLOSURE_KO,
    analyze_image,
    recommend_body,
    sha256_file,
    sha256_obj,
)


ID_AXES = [
    "ID_FaceOutline",
    "ID_Eye",
    "ID_Nose",
    "ID_Mouth",
    "ID_Jaw",
    "ID_Cheek",
    "ID_Hairline",
]


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _round6(x: float) -> float:
    return float(f"{x:.6f}")


@dataclass(frozen=True)
class AdapterInput:
    case_id: str
    image_path: Path
    height_cm: float
    weight_kg: float
    declared_pose: str = "FRONTAL"


def _size_blur_precheck(image_path: Path) -> list[str]:
    """Retain blur/size gates only; never skin/center existence."""
    reasons: list[str] = []
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    if min(w, h) < 64:
        reasons.append("SEVERE_BLUR_OR_OCCLUSION")
        return reasons
    edges = np.asarray(img.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    if float(edges.var()) < 500.0:
        reasons.append("SEVERE_BLUR_OR_OCCLUSION")
    return reasons


def _geometry_identity_preview(geometry: dict[str, float], image_sha: str) -> dict[str, Any]:
    """Optional ratio map — not legacy meanRGB/occupancy hash Identity Core."""
    seed = hashlib.sha256(f"GF_V2:{image_sha}".encode()).digest()

    def u(i: int) -> float:
        return seed[i] / 255.0

    fw = float(geometry.get("FACE_WIDTH_TO_LENGTH", 0.75))
    iod = float(geometry.get("INTEROCULAR_TO_FACE_WIDTH", 0.35))
    nose = float(geometry.get("NOSE_LENGTH_TO_FACE_LENGTH", 0.3))
    mouth = float(geometry.get("MOUTH_WIDTH_TO_FACE_WIDTH", 0.4))
    jaw = float(geometry.get("JAW_WIDTH_TO_CHEEKBONE_WIDTH", 0.85))
    forehead = float(geometry.get("FOREHEAD_HEIGHT_TO_FACE_LENGTH", 0.3))
    asym = float(geometry.get("NATURAL_LEFT_RIGHT_ASYMMETRY", 0.05))
    values = {
        "ID_FaceOutline": _round6(_clamp01(0.25 + 0.55 * fw + 0.05 * u(0))),
        "ID_Eye": _round6(_clamp01(0.2 + 0.7 * iod + 0.05 * u(1))),
        "ID_Nose": _round6(_clamp01(0.2 + 0.7 * nose + 0.05 * u(2))),
        "ID_Mouth": _round6(_clamp01(0.2 + 0.7 * mouth + 0.05 * u(3))),
        "ID_Jaw": _round6(_clamp01(0.2 + 0.7 * jaw + 0.05 * u(4))),
        "ID_Cheek": _round6(_clamp01(0.25 + 0.5 * (1.0 - asym) + 0.05 * u(5))),
        "ID_Hairline": _round6(_clamp01(0.25 + 0.55 * forehead + 0.05 * u(6))),
    }
    return {
        "mode": "GEOMETRY_FIRST_ISOLATED_PREVIEW",
        "label": "GEOMETRY_RATIO_MAP_NOT_LEGACY_HASH",
        "axes": ID_AXES,
        "values": values,
        "method": "NORMALIZED_LANDMARK_RATIOS",
        "replacesFrozenIdentityCore": "DENY",
        "autoClaimFaceRecognition": "DENY",
        "sourceGeometryKeys": sorted(geometry.keys()),
    }


def compare_legacy_heuristic(image_path: Path, declared_pose: str, params: dict) -> dict[str, Any]:
    """Read-only comparison against frozen Identity Core analyzer."""
    legacy = analyze_image(image_path, declared_pose, params)
    return {
        "role": "READ_ONLY_COMPARISON_ONLY",
        "verdict": legacy["verdict"],
        "reasons": list(legacy.get("reasons", [])),
        "analyzer": legacy.get("analyzer"),
        "faceLikeOccupancy": legacy.get("faceLikeOccupancy"),
        "usedAsExistenceGateOnAdapterPath": "DENY",
    }


class GeometryFirstIntegrationAdapter:
    """Isolated Quick Profile face gate using Geometry-First v2."""

    def __init__(self, backend: DenseFaceBackend):
        self.backend = backend
        self.analyzer = GeometryFirstAnalyzer(backend)
        self.contract = GATE4_CONTRACT

    def analyze(
        self,
        bundle: AdapterInput,
        params: dict,
        *,
        include_legacy_comparison: bool = True,
    ) -> dict[str, Any]:
        image_path = Path(bundle.image_path)
        if not image_path.is_file():
            return self._abstain(bundle, ["INPUT_CONTRACT_INCOMPLETE"], None, None)

        precheck = _size_blur_precheck(image_path)
        body = recommend_body(bundle.height_cm, bundle.weight_kg, params)
        legacy = (
            compare_legacy_heuristic(image_path, bundle.declared_pose, params)
            if include_legacy_comparison
            else None
        )

        if precheck:
            return self._abstain(bundle, precheck, legacy, body)

        if body["verdict"] == "ABSTAIN":
            return self._abstain(bundle, list(body.get("reasons", [])), legacy, body)

        rgb = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.uint8)
        geometry_result = self.analyzer.analyze(rgb)
        image_sha = sha256_file(image_path)

        if geometry_result.outcome == "ABSTAIN_RECAPTURE":
            reasons = ["GEOMETRY_ABSTAIN_RECAPTURE"]
            if "BRANCH_CONFLICT" in geometry_result.disclosures:
                reasons.append("BRANCH_CONFLICT")
            if "NO_VALID_DENSE_GEOMETRY" in geometry_result.disclosures:
                reasons.append("NO_VALID_DENSE_GEOMETRY")
            return self._abstain(
                bundle,
                reasons,
                legacy,
                body,
                geometry_result=geometry_result,
                image_sha=image_sha,
            )

        # Heuristic false-abstain must not block when geometry succeeded.
        identity = None
        if geometry_result.outcome == "GEOMETRY_CONFIDENT" and geometry_result.geometry:
            identity = _geometry_identity_preview(geometry_result.geometry, image_sha)

        out: dict[str, Any] = {
            "caseId": bundle.case_id,
            "adapter": "GEOMETRY_FIRST_V2_ISOLATED",
            "verdict": (
                "GEOMETRY_REVIEW_REQUIRED"
                if geometry_result.outcome == "GEOMETRY_REVIEW_REQUIRED"
                else "GEOMETRY_FIRST_DRAFT_READY"
            ),
            "abstainReasons": [],
            "heuristicExistenceGate": "BYPASSED",
            "legacyHeuristicComparison": legacy,
            "geometryAnalysis": _geometry_payload(geometry_result),
            "identityLayer": identity,
            "identityCoreReplacement": "DENY",
            "bodyRecommendation": {
                "verdict": body["verdict"],
                "bmi": body.get("bmi"),
                "recommendedPreset": body.get("recommendedPreset"),
                "bodyMorphValues": body.get("bodyMorphValues"),
                "label": body.get("label"),
            },
            "characterGeneration": "DENY",
            "partialResultGeneration": "DENY",
            "disclosure": {
                **DISCLOSURE,
                "faceAnalyzer": "GEOMETRY_FIRST_V2_ISOLATED_ADAPTER",
                "legacyIdentityCore": "NOT_REPLACED",
            },
            "userFacingDisclosureKo": USER_DISCLOSURE_KO,
            "countsAsGate8ParticipantEvidence": "DENY",
            "participantEvidenceCounting": "DENY",
            "production": "NO-GO",
            "imageSha256": image_sha,
            "backend": self.backend.name,
        }
        out["adapterFingerprintSha256"] = sha256_obj(
            {k: v for k, v in out.items() if k != "adapterFingerprintSha256"}
        )
        return out

    def _abstain(
        self,
        bundle: AdapterInput,
        reasons: list[str],
        legacy: dict | None,
        body: dict | None,
        *,
        geometry_result: AnalysisResult | None = None,
        image_sha: str | None = None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "caseId": bundle.case_id,
            "adapter": "GEOMETRY_FIRST_V2_ISOLATED",
            "verdict": "ABSTAIN",
            "abstainReasons": sorted(set(reasons)),
            "heuristicExistenceGate": "BYPASSED",
            "legacyHeuristicComparison": legacy,
            "geometryAnalysis": None if geometry_result is None else _geometry_payload(geometry_result),
            "identityLayer": None,
            "identityCoreReplacement": "DENY",
            "bodyRecommendation": None
            if body is None
            else {
                "verdict": body.get("verdict"),
                "reasons": body.get("reasons", []),
                "bmi": body.get("bmi"),
                "recommendedPreset": None,
                "bodyMorphValues": None,
                "label": body.get("label"),
                "generativeApplication": "DENY",
            },
            "characterGeneration": "DENY",
            "partialResultGeneration": "DENY",
            "disclosure": {
                **DISCLOSURE,
                "faceAnalyzer": "GEOMETRY_FIRST_V2_ISOLATED_ADAPTER",
                "legacyIdentityCore": "NOT_REPLACED",
            },
            "userFacingDisclosureKo": USER_DISCLOSURE_KO,
            "countsAsGate8ParticipantEvidence": "DENY",
            "participantEvidenceCounting": "DENY",
            "production": "NO-GO",
            "imageSha256": image_sha,
            "backend": self.backend.name,
        }
        out["adapterFingerprintSha256"] = sha256_obj(
            {k: v for k, v in out.items() if k != "adapterFingerprintSha256"}
        )
        return out


def _geometry_payload(result: AnalysisResult) -> dict[str, Any]:
    return {
        "outcome": result.outcome,
        "successfulBranches": list(result.successful_branches),
        "landmarkShape": None if result.landmarks is None else list(result.landmarks.shape),
        "geometry": result.geometry,
        "pose": result.pose,
        "medianBranchDisagreement": result.median_branch_disagreement,
        "p95BranchDisagreement": result.p95_branch_disagreement,
        "skinPolicy": result.skin_policy,
        "disclosures": list(result.disclosures),
    }


def load_gate2_params(root: Path | None = None) -> dict:
    base = ROOT if root is None else Path(root)
    path = base / "dist/v0.7/product/quick_profile/gate2/V07_QP_GATE2_PARAMETERS.json"
    return json.loads(path.read_text(encoding="utf-8"))
