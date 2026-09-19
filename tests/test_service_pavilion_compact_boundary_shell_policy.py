import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "service_pavilion_compact_boundary_shell_policy.py"
spec = importlib.util.spec_from_file_location("compact_boundary_shell_policy", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ServicePavilionCompactBoundaryShellPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = module.load_policy()
        cls.candidate_mesh, cls.geometry_result = module.build_compaction_receipt("UNIT_TEST")

    def test_exact_compact_v2_passes_source_owner_policy(self):
        receipt = module.verify_policy(
            copy.deepcopy(self.policy),
            copy.deepcopy(self.candidate_mesh),
            copy.deepcopy(self.geometry_result),
        )
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_COMPACT_BOUNDARY_SHELL_RECEIVING_OPTION")
        self.assertEqual(receipt["semantic_source"]["variant_id"], "header-segmented-23")
        self.assertEqual(receipt["metrics"]["reference_vertex_count"], 1420)
        self.assertEqual(receipt["metrics"]["reference_triangle_count"], 2884)
        self.assertEqual(receipt["metrics"]["compact_vertex_count"], 1004)
        self.assertEqual(receipt["metrics"]["compact_triangle_count"], 2052)
        self.assertEqual(receipt["metrics"]["historical_v1_vertex_count"], 1402)
        self.assertEqual(receipt["metrics"]["historical_v1_triangle_count"], 2848)
        self.assertEqual(receipt["metrics"]["source_component_owner_count"], 19)
        self.assertEqual(receipt["metrics"]["solid_component_count"], 4)

    def test_semantic_reference_and_compact_roles_stay_separate(self):
        self.assertEqual(self.policy["semantic_source"]["authority"], "SEMANTIC_SOURCE_OF_TRUTH")
        self.assertEqual(
            self.policy["compact_representation"]["status"],
            "SOURCE_OWNED_DERIVED_COMPACT_RECEIVING_OPTION_NOT_DEFAULT",
        )
        self.assertEqual(
            self.policy["selection_policy"],
            "EXPLICIT_RECEIVING_REPRESENTATION_ID_REQUIRED__NO_DEFAULT_OR_IMPLICIT_FALLBACK",
        )
        self.assertEqual(
            self.policy["current_downstream_state"]["materials_reference_or_v1_evidence"],
            "DOES_NOT_COVER_COMPACT_V2",
        )

    def test_compact_geometry_head_drift_fails_closed(self):
        policy = copy.deepcopy(self.policy)
        policy["compact_representation"]["geometry_evidence_head"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "compact Geometry evidence head drift"):
            module.verify_policy(policy, copy.deepcopy(self.candidate_mesh), copy.deepcopy(self.geometry_result))

    def test_source_rebind_head_drift_fails_closed(self):
        policy = copy.deepcopy(self.policy)
        policy["compact_representation"]["source_rebind_head"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "compact source-rebind head drift"):
            module.verify_policy(policy, copy.deepcopy(self.candidate_mesh), copy.deepcopy(self.geometry_result))

    def test_automatic_compact_adoption_fails_closed(self):
        policy = copy.deepcopy(self.policy)
        policy["compact_representation"]["status"] = "SOURCE_ADOPTED_DEFAULT"
        with self.assertRaisesRegex(ValueError, "compact representation adoption/authority drift"):
            module.verify_policy(policy, copy.deepcopy(self.candidate_mesh), copy.deepcopy(self.geometry_result))

    def test_cross_representation_pass_transfer_fails_closed(self):
        policy = copy.deepcopy(self.policy)
        policy["evidence_transfer_policy"] = "ALLOW_REFERENCE_PASS_TRANSFER"
        with self.assertRaisesRegex(ValueError, "downstream evidence transfer policy weakened"):
            module.verify_policy(policy, copy.deepcopy(self.candidate_mesh), copy.deepcopy(self.geometry_result))

    def test_historical_materials_evidence_cannot_cover_v2_without_rebind(self):
        policy = copy.deepcopy(self.policy)
        policy["current_downstream_state"]["materials_reference_or_v1_evidence"] = "COVERS_COMPACT_V2"
        with self.assertRaisesRegex(ValueError, "silently transferred"):
            module.verify_policy(policy, copy.deepcopy(self.candidate_mesh), copy.deepcopy(self.geometry_result))

    def test_source_component_provenance_loss_fails_closed(self):
        mesh = copy.deepcopy(self.candidate_mesh)
        mesh["triangle_owners"][0]["source_component_id"] = None
        with self.assertRaisesRegex(ValueError, "lost source-component provenance"):
            module.verify_policy(copy.deepcopy(self.policy), mesh, copy.deepcopy(self.geometry_result))

    def test_compact_payload_identity_drift_fails_closed(self):
        result = copy.deepcopy(self.geometry_result)
        result["candidate"]["payload_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "payload does not match"):
            module.verify_policy(copy.deepcopy(self.policy), copy.deepcopy(self.candidate_mesh), result)


if __name__ == "__main__":
    unittest.main()
