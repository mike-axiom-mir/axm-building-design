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
    def test_panel_is_reversible_across_current_and_legacy_source_roles(self):
        receipt = mod.verify(exact_head="TEST_HEAD")
        self.assertEqual(
            receipt["result"],
            "PASS_BUILDING_PANEL_180_DEGREE_REVERSIBILITY_ACROSS_CURRENT_AND_LEGACY_SOURCE_ROLES",
        )
        self.assertEqual(receipt["exact_hard_surface_head"], "TEST_HEAD")
        self.assertEqual(receipt["source_mount_pattern_180_residual_m"], 0.0)
        self.assertEqual(receipt["box_proof_geometry_180_residual_m"], 0.0)
        self.assertEqual(
            receipt["source_role_policy"]["current_source_variant_id"],
            "header-segmented-23",
        )
        self.assertEqual(
            receipt["source_role_policy"]["legacy_compatibility_variant_id"],
            "base-closed-outward-19",
        )
        self.assertEqual(
            receipt["source_role_policy"]["selection_policy"],
            mod.EXPECTED_CURRENT_SELECTION_POLICY,
        )
        self.assertEqual(
            receipt["source_role_policy"]["policy_sha256"],
            mod.EXPECTED_CURRENT_POLICY_SHA256,
        )
        self.assertEqual(
            receipt["named_build_result"]["role"],
            "LEGACY_COMPATIBILITY_INTERFACE",
        )
        self.assertEqual(
            receipt["named_build_result"]["schema"],
            "axm.building-build-result/v0.1",
        )
        self.assertEqual(receipt["named_build_result"]["legacy_output_count_observed"], 9)
        self.assertEqual(receipt["named_build_result"]["topology_object_count"], 19)
        self.assertEqual(len(receipt["receiver_results"]), 2)

        roles = receipt["representation_role_results"]
        self.assertEqual(
            [(row["role"], row["variant_id"]) for row in roles],
            [
                ("CURRENT_SOURCE", "header-segmented-23"),
                ("LEGACY_COMPATIBILITY", "base-closed-outward-19"),
            ],
        )
        self.assertEqual(
            [
                (
                    row["emitted_box_count"],
                    row["vertex_count"],
                    row["triangle_count"],
                    row["positive_volume_intersection_count"],
                )
                for row in roles
            ],
            [(23, 184, 276, 0), (19, 152, 228, 4)],
        )
        self.assertEqual(
            [row["historical_emission_contract_status"] for row in roles],
            ["OPT_IN_ONLY", "CURRENT_DEFAULT_UNCHANGED"],
        )
        for representation in roles:
            self.assertEqual(representation["receiver_mount_residual_max_m"], 0.0)
            self.assertEqual(len(representation["receiver_reversibility"]), 2)
            for row in representation["receiver_reversibility"]:
                self.assertEqual(row["zero_degree_mount_pattern_residual_m"], 0.0)
                self.assertEqual(
                    row["one_eighty_degree_unordered_mount_pattern_residual_m"],
                    0.0,
                )

        comparison = receipt["current_legacy_comparison"]
        self.assertEqual(comparison["occupied_union_volume_residual_m3"], 0.0)
        self.assertTrue(comparison["receiver_ids_equal"])
        self.assertTrue(comparison["receiver_fit_residual_equal"])
        self.assertEqual(comparison["current_source_positive_volume_intersections"], 0)
        self.assertEqual(comparison["legacy_positive_volume_intersections"], 4)
        self.assertFalse(receipt["physical_orientation_key_present"])
        self.assertTrue(receipt["receiver_frame_metadata_orientation_preserved"])
        self.assertFalse(receipt["geometry_changed"])
        self.assertFalse(receipt["source_role_adoption_changed"])

    def test_one_millimetre_asymmetric_panel_edit_fails_closed(self):
        panel = mod.load(mod.PANEL)
        panel["mount_points_local_m"][0][0] += 0.001
        with self.assertRaisesRegex(ValueError, "named build-result panel source drift"):
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
            mod.verify(named_result=named)

    def test_current_policy_schema_drift_fails_closed(self):
        contract = mod.load(mod.CONTRACT)
        contract["source_authority"]["current_emission_policy_schema"] = (
            "axm.building-current-emission-policy/DRIFT"
        )
        with self.assertRaisesRegex(ValueError, "declared current-emission policy schema drift"):
            mod.verify(contract=contract)

    def test_current_source_role_regression_fails_closed(self):
        policy = mod.load(mod.CURRENT_POLICY)
        policy["current_source_variant_id"] = "base-closed-outward-19"
        with self.assertRaisesRegex(ValueError, "current Building source variant regressed"):
            mod.verify(current_policy=policy)

    def test_consumer_cannot_relabel_current_and_legacy_roles(self):
        contract = mod.load(mod.CONTRACT)
        contract["observed_mechanical_state"]["tested_representation_roles"] = [
            {"role": "CURRENT_SOURCE", "variant_id": "base-closed-outward-19"},
            {"role": "LEGACY_COMPATIBILITY", "variant_id": "header-segmented-23"},
        ]
        with self.assertRaisesRegex(ValueError, "tested current/legacy representation roles drift"):
            mod.verify(contract=contract)

    def test_negative_controls_are_retained(self):
        controls = mod.run_negative_controls()
        self.assertEqual(
            set(controls),
            {
                "asymmetric_mount_drift_0p001m",
                "unsupported_keyed_claim",
                "source_identity_drift",
                "missing_named_receiver_dependency",
                "current_policy_schema_drift",
                "current_source_role_regression",
                "consumer_role_relabel",
            },
        )
        self.assertTrue(all(value.startswith("REJECTED:") for value in controls.values()))


if __name__ == "__main__":
    unittest.main()
