from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_building_material_lookdev_evidence import build_payload, validate_profile


class BuildingMaterialsLookdevTests(unittest.TestCase):
    def setUp(self):
        self.pavilion = ROOT / "assets/service_pavilion_001.json"
        self.panel = ROOT / "assets/utility_access_panel_001.json"
        self.profile_path = ROOT / "lookdev/building_material_profile_001.json"
        self.profile = json.loads(self.profile_path.read_text(encoding="utf-8"))

    def test_exact_sources_build_one_shared_geometry_contract(self):
        payload, receipt = build_payload(self.pavilion, self.panel, self.profile_path)
        self.assertEqual(receipt["result"], "PASS_SOURCE_BOUND_BUILDING_SURFACE_PAYLOAD")
        self.assertEqual(receipt["structural_prerequisite"]["result"], "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF")
        self.assertEqual(payload["pavilion_asset_id"], "service-pavilion-001")
        self.assertEqual(payload["panel_asset_id"], "utility-access-panel-001")
        self.assertEqual(len(payload["components"]), 19)
        self.assertTrue(payload["truth_boundary"]["same_geometry_baseline_candidate"])
        self.assertTrue(payload["truth_boundary"]["source_receiver_frames_preserved"])
        self.assertFalse(payload["truth_boundary"]["textures"])

    def test_building_surface_hierarchy_is_explicit(self):
        payload, _receipt = build_payload(self.pavilion, self.panel, self.profile_path)
        materials = payload["materials"]["candidate"]
        mapping = self.profile["component_materials"]
        self.assertEqual(mapping["panel-front-utility-bay"], mapping["panel-east-utility-bay"])
        self.assertNotEqual(mapping["slab"], mapping["roof"])
        self.assertNotEqual(mapping["rear-infill-center"], mapping["front-header"])
        self.assertGreater(materials["frame_galvanized"]["metallic"], materials["infill_coating"]["metallic"])
        self.assertGreater(materials["slab_mineral"]["roughness"], materials["frame_galvanized"]["roughness"])

    def test_missing_source_component_mapping_fails_closed(self):
        broken = copy.deepcopy(self.profile)
        broken["component_materials"].pop("east-header")
        component_ids = set(self.profile["component_materials"])
        with self.assertRaisesRegex(AssertionError, "component coverage mismatch"):
            validate_profile(broken, component_ids)

    def test_unknown_material_fails_closed(self):
        broken = copy.deepcopy(self.profile)
        broken["component_materials"]["roof"] = "not-a-material"
        with self.assertRaisesRegex(AssertionError, "unknown candidate material"):
            validate_profile(broken, set(broken["component_materials"]))

    def test_scalar_bounds_fail_closed(self):
        broken = copy.deepcopy(self.profile)
        broken["candidate"]["frame_galvanized"]["metallic"] = 1.1
        with self.assertRaisesRegex(AssertionError, "PBR scalar out of bounds"):
            validate_profile(broken, set(broken["component_materials"]))


if __name__ == "__main__":
    unittest.main()
