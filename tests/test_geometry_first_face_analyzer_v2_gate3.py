import unittest

import numpy as np

from nurion_qp_geometry_face_v2.analyzer import GeometryFirstAnalyzer, make_representations


def fixture_landmarks(offset=0.0):
    p = np.zeros((478, 3), dtype=np.float64)
    p[:, 0] = 0.5
    p[:, 1] = 0.5
    p[33] = (0.4, 0.42, 0); p[263] = (0.6, 0.42, 0)
    p[10] = (0.5, 0.2, 0); p[152] = (0.5, 0.82, 0)
    p[1] = (0.5, 0.52, 0); p[234] = (0.28, 0.5, 0); p[454] = (0.72, 0.5, 0)
    p[61] = (0.42, 0.65, 0); p[291] = (0.58, 0.65, 0)
    p[172] = (0.34, 0.69, 0); p[397] = (0.66, 0.69, 0)
    p[:, 0] += offset
    return p


class FixtureBackend:
    name = "SYNTHETIC_FIXTURE_NO_REAL_PARTICIPANT"
    def __init__(self, failures=(), offsets=None):
        self.failures = set(failures); self.offsets = offsets or {}
    def infer(self, image, branch):
        if branch in self.failures:
            return None
        points = fixture_landmarks()
        # Branch-specific non-rigid warp; unlike translation this survives
        # eye-centred/interocular normalization and exercises conflict policy.
        warp = self.offsets.get(branch, 0.0)
        points[:, 0] += warp * np.sin(np.arange(478) * 0.37)
        return points


class GeometryFirstGate3Tests(unittest.TestCase):
    def setUp(self): self.image = np.full((256, 256, 3), 127, dtype=np.uint8)
    def test_four_representations(self): self.assertEqual(set(make_representations(self.image)), {"ORIGINAL_RGB", "LUMINANCE", "GRAYSCALE", "GRAYSCALE_CLAHE"})
    def test_original_not_mutated(self):
        before = self.image.copy(); make_representations(self.image); self.assertTrue(np.array_equal(before, self.image))
    def test_consensus_passes_without_color_signal(self):
        r = GeometryFirstAnalyzer(FixtureBackend()).analyze(self.image); self.assertEqual(r.outcome, "GEOMETRY_CONFIDENT")
    def test_478_landmarks_preserved(self): self.assertEqual(GeometryFirstAnalyzer(FixtureBackend()).analyze(self.image).landmarks.shape, (478, 3))
    def test_geometry_ratios_are_finite(self): self.assertTrue(all(np.isfinite(list(GeometryFirstAnalyzer(FixtureBackend()).analyze(self.image).geometry.values()))))
    def test_one_branch_requires_review(self):
        r = GeometryFirstAnalyzer(FixtureBackend(failures={"LUMINANCE", "GRAYSCALE", "GRAYSCALE_CLAHE"})).analyze(self.image)
        self.assertEqual(r.outcome, "GEOMETRY_REVIEW_REQUIRED")
    def test_all_branches_fail_abstains(self):
        r = GeometryFirstAnalyzer(FixtureBackend(failures={"ORIGINAL_RGB", "LUMINANCE", "GRAYSCALE", "GRAYSCALE_CLAHE"})).analyze(self.image)
        self.assertEqual(r.outcome, "ABSTAIN_RECAPTURE"); self.assertIsNone(r.landmarks)
    def test_conflict_abstains_without_fabrication(self):
        offsets={"ORIGINAL_RGB": -0.1, "LUMINANCE": 0.1, "GRAYSCALE": -0.08, "GRAYSCALE_CLAHE": 0.08}
        r=GeometryFirstAnalyzer(FixtureBackend(offsets=offsets)).analyze(self.image)
        self.assertEqual(r.outcome,"ABSTAIN_RECAPTURE"); self.assertIsNone(r.landmarks)
    def test_skin_is_post_geometry_placeholder(self):
        r=GeometryFirstAnalyzer(FixtureBackend()).analyze(self.image)
        self.assertEqual(r.skin_policy,"SKIN_TONE_UNCERTAIN_NEUTRAL_PLACEHOLDER")
    def test_no_face_authentication_claim(self): self.assertIn("GEOMETRY_FIRST_NOT_FACE_AUTHENTICATION",GeometryFirstAnalyzer(FixtureBackend()).analyze(self.image).disclosures)
    def test_determinism_three_runs(self):
        runs=[GeometryFirstAnalyzer(FixtureBackend()).analyze(self.image) for _ in range(3)]
        self.assertTrue(np.array_equal(runs[0].landmarks,runs[1].landmarks)); self.assertTrue(np.array_equal(runs[1].landmarks,runs[2].landmarks))
    def test_too_small_input_denied(self):
        with self.assertRaisesRegex(ValueError,"IMAGE_TOO_SMALL"): GeometryFirstAnalyzer(FixtureBackend()).analyze(np.zeros((32,32,3),dtype=np.uint8))


if __name__ == "__main__": unittest.main()
