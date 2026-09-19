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
PROFILE = ROOT / "procedural/service_pavilion_utility_panel_service_surface_receivers_001.json"
DOMAIN = ROOT / "assets/utility_access_panel_001_service_surface_domain.json"
PLACEMENT_PROFILE = ROOT / "procedural/service_pavilion_utility_panel_receivers_001.json"
PLACEMENT_BUILDER = ROOT / "tools/build_pavilion_utility_panel_receivers.py"
SOURCE_SURFACE_VERIFIER = ROOT / "tools/verify_utility_panel_service_surface_domain.py"
EPS = 1e-12
RESULT = "PASS_SOURCE_OWNED_UTILITY_PANEL_SERVICE_SURFACE_RECEIVER_FAMILY"
DECISION = "PASS_DERIVED_SPATIAL_SURFACE_PARAMETERIZATION_FAMILY_ONLY__NO_UV_MATERIAL_ENVIRONMENT_OR_RUNTIME_ADOPTION"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blob(path):
    rel = Path(path).relative_to(ROOT).as_posix()
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{rel}"], cwd=ROOT, text=True
    ).strip()


def dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def cross(a, b):
    return [
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    ]


def norm(a):
    return math.sqrt(dot(a, a))


def approx(a, b, eps=EPS):
    return abs(float(a) - float(b)) <= eps


def vec_approx(a, b, eps=EPS):
    return len(a) == len(b) and all(approx(x, y, eps) for x, y in zip(a, b))


def verify_profile(profile):
    if profile.get("schema") != "axm.building-utility-panel-service-surface-receiver-family/v0.1":
        raise ValueError("service-surface receiver-family schema drift")
    if profile.get("family_id") != profile.get("schema"):
        raise ValueError("service-surface receiver-family identity drift")

    source = profile.get("source_surface", {})
    if source.get("owner") != "Building Hard Surface":
        raise ValueError("source-surface owner drift")
    if source.get("pr") != 17:
        raise ValueError("source-surface PR identity drift")
    donor_head = source.get("head")
    if donor_head != "fbfa3b47048755b45dac91451171d5511c8d4f47":
        raise ValueError("source-surface donor head drift")
    if source.get("contract_path") != DOMAIN.relative_to(ROOT).as_posix():
        raise ValueError("source-surface contract path drift")
    if source.get("contract_blob_sha") != git_blob(DOMAIN):
        raise ValueError("source-surface contract blob drift")
    if source.get("required_schema") != "axm.building-utility-panel-service-surface-domain/v0.1":
        raise ValueError("source-surface required schema drift")
    if source.get("required_surface_id") != "utility_panel_outer_service_surface":
        raise ValueError("source-surface required identity drift")

    placement = profile.get("placement_family", {})
    if placement.get("owner") != "Building Procedural Design":
        raise ValueError("placement-family owner drift")
    if placement.get("profile_path") != PLACEMENT_PROFILE.relative_to(ROOT).as_posix():
        raise ValueError("placement-family profile path drift")
    if placement.get("profile_blob_sha") != git_blob(PLACEMENT_PROFILE):
        raise ValueError("placement-family profile blob drift")
    if placement.get("required_schema") != "axm.building-utility-panel-receiver-placement-family/v0.1":
        raise ValueError("placement-family required schema drift")
    if placement.get("required_result") != "PASS_EXACT_UTILITY_PANEL_RECEIVER_PLACEMENT_FAMILY":
        raise ValueError("placement-family required result drift")

    receiver_ids = profile.get("receiver_ids")
    if receiver_ids != ["front-utility-bay", "east-utility-bay"]:
        raise ValueError("receiver family identity/order drift")
    if len(set(receiver_ids)) != len(receiver_ids):
        raise ValueError("duplicate receiver id")
    if profile.get("transform_policy") != "EXACT_SOURCE_SURFACE_FRAME_THROUGH_EXACT_RECEIVER_PLACEMENT_NO_SCALE_NO_EXTRA_ROTATION":
        raise ValueError("surface transform policy drift")
    if profile.get("canonical_output_order") != "RECEIVER_ID_LEXICOGRAPHIC":
        raise ValueError("canonical output order drift")
    if profile.get("authority") != "DERIVE_ONLY_SOURCE_OWNED_SERVICE_SURFACE_IN_EXISTING_RECEIVER_FRAMES":
        raise ValueError("procedural authority drift")
    if profile.get("failure_policy") != "FAIL_CLOSED_NO_SURFACE_INFERENCE_NO_FRAME_INFERENCE_NO_EXTENT_REDISCOVERY_NO_UV_NO_MATERIAL_NO_ADOPTION":
        raise ValueError("failure policy drift")


