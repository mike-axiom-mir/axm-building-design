import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_boundary_shell_compaction_v2",
    ROOT / "tools" / "build_service_pavilion_boundary_shell_compaction_v2.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ServicePavilionBoundaryShellCompactionV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate, cls.result = module.build_evidence("TEST_HEAD")

    def test_v2_strictly_improves_conservative_v1(self):
        current = self.result["candidate"]
        previous = self.result["historical_v1_control"]
        self.assertEqual(
            self.result["result"],
            "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_COLLINEAR_CHAIN_V2",
        )
        self.assertLess(current["vertex_count"], previous["vertex_count"])
        self.assertLess(current["triangle_count"], previous["triangle_count"])
        self.assertGreater(current["additional_vertex_reduction_vs_v1"], 0)
        self.assertGreater(current["additional_triangle_reduction_vs_v1"], 0)

    def test_reference_surface_and_source_owner_measures_remain_exact(self):
        donor = self.result["donor"]
        current = self.result["candidate"]
        self.assertEqual(current["bounds"], donor["bounds"])
        self.assertAlmostEqual(current["signed_volume_m3"], donor["signed_volume_m3"], places=9)
        self.assertAlmostEqual(current["surface_area_m2"], donor["surface_area_m2"], places=9)
        self.assertEqual(current["triangle_component_count"], donor["solid_component_count"])
        self.assertEqual(current["source_component_owner_count"], donor["source_component_owner_count"])
        self.assertLessEqual(current["maximum_source_component_area_residual_m2"], module.EPS)
        self.assertLessEqual(current["max_patch_area_residual_m2"], module.EPS)

    def test_structural_topology_stays_closed_oriented_and_fan_connected(self):
        current = self.result["candidate"]
        for key in (
            "boundary_edge_count",
            "nonmanifold_edge_count",
            "orientation_conflict_edge_count",
            "degenerate_triangle_count",
            "isolated_vertex_count",
            "disconnected_vertex_fan_count",
        ):
            self.assertEqual(current[key], 0, key)
        self.assertEqual(current["max_vertex_fan_components"], 1)

    def test_exact_outer_boundary_provenance_is_retained(self):
        self.assertEqual(len(self.candidate["vertices"]), len(self.candidate["source_vertex_ids"]))
        self.assertEqual(len(set(self.candidate["source_vertex_ids"])), len(self.candidate["source_vertex_ids"]))
        self.assertTrue(all(row["source_component_id"] for row in self.candidate["triangle_owners"]))
        self.assertTrue(any(row["status"] == "RETRIANGULATED_CONFORMING_PLANAR_PATCH" for row in self.result["patch_audit"]))

    def test_negative_controls_remain_fail_closed(self):
        self.assertTrue(self.result["negative_controls"])
        self.assertTrue(all(value.startswith("REJECTED:") for value in self.result["negative_controls"].values()))


if __name__ == "__main__":
    unittest.main()
