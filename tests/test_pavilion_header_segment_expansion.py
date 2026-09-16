import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_pavilion_header_segment_expansion",
    ROOT / "tools/build_pavilion_header_segment_expansion.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class PavilionHeaderSegmentExpansionTests(unittest.TestCase):
    def test_two_source_owned_headers_expand_exactly(self):
        summary = mod.build()
        self.assertEqual(
            summary["result"], "PASS_SOURCE_EXACT_HEADER_SEGMENT_EXPANSION_FAMILY"
        )
        self.assertEqual(summary["logical_row_count_preserved"], 5)
        self.assertEqual(summary["logical_generated_component_count_preserved"], 15)
        self.assertEqual(summary["logical_distinct_row_digests_preserved"], 5)
        self.assertEqual(
            summary["logical_generated_subset_digest_preserved"],
            "659a5ecc192502b75e8c9f01fa1607b48b7ea8667b5447ee7da7cd5b76902b0e",
        )
        self.assertEqual(summary["expanded_logical_header_count"], 2)
        self.assertEqual(summary["expanded_segment_count"], 6)
        self.assertEqual(summary["expanded_emitted_generated_component_count"], 19)
        self.assertEqual(summary["expanded_emitted_pavilion_coverage"], "19/21")
        self.assertEqual(summary["distinct_expansion_digests"], 2)
        self.assertEqual(summary["distinct_total_output_digests"], 7)

    def test_front_and_rear_inherit_logical_yz_and_share_one_segment_pattern(self):
        summary = mod.build()
        rows = {row["logical_component_id"]: row for row in summary["expansion_rows"]}
        self.assertEqual(set(rows), {"front-header", "rear-header"})
        front = rows["front-header"]["segments"]
        rear = rows["rear-header"]["segments"]
        self.assertEqual([item["center"][0] for item in front], [-2.475, 0.0, 2.475])
        self.assertEqual([item["size"][0] for item in front], [2.25, 2.30, 2.25])
        self.assertEqual([item["center"][0] for item in rear], [-2.475, 0.0, 2.475])
        self.assertEqual([item["size"][0] for item in rear], [2.25, 2.30, 2.25])
        self.assertTrue(all(item["center"][1] == -0.9 for item in front))
        self.assertTrue(all(item["center"][1] == 0.9 for item in rear))
        self.assertTrue(all(item["center"][2] == 3.02 for item in front + rear))
        self.assertTrue(all(item["size"][1:] == [0.18, 0.18] for item in front + rear))

    def test_successor_identity_is_exact(self):
        summary = mod.build()
        self.assertEqual(
            summary["source_hard_surface_head"],
            "34124101e616c423c5a3ed5e122ddf09b98a1650",
        )
        self.assertEqual(
            summary["successor_contract_schema"],
            "axm.building-header-segmentation/v0.1",
        )
        self.assertEqual(
            summary["successor_revision"],
            "service-pavilion-001/interpenetration-free-header-segmentation-003",
        )
        self.assertEqual(
            summary["successor_contract_sha256"],
            "84075473c7320bde6d40d7c7aa6501f88b1e172d05dd5877ab4dc20e1b7a084f",
        )

    def test_fail_closed_controls_hold(self):
        summary = mod.build()
        self.assertEqual(
            set(summary["negative_controls"]),
            {
                "unsupported_segment_axis",
                "duplicate_segment_suffix",
                "segment_count_mismatch",
                "successor_schema_drift",
                "successor_revision_drift",
                "source_segment_drift_0p001m",
                "successor_identity_drift",
            },
        )
        self.assertTrue(
            all(value.startswith("HOLD:") for value in summary["negative_controls"].values())
        )


if __name__ == "__main__":
    unittest.main()
