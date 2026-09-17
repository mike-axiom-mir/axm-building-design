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
CURRENT_POLICY = ROOT / "assets/service_pavilion_001_current_emission_policy.json"
BUILD_RESULT_TOOL = ROOT / "tools/service_pavilion_build_result.py"
EMISSION_VARIANTS_TOOL = ROOT / "tools/service_pavilion_emission_variants.py"
CURRENT_POLICY_TOOL = ROOT / "tools/service_pavilion_current_emission_policy.py"
EPS = 1e-9

EXPECTED_PANEL_SHA256 = "df59fa135abc89f8c85317db1d6b9ce3d03920efc91271de61bfb6289a24c253"
EXPECTED_PAVILION_SHA256 = "5f89ec4109d48f452f9e887ad5ca5449e1d0f6d6ee4b1896be6f25bc0a80736a"
EXPECTED_CURRENT_POLICY_SHA256 = "c26f25c789404919bdb8e40f35d517c444e35f0a7aaf9358ad399296a7afe47a"
EXPECTED_SOURCE_HEAD = "a976af429b0ea90e0f0cc72d4a8bd4eb8fef22d3"
EXPECTED_CONTRACT_SCHEMA = "axm.building-panel-rotational-symmetry/v0.3"
EXPECTED_BUILD_RESULT_SCHEMA = "axm.building-build-result/v0.1"
EXPECTED_EMISSION_VARIANTS_SCHEMA = "axm.building-emission-variants/v0.1"
EXPECTED_EMISSION_SELECTION_POLICY = "EXPLICIT_VARIANT_ID_NO_FALLBACK"
EXPECTED_CURRENT_POLICY_SCHEMA = "axm.building-current-emission-policy/v0.1"
EXPECTED_CURRENT_SELECTION_POLICY = (
    "CURRENT_SOURCE_IS_NAMED__CONSUMER_REBIND_REQUIRED__NO_SILENT_DEFAULT_REWRITE"
)


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
    return load_module(BUILD_RESULT_TOOL, "service_pavilion_build_result_for_panel")


def load_emission_variants_tool():
    return load_module(
        EMISSION_VARIANTS_TOOL,
        "service_pavilion_emission_variants_for_panel_current_roles",
    )


def load_current_policy_tool():
    return load_module(
        CURRENT_POLICY_TOOL,
        "service_pavilion_current_emission_policy_for_panel",
    )


def rotate_mount_points_180(points):
    return [[-float(point[0]), -float(point[1])] for point in points]


def best_pattern_residual(reference, candidate):
    if len(reference) != len(candidate):
        raise ValueError("mount point count mismatch")
    if not reference:
        return 0.0
    best = math.inf
    for permutation in itertools.permutations(candidate):
        best = min(
            best,
            max(math.dist(a, b) for a, b in zip(reference, permutation)),
        )
    return best


def expected_roles(source_policy):
    return [
        {
            "role": "CURRENT_SOURCE",
            "variant_id": source_policy["current_source_variant_id"],
        },
        {
            "role": "LEGACY_COMPATIBILITY",
            "variant_id": source_policy["legacy_compatibility_variant_id"],
        },
    ]


