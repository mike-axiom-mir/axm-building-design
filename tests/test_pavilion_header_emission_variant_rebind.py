import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_pavilion_header_emission_variant_rebind",
    ROOT / "tools/verify_pavilion_header_emission_variant_rebind.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class PavilionHeaderEmissionVariantRebindTests(unittest.TestCase):
    def test_current_source_policy_binds_existing_procedural_family(self):
        summary = mod.build()
        self.assertEqual(
            summary["result"],
            "PASS_PROCEDURAL_HEADER_FAMILY_REBOUND_TO_CURRENT_SOURCE_POLICY",
        )
        self.assertEqual(
            summary["decision"],
            "PASS_EXPLICIT_CURRENT_SOURCE_REBIND__SEGMENTED_23_CURRENT__LEGACY_19_COMPATIBILITY_HELD",
        )
        self.assertEqual(summary["family_schema"], "axm.building-header-segment-expansion-family/v0.3")
        self.assertEqual(summary["source_hard_surface_head"], "a976af429b0ea90e0f0cc72d4a8bd4eb8fef22d3")
        self.assertEqual(summary["current_source_policy_schema"], "axm.building-current-emission-policy/v0.1")
        self.assertEqual(summary["current_source_policy_sha256"], "c26f25c789404919bdb8e40f35d517c444e35f0a7aaf9358ad399296a7afe47a")
        self.assertEqual(
            summary["current_source_selection_policy"],
            "CURRENT_SOURCE_IS_NAMED__CONSUMER_REBIND_REQUIRED__NO_SILENT_DEFAULT_REWRITE",
        )
        self.assertEqual(
            summary["historical_build_result_policy"],
            "KEEP_AXM_BUILDING_BUILD_RESULT_V0_1_AT_19_BOXES_FOR_COMPATIBILITY",
        )
        self.assertEqual(summary["historical_emission_default_variant_id"], "base-closed-outward-19")
        self.assertEqual(summary["current_source_variant_id"], "header-segmented-23")
        self.assertEqual(summary["legacy_compatibility_variant_id"], "base-closed-outward-19")

    def test_current_and_legacy_materially_different_outputs_are_exact(self):
        summary = mod.build()
        self.assertEqual(summary["current_source_emitted_box_count"], 23)
        self.assertEqual(summary["legacy_compatibility_emitted_box_count"], 19)
        self.assertEqual(summary["current_source_header_output_count"], 6)
        self.assertEqual(summary["legacy_compatibility_header_output_count"], 2)
        self.assertEqual(summary["distinct_current_legacy_header_output_digests"], 2)
        self.assertEqual(summary["header_expansion_distinct_front_rear_digests"], 2)
        self.assertNotEqual(
            summary["current_source_header_output_digest"],
            summary["legacy_compatibility_header_output_digest"],
        )
        self.assertEqual(
            {row["logical_component_id"] for row in summary["headers"]},
            {"front-header", "rear-header"},
        )
        self.assertTrue(all(row["current_source_header_count"] == 3 for row in summary["headers"]))
        self.assertTrue(all(row["legacy_compatibility_header_count"] == 1 for row in summary["headers"]))

    def test_source_semantics_remain_explicit_and_bounded(self):
        summary = mod.build()
        self.assertEqual(summary["current_source_positive_volume_intersection_count"], 0)
        self.assertEqual(summary["legacy_compatibility_positive_volume_intersection_count"], 4)
        self.assertEqual(summary["occupied_union_volume_residual_m3"], 0.0)
        self.assertTrue(summary["bounds_equal"])
        self.assertTrue(summary["receiver_ids_equal"])
        self.assertEqual(
            summary["current_source_policy_result"],
            "PASS_SEGMENTED_BUILDING_PROMOTED_TO_CURRENT_SOURCE_POLICY_WITH_LEGACY_COMPATIBILITY",
        )

    def test_fail_closed_controls_hold(self):
        summary = mod.build()
        self.assertEqual(
            set(summary["negative_controls"]),
            {
                "emission_contract_identity_drift",
                "emission_selection_policy_drift",
                "legacy_emission_default_drift",
                "current_policy_identity_drift",
                "current_source_regression",
                "current_source_selection_policy_drift",
                "current_legacy_identity_collapse",
                "historical_build_result_policy_drift",
                "unknown_variant_fallback",
            },
        )
        self.assertTrue(all(value.startswith("HOLD:") for value in summary["negative_controls"].values()))


if __name__ == "__main__":
    unittest.main()
