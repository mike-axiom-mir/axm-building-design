from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_building_materials_tool import run_request, validate_request


def current_head() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def request_for(output_directory: str) -> dict:
    return {
        "schema": "axm.building-materials-tool-request/v0.1",
        "source_root": str(ROOT),
        "source_head": current_head(),
        "material_profile": "lookdev/building_material_profile_001.json",
        "output_directory": output_directory,
    }


class BuildingMaterialsToolTests(unittest.TestCase):
    def test_exact_request_emits_structural_only_result(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = run_request(request_for(temporary_directory))
            self.assertEqual(result["result"], "PASS_BUILDING_MATERIALS_PACKET")
            self.assertEqual(result["implementation_head"], current_head())
            self.assertEqual(result["source_head"], current_head())
            self.assertEqual(result["evidence_scopes"], ["structural"])
            self.assertFalse(result["receipt"]["truth_boundary"]["art_direction_acceptance"])
            self.assertFalse(result["receipt"]["truth_boundary"]["runtime_acceptance"])
            written = json.loads((Path(temporary_directory) / "tool_result.json").read_text())
            self.assertEqual(written, result)

    def test_source_head_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = request_for(temporary_directory)
            request["source_head"] = "0" * 40
            with self.assertRaisesRegex(AssertionError, "source_head mismatch"):
                run_request(request)

    def test_unknown_request_field_fails_closed(self):
        request = request_for("unused")
        request["invent_authority"] = True
        with self.assertRaisesRegex(AssertionError, "request keys mismatch"):
            validate_request(request)

    def test_existing_outputs_require_explicit_replace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = request_for(temporary_directory)
            run_request(request)
            with self.assertRaisesRegex(FileExistsError, "refusing to replace"):
                run_request(request)


if __name__ == "__main__":
    unittest.main()
