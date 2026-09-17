from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "build_building_utility_panel_uv_density_clearance_successor_evidence.py"
SPEC = importlib.util.spec_from_file_location("building_uv_successor", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

PROCEDURAL_HEAD = "0d019e64a9788c05e259e8dde50498e9392469d1"


def fixtures():
    contract = json.loads((ROOT / "lookdev" / "building_utility_panel_uv_density_clearance_successor_001.json").read_text())
    historical = {
        "schema": MOD.HISTORICAL_PAYLOAD_SCHEMA,
        "asset_id": "utility-access-panel-001",
        "surface_id": "utility_panel_outer_service_surface",
        "owner_evidence": {
            "geometry_chart_head": "79e09f68a05770eb6dabbbbbb3b008fc8e050aa0",
            "geometry_chart_blob": "56f1964b3360e371ac8c39d547cb300cd14fb997",
            "hard_surface_domain_head": "97120eb78a72b0a07aff1c65b9b92229d0a42aff",
        },
        "surface_metric": {
            "primary_extent_m": 1.10,
            "secondary_extent_m": 1.50,
            "area_m2": 1.65,
            "outer_face_local_x_m": 0.04,
        },
        "review_atlas": {
            "texel_density_px_per_m": [320.0, 320.0],
            "active_region_px": [352, 480],
            "checker_period_m": 0.05,
        },
        "base_components": [
            {
                "id": "panel-front-utility-bay",
                "center_m": [-2.45, -1.08, 1.65],
                "candidate_material": "utility_panel_ochre",
            },
            {
                "id": "panel-east-utility-bay",
                "center_m": [3.88, 0.10, 1.65],
                "candidate_material": "utility_panel_ochre",
            },
        ],
        "truth_boundary": {},
    }
    outputs = [
        {
            "receiver_id": "east-utility-bay",
            "predecessor_panel_center_m": [3.88, 0.10, 1.65],
            "successor_panel_center_m": [3.90, 0.10, 1.65],
            "panel_center_displacement_m": [0.02, 0.0, 0.0],
            "panel_center_displacement_magnitude_m": 0.02,
            "service_surface_origin_displacement_m": [0.02, 0.0, 0.0],
            "successor_physical_body_gap_m": 0.02,
            "clearance_slack_m": 0.0,
            "source_service_surface_primary_extent_m": 1.10,
            "source_service_surface_secondary_extent_m": 1.50,
            "source_service_surface_area_m2": 1.65,
            "output_digest": "east-digest",
        },
        {
            "receiver_id": "front-utility-bay",
            "predecessor_panel_center_m": [-2.45, -1.08, 1.65],
            "successor_panel_center_m": [-2.45, -1.10, 1.65],
            "panel_center_displacement_m": [0.0, -0.02, 0.0],
            "panel_center_displacement_magnitude_m": 0.02,
            "service_surface_origin_displacement_m": [0.0, -0.02, 0.0],
            "successor_physical_body_gap_m": 0.02,
            "clearance_slack_m": 0.0,
            "source_service_surface_primary_extent_m": 1.10,
            "source_service_surface_secondary_extent_m": 1.50,
            "source_service_surface_area_m2": 1.65,
            "output_digest": "front-digest",
        },
    ]
    procedural = {
        "schema": MOD.PROCEDURAL_SCHEMA,
        "result": "PASS_BOUNDED_BUILDING_UTILITY_PANEL_CLEARANCE_REBIND_FAMILY",
        "decision": "PASS_DERIVED_CLEARANCE_SUCCESSOR_REBIND_ONLY__NO_SOURCE_REWRITE_OR_RECEIVER_ADOPTION",
        "source_authority_head": "6585c62d9e21cd56244d35817ec40f1f92889c6f",
        "source_authority_panel_blob": "51b7fa61dd87934a89e033a2fdf5cc3b99992454",
        "automatic_receiver_adoption": False,
        "canonical_family_digest": "family-digest",
        "outputs": outputs,
    }
    successor_domain = {
        "schema": MOD.SURFACE_SCHEMA,
        "asset_id": "utility-access-panel-001",
        "surface_id": "utility_panel_outer_service_surface",
        "source_panel": {"git_blob_sha": "51b7fa61dd87934a89e033a2fdf5cc3b99992454"},
        "reference_frame": {"origin_local_m": [0.04, 0.0, 0.0]},
        "metric_domain": {
            "primary_extent_m": 1.10,
            "secondary_extent_m": 1.50,
            "area_m2": 1.65,
        },
    }
    return contract, historical, procedural, successor_domain


class UtilityPanelUvDensityClearanceSuccessorTests(unittest.TestCase):
    def test_consumes_owner_rebind_without_rebinding_geometry_chart(self):
        payload, receipt = MOD.derive(*fixtures(), PROCEDURAL_HEAD)
        self.assertEqual(receipt["result"], MOD.RESULT)
        self.assertFalse(receipt["historical_geometry_chart_rebound"])
        by_id = {row["id"]: row for row in payload["base_components"]}
        self.assertEqual(by_id["panel-front-utility-bay"]["center_m"], [-2.45, -1.10, 1.65])
        self.assertEqual(by_id["panel-east-utility-bay"]["center_m"], [3.90, 0.10, 1.65])
        self.assertEqual(payload["review_atlas"]["texel_density_px_per_m"], [320.0, 320.0])
        self.assertEqual(len(receipt["receiver_rebinds"]), 2)
        self.assertFalse(payload["truth_boundary"]["production_uv_adopted"])

    def test_rejects_procedural_center_drift(self):
        contract, historical, procedural, successor_domain = fixtures()
        procedural = copy.deepcopy(procedural)
        procedural["outputs"][0]["successor_panel_center_m"][0] += 0.001
        procedural["outputs"][0]["panel_center_displacement_m"][0] += 0.001
        procedural["outputs"][0]["panel_center_displacement_magnitude_m"] = 0.021
        with self.assertRaisesRegex(AssertionError, "translation magnitude"):
            MOD.derive(contract, historical, procedural, successor_domain, PROCEDURAL_HEAD)

    def test_rejects_silent_receiver_adoption(self):
        contract, historical, procedural, successor_domain = fixtures()
        procedural = copy.deepcopy(procedural)
        procedural["automatic_receiver_adoption"] = True
        with self.assertRaisesRegex(AssertionError, "automatic receiver adoption"):
            MOD.derive(contract, historical, procedural, successor_domain, PROCEDURAL_HEAD)

    def test_rejects_metric_domain_drift(self):
        contract, historical, procedural, successor_domain = fixtures()
        successor_domain = copy.deepcopy(successor_domain)
        successor_domain["metric_domain"]["primary_extent_m"] = 1.11
        with self.assertRaisesRegex(AssertionError, "successor primary extent"):
            MOD.derive(contract, historical, procedural, successor_domain, PROCEDURAL_HEAD)


if __name__ == "__main__":
    unittest.main()
