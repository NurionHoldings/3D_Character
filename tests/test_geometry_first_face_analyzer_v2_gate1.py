import copy
import unittest

from nurion_qp_geometry_face_v2 import CONTRACT, parameter_hash, validate_contract


class GeometryFirstGate1Tests(unittest.TestCase):
    def test_contract_passes(self): self.assertEqual(validate_contract(), [])
    def test_parameter_hash_is_deterministic(self): self.assertEqual(parameter_hash(), parameter_hash())
    def test_parameter_hash_is_full_sha256(self): self.assertEqual(len(parameter_hash()), 64)
    def test_skin_not_face_gate(self):
        self.assertEqual(CONTRACT["faceLocalization"]["skinColorAsExistenceGate"], "DENY")
    def test_center_occupancy_not_face_gate(self):
        self.assertEqual(CONTRACT["faceLocalization"]["centerSkinOccupancyAsExistenceGate"], "DENY")
    def test_hash_not_shape_source(self):
        self.assertEqual(CONTRACT["geometryIdentityLayer"]["imageHashToShapeValues"], "DENY")
    def test_rgb_mean_not_shape_source(self):
        self.assertEqual(CONTRACT["geometryIdentityLayer"]["meanRgbToShapeValues"], "DENY")
    def test_shape_precedes_texture(self): self.assertTrue(CONTRACT["geometryIdentityLayer"]["shapeBeforeTexture"])
    def test_grayscale_is_auxiliary(self):
        self.assertEqual(CONTRACT["representations"]["grayscaleHighContrastRole"], "AUXILIARY_NOT_SINGLE_SOURCE_OF_TRUTH")
    def test_original_never_overwritten(self):
        self.assertEqual(CONTRACT["representations"]["transformedImageOverwriteOriginal"], "DENY")
    def test_white_fallback_denied(self): self.assertEqual(CONTRACT["skinAndAlbedo"]["forcedWhiteToneFallback"], "DENY")
    def test_neutral_fallback_is_disclosed(self):
        self.assertEqual(CONTRACT["skinAndAlbedo"]["uncertainPolicy"], "SKIN_TONE_UNCERTAIN_NEUTRAL_PLACEHOLDER")
    def test_geometry_failure_abstains(self):
        self.assertEqual(CONTRACT["fallbackPolicy"]["geometryFailure"], "ABSTAIN_RECAPTURE_NO_FABRICATION")
    def test_gate2_is_read_only(self):
        self.assertEqual(CONTRACT["baselinePolicy"]["quickProfileGate2Core"], "READ_ONLY_NO_MUTATION")
    def test_gate3_runner_is_read_only(self):
        self.assertEqual(CONTRACT["baselinePolicy"]["quickProfileGate3Runner"], "READ_ONLY_NO_MUTATION")
    def test_gate8_evidence_denied(self): self.assertEqual(CONTRACT["baselinePolicy"]["gate8Evidence"], "DENY")
    def test_runtime_network_denied(self):
        self.assertEqual(CONTRACT["implementationDependencies"]["networkAtRuntime"], "DENY")
    def test_color_gate_mutation_fails(self):
        changed = copy.deepcopy(CONTRACT); changed["faceLocalization"]["skinColorAsExistenceGate"] = "ALLOW"
        self.assertIn("COLOR_GATE_NOT_DENIED:skinColorAsExistenceGate", validate_contract(changed))
    def test_white_fallback_mutation_fails(self):
        changed = copy.deepcopy(CONTRACT); changed["skinAndAlbedo"]["forcedWhiteToneFallback"] = "ALLOW"
        self.assertIn("WHITE_FALLBACK_NOT_DENIED", validate_contract(changed))
    def test_auto_likeness_mutation_fails(self):
        changed = copy.deepcopy(CONTRACT); changed["fallbackPolicy"]["automaticHumanLikenessPass"] = "ALLOW"
        self.assertIn("AUTO_LIKENESS_PASS_NOT_DENIED", validate_contract(changed))


if __name__ == "__main__": unittest.main()
