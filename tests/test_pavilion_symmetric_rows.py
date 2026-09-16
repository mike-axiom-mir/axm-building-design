import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_pavilion_symmetric_rows", ROOT / "tools/build_pavilion_symmetric_rows.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


EXPECTED_ROW_DIGESTS = {
    "front-uprights": "af63a6d13fb8ad1b812780f6a381cd7c0c6d64179c343a0d40f31b6a6505e792",
    "rear-uprights": "00478d2147e7dabcd43a1a0df7581dab158cb579b50cd10638c883e3d276b9db",
    "rear-infill-row": "bfe8fe759c4ce7c64903817167cd72b836092248132894225442fb3d11b55a7a",
    "front-rear-header-pair": "02373d7571a526b08da0a1ef05c7dc2581aad42b0b210f85b78f2e311ce7299c",
    "west-east-header-pair": "15b90d8ae9c552ab4fca340d8897fab2457f3670dd664345e9448d902fb34734",
}


class PavilionSymmetricRowTests(unittest.TestCase):
    def test_generator_reproduces_five_materially_different_source_rows(self):
        summary = mod.build()
        self.assertEqual(summary["result"], "PASS_SOURCE_EXACT_SYMMETRIC_COMPONENT_ROW_GENERATOR")
        self.assertEqual(
            summary["source_rebind_result"],
            "PASS_EXACT_SOURCE_REBIND_TO_CLOSED_OUTWARD_BOX_SHELLS_002",
        )
        self.assertEqual(
            summary["build_result_rebind_result"],
            "PASS_PROCEDURAL_CONSUMER_USES_VERSIONED_NAMED_BUILD_RESULT",
        )
        self.assertEqual(summary["row_count"], 5)
        self.assertEqual(summary["generated_component_count"], 15)
        self.assertEqual(summary["source_component_count"], 17)
        self.assertEqual(summary["generated_source_coverage"], "15/17")
        self.assertEqual(summary["distinct_row_digests"], 5)
        self.assertGreaterEqual(summary["distinct_component_sizes"], 4)
        self.assertEqual(summary["distinct_station_counts"], [2, 3, 4])
        self.assertEqual(
            {row["row_id"]: row["row_digest"] for row in summary["rows"]},
            EXPECTED_ROW_DIGESTS,
        )
        self.assertEqual(
            summary["generated_subset_digest"],
            "659a5ecc192502b75e8c9f01fa1607b48b7ea8667b5447ee7da7cd5b76902b0e",
        )

    def test_exact_source_components_are_reproduced_without_rewrite(self):
        pavilion = mod.load(mod.PAVILION)
        profile = mod.load(mod.PROFILE)
        rows, generated_ids, manual_ids = mod.verify_profile(
            pavilion, profile, mod.sha256(mod.PAVILION)
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(generated_ids), 15)
        self.assertEqual(manual_ids, ["slab", "roof"])
        front = mod.generate_row(profile["rows"][0])
        self.assertEqual(
            [item["center"][0] for item in front], [-3.7, -1.25, 1.25, 3.7]
        )
        infill = mod.generate_row(profile["rows"][2])
        self.assertEqual([item["center"][0] for item in infill], [-2.45, 0.0, 2.45])
        front_rear_headers = mod.generate_row(profile["rows"][3])
        self.assertEqual(
            [item["center"][1] for item in front_rear_headers], [-0.9, 0.9]
        )
        self.assertEqual(
            [item["id"] for item in front_rear_headers], ["front-header", "rear-header"]
        )
        west_east_headers = mod.generate_row(profile["rows"][4])
        self.assertEqual(
            [item["center"][0] for item in west_east_headers], [-3.7, 3.7]
        )
        self.assertEqual(
            [item["id"] for item in west_east_headers], ["west-header", "east-header"]
        )

    def test_named_build_result_is_exact_and_future_trailing_extension_safe(self):
        profile = mod.load(mod.PROFILE)
        contract = mod.load_build_result_contract()
        legacy = contract.builder.build()
        named = contract.from_legacy_output(legacy)
        current = mod.project_named_build_result(contract, named, profile)
        extended = contract.from_legacy_output(
            tuple(legacy) + ({"future_extension": "opaque-to-procedural-v0.1"},)
        )
        future = mod.project_named_build_result(contract, extended, profile)
        self.assertEqual(contract.BUILD_RESULT_SCHEMA, "axm.building-build-result/v0.1")
        self.assertEqual(named["legacy_output_count_observed"], 9)
        self.assertEqual(extended["legacy_output_count_observed"], 10)
        self.assertEqual(extended["opaque_trailing_extension_count"], 1)
        self.assertEqual(current, future)
        self.assertEqual(set(current), set(mod.PROCEDURAL_BUILD_FIELDS))

    def test_source_identity_and_inherited_hard_surface_gate_remain_exact(self):
        summary = mod.build()
        self.assertEqual(summary["source_schema"], "axm.building-hard-surface/v0.2")
        self.assertEqual(
            summary["source_revision"],
            "service-pavilion-001/closed-outward-box-shells-002",
        )
        self.assertEqual(
            summary["source_hard_surface_head"],
            "57f66b1245812f0c3d402232a046b86c0b5c72d8",
        )
        self.assertEqual(
            summary["build_result_contract_hard_surface_head"],
            "595217be3cb9de25d3dc48b19447654533a20599",
        )
        self.assertEqual(
            summary["build_result_contract_schema"],
            "axm.building-build-result/v0.1",
        )
        self.assertEqual(summary["build_result_legacy_output_count_observed"], 9)
        self.assertEqual(
            summary["build_result_future_extension_control"],
            "PASS_EXISTING_PROCEDURAL_INPUTS_UNCHANGED",
        )
        self.assertEqual(
            summary["source_sha256"],
            "5f89ec4109d48f452f9e887ad5ca5449e1d0f6d6ee4b1896be6f25bc0a80736a",
        )
        inherited = summary["inherited_hard_surface_gate"]
        self.assertEqual(inherited["result"], "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF")
        self.assertEqual(
            inherited["topology_result"],
            "PASS_SOURCE_OWNED_CLOSED_OUTWARD_BOX_SHELLS_19_REAL_OUTPUTS",
        )
        self.assertEqual(inherited["box_shell_topology"], "closed-outward-12-triangle-v1")
        self.assertEqual(
            inherited["topology_summary"],
            {
                "object_count": 19,
                "vertex_count": 152,
                "triangle_count": 228,
                "boundary_edge_count": 0,
                "nonmanifold_edge_count": 0,
                "orientation_conflict_edge_count": 0,
                "degenerate_triangle_count": 0,
                "outward_triangle_count": 228,
                "inward_triangle_count": 0,
                "tangent_triangle_count": 0,
            },
        )
        self.assertTrue(inherited["historical_predecessor_rejection"].startswith("REJECTED"))
        self.assertTrue(inherited["single_triangle_flip_rejection"].startswith("REJECTED"))
        self.assertEqual(inherited["receiver_count"], 2)
        self.assertGreaterEqual(inherited["readable_path_gap_m"], 0.35)
        self.assertTrue(
            all(value.startswith("REJECTED") for value in inherited["negative_controls"].values())
        )

    def test_fail_closed_controls_hold(self):
        summary = mod.build()
        self.assertEqual(
            set(summary["negative_controls"]),
            {
                "unsupported_axis",
                "duplicate_component_id",
                "source_pattern_drift_0p001m",
                "header_pattern_drift_0p001m",
                "source_revision_drift",
                "source_topology_contract_drift",
                "source_identity_drift",
                "missing_named_build_dependency",
                "named_build_result_schema_drift",
            },
        )
        self.assertTrue(
            all(value.startswith("HOLD:") for value in summary["negative_controls"].values())
        )


if __name__ == "__main__":
    unittest.main()
