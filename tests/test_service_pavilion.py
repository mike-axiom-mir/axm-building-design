import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_service_pavilion", ROOT / "tools/build_service_pavilion.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ServicePavilionTests(unittest.TestCase):
    def test_structural_build_passes(self):
        pav,panel,fits,obj,mins,maxs,path_gap,negatives = mod.build()
        self.assertEqual(pav["asset_id"], "service-pavilion-001")
        self.assertEqual(panel["asset_id"], "utility-access-panel-001")
        self.assertEqual(len(fits), 2)
        self.assertAlmostEqual(mod.dot(fits[0]["normal"], fits[1]["normal"]), 0.0)
        self.assertGreaterEqual(path_gap, pav["provenance"]["map_minimum_gap_m"])
        self.assertTrue(all(v.startswith("REJECTED") for v in negatives.values()))

    def test_both_receiver_frames_preserve_exact_mount_pattern(self):
        pav,panel = mod.load(mod.PAVILION), mod.load(mod.PANEL)
        for interface in pav["interfaces"]:
            result = mod.fit_panel(interface, panel)
            self.assertEqual(result["mount_pattern_residual_m"], 0.0)
            self.assertGreaterEqual(result["footprint_margin_m"][0], 0.0)
            self.assertGreaterEqual(result["footprint_margin_m"][1], 0.0)
            self.assertGreaterEqual(result["body_clearance_beyond_plate_m"], panel["required_body_clearance_beyond_plate_m"])

    def test_reserved_map_slot_is_not_exceeded(self):
        pav,panel,fits,obj,mins,maxs,path_gap,negatives = mod.build()
        slot = pav["provenance"]["map_slot_size_m"]
        self.assertGreaterEqual(mins[0], -slot[0]/2)
        self.assertLessEqual(maxs[0], slot[0]/2)
        self.assertGreaterEqual(mins[1], -slot[1]/2)
        self.assertLessEqual(maxs[1], slot[1]/2)
        self.assertGreaterEqual(mins[2], 0.0)
        self.assertLessEqual(maxs[2], slot[2])


if __name__ == "__main__":
    unittest.main()
