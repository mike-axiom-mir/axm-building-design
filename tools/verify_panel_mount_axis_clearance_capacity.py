#!/usr/bin/env python3
import argparse
import copy
import hashlib
import itertools
import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "assets/utility_access_panel_001.json"
ROTATIONAL_CONTRACT = ROOT / "assets/utility_panel_rotational_symmetry_001.json"
CONTRACT = ROOT / "assets/utility_panel_mount_axis_clearance_capacity_001.json"
EPS = 1e-9

EXPECTED_PANEL_SHA256 = "df59fa135abc89f8c85317db1d6b9ce3d03920efc91271de61bfb6289a24c253"
EXPECTED_ROTATIONAL_CONTRACT_BLOB = "35fb9d76fad8fd1f8157c3e15a1a3d7c2653bfeb"
EXPECTED_DONOR_HEAD = "7f518b55c6bab083a3c8bbe368bfe77823f31547"
EXPECTED_CONTRACT_SCHEMA = "axm.building-panel-mount-axis-clearance-capacity/v0.1"
EXPECTED_ASSET_ID = "utility-access-panel-001"
EXPECTED_ORIENTATION = (
    "panel local +X maps to receiver outward normal; local +Y maps receiver lateral; "
    "local +Z maps receiver up"
)
EXPECTED_STRICT_CONDITION = (
    "0 <= radius_m < closed_common_reservation_tangency_cap_m"
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path):
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def clean_zero(value):
    return 0.0 if abs(value) <= EPS else value


def planar_capacity(panel):
    footprint = panel.get("interface_footprint_m")
    points = panel.get("mount_points_local_m")
    if not isinstance(footprint, list) or len(footprint) != 2:
        raise ValueError("PANEL_FOOTPRINT_SCHEMA_DRIFT")
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("MOUNT_AXIS_SET_SCHEMA_DRIFT")

    span_y, span_z = map(float, footprint)
    if span_y <= 0.0 or span_z <= 0.0:
        raise ValueError("NONPOSITIVE_PANEL_FOOTPRINT")
    half_y, half_z = span_y / 2.0, span_z / 2.0

    normalized_points = []
    per_axis = []
    for index, point in enumerate(points):
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"MOUNT_AXIS_{index}_SCHEMA_DRIFT")
        y, z = map(float, point)
        normalized_points.append([y, z])
        margin_y = half_y - abs(y)
        margin_z = half_z - abs(z)
        min_margin = min(margin_y, margin_z)
        if min_margin < -EPS:
            raise ValueError(f"MOUNT_AXIS_{index}_OUTSIDE_FOOTPRINT")
        per_axis.append(
            {
                "index": index,
                "local_yz_m": [y, z],
                "margin_to_y_edge_m": clean_zero(margin_y),
                "margin_to_z_edge_m": clean_zero(margin_z),
                "minimum_axis_to_footprint_boundary_m": clean_zero(min_margin),
            }
        )

    pair_rows = []
    for left, right in itertools.combinations(range(len(normalized_points)), 2):
        distance = math.dist(normalized_points[left], normalized_points[right])
        pair_rows.append(
            {
                "axis_indices": [left, right],
                "center_distance_m": distance,
                "equal_circle_pair_tangency_radius_m": distance / 2.0,
            }
        )

    min_edge = min(row["minimum_axis_to_footprint_boundary_m"] for row in per_axis)
    min_pair = min(row["center_distance_m"] for row in pair_rows)
    footprint_cap = min_edge
    pair_cap = min_pair / 2.0
    closed_cap = min(footprint_cap, pair_cap)
    if abs(footprint_cap - pair_cap) <= EPS:
        limiting = "FOOTPRINT_EDGE_AND_AXIS_PAIR"
    elif footprint_cap < pair_cap:
        limiting = "FOOTPRINT_EDGE"
    else:
        limiting = "AXIS_PAIR"

    return {
        "footprint_local_yz_span_m": [span_y, span_z],
        "footprint_half_extents_local_yz_m": [half_y, half_z],
        "mount_axis_count": len(normalized_points),
        "mount_axes": per_axis,
        "axis_pairs": pair_rows,
        "minimum_axis_to_footprint_boundary_m": min_edge,
        "minimum_axis_pair_distance_m": min_pair,
        "footprint_tangency_cap_m": footprint_cap,
        "pairwise_tangency_cap_m": pair_cap,
        "closed_common_reservation_tangency_cap_m": closed_cap,
        "limiting_constraint": limiting,
    }


