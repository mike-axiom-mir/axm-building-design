#!/usr/bin/env python3
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAVILION = ROOT / "assets/service_pavilion_001.json"
PANEL = ROOT / "assets/utility_access_panel_001.json"
PROFILE = ROOT / "procedural/service_pavilion_utility_panel_receivers_001.json"
HARD_SURFACE_BUILDER = ROOT / "tools/build_service_pavilion.py"
EPS = 1e-9


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_hard_surface_builder():
    spec = importlib.util.spec_from_file_location("build_service_pavilion", HARD_SURFACE_BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_profile(pavilion, panel, profile, observed_pavilion_sha256, observed_panel_sha256):
    if profile.get("schema") != "axm.building-utility-panel-receiver-placement-family/v0.1":
        raise ValueError("receiver-placement profile schema drift")
    if profile.get("family_id") != profile.get("schema"):
        raise ValueError("receiver-placement family identity drift")
    if profile.get("source_asset_id") != pavilion.get("asset_id"):
        raise ValueError("pavilion asset identity drift")
    if profile.get("source_schema") != pavilion.get("schema"):
        raise ValueError("pavilion schema drift")
    if profile.get("source_revision") != pavilion.get("source_revision"):
        raise ValueError("pavilion source revision drift")
    if profile.get("source_pavilion_sha256") != observed_pavilion_sha256:
        raise ValueError("pavilion source SHA-256 drift")
    if profile.get("panel_asset_id") != panel.get("asset_id"):
        raise ValueError("panel asset identity drift")
    if profile.get("panel_schema") != panel.get("schema"):
        raise ValueError("panel schema drift")
    if profile.get("panel_sha256") != observed_panel_sha256:
        raise ValueError("panel source SHA-256 drift")
    if profile.get("required_orientation_contract") != panel.get("orientation_contract"):
        raise ValueError("panel orientation contract drift")
    if profile.get("transform_policy") != "EXACT_SOURCE_FRAME_NO_SCALE_NO_EXTRA_ROTATION":
        raise ValueError("receiver-placement transform policy drift")

    receiver_ids = profile.get("receiver_ids")
    if not isinstance(receiver_ids, list) or len(receiver_ids) < 2:
        raise ValueError("receiver family requires at least two source-owned receivers")
    if len(set(receiver_ids)) != len(receiver_ids):
        raise ValueError("duplicate receiver id")
    source_ids = [item.get("id") for item in pavilion.get("interfaces", [])]
    if receiver_ids != source_ids:
        raise ValueError("receiver id/order set drift from exact source")


def generate_placement(hard_surface, receiver, panel):
    fit = hard_surface.fit_panel(receiver, panel)
    basis = [
        [float(v) for v in receiver["normal"]],
        [float(v) for v in receiver["lateral"]],
        [float(v) for v in receiver["up"]],
    ]
    size = [float(v) for v in panel["proof_geometry"]["size_local_xyz_m"]]
    center = [float(v) for v in fit["panel_center_local_m"]]
    vertices = hard_surface.box_vertices(center, size, tuple(basis))
    hard_surface.require_closed_outward_box(vertices)
    mins = [min(vertex[axis] for vertex in vertices) for axis in range(3)]
    maxs = [max(vertex[axis] for vertex in vertices) for axis in range(3)]
    placement = {
        "receiver_id": receiver["id"],
        "panel_asset_id": panel["asset_id"],
        "center_m": center,
        "basis_normal_lateral_up": basis,
        "size_local_xyz_m": size,
        "vertices": vertices,
        "aabb_min_m": mins,
        "aabb_max_m": maxs,
        "mount_pattern_residual_m": float(fit["mount_pattern_residual_m"]),
        "footprint_margin_m": [float(v) for v in fit["footprint_margin_m"]],
        "body_clearance_beyond_plate_m": float(fit["body_clearance_beyond_plate_m"]),
        "scale": [1.0, 1.0, 1.0],
        "extra_rotation_deg": [0.0, 0.0, 0.0],
    }
    placement["frame_digest"] = digest_json(basis)
    placement["mesh_digest"] = digest_json(vertices)
    placement["placement_digest"] = digest_json(
        {
            "receiver_id": placement["receiver_id"],
            "center_m": center,
            "basis_normal_lateral_up": basis,
            "size_local_xyz_m": size,
            "vertices": vertices,
        }
    )
    return placement


def run_negative_controls(hard_surface, pavilion, panel, profile, pavilion_sha, panel_sha):
    controls = {}

    bad = copy.deepcopy(profile)
    bad["receiver_ids"][1] = bad["receiver_ids"][0]
    try:
        verify_profile(pavilion, panel, bad, pavilion_sha, panel_sha)
        controls["duplicate_receiver_id"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["duplicate_receiver_id"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["receiver_ids"][1] = "roof-service-bay"
    try:
        verify_profile(pavilion, panel, bad, pavilion_sha, panel_sha)
        controls["unknown_receiver_id"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["unknown_receiver_id"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["source_pavilion_sha256"] = "0" * 64
    try:
        verify_profile(pavilion, panel, bad, pavilion_sha, panel_sha)
        controls["pavilion_source_identity_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["pavilion_source_identity_drift"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["panel_sha256"] = "0" * 64
    try:
        verify_profile(pavilion, panel, bad, pavilion_sha, panel_sha)
        controls["panel_source_identity_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["panel_source_identity_drift"] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["required_orientation_contract"] = "invented orientation"
    try:
        verify_profile(pavilion, panel, bad, pavilion_sha, panel_sha)
        controls["orientation_contract_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["orientation_contract_drift"] = "HOLD: " + str(exc)

    bad_receiver = copy.deepcopy(pavilion["interfaces"][0])
    bad_receiver["lateral"] = list(bad_receiver["normal"])
    try:
        generate_placement(hard_surface, bad_receiver, panel)
        controls["nonorthogonal_receiver_frame"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["nonorthogonal_receiver_frame"] = "HOLD: " + str(exc)

    bad_panel = copy.deepcopy(panel)
    bad_panel["accepted_tag"] = "unknown-panel-tag"
    try:
        generate_placement(hard_surface, pavilion["interfaces"][0], bad_panel)
        controls["panel_receiver_tag_mismatch"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["panel_receiver_tag_mismatch"] = "HOLD: " + str(exc)

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("receiver-placement negative control unexpectedly passed")
    return controls


def build():
    pavilion = load(PAVILION)
    panel = load(PANEL)
    profile = load(PROFILE)
    pavilion_sha = sha256(PAVILION)
    panel_sha = sha256(PANEL)
    hard_surface = load_hard_surface_builder()

    verify_profile(pavilion, panel, profile, pavilion_sha, panel_sha)

    # Re-run the exact source-owned Hard-Surface prerequisite rather than copying its fit facts.
    base_pavilion, base_panel, base_fits, _, _, _, _, base_negatives, topology_summary = hard_surface.build()
    if base_pavilion["asset_id"] != pavilion["asset_id"] or base_panel["asset_id"] != panel["asset_id"]:
        raise ValueError("Hard-Surface prerequisite source identity drift")
    if len(base_fits) != len(profile["receiver_ids"]):
        raise ValueError("Hard-Surface prerequisite receiver count drift")
    if any(float(item["mount_pattern_residual_m"]) > EPS for item in base_fits):
        raise ValueError("Hard-Surface prerequisite mount residual drift")
    if any(not state.startswith("REJECTED") for state in base_negatives.values()):
        raise ValueError("Hard-Surface prerequisite negative control drift")
    if topology_summary.get("object_count") != 19 or topology_summary.get("triangle_count") != 228:
        raise ValueError("Hard-Surface prerequisite topology aggregate drift")

    receiver_by_id = {item["id"]: item for item in pavilion["interfaces"]}
    placements = [
        generate_placement(hard_surface, receiver_by_id[receiver_id], panel)
        for receiver_id in profile["receiver_ids"]
    ]

    if len({item["placement_digest"] for item in placements}) != len(placements):
        raise ValueError("receiver placements are not materially distinct")
    if len({item["mesh_digest"] for item in placements}) != len(placements):
        raise ValueError("transformed receiver meshes are not materially distinct")
    if len({item["frame_digest"] for item in placements}) != len(placements):
        raise ValueError("receiver frames are not materially distinct")

    normal_dot = sum(
        placements[0]["basis_normal_lateral_up"][0][axis]
        * placements[1]["basis_normal_lateral_up"][0][axis]
        for axis in range(3)
    )
    if abs(normal_dot) > EPS:
        raise ValueError("source receiver normals are no longer orthogonal")

    negatives = run_negative_controls(
        hard_surface, pavilion, panel, profile, pavilion_sha, panel_sha
    )

    return {
        "result": "PASS_EXACT_UTILITY_PANEL_RECEIVER_PLACEMENT_FAMILY",
        "schema": "axm.building-utility-panel-receiver-placement-evidence/v0.1",
        "family_id": profile["family_id"],
        "source_asset_id": pavilion["asset_id"],
        "source_schema": pavilion["schema"],
        "source_revision": pavilion["source_revision"],
        "source_pavilion_sha256": pavilion_sha,
        "panel_asset_id": panel["asset_id"],
        "panel_schema": panel["schema"],
        "panel_sha256": panel_sha,
        "orientation_contract": panel["orientation_contract"],
        "transform_policy": profile["transform_policy"],
        "authority": profile["authority"],
        "failure_policy": profile["failure_policy"],
        "receiver_count": len(placements),
        "receiver_ids": [item["receiver_id"] for item in placements],
        "distinct_placement_digests": len({item["placement_digest"] for item in placements}),
        "distinct_mesh_digests": len({item["mesh_digest"] for item in placements}),
        "distinct_frame_digests": len({item["frame_digest"] for item in placements}),
        "receiver_normal_dot": normal_dot,
        "placements": placements,
        "base_builder_procedural_coverage_with_rows": "17/19",
        "successor_composition_procedural_coverage_with_header_expansion": "21/23",
        "manual_boxes_outside_procedural_families": ["slab", "roof"],
        "hard_surface_prerequisite": {
            "result": "PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF",
            "receiver_fit_count": len(base_fits),
            "box_topology_revision": topology_summary.get("revision"),
            "real_box_output_count": topology_summary.get("object_count"),
            "triangle_count": topology_summary.get("triangle_count"),
        },
        "negative_controls": negatives,
        "truth_boundary": profile["truth_boundary"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    summary = build()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (args.output_dir / "placements.json").write_text(
            json.dumps(summary["placements"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (args.output_dir / "profile.json").write_text(
            PROFILE.read_text(encoding="utf-8"), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