def transform_local_point(placement, point):
    normal, lateral, up = placement["basis_normal_lateral_up"]
    center = placement["center_m"]
    x, y, z = [float(value) for value in point]
    return [
        float(center[axis])
        + x * float(normal[axis])
        + y * float(lateral[axis])
        + z * float(up[axis])
        for axis in range(3)
    ]


def derive_surface(placement, domain):
    if placement.get("panel_asset_id") != domain.get("asset_id"):
        raise ValueError("placement panel identity disagrees with source surface")
    if placement.get("scale") != [1.0, 1.0, 1.0]:
        raise ValueError("service-surface derivation forbids receiver scale")
    if placement.get("extra_rotation_deg") != [0.0, 0.0, 0.0]:
        raise ValueError("service-surface derivation forbids extra receiver rotation")

    basis = placement.get("basis_normal_lateral_up")
    if not isinstance(basis, list) or len(basis) != 3:
        raise ValueError("placement basis missing")
    normal, lateral, up = basis
    if not approx(norm(normal), 1.0) or not approx(norm(lateral), 1.0) or not approx(norm(up), 1.0):
        raise ValueError("placement basis axis is not unit length")
    if not approx(dot(normal, lateral), 0.0) or not approx(dot(normal, up), 0.0) or not approx(dot(lateral, up), 0.0):
        raise ValueError("placement basis is not orthogonal")
    if not vec_approx(cross(lateral, up), normal):
        raise ValueError("placement basis handedness drift")

    frame = domain["reference_frame"]
    if not vec_approx(frame["primary_axis_local"], [0.0, 1.0, 0.0]):
        raise ValueError("source surface primary axis no longer maps to receiver lateral")
    if not vec_approx(frame["secondary_axis_local"], [0.0, 0.0, 1.0]):
        raise ValueError("source surface secondary axis no longer maps to receiver up")
    if not vec_approx(frame["outward_axis_local"], [1.0, 0.0, 0.0]):
        raise ValueError("source surface outward axis no longer maps to receiver normal")

    metric = domain["metric_domain"]
    local_corners = metric["corner_positions_local_m"]
    world_corners = [transform_local_point(placement, point) for point in local_corners]
    world_origin = transform_local_point(placement, frame["origin_local_m"])

    panel_vertices = placement.get("vertices", [])
    for corner in world_corners:
        if not any(vec_approx(corner, vertex) for vertex in panel_vertices):
            raise ValueError("source service-surface corner is not on exact placed panel box")

    primary_span = math.dist(world_corners[0], world_corners[1])
    secondary_span = math.dist(world_corners[1], world_corners[2])
    if not approx(primary_span, metric["primary_extent_m"]):
        raise ValueError("placed primary metric extent drift")
    if not approx(secondary_span, metric["secondary_extent_m"]):
        raise ValueError("placed secondary metric extent drift")
    if not approx(primary_span * secondary_span, metric["area_m2"]):
        raise ValueError("placed service-surface area drift")

    centroid = [sum(point[axis] for point in world_corners) / 4.0 for axis in range(3)]
    if not vec_approx(centroid, world_origin):
        raise ValueError("placed service-surface origin/centroid drift")

    triangle_normal = cross(
        [world_corners[1][axis] - world_corners[0][axis] for axis in range(3)],
        [world_corners[2][axis] - world_corners[0][axis] for axis in range(3)],
    )
    if dot(triangle_normal, normal) <= 0.0:
        raise ValueError("placed service-surface winding no longer faces receiver outward")

    output = {
        "receiver_id": placement["receiver_id"],
        "panel_asset_id": placement["panel_asset_id"],
        "surface_id": domain["surface_id"],
        "source_placement_digest": placement["placement_digest"],
        "world_origin_m": world_origin,
        "world_primary_axis": [float(v) for v in lateral],
        "world_secondary_axis": [float(v) for v in up],
        "world_outward_axis": [float(v) for v in normal],
        "primary_extent_m": float(metric["primary_extent_m"]),
        "secondary_extent_m": float(metric["secondary_extent_m"]),
        "area_m2": float(metric["area_m2"]),
        "corners_m": world_corners,
        "triangles": [[0, 1, 2], [0, 2, 3]],
        "scale": [1.0, 1.0, 1.0],
        "extra_rotation_deg": [0.0, 0.0, 0.0],
    }
    output["world_surface_digest"] = digest_json(output)
    return output


