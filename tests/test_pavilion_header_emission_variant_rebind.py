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
    def test_exact_source_variants_bind_to_existing_procedural_family(self):
        summary = mod.build()
        self.assertEqual(
            summary["result"],
            "PASS_PROCEDURAL_HEADER_FAMILY_REBOUND_TO_EXPLICIT_EMISSION_VARIANTS",
        )
        self.assertEqual(
            summary["decision"],
            "PRESERVE_DEFAULT_BASE__SEGMENTED_OPT_IN_ONLY__NO_AUTO_ADOPTION",
        )
        self.assertEqual(summary["source_hard_surface_head"], "547bd21073332c8f856f07017cf9d279aa157bfa")
        self.assertEqual(summary["emission_variant_contract_schema"], "axm.building-emission-variants/v0.1")
        self.assertEqual(summary["selection_policy"], "EXPLICIT_VARIANT_ID_NO_FALLBACK")
        self.assertEqual(summary["default_variant_id"], "base-closed-outward-19")
        self.assertEqual(summary["default_variant_adoption"], "CURRENT_DEFAULT_UNCHANGED")
        self.assertEqual(summary["segmented_variant_id"], "header-segmented-23")
        self.assertEqual(summary["segmented_variant_adoption"], "OPT_IN_ONLY")

    def test_two_materially_different_header_representations_are_exact(self):
        summary = mod.build()
        self.assertEqual(summary["default_emitted_box_count"], 19)
        self.assertEqual(summary["segmented_emitted_box_count"], 23)
        self.assertEqual(summary["logical_header_output_count"], 2)
        self.assertEqual(summary["segmented_header_output_count"], 6)
        self.assertEqual(summary["distinct_variant_header_output_digests"], 2)
        self.assertEqual(summary["header_expansion_distinct_front_rear_digests"], 2)
        self.assertNotEqual(summary["default_header_output_digest"], summary["segmented_header_output_digest"])
        self.assertEqual({row["logical_component_id"] for row in summary["headers"]}, {"front-header", "rear-header"})
        self.assertTrue(all(row["default_variant_header_count"] == 1 for row in summary["headers"]))
        self.assertTrue(all(row["segmented_variant_header_count"] == 3 for row in summary["headers"]))

    def test_source_semantics_remain_explicit_and_bounded(self):
        summary = mod.build()
        self.assertEqual(summary["default_positive_volume_intersection_count"], 4)
        self.assertEqual(summary["segmented_positive_volume_intersection_count"], 0)
        self.assertEqual(summary["occupied_union_volume_residual_m3"], 0.0)
        self.assertTrue(summary["bounds_equal"])
        self.assertTrue(summary["receiver_ids_equal"])

    def test_fail_closed_controls_hold(self):
        summary = mod.build()
        self.assertEqual(
            set(summary["negative_controls"]),
            {
                "emission_contract_identity_drift",
                "selection_policy_drift",
                "default_variant_drift",
                "segmented_adoption_policy_drift",
                "unknown_variant_fallback",
            },
        )
        self.assertTrue(all(value.startswith("HOLD:") for value in summary["negative_controls"].values()))


if __name__ == "__main__":
    unittest.main()
