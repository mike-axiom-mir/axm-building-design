import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "service_pavilion_build_result", ROOT / "tools/service_pavilion_build_result.py"
)
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


class ServicePavilionBuildResultTests(unittest.TestCase):
    def test_named_contract_matches_current_legacy_payload_exactly(self):
        legacy = contract.builder.build()
        named = contract.from_legacy_output(legacy)
        self.assertEqual(named["schema"], contract.BUILD_RESULT_SCHEMA)
        self.assertEqual(named["legacy_output_count_observed"], 9)
        self.assertEqual(named["opaque_trailing_extension_count"], 0)
        for index, field in enumerate(contract.CURRENT_REQUIRED_FIELDS):
            self.assertEqual(named[field], legacy[index])

    def test_future_trailing_extension_does_not_change_named_fields(self):
        legacy = contract.builder.build()
        baseline = contract.from_legacy_output(legacy)
        extended = contract.from_legacy_output(
            tuple(legacy) + ({"future_extension": "opaque-to-v0.1-consumers"},)
        )
        self.assertEqual(extended["legacy_output_count_observed"], 10)
        self.assertEqual(extended["opaque_trailing_extension_count"], 1)
        for field in contract.CURRENT_REQUIRED_FIELDS:
            self.assertEqual(extended[field], baseline[field])

    def test_missing_topology_summary_fails_closed(self):
        legacy = contract.builder.build()
        with self.assertRaises(ValueError):
            contract.from_legacy_output(tuple(legacy[:8]))

    def test_consumer_declares_named_dependencies(self):
        named = contract.build_named()
        contract.require_fields(named, ("receiver_fits", "topology_summary"))
        missing = dict(named)
        missing.pop("receiver_fits")
        with self.assertRaises(ValueError):
            contract.require_fields(missing, ("receiver_fits", "topology_summary"))

    def test_schema_drift_fails_closed(self):
        named = contract.build_named()
        drifted = dict(named)
        drifted["schema"] = "axm.building-build-result/v9.9"
        with self.assertRaises(ValueError):
            contract.require_fields(drifted, ("pavilion",))


if __name__ == "__main__":
    unittest.main()
