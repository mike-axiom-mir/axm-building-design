import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "build_pavilion_owner_seam_component_family.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("owner_seam_component_family", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def record(pair, a, b, pa, pb):
    edge = sorted([a, b])
    endpoints = {str(a): list(pa), str(b): list(pb)}
    return {
        "owner_pair": sorted(pair),
        "source_edge": edge,
        "endpoints_by_source_id": {str(v): endpoints[str(v)] for v in edge},
        "length_m": math.dist(pa, pb),
    }


class OwnerSeamComponentFamilyTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.records = [
            record(["a", "b"], 1, 2, [0, 0, 0], [1, 0, 0]),
            record(["a", "b"], 2, 3, [1, 0, 0], [2, 0, 0]),
            record(["c", "d"], 10, 11, [0, 0, 0], [0, 2, 0]),
            record(["e", "f"], 20, 21, [0, 0, 0], [0, 0, 1]),
            record(["e", "f"], 21, 22, [0, 0, 1], [0, 0, 2]),
            record(["e", "f"], 20, 22, [0, 0, 0], [0, 0, 2]),
        ]

    def test_materially_different_component_outputs(self):
        outputs = self.tool.build_pair_outputs(self.records)
        by_pair = {tuple(item["owner_pair"]): item for item in outputs}
        self.assertEqual(by_pair[("a", "b")]["components"][0]["graph_class"], "OPEN_CHAIN")
        self.assertEqual(by_pair[("c", "d")]["components"][0]["graph_class"], "SINGLE_SEGMENT")
        self.assertEqual(by_pair[("e", "f")]["components"][0]["graph_class"], "CLOSED_CYCLE")
        self.assertEqual(len({item["pair_output_sha256"] for item in outputs}), 3)

    def test_order_is_canonical(self):
        self.assertEqual(self.tool.build_pair_outputs(self.records), self.tool.build_pair_outputs(list(reversed(self.records))))

    def test_duplicate_exact_identity_fails_closed(self):
        records = list(self.records) + [dict(self.records[0])]
        with self.assertRaisesRegex(ValueError, "duplicate source-owner seam identity"):
            self.tool.build_pair_outputs(records)

    def test_endpoint_provenance_must_match_source_edge(self):
        records = [dict(item) for item in self.records]
        records[0] = dict(records[0])
        records[0]["endpoints_by_source_id"] = {"1": [0, 0, 0], "99": [1, 0, 0]}
        with self.assertRaisesRegex(ValueError, "endpoint provenance"):
            self.tool.build_pair_outputs(records)


if __name__ == "__main__":
    unittest.main()
