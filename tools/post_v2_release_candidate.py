#!/usr/bin/env python3
"""Build and verify deterministic, offline Post-V2 release-candidate bundles.

This tool packages only the two independently releasable Post-V2 Python
packages.  It deliberately does not package, mutate, or evaluate any sealed
V2/v0.5/v0.6/V07 source or evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "NURION_POST_V2_RELEASE_CANDIDATE_V1"
MANIFEST_NAME = "SHA256SUMS.json"
ASSETS_MANIFEST_NAME = "ASSETS_MANIFEST.json"
ASSETS_SCHEMA = "NURION_V2_ASSETS_MANIFEST_V1"
ASSETS_POLICY = "PUBLIC_PINS_ONLY_NO_MESH_BINARY"
RESTRICTED_PUBLIC_SUFFIXES = frozenset({".blend", ".fbx", ".glb", ".gltf", ".usdz", ".vrm", ".zip"})
RESTRICTED_PUBLIC_DIRECTORIES = frozenset({".nurion_blender_tmp", "dist"})
BUNDLES = (
    {
        "filename": "nurion-character-landmarker.zip",
        "package": "nurion_character_landmarker",
        "import": "nurion_character_landmarker.profiles.profile_contract",
        "required": (
            "nurion_character_landmarker/__init__.py",
            "nurion_character_landmarker/profiles/__init__.py",
            "nurion_character_landmarker/profiles/profile_contract.py",
        ),
    },
    {
        "filename": "nurion-post-v2-runtime.zip",
        "package": "nurion_post_v2_runtime",
        "import": "nurion_post_v2_runtime",
        "required": (
            "nurion_post_v2_runtime/__init__.py",
            "nurion_post_v2_runtime/contracts.py",
            "nurion_post_v2_runtime/state_machine.py",
        ),
    },
    {
        "filename": "nurion-public-guides.zip",
        "paths": (
            "README.md",
            "docs/REPRODUCIBLE_RUNTIME.md",
        ),
        "required": (
            "README.md",
            "docs/REPRODUCIBLE_RUNTIME.md",
        ),
    },
)


class ReleaseCandidateError(ValueError):
    """A release-candidate archive or manifest violates its contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_date_epoch(value: str | None) -> int:
    if value is not None:
        try:
            epoch = int(value)
        except ValueError as exc:
            raise ReleaseCandidateError("SOURCE_DATE_EPOCH_INVALID") from exc
    else:
        configured = os.environ.get("SOURCE_DATE_EPOCH")
        if configured:
            return _source_date_epoch(configured)
        try:
            completed = subprocess.run(
                ["git", "-C", str(ROOT), "log", "-1", "--format=%ct"],
                check=True,
                capture_output=True,
                text=True,
            )
            epoch = int(completed.stdout.strip())
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            raise ReleaseCandidateError("SOURCE_DATE_EPOCH_UNRESOLVABLE") from exc
    if epoch < 0:
        raise ReleaseCandidateError("SOURCE_DATE_EPOCH_INVALID")
    return epoch


def _source_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReleaseCandidateError("SOURCE_REVISION_UNRESOLVABLE") from exc
    revision = completed.stdout.strip()
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise ReleaseCandidateError("SOURCE_REVISION_INVALID")
    return revision


def _tracked_paths() -> list[str]:
    """Return only Git-tracked repository paths; ignored local assets are excluded."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReleaseCandidateError("TRACKED_PATHS_UNRESOLVABLE") from exc
    return [item for item in completed.stdout.decode("utf-8").split("\0") if item]


def validate_public_repository_paths(paths: Iterable[str]) -> None:
    """Fail closed when a tracked path is a protected asset or legacy output."""
    for raw_path in paths:
        path = _archive_name(raw_path)
        parts = PurePosixPath(path).parts
        if any(part in RESTRICTED_PUBLIC_DIRECTORIES for part in parts):
            raise ReleaseCandidateError("PUBLIC_POLICY_RESTRICTED_DIRECTORY")
        if PurePosixPath(path).suffix.lower() in RESTRICTED_PUBLIC_SUFFIXES:
            raise ReleaseCandidateError("PUBLIC_POLICY_RESTRICTED_ASSET")


def validate_assets_manifest(path: Path = ROOT / ASSETS_MANIFEST_NAME) -> None:
    """Validate the public pin-only policy without resolving private assets."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseCandidateError("ASSETS_MANIFEST_INVALID") from exc
    if not isinstance(document, dict):
        raise ReleaseCandidateError("ASSETS_MANIFEST_INVALID")
    if document.get("schema") != ASSETS_SCHEMA or document.get("repoPolicy") != ASSETS_POLICY:
        raise ReleaseCandidateError("ASSETS_MANIFEST_POLICY_INVALID")
    assets = document.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ReleaseCandidateError("ASSETS_MANIFEST_ASSETS_INVALID")
    identifiers: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise ReleaseCandidateError("ASSETS_MANIFEST_ASSET_INVALID")
        identifier = asset.get("id")
        digest = asset.get("sha256")
        hints = asset.get("localHints")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in identifiers
            or asset.get("publicGitHub") != "DENY"
            or asset.get("channel") != "private_or_local"
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or not isinstance(hints, list)
            or not hints
            or not all(isinstance(hint, str) and hint for hint in hints)
        ):
            raise ReleaseCandidateError("ASSETS_MANIFEST_ASSET_POLICY_INVALID")
        identifiers.add(identifier)
    allowed = document.get("publicUploadAllowed")
    if not isinstance(allowed, list) or not allowed or not all(isinstance(item, str) for item in allowed):
        raise ReleaseCandidateError("ASSETS_MANIFEST_ALLOWLIST_INVALID")
    validate_public_repository_paths(allowed)
    validate_public_repository_paths(_tracked_paths())


