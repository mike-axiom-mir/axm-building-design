#!/usr/bin/env python3
"""Verify the Building source-owner boundary between 604 hard-normal classes and a 312 quotient.

Hard Surface owns the exact source render-split intent. Geometry PR #13 is consumed only as
an executable diagnostic proving what identity is lost when exact cardinal hard normals are
removed from the equivalence key. This tool emits no replacement mesh or normal field.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_hard_normal_authority_policy.json"
SOURCE_SPLIT_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_render_split_policy.json"
GEOMETRY_POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_normal_boundary_quotient_policy.json"
GEOMETRY_TOOL_PATH = ROOT / "tools" / "analyze_service_pavilion_planar_role_normal_boundary_quotient.py"

EXPECTED_SOURCE_SPLIT_BLOB = "5f2130d6286e2ee1b67395b1a753fbfc3eac22ea"
EXPECTED_GEOMETRY_POLICY_BLOB = "82253e1491f1e21de4be733919762924fa6610f1"
EXPECTED_GEOMETRY_HEAD = "7dfb1153dc5f80bcbf1b48803f044236d4ebb030"
EXPECTED_QUOTIENT_SHA256 = "7d9e0babf605e31ecb3e4edc92d06bd5460cf52a27f02ccbf32bbae44464688f"
EXPECTED_RESULT = "PASS_SOURCE_OWNED_PLANAR_ROLE_HARD_NORMAL_AUTHORITY_BOUNDARY"


def git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_policy(policy: dict, source_split: dict, geometry_policy: dict, geometry_evidence: dict) -> None:
    if policy.get("schema") != "axm.building-planar-role-hard-normal-authority-policy/v0.1":
        raise ValueError("hard-normal authority policy schema drift")
    if policy.get("owner") != "Building Hard Surface":
        raise ValueError("hard-normal authority owner drift")

    source = policy.get("source_render_split_authority", {})
    if source.get("owner_pr") != 11 or source.get("owner_head") != "0caa9ac9644f027350935240476bd0bf3bb66e18":
        raise ValueError("source render-split authority identity drift")
    if source.get("policy_git_blob_sha") != EXPECTED_SOURCE_SPLIT_BLOB:
        raise ValueError("declared source render-split policy blob drift")
    if git_blob_sha1(SOURCE_SPLIT_PATH) != EXPECTED_SOURCE_SPLIT_BLOB:
        raise ValueError("source render-split policy bytes drift")
    expected_key = [
        "MATERIAL_ROLE",
        "EXACT_POSITION",
        "EXACT_CARDINAL_HARD_NORMAL",
        "EXPLICIT_PROTECTED_SPLIT_ID",
    ]
    if source.get("equivalence_key") != expected_key:
        raise ValueError("source equivalence key drift")
    if source.get("cross_hard_normal_sharing") != "FORBIDDEN":
        raise ValueError("source hard-normal boundary was weakened")
    if source_split.get("schema") != "axm.building-planar-role-render-split-policy/v0.1":
        raise ValueError("source render-split policy schema drift")
    intent = source_split.get("intent", {})
    if intent.get("equivalence_attributes") != ["EXACT_POSITION", "EXACT_CARDINAL_HARD_NORMAL"]:
        raise ValueError("source render-split attributes drift")
    if intent.get("cross_hard_normal_sharing") != "FORBIDDEN":
        raise ValueError("source render-split policy no longer forbids cross-normal sharing")

    donor = policy.get("geometry_diagnostic_donor", {})
    if donor.get("pr") != 13 or donor.get("head") != EXPECTED_GEOMETRY_HEAD:
        raise ValueError("Geometry diagnostic donor identity drift")
    if donor.get("policy_git_blob_sha") != EXPECTED_GEOMETRY_POLICY_BLOB:
        raise ValueError("declared Geometry policy blob drift")
    if git_blob_sha1(GEOMETRY_POLICY_PATH) != EXPECTED_GEOMETRY_POLICY_BLOB:
        raise ValueError("Geometry diagnostic policy bytes drift")
    if donor.get("quotient_sha256") != EXPECTED_QUOTIENT_SHA256:
        raise ValueError("declared Geometry quotient digest drift")
    if geometry_policy.get("selection_policy") != "STRUCTURAL_DIAGNOSTIC_ONLY__NO_RENDER_CANDIDATE_NO_SOURCE_REWRITE_NO_RECEIVER_ADOPTION":
        raise ValueError("Geometry diagnostic authority expanded")
    if geometry_evidence.get("result") != donor.get("required_result"):
        raise ValueError("Geometry diagnostic result is not the pinned PASS")
    if geometry_evidence.get("quotient_sha256") != EXPECTED_QUOTIENT_SHA256:
        raise ValueError("rebuilt Geometry quotient digest drift")

    boundary = policy.get("observed_identity_boundary", {})
    metrics = geometry_evidence.get("metrics", {})
    expected_metrics = {
        "source_intent_render_vertex_count": ("parent_render_vertex_count", 604),
        "role_position_quotient_group_count": ("diagnostic_quotient_group_count", 312),
        "source_render_vertex_identities_removed": ("removed_source_vertex_identities", 292),
        "groups_crossing_source_hard_normal_boundaries": ("hard_normal_crossing_group_count", 188),
        "single_hard_normal_groups": ("single_source_group_count", 124),
        "two_hard_normal_groups": ("two_hard_normal_group_count", 84),
        "three_hard_normal_groups": ("three_hard_normal_group_count", 104),
        "maximum_source_hard_normal_classes_per_group": ("maximum_source_hard_normals_per_quotient_group", 3),
    }
    for policy_key, (metric_key, expected) in expected_metrics.items():
        if boundary.get(policy_key) != expected or metrics.get(metric_key) != expected:
            raise ValueError(f"hard-normal identity boundary drift: {policy_key}")
    if boundary.get("dropped_attribute") != "EXACT_CARDINAL_HARD_NORMAL":
        raise ValueError("dropped source attribute is no longer explicit")
    if boundary.get("source_intent_partition_status") != "SOURCE_AUTHORIZED_RENDER_EQUIVALENCE":
        raise ValueError("604 source-intent authority was weakened")
    if boundary.get("role_position_quotient_status") != "DERIVED_ATTRIBUTE_DROPPING_PARTITION_NOT_SOURCE_EQUIVALENT":
        raise ValueError("312 quotient was silently promoted to source equivalence")

    consumer = policy.get("consumer_policy", {})
    false_required = [
        "equal_312_count_is_source_equivalence",
        "exact_role_position_partition_match_is_source_normal_equivalence",
        "consumer_may_claim_source_hard_normal_preservation_from_this_policy",
        "source_owner_normal_field_rewrite",
        "source_owner_312_mesh_emitted",
        "automatic_receiver_adoption",
        "implicit_fallback",
    ]
    if any(consumer.get(key) is not False for key in false_required):
        raise ValueError("consumer/source authority inflation detected")
    true_required = [
        "consumer_must_declare_own_normal_storage_or_generation_identity",
        "consumer_must_declare_dropped_source_attributes",
        "consumer_must_retest_transport_runtime_and_visual_acceptance",
    ]
    if any(consumer.get(key) is not True for key in true_required):
        raise ValueError("consumer rebind/retest boundary weakened")
    if policy.get("universal_promotion") != "HELD_UNTIL_MATERIALLY_DIFFERENT_MANUFACTURED_DOMAIN_REPRODUCES_THE_SAME_SOURCE_ATTRIBUTE_QUOTIENT_NEED":
        raise ValueError("premature universal promotion")


def expect_rejection(policy: dict, source_split: dict, geometry_policy: dict, geometry_evidence: dict) -> str:
    try:
        validate_policy(policy, source_split, geometry_policy, geometry_evidence)
    except ValueError as exc:
        return f"REJECTED:{exc}"
    return "UNEXPECTED_PASS"


def negative_controls(policy: dict, source_split: dict, geometry_policy: dict, geometry_evidence: dict) -> dict:
    controls = {}

    weakened_source = copy.deepcopy(policy)
    weakened_source["source_render_split_authority"]["cross_hard_normal_sharing"] = "ALLOWED"
    controls["cross_hard_normal_sharing_enabled"] = expect_rejection(
        weakened_source, source_split, geometry_policy, geometry_evidence
    )

    promoted_quotient = copy.deepcopy(policy)
    promoted_quotient["observed_identity_boundary"]["role_position_quotient_status"] = "SOURCE_EQUIVALENT"
    controls["quotient_promoted_to_source_equivalence"] = expect_rejection(
        promoted_quotient, source_split, geometry_policy, geometry_evidence
    )

    false_normal_transfer = copy.deepcopy(policy)
    false_normal_transfer["consumer_policy"]["consumer_may_claim_source_hard_normal_preservation_from_this_policy"] = True
    controls["consumer_source_normal_transfer_claim"] = expect_rejection(
        false_normal_transfer, source_split, geometry_policy, geometry_evidence
    )

    metric_drift = copy.deepcopy(geometry_evidence)
    metric_drift["metrics"]["hard_normal_crossing_group_count"] = 0
    controls["geometry_boundary_loss_hidden"] = expect_rejection(
        policy, source_split, geometry_policy, metric_drift
    )

    automatic_adoption = copy.deepcopy(policy)
    automatic_adoption["consumer_policy"]["automatic_receiver_adoption"] = True
    controls["automatic_receiver_adoption"] = expect_rejection(
        automatic_adoption, source_split, geometry_policy, geometry_evidence
    )
    return controls


def build_evidence(exact_head: str) -> dict:
    policy = load_json(POLICY_PATH)
    source_split = load_json(SOURCE_SPLIT_PATH)
    geometry_policy = load_json(GEOMETRY_POLICY_PATH)
    geometry_module = load_module(GEOMETRY_TOOL_PATH, "building_normal_boundary_quotient_for_hard_surface")
    _quotient, geometry_evidence = geometry_module.build_evidence(exact_head)

    validate_policy(policy, source_split, geometry_policy, geometry_evidence)
    controls = negative_controls(policy, source_split, geometry_policy, geometry_evidence)
    if not controls or not all(str(value).startswith("REJECTED:") for value in controls.values()):
        raise ValueError(f"one or more hard-normal authority negative controls did not fail closed: {controls}")

    return {
        "schema": "axm.building-planar-role-hard-normal-authority-evidence/v0.1",
        "result": EXPECTED_RESULT,
        "exact_head": exact_head,
        "asset_id": "service-pavilion-001",
        "policy_id": policy["policy_id"],
        "policy_sha256": canonical_sha256(policy),
        "source_render_split_policy_git_blob_sha": git_blob_sha1(SOURCE_SPLIT_PATH),
        "geometry_diagnostic_policy_git_blob_sha": git_blob_sha1(GEOMETRY_POLICY_PATH),
        "geometry_diagnostic_head": EXPECTED_GEOMETRY_HEAD,
        "geometry_quotient_sha256": geometry_evidence["quotient_sha256"],
        "metrics": {
            "source_intent_render_vertices": 604,
            "role_position_quotient_groups": 312,
            "source_render_vertex_identities_removed": 292,
            "hard_normal_crossing_groups": 188,
            "single_hard_normal_groups": 124,
            "two_hard_normal_groups": 84,
            "three_hard_normal_groups": 104,
            "maximum_source_hard_normal_classes_per_group": 3,
        },
        "classification": {
            "source_604": "SOURCE_AUTHORIZED_RENDER_EQUIVALENCE",
            "quotient_312": "DERIVED_ATTRIBUTE_DROPPING_PARTITION_NOT_SOURCE_EQUIVALENT",
            "dropped_source_attribute": "EXACT_CARDINAL_HARD_NORMAL",
        },
        "authority": {
            "source_representation_and_hard_normal_intent": "BUILDING_HARD_SURFACE",
            "structural_quotient_diagnostic": "BUILDING_GEOMETRY_TOPOLOGY_PR_13",
            "receiver_identity_or_adoption": "NOT_HARD_SURFACE_OWNED",
            "normal_generation_or_repacking": "NOT_HARD_SURFACE_OWNED",
            "transport_acceptance": "NOT_HARD_SURFACE_OWNED",
            "runtime_acceptance": "NOT_HARD_SURFACE_OWNED",
            "visual_acceptance": "NOT_HARD_SURFACE_OWNED",
        },
        "source_mesh_changed": False,
        "source_normal_field_changed": False,
        "product_312_mesh_emitted": False,
        "consumer_adoption": False,
        "uc_or_profession_fabric_changed": False,
        "negative_controls": controls,
        "truth_boundary": policy["truth_boundary"],
    }


def write_evidence(evidence: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "exact-head.txt").write_text(evidence["exact_head"] + "\n", encoding="utf-8")
    (output_dir / "hard-normal-authority-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for source in (POLICY_PATH, SOURCE_SPLIT_PATH, GEOMETRY_POLICY_PATH):
        (output_dir / source.name).write_bytes(source.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evidence = build_evidence(args.exact_head)
    write_evidence(evidence, args.output_dir)
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
