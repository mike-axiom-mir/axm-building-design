#!/usr/bin/env python3
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAVILION = ROOT / "assets/service_pavilion_001.json"
PROFILE = ROOT / "procedural/service_pavilion_symmetric_rows_001.json"
BUILD_RESULT_CONTRACT = ROOT / "tools/service_pavilion_build_result.py"
EPS = 1e-9
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
PROCEDURAL_BUILD_FIELDS = (
    "pavilion",
    "receiver_fits",
    "bounds_min",
    "bounds_max",
    "readable_path_gap_m",
    "negative_controls",
    "topology_summary",
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_build_result_contract():
    spec = importlib.util.spec_from_file_location(
        "service_pavilion_build_result", BUILD_RESULT_CONTRACT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def project_named_build_result(contract, named, profile):
    required_schema = profile.get("required_build_result_schema")
    if required_schema != contract.BUILD_RESULT_SCHEMA:
        raise ValueError("procedural profile build-result schema drift")
    if named.get("schema") != required_schema:
        raise ValueError("named Building build-result schema drift")
    contract.require_fields(named, PROCEDURAL_BUILD_FIELDS)
    return {field: named[field] for field in PROCEDURAL_BUILD_FIELDS}


def _close(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= EPS
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return all(_close(x, y) for x, y in zip(a, b))
    return a == b


def generate_row(row):
    axis = row.get("axis")
    if axis not in AXIS_INDEX:
        raise ValueError(f"{row.get('id', 'row')}: unsupported axis {axis!r}")
    base = row.get("base_center_m")
    size = row.get("size_m")
    offsets = row.get("positive_offsets_m")
    ids = row.get("component_ids_negative_to_positive")
    if not isinstance(base, list) or len(base) != 3:
        raise ValueError(f"{row.get('id', 'row')}: base_center_m must contain 3 values")
    if not isinstance(size, list) or len(size) != 3 or any(float(v) <= 0.0 for v in size):
        raise ValueError(f"{row.get('id', 'row')}: size_m must contain 3 positive values")
    if not isinstance(offsets, list) or not offsets or any(float(v) <= 0.0 for v in offsets):
        raise ValueError(f"{row.get('id', 'row')}: positive_offsets_m must contain positive values")
    if len({float(v) for v in offsets}) != len(offsets):
        raise ValueError(f"{row.get('id', 'row')}: duplicate positive offset")
    stations = sorted(
        [-float(v) for v in offsets]
        + ([0.0] if row.get("include_center") else [])
        + [float(v) for v in offsets]
    )
    if not isinstance(ids, list) or len(ids) != len(stations):
        raise ValueError(f"{row.get('id', 'row')}: component id count does not match stations")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{row.get('id', 'row')}: duplicate generated component id")
    index = AXIS_INDEX[axis]
    components = []
    for component_id, station in zip(ids, stations):
        center = [float(v) for v in base]
        center[index] = station
        components.append(
            {"id": component_id, "center": center, "size": [float(v) for v in size]}
        )
    return components


def verify_profile(pavilion, profile, observed_source_sha256):
    if profile.get("source_asset_id") != pavilion.get("asset_id"):
        raise ValueError("source asset identity mismatch")
    if profile.get("source_schema") != pavilion.get("schema"):
        raise ValueError("source schema drift")
    if profile.get("source_revision") != pavilion.get("source_revision"):
        raise ValueError("source revision drift")
    contract = pavilion.get("generated_geometry_contract", {})
    if profile.get("required_box_shell_topology") != contract.get("box_shell_topology"):
        raise ValueError("source box-shell topology contract drift")
    if profile.get("source_sha256") != observed_source_sha256:
        raise ValueError("source SHA-256 drift")
    rows = profile.get("rows")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("profile must retain at least three materially different rows")

    source_by_id = {item["id"]: item for item in pavilion.get("components", [])}
    generated_ids = []
    row_results = []
    for row in rows:
        generated = generate_row(row)
        for component in generated:
            source = source_by_id.get(component["id"])
            if source is None:
                raise ValueError(
                    f"{row['id']}: generated id absent from source: {component['id']}"
                )
            if not _close(component["center"], source.get("center")):
                raise ValueError(
                    f"{row['id']}: source center mismatch for {component['id']}"
                )
            if not _close(component["size"], source.get("size")):
                raise ValueError(
                    f"{row['id']}: source size mismatch for {component['id']}"
                )
        generated_ids.extend(item["id"] for item in generated)
        row_results.append(
            {
                "row_id": row["id"],
                "component_count": len(generated),
                "component_ids": [item["id"] for item in generated],
                "row_digest": digest_json(generated),
                "size_m": generated[0]["size"],
                "axis": row["axis"],
                "base_center_m": row["base_center_m"],
            }
        )
    if len(set(generated_ids)) != len(generated_ids):
        raise ValueError("component id is generated by more than one row")
    if len({r["row_digest"] for r in row_results}) != len(row_results):
        raise ValueError("row outputs are not materially distinct")
    if len({tuple(r["size_m"]) for r in row_results}) < 2:
        raise ValueError("row outputs do not exercise multiple component sizes")
    if len({r["component_count"] for r in row_results}) < 2:
        raise ValueError("row outputs do not exercise multiple station counts")

    generated_set = set(generated_ids)
    manual_ids = [
        item["id"] for item in pavilion["components"] if item["id"] not in generated_set
    ]
    return row_results, generated_ids, manual_ids


def run_negative_controls(pavilion, profile, observed_source_sha256, build_contract, named):
    controls = {}

    bad = copy.deepcopy(profile)
    bad["rows"][0]["axis"] = "q"
    try:
        verify_profile(pavilion, bad, observed_source_sha256)
        controls["unsupported_axis"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["unsupported_axis"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["rows"][0]["component_ids_negative_to_positive"][1] = bad["rows"][0][
        "component_ids_negative_to_positive"
    ][0]
    try:
        verify_profile(pavilion, bad, observed_source_sha256)
        controls["duplicate_component_id"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["duplicate_component_id"] = "HOLD: " + str(exc)

    bad_source = copy.deepcopy(pavilion)
    target = next(
        item for item in bad_source["components"] if item["id"] == "front-door-left"
    )
    target["center"][0] += 0.001
    try:
        verify_profile(bad_source, profile, observed_source_sha256)
        controls["source_pattern_drift_0p001m"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["source_pattern_drift_0p001m"] = "HOLD: " + str(exc)

    bad_source = copy.deepcopy(pavilion)
    target = next(
        item for item in bad_source["components"] if item["id"] == "east-header"
    )
    target["center"][0] += 0.001
    try:
        verify_profile(bad_source, profile, observed_source_sha256)
        controls["header_pattern_drift_0p001m"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["header_pattern_drift_0p001m"] = "HOLD: " + str(exc)

    bad_source = copy.deepcopy(pavilion)
    bad_source["source_revision"] = "service-pavilion-001/unknown-successor"
    try:
        verify_profile(bad_source, profile, observed_source_sha256)
        controls["source_revision_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["source_revision_drift"] = "HOLD: " + str(exc)

    bad_source = copy.deepcopy(pavilion)
    bad_source["generated_geometry_contract"]["box_shell_topology"] = "historical-malformed-face-table"
    try:
        verify_profile(bad_source, profile, observed_source_sha256)
        controls["source_topology_contract_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["source_topology_contract_drift"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["source_sha256"] = "0" * 64
    try:
        verify_profile(pavilion, bad, observed_source_sha256)
        controls["source_identity_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["source_identity_drift"] = "HOLD: " + str(exc)

    missing = dict(named)
    missing.pop("topology_summary")
    try:
        project_named_build_result(build_contract, missing, profile)
        controls["missing_named_build_dependency"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["missing_named_build_dependency"] = "HOLD: " + str(exc)

    drifted = dict(named)
    drifted["schema"] = "axm.building-build-result/v9.9"
    try:
        project_named_build_result(build_contract, drifted, profile)
        controls["named_build_result_schema_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["named_build_result_schema_drift"] = "HOLD: " + str(exc)

    if any(not state.startswith("HOLD:") for state in controls.values()):
        raise ValueError("negative control unexpectedly passed")
    return controls


def build():
    pavilion = load(PAVILION)
    profile = load(PROFILE)
    observed_source_sha256 = sha256(PAVILION)
    rows, generated_ids, manual_ids = verify_profile(
        pavilion, profile, observed_source_sha256
    )

    build_contract = load_build_result_contract()
    named = build_contract.build_named()
    projected = project_named_build_result(build_contract, named, profile)

    legacy = build_contract.builder.build()
    future_named = build_contract.from_legacy_output(
        tuple(legacy) + ({"future_extension": "opaque-to-v0.1-procedural-consumer"},)
    )
    future_projected = project_named_build_result(build_contract, future_named, profile)
    if future_projected != projected:
        raise ValueError("opaque trailing producer extension changed Procedural named inputs")

    negatives = run_negative_controls(
        pavilion,
        profile,
        observed_source_sha256,
        build_contract,
        named,
    )

    base_pav = projected["pavilion"]
    fits = projected["receiver_fits"]
    mins = projected["bounds_min"]
    maxs = projected["bounds_max"]
    path_gap = projected["readable_path_gap_m"]
    base_negatives = projected["negative_controls"]
    topology_summary = projected["topology_summary"]

    if base_pav["asset_id"] != pavilion["asset_id"]:
        raise ValueError("base structural builder source identity mismatch")
    if base_pav.get("source_revision") != profile.get("source_revision"):
        raise ValueError("inherited hard-surface source revision mismatch")
    if topology_summary.get("revision") != profile.get("required_box_shell_topology"):
        raise ValueError("inherited hard-surface topology revision mismatch")
    if any(not state.startswith("REJECTED") for state in base_negatives.values()):
        raise ValueError("inherited hard-surface negative control drift")

    expected_topology = {
        "object_count": 19,
        "vertex_count": 152,
        "triangle_count": 228,
        "boundary_edge_count": 0,
        "nonmanifold_edge_count": 0,
        "orientation_conflict_edge_count": 0,
        "degenerate_triangle_count": 0,
        "outward_triangle_count": 228,
        "inward_triangle_count": 0,
        "tangent_triangle_count": 0,
    }
    for key, expected in expected_topology.items():
        if topology_summary.get(key) != expected:
            raise ValueError(
                f"inherited hard-surface topology drift {key}: {topology_summary.get(key)} != {expected}"
            )
    if not topology_summary.get("historical_predecessor_rejection", "").startswith("REJECTED"):
        raise ValueError("historical malformed topology control did not reject")
    if not topology_summary.get("single_triangle_flip_rejection", "").startswith("REJECTED"):
        raise ValueError("single-triangle winding control did not reject")

    generated_components = []
    for row in profile["rows"]:
        generated_components.extend(generate_row(row))

    return {
        "result": "PASS_SOURCE_EXACT_SYMMETRIC_COMPONENT_ROW_GENERATOR",
        "source_rebind_result": "PASS_EXACT_SOURCE_REBIND_TO_CLOSED_OUTWARD_BOX_SHELLS_002",
        "build_result_rebind_result": "PASS_PROCEDURAL_CONSUMER_USES_VERSIONED_NAMED_BUILD_RESULT",
        "schema": "axm.building-symmetric-component-row-evidence/v0.3",
        "family_id": profile["family_id"],
        "source_asset_id": pavilion["asset_id"],
        "source_schema": pavilion["schema"],
        "source_revision": pavilion["source_revision"],
        "source_hard_surface_head": profile["source_hard_surface_head"],
        "build_result_contract_hard_surface_head": profile["build_result_contract_hard_surface_head"],
        "build_result_contract_schema": named["schema"],
        "build_result_named_dependencies": list(PROCEDURAL_BUILD_FIELDS),
        "build_result_legacy_output_count_observed": named["legacy_output_count_observed"],
        "build_result_opaque_trailing_extension_count_current": named["opaque_trailing_extension_count"],
        "build_result_future_extension_control": "PASS_EXISTING_PROCEDURAL_INPUTS_UNCHANGED",
        "source_sha256": observed_source_sha256,
        "profile_sha256": sha256(PROFILE),
        "authority": profile["authority"],
        "failure_policy": profile["failure_policy"],
        "row_count": len(rows),
        "generated_component_count": len(generated_components),
        "source_component_count": len(pavilion["components"]),
        "generated_source_coverage": f"{len(generated_components)}/{len(pavilion['components'])}",
        "distinct_row_digests": len({r["row_digest"] for r in rows}),
        "distinct_component_sizes": len({tuple(r["size_m"]) for r in rows}),
        "distinct_station_counts": sorted({r["component_count"] for r in rows}),
        "rows": rows,
        "generated_component_ids": generated_ids,
        "manual_component_ids_outside_family": manual_ids,
        "generated_subset_digest": digest_json(generated_components),
        "inherited_hard_surface_gate": {
            "result": "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF",
            "source_revision": base_pav["source_revision"],
            "box_shell_topology": topology_summary["revision"],
            "topology_result": "PASS_SOURCE_OWNED_CLOSED_OUTWARD_BOX_SHELLS_19_REAL_OUTPUTS",
            "topology_summary": {
                key: topology_summary[key]
                for key in expected_topology
            },
            "historical_predecessor_rejection": topology_summary["historical_predecessor_rejection"],
            "single_triangle_flip_rejection": topology_summary["single_triangle_flip_rejection"],
            "receiver_count": len(fits),
            "readable_path_gap_m": path_gap,
            "combined_bounds_local_m": {"min": mins, "max": maxs},
            "negative_controls": base_negatives,
        },
        "negative_controls": negatives,
        "truth_boundary": profile["truth_boundary"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir", default="evidence/service-pavilion-symmetric-rows-001"
    )
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = build()
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for row in load(PROFILE)["rows"]:
        generated = generate_row(row)
        (out / f"{row['id']}.json").write_text(
            json.dumps(generated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
