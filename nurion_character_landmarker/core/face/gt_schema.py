"""Face ground-truth schema — evaluation only (never feed into generation)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from mathutils import Vector

from ..landmark_engine import LandmarkPoint
from .keys import FACE_LANDMARK_KEYS_FULL
from .spaces import HeadFrame, face_entry


SCHEMA = "NURION_FACE_GROUND_TRUTH"
VERSION = "0.3.0-alpha.1"


def empty_face_gt_document(
    *,
    character_id: str,
    mesh_name: str,
    head_frame: Optional[dict] = None,
) -> dict:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "characterId": character_id,
        "meshName": mesh_name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "space": {
            "world": True,
            "headLocal": True,
            "note": "GT is evaluation-only. Never used for candidate generation.",
        },
        "headFrame": head_frame or {},
        "landmarks": [
            {
                "name": name,
                "positionWorld": None,
                "positionHeadLocal": None,
                "source": "MANUAL",
                "confidence": 1.0,
                "reviewRequired": False,
                "annotated": False,
            }
            for name in FACE_LANDMARK_KEYS_FULL
        ],
    }


def landmarks_to_gt(
    landmarks: Dict[str, LandmarkPoint],
    frame: HeadFrame,
    *,
    character_id: str,
    mesh_name: str,
) -> dict:
    doc = empty_face_gt_document(
        character_id=character_id,
        mesh_name=mesh_name,
        head_frame={
            "origin": [round(float(x), 6) for x in frame.origin],
            "forward": [round(float(x), 6) for x in frame.forward],
            "right": [round(float(x), 6) for x in frame.right],
            "up": [round(float(x), 6) for x in frame.up],
            "headHeight": round(float(frame.head_height), 6),
        },
    )
    by_name = {e["name"]: e for e in doc["landmarks"]}
    for name, lp in landmarks.items():
        if name not in by_name:
            continue
        entry = face_entry(
            name,
            lp.position,
            frame,
            source="MANUAL",
            confidence=1.0,
            review_required=False,
        )
        by_name[name].update(
            {
                "positionWorld": entry["positionWorld"],
                "positionHeadLocal": entry["positionHeadLocal"],
                "annotated": True,
                "source": "MANUAL",
                "confidence": 1.0,
                "reviewRequired": False,
            }
        )
    doc["annotatedCount"] = sum(1 for e in doc["landmarks"] if e.get("annotated"))
    return doc


def load_face_gt(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"Unexpected face GT schema: {data.get('schema')}")
    return data


def save_face_gt(doc: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def gt_positions_world(doc: dict) -> Dict[str, Vector]:
    out: Dict[str, Vector] = {}
    for e in doc.get("landmarks", []):
        pw = e.get("positionWorld")
        if not pw or not e.get("annotated", True):
            continue
        if pw[0] is None:
            continue
        out[e["name"]] = Vector((float(pw[0]), float(pw[1]), float(pw[2])))
    return out
