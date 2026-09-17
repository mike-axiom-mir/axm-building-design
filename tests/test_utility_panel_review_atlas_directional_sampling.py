import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/verify_utility_panel_review_atlas_directional_sampling.py"
spec = importlib.util.spec_from_file_location("review_sampling", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CONTRACT = json.loads(
    (ROOT / "geometry/utility_access_panel_review_atlas_directional_sampling_001.json").read_text(encoding="utf-8")
)
CHART = json.loads(
    (ROOT / "geometry/utility_access_panel_service_surface_chart_001.json").read_text(encoding="utf-8")
)

MATERIALS_BASE = {
    "schema": "axm.building-utility-panel-uv-density-review/v0.1",
    "asset_id": "utility-access-panel-001",
    "surface_id": "utility_panel_outer_service_surface",
    "review_candidate": {
        "atlas_size_px": [512, 512],
        "texel_density_px_per_m": 320,
        "active_region_px": [352, 480],
        "active_region_origin_px": [80, 16],
        "diagnostic_checker_period_px": 16,
        "diagnostic_checker_period_m": 0.05,
    },
    "negative_control": {
        "expected_effective_density_px_per_m": [465.45454545454544, 341.3333333333333],
        "expected_density_ratio_max_over_min": 1.3636363636363638,
    },
}

MATERIALS_SUCCESSOR = {
    "schema": "axm.building-utility-panel-uv-density-clearance-successor-review/v0.1",
    "asset_id": "utility-access-panel-001",
    "surface_id": "utility_panel_outer_service_surface",
    "continuity_requirements": {
        "primary_extent_m": 1.1,
        "secondary_extent_m": 1.5,
        "review_texel_density_px_per_m": 320,
        "review_active_region_px": [352, 480],
    },
}

OBSERVER_TEXT = """
var image := Image.create(width, height, false, Image.FORMAT_RGBA8)
return ImageTexture.create_from_image(image)
uv_bounds = payload["review_atlas"]["active_uv_bounds"] as Array
"""

UC_TEXT = """
def inspect_material_uv_density(path):
    \"\"\"Measure actual static GLB triangle UV scale against embedded texture sizes.\"\"\"
"""


class UtilityPanelReviewAtlasDirectionalSamplingTests(unittest.TestCase):
    def derive(self, *, contract=None, chart=None, materials_base=None, materials_successor=None, observer_text=None, uc_text=None):
        return mod.derive(
            copy.deepcopy(CONTRACT if contract is None else contract),
            copy.deepcopy(CHART if chart is None else chart),
            copy.deepcopy(MATERIALS_BASE if materials_base is None else materials_base),
            copy.deepcopy(MATERIALS_SUCCESSOR if materials_successor is None else materials_successor),
            OBSERVER_TEXT if observer_text is None else observer_text,
            UC_TEXT if uc_text is None else uc_text,
        )

    def test_exact_owner_bound_review_sampling_passes(self):
        receipt = self.derive()
        self.assertEqual(receipt["atlas_size_px"], [512, 512])
        self.assertEqual(receipt["active_region_px"], [352, 480])
        self.assertEqual(receipt["active_uv_span"], [0.6875, 0.9375])
        self.assertEqual(receipt["physical_extent_m_by_chart_axis"], [1.1, 1.5])
        self.assertEqual(receipt["directional_texels_per_m_by_chart_axis"], [320.0, 320.0])
        self.assertEqual(receipt["anisotropy_ratio"], 1.0)
        self.assertAlmostEqual(receipt["negative_full_square_texels_per_m_by_chart_axis"][0], 512.0 / 1.1)
        self.assertAlmostEqual(receipt["negative_full_square_texels_per_m_by_chart_axis"][1], 512.0 / 1.5)
        self.assertAlmostEqual(receipt["negative_full_square_anisotropy_ratio"], 15.0 / 11.0)
        self.assertFalse(receipt["uc_glb_observer_consumed"])
        self.assertFalse(receipt["embedded_glb_directional_density_measured"])

    def test_materials_head_drift_fails_closed(self):
        bad = copy.deepcopy(CONTRACT)
        bad["materials_review"]["head"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "Materials pinned head drift"):
            self.derive(contract=bad)

    def test_review_atlas_size_drift_fails_closed(self):
        bad = copy.deepcopy(MATERIALS_BASE)
        bad["review_candidate"]["atlas_size_px"][0] = 513
        with self.assertRaisesRegex(ValueError, "atlas size drift"):
            self.derive(materials_base=bad)

    def test_review_active_region_drift_fails_closed(self):
        bad = copy.deepcopy(MATERIALS_BASE)
        bad["review_candidate"]["active_region_px"][0] = 353
        with self.assertRaisesRegex(ValueError, "active region drift"):
            self.derive(materials_base=bad)

    def test_geometry_metric_extent_drift_fails_closed(self):
        bad = copy.deepcopy(CHART)
        bad["directional_sampling_interface"]["physical_extent_m_by_chart_axis"][0] = 1.11
        with self.assertRaisesRegex(ValueError, "Geometry physical extents"):
            self.derive(chart=bad)

    def test_successor_density_drift_fails_closed(self):
        bad = copy.deepcopy(MATERIALS_SUCCESSOR)
        bad["continuity_requirements"]["review_texel_density_px_per_m"] = 319
        with self.assertRaisesRegex(ValueError, "successor review density"):
            self.derive(materials_successor=bad)

    def test_fabricated_material_bearing_glb_fails_closed(self):
        bad = copy.deepcopy(CONTRACT)
        bad["evidence_transfer_boundary"]["material_bearing_glb_bound"] = True
        with self.assertRaisesRegex(ValueError, "evidence transfer boundary weakened"):
            self.derive(contract=bad)

    def test_fabricated_uc_observer_consumption_fails_closed(self):
        bad = copy.deepcopy(CONTRACT)
        bad["evidence_transfer_boundary"]["uc_glb_observer_consumed"] = True
        with self.assertRaisesRegex(ValueError, "evidence transfer boundary weakened"):
            self.derive(contract=bad)

    def test_geometry_density_policy_escalation_fails_closed(self):
        bad = copy.deepcopy(CONTRACT)
        bad["evidence_transfer_boundary"]["geometry_selects_texel_density_target"] = True
        with self.assertRaisesRegex(ValueError, "evidence transfer boundary weakened"):
            self.derive(contract=bad)

    def test_runtime_image_implementation_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "observer implementation drift"):
            self.derive(observer_text=OBSERVER_TEXT.replace("ImageTexture.create_from_image(image)", "ImageTexture.new()"))

    def test_uc_semantic_boundary_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "semantic boundary drift"):
            self.derive(uc_text="def inspect_material_uv_density(path): pass")


if __name__ == "__main__":
    unittest.main()
