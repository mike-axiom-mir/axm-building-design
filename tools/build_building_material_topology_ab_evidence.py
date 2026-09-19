#!/usr/bin/env python3
"""Build Materials evidence for the Building topology representation rebind.

This consumes the current source-owned Building material profile, the exact
source-migrated Hard-Surface PR #2 builder, and the exact historical Geometry
PR #6 candidate. It renders the same 19 components under the same material
family as:
- historical malformed predecessor face table;
- the closed/outward face table now owned by current Hard Surface;
- the existing Godot BoxMesh lookdev reference.

The comparison is Materials-owned renderer/provenance evidence only. Hard
Surface remains owner of the migrated source identity and Geometry remains owner
of its historical derived proof.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_SCHEMA = "axm.building-material-profile/v0.1"
PAYLOAD_SCHEMA = "axm.building-material-topology-lookdev-payload/v0.2"
RECEIPT_SCHEMA = "axm.building-material-topology-lookdev-build-receipt/v0.2"
EXPECTED_GEOMETRY_HEAD = "407d3aaf36c26829a64d964143e34587df6d8ea1"
EXPECTED_PREDECESSOR_HARD_SURFACE_HEAD = "4faa769b406bf3ad0ba9489a77141c27f122ce51"
EXPECTED_CURRENT_HARD_SURFACE_HEAD = "57f66b1245812f0c3d402232a046b86c0b5c72d8"
EXPECTED_SOURCE_SCHEMA = "axm.building-hard-surface/v0.2"
EXPECTED_SOURCE_REVISION = "service-pavilion-001/closed-outward-box-shells-002"
EXPECTED_TOPOLOGY_REVISION = "closed-outward-12-triangle-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rgba(hex_value: str) -> list[float]:
    if not isinstance(hex_value, str) or len(hex_value) != 9 or not hex_value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex: {hex_value!r}")
    return [int(hex_value[i:i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]


def normalized_candidate_materials(profile: dict) -> dict:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise AssertionError("material profile schema mismatch")
    candidate = profile.get("candidate")
    if not isinstance(candidate, dict) or len(candidate) != 5:
        raise AssertionError("expected exact five-material Building candidate")
    out = {}
    for material_id, spec in candidate.items():
        metallic = float(spec["metallic"])
        roughness = float(spec["roughness"])
        if not 0.0 <= metallic <= 1.0 or not 0.0 <= roughness <= 1.0:
            raise AssertionError(f"PBR scalar out of bounds: {material_id}")
        out[material_id] = {
            "albedo": rgba(spec["albedo"]),
            "albedo_hex": spec["albedo"],
            "metallic": metallic,
            "roughness": roughness,
        }
    return out


def build_components(base, profile: dict) -> tuple[list[dict], list[dict]]:
    pavilion = base.load(base.PAVILION)
    panel = base.load(base.PANEL)
    fits = [base.fit_panel(interface, panel) for interface in pavilion["interfaces"]]

    raw = []
    for component in pavilion["components"]:
        raw.append({
            "id": component["id"],
            "center_m": component["center"],
            "size_local_xyz_m": component["size"],
            "source_basis": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "vertices_m": base.box_vertices(component["center"], component["size"]),
        })

    interface_by_id = {interface["id"]: interface for interface in pavilion["interfaces"]}
    for fit in fits:
        interface = interface_by_id[fit["interface_id"]]
        basis = [interface["normal"], interface["lateral"], interface["up"]]
        raw.append({
            "id": "panel-" + fit["interface_id"],
            "center_m": fit["panel_center_local_m"],
            "size_local_xyz_m": panel["proof_geometry"]["size_local_xyz_m"],
            "source_basis": basis,
            "vertices_m": base.box_vertices(
                fit["panel_center_local_m"],
                panel["proof_geometry"]["size_local_xyz_m"],
                basis,
            ),
        })

    mapping = profile.get("component_materials")
    if not isinstance(mapping, dict):
        raise AssertionError("component_materials missing")
    ids = {row["id"] for row in raw}
    if set(mapping) != ids:
        raise AssertionError(
            f"material coverage mismatch missing={sorted(ids-set(mapping))} extra={sorted(set(mapping)-ids)}"
        )
    for row in raw:
        row["material_id"] = mapping[row["id"]]
    return raw, fits


def build_payload(geometry_donor: Path, hard_surface_donor: Path, exact_head: str) -> tuple[dict, dict]:
    base_path = hard_surface_donor / "tools" / "build_service_pavilion.py"
    base = load_module(base_path, "building_current_source")
    donor_path = geometry_donor / "tools" / "build_service_pavilion_topology_candidate.py"
    donor = load_module(donor_path, "geometry_historical_donor")

    pavilion = base.load(base.PAVILION)
    if donor.HARD_SURFACE_DONOR_HEAD != EXPECTED_PREDECESSOR_HARD_SURFACE_HEAD:
        raise AssertionError("Geometry donor predecessor Hard-Surface dependency drifted")
    if getattr(base, "PREDECESSOR_HARD_SURFACE_HEAD", None) != EXPECTED_PREDECESSOR_HARD_SURFACE_HEAD:
        raise AssertionError("current Hard-Surface predecessor binding drifted")
    if getattr(base, "GEOMETRY_CANDIDATE_HEAD", None) != EXPECTED_GEOMETRY_HEAD:
        raise AssertionError("current Hard-Surface Geometry adoption binding drifted")
    if getattr(base, "BOX_TOPOLOGY_REVISION", None) != EXPECTED_TOPOLOGY_REVISION:
        raise AssertionError("current Hard-Surface topology revision drifted")
    if pavilion.get("schema") != EXPECTED_SOURCE_SCHEMA:
        raise AssertionError("current Hard-Surface source schema drifted")
    if pavilion.get("source_revision") != EXPECTED_SOURCE_REVISION:
        raise AssertionError("current Hard-Surface source revision drifted")
    if tuple(tuple(face) for face in base.HISTORICAL_FACES) != tuple(tuple(face) for face in donor.HISTORICAL_FACES):
        raise AssertionError("current source historical oracle differs from exact Geometry historical table")
    if tuple(tuple(face) for face in base.FACES) != tuple(tuple(face) for face in donor.CANDIDATE_FACES):
        raise AssertionError("current source face table differs from exact Geometry closed/outward candidate")

    built = base.build()
    if len(built) < 9:
        raise AssertionError("current source builder did not return topology evidence")
    topology_summary = built[8]
    if topology_summary.get("object_count") != 19 or topology_summary.get("triangle_count") != 228:
        raise AssertionError("current source topology aggregate drift")
    if topology_summary.get("outward_triangle_count") != 228 or topology_summary.get("inward_triangle_count") != 0:
        raise AssertionError("current source topology is not exact closed/outward aggregate")

    profile_path = ROOT / "lookdev" / "building_material_profile_001.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    materials = normalized_candidate_materials(profile)
    components, fits = build_components(base, profile)

    historical_faces = [[index - 1 for index in face] for face in base.HISTORICAL_FACES]
    current_faces = [[index - 1 for index in face] for face in base.FACES]
    geometry_candidate_faces = [[index - 1 for index in face] for face in donor.CANDIDATE_FACES]
    if current_faces != geometry_candidate_faces:
        raise AssertionError("source-owned current topology no longer equals the exact proven Geometry candidate")
    if historical_faces == current_faces:
        raise AssertionError("historical/current topology unexpectedly identical")
    if any(len(face) != 3 for face in historical_faces + current_faces):
        raise AssertionError("face tables must remain triangles")
    if any(index < 0 or index > 7 for face in historical_faces + current_faces for index in face):
        raise AssertionError("face table index outside exact eight-vertex box")

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "exact_materials_head": exact_head,
        "hard_surface_source_head": EXPECTED_CURRENT_HARD_SURFACE_HEAD,
        "hard_surface_source_builder_sha256": sha256(base_path),
        "geometry_donor_head": EXPECTED_GEOMETRY_HEAD,
        "geometry_donor_script_sha256": sha256(donor_path),
        "source_schema": pavilion.get("schema"),
        "source_revision": pavilion.get("source_revision"),
        "box_topology_revision": getattr(base, "BOX_TOPOLOGY_REVISION", None),
        "topology_summary": topology_summary,
        "pavilion_source_sha256": sha256(base.PAVILION),
        "panel_source_sha256": sha256(base.PANEL),
        "material_profile_sha256": sha256(profile_path),
        "materials": materials,
        "components": components,
        "faces": {
            "historical_malformed": historical_faces,
            "closed_outward_candidate": current_faces,
        },
        "contexts": ["front_service", "east_service", "three_quarter"],
        "truth_boundary": {
            "same_source_vertices_all_variants": True,
            "same_material_profile_all_variants": True,
            "same_cameras_lighting_all_variants": True,
            "closed_outward_candidate_matches_current_source": True,
            "current_source_matches_exact_geometry_candidate": True,
            "historical_malformed_is_defect_reproduction_only": True,
            "boxmesh_reference_is_existing_materials_proof_representation": True,
            "final_normals_tangents": False,
            "uvs": False,
            "textures": False,
            "source_migration": True,
            "map_receiving_equivalence": False,
            "runtime_acceptance": False,
            "art_direction_acceptance": False,
        },
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_OWNED_BUILDING_TOPOLOGY_MATERIAL_REBIND_PAYLOAD",
        "exact_materials_head": exact_head,
        "hard_surface_source_head": EXPECTED_CURRENT_HARD_SURFACE_HEAD,
        "hard_surface_source_builder_sha256": payload["hard_surface_source_builder_sha256"],
        "geometry_donor_head": EXPECTED_GEOMETRY_HEAD,
        "geometry_donor_script_sha256": payload["geometry_donor_script_sha256"],
        "source_schema": payload["source_schema"],
        "source_revision": payload["source_revision"],
        "box_topology_revision": payload["box_topology_revision"],
        "pavilion_source_sha256": payload["pavilion_source_sha256"],
        "panel_source_sha256": payload["panel_source_sha256"],
        "material_profile_sha256": payload["material_profile_sha256"],
        "component_count": len(components),
        "receiver_count": len(fits),
        "historical_face_count_per_component": len(historical_faces),
        "candidate_face_count_per_component": len(current_faces),
        "current_source_equals_geometry_candidate": current_faces == geometry_candidate_faces,
        "topology_summary": topology_summary,
        "payload_sha256": canonical_digest(payload),
        "truth_boundary": payload["truth_boundary"],
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-donor", required=True)
    parser.add_argument("--hard-surface-donor", required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", default="lookdev-topology-proof/generated")
    args = parser.parse_args()
    if args.exact_head.strip() in {EXPECTED_GEOMETRY_HEAD, EXPECTED_CURRENT_HARD_SURFACE_HEAD}:
        raise AssertionError("materials head must not be conflated with a donor head")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_payload(
        Path(args.geometry_donor),
        Path(args.hard_surface_donor),
        args.exact_head.strip(),
    )
    (out / "building_material_topology_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
