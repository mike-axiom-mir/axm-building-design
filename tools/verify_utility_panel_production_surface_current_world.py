from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

RESULT = "PASS_BUILDING_UTILITY_PANEL_PRODUCTION_SURFACE_SUCCESSOR_CURRENT_WORLD_THREE_WAY_REVIEW_READY__HOLD_ART_QA_ENV_RUNTIME_ADOPTION"
SUCCESSOR_STATE = "PASS_CURRENT_WORLD_BUILDING_UTILITY_PANEL_PRODUCTION_SURFACE_SUCCESSOR__MATERIALS_REVIEW_ONLY__ADOPTION_HELD"
TA_HEAD = "1434bc4a64faa04db10f47723c37ab7925aaa163"
ENV_HEAD = "595df99daf866b5e3dcaa4be87eeb650af637919"
CHECKER_PNG_SHA = "e932cdd94d370184c7361862d5064149cc193e3a8fd80b269cab6543c0919198"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def canonical_runtime(runtime: dict) -> dict:
    drop = {
        "environment_building_utility_panel_material_current_world_state",
        "environment_building_utility_panel_material_current_world_rule",
        "environment_building_utility_panel_material_technical_art_head",
        "environment_building_utility_panel_material_materials_head",
        "environment_building_utility_panel_material_png_sha256",
        "environment_building_utility_panel_material_rgba8_sha256",
        "environment_building_utility_panel_material_environment_adoption",
        "environment_building_utility_panel_material_art_qa_acceptance",
        "environment_building_utility_panel_material_runtime_acceptance",
        "environment_building_utility_panel_material_truth_boundary",
    }

    def scrub(value, path=()):
        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                if key in drop or key in {"node_instance_id", "mesh_instance_id", "material_instance_id"}:
                    continue
                if key == "environment_building_utility_panel_material_current_world":
                    continue
                if path and path[-1] == "capture" and key == "bytes":
                    continue
                if path and path[-1] == "runtime" and key in {"buffer_mem_bytes", "texture_mem_bytes"}:
                    continue
                out[key] = scrub(item, path + (key,))
            return out
        if isinstance(value, list):
            return [scrub(item, path + (str(i),)) for i, item in enumerate(value)]
        return value

    return scrub(runtime)


