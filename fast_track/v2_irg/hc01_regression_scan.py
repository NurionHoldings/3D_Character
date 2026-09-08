"""IRG HC-01 / generalization regression scan (self-contained; does not import gap01_pipeline)."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


def _ast_calls_cr02_select_facial(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "v2_cr02" in mod and "facial_deformation" in mod:
                for alias in node.names:
                    if alias.name == "select_facial_vertices":
                        return True
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "select_facial_vertices":
                return True
            if isinstance(fn, ast.Attribute) and fn.attr == "select_facial_vertices":
                return True
    return False


def _ast_assigns_forbidden_facial_sot(text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [{"code": "CR04_PARSE_FAIL"}]
    forbidden = {"HEAD_SKIN_LOCAL", "FACE_Y_MIN"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in forbidden:
                    hits.append(
                        {
                            "code": "CR04_EMBEDS_IDLE15_FACIAL_SOT",
                            "name": t.id,
                            "line": getattr(node, "lineno", None),
                        }
                    )
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in forbidden:
                hits.append(
                    {
                        "code": "CR04_EMBEDS_IDLE15_FACIAL_SOT",
                        "name": node.target.id,
                        "line": getattr(node, "lineno", None),
                    }
                )
    return hits


def expanded_hardcoding_scan(repo_root: Path) -> dict[str, Any]:
    """Document CR02 Idle_15 facial SoT as historical; fail if CR04/IRG consume path embeds it."""
    blockers: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []

    cr02 = repo_root / "fast_track" / "v2_cr02" / "facial_deformation.py"
    if not cr02.is_file():
        blockers.append({"code": "PROOF_PACKAGE_INCOMPLETE", "missing": "v2_cr02/facial_deformation.py"})
    else:
        text_cr02 = cr02.read_text(encoding="utf-8")
        _cr02_head = "HEAD_SKIN_LOCAL" + " = " + "21"
        _cr02_ymin = "FACE_Y_MIN" + " = " + "1.28"
        if _cr02_head in text_cr02 and _cr02_ymin in text_cr02:
            notes.append(
                {
                    "file": "fast_track/v2_cr02/facial_deformation.py",
                    "disposition": "HISTORICAL_CR02_CONSUME_ONLY_UNCHANGED",
                    "literals": ["HEAD_SKIN_LOCAL=21", "FACE_Y_MIN=1.28"],
                }
            )
        else:
            notes.append({"file": str(cr02), "disposition": "UNEXPECTED_CR02_LITERAL_CHANGE"})

    for rel in (
        "fast_track/v2_cr04/facial_region_resolve.py",
        "fast_track/v2_cr04/gap01_pipeline.py",
        "fast_track/v2_cr04/fasttrack.py",
        "fast_track/v2_irg/fasttrack.py",
        "fast_track/v2_irg/hc01_regression_scan.py",
    ):
        path = repo_root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if _ast_calls_cr02_select_facial(text):
            blockers.append({"code": "CR04_CALLS_CR02_SELECT_FACIAL", "file": rel})
        for hit in _ast_assigns_forbidden_facial_sot(text):
            blockers.append({**hit, "file": rel})

    res_path = repo_root / "fast_track/v2_cr04/facial_region_resolve.py"
    if res_path.is_file():
        res = res_path.read_text(encoding="utf-8")
        if re.search(r"head_local_index\s*=\s*21\b", res) or re.search(r"HEAD_SKIN_LOCAL\s*=\s*21\b", res):
            blockers.append({"code": "RESOLVER_HARDCODES_21"})
        if "FACE_Y_MIN" in res and re.search(r"FACE_Y_MIN\s*=", res):
            blockers.append({"code": "RESOLVER_EMBEDS_FACE_Y_MIN"})

    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "notes": notes,
        "blockers": blockers,
        "covers": [
            "v2_cr04 / v2_irg facial consume path (AST)",
            "documents CR02 historical literals without treating them as release SoT",
        ],
    }
