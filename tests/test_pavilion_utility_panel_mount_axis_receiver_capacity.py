import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/build_pavilion_utility_panel_mount_axis_receiver_capacity.py"
PROFILE_PATH = ROOT / "procedural/service_pavilion_utility_panel_mount_axis_receiver_capacity_001.json"

spec = importlib.util.spec_from_file_location("mount_axis_receiver_capacity", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def source_contract():
    return {
        "schema": "axm.building-panel-mount-axis-clearance-capacity/v0.1",
        "applies_to_asset_id": "utility-access-panel-001",
        "units": "meters",
        "observed_capacity": {
            "mount_axis_count": 4,
            "minimum_axis_to_footprint_boundary_m": 0.05,
            "minimum_axis_pair_distance_m": 1.0,
            "closed_common_reservation_tangency_cap_m": 0.05,
            "limiting_constraint": "FOOTPRINT_EDGE",
            "capacity_invariant_under_supported_180_degree_reversal": True,
        },
        "reservation_radius_selected": False,
        "fastener_geometry_established": False,
        "tooling_envelope_established": False,
        "retention_method_established": False,
    }


def source_panel():
    return {
        "asset_id": "utility-access-panel-001",
        "units": "meters",
        "interface_footprint_m": [1.10, 1.50],
        "mount_points_local_m": [
            [-0.50, -0.70],
            [0.50, -0.70],
            [0.50, 0.70],
            [-0.50, 0.70],
        ],
    }


def surface(receiver_id, origin, primary, secondary, outward, digest):
    return {
        "receiver_id": receiver_id,
        "surface_id": "utility_panel_outer_service_surface",
        "world_surface_digest": digest,
        "world_origin_m": origin,
        "world_primary_axis": primary,
        "world_secondary_axis": secondary,
        "world_outward_axis": outward,
        "primary_extent_m": 1.10,
        "secondary_extent_m": 1.50,
    }


class UtilityPanelMountAxisReceiverCapacityTests(unittest.TestCase):
    def setUp(self):
        self.contract = source_contract()
        self.panel = source_panel()
        self.capacity = module.verify_capacity_contract(self.contract, self.panel)
        self.front = surface(
            "front-utility-bay",
            [-2.45, -1.12, 1.65],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, -1.0, 0.0],
            "front-surface",
        )
        self.east = surface(
            "east-utility-bay",
            [3.92, 0.10, 1.65],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 0.0],
            "east-surface",
        )

    def test_profile_pins_owner_and_existing_receiver_family(self):
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        # Unit suites may run from deliberate fetch-depth=1 checkouts where the
        # exact Hard-Surface donor object is unavailable. Keep this unit test
        # focused on the declared contract and current receiving-family pins;
        # the dedicated full-history workflow and real evidence build perform
        # the exact donor/blob lookups and fail closed there.
        with mock.patch.object(
            module,
            "git_blob_at",
            side_effect=[module.CAPACITY_BLOB, module.PANEL_BLOB],
        ):
            module.verify_profile(profile)

    def test_source_capacity_is_recomputed_without_selecting_radius(self):
        self.assertAlmostEqual(self.capacity["closed_common_reservation_tangency_cap_m"], 0.05, places=12)
        self.assertAlmostEqual(self.capacity["minimum_axis_to_footprint_boundary_m"], 0.05, places=12)
        self.assertAlmostEqual(self.capacity["minimum_axis_pair_distance_m"], 1.0, places=12)
        self.assertLessEqual(self.capacity["maximum_capacity_recompute_residual_m"], 1e-12)

    def test_front_and_east_generate_materially_different_world_axis_sets(self):
        front = module.derive_receiver(self.front, self.capacity)
        east = module.derive_receiver(self.east, self.capacity)
        self.assertNotEqual(front["receiver_axis_set_digest"], east["receiver_axis_set_digest"])
        self.assertEqual(front["axis_count"], 4)
        self.assertEqual(east["axis_count"], 4)
        self.assertAlmostEqual(module.dot(front["world_outward_axis"], east["world_outward_axis"]), 0.0, places=12)
        self.assertEqual(front["axes"][0]["world_axis_origin_on_outer_service_surface_m"], [-2.95, -1.12, 0.95])
        self.assertEqual(east["axes"][0]["world_axis_origin_on_outer_service_surface_m"], [3.92, -0.4, 0.95])

    def test_source_mount_spacing_and_reversal_survive_both_receiver_frames(self):
        for item in (self.front, self.east):
            output = module.derive_receiver(item, self.capacity)
            self.assertLessEqual(output["maximum_pair_distance_residual_m"], 1e-12)
            self.assertTrue(output["supported_180_degree_reversal_axis_set_equal"])

    def test_family_digest_is_receiver_order_invariant(self):
        outputs = [
            module.derive_receiver(self.front, self.capacity),
            module.derive_receiver(self.east, self.capacity),
        ]
        self.assertEqual(module.family_digest(outputs), module.family_digest(list(reversed(outputs))))

    def test_capacity_and_frame_drift_fail_closed(self):
        bad_contract = copy.deepcopy(self.contract)
        bad_contract["observed_capacity"]["closed_common_reservation_tangency_cap_m"] = 0.051
        with self.assertRaises(ValueError):
            module.verify_capacity_contract(bad_contract, self.panel)

        bad_surface = copy.deepcopy(self.front)
        bad_surface["world_outward_axis"] = [2.0, 0.0, 0.0]
        with self.assertRaises(ValueError):
            module.derive_receiver(bad_surface, self.capacity)


if __name__ == "__main__":
    unittest.main()
