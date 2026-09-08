"""P001-P003 Blinded Draft Capture Render GO runner."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
COMMAND = "NURION Quick Profile Geometry-First Face Analyzer v2 P001-P003 Blinded Draft Capture Render GO"
EXP_G4 = "92ebd6e7dd9b5d79cfdee17cf9cac37d4dfd3cdf3860a973b7ba91f829af88c4"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools/blender_qp_gf_blinded_draft_capture.py"
BUNDLE = (
    ROOT
    / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4/human_review/blinded_bundle_20260815T143609Z"
)
G4 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4"
PARTICIPANTS = ("P001", "P002", "P003")
VIEWS = ("front", "left45", "right45")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sys.path.insert(0, str(ROOT))
    from nurion_qp_geometry_face_v2.gate4_contract import gate4_parameter_hash

    if gate4_parameter_hash() != EXP_G4:
        raise SystemExit("GATE4_HASH_MISMATCH")
    if not BLENDER.is_file():
        raise SystemExit("BLENDER_MISSING")
    if not BUNDLE.is_dir():
        raise SystemExit("BUNDLE_MISSING")

    # ensure review forms remain untouched / empty
    for pid in PARTICIPANTS:
        for kind in ("SELF", "INTERNAL"):
            form = BUNDLE / "participants" / pid / "review" / f"{pid}_{kind}_REVIEW.json"
            doc = read_json(form)
            if doc.get("completed") is True or any(v is not None for v in doc.get("scores", {}).values()):
                raise SystemExit(f"FORM_ALREADY_FILLED:{pid}:{kind}")

    captures = {}
    for pid in PARTICIPANTS:
        pres = BUNDLE / "participants" / pid / "presentation"
        cap_dir = pres / "captures"
        cap_dir.mkdir(parents=True, exist_ok=True)
        pid_caps = {}
        for label in ("A", "B"):
            blend = pres / f"Draft_{label}.blend"
            if not blend.is_file():
                raise SystemExit(f"MISSING_BLEND:{pid}:{label}")
            # Do not open operator blind mapping.
            cmd = [
                str(BLENDER),
                "--background",
                str(blend),
                "--python",
                str(SCRIPT),
                "--",
                "--out-dir",
                str(cap_dir),
                "--draft-label",
                label,
                "--resolution",
                "1024",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            (cap_dir / f"_render_{label}_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
            (cap_dir / f"_render_{label}_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
            if proc.returncode != 0:
                raise SystemExit(f"RENDER_FAIL:{pid}:{label}:{proc.returncode}")
            files = {}
            for view in VIEWS:
                png = cap_dir / f"Draft_{label}_{view}.png"
                if not png.is_file():
                    raise SystemExit(f"PNG_MISSING:{pid}:{label}:{view}")
                files[view] = {"file": png.name, "sha256": sha256_file(png), "bytes": png.stat().st_size}
            pid_caps[f"Draft_{label}"] = files
        # presentation index for humans (no mode labels)
        index = {
            "schema": "NURION_V07_QP_GF_FACE_V2_BLINDED_CAPTURE_INDEX_V1",
            "anonymousParticipantId": pid,
            "instructionKo": "같은 조명·카메라·표정 조건으로 렌더된 Draft A/B 캡처입니다. NATURAL/POLISHED 라벨은 없습니다. 이 이미지로 판단한 뒤 review JSON만 기입하세요.",
            "assetLimitationKo": "현재 시안 메시는 Gate5 캐노니컬 저폴리 프록시(블록형)입니다. 포토리얼 얼굴 재현이 아니므로, 사진과의 세밀 유사성보다 A/B 형상·미화 차이 비교에 사용하세요.",
            "meshRendered": "NURION_BP_CanonicalHuman_V1",
            "photorealFaceClaim": "DENY",
            "views": list(VIEWS),
            "captures": pid_caps,
            "automaticSimilarityScore": "DENY",
            "responseInterpolation": "DENY",
            "distribution": "DENY",
            "production": "NO-GO",
        }
        write_json(cap_dir / f"{pid}_BLINDED_CAPTURE_INDEX.json", index)
        captures[pid] = {
            "captureDir": f"participants/{pid}/presentation/captures",
            "files": pid_caps,
        }

    receipt = {
        "schema": "NURION_V07_QP_GF_FACE_V2_P001_P003_BLINDED_DRAFT_CAPTURE_RENDER_RECEIPT_V1",
        "command": COMMAND,
        "registeredAt": now,
        "verdict": "CAPTURES_READY_AWAITING_HUMAN_JUDGMENT",
        "bundle": "human_review/blinded_bundle_20260815T143609Z",
        "participants": list(PARTICIPANTS),
        "views": list(VIEWS),
        "resolution": 1024,
        "cameraLightingExpression": "IDENTICAL_ACROSS_A_B",
        "meshRendered": "NURION_BP_CanonicalHuman_V1",
        "assetClass": "GATE5_CANONICAL_LOWPOLY_PROXY",
        "photorealFaceClaim": "DENY",
        "reviewGuidance": "USE_FOR_A_B_GEOMETRY_BEAUTIFY_DELTA_NOT_PHOTOREAL_LIKENESS",
        "modeLabelsInFilenames": "DENY",
        "operatorBlindMappingOpened": "DENY",
        "reviewFormsMutated": "DENY",
        "automaticSimilarityScore": "DENY",
        "responseInterpolation": "DENY",
        "gate4ParameterHash": EXP_G4,
        "gate4Mutation": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "production": "NO-GO",
        "captures": captures,
        "next": "HUMAN_FILLS_SELF_AND_INTERNAL_REVIEW_JSON_USING_CAPTURES",
    }
    write_json(BUNDLE / "V07_QP_GF_FACE_V2_P001_P003_BLINDED_DRAFT_CAPTURE_RENDER_RECEIPT.json", receipt)
    write_json(G4 / "V07_QP_GF_FACE_V2_P001_P003_BLINDED_DRAFT_CAPTURE_RENDER_RECEIPT.json", receipt)

    st = read_json(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json")
    st["updatedAt"] = now
    st["blindedDraftCaptures"] = {
        "verdict": "CAPTURES_READY_AWAITING_HUMAN_JUDGMENT",
        "bundle": "human_review/blinded_bundle_20260815T143609Z",
        "gate4Mutation": "DENY",
    }
    st["next"] = "AWAIT_HUMAN_REVIEW_FORMS_USING_CAPTURES"
    write_json(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json", st)

    print(
        json.dumps(
            {
                "verdict": "CAPTURES_READY_AWAITING_HUMAN_JUDGMENT",
                "participants": list(PARTICIPANTS),
                "views": list(VIEWS),
                "bundleCaptures": str(BUNDLE / "participants"),
                "production": "NO-GO",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
