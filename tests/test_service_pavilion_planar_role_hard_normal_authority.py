import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_planar_role_hard_normal_authority",
    ROOT / "tools" / "verify_service_pavilion_planar_role_hard_normal_authority.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ServicePavilionPlanarRoleHardNormalAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = module.build_evidence("TEST_HEAD")

    def test_source_owner_boundary_passes(self):
        self.assertEqual(
            self.evidence["result"],
            "PASS_SOURCE_OWNED_PLANAR_ROLE_HARD_NORMAL_AUTHORITY_BOUNDARY",
        )
        self.assertFalse(self.evidence["source_mesh_changed"])
        self.assertFalse(self.evidence["source_normal_field_changed"])
        self.assertFalse(self.evidence["product_312_mesh_emitted"])
        self.assertFalse(self.evidence["consumer_adoption"])
        self.assertFalse(self.evidence["uc_or_profession_fabric_changed"])
        self.assertEqual(
            self.evidence["geometry_source_rebind_head"],
            "fcf3c2a0d3f2f7ee973fb0d7f090f65abf9b8c4e",
        )

    def test_604_and_312_remain_distinct_authority_classes(self):
        metrics = self.evidence["metrics"]
        self.assertEqual(metrics["source_intent_render_vertices"], 604)
        self.assertEqual(metrics["role_position_quotient_groups"], 312)
        self.assertEqual(metrics["source_render_vertex_identities_removed"], 292)
        self.assertEqual(metrics["hard_normal_crossing_groups"], 188)
        self.assertEqual(metrics["single_hard_normal_groups"], 124)
        self.assertEqual(metrics["two_hard_normal_groups"], 84)
        self.assertEqual(metrics["three_hard_normal_groups"], 104)
        self.assertEqual(metrics["maximum_source_hard_normal_classes_per_group"], 3)
        self.assertEqual(
            self.evidence["classification"]["source_604"],
            "SOURCE_AUTHORIZED_RENDER_EQUIVALENCE",
        )
        self.assertEqual(
            self.evidence["classification"]["quotient_312"],
            "DERIVED_ATTRIBUTE_DROPPING_PARTITION_NOT_SOURCE_EQUIVALENT",
        )
        self.assertEqual(
            self.evidence["classification"]["dropped_source_attribute"],
            "EXACT_CARDINAL_HARD_NORMAL",
        )

    def test_hard_surface_does_not_take_downstream_authority(self):
        authority = self.evidence["authority"]
        self.assertEqual(
            authority["source_representation_and_hard_normal_intent"],
            "BUILDING_HARD_SURFACE",
        )
        self.assertEqual(
            authority["structural_quotient_diagnostic"],
            "BUILDING_GEOMETRY_TOPOLOGY_PR_13",
        )
        for key in (
            "receiver_identity_or_adoption",
            "normal_generation_or_repacking",
            "transport_acceptance",
            "runtime_acceptance",
            "visual_acceptance",
        ):
            self.assertEqual(authority[key], "NOT_HARD_SURFACE_OWNED")

    def test_negative_controls_fail_closed(self):
        controls = self.evidence["negative_controls"]
        self.assertEqual(
            set(controls),
            {
                "cross_hard_normal_sharing_enabled",
                "quotient_promoted_to_source_equivalence",
                "consumer_source_normal_transfer_claim",
                "geometry_boundary_loss_hidden",
                "automatic_receiver_adoption",
            },
        )
        for value in controls.values():
            self.assertTrue(value.startswith("REJECTED:"), value)

    def test_direct_consumer_promotion_mutation_is_rejected(self):
        policy = module.load_json(module.POLICY_PATH)
        source_split = module.load_json(module.SOURCE_SPLIT_PATH)
        geometry_policy = module.load_json(module.GEOMETRY_POLICY_PATH)
        geometry_module = module.load_module(
            module.GEOMETRY_TOOL_PATH,
            "building_normal_boundary_quotient_for_hard_surface_unit_test",
        )
        _quotient, geometry_evidence = geometry_module.build_evidence("TEST_HEAD")
        mutated = copy.deepcopy(policy)
        mutated["consumer_policy"]["equal_312_count_is_source_equivalence"] = True
        with self.assertRaisesRegex(ValueError, "authority inflation"):
            module.validate_policy(mutated, source_split, geometry_policy, geometry_evidence)


if __name__ == "__main__":
    unittest.main()
