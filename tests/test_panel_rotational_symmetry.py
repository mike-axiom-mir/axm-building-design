import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_panel_rotational_symmetry",
    ROOT / "tools/verify_panel_rotational_symmetry.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class PanelRotationalSymmetryTests(unittest.TestCase):
    def test_exact_current_panel_is_reversible_at_both_receivers(self):
        receipt = mod.verify(exact_head="TEST_HEAD")
        self.assertEqual(
            receipt["result"],
            "PASS_BUILDING_PANEL_180_DEGREE_MECHANICAL_REVERSIBILITY_CURRENT_SOURCE",
        )
        self.assertEqual(receipt["exact_hard_surface_head"], "TEST_HEAD")
        self.assertEqual(receipt["source_mount_pattern_180_residual_m"], 0.0)
        self.assertEqual(receipt["current_box_proof_geometry_180_residual_m"], 0.0)
        self.assertEqual(receipt["named_build_result"]["schema"], "axm.building-build-result/v0.1")
        self.assertEqual(receipt["named_build_result"]["legacy_output_count_observed"], 9)
        self.assertEqual(receipt["named_build_result"]["topology_revision"], "closed-outward-12-triangle-v1")
        self.assertEqual(receipt["named_build_result"]["topology_object_count"], 19)
        self.assertEqual(len(receipt["receiver_results"]), 2)
        for result in receipt["receiver_results"]:
            self.assertEqual(result["zero_degree_mount_pattern_residual_m"], 0.0)
            self.assertEqual(result["one_eighty_degree_unordered_mount_pattern_residual_m"], 0.0)
        self.assertFalse(receipt["physical_orientation_key_present"])
        self.assertTrue(receipt["receiver_frame_metadata_orientation_preserved"])
        self.assertFalse(receipt["geometry_changed"])

    def test_one_millimetre_asymmetric_mount_drift_breaks_reversibility(self):
        panel = mod.load(mod.PANEL)
        panel["mount_points_local_m"][0][0] += 0.001
        with self.assertRaisesRegex(ValueError, "180-degree reversible"):
            mod.verify(panel=panel)

    def test_keyed_claim_is_rejected_without_source_owned_key(self):
        contract = mod.load(mod.CONTRACT)
        contract["observed_mechanical_state"]["physical_orientation_key_present"] = True
        with self.assertRaisesRegex(ValueError, "unsupported physical orientation-key claim"):
            mod.verify(contract=contract)

    def test_declared_source_identity_drift_fails_closed(self):
        contract = mod.load(mod.CONTRACT)
        contract["source_authority"]["panel_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "declared panel source identity drift"):
            mod.verify(contract=contract)

    def test_missing_named_receiver_dependency_fails_closed(self):
        named = mod.load_build_result_tool().build_named()
        named.pop("receiver_fits")
        with self.assertRaisesRegex(ValueError, "missing required Building build-result fields"):
            mod.validate_named_result(named, mod.load(mod.PAVILION), mod.load(mod.PANEL))

    def test_negative_controls_are_retained(self):
        controls = mod.run_negative_controls()
        self.assertEqual(
            set(controls),
            {
                "asymmetric_mount_drift_0p001m",
                "unsupported_keyed_claim",
                "source_identity_drift",
                "missing_named_receiver_dependency",
            },
        )
        self.assertTrue(all(value.startswith("REJECTED") for value in controls.values()))


if __name__ == "__main__":
    unittest.main()
