import copy
import importlib.util
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/build_pavilion_utility_panel_clearance_rebind_family.py"

spec = importlib.util.spec_from_file_location("clearance_rebind", TOOL)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class UtilityPanelClearanceRebindFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        donor = os.environ.get("AXM_CLEARANCE_DONOR_ROOT")
        if not donor:
            donor = ROOT / "external/hard-surface-clearance"
        cls.donor = Path(donor).resolve()
        if not cls.donor.exists():
            raise unittest.SkipTest("exact Hard Surface clearance donor checkout not present")
        cls.summary = mod.build(cls.donor)

    def test_result_and_authority_boundary(self):
        self.assertEqual(
            self.summary["result"],
            "PASS_BOUNDED_BUILDING_UTILITY_PANEL_CLEARANCE_REBIND_FAMILY",
        )
        self.assertEqual(
            self.summary["decision"],
            "PASS_DERIVED_CLEARANCE_SUCCESSOR_REBIND_ONLY__NO_SOURCE_REWRITE_OR_RECEIVER_ADOPTION",
        )
        self.assertFalse(self.summary["source_geometry_rewritten"])
        self.assertFalse(self.summary["automatic_receiver_adoption"])

    def test_two_materially_different_outputs(self):
        outputs = self.summary["outputs"]
        self.assertEqual(len(outputs), 2)
        self.assertEqual(self.summary["distinct_output_count"], 2)
        self.assertEqual({row["receiver_id"] for row in outputs}, {"front-utility-bay", "east-utility-bay"})
        self.assertAlmostEqual(self.summary["receiver_normal_dot"], 0.0, places=12)
        self.assertNotEqual(outputs[0]["output_digest"], outputs[1]["output_digest"])

    def test_exact_clearance_successor_delta(self):
        self.assertAlmostEqual(self.summary["predecessor_standoff_m"], 0.08, places=12)
        self.assertAlmostEqual(self.summary["successor_standoff_m"], 0.10, places=12)
        self.assertAlmostEqual(self.summary["standoff_delta_m"], 0.02, places=12)
        for row in self.summary["outputs"]:
            self.assertAlmostEqual(row["panel_center_displacement_magnitude_m"], 0.02, places=12)
            self.assertAlmostEqual(row["successor_physical_body_gap_m"], 0.02, places=12)
            self.assertAlmostEqual(row["required_body_gap_m"], 0.02, places=12)
            self.assertAlmostEqual(row["clearance_slack_m"], 0.0, places=12)
            self.assertEqual(
                row["panel_center_displacement_m"],
                row["service_surface_origin_displacement_m"],
            )

    def test_world_centers_are_exact(self):
        rows = {row["receiver_id"]: row for row in self.summary["outputs"]}
        self.assertEqual(rows["front-utility-bay"]["predecessor_panel_center_m"], [-2.45, -1.08, 1.65])
        self.assertEqual(rows["front-utility-bay"]["successor_panel_center_m"], [-2.45, -1.1, 1.65])
        self.assertEqual(rows["east-utility-bay"]["predecessor_panel_center_m"], [3.88, 0.1, 1.65])
        self.assertEqual(rows["east-utility-bay"]["successor_panel_center_m"], [3.9, 0.1, 1.65])

    def test_local_service_surface_contract_is_preserved(self):
        self.assertFalse(self.summary["source_service_surface_local_frame_changed"])
        self.assertFalse(self.summary["source_service_surface_metric_domain_changed"])
        for row in self.summary["outputs"]:
            self.assertEqual(row["source_service_surface_id"], "utility_panel_outer_service_surface")
            self.assertAlmostEqual(row["source_service_surface_primary_extent_m"], 1.10, places=12)
            self.assertAlmostEqual(row["source_service_surface_secondary_extent_m"], 1.50, places=12)
            self.assertAlmostEqual(row["source_service_surface_area_m2"], 1.65, places=12)

    def test_canonical_digest_is_order_independent(self):
        self.assertEqual(
            self.summary["canonical_family_digest"],
            self.summary["reverse_order_family_digest"],
        )

    def test_all_negative_controls_fail_closed(self):
        controls = self.summary["negative_controls"]
        self.assertEqual(len(controls), 7)
        for name, state in controls.items():
            self.assertTrue(state.startswith("HOLD:"), f"{name}: {state}")


if __name__ == "__main__":
    unittest.main()
