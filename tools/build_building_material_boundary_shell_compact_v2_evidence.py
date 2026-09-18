#!/usr/bin/env python3
"""Bind Building Materials to the exact source-owned compact-v2 boundary receiver.

This lane does not own Building geometry. It consumes the exact Geometry PR #8
compact-v2 output only after Hard Surface PR #9 has source-owned that identity as
an explicit, non-default material receiving option. The existing five-surface
Building profile is held byte-identical; this builder only proves exact
source-component rebinding and prepares target-host A/B evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "lookdev" / "building_material_profile_001.json"

GEOMETRY_HEAD = "16253e7dd2f8cd590667f9631e4b50fdfcc7280d"
HARD_SURFACE_HEAD = "35d0ba62d7e534b3cd00ac69e99386843ffa3f2e"
OWNER_POLICY_REL = Path("assets/service_pavilion_001_compact_boundary_shell_policy.json")

REFERENCE_SCHEMA = "axm.building-current-source-boundary-shell/v0.1"
COMPACT_SCHEMA = "axm.building-boundary-shell-conforming-compaction/v0.2"
OWNER_SCHEMA = "axm.building-compact-boundary-shell-policy/v0.1"
PAYLOAD_SCHEMA = "axm.building-material-boundary-shell-compaction-lookdev/v0.2"
RECEIPT_SCHEMA = "axm.building-material-boundary-shell-compaction-build-receipt/v0.3"

REFERENCE_ID = "boundary-only-union-shell-001"
COMPACT_ID = "boundary-only-union-shell-conforming-compact-v2-001"
SEMANTIC_SOURCE_ID = "header-segmented-23"
EPS = 1e-9


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def rgba(value: str) -> list[float]:
    if not isinstance(value, str) or len(value) != 9 or not value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex {value!r}")
    return [int(value[i : i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]


def close(a, b) -> bool:
    return abs(float(a) - float(b)) <= EPS


def validate_mesh(name: str, mesh: dict, schema: str, mapping: dict) -> dict:
    if mesh.get("schema") != schema:
        raise AssertionError(f"{name} schema drift: {mesh.get('schema')!r}")
    vertices = mesh.get("vertices")
    triangles = mesh.get("triangles")
    owners = mesh.get("triangle_owners")
    if not isinstance(vertices, list) or not isinstance(triangles, list) or not isinstance(owners, list):
        raise AssertionError(f"{name} mesh arrays missing")
    if len(triangles) != len(owners):
        raise AssertionError(f"{name} triangle/owner cardinality drift")

    owner_ids = {row.get("source_component_id") for row in owners}
    if None in owner_ids:
        raise AssertionError(f"{name} lost source_component_id")
    if owner_ids != set(mapping):
        raise AssertionError(
            f"{name} material-owner coverage mismatch "
            f"missing={sorted(set(mapping)-owner_ids)} extra={sorted(owner_ids-set(mapping))}"
        )

    material_counts = {material_id: 0 for material_id in sorted(set(mapping.values()))}
    for tri, owner in zip(triangles, owners):
        if len(tri) != 3 or any(
            not isinstance(index, int) or index < 0 or index >= len(vertices)
            for index in tri
        ):
            raise AssertionError(f"{name} invalid triangle")
        material_counts[mapping[owner["source_component_id"]]] += 1

    return {
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "source_component_owner_count": len(owner_ids),
        "material_triangle_counts": material_counts,
    }


def normalized_materials(profile: dict) -> dict:
    candidate = profile.get("candidate")
    if not isinstance(candidate, dict) or len(candidate) != 5:
        raise AssertionError("expected exact five-material Building family")
    output = {}
    for material_id, spec in candidate.items():
        metallic = float(spec["metallic"])
        roughness = float(spec["roughness"])
        if not (0.0 <= metallic <= 1.0 and 0.0 <= roughness <= 1.0):
            raise AssertionError(f"invalid PBR scalar for {material_id}")
        output[material_id] = {
            "albedo": rgba(spec["albedo"]),
            "albedo_hex": spec["albedo"],
            "metallic": metallic,
            "roughness": roughness,
        }
    return output


def validate_owner_policy(policy: dict) -> dict:
    if policy.get("schema") != OWNER_SCHEMA:
        raise AssertionError("Hard-Surface compact owner policy schema drift")
    if policy.get("policy_revision") != "service-pavilion-001/compact-boundary-shell-policy-005":
        raise AssertionError("Hard-Surface compact owner policy revision drift")

    semantic = policy.get("semantic_source", {})
    if semantic.get("variant_id") != SEMANTIC_SOURCE_ID:
        raise AssertionError("semantic source identity drift")
    if semantic.get("authority") != "SEMANTIC_SOURCE_OF_TRUTH":
        raise AssertionError("semantic source authority drift")

    reference = policy.get("reference_representation", {})
    compact = policy.get("compact_representation", {})
    if reference.get("representation_id") != REFERENCE_ID:
        raise AssertionError("reference representation identity drift")
    if compact.get("representation_id") != COMPACT_ID:
        raise AssertionError("compact-v2 representation identity drift")
    if compact.get("schema") != COMPACT_SCHEMA:
        raise AssertionError("compact-v2 representation schema drift")
    if compact.get("geometry_evidence_head") != GEOMETRY_HEAD:
        raise AssertionError("compact-v2 Geometry head drift")
    if compact.get("status") != "SOURCE_OWNED_DERIVED_COMPACT_RECEIVING_OPTION_NOT_DEFAULT":
        raise AssertionError("compact-v2 owner status drift")
    if "material_surface_receiving_candidate" not in compact.get("allowed_roles", []):
        raise AssertionError("Hard Surface no longer allows Materials receiving review")
    if policy.get("selection_policy") != "EXPLICIT_RECEIVING_REPRESENTATION_ID_REQUIRED__NO_DEFAULT_OR_IMPLICIT_FALLBACK":
        raise AssertionError("receiving selection policy drift")
    if policy.get("evidence_transfer_policy") != "NO_DOWNSTREAM_PASS_TRANSFER_ACROSS_REFERENCE_V1_OR_COMPACT_V2_IDENTITIES__EXACT_CONSUMER_REBIND_REQUIRED":
        raise AssertionError("evidence transfer policy drift")
    if policy.get("current_downstream_state", {}).get("materials_reference_or_v1_evidence") != "DOES_NOT_COVER_COMPACT_V2":
        raise AssertionError("owner policy no longer requires an exact Materials compact-v2 rebind")
    return compact


def build(geometry_root: Path, owner_root: Path, exact_head: str) -> tuple[dict, dict]:
    profile = load_json(PROFILE)
    if profile.get("schema") != "axm.building-material-profile/v0.1":
        raise AssertionError("material profile schema drift")
    mapping = profile.get("component_materials")
    if not isinstance(mapping, dict) or len(mapping) != 19:
        raise AssertionError("Building material mapping must retain exact 19-owner coverage")

    owner_policy_path = owner_root / OWNER_POLICY_REL
    owner_policy = load_json(owner_policy_path)
    compact_owner = validate_owner_policy(owner_policy)

    reference_root = geometry_root / "evidence" / "service-pavilion-boundary-shell-001"
    compact_root = geometry_root / "evidence" / "service-pavilion-boundary-shell-compaction-v2-001"
    reference_path = reference_root / "boundary-shell.json"
    reference_evidence_path = reference_root / "boundary-shell-evidence.json"
    compact_path = compact_root / "compacted-boundary-shell-v2.json"
    compact_evidence_path = compact_root / "compaction-v2-evidence.json"
    geometry_head_path = compact_root / "exact-head.txt"

    reference = load_json(reference_path)
    reference_evidence = load_json(reference_evidence_path)
    compact = load_json(compact_path)
    compact_evidence = load_json(compact_evidence_path)

    if geometry_head_path.read_text(encoding="utf-8").strip() != GEOMETRY_HEAD:
        raise AssertionError("Geometry compact-v2 exact-head drift")
    if compact_evidence.get("exact_geometry_head") != GEOMETRY_HEAD:
        raise AssertionError("Geometry compact-v2 receipt head drift")
    if reference_evidence.get("result") != "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE":
        raise AssertionError("reference boundary-shell evidence is not PASS")
    if compact_evidence.get("result") != "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_COLLINEAR_CHAIN_V2":
        raise AssertionError("compact-v2 Geometry evidence is not PASS")

    reference_stats = validate_mesh("reference", reference, REFERENCE_SCHEMA, mapping)
    compact_stats = validate_mesh("compact_v2", compact, COMPACT_SCHEMA, mapping)
    if (reference_stats["vertex_count"], reference_stats["triangle_count"]) != (1420, 2884):
        raise AssertionError(f"reference budget drift: {reference_stats}")
    if (compact_stats["vertex_count"], compact_stats["triangle_count"]) != (1004, 2052):
        raise AssertionError(f"compact-v2 budget drift: {compact_stats}")

    donor = compact_evidence.get("donor", {})
    candidate = compact_evidence.get("candidate", {})
    expected_payload_sha = compact_owner.get("expected_payload_sha256")
    if candidate.get("payload_sha256") != expected_payload_sha:
        raise AssertionError("compact-v2 payload identity does not match Hard-Surface owner policy")
    if candidate.get("bounds") != donor.get("bounds"):
        raise AssertionError("compact-v2 bounds drift")
    if not close(candidate.get("signed_volume_m3"), donor.get("signed_volume_m3")):
        raise AssertionError("compact-v2 volume drift")
    if not close(candidate.get("surface_area_m2"), donor.get("surface_area_m2")):
        raise AssertionError("compact-v2 surface-area drift")
    if candidate.get("source_component_owner_count") != donor.get("source_component_owner_count") or candidate.get("source_component_owner_count") != 19:
        raise AssertionError("compact-v2 source owner count drift")
    if float(candidate.get("maximum_source_component_area_residual_m2", 1.0)) > EPS:
        raise AssertionError("compact-v2 source-owner boundary area drift")
    if float(candidate.get("max_patch_area_residual_m2", 1.0)) > EPS:
        raise AssertionError("compact-v2 planar-patch area drift")
    for key in (
        "boundary_edge_count",
        "nonmanifold_edge_count",
        "orientation_conflict_edge_count",
        "degenerate_triangle_count",
        "isolated_vertex_count",
        "disconnected_vertex_fan_count",
    ):
        if int(candidate.get(key, -1)) != 0:
            raise AssertionError(f"compact-v2 structural gate drift: {key}")

    materials = normalized_materials(profile)
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "exact_materials_head": exact_head.strip(),
        "hard_surface_owner_head": HARD_SURFACE_HEAD,
        "hard_surface_owner_policy_sha256": sha256(owner_policy_path),
        "geometry_donor_head": GEOMETRY_HEAD,
        "semantic_source_variant_id": SEMANTIC_SOURCE_ID,
        "reference_representation_id": REFERENCE_ID,
        "selected_representation_id": COMPACT_ID,
        "selection_policy": owner_policy["selection_policy"],
        "evidence_transfer_policy": owner_policy["evidence_transfer_policy"],
        "geometry_reference_sha256": sha256(reference_path),
        "geometry_compact_sha256": sha256(compact_path),
        "geometry_compaction_evidence_sha256": sha256(compact_evidence_path),
        "geometry_compact_payload_sha256": candidate["payload_sha256"],
        "material_profile_sha256": sha256(PROFILE),
        "materials": materials,
        "component_materials": mapping,
        "normal_policy": "EXPLICIT_PER_TRIANGLE_PLANE_NORMAL__NO_VERTEX_SMOOTHING__HARD_SURFACE_REVIEW",
        "contexts": ["front_service", "east_service", "three_quarter"],
        "reference": reference,
        "compact": compact,
        "reference_stats": reference_stats,
        "compact_stats": compact_stats,
        "geometry_evidence": {
            "reference_result": reference_evidence["result"],
            "compact_result": compact_evidence["result"],
            "signed_volume_m3": candidate["signed_volume_m3"],
            "surface_area_m2": candidate["surface_area_m2"],
            "surface_area_residual_vs_donor_m2": abs(
                float(candidate["surface_area_m2"]) - float(donor["surface_area_m2"])
            ),
            "source_component_owner_count": candidate["source_component_owner_count"],
            "maximum_source_component_area_residual_m2": candidate["maximum_source_component_area_residual_m2"],
            "max_patch_area_residual_m2": candidate["max_patch_area_residual_m2"],
            "vertex_reduction": reference_stats["vertex_count"] - compact_stats["vertex_count"],
            "triangle_reduction": reference_stats["triangle_count"] - compact_stats["triangle_count"],
            "historical_v1_vertex_count": compact_evidence["historical_v1_control"]["vertex_count"],
            "historical_v1_triangle_count": compact_evidence["historical_v1_control"]["triangle_count"],
            "additional_vertex_reduction_vs_v1": candidate["additional_vertex_reduction_vs_v1"],
            "additional_triangle_reduction_vs_v1": candidate["additional_triangle_reduction_vs_v1"],
        },
        "truth_boundary": {
            "material_scalars_changed": False,
            "source_component_material_mapping_changed": False,
            "geometry_owned_by_materials": False,
            "semantic_source_replaced": False,
            "compact_v2_selected_as_default": False,
            "reference_and_compact_material_family_identical": True,
            "hard_surface_normal_policy_explicit": True,
            "vertex_smooth_generated_normals_tested": False,
            "uvs_or_textures_tested": False,
            "environment_adoption": False,
            "technical_art_transport_acceptance": False,
            "runtime_acceptance": False,
            "art_direction_acceptance": False,
            "visual_qa_acceptance": False,
        },
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_BUILDING_COMPACT_V2_SOURCE_OWNER_MATERIAL_REBIND_PACKET",
        "exact_materials_head": exact_head.strip(),
        "hard_surface_owner_head": HARD_SURFACE_HEAD,
        "geometry_donor_head": GEOMETRY_HEAD,
        "semantic_source_variant_id": SEMANTIC_SOURCE_ID,
        "reference_representation_id": REFERENCE_ID,
        "selected_representation_id": COMPACT_ID,
        "reference_stats": reference_stats,
        "compact_stats": compact_stats,
        "geometry_evidence": payload["geometry_evidence"],
        "material_profile_sha256": payload["material_profile_sha256"],
        "hard_surface_owner_policy_sha256": payload["hard_surface_owner_policy_sha256"],
        "payload_sha256": canonical_digest(payload),
        "truth_boundary": payload["truth_boundary"],
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-root", required=True, type=Path)
    parser.add_argument("--owner-root", required=True, type=Path)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument(
        "--out",
        default="lookdev-boundary-shell-compaction-proof/generated",
        type=Path,
    )
    args = parser.parse_args()

    payload, receipt = build(
        args.geometry_root.resolve(),
        args.owner_root.resolve(),
        args.exact_head.strip(),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
