import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_emission_variants", ROOT / "tools/service_pavilion_emission_variants.py"
)
variants = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(variants)


class ServicePavilionEmissionVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = variants.build_variant("base-closed-outward-19", "TEST_HEAD")
        cls.segmented = variants.build_variant("header-segmented-23", "TEST_HEAD")

    def test_default_variant_keeps_existing_named_build_contract(self):
        self.assertEqual(self.base["schema"], "axm.building-emission-variants/v0.1")
        self.assertEqual(self.base["default_variant_id"], "base-closed-outward-19")
        self.assertEqual(self.base["default_build_result_schema"], "axm.building-build-result/v0.1")
        self.assertEqual(self.base["default_build_result_topology_object_count"], 19)
        self.assertEqual(self.base["downstream_adoption"], "CURRENT_DEFAULT_UNCHANGED")
        self.assertEqual(self.base["emitted_box_count"], 19)
        self.assertEqual(self.base["vertex_count"], 152)
        self.assertEqual(self.base["triangle_count"], 228)

    def test_header_segmented_variant_is_explicit_and_interpenetration_free(self):
        self.assertEqual(self.segmented["variant_id"], "header-segmented-23")
        self.assertEqual(self.segmented["downstream_adoption"], "OPT_IN_ONLY")
        self.assertEqual(self.segmented["emitted_box_count"], 23)
        self.assertEqual(self.segmented["vertex_count"], 184)
        self.assertEqual(self.segmented["triangle_count"], 276)
        self.assertEqual(self.segmented["positive_volume_intersection_count"], 0)
        self.assertEqual(len(self.segmented["segment_map"]["front-header"]), 3)
        self.assertEqual(len(self.segmented["segment_map"]["rear-header"]), 3)

    def test_variants_preserve_union_bounds_and_receivers(self):
        self.assertEqual(self.base["bounds"], self.segmented["bounds"])
        self.assertEqual(self.base["receiver_ids"], self.segmented["receiver_ids"])
        self.assertEqual(
            self.base["receiver_mount_residual_max_m"],
            self.segmented["receiver_mount_residual_max_m"],
        )
        self.assertAlmostEqual(
            self.base["occupied_union_volume_m3"],
            self.segmented["occupied_union_volume_m3"],
            places=9,
        )
        self.assertEqual(self.base["positive_volume_intersection_count"], 4)

    def test_segmented_boxes_retain_logical_header_parent_identity(self):
        mapped = {
            box["id"]: box["source_component_id"]
            for box in self.segmented["boxes"]
            if "header::segment" in box["id"]
        }
        self.assertEqual(len(mapped), 6)
        self.assertTrue(all(parent in {"front-header", "rear-header"} for parent in mapped.values()))

    def test_unknown_variant_fails_closed_without_fallback(self):
        with self.assertRaises(ValueError):
            variants.build_variant("best-effort-or-default", "TEST_HEAD")

    def test_full_evidence_reports_only_bounded_selection_pass(self):
        receipt = variants.build_evidence("TEST_HEAD")
        self.assertEqual(
            receipt["result"],
            "PASS_EXPLICIT_SOURCE_OWNED_BUILDING_EMISSION_VARIANT_SELECTION",
        )
        self.assertTrue(receipt["default_build_result_unchanged"])
        self.assertEqual(receipt["comparison"]["emitted_box_delta"], 4)
        self.assertEqual(receipt["comparison"]["vertex_delta"], 32)
        self.assertEqual(receipt["comparison"]["triangle_delta"], 48)
        self.assertEqual(receipt["comparison"]["positive_volume_intersection_delta"], -4)
        self.assertEqual(receipt["comparison"]["occupied_union_volume_residual_m3"], 0.0)
        self.assertTrue(receipt["unknown_variant_control"].startswith("REJECTED:"))


if __name__ == "__main__":
    unittest.main()
