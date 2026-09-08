import unittest
from copy import deepcopy
from pathlib import Path

from nurion_ccs_gate1 import load_json, validate_asset_manifest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_json(ROOT / "dist/v0.7/canonical/gate1/V07_CCS_GATE1_TOPOLOGY_CONTRACT.json")
TEMPLATE = load_json(ROOT / "dist/v0.7/canonical/gate1/V07_CCS_GATE1_ASSET_MANIFEST_TEMPLATE.json")


def valid_manifest():
    value = deepcopy(TEMPLATE)
    value["status"] = "ASSET_EVIDENCE_COMPLETE"
    value["asset"] = {
        "name": "canonical-base",
        "path": "canonical-base.blend",
        "blendSha256": "1" * 64,
        "meshGeometrySha256": "2" * 64,
        "vertexOrderSha256": "3" * 64,
        "edgeConnectivitySha256": "4" * 64,
        "uvLayoutSha256": "5" * 64,
        "materialSlotOrderSha256": "6" * 64,
    }
    value["geometry"] = {
        "objectCount": 1,
        "vertexCount": 100,
        "edgeCount": 200,
        "faceCount": 100,
        "nonManifoldEdges": 0,
        "looseVertices": 0,
        "duplicateVertices": 0,
        "degenerateFaces": 0,
        "ngonsInDeformationZones": 0,
        "unit": "METER",
        "worldUp": "+Z",
        "forward": "-Y",
        "originPolicy": "FLOOR_CENTER_BETWEEN_FEET",
    }
    value["pose"] = {
        "name": "RELAXED_A_POSE",
        "symmetric": True,
        "armBodyClearance": True,
        "fingersSeparated": True,
        "feetForward": True,
        "faceNeutral": True,
    }
    value["topology"] = {
        "manifold": True,
        "requiredVertexGroupsPresent": CONTRACT["requiredVertexGroups"],
        "uvPresent": True,
        "faceDedicatedUvRegion": True,
        "declaredSymmetryOverlaps": [],
    }
    value["ownership"] = {
        "sourceDeclaration": "OWNED_ORIGINAL",
        "creatorOrLicenseEvidenceSha256": "a" * 64,
        "commercialModification": True,
        "commercialDistribution": True,
        "thirdPartyRestrictions": [],
        "reviewedBy": "reviewer-001",
        "reviewedAt": "2026-08-15T00:00:00+09:00",
    }
    return value


class CanonicalGate1Test(unittest.TestCase):
    def test_empty_template_waits_for_asset(self):
        result = validate_asset_manifest(TEMPLATE, CONTRACT)
        self.assertEqual("CONTRACT_PASS_ASSET_REQUIRED", result["verdict"])

    def test_valid_asset_manifest_passes_deterministically(self):
        first = validate_asset_manifest(valid_manifest(), CONTRACT)
        second = validate_asset_manifest(valid_manifest(), CONTRACT)
        self.assertEqual("PASS", first["verdict"])
        self.assertEqual(first["manifestSha256"], second["manifestSha256"])

    def test_mesh_defect_is_ineligible(self):
        value = valid_manifest()
        value["geometry"]["nonManifoldEdges"] = 1
        result = validate_asset_manifest(value, CONTRACT)
        self.assertEqual("ASSET_INELIGIBLE", result["verdict"])
        self.assertIn("GEOMETRY_LIMIT_FAIL:nonManifoldEdges", result["failures"])

    def test_ownership_is_mandatory(self):
        value = valid_manifest()
        value["ownership"]["commercialDistribution"] = False
        result = validate_asset_manifest(value, CONTRACT)
        self.assertIn("COMMERCIAL_DISTRIBUTION_NOT_GRANTED", result["failures"])

    def test_pose_and_fingers_are_mandatory(self):
        value = valid_manifest()
        value["pose"]["fingersSeparated"] = False
        result = validate_asset_manifest(value, CONTRACT)
        self.assertIn("POSE_REQUIREMENT_FAIL:fingersSeparated", result["failures"])


if __name__ == "__main__":
    unittest.main()
