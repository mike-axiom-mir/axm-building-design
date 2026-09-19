from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONTRACT_SCHEMA = "axm.building-utility-panel-uv-density-review/v0.1"
CHART_SCHEMA = "axm.building-utility-panel-service-surface-chart/v0.1"
SURFACE_SCHEMA = "axm.building-utility-panel-service-surface-domain/v0.1"
BASE_PAYLOAD_SCHEMA = "axm.building-material-lookdev-payload/v0.1"
PAYLOAD_SCHEMA = "axm.building-utility-panel-uv-density-payload/v0.1"
RECEIPT_SCHEMA = "axm.building-utility-panel-uv-density-build-receipt/v0.1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def require_close(actual: float, expected: float, label: str, tol: float = 1e-12) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tol):
        raise AssertionError(f"{label} mismatch: {actual!r} != {expected!r}")


def _checker_color(base: list[float], factor: float) -> list[float]:
    return [min(1.0, max(0.0, float(c) * factor)) for c in base[:3]] + [1.0]


def derive(
    contract: dict,
    chart: dict,
    surface: dict,
    base_payload: dict,
) -> tuple[dict, dict]:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("review contract schema mismatch")
    if chart.get("schema") != CHART_SCHEMA:
        raise AssertionError("Geometry chart schema mismatch")
    if surface.get("schema") != SURFACE_SCHEMA:
        raise AssertionError("Hard-Surface domain schema mismatch")
    if base_payload.get("schema") != BASE_PAYLOAD_SCHEMA:
        raise AssertionError("base Materials payload schema mismatch")

    if chart.get("asset_id") != contract.get("asset_id") or surface.get("asset_id") != contract.get("asset_id"):
        raise AssertionError("asset identity mismatch")
    if chart.get("surface_id") != contract.get("surface_id") or surface.get("surface_id") != contract.get("surface_id"):
        raise AssertionError("surface identity mismatch")

    chart_ref = contract["geometry_chart"]
    source_ref = contract["source_surface"]
    if chart_ref.get("head") != "79e09f68a05770eb6dabbbbbb3b008fc8e050aa0":
        raise AssertionError("unexpected Geometry owner head")
    if chart_ref.get("git_blob_sha") != "56f1964b3360e371ac8c39d547cb300cd14fb997":
        raise AssertionError("unexpected Geometry chart blob")
    if source_ref.get("head") != "97120eb78a72b0a07aff1c65b9b92229d0a42aff":
        raise AssertionError("unexpected Hard-Surface owner head")
    if source_ref.get("git_blob_sha") != "14037a0fb939104ea319c9ac96fbe9fdaa949a18":
        raise AssertionError("unexpected Hard-Surface domain blob")

    if chart.get("source_surface", {}).get("head") != source_ref["head"]:
        raise AssertionError("Geometry chart is not bound to expected Hard-Surface source head")
    if chart.get("source_surface", {}).get("contract_blob_sha") != source_ref["git_blob_sha"]:
        raise AssertionError("Geometry chart source-domain blob drift")

    metric = surface["metric_domain"]
    primary_m = float(metric["primary_extent_m"])
    secondary_m = float(metric["secondary_extent_m"])
    area_m2 = float(metric["area_m2"])
    require_close(primary_m, 1.10, "primary extent")
    require_close(secondary_m, 1.50, "secondary extent")
    require_close(area_m2, primary_m * secondary_m, "surface area")

    vertices = chart.get("vertices")
    if not isinstance(vertices, list) or len(vertices) != 4:
        raise AssertionError("expected four source-corner chart vertices")
    if chart.get("triangles") != [[0, 1, 2], [0, 2, 3]]:
        raise AssertionError("unexpected chart topology")
    if chart.get("boundary_loop") != [0, 1, 2, 3]:
        raise AssertionError("unexpected chart boundary loop")

    source_corners = metric["corner_positions_local_m"]
    for expected_index, vertex in enumerate(vertices):
        if int(vertex["source_corner_index"]) != expected_index:
            raise AssertionError("source-corner identity drift")
        s_m, t_m = [float(v) for v in vertex["metric_st_m"]]
        corner = source_corners[expected_index]
        require_close(s_m, float(corner[1]), f"corner {expected_index} primary metric")
        require_close(t_m, float(corner[2]), f"corner {expected_index} secondary metric")
        u, v = [float(x) for x in vertex["chart_uv"]]
        require_close(u, (s_m + primary_m / 2.0) / primary_m, f"corner {expected_index} chart u")
        require_close(v, (t_m + secondary_m / 2.0) / secondary_m, f"corner {expected_index} chart v")

    review = contract["review_candidate"]
    atlas_w, atlas_h = [int(v) for v in review["atlas_size_px"]]
    density = int(review["texel_density_px_per_m"])
    period_px = int(review["diagnostic_checker_period_px"])
    if atlas_w != 512 or atlas_h != 512:
        raise AssertionError("review atlas must remain 512 x 512")
    if density != 320:
        raise AssertionError("review density drift")
    if period_px != 16:
        raise AssertionError("diagnostic checker period drift")

    exact_w = primary_m * density
    exact_h = secondary_m * density
    if not exact_w.is_integer() or not exact_h.is_integer():
        raise AssertionError("review density must yield integer active texel dimensions")
    active_w, active_h = int(exact_w), int(exact_h)
    if [active_w, active_h] != [int(v) for v in review["active_region_px"]]:
        raise AssertionError("active review region drift")
    if active_w > atlas_w or active_h > atlas_h:
        raise AssertionError("active review region does not fit atlas")

    origin_x = (atlas_w - active_w) // 2
    origin_y = (atlas_h - active_h) // 2
    if [origin_x, origin_y] != [int(v) for v in review["active_region_origin_px"]]:
        raise AssertionError("active review region origin drift")
    if (atlas_w - active_w) % 2 or (atlas_h - active_h) % 2:
        raise AssertionError("active region is not exactly centered on integer texels")
    if active_w % period_px or active_h % period_px:
        raise AssertionError("diagnostic period must tile the active region exactly")

    checker_period_m = period_px / float(density)
    require_close(checker_period_m, float(review["diagnostic_checker_period_m"]), "checker physical period")
    candidate_cells = [active_w // period_px, active_h // period_px]
    if candidate_cells != [22, 30]:
        raise AssertionError("unexpected candidate checker cell count")

    negative_density = [atlas_w / primary_m, atlas_h / secondary_m]
    negative_ratio = max(negative_density) / min(negative_density)
    negative = contract["negative_control"]
    for actual, expected, label in zip(
        negative_density,
        negative["expected_effective_density_px_per_m"],
        ("negative primary density", "negative secondary density"),
    ):
        require_close(actual, float(expected), label)
    require_close(negative_ratio, float(negative["expected_density_ratio_max_over_min"]), "negative anisotropy ratio")
    negative_cells = [atlas_w // period_px, atlas_h // period_px]
    if negative_cells != [int(v) for v in negative["expected_checker_cells"]]:
        raise AssertionError("negative checker cell count drift")
    if negative_ratio <= 1.25:
        raise AssertionError("negative control is not materially anisotropic")

    components = base_payload.get("components")
    if not isinstance(components, list):
        raise AssertionError("base payload components missing")
    by_id = {str(row["id"]): row for row in components}
    panel_ids = ["panel-front-utility-bay", "panel-east-utility-bay"]
    for panel_id in panel_ids:
        if panel_id not in by_id:
            raise AssertionError(f"missing exact receiver panel {panel_id}")
        component = by_id[panel_id]
        if [float(v) for v in component["size_local_xyz_m"]] != [0.08, 1.10, 1.50]:
            raise AssertionError(f"panel size drift for {panel_id}")
        if component.get("candidate_material") != contract["material_role"]:
            raise AssertionError(f"panel material-role drift for {panel_id}")

    materials = base_payload.get("materials", {}).get("candidate", {})
    material = materials.get(contract["material_role"])
    if not isinstance(material, dict):
        raise AssertionError("utility panel material role missing from current Materials payload")
    base_albedo = [float(v) for v in material["albedo"]]
    if len(base_albedo) != 4:
        raise AssertionError("utility-panel albedo must be RGBA")

    active_uv_bounds = [
        origin_x / atlas_w,
        origin_y / atlas_h,
        (origin_x + active_w) / atlas_w,
        (origin_y + active_h) / atlas_h,
    ]

    truth_boundary = dict(contract["truth_boundary"])
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "asset_id": contract["asset_id"],
        "surface_id": contract["surface_id"],
        "owner_evidence": {
            "geometry_chart_head": chart_ref["head"],
            "geometry_chart_blob": chart_ref["git_blob_sha"],
            "hard_surface_domain_head": source_ref["head"],
            "hard_surface_domain_blob": source_ref["git_blob_sha"],
            "base_material_source_head": base_payload.get("source_identity", {}).get("hard_surface_head"),
        },
        "base_components": components,
        "base_candidate_materials": materials,
        "panel_component_ids": panel_ids,
        "chart_vertices": vertices,
        "surface_metric": {
            "primary_extent_m": primary_m,
            "secondary_extent_m": secondary_m,
            "area_m2": area_m2,
            "outer_face_local_x_m": float(surface["reference_frame"]["origin_local_m"][0]),
        },
        "review_atlas": {
            "size_px": [atlas_w, atlas_h],
            "texel_density_px_per_m": [float(density), float(density)],
            "active_region_px": [active_w, active_h],
            "active_region_origin_px": [origin_x, origin_y],
            "active_uv_bounds": active_uv_bounds,
            "checker_period_px": period_px,
            "checker_period_m": checker_period_m,
            "checker_cells": candidate_cells,
            "checker_dark_rgba": _checker_color(base_albedo, 0.72),
            "checker_light_rgba": _checker_color(base_albedo, 1.28),
            "base_material": material,
        },
        "negative_control": {
            "id": negative["id"],
            "full_square_uv_bounds": [0.0, 0.0, 1.0, 1.0],
            "effective_density_px_per_m": negative_density,
            "density_ratio_max_over_min": negative_ratio,
            "checker_cells": negative_cells,
        },
        "contexts": ["front_service", "east_service", "three_quarter"],
        "truth_boundary": truth_boundary,
    }

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_BUILDING_UTILITY_PANEL_PHYSICAL_UV_DENSITY_PAYLOAD",
        "candidate": {
            "texel_density_px_per_m": [float(density), float(density)],
            "active_region_px": [active_w, active_h],
            "active_region_origin_px": [origin_x, origin_y],
            "checker_period_m": checker_period_m,
            "checker_cells": candidate_cells,
            "density_ratio_max_over_min": 1.0,
        },
        "negative_control": payload["negative_control"],
        "owner_evidence": payload["owner_evidence"],
        "panel_component_ids": panel_ids,
        "payload_sha256": canonical_digest(payload),
        "truth_boundary": truth_boundary,
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="lookdev/building_utility_panel_uv_density_001.json")
    parser.add_argument("--geometry-chart", required=True)
    parser.add_argument("--surface-domain", required=True)
    parser.add_argument("--base-payload", required=True)
    parser.add_argument("--out", default="lookdev-utility-panel-uv-proof/generated")
    args = parser.parse_args()

    contract_path = Path(args.contract)
    chart_path = Path(args.geometry_chart)
    surface_path = Path(args.surface_domain)
    base_payload_path = Path(args.base_payload)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    payload, receipt = derive(
        load_json(contract_path),
        load_json(chart_path),
        load_json(surface_path),
        load_json(base_payload_path),
    )
    receipt["inputs"] = {
        "contract_sha256": sha256(contract_path),
        "geometry_chart_sha256": sha256(chart_path),
        "surface_domain_sha256": sha256(surface_path),
        "base_payload_sha256": sha256(base_payload_path),
    }
    (out / "utility_panel_uv_density_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
