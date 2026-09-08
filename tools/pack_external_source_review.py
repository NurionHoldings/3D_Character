#!/usr/bin/env python3
"""Build an external source-code analysis package (no large binary dump)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "dist" / "external_source_review"
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
PACKAGE_NAME = f"NURION_Character_Landmarker_EXTERNAL_SOURCE_REVIEW_{STAMP}"
MAX_BINARY_BYTES = 2 * 1024 * 1024

INCLUDE_ROOT_FILES = [
    "README.md",
    "DESIGN_SPEC.md",
    "STATUS.json",
    "ALPHA3_LESSONS.json",
    "start_presentation.bat",
    "NURION_v0.5_FINAL_SEAL_REVIEW.md",
    "NURION_v0.5_FINAL_SEAL_REVIEW.json",
    "NURION_v0.6_FINAL_SEAL_REVIEW.json",
    "V05_FINAL_BASELINE_LOCK.json",
    "V05_FINAL_SEAL_RECEIPT.json",
    "V05_VALIDATION_STATUS.json",
    "V06_FINAL_BASELINE_LOCK.json",
    "V06_FINAL_SEAL_RECEIPT.json",
]

INCLUDE_DIRS = [
    "tools",
    "tests",
    "examples",
    "fixtures",
    "nurion_character_landmarker",
    "nurion_qp_geometry_face_v2",
    "nurion_universal_eye",
    "nurion_universal_eye_calibration",
    "nurion_v04_face_rig",
    "nurion_v05_body_motion",
    "nurion_v06_production_readiness",
    "nurion_v06_unified_runtime",
    "nurion_v07_homepage_performance_rig",
    "nurion_ccs_gate1",
    "fast_track/runtime",
    "fast_track/presentation_app",
    "fast_track/intake",
]

# Receipts / semantic evidence only from working lane (no GLB media dump).
FAST_TRACK_EVIDENCE_GLOBS = [
    "fast_track/working/**/evidence/*.json",
    "fast_track/working/**/semantic/*.json",
    "fast_track/working/**/mutation_ledger.json",
    "fast_track/working/**/narration/*.json",
]

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "node_modules",
    ".nurion_blender_tmp",
    "dist",
    "assets",
    "ai-baeby",
}

SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".glb",
    ".gltf",
    ".fbx",
    ".obj",
    ".blend",
    ".blend1",
    ".wav",
    ".mp3",
    ".mp4",
    ".mov",
    ".webm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".exr",
    ".hdr",
    ".zip",
    ".7z",
    ".rar",
    ".dll",
    ".exe",
    ".pyd",
    ".so",
    ".dylib",
}

TEXTISH_SUFFIXES = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".bat",
    ".ps1",
    ".sh",
    ".csv",
    ".tsv",
    ".glsl",
    ".vert",
    ".frag",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def should_skip_dir(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def is_candidate_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if should_skip_dir(path.relative_to(ROOT)):
        return False
    if path.name.startswith("."):
        return False
    suffix = path.suffix.lower()
    if suffix in SKIP_SUFFIXES:
        return False
    if suffix in TEXTISH_SUFFIXES:
        return True
    # Allow small non-media binaries that may be config-like.
    return path.stat().st_size <= MAX_BINARY_BYTES


def collect_files() -> list[Path]:
    selected: set[Path] = set()
    for name in INCLUDE_ROOT_FILES:
        path = ROOT / name
        if path.is_file():
            selected.add(path)
    for rel in INCLUDE_DIRS:
        base = ROOT / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if is_candidate_file(path):
                selected.add(path)
    for pattern in FAST_TRACK_EVIDENCE_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and path.suffix.lower() == ".json" and not should_skip_dir(path.relative_to(ROOT)):
                selected.add(path)
    return sorted(selected, key=lambda p: p.as_posix().lower())


def write_review_readme(path: Path, file_count: int, package_name: str) -> None:
    text = f"""# NURION Character Landmarker — External Source Review Package

생성 시각(UTC): `{STAMP}`  
패키지명: `{package_name}`  
포함 파일 수: `{file_count}`

