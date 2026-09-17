#!/usr/bin/env python3
import argparse
import copy
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = ROOT / "assets/utility_access_panel_001.json"
PAVILION_PATH = ROOT / "assets/service_pavilion_001.json"
DOMAIN_PATH = ROOT / "assets/utility_access_panel_001_service_surface_domain.json"
POLICY_PATH = ROOT / "assets/utility_access_panel_001_receiver_clearance_envelope.json"
EPS = 1e-12
RESULT = "PASS_SOURCE_OWNED_BUILDING_UTILITY_PANEL_RECEIVER_CLEARANCE_ENVELOPE"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def approx(a, b, eps=EPS):
    return abs(float(a) - float(b)) <= eps


def vec_approx(a, b, eps=EPS):
    return len(a) == len(b) and all(approx(x, y, eps) for x, y in zip(a, b))


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def mul(a, scalar):
    return [x * scalar for x in a]


def git_blob(path):
    rel = path.relative_to(ROOT).as_posix()
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{rel}"], cwd=ROOT, text=True
    ).strip()


def receiver_metrics(panel, interface):
    depth = float(panel["body_depth_m"])
    standoff = float(panel["standoff_from_receiver_origin_m"])
    plate = float(interface["plate_thickness_m"])
    required = float(panel["required_body_clearance_beyond_plate_m"])
    inner = standoff - depth / 2.0
    outer = standoff + depth / 2.0
    gap = inner - plate
    legacy_center_surplus = standoff - plate
    panel_center = add(interface["origin"], mul(interface["normal"], standoff))
    footprint_margin = [
        float(interface["plate_footprint_m"][0]) - float(panel["interface_footprint_m"][0]),
        float(interface["plate_footprint_m"][1]) - float(panel["interface_footprint_m"][1]),
    ]
    return {
        "panel_center": panel_center,
        "plate_outer_offset_m": plate,
        "panel_body_inner_offset_m": inner,
        "panel_body_outer_offset_m": outer,
        "physical_body_gap_m": gap,
        "required_body_clearance_m": required,
        "clearance_slack_m": gap - required,
        "legacy_center_offset_surplus_m": legacy_center_surplus,
        "footprint_margin_m": footprint_margin,
        "per_side_footprint_margin_m": [footprint_margin[0] / 2.0, footprint_margin[1] / 2.0],
    }


