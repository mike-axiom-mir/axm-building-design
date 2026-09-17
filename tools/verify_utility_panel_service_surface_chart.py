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
RESULT = "PASS_BUILDING_UTILITY_PANEL_UV_READY_SOURCE_FRAME_CHART_SUCCESSOR_REBIND"
DECISION = "PASS_DERIVED_GEOMETRY_CHART_REBOUND_TO_CLEARANCE_SUCCESSOR__NO_TEXEL_DENSITY_ATLAS_MATERIAL_RECEIVER_OR_VISUAL_ADOPTION"
PATTERN = "DERIVED_CHART_MUST_REBIND_TO_EXACT_SOURCE_SUCCESSOR_BEFORE_EVIDENCE_TRANSFER"
DIRECTIONAL_PATTERN = "PHYSICAL_UV_AXIS_METRICS_AND_IMAGE_BINDING_GATE_BEFORE_DIRECTIONAL_TEXEL_DENSITY_CONSUMPTION"
DIRECTIONAL_STATE = "PASS_SOURCE_LOCAL_DIRECTIONAL_SAMPLING_INTERFACE__HOLD_SHARED_OBSERVER_CONSUMPTION_PENDING_BOUND_ARTIFACT_AND_IMAGE"
SOURCE_PR = 17
SOURCE_HEAD = "32bbdd54f00aaac87ba8139bf932d8aff6109a66"
HISTORICAL_GEOMETRY_PR = 16
HISTORICAL_GEOMETRY_HEAD = "79e09f68a05770eb6dabbbbbb3b008fc8e050aa0"
HISTORICAL_CHART_BLOB = "56f1964b3360e371ac8c39d547cb300cd14fb997"
HISTORICAL_SOURCE_HEAD = "97120eb78a72b0a07aff1c65b9b92229d0a42aff"
UC_OBSERVER_REPOSITORY = "mike-axiom-mir/axm-universal-creation"
UC_OBSERVER_PR = 194
UC_OBSERVER_MERGE = "aa53ee8aa803c19524b7edbef6250bf6ed9336c0"
UC_OBSERVER_MODULE = "src/axm_uc/material_uv_evidence.py"
UC_OBSERVER_API = "inspect_material_uv_density"
CONSUMPTION_HOLD = "HOLD_BOUND_MATERIAL_BEARING_ARTIFACT_AND_IMAGE_DIMENSIONS_REQUIRED"
REQUIRED_DOWNSTREAM_INPUTS = [
    "material_bearing_glb_artifact",
    "embedded_image_width_px",
    "embedded_image_height_px",
]


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


def sub3(a, b):
    return [float(a[i]) - float(b[i]) for i in range(3)]