def validate_contract(contract, source_policy):
    if contract.get("schema") != EXPECTED_CONTRACT_SCHEMA:
        raise ValueError("panel rotational-symmetry contract schema drift")

    authority = contract.get("source_authority", {})
    if authority.get("hard_surface_pr2_head") != EXPECTED_SOURCE_HEAD:
        raise ValueError("hard-surface source-authority head drift")
    if authority.get("pavilion_source_sha256") != EXPECTED_PAVILION_SHA256:
        raise ValueError("declared pavilion source identity drift")
    if authority.get("panel_source_sha256") != EXPECTED_PANEL_SHA256:
        raise ValueError("declared panel source identity drift")
    if authority.get("build_result_schema") != EXPECTED_BUILD_RESULT_SCHEMA:
        raise ValueError("declared named build-result schema drift")
    if authority.get("emission_variants_schema") != EXPECTED_EMISSION_VARIANTS_SCHEMA:
        raise ValueError("declared emission-variants schema drift")
    if (
        authority.get("emission_variant_selection_policy")
        != EXPECTED_EMISSION_SELECTION_POLICY
    ):
        raise ValueError("declared emission-variant selection policy drift")
    if authority.get("current_emission_policy_schema") != EXPECTED_CURRENT_POLICY_SCHEMA:
        raise ValueError("declared current-emission policy schema drift")
    if (
        authority.get("current_emission_policy_sha256")
        != EXPECTED_CURRENT_POLICY_SHA256
    ):
        raise ValueError("declared current-emission policy identity drift")
    if (
        authority.get("current_emission_selection_policy")
        != EXPECTED_CURRENT_SELECTION_POLICY
    ):
        raise ValueError("declared current-emission selection policy drift")

    state = contract.get("observed_mechanical_state", {})
    if state.get("tested_in_plane_rotations_degrees") != [0, 180]:
        raise ValueError("unsupported rotation evidence set")
    if state.get("tested_representation_roles") != expected_roles(source_policy):
        raise ValueError("tested current/legacy representation roles drift")
    if state.get("physical_orientation_key_present"):
        raise ValueError("unsupported physical orientation-key claim in exact current source")
    if not state.get("receiver_frame_metadata_orientation_remains_authoritative"):
        raise ValueError("receiver metadata orientation cannot be discarded")
    if not state.get("mount_pattern_is_180_degree_reversible"):
        raise ValueError("contract contradicts exact reversible mount evidence")
    if not state.get("box_proof_geometry_is_180_degree_reversible"):
        raise ValueError("contract contradicts exact reversible box proof geometry")
    if not state.get("reversibility_invariant_across_tested_representation_roles"):
        raise ValueError("contract contradicts representation-role invariance")
    if contract.get("geometry_changed"):
        raise ValueError("rotational-symmetry evidence must not change source geometry")
    if contract.get("source_role_adoption_changed"):
        raise ValueError("rotational-symmetry evidence cannot rewrite source-role policy")
    return authority, state


def validate_named_result(named, pavilion, panel):
    build_result = load_build_result_tool()
    build_result.require_fields(
        named,
        ("pavilion", "panel", "receiver_fits", "negative_controls", "topology_summary"),
    )
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


def validate_source_policy(source_policy, authority):
    current_policy_tool = load_current_policy_tool()
    current_policy_tool.validate_policy(source_policy)

    if source_policy["schema"] != authority["current_emission_policy_schema"]:
        raise ValueError("source current-emission policy schema no longer matches panel contract")
    if source_policy["selection_policy"] != authority["current_emission_selection_policy"]:
        raise ValueError(
            "source current-emission selection policy no longer matches panel contract"
        )
    if sha256(CURRENT_POLICY) != authority["current_emission_policy_sha256"]:
        raise ValueError("source current-emission policy bytes drift")
    return source_policy


def receiver_reversibility(build_result, pavilion, panel):
    points = panel["mount_points_local_m"]
    rotated = rotate_mount_points_180(points)
    source_residual = best_pattern_residual(points, rotated)
    if source_residual > EPS:
        raise ValueError(
            f"source mount pattern is not 180-degree reversible: {source_residual}"
        )

    size = panel["proof_geometry"]["size_local_xyz_m"]
    if len(size) != 3 or size[1] <= 0 or size[2] <= 0:
        raise ValueError("unsupported current proof geometry")

    rows = []
    for interface in pavilion["interfaces"]:
        base = build_result.builder.fit_panel(interface, panel)
        rotated_residual = best_pattern_residual(
            interface["mount_points_local_m"],
            rotated,
        )
        if rotated_residual > EPS:
            raise ValueError(
                f"{interface['id']}: rotated mount-pattern residual {rotated_residual}"
            )
        rows.append(
            {
                "interface_id": interface["id"],
                "normal": interface["normal"],
                "lateral": interface["lateral"],
                "up": interface["up"],
                "zero_degree_mount_pattern_residual_m": base[
                    "mount_pattern_residual_m"
                ],
                "one_eighty_degree_unordered_mount_pattern_residual_m": (
                    rotated_residual
                ),
                "body_clearance_beyond_plate_m": base[
                    "body_clearance_beyond_plate_m"
                ],
                "footprint_margin_m": base["footprint_margin_m"],
            }
        )
    return source_residual, rows


