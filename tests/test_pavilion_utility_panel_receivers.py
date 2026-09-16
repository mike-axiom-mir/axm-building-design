import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/build_pavilion_utility_panel_receivers.py"
spec = importlib.util.spec_from_file_location("build_pavilion_utility_panel_receivers", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class UtilityPanelReceiverPlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = mod.build()

    def test_exact_family_passes(self):
        data = self.summary
        self.assertEqual(data["result"], "PASS_EXACT_UTILITY_PANEL_RECEIVER_PLACEMENT_FAMILY")
        self.assertEqual(data["receiver_count"], 2)
        self.assertEqual(data["receiver_ids"], ["front-utility-bay", "east-utility-bay"])
        self.assertEqual(data["distinct_placement_digests"], 2)
        self.assertEqual(data["distinct_mesh_digests"], 2)
        self.assertEqual(data["distinct_frame_digests"], 2)
        self.assertAlmostEqual(data["receiver_normal_dot"], 0.0, places=12)

    def test_materially_different_exact_outputs(self):
        by_id = {item["receiver_id"]: item for item in self.summary["placements"]}
        front = by_id["front-utility-bay"]
        east = by_id["east-utility-bay"]
        self.assertEqual(front["center_m"], [-2.45, -1.08, 1.65])
        self.assertEqual(east["center_m"], [3.88, 0.1, 1.65])
        self.assertEqual(front["basis_normal_lateral_up"][0], [0.0, -1.0, 0.0])
        self.assertEqual(east["basis_normal_lateral_up"][0], [1.0, 0.0, 0.0])
        self.assertNotEqual(front["mesh_digest"], east["mesh_digest"])
        self.assertNotEqual(front["placement_digest"], east["placement_digest"])

    def test_fit_and_transform_policy_stay_exact(self):
        for placement in self.summary["placements"]:
            self.assertAlmostEqual(placement["mount_pattern_residual_m"], 0.0, places=12)
            self.assertEqual(placement["footprint_margin_m"], [0.09999999999999987, 0.10000000000000009])
            self.assertAlmostEqual(placement["body_clearance_beyond_plate_m"], 0.04, places=12)
            self.assertEqual(placement["scale"], [1.0, 1.0, 1.0])
            self.assertEqual(placement["extra_rotation_deg"], [0.0, 0.0, 0.0])

    def test_failure_bounds_hold(self):
        controls = self.summary["negative_controls"]
        self.assertEqual(len(controls), 7)
        self.assertTrue(all(value.startswith("HOLD:") for value in controls.values()))
        self.assertEqual(
            set(controls),
            {
                "duplicate_receiver_id",
                "unknown_receiver_id",
                "pavilion_source_identity_drift",
                "panel_source_identity_drift",
                "orientation_contract_drift",
                "nonorthogonal_receiver_frame",
                "panel_receiver_tag_mismatch",
            },
        )

    def test_only_slab_and_roof_remain_outside_procedural_families(self):
        self.assertEqual(self.summary["base_builder_procedural_coverage_with_rows"], "17/19")
        self.assertEqual(
            self.summary["successor_composition_procedural_coverage_with_header_expansion"],
            "21/23",
        )
        self.assertEqual(self.summary["manual_boxes_outside_procedural_families"], ["slab", "roof"])


if __name__ == "__main__":
    unittest.main()
