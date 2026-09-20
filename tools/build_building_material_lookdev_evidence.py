from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROFILE_SCHEMA = "axm.building-material-profile/v0.1"
PAYLOAD_SCHEMA = "axm.building-material-lookdev-payload/v0.1"
RECEIPT_SCHEMA = "axm.building-material-lookdev-build-receipt/v0.1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rgba(hex_value: str) -> list[float]:
    if not isinstance(hex_value, str) or len(hex_value) != 9 or not hex_value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex: {hex_value!r}")
    try:
        return [int(hex_value[i : i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]
    except ValueError as exc:
        raise AssertionError(f"invalid RGBA hex: {hex_value!r}") from exc


def validate_profile(profile: dict, component_ids: set[str]) -> dict:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise AssertionError("material profile schema mismatch")
    baseline = profile.get("baseline")
    candidate = profile.get("candidate")
    mapping = profile.get("component_materials")
    if not isinstance(baseline, dict) or set(baseline) != {"neutral_proof"}:
        raise AssertionError("baseline must contain only neutral_proof")
    if not isinstance(candidate, dict) or len(candidate) != 5:
        raise AssertionError("candidate must contain exactly five bounded Building materials")
    if not isinstance(mapping, dict):
        raise AssertionError("component_materials missing")
    missing = sorted(component_ids - set(mapping))
    extra = sorted(set(mapping) - component_ids)
    if missing or extra:
        raise AssertionError(f"component coverage mismatch missing={missing} extra={extra}")

    normalized = {"baseline": {}, "candidate": {}}
    for family_name, family in (("baseline", baseline), ("candidate", candidate)):
        for material_id, spec in family.items():
            metallic = float(spec["metallic"])
            roughness = float(spec["roughness"])
            if not 0.0 <= metallic <= 1.0 or not 0.0 <= roughness <= 1.0:
                raise AssertionError(f"PBR scalar out of bounds for {material_id}")
            normalized[family_name][material_id] = {
                "albedo": rgba(spec["albedo"]),
                "albedo_hex": spec["albedo"],
                "metallic": metallic,
                "roughness": roughness,
            }
    for component_id, material_id in mapping.items():
        if material_id not in candidate:
            raise AssertionError(f"unknown candidate material {material_id!r} for {component_id!r}")
    if profile.get("provenance", {}).get("external_textures") not in ([], None):
        raise AssertionError("v0.1 Building proof forbids external textures")
    return normalized


def build_payload(
    pavilion_path: Path,
    panel_path: Path,
    profile_path: Path,
    source_root: Path | None = None,
    source_head: str | None = None,
) -> tuple[dict, dict]:
    source_root = Path(source_root) if source_root is not None else ROOT
    source_module = _load_module(source_root / "tools" / "build_service_pavilion.py", "axm_materials_building_source")
    built = source_module.build()
    if len(built) < 8:
        raise AssertionError("Building source builder returned an unsupported contract")
    pavilion, panel, fits, _obj, _mins, _maxs, _path_gap, _negatives = built[:8]
    topology_summary = built[8] if len(built) > 8 else None
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    components = []
    for component in pavilion["components"]:
        components.append({
            "id": component["id"],
            "kind": "box",
            "center_m": copy.deepcopy(component["center"]),
            "size_local_xyz_m": copy.deepcopy(component["size"]),
            "source_basis": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "source": "service-pavilion-001 component",
        })

    interface_by_id = {interface["id"]: interface for interface in pavilion["interfaces"]}
    for fit in fits:
        interface = interface_by_id[fit["interface_id"]]
        components.append({
            "id": "panel-" + fit["interface_id"],
            "kind": "box",
            "center_m": copy.deepcopy(fit["panel_center_local_m"]),
            "size_local_xyz_m": copy.deepcopy(panel["proof_geometry"]["size_local_xyz_m"]),
            "source_basis": [
                copy.deepcopy(interface["normal"]),
                copy.deepcopy(interface["lateral"]),
                copy.deepcopy(interface["up"]),
            ],
            "source": "utility-access-panel-001 exact proof box placed by source receiver frame",
        })

    component_ids = {component["id"] for component in components}
    normalized = validate_profile(profile, component_ids)
    for component in components:
        component["baseline_material"] = "neutral_proof"
        component["candidate_material"] = profile["component_materials"][component["id"]]

    geometry_contract = {
        "pavilion_asset_id": pavilion["asset_id"],
        "panel_asset_id": panel["asset_id"],
        "source_schema": pavilion.get("schema"),
        "source_revision": pavilion.get("source_revision"),
        "box_topology_revision": getattr(source_module, "BOX_TOPOLOGY_REVISION", None),
        "components": components,
    }
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "pavilion_asset_id": pavilion["asset_id"],
        "panel_asset_id": panel["asset_id"],
        "source_identity": {
            "hard_surface_head": source_head,
            "source_schema": pavilion.get("schema"),
            "source_revision": pavilion.get("source_revision"),
            "box_topology_revision": getattr(source_module, "BOX_TOPOLOGY_REVISION", None),
            "topology_summary": topology_summary,
        },
        "components": components,
        "materials": normalized,
        "contexts": ["front_service", "east_service", "three_quarter"],
        "truth_boundary": {
            "same_geometry_baseline_candidate": True,
            "source_component_material_assignment_only": True,
            "source_receiver_frames_preserved": True,
            "source_identity_explicit": True,
            "uvs": False,
            "textures": False,
            "weathering": False,
            "physical_surface_validation": False,
            "environment_acceptance": False,
            "runtime_acceptance": False,
            "art_direction_acceptance": False,
        },
    }
    structural_prerequisite = {
        "result": "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF",
        "receiver_count": len(fits),
        "receiver_normal_dot": sum(a * b for a, b in zip(fits[0]["normal"], fits[1]["normal"])),
        "receiver_fit_results": fits,
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_BOUND_BUILDING_SURFACE_PAYLOAD",
        "hard_surface_source_head": source_head,
        "source_schema": pavilion.get("schema"),
        "source_revision": pavilion.get("source_revision"),
        "box_topology_revision": getattr(source_module, "BOX_TOPOLOGY_REVISION", None),
        "pavilion_source_sha256": sha256(pavilion_path),
        "panel_source_sha256": sha256(panel_path),
        "material_profile_sha256": sha256(profile_path),
        "geometry_contract_sha256": canonical_digest(geometry_contract),
        "component_count": len(components),
        "candidate_material_ids": sorted(normalized["candidate"]),
        "topology_summary": topology_summary,
        "structural_prerequisite": structural_prerequisite,
        "truth_boundary": payload["truth_boundary"],
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--source-head", default=None)
    parser.add_argument("--pavilion", default=None)
    parser.add_argument("--panel", default=None)
    parser.add_argument("--profile", default="lookdev/building_material_profile_001.json")
    parser.add_argument("--out", default="lookdev-proof/generated")
    args = parser.parse_args()

    source_root = Path(args.source_root)
    pavilion_path = Path(args.pavilion) if args.pavilion else source_root / "assets/service_pavilion_001.json"
    panel_path = Path(args.panel) if args.panel else source_root / "assets/utility_access_panel_001.json"
    profile_path = Path(args.profile)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_payload(
        pavilion_path,
        panel_path,
        profile_path,
        source_root=source_root,
        source_head=args.source_head,
    )
    (out / "building_material_payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "build_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
