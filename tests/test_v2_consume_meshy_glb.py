"""Fail-closed tests for tools/run_v2_consume_meshy_glb.py (no mesh binaries in git)."""

from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    path = ROOT / "tools" / "run_v2_consume_meshy_glb.py"
    spec = importlib.util.spec_from_file_location("run_v2_consume_meshy_glb", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def consume():
    return _load_runner()


def _minimal_glb_bytes(payload_len: int = 0) -> bytes:
    """Valid glTF-2 GLB container header + zero JSON/BIN (structurally incomplete for engine)."""
    # Empty GLB with only header is invalid length-wise if we claim total=12; OK for header tests.
    total = 12 + payload_len
    return struct.pack("<4sII", b"glTF", 2, total) + (b"\x00" * payload_len)


def test_input_missing(consume, tmp_path):
    missing = tmp_path / "nope.glb"
    out = tmp_path / "out"
    report = consume.run_consume(input_glb=missing, out_dir=out)
    assert report["status"] == "BLOCKED"
    assert report["reason"] == "INPUT_MISSING"
    assert not out.exists()


def test_input_not_glb_suffix(consume, tmp_path):
    path = tmp_path / "asset.fbx"
    path.write_bytes(_minimal_glb_bytes())
    report = consume.run_consume(input_glb=path, out_dir=tmp_path / "out")
    assert report["status"] == "BLOCKED"
    assert report["reason"] == "INPUT_NOT_GLB"


def test_invalid_glb_header(consume, tmp_path):
    path = tmp_path / "fake.glb"
    path.write_bytes(b"NOTGLTFFILE!!!!")
    report = consume.run_consume(input_glb=path, out_dir=tmp_path / "out")
    assert report["status"] == "BLOCKED"
    assert report["reason"] == "INVALID_GLB_HEADER"


def test_input_too_large(consume, tmp_path, monkeypatch):
    path = tmp_path / "big.glb"
    # Valid tiny header claiming length 12; we monkeypatch MAX and st_size check via constant.
    path.write_bytes(_minimal_glb_bytes())
    monkeypatch.setattr(consume, "MAX_INPUT_BYTES", 8)
    report = consume.run_consume(input_glb=path, out_dir=tmp_path / "out")
    assert report["status"] == "BLOCKED"
    assert report["reason"] == "INPUT_TOO_LARGE"


def test_output_already_exists_no_clobber(consume, tmp_path):
    src = tmp_path / "char.glb"
    src.write_bytes(_minimal_glb_bytes())
    out = tmp_path / "out"
    out.mkdir()
    stem = consume._safe_stem(src)
    existing = out / f"{stem}_V2_FACE.glb"
    marker = b"DO_NOT_CLOBBER"
    existing.write_bytes(marker)

    report = consume.run_consume(input_glb=src, out_dir=out)
    assert report["status"] == "BLOCKED"
    assert report["reason"] == "OUTPUT_ALREADY_EXISTS"
    assert existing.read_bytes() == marker
    assert not (out / "CONSUME_E2E_REPORT.json").exists()


def test_talking_inject_fail_blocks(consume, tmp_path, monkeypatch):
    src = tmp_path / "char.glb"
    # Length-matching header only — pipeline will be mocked before deep parse.
    src.write_bytes(_minimal_glb_bytes())
    out = tmp_path / "out"

    monkeypatch.setattr(
        consume,
        "run_flexible_adapter",
        lambda _p: {
            "status": "PASS",
            "mappingView": {"NURION_head": "Head"},
            "semanticAdapterDigest": "deadbeef",
        },
    )

    def _boom(**_kwargs):
        raise RuntimeError("inject exploded")

    # Force path past GLB load by stubbing the heavy chain after CR01.
    monkeypatch.setattr(
        consume,
        "load_gltf_document",
        lambda _p: (
            {
                "skins": [{"joints": [0]}],
                "nodes": [{"name": "Head"}],
                "meshes": [
                    {
                        "primitives": [
                            {
                                "attributes": {
                                    "POSITION": 0,
                                    "JOINTS_0": 1,
                                    "WEIGHTS_0": 2,
                                }
                            }
                        ]
                    }
                ],
            },
            b"\x00" * 64,
            None,
        ),
    )
    monkeypatch.setattr(consume, "resolve_head_joint_local_index", lambda **_k: {"headJointLocalIndex": 0})
    import numpy as np

    n = 4
    monkeypatch.setattr(consume, "_read_f32_vec3", lambda *_a, **_k: np.zeros((n, 3), dtype=np.float32))
    monkeypatch.setattr(consume, "_read_u8_vec4", lambda *_a, **_k: np.zeros((n, 4), dtype=np.uint8))
    monkeypatch.setattr(consume, "_read_f32_vec4", lambda *_a, **_k: np.ones((n, 4), dtype=np.float32))
    monkeypatch.setattr(
        consume,
        "select_facial_vertices_resolved",
        lambda *_a, **_k: {"face": np.ones(n, dtype=bool)},
    )
    monkeypatch.setattr(consume, "build_morph_deltas", lambda *_a, **_k: {"Blink_L": np.zeros((n, 3), dtype=np.float32)})
    def _write_face(_i, o, **_k):
        o.write_bytes(b"face")
        return {"derivedSha256": "abc"}

    monkeypatch.setattr(consume, "write_deformed_glb", _write_face)
    monkeypatch.setattr(consume, "inject_talking_by_name", _boom)

    report = consume.run_consume(input_glb=src, out_dir=out)
    assert report["status"] == "BLOCKED"
    assert report["reason"] == "TALKING_INJECT_FAIL"
    assert (out / "CONSUME_E2E_REPORT.json").is_file()
    assert "path" not in report.get("input", {})


def test_source_mutated_blocks(consume, tmp_path, monkeypatch):
    src = tmp_path / "char.glb"
    src.write_bytes(_minimal_glb_bytes())
    out = tmp_path / "out"

    def _mutate_adapter(_path):
        src.write_bytes(src.read_bytes() + b"X")
        return {
            "status": "PASS",
            "mappingView": {"NURION_head": "Head"},
            "semanticAdapterDigest": "deadbeef",
        }

    monkeypatch.setattr(consume, "run_flexible_adapter", _mutate_adapter)
    report = consume.run_consume(input_glb=src, out_dir=out)
    assert report["status"] == "BLOCKED"
    assert report["reason"] == "SOURCE_MUTATED"


def test_reports_omit_absolute_paths_on_early_block(consume, tmp_path):
    import json

    missing = tmp_path / "missing.glb"
    report = consume.run_consume(input_glb=missing, out_dir=tmp_path / "out")
    blob = json.dumps(report)
    assert ":\\" not in blob and "/Users/" not in blob
    assert "path" not in report.get("input", {})
