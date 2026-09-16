#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

import service_pavilion_build_result as contract


def stable_digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="evidence/service-pavilion-001")
    ap.add_argument("--exact-head", default="LOCAL_UNBOUND")
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    legacy = contract.builder.build()
    named = contract.from_legacy_output(legacy)

    # Prove every current named payload is exactly the corresponding legacy value.
    equality = {}
    for index, field in enumerate(contract.CURRENT_REQUIRED_FIELDS):
        equality[field] = named[field] == legacy[index]
    if not all(equality.values()):
        raise ValueError(f"named/legacy field mismatch: {equality}")

    # Prove a future trailing extension does not change any existing named field.
    future_output = tuple(legacy) + ({"future_extension": "opaque-to-v0.1-consumers"},)
    future_named = contract.from_legacy_output(future_output)
    future_equal = all(future_named[field] == named[field] for field in contract.CURRENT_REQUIRED_FIELDS)
    if not future_equal or future_named["opaque_trailing_extension_count"] != 1:
        raise ValueError("opaque trailing extension changed existing named build-result fields")

    # Fail-closed controls.
    try:
        contract.from_legacy_output(tuple(legacy[:8]))
        missing_topology_control = "UNEXPECTED_PASS"
    except ValueError as exc:
        missing_topology_control = "REJECTED: " + str(exc)
    if not missing_topology_control.startswith("REJECTED:"):
        raise ValueError("missing topology summary unexpectedly passed v0.1 contract")

    missing_named = dict(named)
    missing_named.pop("receiver_fits")
    try:
        contract.require_fields(missing_named, ("receiver_fits", "topology_summary"))
        missing_named_control = "UNEXPECTED_PASS"
    except ValueError as exc:
        missing_named_control = "REJECTED: " + str(exc)
    if not missing_named_control.startswith("REJECTED:"):
        raise ValueError("missing named dependency unexpectedly passed")

    schema_drift = dict(named)
    schema_drift["schema"] = "axm.building-build-result/v9.9"
    try:
        contract.require_fields(schema_drift, ("pavilion",))
        schema_control = "UNEXPECTED_PASS"
    except ValueError as exc:
        schema_control = "REJECTED: " + str(exc)
    if not schema_control.startswith("REJECTED:"):
        raise ValueError("schema drift unexpectedly passed")

    retained_named = {
        "schema": named["schema"],
        "field_names": list(contract.CURRENT_REQUIRED_FIELDS),
        "historical_prefix_fields": list(contract.HISTORICAL_PREFIX_FIELDS),
        "legacy_output_count_observed": named["legacy_output_count_observed"],
        "opaque_trailing_extension_count": named["opaque_trailing_extension_count"],
        "pavilion_asset_id": named["pavilion"]["asset_id"],
        "pavilion_source_revision": named["pavilion"]["source_revision"],
        "panel_asset_id": named["panel"]["asset_id"],
        "receiver_ids": [row["interface_id"] for row in named["receiver_fits"]],
        "bounds_min": named["bounds_min"],
        "bounds_max": named["bounds_max"],
        "readable_path_gap_m": named["readable_path_gap_m"],
        "topology_revision": named["topology_summary"]["revision"],
        "topology_object_count": named["topology_summary"]["object_count"],
        "legacy_current_required_payload_sha256": stable_digest(list(legacy[:9])),
        "named_current_required_payload_sha256": stable_digest([named[field] for field in contract.CURRENT_REQUIRED_FIELDS]),
    }
    if retained_named["legacy_current_required_payload_sha256"] != retained_named["named_current_required_payload_sha256"]:
        raise ValueError("named result digest differs from exact legacy payload digest")

    receipt = {
        "result": "PASS_VERSIONED_NAMED_BUILD_RESULT_WITH_LEGACY_TUPLE_COMPATIBILITY",
        "exact_hard_surface_head": args.exact_head,
        "contract": retained_named,
        "current_named_legacy_equality": equality,
        "future_trailing_extension_control": "PASS_EXISTING_NAMED_FIELDS_UNCHANGED",
        "missing_topology_control": missing_topology_control,
        "missing_named_dependency_control": missing_named_control,
        "schema_drift_control": schema_control,
        "truth_boundary": (
            "This proves only that the current Building source result can be addressed by versioned names while the "
            "historical tuple remains reproducible, and that one opaque trailing tuple extension does not change the "
            "existing named v0.1 fields."
        ),
        "non_claims": [
            "consumer migration in Map, Procedural, Materials or Runtime",
            "retirement of the historical tuple interface",
            "generic cross-domain producer-result standard",
            "Universal Creation or Profession Fabric promotion",
            "geometry, topology, material, runtime or gameplay improvement",
            "CANON, production readiness, or Hard-Surface mastery",
        ],
    }

    (out / "build-result-contract.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
