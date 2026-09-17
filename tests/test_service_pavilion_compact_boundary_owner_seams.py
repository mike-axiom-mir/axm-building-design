import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "verify_service_pavilion_compact_boundary_owner_seams.py"
spec = importlib.util.spec_from_file_location("compact_boundary_owner_seams", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ServicePavilionCompactBoundaryOwnerSeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = module.load_policy()
        cls.compact_policy = module.load_compact_policy()
        cls.donor_shell, cls.donor_result, cls.compact_mesh, cls.compact_result = module.build_exact_meshes("UNIT_TEST")

    def verify(self, policy=None, mesh=None):
        return module.verify(
            copy.deepcopy(self.policy if policy is None else policy),
            copy.deepcopy(self.compact_policy),
            copy.deepcopy(self.donor_shell),
            copy.deepcopy(self.donor_result),
            copy.deepcopy(self.compact_mesh if mesh is None else mesh),
            copy.deepcopy(self.compact_result),
        )

    def first_cross_owner_edge(self):
        incidence = module.edge_incidence(self.compact_mesh["triangles"])
        for edge, incident in incidence.items():
            if len(incident) != 2:
                continue
            first = self.compact_mesh["triangle_owners"][incident[0]]["source_component_id"]
            second = self.compact_mesh["triangle_owners"][incident[1]]["source_component_id"]
            if first != second:
                return edge, incident, first, second
        self.fail("no cross-owner seam found")

    def test_exact_compact_v2_preserves_source_owner_seam_graph(self):
        receipt = self.verify()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_COMPACT_BOUNDARY_OWNER_SEAM_GRAPH_PRESERVED")
        metrics = receipt["metrics"]
        self.assertEqual(metrics["reference_owner_seam_edge_count"], 268)
        self.assertEqual(metrics["compact_owner_seam_edge_count"], 268)
        self.assertEqual(metrics["owner_pair_count"], 30)
        self.assertAlmostEqual(metrics["total_owner_seam_length_m"], 34.72, places=9)
        self.assertEqual(metrics["owner_seam_identity_sha256"], module.EXPECTED_SEAM_DIGEST)
        self.assertEqual(metrics["missing_owner_seam_identities"], 0)
        self.assertEqual(metrics["added_owner_seam_identities"], 0)
        self.assertLessEqual(metrics["maximum_seam_endpoint_residual_m"], module.EPS)
        self.assertLessEqual(metrics["maximum_seam_length_residual_m"], module.EPS)
        self.assertGreater(metrics["same_owner_internal_edge_reduction"], 0)

    def test_cross_owner_triangle_relabel_fails_closed(self):
        mesh = copy.deepcopy(self.compact_mesh)
        _, incident, _, second = self.first_cross_owner_edge()
        mesh["triangle_owners"][incident[0]]["source_component_id"] = second
        with self.assertRaisesRegex(ValueError, "owner-seam"):
            self.verify(mesh=mesh)

    def test_seam_source_vertex_identity_collapse_fails_closed(self):
        mesh = copy.deepcopy(self.compact_mesh)
        edge, _, _, _ = self.first_cross_owner_edge()
        mesh["source_vertex_ids"][edge[0]] = mesh["source_vertex_ids"][edge[1]]
        with self.assertRaisesRegex(ValueError, "source-vertex provenance"):
            self.verify(mesh=mesh)

    def test_physical_seam_authority_expansion_fails_closed(self):
        policy = copy.deepcopy(self.policy)
        policy["physical_seam_inference"] = "PHYSICAL_BEVEL_REQUIRED"
        with self.assertRaisesRegex(ValueError, "physical seam authority"):
            self.verify(policy=policy)

    def test_same_owner_triangulation_is_not_frozen_by_hard_surface(self):
        receipt = self.verify()
        metrics = receipt["metrics"]
        self.assertLess(
            metrics["compact_same_owner_internal_edge_count"],
            metrics["reference_same_owner_internal_edge_count"],
        )
        self.assertEqual(
            receipt["same_owner_internal_policy"],
            "MAY_CHANGE_INSIDE_ONE_OWNER_PLANAR_PATCH_SUBJECT_TO_EXISTING_GEOMETRY_GATES",
        )


if __name__ == "__main__":
    unittest.main()
