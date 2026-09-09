"""Offline-only smoke for the isolated Post-V2 state machine."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nurion_post_v2_runtime.state_machine import PostV2RuntimeEngine


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "asset.fbx"
        source.write_bytes(b"fbx")
        engine = PostV2RuntimeEngine()
        assert engine.precheck_fbx(source)["ok"]
        # This is intentionally an offline state assertion; Blender transaction
        # execution belongs to a configured Blender job.
        assert engine.record_import({"ok": False, "abort": "OFFLINE_NO_BLENDER"})["ok"] is False
    print("post-v2-offline-smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
