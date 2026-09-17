from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "build_pavilion_planar_role_hard_normal_stress_family.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("building_procedural_hard_normal_stress_test", TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Procedural stress-family builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlanarRoleHardNormalStressFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()
        cls.outputs, cls.evidence = cls.tool.build_evidence("unit-test-head")

    def test_three_materially_different_outputs_cover_exact_domains(self):
        self.assertEqual(
            self.evidence["result"],
            "PASS_BOUNDED_PLANAR_ROLE_HARD_NORMAL_STRESS_FAMILY",
        )
        self.assertEqual(self.evidence["cohort_count"], 3)
        self.assertEqual(self.evidence["distinct_cohort_digests"], 3)
        self.assertTrue(self.evidence["cohorts_cover_all_312_quotient_groups_exactly_once"])
        self.assertTrue(self.evidence["cohorts_cover_all_604_source_render_identities_exactly_once"])
        self.assertEqual(
            self.evidence["canonical_replay_under_reversed_input_order"],
            "PASS_EXACT_COHORT_DIGESTS_REPRODUCED",
        )

    def test_expected_cohort_sizes_are_retained(self):
        expected = {
            "single-normal-control": (1, 124, 124),
            "two-normal-boundary": (2, 84, 168),
            "three-normal-boundary": (3, 104, 312),
        }
        for cohort_id, (normal_count, group_count, source_count) in expected.items():
            output = self.outputs[cohort_id]
            self.assertEqual(output["distinct_source_normal_count"], normal_count)
            self.assertEqual(output["quotient_group_count"], group_count)
            self.assertEqual(output["source_render_identity_count"], source_count)

    def test_source_and_receiver_authority_are_not_promoted(self):
        self.assertFalse(self.evidence["source_mesh_changed"])
        self.assertFalse(self.evidence["source_equivalence_changed"])
        self.assertFalse(self.evidence["product_mesh_emitted"])
        self.assertFalse(self.evidence["normal_field_generated_or_repacked"])
        self.assertFalse(self.evidence["receiver_adoption"])
        self.assertFalse(self.evidence["uc_or_profession_fabric_changed"])
        self.assertEqual(
            self.evidence["decision"],
            "PASS_DIAGNOSTIC_STRESS_COHORT_FAMILY_ONLY__NO_RECEIVER_OR_SOURCE_ADOPTION",
        )

    def test_all_negative_controls_fail_closed(self):
        controls = self.evidence["negative_controls"]
        self.assertEqual(len(controls), 6)
        self.assertTrue(all(value.startswith("REJECTED:") for value in controls.values()))


if __name__ == "__main__":
    unittest.main()
