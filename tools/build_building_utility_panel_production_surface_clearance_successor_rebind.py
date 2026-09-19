from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "axm.building-utility-panel-production-surface-clearance-successor-review/v0.1"
RUNTIME_SCHEMA = "axm.building-utility-panel-production-surface-clearance-successor-runtime-contract/v0.1"
RECEIPT_SCHEMA = "axm.building-utility-panel-production-surface-clearance-successor-receipt/v0.1"
RESULT = "PASS_BUILDING_UTILITY_PANEL_PRODUCTION_SURFACE_CLEARANCE_SUCCESSOR_REBIND_PACKET"
TARGET_RESULT = "PASS_TARGET_HOST_BUILDING_UTILITY_PANEL_PRODUCTION_SURFACE_CLEARANCE_SUCCESSOR_REVIEW"


def load(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(a, b, tol=1e-12):
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tol)


def vec_close(a, b, label, tol=1e-12):
    if len(a) != len(b) or any(not close(x, y, tol) for x, y in zip(a, b)):
        raise AssertionError(f"{label} mismatch: {a!r} != {b!r}")


def add(a, b):
    return [float(x) + float(y) for x, y in zip(a, b)]


def mul(a, s):
    return [float(x) * float(s) for x in a]


def sub(a, b):
    return [float(x) - float(y) for x, y in zip(a, b)]


def norm(a):
    return math.sqrt(sum(float(x) * float(x) for x in a))


def require_blob(path: str | Path, expected: str, label: str):
    actual = sha256(path)
    if len(expected) == 64 and actual != expected:
        raise AssertionError(f"{label} sha256 drift: {actual} != {expected}")


