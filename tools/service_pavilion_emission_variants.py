#!/usr/bin/env python3
"""Explicit source-owned emission variants for service-pavilion-001.

The historical builder and ``axm.building-build-result/v0.1`` stay unchanged.
This module gives receiving domains one fail-closed name for the existing 19-box
representation and one for the already-source-owned 23-box header-segmented
representation, so downstream adoption can be explicit rather than inferred
from a proof builder or tuple shape.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "assets" / "service_pavilion_001_emission_variants.json"
BUILD_RESULT_PATH = ROOT / "tools" / "service_pavilion_build_result.py"
SEGMENTATION_PATH = ROOT / "tools" / "build_service_pavilion_header_segmentation.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_contract() -> dict:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract.get("schema") != "axm.building-emission-variants/v0.1":
        raise ValueError("Building emission-variant schema drift")
    if contract.get("owner") != "Building Hard Surface":
        raise ValueError("Building emission-variant owner drift")
    if contract.get("selection_policy") != "EXPLICIT_VARIANT_ID_NO_FALLBACK":
        raise ValueError("Building emission-variant selection policy drift")
    variants = contract.get("variants", {})
    if set(variants) != {"base-closed-outward-19", "header-segmented-23"}:
        raise ValueError("Building emission-variant allowlist drift")
    if contract.get("default_variant_id") != "base-closed-outward-19":
        raise ValueError("Building default emission variant drift")
    return contract


def _context(exact_head: str):
    contract = load_contract()
    build_result = load_module(BUILD_RESULT_PATH, "service_pavilion_build_result_for_variants")
    segmentation = load_module(SEGMENTATION_PATH, "service_pavilion_header_segmentation_for_variants")

    named = build_result.build_named()
    build_result.require_fields(
        named,
        ("pavilion", "panel", "receiver_fits", "bounds_min", "bounds_max", "topology_summary"),
    )
    if named["schema"] != contract["provenance"]["base_build_result_schema"]:
        raise ValueError("base named-result schema no longer matches emission contract")

    base_module, segmented_boxes, segmented_receipt = segmentation.build(exact_head)
    segmentation_contract = json.loads(segmentation.CONTRACT_PATH.read_text(encoding="utf-8"))
    if segmentation_contract.get("schema") != contract["provenance"]["header_segmentation_schema"]:
        raise ValueError("header segmentation schema no longer matches emission contract")
    if segmentation_contract.get("successor_revision") != contract["provenance"]["header_segmentation_revision"]:
        raise ValueError("header segmentation revision no longer matches emission contract")

    pavilion = base_module.load(base_module.PAVILION)
    panel = base_module.load(base_module.PANEL)
    fits = [base_module.fit_panel(interface, panel) for interface in pavilion["interfaces"]]
    base_boxes = segmentation.source_boxes(base_module, pavilion, panel, fits)

    return contract, named, segmentation, base_module, base_boxes, segmented_boxes, segmented_receipt


def _box_payload(box: dict) -> dict:
    return {
        "id": box["id"],
        "source_component_id": box["source_component_id"],
        "role": box["role"],
        "vertices": box["vertices"],
        "lo": box["lo"],
        "hi": box["hi"],
    }


def build_variant(variant_id: str, exact_head: str = "LOCAL_UNBOUND") -> dict:
    contract, named, segmentation, base_module, base_boxes, segmented_boxes, segmented_receipt = _context(exact_head)
    declared = contract["variants"]
    if variant_id not in declared:
        raise ValueError(f"unsupported Building emission variant: {variant_id!r}")

    if variant_id == "base-closed-outward-19":
        boxes = base_boxes
        topology = segmentation.topology_summary(base_module, boxes)
        positive_overlaps = segmentation.positive_overlaps(boxes)
        occupied_union_volume = segmented_receipt["occupied_union"]["source_union_volume_m3"]
        revision = contract["provenance"]["base_source_revision"]
        segment_map = {}
    elif variant_id == "header-segmented-23":
        boxes = segmented_boxes
        topology = segmented_receipt["topology"]
        positive_overlaps = segmentation.positive_overlaps(boxes)
        occupied_union_volume = segmented_receipt["occupied_union"]["candidate_union_volume_m3"]
        revision = segmented_receipt["successor_revision"]
        segment_map = segmented_receipt["segment_map"]
    else:  # pragma: no cover - allowlist gate above is authoritative
        raise AssertionError("unreachable emission variant")

    spec = declared[variant_id]
    observed = {
        "box_count": len(boxes),
        "vertex_count": topology["vertex_count"],
        "triangle_count": topology["triangle_count"],
    }
    for key, expected_key in (
        ("box_count", "expected_box_count"),
        ("vertex_count", "expected_vertex_count"),
        ("triangle_count", "expected_triangle_count"),
    ):
        if observed[key] != spec[expected_key]:
            raise ValueError(f"{variant_id}: {key} drift {observed[key]} != {spec[expected_key]}")

    payload = {
        "schema": contract["schema"],
        "asset_id": contract["asset_id"],
        "owner": contract["owner"],
        "variant_id": variant_id,
        "representation": spec["representation"],
        "source_revision": revision,
        "downstream_adoption": spec["downstream_adoption"],
        "selection_policy": contract["selection_policy"],
        "default_variant_id": contract["default_variant_id"],
        "default_build_result_schema": named["schema"],
        "default_build_result_topology_object_count": named["topology_summary"]["object_count"],
        "logical_component_count": len(named["pavilion"]["components"]),
        "emitted_box_count": len(boxes),
        "vertex_count": topology["vertex_count"],
        "triangle_count": topology["triangle_count"],
        "topology": topology,
        "positive_volume_intersection_count": len(positive_overlaps),
        "positive_volume_intersections": positive_overlaps,
        "occupied_union_volume_m3": occupied_union_volume,
        "bounds": segmentation.combined_bounds(boxes),
        "receiver_ids": [fit["interface_id"] for fit in named["receiver_fits"]],
        "receiver_mount_residual_max_m": max(fit["mount_pattern_residual_m"] for fit in named["receiver_fits"]),
        "segment_map": segment_map,
        "boxes": [_box_payload(box) for box in boxes],
        "contract_sha256": sha256(CONTRACT_PATH),
        "header_segmentation_contract_sha256": segmented_receipt["segmentation_contract_sha256"],
        "exact_hard_surface_head": exact_head,
        "truth_boundary": contract["truth_boundary"],
    }
    payload["payload_sha256"] = canonical_sha256({k: v for k, v in payload.items() if k != "payload_sha256"})
    return payload


def build_evidence(exact_head: str = "LOCAL_UNBOUND") -> dict:
    contract = load_contract()
    base = build_variant("base-closed-outward-19", exact_head)
    segmented = build_variant("header-segmented-23", exact_head)

    if base["bounds"] != segmented["bounds"]:
        raise ValueError("header-segmented variant changed assembled bounds")
    if base["receiver_ids"] != segmented["receiver_ids"]:
        raise ValueError("header-segmented variant changed receiver identity")
    if base["receiver_mount_residual_max_m"] != segmented["receiver_mount_residual_max_m"]:
        raise ValueError("header-segmented variant changed receiver fit residual")
    if abs(base["occupied_union_volume_m3"] - segmented["occupied_union_volume_m3"]) > 1e-9:
        raise ValueError("header-segmented variant changed occupied union volume")
    if base["positive_volume_intersection_count"] != 4:
        raise ValueError("base overlap signature drift")
    if segmented["positive_volume_intersection_count"] != 0:
        raise ValueError("segmented variant retained positive-volume intersections")
    if len(segmented["segment_map"].get("front-header", [])) != 3:
        raise ValueError("front-header segment mapping drift")
    if len(segmented["segment_map"].get("rear-header", [])) != 3:
        raise ValueError("rear-header segment mapping drift")

    unknown_rejection = None
    try:
        build_variant("silent-best-effort", exact_head)
    except ValueError as exc:
        unknown_rejection = "REJECTED:" + str(exc)
    if not unknown_rejection:
        raise ValueError("unknown emission variant did not fail closed")

    return {
        "result": "PASS_EXPLICIT_SOURCE_OWNED_BUILDING_EMISSION_VARIANT_SELECTION",
        "exact_hard_surface_head": exact_head,
        "schema": contract["schema"],
        "selection_policy": contract["selection_policy"],
        "default_variant_id": contract["default_variant_id"],
        "default_build_result_unchanged": True,
        "base_variant": base,
        "header_segmented_variant": segmented,
        "comparison": {
            "occupied_union_volume_residual_m3": round(
                segmented["occupied_union_volume_m3"] - base["occupied_union_volume_m3"], 12
            ),
            "emitted_box_delta": segmented["emitted_box_count"] - base["emitted_box_count"],
            "vertex_delta": segmented["vertex_count"] - base["vertex_count"],
            "triangle_delta": segmented["triangle_count"] - base["triangle_count"],
            "positive_volume_intersection_delta": segmented["positive_volume_intersection_count"] - base["positive_volume_intersection_count"],
            "bounds_equal": base["bounds"] == segmented["bounds"],
            "receiver_ids_equal": base["receiver_ids"] == segmented["receiver_ids"],
            "receiver_residual_equal": base["receiver_mount_residual_max_m"] == segmented["receiver_mount_residual_max_m"],
        },
        "unknown_variant_control": unknown_rejection,
        "downstream_policy": "NO_AUTOMATIC_ADOPTION__CONSUMER_MUST_EXPLICITLY_SELECT_AND_RETEST",
        "non_claims": [
            "Map or other downstream adoption of header-segmented-23",
            "material-role mapping for segmented header surfaces",
            "target-host render or runtime performance acceptance",
            "boolean-unioned or global vertex-manifold pavilion shell",
            "architectural, structural or manufacturing validity",
            "collision, navigation or gameplay acceptance",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness, or Hard-Surface mastery"
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    parser.add_argument("--output-dir", default="evidence/service-pavilion-001/emission-variants-001")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    receipt = build_evidence(args.exact_head)
    (out / "emission-variant-contract.json").write_text(
        CONTRACT_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
