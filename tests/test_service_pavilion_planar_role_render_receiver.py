import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "build_service_pavilion_planar_role_render_receiver.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("planar_role_render_receiver_test_module", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PlanarRoleRenderReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_tool()
        cls.candidate, cls.result = cls.module.build_evidence("TEST_HEAD")

    def test_structural_candidate_passes(self):
        self.assertEqual(
            self.result["result"],
            "PASS_STRUCTURAL_PLANAR_ROLE_RECTANGLE_RENDER_RECEIVER_CANDIDATE",
        )
        self.assertEqual(
            self.result["representation_id"],
            "boundary-only-planar-role-rectangle-render-001",
        )
        self.assertTrue(self.result["candidate"]["atomic_coverage_complete"])
        self.assertEqual(self.result["candidate"]["atomic_overlap_count"], 0)
        self.assertTrue(self.result["candidate"]["cardinal_hard_normals_only"])
        self.assertEqual(self.result["candidate"]["role_count"], 5)

    def test_exact_source_boundary_facts_survive(self):
        self.assertEqual(self.result["semantic_source"]["variant_id"], "header-segmented-23")
        self.assertEqual(self.result["semantic_source"]["emitted_box_count"], 23)
        self.assertEqual(self.result["semantic_source"]["triangle_count"], 276)
        self.assertEqual(
            self.result["candidate"]["signed_volume_m3"],
            self.result["semantic_source"]["occupied_union_volume_m3"],
        )
        self.assertEqual(
            self.result["candidate"]["bounds"],
            self.result["semantic_source"]["bounds"],
        )
        self.assertAlmostEqual(
            self.result["candidate"]["surface_area_m2"],
            self.result["boundary_oracle"]["surface_area_m2"],
            delta=self.module.EPS,
        )

    def test_candidate_is_materially_smaller_than_compact_v2_triangle_domain(self):
        self.assertLess(self.result["candidate"]["triangle_count"], 2052)
        self.assertLess(
            self.result["comparison"]["map_style_position_normal_model_bytes_candidate"],
            self.result["comparison"]["map_style_position_normal_model_bytes_compact_v2"],
        )

    def test_rectangle_provenance_is_explicit(self):
        self.assertGreater(len(self.candidate["rectangles"]), 0)
        for rectangle in self.candidate["rectangles"]:
            self.assertTrue(rectangle["source_component_ids"])
            self.assertTrue(rectangle["box_ids"])
            self.assertGreater(rectangle["atomic_face_count"], 0)
            self.assertIn(rectangle["role"], self.module.EXPECTED_ROLES)

    def test_negative_controls_fail_closed(self):
        controls = self.result["negative_controls"]
        self.assertTrue(controls["drop_one_rectangle"].startswith("REJECTED:"))
        self.assertTrue(controls["role_drift"].startswith("REJECTED:"))
        self.assertTrue(controls["missing_contributor_provenance"].startswith("REJECTED:"))

    def test_policy_remains_non_default_and_render_only(self):
        policy = self.module.load_policy()
        self.assertEqual(
            policy["selection_policy"],
            "EXPLICIT_RECEIVING_REPRESENTATION_ID_REQUIRED__NO_DEFAULT_OR_IMPLICIT_FALLBACK",
        )
        self.assertEqual(
            policy["candidate"]["status"],
            "SOURCE_OWNED_DERIVED_RENDER_RECEIVING_OPTION_NOT_DEFAULT",
        )
        self.assertIn("collision_mesh", policy["candidate"]["forbidden_roles"])
        self.assertIn("structural_transport_mesh", policy["candidate"]["forbidden_roles"])


if __name__ == "__main__":
    unittest.main()
