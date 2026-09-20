from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

SCHEMA = "axm.building-material-current-world-infill-repair/v0.1"
STATUS = "PASS_BUILDING_CURRENT_WORLD_INFILL_REPAIR_STRUCTURE"
DONOR_SCHEMA = "axm.environment-current-world-building-source-successor-evidence/v0.1"
DONOR_STATUS = "PASS_CURRENT_WORLD_BUILDING_SOURCE_SUCCESSOR_STRUCTURE"
OBSERVER_SCHEMA = "axm.environment-current-world-weather-variant-evidence/v0.1"
OBSERVER_STATUS = "PASS_CURRENT_WORLD_WEATHER_VARIANT_REBIND_STRUCTURE"
BUILDING = "source:building:service-pavilion-001"
ROLE = "infill_coating"
PREDECESSOR_PROFILE_SHA256 = "e8dd0c33b9b2aea108194af57a8fe8de39c7e67bb86109af6dbf3895f22c010b"
SOURCE_HEAD = "57f66b1245812f0c3d402232a046b86c0b5c72d8"
SOURCE_REVISION = "service-pavilion-001/closed-outward-box-shells-002"
TOPOLOGY = "closed-outward-12-triangle-v1"


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def scene_digest(scene: dict) -> str:
    value = copy.deepcopy(scene)
    value.pop("scene_digest", None)
    return digest(value)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def surface_map(receiving: dict) -> dict[str, dict]:
    rows = receiving.get("surfaces", [])
    return {str(row.get("surface_role")): row for row in rows}


def profile_candidate(profile: dict) -> dict:
    candidate = profile.get("candidate", {})
    if set(candidate) != {"slab_mineral", "frame_galvanized", "infill_coating", "roof_membrane", "utility_panel_ochre"}:
        raise ValueError("five-surface profile identity drift")
    return candidate


def normalized_material(material_payload: dict, role: str) -> dict:
    return copy.deepcopy(material_payload["materials"]["candidate"][role])


def validate_single_delta(old_profile: dict, new_profile: dict) -> None:
    old = profile_candidate(old_profile)
    new = profile_candidate(new_profile)
    for role in old:
        if role == ROLE:
            continue
        if old[role] != new[role]:
            raise ValueError(f"unauthorized non-infill material change: {role}")
    old_infill = old[ROLE]
    new_infill = new[ROLE]
    if old_infill.get("metallic") != new_infill.get("metallic") or old_infill.get("roughness") != new_infill.get("roughness"):
        raise ValueError("first hierarchy repair must preserve infill metallic and roughness")
    if old_infill.get("albedo") == new_infill.get("albedo"):
        raise ValueError("infill repair must change albedo")
    if old_profile.get("component_materials") != new_profile.get("component_materials"):
        raise ValueError("component/material mapping drift")


