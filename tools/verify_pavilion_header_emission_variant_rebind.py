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
CURRENT_POLICY_MODULE = ROOT / "tools/service_pavilion_current_emission_policy.py"
CURRENT_POLICY_CONTRACT = ROOT / "assets/service_pavilion_001_current_emission_policy.json"
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


def verify_binding(profile, emission_contract, emission_sha, current_policy, policy_sha):
    if profile.get("schema") != "axm.building-header-segment-expansion-family/v0.3":
        raise ValueError("procedural header family schema drift")

    if emission_contract.get("schema") != profile.get("emission_variant_contract_schema"):
        raise ValueError("emission variant contract schema drift")
    if emission_sha != profile.get("emission_variant_contract_sha256"):
        raise ValueError("emission variant contract SHA-256 drift")
    if emission_contract.get("selection_policy") != profile.get("emission_selection_policy"):
        raise ValueError("emission variant selection policy drift")
    if emission_contract.get("default_variant_id") != profile.get("legacy_emission_default_variant_id"):
        raise ValueError("historical emission default drift")

    legacy_id = profile.get("legacy_compatibility_variant_id")
    current_id = profile.get("current_source_variant_id")
    variants = emission_contract.get("variants", {})
    if set(variants) != {legacy_id, current_id}:
        raise ValueError("emission variant allowlist drift")
    if variants[legacy_id].get("downstream_adoption") != profile.get("legacy_emission_default_adoption"):
        raise ValueError("legacy emission adoption metadata drift")
    if variants[current_id].get("downstream_adoption") != profile.get("segmented_variant_legacy_adoption"):
        raise ValueError("historical segmented adoption metadata drift")

    if current_policy.get("schema") != profile.get("current_source_policy_schema"):
        raise ValueError("current-source policy schema drift")
    if policy_sha != profile.get("current_source_policy_sha256"):
        raise ValueError("current-source policy SHA-256 drift")
    if current_policy.get("current_source_variant_id") != current_id:
        raise ValueError("current-source policy no longer selects procedural segmented variant")
    if current_policy.get("legacy_compatibility_variant_id") != legacy_id:
        raise ValueError("legacy compatibility identity drift")
    if current_id == legacy_id:
        raise ValueError("current and legacy procedural identities collapsed")
    if current_policy.get("selection_policy") != profile.get("current_source_selection_policy"):
        raise ValueError("current-source selection policy drift")
    if current_policy.get("historical_build_result_policy") != profile.get("historical_build_result_policy"):
        raise ValueError("historical build-result policy drift")
    if profile.get("source_hard_surface_head") != profile.get("current_source_policy_hard_surface_head"):
        raise ValueError("procedural source head no longer matches current-source policy head")
    if profile.get("procedural_current_source_binding") != "EXPLICIT_REBIND_TO_HEADER_SEGMENTED_23__LEGACY_19_BOX_COMPATIBILITY_RETAINED":
        raise ValueError("procedural current-source binding decision drift")


def _hold(name, fn, controls):
    try:
        fn()
        controls[name] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls[name] = "HOLD: " + str(exc)


