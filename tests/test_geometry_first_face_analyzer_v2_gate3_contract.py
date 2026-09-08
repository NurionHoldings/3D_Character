import unittest

from nurion_qp_geometry_face_v2.gate3_contract import GATE3_CONTRACT, gate3_parameter_hash


class Gate3ContractTests(unittest.TestCase):
    def test_hash_full_and_deterministic(self): self.assertEqual(len(gate3_parameter_hash()), 64); self.assertEqual(gate3_parameter_hash(), gate3_parameter_hash())
    def test_gate2_official_pin(self): self.assertEqual(GATE3_CONTRACT["gate2OfficialParameterHash"], "93d87283d3a5492d6c2773f46122f4d32cce63026bfa77f111a956fd4345fc60")
    def test_runtime_network_denied(self): self.assertEqual(GATE3_CONTRACT["runtime"]["network"], "DENY")
    def test_real_participants_denied(self): self.assertEqual(GATE3_CONTRACT["validation"]["realParticipantUsage"], 0)
    def test_actual_model_inference_not_claimed(self): self.assertEqual(GATE3_CONTRACT["runtime"]["actualPinnedModelInference"], "NOT_EXECUTED")
    def test_production_no_go(self): self.assertEqual(GATE3_CONTRACT["baseline"]["production"], "NO-GO")


if __name__ == "__main__": unittest.main()
