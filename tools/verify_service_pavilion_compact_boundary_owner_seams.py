#!/usr/bin/env python3
"""Verify that compact Building receiving topology preserves source-owner seam identity.

A source-owner seam is deliberately narrower than a physical manufactured seam: it is
an indexed manifold edge whose two incident triangles carry different exact
``source_component_id`` values. The check protects that source-boundary graph while
allowing Geometry to remove triangulation only inside one owner's planar patch.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_compact_boundary_owner_seam_policy.json"
COMPACT_POLICY_PATH = ROOT / "assets" / "service_pavilion_001_compact_boundary_shell_policy.json"
V2_TOOL = ROOT / "tools" / "build_service_pavilion_boundary_shell_compaction_v2.py"
REFERENCE_GEOMETRY_HEAD = "b6d14d48c59859ae6ff2aaed7dea86b4e00a5402"
COMPACTION_GEOMETRY_HEAD = "16253e7dd2f8cd590667f9631e4b50fdfcc7280d"
EXPECTED_COMPACT_POLICY_BLOB = "ccb06b004f96d1ecfaacd39f093b88cf5194e6c0"
EXPECTED_COMPACT_PAYLOAD = "d51d853ce95216ad66f6ce88cf5bca6aecfa19e22e5e8ce4045cf481b719936a"
EXPECTED_SEAM_DIGEST = "75b865c2b6f0559410549c03ac1c3b44fd00a71b186289d8a2ccb1e06df2c322"
EPS = 1e-9


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


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text())


def load_compact_policy() -> dict:
    return json.loads(COMPACT_POLICY_PATH.read_text())


def build_exact_meshes(exact_head: str):
    v2 = load_module(V2_TOOL, "service_pavilion_boundary_shell_compaction_v2_for_owner_seams")
    base = v2.load_base("service_pavilion_boundary_shell_compaction_base_for_owner_seams")
    donor_module = base.load_module(base.DONOR_TOOL, "service_pavilion_boundary_shell_reference_for_owner_seams")
    donor_shell, donor_result = donor_module.build_evidence(exact_head)
    compact_mesh, compact_result = v2.build_evidence(exact_head)
    return donor_shell, donor_result, compact_mesh, compact_result


def edge_incidence(triangles):
    edges = collections.defaultdict(list)
    for triangle_index, triangle in enumerate(triangles):
        a, b, c = triangle
        for start, end in ((a, b), (b, c), (c, a)):
            key = (start, end) if start < end else (end, start)
            edges[key].append(triangle_index)
    return edges


def seam_records(mesh: dict, source_vertex_ids=None):
    vertices = mesh["vertices"]
    triangles = mesh["triangles"]
    owners = mesh["triangle_owners"]
    if len(triangles) != len(owners):
        raise ValueError("triangle-owner cardinality drift")
    if source_vertex_ids is None:
        source_vertex_ids = list(range(len(vertices)))
    if len(source_vertex_ids) != len(vertices):
        raise ValueError("source-vertex provenance cardinality drift")
    if len(set(source_vertex_ids)) != len(source_vertex_ids):
        raise ValueError("source-vertex provenance is not one-to-one")

    rows = []
    same_owner_internal_edge_count = 0
    incidence = edge_incidence(triangles)
    for (a, b), incident in incidence.items():
        if len(incident) != 2:
            raise ValueError(f"receiving mesh is not closed manifold at edge {(a, b)} incidence={len(incident)}")
        owner_a = owners[incident[0]].get("source_component_id")
        owner_b = owners[incident[1]].get("source_component_id")
        if not owner_a or not owner_b:
            raise ValueError("source-component provenance missing on seam observer input")
        if owner_a == owner_b:
            same_owner_internal_edge_count += 1
            continue

        source_a = int(source_vertex_ids[a])
        source_b = int(source_vertex_ids[b])
        pair = sorted((owner_a, owner_b))
        source_edge = sorted((source_a, source_b))
        endpoints = {
            source_a: [float(value) for value in vertices[a]],
            source_b: [float(value) for value in vertices[b]],
        }
        rows.append({
            "owner_pair": pair,
            "source_edge": source_edge,
            "endpoints_by_source_id": {str(key): endpoints[key] for key in sorted(endpoints)},
            "length_m": math.dist(vertices[a], vertices[b]),
        })

    rows.sort(key=lambda row: (row["owner_pair"], row["source_edge"]))
    identity_rows = [
        {"owner_pair": row["owner_pair"], "source_edge": row["source_edge"]}
        for row in rows
    ]
    pair_stats = collections.defaultdict(lambda: {"edge_count": 0, "length_m": 0.0})
    for row in rows:
        key = "|".join(row["owner_pair"])
        pair_stats[key]["edge_count"] += 1
        pair_stats[key]["length_m"] += row["length_m"]
    pair_stats = {
        key: {
            "edge_count": value["edge_count"],
            "length_m": value["length_m"],
        }
        for key, value in sorted(pair_stats.items())
    }
    return {
        "records": rows,
        "identity_rows": identity_rows,
        "identity_sha256": canonical_sha256(identity_rows),
        "owner_seam_edge_count": len(rows),
        "owner_pair_count": len(pair_stats),
        "total_owner_seam_length_m": sum(row["length_m"] for row in rows),
        "same_owner_internal_edge_count": same_owner_internal_edge_count,
        "pair_stats": pair_stats,
    }


def verify(policy: dict, compact_policy: dict, donor_shell: dict, donor_result: dict, compact_mesh: dict, compact_result: dict) -> dict:
    if policy.get("schema") != "axm.building-compact-boundary-owner-seam-policy/v0.1":
        raise ValueError("owner-seam policy schema drift")
    if policy.get("asset_id") != "service-pavilion-001":
        raise ValueError("owner-seam policy asset drift")
    if policy.get("semantic_source_variant_id") != "header-segmented-23":
        raise ValueError("semantic source variant drift")

    binding = policy.get("compact_receiving_policy", {})
    if binding.get("schema") != "axm.building-compact-boundary-shell-policy/v0.1":
        raise ValueError("compact receiving-policy schema drift")
    if binding.get("git_blob_sha") != EXPECTED_COMPACT_POLICY_BLOB:
        raise ValueError("compact receiving-policy blob drift")
    if binding.get("reference_representation_id") != "boundary-only-union-shell-001":
        raise ValueError("reference representation identity drift")
    if binding.get("compact_representation_id") != "boundary-only-union-shell-conforming-compact-v2-001":
        raise ValueError("compact representation identity drift")

    if compact_policy.get("schema") != binding["schema"]:
        raise ValueError("loaded compact receiving-policy schema mismatch")
    if compact_policy.get("reference_representation", {}).get("representation_id") != binding["reference_representation_id"]:
        raise ValueError("loaded reference representation mismatch")
    if compact_policy.get("compact_representation", {}).get("representation_id") != binding["compact_representation_id"]:
        raise ValueError("loaded compact representation mismatch")
    if compact_policy.get("selection_policy") != "EXPLICIT_RECEIVING_REPRESENTATION_ID_REQUIRED__NO_DEFAULT_OR_IMPLICIT_FALLBACK":
        raise ValueError("compact receiving selection boundary weakened")

    lineage = policy.get("geometry_lineage", {})
    if lineage.get("reference_geometry_head") != REFERENCE_GEOMETRY_HEAD:
        raise ValueError("reference Geometry head drift")
    if lineage.get("compaction_geometry_head") != COMPACTION_GEOMETRY_HEAD:
        raise ValueError("compaction Geometry head drift")
    if lineage.get("compact_payload_sha256") != EXPECTED_COMPACT_PAYLOAD:
        raise ValueError("compact payload pin drift")
    if compact_result.get("candidate", {}).get("payload_sha256") != EXPECTED_COMPACT_PAYLOAD:
        raise ValueError("rebuilt compact payload identity drift")
    if donor_result.get("result") != "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE":
        raise ValueError("reference boundary-shell prerequisite is not PASS")
    if compact_result.get("result") != "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_COLLINEAR_CHAIN_V2":
        raise ValueError("compact Geometry prerequisite is not PASS")

    if policy.get("owner_seam_definition") != "MANIFOLD_EDGE_INCIDENT_TO_EXACTLY_TWO_TRIANGLES_WITH_DIFFERENT_SOURCE_COMPONENT_ID":
        raise ValueError("owner-seam definition drift")
    if policy.get("owner_seam_identity_basis") != "SORTED_SOURCE_COMPONENT_PAIR_PLUS_SORTED_DONOR_SOURCE_VERTEX_IDS":
        raise ValueError("owner-seam identity basis drift")
    if policy.get("preservation_policy") != "EXACT_OWNER_SEAM_IDENTITY_AND_GEOMETRY_REQUIRED_ON_COMPACT_V2":
        raise ValueError("owner-seam preservation policy weakened")
    if policy.get("same_owner_internal_policy") != "MAY_CHANGE_INSIDE_ONE_OWNER_PLANAR_PATCH_SUBJECT_TO_EXISTING_GEOMETRY_GATES":
        raise ValueError("same-owner internal-triangulation boundary drift")
    if policy.get("physical_seam_inference") != "NOT_CLAIMED_NO_GAP_BEVEL_WELD_FASTENER_OR_MATERIAL_BOUNDARY_INFERRED":
        raise ValueError("physical seam authority silently expanded")
    if policy.get("downstream_evidence_policy") != "OWNER_SEAM_PRESERVATION_DOES_NOT_TRANSFER_MATERIAL_NORMAL_TANGENT_UV_TRANSPORT_RUNTIME_OR_VISUAL_PASS":
        raise ValueError("downstream evidence transfer boundary weakened")

    donor = seam_records(donor_shell)
    compact = seam_records(compact_mesh, compact_mesh.get("source_vertex_ids"))

    expected_count = int(policy.get("expected_owner_seam_edge_count", -1))
    expected_pairs = int(policy.get("expected_owner_pair_count", -1))
    expected_length = float(policy.get("expected_total_owner_seam_length_m", -1.0))
    expected_digest = policy.get("expected_owner_seam_identity_sha256")
    for label, observed in (("reference", donor), ("compact", compact)):
        if observed["owner_seam_edge_count"] != expected_count:
            raise ValueError(f"{label} owner-seam edge count drift")
        if observed["owner_pair_count"] != expected_pairs:
            raise ValueError(f"{label} owner-pair count drift")
        if abs(observed["total_owner_seam_length_m"] - expected_length) > EPS:
            raise ValueError(f"{label} total owner-seam length drift")
        if observed["identity_sha256"] != expected_digest or observed["identity_sha256"] != EXPECTED_SEAM_DIGEST:
            raise ValueError(f"{label} owner-seam identity digest drift")

    reference_keys = {
        (tuple(row["owner_pair"]), tuple(row["source_edge"])): row
        for row in donor["records"]
    }
    compact_keys = {
        (tuple(row["owner_pair"]), tuple(row["source_edge"])): row
        for row in compact["records"]
    }
    missing = sorted(set(reference_keys) - set(compact_keys))
    added = sorted(set(compact_keys) - set(reference_keys))
    if missing:
        raise ValueError(f"compact v2 lost source-owner seam identities: {missing[:3]}")
    if added:
        raise ValueError(f"compact v2 added source-owner seam identities: {added[:3]}")

    maximum_endpoint_residual_m = 0.0
    maximum_length_residual_m = 0.0
    for key, reference_row in reference_keys.items():
        compact_row = compact_keys[key]
        maximum_length_residual_m = max(
            maximum_length_residual_m,
            abs(reference_row["length_m"] - compact_row["length_m"]),
        )
        for source_id, reference_position in reference_row["endpoints_by_source_id"].items():
            compact_position = compact_row["endpoints_by_source_id"].get(source_id)
            if compact_position is None:
                raise ValueError("compact v2 lost seam endpoint source identity")
            maximum_endpoint_residual_m = max(
                maximum_endpoint_residual_m,
                math.dist(reference_position, compact_position),
            )
    if maximum_endpoint_residual_m > EPS:
        raise ValueError("compact v2 moved a source-owner seam endpoint")
    if maximum_length_residual_m > EPS:
        raise ValueError("compact v2 changed source-owner seam segment length")
    if compact["pair_stats"] != donor["pair_stats"]:
        raise ValueError("compact v2 changed source-owner seam pair distribution")
    if compact["same_owner_internal_edge_count"] >= donor["same_owner_internal_edge_count"]:
        raise ValueError("compact v2 no longer removes any same-owner internal triangulation edges")

    return {
        "schema": policy["schema"],
        "result": "PASS_SOURCE_OWNED_COMPACT_BOUNDARY_OWNER_SEAM_GRAPH_PRESERVED",
        "asset_id": policy["asset_id"],
        "policy_revision": policy["policy_revision"],
        "semantic_source_variant_id": policy["semantic_source_variant_id"],
        "reference_representation_id": binding["reference_representation_id"],
        "compact_representation_id": binding["compact_representation_id"],
        "owner_seam_definition": policy["owner_seam_definition"],
        "owner_seam_identity_basis": policy["owner_seam_identity_basis"],
        "preservation_policy": policy["preservation_policy"],
        "same_owner_internal_policy": policy["same_owner_internal_policy"],
        "physical_seam_inference": policy["physical_seam_inference"],
        "downstream_evidence_policy": policy["downstream_evidence_policy"],
        "metrics": {
            "reference_owner_seam_edge_count": donor["owner_seam_edge_count"],
            "compact_owner_seam_edge_count": compact["owner_seam_edge_count"],
            "owner_pair_count": compact["owner_pair_count"],
            "total_owner_seam_length_m": compact["total_owner_seam_length_m"],
            "owner_seam_identity_sha256": compact["identity_sha256"],
            "missing_owner_seam_identities": len(missing),
            "added_owner_seam_identities": len(added),
            "maximum_seam_endpoint_residual_m": maximum_endpoint_residual_m,
            "maximum_seam_length_residual_m": maximum_length_residual_m,
            "reference_same_owner_internal_edge_count": donor["same_owner_internal_edge_count"],
            "compact_same_owner_internal_edge_count": compact["same_owner_internal_edge_count"],
            "same_owner_internal_edge_reduction": donor["same_owner_internal_edge_count"] - compact["same_owner_internal_edge_count"],
        },
        "owner_pair_stats": compact["pair_stats"],
        "policy_sha256": canonical_sha256(policy),
        "truth_boundary": (
            "The exact compact v2 receiving option preserves the reference boundary shell's indexed cross-source-owner seam graph by donor source-vertex identity and geometry. "
            "Geometry may remove triangulation only inside one source owner's planar patch under its existing structural gates. This owner-boundary graph is representational evidence only: it does not assert a physical gap, bevel, weld, fastener, material border, manufacturing joint or visual acceptance."
        ),
        "non_claims": [
            "physical seam gap, bevel, chamfer, weld, fastener, gasket or material boundary",
            "manufacturing process, assembly order, tolerance, load or sealing validity",
            "normal, tangent, UV, texture or material equivalence",
            "Technical Art transport, Environment adoption, Runtime performance or target-device acceptance",
            "Art Direction or Visual QA acceptance",
            "semantic source replacement or automatic compact-v2 adoption",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness or Hard-Surface mastery"
        ],
    }


def rejected(fn) -> str:
    try:
        fn()
    except (ValueError, KeyError, IndexError) as exc:
        return f"REJECTED:{exc}"
    raise AssertionError("negative control unexpectedly accepted")


def build_receipt(exact_head: str) -> dict:
    policy = load_policy()
    compact_policy = load_compact_policy()
    donor_shell, donor_result, compact_mesh, compact_result = build_exact_meshes(exact_head)
    receipt = verify(policy, compact_policy, donor_shell, donor_result, compact_mesh, compact_result)

    seam_edges = []
    incidence = edge_incidence(compact_mesh["triangles"])
    for edge, incident in incidence.items():
        if len(incident) != 2:
            continue
        first = compact_mesh["triangle_owners"][incident[0]]["source_component_id"]
        second = compact_mesh["triangle_owners"][incident[1]]["source_component_id"]
        if first != second:
            seam_edges.append((edge, incident, first, second))
    if not seam_edges:
        raise ValueError("no source-owner seam available for negative control")

    bad_owner = copy.deepcopy(compact_mesh)
    _, incident, first_owner, second_owner = seam_edges[0]
    bad_owner["triangle_owners"][incident[0]]["source_component_id"] = second_owner

    bad_provenance = copy.deepcopy(compact_mesh)
    edge, _, _, _ = seam_edges[0]
    bad_provenance["source_vertex_ids"][edge[0]] = bad_provenance["source_vertex_ids"][edge[1]]

    bad_digest_policy = copy.deepcopy(policy)
    bad_digest_policy["expected_owner_seam_identity_sha256"] = "0" * 64

    bad_authority_policy = copy.deepcopy(policy)
    bad_authority_policy["physical_seam_inference"] = "PHYSICAL_BEVEL_REQUIRED"

    receipt["exact_hard_surface_head"] = exact_head
    receipt["reference_geometry_head"] = REFERENCE_GEOMETRY_HEAD
    receipt["compaction_geometry_head"] = COMPACTION_GEOMETRY_HEAD
    receipt["negative_controls"] = {
        "cross_owner_triangle_relabel": rejected(lambda: verify(policy, compact_policy, donor_shell, donor_result, bad_owner, compact_result)),
        "seam_source_vertex_identity_collapse": rejected(lambda: verify(policy, compact_policy, donor_shell, donor_result, bad_provenance, compact_result)),
        "expected_seam_digest_drift": rejected(lambda: verify(bad_digest_policy, compact_policy, donor_shell, donor_result, compact_mesh, compact_result)),
        "physical_seam_authority_expansion": rejected(lambda: verify(bad_authority_policy, compact_policy, donor_shell, donor_result, compact_mesh, compact_result)),
    }
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    parser.add_argument("--output-dir", default="evidence/service-pavilion-compact-boundary-owner-seams-001")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    receipt = build_receipt(args.exact_head)
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    (output / "policy.json").write_text(json.dumps(load_policy(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
