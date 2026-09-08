from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256_text(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_asset_manifest(manifest: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    limitations: list[str] = []

    if manifest.get("status") == "EMPTY_TEMPLATE_NOT_EVIDENCE":
        return {
            "verdict": "CONTRACT_PASS_ASSET_REQUIRED",
            "failures": [],
            "limitations": ["CANONICAL_BASE_MESH_NOT_SUBMITTED"],
            "manifestSha256": _sha256_text(manifest),
            "production": "NO-GO",
        }

    asset = manifest.get("asset", {})
    geometry = manifest.get("geometry", {})
    pose = manifest.get("pose", {})
    topology = manifest.get("topology", {})
    ownership = manifest.get("ownership", {})

    for key in (
        "blendSha256", "meshGeometrySha256", "vertexOrderSha256",
        "edgeConnectivitySha256", "uvLayoutSha256", "materialSlotOrderSha256",
    ):
        value = asset.get(key)
        if not isinstance(value, str) or len(value) != 64:
            failures.append(f"ASSET_HASH_INVALID:{key}")

    for key, maximum in {
        "nonManifoldEdges": contract["topology"]["nonManifoldEdgeMax"],
        "looseVertices": contract["topology"]["looseVertexMax"],
        "duplicateVertices": contract["topology"]["duplicateVertexMax"],
        "degenerateFaces": contract["topology"]["degenerateFaceMax"],
    }.items():
        value = geometry.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value > maximum:
            failures.append(f"GEOMETRY_LIMIT_FAIL:{key}")

    if geometry.get("ngonsInDeformationZones") != 0:
        failures.append("NGON_IN_DEFORMATION_ZONE")
    if geometry.get("unit") != contract["topology"]["scaleUnit"]:
        failures.append("UNIT_MISMATCH")
    if geometry.get("worldUp") != contract["topology"]["worldUp"]:
        failures.append("WORLD_UP_MISMATCH")
    if geometry.get("forward") != contract["topology"]["forward"]:
        failures.append("FORWARD_AXIS_MISMATCH")
    if geometry.get("originPolicy") != contract["topology"]["origin"]:
        failures.append("ORIGIN_POLICY_MISMATCH")

    if pose.get("name") != contract["pose"]["required"]:
        failures.append("REST_POSE_UNSUPPORTED")
    for key in ("symmetric", "armBodyClearance", "fingersSeparated", "feetForward", "faceNeutral"):
        if pose.get(key) is not True:
            failures.append(f"POSE_REQUIREMENT_FAIL:{key}")

    if topology.get("manifold") is not True:
        failures.append("MESH_NOT_MANIFOLD")
    if topology.get("uvPresent") is not True:
        failures.append("UV_MISSING")
    if topology.get("faceDedicatedUvRegion") is not True:
        failures.append("FACE_UV_REGION_MISSING")
    missing_groups = sorted(set(contract["requiredVertexGroups"]) - set(topology.get("requiredVertexGroupsPresent", [])))
    failures.extend(f"VERTEX_GROUP_MISSING:{name}" for name in missing_groups)

    if not ownership.get("sourceDeclaration"):
        failures.append("OWNERSHIP_SOURCE_UNDECLARED")
    license_hash = ownership.get("creatorOrLicenseEvidenceSha256")
    if not isinstance(license_hash, str) or len(license_hash) != 64:
        failures.append("OWNERSHIP_EVIDENCE_MISSING")
    if ownership.get("commercialModification") is not True:
        failures.append("COMMERCIAL_MODIFICATION_NOT_GRANTED")
    if ownership.get("commercialDistribution") is not True:
        failures.append("COMMERCIAL_DISTRIBUTION_NOT_GRANTED")
    if ownership.get("thirdPartyRestrictions"):
        limitations.append("THIRD_PARTY_RESTRICTIONS_DISCLOSED")

    if manifest.get("sourceMutation") != 0:
        failures.append("SOURCE_MUTATION_NONZERO")

    verdict = "PASS" if not failures and not limitations else "PASS_WITH_LIMITATIONS" if not failures else "ASSET_INELIGIBLE"
    return {
        "verdict": verdict,
        "failures": failures,
        "limitations": limitations,
        "manifestSha256": _sha256_text(manifest),
        "production": "NO-GO",
    }
