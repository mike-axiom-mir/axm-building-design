#!/usr/bin/env python3
"""Hard-Surface source-owner gate for the compact Building boundary-shell option.

The 23-box header-segmented representation remains semantic source authority. The
existing boundary-only shell remains the reference receiving representation. This gate
source-owns Geometry's exact conforming compact v2 mesh only as a second explicit
receiving option: no default, no fallback, and no downstream PASS transfer.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_compact_boundary_shell_policy.json"
COMPACTION_TOOL = ROOT / "tools" / "build_service_pavilion_boundary_shell_compaction_v2.py"
REFERENCE_GEOMETRY_HEAD = "b6d14d48c59859ae6ff2aaed7dea86b4e00a5402"
REFERENCE_POLICY_HEAD = "4f223e95fa95a8eb2e07d24ab1a2f4d3db70df55"
COMPACTION_GEOMETRY_HEAD = "16253e7dd2f8cd590667f9631e4b50fdfcc7280d"
EXPECTED_COMPACT_PAYLOAD = "d51d853ce95216ad66f6ce88cf5bca6aecfa19e22e5e8ce4045cf481b719936a"
EPS = 1e-9


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text())


def load_compaction_module():
    spec = importlib.util.spec_from_file_location("service_pavilion_boundary_shell_compaction_v2_policy_donor", COMPACTION_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {COMPACTION_TOOL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_compaction_receipt(exact_head: str):
    module = load_compaction_module()
    return module.build_evidence(exact_head)


def verify_policy(policy: dict, candidate_mesh: dict, geometry_result: dict) -> dict:
    if policy.get("schema") != "axm.building-compact-boundary-shell-policy/v0.1":
        raise ValueError("compact boundary-shell policy schema drift")
    if policy.get("asset_id") != "service-pavilion-001":
        raise ValueError("compact boundary-shell policy asset drift")

    semantic = policy.get("semantic_source", {})
    if semantic.get("schema") != "axm.building-current-emission-policy/v0.1":
        raise ValueError("semantic-source schema drift")
    if semantic.get("variant_id") != "header-segmented-23":
        raise ValueError("semantic source must remain current header-segmented-23")
    if semantic.get("emitted_box_count") != 23:
        raise ValueError("semantic source box-count drift")
    if semantic.get("authority") != "SEMANTIC_SOURCE_OF_TRUTH":
        raise ValueError("semantic source authority weakened")

    reference = policy.get("reference_representation", {})
    if reference.get("schema") != "axm.building-current-source-boundary-shell/v0.1":
        raise ValueError("reference representation schema drift")
    if reference.get("representation_id") != "boundary-only-union-shell-001":
        raise ValueError("reference representation identity drift")
    if reference.get("geometry_evidence_head") != REFERENCE_GEOMETRY_HEAD:
        raise ValueError("reference Geometry evidence head drift")
    if reference.get("source_owner_policy_head") != REFERENCE_POLICY_HEAD:
        raise ValueError("reference Hard-Surface policy head drift")
    if reference.get("status") != "SOURCE_OWNED_DERIVED_REFERENCE_RECEIVING_REPRESENTATION_NOT_SEMANTIC_SOURCE":
        raise ValueError("reference representation authority drift")

    compact = policy.get("compact_representation", {})
    if compact.get("schema") != "axm.building-boundary-shell-conforming-compaction/v0.2":
        raise ValueError("compact representation schema drift")
    if compact.get("representation_id") != "boundary-only-union-shell-conforming-compact-v2-001":
        raise ValueError("compact representation identity drift")
    if compact.get("geometry_evidence_head") != COMPACTION_GEOMETRY_HEAD:
        raise ValueError("compact Geometry evidence head drift")
    if compact.get("donor_representation_id") != reference["representation_id"]:
        raise ValueError("compact donor representation drift")
    if compact.get("expected_payload_sha256") != EXPECTED_COMPACT_PAYLOAD:
        raise ValueError("compact payload identity drift")
    if compact.get("status") != "SOURCE_OWNED_DERIVED_COMPACT_RECEIVING_OPTION_NOT_DEFAULT":
        raise ValueError("compact representation adoption/authority drift")

    if policy.get("selection_policy") != "EXPLICIT_RECEIVING_REPRESENTATION_ID_REQUIRED__NO_DEFAULT_OR_IMPLICIT_FALLBACK":
        raise ValueError("explicit receiving-representation selection policy drift")
    if policy.get("semantic_authority_policy") != "RECEIVING_REPRESENTATION_NEVER_REPLACES_HEADER_SEGMENTED_23_SEMANTIC_AUTHORITY":
        raise ValueError("semantic authority boundary drift")
    if policy.get("provenance_policy") != "PRESERVE_SOURCE_COMPONENT_ID_AND_DONOR_VERTEX_PROVENANCE_ON_COMPACT_V2":
        raise ValueError("compact provenance policy drift")
    if policy.get("evidence_transfer_policy") != "NO_DOWNSTREAM_PASS_TRANSFER_ACROSS_REFERENCE_V1_OR_COMPACT_V2_IDENTITIES__EXACT_CONSUMER_REBIND_REQUIRED":
        raise ValueError("downstream evidence transfer policy weakened")

    downstream = policy.get("current_downstream_state", {})
    if downstream.get("materials_reference_or_v1_evidence") != "DOES_NOT_COVER_COMPACT_V2":
        raise ValueError("historical Materials evidence was silently transferred to compact v2")
    for key in ("environment_adoption", "technical_art_transport", "runtime_acceptance", "visual_qa_art_acceptance"):
        if downstream.get(key) != "NOT_CLAIMED":
            raise ValueError(f"downstream acceptance silently claimed: {key}")

    if geometry_result.get("schema") != compact["schema"]:
        raise ValueError("Geometry result schema does not match compact policy")
    if geometry_result.get("result") != "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_COLLINEAR_CHAIN_V2":
        raise ValueError("Geometry compact prerequisite is not PASS")

    donor = geometry_result.get("donor", {})
    current = geometry_result.get("candidate", {})
    v1 = geometry_result.get("historical_v1_control", {})
    if donor.get("semantic_source_variant_id") != semantic["variant_id"]:
        raise ValueError("Geometry donor semantic-source variant drift")
    if donor.get("vertex_count") != 1420 or donor.get("triangle_count") != 2884:
        raise ValueError("reference boundary-shell topology identity drift")
    if current.get("vertex_count") != 1004 or current.get("triangle_count") != 2052:
        raise ValueError("compact v2 topology identity drift")
    if v1.get("vertex_count") != 1402 or v1.get("triangle_count") != 2848:
        raise ValueError("historical v1 control identity drift")
    if current.get("payload_sha256") != compact["expected_payload_sha256"]:
        raise ValueError("compact v2 payload does not match source-owned policy")
    if current.get("vertex_count", 0) >= donor.get("vertex_count", 0):
        raise ValueError("compact v2 no longer reduces reference vertices")
    if current.get("triangle_count", 0) >= donor.get("triangle_count", 0):
        raise ValueError("compact v2 no longer reduces reference triangles")
    if current.get("vertex_count", 0) >= v1.get("vertex_count", 0):
        raise ValueError("compact v2 no longer improves historical v1 vertices")
    if current.get("triangle_count", 0) >= v1.get("triangle_count", 0):
        raise ValueError("compact v2 no longer improves historical v1 triangles")
    if current.get("bounds") != donor.get("bounds"):
        raise ValueError("compact v2 bounds drift")
    if abs(float(current.get("signed_volume_m3", 0.0)) - float(donor.get("signed_volume_m3", 0.0))) > EPS:
        raise ValueError("compact v2 occupied volume drift")
    if abs(float(current.get("surface_area_m2", 0.0)) - float(donor.get("surface_area_m2", 0.0))) > EPS:
        raise ValueError("compact v2 boundary area drift")
    if current.get("triangle_component_count") != donor.get("solid_component_count"):
        raise ValueError("compact v2 solid-component count drift")
    if current.get("source_component_owner_count") != donor.get("source_component_owner_count"):
        raise ValueError("compact v2 source-owner coverage drift")
    if current.get("source_component_owner_count") != 19:
        raise ValueError("compact v2 source-owner cardinality drift")
    if float(current.get("maximum_source_component_area_residual_m2", 1.0)) > EPS:
        raise ValueError("compact v2 source-owner area residual drift")
    if float(current.get("max_patch_area_residual_m2", 1.0)) > EPS:
        raise ValueError("compact v2 planar-patch area residual drift")
    for key in (
        "boundary_edge_count",
        "nonmanifold_edge_count",
        "orientation_conflict_edge_count",
        "degenerate_triangle_count",
        "isolated_vertex_count",
        "disconnected_vertex_fan_count",
    ):
        if current.get(key) != 0:
            raise ValueError(f"compact v2 structural gate failed: {key}={current.get(key)}")
    if current.get("max_vertex_fan_components") != 1:
        raise ValueError("compact v2 vertex-fan connectivity drift")

    if len(candidate_mesh.get("vertices", [])) != current["vertex_count"]:
        raise ValueError("compact v2 mesh vertex cardinality drift")
    if len(candidate_mesh.get("triangles", [])) != current["triangle_count"]:
        raise ValueError("compact v2 mesh triangle cardinality drift")
    if len(candidate_mesh.get("source_vertex_ids", [])) != current["vertex_count"]:
        raise ValueError("compact v2 donor-vertex provenance cardinality drift")
    if len(set(candidate_mesh.get("source_vertex_ids", []))) != current["vertex_count"]:
        raise ValueError("compact v2 donor-vertex provenance is not one-to-one")
    owners = candidate_mesh.get("triangle_owners", [])
    if len(owners) != current["triangle_count"]:
        raise ValueError("compact v2 triangle-owner cardinality drift")
    if any(not row.get("source_component_id") for row in owners):
        raise ValueError("compact v2 lost source-component provenance")

    vertex_reduction = donor["vertex_count"] - current["vertex_count"]
    triangle_reduction = donor["triangle_count"] - current["triangle_count"]
    return {
        "schema": policy["schema"],
        "result": "PASS_SOURCE_OWNED_COMPACT_BOUNDARY_SHELL_RECEIVING_OPTION",
        "asset_id": policy["asset_id"],
        "policy_revision": policy["policy_revision"],
        "semantic_source": copy.deepcopy(semantic),
        "reference_representation": copy.deepcopy(reference),
        "compact_representation": copy.deepcopy(compact),
        "selection_policy": policy["selection_policy"],
        "semantic_authority_policy": policy["semantic_authority_policy"],
        "provenance_policy": policy["provenance_policy"],
        "evidence_transfer_policy": policy["evidence_transfer_policy"],
        "current_downstream_state": copy.deepcopy(downstream),
        "metrics": {
            "reference_vertex_count": donor["vertex_count"],
            "reference_triangle_count": donor["triangle_count"],
            "compact_vertex_count": current["vertex_count"],
            "compact_triangle_count": current["triangle_count"],
            "vertex_reduction": vertex_reduction,
            "triangle_reduction": triangle_reduction,
            "vertex_reduction_percent": 100.0 * vertex_reduction / donor["vertex_count"],
            "triangle_reduction_percent": 100.0 * triangle_reduction / donor["triangle_count"],
            "historical_v1_vertex_count": v1["vertex_count"],
            "historical_v1_triangle_count": v1["triangle_count"],
            "solid_component_count": current["triangle_component_count"],
            "source_component_owner_count": current["source_component_owner_count"],
            "signed_volume_m3": current["signed_volume_m3"],
            "surface_area_m2": current["surface_area_m2"],
            "compacted_patch_count": current["compacted_patch_count"],
            "preserved_patch_count": current["preserved_patch_count"],
            "payload_sha256": current["payload_sha256"],
        },
        "policy_sha256": canonical_sha256(policy),
        "truth_boundary": (
            "The 23-box header-segmented Building source remains semantic authority. Hard Surface source-owns the exact Geometry v2 compact "
            "boundary mesh only as an additional explicitly selected receiving option. The reference shell remains separately identifiable, "
            "and no Materials, Environment, Technical Art, Runtime, Art or QA PASS transfers without an exact consumer rebind and retest."
        ),
        "non_claims": [
            "semantic source replacement",
            "automatic replacement of boundary-only-union-shell-001",
            "material, normal, tangent, UV or texture equivalence for compact v2",
            "Technical Art transport or Environment adoption",
            "runtime, draw-call, memory, FPS or target-device acceptance",
            "collision, navigation, physics or gameplay acceptance",
            "architectural engineering, manufacturing validity, loads, tolerances or sealing",
            "generic simplification for rotated, curved or arbitrary meshes",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness or Hard-Surface mastery"
        ],
    }


def rejected(fn) -> str:
    try:
        fn()
    except (ValueError, KeyError) as exc:
        return f"REJECTED:{exc}"
    raise AssertionError("negative control unexpectedly accepted")


def build_receipt(exact_head: str) -> dict:
    policy = load_policy()
    candidate_mesh, geometry_result = build_compaction_receipt(exact_head)
    receipt = verify_policy(policy, candidate_mesh, geometry_result)

    bad_semantic = copy.deepcopy(policy)
    bad_semantic["semantic_source"]["variant_id"] = "base-closed-outward-19"
    bad_compact_head = copy.deepcopy(policy)
    bad_compact_head["compact_representation"]["geometry_evidence_head"] = "0" * 40
    bad_adoption = copy.deepcopy(policy)
    bad_adoption["compact_representation"]["status"] = "SOURCE_ADOPTED_DEFAULT"
    bad_fallback = copy.deepcopy(policy)
    bad_fallback["selection_policy"] = "USE_COMPACT_BY_DEFAULT"
    bad_transfer = copy.deepcopy(policy)
    bad_transfer["evidence_transfer_policy"] = "ALLOW_REFERENCE_PASS_TRANSFER"
    bad_downstream = copy.deepcopy(policy)
    bad_downstream["current_downstream_state"]["materials_reference_or_v1_evidence"] = "COVERS_COMPACT_V2"
    bad_owner_mesh = copy.deepcopy(candidate_mesh)
    bad_owner_mesh["triangle_owners"][0]["source_component_id"] = None
    bad_payload = copy.deepcopy(geometry_result)
    bad_payload["candidate"]["payload_sha256"] = "0" * 64

    receipt["exact_hard_surface_head"] = exact_head
    receipt["reference_geometry_head"] = REFERENCE_GEOMETRY_HEAD
    receipt["reference_policy_head"] = REFERENCE_POLICY_HEAD
    receipt["compaction_geometry_head"] = COMPACTION_GEOMETRY_HEAD
    receipt["negative_controls"] = {
        "semantic_source_variant_drift": rejected(lambda: verify_policy(bad_semantic, candidate_mesh, geometry_result)),
        "compaction_geometry_head_drift": rejected(lambda: verify_policy(bad_compact_head, candidate_mesh, geometry_result)),
        "automatic_compact_adoption": rejected(lambda: verify_policy(bad_adoption, candidate_mesh, geometry_result)),
        "implicit_receiving_fallback": rejected(lambda: verify_policy(bad_fallback, candidate_mesh, geometry_result)),
        "cross_representation_pass_transfer": rejected(lambda: verify_policy(bad_transfer, candidate_mesh, geometry_result)),
        "historical_materials_pass_transfer": rejected(lambda: verify_policy(bad_downstream, candidate_mesh, geometry_result)),
        "source_component_provenance_loss": rejected(lambda: verify_policy(policy, bad_owner_mesh, geometry_result)),
        "compact_payload_identity_drift": rejected(lambda: verify_policy(policy, candidate_mesh, bad_payload)),
    }
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_receipt(args.exact_head)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "exact-head.txt").write_text(args.exact_head + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
