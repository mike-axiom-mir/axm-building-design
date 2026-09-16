#!/usr/bin/env python3
"""Current-source emission policy for service-pavilion-001.

This is deliberately additive. The historical build tuple and
``axm.building-build-result/v0.1`` remain compatibility interfaces. New source
claims can instead bind this policy and explicitly consume its named current
source variant. No downstream consumer is silently migrated.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_current_emission_policy.json"
VARIANTS_PATH = ROOT / "tools" / "service_pavilion_emission_variants.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_policy(policy: dict) -> dict:
    if policy.get("schema") != "axm.building-current-emission-policy/v0.1":
        raise ValueError("current-emission policy schema drift")
    if policy.get("owner") != "Building Hard Surface":
        raise ValueError("current-emission policy owner drift")
    if policy.get("current_source_variant_id") != "header-segmented-23":
        raise ValueError("current Building source variant regressed from segmented representation")
    if policy.get("legacy_compatibility_variant_id") != "base-closed-outward-19":
        raise ValueError("legacy Building compatibility variant drift")
    if policy["current_source_variant_id"] == policy["legacy_compatibility_variant_id"]:
        raise ValueError("current and legacy Building emission identities collapsed")
    if policy.get("selection_policy") != "CURRENT_SOURCE_IS_NAMED__CONSUMER_REBIND_REQUIRED__NO_SILENT_DEFAULT_REWRITE":
        raise ValueError("current-emission consumer rebinding policy drift")
    if policy.get("historical_build_result_policy") != "KEEP_AXM_BUILDING_BUILD_RESULT_V0_1_AT_19_BOXES_FOR_COMPATIBILITY":
        raise ValueError("historical Building compatibility policy drift")
    provenance = policy.get("provenance", {})
    if provenance.get("emission_variant_schema") != "axm.building-emission-variants/v0.1":
        raise ValueError("emission-variant prerequisite schema drift")
    if provenance.get("header_segmentation_schema") != "axm.building-header-segmentation/v0.1":
        raise ValueError("header-segmentation prerequisite schema drift")
    if provenance.get("receiving_result") != "PASS_CURRENT_WORLD_BUILDING_HEADER_SEGMENTATION_BOUNDED_CONTINUITY":
        raise ValueError("receiving-evidence result drift")
    return policy


def load_policy() -> dict:
    return validate_policy(json.loads(POLICY_PATH.read_text(encoding="utf-8")))


def _rejection(policy: dict) -> str:
    try:
        validate_policy(policy)
    except ValueError as exc:
        return "REJECTED:" + str(exc)
    raise ValueError("negative-control policy unexpectedly accepted")


def build_evidence(exact_head: str = "LOCAL_UNBOUND") -> dict:
    policy = load_policy()
    variants = load_module(VARIANTS_PATH, "service_pavilion_emission_variants_for_current_policy")
    variant_contract = variants.load_contract()

    current = variants.build_variant(policy["current_source_variant_id"], exact_head)
    legacy = variants.build_variant(policy["legacy_compatibility_variant_id"], exact_head)

    if variant_contract["schema"] != policy["provenance"]["emission_variant_schema"]:
        raise ValueError("current policy no longer binds exact emission-variant schema")
    if variant_contract["default_variant_id"] != policy["legacy_compatibility_variant_id"]:
        raise ValueError("historical emission default no longer matches declared compatibility variant")
    if current["positive_volume_intersection_count"] != 0:
        raise ValueError("current segmented source retained positive-volume intersections")
    if legacy["positive_volume_intersection_count"] != 4:
        raise ValueError("legacy compatibility overlap signature drift")
    if current["bounds"] != legacy["bounds"]:
        raise ValueError("current source promotion changed assembled bounds")
    if current["receiver_ids"] != legacy["receiver_ids"]:
        raise ValueError("current source promotion changed receiver identity")
    if current["receiver_mount_residual_max_m"] != legacy["receiver_mount_residual_max_m"]:
        raise ValueError("current source promotion changed receiver fit residual")
    union_residual = current["occupied_union_volume_m3"] - legacy["occupied_union_volume_m3"]
    if abs(union_residual) > 1e-9:
        raise ValueError("current source promotion changed occupied union volume")

    regressed = copy.deepcopy(policy)
    regressed["current_source_variant_id"] = "base-closed-outward-19"
    fallback = copy.deepcopy(policy)
    fallback["selection_policy"] = "BEST_EFFORT_FALLBACK_ALLOWED"
    collapsed = copy.deepcopy(policy)
    collapsed["legacy_compatibility_variant_id"] = "header-segmented-23"

    return {
        "result": "PASS_SEGMENTED_BUILDING_PROMOTED_TO_CURRENT_SOURCE_POLICY_WITH_LEGACY_COMPATIBILITY",
        "schema": policy["schema"],
        "exact_hard_surface_head": exact_head,
        "policy_sha256": sha256(POLICY_PATH),
        "current_source_variant_id": policy["current_source_variant_id"],
        "legacy_compatibility_variant_id": policy["legacy_compatibility_variant_id"],
        "selection_policy": policy["selection_policy"],
        "historical_build_result_policy": policy["historical_build_result_policy"],
        "historical_build_result_unchanged": True,
        "current_source": {
            "variant_id": current["variant_id"],
            "source_revision": current["source_revision"],
            "emitted_box_count": current["emitted_box_count"],
            "vertex_count": current["vertex_count"],
            "triangle_count": current["triangle_count"],
            "positive_volume_intersection_count": current["positive_volume_intersection_count"],
            "occupied_union_volume_m3": current["occupied_union_volume_m3"],
            "bounds": current["bounds"],
            "receiver_ids": current["receiver_ids"],
            "receiver_mount_residual_max_m": current["receiver_mount_residual_max_m"],
            "payload_sha256": current["payload_sha256"],
        },
        "legacy_compatibility": {
            "variant_id": legacy["variant_id"],
            "source_revision": legacy["source_revision"],
            "emitted_box_count": legacy["emitted_box_count"],
            "vertex_count": legacy["vertex_count"],
            "triangle_count": legacy["triangle_count"],
            "positive_volume_intersection_count": legacy["positive_volume_intersection_count"],
            "occupied_union_volume_m3": legacy["occupied_union_volume_m3"],
            "bounds": legacy["bounds"],
            "receiver_ids": legacy["receiver_ids"],
            "receiver_mount_residual_max_m": legacy["receiver_mount_residual_max_m"],
            "payload_sha256": legacy["payload_sha256"],
        },
        "comparison": {
            "occupied_union_volume_residual_m3": round(union_residual, 12),
            "emitted_box_delta": current["emitted_box_count"] - legacy["emitted_box_count"],
            "vertex_delta": current["vertex_count"] - legacy["vertex_count"],
            "triangle_delta": current["triangle_count"] - legacy["triangle_count"],
            "positive_volume_intersection_delta": current["positive_volume_intersection_count"] - legacy["positive_volume_intersection_count"],
            "bounds_equal": current["bounds"] == legacy["bounds"],
            "receiver_ids_equal": current["receiver_ids"] == legacy["receiver_ids"],
            "receiver_residual_equal": current["receiver_mount_residual_max_m"] == legacy["receiver_mount_residual_max_m"],
        },
        "negative_controls": {
            "current_source_regression": _rejection(regressed),
            "implicit_fallback_policy": _rejection(fallback),
            "current_legacy_identity_collapse": _rejection(collapsed),
        },
        "receiving_evidence": policy["provenance"],
        "downstream_policy": "CURRENT_SOURCE_PROMOTED__NO_CONSUMER_AUTO_MIGRATION__EXACT_REBIND_AND_RETEST_REQUIRED",
        "non_claims": [
            "silent rewrite of axm.building-build-result/v0.1 or the historical tuple",
            "automatic downstream migration or current-source claim transfer",
            "boolean-unioned or global vertex-manifold pavilion shell",
            "removal of coplanar internal faces at touching components",
            "architectural, structural or manufacturing validity",
            "final material or visual acceptance",
            "target-device runtime, collision, navigation or gameplay acceptance",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness, or Hard-Surface mastery"
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    parser.add_argument("--output-dir", default="evidence/service-pavilion-001/current-emission-policy-001")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    receipt = build_evidence(args.exact_head)
    (out / "current-emission-policy.json").write_text(
        POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