def _zip_datetime(epoch: int) -> tuple[int, int, int, int, int, int]:
    # ZIP cannot encode dates before 1980 and stores seconds with two-second
    # precision.  UTC avoids workstation timezone influence.
    minimum_zip_epoch = 315532800  # 1980-01-01T00:00:00Z
    value = datetime.fromtimestamp(max(epoch, minimum_zip_epoch), tz=timezone.utc)
    return (value.year, value.month, value.day, value.hour, value.minute, value.second - value.second % 2)


def _archive_name(name: str) -> str:
    candidate = PurePosixPath(name)
    if not name or "\\" in name or candidate.is_absolute() or any(part in ("", ".", "..") for part in candidate.parts):
        raise ReleaseCandidateError("ARCHIVE_PATH_TRAVERSAL")
    return candidate.as_posix()


def _package_files(package: str) -> list[Path]:
    package_root = ROOT / package
    if not package_root.is_dir():
        raise ReleaseCandidateError("PACKAGE_ROOT_MISSING")
    files: list[Path] = []
    for path in sorted(package_root.rglob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise ReleaseCandidateError("PACKAGE_FILE_UNSAFE")
        try:
            path.resolve().relative_to(ROOT.resolve())
        except ValueError as exc:
            raise ReleaseCandidateError("PACKAGE_FILE_ESCAPE") from exc
        files.append(path)
    if not files:
        raise ReleaseCandidateError("PACKAGE_EMPTY")
    return files


def _bundle_files(specification: dict[str, Any]) -> list[Path]:
    """Resolve a static, source-only bundle allowlist from the checkout."""
    if "package" in specification:
        return _package_files(str(specification["package"]))
    paths = specification.get("paths")
    if not isinstance(paths, tuple) or not paths:
        raise ReleaseCandidateError("BUNDLE_SOURCE_INVALID")
    files: list[Path] = []
    for relative_path in paths:
        if not isinstance(relative_path, str):
            raise ReleaseCandidateError("BUNDLE_SOURCE_INVALID")
        safe_path = _archive_name(relative_path)
        source = ROOT / safe_path
        if source.is_symlink() or not source.is_file():
            raise ReleaseCandidateError("BUNDLE_SOURCE_MISSING")
        files.append(source)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def _expected_entries(specification: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the exact permitted source inventory for one bundle."""
    entries = []
    for source in _bundle_files(specification):
        arcname = _archive_name(source.relative_to(ROOT).as_posix())
        payload = source.read_bytes()
        entries.append({"path": arcname, "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)})
    return entries


def _specification_by_filename() -> dict[str, dict[str, Any]]:
    specifications = {str(specification["filename"]): specification for specification in BUNDLES}
    if len(specifications) != len(BUNDLES):
        raise ReleaseCandidateError("BUNDLE_CONFIGURATION_INVALID")
    return specifications


def _write_deterministic_zip(destination: Path, files: Iterable[Path], timestamp: tuple[int, int, int, int, int, int]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(destination, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as archive:
        for source in files:
            arcname = _archive_name(source.relative_to(ROOT).as_posix())
            payload = source.read_bytes()
            info = zipfile.ZipInfo(arcname, date_time=timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.flag_bits |= 0x800
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            entries.append({"path": arcname, "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)})
    return entries


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseCandidateError("MANIFEST_INVALID") from exc
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise ReleaseCandidateError("MANIFEST_SCHEMA_INVALID")
    if not isinstance(document.get("bundles"), list) or not document["bundles"]:
        raise ReleaseCandidateError("MANIFEST_BUNDLES_INVALID")
    return document


def _validate_zip_members(archive_path: Path, expected_entries: list[dict[str, Any]]) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            names = [_archive_name(member.filename) for member in members]
            if len(names) != len(set(names)):
                raise ReleaseCandidateError("ARCHIVE_DUPLICATE_MEMBER")
            expected_names = [entry["path"] for entry in expected_entries]
            if names != expected_names:
                raise ReleaseCandidateError("ARCHIVE_EXPECTED_FILES_MISMATCH")
            for member, expected in zip(members, expected_entries, strict=True):
                if member.is_dir() or member.file_size != expected["size"]:
                    raise ReleaseCandidateError("ARCHIVE_MEMBER_METADATA_INVALID")
                payload = archive.read(member)
                if hashlib.sha256(payload).hexdigest() != expected["sha256"]:
                    raise ReleaseCandidateError("ARCHIVE_MEMBER_SHA256_MISMATCH")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReleaseCandidateError("ARCHIVE_INVALID") from exc


def _run_isolated_import(archive_path: Path, module: str) -> None:
    with tempfile.TemporaryDirectory(prefix="nurion-release-import-") as temporary:
        code = (
            "import importlib, sys; "
            f"sys.path.insert(0, {str(archive_path.resolve())!r}); "
            f"importlib.import_module({module!r}); print('isolated-import PASS')"
        )
        child_environment = os.environ.copy()
        child_environment["PYTHONNOUSERSITE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-c", code],
            cwd=temporary,
            env=child_environment,
            capture_output=True,
            text=True,
        )
    if completed.returncode != 0 or "isolated-import PASS" not in completed.stdout:
        raise ReleaseCandidateError("ARCHIVE_ISOLATED_IMPORT_FAILED")


def verify(manifest_path: Path) -> dict[str, Any]:
    """Verify digest, safe member names, exact inventory, and isolated imports."""
    validate_assets_manifest()
    document = _load_manifest(manifest_path)
    if document.get("sourceRevision") != _source_revision():
        raise ReleaseCandidateError("MANIFEST_SOURCE_REVISION_MISMATCH")
    specifications = _specification_by_filename()
    if len(document["bundles"]) != len(specifications):
        raise ReleaseCandidateError("MANIFEST_BUNDLE_SET_INVALID")
    names: set[str] = set()
    for bundle in document["bundles"]:
        if not isinstance(bundle, dict):
            raise ReleaseCandidateError("MANIFEST_BUNDLE_INVALID")
        filename = bundle.get("filename")
        if not isinstance(filename, str) or filename != Path(filename).name or filename in names:
            raise ReleaseCandidateError("MANIFEST_BUNDLE_NAME_INVALID")
        if filename not in specifications:
            raise ReleaseCandidateError("MANIFEST_BUNDLE_NAME_INVALID")
        names.add(filename)
        specification = specifications[filename]
        archive_path = manifest_path.parent / filename
        if not archive_path.is_file() or _sha256(archive_path) != bundle.get("sha256"):
            raise ReleaseCandidateError("ARCHIVE_SHA256_MISMATCH")
        entries = bundle.get("entries")
        if not isinstance(entries, list) or not entries:
            raise ReleaseCandidateError("MANIFEST_ENTRIES_INVALID")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str) or not isinstance(entry.get("size"), int):
                raise ReleaseCandidateError("MANIFEST_ENTRY_INVALID")
        if entries != _expected_entries(specification):
            raise ReleaseCandidateError("ARCHIVE_SOURCE_ALLOWLIST_MISMATCH")
        _validate_zip_members(archive_path, entries)
        required = bundle.get("required")
        expected_required = list(specification["required"])
        if required != expected_required or not set(required).issubset({entry["path"] for entry in entries}):
            raise ReleaseCandidateError("ARCHIVE_REQUIRED_FILES_MISSING")
        module = bundle.get("isolatedImport")
        expected_module = specification.get("import")
        if module != expected_module:
            raise ReleaseCandidateError("ARCHIVE_IMPORT_TARGET_INVALID")
        if isinstance(module, str):
            _run_isolated_import(archive_path, module)
    if names != set(specifications):
        raise ReleaseCandidateError("MANIFEST_BUNDLE_SET_INVALID")
    return document


def build(output_dir: Path, *, source_date_epoch: str | None = None) -> Path:
    """Create both release candidates and a SHA-256 manifest, then verify them."""
    validate_assets_manifest()
    epoch = _source_date_epoch(source_date_epoch)
    revision = _source_revision()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise ReleaseCandidateError("OUTPUT_DIRECTORY_INVALID")
    timestamp = _zip_datetime(epoch)
    bundles: list[dict[str, Any]] = []
    for specification in BUNDLES:
        destination = output_dir / specification["filename"]
        entries = _write_deterministic_zip(destination, _bundle_files(specification), timestamp)
        bundles.append(
            {
                "filename": specification["filename"],
                "sha256": _sha256(destination),
                "size": destination.stat().st_size,
                "entries": entries,
                "required": list(specification["required"]),
                "isolatedImport": specification.get("import"),
            }
        )
    manifest = {
        "schema": SCHEMA,
        "sourceRevision": revision,
        "sourceDateEpoch": epoch,
        "bundles": bundles,
    }
    manifest_path = output_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify(manifest_path)
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="build and verify release candidates")
    build_parser.add_argument("--output-dir", type=Path, required=True)
    build_parser.add_argument("--source-date-epoch")
    verify_parser = commands.add_parser("verify", help="verify a release-candidate manifest")
    verify_parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            manifest = build(args.output_dir, source_date_epoch=args.source_date_epoch)
            print(f"release-candidate build PASS: {manifest}")
        else:
            verify(args.manifest)
            print(f"release-candidate verify PASS: {args.manifest}")
    except ReleaseCandidateError as exc:
        print(f"release-candidate FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