def _verify(panel, pavilion, domain, policy):
    if panel.get("schema") != "axm.building-utility-panel/v0.1":
        raise ValueError("panel schema drift")
    if panel.get("asset_id") != "utility-access-panel-001":
        raise ValueError("panel asset identity drift")
    if panel.get("units") != "meters":
        raise ValueError("panel units drift")

    if policy.get("schema") != "axm.building-utility-panel-receiver-clearance-envelope/v0.1":
        raise ValueError("clearance policy schema drift")
    if policy.get("asset_id") != panel["asset_id"]:
        raise ValueError("clearance policy asset identity drift")
    if policy.get("owner") != "Building Hard Surface":
        raise ValueError("clearance authority owner drift")
    if policy.get("base_hard_surface_head") != "97120eb78a72b0a07aff1c65b9b92229d0a42aff":
        raise ValueError("clearance base-head drift")
    if policy.get("predecessor_source_blob") != "4da242e35a84b20a80f4acf28146be613624e734":
        raise ValueError("predecessor source identity drift")

    actual_panel_blob = git_blob(PANEL_PATH)
    actual_pavilion_blob = git_blob(PAVILION_PATH)
    if policy.get("successor_source_blob") != actual_panel_blob:
        raise ValueError(f"successor source blob drift: {actual_panel_blob}")
    if policy.get("pavilion_source_blob") != actual_pavilion_blob:
        raise ValueError(f"pavilion source blob drift: {actual_pavilion_blob}")

    expected_source = policy.get("expected_source", {})
    if not approx(panel.get("body_depth_m"), expected_source.get("body_depth_m")):
        raise ValueError("panel body depth drift")
    if not approx(panel.get("standoff_from_receiver_origin_m"), expected_source.get("standoff_from_receiver_origin_m")):
        raise ValueError("panel standoff drift")
    if not approx(panel.get("required_body_clearance_beyond_plate_m"), expected_source.get("required_body_clearance_beyond_plate_m")):
        raise ValueError("required body clearance drift")
    if not vec_approx(panel.get("interface_footprint_m"), expected_source.get("interface_footprint_m")):
        raise ValueError("panel footprint drift")
    if panel.get("mount_points_local_m") != expected_source.get("mount_points_local_m"):
        raise ValueError("panel mount-point identity drift")
    proof = panel.get("proof_geometry", {})
    if proof.get("kind") != "box" or not vec_approx(proof.get("size_local_xyz_m", []), [0.08, 1.10, 1.50]):
        raise ValueError("panel proof-box identity drift")
    if panel.get("standoff_semantics") != "Under the exact service-pavilion receiver-fit convention, this is the receiver-normal distance from interface origin to panel body center. Physical body gap beyond the receiver plate is standoff - plate_thickness - 0.5 * body_depth.":
        raise ValueError("panel standoff semantics missing or drifted")

    # The source-owned service surface stays local to the proof box. Only its source pin changes.
    if domain.get("schema") != "axm.building-utility-panel-service-surface-domain/v0.1":
        raise ValueError("service-surface domain schema drift")
    if domain.get("source_panel", {}).get("git_blob_sha") != actual_panel_blob:
        raise ValueError("service-surface domain not rebound to corrected source")
    if domain.get("surface_id") != "utility_panel_outer_service_surface":
        raise ValueError("service-surface identity drift")
    if not vec_approx(domain.get("reference_frame", {}).get("origin_local_m", []), [0.04, 0.0, 0.0]):
        raise ValueError("service-surface local origin drift")
    if not vec_approx(domain.get("reference_frame", {}).get("outward_axis_local", []), [1.0, 0.0, 0.0]):
        raise ValueError("service-surface outward axis drift")
    metric = domain.get("metric_domain", {})
    if not approx(metric.get("primary_extent_m"), 1.10) or not approx(metric.get("secondary_extent_m"), 1.50) or not approx(metric.get("area_m2"), 1.65):
        raise ValueError("service-surface metric domain drift")

    authority = policy.get("authority", {})
    downstream = set(authority.get("downstream_or_unproven_facts", []))
    forbidden_owner_expansion = {
        "fastener geometry", "tooling envelope", "hinges", "latches", "seals",
        "engineering loads", "manufacturing tolerance", "collision or physics",
        "runtime attachment", "materials or UVs", "Map adoption", "visual acceptance",
        "Universal Creation implementation", "Profession Fabric implementation",
    }
    if not forbidden_owner_expansion.issubset(downstream):
        raise ValueError("clearance authority boundary weakened")
    convention = policy.get("receiver_fit_convention", {})
    if convention.get("physical_body_gap_formula") != "standoff_from_receiver_origin_m - plate_thickness_m - body_depth_m/2":
        raise ValueError("physical gap formula drift")
    if convention.get("rule") != "BODY_CLEARANCE_MUST_BE_MEASURED_FROM_THE_NEAREST_BODY_FACE__CENTER_OFFSET_MINUS_PLATE_THICKNESS_IS_NOT_BODY_GAP_WHEN_THE_BODY_HAS_DEPTH":
        raise ValueError("reusable clearance rule drift")

    interfaces = {row["id"]: row for row in pavilion.get("interfaces", [])}
    expected_receivers = policy.get("expected_receivers", [])
    if len(expected_receivers) != 2 or set(interfaces) != {"front-utility-bay", "east-utility-bay"}:
        raise ValueError("exact receiver family drift")

    expected_clearance = policy.get("expected_clearance", {})
    receiver_rows = []
    for expected in expected_receivers:
        interface_id = expected["interface_id"]
        if interface_id not in interfaces:
            raise ValueError(f"missing receiver {interface_id}")
        interface = interfaces[interface_id]
        if not vec_approx(interface.get("origin", []), expected["origin"]):
            raise ValueError(f"{interface_id}: origin drift")
        if not vec_approx(interface.get("normal", []), expected["normal"]):
            raise ValueError(f"{interface_id}: normal drift")
        if not vec_approx(interface.get("plate_footprint_m", []), expected["plate_footprint_m"]):
            raise ValueError(f"{interface_id}: plate footprint drift")
        if not approx(interface.get("plate_thickness_m"), expected["plate_thickness_m"]):
            raise ValueError(f"{interface_id}: plate thickness drift")
        if interface.get("mount_points_local_m") != panel.get("mount_points_local_m"):
            raise ValueError(f"{interface_id}: mount pattern drift")

        metrics = receiver_metrics(panel, interface)
        if not vec_approx(metrics["panel_center"], expected["expected_panel_center"]):
            raise ValueError(f"{interface_id}: corrected panel center drift")
        for key in ("plate_outer_offset_m", "panel_body_inner_offset_m", "panel_body_outer_offset_m", "physical_body_gap_m"):
            if not approx(metrics[key], expected_clearance[key]):
                raise ValueError(f"{interface_id}: {key} drift")
        if not approx(metrics["legacy_center_offset_surplus_m"], expected_clearance["successor_legacy_center_surplus_m"]):
            raise ValueError(f"{interface_id}: legacy center-surplus witness drift")
        if approx(metrics["legacy_center_offset_surplus_m"], metrics["physical_body_gap_m"]):
            raise ValueError(f"{interface_id}: center surplus incorrectly equals physical body gap")
        if metrics["physical_body_gap_m"] + EPS < metrics["required_body_clearance_m"]:
            raise ValueError(f"{interface_id}: corrected source still violates required physical body gap")
        if not vec_approx(metrics["per_side_footprint_margin_m"], expected_clearance["per_side_footprint_margin_m"]):
            raise ValueError(f"{interface_id}: per-side footprint margin drift")
        receiver_rows.append({"interface_id": interface_id, **metrics})

    predecessor = copy.deepcopy(panel)
    predecessor["standoff_from_receiver_origin_m"] = float(expected_clearance["predecessor_standoff_m"])
    predecessor_rows = []
    for expected in expected_receivers:
        metrics = receiver_metrics(predecessor, interfaces[expected["interface_id"]])
        if not approx(metrics["physical_body_gap_m"], expected_clearance["predecessor_physical_body_gap_m"]):
            raise ValueError("predecessor physical-gap witness drift")
        shortfall = metrics["required_body_clearance_m"] - metrics["physical_body_gap_m"]
        if not approx(shortfall, expected_clearance["predecessor_clearance_shortfall_m"]):
            raise ValueError("predecessor shortfall witness drift")
        if metrics["physical_body_gap_m"] + EPS >= metrics["required_body_clearance_m"]:
            raise ValueError("predecessor unexpectedly satisfies physical body clearance")
        predecessor_rows.append({"interface_id": expected["interface_id"], **metrics, "clearance_shortfall_m": shortfall})

    return {
        "schema": "axm.building-utility-panel-receiver-clearance-envelope-evidence/v0.1",
        "result": RESULT,
        "asset_id": panel["asset_id"],
        "panel_source_blob": actual_panel_blob,
        "pavilion_source_blob": actual_pavilion_blob,
        "service_surface_domain_blob": git_blob(DOMAIN_PATH),
        "predecessor_source_blob": policy["predecessor_source_blob"],
        "reusable_rule": convention["rule"],
        "receiver_results": receiver_rows,
        "predecessor_failure_witness": predecessor_rows,
        "source_service_surface_changed": False,
        "source_footprint_changed": False,
        "source_mount_pattern_changed": False,
        "source_body_depth_changed": False,
        "source_standoff_changed_from_m": 0.08,
        "source_standoff_changed_to_m": 0.10,
        "downstream_adoption_authorized": False,
        "uc_or_pf_implementation_changed": False,
        "status": policy["status"],
        "truth_boundary": policy["truth_boundary"],
    }


