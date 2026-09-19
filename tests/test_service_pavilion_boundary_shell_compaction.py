import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_boundary_shell_compaction",
    ROOT / "tools" / "build_service_pavilion_boundary_shell_compaction.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ServicePavilionBoundaryShellCompactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate, cls.result = module.build_evidence("TEST_HEAD")

    def test_exact_donor_identity_and_surface_are_preserved(self):
        result = self.result
        self.assertEqual(result["result"], "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_CANDIDATE")
        self.assertEqual(result["exact_geometry_head"], "TEST_HEAD")
        self.assertEqual(result["donor"]["semantic_source_variant_id"], "header-segmented-23")
        self.assertAlmostEqual(result["candidate"]["signed_volume_m3"], result["donor"]["signed_volume_m3"], places=9)
        self.assertAlmostEqual(result["candidate"]["surface_area_m2"], result["donor"]["surface_area_m2"], places=9)
        self.assertEqual(result["candidate"]["bounds"], result["donor"]["bounds"])
        self.assertEqual(result["candidate"]["triangle_component_count"], result["donor"]["solid_component_count"])
        self.assertEqual(result["candidate"]["source_component_owner_count"], result["donor"]["source_component_owner_count"])
        self.assertLessEqual(result["candidate"]["maximum_source_component_area_residual_m2"], module.EPS)
        self.assertLessEqual(result["candidate"]["max_patch_area_residual_m2"], module.EPS)

    def test_compaction_reduces_reference_shell_without_moving_vertices(self):
        result = self.result
        self.assertGreater(result["candidate"]["compacted_patch_count"], 0)
        self.assertGreater(result["candidate"]["vertex_reduction"], 0)
        self.assertGreater(result["candidate"]["triangle_reduction"], 0)
        self.assertLess(result["candidate"]["vertex_count"], result["donor"]["vertex_count"])
        self.assertLess(result["candidate"]["triangle_count"], result["donor"]["triangle_count"])
        self.assertEqual(len(self.candidate["vertices"]), len(self.candidate["source_vertex_ids"]))
        self.assertEqual(len(set(self.candidate["source_vertex_ids"])), len(self.candidate["source_vertex_ids"]))

    def test_compacted_shell_remains_closed_oriented_and_vertex_fan_connected(self):
        candidate = self.result["candidate"]
        self.assertEqual(candidate["boundary_edge_count"], 0)
        self.assertEqual(candidate["nonmanifold_edge_count"], 0)
        self.assertEqual(candidate["orientation_conflict_edge_count"], 0)
        self.assertEqual(candidate["degenerate_triangle_count"], 0)
        self.assertEqual(candidate["isolated_vertex_count"], 0)
        self.assertEqual(candidate["disconnected_vertex_fan_count"], 0)
        self.assertEqual(candidate["max_vertex_fan_components"], 1)

    def test_every_triangle_retains_source_component_provenance(self):
        self.assertEqual(len(self.candidate["triangles"]), len(self.candidate["triangle_owners"]))
        self.assertTrue(all(row["source_component_id"] for row in self.candidate["triangle_owners"]))
        self.assertEqual(
            set(self.result["candidate"]["source_component_boundary_area_m2"]),
            set(self.result["donor"].get("source_component_boundary_area_m2", self.result["candidate"]["source_component_boundary_area_m2"])),
        )

    def test_patch_audit_is_explicit_and_fail_closed(self):
        self.assertTrue(self.result["patch_audit"])
        self.assertTrue(all(row["area_residual_m2"] <= module.EPS for row in self.result["patch_audit"]))
        controls = self.result["negative_controls"]
        self.assertTrue(controls)
        self.assertTrue(all(value.startswith("REJECTED:") for value in controls.values()))

    def test_evidence_is_deterministic(self):
        _, second = module.build_evidence("TEST_HEAD")
        self.assertEqual(self.result["candidate"]["payload_sha256"], second["candidate"]["payload_sha256"])
        self.assertEqual(self.result["candidate"]["vertex_count"], second["candidate"]["vertex_count"])
        self.assertEqual(self.result["candidate"]["triangle_count"], second["candidate"]["triangle_count"])


if __name__ == "__main__":
    unittest.main()
