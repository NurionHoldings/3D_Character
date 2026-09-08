"""Gate 5 unit tests — dense identity face draft (no real participants)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from nurion_qp_geometry_face_v2.dense_identity_draft import (
    TRIANGLES,
    build_dense_identity_draft,
    write_obj,
    write_region_sidecar,
)
from nurion_qp_geometry_face_v2.gate4_contract import gate4_parameter_hash
from nurion_qp_geometry_face_v2.gate5_contract import GATE5_CONTRACT, gate5_parameter_hash


def fixture_landmarks():
    p = np.zeros((478, 3), dtype=np.float64)
    p[:, 0] = 0.5
    p[:, 1] = 0.5
    # seed with analyzer key points then perturb all indices for surface extent
    p[33] = (0.4, 0.42, 0.02)
    p[263] = (0.6, 0.42, 0.02)
    p[10] = (0.5, 0.2, -0.01)
    p[152] = (0.5, 0.82, 0.0)
    p[1] = (0.5, 0.52, 0.05)
    rng = np.random.default_rng(0)
    jitter = rng.normal(0.0, 0.01, size=p.shape)
    jitter[:, 2] *= 0.5
    # radial face-like placement
    for i in range(478):
        ang = 2 * np.pi * (i / 478.0)
        r = 0.18 + 0.05 * np.sin(3 * ang)
        p[i, 0] = 0.5 + r * np.cos(ang) * (0.7 if i % 2 == 0 else 1.0)
        p[i, 1] = 0.5 + r * np.sin(ang) * 1.1
        p[i, 2] = 0.02 * np.cos(2 * ang)
    p[33] = (0.4, 0.42, 0.02)
    p[263] = (0.6, 0.42, 0.02)
    p += jitter * 0.2
    return p


class GeometryFirstGate5Tests(unittest.TestCase):
    def test_hash_pins_gate4(self):
        self.assertEqual(len(gate5_parameter_hash()), 64)
        self.assertEqual(GATE5_CONTRACT["gate4OfficialParameterHash"], gate4_parameter_hash())
        self.assertEqual(GATE5_CONTRACT["qualityClaims"]["photorealAutomaticPass"], "DENY")
        self.assertEqual(GATE5_CONTRACT["baseline"]["production"], "NO-GO")

    def test_triangles_dense(self):
        self.assertGreaterEqual(len(TRIANGLES), 800)

    def test_natural_draft_regions(self):
        d = build_dense_identity_draft(fixture_landmarks(), "NATURAL")
        self.assertEqual(d.vertex_count, 478)
        self.assertGreaterEqual(d.triangle_count, 800)
        for region in ("EYES", "EYELIDS", "NOSE", "NOSE_ALAE", "LIPS", "MOUTH", "JAWLINE"):
            self.assertIn(region, d.expressed_regions)
        self.assertIn("DENSE_IDENTITY_FACE_DRAFT_NOT_PHOTOREAL_CLAIM", d.disclosures)

    def test_polished_differs_but_not_photoreal_claim(self):
        lm = fixture_landmarks()
        n = build_dense_identity_draft(lm, "NATURAL")
        p = build_dense_identity_draft(lm, "POLISHED")
        self.assertFalse(np.allclose(n.vertices, p.vertices))
        self.assertIn("POLISHED_IS_MILD_SYMMETRY_SMOOTH_PROXY_ONLY", p.disclosures)

    def test_obj_roundtrip_counts(self):
        d = build_dense_identity_draft(fixture_landmarks(), "NATURAL")
        with tempfile.TemporaryDirectory() as td:
            obj = Path(td) / "face.obj"
            side = Path(td) / "regions.json"
            write_obj(d, obj)
            write_region_sidecar(d, side)
            text = obj.read_text(encoding="utf-8")
            self.assertEqual(text.count("\nv "), 478)
            self.assertGreaterEqual(text.count("\nf "), 800)
            self.assertTrue(side.is_file())


if __name__ == "__main__":
    unittest.main()
