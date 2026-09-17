#!/usr/bin/env python3
"""Diagnose the exact vertex-identity loss caused by dropping hard-normal identity.

This tool is Geometry-owned structural evidence only. It consumes the exact 604-vertex
source-intent indexed candidate from Geometry PR #12 and asks one bounded question:
what partition results if material role, exact position and protected-split identity are
preserved but exact source hard normal is removed from the render-vertex identity key?

It emits no product mesh, replacement normal field or receiver-adoption decision.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_normal_boundary_quotient_policy.json"
PARENT_POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_indexed_geometry_policy.json"
PARENT_TOOL_PATH = ROOT / "tools" / "build_service_pavilion_planar_role_indexed_geometry.py"
EXPECTED_PARENT_HEAD = "b9b4ab63e23b9756ab79597e86ecc41ea75ea8b7"
EXPECTED_PARENT_CANDIDATE_SHA = "f6a831058de66901fd42704b1d8c1cf187b13a0919ae3719c03c4369f107e6c0"
EXPECTED_PARENT_POLICY_BLOB = "ec1c7d39baa606ba02ebcfbd21cf3b3b5b7ed11c"
EXPECTED_RESULT = "PASS_HARD_NORMAL_IDENTITY_REMOVAL_YIELDS_EXACT_312_GROUP_STRUCTURAL_QUOTIENT"


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


def load_policy() -> dict:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy.get("schema") != "axm.building-planar-role-normal-boundary-quotient-policy/v0.1":
        raise ValueError("normal-boundary quotient policy schema drift")
    if policy.get("owner") != "Building Geometry / Topology":
        raise ValueError("normal-boundary quotient policy owner drift")
    parent = policy.get("parent_geometry", {})
    if parent.get("pr") != 12 or parent.get("head") != EXPECTED_PARENT_HEAD:
        raise ValueError("parent Geometry identity drift")
    if parent.get("candidate_id") != "boundary-only-planar-role-source-intent-indexed-001":
        raise ValueError("parent candidate identity drift")
    if parent.get("candidate_sha256") != EXPECTED_PARENT_CANDIDATE_SHA:
        raise ValueError("declared parent candidate digest drift")
    if parent.get("policy_git_blob_sha") != EXPECTED_PARENT_POLICY_BLOB:
        raise ValueError("declared parent policy blob drift")
    if git_blob_sha1(PARENT_POLICY_PATH) != EXPECTED_PARENT_POLICY_BLOB:
        raise ValueError("parent Geometry policy content drift")

    construction = policy.get("construction", {})
    if construction.get("parent_equivalence_key") != [
        "MATERIAL_ROLE",
        "EXACT_POSITION",
        "EXACT_CARDINAL_HARD_NORMAL",
        "EXPLICIT_PROTECTED_SPLIT_ID",
    ]:
        raise ValueError("parent equivalence key drift")
    if construction.get("diagnostic_quotient_key") != [
        "MATERIAL_ROLE",
        "EXACT_POSITION",
        "EXPLICIT_PROTECTED_SPLIT_ID",
    ]:
        raise ValueError("diagnostic quotient key drift")
    if construction.get("drop_only_hard_normal_from_identity") is not True:
        raise ValueError("diagnostic no longer isolates hard-normal identity")
    if construction.get("emit_product_mesh") is not False:
        raise ValueError("diagnostic must not emit a product mesh")
    if policy.get("selection_policy") != "STRUCTURAL_DIAGNOSTIC_ONLY__NO_RENDER_CANDIDATE_NO_SOURCE_REWRITE_NO_RECEIVER_ADOPTION":
        raise ValueError("diagnostic selection policy drift")
    return policy


def build_quotient(candidate: dict) -> dict:
    vertices = candidate["vertices"]
    groups_by_key: dict[tuple, dict] = {}
    ordered_keys: list[tuple] = []

    for vertex in vertices:
        key = (
            vertex["material_role"],
            tuple(vertex["position"]),
            vertex["protected_split_id"],
        )
        if key not in groups_by_key:
            groups_by_key[key] = {
                "quotient_group_index": len(ordered_keys),
                "material_role": vertex["material_role"],
                "position": list(vertex["position"]),
                "protected_split_id": vertex["protected_split_id"],
                "source_render_vertex_indices": [],
                "source_equivalence_group_ids": [],
                "source_normals": [],
            }
            ordered_keys.append(key)
        group = groups_by_key[key]
        group["source_render_vertex_indices"].append(int(vertex["vertex_index"]))
        group["source_equivalence_group_ids"].append(vertex["source_equivalence_group_id"])
        if vertex["normal"] not in group["source_normals"]:
            group["source_normals"].append(list(vertex["normal"]))

    groups = [groups_by_key[key] for key in ordered_keys]
    source_to_quotient: dict[int, int] = {}
    for group in groups:
        group["source_render_vertex_count"] = len(group["source_render_vertex_indices"])
        group["distinct_source_normal_count"] = len(group["source_normals"])
        for source_vertex_index in group["source_render_vertex_indices"]:
            if source_vertex_index in source_to_quotient:
                raise ValueError("parent render vertex appears in more than one quotient group")
            source_to_quotient[source_vertex_index] = group["quotient_group_index"]

    quotient_indices = []
    for source_vertex_index in candidate["indices"]:
        if int(source_vertex_index) not in source_to_quotient:
            raise ValueError("parent corner index references unmapped source render vertex")
        quotient_indices.append(source_to_quotient[int(source_vertex_index)])

    return {
        "schema": "axm.building-planar-role-normal-boundary-quotient/v0.1",
        "diagnostic_id": "source-intent-hard-normal-to-role-position-quotient-001",
        "parent_candidate_id": candidate["candidate_id"],
        "groups": groups,
        "corner_quotient_indices": quotient_indices,
    }


def verify_quotient(candidate: dict, quotient: dict) -> dict:
    vertices = candidate["vertices"]
    groups = quotient["groups"]
    indices = quotient["corner_quotient_indices"]

    if len(vertices) != 604:
        raise ValueError(f"unexpected parent render-vertex count: {len(vertices)}")
    if len(groups) != 312:
        raise ValueError(f"unexpected quotient-group count: {len(groups)}")
    if len(indices) != 1008:
        raise ValueError(f"unexpected quotient corner-index count: {len(indices)}")
    if len(candidate["triangles"]) != 336:
        raise ValueError("parent triangle count drift")

    source_membership: dict[int, int] = {}
    group_size_distribution = Counter()
    per_role_group_count = Counter()
    hard_normal_crossing_groups = 0
    two_normal_groups = 0
    three_normal_groups = 0

    for expected_group_index, group in enumerate(groups):
        if int(group["quotient_group_index"]) != expected_group_index:
            raise ValueError("quotient group ordering drift")
        members = [int(value) for value in group["source_render_vertex_indices"]]
        if not members:
            raise ValueError("empty quotient group")

        normals = []
        for source_vertex_index in members:
            if not 0 <= source_vertex_index < len(vertices):
                raise ValueError("quotient group contains out-of-range source render vertex")
            if source_vertex_index in source_membership:
                raise ValueError("source render vertex assigned to more than one quotient group")
            source_membership[source_vertex_index] = expected_group_index
            source = vertices[source_vertex_index]
            if source["material_role"] != group["material_role"]:
                raise ValueError("quotient group crosses material-role boundary")
            if source["position"] != group["position"]:
                raise ValueError("quotient group crosses exact-position boundary")
            if source["protected_split_id"] != group["protected_split_id"]:
                raise ValueError("quotient group crosses protected-split boundary")
            if source["normal"] not in normals:
                normals.append(source["normal"])

        if len(normals) != int(group["distinct_source_normal_count"]):
            raise ValueError("quotient group source-normal count drift")
        if len(members) != int(group["source_render_vertex_count"]):
            raise ValueError("quotient group member-count drift")
        # Parent Geometry already equivalences same role+position+normal+split.
        # Therefore multiple parent vertices in one diagnostic group must represent
        # distinct hard-normal identities rather than duplicate source classes.
        if len(normals) != len(members):
            raise ValueError("diagnostic quotient merged duplicate parent identities unexpectedly")

        count = len(members)
        group_size_distribution[count] += 1
        per_role_group_count[group["material_role"]] += 1
        if len(normals) > 1:
            hard_normal_crossing_groups += 1
        if len(normals) == 2:
            two_normal_groups += 1
        if len(normals) == 3:
            three_normal_groups += 1

    if set(source_membership) != set(range(len(vertices))):
        raise ValueError("quotient does not cover every parent render vertex exactly once")

    for corner_index, quotient_index in enumerate(indices):
        parent_vertex_index = int(candidate["indices"][corner_index])
        if source_membership[parent_vertex_index] != int(quotient_index):
            raise ValueError("quotient corner stream does not match parent vertex membership")
        group = groups[int(quotient_index)]
        expected_role = candidate["triangle_roles"][corner_index // 3]
        if group["material_role"] != expected_role:
            raise ValueError("quotient corner crosses parent triangle material partition")

    roles = sorted(set(candidate["triangle_roles"]))
    metrics = {
        "parent_render_vertex_count": len(vertices),
        "diagnostic_quotient_group_count": len(groups),
        "corner_index_count": len(indices),
        "triangle_count": len(candidate["triangles"]),
        "material_role_count": len(roles),
        "removed_source_vertex_identities": len(vertices) - len(groups),
        "single_source_group_count": group_size_distribution[1],
        "two_hard_normal_group_count": two_normal_groups,
        "three_hard_normal_group_count": three_normal_groups,
        "hard_normal_crossing_group_count": hard_normal_crossing_groups,
        "maximum_source_hard_normals_per_quotient_group": max(
            int(group["distinct_source_normal_count"]) for group in groups
        ),
        "group_size_distribution": {str(key): value for key, value in sorted(group_size_distribution.items())},
        "per_role_quotient_group_count": dict(sorted(per_role_group_count.items())),
        "every_parent_vertex_maps_exactly_once": True,
        "cross_material_merge_count": 0,
        "cross_position_merge_count": 0,
        "cross_protected_split_merge_count": 0,
    }

    expected = {
        "parent_render_vertex_count": 604,
        "diagnostic_quotient_group_count": 312,
        "corner_index_count": 1008,
        "triangle_count": 336,
        "material_role_count": 5,
        "removed_source_vertex_identities": 292,
        "single_source_group_count": 124,
        "two_hard_normal_group_count": 84,
        "three_hard_normal_group_count": 104,
        "hard_normal_crossing_group_count": 188,
        "maximum_source_hard_normals_per_quotient_group": 3,
    }
    for key, value in expected.items():
        if metrics[key] != value:
            raise ValueError(f"diagnostic quotient metric drift for {key}: {metrics[key]!r} != {value!r}")
    if metrics["group_size_distribution"] != {"1": 124, "2": 84, "3": 104}:
        raise ValueError("diagnostic quotient group-size distribution drift")
    if metrics["per_role_quotient_group_count"] != {
        "frame_galvanized": 200,
        "infill_coating": 24,
        "roof_membrane": 36,
        "slab_mineral": 36,
        "utility_panel_ochre": 16,
    }:
        raise ValueError("diagnostic quotient per-role partition drift")
    return metrics


def expect_rejection(candidate: dict, quotient: dict) -> str:
    try:
        verify_quotient(candidate, quotient)
    except ValueError as exc:
        return f"REJECTED:{exc}"
    return "UNEXPECTED_PASS"


def negative_controls(candidate: dict, quotient: dict) -> dict:
    controls = {}

    missing_member = copy.deepcopy(quotient)
    first_group = missing_member["groups"][0]
    first_group["source_render_vertex_indices"].pop()
    first_group["source_render_vertex_count"] -= 1
    controls["missing_parent_vertex"] = expect_rejection(candidate, missing_member)

    cross_position = copy.deepcopy(quotient)
    target = next(group for group in cross_position["groups"] if group["quotient_group_index"] != 0)
    moved = target["source_render_vertex_indices"].pop()
    target["source_render_vertex_count"] -= 1
    cross_position["groups"][0]["source_render_vertex_indices"].append(moved)
    cross_position["groups"][0]["source_render_vertex_count"] += 1
    controls["cross_position_membership"] = expect_rejection(candidate, cross_position)

    role_drift = copy.deepcopy(quotient)
    role_drift["groups"][0]["material_role"] = "geometry-negative-control"
    controls["material_role_drift"] = expect_rejection(candidate, role_drift)

    split_drift = copy.deepcopy(quotient)
    split_drift["groups"][0]["protected_split_id"] = "geometry-negative-control"
    controls["protected_split_drift"] = expect_rejection(candidate, split_drift)

    return controls


def build_evidence(exact_head: str) -> tuple[dict, dict]:
    policy = load_policy()
    parent = load_module(PARENT_TOOL_PATH, "building_planar_role_indexed_geometry_for_quotient")
    candidate, parent_evidence = parent.build_evidence(exact_head)
    if parent_evidence.get("result") != "PASS_SOURCE_INTENT_INDEXED_RENDER_DOMAIN_EXACT_CORNER_RECONSTRUCTION":
        raise ValueError("parent Geometry indexed-domain evidence is not PASS")
    if parent_evidence.get("candidate_sha256") != EXPECTED_PARENT_CANDIDATE_SHA:
        raise ValueError("parent Geometry candidate digest changed")

    quotient = build_quotient(candidate)
    metrics = verify_quotient(candidate, quotient)
    controls = negative_controls(candidate, quotient)
    if not controls or not all(str(value).startswith("REJECTED:") for value in controls.values()):
        raise ValueError(f"one or more quotient negative controls did not fail closed: {controls}")

    evidence = {
        "schema": "axm.building-planar-role-normal-boundary-quotient-evidence/v0.1",
        "result": EXPECTED_RESULT,
        "exact_head": exact_head,
        "asset_id": "service-pavilion-001",
        "diagnostic_id": quotient["diagnostic_id"],
        "parent_geometry_head": EXPECTED_PARENT_HEAD,
        "parent_candidate_id": candidate["candidate_id"],
        "parent_candidate_sha256": EXPECTED_PARENT_CANDIDATE_SHA,
        "quotient_sha256": canonical_sha256(quotient),
        "metrics": metrics,
        "negative_controls": controls,
        "authority": {
            "semantic_source": "BUILDING_HARD_SURFACE",
            "source_intent_indexed_geometry": "BUILDING_GEOMETRY_TOPOLOGY_PR_12",
            "normal_boundary_quotient_diagnostic": "BUILDING_GEOMETRY_TOPOLOGY",
            "receiver_identity_or_adoption": "NOT_GEOMETRY_OWNED",
            "transport_acceptance": "NOT_GEOMETRY_OWNED",
            "runtime_acceptance": "NOT_GEOMETRY_OWNED",
            "visual_acceptance": "NOT_GEOMETRY_OWNED",
        },
        "interpretation": (
            "The current 604 source-intent render vertices form exactly 312 material-role + exact-position + "
            "protected-split groups when hard-normal identity alone is removed. 188 of those groups cross source "
            "hard-normal boundaries (84 two-way, 104 three-way), removing 292 source render-vertex identities. "
            "This is a structural quotient diagnostic, not permission to perform the collapse or generate smooth normals."
        ),
        "truth_boundary": policy["truth_boundary"],
    }
    return quotient, evidence


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", default="evidence/service-pavilion-planar-role-normal-boundary-quotient-001")
    args = parser.parse_args()

    quotient, evidence = build_evidence(args.exact_head)
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "normal-boundary-quotient-policy.json", load_policy())
    write_json(output / "normal-boundary-quotient-groups.json", quotient)
    write_json(output / "normal-boundary-quotient-evidence.json", evidence)
    (output / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