## 목적
외부 검토자가 **전체 소스코드 구조·런타임·FAST Track 영수증**을 분석할 수 있도록
소스/도구/문서/JSON evidence만 묶은 제출용 자료입니다.

## 포함
- Python 패키지: `nurion_*`, `nurion_character_landmarker`
- 도구: `tools/`
- 테스트: `tests/`
- FAST Track: `fast_track/runtime`, `fast_track/presentation_app`, intake
- FAST evidence/semantic/mutation ledger JSON
- 루트 문서: README / STATUS / DESIGN_SPEC / seal review

## 제외 (의도적)
- `dist/`, `assets/`, `.nurion_blender_tmp/`
- GLB/FBX/OBJ/BLEND/미디어(PNG/WAV/MP4 등)
- 대용량 ZIP/바이너리 덤프
- `__pycache__`, 숨김 파일

## 분석 시작점
1. `README.md`, `STATUS.json`, `DESIGN_SPEC.md`
2. `fast_track/working/meshy_silver_starlight/mutation_ledger.json`
3. `fast_track/working/meshy_silver_starlight/evidence/`
4. `fast_track/presentation_app/static/app.js`
5. `tools/run_fast_*.py`, `tools/blender_fast_*.py`

## 현재 FAST 상태 요약 (패키징 시점 기준)
- FAST-HR04 = TECHNICAL PASS / PRODUCT REJECT
- HM08 donor = REJECTED_FOR_FAST_PRODUCT
- TALKING = HOLD
- 다음 GO = FAST-HR05 NEW FACIAL-READY DONOR SELECTION
- Ready Player Me = 후보 제외
- OFFLINE ASSET OWNERSHIP REQUIRED

## 주의
이 패키지는 설치용 RC ZIP이 아닙니다. 외부 코드 분석/리뷰 전용입니다.
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    files = collect_files()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUT_DIR / PACKAGE_NAME
    if staging.exists():
        for p in sorted(staging.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            else:
                p.rmdir()
    staging.mkdir(parents=True, exist_ok=True)

    inventory = []
    for src in files:
        rel = src.relative_to(ROOT).as_posix()
        dst = staging / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        dst.write_bytes(data)
        inventory.append(
            {
                "path": rel,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
        )

    write_review_readme(staging / "EXTERNAL_REVIEW_README.md", len(inventory), PACKAGE_NAME)
    inventory.append(
        {
            "path": "EXTERNAL_REVIEW_README.md",
            "bytes": (staging / "EXTERNAL_REVIEW_README.md").stat().st_size,
            "sha256": sha256_file(staging / "EXTERNAL_REVIEW_README.md"),
        }
    )

    manifest = {
        "schema": "NURION_EXTERNAL_SOURCE_REVIEW_PACKAGE_V1",
        "packageName": PACKAGE_NAME,
        "createdAtUtc": STAMP,
        "purpose": "EXTERNAL_SOURCE_CODE_ANALYSIS",
        "root": str(ROOT),
        "fileCount": len(inventory),
        "totalBytes": sum(row["bytes"] for row in inventory),
        "includeDirs": INCLUDE_DIRS,
        "includeRootFiles": INCLUDE_ROOT_FILES,
        "excludedCategories": sorted(SKIP_DIR_NAMES | {s.lstrip(".") for s in SKIP_SUFFIXES}),
        "notes": [
            "Large media and sealed dist artifacts intentionally omitted.",
            "JSON evidence retained for FAST decision trail.",
        ],
        "inventory": inventory,
    }
    (staging / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    zip_path = OUT_DIR / f"{PACKAGE_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zf.write(path, (Path(PACKAGE_NAME) / path.relative_to(staging)).as_posix())

    receipt = {
        "packageName": PACKAGE_NAME,
        "zipPath": str(zip_path),
        "zipSha256": sha256_file(zip_path),
        "zipBytes": zip_path.stat().st_size,
        "stagingDir": str(staging),
        "fileCount": len(inventory),
        "totalSourceBytes": manifest["totalBytes"],
        "createdAtUtc": STAMP,
        "verdict": "READY_FOR_EXTERNAL_SOURCE_REVIEW",
    }
    receipt_path = OUT_DIR / f"{PACKAGE_NAME}_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