def evaluate_common_radius(capacity, radius_m):
    radius_m = float(radius_m)
    if radius_m < 0.0:
        raise ValueError("NEGATIVE_RADIUS")
    edge_residual = capacity["minimum_axis_to_footprint_boundary_m"] - radius_m
    pair_gap = capacity["minimum_axis_pair_distance_m"] - (2.0 * radius_m)
    return {
        "radius_m": radius_m,
        "minimum_footprint_edge_residual_m": clean_zero(edge_residual),
        "minimum_pair_gap_m": clean_zero(pair_gap),
        "within_closed_footprint": edge_residual >= -EPS,
        "strictly_inside_footprint": edge_residual > EPS,
        "pairwise_nonoverlap": pair_gap >= -EPS,
    }


def rotate_points_180(panel):
    rotated = copy.deepcopy(panel)
    rotated["mount_points_local_m"] = [
        [-float(point[0]), -float(point[1])]
        for point in panel["mount_points_local_m"]
    ]
    return rotated


def validate_contract(contract):
    if contract.get("schema") != EXPECTED_CONTRACT_SCHEMA:
        raise ValueError("CLEARANCE_CAPACITY_CONTRACT_SCHEMA_DRIFT")
    if contract.get("applies_to_asset_id") != EXPECTED_ASSET_ID:
        raise ValueError("CLEARANCE_CAPACITY_ASSET_ID_DRIFT")

    authority = contract.get("source_authority", {})
    if authority.get("hard_surface_pr5_donor_head") != EXPECTED_DONOR_HEAD:
        raise ValueError("HARD_SURFACE_DONOR_HEAD_DRIFT")
    if authority.get("panel_source_sha256") != EXPECTED_PANEL_SHA256:
        raise ValueError("DECLARED_PANEL_SOURCE_IDENTITY_DRIFT")
    if authority.get("rotational_symmetry_contract_git_blob") != EXPECTED_ROTATIONAL_CONTRACT_BLOB:
        raise ValueError("DECLARED_ROTATIONAL_CONTRACT_IDENTITY_DRIFT")

    if contract.get("reservation_radius_selected") is not False:
        raise ValueError("CLEARANCE_RADIUS_SELECTION_NOT_SOURCE_OWNED")
    if contract.get("fastener_geometry_established") is not False:
        raise ValueError("FASTENER_GEOMETRY_AUTHORITY_EXPANSION")
    if contract.get("tooling_envelope_established") is not False:
        raise ValueError("TOOLING_ENVELOPE_AUTHORITY_EXPANSION")
    if contract.get("retention_method_established") is not False:
        raise ValueError("RETENTION_METHOD_AUTHORITY_EXPANSION")
    if contract.get("geometry_changed") is not False:
        raise ValueError("CLEARANCE_CAPACITY_EVIDENCE_MUST_NOT_CHANGE_GEOMETRY")
    if contract.get("source_role_adoption_changed") is not False:
        raise ValueError("CLEARANCE_CAPACITY_EVIDENCE_MUST_NOT_CHANGE_SOURCE_ROLE")

    observed = contract.get("observed_capacity", {})
    if observed.get("mount_axis_count") != 4:
        raise ValueError("DECLARED_MOUNT_AXIS_COUNT_DRIFT")
    if abs(float(observed.get("minimum_axis_to_footprint_boundary_m", -1.0)) - 0.05) > EPS:
        raise ValueError("DECLARED_EDGE_CAPACITY_DRIFT")
    if abs(float(observed.get("minimum_axis_pair_distance_m", -1.0)) - 1.0) > EPS:
        raise ValueError("DECLARED_AXIS_PAIR_DISTANCE_DRIFT")
    if abs(float(observed.get("closed_common_reservation_tangency_cap_m", -1.0)) - 0.05) > EPS:
        raise ValueError("DECLARED_CAPACITY_DRIFT")
    if observed.get("limiting_constraint") != "FOOTPRINT_EDGE":
        raise ValueError("DECLARED_LIMITING_CONSTRAINT_DRIFT")
    if observed.get("strict_no_encroachment_common_radius_condition") != EXPECTED_STRICT_CONDITION:
        raise ValueError("STRICT_INTERIOR_POLICY_DRIFT")
    if observed.get("capacity_invariant_under_supported_180_degree_reversal") is not True:
        raise ValueError("ROTATIONAL_CAPACITY_INVARIANCE_CLAIM_DRIFT")
    return authority, observed