def image_array(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def pair_metrics(a: np.ndarray, b: np.ndarray) -> tuple[dict, np.ndarray]:
    if a.shape != b.shape:
        raise AssertionError(f"image dimension drift: {a.shape} != {b.shape}")
    delta = np.abs(a - b)
    per = delta.max(axis=2)
    gt1 = per > 1
    ys, xs = np.nonzero(gt1)
    metrics = {
        "raw_changed_pixels": int((per > 0).sum()),
        "changed_pixels_gt_1lsb": int(gt1.sum()),
        "max_rgb_channel_delta_lsb": int(per.max()),
        "mean_abs_rgb_delta_lsb": float(delta.mean()),
        "changed_bbox_gt_1lsb_px": None if xs.size == 0 else [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
    }
    return metrics, gt1


def frame_map(directory: Path) -> dict[str, Path]:
    files = sorted(directory.glob("atmosphere-width-*.png"))
    assert len(files) == 68, f"expected 68 frames, got {len(files)} in {directory}"
    return {p.name: p for p in files}


def texture_metrics(recipe: dict, image_path: Path) -> dict:
    data = image_path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == recipe["expected_png_sha256"]
    image = Image.open(image_path).convert("RGBA")
    assert image.size == (512, 512)
    arr = np.asarray(image, dtype=np.int16)
    assert np.all(arr[:, :, 3] == 255)
    raw_sha = hashlib.sha256(arr.astype(np.uint8).tobytes()).hexdigest()
    assert raw_sha == recipe["expected_rgba8_sha256"]
    rgb = arr[:, :, :3]
    dx = np.abs(rgb[:, 1:] - rgb[:, :-1])
    dy = np.abs(rgb[1:] - rgb[:-1])
    means = rgb.mean(axis=(0, 1))
    mins = rgb.min(axis=(0, 1))
    maxs = rgb.max(axis=(0, 1))
    for mean, base in zip(means, recipe["base_srgb8"]):
        assert abs(float(mean) - float(base)) <= 1.0
    max_neighbor = int(max(dx.max(), dy.max()))
    assert max_neighbor <= 2
    return {
        "png_sha256": recipe["expected_png_sha256"],
        "rgba8_sha256": raw_sha,
        "mean_srgb8": [float(v) for v in means],
        "min_srgb8": [int(v) for v in mins],
        "max_srgb8": [int(v) for v in maxs],
        "max_neighbor_channel_delta_lsb": max_neighbor,
        "fully_opaque": True,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--successor-texture", type=Path, required=True)
    ap.add_argument("--scalar-runtime", type=Path, required=True)
    ap.add_argument("--checker-runtime", type=Path, required=True)
    ap.add_argument("--successor-runtime", type=Path, required=True)
    ap.add_argument("--scalar-rendered", type=Path, required=True)
    ap.add_argument("--checker-rendered", type=Path, required=True)
    ap.add_argument("--successor-rendered", type=Path, required=True)
    ap.add_argument("--materials-head", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    recipe = load(args.recipe)
    assert recipe["schema"] == "axm.building.utility-panel-production-surface/v0.1"
    assert recipe["technical_art_head"] == TA_HEAD
    assert recipe["environment_head"] == ENV_HEAD
    assert recipe["materials_predecessor_head"] == "0ae911792929eaa38b2c2f32239ebfdce8967251"
    assert recipe["art_direction"]["decision"] == "REQUEST_ONE_MATERIALS_OWNED_PRODUCTION_SURFACE_SUCCESSOR"
    assert recipe["holds"]["environment_adoption"] is False
    assert recipe["holds"]["art_direction_acceptance"] is False
    assert recipe["holds"]["visual_qa_acceptance"] is False

    tex = texture_metrics(recipe, args.successor_texture)
    scalar_runtime = load(args.scalar_runtime)
    checker_runtime = load(args.checker_runtime)
    successor_runtime = load(args.successor_runtime)

    assert successor_runtime.get("environment_building_utility_panel_material_current_world_state") == SUCCESSOR_STATE
    assert successor_runtime.get("environment_building_utility_panel_material_technical_art_head") == TA_HEAD
    assert successor_runtime.get("environment_building_utility_panel_material_materials_head") == args.materials_head
    assert successor_runtime.get("environment_building_utility_panel_material_png_sha256") == recipe["expected_png_sha256"]
    assert successor_runtime.get("environment_building_utility_panel_material_rgba8_sha256") == recipe["expected_rgba8_sha256"]
    assert successor_runtime.get("environment_building_utility_panel_material_environment_adoption") is False
    assert successor_runtime.get("environment_building_utility_panel_material_art_qa_acceptance") is False
    assert successor_runtime.get("environment_building_utility_panel_material_runtime_acceptance") is False

    canonical_scalar = canonical_runtime(scalar_runtime)
    assert canonical_scalar == canonical_runtime(checker_runtime), "checker changed unrelated current-world runtime identity"
    assert canonical_scalar == canonical_runtime(successor_runtime), "successor changed unrelated current-world runtime identity"

    scalar = frame_map(args.scalar_rendered)
    checker = frame_map(args.checker_rendered)
    successor = frame_map(args.successor_rendered)
    assert set(scalar) == set(checker) == set(successor)

    frames = []
    totals = {
        "scalar_to_checker_gt1": 0,
        "scalar_to_successor_gt1": 0,
        "checker_to_successor_gt1": 0,
    }
    successor_visible = 0
    checker_visible = 0
    min_exact_checker_mask_overlap = 1.0
    min_checker_bbox_localization = 1.0
    max_successor_delta = 0
    max_checker_delta = 0
    camera_phase_counts: dict[str, list[int]] = {"path_eye": [], "elevated_oblique": []}

    for name in sorted(scalar):
        a = image_array(scalar[name])
        b = image_array(checker[name])
        c = image_array(successor[name])
        m_ab, mask_ab = pair_metrics(a, b)
        m_ac, mask_ac = pair_metrics(a, c)
        m_bc, _ = pair_metrics(b, c)
        totals["scalar_to_checker_gt1"] += m_ab["changed_pixels_gt_1lsb"]
        totals["scalar_to_successor_gt1"] += m_ac["changed_pixels_gt_1lsb"]
        totals["checker_to_successor_gt1"] += m_bc["changed_pixels_gt_1lsb"]
        checker_visible += int(m_ab["changed_pixels_gt_1lsb"] > 0)
        successor_visible += int(m_ac["changed_pixels_gt_1lsb"] > 0)
        max_checker_delta = max(max_checker_delta, m_ab["max_rgb_channel_delta_lsb"])
        max_successor_delta = max(max_successor_delta, m_ac["max_rgb_channel_delta_lsb"])
        if mask_ac.any():
            exact_overlap = float(np.logical_and(mask_ac, mask_ab).sum() / mask_ac.sum())
            min_exact_checker_mask_overlap = min(min_exact_checker_mask_overlap, exact_overlap)
            checker_bbox = m_ab["changed_bbox_gt_1lsb_px"]
            assert checker_bbox is not None
            x0, y0, x1, y1 = checker_bbox
            # The checker delta itself is a sparse thresholded pattern, not a silhouette mask.
            # Use its already-proven projection bbox with one raster pixel of tolerance so a
            # lower-contrast successor is not falsely rejected for revealing edge samples that
            # happen to match the scalar control inside the checker pattern.
            h, w = mask_ac.shape
            x0 = max(0, x0 - 1)
            y0 = max(0, y0 - 1)
            x1 = min(w - 1, x1 + 1)
            y1 = min(h - 1, y1 + 1)
            projection_mask = np.zeros_like(mask_ac)
            projection_mask[y0 : y1 + 1, x0 : x1 + 1] = True
            bbox_localization = float(np.logical_and(mask_ac, projection_mask).sum() / mask_ac.sum())
            min_checker_bbox_localization = min(min_checker_bbox_localization, bbox_localization)
        else:
            exact_overlap = 1.0
            bbox_localization = 1.0
        camera = "path_eye" if "path_eye" in name else "elevated_oblique"
        camera_phase_counts[camera].append(m_ac["changed_pixels_gt_1lsb"])
        frames.append({
            "frame": name,
            "scalar_to_checker": m_ab,
            "scalar_to_successor": m_ac,
            "checker_to_successor": m_bc,
            "successor_diff_overlap_with_exact_checker_delta_mask": exact_overlap,
            "successor_diff_localization_within_checker_projection_bbox_plus_1px": bbox_localization,
        })

    assert checker_visible == 68, "historical checker control lost expected visibility"
    assert successor_visible == 68, "production successor is not visible in every retained current-world observation"
    assert totals["scalar_to_successor_gt1"] > 0
    assert totals["checker_to_successor_gt1"] > 0
    assert min_checker_bbox_localization >= 0.999, (
        "successor raster delta escaped checker projection bbox plus 1px tolerance: "
        f"{min_checker_bbox_localization}"
    )

    # The successor is intentionally broad/medium variation. This is not an aesthetic gate;
    # it only ensures we did not regenerate another high-contrast calibration pattern.
    assert max_successor_delta < max_checker_delta, (max_successor_delta, max_checker_delta)

    report = {
        "schema": "axm.building.utility-panel-production-surface-current-world-three-way-report/v0.1",
        "result": RESULT,
        "materials_head": args.materials_head,
        "technical_art_head": TA_HEAD,
        "environment_head": ENV_HEAD,
        "texture": tex,
        "review": {
            "rendered_frames_per_variant": 68,
            "variants": ["scalar_ochre_control", "checker_diagnostic", "production_surface_successor_001"],
            "unrelated_current_world_runtime_identity_equal": True,
            "successor_visible_frames": successor_visible,
            "checker_visible_frames": checker_visible,
            "minimum_successor_delta_overlap_with_exact_checker_delta_mask": min_exact_checker_mask_overlap,
            "minimum_successor_delta_localization_within_checker_projection_bbox_plus_1px": min_checker_bbox_localization,
            "total_changed_pixels_gt_1lsb": totals,
            "max_scalar_to_checker_channel_delta_lsb": max_checker_delta,
            "max_scalar_to_successor_channel_delta_lsb": max_successor_delta,
            "camera_successor_gt1_counts": camera_phase_counts,
            "aesthetic_acceptance": False,
        },
        "frames": frames,
        "truth_boundary": recipe["truth_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(RESULT)
    print(json.dumps(report["review"], sort_keys=True))


if __name__ == "__main__":
    main()
