#!/usr/bin/env python3
"""Build bounded Materials evidence for the Building boundary-shell compaction.

This lane does not own either Building topology. It consumes the exact Geometry
reference boundary shell and its exact compacted successor, then proves that the
existing five-surface Building material family can bind both representations by
source_component_id without fallback or material retuning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "lookdev" / "building_material_profile_001.json"
EXPECTED_GEOMETRY_HEAD = "43ace6fc44e6f6c0f637cd3436a94099c97c2d48"
REFERENCE_SCHEMA = "axm.building-current-source-boundary-shell/v0.1"
COMPACT_SCHEMA = "axm.building-boundary-shell-conforming-compaction/v0.1"
PAYLOAD_SCHEMA = "axm.building-material-boundary-shell-compaction-lookdev/v0.1"
RECEIPT_SCHEMA = "axm.building-material-boundary-shell-compaction-build-receipt/v0.1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rgba(value: str) -> list[float]:
    if not isinstance(value, str) or len(value) != 9 or not value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex {value!r}")
    return [int(value[i:i+2], 16) / 255.0 for i in (1, 3, 5, 7)]


def normalized_materials(profile: dict) -> dict:
    candidate = profile.get("candidate")
    if not isinstance(candidate, dict) or len(candidate) != 5:
        raise AssertionError("expected exact five-material Building family")
    out = {}
    for material_id, spec in candidate.items():
        metallic = float(spec["metallic"])
        roughness = float(spec["roughness"])
        if not (0.0 <= metallic <= 1.0 and 0.0 <= roughness <= 1.0):
            raise AssertionError(f"invalid PBR scalar for {material_id}")
        out[material_id] = {
            "albedo": rgba(spec["albedo"]),
            "albedo_hex": spec["albedo"],
            "metallic": metallic,
            "roughness": roughness,
        }
    return out


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object: {path}")
    return value


def validate_mesh(name: str, mesh: dict, schema: str, mapping: dict) -> dict:
    if mesh.get("schema") != schema:
        raise AssertionError(f"{name} schema drift")
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
            f"{name} material-owner coverage mismatch missing={sorted(set(mapping)-owner_ids)} extra={sorted(owner_ids-set(mapping))}"
        )
    for triangle in triangles:
        if len(triangle) != 3 or any(not isinstance(i, int) or i < 0 or i >= len(vertices) for i in triangle):
            raise AssertionError(f"{name} invalid triangle")
    material_counts = {material_id: 0 for material_id in sorted(set(mapping.values()))}
    for owner in owners:
        material_counts[mapping[owner["source_component_id"]]] += 1
    return {
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "source_component_owner_count": len(owner_ids),
        "material_triangle_counts": material_counts,
    }


def build(geometry_root: Path, exact_head: str) -> tuple[dict, dict]:
    profile = load_json(PROFILE)
    if profile.get("schema") != "axm.building-material-profile/v0.1":
        raise AssertionError("material profile schema drift")
    mapping = profile.get("component_materials")
    if not isinstance(mapping, dict) or len(mapping) != 19:
        raise AssertionError("Building material component mapping must remain exact 19-owner coverage")

    reference_root = geometry_root / "evidence" / "service-pavilion-boundary-shell-001"
    compact_root = geometry_root / "evidence" / "service-pavilion-boundary-shell-compaction-001"
    reference_path = reference_root / "boundary-shell.json"
    reference_evidence_path = reference_root / "boundary-shell-evidence.json"
    compact_path = compact_root / "compacted-boundary-shell.json"
    compact_evidence_path = compact_root / "compaction-evidence.json"
    geometry_head_path = compact_root / "exact-head.txt"

    reference = load_json(reference_path)
    reference_evidence = load_json(reference_evidence_path)
    compact = load_json(compact_path)
    compact_evidence = load_json(compact_evidence_path)
    observed_geometry_head = geometry_head_path.read_text(encoding="utf-8").strip()
    if observed_geometry_head != EXPECTED_GEOMETRY_HEAD:
        raise AssertionError(f"Geometry head drift: {observed_geometry_head}")
    if compact_evidence.get("exact_geometry_head") != EXPECTED_GEOMETRY_HEAD:
        raise AssertionError("compaction evidence head drift")
    if reference_evidence.get("result") != "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE":
        raise AssertionError("reference boundary-shell evidence is not PASS")
    if compact_evidence.get("result") != "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_CANDIDATE":
        raise AssertionError("compaction evidence is not PASS")

    reference_stats = validate_mesh("reference", reference, REFERENCE_SCHEMA, mapping)
    compact_stats = validate_mesh("compact", compact, COMPACT_SCHEMA, mapping)
    if reference_stats["vertex_count"] != 1420 or reference_stats["triangle_count"] != 2884:
        raise AssertionError(f"reference budget drift: {reference_stats}")
    if compact_stats["vertex_count"] != 1402 or compact_stats["triangle_count"] != 2848:
        raise AssertionError(f"compact budget drift: {compact_stats}")
    if compact_stats["vertex_count"] >= reference_stats["vertex_count"] or compact_stats["triangle_count"] >= reference_stats["triangle_count"]:
        raise AssertionError("compaction no longer reduces representation")

    donor = compact_evidence.get("donor", {})
    candidate = compact_evidence.get("candidate", {})
    for key in ("signed_volume_m3", "surface_area_m2", "bounds", "source_component_owner_count"):
        if candidate.get(key) != donor.get(key):
            raise AssertionError(f"compaction donor/candidate invariant drift: {key}")
    if float(candidate.get("maximum_source_component_area_residual_m2", 1.0)) > 1e-9:
        raise AssertionError("source-component boundary area drift")

    materials = normalized_materials(profile)
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "exact_materials_head": exact_head,
        "geometry_donor_head": EXPECTED_GEOMETRY_HEAD,
        "geometry_reference_sha256": sha256(reference_path),
        "geometry_compact_sha256": sha256(compact_path),
        "geometry_compaction_evidence_sha256": sha256(compact_evidence_path),
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
            "source_component_owner_count": candidate["source_component_owner_count"],
            "maximum_source_component_area_residual_m2": candidate["maximum_source_component_area_residual_m2"],
            "vertex_reduction": reference_stats["vertex_count"] - compact_stats["vertex_count"],
            "triangle_reduction": reference_stats["triangle_count"] - compact_stats["triangle_count"],
        },
        "truth_boundary": {
            "material_scalars_changed": False,
            "source_component_material_mapping_changed": False,
            "geometry_owned_by_materials": False,
            "reference_and_compact_material_family_identical": True,
            "hard_surface_normal_policy_explicit": True,
            "vertex_smooth_generated_normals_tested": False,
            "uvs_or_textures_tested": False,
            "environment_adoption": False,
            "runtime_acceptance": False,
            "art_direction_acceptance": False,
            "visual_qa_acceptance": False,
        },
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_BUILDING_BOUNDARY_SHELL_COMPACTION_MATERIAL_BINDING_PACKET",
        "exact_materials_head": exact_head,
        "geometry_donor_head": EXPECTED_GEOMETRY_HEAD,
        "reference_stats": reference_stats,
        "compact_stats": compact_stats,
        "geometry_evidence": payload["geometry_evidence"],
        "material_profile_sha256": payload["material_profile_sha256"],
        "payload_sha256": canonical_digest(payload),
        "truth_boundary": payload["truth_boundary"],
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-root", required=True, type=Path)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", default="lookdev-boundary-shell-compaction-proof/generated", type=Path)
    args = parser.parse_args()
    payload, receipt = build(args.geometry_root.resolve(), args.exact_head.strip())
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "build_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
