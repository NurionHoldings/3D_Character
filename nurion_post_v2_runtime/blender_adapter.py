"""Blender adapter with transactional import rollback and no-clobber publish."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from .contracts import ContractViolation, sha256_file, validate_export_target, validate_fbx_input

_COLLECTIONS = ("objects", "meshes", "armatures", "actions", "materials", "images", "collections", "cameras", "lights")


def _snapshot(data: Any) -> dict:
    return {name: {id(item) for item in getattr(data, name, [])} for name in _COLLECTIONS}


def rollback_new_datablocks(data: Any, before: dict) -> dict:
    removed = {}
    for name in reversed(_COLLECTIONS):
        collection = getattr(data, name, None)
        if collection is None:
            continue
        fresh = [item for item in list(collection) if id(item) not in before.get(name, set())]
        for item in fresh:
            try:
                collection.remove(item, do_unlink=True)
            except TypeError:
                collection.remove(item)
        removed[name] = len(fresh)
    return removed


def import_transaction(bpy_module: Any, path: str | Path) -> dict:
    precheck = validate_fbx_input(path)
    before = _snapshot(bpy_module.data)
    try:
        outcome = bpy_module.ops.import_scene.fbx(filepath=str(precheck["path"]), automatic_bone_orientation=True, use_anim=True)
        if "FINISHED" not in outcome:
            raise RuntimeError("FBX_IMPORT_CANCELLED")
        new_objects = [item.name for item in getattr(bpy_module.data, "objects", []) if id(item) not in before["objects"]]
        if not new_objects:
            raise RuntimeError("FBX_IMPORT_NO_OBJECTS")
    except Exception as exc:
        return {"ok": False, "abort": f"IMPORT_FAILED:{type(exc).__name__}", "rollback": rollback_new_datablocks(bpy_module.data, before)}
    return {
        "ok": True,
        "provenance": {"path": precheck["path"].as_posix(), "size": precheck["size"], "sha256": precheck["sha256"], "importedObjects": sorted(new_objects)},
    }


def publish_no_clobber(temp_path: Path, target: Path) -> dict:
    if not temp_path.is_file() or temp_path.stat().st_size <= 0:
        return {"ok": False, "abort": "EXPORT_TEMP_MISSING"}
    try:
        os.link(temp_path, target)  # atomic no-clobber on one filesystem
    except FileExistsError:
        return {"ok": False, "abort": "EXPORT_TARGET_EXISTS"}
    except OSError:
        return {"ok": False, "abort": "EXPORT_PUBLISH_FAILED"}
    temp_path.unlink()
    return {"ok": target.is_file() and target.stat().st_size > 0, "path": target.as_posix()}


def export_transaction(bpy_module: Any, *, path: str | Path, fmt: str, root: str | Path) -> dict:
    target = validate_export_target(path, fmt=fmt, root=root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.stem}.{secrets.token_hex(8)}.partial{target.suffix}")
    try:
        if str(fmt).upper() == "GLB":
            outcome = bpy_module.ops.export_scene.gltf(filepath=str(temp), export_format="GLB")
        else:
            outcome = bpy_module.ops.export_scene.fbx(filepath=str(temp))
        if "FINISHED" not in outcome:
            raise RuntimeError("EXPORT_CANCELLED")
        result = publish_no_clobber(temp, target)
        if not result["ok"]:
            raise RuntimeError(result["abort"])
        return result
    except Exception as exc:
        if temp.exists():
            temp.unlink()
        return {"ok": False, "abort": f"EXPORT_FAILED:{type(exc).__name__}"}
