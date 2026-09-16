#!/usr/bin/env python3
import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "assets/utility_access_panel_001.json"
PAVILION = ROOT / "assets/service_pavilion_001.json"
CONTRACT = ROOT / "assets/utility_panel_rotational_symmetry_001.json"
BUILD_TOOL = ROOT / "tools/build_service_pavilion.py"
EPS = 1e-9

EXPECTED_PANEL_SHA256 = "df59fa135abc89f8c85317db1d6b9ce3d03920efc91271de61bfb6289a24c253"
EXPECTED_PAVILION_SHA256 = "852038d2288ead9a0ee271e09f1a7f7207ec8fd74668e0c52e739e9a224f87d7"
EXPECTED_BASE_HEAD = "4faa769b406bf3ad0ba9489a77141c27f122ce51"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_build_tool():
    spec = importlib.util.spec_from_file_location("build_service_pavilion", BUILD_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rotate_mount_points_180(points):
    return [[-float(p[0]), -float(p[1])] for p in points]


def best_pattern_residual(reference, candidate):
    if len(reference) != len(candidate):
        raise ValueError("mount point count mismatch")
    if not reference:
        return 0.0
    best = math.inf
    for perm in itertools.permutations(candidate):
        residual = max(math.dist(a, b) for a, b in zip(reference, perm))
        best = min(best, residual)
    return best


def verify(panel=None, pavilion=None, contract=None):
    panel = copy.deepcopy(panel if panel is not None else load(PANEL))
    pavilion = copy.deepcopy(pavilion if pavilion is not None else load(PAVILION))
    contract = copy.deepcopy(contract if contract is not None else load(CONTRACT))

    if panel["asset_id"] != contract["applies_to_asset_id"]:
        raise ValueError("contract asset identity mismatch")
    authority = contract["source_authority"]
    if authority["hard_surface_pr2_head"] != EXPECTED_BASE_HEAD:
        raise ValueError("hard-surface source-authority head drift")
    if authority["panel_source_sha256"] != EXPECTED_PANEL_SHA256:
        raise ValueError("declared panel source identity drift")
    if authority["pavilion_source_sha256"] != EXPECTED_PAVILION_SHA256:
        raise ValueError("declared pavilion source identity drift")
    if panel is not None and load(PANEL) == panel and sha256(PANEL) != EXPECTED_PANEL_SHA256:
        raise ValueError("panel source bytes drift")
    if pavilion is not None and load(PAVILION) == pavilion and sha256(PAVILION) != EXPECTED_PAVILION_SHA256:
        raise ValueError("pavilion source bytes drift")

    state = contract["observed_mechanical_state"]
    if state["tested_in_plane_rotations_degrees"] != [0, 180]:
        raise ValueError("unsupported rotation evidence set")
    if state["physical_orientation_key_present"]:
        raise ValueError("unsupported physical orientation-key claim in exact current source")
    if not state["receiver_frame_metadata_orientation_remains_authoritative"]:
        raise ValueError("receiver metadata orientation cannot be discarded")
    if contract["geometry_changed"]:
        raise ValueError("rotational-symmetry evidence must not change source geometry")

    points = panel["mount_points_local_m"]
    rotated = rotate_mount_points_180(points)
    source_residual = best_pattern_residual(points, rotated)
    if source_residual > EPS:
        raise ValueError(f"source mount pattern is not 180-degree reversible: {source_residual}")

    size = panel["proof_geometry"]["size_local_xyz_m"]
    if len(size) != 3 or size[1] <= 0 or size[2] <= 0:
        raise ValueError("unsupported current proof geometry")
    # A centered box is invariant under 180 degrees about local +X; only its
    # lateral/up signs swap. This does not claim future detailed geometry is.
    proof_geometry_residual_m = 0.0

    build = load_build_tool()
    # Re-execute the exact inherited Hard-Surface prerequisite before the new gate.
    _, _, fits, _, _, _, _, negatives = build.build()
    if len(fits) != len(pavilion["interfaces"]):
        raise ValueError("inherited receiver count drift")
    if any(not value.startswith("REJECTED") for value in negatives.values()):
        raise ValueError("inherited negative control drift")

    receiver_results = []
    for interface in pavilion["interfaces"]:
        base = build.fit_panel(interface, panel)
        rotated_residual = best_pattern_residual(interface["mount_points_local_m"], rotated)
        if rotated_residual > EPS:
            raise ValueError(f"{interface['id']}: rotated mount-pattern residual {rotated_residual}")
        receiver_results.append({
            "interface_id": interface["id"],
            "normal": interface["normal"],
            "lateral": interface["lateral"],
            "up": interface["up"],
            "zero_degree_mount_pattern_residual_m": base["mount_pattern_residual_m"],
            "one_eighty_degree_unordered_mount_pattern_residual_m": rotated_residual,
            "body_clearance_beyond_plate_m": base["body_clearance_beyond_plate_m"],
            "footprint_margin_m": base["footprint_margin_m"],
        })

    if not state["mount_pattern_is_180_degree_reversible"]:
        raise ValueError("contract contradicts exact reversible mount evidence")
    if not state["current_box_proof_geometry_is_180_degree_reversible"]:
        raise ValueError("contract contradicts exact current box proof geometry")

    return {
        "result": "PASS_BUILDING_PANEL_180_DEGREE_MECHANICAL_REVERSIBILITY_EVIDENCE",
        "scope": contract["scope"],
        "source_authority": authority,
        "panel_source_sha256": EXPECTED_PANEL_SHA256,
        "pavilion_source_sha256": EXPECTED_PAVILION_SHA256,
        "source_mount_pattern_180_residual_m": source_residual,
        "current_box_proof_geometry_180_residual_m": proof_geometry_residual_m,
        "receiver_results": receiver_results,
        "physical_orientation_key_present": False,
        "receiver_frame_metadata_orientation_preserved": True,
        "geometry_changed": False,
        "preservation_policy": contract["preservation_policy"],
        "inherited_hard_surface_prerequisite": "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF",
        "truth_boundary": contract["truth_boundary"],
    }


def run_negative_controls():
    panel = load(PANEL)
    pavilion = load(PAVILION)
    contract = load(CONTRACT)
    results = {}

    bad = copy.deepcopy(panel)
    bad["mount_points_local_m"][0][0] += 0.001
    try:
        verify(panel=bad, pavilion=pavilion, contract=contract)
        results["asymmetric_mount_drift_0p001m"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["asymmetric_mount_drift_0p001m"] = "REJECTED: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["observed_mechanical_state"]["physical_orientation_key_present"] = True
    try:
        verify(panel=panel, pavilion=pavilion, contract=bad_contract)
        results["unsupported_keyed_claim"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["unsupported_keyed_claim"] = "REJECTED: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["source_authority"]["panel_source_sha256"] = "0" * 64
    try:
        verify(panel=panel, pavilion=pavilion, contract=bad_contract)
        results["source_identity_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["source_identity_drift"] = "REJECTED: " + str(exc)

    if any(not value.startswith("REJECTED") for value in results.values()):
        raise ValueError("negative control unexpectedly passed")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="evidence/utility-panel-rotational-symmetry-001")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    receipt = verify()
    receipt["negative_controls"] = run_negative_controls()
    receipt["contract_sha256"] = sha256(CONTRACT)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "contract.json").write_text(CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
