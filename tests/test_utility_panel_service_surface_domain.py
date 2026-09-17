import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/verify_utility_panel_service_surface_domain.py"
spec = importlib.util.spec_from_file_location("surface_domain", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PANEL = json.loads((ROOT / "assets/utility_access_panel_001.json").read_text(encoding="utf-8"))
DOMAIN = json.loads((ROOT / "assets/utility_access_panel_001_service_surface_domain.json").read_text(encoding="utf-8"))


class UtilityPanelServiceSurfaceDomainTests(unittest.TestCase):
    def test_exact_source_surface_domain_passes(self):
        receipt = mod.verify(copy.deepcopy(PANEL), copy.deepcopy(DOMAIN))
        self.assertEqual(receipt["result"], mod.RESULT)
        self.assertEqual(receipt["surface_id"], "utility_panel_outer_service_surface")
        self.assertAlmostEqual(receipt["metric_domain"]["primary_extent_m"], 1.10)
        self.assertAlmostEqual(receipt["metric_domain"]["secondary_extent_m"], 1.50)
        self.assertAlmostEqual(receipt["metric_domain"]["area_m2"], 1.65)
        self.assertEqual(receipt["source_face_structure"], {"vertex_count": 4, "triangle_count": 2})
        self.assertFalse(receipt["source_geometry_changed"])
        self.assertFalse(receipt["uv_authored_or_selected"])
        self.assertFalse(receipt["material_authored_or_selected"])
        self.assertFalse(receipt["downstream_adoption_authorized"])

    def test_one_millimeter_face_origin_drift_fails_closed(self):
        bad = copy.deepcopy(DOMAIN)
        bad["reference_frame"]["origin_local_m"][0] += 0.001
        with self.assertRaisesRegex(ValueError, "exact \\+X proof-box face center"):
            mod.verify(copy.deepcopy(PANEL), bad)

    def test_flipped_outward_axis_fails_closed(self):
        bad = copy.deepcopy(DOMAIN)
        bad["reference_frame"]["outward_axis_local"] = [-1.0, 0.0, 0.0]
        with self.assertRaisesRegex(ValueError, "outward axis drift"):
            mod.verify(copy.deepcopy(PANEL), bad)

    def test_metric_extent_drift_fails_closed(self):
        bad = copy.deepcopy(DOMAIN)
        bad["metric_domain"]["primary_extent_m"] = 1.101
        with self.assertRaisesRegex(ValueError, "primary metric extent drift"):
            mod.verify(copy.deepcopy(PANEL), bad)

    def test_corner_order_or_position_drift_fails_closed(self):
        bad = copy.deepcopy(DOMAIN)
        bad["metric_domain"]["corner_positions_local_m"][0][1] += 0.001
        with self.assertRaisesRegex(ValueError, "corner positions drift"):
            mod.verify(copy.deepcopy(PANEL), bad)

    def test_source_box_extent_drift_fails_closed(self):
        bad_panel = copy.deepcopy(PANEL)
        bad_panel["proof_geometry"]["size_local_xyz_m"][1] = 1.101
        with self.assertRaisesRegex(ValueError, "extents disagree"):
            mod.verify(bad_panel, copy.deepcopy(DOMAIN))

    def test_downstream_authority_boundary_cannot_be_silently_removed(self):
        bad = copy.deepcopy(DOMAIN)
        bad["authority"]["downstream_owned_facts"].remove("UV mapping")
        with self.assertRaisesRegex(ValueError, "authority boundary weakened"):
            mod.verify(copy.deepcopy(PANEL), bad)


if __name__ == "__main__":
    unittest.main()
