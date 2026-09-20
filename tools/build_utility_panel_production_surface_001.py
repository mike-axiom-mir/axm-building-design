from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

W = H = 512
Q = 65536
TA_HEAD = "1434bc4a64faa04db10f47723c37ab7925aaa163"
OLD_MATERIALS_HEAD = "0ae911792929eaa38b2c2f32239ebfdce8967251"
OLD_PNG_SHA = "e932cdd94d370184c7361862d5064149cc193e3a8fd80b269cab6543c0919198"
OLD_RGBA_SHA = "02f8f464eabc734a3be687a7706edf8b8f62ece834fa981c8c993fbb8227bb4b"
OLD_STATE = "PASS_CURRENT_WORLD_BUILDING_UTILITY_PANEL_MATERIAL_BOUND_RECEIVER__A_B_REVIEW_ONLY__ADOPTION_HELD"
OLD_RULE = "OWNER_BOUND_UV_IMAGE_TRANSPORT_MAY_ENTER_THE_REAL_WORLD_ONLY_AS_AN_EXPLICIT_A_B_RECEIVER_SUCCESSOR_WITH_UNRELATED_WORLD_IDENTITIES_AND_ROLLBACK_HELD"
NEW_STATE = "PASS_CURRENT_WORLD_BUILDING_UTILITY_PANEL_PRODUCTION_SURFACE_SUCCESSOR__MATERIALS_REVIEW_ONLY__ADOPTION_HELD"
NEW_RULE = "PRODUCTION_INTENT_SURFACE_SUCCESSOR_MUST_REUSE_PROVEN_TRANSPORT_WITH_WORLD_GEOMETRY_CAMERA_LIGHTING_AND_ROLLBACK_IDENTITIES_HELD"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def mix32(x: int) -> int:
    x &= 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7FEB352D) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846CA68B) & 0xFFFFFFFF
    x ^= x >> 16
    return x & 0xFFFFFFFF


