import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_union_shell_candidate",
    ROOT / "tools" / "build_service_pavilion_union_shell_candidate.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ServicePavilionUnionShellCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell, cls.result = module.build_evidence("TEST_HEAD")

    def test_current_source_identity_and_exact_union_are_preserved(self):
        result = self.result
        self.assertEqual(result["result"], "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE")
        self.assertEqual(result["exact_geometry_head"], "TEST_HEAD")
        self.assertEqual(result["current_source_policy"]["variant_id"], "header-segmented-23")
        self.assertEqual(result["source"]["emitted_box_count"], 23)
        self.assertEqual(result["source"]["positive_volume_intersection_count"], 0)
        self.assertAlmostEqual(
            result["candidate"]["signed_volume_m3"],
            result["source"]["occupied_union_volume_m3"],
            places=9,
        )
        self.assertEqual(result["candidate"]["bounds"], result["source"]["bounds"])

    def test_boundary_only_shell_is_closed_oriented_and_vertex_fan_connected(self):
        candidate = self.result["candidate"]
        self.assertEqual(candidate["boundary_edge_count"], 0)
        self.assertEqual(candidate["nonmanifold_edge_count"], 0)
        self.assertEqual(candidate["orientation_conflict_edge_count"], 0)
        self.assertEqual(candidate["degenerate_triangle_count"], 0)
        self.assertEqual(candidate["isolated_vertex_count"], 0)
        self.assertEqual(candidate["disconnected_vertex_fan_count"], 0)
        self.assertEqual(candidate["max_vertex_fan_components"], 1)
        self.assertEqual(candidate["internal_face_count_by_construction"], 0)

    def test_hidden_contact_area_is_removed_from_box_surface_sum(self):
        result = self.result
        removal = result["internal_face_removal"]
        self.assertGreater(removal["contact_patch_count"], 0)
        self.assertGreater(removal["single_sided_internal_contact_area_m2"], 0.0)
        self.assertAlmostEqual(
            result["source"]["surface_area_sum_m2"] - result["candidate"]["surface_area_m2"],
            removal["double_sided_hidden_area_removed_m2"],
            places=9,
        )
        self.assertAlmostEqual(
            result["candidate"]["surface_area_m2"],
            removal["expected_boundary_surface_area_m2"],
            places=9,
        )

    def test_every_boundary_triangle_retains_source_owner(self):
        self.assertEqual(len(self.shell["triangles"]), len(self.shell["triangle_owners"]))
        self.assertTrue(self.result["candidate"]["source_component_triangle_counts"])
        self.assertTrue(all(row["source_component_id"] for row in self.shell["triangle_owners"]))

    def test_negative_controls_fail_closed(self):
        controls = self.result["negative_controls"]
        self.assertTrue(controls["reintroduced_internal_contact_face"].startswith("REJECTED:"))
        self.assertTrue(controls["missing_boundary_triangle"].startswith("REJECTED:"))
        self.assertTrue(controls["single_triangle_winding_flip"].startswith("REJECTED:"))


if __name__ == "__main__":
    unittest.main()
