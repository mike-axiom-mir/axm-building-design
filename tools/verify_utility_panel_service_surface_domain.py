#!/usr/bin/env python3
import argparse
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = ROOT / "assets/utility_access_panel_001.json"
DOMAIN_PATH = ROOT / "assets/utility_access_panel_001_service_surface_domain.json"
EPS = 1e-12
RESULT = "PASS_SOURCE_OWNED_BUILDING_UTILITY_PANEL_OUTER_SERVICE_SURFACE_METRIC_DOMAIN"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def norm(a):
    return math.sqrt(dot(a, a))


def approx(a, b, eps=EPS):
    return abs(float(a) - float(b)) <= eps


def vec_approx(a, b, eps=EPS):
    return len(a) == len(b) and all(approx(x, y, eps) for x, y in zip(a, b))


def git_blob(path):
    rel = path.relative_to(ROOT).as_posix()
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{rel}"], cwd=ROOT, text=True
    ).strip()


def verify(panel=None, domain=None):
    panel = panel or load(PANEL_PATH)
    domain = domain or load(DOMAIN_PATH)

    if panel.get("schema") != "axm.building-utility-panel/v0.1":
        raise ValueError("panel schema drift")
    if panel.get("asset_id") != "utility-access-panel-001":
        raise ValueError("panel asset identity drift")
    if panel.get("units") != "meters":
        raise ValueError("panel units drift")

    if domain.get("schema") != "axm.building-utility-panel-service-surface-domain/v0.1":
        raise ValueError("service-surface domain schema drift")
    if domain.get("asset_id") != panel["asset_id"]:
        raise ValueError("domain asset identity does not match panel")
    if domain.get("surface_id") != "utility_panel_outer_service_surface":
        raise ValueError("service-surface identity drift")
    if domain.get("units") != panel["units"]:
        raise ValueError("domain units do not match panel")
    if domain.get("face_selector") != "LOCAL_POSITIVE_X_OUTER_FACE":
        raise ValueError("service surface is not bound to the source +X outer face")

    source = domain.get("source_panel", {})
    if source.get("path") != "assets/utility_access_panel_001.json":
        raise ValueError("source panel path drift")
    if source.get("schema") != panel["schema"]:
        raise ValueError("source panel schema binding drift")
    actual_blob = git_blob(PANEL_PATH)
    if source.get("git_blob_sha") != actual_blob:
        raise ValueError(f"source panel blob drift: {actual_blob}")

    proof = panel.get("proof_geometry", {})
    if proof.get("kind") != "box":
        raise ValueError("panel proof geometry is not the expected source box")
    size = proof.get("size_local_xyz_m")
    if not isinstance(size, list) or len(size) != 3:
        raise ValueError("panel source box size missing")
    depth, primary_extent, secondary_extent = map(float, size)
    footprint = panel.get("interface_footprint_m")
    if not isinstance(footprint, list) or len(footprint) != 2:
        raise ValueError("panel interface footprint missing")
    if not approx(primary_extent, footprint[0]) or not approx(secondary_extent, footprint[1]):
        raise ValueError("proof-box service-surface extents disagree with source interface footprint")

    frame = domain.get("reference_frame", {})
    origin = frame.get("origin_local_m")
    primary = frame.get("primary_axis_local")
    secondary = frame.get("secondary_axis_local")
    outward = frame.get("outward_axis_local")
    expected_origin = [depth / 2.0, 0.0, 0.0]
    if not vec_approx(origin, expected_origin):
        raise ValueError("service-surface origin is not the exact +X proof-box face center")
    if not vec_approx(primary, [0.0, 1.0, 0.0]):
        raise ValueError("service-surface primary axis drift")
    if not vec_approx(secondary, [0.0, 0.0, 1.0]):
        raise ValueError("service-surface secondary axis drift")
    if not vec_approx(outward, [1.0, 0.0, 0.0]):
        raise ValueError("service-surface outward axis drift")
    for name, axis in (("primary", primary), ("secondary", secondary), ("outward", outward)):
        if not approx(norm(axis), 1.0):
            raise ValueError(f"{name} service-surface axis is not unit length")
    if not approx(dot(primary, secondary), 0.0) or not approx(dot(primary, outward), 0.0) or not approx(dot(secondary, outward), 0.0):
        raise ValueError("service-surface frame is not orthogonal")
    if not vec_approx(cross(primary, secondary), outward):
        raise ValueError("service-surface frame handedness drift")

    metric = domain.get("metric_domain", {})
    if not approx(metric.get("primary_extent_m"), primary_extent):
        raise ValueError("primary metric extent drift")
    if not approx(metric.get("secondary_extent_m"), secondary_extent):
        raise ValueError("secondary metric extent drift")
    expected_area = primary_extent * secondary_extent
    if not approx(metric.get("area_m2"), expected_area):
        raise ValueError("service-surface metric area drift")

    expected_corners = [
        [depth / 2.0, -primary_extent / 2.0, -secondary_extent / 2.0],
        [depth / 2.0, primary_extent / 2.0, -secondary_extent / 2.0],
        [depth / 2.0, primary_extent / 2.0, secondary_extent / 2.0],
        [depth / 2.0, -primary_extent / 2.0, secondary_extent / 2.0],
    ]
    corners = metric.get("corner_positions_local_m")
    if not isinstance(corners, list) or len(corners) != 4:
        raise ValueError("service-surface corner domain must contain exactly four corners")
    if any(not vec_approx(observed, expected) for observed, expected in zip(corners, expected_corners)):
        raise ValueError("service-surface corner positions drift from exact source box face")

    structure = domain.get("source_face_structure", {})
    if structure.get("vertex_count") != 4 or structure.get("triangle_count") != 2:
        raise ValueError("source service-surface face structure drift")
    if structure.get("derived_from_proof_box") is not True:
        raise ValueError("source service-surface derivation is not explicit")

    authority = domain.get("authority", {})
    if authority.get("owner") != "Building Hard Surface":
        raise ValueError("service-surface source authority drift")
    forbidden = {"UV mapping", "material response", "texture payload", "environment adoption", "visual acceptance"}
    downstream = set(authority.get("downstream_owned_facts", []))
    if not forbidden.issubset(downstream):
        raise ValueError("downstream authority boundary weakened")

    return {
        "schema": "axm.building-utility-panel-service-surface-domain-evidence/v0.1",
        "result": RESULT,
        "asset_id": panel["asset_id"],
        "surface_id": domain["surface_id"],
        "source_panel_blob_sha": actual_blob,
        "face_selector": domain["face_selector"],
        "reference_frame": frame,
        "metric_domain": {
            "primary_extent_m": primary_extent,
            "secondary_extent_m": secondary_extent,
            "area_m2": expected_area,
            "corner_positions_local_m": expected_corners,
        },
        "source_face_structure": {"vertex_count": 4, "triangle_count": 2},
        "source_geometry_changed": False,
        "uv_authored_or_selected": False,
        "material_authored_or_selected": False,
        "downstream_adoption_authorized": False,
        "reusable_observation": "MANUFACTURED_SERVICE_SURFACE_SOURCE_OWNS_IDENTITY_FRAME_AND_METRIC_DOMAIN_BEFORE_SPATIAL_PARAMETERIZATION",
        "truth_boundary": domain["truth_boundary"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = verify()
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
