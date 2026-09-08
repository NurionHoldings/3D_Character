import copy
import unittest
from pathlib import Path

import cv2
import numpy as np

from nurion_qp_geometry_face_v2.contract import CONTRACT, parameter_hash as gate1_hash
from nurion_qp_geometry_face_v2.gate2_selection import (
    GATE2_SELECTION,
    parameter_hash,
    validate_selection,
    verify_offline_model_bytes,
)

ROOT = Path(__file__).resolve().parents[1]


class GeometryFirstGate2Tests(unittest.TestCase):
    def test_selection_passes(self):
        self.assertEqual(validate_selection(), [])

    def test_parameter_hash_full_and_deterministic(self):
        self.assertEqual(len(parameter_hash()), 64)
        self.assertEqual(parameter_hash(), parameter_hash())

    def test_gate1_pin_unchanged(self):
        self.assertEqual(
            GATE2_SELECTION["gate1ParameterHash"],
            "e2e90a2fac7f5b64ecd6c73b63b7852782249a0593ee594bc414ce293d21ff8a",
        )
        self.assertEqual(
            gate1_hash(),
            "e2e90a2fac7f5b64ecd6c73b63b7852782249a0593ee594bc414ce293d21ff8a",
        )

    def test_detector_is_skin_independent(self):
        self.assertEqual(
            GATE2_SELECTION["faceDetector"]["skinColorAsExistenceGate"], "DENY"
        )

    def test_dense_landmark_count(self):
        self.assertGreaterEqual(
            GATE2_SELECTION["denseFaceLandmarker"]["declaredDenseLandmarkCount"], 468
        )

    def test_runtime_network_denied(self):
        self.assertEqual(GATE2_SELECTION["baselinePolicy"]["runtimeNetwork"], "DENY")
        self.assertEqual(GATE2_SELECTION["faceDetector"]["runtimeFetch"], "DENY")
        self.assertEqual(GATE2_SELECTION["denseFaceLandmarker"]["runtimeFetch"], "DENY")

    def test_real_participants_denied(self):
        self.assertEqual(GATE2_SELECTION["baselinePolicy"]["realParticipantUsage"], "DENY")

    def test_qp_baselines_read_only(self):
        self.assertEqual(
            GATE2_SELECTION["baselinePolicy"]["quickProfileGate2Core"],
            "READ_ONLY_NO_MUTATION",
        )
        self.assertEqual(
            GATE2_SELECTION["baselinePolicy"]["quickProfileGate3Runner"],
            "READ_ONLY_NO_MUTATION",
        )

    def test_offline_model_bytes_match_pins(self):
        self.assertEqual(verify_offline_model_bytes(ROOT), [])

    def test_input_branches_include_clahe(self):
        branches = GATE2_SELECTION["inputCompatibility"]["acceptedBranches"]
        for name in ("ORIGINAL_RGB", "LUMINANCE", "GRAYSCALE", "GRAYSCALE_CLAHE"):
            self.assertIn(name, branches)

    def test_synthetic_branch_tensors_are_hwc_uint8_3ch(self):
        # Synthetic only — never P001-P003 real packages.
        rgb = np.zeros((128, 128, 3), dtype=np.uint8)
        rgb[32:96, 40:88] = (180, 140, 120)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        lum = gray  # luminance proxy for compatibility shape test
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

        def to_3ch(img: np.ndarray) -> np.ndarray:
            if img.ndim == 2:
                return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            return img

        for name, arr in (
            ("ORIGINAL_RGB", rgb),
            ("LUMINANCE", lum),
            ("GRAYSCALE", gray),
            ("GRAYSCALE_CLAHE", clahe),
        ):
            out = to_3ch(arr)
            self.assertEqual(out.dtype, np.uint8, name)
            self.assertEqual(out.ndim, 3, name)
            self.assertEqual(out.shape[2], 3, name)

    def test_canonical_output_contract(self):
        out = GATE2_SELECTION["canonicalOutputContract"]
        self.assertEqual(
            out["coordinateFrame"],
            CONTRACT["poseNormalization"]["coordinateFrame"],
        )
        self.assertEqual(out["automaticHumanLikenessPass"], "DENY")
        self.assertEqual(out["faceAuthentication"], "OUT_OF_SCOPE")

    def test_network_mutation_fails(self):
        changed = copy.deepcopy(GATE2_SELECTION)
        changed["baselinePolicy"]["runtimeNetwork"] = "ALLOW"
        self.assertIn("RUNTIME_NETWORK_NOT_DENIED", validate_selection(changed))

    def test_qp_gate2_core_and_runner_hashes_unmutated(self):
        import hashlib

        runner = ROOT / "tools/run_quick_profile_gate3_consented_human_review.py"
        core = ROOT / "tools/nurion_quick_profile_core.py"
        self.assertTrue(runner.is_file() and core.is_file())
        self.assertEqual(
            hashlib.sha256(runner.read_bytes()).hexdigest(),
            "13837c5e5b4a31e9efb10c83528703375df44f59ac15babb69207a57e22dbcc4",
        )
        g2 = __import__("json").loads(
            (
                ROOT
                / "dist/v0.7/product/quick_profile/gate2/V07_QP_GATE2_OFFICIAL_FREEZE.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            g2["parameterHash"],
            "f58def1d79f66b0a04189b9694af3ddb7283e5236b4288f511434c6577b545b3",
        )
        g3r = __import__("json").loads(
            (
                ROOT
                / "dist/v0.7/product/quick_profile/gate3/runner/V07_QP_GATE3_RUNNER_OFFICIAL_FREEZE.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            g3r["runnerParameterHash"],
            "20333fb895860d02a0a6096107ff14cc94078290abe58c93ed814b04ef89a4e5",
        )


if __name__ == "__main__":
    unittest.main()
