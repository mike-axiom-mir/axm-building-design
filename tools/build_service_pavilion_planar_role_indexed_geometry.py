#!/usr/bin/env python3
"""Build one deterministic indexed Geometry render domain from Building source split intent.

The parent Hard-Surface lane owns the non-indexed planar-role surface and the exact
render-corner equivalence policy. This Geometry lane realizes that equivalence relation
as an indexed mesh without changing source form, normals, material roles, protected
splits, Environment adoption, Runtime policy or Technical-Art transport behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_indexed_geometry_policy.json"
SPLIT_POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_render_split_policy.json"
SPLIT_TOOL_PATH = ROOT / "tools" / "verify_service_pavilion_planar_role_render_split_policy.py"
EXPECTED_PARENT_HEAD = "0caa9ac9644f027350935240476bd0bf3bb66e18"
EXPECTED_SPLIT_POLICY_BLOB = "5f2130d6286e2ee1b67395b1a753fbfc3eac22ea"
EXPECTED_RESULT = "PASS_SOURCE_INTENT_INDEXED_RENDER_DOMAIN_EXACT_CORNER_RECONSTRUCTION"


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
    if policy.get("schema") != "axm.building-planar-role-indexed-geometry-policy/v0.1":
        raise ValueError("indexed Geometry policy schema drift")
    if policy.get("owner") != "Building Geometry / Topology":
        raise ValueError("indexed Geometry policy owner drift")
    parent = policy.get("parent_representation", {})
    if parent.get("representation_id") != "boundary-only-planar-role-rectangle-render-001":
        raise ValueError("parent representation drift")
    if parent.get("owner_pr") != 11:
        raise ValueError("parent owner PR drift")
    if parent.get("owner_head") != EXPECTED_PARENT_HEAD:
        raise ValueError("parent owner head drift")
    if parent.get("source_split_policy_path") != "assets/service_pavilion_001_planar_role_render_split_policy.json":
        raise ValueError("source split policy path drift")
    if parent.get("source_split_policy_blob_sha") != EXPECTED_SPLIT_POLICY_BLOB:
        raise ValueError("declared source split policy blob drift")
    if git_blob_sha1(SPLIT_POLICY_PATH) != EXPECTED_SPLIT_POLICY_BLOB:
        raise ValueError("source split policy content drift")

    construction = policy.get("construction", {})
    if construction.get("rule") != "ONE_INDEXED_RENDER_VERTEX_PER_EXACT_SOURCE_OWNER_EQUIVALENCE_CLASS":
        raise ValueError("indexed construction rule drift")
    if construction.get("required_equivalence_key") != [
        "MATERIAL_ROLE",
        "EXACT_POSITION",
        "EXACT_CARDINAL_HARD_NORMAL",
        "EXPLICIT_PROTECTED_SPLIT_ID",
    ]:
        raise ValueError("indexed equivalence key drift")
    acceptance = policy.get("acceptance", {})
    if acceptance.get("expected_triangle_corners") != 1008:
        raise ValueError("expected triangle-corner count drift")
    if acceptance.get("expected_render_vertices") != 604:
        raise ValueError("expected render-vertex count drift")
    if acceptance.get("expected_indices") != 1008:
        raise ValueError("expected index count drift")
    if acceptance.get("expected_triangles") != 336:
        raise ValueError("expected triangle count drift")
    if acceptance.get("expected_material_roles") != 5:
        raise ValueError("expected material-role count drift")
    if policy.get("selection_policy") != "GEOMETRY_RENDER_DOMAIN_CANDIDATE_ONLY__NO_ENVIRONMENT_RUNTIME_OR_TRANSPORT_ADOPTION":
        raise ValueError("indexed Geometry selection policy drift")
    return policy


def build_indexed_candidate(records: list[dict], groups: list[dict]) -> dict:
    if len(records) != 1008:
        raise ValueError(f"unexpected source corner count: {len(records)}")
    if len(groups) != 604:
        raise ValueError(f"unexpected source equivalence group count: {len(groups)}")

    corner_to_group: dict[int, int] = {}
    vertices: list[dict] = []
    for vertex_index, group in enumerate(groups):
        members = list(group["member_corner_indices"])
        if not members:
            raise ValueError("empty source equivalence group")
        for corner_index in members:
            if corner_index in corner_to_group:
                raise ValueError("source corner assigned to more than one equivalence group")
            corner_to_group[int(corner_index)] = vertex_index
        vertices.append({
            "vertex_index": vertex_index,
            "source_equivalence_group_id": group["group_id"],
            "material_role": group["material_role"],
            "position": list(group["position"]),
            "normal": list(group["normal"]),
            "protected_split_id": group["protected_split_id"],
            "source_component_ids": list(group["source_component_ids"]),
            "rectangle_ids": list(group["rectangle_ids"]),
            "source_corner_count": int(group["member_count"]),
        })

    if set(corner_to_group) != set(range(len(records))):
        raise ValueError("source equivalence groups do not cover every triangle corner exactly once")

    indices = [corner_to_group[index] for index in range(len(records))]
    triangles = [indices[offset:offset + 3] for offset in range(0, len(indices), 3)]
    triangle_roles = []
    rectangle_ids = []
    for triangle_index in range(len(triangles)):
        triangle_records = records[triangle_index * 3:triangle_index * 3 + 3]
        roles = {record["material_role"] for record in triangle_records}
        rectangles = {record["rectangle_id"] for record in triangle_records}
        if len(roles) != 1:
            raise ValueError("one triangle crosses source material-role boundaries")
        if len(rectangles) != 1:
            raise ValueError("one triangle crosses source rectangle identities")
        triangle_roles.append(next(iter(roles)))
        rectangle_ids.append(next(iter(rectangles)))

    return {
        "schema": "axm.building-planar-role-indexed-geometry-candidate/v0.1",
        "candidate_id": "boundary-only-planar-role-source-intent-indexed-001",
        "parent_representation_id": "boundary-only-planar-role-rectangle-render-001",
        "vertices": vertices,
        "indices": indices,
        "triangles": triangles,
        "triangle_roles": triangle_roles,
        "rectangle_ids": rectangle_ids,
    }


def verify_exact_corner_reconstruction(candidate: dict, records: list[dict]) -> dict:
    vertices = candidate["vertices"]
    indices = candidate["indices"]
    if len(indices) != len(records):
        raise ValueError("indexed candidate corner count drift")
    if len(vertices) != 604:
        raise ValueError("indexed candidate render-vertex count drift")

    mismatch_counts = {
        "position": 0,
        "normal": 0,
        "material_role": 0,
        "protected_split_id": 0,
    }
    for corner_index, record in enumerate(records):
        vertex_index = int(indices[corner_index])
        if not 0 <= vertex_index < len(vertices):
            raise ValueError("indexed candidate contains out-of-range vertex index")
        vertex = vertices[vertex_index]
        if vertex["position"] != record["position"]:
            mismatch_counts["position"] += 1
        if vertex["normal"] != record["normal"]:
            mismatch_counts["normal"] += 1
        if vertex["material_role"] != record["material_role"]:
            mismatch_counts["material_role"] += 1
        if vertex["protected_split_id"] != record["protected_split_id"]:
            mismatch_counts["protected_split_id"] += 1

    if any(mismatch_counts.values()):
        raise ValueError(f"indexed candidate does not reconstruct source corner stream exactly: {mismatch_counts}")

    roles = sorted(set(candidate["triangle_roles"]))
    if len(roles) != 5:
        raise ValueError("indexed candidate material-role count drift")
    if len(candidate["triangles"]) != 336:
        raise ValueError("indexed candidate triangle count drift")

    unique_positions = {tuple(vertex["position"]) for vertex in vertices}
    position_normal_pairs = {(tuple(vertex["position"]), tuple(vertex["normal"])) for vertex in vertices}
    cross_rectangle_vertices = sum(1 for vertex in vertices if len(vertex["rectangle_ids"]) > 1)
    maximum_source_corner_membership = max(vertex["source_corner_count"] for vertex in vertices)

    return {
        "source_triangle_corner_count": len(records),
        "render_vertex_count": len(vertices),
        "index_count": len(indices),
        "triangle_count": len(candidate["triangles"]),
        "material_role_count": len(roles),
        "storage_vertex_reduction_vs_unindexed_corners": len(records) - len(vertices),
        "storage_vertex_reduction_fraction_vs_unindexed_corners": (len(records) - len(vertices)) / len(records),
        "unique_position_count": len(unique_positions),
        "unique_position_normal_pair_count": len(position_normal_pairs),
        "render_vertices_sharing_geometric_position": len(vertices) - len(unique_positions),
        "cross_rectangle_render_vertex_count": cross_rectangle_vertices,
        "maximum_source_corner_membership": maximum_source_corner_membership,
        "position_mismatch_count": 0,
        "normal_mismatch_count": 0,
        "material_role_mismatch_count": 0,
        "protected_split_mismatch_count": 0,
        "exact_corner_stream_reconstruction": True,
    }


def expect_reconstruction_rejection(candidate: dict, records: list[dict]) -> str:
    try:
        verify_exact_corner_reconstruction(candidate, records)
    except ValueError as exc:
        return f"REJECTED:{exc}"
    return "UNEXPECTED_PASS"


def negative_controls(candidate: dict, records: list[dict]) -> dict:
    controls = {}

    missing_index = json.loads(json.dumps(candidate))
    missing_index["indices"].pop()
    controls["missing_corner_index"] = expect_reconstruction_rejection(missing_index, records)

    normal_mutation = json.loads(json.dumps(candidate))
    first_vertex = normal_mutation["vertices"][normal_mutation["indices"][0]]
    first_vertex["normal"] = [0.0, 0.0, 0.0]
    controls["source_normal_mutation"] = expect_reconstruction_rejection(normal_mutation, records)

    role_mutation = json.loads(json.dumps(candidate))
    first_role_vertex = role_mutation["vertices"][role_mutation["indices"][0]]
    original_role = first_role_vertex["material_role"]
    replacement_role = next(role for role in sorted(set(candidate["triangle_roles"])) if role != original_role)
    first_role_vertex["material_role"] = replacement_role
    controls["material_role_mutation"] = expect_reconstruction_rejection(role_mutation, records)

    split_mutation = json.loads(json.dumps(candidate))
    split_vertex = split_mutation["vertices"][split_mutation["indices"][0]]
    split_vertex["protected_split_id"] = "geometry-negative-control"
    controls["protected_split_mutation"] = expect_reconstruction_rejection(split_mutation, records)

    # Prove that at least one geometric position legitimately needs multiple render
    # vertices because the source-owner cardinal hard-normal boundary differs.
    by_position: dict[tuple, set[tuple]] = {}
    for vertex in candidate["vertices"]:
        position = tuple(vertex["position"])
        by_position.setdefault(position, set()).add(tuple(vertex["normal"]))
    hard_edge_positions = [position for position, normals in by_position.items() if len(normals) > 1]
    if not hard_edge_positions:
        controls["hard_normal_boundary_presence"] = "UNEXPECTED_PASS"
    else:
        controls["hard_normal_boundary_presence"] = (
            f"REJECTED:collapsing by position alone would cross source hard-normal boundaries at {len(hard_edge_positions)} positions"
        )

    return controls


def build_evidence(exact_head: str) -> tuple[dict, dict]:
    policy = load_policy()
    split = load_module(SPLIT_TOOL_PATH, "building_planar_role_split_for_geometry")
    retained, split_evidence = split.build_evidence(exact_head)
    if split_evidence.get("result") != "PASS_SOURCE_OWNED_PLANAR_ROLE_RENDER_SPLIT_INTENT":
        raise ValueError("parent source split intent is not PASS")
    if split_evidence.get("source_intent", {}).get("triangle_corner_count") != 1008:
        raise ValueError("parent source corner count drift")
    if split_evidence.get("source_intent", {}).get("equivalence_group_count") != 604:
        raise ValueError("parent source equivalence group count drift")

    records = retained["corner_records"]
    groups = retained["equivalence_groups"]
    candidate = build_indexed_candidate(records, groups)
    metrics = verify_exact_corner_reconstruction(candidate, records)
    controls = negative_controls(candidate, records)
    if not controls or not all(str(value).startswith("REJECTED:") for value in controls.values()):
        raise ValueError(f"one or more indexed Geometry negative controls did not fail closed: {controls}")

    candidate_sha = canonical_sha256(candidate)
    evidence = {
        "schema": "axm.building-planar-role-indexed-geometry-evidence/v0.1",
        "result": EXPECTED_RESULT,
        "exact_head": exact_head,
        "asset_id": "service-pavilion-001",
        "candidate_id": candidate["candidate_id"],
        "parent_hard_surface_head": EXPECTED_PARENT_HEAD,
        "parent_representation_id": candidate["parent_representation_id"],
        "parent_corner_domain_sha256": split_evidence["corner_domain_sha256"],
        "parent_equivalence_grouping_sha256": split_evidence["grouping_sha256"],
        "source_split_policy_blob_sha": EXPECTED_SPLIT_POLICY_BLOB,
        "policy_sha256": hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
        "candidate_sha256": candidate_sha,
        "metrics": metrics,
        "negative_controls": controls,
        "authority": {
            "semantic_source": "BUILDING_HARD_SURFACE",
            "render_domain_construction": "BUILDING_GEOMETRY_TOPOLOGY",
            "environment_adoption": "NOT_GEOMETRY_OWNED",
            "runtime_adoption": "NOT_GEOMETRY_OWNED",
            "transport_acceptance": "NOT_GEOMETRY_OWNED",
            "visual_acceptance": "NOT_GEOMETRY_OWNED",
        },
        "truth_boundary": policy["truth_boundary"],
    }
    return candidate, evidence


def write_obj(candidate: dict, path: Path) -> None:
    lines = [
        "# AXM Building planar-role source-intent indexed Geometry candidate",
        f"# candidate_id {candidate['candidate_id']}",
    ]
    for vertex in candidate["vertices"]:
        x, y, z = vertex["position"]
        lines.append(f"v {x:.9f} {y:.9f} {z:.9f}")
    for vertex in candidate["vertices"]:
        nx, ny, nz = vertex["normal"]
        lines.append(f"vn {nx:.9f} {ny:.9f} {nz:.9f}")

    current_role = None
    for triangle, role in zip(candidate["triangles"], candidate["triangle_roles"]):
        if role != current_role:
            lines.append(f"usemtl {role}")
            current_role = role
        a, b, c = (index + 1 for index in triangle)
        lines.append(f"f {a}//{a} {b}//{b} {c}//{c}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_evidence(output_dir: Path, exact_head: str) -> dict:
    candidate, evidence = build_evidence(exact_head)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "exact-head.txt").write_text(exact_head + "\n", encoding="utf-8")
    (output_dir / "geometry-policy.json").write_text(POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    (output_dir / "indexed-render-domain.json").write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "indexed-render-domain-evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_obj(candidate, output_dir / "indexed-render-domain.obj")
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
