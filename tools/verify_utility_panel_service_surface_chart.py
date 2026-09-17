#!/usr/bin/env python3
import argparse
import copy
import importlib.util
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "geometry/utility_access_panel_service_surface_chart_001.json"
DOMAIN_PATH = ROOT / "assets/utility_access_panel_001_service_surface_domain.json"
SOURCE_VERIFIER_PATH = ROOT / "tools/verify_utility_panel_service_surface_domain.py"
EPS = 1e-12
RESULT = "PASS_BUILDING_UTILITY_PANEL_UV_READY_SOURCE_FRAME_CHART"
DECISION = "PASS_DERIVED_GEOMETRY_CHART_ONLY__NO_TEXEL_DENSITY_ATLAS_MATERIAL_RECEIVER_OR_VISUAL_ADOPTION"
PATTERN = "SOURCE_OWNED_PLANAR_FRAME_TO_BIJECTIVE_UV_READY_CHART_BEFORE_TEXEL_DENSITY_ATLAS_OR_MATERIAL_POLICY"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blob(path):
    rel = Path(path).relative_to(ROOT).as_posix()
    return subprocess.check_output(["git", "rev-parse", f"HEAD:{rel}"], cwd=ROOT, text=True).strip()


def dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def cross(a, b):
    return [
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    ]


def add3(a, b):
    return [float(a[i]) + float(b[i]) for i in range(3)]


def mul3(v, scalar):
    return [float(value) * float(scalar) for value in v]


def sub3(a, b):
    return [float(a[i]) - float(b[i]) for i in range(3)]


def vec2_approx(a, b, eps=EPS):
    return len(a) == 2 and len(b) == 2 and all(abs(float(x) - float(y)) <= eps for x, y in zip(a, b))


def signed_area2(points, tri):
    a, b, c = [points[index] for index in tri]
    return 0.5 * (
        (float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1]))
        - (float(b[1]) - float(a[1])) * (float(c[0]) - float(a[0]))
    )


def edge_incidence(triangles):
    counts = Counter()
    for tri in triangles:
        if not isinstance(tri, list) or len(tri) != 3:
            raise ValueError("chart triangle must contain exactly three indices")
        if len(set(tri)) != 3:
            raise ValueError("chart triangle contains a repeated index")
        for index in tri:
            if not isinstance(index, int) or not 0 <= index < 4:
                raise ValueError("chart triangle index out of range")
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[tuple(sorted((a, b)))] += 1
    return counts