def mul3(v, scalar):
    return [float(value) * float(scalar) for value in v]


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
    if source.get("owner") != "Building Hard Surface" or source.get("pr") != SOURCE_PR:
        raise ValueError("source-surface authority drift")
    if source.get("head") != SOURCE_HEAD:
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

    historical = profile.get("historical_geometry_evidence", {})
    if historical.get("pr") != HISTORICAL_GEOMETRY_PR:
        raise ValueError("historical Geometry PR identity drift")
    if historical.get("head") != HISTORICAL_GEOMETRY_HEAD:
        raise ValueError("historical Geometry head drift")
    if historical.get("chart_contract_blob_sha") != HISTORICAL_CHART_BLOB:
        raise ValueError("historical Geometry chart blob drift")
    if historical.get("source_surface_head") != HISTORICAL_SOURCE_HEAD:
        raise ValueError("historical source-surface head drift")
    if historical.get("transfer_policy") != "HISTORICAL_PASS_RETAINED_NOT_TRANSFERRED__CURRENT_SOURCE_SUCCESSOR_REQUIRES_DIRECT_REBIND":
        raise ValueError("historical evidence transfer boundary drift")

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
    corners = [[float(v) for v in point] for point in metric["corner_positions_local_m"]]
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
        metric_points.append([float(value) for value in observed_metric])
        uv_points.append([float(value) for value in observed_uv])

    if len({tuple(point) for point in metric_points}) != 4 or len({tuple(point) for point in uv_points}) != 4:
        raise ValueError("Geometry chart vertex coordinates are not bijective")

    metric_extent_by_axis = [
        max(point[axis] for point in metric_points) - min(point[axis] for point in metric_points)
        for axis in range(2)
    ]
    normalized_extent_by_axis = [
        max(point[axis] for point in uv_points) - min(point[axis] for point in uv_points)
        for axis in range(2)
    ]
    if not vec2_approx(metric_extent_by_axis, [primary_extent, secondary_extent]):
        raise ValueError("derived physical chart-axis extent drift")
    if any(value <= EPS for value in normalized_extent_by_axis):
        raise ValueError("normalized chart-axis extent is singular")
    metres_per_uv_unit = [
        metric_extent_by_axis[index] / normalized_extent_by_axis[index]
        for index in range(2)
    ]

    directional = profile.get("directional_sampling_interface", {})
    if directional.get("pattern") != DIRECTIONAL_PATTERN:
        raise ValueError("directional sampling pattern drift")
    if directional.get("chart_axis_order") != ["u", "v"]:
        raise ValueError("directional sampling chart-axis order drift")
    if not vec2_approx(directional.get("physical_extent_m_by_chart_axis", []), metric_extent_by_axis):
        raise ValueError("directional physical extent declaration drift")
    if not vec2_approx(directional.get("normalized_extent_by_chart_axis", []), normalized_extent_by_axis):
        raise ValueError("directional normalized extent declaration drift")
    if not vec2_approx(directional.get("metres_per_uv_unit_by_chart_axis", []), metres_per_uv_unit):
        raise ValueError("directional metres-per-UV declaration drift")

    shared = directional.get("shared_observer", {})
    expected_shared = {
        "repository": UC_OBSERVER_REPOSITORY,
        "pull_request": UC_OBSERVER_PR,
        "merge_commit": UC_OBSERVER_MERGE,
        "module": UC_OBSERVER_MODULE,
        "api": UC_OBSERVER_API,
    }
    if shared != expected_shared:
        raise ValueError("shared directional-density observer identity drift")

    gate = directional.get("consumption_gate", {})
    if gate.get("observer_consumed") is not False:
        raise ValueError("shared directional-density observer must remain unconsumed without bound product inputs")
    if gate.get("directional_density_measured") is not False:
        raise ValueError("directional texel density must remain unmeasured without bound product inputs")
    if gate.get("state") != CONSUMPTION_HOLD:
        raise ValueError("directional-density consumption HOLD state drift")
    if gate.get("required_downstream_inputs") != REQUIRED_DOWNSTREAM_INPUTS:
        raise ValueError("directional-density required downstream inputs drift")

    policy = directional.get("policy_boundary", {})
    if policy.get("geometry_selects_texel_density_target") is not False:
        raise ValueError("Geometry may not select the product texel-density target")
    if policy.get("geometry_selects_anisotropy_threshold") is not False:
        raise ValueError("Geometry may not select an anisotropy threshold")
    if policy.get("geometry_selects_atlas_layout") is not False:
        raise ValueError("Geometry may not select atlas layout")

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
        outward_dot = dot(cross(sub3(b, a), sub3(c, a)), outward)
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
        "chart_axis_order": ["u", "v"],
        "physical_extent_m_by_chart_axis": metric_extent_by_axis,
        "normalized_extent_by_chart_axis": normalized_extent_by_axis,
        "metres_per_uv_unit_by_chart_axis": metres_per_uv_unit,
        "shared_directional_density_observer": shared,
        "directional_density_consumption_gate": gate,
        "directional_density_policy_boundary": policy,
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
    bad["historical_geometry_evidence"]["head"] = "0" * 40
    expect_reject("historical_geometry_lineage_drift", bad)

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

    bad = copy.deepcopy(profile)
    bad["directional_sampling_interface"]["physical_extent_m_by_chart_axis"][0] += 0.01
    expect_reject("directional_metric_extent_drift", bad)

    bad = copy.deepcopy(profile)
    bad["directional_sampling_interface"]["shared_observer"]["merge_commit"] = "0" * 40
    expect_reject("uc_observer_identity_drift", bad)

    bad = copy.deepcopy(profile)
    bad["directional_sampling_interface"]["consumption_gate"]["observer_consumed"] = True
    expect_reject("fabricated_uc_observer_consumption", bad)

    bad = copy.deepcopy(profile)
    bad["directional_sampling_interface"]["consumption_gate"]["directional_density_measured"] = True
    expect_reject("fabricated_directional_density_measurement", bad)

    bad = copy.deepcopy(profile)
    bad["directional_sampling_interface"]["policy_boundary"]["geometry_selects_texel_density_target"] = True
    expect_reject("geometry_density_policy_escalation", bad)

    if any(not value.startswith("REJECTED:") for value in controls.values()):
        raise ValueError("one or more Geometry chart negative controls unexpectedly passed")
    return controls


def build(exact_head=None, profile=None, domain=None):
    profile = copy.deepcopy(profile or load(PROFILE_PATH))
    domain = copy.deepcopy(domain or load(DOMAIN_PATH))
    core = verify_core(profile, domain)
    negatives = run_negative_controls(profile, domain)
    historical = profile["historical_geometry_evidence"]
    gate = core["directional_density_consumption_gate"]
    return {
        "schema": "axm.building-utility-panel-service-surface-chart-evidence/v0.2",
        "result": RESULT,
        "decision": DECISION,
        "pattern": PATTERN,
        "directional_sampling_pattern": DIRECTIONAL_PATTERN,
        "directional_sampling_state": DIRECTIONAL_STATE,
        "exact_geometry_head": exact_head,
        "chart_id": profile["chart_id"],
        "asset_id": profile["asset_id"],
        "surface_id": profile["surface_id"],
        "source_surface_owner": profile["source_surface"]["owner"],
        "source_surface_pr": profile["source_surface"]["pr"],
        "source_surface_head": profile["source_surface"]["head"],
        "source_surface_result": core["source_receipt"]["result"],
        "source_surface_contract_blob_sha": core["source_surface_contract_blob_sha"],
        "source_surface_verifier_blob_sha": core["source_surface_verifier_blob_sha"],
        "historical_geometry_pr": historical["pr"],
        "historical_geometry_head": historical["head"],
        "historical_geometry_chart_blob_sha": historical["chart_contract_blob_sha"],
        "historical_pass_transferred": False,
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
        "chart_axis_order": core["chart_axis_order"],
        "physical_extent_m_by_chart_axis": core["physical_extent_m_by_chart_axis"],
        "normalized_extent_by_chart_axis": core["normalized_extent_by_chart_axis"],
        "metres_per_uv_unit_by_chart_axis": core["metres_per_uv_unit_by_chart_axis"],
        "shared_directional_density_observer": core["shared_directional_density_observer"],
        "shared_observer_consumed": gate["observer_consumed"],
        "directional_density_measured": gate["directional_density_measured"],
        "directional_density_consumption_state": gate["state"],
        "required_directional_density_inputs": gate["required_downstream_inputs"],
        "directional_density_policy_boundary": core["directional_density_policy_boundary"],
        "source_geometry_changed": False,
        "production_uv_adopted": False,
        "downstream_adoption_authorized": False,
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
