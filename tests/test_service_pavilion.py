import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_service_pavilion", ROOT / "tools/build_service_pavilion.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ServicePavilionTests(unittest.TestCase):
    def test_structural_build_passes(self):
        pav,panel,fits,obj,mins,maxs,path_gap,negatives,topology = mod.build()
        self.assertEqual(pav["asset_id"], "service-pavilion-001")
        self.assertEqual(pav["schema"], "axm.building-hard-surface/v0.2")
        self.assertEqual(pav["source_revision"], "service-pavilion-001/closed-outward-box-shells-002")
        self.assertEqual(panel["asset_id"], "utility-access-panel-001")
        self.assertEqual(len(fits), 2)
        self.assertAlmostEqual(mod.dot(fits[0]["normal"], fits[1]["normal"]), 0.0)
        self.assertGreaterEqual(path_gap, pav["provenance"]["map_minimum_gap_m"])
        self.assertTrue(all(v.startswith("REJECTED") for v in negatives.values()))
        self.assertEqual(topology["revision"], mod.BOX_TOPOLOGY_REVISION)
        self.assertEqual(topology["object_count"], 19)
        self.assertEqual(topology["vertex_count"], 152)
        self.assertEqual(topology["triangle_count"], 228)
        self.assertEqual(topology["boundary_edge_count"], 0)
        self.assertEqual(topology["nonmanifold_edge_count"], 0)
        self.assertEqual(topology["orientation_conflict_edge_count"], 0)
        self.assertEqual(topology["degenerate_triangle_count"], 0)
        self.assertEqual(topology["outward_triangle_count"], 228)
        self.assertEqual(topology["inward_triangle_count"], 0)
        self.assertEqual(topology["tangent_triangle_count"], 0)

    def test_both_receiver_frames_preserve_exact_mount_pattern(self):
        pav,panel = mod.load(mod.PAVILION), mod.load(mod.PANEL)
        for interface in pav["interfaces"]:
            result = mod.fit_panel(interface, panel)
            self.assertEqual(result["mount_pattern_residual_m"], 0.0)
            self.assertGreaterEqual(result["footprint_margin_m"][0], 0.0)
            self.assertGreaterEqual(result["footprint_margin_m"][1], 0.0)
            self.assertAlmostEqual(
                result["body_clearance_beyond_plate_m"],
                panel["required_body_clearance_beyond_plate_m"],
                places=12,
            )
            self.assertAlmostEqual(result["body_center_surplus_beyond_plate_m"], 0.06, places=12)
            self.assertNotAlmostEqual(
                result["body_center_surplus_beyond_plate_m"],
                result["body_clearance_beyond_plate_m"],
                places=12,
            )

    def test_reserved_map_slot_is_not_exceeded(self):
        pav,panel,fits,obj,mins,maxs,path_gap,negatives,topology = mod.build()
        slot = pav["provenance"]["map_slot_size_m"]
        self.assertGreaterEqual(mins[0], -slot[0]/2)
        self.assertLessEqual(maxs[0], slot[0]/2)
        self.assertGreaterEqual(mins[1], -slot[1]/2)
        self.assertLessEqual(maxs[1], slot[1]/2)
        self.assertGreaterEqual(mins[2], 0.0)
        self.assertLessEqual(maxs[2], slot[2])

    def test_current_box_face_table_is_closed_and_outward(self):
        unit_box = mod.box_vertices([0.0,0.0,0.0],[2.0,2.0,2.0])
        metrics = mod.require_closed_outward_box(unit_box)
        self.assertEqual(metrics["edge_count"], 18)
        self.assertEqual(metrics["boundary_edge_count"], 0)
        self.assertEqual(metrics["nonmanifold_edge_count"], 0)
        self.assertEqual(metrics["orientation_conflict_edge_count"], 0)
        self.assertEqual(metrics["outward_triangle_count"], 12)
        self.assertEqual(metrics["inward_triangle_count"], 0)

    def test_historical_face_table_fails_successor_topology_gate(self):
        unit_box = mod.box_vertices([0.0,0.0,0.0],[2.0,2.0,2.0])
        metrics = mod.inspect_box_shell(unit_box, mod.HISTORICAL_FACES)
        self.assertEqual(metrics["boundary_edge_count"], 6)
        self.assertEqual(metrics["nonmanifold_edge_count"], 2)
        self.assertEqual(metrics["orientation_conflict_edge_count"], 4)
        self.assertEqual(metrics["outward_triangle_count"], 6)
        self.assertEqual(metrics["inward_triangle_count"], 6)
        with self.assertRaises(ValueError):
            mod.require_closed_outward_box(unit_box, mod.HISTORICAL_FACES)

    def test_single_triangle_flip_fails_successor_topology_gate(self):
        unit_box = mod.box_vertices([0.0,0.0,0.0],[2.0,2.0,2.0])
        flipped = list(mod.FACES)
        a,b,c = flipped[0]
        flipped[0] = (a,c,b)
        with self.assertRaises(ValueError):
            mod.require_closed_outward_box(unit_box, flipped)


if __name__ == "__main__":
    unittest.main()
