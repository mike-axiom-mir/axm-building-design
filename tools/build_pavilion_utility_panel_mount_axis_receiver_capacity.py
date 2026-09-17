#!/usr/bin/env python3
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "procedural/service_pavilion_utility_panel_mount_axis_receiver_capacity_001.json"
SURFACE_PROFILE = ROOT / "procedural/service_pavilion_utility_panel_service_surface_receivers_001.json"
SURFACE_BUILDER = ROOT / "tools/build_pavilion_utility_panel_service_surface_receivers.py"
EPS = 1e-12

HARD_SURFACE_HEAD = "2a5df5fa720ec939bf0e935f2cb8bc3d94049d89"
CAPACITY_PATH = "assets/utility_panel_mount_axis_clearance_capacity_001.json"
CAPACITY_BLOB = "e8efe188156f4a0e09706d7d2a45b0723b1d3920"
PANEL_PATH = "assets/utility_access_panel_001.json"
PANEL_BLOB = "4da242e35a84b20a80f4acf28146be613624e734"
SURFACE_PROFILE_BLOB = "fdf9a1933e928959fe6477f83e2b017ea481249d"
SURFACE_BUILDER_BLOB = "7d196565d3c97368fbe5e701fd1c93d223a73cff"

RESULT = "PASS_BOUNDED_UTILITY_PANEL_MOUNT_AXIS_RECEIVER_CAPACITY_FAMILY"
DECISION = "PASS_DERIVED_WORLD_MOUNT_AXIS_CAPACITY_FAMILY_ONLY__NO_RESERVATION_FASTENER_TOOLING_OR_ADOPTION"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def git_blob_at(head, path):
    return subprocess.check_output(
        ["git", "rev-parse", f"{head}:{path}"], cwd=ROOT, text=True
    ).strip()


def git_bytes_at(head, path):
    return subprocess.check_output(
        ["git", "show", f"{head}:{path}"], cwd=ROOT
    )


def git_json_at(head, path):
    return json.loads(git_bytes_at(head, path).decode("utf-8"))


def current_blob(path):
    rel = Path(path).relative_to(ROOT).as_posix()
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{rel}"], cwd=ROOT, text=True
    ).strip()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def approx(a, b, eps=EPS):
    return abs(float(a) - float(b)) <= eps


def vec_add(a, b):
    return [float(x) + float(y) for x, y in zip(a, b)]


def vec_scale(a, scale):
    return [float(x) * float(scale) for x in a]


def dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def distance(a, b):
    return math.dist([float(x) for x in a], [float(x) for x in b])


def pairwise_distances(points):
    values = []
    for left in range(len(points)):
        for right in range(left + 1, len(points)):
            values.append(distance(points[left], points[right]))
    return sorted(values)


