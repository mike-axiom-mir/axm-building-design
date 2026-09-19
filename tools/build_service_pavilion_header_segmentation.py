#!/usr/bin/env python3
"""Build retained Hard-Surface evidence for the source-owned header segmentation overlay.

The historical v0.2 pavilion source/builder remains reproducible. This module owns only
one explicit successor emission contract: split the two long X headers around the four
source-owned vertical-post volumes, while preserving the exact occupied solid union,
logical component semantics, receiver fits and closed/outward per-box topology.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "assets" / "service_pavilion_001_header_segmentation.json"
BASE_HEAD = "595217be3cb9de25d3dc48b19447654533a20599"
GEOMETRY_HEAD = "aaa987397c33f0dc9579a2ac3785ca00a5bc7402"
EPS = 1e-9
EXPECTED_SOURCE_OVERLAPS = {
    ("front-door-left", "front-header", 0.00648),
    ("front-door-right", "front-header", 0.00648),
    ("rear-left-mid", "rear-header", 0.00648),
    ("rear-right-mid", "rear-header", 0.00648),
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def q(value: float) -> float:
    return round(float(value), 9)


def q12(value: float) -> float:
    return round(float(value), 12)


def bounds_from_vertices(vertices):
    return (
        tuple(q(min(v[axis] for v in vertices)) for axis in range(3)),
        tuple(q(max(v[axis] for v in vertices)) for axis in range(3)),
    )


def record(name, vertices, *, source_component_id=None, role="source"):
    lo, hi = bounds_from_vertices(vertices)
    return {
        "id": name,
        "source_component_id": source_component_id or name,
        "role": role,
        "vertices": [[q(x) for x in vertex] for vertex in vertices],
        "lo": list(lo),
        "hi": list(hi),
    }


def axis_box(base, name, lo, hi, *, source_component_id, role):
    center = [q((lo[i] + hi[i]) / 2.0) for i in range(3)]
    size = [q(hi[i] - lo[i]) for i in range(3)]
    if any(value <= EPS for value in size):
        raise ValueError(f"{name}: non-positive box size {size}")
    return record(
        name,
        base.box_vertices(center, size),
        source_component_id=source_component_id,
        role=role,
    )


def overlap_dims(a, b):
    return tuple(q(min(a["hi"][i], b["hi"][i]) - max(a["lo"][i], b["lo"][i])) for i in range(3))


def positive_overlaps(boxes):
    rows = []
    for index, a in enumerate(boxes):
        for b in boxes[index + 1:]:
            dims = overlap_dims(a, b)
            if all(value > EPS for value in dims):
                rows.append({
                    "a": a["id"],
                    "b": b["id"],
                    "overlap_size_m": list(dims),
                    "overlap_volume_m3": q12(math.prod(dims)),
                })
    return rows


def component_volume_sum(boxes):
    return q12(sum(math.prod(box["hi"][i] - box["lo"][i] for i in range(3)) for box in boxes))


def combined_bounds(boxes):
    return {
        "min": [q(min(box["lo"][i] for box in boxes)) for i in range(3)],
        "max": [q(max(box["hi"][i] for box in boxes)) for i in range(3)],
    }


def occupied(box, point):
    return all(box["lo"][i] + EPS < point[i] < box["hi"][i] - EPS for i in range(3))


def union_equivalence(source, candidate):
    axes = [
        sorted({q(value) for box in source + candidate for value in (box["lo"][axis], box["hi"][axis])})
        for axis in range(3)
    ]
    mismatches = []
    source_volume = 0.0
    candidate_volume = 0.0
    compared_cells = 0
    for ix in range(len(axes[0]) - 1):
        for iy in range(len(axes[1]) - 1):
            for iz in range(len(axes[2]) - 1):
                lo = (axes[0][ix], axes[1][iy], axes[2][iz])
                hi = (axes[0][ix + 1], axes[1][iy + 1], axes[2][iz + 1])
                dims = tuple(hi[i] - lo[i] for i in range(3))
                if any(value <= EPS for value in dims):
                    continue
                point = tuple((lo[i] + hi[i]) / 2.0 for i in range(3))
                source_hit = any(occupied(box, point) for box in source)
                candidate_hit = any(occupied(box, point) for box in candidate)
                volume = math.prod(dims)
                if source_hit:
                    source_volume += volume
                if candidate_hit:
                    candidate_volume += volume
                compared_cells += 1
                if source_hit != candidate_hit and len(mismatches) < 8:
                    mismatches.append({
                        "midpoint_m": [q(v) for v in point],
                        "source_occupied": source_hit,
                        "candidate_occupied": candidate_hit,
                    })
    return {
        "equivalent": not mismatches,
        "compared_cells": compared_cells,
        "source_union_volume_m3": q12(source_volume),
        "candidate_union_volume_m3": q12(candidate_volume),
        "volume_residual_m3": q12(candidate_volume - source_volume),
        "first_mismatch_cells": mismatches,
    }


def source_boxes(base, pavilion, panel, fits):
    boxes = []
    for component in pavilion["components"]:
        vertices = base.box_vertices(component["center"], component["size"])
        base.require_closed_outward_box(vertices)
        boxes.append(record(component["id"], vertices))
    for interface, fit in zip(pavilion["interfaces"], fits):
        vertices = base.box_vertices(
            fit["panel_center_local_m"],
            panel["proof_geometry"]["size_local_xyz_m"],
            (interface["normal"], interface["lateral"], interface["up"]),
        )
        base.require_closed_outward_box(vertices)
        boxes.append(record("panel-" + interface["id"], vertices, role="panel"))
    if len(boxes) != 19:
        raise ValueError(f"expected 19 exact logical source boxes, got {len(boxes)}")
    return boxes


def emitted_boxes(base, pavilion, panel, fits, contract):
    segmented = contract["segmented_components"]
    if set(segmented) != {"front-header", "rear-header"}:
        raise ValueError("segmentation scope drift")
    boxes = []
    segment_map = {}
    for component in pavilion["components"]:
        if component["id"] not in segmented:
            vertices = base.box_vertices(component["center"], component["size"])
            boxes.append(record(component["id"], vertices))
            continue
        rows = segmented[component["id"]]
        if len(rows) != 3:
            raise ValueError(f"{component['id']}: expected exactly three source-owned segments")
        segment_map[component["id"]] = []
        for row in rows:
            vertices = base.box_vertices(row["center"], row["size"])
            boxes.append(record(
                row["id"],
                vertices,
                source_component_id=component["id"],
                role="source-owned-header-segment",
            ))
            segment_map[component["id"]].append(row["id"])
    for interface, fit in zip(pavilion["interfaces"], fits):
        vertices = base.box_vertices(
            fit["panel_center_local_m"],
            panel["proof_geometry"]["size_local_xyz_m"],
            (interface["normal"], interface["lateral"], interface["up"]),
        )
        boxes.append(record("panel-" + interface["id"], vertices, role="panel"))
    if len(boxes) != 23:
        raise ValueError(f"expected 23 exact emitted boxes, got {len(boxes)}")
    return boxes, segment_map


def topology_summary(base, boxes):
    rows = []
    for box in boxes:
        metrics = base.require_closed_outward_box(box["vertices"])
        rows.append({"object": box["id"], **metrics})
    return {
        "object_count": len(rows),
        "vertex_count": len(rows) * 8,
        "triangle_count": len(rows) * 12,
        "boundary_edge_count": sum(row["boundary_edge_count"] for row in rows),
        "nonmanifold_edge_count": sum(row["nonmanifold_edge_count"] for row in rows),
        "orientation_conflict_edge_count": sum(row["orientation_conflict_edge_count"] for row in rows),
        "degenerate_triangle_count": sum(row["degenerate_triangle_count"] for row in rows),
        "outward_triangle_count": sum(row["outward_triangle_count"] for row in rows),
        "inward_triangle_count": sum(row["inward_triangle_count"] for row in rows),
    }


def mutated_x(base, box, hi_delta):
    lo = list(box["lo"])
    hi = list(box["hi"])
    hi[0] = q(hi[0] + hi_delta)
    return axis_box(
        base,
        box["id"],
        lo,
        hi,
        source_component_id=box["source_component_id"],
        role=box["role"],
    )


def build(exact_head="LOCAL_UNBOUND"):
    base = load_module(ROOT / "tools" / "build_service_pavilion.py", "service_pavilion_base")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    pavilion = base.load(base.PAVILION)
    panel = base.load(base.PANEL)

    if contract.get("schema") != "axm.building-header-segmentation/v0.1":
        raise ValueError("header segmentation schema drift")
    if contract.get("owner") != "Building Hard Surface":
        raise ValueError("header segmentation ownership drift")
    if contract["provenance"].get("base_hard_surface_head") != BASE_HEAD:
        raise ValueError("base Hard-Surface head drift")
    if contract["provenance"].get("geometry_candidate_head") != GEOMETRY_HEAD:
        raise ValueError("Geometry evidence head drift")
    if pavilion.get("source_revision") != contract["provenance"].get("base_source_revision"):
        raise ValueError("base source revision drift")
    if sha256(base.PAVILION) != contract["provenance"].get("base_source_sha256"):
        raise ValueError("base source bytes drift")

    fits = [base.fit_panel(interface, panel) for interface in pavilion["interfaces"]]
    source = source_boxes(base, pavilion, panel, fits)
    candidate, segment_map = emitted_boxes(base, pavilion, panel, fits, contract)

    source_overlaps = positive_overlaps(source)
    signature = {
        (row["a"], row["b"], row["overlap_volume_m3"])
        for row in source_overlaps
    }
    if signature != EXPECTED_SOURCE_OVERLAPS:
        raise ValueError(f"base source overlap signature drift: {source_overlaps}")

    candidate_overlaps = positive_overlaps(candidate)
    if candidate_overlaps:
        raise ValueError(f"source-owned successor retains positive-volume interpenetrations: {candidate_overlaps}")

    equivalence = union_equivalence(source, candidate)
    if not equivalence["equivalent"] or abs(equivalence["volume_residual_m3"]) > EPS:
        raise ValueError(f"source-owned successor changed occupied union: {equivalence}")
    if combined_bounds(source) != combined_bounds(candidate):
        raise ValueError("source-owned successor changed assembled bounds")

    source_component_volume = component_volume_sum(source)
    candidate_component_volume = component_volume_sum(candidate)
    removed_double_coverage = q12(source_component_volume - candidate_component_volume)
    overlap_total = q12(sum(row["overlap_volume_m3"] for row in source_overlaps))
    if abs(removed_double_coverage - overlap_total) > EPS:
        raise ValueError("successor did not remove exactly the known double-covered volume")
    if abs(candidate_component_volume - equivalence["candidate_union_volume_m3"]) > EPS:
        raise ValueError("successor emitted boxes still contain positive-volume double coverage")

    topo = topology_summary(base, candidate)
    expected_topology = {
        "object_count": 23,
        "vertex_count": 184,
        "triangle_count": 276,
        "boundary_edge_count": 0,
        "nonmanifold_edge_count": 0,
        "orientation_conflict_edge_count": 0,
        "degenerate_triangle_count": 0,
        "outward_triangle_count": 276,
        "inward_triangle_count": 0,
    }
    for key, expected in expected_topology.items():
        if topo[key] != expected:
            raise ValueError(f"unexpected successor topology {key}: {topo[key]} != {expected}")

    # Fail closed: +1 mm into the adjacent post reintroduces a volume intersection.
    overlap_control = copy.deepcopy(candidate)
    index = next(i for i, box in enumerate(overlap_control) if box["id"] == "front-header::segment-0")
    overlap_control[index] = mutated_x(base, overlap_control[index], +0.001)
    overlap_rows = positive_overlaps(overlap_control)
    if not overlap_rows:
        raise ValueError("+1 mm overlap negative control unexpectedly retained zero intersections")

    # Fail closed: -1 mm leaves an uncovered sliver, changing the exact occupied union.
    gap_control = copy.deepcopy(candidate)
    index = next(i for i, box in enumerate(gap_control) if box["id"] == "front-header::segment-0")
    gap_control[index] = mutated_x(base, gap_control[index], -0.001)
    gap_equivalence = union_equivalence(source, gap_control)
    if gap_equivalence["equivalent"]:
        raise ValueError("-1 mm gap negative control unexpectedly preserved occupied union")

    result = {
        "result": "PASS_SOURCE_OWNED_INTERPENETRATION_FREE_HEADER_SEGMENTATION_OVERLAY",
        "exact_hard_surface_head": exact_head,
        "successor_revision": contract["successor_revision"],
        "base_hard_surface_head": BASE_HEAD,
        "geometry_candidate_head": GEOMETRY_HEAD,
        "base_source_sha256": sha256(base.PAVILION),
        "segmentation_contract_sha256": sha256(CONTRACT_PATH),
        "logical_component_count": len(pavilion["components"]),
        "logical_source_box_count_with_panels": len(source),
        "emitted_successor_box_count_with_panels": len(candidate),
        "segment_map": segment_map,
        "source_positive_volume_intersection_count": len(source_overlaps),
        "source_positive_double_covered_volume_m3": overlap_total,
        "successor_positive_volume_intersection_count": len(candidate_overlaps),
        "source_component_volume_sum_m3": source_component_volume,
        "successor_component_volume_sum_m3": candidate_component_volume,
        "occupied_union": equivalence,
        "bounds": combined_bounds(candidate),
        "receiver_ids": [fit["interface_id"] for fit in fits],
        "receiver_mount_residual_max_m": max(fit["mount_pattern_residual_m"] for fit in fits),
        "topology": topo,
        "negative_controls": {
            "plus_1mm_header_overlap": {
                "result": "REJECTED_POSITIVE_VOLUME_INTERSECTION",
                "intersection_count": len(overlap_rows),
            },
            "minus_1mm_header_gap": {
                "result": "REJECTED_OCCUPIED_UNION_CHANGE",
                "volume_residual_m3": gap_equivalence["volume_residual_m3"],
                "first_mismatch_cells": gap_equivalence["first_mismatch_cells"],
            },
        },
        "truth_boundary": contract["truth_boundary"],
        "non_claims": [
            "replacement or deletion of the historical v0.2 builder/source",
            "boolean-unioned or global vertex-manifold pavilion shell",
            "removal of coplanar internal faces at face-contact seams",
            "architectural, structural, sealing or manufacturing validity",
            "final normals, tangents, UVs, materials or visual acceptance",
            "runtime import, collision, navigation, gameplay or target-device performance",
            "automatic downstream consumer migration",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness, or Hard-Surface mastery",
        ],
    }
    return base, candidate, result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="evidence/service-pavilion-001/header-segmentation-003")
    ap.add_argument("--exact-head", default="LOCAL_UNBOUND")
    args = ap.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    base, candidate, receipt = build(args.exact_head)
    obj = ["# AXM service-pavilion-001 source-owned header segmentation successor"]
    offset = 0
    for box in candidate:
        offset = base.add_box_obj(obj, box["id"], box["vertices"], offset)
    obj_path = out / "service-pavilion-001-header-segmentation-003.obj"
    obj_path.write_text("\n".join(obj) + "\n", encoding="utf-8")
    receipt["obj_sha256"] = sha256(obj_path)

    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    (out / "base-hard-surface-head.txt").write_text(BASE_HEAD + "\n", encoding="utf-8")
    (out / "geometry-candidate-head.txt").write_text(GEOMETRY_HEAD + "\n", encoding="utf-8")
    (out / "segmentation-contract.json").write_text(CONTRACT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