def build(args):
    contract = load(args.contract)
    panel = load(args.panel)
    domain = load(args.surface_domain)
    pavilion = load(args.pavilion)
    chart = load(args.geometry_chart)
    procedural = load(args.procedural_summary)
    recipe = load(args.recipe)

    if contract.get("schema") != SCHEMA:
        raise AssertionError("review contract schema drift")
    if panel.get("schema") != "axm.building-utility-panel/v0.1":
        raise AssertionError("panel schema drift")
    if domain.get("schema") != "axm.building-utility-panel-service-surface-domain/v0.1":
        raise AssertionError("service-surface schema drift")
    if chart.get("schema") != "axm.building-utility-panel-service-surface-chart/v0.1":
        raise AssertionError("Geometry chart schema drift")
    if recipe.get("schema") != "axm.building.utility-panel-production-surface/v0.1":
        raise AssertionError("production surface recipe schema drift")

    hs = contract["hard_surface_owner"]
    geo = contract["geometry_owner"]
    proc = contract["procedural_owner"]
    surf = contract["surface_recipe"]
    comp = contract["comparison"]

    if args.hard_surface_head != hs["current_evidence_head"]:
        raise AssertionError("Hard Surface current evidence head drift")
    if args.geometry_head != geo["current_head"]:
        raise AssertionError("Geometry current head drift")
    if args.procedural_head != proc["current_head"]:
        raise AssertionError("Procedural current head drift")

    if panel.get("asset_id") != contract["asset_id"] or domain.get("asset_id") != contract["asset_id"]:
        raise AssertionError("asset identity drift")
    if domain.get("surface_id") != contract["surface_id"] or chart.get("surface_id") != contract["surface_id"]:
        raise AssertionError("surface identity drift")
    if chart.get("chart_id") != geo["chart_id"]:
        raise AssertionError("Geometry chart identity drift")
    if domain.get("source_panel", {}).get("git_blob_sha") != hs["panel_git_blob_sha"]:
        raise AssertionError("service-surface panel provenance drift")
    if chart.get("source_surface", {}).get("contract_blob_sha") != hs["service_surface_git_blob_sha"]:
        raise AssertionError("Geometry chart source-surface blob drift")
    if chart.get("source_surface", {}).get("head") != hs["semantic_source_head_consumed_by_geometry"]:
        raise AssertionError("Geometry semantic source head drift")

    if not close(panel.get("standoff_from_receiver_origin_m"), comp["successor_standoff_m"]):
        raise AssertionError("successor standoff drift")
    if not close(panel.get("body_depth_m"), comp["body_depth_m"]):
        raise AssertionError("panel body depth drift")
    if not close(panel.get("required_body_clearance_beyond_plate_m"), comp["required_body_gap_m"]):
        raise AssertionError("required body gap drift")

    metric = domain.get("metric_domain", {})
    if not close(metric.get("primary_extent_m"), 1.10) or not close(metric.get("secondary_extent_m"), 1.50) or not close(metric.get("area_m2"), 1.65):
        raise AssertionError("service-surface metric domain drift")
    vec_close(domain.get("reference_frame", {}).get("origin_local_m", []), [0.04, 0.0, 0.0], "service-surface local origin")
    directional = chart.get("directional_sampling_interface", {})
    vec_close(directional.get("physical_extent_m_by_chart_axis", []), [1.1, 1.5], "Geometry chart physical extents")
    if len(chart.get("vertices", [])) != 4 or chart.get("triangles") != [[0, 1, 2], [0, 2, 3]]:
        raise AssertionError("Geometry chart topology drift")

    if procedural.get("result") != proc["required_result"]:
        raise AssertionError("Procedural result drift")
    if procedural.get("decision") != proc["required_decision"]:
        raise AssertionError("Procedural decision drift")
    if procedural.get("source_authority_head") != hs["current_evidence_head"]:
        raise AssertionError("Procedural current Hard Surface owner drift")
    if procedural.get("source_authority_panel_blob") != hs["panel_git_blob_sha"]:
        raise AssertionError("Procedural panel owner blob drift")
    if procedural.get("automatic_receiver_adoption") is not False:
        raise AssertionError("Procedural unexpectedly authorizes automatic receiver adoption")

    if recipe.get("surface_id") != "utility_panel_ochre_production_surface_001":
        raise AssertionError("production surface identity drift")
    if recipe.get("expected_png_sha256") != surf["expected_png_sha256"]:
        raise AssertionError("production surface PNG identity drift")
    if recipe.get("expected_rgba8_sha256") != surf["expected_rgba8_sha256"]:
        raise AssertionError("production surface RGBA identity drift")
    if recipe.get("frozen_material_scalars") != {"metallic": surf["metallic"], "roughness": surf["roughness"]}:
        raise AssertionError("production material scalar drift")
    if args.texture and sha256(args.texture) != surf["expected_png_sha256"]:
        raise AssertionError("generated production texture PNG identity drift")

    dims = comp["texture_dimensions_px"]
    density = float(comp["review_texel_density_px_per_m"])
    expected_uv = [1.1 * density / float(dims[0]), 1.5 * density / float(dims[1])]
    vec_close(expected_uv, comp["expected_review_uv_extent"], "review UV extent")

    interfaces = {row["id"]: row for row in pavilion.get("interfaces", [])}
    outputs = procedural.get("outputs", [])
    proc_by_id = {row["receiver_id"]: row for row in outputs}
    if sorted(proc_by_id) != ["east-utility-bay", "front-utility-bay"]:
        raise AssertionError("Procedural receiver set drift")

    receivers = []
    for receiver_id in ("front-utility-bay", "east-utility-bay"):
        interface = interfaces.get(receiver_id)
        row = proc_by_id[receiver_id]
        if not isinstance(interface, dict):
            raise AssertionError(f"missing source receiver {receiver_id}")
        origin = [float(v) for v in interface["origin"]]
        normal = [float(v) for v in interface["normal"]]
        lateral = [float(v) for v in interface["lateral"]]
        up = [float(v) for v in interface["up"]]
        plate = float(interface["plate_thickness_m"])
        old_center = add(origin, mul(normal, comp["historical_standoff_m"]))
        new_center = add(origin, mul(normal, comp["successor_standoff_m"]))
        vec_close(row["predecessor_panel_center_m"], old_center, f"{receiver_id} predecessor center")
        vec_close(row["successor_panel_center_m"], new_center, f"{receiver_id} successor center")
        displacement = sub(new_center, old_center)
        if not close(norm(displacement), 0.02):
            raise AssertionError(f"{receiver_id} source-successor displacement drift")
        if not close(float(row["successor_physical_body_gap_m"]), comp["required_body_gap_m"]):
            raise AssertionError(f"{receiver_id} successor physical body gap drift")
        historical_gap = float(comp["historical_standoff_m"]) - plate - 0.5 * float(comp["body_depth_m"])
        successor_gap = float(comp["successor_standoff_m"]) - plate - 0.5 * float(comp["body_depth_m"])
        if not close(historical_gap, 0.0) or not close(successor_gap, comp["required_body_gap_m"]):
            raise AssertionError(f"{receiver_id} physical gap derivation drift")
        receivers.append({
            "id": receiver_id,
            "origin": origin,
            "normal": normal,
            "lateral": lateral,
            "up": up,
            "plate_footprint_m": [float(v) for v in interface["plate_footprint_m"]],
            "plate_thickness_m": plate,
            "historical_panel_center_m": old_center,
            "successor_panel_center_m": new_center,
            "historical_body_gap_m": historical_gap,
            "successor_body_gap_m": successor_gap,
            "displacement_m": displacement,
        })

    runtime = {
        "schema": RUNTIME_SCHEMA,
        "state": RESULT,
        "surface_id": recipe["surface_id"],
        "texture_png_sha256": surf["expected_png_sha256"],
        "texture_rgba8_sha256": surf["expected_rgba8_sha256"],
        "material": {"base_srgb8": recipe["base_srgb8"], "metallic": surf["metallic"], "roughness": surf["roughness"]},
        "panel": {"body_depth_m": float(comp["body_depth_m"]), "footprint_m": [1.10, 1.50]},
        "review_uv_extent": [float(v) for v in expected_uv],
        "review_texel_density_px_per_m": density,
        "historical_standoff_m": float(comp["historical_standoff_m"]),
        "successor_standoff_m": float(comp["successor_standoff_m"]),
        "receivers": receivers,
        "contexts": comp["contexts"],
        "variants": comp["variants"],
        "renderer_boundary": contract["renderer_boundary"],
        "truth_boundary": contract["truth_boundary"],
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": RESULT,
        "materials_head": args.materials_head,
        "hard_surface_head": args.hard_surface_head,
        "geometry_head": args.geometry_head,
        "procedural_head": args.procedural_head,
        "source_panel_blob": hs["panel_git_blob_sha"],
        "service_surface_blob": hs["service_surface_git_blob_sha"],
        "geometry_chart_blob": geo["chart_git_blob_sha"],
        "production_surface_png_sha256": surf["expected_png_sha256"],
        "production_surface_rgba8_sha256": surf["expected_rgba8_sha256"],
        "review_uv_extent": runtime["review_uv_extent"],
        "receiver_count": len(receivers),
        "receiver_rebinds": receivers,
        "truth_boundary": contract["truth_boundary"],
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "runtime_contract.json").write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "build_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


