#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "geometry/utility_access_panel_review_atlas_directional_sampling_001.json"
CHART_PATH = ROOT / "geometry/utility_access_panel_service_surface_chart_001.json"

SCHEMA = "axm.building-utility-panel-review-atlas-directional-sampling-rebind/v0.1"
RESULT = "PASS_BUILDING_REVIEW_ATLAS_DIRECTIONAL_SAMPLING_INTERFACE__HOLD_EMBEDDED_GLB_OBSERVER"
DECISION = "PASS_OWNER_BOUND_REVIEW_SAMPLING_MEASUREMENT__NO_TRANSFER_TO_UC_GLTF_EVIDENCE_OR_POLICY_ADOPTION"
PATTERN = "OWNER_BOUND_REVIEW_ATLAS_ACTIVE_REGION_TO_PHYSICAL_UV_SAMPLING_WITHOUT_GLTF_EVIDENCE_TRANSFER"

GEOMETRY_CHART_BLOB = "08431f75edff5ae7d8b8c32468190e7a1b81d526"
MATERIALS_HEAD = "fe4fdfb2033b0c3c2705a532b9e6b610a3d119c1"
MATERIALS_BASE_PATH = Path("lookdev/building_utility_panel_uv_density_001.json")
MATERIALS_BASE_BLOB = "a35ed0b214d7d4443127decabe06c8b05e8bc49b"
MATERIALS_SUCCESSOR_PATH = Path("lookdev/building_utility_panel_uv_density_clearance_successor_001.json")
MATERIALS_SUCCESSOR_BLOB = "61ba08fcef44fd685c60c833d39ec28171e78859"
MATERIALS_OBSERVER_PATH = Path("lookdev-utility-panel-uv-proof/observe.gd")
MATERIALS_OBSERVER_BLOB = "7edaaa1550a21f482b27436a00d417ada4e90b35"

UC_MERGE = "aa53ee8aa803c19524b7edbef6250bf6ed9336c0"
UC_MODULE_PATH = Path("src/axm_uc/material_uv_evidence.py")
UC_MODULE_BLOB = "bc7aa2ffc2c598d75a78739c70fd349138f511e2"
UC_API = "inspect_material_uv_density"

EPS = 1e-12


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def git_blob(root: Path, path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{path.as_posix()}"],
        text=True,
    ).strip()


def close(actual: float, expected: float, label: str, eps: float = EPS) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=eps):
        raise ValueError(f"{label} drift: {actual!r} != {expected!r}")


def vec_close(actual, expected, label: str, eps: float = EPS) -> None:
    if not isinstance(actual, list) or len(actual) != len(expected):
        raise ValueError(f"{label} shape drift")
    for index, (a, b) in enumerate(zip(actual, expected)):
        close(a, b, f"{label}[{index}]", eps)


def verify_repository_bindings(
    contract: dict,
    *,
    materials_root: Path,
    uc_root: Path,
) -> dict:
    chart_binding = contract.get("geometry_chart", {})
    actual_chart_blob = git_blob(ROOT, CHART_PATH.relative_to(ROOT))
    if actual_chart_blob != GEOMETRY_CHART_BLOB or chart_binding.get("git_blob_sha") != actual_chart_blob:
        raise ValueError("current Geometry chart blob drift")

    if git_head(materials_root) != MATERIALS_HEAD:
        raise ValueError("Materials donor head drift")
    expected_material_blobs = {
        MATERIALS_BASE_PATH: MATERIALS_BASE_BLOB,
        MATERIALS_SUCCESSOR_PATH: MATERIALS_SUCCESSOR_BLOB,
        MATERIALS_OBSERVER_PATH: MATERIALS_OBSERVER_BLOB,
    }
    actual_material_blobs = {}
    for path, expected in expected_material_blobs.items():
        actual = git_blob(materials_root, path)
        actual_material_blobs[path.as_posix()] = actual
        if actual != expected:
            raise ValueError(f"Materials donor blob drift: {path}")

    if git_head(uc_root) != UC_MERGE:
        raise ValueError("UC observer merge identity drift")
    actual_uc_blob = git_blob(uc_root, UC_MODULE_PATH)
    if actual_uc_blob != UC_MODULE_BLOB:
        raise ValueError("UC observer module blob drift")

    return {
        "geometry_chart_blob": actual_chart_blob,
        "materials_head": MATERIALS_HEAD,
        "materials_blobs": actual_material_blobs,
        "uc_merge": UC_MERGE,
        "uc_module_blob": actual_uc_blob,
    }


