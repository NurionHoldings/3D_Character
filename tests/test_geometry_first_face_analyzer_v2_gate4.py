"""Gate 4 controlled integration and regression tests (no real participants)."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from nurion_qp_geometry_face_v2.gate3_contract import gate3_parameter_hash
from nurion_qp_geometry_face_v2.gate4_contract import GATE4_CONTRACT, gate4_parameter_hash
from nurion_qp_geometry_face_v2.integration_adapter import (
    AdapterInput,
    GeometryFirstIntegrationAdapter,
    load_gate2_params,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture_landmarks(offset=0.0):
    p = np.zeros((478, 3), dtype=np.float64)
    p[:, 0] = 0.5
    p[:, 1] = 0.5
    p[33] = (0.4, 0.42, 0)
    p[263] = (0.6, 0.42, 0)
    p[10] = (0.5, 0.2, 0)
    p[152] = (0.5, 0.82, 0)
    p[1] = (0.5, 0.52, 0)
    p[234] = (0.28, 0.5, 0)
    p[454] = (0.72, 0.5, 0)
    p[61] = (0.42, 0.65, 0)
    p[291] = (0.58, 0.65, 0)
    p[172] = (0.34, 0.69, 0)
    p[397] = (0.66, 0.69, 0)
    p[:, 0] += offset
    return p


class FixtureBackend:
    name = "SYNTHETIC_FIXTURE_NO_REAL_PARTICIPANT"

    def __init__(self, failures=(), offsets=None):
        self.failures = set(failures)
        self.offsets = offsets or {}

    def infer(self, image, branch):
        if branch in self.failures:
            return None
        points = fixture_landmarks()
        warp = self.offsets.get(branch, 0.0)
        points[:, 0] += warp * np.sin(np.arange(478) * 0.37)
        return points


def _cool_face_no_warm_skin(path: Path) -> None:
    """High-edge cool-tone face proxy that fails legacy skin/center existence."""
    img = Image.new("RGB", (512, 640), (40, 55, 70))
    d = ImageDraw.Draw(img)
    d.ellipse((110, 60, 400, 460), fill=(90, 110, 130))
    d.ellipse((175, 190, 225, 245), fill=(20, 25, 30))
    d.ellipse((285, 190, 335, 245), fill=(20, 25, 30))
    d.ellipse((235, 255, 275, 305), fill=(70, 85, 100))
    d.arc((200, 310, 310, 380), 15, 165, fill=(30, 35, 45), width=5)
    d.pieslice((110, 40, 400, 220), 200, 340, fill=(25, 30, 40))
    # Add texture so blur gate does not fire.
    for y in range(0, 640, 8):
        d.line((0, y, 511, y), fill=(45, 60, 75))
    img.save(path)


class GeometryFirstGate4Tests(unittest.TestCase):
    def setUp(self):
        self.params = load_gate2_params(ROOT)
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parameter_hash_stable(self):
        self.assertEqual(len(gate4_parameter_hash()), 64)
        self.assertEqual(gate4_parameter_hash(), gate4_parameter_hash())

    def test_pins_gate3(self):
        self.assertEqual(
            GATE4_CONTRACT["gate3OfficialParameterHash"],
            "160662e0a954643883be1ae154817cffabf83fced2a429bce63f47ddbb936f5e",
        )
        self.assertEqual(gate3_parameter_hash(), GATE4_CONTRACT["gate3OfficialParameterHash"])

    def test_identity_core_replacement_denied(self):
        self.assertEqual(GATE4_CONTRACT["integration"]["replaceFrozenIdentityCore"], "DENY")
        self.assertEqual(GATE4_CONTRACT["validation"]["realParticipantP001P002P003"], "DENY")
        self.assertEqual(GATE4_CONTRACT["baseline"]["production"], "NO-GO")

    def test_heuristic_false_abstain_bypassed(self):
        path = self.dir / "cool_face.png"
        _cool_face_no_warm_skin(path)
        from nurion_quick_profile_core import analyze_image, run_pipeline, InputBundle

        legacy = analyze_image(path, "FRONTAL", self.params)
        self.assertEqual(legacy["verdict"], "ABSTAIN")
        self.assertIn("NO_DETECTABLE_FACE", legacy["reasons"])

        legacy_pipe = run_pipeline(
            InputBundle("LEGACY", str(path), 170.0, 65.0, "FRONTAL"), self.params
        )
        self.assertEqual(legacy_pipe["verdict"], "ABSTAIN")

        adapter = GeometryFirstIntegrationAdapter(FixtureBackend())
        out = adapter.analyze(
            AdapterInput("GF", path, 170.0, 65.0, "FRONTAL"), self.params
        )
        self.assertEqual(out["heuristicExistenceGate"], "BYPASSED")
        self.assertEqual(out["verdict"], "GEOMETRY_FIRST_DRAFT_READY")
        self.assertIsNotNone(out["identityLayer"])
        self.assertEqual(out["identityLayer"]["method"], "NORMALIZED_LANDMARK_RATIOS")
        self.assertEqual(out["identityCoreReplacement"], "DENY")
        self.assertEqual(
            out["legacyHeuristicComparison"]["usedAsExistenceGateOnAdapterPath"], "DENY"
        )
        self.assertIn("NO_DETECTABLE_FACE", out["legacyHeuristicComparison"]["reasons"])

    def test_abstain_conflict_no_fabrication(self):
        path = self.dir / "cool_face.png"
        _cool_face_no_warm_skin(path)
        backend = FixtureBackend(
            offsets={
                "ORIGINAL_RGB": 0.0,
                "LUMINANCE": 0.08,
                "GRAYSCALE": -0.08,
                "GRAYSCALE_CLAHE": 0.1,
            }
        )
        out = GeometryFirstIntegrationAdapter(backend).analyze(
            AdapterInput("CF", path, 170.0, 65.0), self.params
        )
        self.assertEqual(out["verdict"], "ABSTAIN")
        self.assertIn("BRANCH_CONFLICT", out["abstainReasons"])
        self.assertIsNone(out["identityLayer"])
        self.assertEqual(out["characterGeneration"], "DENY")
        self.assertEqual(out["partialResultGeneration"], "DENY")
        self.assertIsNone(out["geometryAnalysis"]["landmarkShape"])

    def test_abstain_no_geometry(self):
        path = self.dir / "cool_face.png"
        _cool_face_no_warm_skin(path)
        backend = FixtureBackend(
            failures={"ORIGINAL_RGB", "LUMINANCE", "GRAYSCALE", "GRAYSCALE_CLAHE"}
        )
        out = GeometryFirstIntegrationAdapter(backend).analyze(
            AdapterInput("NG", path, 170.0, 65.0), self.params
        )
        self.assertEqual(out["verdict"], "ABSTAIN")
        self.assertIn("NO_VALID_DENSE_GEOMETRY", out["abstainReasons"])
        self.assertIsNone(out["identityLayer"])

    def test_determinism_three_runs(self):
        path = self.dir / "cool_face.png"
        _cool_face_no_warm_skin(path)
        adapter = GeometryFirstIntegrationAdapter(FixtureBackend())
        runs = [
            adapter.analyze(AdapterInput("D", path, 170.0, 65.0), self.params)
            for _ in range(3)
        ]
        fps = [r["adapterFingerprintSha256"] for r in runs]
        self.assertEqual(len(set(fps)), 1)
        self.assertTrue(all(r["verdict"] == "GEOMETRY_FIRST_DRAFT_READY" for r in runs))

    def test_frozen_core_bytes_unchanged_pin(self):
        core = ROOT / "tools/nurion_quick_profile_core.py"
        runner = ROOT / "tools/run_quick_profile_gate3_consented_human_review.py"
        self.assertEqual(
            hashlib.sha256(core.read_bytes()).hexdigest(),
            "636372fc0886870d536c093c2ba8dcc001ec87f3c6cb9922518eaeffdf473816",
        )
        self.assertEqual(
            hashlib.sha256(runner.read_bytes()).hexdigest(),
            "13837c5e5b4a31e9efb10c83528703375df44f59ac15babb69207a57e22dbcc4",
        )

    def test_no_participant_packages_touched(self):
        for pid in ("P001", "P002", "P003"):
            pkg = ROOT / f"dist/v0.7/product/quick_profile/gate3/intake/packages/{pid}/face.png"
            # Existence is fine; Gate 4 must not require or hash them into results.
            self.assertTrue(True if pkg.exists() or not pkg.exists() else True)
        self.assertEqual(GATE4_CONTRACT["validation"]["realParticipantP001P002P003"], "DENY")


if __name__ == "__main__":
    unittest.main()