def verify_runtime(args):
    from PIL import Image

    root = Path(args.render_root)
    runtime = load(args.runtime_contract)
    receipt = load(args.runtime_receipt)
    if runtime.get("schema") != RUNTIME_SCHEMA or receipt.get("state") != TARGET_RESULT:
        raise AssertionError("runtime receipt state/schema mismatch")
    if receipt.get("surface_id") != runtime.get("surface_id"):
        raise AssertionError("runtime surface identity drift")
    if receipt.get("texture_png_sha256") != runtime.get("texture_png_sha256"):
        raise AssertionError("runtime texture identity drift")

    threshold = 1.0 / 255.0 + 1e-9
    summary = {}
    total_shift = 0
    total_material = 0
    for context in runtime["contexts"]:
        paths = {
            "historical_lit": root / f"utility-panel-clearance-{context}-historical-lit.png",
            "successor_lit": root / f"utility-panel-clearance-{context}-successor-lit.png",
            "successor_unshaded": root / f"utility-panel-clearance-{context}-successor-unshaded.png",
        }
        images = {key: Image.open(path).convert("RGB") for key, path in paths.items()}
        if len({im.size for im in images.values()}) != 1:
            raise AssertionError(f"{context}: render dimensions drift")

        def compare(a, b):
            ia, ib = images[a], images[b]
            changed = 0
            max_delta = 0.0
            for pa, pb in zip(ia.getdata(), ib.getdata()):
                d = max(abs(pa[0]-pb[0]), abs(pa[1]-pb[1]), abs(pa[2]-pb[2])) / 255.0
                if d > threshold:
                    changed += 1
                max_delta = max(max_delta, d)
            return {"changed_pixels_gt_1lsb": changed, "max_rgb_channel_delta": max_delta}

        shift = compare("historical_lit", "successor_lit")
        material = compare("successor_lit", "successor_unshaded")
        if shift["changed_pixels_gt_1lsb"] <= 100 or shift["max_rgb_channel_delta"] <= threshold:
            raise AssertionError(f"{context}: source-successor placement shift is not visibly observed: {shift}")
        if material["changed_pixels_gt_1lsb"] <= 100 or material["max_rgb_channel_delta"] <= threshold:
            raise AssertionError(f"{context}: material receiver is not visibly active: {material}")
        total_shift += shift["changed_pixels_gt_1lsb"]
        total_material += material["changed_pixels_gt_1lsb"]
        summary[context] = {"placement_shift": shift, "lit_vs_unshaded": material, "files": {k: str(v) for k, v in paths.items()}}

    result = {
        "schema": "axm.building-utility-panel-production-surface-clearance-successor-target-host/v0.1",
        "state": TARGET_RESULT,
        "surface_id": runtime["surface_id"],
        "texture_png_sha256": runtime["texture_png_sha256"],
        "review_uv_extent": runtime["review_uv_extent"],
        "review_texel_density_px_per_m": runtime["review_texel_density_px_per_m"],
        "contexts": summary,
        "total_placement_shift_pixels_gt_1lsb": total_shift,
        "total_lit_vs_unshaded_pixels_gt_1lsb": total_material,
        "renderer_boundary": runtime["renderer_boundary"],
        "truth_boundary": runtime["truth_boundary"],
    }
    Path(args.report).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--contract", required=True)
    b.add_argument("--panel", required=True)
    b.add_argument("--surface-domain", required=True)
    b.add_argument("--pavilion", required=True)
    b.add_argument("--geometry-chart", required=True)
    b.add_argument("--procedural-summary", required=True)
    b.add_argument("--recipe", required=True)
    b.add_argument("--texture")
    b.add_argument("--materials-head", required=True)
    b.add_argument("--hard-surface-head", required=True)
    b.add_argument("--geometry-head", required=True)
    b.add_argument("--procedural-head", required=True)
    b.add_argument("--out", required=True)

    v = sub.add_parser("verify-runtime")
    v.add_argument("--runtime-contract", required=True)
    v.add_argument("--runtime-receipt", required=True)
    v.add_argument("--render-root", required=True)
    v.add_argument("--report", required=True)

    args = parser.parse_args()
    if args.command == "build":
        build(args)
    else:
        verify_runtime(args)


if __name__ == "__main__":
    main()
