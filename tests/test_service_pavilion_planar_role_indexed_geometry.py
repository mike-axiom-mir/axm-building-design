import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_planar_role_indexed_geometry",
    ROOT / "tools" / "build_service_pavilion_planar_role_indexed_geometry.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ServicePavilionPlanarRoleIndexedGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate, cls.evidence = module.build_evidence("TEST_HEAD")

    def test_exact_source_equivalence_classes_become_render_vertices(self):
        metrics = self.evidence["metrics"]
        self.assertEqual(
            self.evidence["result"],
            "PASS_SOURCE_INTENT_INDEXED_RENDER_DOMAIN_EXACT_CORNER_RECONSTRUCTION",
        )
        self.assertEqual(metrics["source_triangle_corner_count"], 1008)
        self.assertEqual(metrics["render_vertex_count"], 604)
        self.assertEqual(metrics["index_count"], 1008)
        self.assertEqual(metrics["triangle_count"], 336)
        self.assertEqual(metrics["material_role_count"], 5)
        self.assertEqual(metrics["storage_vertex_reduction_vs_unindexed_corners"], 404)

    def test_source_corner_stream_reconstructs_exactly(self):
        metrics = self.evidence["metrics"]
        self.assertTrue(metrics["exact_corner_stream_reconstruction"])
        self.assertEqual(metrics["position_mismatch_count"], 0)
        self.assertEqual(metrics["normal_mismatch_count"], 0)
        self.assertEqual(metrics["material_role_mismatch_count"], 0)
        self.assertEqual(metrics["protected_split_mismatch_count"], 0)

    def test_render_domain_preserves_real_hard_edge_splits(self):
        metrics = self.evidence["metrics"]
        self.assertGreater(metrics["render_vertices_sharing_geometric_position"], 0)
        self.assertGreater(metrics["unique_position_normal_pair_count"], metrics["unique_position_count"])
        self.assertGreater(metrics["cross_rectangle_render_vertex_count"], 0)

    def test_candidate_indices_are_bounded_and_triangle_roles_are_stable(self):
        vertex_count = len(self.candidate["vertices"])
        self.assertEqual(vertex_count, 604)
        self.assertEqual(len(self.candidate["indices"]), 1008)
        self.assertEqual(len(self.candidate["triangles"]), 336)
        self.assertTrue(all(0 <= index < vertex_count for index in self.candidate["indices"]))
        self.assertEqual(len(set(self.candidate["triangle_roles"])), 5)
        self.assertEqual(len(self.candidate["triangle_roles"]), 336)
        self.assertEqual(len(self.candidate["rectangle_ids"]), 336)

    def test_negative_controls_fail_closed(self):
        controls = self.evidence["negative_controls"]
        self.assertTrue(controls)
        self.assertTrue(all(value.startswith("REJECTED:") for value in controls.values()))

    def test_authority_boundary_stays_explicit(self):
        authority = self.evidence["authority"]
        self.assertEqual(authority["semantic_source"], "BUILDING_HARD_SURFACE")
        self.assertEqual(authority["render_domain_construction"], "BUILDING_GEOMETRY_TOPOLOGY")
        self.assertEqual(authority["environment_adoption"], "NOT_GEOMETRY_OWNED")
        self.assertEqual(authority["runtime_adoption"], "NOT_GEOMETRY_OWNED")
        self.assertEqual(authority["transport_acceptance"], "NOT_GEOMETRY_OWNED")
        self.assertEqual(authority["visual_acceptance"], "NOT_GEOMETRY_OWNED")


if __name__ == "__main__":
    unittest.main()