def verify_profile(profile):
    schema = "axm.building-utility-panel-mount-axis-receiver-capacity-family/v0.1"
    if profile.get("schema") != schema or profile.get("family_id") != schema:
        raise ValueError("mount-axis receiver-capacity family identity drift")

    source = profile.get("hard_surface_capacity", {})
    if source.get("owner") != "Building Hard Surface" or source.get("pr") != 5:
        raise ValueError("Hard-Surface capacity owner drift")
    if source.get("head") != HARD_SURFACE_HEAD:
        raise ValueError("Hard-Surface capacity head drift")
    if source.get("contract_path") != CAPACITY_PATH:
        raise ValueError("capacity contract path drift")
    if source.get("contract_blob_sha") != CAPACITY_BLOB:
        raise ValueError("declared capacity contract blob drift")
    if source.get("panel_path") != PANEL_PATH:
        raise ValueError("panel source path drift")
    if source.get("panel_blob_sha") != PANEL_BLOB:
        raise ValueError("declared panel source blob drift")
    if git_blob_at(source["head"], source["contract_path"]) != CAPACITY_BLOB:
        raise ValueError("observed capacity contract blob drift")
    if git_blob_at(source["head"], source["panel_path"]) != PANEL_BLOB:
        raise ValueError("observed panel source blob drift")

    surface = profile.get("receiver_surface_family", {})
    if surface.get("owner") != "Building Procedural Design":
        raise ValueError("receiver surface-family owner drift")
    if surface.get("profile_path") != SURFACE_PROFILE.relative_to(ROOT).as_posix():
        raise ValueError("receiver surface profile path drift")
    if surface.get("profile_blob_sha") != SURFACE_PROFILE_BLOB:
        raise ValueError("declared receiver surface profile blob drift")
    if surface.get("builder_path") != SURFACE_BUILDER.relative_to(ROOT).as_posix():
        raise ValueError("receiver surface builder path drift")
    if surface.get("builder_blob_sha") != SURFACE_BUILDER_BLOB:
        raise ValueError("declared receiver surface builder blob drift")
    if current_blob(SURFACE_PROFILE) != SURFACE_PROFILE_BLOB:
        raise ValueError("observed receiver surface profile blob drift")
    if current_blob(SURFACE_BUILDER) != SURFACE_BUILDER_BLOB:
        raise ValueError("observed receiver surface builder blob drift")
    if surface.get("required_result") != "PASS_SOURCE_OWNED_UTILITY_PANEL_SERVICE_SURFACE_RECEIVER_FAMILY":
        raise ValueError("receiver surface prerequisite result drift")

    if profile.get("receiver_ids") != ["front-utility-bay", "east-utility-bay"]:
        raise ValueError("receiver identity/order drift")
    if len(set(profile["receiver_ids"])) != 2:
        raise ValueError("duplicate receiver identity")
    if profile.get("axis_identity_policy") != "SOURCE_MOUNT_POINT_ORDER_IS_IDENTITY__NO_RENUMBERING":
        raise ValueError("axis identity policy drift")
    if profile.get("world_transform_policy") != (
        "SOURCE_LOCAL_YZ_POINT_THROUGH_EXISTING_SERVICE_SURFACE_PRIMARY_SECONDARY_FRAME__AXIS_ALONG_WORLD_OUTWARD"
    ):
        raise ValueError("world transform policy drift")
    if profile.get("canonical_output_order") != "RECEIVER_ID_THEN_SOURCE_MOUNT_INDEX":
        raise ValueError("canonical output order drift")
    if profile.get("reservation_radius_selected") is not False or profile.get("selected_radius_m") is not None:
        raise ValueError("Procedural must not select a reservation radius")
    if profile.get("fastener_geometry_selected") is not False:
        raise ValueError("Procedural must not select fastener geometry")
    if profile.get("tooling_envelope_selected") is not False:
        raise ValueError("Procedural must not select a tooling envelope")
    if profile.get("automatic_receiver_adoption") is not False:
        raise ValueError("Procedural must not authorize receiver adoption")


def verify_capacity_contract(contract, panel):
    if contract.get("schema") != "axm.building-panel-mount-axis-clearance-capacity/v0.1":
        raise ValueError("capacity contract schema drift")
    if contract.get("applies_to_asset_id") != panel.get("asset_id"):
        raise ValueError("capacity/panel asset identity drift")
    if contract.get("units") != "meters" or panel.get("units") != "meters":
        raise ValueError("capacity units drift")
    if contract.get("reservation_radius_selected") is not False:
        raise ValueError("owner contract unexpectedly selected a radius")
    if contract.get("fastener_geometry_established") is not False:
        raise ValueError("owner contract unexpectedly establishes fastener geometry")
    if contract.get("tooling_envelope_established") is not False:
        raise ValueError("owner contract unexpectedly establishes tooling")
    if contract.get("retention_method_established") is not False:
        raise ValueError("owner contract unexpectedly establishes retention")

    mounts = panel.get("mount_points_local_m")
    footprint = panel.get("interface_footprint_m")
    if not isinstance(mounts, list) or len(mounts) != 4:
        raise ValueError("source mount-axis cardinality drift")
    if len({tuple(float(v) for v in point) for point in mounts}) != 4:
        raise ValueError("duplicate source mount axis")
    if not isinstance(footprint, list) or len(footprint) != 2:
        raise ValueError("panel footprint drift")
    half_y, half_z = float(footprint[0]) / 2.0, float(footprint[1]) / 2.0

    boundary = min(
        min(half_y - abs(float(y)), half_z - abs(float(z)))
        for y, z in mounts
    )
    pair_min = min(pairwise_distances(mounts))
    cap = min(boundary, pair_min / 2.0)
    observed = contract.get("observed_capacity", {})
    if observed.get("mount_axis_count") != len(mounts):
        raise ValueError("capacity mount-axis count drift")
    if not approx(observed.get("minimum_axis_to_footprint_boundary_m"), boundary):
        raise ValueError("capacity footprint-boundary drift")
    if not approx(observed.get("minimum_axis_pair_distance_m"), pair_min):
        raise ValueError("capacity pair-distance drift")
    if not approx(observed.get("closed_common_reservation_tangency_cap_m"), cap):
        raise ValueError("capacity closed-cap drift")
    if observed.get("limiting_constraint") != "FOOTPRINT_EDGE":
        raise ValueError("capacity limiting constraint drift")
    if observed.get("capacity_invariant_under_supported_180_degree_reversal") is not True:
        raise ValueError("capacity reversal invariant drift")
    if cap <= 0.0:
        raise ValueError("nonpositive source geometric capacity")
    return {
        "mount_points_local_yz_m": [[float(v) for v in point] for point in mounts],
        "interface_footprint_yz_m": [float(v) for v in footprint],
        "minimum_axis_to_footprint_boundary_m": float(observed["minimum_axis_to_footprint_boundary_m"]),
        "minimum_axis_pair_distance_m": float(observed["minimum_axis_pair_distance_m"]),
        "closed_common_reservation_tangency_cap_m": float(observed["closed_common_reservation_tangency_cap_m"]),
        "limiting_constraint": observed["limiting_constraint"],
        "maximum_capacity_recompute_residual_m": max(
            abs(float(observed["minimum_axis_to_footprint_boundary_m"]) - boundary),
            abs(float(observed["minimum_axis_pair_distance_m"]) - pair_min),
            abs(float(observed["closed_common_reservation_tangency_cap_m"]) - cap),
        ),
    }