def run_negative_controls(profile, emission_contract, emission_sha, current_policy, policy_sha, emission_mod):
    controls = {}

    bad = copy.deepcopy(profile)
    bad["emission_variant_contract_sha256"] = "0" * 64
    _hold("emission_contract_identity_drift", lambda: verify_binding(bad, emission_contract, emission_sha, current_policy, policy_sha), controls)

    bad_contract = copy.deepcopy(emission_contract)
    bad_contract["selection_policy"] = "IMPLICIT_BEST_EFFORT"
    _hold("emission_selection_policy_drift", lambda: verify_binding(profile, bad_contract, emission_sha, current_policy, policy_sha), controls)

    bad_contract = copy.deepcopy(emission_contract)
    bad_contract["default_variant_id"] = profile["current_source_variant_id"]
    _hold("legacy_emission_default_drift", lambda: verify_binding(profile, bad_contract, emission_sha, current_policy, policy_sha), controls)

    bad = copy.deepcopy(profile)
    bad["current_source_policy_sha256"] = "0" * 64
    _hold("current_policy_identity_drift", lambda: verify_binding(bad, emission_contract, emission_sha, current_policy, policy_sha), controls)

    bad_policy = copy.deepcopy(current_policy)
    bad_policy["current_source_variant_id"] = profile["legacy_compatibility_variant_id"]
    _hold("current_source_regression", lambda: verify_binding(profile, emission_contract, emission_sha, bad_policy, policy_sha), controls)

    bad_policy = copy.deepcopy(current_policy)
    bad_policy["selection_policy"] = "BEST_EFFORT_FALLBACK_ALLOWED"
    _hold("current_source_selection_policy_drift", lambda: verify_binding(profile, emission_contract, emission_sha, bad_policy, policy_sha), controls)

    bad_policy = copy.deepcopy(current_policy)
    bad_policy["legacy_compatibility_variant_id"] = profile["current_source_variant_id"]
    _hold("current_legacy_identity_collapse", lambda: verify_binding(profile, emission_contract, emission_sha, bad_policy, policy_sha), controls)

    bad_policy = copy.deepcopy(current_policy)
    bad_policy["historical_build_result_policy"] = "REWRITE_BUILD_RESULT_TO_CURRENT_SOURCE"
    _hold("historical_build_result_policy_drift", lambda: verify_binding(profile, emission_contract, emission_sha, bad_policy, policy_sha), controls)

    try:
        emission_mod.build_variant("silent-best-effort", profile["source_hard_surface_head"])
        controls["unknown_variant_fallback"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["unknown_variant_fallback"] = "HOLD: " + str(exc)

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("current-source policy negative control unexpectedly passed")
    return controls


def build():
    expansion_mod = load_module(EXPANSION_BUILDER, "pavilion_header_expansion_for_current_source_rebind")
    emission_mod = load_module(EMISSION_MODULE, "service_pavilion_emission_variants_for_procedural")
    policy_mod = load_module(CURRENT_POLICY_MODULE, "service_pavilion_current_emission_policy_for_procedural")
    profile = load(EXPANSION_PROFILE)
    emission_contract = load(EMISSION_CONTRACT)
    current_policy = load(CURRENT_POLICY_CONTRACT)
    emission_sha = sha256(EMISSION_CONTRACT)
    policy_sha = sha256(CURRENT_POLICY_CONTRACT)

    expansion = expansion_mod.build()
    if expansion.get("result") != "PASS_SOURCE_EXACT_HEADER_SEGMENT_EXPANSION_FAMILY":
        raise ValueError("header expansion prerequisite is not PASS")
    verify_binding(profile, emission_contract, emission_sha, current_policy, policy_sha)

    policy_receipt = policy_mod.build_evidence(profile["source_hard_surface_head"])
    if policy_receipt.get("result") != "PASS_SEGMENTED_BUILDING_PROMOTED_TO_CURRENT_SOURCE_POLICY_WITH_LEGACY_COMPATIBILITY":
        raise ValueError("source current-emission policy prerequisite is not PASS")

    logical_mod = expansion_mod.load_logical_builder()
    logical_profile = expansion_mod.load(expansion_mod.LOGICAL_PROFILE)
    logical_headers = expansion_mod.find_logical_header_row(logical_mod, logical_profile, profile)
    logical_by_id = {row["id"]: row for row in logical_headers}
    expanded_by_id = {
        row["logical_component_id"]: row["segments"]
        for row in expansion["expansion_rows"]
    }

    legacy_id = profile["legacy_compatibility_variant_id"]
    current_id = profile["current_source_variant_id"]
    legacy = emission_mod.build_variant(legacy_id, profile["source_hard_surface_head"])
    current = emission_mod.build_variant(current_id, profile["source_hard_surface_head"])

    rows = []
    for logical_id in ("front-header", "rear-header"):
        legacy_rows = header_rows(legacy, logical_id)
        current_rows = header_rows(current, logical_id)
        expected_legacy = [logical_by_id[logical_id]]
        expected_current = expanded_by_id[logical_id]
        if not close(legacy_rows, expected_legacy):
            raise ValueError(f"{logical_id}: legacy compatibility variant no longer matches logical procedural header")
        if not close(current_rows, expected_current):
            raise ValueError(f"{logical_id}: current source variant no longer matches procedural expansion")
        rows.append({
            "logical_component_id": logical_id,
            "legacy_compatibility_header_count": len(legacy_rows),
            "current_source_header_count": len(current_rows),
            "legacy_compatibility_header_digest": digest_json(legacy_rows),
            "current_source_header_digest": digest_json(current_rows),
            "legacy_compatibility_headers": legacy_rows,
            "current_source_headers": current_rows,
        })

    legacy_digest = digest_json([row["legacy_compatibility_headers"] for row in rows])
    current_digest = digest_json([row["current_source_headers"] for row in rows])
    if legacy_digest == current_digest:
        raise ValueError("current and legacy procedural header outputs are not materially distinct")

    if legacy["emitted_box_count"] != 19 or current["emitted_box_count"] != 23:
        raise ValueError("source emission box-count identity drift")
    if legacy["positive_volume_intersection_count"] != 4:
        raise ValueError("legacy source overlap signature drift")
    if current["positive_volume_intersection_count"] != 0:
        raise ValueError("current segmented source overlap signature drift")
    if legacy["bounds"] != current["bounds"]:
        raise ValueError("source emission variants changed assembled bounds")
    if legacy["receiver_ids"] != current["receiver_ids"]:
        raise ValueError("source emission variants changed receiver identities")
    if abs(legacy["occupied_union_volume_m3"] - current["occupied_union_volume_m3"]) > EPS:
        raise ValueError("source emission variants changed occupied union volume")

    negatives = run_negative_controls(
        profile,
        emission_contract,
        emission_sha,
        current_policy,
        policy_sha,
        emission_mod,
    )

    return {
        "result": "PASS_PROCEDURAL_HEADER_FAMILY_REBOUND_TO_CURRENT_SOURCE_POLICY",
        "decision": "PASS_EXPLICIT_CURRENT_SOURCE_REBIND__SEGMENTED_23_CURRENT__LEGACY_19_COMPATIBILITY_HELD",
        "family_id": profile["family_id"],
        "family_schema": profile["schema"],
        "source_hard_surface_head": profile["source_hard_surface_head"],
        "current_source_policy_schema": current_policy["schema"],
        "current_source_policy_sha256": policy_sha,
        "current_source_policy_result": policy_receipt["result"],
        "current_source_selection_policy": current_policy["selection_policy"],
        "historical_build_result_policy": current_policy["historical_build_result_policy"],
        "emission_variant_contract_schema": emission_contract["schema"],
        "emission_variant_contract_sha256": emission_sha,
        "emission_variant_selection_policy": emission_contract["selection_policy"],
        "historical_emission_default_variant_id": emission_contract["default_variant_id"],
        "current_source_variant_id": current_id,
        "legacy_compatibility_variant_id": legacy_id,
        "current_source_emitted_box_count": current["emitted_box_count"],
        "legacy_compatibility_emitted_box_count": legacy["emitted_box_count"],
        "current_source_positive_volume_intersection_count": current["positive_volume_intersection_count"],
        "legacy_compatibility_positive_volume_intersection_count": legacy["positive_volume_intersection_count"],
        "occupied_union_volume_residual_m3": round(current["occupied_union_volume_m3"] - legacy["occupied_union_volume_m3"], 12),
        "bounds_equal": legacy["bounds"] == current["bounds"],
        "receiver_ids_equal": legacy["receiver_ids"] == current["receiver_ids"],
        "legacy_compatibility_header_output_count": sum(row["legacy_compatibility_header_count"] for row in rows),
        "current_source_header_output_count": sum(row["current_source_header_count"] for row in rows),
        "distinct_current_legacy_header_output_digests": len({legacy_digest, current_digest}),
        "legacy_compatibility_header_output_digest": legacy_digest,
        "current_source_header_output_digest": current_digest,
        "headers": rows,
        "header_expansion_prerequisite_result": expansion["result"],
        "header_expansion_distinct_front_rear_digests": expansion["distinct_expansion_digests"],
        "negative_controls": negatives,
        "authority": profile["authority"],
        "failure_policy": profile["failure_policy"],
        "truth_boundary": profile["truth_boundary"],
        "non_claims": [
            "silent rewrite of axm.building-build-result/v0.1 or the historical 19-box tuple",
            "automatic migration of Map, Materials, Environment, Runtime or any other consumer",
            "arbitrary building-member segmentation",
            "boolean-unioned or global-manifold pavilion topology",
            "architecture, structural engineering or manufacturing validity",
            "final material or visual acceptance",
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
        (args.output_dir / "source-current-emission-policy.json").write_text(
            CURRENT_POLICY_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (args.output_dir / "procedural-header-family-profile.json").write_text(
            EXPANSION_PROFILE.read_text(encoding="utf-8"), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
