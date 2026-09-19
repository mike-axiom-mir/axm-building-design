import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_planar_role_normal_boundary_quotient",
    ROOT / "tools" / "analyze_service_pavilion_planar_role_normal_boundary_quotient.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ServicePavilionPlanarRoleNormalBoundaryQuotientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quotient, cls.evidence = module.build_evidence("TEST_HEAD")

    def test_exact_hard_normal_identity_removal_yields_312_groups(self):
        metrics = self.evidence["metrics"]
        self.assertEqual(
            self.evidence["result"],
            "PASS_HARD_NORMAL_IDENTITY_REMOVAL_YIELDS_EXACT_312_GROUP_STRUCTURAL_QUOTIENT",
        )
        self.assertEqual(metrics["parent_render_vertex_count"], 604)
        self.assertEqual(metrics["diagnostic_quotient_group_count"], 312)
        self.assertEqual(metrics["corner_index_count"], 1008)
        self.assertEqual(metrics["triangle_count"], 336)
        self.assertEqual(metrics["material_role_count"], 5)
        self.assertEqual(metrics["removed_source_vertex_identities"], 292)
        self.assertEqual(
            self.evidence["parent_geometry_source_rebind_head"],
            "fcf3c2a0d3f2f7ee973fb0d7f090f65abf9b8c4e",
        )
        self.assertEqual(
            self.evidence["parent_candidate_sha256"],
            "9b1a13be7287f56ed5a23a4880a12544befcf458fe72b67847c8f319d65c0980",
        )

    def test_hard_normal_boundary_loss_is_explicit(self):
        metrics = self.evidence["metrics"]
        self.assertEqual(metrics["single_source_group_count"], 124)
        self.assertEqual(metrics["two_hard_normal_group_count"], 84)
        self.assertEqual(metrics["three_hard_normal_group_count"], 104)
        self.assertEqual(metrics["hard_normal_crossing_group_count"], 188)
        self.assertEqual(metrics["maximum_source_hard_normals_per_quotient_group"], 3)
        self.assertEqual(metrics["group_size_distribution"], {"1": 124, "2": 84, "3": 104})

    def test_material_position_and_protected_split_boundaries_remain_exact(self):
        metrics = self.evidence["metrics"]
        self.assertTrue(metrics["every_parent_vertex_maps_exactly_once"])
        self.assertEqual(metrics["cross_material_merge_count"], 0)
        self.assertEqual(metrics["cross_position_merge_count"], 0)
        self.assertEqual(metrics["cross_protected_split_merge_count"], 0)
        self.assertEqual(
            metrics["per_role_quotient_group_count"],
            {
                "frame_galvanized": 200,
                "infill_coating": 24,
                "roof_membrane": 36,
                "slab_mineral": 36,
                "utility_panel_ochre": 16,
            },
        )

    def test_diagnostic_emits_no_render_mesh_contract(self):
        self.assertEqual(
            self.quotient["schema"],
            "axm.building-planar-role-normal-boundary-quotient/v0.1",
        )
        self.assertNotIn("vertices", self.quotient)
        self.assertNotIn("triangles", self.quotient)
        self.assertNotIn("normals", self.quotient)
        self.assertEqual(
            self.evidence["authority"]["receiver_identity_or_adoption"],
            "NOT_GEOMETRY_OWNED",
        )
        self.assertEqual(
            self.evidence["authority"]["visual_acceptance"],
            "NOT_GEOMETRY_OWNED",
        )

    def test_negative_controls_fail_closed(self):
        controls = self.evidence["negative_controls"]
        self.assertEqual(
            set(controls),
            {
                "missing_parent_vertex",
                "cross_position_membership",
                "material_role_drift",
                "protected_split_drift",
            },
        )
        for value in controls.values():
            self.assertTrue(value.startswith("REJECTED:"), value)


if __name__ == "__main__":
    unittest.main()