def mount_world_origin(surface, local_yz):
    y, z = [float(v) for v in local_yz]
    origin = [float(v) for v in surface["world_origin_m"]]
    primary = [float(v) for v in surface["world_primary_axis"]]
    secondary = [float(v) for v in surface["world_secondary_axis"]]
    return vec_add(origin, vec_add(vec_scale(primary, y), vec_scale(secondary, z)))


def derive_receiver(surface, capacity):
    if surface.get("surface_id") != "utility_panel_outer_service_surface":
        raise ValueError("receiver source surface identity drift")
    if not approx(surface.get("primary_extent_m"), capacity["interface_footprint_yz_m"][0]):
        raise ValueError("receiver/source primary extent disagreement")
    if not approx(surface.get("secondary_extent_m"), capacity["interface_footprint_yz_m"][1]):
        raise ValueError("receiver/source secondary extent disagreement")

    outward = [float(v) for v in surface.get("world_outward_axis", [])]
    primary = [float(v) for v in surface.get("world_primary_axis", [])]
    secondary = [float(v) for v in surface.get("world_secondary_axis", [])]
    if len(outward) != 3 or len(primary) != 3 or len(secondary) != 3:
        raise ValueError("receiver frame cardinality drift")
    if not approx(norm(outward), 1.0) or not approx(norm(primary), 1.0) or not approx(norm(secondary), 1.0):
        raise ValueError("receiver frame unit-axis drift")
    if not approx(dot(outward, primary), 0.0) or not approx(dot(outward, secondary), 0.0) or not approx(dot(primary, secondary), 0.0):
        raise ValueError("receiver frame orthogonality drift")

    axes = []
    for index, point in enumerate(capacity["mount_points_local_yz_m"]):
        axis = {
            "source_mount_index": index,
            "source_local_yz_m": [float(v) for v in point],
            "world_axis_origin_on_outer_service_surface_m": mount_world_origin(surface, point),
            "world_axis_direction": outward,
            "closed_common_reservation_tangency_cap_m": capacity["closed_common_reservation_tangency_cap_m"],
            "reservation_radius_selected": False,
        }
        axis["axis_digest"] = digest_json(axis)
        axes.append(axis)

    source_distances = pairwise_distances(capacity["mount_points_local_yz_m"])
    world_distances = pairwise_distances(
        [axis["world_axis_origin_on_outer_service_surface_m"] for axis in axes]
    )
    residual = max(abs(a - b) for a, b in zip(source_distances, world_distances))

    reversed_origins = sorted(
        tuple(round(v, 12) for v in mount_world_origin(surface, [-point[0], -point[1]]))
        for point in capacity["mount_points_local_yz_m"]
    )
    original_origins = sorted(
        tuple(round(v, 12) for v in axis["world_axis_origin_on_outer_service_surface_m"])
        for axis in axes
    )
    if reversed_origins != original_origins:
        raise ValueError("receiver mount-axis set lost source 180-degree reversal symmetry")

    output = {
        "receiver_id": surface["receiver_id"],
        "source_surface_digest": surface["world_surface_digest"],
        "world_surface_origin_m": [float(v) for v in surface["world_origin_m"]],
        "world_outward_axis": outward,
        "world_primary_axis": primary,
        "world_secondary_axis": secondary,
        "axis_count": len(axes),
        "axes": axes,
        "minimum_axis_to_footprint_boundary_m": capacity["minimum_axis_to_footprint_boundary_m"],
        "minimum_axis_pair_distance_m": capacity["minimum_axis_pair_distance_m"],
        "closed_common_reservation_tangency_cap_m": capacity["closed_common_reservation_tangency_cap_m"],
        "limiting_constraint": capacity["limiting_constraint"],
        "maximum_pair_distance_residual_m": residual,
        "supported_180_degree_reversal_axis_set_equal": True,
        "reservation_radius_selected": False,
        "fastener_geometry_selected": False,
        "tooling_envelope_selected": False,
    }
    output["receiver_axis_set_digest"] = digest_json(output)
    return output


