"""NURION Quick Profile core — single-image pipeline (Gate 2).

Deterministic, disclosure-honest estimates. Not Gate 8 participant evidence.
Does not mutate sealed CCS baselines.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ID_AXES = [
    "ID_FaceOutline",
    "ID_Eye",
    "ID_Nose",
    "ID_Mouth",
    "ID_Jaw",
    "ID_Cheek",
    "ID_Hairline",
]

POLISHED = {
    "BEAU_Skin": 0.35,
    "BEAU_Symmetry": 0.25,
    "BEAU_Jawline": 0.3,
    "BEAU_Eye": 0.28,
    "BEAU_Smile": 0.22,
    "BEAU_AgeImpression": 0.15,
}

BODY_PRESETS = {
    "SLIM": {
        "BODY_Height": 0.05,
        "BODY_Shoulder": -0.15,
        "BODY_Torso": -0.1,
        "BODY_Waist": -0.35,
        "BODY_Pelvis": -0.1,
        "BODY_Muscle": -0.1,
        "BODY_Fat": -0.4,
        "BODY_LimbLength": 0.1,
        "BODY_HeadSize": 0.0,
    },
    "BALANCED": {
        "BODY_Height": 0.0,
        "BODY_Shoulder": 0.0,
        "BODY_Torso": 0.0,
        "BODY_Waist": 0.0,
        "BODY_Pelvis": 0.0,
        "BODY_Muscle": 0.0,
        "BODY_Fat": 0.0,
        "BODY_LimbLength": 0.0,
        "BODY_HeadSize": 0.0,
    },
    "SOFT": {
        "BODY_Height": 0.0,
        "BODY_Shoulder": 0.05,
        "BODY_Torso": 0.15,
        "BODY_Waist": 0.2,
        "BODY_Pelvis": 0.15,
        "BODY_Muscle": -0.2,
        "BODY_Fat": 0.45,
        "BODY_LimbLength": 0.0,
        "BODY_HeadSize": 0.05,
    },
}

SILENT_PRESETS = [
    "NATURAL_IDLE",
    "EYE_CONTACT",
    "SOFT_SMILE",
    "LIGHT_GREETING",
    "WELCOME_GESTURE",
    "CONSULTATION_INVITE",
    "SCREEN_CTA_POINTING",
    "NATURAL_REST_RETURN",
]

ARKAON_BIND = [
    "ARKAON_WELCOME",
    "ARKAON_START_CTA",
    "ARKAON_PROGRESS",
    "ARKAON_CONSULTATION_INVITE",
]

DEFAULT_HAIR = "SHORT_NEAT_01"
DEFAULT_OUTFIT = "BUSINESS_SUIT_01"

DISCLOSURE = {
    "face": "SINGLE_IMAGE_IDENTITY_ESTIMATE",
    "body": "HEIGHT_WEIGHT_CANONICAL_RECOMMENDATION",
    "back": "UNOBSERVED_STANDARD_COMPLETION",
    "resultGrade": "QUICK_PROFILE_PREVIEW",
    "faceAuthentication": "OUT_OF_SCOPE",
    "claimFullRealBodyReconstruction": "DENY",
}

USER_DISCLOSURE_KO = (
    "얼굴 사진을 중심으로 개인화했으며, 체형과 보이지 않는 부분에는 "
    "NURION 추천 표준 모델이 적용되었습니다. 추가 사진으로 언제든 정밀화할 수 있습니다."
)


@dataclass
class InputBundle:
    caseId: str
    imagePath: str
    heightCm: float
    weightKg: float
    declaredPose: str = "FRONTAL"


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _round6(x: float) -> float:
    return float(f"{x:.6f}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def analyze_image(image_path: Path, declared_pose: str, params: dict) -> dict:
    """Quality / eligibility analyzer. Heuristic face-like region; not authentication."""
    pq = params["photoQualityCriteria"]
    ic = params["inputContract"]
    reasons: list[str] = []
    verdict = "ELIGIBLE"

    if declared_pose not in pq["acceptedPose"]:
        reasons.append("POSE_OUTSIDE_FRONTAL_OR_WEAK_45")
        verdict = "ABSTAIN"

    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    arr = np.asarray(img, dtype=np.float32)

    if w < 64 or h < 64:
        reasons.append("SEVERE_BLUR_OR_OCCLUSION")
        verdict = "ABSTAIN"

    # Laplacian-ish blur proxy via PIL edges
    edges = np.asarray(img.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    edge_var = float(edges.var())
    if edge_var < 500.0:
        reasons.append("SEVERE_BLUR_OR_OCCLUSION")
        verdict = "ABSTAIN"

    # Skin-tone heuristic for face-like occupancy (center-biased)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    skin = (r > 95) & (g > 40) & (b > 20) & (r > g) & (r > b) & ((r - g) > 15)
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2.0, w / 2.0
    center_mask = ((yy - cy) ** 2 / (0.35 * h) ** 2 + (xx - cx) ** 2 / (0.28 * w) ** 2) <= 1.0
    face_like = skin & center_mask
    occupancy = float(face_like.mean()) if face_like.size else 0.0
    if occupancy < float(pq["minimumFaceOccupancyOfFrameApprox"]):
        reasons.append("NO_DETECTABLE_FACE")
        verdict = "ABSTAIN"

    # Dual-peak crude check: require both halves strong AND a clear mid gap
    left = float(face_like[:, : w // 2].mean()) if w > 2 else 0.0
    right = float(face_like[:, w // 2 :].mean()) if w > 2 else 0.0
    mid = float(face_like[:, w // 2 - max(1, w // 20) : w // 2 + max(1, w // 20)].mean()) if w > 40 else 1.0
    if left > 0.15 and right > 0.15 and mid < min(left, right) * 0.35:
        reasons.append("MULTIPLE_DOMINANT_FACES")
        verdict = "ABSTAIN"

    mean_rgb = [float(arr[:, :, i].mean() / 255.0) for i in range(3)]
    return {
        "verdict": verdict,
        "reasons": sorted(set(reasons)),
        "width": w,
        "height": h,
        "edgeVariance": _round6(edge_var),
        "faceLikeOccupancy": _round6(occupancy),
        "meanRgb": [_round6(x) for x in mean_rgb],
        "declaredPose": declared_pose,
        "imageSha256": sha256_file(image_path),
        "faceAuthentication": "OUT_OF_SCOPE",
        "analyzer": "HEURISTIC_SKIN_CENTER_EDGE_NOT_ML_LANDMARKER",
    }


def recommend_body(height_cm: float, weight_kg: float, params: dict) -> dict:
    ic = params["inputContract"]
    reasons: list[str] = []
    if not (ic["heightCmMin"] <= height_cm <= ic["heightCmMax"]):
        reasons.append("HEIGHT_OR_WEIGHT_OUT_OF_RANGE")
    if not (ic["weightKgMin"] <= weight_kg <= ic["weightKgMax"]):
        reasons.append("HEIGHT_OR_WEIGHT_OUT_OF_RANGE")

    if reasons:
        return {
            "verdict": "ABSTAIN",
            "reasons": sorted(set(reasons)),
            "bmi": None,
            "recommendedPreset": None,
            "bodyMorphValues": None,
            "label": "HEIGHT_WEIGHT_CANONICAL_RECOMMENDATION",
        }

    bmi = weight_kg / ((height_cm / 100.0) ** 2)
    if bmi < 20.0:
        preset = "SLIM"
    elif bmi > 25.0:
        preset = "SOFT"
    else:
        preset = "BALANCED"

    if preset not in ("SLIM", "BALANCED", "SOFT"):
        return {
            "verdict": "ABSTAIN",
            "reasons": ["UNSUPPORTED_EXTREME_BODY_REQUEST_OUTSIDE_SLIM_BALANCED_SOFT"],
            "bmi": _round6(bmi),
            "recommendedPreset": None,
            "bodyMorphValues": None,
            "label": "HEIGHT_WEIGHT_CANONICAL_RECOMMENDATION",
        }

    morphs = {k: _round6(v) for k, v in BODY_PRESETS[preset].items()}
    # mild height influence on BODY_Height only within preset family
    height_offset = _round6(max(-0.15, min(0.15, (height_cm - 170.0) / 200.0)))
    morphs["BODY_Height"] = _round6(morphs["BODY_Height"] + height_offset)

    return {
        "verdict": "ELIGIBLE",
        "reasons": [],
        "bmi": _round6(bmi),
        "recommendedPreset": preset,
        "bodyMorphValues": morphs,
        "doNotClaimAccurate": [
            "MUSCLE_MASS",
            "BODY_FAT_PERCENT",
            "SKELETAL_STRUCTURE",
            "FULL_REAL_BODY_RECONSTRUCTION",
        ],
        "label": "HEIGHT_WEIGHT_CANONICAL_RECOMMENDATION",
        "userSingleChoiceAfterPreview": [
            "A_BIT_SLIMMER",
            "KEEP_RECOMMENDED",
            "A_BIT_SOFTER",
        ],
    }


def build_identity_layer(image_analysis: dict) -> dict:
    """Map image stats → ID_* values. Honest estimate, not recognition claim."""
    mr, mg, mb = image_analysis["meanRgb"]
    occ = image_analysis["faceLikeOccupancy"]
    edge = image_analysis["edgeVariance"]
    seed = hashlib.sha256(
        f"{image_analysis['imageSha256']}:{occ}:{edge}".encode("utf-8")
    ).digest()

    def u(i: int) -> float:
        return seed[i] / 255.0

    values = {
        "ID_FaceOutline": _round6(_clamp01(0.35 + 0.4 * occ + 0.1 * u(0))),
        "ID_Eye": _round6(_clamp01(0.25 + 0.35 * (1.0 - abs(mr - mg)) + 0.15 * u(1))),
        "ID_Nose": _round6(_clamp01(0.3 + 0.3 * mb + 0.2 * u(2))),
        "ID_Mouth": _round6(_clamp01(0.28 + 0.25 * mr + 0.2 * u(3))),
        "ID_Jaw": _round6(_clamp01(0.32 + 0.25 * occ + 0.15 * u(4))),
        "ID_Cheek": _round6(_clamp01(0.3 + 0.2 * mg + 0.2 * u(5))),
        "ID_Hairline": _round6(_clamp01(0.4 + 0.2 * (1.0 - mb) + 0.15 * u(6))),
    }
    return {
        "mode": "IDENTITY_CENTERED_PERSONALIZATION",
        "label": "SINGLE_IMAGE_IDENTITY_ESTIMATE",
        "axes": ID_AXES,
        "values": values,
        "method": "DETERMINISTIC_IMAGE_STAT_HASH_MAP",
        "autoClaimFaceRecognition": "DENY",
    }


def apply_polished() -> dict:
    return {
        "mode": "POLISHED",
        "values": {k: _round6(v) for k, v in POLISHED.items()},
        "aspirationalWithoutExplicitChoice": "DENY",
    }


def unobserved_completion() -> dict:
    return {
        "back": "UNOBSERVED_STANDARD_COMPLETION",
        "sides": "CANONICAL_STANDARD_COMPLETION",
        "claimObserved": "DENY",
    }


def bind_hair_outfit() -> dict:
    return {
        "hair": DEFAULT_HAIR,
        "outfit": DEFAULT_OUTFIT,
        "source": "QUICK_DEFAULT_FROM_GATE6_LIBRARY_IDS",
        "artistCertified": "NOT_CLAIMED",
    }


def bind_silent_and_arkaon() -> dict:
    return {
        "silentHomepagePresets": list(SILENT_PRESETS),
        "arkaonPresetBinding": list(ARKAON_BIND),
        "arkaonGenerationIntervention": "DENY",
        "arkaonRigWeightMutation": "DENY",
        "voiceLipsync": "DENY",
        "talkingProfileMix": "DENY",
    }


def run_pipeline(bundle: InputBundle, params: dict) -> dict:
    image_path = Path(bundle.imagePath)
    if not image_path.is_file():
        return {
            "caseId": bundle.caseId,
            "verdict": "ABSTAIN",
            "abstainReasons": ["INPUT_CONTRACT_INCOMPLETE"],
            "countsAsGate8ParticipantEvidence": "DENY",
        }

    if bundle.heightCm is None or bundle.weightKg is None:
        return {
            "caseId": bundle.caseId,
            "verdict": "ABSTAIN",
            "abstainReasons": ["INPUT_CONTRACT_INCOMPLETE"],
            "countsAsGate8ParticipantEvidence": "DENY",
        }

    qa = analyze_image(image_path, bundle.declaredPose, params)
    body = recommend_body(bundle.heightCm, bundle.weightKg, params)

    abstain = []
    if qa["verdict"] == "ABSTAIN":
        abstain.extend(qa["reasons"])
    if body["verdict"] == "ABSTAIN":
        abstain.extend(body["reasons"])

    if abstain:
        out = {
            "caseId": bundle.caseId,
            "verdict": "ABSTAIN",
            "abstainReasons": sorted(set(abstain)),
            "imageAnalysis": {
                "verdict": qa["verdict"],
                "reasons": qa["reasons"],
                "imageSha256": qa["imageSha256"],
                "faceAuthentication": "OUT_OF_SCOPE",
                "analyzer": qa["analyzer"],
            },
            "bodyRecommendation": {
                "verdict": body["verdict"],
                "reasons": body.get("reasons", []),
                "bmi": body.get("bmi"),
                "recommendedPreset": None,
                "bodyMorphValues": None,
                "label": "HEIGHT_WEIGHT_CANONICAL_RECOMMENDATION",
                "generativeApplication": "DENY",
            },
            "characterGeneration": "DENY",
            "partialResultGeneration": "DENY",
            "identityLayer": None,
            "beautification": None,
            "unobservedCompletion": None,
            "hairOutfit": None,
            "performanceBinding": None,
            "recipe": None,
            "assembleFingerprintSha256": None,
            "outputBlendSha256": None,
            "disclosure": DISCLOSURE,
            "userFacingDisclosureKo": USER_DISCLOSURE_KO,
            "countsAsGate8ParticipantEvidence": "DENY",
            "participantEvidenceCounting": "DENY",
            "production": "NO-GO",
        }
        out["pipelineFingerprintSha256"] = sha256_obj(
            {k: v for k, v in out.items() if k != "pipelineFingerprintSha256"}
        )
        return out

    identity = build_identity_layer(qa)
    beau = apply_polished()
    unobs = unobserved_completion()
    apparel = bind_hair_outfit()
    perf = bind_silent_and_arkaon()

    recipe = {
        "identityValues": identity["values"],
        "beautificationValues": beau["values"],
        "beautificationMode": beau["mode"],
        "bodyPreset": body["recommendedPreset"],
        "bodyMorphValues": body["bodyMorphValues"],
        "hair": apparel["hair"],
        "outfit": apparel["outfit"],
        "silentHomepagePresets": perf["silentHomepagePresets"],
        "arkaonPresetBinding": perf["arkaonPresetBinding"],
    }

    out = {
        "caseId": bundle.caseId,
        "verdict": "QUICK_PROFILE_DRAFT_READY",
        "abstainReasons": [],
        "imageAnalysis": qa,
        "identityLayer": identity,
        "bodyRecommendation": body,
        "beautification": beau,
        "unobservedCompletion": unobs,
        "hairOutfit": apparel,
        "performanceBinding": perf,
        "recipe": recipe,
        "disclosure": DISCLOSURE,
        "userFacingDisclosureKo": USER_DISCLOSURE_KO,
        "resultGrade": "QUICK_PROFILE_PREVIEW",
        "countsAsGate8ParticipantEvidence": "DENY",
        "participantEvidenceCounting": "DENY",
        "internalDryRun": True,
        "production": "NO-GO",
        "exaggerationBan": params.get("exaggerationBan", {}),
    }
    out["pipelineFingerprintSha256"] = sha256_obj(
        {k: v for k, v in out.items() if k != "pipelineFingerprintSha256"}
    )
    return out


def write_fixture_images(fixtures_dir: Path) -> dict[str, Path]:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # Eligible frontal-ish face proxy (large center skin oval)
    img = Image.new("RGB", (512, 640), (245, 246, 248))
    d = ImageDraw.Draw(img)
    d.ellipse((110, 60, 400, 460), fill=(205, 155, 125))
    d.ellipse((175, 190, 225, 245), fill=(45, 35, 35))
    d.ellipse((285, 190, 335, 245), fill=(45, 35, 35))
    d.ellipse((235, 255, 275, 305), fill=(175, 115, 105))
    d.arc((200, 310, 310, 380), 15, 165, fill=(130, 70, 70), width=4)
    # hairline dark band
    d.pieslice((110, 40, 400, 220), 200, 340, fill=(55, 40, 30))
    p = fixtures_dir / "dryrun_eligible_frontal.png"
    img.save(p)
    paths["eligible_frontal"] = p

    # Blurry abstain (heavy blur so edge variance collapses)
    blur = img.filter(ImageFilter.GaussianBlur(radius=28))
    p2 = fixtures_dir / "dryrun_abstain_blur.png"
    blur.save(p2)
    paths["abstain_blur"] = p2

    # Tiny / no face abstain
    tiny = Image.new("RGB", (48, 48), (10, 10, 10))
    p3 = fixtures_dir / "dryrun_abstain_noface.png"
    tiny.save(p3)
    paths["abstain_noface"] = p3

    return paths
