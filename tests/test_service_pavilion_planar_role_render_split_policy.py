import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "verify_service_pavilion_planar_role_render_split_policy.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("planar_role_render_split_policy_test_module", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PlanarRoleRenderSplitPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_tool()
        cls.retained, cls.result = cls.module.build_evidence("TEST_HEAD")

    def test_source_owned_split_intent_passes(self):
        self.assertEqual(
            self.result["result"],
            "PASS_SOURCE_OWNED_PLANAR_ROLE_RENDER_SPLIT_INTENT",
        )
        self.assertEqual(
            self.result["representation_id"],
            "boundary-only-planar-role-rectangle-render-001",
        )
        self.assertEqual(self.result["semantic_source_variant"], "header-segmented-23")
        self.assertEqual(self.result["rectangle_count"], 168)
        self.assertEqual(self.result["triangle_count"], 336)
        self.assertEqual(self.result["material_role_count"], 5)

    def test_exact_render_corner_grouping_is_bounded(self):
        intent = self.result["source_intent"]
        self.assertEqual(intent["triangle_corner_count"], 1008)
        # Source-owner grouping is intentionally stricter than the current downstream
        # Godot 312-vertex receiver because the Hard-Surface candidate owns exact
        # cardinal hard normals. Do not weaken this test to match a consumer result.
        self.assertEqual(intent["equivalence_group_count"], 604)
        self.assertEqual(intent["storage_group_reduction"], 404)
        self.assertAlmostEqual(intent["storage_group_reduction_fraction"], 404 / 1008)
        self.assertGreater(intent["cross_rectangle_group_count"], 0)
        self.assertGreaterEqual(intent["maximum_group_member_count"], 2)

    def test_every_corner_explicitly_declares_current_protected_split(self):
        records = self.retained["corner_records"]
        self.assertEqual(len(records), 1008)
        self.assertTrue(all("protected_split_id" in record for record in records))
        self.assertTrue(all(record["protected_split_id"] is None for record in records))
        self.assertTrue(self.result["source_intent"]["all_protected_split_ids_explicit"])
        self.assertTrue(self.result["source_intent"]["all_current_protected_split_ids_null"])

    def test_equivalence_groups_never_cross_owned_boundaries(self):
        for group in self.retained["equivalence_groups"]:
            member_records = [self.retained["corner_records"][index] for index in group["member_corner_indices"]]
            self.assertTrue(all(record["material_role"] == group["material_role"] for record in member_records))
            self.assertTrue(all(record["position"] == group["position"] for record in member_records))
            self.assertTrue(all(record["normal"] == group["normal"] for record in member_records))
            self.assertTrue(all(record["protected_split_id"] == group["protected_split_id"] for record in member_records))

    def test_policy_keeps_downstream_authority_separate(self):
        policy = self.module.load_policy()
        intent = policy["intent"]
        self.assertFalse(intent["indexing_implementation_owned_by_hard_surface"])
        self.assertFalse(intent["runtime_adoption_owned_by_hard_surface"])
        self.assertFalse(intent["transport_acceptance_owned_by_hard_surface"])
        self.assertFalse(intent["visual_acceptance_owned_by_hard_surface"])
        self.assertEqual(
            policy["selection_policy"],
            "SOURCE_INTENT_ONLY__CONSUMERS_MUST_EXPLICITLY_REBIND_AND_RETEST",
        )

    def test_parent_planar_role_policy_is_exactly_pinned(self):
        self.assertEqual(
            self.module.git_blob_sha1(self.module.PARENT_POLICY_PATH),
            self.module.EXPECTED_PARENT_POLICY_GIT_BLOB,
        )
        self.assertEqual(
            self.result["parent_owner_head"],
            "93f22e4eeb9bb32516d4b11f8d8bcf47d9792910",
        )

    def test_negative_controls_fail_closed(self):
        controls = self.result["negative_controls"]
        self.assertTrue(controls["missing_protected_split_declaration"].startswith("REJECTED:"))
        self.assertTrue(controls["explicit_non_attribute_split"].startswith("REJECTED:"))
        self.assertTrue(controls["authority_inflation"].startswith("REJECTED:"))


if __name__ == "__main__":
    unittest.main()
