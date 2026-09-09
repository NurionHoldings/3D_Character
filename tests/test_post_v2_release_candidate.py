import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("post_v2_release_candidate", ROOT / "tools" / "post_v2_release_candidate.py")
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def test_release_candidate_is_deterministic_and_self_verifying(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    release.build(first, source_date_epoch="1700000000")
    release.build(second, source_date_epoch="1700000000")
    for filename in (
        "nurion-character-landmarker.zip",
        "nurion-post-v2-runtime.zip",
        "nurion-public-guides.zip",
        "SHA256SUMS.json",
    ):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
    document = json.loads((first / "SHA256SUMS.json").read_text(encoding="utf-8"))
    assert document["schema"] == release.SCHEMA
    assert {item["filename"] for item in document["bundles"]} == {
        "nurion-character-landmarker.zip",
        "nurion-post-v2-runtime.zip",
        "nurion-public-guides.zip",
    }
    release.verify(first / "SHA256SUMS.json")


def test_archive_verifier_rejects_path_traversal_and_unexpected_files(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.py", "x = 1\n")
    with pytest.raises(release.ReleaseCandidateError, match="ARCHIVE_PATH_TRAVERSAL"):
        release._validate_zip_members(archive, [])

    safe = tmp_path / "unexpected.zip"
    with zipfile.ZipFile(safe, "w") as bundle:
        bundle.writestr("package/__init__.py", "")
        bundle.writestr("package/unexpected.py", "")
    with pytest.raises(release.ReleaseCandidateError, match="ARCHIVE_EXPECTED_FILES_MISMATCH"):
        release._validate_zip_members(safe, [{"path": "package/__init__.py", "size": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}])


def test_public_asset_policy_is_pin_only_and_rejects_protected_payload_paths():
    release.validate_assets_manifest()
    for path, expected in (
        ("customer/face.glb", "PUBLIC_POLICY_RESTRICTED_ASSET"),
        ("external/Jake.fbx", "PUBLIC_POLICY_RESTRICTED_ASSET"),
        ("evidence/IRG_R2_proof.zip", "PUBLIC_POLICY_RESTRICTED_ASSET"),
        ("dist/v0.7/legacy.json", "PUBLIC_POLICY_RESTRICTED_DIRECTORY"),
        (".nurion_blender_tmp/cache.json", "PUBLIC_POLICY_RESTRICTED_DIRECTORY"),
    ):
        with pytest.raises(release.ReleaseCandidateError, match=expected):
            release.validate_public_repository_paths([path])


def test_manifest_cannot_expand_the_static_source_allowlist(tmp_path):
    output = tmp_path / "candidate"
    manifest_path = release.build(output, source_date_epoch="1700000000")
    archive = output / "nurion-post-v2-runtime.zip"
    with zipfile.ZipFile(archive, "a") as bundle:
        bundle.writestr("nurion_post_v2_runtime/unexpected.txt", "not source-only\n")

    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime = next(item for item in document["bundles"] if item["filename"] == archive.name)
    runtime["sha256"] = release._sha256(archive)
    runtime["size"] = archive.stat().st_size
    runtime["entries"].append(
        {
            "path": "nurion_post_v2_runtime/unexpected.txt",
            "sha256": "776b8df05b117061c040164760e214c003ee358331daeffd474791f279c6ce65",
            "size": 16,
        }
    )
    manifest_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(release.ReleaseCandidateError, match="ARCHIVE_SOURCE_ALLOWLIST_MISMATCH"):
        release.verify(manifest_path)
