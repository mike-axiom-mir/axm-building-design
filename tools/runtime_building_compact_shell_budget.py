#!/usr/bin/env python3
"""Bounded Runtime characterization for the source-owned Building compact shell v2.

This lane does not adopt the compact shell. It compares the exact Hard-Surface-owned
reference and compact receiving representations, converts each to the same explicit
hard-edge render domain (position + face normal + u32 index), and verifies real Godot
proof-host receipts plus fixed-view image deltas.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT_HEAD = "35d0ba62d7e534b3cd00ac69e99386843ffa3f2e"
REFERENCE_TOOL = ROOT / "tools" / "build_service_pavilion_union_shell_candidate.py"
COMPACT_TOOL = ROOT / "tools" / "build_service_pavilion_boundary_shell_compaction_v2.py"
SCHEMA = "axm.runtime-building-compact-shell-budget/v0.1"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def q(value: float) -> float:
    return round(float(value), 9)


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def face_normal(vertices, triangle):
    a, b, c = (vertices[index] for index in triangle)
    n = cross(vec_sub(b, a), vec_sub(c, a))
    length = math.sqrt(sum(component * component for component in n))
    if length <= 1e-12:
        raise ValueError("degenerate triangle in render-domain conversion")
    return tuple(q(component / length) for component in n)


def render_domain(mesh: dict) -> dict:
    """Deduplicate only identical final position+face-normal tuples.

    This preserves hard edges. It does not merge across different face normals and does
    not infer UV/tangent/material equivalence that the source does not yet prove.
    """
    vertices = mesh["vertices"]
    triangles = mesh["triangles"]
    unique = {}
    render_vertices = []
    render_normals = []
    indices = []
    for triangle in triangles:
        normal = face_normal(vertices, triangle)
        for source_index in triangle:
            position = tuple(q(value) for value in vertices[source_index])
            key = (position, normal)
            render_index = unique.get(key)
            if render_index is None:
                render_index = len(render_vertices)
                unique[key] = render_index
                render_vertices.append(list(position))
                render_normals.append(list(normal))
            indices.append(render_index)
    return {
        "vertices": render_vertices,
        "normals": render_normals,
        "indices": indices,
        "stored_vertex_count": len(render_vertices),
        "index_count": len(indices),
        "triangle_count": len(triangles),
        "surface_count": 1,
        "modeled_payload_bytes": len(render_vertices) * 24 + len(indices) * 4,
        "payload_model": "POSITION_FLOAT32x3_PLUS_NORMAL_FLOAT32x3_PLUS_UINT32_INDEX__ONE_SURFACE",
    }


def bounds(vertices):
    return {
        "min": [min(float(v[axis]) for v in vertices) for axis in range(3)],
        "max": [max(float(v[axis]) for v in vertices) for axis in range(3)],
    }


def canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(exact_head: str, output: Path):
    donor = load_module(REFERENCE_TOOL, "runtime_building_reference_shell")
    reference, reference_evidence = donor.build_evidence(exact_head)
    compact_mod = load_module(COMPACT_TOOL, "runtime_building_compact_shell_v2")
    compact, compact_evidence = compact_mod.build_evidence(exact_head)

    if reference_evidence.get("result") != "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE":
        raise ValueError("reference shell prerequisite is not PASS")
    if compact_evidence.get("result") != "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_COLLINEAR_CHAIN_V2":
        raise ValueError("compact v2 prerequisite is not PASS")
    if (len(reference["vertices"]), len(reference["triangles"])) != (1420, 2884):
        raise ValueError("reference identity/count drift")
    if (len(compact["vertices"]), len(compact["triangles"])) != (1004, 2052):
        raise ValueError("compact v2 identity/count drift")

    control = render_domain(reference)
    candidate = render_domain(compact)
    if candidate["triangle_count"] >= control["triangle_count"]:
        raise ValueError("compact render domain did not reduce triangle count")
    if candidate["stored_vertex_count"] >= control["stored_vertex_count"]:
        raise ValueError("compact render domain did not reduce stored vertices")
    if candidate["modeled_payload_bytes"] >= control["modeled_payload_bytes"]:
        raise ValueError("compact render domain did not reduce modeled payload")

    payload = {
        "schema": SCHEMA,
        "exact_runtime_head": exact_head,
        "hard_surface_parent_head": PARENT_HEAD,
        "reference_geometry_result": reference_evidence["result"],
        "compact_geometry_result": compact_evidence["result"],
        "reference_logical": {"vertex_count": len(reference["vertices"]), "triangle_count": len(reference["triangles"])},
        "compact_logical": {"vertex_count": len(compact["vertices"]), "triangle_count": len(compact["triangles"])},
        "bounds": bounds(reference["vertices"]),
        "control": control,
        "candidate": candidate,
        "modeled_payload_bytes_saved": control["modeled_payload_bytes"] - candidate["modeled_payload_bytes"],
        "modeled_payload_reduction_percent": q(100.0 * (control["modeled_payload_bytes"] - candidate["modeled_payload_bytes"]) / control["modeled_payload_bytes"]),
        "truth_boundary": "Runtime compares the exact Hard-Surface-owned reference shell with compact v2 under one neutral single-surface explicit hard-edge render domain. It does not transfer Materials/Art/Environment acceptance, choose a production receiver, claim target-device performance, or generalize this planar compaction to arbitrary meshes.",
    }
    payload["payload_sha256"] = canonical_sha(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("reference_logical", "compact_logical", "modeled_payload_bytes_saved", "modeled_payload_reduction_percent", "payload_sha256")}, indent=2))


def image_delta(control_path: Path, candidate_path: Path) -> dict:
    from PIL import Image, ImageChops
    with Image.open(control_path).convert("RGB") as a, Image.open(candidate_path).convert("RGB") as b:
        if a.size != b.size:
            raise ValueError(f"image-size drift: {a.size} vs {b.size}")
        diff = ImageChops.difference(a, b)
        bbox = diff.getbbox()
        changed = 0
        max_channel = 0
        if bbox is not None:
            for pixel in diff.getdata():
                local = max(pixel)
                if local:
                    changed += 1
                    max_channel = max(max_channel, local)
        return {
            "size": list(a.size),
            "byte_identical": bbox is None,
            "changed_pixels": changed,
            "changed_fraction": q(changed / float(a.size[0] * a.size[1])),
            "max_channel_delta_lsb": max_channel,
            "bbox": list(bbox) if bbox is not None else None,
        }


def verify(payload_path: Path, control_receipt: Path, candidate_receipt: Path, control_images: Path, candidate_images: Path, output: Path):
    payload = json.loads(payload_path.read_text())
    control = json.loads(control_receipt.read_text())
    candidate = json.loads(candidate_receipt.read_text())
    if payload.get("schema") != SCHEMA:
        raise ValueError("payload schema drift")
    if control.get("mode") != "REFERENCE_CONTROL" or candidate.get("mode") != "COMPACT_V2_CANDIDATE":
        raise ValueError("runtime mode drift")
    if control.get("exact_runtime_head") != payload["exact_runtime_head"] or candidate.get("exact_runtime_head") != payload["exact_runtime_head"]:
        raise ValueError("runtime head binding drift")
    if control["mesh"] != {k: payload["control"][k] for k in ("stored_vertex_count", "index_count", "triangle_count", "surface_count", "modeled_payload_bytes")}:
        raise ValueError("control mesh receipt drift")
    if candidate["mesh"] != {k: payload["candidate"][k] for k in ("stored_vertex_count", "index_count", "triangle_count", "surface_count", "modeled_payload_bytes")}:
        raise ValueError("candidate mesh receipt drift")

    control_rows = {row["camera"]: row for row in control["cameras"]}
    candidate_rows = {row["camera"]: row for row in candidate["cameras"]}
    if set(control_rows) != {"front_oblique", "rear_oblique"} or set(candidate_rows) != set(control_rows):
        raise ValueError("camera receipt drift")
    counter_deltas = {}
    for name in sorted(control_rows):
        cr, ca = control_rows[name], candidate_rows[name]
        delta = {key: int(ca[key]) - int(cr[key]) for key in ("draw_calls", "objects", "primitives", "buffer_memory", "texture_memory")}
        if delta["draw_calls"] != 0 or delta["objects"] != 0:
            raise ValueError(f"submission/object count drift in {name}: {delta}")
        if delta["primitives"] >= 0:
            raise ValueError(f"primitive count did not reduce in {name}: {delta}")
        counter_deltas[name] = delta

    visuals = {}
    for name in sorted(control_rows):
        visuals[name] = image_delta(control_images / f"{name}.png", candidate_images / f"{name}.png")
    byte_identical = sum(1 for row in visuals.values() if row["byte_identical"])
    max_pixels = max(row["changed_pixels"] for row in visuals.values())
    max_channel = max(row["max_channel_delta_lsb"] for row in visuals.values())
    visual_tradeoff = (
        "NONE_OBSERVED__TWO_FIXED_VIEWS_BYTE_IDENTICAL"
        if byte_identical == len(visuals)
        else f"MEASURED_RETRIANGULATION_RENDER_DELTA__ART_REVIEW_REQUIRED__MAX_CHANGED_PIXELS_{max_pixels}__MAX_CHANNEL_DELTA_{max_channel}_LSB"
    )

    report = {
        "schema": SCHEMA,
        "state": "PASS_BUILDING_COMPACT_SHELL_RUNTIME_REPRESENTATION_COST_CHARACTERIZED__HOLD_VISUAL_AND_RECEIVER_ADOPTION",
        "exact_runtime_head": payload["exact_runtime_head"],
        "hard_surface_parent_head": PARENT_HEAD,
        "logical_geometry": {"control": payload["reference_logical"], "candidate": payload["compact_logical"]},
        "render_domain": {
            "control": {k: payload["control"][k] for k in ("stored_vertex_count", "index_count", "triangle_count", "surface_count", "modeled_payload_bytes")},
            "candidate": {k: payload["candidate"][k] for k in ("stored_vertex_count", "index_count", "triangle_count", "surface_count", "modeled_payload_bytes")},
            "modeled_payload_bytes_saved": payload["modeled_payload_bytes_saved"],
            "modeled_payload_reduction_percent": payload["modeled_payload_reduction_percent"],
        },
        "proof_host_counter_deltas": counter_deltas,
        "visual_delta": visuals,
        "byte_identical_view_count": byte_identical,
        "visual_tradeoff": visual_tradeoff,
        "decision": "COMPACT_V2_HAS_REAL_RENDER_DOMAIN_AND_PRIMITIVE_COST_REDUCTION__ADOPTION_REMAINS_WITH_MATERIALS_ART_ENVIRONMENT_AND_TECHNICAL_ART",
        "truth_boundary": payload["truth_boundary"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    build_p = sub.add_parser("build")
    build_p.add_argument("--exact-head", required=True)
    build_p.add_argument("--output", type=Path, required=True)
    verify_p = sub.add_parser("verify")
    verify_p.add_argument("--payload", type=Path, required=True)
    verify_p.add_argument("--control-receipt", type=Path, required=True)
    verify_p.add_argument("--candidate-receipt", type=Path, required=True)
    verify_p.add_argument("--control-images", type=Path, required=True)
    verify_p.add_argument("--candidate-images", type=Path, required=True)
    verify_p.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.command == "build":
        build(args.exact_head, args.output)
    else:
        verify(args.payload, args.control_receipt, args.candidate_receipt, args.control_images, args.candidate_images, args.output)


if __name__ == "__main__":
    main()
