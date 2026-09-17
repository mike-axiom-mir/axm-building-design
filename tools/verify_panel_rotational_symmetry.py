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
BUILD_RESULT_TOOL = ROOT / "tools/service_pavilion_build_result.py"
EMISSION_VARIANTS_TOOL = ROOT / "tools/service_pavilion_emission_variants.py"
EPS = 1e-9

EXPECTED_PANEL_SHA256 = "df59fa135abc89f8c85317db1d6b9ce3d03920efc91271de61bfb6289a24c253"
EXPECTED_PAVILION_SHA256 = "5f89ec4109d48f452f9e887ad5ca5449e1d0f6d6ee4b1896be6f25bc0a80736a"
EXPECTED_BASE_HEAD = "547bd21073332c8f856f07017cf9d279aa157bfa"
EXPECTED_CONTRACT_SCHEMA = "axm.building-panel-rotational-symmetry/v0.2"
EXPECTED_BUILD_RESULT_SCHEMA = "axm.building-build-result/v0.1"
EXPECTED_EMISSION_VARIANTS_SCHEMA = "axm.building-emission-variants/v0.1"
EXPECTED_EMISSION_SELECTION_POLICY = "EXPLICIT_VARIANT_ID_NO_FALLBACK"
EXPECTED_VARIANT_IDS = ("base-closed-outward-19", "header-segmented-23")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_build_result_tool():
    return load_module(BUILD_RESULT_TOOL, "service_pavilion_build_result")


def load_emission_variants_tool():
    return load_module(EMISSION_VARIANTS_TOOL, "service_pavilion_emission_variants_for_panel")


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


def validate_contract(contract):
    if contract.get("schema") != EXPECTED_CONTRACT_SCHEMA:
        raise ValueError("panel rotational-symmetry contract schema drift")
    authority = contract.get("source_authority", {})
    if authority.get("hard_surface_pr2_head") != EXPECTED_BASE_HEAD:
        raise ValueError("hard-surface source-authority head drift")
    if authority.get("build_result_schema") != EXPECTED_BUILD_RESULT_SCHEMA:
        raise ValueError("declared named build-result schema drift")
    if authority.get("emission_variants_schema") != EXPECTED_EMISSION_VARIANTS_SCHEMA:
        raise ValueError("declared emission-variants schema drift")
    if authority.get("emission_variant_selection_policy") != EXPECTED_EMISSION_SELECTION_POLICY:
        raise ValueError("declared emission-variant selection policy drift")
    state = contract.get("observed_mechanical_state", {})
    if state.get("tested_in_plane_rotations_degrees") != [0, 180]:
        raise ValueError("unsupported rotation evidence set")
    if tuple(state.get("tested_emission_variant_ids", ())) != EXPECTED_VARIANT_IDS:
        raise ValueError("tested emission-variant allowlist drift")
    if state.get("physical_orientation_key_present"):
        raise ValueError("unsupported physical orientation-key claim in exact current source")
    if not state.get("receiver_frame_metadata_orientation_remains_authoritative"):
        raise ValueError("receiver metadata orientation cannot be discarded")
    if contract.get("geometry_changed"):
        raise ValueError("rotational-symmetry evidence must not change source geometry")
    if contract.get("downstream_variant_adoption_changed"):
        raise ValueError("rotational-symmetry evidence cannot silently adopt a downstream emission variant")
    return authority, state


def validate_named_result(named, pavilion, panel):
    build_result = load_build_result_tool()
    build_result.require_fields(named, ("pavilion", "panel", "receiver_fits", "negative_controls", "topology_summary"))
    if named.get("schema") != EXPECTED_BUILD_RESULT_SCHEMA:
        raise ValueError("Building named build-result schema drift")
    if named["pavilion"] != pavilion:
        raise ValueError("named build-result pavilion source drift")
    if named["panel"] != panel:
        raise ValueError("named build-result panel source drift")
    topology = named["topology_summary"]
    if topology.get("revision") != "closed-outward-12-triangle-v1":
        raise ValueError("named build-result topology revision drift")
    if topology.get("object_count") != 19:
        raise ValueError("named build-result topology object-count drift")
    return named


