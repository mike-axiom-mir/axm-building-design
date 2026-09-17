from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "build_building_utility_panel_uv_density_evidence.py"
SPEC = importlib.util.spec_from_file_location("building_utility_panel_uv_density", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def fixtures():
    contract = json.loads((ROOT / "lookdev" / "building_utility_panel_uv_density_001.json").read_text())
    chart = {
        "schema": MOD.CHART_SCHEMA,
        "chart_id": "utility-panel-outer-service-surface-chart-001",
        "asset_id": "utility-access-panel-001",
        "surface_id": "utility_panel_outer_service_surface",
        "source_surface": {
            "head": "97120eb78a72b0a07aff1c65b9b92229d0a42aff",
            "contract_blob_sha": "14037a0fb939104ea319c9ac96fbe9fdaa949a18",
        },
        "vertices": [
            {"source_corner_index": 0, "metric_st_m": [-0.55, -0.75], "chart_uv": [0.0, 0.0]},
            {"source_corner_index": 1, "metric_st_m": [0.55, -0.75], "chart_uv": [1.0, 0.0]},
            {"source_corner_index": 2, "metric_st_m": [0.55, 0.75], "chart_uv": [1.0, 1.0]},
            {"source_corner_index": 3, "metric_st_m": [-0.55, 0.75], "chart_uv": [0.0, 1.0]},
        ],
        "triangles": [[0, 1, 2], [0, 2, 3]],
        "boundary_loop": [0, 1, 2, 3],
    }
    surface = {
        "schema": MOD.SURFACE_SCHEMA,
        "asset_id": "utility-access-panel-001",
        "surface_id": "utility_panel_outer_service_surface",
        "reference_frame": {"origin_local_m": [0.04, 0.0, 0.0]},
        "metric_domain": {
            "primary_extent_m": 1.10,
            "secondary_extent_m": 1.50,
            "area_m2": 1.65,
            "corner_positions_local_m": [
                [0.04, -0.55, -0.75],
                [0.04, 0.55, -0.75],
                [0.04, 0.55, 0.75],
                [0.04, -0.55, 0.75],
            ],
        },
    }
    base_payload = {
        "schema": MOD.BASE_PAYLOAD_SCHEMA,
        "source_identity": {"hard_surface_head": "57f66b1245812f0c3d402232a046b86c0b5c72d8"},
        "components": [
            {
                "id": "panel-front-utility-bay",
                "kind": "box",
                "size_local_xyz_m": [0.08, 1.10, 1.50],
                "center_m": [-2.45, -1.08, 1.65],
                "source_basis": [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
                "candidate_material": "utility_panel_ochre",
            },
            {
                "id": "panel-east-utility-bay",
                "kind": "box",
                "size_local_xyz_m": [0.08, 1.10, 1.50],
                "center_m": [3.88, 0.10, 1.65],
                "source_basis": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "candidate_material": "utility_panel_ochre",
            },
        ],
        "materials": {
            "candidate": {
                "utility_panel_ochre": {
                    "albedo": [0.43529411764705883, 0.35294117647058826, 0.22745098039215686, 1.0],
                    "albedo_hex": "#6F5A3AFF",
                    "metallic": 0.18,
                    "roughness": 0.62,
                }
            }
        },
    }
    return contract, chart, surface, base_payload


class UtilityPanelUvDensityTests(unittest.TestCase):
    def test_derives_exact_isotropic_320_ppm_layout(self):
        payload, receipt = MOD.derive(*fixtures())
        self.assertEqual(receipt["result"], "PASS_BUILDING_UTILITY_PANEL_PHYSICAL_UV_DENSITY_PAYLOAD")
        self.assertEqual(receipt["candidate"]["active_region_px"], [352, 480])
        self.assertEqual(receipt["candidate"]["active_region_origin_px"], [80, 16])
        self.assertEqual(receipt["candidate"]["checker_cells"], [22, 30])
        self.assertEqual(receipt["candidate"]["texel_density_px_per_m"], [320.0, 320.0])
        self.assertEqual(receipt["candidate"]["density_ratio_max_over_min"], 1.0)
        self.assertGreater(receipt["negative_control"]["density_ratio_max_over_min"], 1.3)
        self.assertEqual(payload["review_atlas"]["active_uv_bounds"], [0.15625, 0.03125, 0.84375, 0.96875])

    def test_rejects_density_drift(self):
        contract, chart, surface, base_payload = fixtures()
        contract = copy.deepcopy(contract)
        contract["review_candidate"]["texel_density_px_per_m"] = 321
        with self.assertRaisesRegex(AssertionError, "review density drift"):
            MOD.derive(contract, chart, surface, base_payload)

    def test_rejects_geometry_chart_drift(self):
        contract, chart, surface, base_payload = fixtures()
        chart = copy.deepcopy(chart)
        chart["vertices"][2]["chart_uv"] = [0.95, 1.0]
        with self.assertRaisesRegex(AssertionError, "chart u"):
            MOD.derive(contract, chart, surface, base_payload)

    def test_rejects_panel_material_role_drift(self):
        contract, chart, surface, base_payload = fixtures()
        base_payload = copy.deepcopy(base_payload)
        base_payload["components"][0]["candidate_material"] = "frame_galvanized"
        with self.assertRaisesRegex(AssertionError, "panel material-role drift"):
            MOD.derive(contract, chart, surface, base_payload)


if __name__ == "__main__":
    unittest.main()