def build(
    donor: dict,
    donor_observer: dict,
    old_profile: dict,
    new_profile: dict,
    new_profile_sha256: str,
    material_payload: dict,
    material_receipt: dict,
    material_head: str,
) -> tuple[dict, dict]:
    if donor.get("schema") != DONOR_SCHEMA or donor.get("status") != DONOR_STATUS:
        raise ValueError("exact Map current-source donor must PASS first")
    if donor.get("building_source_head") != SOURCE_HEAD or donor.get("building_source_revision") != SOURCE_REVISION or donor.get("building_box_topology_revision") != TOPOLOGY:
        raise ValueError("Map donor is not the exact source-owned Building successor")
    if donor.get("building_material_profile_sha256") != PREDECESSOR_PROFILE_SHA256:
        raise ValueError("Map donor material profile is not the exact held predecessor")
    if donor_observer.get("schema") != OBSERVER_SCHEMA or donor_observer.get("status") != OBSERVER_STATUS:
        raise ValueError("Map donor observer compatibility payload drift")
    if material_receipt.get("result") != "PASS_SOURCE_BOUND_BUILDING_SURFACE_PAYLOAD":
        raise ValueError("current Building material payload must PASS source binding")
    if material_receipt.get("hard_surface_source_head") != SOURCE_HEAD:
        raise ValueError("current Building material payload source-head drift")
    if material_receipt.get("source_revision") != SOURCE_REVISION or material_receipt.get("box_topology_revision") != TOPOLOGY:
        raise ValueError("current Building material source identity drift")
    if material_receipt.get("material_profile_sha256") != new_profile_sha256:
        raise ValueError("current material receipt/profile digest drift")
    if material_payload.get("source_identity", {}).get("hard_surface_head") != SOURCE_HEAD:
        raise ValueError("material payload source identity drift")

    validate_single_delta(old_profile, new_profile)
    current_infill = normalized_material(material_payload, ROLE)
    expected_hex = new_profile["candidate"][ROLE]["albedo"]
    if current_infill.get("albedo_hex") != expected_hex:
        raise ValueError("normalized current infill does not match profile")

    states = []
    changed_surface_count = 0
    predecessor_infill = None
    for donor_row in donor.get("states", []):
        row = copy.deepcopy(donor_row)
        scene = row["scene"]
        receiving = scene.get("environment_building_material_receiving", {})
        if receiving.get("asset_id") != BUILDING:
            raise ValueError("missing exact Building receiving row")
        if receiving.get("provenance", {}).get("material_profile_sha256") != PREDECESSOR_PROFILE_SHA256:
            raise ValueError("state predecessor material profile drift")
        surfaces = surface_map(receiving)
        if set(surfaces) != {"frame_galvanized", "infill_coating", "roof_membrane", "slab_mineral", "utility_panel_ochre"}:
            raise ValueError("state five-surface role drift")
        old_materials = {role: copy.deepcopy(surface["material"]) for role, surface in surfaces.items()}
        if predecessor_infill is None:
            predecessor_infill = copy.deepcopy(old_materials[ROLE])
        elif predecessor_infill != old_materials[ROLE]:
            raise ValueError("predecessor infill changed across states")

        surfaces[ROLE]["material"] = copy.deepcopy(current_infill)
        changed_surface_count += 1
        for role, old_material in old_materials.items():
            if role == ROLE:
                if surfaces[role]["material"] == old_material:
                    raise ValueError("infill material failed to change")
            elif surfaces[role]["material"] != old_material:
                raise ValueError(f"unrelated surface material drift: {role}")

        provenance = receiving.setdefault("provenance", {})
        provenance["material_profile_sha256"] = new_profile_sha256
        provenance["building_material_head"] = material_head
        receiving["receiving_policy"] = "EXACT_CURRENT_SOURCE_INFILL_ALBEDO_ONLY_REPAIR_FIXED_WORLD"
        rebind = receiving.setdefault("source_successor_rebind", {})
        rebind["material_head"] = material_head
        rebind["material_profile_sha256"] = new_profile_sha256
        receiving["truth_boundary"] = (
            "Materials changes only the exact source-owned pavilion infill_coating albedo over the already-proven "
            "Map current-source successor world. Frame, roof, slab, service panel, geometry, Weather, Nature, Object, "
            "path, cameras and lighting remain fixed. This is a bounded lookdev candidate, not final acceptance."
        )
        scene["scene_digest"] = scene_digest(scene)
        states.append(row)

    if len(states) != 17 or changed_surface_count != 17:
        raise ValueError("exact 17-state current-world sequence required")

    checks = {
        "exact_current_source_map_donor_passes_first": True,
        "exact_17_state_sequence_preserved": [r.get("time_s") for r in states] == [r.get("time_s") for r in donor.get("states", [])],
        "weather_sequence_preserved": [r.get("weather_field_digest") for r in states] == [r.get("weather_field_digest") for r in donor.get("states", [])],
        "sapling_sequence_preserved": [r.get("sapling_mesh_digest") for r in states] == [r.get("sapling_mesh_digest") for r in donor.get("states", [])],
        "building_source_successor_preserved": donor.get("building_source_head") == SOURCE_HEAD,
        "only_infill_surface_material_changed": changed_surface_count == 17,
        "component_mapping_preserved": old_profile.get("component_materials") == new_profile.get("component_materials"),
        "infill_metallic_preserved": old_profile["candidate"][ROLE]["metallic"] == new_profile["candidate"][ROLE]["metallic"],
        "infill_roughness_preserved": old_profile["candidate"][ROLE]["roughness"] == new_profile["candidate"][ROLE]["roughness"],
        "infill_albedo_changed": old_profile["candidate"][ROLE]["albedo"] != new_profile["candidate"][ROLE]["albedo"],
    }
    if not all(checks.values()):
        raise ValueError(f"current-world infill repair checks failed: {checks}")

    payload = {
        "schema": SCHEMA,
        "study_id": "building-current-world-infill-hierarchy-repair-001",
        "status": STATUS,
        "receiving_head": material_head,
        "map_donor_head": donor.get("receiving_head"),
        "map_donor_composition_digest": donor.get("composition_digest"),
        "weather_variant_head": donor.get("weather_variant_head"),
        "weather_variant_seed": donor.get("weather_variant_seed"),
        "weather_variant_layout_digest": donor.get("weather_variant_layout_digest"),
        "rear_migrated_mesh_digest": donor.get("rear_migrated_mesh_digest"),
        "building_source_head": SOURCE_HEAD,
        "building_source_revision": SOURCE_REVISION,
        "building_box_topology_revision": TOPOLOGY,
        "predecessor_material_profile_sha256": PREDECESSOR_PROFILE_SHA256,
        "material_profile_sha256": new_profile_sha256,
        "material_head": material_head,
        "predecessor_infill": predecessor_infill,
        "candidate_infill": current_infill,
        "checks": checks,
        "states": states,
        "truth_boundary": (
            "PASS proves only that one exact Building Materials successor changes only infill_coating albedo while the exact "
            "source-owned current Map world, all other Building surface values, Weather, Nature, Object, path, cameras and "
            "lighting remain fixed. It does not establish Art Direction/Visual QA acceptance, physical material accuracy, "
            "UV/textures/weathering, renderer equivalence, target-device performance, gameplay, CANON or production readiness."
        ),
        "non_claims": [
            "FINAL_ART_DIRECTION_OR_VISUAL_QA_ACCEPTANCE",
            "PHYSICALLY_MEASURED_MATERIAL_RESPONSE",
            "FINAL_UVS_TEXTURES_DECALS_OR_WEATHERING",
            "RENDERER_EQUIVALENCE",
            "TARGET_DEVICE_RUNTIME_BUDGET",
            "GAMEPLAY_CANON_PRODUCTION_READY_OR_MASTERY",
        ],
    }
    payload["composition_digest"] = digest({
        "map_donor": payload["map_donor_composition_digest"],
        "material_profile": payload["material_profile_sha256"],
        "material_head": material_head,
        "state_scene_digests": [r["scene"]["scene_digest"] for r in states],
    })

    observer = copy.deepcopy(donor_observer)
    observer["receiving_head"] = material_head
    observer["states"] = copy.deepcopy(states)
    observer["compatibility_projection_truth"] = (
        "OBSERVER_COMPATIBILITY_ONLY_CANONICAL_ACCEPTANCE_USES_BUILDING_CURRENT_WORLD_INFILL_REPAIR_SCHEMA"
    )
    return payload, observer


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--donor", required=True)
    p.add_argument("--donor-observer", required=True)
    p.add_argument("--old-profile", required=True)
    p.add_argument("--new-profile", required=True)
    p.add_argument("--material-payload", required=True)
    p.add_argument("--material-receipt", required=True)
    p.add_argument("--material-head", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--observer-output", required=True)
    a = p.parse_args()

    new_profile_path = Path(a.new_profile)
    payload, observer = build(
        json.load(open(a.donor)),
        json.load(open(a.donor_observer)),
        json.load(open(a.old_profile)),
        json.load(open(a.new_profile)),
        file_sha(new_profile_path),
        json.load(open(a.material_payload)),
        json.load(open(a.material_receipt)),
        a.material_head,
    )
    Path(a.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    Path(a.observer_output).write_text(json.dumps(observer, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": payload["status"], "composition_digest": payload["composition_digest"], "checks": payload["checks"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
