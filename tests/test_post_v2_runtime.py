import os
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from nurion_character_landmarker.profiles.profile_contract import ContractViolation as ProfileViolation
from nurion_character_landmarker.profiles.profile_contract import normalize_and_validate
from nurion_post_v2_runtime.authority import SourceArmature, SourceMesh, select_source_authority
from nurion_post_v2_runtime.blender_adapter import import_transaction
from nurion_post_v2_runtime.contracts import ContractViolation, validate_export_target
from nurion_post_v2_runtime.state_machine import PostV2RuntimeEngine


def _fbx(tmp_path):
    path = tmp_path / "asset.fbx"
    path.write_bytes(b"fbx")
    return path


def _profile(landmarks=None):
    return {"schema": "NURION_CHARACTER_PROFILE", "version": "0.1.0", "characterId": "asset-1", "characterHeight": 1.7, "width": 0.5, "center": [0, 0, 0.8], "forwardAxis": "-Y", "floorZ": 0, "landmarks": landmarks or {"head": [0, 0, 1.5]}}


def test_profile_normalizes_legacy_before_validation_and_rejects_bad_bounds():
    doc = normalize_and_validate(_profile())
    assert doc["landmarks"][0]["name"] == "head"
    bad = _profile()
    bad["characterHeight"] = 0
    with pytest.raises(ProfileViolation, match="PROFILE_CHARACTERHEIGHT_INVALID"):
        normalize_and_validate(bad)
    many = _profile({f"p{i}": [0, 0, 0] for i in range(513)})
    with pytest.raises(ProfileViolation, match="PROFILE_LANDMARK_COUNT_EXCEEDED"):
        normalize_and_validate(many)


def test_export_rejects_escape_symlink_and_clobber(tmp_path):
    root = tmp_path / "out"
    root.mkdir()
    assert validate_export_target(root / "a.fbx", fmt="FBX", root=root).name == "a.fbx"
    with pytest.raises(ContractViolation, match="EXPORT_ROOT_DENIED"):
        validate_export_target(root / ".." / "escape.fbx", fmt="FBX", root=root)
    target = root / "exists.fbx"
    target.write_bytes(b"x")
    with pytest.raises(ContractViolation, match="EXPORT_TARGET_EXISTS"):
        validate_export_target(target, fmt="FBX", root=root)
    link = root / "linked"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege is unavailable")
        raise
    with pytest.raises(ContractViolation, match="EXPORT_ROOT_DENIED|EXPORT_SYMLINK_DENIED"):
        validate_export_target(link / "x.fbx", fmt="FBX", root=root)


def test_authority_requires_explicit_or_unique_pair():
    arm = SourceArmature("Arm")
    mesh = SourceMesh("Body", "Arm", True)
    assert select_source_authority([arm], [mesh])[1] == mesh
    with pytest.raises(ContractViolation, match="SOURCE_MESH_NOT_UNIQUE"):
        select_source_authority([arm], [mesh, SourceMesh("Hair", "Arm", True)])


class _Blocks(list):
    def remove(self, item, do_unlink=True):
        super().remove(item)


def _fake_bpy(*, finished):
    data = SimpleNamespace(**{name: _Blocks() for name in ("objects", "meshes", "armatures", "actions", "materials", "images", "collections", "cameras", "lights")})

    def fbx(**kwargs):
        data.objects.append(SimpleNamespace(name="Imported"))
        data.meshes.append(SimpleNamespace(name="ImportedMesh"))
        data.materials.append(SimpleNamespace(name="ImportedMat"))
        return {"FINISHED"} if finished else {"CANCELLED"}

    return SimpleNamespace(data=data, ops=SimpleNamespace(import_scene=SimpleNamespace(fbx=fbx)))


def test_import_transaction_rolls_back_all_new_datablocks(tmp_path):
    bpy = _fake_bpy(finished=False)
    result = import_transaction(bpy, _fbx(tmp_path))
    assert result["ok"] is False
    assert result["rollback"]["objects"] == result["rollback"]["meshes"] == result["rollback"]["materials"] == 1
    assert not bpy.data.objects and not bpy.data.meshes and not bpy.data.materials