def verify(panel=None, pavilion=None, domain=None, policy=None):
    return _verify(
        panel or load(PANEL_PATH),
        pavilion or load(PAVILION_PATH),
        domain or load(DOMAIN_PATH),
        policy or load(POLICY_PATH),
    )


def negative_controls():
    panel = load(PANEL_PATH)
    pavilion = load(PAVILION_PATH)
    domain = load(DOMAIN_PATH)
    policy = load(POLICY_PATH)
    controls = {}

    cases = []
    bad = copy.deepcopy(panel)
    bad["standoff_from_receiver_origin_m"] = 0.08
    cases.append(("predecessor_standoff_0p08m", bad, pavilion, domain, policy))

    bad = copy.deepcopy(panel)
    bad["body_depth_m"] = 0.10
    cases.append(("body_depth_0p10m", bad, pavilion, domain, policy))

    bad = copy.deepcopy(panel)
    bad["required_body_clearance_beyond_plate_m"] = 0.03
    cases.append(("required_gap_0p03m", bad, pavilion, domain, policy))

    bad_pavilion = copy.deepcopy(pavilion)
    for row in bad_pavilion["interfaces"]:
        if row["id"] == "front-utility-bay":
            row["plate_thickness_m"] = 0.05
    cases.append(("front_plate_thickness_0p05m", panel, bad_pavilion, domain, policy))

    bad_policy = copy.deepcopy(policy)
    bad_policy["authority"]["downstream_or_unproven_facts"].remove("fastener geometry")
    cases.append(("authority_expansion_fastener_geometry", panel, pavilion, domain, bad_policy))

    for name, p, pav, dom, pol in cases:
        try:
            _verify(p, pav, dom, pol)
            controls[name] = "UNEXPECTED_PASS"
        except ValueError as exc:
            controls[name] = "REJECTED: " + str(exc)

    if any(not value.startswith("REJECTED") for value in controls.values()):
        raise ValueError("clearance negative control unexpectedly passed")
    return controls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = verify()
    receipt["negative_controls"] = negative_controls()
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