def derive(
    contract: dict,
    chart: dict,
    materials_base: dict,
    materials_successor: dict,
    materials_observer_text: str,
    uc_module_text: str,
) -> dict:
    if contract.get("schema") != SCHEMA:
        raise ValueError("sampling contract schema drift")
    if contract.get("pattern") != PATTERN:
        raise ValueError("sampling pattern drift")
    if contract.get("asset_id") != "utility-access-panel-001":
        raise ValueError("asset identity drift")
    if contract.get("surface_id") != "utility_panel_outer_service_surface":
        raise ValueError("surface identity drift")

    geometry = contract.get("geometry_chart", {})
    if geometry.get("owner") != "Geometry / Topology" or geometry.get("pull_request") != 18:
        raise ValueError("Geometry chart authority drift")
    if geometry.get("path") != CHART_PATH.relative_to(ROOT).as_posix():
        raise ValueError("Geometry chart path drift")
    if geometry.get("git_blob_sha") != GEOMETRY_CHART_BLOB:
        raise ValueError("Geometry chart pinned blob drift")

    directional = chart.get("directional_sampling_interface", {})
    if directional.get("chart_axis_order") != ["u", "v"]:
        raise ValueError("Geometry chart axis order drift")
    physical_extent = directional.get("physical_extent_m_by_chart_axis")
    vec_close(physical_extent, [1.1, 1.5], "Geometry physical extents")
    vec_close(directional.get("normalized_extent_by_chart_axis"), [1.0, 1.0], "Geometry normalized extents")
    vec_close(directional.get("metres_per_uv_unit_by_chart_axis"), physical_extent, "Geometry metres per UV unit")

    shared = directional.get("shared_observer", {})
    if shared.get("merge_commit") != UC_MERGE or shared.get("api") != UC_API:
        raise ValueError("Geometry shared observer identity drift")

    materials = contract.get("materials_review", {})
    if materials.get("owner") != "Materials / LookDev" or materials.get("pull_request") != 3:
        raise ValueError("Materials authority drift")
    if materials.get("head") != MATERIALS_HEAD:
        raise ValueError("Materials pinned head drift")
    if materials.get("base_contract_blob_sha") != MATERIALS_BASE_BLOB:
        raise ValueError("Materials base-contract blob drift")
    if materials.get("successor_contract_blob_sha") != MATERIALS_SUCCESSOR_BLOB:
        raise ValueError("Materials successor-contract blob drift")
    if materials.get("target_host_observer_blob_sha") != MATERIALS_OBSERVER_BLOB:
        raise ValueError("Materials observer blob drift")

    if materials_base.get("schema") != "axm.building-utility-panel-uv-density-review/v0.1":
        raise ValueError("Materials base review schema drift")
    if materials_successor.get("schema") != "axm.building-utility-panel-uv-density-clearance-successor-review/v0.1":
        raise ValueError("Materials successor review schema drift")
    for payload in (materials_base, materials_successor):
        if payload.get("asset_id") != contract["asset_id"] or payload.get("surface_id") != contract["surface_id"]:
            raise ValueError("Materials asset/surface identity drift")

    review = materials_base.get("review_candidate", {})
    atlas_size = review.get("atlas_size_px")
    active_region = review.get("active_region_px")
    if atlas_size != [512, 512]:
        raise ValueError("Materials review atlas size drift")
    if active_region != [352, 480]:
        raise ValueError("Materials review active region drift")
    close(review.get("texel_density_px_per_m"), 320.0, "Materials review density")
    close(review.get("diagnostic_checker_period_m"), 0.05, "Materials checker period")
    if review.get("diagnostic_checker_period_px") != 16:
        raise ValueError("Materials checker pixel period drift")

    continuity = materials_successor.get("continuity_requirements", {})
    vec_close(
        [continuity.get("primary_extent_m"), continuity.get("secondary_extent_m")],
        physical_extent,
        "Materials successor metric extents",
    )
    if continuity.get("review_active_region_px") != active_region:
        raise ValueError("Materials successor active-region continuity drift")
    close(continuity.get("review_texel_density_px_per_m"), 320.0, "Materials successor review density")

    required_observer_snippets = (
        "Image.create(width, height, false, Image.FORMAT_RGBA8)",
        "ImageTexture.create_from_image(image)",
        'uv_bounds = payload["review_atlas"]["active_uv_bounds"] as Array',
    )
    for snippet in required_observer_snippets:
        if snippet not in materials_observer_text:
            raise ValueError("Materials target-host observer implementation drift")

    uc_binding = contract.get("shared_glb_observer", {})
    expected_uc = {
        "repository": "mike-axiom-mir/axm-universal-creation",
        "pull_request": 194,
        "merge_commit": UC_MERGE,
        "module_path": UC_MODULE_PATH.as_posix(),
        "module_blob_sha": UC_MODULE_BLOB,
        "api": UC_API,
    }
    if uc_binding != expected_uc:
        raise ValueError("shared GLB observer binding drift")
    if "Measure actual static GLB triangle UV scale against embedded texture sizes." not in uc_module_text:
        raise ValueError("UC GLB observer semantic boundary drift")
    if f"def {UC_API}(" not in uc_module_text:
        raise ValueError("UC GLB observer API drift")

    active_uv_span = [
        float(active_region[0]) / float(atlas_size[0]),
        float(active_region[1]) / float(atlas_size[1]),
    ]
    review_density = [
        float(active_region[0]) / float(physical_extent[0]),
        float(active_region[1]) / float(physical_extent[1]),
    ]
    review_anisotropy = max(review_density) / min(review_density)
    negative_density = [
        float(atlas_size[0]) / float(physical_extent[0]),
        float(atlas_size[1]) / float(physical_extent[1]),
    ]
    negative_anisotropy = max(negative_density) / min(negative_density)

    claim = contract.get("review_sampling_claim", {})
    if claim.get("scope") != "MATERIALS_GODOT_REVIEW_ATLAS_SPACE_ONLY":
        raise ValueError("review sampling scope drift")
    if claim.get("atlas_size_px") != atlas_size:
        raise ValueError("declared review atlas size drift")
    if claim.get("active_region_px") != active_region:
        raise ValueError("declared active region drift")
    vec_close(claim.get("active_uv_span"), active_uv_span, "declared active UV span")
    vec_close(claim.get("physical_extent_m_by_chart_axis"), physical_extent, "declared physical extents")
    vec_close(claim.get("directional_texels_per_m_by_chart_axis"), review_density, "declared review directional density")
    close(claim.get("anisotropy_ratio"), review_anisotropy, "declared review anisotropy")
    vec_close(
        claim.get("negative_full_square_texels_per_m_by_chart_axis"),
        negative_density,
        "declared negative directional density",
        eps=1e-9,
    )
    close(
        claim.get("negative_full_square_anisotropy_ratio"),
        negative_anisotropy,
        "declared negative anisotropy",
        eps=1e-12,
    )

    negative = materials_base.get("negative_control", {})
    vec_close(
        negative.get("expected_effective_density_px_per_m"),
        negative_density,
        "Materials negative density",
        eps=1e-9,
    )
    close(
        negative.get("expected_density_ratio_max_over_min"),
        negative_anisotropy,
        "Materials negative anisotropy",
        eps=1e-12,
    )

    transfer = contract.get("evidence_transfer_boundary", {})
    required_false = (
        "geometry_selects_texel_density_target",
        "geometry_selects_atlas_layout",
        "geometry_selects_anisotropy_threshold",
        "material_bearing_glb_bound",
        "embedded_glb_image_dimensions_proven",
        "uc_glb_observer_consumed",
        "embedded_glb_directional_density_measured",
    )
    if transfer.get("materials_review_is_target_policy") is not True:
        raise ValueError("Materials review-policy ownership drift")
    if transfer.get("review_image_is_runtime_generated_godot_imagetexture") is not True:
        raise ValueError("runtime-generated review-image boundary drift")
    for key in required_false:
        if transfer.get(key) is not False:
            raise ValueError(f"evidence transfer boundary weakened: {key}")
    if transfer.get("transfer_policy") != "REVIEW_ATLAS_MEASUREMENT_IS_NOT_EMBEDDED_GLTF_IMAGE_EVIDENCE__EXPLICIT_GLTF_BIND_AND_RERUN_REQUIRED":
        raise ValueError("review-to-GLTF transfer policy drift")

    return {
        "atlas_size_px": atlas_size,
        "active_region_px": active_region,
        "active_uv_span": active_uv_span,
        "physical_extent_m_by_chart_axis": physical_extent,
        "directional_texels_per_m_by_chart_axis": review_density,
        "anisotropy_ratio": review_anisotropy,
        "negative_full_square_texels_per_m_by_chart_axis": negative_density,
        "negative_full_square_anisotropy_ratio": negative_anisotropy,
        "materials_workflow_run": materials["exact_workflow_run"],
        "materials_artifact_id": materials["retained_artifact_id"],
        "materials_artifact_sha256": materials["retained_artifact_sha256"],
        "materials_artifact_size_bytes": materials["retained_artifact_size_bytes"],
        "review_scope": claim["scope"],
        "transfer_policy": transfer["transfer_policy"],
        "uc_glb_observer_consumed": transfer["uc_glb_observer_consumed"],
        "embedded_glb_directional_density_measured": transfer["embedded_glb_directional_density_measured"],
    }


