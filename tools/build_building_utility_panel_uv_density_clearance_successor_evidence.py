from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

CONTRACT_SCHEMA = "axm.building-utility-panel-uv-density-clearance-successor-review/v0.1"
HISTORICAL_PAYLOAD_SCHEMA = "axm.building-utility-panel-uv-density-payload/v0.1"
PROCEDURAL_SCHEMA = "axm.building-utility-panel-clearance-rebind-family-evidence/v0.1"
SURFACE_SCHEMA = "axm.building-utility-panel-service-surface-domain/v0.1"
SUCCESSOR_PAYLOAD_SCHEMA = "axm.building-utility-panel-uv-density-clearance-successor-payload/v0.1"
RECEIPT_SCHEMA = "axm.building-utility-panel-uv-density-clearance-successor-receipt/v0.1"
RESULT = "PASS_BUILDING_UTILITY_PANEL_UV_DENSITY_CLEARANCE_SUCCESSOR_PAYLOAD"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def require_close(actual: float, expected: float, label: str, tol: float = 1e-12) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tol):
        raise AssertionError(f"{label} mismatch: {actual!r} != {expected!r}")


def vec_close(actual, expected, label: str, tol: float = 1e-12) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"{label} length mismatch")
    for index, (a, b) in enumerate(zip(actual, expected)):
        require_close(float(a), float(b), f"{label}[{index}]", tol)


