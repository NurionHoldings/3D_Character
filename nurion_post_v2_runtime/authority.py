"""Deterministic source authority resolution independent from Blender."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .contracts import ContractViolation


@dataclass(frozen=True)
class SourceArmature:
    name: str


@dataclass(frozen=True)
class SourceMesh:
    name: str
    armature_name: str
    skinned: bool


def select_source_authority(
    armatures: Iterable[SourceArmature], meshes: Iterable[SourceMesh], *, armature_name: str = "", mesh_name: str = ""
) -> tuple[SourceArmature, SourceMesh]:
    arms = list(armatures)
    if armature_name:
        arms = [item for item in arms if item.name == armature_name]
    if len(arms) != 1:
        raise ContractViolation("SOURCE_ARMATURE_NOT_UNIQUE")
    arm = arms[0]
    candidates = [item for item in meshes if item.skinned and item.armature_name == arm.name]
    if mesh_name:
        candidates = [item for item in candidates if item.name == mesh_name]
    if len(candidates) != 1:
        raise ContractViolation("SOURCE_MESH_NOT_UNIQUE")
    return arm, candidates[0]
