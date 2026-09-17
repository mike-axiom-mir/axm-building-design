import copy
import importlib.util
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/verify_panel_mount_axis_clearance_capacity.py"
PANEL = ROOT / "assets/utility_access_panel_001.json"
CONTRACT = ROOT / "assets/utility_panel_mount_axis_clearance_capacity_001.json"

spec = importlib.util.spec_from_file_location("panel_mount_axis_clearance_capacity", TOOL)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PanelMountAxisClearanceCapacityTests(unittest.TestCase):
    def setUp(self):
        self.panel = json.loads(PANEL.read_text(encoding="utf-8"))
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_source_capacity_passes(self):
        receipt = mod.verify(exact_head="TEST_HEAD")
        self.assertEqual(
            receipt["result"],
            "PASS_SOURCE_OWNED_BUILDING_PANEL_MOUNT_AXIS_CLEARANCE_CAPACITY",
        )
        self.assertEqual(receipt["exact_hard_surface_head"], "TEST_HEAD")
        self.assertFalse(receipt["reservation_radius_selected"])
        self.assertFalse(receipt["fastener_geometry_established"])
        self.assertFalse(receipt["tooling_envelope_established"])
        self.assertFalse(receipt["retention_method_established"])
        self.assertFalse(receipt["geometry_changed"])

    def test_exact_capacity_is_footprint_limited(self):
        capacity = mod.planar_capacity(self.panel)
        self.assertEqual(capacity["mount_axis_count"], 4)
        self.assertAlmostEqual(
            capacity["minimum_axis_to_footprint_boundary_m"], 0.05, places=12
        )
        self.assertAlmostEqual(capacity["minimum_axis_pair_distance_m"], 1.0, places=12)
        self.assertAlmostEqual(capacity["pairwise_tangency_cap_m"], 0.5, places=12)
        self.assertAlmostEqual(
            capacity["closed_common_reservation_tangency_cap_m"], 0.05, places=12
        )
        self.assertEqual(capacity["limiting_constraint"], "FOOTPRINT_EDGE")

    def test_each_axis_has_same_nearest_edge_margin(self):
        capacity = mod.planar_capacity(self.panel)
        margins = [
            row["minimum_axis_to_footprint_boundary_m"]
            for row in capacity["mount_axes"]
        ]
        self.assertEqual(len(margins), 4)
        for margin in margins:
            self.assertAlmostEqual(margin, 0.05, places=12)

    def test_180_degree_reversal_preserves_capacity(self):
        base = mod.planar_capacity(self.panel)
        rotated = mod.planar_capacity(mod.rotate_points_180(self.panel))
        self.assertAlmostEqual(
            base["closed_common_reservation_tangency_cap_m"],
            rotated["closed_common_reservation_tangency_cap_m"],
            places=12,
        )
        self.assertEqual(base["limiting_constraint"], rotated["limiting_constraint"])

    def test_closed_cap_is_tangency_not_strict_service_clearance(self):
        capacity = mod.planar_capacity(self.panel)
        cap = capacity["closed_common_reservation_tangency_cap_m"]
        tangent = mod.evaluate_common_radius(capacity, cap)
        self.assertTrue(tangent["within_closed_footprint"])
        self.assertFalse(tangent["strictly_inside_footprint"])
        self.assertTrue(tangent["pairwise_nonoverlap"])
        self.assertAlmostEqual(tangent["minimum_footprint_edge_residual_m"], 0.0, places=12)
        self.assertAlmostEqual(tangent["minimum_pair_gap_m"], 0.9, places=12)

    def test_one_mm_below_cap_has_positive_edge_slack(self):
        capacity = mod.planar_capacity(self.panel)
        probe = mod.evaluate_common_radius(
            capacity, capacity["closed_common_reservation_tangency_cap_m"] - 0.001
        )
        self.assertTrue(probe["strictly_inside_footprint"])
        self.assertTrue(probe["pairwise_nonoverlap"])
        self.assertAlmostEqual(probe["minimum_footprint_edge_residual_m"], 0.001, places=12)

    def test_one_mm_above_cap_breaks_footprint_before_pair_spacing(self):
        capacity = mod.planar_capacity(self.panel)
        probe = mod.evaluate_common_radius(
            capacity, capacity["closed_common_reservation_tangency_cap_m"] + 0.001
        )
        self.assertFalse(probe["within_closed_footprint"])
        self.assertTrue(probe["pairwise_nonoverlap"])
        self.assertAlmostEqual(probe["minimum_footprint_edge_residual_m"], -0.001, places=12)

    def test_source_mutation_fails_closed(self):
        mutated = copy.deepcopy(self.panel)
        mutated["mount_points_local_m"][0][0] -= 0.001
        with self.assertRaisesRegex(ValueError, "PANEL_SOURCE_CONTENT_DRIFT"):
            mod.verify(panel=mutated, contract=self.contract)

    def test_contract_cannot_select_a_radius(self):
        mutated = copy.deepcopy(self.contract)
        mutated["reservation_radius_selected"] = True
        with self.assertRaisesRegex(
            ValueError, "CLEARANCE_RADIUS_SELECTION_NOT_SOURCE_OWNED"
        ):
            mod.verify(panel=self.panel, contract=mutated)

    def test_contract_cannot_claim_fastener_geometry(self):
        mutated = copy.deepcopy(self.contract)
        mutated["fastener_geometry_established"] = True
        with self.assertRaisesRegex(ValueError, "FASTENER_GEOMETRY_AUTHORITY_EXPANSION"):
            mod.verify(panel=self.panel, contract=mutated)

    def test_contract_cannot_relabel_edge_tangency_as_strict(self):
        mutated = copy.deepcopy(self.contract)
        mutated["observed_capacity"]["strict_no_encroachment_common_radius_condition"] = (
            "0 <= radius_m <= closed_common_reservation_tangency_cap_m"
        )
        with self.assertRaisesRegex(ValueError, "STRICT_INTERIOR_POLICY_DRIFT"):
            mod.verify(panel=self.panel, contract=mutated)

    def test_negative_controls_all_reject(self):
        receipt = mod.verify(exact_head="TEST_HEAD")
        controls = receipt["negative_controls"]
        self.assertEqual(len(controls), 5)
        self.assertTrue(all(value.startswith("REJECTED:") for value in controls.values()))


if __name__ == "__main__":
    unittest.main()
