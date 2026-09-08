"""Cryptographic upstream binding for ADAPT-02 — pins locked BODY/Axis artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fast_track.adaptation.inspector import canonical_dumps, canonical_sha256

# Authoritative locked upstream identities + SHA256 (file bytes, not canonical JSON)
AUTHORITATIVE_BODY_SPEC_ID = "NURION_BODY_CANONICAL_BONE_SPEC_V1"
AUTHORITATIVE_BODY_SPEC_SHA256 = (
    "c73b5c540e29fcbf4ef4477c51f869eead9640194cec21110c6d60e55d1f900a"
)
AUTHORITATIVE_BODY_SPEC_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json"
)

AUTHORITATIVE_AXIS_ID = "NURION_BODY_AXIS_RETARGET_CONVENTION_V1"
AUTHORITATIVE_AXIS_SHA256 = (
    "19da5a00f4943a144426efaf675d364f64d244773dc60ede7db81be5bb8c6d9a"
)
AUTHORITATIVE_AXIS_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_body_core_snapshot(bone_spec: dict[str, Any]) -> dict[str, Any]:
    core = bone_spec["tiers"]["BODY_CORE_V1"]
    decisions = (bone_spec.get("hierarchySemantics") or {}).get("decisions") or {}
    return {
        "schema": "NURION_ADAPT02_BODY_CORE_SNAPSHOT_V1",
        "sourceIdentity": AUTHORITATIVE_BODY_SPEC_ID,
        "bones": list(core["bones"]),
        "hierarchy": dict(core["hierarchy"]),
        "invariants": {
            "rootPelvisDistinct": True,
            "rootPelvisNeverMerge": decisions.get("root_pelvis_never_merge") == "CONFIRMED",
        },
    }


def extract_axis_snapshot(axis_spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "NURION_ADAPT02_AXIS_SNAPSHOT_V1",
        "sourceIdentity": AUTHORITATIVE_AXIS_ID,
        "up": axis_spec["2_worldUpAxis"]["canonical"],
        "forward": axis_spec["3_characterForwardAxis"]["canonical"],
        "right": axis_spec["1_coordinateSystem"]["canonicalBasis"]["right"],
        "handedness": axis_spec["4_handedness"]["canonical"],
        "unitScale": axis_spec["5_unitScale"]["canonical"],
    }


def snapshot_digest(snapshot: dict[str, Any]) -> str:
    return canonical_sha256(snapshot)


def derive_from_upstream_files(
    bone_path: Path,
    axis_path: Path,
) -> dict[str, Any]:
    """READ_ONLY extract — fails if upstream SHA256 != pinned authoritative values."""
    if not bone_path.is_file():
        raise FileNotFoundError(f"missing authoritative BODY spec: {bone_path}")
    if not axis_path.is_file():
        raise FileNotFoundError(f"missing authoritative Axis convention: {axis_path}")

    bone_sha = sha256_file(bone_path)
    axis_sha = sha256_file(axis_path)
    if bone_sha != AUTHORITATIVE_BODY_SPEC_SHA256:
        raise ValueError(
            f"BODY spec SHA256 mismatch: observed {bone_sha} != pinned {AUTHORITATIVE_BODY_SPEC_SHA256}"
        )
    if axis_sha != AUTHORITATIVE_AXIS_SHA256:
        raise ValueError(
            f"Axis convention SHA256 mismatch: observed {axis_sha} != pinned {AUTHORITATIVE_AXIS_SHA256}"
        )

    bone_spec = json.loads(bone_path.read_text(encoding="utf-8"))
    axis_spec = json.loads(axis_path.read_text(encoding="utf-8"))
    body_snap = extract_body_core_snapshot(bone_spec)
    axis_snap = extract_axis_snapshot(axis_spec)

    return {
        "upstream": {
            "bodyCanonicalSpec": {
                "identity": AUTHORITATIVE_BODY_SPEC_ID,
                "sha256": AUTHORITATIVE_BODY_SPEC_SHA256,
                "repoRel": AUTHORITATIVE_BODY_SPEC_REL,
            },
            "axisRetargetConvention": {
                "identity": AUTHORITATIVE_AXIS_ID,
                "sha256": AUTHORITATIVE_AXIS_SHA256,
                "repoRel": AUTHORITATIVE_AXIS_REL,
            },
        },
        "snapshot": {
            "derivation": "READ_ONLY_EXTRACT",
            "bodyCoreSnapshotFile": "semantic/NURION_ADAPT02_BODY_CORE_SNAPSHOT_V1.json",
            "axisSnapshotFile": "semantic/NURION_ADAPT02_AXIS_SNAPSHOT_V1.json",
            "bodyCoreDigest": snapshot_digest(body_snap),
            "axisConventionDigest": snapshot_digest(axis_snap),
        },
        "bodyCoreSnapshot": body_snap,
        "axisSnapshot": axis_snap,
        "observedUpstreamSha256": {"body": bone_sha, "axis": axis_sha},
    }


def verify_authoritative_binding(
    binding: dict[str, Any],
    *,
    repo_root: Path | None = None,
    body_snapshot_path: Path | None = None,
    axis_snapshot_path: Path | None = None,
    provenance_path: Path | None = None,
) -> dict[str, Any]:
    """
    Verify cryptographic pins. FAIL CLOSED on any mismatch.
    Works in monorepo (live upstream compare) and extracted ZIP (pins + snapshot files).
    """
    result: dict[str, Any] = {
        "status": "PASS",
        "mode": "UNKNOWN",
        "checks": [],
        "blockers": [],
    }

    def fail(code: str, msg: str) -> None:
        result["status"] = "BLOCKED"
        result["blockers"].append({"code": code, "message": msg})

    upstream = binding.get("upstream") or {}
    snap_meta = binding.get("snapshot") or {}

    # 1. Pinned upstream identities must match locked constants
    body_up = upstream.get("bodyCanonicalSpec") or {}
    axis_up = upstream.get("axisRetargetConvention") or {}
    if body_up.get("identity") != AUTHORITATIVE_BODY_SPEC_ID:
        fail("UPSTREAM_IDENTITY_MISMATCH", "bodyCanonicalSpec identity")
    if body_up.get("sha256") != AUTHORITATIVE_BODY_SPEC_SHA256:
        fail("UPSTREAM_SHA256_PIN_MISMATCH", "bodyCanonicalSpec sha256 pin")
    if axis_up.get("identity") != AUTHORITATIVE_AXIS_ID:
        fail("UPSTREAM_IDENTITY_MISMATCH", "axisRetargetConvention identity")
    if axis_up.get("sha256") != AUTHORITATIVE_AXIS_SHA256:
        fail("UPSTREAM_SHA256_PIN_MISMATCH", "axisRetargetConvention sha256 pin")
    result["checks"].append("pinned_upstream_identities")

    expected_body_digest = snap_meta.get("bodyCoreDigest")
    expected_axis_digest = snap_meta.get("axisConventionDigest")
    if not expected_body_digest or not expected_axis_digest:
        fail("SNAPSHOT_DIGEST_MISSING", "binding.snapshot digests required")
        return result

    # 2. Load snapshot artifacts from files or binding-embedded copies
    body_snap: dict[str, Any] | None = None
    axis_snap: dict[str, Any] | None = None
    if body_snapshot_path and body_snapshot_path.is_file():
        body_snap = json.loads(body_snapshot_path.read_text(encoding="utf-8"))
    if axis_snapshot_path and axis_snapshot_path.is_file():
        axis_snap = json.loads(axis_snapshot_path.read_text(encoding="utf-8"))

    # 3. Verify snapshot digests
    if body_snap:
        obs = snapshot_digest(body_snap)
        if obs != expected_body_digest:
            fail("BODY_SNAPSHOT_DIGEST_MISMATCH", f"observed {obs} != {expected_body_digest}")
        else:
            result["checks"].append("body_snapshot_digest")
    if axis_snap:
        obs = snapshot_digest(axis_snap)
        if obs != expected_axis_digest:
            fail("AXIS_SNAPSHOT_DIGEST_MISMATCH", f"observed {obs} != {expected_axis_digest}")
        else:
            result["checks"].append("axis_snapshot_digest")

    # 4. Verify binding operational fields match body snapshot (semantic link)
    if body_snap:
        if list(binding.get("bodyCore23") or []) != body_snap.get("bones"):
            fail("BINDING_BODY_CORE_MISMATCH", "bodyCore23 != snapshot bones")
        if dict(binding.get("hierarchy") or {}) != body_snap.get("hierarchy"):
            fail("BINDING_HIERARCHY_MISMATCH", "hierarchy != snapshot hierarchy")
        else:
            result["checks"].append("binding_body_semantic_link")

    # 5. Verify binding axis matches axis snapshot
    if axis_snap:
        canon = binding.get("canonicalAxis") or {}
        expected_axis_binding = {
            "up": axis_snap["up"],
            "forward": axis_snap["forward"],
            "right": axis_snap["right"],
            "handedness": axis_snap["handedness"],
        }
        for k, v in expected_axis_binding.items():
            if canon.get(k) != v:
                fail("BINDING_AXIS_MISMATCH", f"canonicalAxis.{k}")
        if result["status"] == "PASS":
            result["checks"].append("binding_axis_semantic_link")

    # 6. Monorepo: live upstream file verification
    if repo_root is not None:
        result["mode"] = "MONOREPO_LIVE_VERIFY"
        bone_path = repo_root / AUTHORITATIVE_BODY_SPEC_REL
        axis_path = repo_root / AUTHORITATIVE_AXIS_REL
        if not bone_path.is_file() or not axis_path.is_file():
            fail("UPSTREAM_FILES_MISSING", "authoritative upstream files absent in monorepo")
        else:
            if sha256_file(bone_path) != AUTHORITATIVE_BODY_SPEC_SHA256:
                fail("UPSTREAM_BODY_FILE_SHA_MISMATCH", "live BODY spec changed")
            if sha256_file(axis_path) != AUTHORITATIVE_AXIS_SHA256:
                fail("UPSTREAM_AXIS_FILE_SHA_MISMATCH", "live Axis convention changed")
            try:
                derived = derive_from_upstream_files(bone_path, axis_path)
                if derived["snapshot"]["bodyCoreDigest"] != expected_body_digest:
                    fail("LIVE_DERIVATION_BODY_MISMATCH", "live extract != binding digest")
                if derived["snapshot"]["axisConventionDigest"] != expected_axis_digest:
                    fail("LIVE_DERIVATION_AXIS_MISMATCH", "live extract != binding digest")
                else:
                    result["checks"].append("monorepo_live_upstream_match")
            except (ValueError, KeyError) as e:
                fail("LIVE_DERIVATION_FAILED", str(e))
    else:
        result["mode"] = "EXTRACTED_PIN_VERIFY"
        if not body_snap or not axis_snap:
            fail("SNAPSHOT_FILES_REQUIRED", "extracted package must include snapshot JSON files")
        if provenance_path and provenance_path.is_file():
            prov = json.loads(provenance_path.read_text(encoding="utf-8"))
            if prov.get("upstream", {}).get("bodyCanonicalSpec", {}).get("sha256") != AUTHORITATIVE_BODY_SPEC_SHA256:
                fail("PROVENANCE_BODY_PIN_MISMATCH", "provenance receipt body pin")
            if prov.get("upstream", {}).get("axisRetargetConvention", {}).get("sha256") != AUTHORITATIVE_AXIS_SHA256:
                fail("PROVENANCE_AXIS_PIN_MISMATCH", "provenance receipt axis pin")
            if prov.get("snapshot", {}).get("bodyCoreDigest") != expected_body_digest:
                fail("PROVENANCE_BODY_DIGEST_MISMATCH", "provenance body digest")
            if prov.get("snapshot", {}).get("axisConventionDigest") != expected_axis_digest:
                fail("PROVENANCE_AXIS_DIGEST_MISMATCH", "provenance axis digest")
            else:
                result["checks"].append("provenance_receipt_pins")
        else:
            fail("PROVENANCE_RECEIPT_MISSING", "NURION-ADAPT-02_UPSTREAM_PROVENANCE_RECEIPT.json required")

    result["authoritativePins"] = {
        "bodyCanonicalSpecSha256": AUTHORITATIVE_BODY_SPEC_SHA256,
        "axisRetargetConventionSha256": AUTHORITATIVE_AXIS_SHA256,
        "bodyCoreDigest": expected_body_digest,
        "axisConventionDigest": expected_axis_digest,
    }
    return result
