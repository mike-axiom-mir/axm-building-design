#!/usr/bin/env python3
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGICAL_BUILDER = ROOT / "tools/build_pavilion_symmetric_rows.py"
LOGICAL_PROFILE = ROOT / "procedural/service_pavilion_symmetric_rows_001.json"
EXPANSION_PROFILE = ROOT / "procedural/service_pavilion_header_segment_expansion_001.json"
SUCCESSOR_CONTRACT = ROOT / "assets/service_pavilion_001_header_segmentation.json"
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
EPS = 1e-9


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_logical_builder():
    spec = importlib.util.spec_from_file_location("build_pavilion_symmetric_rows", LOGICAL_BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _close(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= EPS
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return all(_close(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b):
        return all(_close(a[key], b[key]) for key in a)
    return a == b


def find_logical_header_row(logical_mod, logical_profile, expansion_profile):
    matches = [
        row for row in logical_profile.get("rows", [])
        if row.get("id") == expansion_profile.get("logical_row_id")
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one logical header row")
    generated = logical_mod.generate_row(matches[0])
    expected_ids = ["front-header", "rear-header"]
    if [item["id"] for item in generated] != expected_ids:
        raise ValueError("logical header row identity/order drift")
    return generated


def generate_segmented_headers(logical_headers, profile):
    axis = profile.get("segment_axis")
    if axis not in AXIS_INDEX:
        raise ValueError("unsupported segment axis")
    centers = profile.get("segment_centers_m")
    lengths = profile.get("segment_lengths_m")
    suffixes = profile.get("segment_id_suffixes")
    if not isinstance(centers, list) or len(centers) < 2:
        raise ValueError("segment centers must contain at least two stations")
    if not isinstance(lengths, list) or len(lengths) != len(centers):
        raise ValueError("segment length count mismatch")
    if not isinstance(suffixes, list) or len(suffixes) != len(centers):
        raise ValueError("segment suffix count mismatch")
    if len(set(suffixes)) != len(suffixes):
        raise ValueError("duplicate segment suffix")
    if any(float(length) <= 0.0 for length in lengths):
        raise ValueError("segment lengths must be positive")
    if len({float(center) for center in centers}) != len(centers):
        raise ValueError("duplicate segment center")

    axis_index = AXIS_INDEX[axis]
    result = {}
    for logical in logical_headers:
        base_center = [float(v) for v in logical["center"]]
        base_size = [float(v) for v in logical["size"]]
        segments = []
        for center_value, length, suffix in zip(centers, lengths, suffixes):
            center = list(base_center)
            size = list(base_size)
            center[axis_index] = float(center_value)
            size[axis_index] = float(length)
            segments.append({
                "id": logical["id"] + suffix,
                "center": center,
                "size": size,
            })
        result[logical["id"]] = segments
    return result


def verify_contract(profile, successor_contract, observed_contract_sha256, generated):
    if successor_contract.get("schema") != profile.get("successor_contract_schema"):
        raise ValueError("successor contract schema drift")
    if successor_contract.get("asset_id") != profile.get("source_asset_id"):
        raise ValueError("successor asset identity drift")
    if successor_contract.get("successor_revision") != profile.get("successor_revision"):
        raise ValueError("successor revision drift")
    if observed_contract_sha256 != profile.get("successor_contract_sha256"):
        raise ValueError("successor contract SHA-256 drift")
    source_segments = successor_contract.get("segmented_components")
    if not isinstance(source_segments, dict):
        raise ValueError("successor segmented component map missing")
    if set(source_segments) != set(generated):
        raise ValueError("successor segmented logical component set drift")
    for logical_id, segments in generated.items():
        if not _close(segments, source_segments.get(logical_id)):
            raise ValueError(f"source-owned segment pattern mismatch for {logical_id}")


def run_negative_controls(logical_mod, logical_profile, profile, contract, contract_sha):
    controls = {}
    logical_headers = find_logical_header_row(logical_mod, logical_profile, profile)
    generated = generate_segmented_headers(logical_headers, profile)

    bad = copy.deepcopy(profile)
    bad["segment_axis"] = "q"
    try:
        generate_segmented_headers(logical_headers, bad)
        controls["unsupported_segment_axis"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["unsupported_segment_axis"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["segment_id_suffixes"][1] = bad["segment_id_suffixes"][0]
    try:
        generate_segmented_headers(logical_headers, bad)
        controls["duplicate_segment_suffix"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["duplicate_segment_suffix"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["segment_lengths_m"] = bad["segment_lengths_m"][:-1]
    try:
        generate_segmented_headers(logical_headers, bad)
        controls["segment_count_mismatch"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["segment_count_mismatch"] = "HOLD: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["schema"] = "axm.building-header-segmentation/v9.9"
    try:
        verify_contract(profile, bad_contract, contract_sha, generated)
        controls["successor_schema_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["successor_schema_drift"] = "HOLD: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["successor_revision"] = "service-pavilion-001/unknown-successor"
    try:
        verify_contract(profile, bad_contract, contract_sha, generated)
        controls["successor_revision_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["successor_revision_drift"] = "HOLD: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["segmented_components"]["front-header"][0]["center"][0] += 0.001
    try:
        verify_contract(profile, bad_contract, contract_sha, generated)
        controls["source_segment_drift_0p001m"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["source_segment_drift_0p001m"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["successor_contract_sha256"] = "0" * 64
    try:
        verify_contract(bad, contract, contract_sha, generated)
        controls["successor_identity_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["successor_identity_drift"] = "HOLD: " + str(exc)

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("negative control unexpectedly passed")
    return controls


def build():
    logical_mod = load_logical_builder()
    logical_summary = logical_mod.build()
    logical_profile = load(LOGICAL_PROFILE)
    profile = load(EXPANSION_PROFILE)
    successor_contract = load(SUCCESSOR_CONTRACT)
    observed_contract_sha256 = sha256(SUCCESSOR_CONTRACT)

    if logical_summary.get("result") != "PASS_SOURCE_EXACT_SYMMETRIC_COMPONENT_ROW_GENERATOR":
        raise ValueError("logical procedural prerequisite is not PASS")
    if profile.get("logical_family_id") != logical_summary.get("family_id"):
        raise ValueError("logical procedural family identity drift")

    logical_headers = find_logical_header_row(logical_mod, logical_profile, profile)
    generated = generate_segmented_headers(logical_headers, profile)
    verify_contract(profile, successor_contract, observed_contract_sha256, generated)

    expansion_rows = []
    for logical_id in [item["id"] for item in logical_headers]:
        segments = generated[logical_id]
        expansion_rows.append({
            "logical_component_id": logical_id,
            "segment_count": len(segments),
            "segment_ids": [item["id"] for item in segments],
            "segment_digest": digest_json(segments),
            "segments": segments,
        })

    expansion_digests = [item["segment_digest"] for item in expansion_rows]
    if len(set(expansion_digests)) != len(expansion_digests):
        raise ValueError("front/rear segmented outputs are not materially distinct")

    negatives = run_negative_controls(
        logical_mod,
        logical_profile,
        profile,
        successor_contract,
        observed_contract_sha256,
    )

    emitted_count = logical_summary["generated_component_count"] - len(logical_headers) + sum(
        item["segment_count"] for item in expansion_rows
    )
    logical_row_digests = [row["row_digest"] for row in logical_summary["rows"]]
    all_output_digests = logical_row_digests + expansion_digests

    return {
        "result": "PASS_SOURCE_EXACT_HEADER_SEGMENT_EXPANSION_FAMILY",
        "logical_prerequisite_result": logical_summary["result"],
        "logical_source_rebind_result": logical_summary["source_rebind_result"],
        "logical_build_result_rebind_result": logical_summary["build_result_rebind_result"],
        "schema": "axm.building-header-segment-expansion-evidence/v0.1",
        "family_id": profile["family_id"],
        "logical_family_id": profile["logical_family_id"],
        "logical_row_id": profile["logical_row_id"],
        "source_asset_id": profile["source_asset_id"],
        "source_hard_surface_head": profile["source_hard_surface_head"],
        "successor_contract_schema": successor_contract["schema"],
        "successor_revision": successor_contract["successor_revision"],
        "successor_contract_sha256": observed_contract_sha256,
        "authority": profile["authority"],
        "failure_policy": profile["failure_policy"],
        "logical_row_count_preserved": logical_summary["row_count"],
        "logical_generated_component_count_preserved": logical_summary["generated_component_count"],
        "logical_generated_subset_digest_preserved": logical_summary["generated_subset_digest"],
        "logical_distinct_row_digests_preserved": logical_summary["distinct_row_digests"],
        "expanded_logical_header_count": len(expansion_rows),
        "expanded_segment_count": sum(item["segment_count"] for item in expansion_rows),
        "expanded_emitted_generated_component_count": emitted_count,
        "expanded_emitted_pavilion_coverage": f"{emitted_count}/21",
        "distinct_expansion_digests": len(set(expansion_digests)),
        "distinct_total_output_digests": len(set(all_output_digests)),
        "expansion_rows": expansion_rows,
        "negative_controls": negatives,
        "truth_boundary": profile["truth_boundary"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    summary = build()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (args.output_dir / "generated-header-segments.json").write_text(
            json.dumps(
                {
                    row["logical_component_id"]: row["segments"]
                    for row in summary["expansion_rows"]
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        (args.output_dir / "source-header-segmentation-contract.json").write_text(
            SUCCESSOR_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