def canonical_family_digest(outputs):
    canonical = sorted(outputs, key=lambda item: item["receiver_id"])
    return digest_json(canonical)


def run_negative_controls(profile, domain, surface_verifier, placements):
    controls = {}

    def expect_hold(name, fn):
        try:
            fn()
            controls[name] = "UNEXPECTED_PASS"
        except (ValueError, KeyError) as exc:
            controls[name] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["source_surface"]["head"] = "0" * 40
    expect_hold("source_surface_donor_head_drift", lambda: verify_profile(bad))

    bad = copy.deepcopy(profile)
    bad["source_surface"]["contract_blob_sha"] = "0" * 40
    expect_hold("source_surface_contract_blob_drift", lambda: verify_profile(bad))

    bad = copy.deepcopy(profile)
    bad["placement_family"]["profile_blob_sha"] = "0" * 40
    expect_hold("placement_family_profile_blob_drift", lambda: verify_profile(bad))

    bad = copy.deepcopy(profile)
    bad["receiver_ids"] = ["front-utility-bay", "front-utility-bay"]
    expect_hold("duplicate_receiver_identity", lambda: verify_profile(bad))

    bad_domain = copy.deepcopy(domain)
    bad_domain["surface_id"] = "invented_surface"
    expect_hold("source_surface_identity_drift", lambda: surface_verifier.verify(domain=bad_domain))

    bad_domain = copy.deepcopy(domain)
    bad_domain["reference_frame"]["outward_axis_local"] = [-1.0, 0.0, 0.0]
    expect_hold("source_surface_outward_axis_drift", lambda: surface_verifier.verify(domain=bad_domain))

    bad_domain = copy.deepcopy(domain)
    bad_domain["metric_domain"]["primary_extent_m"] += 0.001
    expect_hold("source_surface_metric_extent_drift", lambda: surface_verifier.verify(domain=bad_domain))

    bad_placement = copy.deepcopy(placements[0])
    bad_placement["scale"] = [1.0, 1.001, 1.0]
    expect_hold("receiver_scale_injection", lambda: derive_surface(bad_placement, domain))

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("service-surface receiver-family negative control unexpectedly passed")
    return controls


