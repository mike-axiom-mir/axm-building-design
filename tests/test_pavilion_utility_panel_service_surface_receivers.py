import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/build_pavilion_utility_panel_service_surface_receivers.py"
DOMAIN_PATH = ROOT / "assets/utility_access_panel_001_service_surface_domain.json"
PROFILE_PATH = ROOT / "procedural/service_pavilion_utility_panel_service_surface_receivers_001.json"

spec = importlib.util.spec_from_file_location("surface_receiver_family", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def placement(receiver_id, center, basis):
    local_vertices = [
        [x, y, z]
        for x in (-0.04, 0.04)
        for y in (-0.55, 0.55)
        for z in (-0.75, 0.75)
    ]
    provisional = {
        "receiver_id": receiver_id,
        "panel_asset_id": "utility-access-panel-001",
        "center_m": center,
        "basis_normal_lateral_up": basis,
        "scale": [1.0, 1.0, 1.0],
        "extra_rotation_deg": [0.0, 0.0, 0.0],
        "placement_digest": receiver_id + "-placement",
    }
    provisional["vertices"] = [module.transform_local_point(provisional, point) for point in local_vertices]
    return provisional


class UtilityPanelServiceSurfaceReceiverFamilyTests(unittest.TestCase):
    def setUp(self):
        self.domain = json.loads(DOMAIN_PATH.read_text(encoding="utf-8"))
        self.front = placement(
            "front-utility-bay",
            [-2.45, -1.08, 1.65],
            [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )
        self.east = placement(
            "east-utility-bay",
            [3.88, 0.1, 1.65],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_profile_binds_exact_owner_and_previous_family(self):
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        module.verify_profile(profile)
        self.assertEqual(profile["source_surface"]["pr"], 17)
        self.assertEqual(
            profile["source_surface"]["head"],
            "fbfa3b47048755b45dac91451171d5511c8d4f47",
        )
        self.assertEqual(
            profile["source_surface"]["contract_blob_sha"],
            "8b4484d4ccbd500e58910a2835d8780112489919",
        )

    def test_front_surface_uses_exact_source_domain(self):
        output = module.derive_surface(self.front, self.domain)
        self.assertEqual(output["world_origin_m"], [-2.45, -1.12, 1.65])
        self.assertEqual(output["world_outward_axis"], [0.0, -1.0, 0.0])
        self.assertEqual(
            output["corners_m"],
            [
                [-3.0, -1.12, 0.8999999999999999],
                [-1.9000000000000001, -1.12, 0.8999999999999999],
                [-1.9000000000000001, -1.12, 2.4],
                [-3.0, -1.12, 2.4],
            ],
        )
        self.assertAlmostEqual(output["area_m2"], 1.65, places=12)

    def test_east_surface_is_materially_different_orientation(self):
        output = module.derive_surface(self.east, self.domain)
        self.assertEqual(output["world_origin_m"], [3.92, 0.1, 1.65])
        self.assertEqual(output["world_outward_axis"], [1.0, 0.0, 0.0])
        self.assertEqual(
            output["corners_m"],
            [
                [3.92, -0.45000000000000007, 0.8999999999999999],
                [3.92, 0.65, 0.8999999999999999],
                [3.92, 0.65, 2.4],
                [3.92, -0.45000000000000007, 2.4],
            ],
        )
        front = module.derive_surface(self.front, self.domain)
        self.assertNotEqual(output["world_surface_digest"], front["world_surface_digest"])
        self.assertAlmostEqual(module.dot(output["world_outward_axis"], front["world_outward_axis"]), 0.0, places=12)

    def test_canonical_digest_is_order_invariant(self):
        outputs = [module.derive_surface(self.front, self.domain), module.derive_surface(self.east, self.domain)]
        self.assertEqual(module.canonical_family_digest(outputs), module.canonical_family_digest(list(reversed(outputs))))

    def test_scale_injection_fails_closed(self):
        bad = dict(self.front)
        bad["scale"] = [1.0, 1.001, 1.0]
        with self.assertRaises(ValueError):
            module.derive_surface(bad, self.domain)


if __name__ == "__main__":
    unittest.main()
