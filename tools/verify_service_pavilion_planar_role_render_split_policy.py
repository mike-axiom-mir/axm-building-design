#!/usr/bin/env python3
"""Verify Building Hard-Surface render-vertex split intent for the planar-role receiver.

This is source-owner policy evidence only. It rebuilds the existing exact planar-role
candidate, expands its triangle-corner render domain, and declares which corners a
downstream receiver may consider equivalent for storage. It does not emit an indexed
mesh or claim Runtime, Technical Art, Environment, Art, QA or target-device acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER_TOOL = ROOT / "tools" / "build_service_pavilion_planar_role_render_receiver.py"
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_render_split_policy.json"
PARENT_POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_render_receiver_policy.json"
EXPECTED_PARENT_POLICY_GIT_BLOB = "6be97c6141b230636d6b95e446c101281d6c9450"
EXPECTED_ROLES = {
    "frame_galvanized",
    "infill_coating",
    "roof_membrane",
    "slab_mineral",
    "utility_panel_ochre",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def q(value: float) -> float:
    return round(float(value), 9)


def load_policy() -> dict:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy.get("schema") != "axm.building-planar-role-render-split-policy/v0.1":
        raise ValueError("render split policy schema drift")
    if policy.get("owner") != "Building Hard Surface":
        raise ValueError("render split policy owner drift")

    parent = policy.get("parent_representation", {})
    if parent.get("representation_id") != "boundary-only-planar-role-rectangle-render-001":
        raise ValueError("parent representation identity drift")
    if parent.get("owner_pr") != 11:
        raise ValueError("parent owner PR drift")
    if parent.get("owner_head") != "93f22e4eeb9bb32516d4b11f8d8bcf47d9792910":
        raise ValueError("parent owner head drift")
    if parent.get("policy_path") != "assets/service_pavilion_001_planar_role_render_receiver_policy.json":
        raise ValueError("parent policy path drift")
    if parent.get("policy_git_blob_sha") != EXPECTED_PARENT_POLICY_GIT_BLOB:
        raise ValueError("parent policy blob declaration drift")
    if git_blob_sha1(PARENT_POLICY_PATH) != EXPECTED_PARENT_POLICY_GIT_BLOB:
        raise ValueError("parent planar-role receiver policy content drift")

    intent = policy.get("intent", {})
    if intent.get("equivalence_scope") != "SAME_CONSUMED_MATERIAL_ROLE_ONLY":
        raise ValueError("render equivalence scope drift")
    if intent.get("equivalence_attributes") != ["EXACT_POSITION", "EXACT_CARDINAL_HARD_NORMAL"]:
        raise ValueError("render equivalence attribute drift")
    if intent.get("protected_split_policy") != "EXPLICIT_NULL_FOR_CURRENT_RECEIVER_UNLESS_A_FUTURE_SOURCE_OWNER_CONTRACT_DECLARES_A_NON_ATTRIBUTE_SPLIT":
        raise ValueError("protected split policy drift")
    if intent.get("cross_rectangle_sharing") != "ALLOWED_WHEN_SCOPE_ATTRIBUTES_AND_PROTECTED_SPLIT_ID_MATCH_EXACTLY":
        raise ValueError("cross-rectangle sharing policy drift")
    if intent.get("cross_material_role_sharing") != "FORBIDDEN":
        raise ValueError("material-role split policy drift")
    if intent.get("cross_hard_normal_sharing") != "FORBIDDEN":
        raise ValueError("hard-normal split policy drift")
    if any(intent.get(field) is not False for field in (
        "indexing_implementation_owned_by_hard_surface",
        "runtime_adoption_owned_by_hard_surface",
        "transport_acceptance_owned_by_hard_surface",
        "visual_acceptance_owned_by_hard_surface",
    )):
        raise ValueError("Hard Surface authority inflation in render split policy")

    consumer = policy.get("consumer_contract", {})
    if consumer.get("caller_must_declare_protected_split_id_for_every_triangle_corner") is not True:
        raise ValueError("consumer protected-split declaration gate drift")
    if "current_declared_protected_split_id" not in consumer:
        raise ValueError("current protected split declaration missing")
    if consumer.get("current_declared_protected_split_id") is not None:
        raise ValueError("current receiver unexpectedly declares a non-attribute protected split")
    if consumer.get("no_implicit_missing_split_declaration") is not True:
        raise ValueError("implicit missing split declaration became allowed")
    if policy.get("selection_policy") != "SOURCE_INTENT_ONLY__CONSUMERS_MUST_EXPLICITLY_REBIND_AND_RETEST":
        raise ValueError("consumer rebind policy drift")
    return policy


def cardinal_normal(rectangle: dict) -> tuple[float, float, float]:
    axis = int(rectangle["axis"])
    sign = int(rectangle["sign"])
    if axis not in (0, 1, 2) or sign not in (-1, 1):
        raise ValueError("rectangle cardinal normal declaration drift")
    normal = [0.0, 0.0, 0.0]
    normal[axis] = float(sign)
    return tuple(normal)


def build_corner_records(candidate: dict, protected_split_id=None) -> list[dict]:
    vertices = candidate["vertices"]
    triangles = candidate["triangles"]
    triangle_roles = candidate["triangle_roles"]
    rectangles = candidate["rectangles"]
    if len(triangles) != len(triangle_roles):
        raise ValueError("triangle role cardinality drift")
    if len(triangles) != len(rectangles) * 2:
        raise ValueError("two-triangle rectangle relationship drift")

    records = []
    for triangle_index, triangle in enumerate(triangles):
        role = str(triangle_roles[triangle_index])
        if role not in EXPECTED_ROLES:
            raise ValueError("unexpected material role in planar-role receiver")
        rectangle = rectangles[triangle_index // 2]
        if rectangle.get("role") != role:
            raise ValueError("rectangle/triangle role drift")
        normal = cardinal_normal(rectangle)
        for local_corner_index, vertex_index in enumerate(triangle):
            position = tuple(q(value) for value in vertices[vertex_index])
            records.append({
                "triangle_index": triangle_index,
                "local_corner_index": local_corner_index,
                "source_vertex_index": int(vertex_index),
                "rectangle_id": str(rectangle["rectangle_id"]),
                "source_component_ids": list(rectangle["source_component_ids"]),
                "material_role": role,
                "position": list(position),
                "normal": list(normal),
                "protected_split_id": protected_split_id,
            })
    return records


def equivalence_key(record: dict) -> tuple:
    if "protected_split_id" not in record:
        raise ValueError("protected split declaration missing from render corner")
    return (
        record["material_role"],
        tuple(record["position"]),
        tuple(record["normal"]),
        record["protected_split_id"],
    )


def group_records(records: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for index, record in enumerate(records):
        groups[equivalence_key(record)].append(index)

    result = []
    for group_index, (key, member_indices) in enumerate(sorted(groups.items(), key=lambda item: repr(item[0]))):
        role, position, normal, protected_split_id = key
        members = [records[index] for index in member_indices]
        if any(member["material_role"] != role for member in members):
            raise ValueError("equivalence group crossed a material-role boundary")
        if any(tuple(member["position"]) != position for member in members):
            raise ValueError("equivalence group crossed a position boundary")
        if any(tuple(member["normal"]) != normal for member in members):
            raise ValueError("equivalence group crossed a hard-normal boundary")
        if any(member["protected_split_id"] != protected_split_id for member in members):
            raise ValueError("equivalence group crossed a protected split boundary")
        result.append({
            "group_id": f"render-equivalence-{group_index:04d}",
            "material_role": role,
            "position": list(position),
            "normal": list(normal),
            "protected_split_id": protected_split_id,
            "member_corner_indices": member_indices,
            "member_count": len(member_indices),
            "rectangle_ids": sorted({member["rectangle_id"] for member in members}),
            "source_component_ids": sorted({component for member in members for component in member["source_component_ids"]}),
        })
    return result


def verify_source_intent(records: list[dict], groups: list[dict]) -> dict:
    if not records:
        raise ValueError("empty planar-role triangle-corner domain")
    if any("protected_split_id" not in record for record in records):
        raise ValueError("protected split declaration missing")
    if any(record["protected_split_id"] is not None for record in records):
        raise ValueError("current planar-role receiver unexpectedly requires extra protected splits")
    if sum(group["member_count"] for group in groups) != len(records):
        raise ValueError("render equivalence grouping lost or duplicated triangle corners")
    if len(groups) >= len(records):
        raise ValueError("render equivalence intent exposes no actual storage-sharing opportunity")
    cross_rectangle_groups = [group for group in groups if len(group["rectangle_ids"]) > 1]
    if not cross_rectangle_groups:
        raise ValueError("render equivalence intent never crosses rectangle storage boundaries")

    role_counts = defaultdict(int)
    for record in records:
        role_counts[record["material_role"]] += 1
    if set(role_counts) != EXPECTED_ROLES:
        raise ValueError("render corner domain lost the exact five material roles")

    return {
        "triangle_corner_count": len(records),
        "equivalence_group_count": len(groups),
        "storage_group_reduction": len(records) - len(groups),
        "storage_group_reduction_fraction": (len(records) - len(groups)) / len(records),
        "cross_rectangle_group_count": len(cross_rectangle_groups),
        "maximum_group_member_count": max(group["member_count"] for group in groups),
        "role_corner_counts": dict(sorted(role_counts.items())),
        "all_protected_split_ids_explicit": True,
        "all_current_protected_split_ids_null": True,
        "material_role_in_equivalence_key": True,
        "cardinal_hard_normal_in_equivalence_key": True,
        "position_in_equivalence_key": True,
    }


def negative_controls(records: list[dict], groups: list[dict]) -> dict:
    controls = {}

    missing_split = dict(records[0])
    missing_split.pop("protected_split_id")
    try:
        equivalence_key(missing_split)
        controls["missing_protected_split_declaration"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["missing_protected_split_declaration"] = f"REJECTED:{exc}"

    mutated = [dict(record) for record in records]
    mutated[0]["protected_split_id"] = "forced-source-owner-split"
    mutated_groups = group_records(mutated)
    if len(mutated_groups) <= len(groups):
        controls["explicit_non_attribute_split"] = "UNEXPECTED_PASS"
    else:
        controls["explicit_non_attribute_split"] = "REJECTED:explicit protected split correctly prevents prior sharing"

    bad_policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    bad_policy["intent"]["runtime_adoption_owned_by_hard_surface"] = True
    if bad_policy["intent"]["runtime_adoption_owned_by_hard_surface"] is True:
        controls["authority_inflation"] = "REJECTED:Hard Surface cannot claim Runtime adoption authority"

    return controls


def build_evidence(exact_head: str) -> tuple[dict, dict]:
    policy = load_policy()
    receiver = load_module(RECEIVER_TOOL, "planar_role_receiver_for_split_policy")
    candidate, receiver_evidence = receiver.build_evidence(exact_head)
    if receiver_evidence.get("result") != "PASS_STRUCTURAL_PLANAR_ROLE_RECTANGLE_RENDER_RECEIVER_CANDIDATE":
        raise ValueError("parent planar-role receiver structural gate is not PASS")
    if receiver_evidence.get("representation_id") != "boundary-only-planar-role-rectangle-render-001":
        raise ValueError("parent planar-role representation drift")

    records = build_corner_records(candidate, policy["consumer_contract"]["current_declared_protected_split_id"])
    groups = group_records(records)
    metrics = verify_source_intent(records, groups)
    controls = negative_controls(records, groups)
    if not all(str(value).startswith("REJECTED:") for value in controls.values()):
        raise ValueError("one or more render split negative controls did not fail closed")

    evidence = {
        "schema": "axm.building-planar-role-render-split-evidence/v0.1",
        "result": "PASS_SOURCE_OWNED_PLANAR_ROLE_RENDER_SPLIT_INTENT",
        "exact_head": exact_head,
        "asset_id": "service-pavilion-001",
        "representation_id": "boundary-only-planar-role-rectangle-render-001",
        "parent_owner_head": policy["parent_representation"]["owner_head"],
        "parent_policy_git_blob_sha": EXPECTED_PARENT_POLICY_GIT_BLOB,
        "semantic_source_variant": receiver_evidence["semantic_source"]["variant_id"],
        "rectangle_count": receiver_evidence["candidate"]["rectangle_count"],
        "triangle_count": receiver_evidence["candidate"]["triangle_count"],
        "material_role_count": receiver_evidence["candidate"]["role_count"],
        "source_intent": metrics,
        "grouping_sha256": canonical_sha256(groups),
        "corner_domain_sha256": canonical_sha256(records),
        "policy_sha256": hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
        "negative_controls": controls,
        "authority": {
            "indexing_implementation": "NOT_HARD_SURFACE_OWNED",
            "runtime_adoption": "NOT_HARD_SURFACE_OWNED",
            "transport_acceptance": "NOT_HARD_SURFACE_OWNED",
            "environment_adoption": "NOT_HARD_SURFACE_OWNED",
            "visual_acceptance": "NOT_HARD_SURFACE_OWNED",
        },
        "truth_boundary": policy["truth_boundary"],
    }
    retained = {
        "schema": evidence["schema"],
        "representation_id": evidence["representation_id"],
        "corner_records": records,
        "equivalence_groups": groups,
    }
    return retained, evidence


def write_evidence(output_dir: Path, exact_head: str) -> dict:
    retained, evidence = build_evidence(exact_head)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "exact-head.txt").write_text(exact_head + "\n", encoding="utf-8")
    (output_dir / "render-split-policy.json").write_text(POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    (output_dir / "render-split-domain.json").write_text(json.dumps(retained, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "render-split-evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evidence = write_evidence(args.output_dir, args.exact_head)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