def cell_value(ix: int, iy: int, seed: int) -> int:
    h = mix32((ix * 0x1F123BB5) ^ (iy * 0x5F356495) ^ seed)
    return int((h & 0xFFFF) * 2048 // 65535) - 1024


def smooth_q16(frac: int, cell: int) -> int:
    t = max(0, min(Q, (frac * Q) // cell))
    t2 = (t * t) // Q
    return (t2 * (3 * Q - 2 * t)) // Q


def lerp_q16(a: int, b: int, t: int) -> int:
    return a + ((b - a) * t) // Q


def value_noise(x: int, y: int, cell: int, seed: int, ox: int, oy: int) -> int:
    xx, yy = x + ox, y + oy
    ix, iy = xx // cell, yy // cell
    fx, fy = xx % cell, yy % cell
    sx, sy = smooth_q16(fx, cell), smooth_q16(fy, cell)
    a = lerp_q16(cell_value(ix, iy, seed), cell_value(ix + 1, iy, seed), sx)
    b = lerp_q16(cell_value(ix, iy + 1, seed), cell_value(ix + 1, iy + 1, seed), sx)
    return lerp_q16(a, b, sy)


def png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def generate(recipe: dict) -> tuple[bytes, bytes, dict]:
    assert recipe["schema"] == "axm.building.utility-panel-production-surface/v0.1"
    assert recipe["dimensions_px"] == [512, 512]
    assert recipe["alpha_policy"] == "fully_opaque_255"
    base = tuple(int(v) for v in recipe["base_srgb8"])
    seed = int(recipe["generator"]["seed"])
    octaves = recipe["generator"]["octaves"]
    assert [(o["cell_px"], o["amplitude_lsb"]) for o in octaves] == [(128, 6), (64, 3), (32, 1)]
    chroma = recipe["generator"]["chroma_field"]

    fields: list[int] = []
    chroms: list[int] = []
    for y in range(H):
        for x in range(W):
            total = 0
            for octave in octaves:
                total += value_noise(
                    x,
                    y,
                    int(octave["cell_px"]),
                    seed + int(octave["seed_offset"]),
                    int(octave["offset_px"][0]),
                    int(octave["offset_px"][1]),
                ) * int(octave["amplitude_lsb"])
            fields.append(total // 1024)
            chroms.append(
                value_noise(
                    x,
                    y,
                    int(chroma["cell_px"]),
                    seed + int(chroma["seed_offset"]),
                    int(chroma["offset_px"][0]),
                    int(chroma["offset_px"][1]),
                )
            )

    field_mean = round(sum(fields) / len(fields))
    chroma_mean = round(sum(chroms) / len(chroms))
    raw_rows = bytearray()
    rgba = bytearray()
    sums = [0, 0, 0]
    mins = [255, 255, 255]
    maxs = [0, 0, 0]
    max_neighbor_channel_delta = 0
    previous_row: list[tuple[int, int, int]] | None = None
    cursor = 0
    for y in range(H):
        raw_rows.append(0)
        row_rgb: list[tuple[int, int, int]] = []
        for x in range(W):
            field = max(-9, min(9, fields[cursor] - field_mean))
            chrom = chroms[cursor] - chroma_mean
            cursor += 1
            rgb = (
                max(0, min(255, base[0] + field + chrom // 2048)),
                max(0, min(255, base[1] + (field * 7) // 8)),
                max(0, min(255, base[2] + (field * 5) // 8 - chrom // 3072)),
            )
            if row_rgb:
                max_neighbor_channel_delta = max(
                    max_neighbor_channel_delta,
                    max(abs(rgb[i] - row_rgb[-1][i]) for i in range(3)),
                )
            if previous_row is not None:
                max_neighbor_channel_delta = max(
                    max_neighbor_channel_delta,
                    max(abs(rgb[i] - previous_row[x][i]) for i in range(3)),
                )
            row_rgb.append(rgb)
            for i, value in enumerate(rgb):
                sums[i] += value
                mins[i] = min(mins[i], value)
                maxs[i] = max(maxs[i], value)
            raw_rows.extend((*rgb, 255))
            rgba.extend((*rgb, 255))
        previous_row = row_rgb

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(bytes(raw_rows), 9))
    png += png_chunk(b"IEND", b"")
    count = W * H
    stats = {
        "dimensions_px": [W, H],
        "mean_srgb8": [v / count for v in sums],
        "min_srgb8": mins,
        "max_srgb8": maxs,
        "max_neighbor_channel_delta_lsb": max_neighbor_channel_delta,
        "alpha_min": 255,
        "alpha_max": 255,
        "serialized_png_bytes": len(png),
        "png_sha256": hashlib.sha256(png).hexdigest(),
        "rgba8_sha256": hashlib.sha256(bytes(rgba)).hexdigest(),
    }
    return png, bytes(rgba), stats


def exact_replace(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"expected exactly one donor occurrence, got {count}: {old[:80]!r}")
    return text.replace(old, new, 1)


def compose_observer(donor: Path, output: Path, current_head: str, recipe: dict) -> None:
    text = donor.read_text()
    text = exact_replace(
        text,
        'const MATERIAL_IMAGE_PATH := "res://generated/utility-panel-review-checker-512.png"',
        'const MATERIAL_IMAGE_PATH := "res://generated/utility-panel-production-surface-001.png"',
    )
    text = exact_replace(text, f'const MATERIAL_STATE := "{OLD_STATE}"', f'const MATERIAL_STATE := "{NEW_STATE}"')
    text = exact_replace(text, f'const MATERIAL_RULE := "{OLD_RULE}"', f'const MATERIAL_RULE := "{NEW_RULE}"')
    text = exact_replace(
        text,
        f'const EXPECTED_MATERIALS_HEAD := "{OLD_MATERIALS_HEAD}"',
        f'const EXPECTED_MATERIALS_HEAD := "{current_head}"',
    )
    text = exact_replace(
        text,
        f'const EXPECTED_PNG_SHA := "{OLD_PNG_SHA}"',
        f'const EXPECTED_PNG_SHA := "{recipe["expected_png_sha256"]}"',
    )
    text = exact_replace(
        text,
        f'const EXPECTED_RGBA_SHA := "{OLD_RGBA_SHA}"',
        f'const EXPECTED_RGBA_SHA := "{recipe["expected_rgba8_sha256"]}"',
    )
    text = exact_replace(
        text,
        '"material_albedo_source":"EXACT_MATERIALS_SERIALIZED_REVIEW_TEXTURE"',
        '"material_albedo_source":"MATERIALS_PRODUCTION_SURFACE_SUCCESSOR_001"',
    )
    text = exact_replace(
        text,
        'receipt["environment_building_utility_panel_material_truth_boundary"]="Exact Technical Art current-receiver UV/image binding consumed into the existing 184v/276t/5-surface Building receiver for real-world A/B review only. Only the utility-panel material surface receives the exact Materials review PNG and TA UV0 mapping; receiver-local fill remains explicitly non-source. Building geometry/placement, Object articulation, Nature, Weather, Environment dressing, cameras and lights remain inherited. No automatic Environment, Art/QA, Runtime/device, CANON or production adoption."',
        'receipt["environment_building_utility_panel_material_truth_boundary"]="Exact Technical Art current-receiver UV mapping reused with the Materials-owned production-surface successor PNG inside the existing 184v/276t/5-surface Building receiver for same-world three-way review only. The historical checker remains a separate diagnostic control. Building geometry/placement, Object articulation, Nature, Weather, Environment dressing, cameras and lights remain inherited. No automatic Environment, Art/QA, Runtime/device, CANON or production adoption."',
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)


def receiver_contract(recipe: dict, current_head: str) -> dict:
    return {
        "schema": "axm.environment-building-utility-panel-material-current-world-ab/v0.1",
        "reusable_rule": NEW_RULE,
        "technical_art": {"head": TA_HEAD},
        "materials": {
            "head": current_head,
            "retained_png_sha256": recipe["expected_png_sha256"],
            "retained_rgba8_sha256": recipe["expected_rgba8_sha256"],
            "surface_id": recipe["surface_id"],
        },
        "environment": {
            "head": recipe["environment_head"],
            "object_motion_sample_index": 40,
            "review_variants": ["scalar_ochre_control", "checker_diagnostic", "production_surface_successor_001"],
        },
        "promotion": {
            "environment_adoption": False,
            "art_qa_acceptance": False,
            "runtime_acceptance": False,
            "canon": False,
        },
        "truth_boundary": recipe["truth_boundary"],
    }


def command_generate(args: argparse.Namespace) -> None:
    recipe = load(args.recipe)
    png, rgba, stats = generate(recipe)
    assert stats["png_sha256"] == recipe["expected_png_sha256"]
    assert stats["rgba8_sha256"] == recipe["expected_rgba8_sha256"]
    assert stats["alpha_min"] == stats["alpha_max"] == 255
    assert stats["max_neighbor_channel_delta_lsb"] <= 2
    for mean, base in zip(stats["mean_srgb8"], recipe["base_srgb8"]):
        assert abs(mean - base) <= 1.0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(png)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"schema": "axm.building.utility-panel-production-surface-generation-report/v0.1", "surface_id": recipe["surface_id"], "stats": stats, "truth_boundary": recipe["truth_boundary"]}, indent=2, sort_keys=True) + "\n")
    print("PASS_UTILITY_PANEL_PRODUCTION_SURFACE_001_GENERATION")
    print(json.dumps(stats, sort_keys=True))


def command_compose(args: argparse.Namespace) -> None:
    recipe = load(args.recipe)
    compose_observer(args.donor_observer, args.output_observer, args.materials_head, recipe)
    contract = receiver_contract(recipe, args.materials_head)
    args.output_contract.parent.mkdir(parents=True, exist_ok=True)
    args.output_contract.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    print("PASS_UTILITY_PANEL_PRODUCTION_SURFACE_001_OBSERVER_COMPOSITION")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--recipe", type=Path, required=True)
    gen.add_argument("--output", type=Path, required=True)
    gen.add_argument("--report", type=Path)
    gen.set_defaults(func=command_generate)
    comp = sub.add_parser("compose-observer")
    comp.add_argument("--recipe", type=Path, required=True)
    comp.add_argument("--donor-observer", type=Path, required=True)
    comp.add_argument("--output-observer", type=Path, required=True)
    comp.add_argument("--output-contract", type=Path, required=True)
    comp.add_argument("--materials-head", required=True)
    comp.set_defaults(func=command_compose)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
