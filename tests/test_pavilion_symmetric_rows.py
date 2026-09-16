import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_pavilion_symmetric_rows", ROOT / "tools/build_pavilion_symmetric_rows.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class PavilionSymmetricRowTests(unittest.TestCase):
    def test_generator_reproduces_five_materially_different_source_rows(self):
        summary = mod.build()
        self.assertEqual(summary["result"], "PASS_SOURCE_EXACT_SYMMETRIC_COMPONENT_ROW_GENERATOR")
        self.assertEqual(summary["row_count"], 5)
        self.assertEqual(summary["generated_component_count"], 15)
        self.assertEqual(summary["source_component_count"], 17)
        self.assertEqual(summary["generated_source_coverage"], "15/17")
        self.assertEqual(summary["distinct_row_digests"], 5)
        self.assertGreaterEqual(summary["distinct_component_sizes"], 4)
        self.assertEqual(summary["distinct_station_counts"], [2, 3, 4])

    def test_exact_source_components_are_reproduced_without_rewrite(self):
        pavilion = mod.load(mod.PAVILION)
        profile = mod.load(mod.PROFILE)
        rows, generated_ids, manual_ids = mod.verify_profile(
            pavilion, profile, mod.sha256(mod.PAVILION)
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(generated_ids), 15)
        self.assertEqual(manual_ids, ["slab", "roof"])
        front = mod.generate_row(profile["rows"][0])
        self.assertEqual(
            [item["center"][0] for item in front], [-3.7, -1.25, 1.25, 3.7]
        )
        infill = mod.generate_row(profile["rows"][2])
        self.assertEqual([item["center"][0] for item in infill], [-2.45, 0.0, 2.45])
        front_rear_headers = mod.generate_row(profile["rows"][3])
        self.assertEqual(
            [item["center"][1] for item in front_rear_headers], [-0.9, 0.9]
        )
        self.assertEqual(
            [item["id"] for item in front_rear_headers], ["front-header", "rear-header"]
        )
        west_east_headers = mod.generate_row(profile["rows"][4])
        self.assertEqual(
            [item["center"][0] for item in west_east_headers], [-3.7, 3.7]
        )
        self.assertEqual(
            [item["id"] for item in west_east_headers], ["west-header", "east-header"]
        )

    def test_source_identity_and_inherited_hard_surface_gate_remain_exact(self):
        summary = mod.build()
        self.assertEqual(
            summary["source_sha256"],
            "852038d2288ead9a0ee271e09f1a7f7207ec8fd74668e0c52e739e9a224f87d7",
        )
        inherited = summary["inherited_hard_surface_gate"]
        self.assertEqual(inherited["result"], "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF")
        self.assertEqual(inherited["receiver_count"], 2)
        self.assertGreaterEqual(inherited["readable_path_gap_m"], 0.35)
        self.assertTrue(
            all(value.startswith("REJECTED") for value in inherited["negative_controls"].values())
        )

    def test_fail_closed_controls_hold(self):
        summary = mod.build()
        self.assertEqual(set(summary["negative_controls"]), {
            "unsupported_axis",
            "duplicate_component_id",
            "source_pattern_drift_0p001m",
            "header_pattern_drift_0p001m",
            "source_identity_drift",
        })
        self.assertTrue(
            all(value.startswith("HOLD:") for value in summary["negative_controls"].values())
        )


if __name__ == "__main__":
    unittest.main()
