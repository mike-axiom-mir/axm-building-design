import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "service_pavilion_boundary_shell_policy.py"
spec = importlib.util.spec_from_file_location("boundary_shell_policy", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ServicePavilionBoundaryShellPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = module.load_policy()
        cls.candidate = module.build_candidate_receipt("UNIT_TEST")

    def test_exact_candidate_passes_source_owner_policy(self):
        receipt = module.verify_policy(copy.deepcopy(self.policy), copy.deepcopy(self.candidate))
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_BOUNDARY_SHELL_RECEIVING_POLICY")
        self.assertEqual(receipt["semantic_source"]["variant_id"], "header-segmented-23")
        self.assertEqual(receipt["semantic_source"]["authority"], "SEMANTIC_SOURCE_OF_TRUTH")
        self.assertEqual(
            receipt["derived_representation"]["status"],
            "SOURCE_OWNED_DERIVED_REPRESENTATION_NOT_SEMANTIC_SOURCE",
        )
        self.assertEqual(receipt["candidate_metrics"]["semantic_box_count"], 23)
        self.assertEqual(receipt["candidate_metrics"]["solid_component_count"], 4)
        self.assertEqual(receipt["candidate_metrics"]["source_component_owner_count"], 19)
        self.assertGreater(receipt["candidate_metrics"]["double_sided_hidden_area_removed_m2"], 0.0)

    def test_policy_keeps_semantic_and_receiving_authority_separate(self):
        self.assertEqual(
            self.policy["selection_policy"],
            "SEMANTIC_BOXES_REMAIN_AUTHORITY__BOUNDARY_SHELL_REQUIRES_EXPLICIT_CONSUMER_REBIND",
        )
        self.assertEqual(self.policy["fallback_policy"], "NO_IMPLICIT_REPRESENTATION_FALLBACK")
        self.assertNotIn("collision_acceptance", self.policy["derived_representation"]["allowed_roles"])
        self.assertIn("collision_acceptance", self.policy["derived_representation"]["forbidden_inference"])

    def test_geometry_head_drift_fails_closed(self):
        policy = copy.deepcopy(self.policy)
        policy["derived_representation"]["geometry_evidence_head"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "Geometry evidence head drift"):
            module.verify_policy(policy, copy.deepcopy(self.candidate))

    def test_semantic_variant_drift_fails_closed(self):
        policy = copy.deepcopy(self.policy)
        policy["semantic_source"]["variant_id"] = "base-closed-outward-19"
        with self.assertRaisesRegex(ValueError, "semantic source must remain"):
            module.verify_policy(policy, copy.deepcopy(self.candidate))

    def test_implicit_fallback_fails_closed(self):
        policy = copy.deepcopy(self.policy)
        policy["fallback_policy"] = "ALLOW_DEFAULT_FALLBACK"
        with self.assertRaisesRegex(ValueError, "implicit representation fallback"):
            module.verify_policy(policy, copy.deepcopy(self.candidate))

    def test_source_component_provenance_loss_fails_closed(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["candidate"]["source_component_owner_count"] = 18
        with self.assertRaisesRegex(ValueError, "source-component ownership coverage drift"):
            module.verify_policy(copy.deepcopy(self.policy), candidate)

    def test_internal_face_reintroduction_fails_closed(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["candidate"]["internal_face_count_by_construction"] = 1
        with self.assertRaisesRegex(ValueError, "internal_face_count_by_construction"):
            module.verify_policy(copy.deepcopy(self.policy), candidate)


if __name__ == "__main__":
    unittest.main()
