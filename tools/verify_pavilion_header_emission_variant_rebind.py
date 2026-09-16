#!/usr/bin/env python3
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPANSION_BUILDER = ROOT / "tools/build_pavilion_header_segment_expansion.py"
EXPANSION_PROFILE = ROOT / "procedural/service_pavilion_header_segment_expansion_001.json"
EMISSION_MODULE = ROOT / "tools/service_pavilion_emission_variants.py"
EMISSION_CONTRACT = ROOT / "assets/service_pavilion_001_emission_variants.json"
EPS = 1e-9


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def close(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= EPS
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b):
        return all(close(a[key], b[key]) for key in a)
    return a == b


def center_size(box):
    center = [round((float(lo) + float(hi)) / 2.0, 9) for lo, hi in zip(box["lo"], box["hi"])]
    size = [round(float(hi) - float(lo), 9) for lo, hi in zip(box["lo"], box["hi"])]
    return {"id": box["id"], "center": center, "size": size}


def header_rows(variant, logical_id):
    rows = [
        center_size(box)
        for box in variant["boxes"]
        if box.get("source_component_id") == logical_id and box.get("role") != "panel"
    ]
    return sorted(rows, key=lambda row: row["id"])


def verify_binding(profile, contract, observed_contract_sha256):
    if profile.get("schema") != "axm.building-header-segment-expansion-family/v0.2":
        raise ValueError("procedural header family schema drift")
    if contract.get("schema") != profile.get("emission_variant_contract_schema"):
        raise ValueError("emission variant contract schema drift")
    if observed_contract_sha256 != profile.get("emission_variant_contract_sha256"):
        raise ValueError("emission variant contract SHA-256 drift")
    if contract.get("selection_policy") != profile.get("emission_selection_policy"):
        raise ValueError("emission variant selection policy drift")
    if contract.get("default_variant_id") != profile.get("default_variant_id"):
        raise ValueError("default emission variant drift")
    variants = contract.get("variants", {})
    default_id = profile.get("default_variant_id")
    segmented_id = profile.get("segmented_variant_id")
    if set(variants) != {default_id, segmented_id}:
        raise ValueError("emission variant allowlist drift")
    if variants[default_id].get("downstream_adoption") != profile.get("default_variant_adoption"):
        raise ValueError("default variant adoption policy drift")
    if variants[segmented_id].get("downstream_adoption") != profile.get("segmented_variant_adoption"):
        raise ValueError("segmented variant adoption policy drift")


