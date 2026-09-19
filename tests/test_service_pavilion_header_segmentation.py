import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_service_pavilion_header_segmentation",
    ROOT / "tools" / "build_service_pavilion_header_segmentation.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ServicePavilionHeaderSegmentationTests(unittest.TestCase):
    def test_source_owned_successor_removes_exact_positive_volume_intersections(self):
        base, boxes, receipt = mod.build()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_INTERPENETRATION_FREE_HEADER_SEGMENTATION_OVERLAY")
        self.assertEqual(receipt["logical_component_count"], 17)
        self.assertEqual(receipt["logical_source_box_count_with_panels"], 19)
        self.assertEqual(receipt["emitted_successor_box_count_with_panels"], 23)
        self.assertEqual(receipt["source_positive_volume_intersection_count"], 4)
        self.assertAlmostEqual(receipt["source_positive_double_covered_volume_m3"], 0.02592)
        self.assertEqual(receipt["successor_positive_volume_intersection_count"], 0)
        self.assertTrue(receipt["occupied_union"]["equivalent"])
        self.assertEqual(receipt["occupied_union"]["volume_residual_m3"], 0.0)
        self.assertEqual(receipt["receiver_mount_residual_max_m"], 0.0)

    def test_exact_segment_map_and_topology_budget(self):
        base, boxes, receipt = mod.build()
        self.assertEqual(receipt["segment_map"]["front-header"], [
            "front-header::segment-0", "front-header::segment-1", "front-header::segment-2"
        ])
        self.assertEqual(receipt["segment_map"]["rear-header"], [
            "rear-header::segment-0", "rear-header::segment-1", "rear-header::segment-2"
        ])
        topology = receipt["topology"]
        self.assertEqual(topology["object_count"], 23)
        self.assertEqual(topology["vertex_count"], 184)
        self.assertEqual(topology["triangle_count"], 276)
        self.assertEqual(topology["boundary_edge_count"], 0)
        self.assertEqual(topology["nonmanifold_edge_count"], 0)
        self.assertEqual(topology["orientation_conflict_edge_count"], 0)
        self.assertEqual(topology["degenerate_triangle_count"], 0)
        self.assertEqual(topology["outward_triangle_count"], 276)
        self.assertEqual(topology["inward_triangle_count"], 0)

    def test_negative_controls_fail_closed(self):
        base, boxes, receipt = mod.build()
        controls = receipt["negative_controls"]
        self.assertEqual(controls["plus_1mm_header_overlap"]["result"], "REJECTED_POSITIVE_VOLUME_INTERSECTION")
        self.assertGreater(controls["plus_1mm_header_overlap"]["intersection_count"], 0)
        self.assertEqual(controls["minus_1mm_header_gap"]["result"], "REJECTED_OCCUPIED_UNION_CHANGE")
        self.assertNotEqual(controls["minus_1mm_header_gap"]["volume_residual_m3"], 0.0)

    def test_historical_builder_remains_reproducible_and_separate(self):
        base, boxes, receipt = mod.build()
        legacy = base.build()
        topology = legacy[8]
        self.assertEqual(topology["object_count"], 19)
        self.assertEqual(topology["vertex_count"], 152)
        self.assertEqual(topology["triangle_count"], 228)
        self.assertNotEqual(topology["object_count"], receipt["topology"]["object_count"])


if __name__ == "__main__":
    unittest.main()
