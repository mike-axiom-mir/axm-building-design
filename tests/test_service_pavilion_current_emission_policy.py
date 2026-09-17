import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_current_emission_policy",
    ROOT / "tools/service_pavilion_current_emission_policy.py",
)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class ServicePavilionCurrentEmissionPolicyTests(unittest.TestCase):
    def test_current_source_is_segmented_while_legacy_build_contract_stays_compatible(self):
        receipt = policy.build_evidence("TEST_HEAD")
        self.assertEqual(
            receipt["result"],
            "PASS_SEGMENTED_BUILDING_PROMOTED_TO_CURRENT_SOURCE_POLICY_WITH_LEGACY_COMPATIBILITY",
        )
        self.assertEqual(receipt["current_source_variant_id"], "header-segmented-23")
        self.assertEqual(receipt["legacy_compatibility_variant_id"], "base-closed-outward-19")
        self.assertTrue(receipt["historical_build_result_unchanged"])
        self.assertEqual(receipt["current_source"]["emitted_box_count"], 23)
        self.assertEqual(receipt["legacy_compatibility"]["emitted_box_count"], 19)

    def test_current_source_removes_overlap_without_changing_union_bounds_or_receivers(self):
        receipt = policy.build_evidence("TEST_HEAD")
        self.assertEqual(receipt["current_source"]["positive_volume_intersection_count"], 0)
        self.assertEqual(receipt["legacy_compatibility"]["positive_volume_intersection_count"], 4)
        comparison = receipt["comparison"]
        self.assertEqual(comparison["occupied_union_volume_residual_m3"], 0.0)
        self.assertTrue(comparison["bounds_equal"])
        self.assertTrue(comparison["receiver_ids_equal"])
        self.assertTrue(comparison["receiver_residual_equal"])
        self.assertEqual(comparison["emitted_box_delta"], 4)
        self.assertEqual(comparison["vertex_delta"], 32)
        self.assertEqual(comparison["triangle_delta"], 48)
        self.assertEqual(comparison["positive_volume_intersection_delta"], -4)

    def test_current_source_regression_fails_closed(self):
        candidate = copy.deepcopy(policy.load_policy())
        candidate["current_source_variant_id"] = "base-closed-outward-19"
        with self.assertRaises(ValueError):
            policy.validate_policy(candidate)

    def test_implicit_fallback_policy_fails_closed(self):
        candidate = copy.deepcopy(policy.load_policy())
        candidate["selection_policy"] = "BEST_EFFORT_FALLBACK_ALLOWED"
        with self.assertRaises(ValueError):
            policy.validate_policy(candidate)

    def test_current_and_legacy_identity_cannot_collapse(self):
        candidate = copy.deepcopy(policy.load_policy())
        candidate["legacy_compatibility_variant_id"] = "header-segmented-23"
        with self.assertRaises(ValueError):
            policy.validate_policy(candidate)


if __name__ == "__main__":
    unittest.main()