def build(sticker_root=None):
    sticker_root = Path(sticker_root or (ROOT / "external/axm-sticker-fabric")).resolve()
    profile = load(PROFILE)
    domain = load(DOMAIN)
    verify_profile(profile)

    surface_verifier = load_module(SOURCE_SURFACE_VERIFIER, "axm_building_surface_domain_verifier")
    source_receipt = surface_verifier.verify(domain=domain)
    if source_receipt.get("result") != "PASS_SOURCE_OWNED_BUILDING_UTILITY_PANEL_OUTER_SERVICE_SURFACE_METRIC_DOMAIN":
        raise ValueError("source surface prerequisite is not PASS")

    placement_builder = load_module(PLACEMENT_BUILDER, "axm_building_receiver_placement_family")
    placement_summary = placement_builder.build(sticker_root)
    required = profile["placement_family"]
    if placement_summary.get("result") != required["required_result"]:
        raise ValueError("placement-family prerequisite result drift")
    if placement_summary.get("family_id") != required["required_schema"]:
        raise ValueError("placement-family prerequisite schema drift")
    if placement_summary.get("receiver_ids") != profile["receiver_ids"]:
        raise ValueError("placement-family receiver identity drift")
    if placement_summary.get("panel_asset_id") != domain["asset_id"]:
        raise ValueError("placement-family panel identity drift")

    placement_by_id = {item["receiver_id"]: item for item in placement_summary["placements"]}
    outputs = [derive_surface(placement_by_id[receiver_id], domain) for receiver_id in profile["receiver_ids"]]
    canonical_outputs = sorted(outputs, key=lambda item: item["receiver_id"])

    if len({item["world_surface_digest"] for item in outputs}) != 2:
        raise ValueError("world service-surface outputs are not materially distinct")
    if len({digest_json(item["world_outward_axis"]) for item in outputs}) != 2:
        raise ValueError("receiver surface orientations are not materially distinct")
    if abs(dot(outputs[0]["world_outward_axis"], outputs[1]["world_outward_axis"])) > EPS:
        raise ValueError("expected orthogonal receiver surface orientations drifted")

    family_digest = canonical_family_digest(outputs)
    reversed_digest = canonical_family_digest(list(reversed(outputs)))
    if family_digest != reversed_digest:
        raise ValueError("canonical receiver ordering is not deterministic")

    negatives = run_negative_controls(profile, domain, surface_verifier, placement_summary["placements"])

    return {
        "schema": "axm.building-utility-panel-service-surface-receiver-family-evidence/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "family_id": profile["family_id"],
        "source_surface_owner": profile["source_surface"]["owner"],
        "source_surface_head": profile["source_surface"]["head"],
        "source_surface_contract_blob_sha": profile["source_surface"]["contract_blob_sha"],
        "source_surface_result": source_receipt["result"],
        "source_surface_id": domain["surface_id"],
        "source_surface_metric_domain": source_receipt["metric_domain"],
        "placement_family_result": placement_summary["result"],
        "placement_family_id": placement_summary["family_id"],
        "receiver_count": len(outputs),
        "receiver_ids": profile["receiver_ids"],
        "distinct_world_surface_digests": len({item["world_surface_digest"] for item in outputs}),
        "distinct_world_outward_axes": len({digest_json(item["world_outward_axis"]) for item in outputs}),
        "receiver_outward_axis_dot": dot(outputs[0]["world_outward_axis"], outputs[1]["world_outward_axis"]),
        "family_digest": family_digest,
        "reverse_iteration_family_digest": reversed_digest,
        "canonical_order_invariant": family_digest == reversed_digest,
        "outputs": canonical_outputs,
        "negative_controls": negatives,
        "transform_policy": profile["transform_policy"],
        "authority": profile["authority"],
        "failure_policy": profile["failure_policy"],
        "source_geometry_changed": False,
        "uv_authored_or_selected": False,
        "material_authored_or_selected": False,
        "environment_adoption_authorized": False,
        "runtime_acceptance_authorized": False,
        "truth_boundary": profile["truth_boundary"],
    }, source_receipt, placement_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sticker-root", type=Path, default=ROOT / "external/axm-sticker-fabric")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    summary, source_receipt, placement_summary = build(args.sticker_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "outputs.json").write_text(json.dumps(summary["outputs"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "profile.json").write_text(PROFILE.read_text(encoding="utf-8"), encoding="utf-8")
    (args.output_dir / "source-surface-contract.json").write_text(DOMAIN.read_text(encoding="utf-8"), encoding="utf-8")
    (args.output_dir / "source-surface-receipt.json").write_text(json.dumps(source_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "placement-prerequisite-summary.json").write_text(json.dumps(placement_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