def test_precheck_import_select_commit_and_invalidation(tmp_path):
    source, root = _fbx(tmp_path), tmp_path / "out"
    root.mkdir()
    engine = PostV2RuntimeEngine()
    precheck = engine.precheck_fbx(source)
    bpy = _fake_bpy(finished=True)
    assert engine.record_import(import_transaction(bpy, source))["ok"]
    assert engine.select_commit()["ok"]
    assert engine.analyze("LIMITED")["ok"]
    assert engine.build(runtime_built=True)["ok"]
    assert engine.apply(motion_applied=True)["ok"]
    assert engine.validate(report={"fps": 30, "dt": 1 / 30, "frameStart": 0, "frameEnd": 1}, passed=True)["ok"]
    preflight = engine.preflight_export(path=root / "runtime.fbx", fmt="FBX", root=root)
    target = preflight["target"]
    target.write_bytes(b"output")
    assert engine.record_export({"ok": True, "path": target.as_posix()})["ok"]
    assert "EXPORT" in engine.state.completed
    assert engine.validate(report={"fps": 30, "dt": 1 / 30, "frameStart": 0, "frameEnd": 1}, passed=True)["ok"]
    assert "EXPORT" not in engine.state.completed and engine.state.wrote is False
    assert precheck["ok"]


def test_false_build_apply_and_missing_export_file_fail_closed(tmp_path):
    source = _fbx(tmp_path)
    engine = PostV2RuntimeEngine()
    precheck = engine.precheck_fbx(source)["precheck"]
    assert engine.record_import({"ok": True, "provenance": {"path": precheck["path"].as_posix(), "size": precheck["size"], "sha256": precheck["sha256"], "importedObjects": ["Body"]}})["ok"]
    engine.select_commit()
    engine.analyze("LIMITED")
    assert engine.build(runtime_built=False)["abort"] == "RUNTIME_BUILD_FAILED"
    engine.build(runtime_built=True)
    assert engine.apply(motion_applied=False)["abort"] == "MOTION_APPLY_FAILED"
    engine.apply(motion_applied=True)
    engine.validate(report={"fps": 30, "dt": 1 / 30, "frameStart": 0, "frameEnd": 1}, passed=True)
    root = tmp_path / "out"
    root.mkdir()
    engine.preflight_export(path=root / "missing.fbx", fmt="FBX", root=root)
    assert engine.record_export({"ok": True, "path": str(root / "missing.fbx")})["abort"] == "EXPORT_WRITE_FAILED"


def test_runtime_package_imports_from_zip_without_checkout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in (root / "nurion_post_v2_runtime").glob("*.py"):
            bundle.write(path, path.relative_to(root))
    code = f"import sys; sys.path.insert(0, {str(archive)!r}); import nurion_post_v2_runtime; print(nurion_post_v2_runtime.__all__)"
    completed = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True, capture_output=True, text=True, env=os.environ.copy())
    assert "PostV2RuntimeEngine" in completed.stdout


def test_landmarker_profile_contract_imports_from_addon_zip(tmp_path):
    root = Path(__file__).resolve().parents[1]
    archive = tmp_path / "addon.zip"
    files = (
        root / "nurion_character_landmarker" / "__init__.py",
        root / "nurion_character_landmarker" / "profiles" / "__init__.py",
        root / "nurion_character_landmarker" / "profiles" / "profile_contract.py",
    )
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in files:
            bundle.write(path, path.relative_to(root))
    code = f"import sys; sys.path.insert(0, {str(archive)!r}); from nurion_character_landmarker.profiles.profile_contract import normalize_and_validate; print(normalize_and_validate({{'schema':'NURION_CHARACTER_PROFILE','version':'0.1.0','characterId':'a','characterHeight':1,'width':1,'center':[0,0,0],'forwardAxis':'-Y','floorZ':0,'landmarks':[]}})['schema'])"
    completed = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True, capture_output=True, text=True, env=os.environ.copy())
    assert "NURION_CHARACTER_PROFILE" in completed.stdout