def derive(
    contract: dict,
    historical_payload: dict,
    procedural_summary: dict,
    successor_domain: dict,
    procedural_head: str,
) -> tuple[dict, dict]:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("successor review contract schema mismatch")
    if historical_payload.get("schema") != HISTORICAL_PAYLOAD_SCHEMA:
        raise AssertionError("historical Materials UV payload schema mismatch")
    if procedural_summary.get("schema") != PROCEDURAL_SCHEMA:
        raise AssertionError("Procedural successor summary schema mismatch")
    if successor_domain.get("schema") != SURFACE_SCHEMA:
        raise AssertionError("Hard-Surface successor domain schema mismatch")

    if contract.get("asset_id") != historical_payload.get("asset_id") or contract.get("asset_id") != successor_domain.get("asset_id"):
        raise AssertionError("asset identity mismatch across successor receiving chain")
    if contract.get("surface_id") != historical_payload.get("surface_id") or contract.get("surface_id") != successor_domain.get("surface_id"):
        raise AssertionError("surface identity mismatch across successor receiving chain")

    history = contract["historical_materials_uv_evidence"]
    chart = contract["historical_geometry_chart"]
    successor = contract["source_successor"]
    rebind = contract["procedural_rebind"]
    continuity = contract["continuity_requirements"]

    if history.get("head") != "c12766ecdc3e47a6d422a5af67b4cd28ec68c1ac":
        raise AssertionError("historical Materials evidence head drift")
    owner = historical_payload.get("owner_evidence", {})
    if owner.get("geometry_chart_head") != chart.get("head"):
        raise AssertionError("historical Geometry chart head drift")
    if owner.get("geometry_chart_blob") != chart.get("git_blob_sha"):
        raise AssertionError("historical Geometry chart blob drift")
    if chart.get("adopted_for_successor") is not False:
        raise AssertionError("historical Geometry chart must not be silently adopted")

    if procedural_head != rebind.get("head"):
        raise AssertionError("Procedural successor head drift")
    if procedural_summary.get("result") != rebind.get("required_result"):
        raise AssertionError("Procedural successor result is not the required PASS")
    if procedural_summary.get("decision") != rebind.get("required_decision"):
        raise AssertionError("Procedural successor decision drift")
    if procedural_summary.get("automatic_receiver_adoption") is not False:
        raise AssertionError("Procedural summary unexpectedly authorizes automatic receiver adoption")
    if rebind.get("automatic_receiver_adoption") is not False:
        raise AssertionError("Materials contract must not authorize automatic receiver adoption")
    if procedural_summary.get("source_authority_head") != successor.get("evidence_head"):
        raise AssertionError("Hard-Surface successor head mismatch")
    if procedural_summary.get("source_authority_panel_blob") != successor.get("panel_git_blob_sha"):
        raise AssertionError("Hard-Surface successor panel blob mismatch")

    source_panel = successor_domain.get("source_panel", {})
    if source_panel.get("git_blob_sha") != successor.get("panel_git_blob_sha"):
        raise AssertionError("successor service-surface domain is not bound to expected panel blob")

    metric = successor_domain.get("metric_domain", {})
    require_close(metric.get("primary_extent_m"), continuity.get("primary_extent_m"), "successor primary extent")
    require_close(metric.get("secondary_extent_m"), continuity.get("secondary_extent_m"), "successor secondary extent")
    require_close(metric.get("area_m2"), continuity.get("area_m2"), "successor surface area")
    vec_close(successor_domain.get("reference_frame", {}).get("origin_local_m", []), [0.04, 0.0, 0.0], "successor local surface origin")

    old_metric = historical_payload.get("surface_metric", {})
    require_close(old_metric.get("primary_extent_m"), metric.get("primary_extent_m"), "metric continuity primary")
    require_close(old_metric.get("secondary_extent_m"), metric.get("secondary_extent_m"), "metric continuity secondary")
    require_close(old_metric.get("area_m2"), metric.get("area_m2"), "metric continuity area")
    require_close(old_metric.get("outer_face_local_x_m"), 0.04, "metric continuity outer face")

    atlas = historical_payload.get("review_atlas", {})
    density = atlas.get("texel_density_px_per_m", [])
    vec_close(density, [float(continuity["review_texel_density_px_per_m"])] * 2, "historical review density")
    if atlas.get("active_region_px") != continuity.get("review_active_region_px"):
        raise AssertionError("historical active review region drift")
    require_close(atlas.get("checker_period_m"), continuity.get("review_checker_period_m"), "historical checker physical period")

    expected_receivers = list(continuity.get("receiver_ids", []))
    outputs = procedural_summary.get("outputs")
    if not isinstance(outputs, list):
        raise AssertionError("Procedural successor outputs missing")
    by_receiver = {str(row.get("receiver_id")): row for row in outputs}
    if sorted(by_receiver) != sorted(expected_receivers):
        raise AssertionError("Procedural successor receiver set drift")

    payload = copy.deepcopy(historical_payload)
    payload["schema"] = SUCCESSOR_PAYLOAD_SCHEMA
    payload["historical_payload_schema"] = HISTORICAL_PAYLOAD_SCHEMA
    payload["owner_evidence"] = dict(payload.get("owner_evidence", {}))
    payload["owner_evidence"].update(
        {
            "historical_materials_uv_head": history["head"],
            "procedural_successor_head": procedural_head,
            "hard_surface_successor_head": successor["evidence_head"],
            "hard_surface_successor_panel_blob": successor["panel_git_blob_sha"],
            "hard_surface_successor_service_surface_blob": successor["service_surface_git_blob_sha"],
            "historical_geometry_chart_rebound": False,
        }
    )

    components = payload.get("base_components")
    if not isinstance(components, list):
        raise AssertionError("historical base components missing")
    component_by_id = {str(row.get("id")): row for row in components}
    mapping = {
        "front-utility-bay": "panel-front-utility-bay",
        "east-utility-bay": "panel-east-utility-bay",
    }
    rebind_rows = []
    for receiver_id in expected_receivers:
        row = by_receiver[receiver_id]
        component_id = mapping[receiver_id]
        component = component_by_id.get(component_id)
        if not isinstance(component, dict):
            raise AssertionError(f"missing historical panel component {component_id}")
        predecessor_center = row.get("predecessor_panel_center_m", [])
        successor_center = row.get("successor_panel_center_m", [])
        vec_close(component.get("center_m", []), predecessor_center, f"{receiver_id} predecessor center")
        displacement = row.get("panel_center_displacement_m", [])
        required_translation = float(continuity["required_receiver_translation_m"])
        require_close(row.get("panel_center_displacement_magnitude_m"), required_translation, f"{receiver_id} translation magnitude")
        if math.sqrt(sum(float(v) ** 2 for v in displacement)) <= 0.0:
            raise AssertionError(f"{receiver_id} successor displacement unexpectedly zero")
        vec_close(row.get("service_surface_origin_displacement_m", []), displacement, f"{receiver_id} service-surface translation")
        require_close(row.get("source_service_surface_primary_extent_m"), metric.get("primary_extent_m"), f"{receiver_id} primary metric")
        require_close(row.get("source_service_surface_secondary_extent_m"), metric.get("secondary_extent_m"), f"{receiver_id} secondary metric")
        require_close(row.get("source_service_surface_area_m2"), metric.get("area_m2"), f"{receiver_id} area")
        require_close(row.get("successor_physical_body_gap_m"), successor.get("required_physical_body_gap_m"), f"{receiver_id} body gap")
        require_close(row.get("clearance_slack_m"), 0.0, f"{receiver_id} clearance slack")
        component["center_m"] = [float(v) for v in successor_center]
        rebind_rows.append(
            {
                "receiver_id": receiver_id,
                "component_id": component_id,
                "predecessor_center_m": [float(v) for v in predecessor_center],
                "successor_center_m": [float(v) for v in successor_center],
                "displacement_m": [float(v) for v in displacement],
                "displacement_magnitude_m": float(row["panel_center_displacement_magnitude_m"]),
                "procedural_output_digest": row.get("output_digest"),
            }
        )

    payload["successor_continuity"] = {
        "receiving_policy": contract["receiving_policy"],
        "source_service_surface_local_frame_changed": False,
        "source_service_surface_metric_domain_changed": False,
        "historical_geometry_chart_rebound": False,
        "automatic_receiver_adoption": False,
        "receiver_rebinds": rebind_rows,
        "procedural_family_digest": procedural_summary.get("canonical_family_digest"),
    }
    payload["truth_boundary"] = copy.deepcopy(contract["truth_boundary"])

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": RESULT,
        "asset_id": contract["asset_id"],
        "surface_id": contract["surface_id"],
        "procedural_head": procedural_head,
        "hard_surface_successor_head": successor["evidence_head"],
        "historical_materials_uv_head": history["head"],
        "historical_geometry_chart_head": chart["head"],
        "historical_geometry_chart_rebound": False,
        "review_texel_density_px_per_m": density,
        "review_active_region_px": atlas["active_region_px"],
        "review_checker_period_m": atlas["checker_period_m"],
        "receiver_rebinds": rebind_rows,
        "payload_sha256": canonical_digest(payload),
        "truth_boundary": copy.deepcopy(contract["truth_boundary"]),
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="lookdev/building_utility_panel_uv_density_clearance_successor_001.json")
    parser.add_argument("--historical-payload", required=True)
    parser.add_argument("--procedural-summary", required=True)
    parser.add_argument("--successor-domain", required=True)
    parser.add_argument("--procedural-head", required=True)
    parser.add_argument("--out", default="lookdev-utility-panel-uv-proof/generated/successor")
    args = parser.parse_args()

    contract_path = Path(args.contract)
    historical_path = Path(args.historical_payload)
    procedural_path = Path(args.procedural_summary)
    successor_domain_path = Path(args.successor_domain)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    payload, receipt = derive(
        load_json(contract_path),
        load_json(historical_path),
        load_json(procedural_path),
        load_json(successor_domain_path),
        args.procedural_head,
    )
    receipt["inputs"] = {
        "contract_sha256": sha256(contract_path),
        "historical_payload_sha256": sha256(historical_path),
        "procedural_summary_sha256": sha256(procedural_path),
        "successor_domain_sha256": sha256(successor_domain_path),
    }
    (out / "utility_panel_uv_density_clearance_successor_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
