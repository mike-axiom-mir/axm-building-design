import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_utility_panel_receiver_clearance_envelope",
    ROOT / "tools/verify_utility_panel_receiver_clearance_envelope.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class UtilityPanelReceiverClearanceEnvelopeTests(unittest.TestCase):
    def test_exact_successor_preserves_required_nearest_body_face_gap(self):
        receipt = mod.verify()
        self.assertEqual(
            receipt["result"],
            "PASS_SOURCE_OWNED_BUILDING_UTILITY_PANEL_RECEIVER_CLEARANCE_ENVELOPE",
        )
        self.assertEqual(len(receipt["receiver_results"]), 2)
        for row in receipt["receiver_results"]:
            self.assertAlmostEqual(row["physical_body_gap_m"], 0.02, places=12)
            self.assertAlmostEqual(row["required_body_clearance_m"], 0.02, places=12)
            self.assertAlmostEqual(row["clearance_slack_m"], 0.0, places=12)
            self.assertAlmostEqual(row["panel_body_inner_offset_m"], 0.06, places=12)
            self.assertAlmostEqual(row["panel_body_outer_offset_m"], 0.14, places=12)
            self.assertAlmostEqual(row["plate_outer_offset_m"], 0.04, places=12)
            self.assertEqual(len(row["per_side_footprint_margin_m"]), 2)
            self.assertAlmostEqual(row["per_side_footprint_margin_m"][0], 0.05, places=12)
            self.assertAlmostEqual(row["per_side_footprint_margin_m"][1], 0.05, places=12)

    def test_predecessor_center_standoff_was_not_physical_body_clearance(self):
        receipt = mod.verify()
        self.assertEqual(len(receipt["predecessor_failure_witness"]), 2)
        for row in receipt["predecessor_failure_witness"]:
            self.assertAlmostEqual(row["physical_body_gap_m"], 0.0, places=12)
            self.assertAlmostEqual(row["clearance_shortfall_m"], 0.02, places=12)

    def test_center_offset_surplus_is_not_nearest_body_face_gap(self):
        receipt = mod.verify()
        for row in receipt["receiver_results"]:
            self.assertAlmostEqual(row["legacy_center_offset_surplus_m"], 0.06, places=12)
            self.assertAlmostEqual(row["physical_body_gap_m"], 0.02, places=12)
            self.assertNotAlmostEqual(
                row["legacy_center_offset_surplus_m"],
                row["physical_body_gap_m"],
                places=12,
            )

    def test_fail_closed_controls_reject(self):
        controls = mod.negative_controls()
        self.assertEqual(len(controls), 5)
        self.assertTrue(all(value.startswith("REJECTED") for value in controls.values()))


if __name__ == "__main__":
    unittest.main()