def verify(
    panel=None,
    pavilion=None,
    contract=None,
    named_result=None,
    current_policy=None,
    exact_head="LOCAL_UNBOUND",
):
    panel = copy.deepcopy(panel if panel is not None else load(PANEL))
    pavilion = copy.deepcopy(pavilion if pavilion is not None else load(PAVILION))
    contract = copy.deepcopy(contract if contract is not None else load(CONTRACT))
    source_policy = copy.deepcopy(
        current_policy if current_policy is not None else load(CURRENT_POLICY)
    )

    if panel["asset_id"] != contract["applies_to_asset_id"]:
        raise ValueError("contract asset identity mismatch")
    # Source-owner policy must be valid before any consumer role interpretation.
    load_current_policy_tool().validate_policy(source_policy)
    authority, state = validate_contract(contract, source_policy)
    validate_source_policy(source_policy, authority)

    if load(PANEL) == panel and sha256(PANEL) != EXPECTED_PANEL_SHA256:
        raise ValueError("panel source bytes drift")
    if load(PAVILION) == pavilion and sha256(PAVILION) != EXPECTED_PAVILION_SHA256:
        raise ValueError("pavilion source bytes drift")

    build_result = load_build_result_tool()
    named = copy.deepcopy(
        named_result if named_result is not None else build_result.build_named()
    )
    validate_named_result(named, pavilion, panel)
    fits = named["receiver_fits"]
    negatives = named["negative_controls"]
    if len(fits) != len(pavilion["interfaces"]):
        raise ValueError("inherited receiver count drift")
    if any(not value.startswith("REJECTED") for value in negatives.values()):
        raise ValueError("inherited negative control drift")

    source_residual, receiver_results = receiver_reversibility(
        build_result,
        pavilion,
        panel,
    )

    emission_variants = load_emission_variants_tool()
    source_variant_contract = emission_variants.load_contract()
    if source_variant_contract.get("schema") != authority["emission_variants_schema"]:
        raise ValueError("source-owned emission-variant schema no longer matches panel contract")
    if (
        source_variant_contract.get("selection_policy")
        != authority["emission_variant_selection_policy"]
    ):
        raise ValueError(
            "source-owned emission-variant selection policy no longer matches panel contract"
        )

    expected_receiver_ids = [fit["interface_id"] for fit in fits]
    role_results = []
    for role_entry in state["tested_representation_roles"]:
        role = role_entry["role"]
        variant_id = role_entry["variant_id"]
        payload = emission_variants.build_variant(variant_id, exact_head)

        if payload["schema"] != EXPECTED_EMISSION_VARIANTS_SCHEMA:
            raise ValueError(f"{role}/{variant_id}: emission schema drift")
        if payload["selection_policy"] != EXPECTED_EMISSION_SELECTION_POLICY:
            raise ValueError(f"{role}/{variant_id}: emission selection policy drift")
        if payload["receiver_ids"] != expected_receiver_ids:
            raise ValueError(f"{role}/{variant_id}: receiver identity drift")
        if payload["receiver_mount_residual_max_m"] > EPS:
            raise ValueError(f"{role}/{variant_id}: receiver fit residual drift")

        per_receiver = []
        for row in receiver_results:
            if row["zero_degree_mount_pattern_residual_m"] > EPS:
                raise ValueError(
                    f"{role}/{variant_id}/{row['interface_id']}: "
                    "zero-degree residual drift"
                )
            if row["one_eighty_degree_unordered_mount_pattern_residual_m"] > EPS:
                raise ValueError(
                    f"{role}/{variant_id}/{row['interface_id']}: "
                    "180-degree residual drift"
                )
            per_receiver.append(
                {
                    "interface_id": row["interface_id"],
                    "zero_degree_mount_pattern_residual_m": row[
                        "zero_degree_mount_pattern_residual_m"
                    ],
                    "one_eighty_degree_unordered_mount_pattern_residual_m": row[
                        "one_eighty_degree_unordered_mount_pattern_residual_m"
                    ],
                }
            )

        role_results.append(
            {
                "role": role,
                "variant_id": variant_id,
                "representation": payload["representation"],
                "historical_emission_contract_status": payload[
                    "downstream_adoption"
                ],
                "emitted_box_count": payload["emitted_box_count"],
                "vertex_count": payload["vertex_count"],
                "triangle_count": payload["triangle_count"],
                "positive_volume_intersection_count": payload[
                    "positive_volume_intersection_count"
                ],
                "occupied_union_volume_m3": payload["occupied_union_volume_m3"],
                "receiver_ids": payload["receiver_ids"],
                "receiver_mount_residual_max_m": payload[
                    "receiver_mount_residual_max_m"
                ],
                "receiver_reversibility": per_receiver,
            }
        )

    expected_signatures = {
        ("CURRENT_SOURCE", "header-segmented-23"): (
            23,
            184,
            276,
            0,
            "OPT_IN_ONLY",
        ),
        ("LEGACY_COMPATIBILITY", "base-closed-outward-19"): (
            19,
            152,
            228,
            4,
            "CURRENT_DEFAULT_UNCHANGED",
        ),
    }
    for row in role_results:
        key = (row["role"], row["variant_id"])
        if key not in expected_signatures:
            raise ValueError(f"undeclared representation role: {key}")
        observed = (
            row["emitted_box_count"],
            row["vertex_count"],
            row["triangle_count"],
            row["positive_volume_intersection_count"],
            row["historical_emission_contract_status"],
        )
        if observed != expected_signatures[key]:
            raise ValueError(
                f"{row['role']}/{row['variant_id']}: exact signature drift "
                f"{observed} != {expected_signatures[key]}"
            )

    current = next(row for row in role_results if row["role"] == "CURRENT_SOURCE")
    legacy = next(
        row for row in role_results if row["role"] == "LEGACY_COMPATIBILITY"
    )
    union_residual = (
        current["occupied_union_volume_m3"] - legacy["occupied_union_volume_m3"]
    )
    if abs(union_residual) > EPS:
        raise ValueError("current/legacy occupied union volume drift")
    if current["receiver_ids"] != legacy["receiver_ids"]:
        raise ValueError("current/legacy receiver identity drift")
    if (
        current["receiver_mount_residual_max_m"]
        != legacy["receiver_mount_residual_max_m"]
    ):
        raise ValueError("current/legacy receiver fit residual drift")

    return {
        "result": (
            "PASS_BUILDING_PANEL_180_DEGREE_REVERSIBILITY_"
            "ACROSS_CURRENT_AND_LEGACY_SOURCE_ROLES"
        ),
        "exact_hard_surface_head": exact_head,
        "scope": contract["scope"],
        "source_authority": authority,
        "source_role_policy": {
            "schema": source_policy["schema"],
            "current_source_variant_id": source_policy["current_source_variant_id"],
            "legacy_compatibility_variant_id": source_policy[
                "legacy_compatibility_variant_id"
            ],
            "selection_policy": source_policy["selection_policy"],
            "historical_build_result_policy": source_policy[
                "historical_build_result_policy"
            ],
            "policy_sha256": sha256(CURRENT_POLICY),
        },
        "panel_source_sha256": EXPECTED_PANEL_SHA256,
        "pavilion_source_sha256": EXPECTED_PAVILION_SHA256,
        "source_mount_pattern_180_residual_m": source_residual,
        "box_proof_geometry_180_residual_m": 0.0,
        "named_build_result": {
            "schema": named["schema"],
            "role": "LEGACY_COMPATIBILITY_INTERFACE",
            "legacy_output_count_observed": named["legacy_output_count_observed"],
            "opaque_trailing_extension_count": named[
                "opaque_trailing_extension_count"
            ],
            "topology_revision": named["topology_summary"]["revision"],
            "topology_object_count": named["topology_summary"]["object_count"],
            "receiver_ids": expected_receiver_ids,
        },
        "receiver_results": receiver_results,
        "representation_role_results": role_results,
        "current_legacy_comparison": {
            "occupied_union_volume_residual_m3": round(union_residual, 12),
            "receiver_ids_equal": current["receiver_ids"] == legacy["receiver_ids"],
            "receiver_fit_residual_equal": (
                current["receiver_mount_residual_max_m"]
                == legacy["receiver_mount_residual_max_m"]
            ),
            "current_source_positive_volume_intersections": current[
                "positive_volume_intersection_count"
            ],
            "legacy_positive_volume_intersections": legacy[
                "positive_volume_intersection_count"
            ],
        },
        "physical_orientation_key_present": False,
        "receiver_frame_metadata_orientation_preserved": True,
        "geometry_changed": False,
        "source_role_adoption_changed": False,
        "preservation_policy": contract["preservation_policy"],
        "inherited_hard_surface_prerequisite": (
            "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF"
        ),
        "emission_variant_prerequisite": (
            "PASS_EXPLICIT_SOURCE_OWNED_BUILDING_EMISSION_VARIANT_SELECTION"
        ),
        "current_source_policy_prerequisite": (
            "PASS_SEGMENTED_BUILDING_PROMOTED_TO_CURRENT_SOURCE_POLICY_"
            "WITH_LEGACY_COMPATIBILITY"
        ),
        "truth_boundary": contract["truth_boundary"],
    }


