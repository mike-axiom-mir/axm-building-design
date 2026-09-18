#!/usr/bin/env python3
"""Build bounded Geometry evidence for service-pavilion assembly interpenetration.

The current Hard-Surface source owns individually closed/outward box shells. This
Geometry lane leaves that source unchanged and derives one review candidate that
segments only the front/rear headers around the four exact vertical-post volume
overlaps. The candidate must preserve the exact occupied solid union while removing
all positive-volume pairwise AABB interpenetrations. Face contacts remain explicit
and are not relabelled as a boolean-unioned/global-manifold shell.
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
HARD_SURFACE_SOURCE_HEAD = "57f66b1245812f0c3d402232a046b86c0b5c72d8"
PREDECESSOR_GEOMETRY_HEAD = "407d3aaf36c26829a64d964143e34587df6d8ea1"
HEADER_IDS = ("front-header", "rear-header")
EPS = 1e-9

EXPECTED_SOURCE_OVERLAPS = [
    ("front-door-left", "front-header", (0.2, 0.18, 0.18), 0.00648),
    ("front-door-right", "front-header", (0.2, 0.18, 0.18), 0.00648),
    ("rear-left-mid", "rear-header", (0.2, 0.18, 0.18), 0.00648),
    ("rear-right-mid", "rear-header", (0.2, 0.18, 0.18), 0.00648),
]


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


def make_box_record(name, vertices, *, source_component_id=None, role="source"):
    lo, hi = bounds_from_vertices(vertices)
    return {
        "id": name,
        "source_component_id": source_component_id or name,
        "role": role,
        "vertices": [[q(x) for x in vertex] for vertex in vertices],
        "lo": list(lo),
        "hi": list(hi),
    }


def make_axis_box(base, name, lo, hi, *, source_component_id, role):
    center = [q((lo[axis] + hi[axis]) / 2.0) for axis in range(3)]
    size = [q(hi[axis] - lo[axis]) for axis in range(3)]
    if any(value <= EPS for value in size):
        raise AssertionError(f"{name}: non-positive segment size {size}")
    vertices = base.box_vertices(center, size)
    return make_box_record(
        name,
        vertices,
        source_component_id=source_component_id,
        role=role,
    )


def source_boxes(base):
    pavilion = base.load(base.PAVILION)
    panel = base.load(base.PANEL)
    contract = pavilion.get("generated_geometry_contract", {})
    if pavilion.get("schema") != "axm.building-hard-surface/v0.2":
        raise AssertionError("source schema drift")
    if pavilion.get("source_revision") != "service-pavilion-001/closed-outward-box-shells-002":
        raise AssertionError("source revision drift")
    if contract.get("box_shell_topology") != base.BOX_TOPOLOGY_REVISION:
        raise AssertionError("source topology contract drift")

    fits = [base.fit_panel(interface, panel) for interface in pavilion["interfaces"]]
    boxes = []
    for component in pavilion["components"]:
        vertices = base.box_vertices(component["center"], component["size"])
        base.require_closed_outward_box(vertices)
        boxes.append(make_box_record(component["id"], vertices))
    for interface, fit in zip(pavilion["interfaces"], fits):
        basis = (interface["normal"], interface["lateral"], interface["up"])
        vertices = base.box_vertices(
            fit["panel_center_local_m"],
            panel["proof_geometry"]["size_local_xyz_m"],
            basis,
        )
        base.require_closed_outward_box(vertices)
        boxes.append(make_box_record("panel-" + interface["id"], vertices, role="panel"))
    if len(boxes) != 19:
        raise AssertionError(f"expected 19 exact source boxes, got {len(boxes)}")
    return pavilion, panel, fits, boxes


def overlap_dims(a, b):
    return tuple(q(min(a["hi"][axis], b["hi"][axis]) - max(a["lo"][axis], b["lo"][axis])) for axis in range(3))


def positive_overlap_rows(boxes):
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


def face_contact_rows(boxes):
    rows = []
    for index, a in enumerate(boxes):
        for b in boxes[index + 1:]:
            dims = overlap_dims(a, b)
            zero_axes = [axis for axis, value in enumerate(dims) if abs(value) <= EPS]
            if len(zero_axes) == 1 and all(value >= -EPS for value in dims):
                area = math.prod(value for value in dims if value > EPS)
                if area > EPS:
                    rows.append({
                        "a": a["id"],
                        "b": b["id"],
                        "contact_size_m": [max(0.0, value) for value in dims],
                        "contact_area_m2": q12(area),
                    })
    return rows


def component_volume_sum(boxes):
    return q12(sum(math.prod(q(box["hi"][axis] - box["lo"][axis]) for axis in range(3)) for box in boxes))


def combined_bounds(boxes):
    return {
        "min": [q(min(box["lo"][axis] for box in boxes)) for axis in range(3)],
        "max": [q(max(box["hi"][axis] for box in boxes)) for axis in range(3)],
    }


def occupied(box, point):
    return all(box["lo"][axis] + EPS < point[axis] < box["hi"][axis] - EPS for axis in range(3))


def union_equivalence(source, candidate):
    axes = []
    for axis in range(3):
        axes.append(sorted({q(value) for box in source + candidate for value in (box["lo"][axis], box["hi"][axis])}))

    mismatch_cells = []
    source_volume = 0.0
    candidate_volume = 0.0
    compared_cells = 0
    for ix in range(len(axes[0]) - 1):
        dx = axes[0][ix + 1] - axes[0][ix]
        for iy in range(len(axes[1]) - 1):
            dy = axes[1][iy + 1] - axes[1][iy]
            for iz in range(len(axes[2]) - 1):
                dz = axes[2][iz + 1] - axes[2][iz]
                if dx <= EPS or dy <= EPS or dz <= EPS:
                    continue
                point = (
                    (axes[0][ix] + axes[0][ix + 1]) / 2.0,
                    (axes[1][iy] + axes[1][iy + 1]) / 2.0,
                    (axes[2][iz] + axes[2][iz + 1]) / 2.0,
                )
                s = any(occupied(box, point) for box in source)
                c = any(occupied(box, point) for box in candidate)
                cell_volume = dx * dy * dz
                source_volume += cell_volume if s else 0.0
                candidate_volume += cell_volume if c else 0.0
                compared_cells += 1
                if s != c and len(mismatch_cells) < 8:
                    mismatch_cells.append({
                        "midpoint_m": [q(value) for value in point],
                        "source_occupied": s,
                        "candidate_occupied": c,
                    })
    return {
        "equivalent": not mismatch_cells,
        "compared_cells": compared_cells,
        "source_union_volume_m3": q12(source_volume),
        "candidate_union_volume_m3": q12(candidate_volume),
        "volume_residual_m3": q12(candidate_volume - source_volume),
        "first_mismatch_cells": mismatch_cells,
    }


def expected_overlap_signature(rows):
    return [
        (row["a"], row["b"], tuple(row["overlap_size_m"]), row["overlap_volume_m3"])
        for row in rows
    ]


def derive_header_segments(base, source):
    overlaps = positive_overlap_rows(source)
    if expected_overlap_signature(overlaps) != EXPECTED_SOURCE_OVERLAPS:
        raise AssertionError(f"source positive-overlap signature drift: {overlaps}")

    by_id = {box["id"]: box for box in source}
    cut_ranges = {header: [] for header in HEADER_IDS}
    for row in overlaps:
        if row["b"] in HEADER_IDS:
            header_id, cutter_id = row["b"], row["a"]
        elif row["a"] in HEADER_IDS:
            header_id, cutter_id = row["a"], row["b"]
        else:
            raise AssertionError(f"non-header volumetric overlap is outside bounded candidate: {row}")
        header = by_id[header_id]
        cutter = by_id[cutter_id]
        cut_ranges[header_id].append((max(header["lo"][0], cutter["lo"][0]), min(header["hi"][0], cutter["hi"][0]), cutter_id))

    candidate = []
    segment_map = {}
    for box in source:
        if box["id"] not in HEADER_IDS:
            candidate.append(copy.deepcopy(box))
            continue
        cursor = box["lo"][0]
        segments = []
        cuts = sorted(cut_ranges[box["id"]])
        for cut_lo, cut_hi, cutter_id in cuts:
            if cut_lo <= cursor + EPS or cut_hi <= cut_lo + EPS:
                raise AssertionError(f"{box['id']}: invalid or overlapping cut interval")
            segment_id = f"{box['id']}::segment-{len(segments)}"
            segments.append(make_axis_box(
                base,
                segment_id,
                [cursor, box["lo"][1], box["lo"][2]],
                [cut_lo, box["hi"][1], box["hi"][2]],
                source_component_id=box["id"],
                role="geometry-header-segment",
            ))
            cursor = cut_hi
        if cursor >= box["hi"][0] - EPS:
            raise AssertionError(f"{box['id']}: cuts consumed full header")
        segment_id = f"{box['id']}::segment-{len(segments)}"
        segments.append(make_axis_box(
            base,
            segment_id,
            [cursor, box["lo"][1], box["lo"][2]],
            box["hi"],
            source_component_id=box["id"],
            role="geometry-header-segment",
        ))
        if len(segments) != 3:
            raise AssertionError(f"{box['id']}: expected 3 exact retained header segments, got {len(segments)}")
        segment_map[box["id"]] = [segment["id"] for segment in segments]
        candidate.extend(segments)
    return candidate, segment_map, overlaps


def obj_lines(base, boxes, header):
    lines = [header]
    offset = 0
    for box in boxes:
        offset = base.add_box_obj(lines, box["id"], box["vertices"], offset)
    return lines


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
        "per_object": rows,
    }


def mutate_box_x(base, box, lo_delta=0.0, hi_delta=0.0):
    changed = copy.deepcopy(box)
    lo = list(changed["lo"])
    hi = list(changed["hi"])
    lo[0] = q(lo[0] + lo_delta)
    hi[0] = q(hi[0] + hi_delta)
    return make_axis_box(
        base,
        changed["id"],
        lo,
        hi,
        source_component_id=changed["source_component_id"],
        role=changed["role"],
    )


def build_evidence(exact_head: str):
    base = load_module(ROOT / "tools" / "build_service_pavilion.py", "service_pavilion_current")
    pavilion, panel, fits, source = source_boxes(base)
    candidate, segment_map, source_overlaps = derive_header_segments(base, source)

    candidate_overlaps = positive_overlap_rows(candidate)
    if candidate_overlaps:
        raise AssertionError(f"candidate retains positive-volume interpenetration: {candidate_overlaps}")

    equivalence = union_equivalence(source, candidate)
    if not equivalence["equivalent"] or abs(equivalence["volume_residual_m3"]) > EPS:
        raise AssertionError(f"candidate changed occupied solid union: {equivalence}")
    if combined_bounds(source) != combined_bounds(candidate):
        raise AssertionError("candidate changed assembled proof bounds")

    source_component_volume = component_volume_sum(source)
    candidate_component_volume = component_volume_sum(candidate)
    removed_double_coverage = q12(source_component_volume - candidate_component_volume)
    overlap_total = q12(sum(row["overlap_volume_m3"] for row in source_overlaps))
    if abs(removed_double_coverage - overlap_total) > EPS:
        raise AssertionError("header segmentation did not remove exactly the source double-covered volume")
    if abs(candidate_component_volume - equivalence["candidate_union_volume_m3"]) > EPS:
        raise AssertionError("candidate component volumes still contain positive-volume double coverage")

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
    for key, value in expected_topology.items():
        if topo[key] != value:
            raise AssertionError(f"unexpected candidate box-topology aggregate {key}: {topo[key]} != {value}")

    source_contacts = face_contact_rows(source)
    candidate_contacts = face_contact_rows(candidate)

    overlap_bad = copy.deepcopy(candidate)
    index = next(i for i, box in enumerate(overlap_bad) if box["id"] == "front-header::segment-0")
    overlap_bad[index] = mutate_box_x(base, overlap_bad[index], hi_delta=0.001)
    overlap_negative = positive_overlap_rows(overlap_bad)
    if not overlap_negative:
        raise AssertionError("1 mm overlap negative control unexpectedly remained interpenetration-free")

    gap_bad = copy.deepcopy(candidate)
    index = next(i for i, box in enumerate(gap_bad) if box["id"] == "front-header::segment-1")
    gap_bad[index] = mutate_box_x(base, gap_bad[index], lo_delta=0.001)
    gap_negative = union_equivalence(source, gap_bad)
    if gap_negative["equivalent"]:
        raise AssertionError("1 mm gap negative control unexpectedly preserved exact solid union")

    _p, _pa, _fits, source_obj, mins, maxs, path_gap, inherited_negatives, source_topology = base.build()
    if source_topology["object_count"] != 19 or source_topology["outward_triangle_count"] != 228:
        raise AssertionError("inherited source-owned box-topology gate drift")

    receipt = {
        "schema": "axm.building-interpenetration-free-header-segmentation/v0.1",
        "result": "PASS_EXACT_UNION_HEADER_SEGMENTATION_REMOVES_ALL_POSITIVE_VOLUME_INTERPENETRATIONS",
        "exact_geometry_head": exact_head,
        "hard_surface_source_head": HARD_SURFACE_SOURCE_HEAD,
        "predecessor_geometry_head": PREDECESSOR_GEOMETRY_HEAD,
        "pavilion_source_sha256": sha256(base.PAVILION),
        "panel_source_sha256": sha256(base.PANEL),
        "source_revision": pavilion["source_revision"],
        "source_topology_revision": pavilion["generated_geometry_contract"]["box_shell_topology"],
        "source_box_count": len(source),
        "candidate_box_count": len(candidate),
        "header_segment_map": segment_map,
        "source_positive_volume_intersections": source_overlaps,
        "source_positive_volume_intersection_count": len(source_overlaps),
        "source_positive_overlap_volume_m3": overlap_total,
        "candidate_positive_volume_intersections": candidate_overlaps,
        "candidate_positive_volume_intersection_count": len(candidate_overlaps),
        "source_component_volume_sum_m3": source_component_volume,
        "candidate_component_volume_sum_m3": candidate_component_volume,
        "removed_double_covered_volume_m3": removed_double_coverage,
        "union_equivalence": equivalence,
        "combined_bounds_source": combined_bounds(source),
        "combined_bounds_candidate": combined_bounds(candidate),
        "source_face_contact_count": len(source_contacts),
        "candidate_face_contact_count": len(candidate_contacts),
        "source_face_contact_area_sum_m2": q12(sum(row["contact_area_m2"] for row in source_contacts)),
        "candidate_face_contact_area_sum_m2": q12(sum(row["contact_area_m2"] for row in candidate_contacts)),
        "candidate_box_topology": topo,
        "inherited_source_topology": source_topology,
        "receiver_fits": fits,
        "combined_bounds_from_source_builder": {"min": mins, "max": maxs},
        "readable_path_gap_m": path_gap,
        "inherited_negative_controls": inherited_negatives,
        "negative_controls": {
            "front_header_segment_overlap_plus_0p001m": {
                "accepted": False,
                "positive_volume_intersections": overlap_negative,
            },
            "front_header_segment_gap_plus_0p001m": {
                "accepted": False,
                "union_equivalence": gap_negative,
            },
        },
        "cost_delta": {
            "box_objects": len(candidate) - len(source),
            "vertices": topo["vertex_count"] - 152,
            "triangles": topo["triangle_count"] - 228,
            "note": "representation cost only; no runtime/draw-call claim",
        },
        "truth_boundary": {
            "proved": [
                "exact current Hard-Surface source identity is consumed without source-file edits",
                "the exact source has four bounded positive-volume header/post intersections totaling 0.02592 m^3",
                "front/rear header segmentation removes all positive-volume pairwise box intersections",
                "candidate and source occupy the exact same axis-aligned solid union over the combined coordinate partition",
                "assembled bounds, receiver fits and readable-path gap remain unchanged",
                "every retained candidate box remains a source-topology closed/outward 12-triangle shell",
            ],
            "not_proved": [
                "source adoption or semantic approval of segmented headers",
                "boolean-unioned/global vertex-manifold pavilion topology",
                "removal of coplanar internal faces at face contacts",
                "self-intersection freedom for arbitrary non-box geometry",
                "final normals, tangents, smoothing or UVs",
                "visual/material acceptance",
                "runtime, draw-call, memory or target-device performance",
                "collision, navigation or gameplay suitability",
                "CANON, production/game readiness, or Geometry mastery",
            ],
        },
    }
    candidate_obj = obj_lines(
        base,
        candidate,
        "# AXM Geometry derived service-pavilion-001 interpenetration-free header segmentation candidate",
    )
    return receipt, source_obj, candidate_obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", default="evidence/service-pavilion-interpenetration-001")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    receipt, source_obj, candidate_obj = build_evidence(args.exact_head)
    (out / "source-control.obj").write_text("\n".join(source_obj) + "\n", encoding="utf-8")
    (out / "header-segmented-candidate.obj").write_text("\n".join(candidate_obj) + "\n", encoding="utf-8")
    (out / "interpenetration-evidence.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    (out / "hard-surface-source-head.txt").write_text(HARD_SURFACE_SOURCE_HEAD + "\n", encoding="utf-8")
    (out / "predecessor-geometry-head.txt").write_text(PREDECESSOR_GEOMETRY_HEAD + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