def verify(panel=None, pavilion=None, contract=None, named_result=None, exact_head="LOCAL_UNBOUND"):
    panel = copy.deepcopy(panel if panel is not None else load(PANEL))
    pavilion = copy.deepcopy(pavilion if pavilion is not None else load(PAVILION))
    contract = copy.deepcopy(contract if contract is not None else load(CONTRACT))

    if panel["asset_id"] != contract["applies_to_asset_id"]:
        raise ValueError("contract asset identity mismatch")
    authority, state = validate_contract(contract)
    if authority["panel_source_sha256"] != EXPECTED_PANEL_SHA256:
        raise ValueError("declared panel source identity drift")
    if authority["pavilion_source_sha256"] != EXPECTED_PAVILION_SHA256:
        raise ValueError("declared pavilion source identity drift")
    if load(PANEL) == panel and sha256(PANEL) != EXPECTED_PANEL_SHA256:
        raise ValueError("panel source bytes drift")
    if load(PAVILION) == pavilion and sha256(PAVILION) != EXPECTED_PAVILION_SHA256:
        raise ValueError("pavilion source bytes drift")

    points = panel["mount_points_local_m"]
    rotated = rotate_mount_points_180(points)
    source_residual = best_pattern_residual(points, rotated)
    if source_residual > EPS:
        raise ValueError(f"source mount pattern is not 180-degree reversible: {source_residual}")

    size = panel["proof_geometry"]["size_local_xyz_m"]
    if len(size) != 3 or size[1] <= 0 or size[2] <= 0:
        raise ValueError("unsupported current proof geometry")
    proof_geometry_residual_m = 0.0

    build_result = load_build_result_tool()
    named = copy.deepcopy(named_result if named_result is not None else build_result.build_named())
    validate_named_result(named, pavilion, panel)
    fits = named["receiver_fits"]
    negatives = named["negative_controls"]
    if len(fits) != len(pavilion["interfaces"]):
        raise ValueError("inherited receiver count drift")
    if any(not value.startswith("REJECTED") for value in negatives.values()):
        raise ValueError("inherited negative control drift")

    receiver_results = []
    for interface in pavilion["interfaces"]:
        base = build_result.builder.fit_panel(interface, panel)
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
    if not state["reversibility_invariant_across_tested_emission_variants"]:
        raise ValueError("contract contradicts tested emission-variant invariance")

    emission_variants = load_emission_variants_tool()
    source_variant_contract = emission_variants.load_contract()
    if source_variant_contract.get("schema") != authority["emission_variants_schema"]:
        raise ValueError("source-owned emission-variant schema no longer matches panel contract")
    if source_variant_contract.get("selection_policy") != authority["emission_variant_selection_policy"]:
        raise ValueError("source-owned emission-variant selection policy no longer matches panel contract")

    expected_receiver_ids = [fit["interface_id"] for fit in fits]
    variant_results = []
    for variant_id in state["tested_emission_variant_ids"]:
        payload = emission_variants.build_variant(variant_id, exact_head)
        if payload["schema"] != EXPECTED_EMISSION_VARIANTS_SCHEMA:
            raise ValueError(f"{variant_id}: emission schema drift")
        if payload["selection_policy"] != EXPECTED_EMISSION_SELECTION_POLICY:
            raise ValueError(f"{variant_id}: emission selection policy drift")
        if payload["receiver_ids"] != expected_receiver_ids:
            raise ValueError(f"{variant_id}: receiver identity drift")
        if payload["receiver_mount_residual_max_m"] > EPS:
            raise ValueError(f"{variant_id}: receiver fit residual drift")
        per_receiver = []
        for row in receiver_results:
            if row["zero_degree_mount_pattern_residual_m"] > EPS:
                raise ValueError(f"{variant_id}/{row['interface_id']}: zero-degree residual drift")
            if row["one_eighty_degree_unordered_mount_pattern_residual_m"] > EPS:
                raise ValueError(f"{variant_id}/{row['interface_id']}: 180-degree residual drift")
            per_receiver.append({
                "interface_id": row["interface_id"],
                "zero_degree_mount_pattern_residual_m": row["zero_degree_mount_pattern_residual_m"],
                "one_eighty_degree_unordered_mount_pattern_residual_m": row["one_eighty_degree_unordered_mount_pattern_residual_m"],
            })
        variant_results.append({
            "variant_id": variant_id,
            "representation": payload["representation"],
            "downstream_adoption": payload["downstream_adoption"],
            "emitted_box_count": payload["emitted_box_count"],
            "vertex_count": payload["vertex_count"],
            "triangle_count": payload["triangle_count"],
            "positive_volume_intersection_count": payload["positive_volume_intersection_count"],
            "receiver_ids": payload["receiver_ids"],
            "receiver_mount_residual_max_m": payload["receiver_mount_residual_max_m"],
            "receiver_reversibility": per_receiver,
        })

    expected_counts = {
        "base-closed-outward-19": (19, 152, 228, 4, "CURRENT_DEFAULT_UNCHANGED"),
        "header-segmented-23": (23, 184, 276, 0, "OPT_IN_ONLY"),
    }
    for row in variant_results:
        expected = expected_counts[row["variant_id"]]
        observed = (
            row["emitted_box_count"],
            row["vertex_count"],
            row["triangle_count"],
            row["positive_volume_intersection_count"],
            row["downstream_adoption"],
        )
        if observed != expected:
            raise ValueError(f"{row['variant_id']}: exact emission signature drift {observed} != {expected}")

    return {
        "result": "PASS_BUILDING_PANEL_180_DEGREE_REVERSIBILITY_ACROSS_EXPLICIT_EMISSION_VARIANTS_CURRENT_SOURCE",
        "exact_hard_surface_head": exact_head,
        "scope": contract["scope"],
        "source_authority": authority,
        "panel_source_sha256": EXPECTED_PANEL_SHA256,
        "pavilion_source_sha256": EXPECTED_PAVILION_SHA256,
        "source_mount_pattern_180_residual_m": source_residual,
        "current_box_proof_geometry_180_residual_m": proof_geometry_residual_m,
        "named_build_result": {
            "schema": named["schema"],
            "legacy_output_count_observed": named["legacy_output_count_observed"],
            "opaque_trailing_extension_count": named["opaque_trailing_extension_count"],
            "topology_revision": named["topology_summary"]["revision"],
            "topology_object_count": named["topology_summary"]["object_count"],
            "receiver_ids": expected_receiver_ids,
        },
        "receiver_results": receiver_results,
        "emission_variant_results": variant_results,
        "physical_orientation_key_present": False,
        "receiver_frame_metadata_orientation_preserved": True,
        "geometry_changed": False,
        "downstream_variant_adoption_changed": False,
        "preservation_policy": contract["preservation_policy"],
        "inherited_hard_surface_prerequisite": "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF",
        "emission_variant_prerequisite": "PASS_EXPLICIT_SOURCE_OWNED_BUILDING_EMISSION_VARIANT_SELECTION",
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

    named = load_build_result_tool().build_named()
    named.pop("receiver_fits")
    try:
        verify(panel=panel, pavilion=pavilion, contract=contract, named_result=named)
        results["missing_named_receiver_dependency"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["missing_named_receiver_dependency"] = "REJECTED: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["source_authority"]["emission_variants_schema"] = "axm.building-emission-variants/DRIFT"
    try:
        verify(panel=panel, pavilion=pavilion, contract=bad_contract)
        results["emission_variant_schema_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["emission_variant_schema_drift"] = "REJECTED: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["observed_mechanical_state"]["tested_emission_variant_ids"] = [
        "base-closed-outward-19",
        "silent-best-effort",
    ]
    try:
        verify(panel=panel, pavilion=pavilion, contract=bad_contract)
        results["undeclared_emission_variant"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["undeclared_emission_variant"] = "REJECTED: " + str(exc)

    if any(not value.startswith("REJECTED") for value in results.values()):
        raise ValueError("negative control unexpectedly passed")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="evidence/utility-panel-rotational-symmetry-003")
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    receipt = verify(exact_head=args.exact_head)
    receipt["negative_controls"] = run_negative_controls()
    receipt["contract_sha256"] = sha256(CONTRACT)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "contract.json").write_text(CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