def family_digest(outputs):
    canonical = sorted(outputs, key=lambda item: item["receiver_id"])
    return digest_json(canonical)


def run_negative_controls(profile, contract, panel, surface_outputs):
    controls = {}

    def expect_hold(name, fn):
        try:
            fn()
            controls[name] = "UNEXPECTED_PASS"
        except (ValueError, KeyError, TypeError) as exc:
            controls[name] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["hard_surface_capacity"]["head"] = "0" * 40
    expect_hold("hard_surface_capacity_head_drift", lambda: verify_profile(bad))

    bad = copy.deepcopy(profile)
    bad["hard_surface_capacity"]["contract_blob_sha"] = "0" * 40
    expect_hold("capacity_contract_blob_drift", lambda: verify_profile(bad))

    bad = copy.deepcopy(profile)
    bad["hard_surface_capacity"]["panel_blob_sha"] = "0" * 40
    expect_hold("panel_source_blob_drift", lambda: verify_profile(bad))

    bad = copy.deepcopy(profile)
    bad["receiver_ids"] = ["front-utility-bay", "front-utility-bay"]
    expect_hold("duplicate_receiver_identity", lambda: verify_profile(bad))

    bad = copy.deepcopy(profile)
    bad["selected_radius_m"] = 0.01
    bad["reservation_radius_selected"] = True
    expect_hold("procedural_radius_selection", lambda: verify_profile(bad))

    bad_contract = copy.deepcopy(contract)
    bad_contract["observed_capacity"]["closed_common_reservation_tangency_cap_m"] = 0.051
    expect_hold("source_capacity_drift", lambda: verify_capacity_contract(bad_contract, panel))

    bad_panel = copy.deepcopy(panel)
    bad_panel["mount_points_local_m"][0][0] += 0.001
    expect_hold("source_mount_axis_drift", lambda: verify_capacity_contract(contract, bad_panel))

    bad_surface = copy.deepcopy(surface_outputs[0])
    bad_surface["world_outward_axis"] = [2.0, 0.0, 0.0]
    capacity = verify_capacity_contract(contract, panel)
    expect_hold("receiver_frame_axis_drift", lambda: derive_receiver(bad_surface, capacity))

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("mount-axis receiver-capacity negative control unexpectedly passed")
    return controls