def _verify_core(panel, contract, exact_head):
    exact_panel = load(PANEL)
    if panel != exact_panel:
        raise ValueError("PANEL_SOURCE_CONTENT_DRIFT")
    if panel.get("asset_id") != EXPECTED_ASSET_ID:
        raise ValueError("PANEL_ASSET_ID_DRIFT")
    if panel.get("orientation_contract") != EXPECTED_ORIENTATION:
        raise ValueError("PANEL_ORIENTATION_CONTRACT_DRIFT")
    if sha256(PANEL) != EXPECTED_PANEL_SHA256:
        raise ValueError("PANEL_SOURCE_BYTES_DRIFT")
    if git_blob_sha1(ROTATIONAL_CONTRACT) != EXPECTED_ROTATIONAL_CONTRACT_BLOB:
        raise ValueError("ROTATIONAL_CONTRACT_BYTES_DRIFT")

    authority, observed = validate_contract(contract)
    capacity = planar_capacity(panel)

    if capacity["mount_axis_count"] != observed["mount_axis_count"]:
        raise ValueError("OBSERVED_MOUNT_AXIS_COUNT_MISMATCH")
    if abs(capacity["minimum_axis_to_footprint_boundary_m"] - float(observed["minimum_axis_to_footprint_boundary_m"])) > EPS:
        raise ValueError("OBSERVED_EDGE_CAPACITY_MISMATCH")
    if abs(capacity["minimum_axis_pair_distance_m"] - float(observed["minimum_axis_pair_distance_m"])) > EPS:
        raise ValueError("OBSERVED_AXIS_PAIR_DISTANCE_MISMATCH")
    if abs(capacity["closed_common_reservation_tangency_cap_m"] - float(observed["closed_common_reservation_tangency_cap_m"])) > EPS:
        raise ValueError("OBSERVED_CLOSED_CAPACITY_MISMATCH")
    if capacity["limiting_constraint"] != observed["limiting_constraint"]:
        raise ValueError("OBSERVED_LIMITING_CONSTRAINT_MISMATCH")

    rotated_capacity = planar_capacity(rotate_points_180(panel))
    rotation_residual = abs(
        capacity["closed_common_reservation_tangency_cap_m"]
        - rotated_capacity["closed_common_reservation_tangency_cap_m"]
    )
    if rotation_residual > EPS:
        raise ValueError("CLEARANCE_CAPACITY_NOT_180_DEGREE_INVARIANT")

    cap = capacity["closed_common_reservation_tangency_cap_m"]
    below = evaluate_common_radius(capacity, cap - 0.001)
    tangent = evaluate_common_radius(capacity, cap)
    above = evaluate_common_radius(capacity, cap + 0.001)

    if not below["strictly_inside_footprint"] or not below["pairwise_nonoverlap"]:
        raise ValueError("BELOW_CAP_PROBE_SHOULD_HAVE_POSITIVE_CLEARANCE")
    if not tangent["within_closed_footprint"] or tangent["strictly_inside_footprint"]:
        raise ValueError("TANGENCY_PROBE_CLASSIFICATION_DRIFT")
    if not tangent["pairwise_nonoverlap"]:
        raise ValueError("TANGENCY_PROBE_PAIRWISE_OVERLAP")
    if above["within_closed_footprint"]:
        raise ValueError("ABOVE_CAP_PROBE_SHOULD_BREAK_FOOTPRINT")

    return {
        "schema": "axm.building-panel-mount-axis-clearance-capacity-evidence/v0.1",
        "result": "PASS_SOURCE_OWNED_BUILDING_PANEL_MOUNT_AXIS_CLEARANCE_CAPACITY",
        "exact_hard_surface_head": exact_head,
        "source_authority": {
            **authority,
            "panel_source_git_blob": git_blob_sha1(PANEL),
            "rotational_symmetry_contract_git_blob_observed": git_blob_sha1(ROTATIONAL_CONTRACT),
        },
        "source_coordinate_interpretation": contract["source_coordinate_interpretation"],
        "capacity": capacity,
        "supported_180_degree_reversal": {
            "closed_cap_residual_m": clean_zero(rotation_residual),
            "rotated_closed_common_reservation_tangency_cap_m": rotated_capacity[
                "closed_common_reservation_tangency_cap_m"
            ],
        },
        "boundary_probes": {
            "one_mm_below_closed_cap": below,
            "at_closed_tangency_cap": tangent,
            "one_mm_above_closed_cap": above,
        },
        "reservation_radius_selected": False,
        "fastener_geometry_established": False,
        "tooling_envelope_established": False,
        "retention_method_established": False,
        "geometry_changed": False,
        "source_role_adoption_changed": False,
        "truth_boundary": contract["truth_boundary"],
    }