def run_negative_controls():
    panel = load(PANEL)
    pavilion = load(PAVILION)
    contract = load(CONTRACT)
    source_policy = load(CURRENT_POLICY)
    results = {}

    bad_panel = copy.deepcopy(panel)
    bad_panel["mount_points_local_m"][0][0] += 0.001
    try:
        verify(
            panel=bad_panel,
            pavilion=pavilion,
            contract=contract,
            current_policy=source_policy,
        )
        results["asymmetric_mount_drift_0p001m"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["asymmetric_mount_drift_0p001m"] = "REJECTED: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["observed_mechanical_state"]["physical_orientation_key_present"] = True
    try:
        verify(
            panel=panel,
            pavilion=pavilion,
            contract=bad_contract,
            current_policy=source_policy,
        )
        results["unsupported_keyed_claim"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["unsupported_keyed_claim"] = "REJECTED: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["source_authority"]["panel_source_sha256"] = "0" * 64
    try:
        verify(
            panel=panel,
            pavilion=pavilion,
            contract=bad_contract,
            current_policy=source_policy,
        )
        results["source_identity_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["source_identity_drift"] = "REJECTED: " + str(exc)

    named = load_build_result_tool().build_named()
    named.pop("receiver_fits")
    try:
        verify(
            panel=panel,
            pavilion=pavilion,
            contract=contract,
            named_result=named,
            current_policy=source_policy,
        )
        results["missing_named_receiver_dependency"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["missing_named_receiver_dependency"] = "REJECTED: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["source_authority"]["current_emission_policy_schema"] = (
        "axm.building-current-emission-policy/DRIFT"
    )
    try:
        verify(
            panel=panel,
            pavilion=pavilion,
            contract=bad_contract,
            current_policy=source_policy,
        )
        results["current_policy_schema_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["current_policy_schema_drift"] = "REJECTED: " + str(exc)

    regressed_policy = copy.deepcopy(source_policy)
    regressed_policy["current_source_variant_id"] = "base-closed-outward-19"
    try:
        verify(
            panel=panel,
            pavilion=pavilion,
            contract=contract,
            current_policy=regressed_policy,
        )
        results["current_source_role_regression"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["current_source_role_regression"] = "REJECTED: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["observed_mechanical_state"]["tested_representation_roles"] = [
        {"role": "CURRENT_SOURCE", "variant_id": "base-closed-outward-19"},
        {"role": "LEGACY_COMPATIBILITY", "variant_id": "header-segmented-23"},
    ]
    try:
        verify(
            panel=panel,
            pavilion=pavilion,
            contract=bad_contract,
            current_policy=source_policy,
        )
        results["consumer_role_relabel"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        results["consumer_role_relabel"] = "REJECTED: " + str(exc)

    if any(not value.startswith("REJECTED:") for value in results.values()):
        raise ValueError("negative control unexpectedly passed")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="evidence/utility-panel-rotational-symmetry-004",
    )
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    receipt = verify(exact_head=args.exact_head)
    receipt["negative_controls"] = run_negative_controls()
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "contract.json").write_text(
        CONTRACT.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "current-emission-policy.json").write_text(
        CURRENT_POLICY.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "exact-head.txt").write_text(
        args.exact_head + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