def run_negative_controls(contract, chart, materials_base, materials_successor, observer_text, uc_text):
    controls = {}

    def reject(name, *, c=None, ch=None, mb=None, ms=None, ot=None, ut=None):
        try:
            derive(
                copy.deepcopy(c if c is not None else contract),
                copy.deepcopy(ch if ch is not None else chart),
                copy.deepcopy(mb if mb is not None else materials_base),
                copy.deepcopy(ms if ms is not None else materials_successor),
                observer_text if ot is None else ot,
                uc_text if ut is None else ut,
            )
        except ValueError as exc:
            controls[name] = f"REJECTED:{exc}"
        else:
            controls[name] = "FAILED_TO_REJECT"

    bad = copy.deepcopy(contract)
    bad["materials_review"]["head"] = "0" * 40
    reject("materials_head_drift", c=bad)

    bad = copy.deepcopy(materials_base)
    bad["review_candidate"]["atlas_size_px"][0] += 1
    reject("review_atlas_size_drift", mb=bad)

    bad = copy.deepcopy(materials_base)
    bad["review_candidate"]["active_region_px"][0] += 1
    reject("review_active_region_drift", mb=bad)

    bad = copy.deepcopy(chart)
    bad["directional_sampling_interface"]["physical_extent_m_by_chart_axis"][0] += 0.01
    reject("geometry_physical_extent_drift", ch=bad)

    bad = copy.deepcopy(materials_successor)
    bad["continuity_requirements"]["review_texel_density_px_per_m"] = 319
    reject("materials_successor_density_drift", ms=bad)

    bad = copy.deepcopy(contract)
    bad["evidence_transfer_boundary"]["material_bearing_glb_bound"] = True
    reject("fabricated_material_bearing_glb", c=bad)

    bad = copy.deepcopy(contract)
    bad["evidence_transfer_boundary"]["uc_glb_observer_consumed"] = True
    reject("fabricated_uc_glb_observer_consumption", c=bad)

    bad = copy.deepcopy(contract)
    bad["evidence_transfer_boundary"]["geometry_selects_texel_density_target"] = True
    reject("geometry_density_policy_escalation", c=bad)

    reject(
        "materials_runtime_image_implementation_drift",
        ot=observer_text.replace("ImageTexture.create_from_image(image)", "ImageTexture.new()", 1),
    )

    if any(not value.startswith("REJECTED:") for value in controls.values()):
        raise ValueError("one or more review-sampling negative controls unexpectedly passed")
    return controls