def build(sticker_root=None):
    sticker_root = Path(sticker_root or (ROOT / "external/axm-sticker-fabric")).resolve()
    profile = load(PROFILE)
    verify_profile(profile)

    source = profile["hard_surface_capacity"]
    contract = git_json_at(source["head"], source["contract_path"])
    panel = git_json_at(source["head"], source["panel_path"])
    capacity = verify_capacity_contract(contract, panel)

    source_panel_sha256 = hashlib.sha256(git_bytes_at(source["head"], source["panel_path"])).hexdigest()
    declared_source_sha256 = contract.get("source_authority", {}).get("panel_source_sha256")
    if source_panel_sha256 != declared_source_sha256:
        raise ValueError("Hard-Surface capacity contract/panel SHA-256 disagreement")

    surface_builder = load_module(SURFACE_BUILDER, "axm_building_service_surface_receiver_family")
    surface_summary = surface_builder.build(sticker_root)
    required_surface = profile["receiver_surface_family"]
    if surface_summary.get("result") != required_surface["required_result"]:
        raise ValueError("receiver surface-family prerequisite result drift")
    if surface_summary.get("receiver_ids") != profile["receiver_ids"]:
        raise ValueError("receiver surface-family identity/order drift")

    surface_by_id = {item["receiver_id"]: item for item in surface_summary["outputs"]}
    outputs = [
        derive_receiver(surface_by_id[receiver_id], capacity)
        for receiver_id in profile["receiver_ids"]
    ]

    if len(outputs) != 2 or len({item["receiver_axis_set_digest"] for item in outputs}) != 2:
        raise ValueError("receiver mount-axis outputs are not materially distinct")
    if sum(item["axis_count"] for item in outputs) != 8:
        raise ValueError("expected eight transformed mount axes")
    if len({
        tuple(round(v, 12) for v in axis["world_axis_origin_on_outer_service_surface_m"])
        for output in outputs for axis in output["axes"]
    }) != 8:
        raise ValueError("world mount-axis origins are not materially distinct")
    if abs(dot(outputs[0]["world_outward_axis"], outputs[1]["world_outward_axis"])) > EPS:
        raise ValueError("receiver mount-axis directions are no longer orthogonal")
    if max(item["maximum_pair_distance_residual_m"] for item in outputs) > EPS:
        raise ValueError("rigid receiver transform changed source mount-axis spacing")

    digest = family_digest(outputs)
    reverse_digest = family_digest(list(reversed(outputs)))
    if digest != reverse_digest:
        raise ValueError("canonical receiver family digest depends on iteration order")

    negatives = run_negative_controls(profile, contract, panel, surface_summary["outputs"])

    return {
        "schema": "axm.building-utility-panel-mount-axis-receiver-capacity-family-evidence/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "family_id": profile["family_id"],
        "hard_surface_capacity_head": source["head"],
        "capacity_contract_blob_sha": source["contract_blob_sha"],
        "panel_source_blob_sha": source["panel_blob_sha"],
        "panel_source_sha256": source_panel_sha256,
        "receiver_surface_family_result": surface_summary["result"],
        "receiver_surface_family_digest": surface_summary["family_digest"],
        "receiver_ids": [item["receiver_id"] for item in outputs],
        "receiver_count": len(outputs),
        "source_mount_axis_count": len(capacity["mount_points_local_yz_m"]),
        "world_axis_count": sum(item["axis_count"] for item in outputs),
        "distinct_receiver_axis_set_digests": len({item["receiver_axis_set_digest"] for item in outputs}),
        "distinct_world_axis_origins": len({
            tuple(round(v, 12) for v in axis["world_axis_origin_on_outer_service_surface_m"])
            for output in outputs for axis in output["axes"]
        }),
        "closed_common_reservation_tangency_cap_m": capacity["closed_common_reservation_tangency_cap_m"],
        "minimum_axis_to_footprint_boundary_m": capacity["minimum_axis_to_footprint_boundary_m"],
        "minimum_axis_pair_distance_m": capacity["minimum_axis_pair_distance_m"],
        "limiting_constraint": capacity["limiting_constraint"],
        "maximum_capacity_recompute_residual_m": capacity["maximum_capacity_recompute_residual_m"],
        "maximum_pair_distance_residual_m": max(item["maximum_pair_distance_residual_m"] for item in outputs),
        "receiver_outward_axis_dot": dot(outputs[0]["world_outward_axis"], outputs[1]["world_outward_axis"]),
        "all_receivers_preserve_180_degree_axis_set": all(
            item["supported_180_degree_reversal_axis_set_equal"] for item in outputs
        ),
        "canonical_order_invariant": digest == reverse_digest,
        "family_digest": digest,
        "reverse_iteration_family_digest": reverse_digest,
        "outputs": sorted(outputs, key=lambda item: item["receiver_id"]),
        "negative_controls": negatives,
        "reservation_radius_selected": False,
        "selected_radius_m": None,
        "fastener_geometry_selected": False,
        "tooling_envelope_selected": False,
        "source_geometry_changed": False,
        "receiver_geometry_changed": False,
        "automatic_receiver_adoption": False,
        "truth_boundary": profile["truth_boundary"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sticker-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--exact-head", default="")
    args = parser.parse_args()

    summary = build(args.sticker_root)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for item in summary["outputs"]:
        (out / f"{item['receiver_id']}.json").write_text(
            json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (out / "family-profile.json").write_text(PROFILE.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "hard-surface-capacity-contract.json").write_bytes(
        git_bytes_at(HARD_SURFACE_HEAD, CAPACITY_PATH)
    )
    (out / "hard-surface-panel-source.json").write_bytes(
        git_bytes_at(HARD_SURFACE_HEAD, PANEL_PATH)
    )
    if args.exact_head:
        (out / "exact-head.txt").write_text(args.exact_head.strip() + "\n", encoding="utf-8")
    (out / "hard-surface-head.txt").write_text(HARD_SURFACE_HEAD + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
