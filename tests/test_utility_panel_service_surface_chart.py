import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/verify_utility_panel_service_surface_chart.py"
spec = importlib.util.spec_from_file_location("geometry_chart", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PROFILE = json.loads((ROOT / "geometry/utility_access_panel_service_surface_chart_001.json").read_text(encoding="utf-8"))
DOMAIN = json.loads((ROOT / "assets/utility_access_panel_001_service_surface_domain.json").read_text(encoding="utf-8"))


class UtilityPanelServiceSurfaceChartTests(unittest.TestCase):
    def test_exact_chart_successor_rebind_passes(self):
        receipt = mod.build(exact_head="test-head", profile=copy.deepcopy(PROFILE), domain=copy.deepcopy(DOMAIN))
        self.assertEqual(receipt["result"], mod.RESULT)
        self.assertEqual(receipt["decision"], mod.DECISION)
        self.assertEqual(receipt["pattern"], mod.PATTERN)
        self.assertEqual(receipt["source_surface_pr"], 17)
        self.assertEqual(receipt["source_surface_head"], mod.SOURCE_HEAD)
        self.assertEqual(receipt["historical_geometry_pr"], 16)
        self.assertEqual(receipt["historical_geometry_head"], mod.HISTORICAL_GEOMETRY_HEAD)
        self.assertFalse(receipt["historical_pass_transferred"])
        self.assertEqual(receipt["vertex_count"], 4)
        self.assertEqual(receipt["triangle_count"], 2)
        self.assertEqual(receipt["boundary_edge_count"], 4)
        self.assertEqual(receipt["internal_edge_count"], 1)
        self.assertEqual(receipt["unreferenced_chart_vertex_count"], 0)
        self.assertAlmostEqual(receipt["metric_area_m2"], 1.65)
        self.assertAlmostEqual(receipt["normalized_chart_area"], 1.0)
        self.assertLessEqual(receipt["max_source_reconstruction_residual_m"], mod.EPS)
        self.assertLessEqual(receipt["max_metric_projection_residual_m"], mod.EPS)
        self.assertLessEqual(receipt["max_normalized_mapping_residual"], mod.EPS)
        self.assertFalse(receipt["source_geometry_changed"])
        self.assertFalse(receipt["production_uv_adopted"])
        self.assertFalse(receipt["downstream_adoption_authorized"])
        self.assertTrue(all(value.startswith("REJECTED:") for value in receipt["negative_controls"].values()))

    def test_chart_uv_swap_fails_closed(self):
        bad = copy.deepcopy(PROFILE)
        bad["vertices"][1]["chart_uv"], bad["vertices"][2]["chart_uv"] = bad["vertices"][2]["chart_uv"], bad["vertices"][1]["chart_uv"]
        with self.assertRaisesRegex(ValueError, "normalized mapping drift"):
            mod.verify_core(bad, copy.deepcopy(DOMAIN))

    def test_metric_projection_drift_fails_closed(self):
        bad = copy.deepcopy(PROFILE)
        bad["vertices"][0]["metric_st_m"][0] += 0.001
        with self.assertRaisesRegex(ValueError, "metric coordinate drift"):
            mod.verify_core(bad, copy.deepcopy(DOMAIN))

    def test_duplicate_source_corner_identity_fails_closed(self):
        bad = copy.deepcopy(PROFILE)
        bad["vertices"][3]["source_corner_index"] = 2
        with self.assertRaisesRegex(ValueError, "not exact and bijective"):
            mod.verify_core(bad, copy.deepcopy(DOMAIN))

    def test_triangle_winding_flip_fails_closed(self):
        bad = copy.deepcopy(PROFILE)
        bad["triangles"][0] = list(reversed(bad["triangles"][0]))
        with self.assertRaisesRegex(ValueError, "winding or area is not positive"):
            mod.verify_core(bad, copy.deepcopy(DOMAIN))

    def test_internal_diagonal_identity_drift_fails_closed(self):
        bad = copy.deepcopy(PROFILE)
        bad["internal_diagonal"] = [1, 3]
        with self.assertRaisesRegex(ValueError, "internal diagonal does not match"):
            mod.verify_core(bad, copy.deepcopy(DOMAIN))

    def test_current_donor_head_drift_fails_closed(self):
        bad = copy.deepcopy(PROFILE)
        bad["source_surface"]["head"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "donor head drift"):
            mod.verify_core(bad, copy.deepcopy(DOMAIN))

    def test_historical_lineage_drift_fails_closed(self):
        bad = copy.deepcopy(PROFILE)
        bad["historical_geometry_evidence"]["head"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "historical Geometry head drift"):
            mod.verify_core(bad, copy.deepcopy(DOMAIN))

    def test_downstream_authority_boundary_fails_closed(self):
        bad = copy.deepcopy(PROFILE)
        bad["authority"]["holds"].remove("atlas placement")
        with self.assertRaisesRegex(ValueError, "authority boundary weakened"):
            mod.verify_core(bad, copy.deepcopy(DOMAIN))


if __name__ == "__main__":
    unittest.main()
