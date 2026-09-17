import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


geo = load(
    ROOT / "tools" / "build_service_pavilion_interpenetration_candidate.py",
    "building_geometry_interpenetration_candidate",
)


class ServicePavilionInterpenetrationCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt, cls.source_obj, cls.candidate_obj = geo.build_evidence("UNIT_TEST_HEAD")

    def test_exact_source_overlap_signature_is_bounded(self):
        self.assertEqual(self.receipt["source_positive_volume_intersection_count"], 4)
        self.assertEqual(self.receipt["source_positive_overlap_volume_m3"], 0.02592)
        self.assertEqual(
            [
                (row["a"], row["b"], tuple(row["overlap_size_m"]), row["overlap_volume_m3"])
                for row in self.receipt["source_positive_volume_intersections"]
            ],
            geo.EXPECTED_SOURCE_OVERLAPS,
        )

    def test_candidate_removes_volume_overlap_without_changing_union(self):
        self.assertEqual(self.receipt["candidate_positive_volume_intersection_count"], 0)
        self.assertTrue(self.receipt["union_equivalence"]["equivalent"])
        self.assertEqual(self.receipt["union_equivalence"]["volume_residual_m3"], 0.0)
        self.assertEqual(self.receipt["source_component_volume_sum_m3"], 9.52424)
        self.assertEqual(self.receipt["candidate_component_volume_sum_m3"], 9.49832)
        self.assertEqual(self.receipt["removed_double_covered_volume_m3"], 0.02592)
        self.assertEqual(self.receipt["combined_bounds_source"], self.receipt["combined_bounds_candidate"])

    def test_candidate_keeps_closed_outward_box_topology(self):
        topo = self.receipt["candidate_box_topology"]
        self.assertEqual(topo["object_count"], 23)
        self.assertEqual(topo["vertex_count"], 184)
        self.assertEqual(topo["triangle_count"], 276)
        self.assertEqual(topo["boundary_edge_count"], 0)
        self.assertEqual(topo["nonmanifold_edge_count"], 0)
        self.assertEqual(topo["orientation_conflict_edge_count"], 0)
        self.assertEqual(topo["degenerate_triangle_count"], 0)
        self.assertEqual(topo["outward_triangle_count"], 276)
        self.assertEqual(topo["inward_triangle_count"], 0)

    def test_cost_and_remaining_contact_truth_are_explicit(self):
        self.assertEqual(self.receipt["cost_delta"], {
            "box_objects": 4,
            "vertices": 32,
            "triangles": 48,
            "note": "representation cost only; no runtime/draw-call claim",
        })
        self.assertEqual(self.receipt["source_face_contact_count"], 26)
        self.assertEqual(self.receipt["candidate_face_contact_count"], 34)
        self.assertIn(
            "removal of coplanar internal faces at face contacts",
            self.receipt["truth_boundary"]["not_proved"],
        )

    def test_negative_controls_fail_closed(self):
        negatives = self.receipt["negative_controls"]
        self.assertFalse(negatives["front_header_segment_overlap_plus_0p001m"]["accepted"])
        self.assertGreater(
            len(negatives["front_header_segment_overlap_plus_0p001m"]["positive_volume_intersections"]),
            0,
        )
        self.assertFalse(negatives["front_header_segment_gap_plus_0p001m"]["accepted"])
        self.assertFalse(
            negatives["front_header_segment_gap_plus_0p001m"]["union_equivalence"]["equivalent"]
        )


if __name__ == "__main__":
    unittest.main()