def verify_core(profile, domain):
    if profile.get("schema") != "axm.building-utility-panel-service-surface-chart/v0.1":
        raise ValueError("Geometry chart schema drift")
    if profile.get("chart_id") != "utility-panel-outer-service-surface-chart-001":
        raise ValueError("Geometry chart identity drift")
    if profile.get("asset_id") != domain.get("asset_id"):
        raise ValueError("Geometry chart asset identity drift")
    if profile.get("surface_id") != domain.get("surface_id"):
        raise ValueError("Geometry chart surface identity drift")
    if profile.get("derivation") != "SOURCE_FRAME_BIJECTIVE_RECTANGULAR_UV_READY_CHART":
        raise ValueError("Geometry chart derivation drift")

    source = profile.get("source_surface", {})
    if source.get("owner") != "Building Hard Surface" or source.get("pr") != 15:
        raise ValueError("source-surface authority drift")
    if source.get("head") != "97120eb78a72b0a07aff1c65b9b92229d0a42aff":
        raise ValueError("source-surface donor head drift")
    if source.get("contract_path") != DOMAIN_PATH.relative_to(ROOT).as_posix():
        raise ValueError("source-surface contract path drift")
    if source.get("verifier_path") != SOURCE_VERIFIER_PATH.relative_to(ROOT).as_posix():
        raise ValueError("source-surface verifier path drift")
    actual_domain_blob = git_blob(DOMAIN_PATH)
    actual_verifier_blob = git_blob(SOURCE_VERIFIER_PATH)
    if source.get("contract_blob_sha") != actual_domain_blob:
        raise ValueError("source-surface contract blob drift")
    if source.get("verifier_blob_sha") != actual_verifier_blob:
        raise ValueError("source-surface verifier blob drift")

    authority = profile.get("authority", {})
    if authority.get("owner") != "Geometry / Topology":
        raise ValueError("Geometry authority drift")
    required_holds = {
        "texel density",
        "atlas placement",
        "material response",
        "texture payload",
        "normal or tangent transport",
        "target receiver adoption",
        "runtime storage",
        "environment adoption",
        "visual acceptance",
    }
    if not required_holds.issubset(set(authority.get("holds", []))):
        raise ValueError("downstream authority boundary weakened")

    source_verifier = load_module(SOURCE_VERIFIER_PATH, "axm_building_service_surface_owner")
    source_receipt = source_verifier.verify(domain=domain)
    if source_receipt.get("result") != "PASS_SOURCE_OWNED_BUILDING_UTILITY_PANEL_OUTER_SERVICE_SURFACE_METRIC_DOMAIN":
        raise ValueError("Hard Surface source-surface prerequisite is not PASS")

    frame = domain["reference_frame"]
    metric = domain["metric_domain"]
    origin = [float(v) for v in frame["origin_local_m"]]
    primary = [float(v) for v in frame["primary_axis_local"]]
    secondary = [float(v) for v in frame["secondary_axis_local"]]
    outward = [float(v) for v in frame["outward_axis_local"]]
    corners = [[float(v) for v in p] for p in metric["corner_positions_local_m"]]
    primary_extent = float(metric["primary_extent_m"])
    secondary_extent = float(metric["secondary_extent_m"])

    vertices = profile.get("vertices")
    if not isinstance(vertices, list) or len(vertices) != 4:
        raise ValueError("Geometry chart must contain exactly four vertices")
    source_indices = [row.get("source_corner_index") for row in vertices]
    if source_indices != [0, 1, 2, 3] or len(set(source_indices)) != 4:
        raise ValueError("Geometry chart source-corner mapping is not exact and bijective")

    metric_points = []
    uv_points = []
    reconstruction_residuals = []
    projection_residuals = []
    normalized_residuals = []
    for row in vertices:
        index = row["source_corner_index"]
        corner = corners[index]
        delta = sub3(corner, origin)
        projected = [dot(delta, primary), dot(delta, secondary)]
        observed_metric = row.get("metric_st_m")
        if not isinstance(observed_metric, list) or len(observed_metric) != 2:
            raise ValueError("Geometry chart metric coordinate missing")
        projection_residuals.append(max(abs(float(observed_metric[i]) - projected[i]) for i in range(2)))
        if not vec2_approx(observed_metric, projected):
            raise ValueError("Geometry chart metric coordinate drift")

        reconstructed = add3(origin, add3(mul3(primary, observed_metric[0]), mul3(secondary, observed_metric[1])))
        reconstruction_residual = math.dist(reconstructed, corner)
        reconstruction_residuals.append(reconstruction_residual)
        if reconstruction_residual > EPS:
            raise ValueError("Geometry chart does not reconstruct exact source corner")

        expected_uv = [
            float(observed_metric[0]) / primary_extent + 0.5,
            float(observed_metric[1]) / secondary_extent + 0.5,
        ]
        observed_uv = row.get("chart_uv")
        if not isinstance(observed_uv, list) or len(observed_uv) != 2:
            raise ValueError("Geometry chart normalized coordinate missing")
        normalized_residuals.append(max(abs(float(observed_uv[i]) - expected_uv[i]) for i in range(2)))
        if not vec2_approx(observed_uv, expected_uv):
            raise ValueError("Geometry chart normalized mapping drift")
        if any(float(value) < -EPS or float(value) > 1.0 + EPS for value in observed_uv):
            raise ValueError("Geometry chart normalized coordinate outside unit square")
        metric_points.append([float(v) for v in observed_metric])
        uv_points.append([float(v) for v in observed_uv])

    if len({tuple(point) for point in metric_points}) != 4 or len({tuple(point) for point in uv_points}) != 4:
        raise ValueError("Geometry chart vertex coordinates are not bijective")

    triangles = profile.get("triangles")
    if not isinstance(triangles, list) or len(triangles) != 2:
        raise ValueError("Geometry chart must contain exactly two triangles")
    incidence = edge_incidence(triangles)
    boundary_edges = {edge for edge, count in incidence.items() if count == 1}
    internal_edges = {edge for edge, count in incidence.items() if count == 2}
    if any(count not in (1, 2) for count in incidence.values()):
        raise ValueError("Geometry chart edge incidence is non-manifold")
    if len(boundary_edges) != 4 or len(internal_edges) != 1:
        raise ValueError("Geometry chart is not a two-triangle quad disk")

    boundary_loop = profile.get("boundary_loop")
    if boundary_loop != [0, 1, 2, 3]:
        raise ValueError("Geometry chart boundary-loop identity drift")
    loop_edges = {
        tuple(sorted((boundary_loop[i], boundary_loop[(i + 1) % len(boundary_loop)])))
        for i in range(len(boundary_loop))
    }
    if loop_edges != boundary_edges:
        raise ValueError("Geometry chart boundary loop does not match triangle boundary")

    internal_diagonal = profile.get("internal_diagonal")
    if not isinstance(internal_diagonal, list) or len(internal_diagonal) != 2:
        raise ValueError("Geometry chart internal diagonal missing")
    if {tuple(sorted(internal_diagonal))} != internal_edges:
        raise ValueError("Geometry chart internal diagonal does not match triangle connectivity")

    metric_areas = []
    uv_areas = []
    outward_dots = []
    references = Counter()
    for tri in triangles:
        metric_area = signed_area2(metric_points, tri)
        uv_area = signed_area2(uv_points, tri)
        if metric_area <= EPS or uv_area <= EPS:
            raise ValueError("Geometry chart triangle winding or area is not positive")
        metric_areas.append(metric_area)
        uv_areas.append(uv_area)
        a, b, c = [corners[vertices[index]["source_corner_index"]] for index in tri]
        normal = cross(sub3(b, a), sub3(c, a))
        outward_dot = dot(normal, outward)
        if outward_dot <= EPS:
            raise ValueError("Geometry chart triangle no longer follows source outward winding")
        outward_dots.append(outward_dot)
        references.update(tri)

    expected_metric_area = float(metric["area_m2"])
    if abs(sum(metric_areas) - expected_metric_area) > EPS:
        raise ValueError("Geometry chart metric area does not cover exact source service surface")
    if abs(sum(uv_areas) - 1.0) > EPS:
        raise ValueError("Geometry chart normalized area does not cover unit square")
    unreferenced = [index for index in range(4) if references[index] == 0]
    if unreferenced:
        raise ValueError("Geometry chart contains unreferenced vertices")

    return {
        "source_receipt": source_receipt,
        "source_surface_contract_blob_sha": actual_domain_blob,
        "source_surface_verifier_blob_sha": actual_verifier_blob,
        "metric_area_m2": sum(metric_areas),
        "normalized_chart_area": sum(uv_areas),
        "boundary_edge_count": len(boundary_edges),
        "internal_edge_count": len(internal_edges),
        "unreferenced_chart_vertex_count": len(unreferenced),
        "max_source_reconstruction_residual_m": max(reconstruction_residuals),
        "max_metric_projection_residual_m": max(projection_residuals),
        "max_normalized_mapping_residual": max(normalized_residuals),
        "minimum_outward_winding_dot": min(outward_dots),
    }


