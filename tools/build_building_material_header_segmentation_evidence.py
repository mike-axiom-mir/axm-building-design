#!/usr/bin/env python3
"""Build a bounded Materials rebind over the source-owned Building header segmentation.

Hard Surface owns the segmented representation. Materials owns only the exact
emitted-id -> existing material mapping and renderer continuity evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HARD_SURFACE_HEAD = "34124101e616c423c5a3ed5e122ddf09b98a1650"
EXPECTED_OVERLAY_SCHEMA = "axm.building-header-segmentation/v0.1"
EXPECTED_SUCCESSOR_REVISION = "service-pavilion-001/interpenetration-free-header-segmentation-003"
EXPECTED_PROFILE_SCHEMA = "axm.building-material-profile/v0.1"
PAYLOAD_SCHEMA = "axm.building-material-header-segmentation-lookdev/v0.1"
RECEIPT_SCHEMA = "axm.building-material-header-segmentation-build-receipt/v0.1"
IDENTITY_BASIS = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rgba(value: str) -> list[float]:
    if not isinstance(value, str) or len(value) != 9 or not value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex: {value!r}")
    return [int(value[i:i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]


def materials(profile: dict) -> dict:
    if profile.get("schema") != EXPECTED_PROFILE_SCHEMA:
        raise AssertionError("material profile schema drift")
    candidate = profile.get("candidate")
    if not isinstance(candidate, dict) or len(candidate) != 5:
        raise AssertionError("expected exact five-surface Building family")
    out = {}
    for material_id, spec in candidate.items():
        metallic = float(spec["metallic"])
        roughness = float(spec["roughness"])
        if not 0.0 <= metallic <= 1.0 or not 0.0 <= roughness <= 1.0:
            raise AssertionError(f"PBR scalar outside [0,1]: {material_id}")
        out[material_id] = {
            "albedo": rgba(spec["albedo"]),
            "albedo_hex": spec["albedo"],
            "metallic": metallic,
            "roughness": roughness,
        }
    return out


def component_row(base, component: dict, material_id: str) -> dict:
    return {
        "id": component["id"],
        "center_m": component["center"],
        "size_local_xyz_m": component["size"],
        "source_basis": IDENTITY_BASIS,
        "vertices_m": base.box_vertices(component["center"], component["size"]),
        "material_id": material_id,
    }


def panel_rows(base, pavilion: dict, panel: dict, mapping: dict) -> list[dict]:
    rows = []
    for interface in pavilion["interfaces"]:
        fit = base.fit_panel(interface, panel)
        component_id = "panel-" + fit["interface_id"]
        if component_id not in mapping:
            raise AssertionError(f"missing panel material mapping: {component_id}")
        basis = [interface["normal"], interface["lateral"], interface["up"]]
        center = fit["panel_center_local_m"]
        size = panel["proof_geometry"]["size_local_xyz_m"]
        rows.append({
            "id": component_id,
            "center_m": center,
            "size_local_xyz_m": size,
            "source_basis": basis,
            "vertices_m": base.box_vertices(center, size, basis),
            "material_id": mapping[component_id],
        })
    return rows


def build_payload(hard_surface_donor: Path, exact_head: str) -> tuple[dict, dict]:
    base_path = hard_surface_donor / "tools" / "build_service_pavilion.py"
    overlay_path = hard_surface_donor / "assets" / "service_pavilion_001_header_segmentation.json"
    if not base_path.exists() or not overlay_path.exists():
        raise AssertionError("exact Hard-Surface donor is missing required source files")
    base = load_module(base_path, "building_hard_surface_current")
    pavilion = base.load(base.PAVILION)
    panel = base.load(base.PANEL)
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    if pavilion.get("schema") != "axm.building-hard-surface/v0.2":
        raise AssertionError("base Hard-Surface source schema drift")
    if overlay.get("schema") != EXPECTED_OVERLAY_SCHEMA:
        raise AssertionError("header segmentation overlay schema drift")
    if overlay.get("successor_revision") != EXPECTED_SUCCESSOR_REVISION:
        raise AssertionError("header segmentation successor revision drift")
    if overlay.get("owner") != "Building Hard Surface":
        raise AssertionError("header segmentation owner drift")
    if overlay.get("logical_component_policy") is None:
        raise AssertionError("missing logical component preservation policy")

    profile_path = ROOT / "lookdev" / "building_material_profile_001.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    mats = materials(profile)
    mapping = profile.get("component_materials")
    successor = profile.get("successor_representation_materials")
    if not isinstance(mapping, dict) or not isinstance(successor, dict):
        raise AssertionError("material mappings missing")
    if successor.get("contract") != EXPECTED_OVERLAY_SCHEMA:
        raise AssertionError("Materials successor contract drift")
    if successor.get("source_head") != EXPECTED_HARD_SURFACE_HEAD:
        raise AssertionError("Materials successor source head drift")
    if successor.get("successor_revision") != EXPECTED_SUCCESSOR_REVISION:
        raise AssertionError("Materials successor revision drift")
    if successor.get("fallback_policy") != "NONE_EXPLICIT_IDS_ONLY":
        raise AssertionError("successor mapping must fail closed without wildcard fallback")

    segments = overlay.get("segmented_components")
    if set(segments or {}) != {"front-header", "rear-header"}:
        raise AssertionError("unexpected segmented logical component set")
    emitted = {row["id"] for rows in segments.values() for row in rows}
    explicit = successor.get("emitted_component_materials")
    if not isinstance(explicit, dict) or set(explicit) != emitted:
        raise AssertionError(f"successor emitted material coverage mismatch expected={sorted(emitted)} got={sorted(explicit or {})}")
    if any(material_id not in mats for material_id in explicit.values()):
        raise AssertionError("successor mapping references unknown material")
    if set(explicit.values()) != {"frame_galvanized"}:
        raise AssertionError("segmented headers must preserve exact galvanized-frame family")

    logical_ids = {component["id"] for component in pavilion["components"]}
    panel_ids = {"panel-" + interface["id"] for interface in pavilion["interfaces"]}
    if set(mapping) != logical_ids | panel_ids:
        raise AssertionError("logical source material coverage drift")

    control = [component_row(base, c, mapping[c["id"]]) for c in pavilion["components"]]
    control.extend(panel_rows(base, pavilion, panel, mapping))

    candidate = []
    for component in pavilion["components"]:
        logical_id = component["id"]
        if logical_id not in segments:
            candidate.append(component_row(base, component, mapping[logical_id]))
            continue
        if mapping[logical_id] != "frame_galvanized":
            raise AssertionError(f"logical header material drift: {logical_id}")
        for segment in segments[logical_id]:
            candidate.append(component_row(base, segment, explicit[segment["id"]]))
    candidate.extend(panel_rows(base, pavilion, panel, mapping))

    if len(control) != 19 or len(candidate) != 23:
        raise AssertionError(f"unexpected control/candidate counts: {len(control)}/{len(candidate)}")
    if sum(1 for row in candidate if row["material_id"] == "frame_galvanized") != 16:
        raise AssertionError("candidate galvanized component count drift")

    faces = [[index - 1 for index in face] for face in base.FACES]
    if len(faces) != 12:
        raise AssertionError("source-owned box topology face count drift")

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "exact_materials_head": exact_head,
        "hard_surface_source_head": EXPECTED_HARD_SURFACE_HEAD,
        "hard_surface_builder_sha256": sha256(base_path),
        "base_source_sha256": sha256(base.PAVILION),
        "panel_source_sha256": sha256(base.PANEL),
        "header_segmentation_overlay_sha256": sha256(overlay_path),
        "header_segmentation_schema": overlay["schema"],
        "successor_revision": overlay["successor_revision"],
        "material_profile_sha256": sha256(profile_path),
        "materials": mats,
        "faces": faces,
        "variants": {
            "logical_pre_segmentation": control,
            "source_owned_segmented_headers": candidate,
        },
        "contexts": ["front_service", "east_service", "three_quarter"],
        "truth_boundary": {
            "material_scalars_changed": False,
            "logical_material_roles_changed": False,
            "explicit_segment_id_binding": True,
            "wildcard_or_prefix_material_inference": False,
            "source_geometry_owned_by_materials": False,
            "source_union_equivalence_reproven_here": False,
            "uvs": False,
            "textures": False,
            "weathering": False,
            "map_receiving_equivalence": False,
            "runtime_acceptance": False,
            "art_direction_acceptance": False,
        },
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_OWNED_HEADER_SEGMENTATION_MATERIAL_REBIND_PAYLOAD",
        "exact_materials_head": exact_head,
        "hard_surface_source_head": EXPECTED_HARD_SURFACE_HEAD,
        "header_segmentation_overlay_sha256": payload["header_segmentation_overlay_sha256"],
        "material_profile_sha256": payload["material_profile_sha256"],
        "control_component_count": len(control),
        "candidate_component_count": len(candidate),
        "explicit_segment_binding_count": len(explicit),
        "candidate_frame_component_count": sum(1 for row in candidate if row["material_id"] == "frame_galvanized"),
        "payload_sha256": canonical_digest(payload),
        "truth_boundary": payload["truth_boundary"],
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hard-surface-donor", required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", default="lookdev-header-segmentation-proof/generated")
    args = parser.parse_args()
    if args.exact_head.strip() == EXPECTED_HARD_SURFACE_HEAD:
        raise AssertionError("Materials head must not be conflated with Hard-Surface source head")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_payload(Path(args.hard_surface_donor), args.exact_head.strip())
    (out / "payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "build_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