def build(*, exact_head: str, materials_root: Path, uc_root: Path) -> dict:
    contract = load_json(CONTRACT_PATH)
    chart = load_json(CHART_PATH)
    materials_base = load_json(materials_root / MATERIALS_BASE_PATH)
    materials_successor = load_json(materials_root / MATERIALS_SUCCESSOR_PATH)
    observer_text = (materials_root / MATERIALS_OBSERVER_PATH).read_text(encoding="utf-8")
    uc_text = (uc_root / UC_MODULE_PATH).read_text(encoding="utf-8")

    bindings = verify_repository_bindings(contract, materials_root=materials_root, uc_root=uc_root)
    core = derive(contract, chart, materials_base, materials_successor, observer_text, uc_text)
    negatives = run_negative_controls(
        contract, chart, materials_base, materials_successor, observer_text, uc_text
    )
    return {
        "schema": "axm.building-utility-panel-review-atlas-directional-sampling-evidence/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "pattern": PATTERN,
        "exact_geometry_head": exact_head,
        "asset_id": contract["asset_id"],
        "surface_id": contract["surface_id"],
        "repository_bindings": bindings,
        **core,
        "review_density_is_materials_owned": True,
        "source_geometry_changed": False,
        "uv_chart_changed": False,
        "production_uv_adopted": False,
        "production_texel_density_adopted": False,
        "downstream_adoption_authorized": False,
        "negative_controls": negatives,
        "truth_boundary": contract["truth_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--materials-root", required=True)
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = build(
        exact_head=args.exact_head,
        materials_root=Path(args.materials_root),
        uc_root=Path(args.uc_root),
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