def run_negative_controls(profile, domain):
    controls = {}

    def expect_reject(name, mutated_profile):
        try:
            verify_core(mutated_profile, copy.deepcopy(domain))
            controls[name] = "UNEXPECTED_PASS"
        except (ValueError, KeyError, TypeError) as exc:
            controls[name] = "REJECTED: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["source_surface"]["head"] = "0" * 40
    expect_reject("source_surface_head_drift", bad)

    bad = copy.deepcopy(profile)
    bad["vertices"][1]["chart_uv"], bad["vertices"][2]["chart_uv"] = bad["vertices"][2]["chart_uv"], bad["vertices"][1]["chart_uv"]
    expect_reject("normalized_corner_swap", bad)

    bad = copy.deepcopy(profile)
    bad["vertices"][0]["metric_st_m"][0] += 0.001
    expect_reject("metric_coordinate_drift", bad)

    bad = copy.deepcopy(profile)
    bad["vertices"][3]["source_corner_index"] = 2
    expect_reject("duplicate_source_corner_identity", bad)

    bad = copy.deepcopy(profile)
    bad["triangles"][0] = list(reversed(bad["triangles"][0]))
    expect_reject("triangle_winding_flip", bad)

    bad = copy.deepcopy(profile)
    bad["internal_diagonal"] = [1, 3]
    expect_reject("internal_diagonal_identity_drift", bad)

    bad = copy.deepcopy(profile)
    bad["authority"]["holds"].remove("atlas placement")
    expect_reject("downstream_authority_weakening", bad)

    if any(not value.startswith("REJECTED:") for value in controls.values()):
        raise ValueError("one or more Geometry chart negative controls unexpectedly passed")
    return controls


def build(exact_head=None, profile=None, domain=None):
    profile = copy.deepcopy(profile or load(PROFILE_PATH))
    domain = copy.deepcopy(domain or load(DOMAIN_PATH))
    core = verify_core(profile, domain)
    negatives = run_negative_controls(profile, domain)
    return {
        "schema": "axm.building-utility-panel-service-surface-chart-evidence/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "exact_geometry_head": exact_head,
        "chart_id": profile["chart_id"],
        "asset_id": profile["asset_id"],
        "surface_id": profile["surface_id"],
        "source_surface_owner": profile["source_surface"]["owner"],
        "source_surface_head": profile["source_surface"]["head"],
        "source_surface_result": core["source_receipt"]["result"],
        "source_surface_contract_blob_sha": core["source_surface_contract_blob_sha"],
        "source_surface_verifier_blob_sha": core["source_surface_verifier_blob_sha"],
        "vertex_count": 4,
        "triangle_count": 2,
        "boundary_edge_count": core["boundary_edge_count"],
        "internal_edge_count": core["internal_edge_count"],
        "unreferenced_chart_vertex_count": core["unreferenced_chart_vertex_count"],
        "metric_area_m2": core["metric_area_m2"],
        "normalized_chart_area": core["normalized_chart_area"],
        "max_source_reconstruction_residual_m": core["max_source_reconstruction_residual_m"],
        "max_metric_projection_residual_m": core["max_metric_projection_residual_m"],
        "max_normalized_mapping_residual": core["max_normalized_mapping_residual"],
        "minimum_outward_winding_dot": core["minimum_outward_winding_dot"],
        "source_geometry_changed": False,
        "production_uv_adopted": False,
        "downstream_adoption_authorized": False,
        "reusable_pattern": PATTERN,
        "negative_controls": negatives,
        "truth_boundary": profile["truth_boundary"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = build(exact_head=args.exact_head)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