def expect_rejected(label, fn):
    try:
        fn()
    except ValueError as exc:
        return f"REJECTED:{label}:{exc}"
    raise AssertionError(f"negative control unexpectedly passed: {label}")


def build_negative_controls(panel, contract, exact_head):
    controls = {}

    mutated_panel = copy.deepcopy(panel)
    mutated_panel["mount_points_local_m"][0][0] -= 0.001
    controls["one_mm_mount_axis_source_drift"] = expect_rejected(
        "ONE_MM_MOUNT_AXIS_SOURCE_DRIFT",
        lambda: _verify_core(mutated_panel, contract, exact_head),
    )

    selected = copy.deepcopy(contract)
    selected["reservation_radius_selected"] = True
    controls["unsupported_radius_selection"] = expect_rejected(
        "UNSUPPORTED_RADIUS_SELECTION",
        lambda: _verify_core(panel, selected, exact_head),
    )

    fastener = copy.deepcopy(contract)
    fastener["fastener_geometry_established"] = True
    controls["unsupported_fastener_geometry_claim"] = expect_rejected(
        "UNSUPPORTED_FASTENER_GEOMETRY_CLAIM",
        lambda: _verify_core(panel, fastener, exact_head),
    )

    cap_drift = copy.deepcopy(contract)
    cap_drift["observed_capacity"]["closed_common_reservation_tangency_cap_m"] = 0.049
    controls["declared_capacity_drift"] = expect_rejected(
        "DECLARED_CAPACITY_DRIFT",
        lambda: _verify_core(panel, cap_drift, exact_head),
    )

    weak_policy = copy.deepcopy(contract)
    weak_policy["observed_capacity"]["strict_no_encroachment_common_radius_condition"] = (
        "0 <= radius_m <= closed_common_reservation_tangency_cap_m"
    )
    controls["edge_tangency_silently_relabelled_strict"] = expect_rejected(
        "EDGE_TANGENCY_SILENTLY_RELABELLED_STRICT",
        lambda: _verify_core(panel, weak_policy, exact_head),
    )

    return controls


def verify(panel=None, contract=None, exact_head="LOCAL_UNBOUND"):
    panel = copy.deepcopy(panel if panel is not None else load(PANEL))
    contract = copy.deepcopy(contract if contract is not None else load(CONTRACT))
    receipt = _verify_core(panel, contract, exact_head)
    receipt["negative_controls"] = build_negative_controls(panel, contract, exact_head)
    return receipt


def write_evidence(output_dir, receipt):
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "exact-head.txt").write_text(
        receipt["exact_hard_surface_head"] + "\n", encoding="utf-8"
    )
    shutil.copy2(PANEL, output_dir / PANEL.name)
    shutil.copy2(CONTRACT, output_dir / CONTRACT.name)
    shutil.copy2(ROTATIONAL_CONTRACT, output_dir / ROTATIONAL_CONTRACT.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    receipt = verify(exact_head=args.exact_head)
    if args.output_dir is not None:
        write_evidence(args.output_dir, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