def run_negative_controls(profile, contract, contract_sha, emission_mod):
    controls = {}

    bad = copy.deepcopy(profile)
    bad["emission_variant_contract_sha256"] = "0" * 64
    try:
        verify_binding(bad, contract, contract_sha)
        controls["emission_contract_identity_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["emission_contract_identity_drift"] = "HOLD: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["selection_policy"] = "IMPLICIT_BEST_EFFORT"
    try:
        verify_binding(profile, bad_contract, contract_sha)
        controls["selection_policy_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["selection_policy_drift"] = "HOLD: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["default_variant_id"] = profile["segmented_variant_id"]
    try:
        verify_binding(profile, bad_contract, contract_sha)
        controls["default_variant_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["default_variant_drift"] = "HOLD: " + str(exc)

    bad_contract = copy.deepcopy(contract)
    bad_contract["variants"][profile["segmented_variant_id"]]["downstream_adoption"] = "AUTO_ADOPT"
    try:
        verify_binding(profile, bad_contract, contract_sha)
        controls["segmented_adoption_policy_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["segmented_adoption_policy_drift"] = "HOLD: " + str(exc)

    try:
        emission_mod.build_variant("silent-best-effort", profile["source_hard_surface_head"])
        controls["unknown_variant_fallback"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["unknown_variant_fallback"] = "HOLD: " + str(exc)

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("emission-variant negative control unexpectedly passed")
    return controls


def build():
    expansion_mod = load_module(EXPANSION_BUILDER, "pavilion_header_expansion_for_variant_rebind")
    emission_mod = load_module(EMISSION_MODULE, "service_pavilion_emission_variants_for_procedural")
    profile = load(EXPANSION_PROFILE)
    contract = load(EMISSION_CONTRACT)
    contract_sha = sha256(EMISSION_CONTRACT)

    expansion = expansion_mod.build()
    if expansion.get("result") != "PASS_SOURCE_EXACT_HEADER_SEGMENT_EXPANSION_FAMILY":
        raise ValueError("header expansion prerequisite is not PASS")
    verify_binding(profile, contract, contract_sha)

    logical_mod = expansion_mod.load_logical_builder()
    logical_profile = expansion_mod.load(expansion_mod.LOGICAL_PROFILE)
    logical_headers = expansion_mod.find_logical_header_row(logical_mod, logical_profile, profile)
    logical_by_id = {row["id"]: row for row in logical_headers}
    expanded_by_id = {
        row["logical_component_id"]: row["segments"]
        for row in expansion["expansion_rows"]
    }

    default_id = profile["default_variant_id"]
    segmented_id = profile["segmented_variant_id"]
    base = emission_mod.build_variant(default_id, profile["source_hard_surface_head"])
    segmented = emission_mod.build_variant(segmented_id, profile["source_hard_surface_head"])

    rows = []
    for logical_id in ("front-header", "rear-header"):
        base_rows = header_rows(base, logical_id)
        segmented_rows = header_rows(segmented, logical_id)
        expected_base = [logical_by_id[logical_id]]
        expected_segmented = expanded_by_id[logical_id]
        if not close(base_rows, expected_base):
            raise ValueError(f"{logical_id}: default source variant no longer matches logical procedural header")
        if not close(segmented_rows, expected_segmented):
            raise ValueError(f"{logical_id}: segmented source variant no longer matches procedural expansion")
        rows.append({
            "logical_component_id": logical_id,
            "default_variant_header_count": len(base_rows),
            "segmented_variant_header_count": len(segmented_rows),
            "default_variant_header_digest": digest_json(base_rows),
            "segmented_variant_header_digest": digest_json(segmented_rows),
            "default_variant_headers": base_rows,
            "segmented_variant_headers": segmented_rows,
        })

    default_digest = digest_json([row["default_variant_headers"] for row in rows])
    segmented_digest = digest_json([row["segmented_variant_headers"] for row in rows])
    if default_digest == segmented_digest:
        raise ValueError("default and segmented procedural header outputs are not materially distinct")

    if base["emitted_box_count"] != 19 or segmented["emitted_box_count"] != 23:
        raise ValueError("source emission box-count identity drift")
    if base["positive_volume_intersection_count"] != 4:
        raise ValueError("default source overlap signature drift")
    if segmented["positive_volume_intersection_count"] != 0:
        raise ValueError("segmented source overlap signature drift")
    if base["bounds"] != segmented["bounds"]:
        raise ValueError("source emission variants changed assembled bounds")
    if base["receiver_ids"] != segmented["receiver_ids"]:
        raise ValueError("source emission variants changed receiver identities")
    if abs(base["occupied_union_volume_m3"] - segmented["occupied_union_volume_m3"]) > EPS:
        raise ValueError("source emission variants changed occupied union volume")

    negatives = run_negative_controls(profile, contract, contract_sha, emission_mod)

    return {
        "result": "PASS_PROCEDURAL_HEADER_FAMILY_REBOUND_TO_EXPLICIT_EMISSION_VARIANTS",
        "decision": "PRESERVE_DEFAULT_BASE__SEGMENTED_OPT_IN_ONLY__NO_AUTO_ADOPTION",
        "family_id": profile["family_id"],
        "family_schema": profile["schema"],
        "source_hard_surface_head": profile["source_hard_surface_head"],
        "emission_variant_contract_schema": contract["schema"],
        "emission_variant_contract_sha256": contract_sha,
        "selection_policy": contract["selection_policy"],
        "default_variant_id": default_id,
        "default_variant_adoption": base["downstream_adoption"],
        "segmented_variant_id": segmented_id,
        "segmented_variant_adoption": segmented["downstream_adoption"],
        "default_emitted_box_count": base["emitted_box_count"],
        "segmented_emitted_box_count": segmented["emitted_box_count"],
        "default_positive_volume_intersection_count": base["positive_volume_intersection_count"],
        "segmented_positive_volume_intersection_count": segmented["positive_volume_intersection_count"],
        "occupied_union_volume_residual_m3": round(segmented["occupied_union_volume_m3"] - base["occupied_union_volume_m3"], 12),
        "bounds_equal": base["bounds"] == segmented["bounds"],
        "receiver_ids_equal": base["receiver_ids"] == segmented["receiver_ids"],
        "logical_header_output_count": sum(row["default_variant_header_count"] for row in rows),
        "segmented_header_output_count": sum(row["segmented_variant_header_count"] for row in rows),
        "distinct_variant_header_output_digests": len({default_digest, segmented_digest}),
        "default_header_output_digest": default_digest,
        "segmented_header_output_digest": segmented_digest,
        "headers": rows,
        "header_expansion_prerequisite_result": expansion["result"],
        "header_expansion_distinct_front_rear_digests": expansion["distinct_expansion_digests"],
        "negative_controls": negatives,
        "authority": profile["authority"],
        "failure_policy": profile["failure_policy"],
        "truth_boundary": profile["truth_boundary"],
        "non_claims": [
            "automatic downstream adoption of header-segmented-23",
            "Map, Materials, Environment or Runtime acceptance of the segmented variant",
            "arbitrary building-member segmentation",
            "boolean-unioned or global-manifold pavilion topology",
            "architecture, structural engineering or manufacturing validity",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness, or Procedural Design mastery"
        ]
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
        (args.output_dir / "source-emission-variant-contract.json").write_text(
            EMISSION_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (args.output_dir / "procedural-header-family-profile.json").write_text(
            EXPANSION_PROFILE.read_text(encoding="utf-8"), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
