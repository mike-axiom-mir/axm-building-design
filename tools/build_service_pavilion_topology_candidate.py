#!/usr/bin/env python3
"""Build bounded Geometry evidence for the service-pavilion box topology.

This deliberately leaves the Hard-Surface source/builder unchanged. It compares the
exact historical box face table with one derived closed/outward-oriented face table
on the exact same vertices, components and receiver-panel placements.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARD_SURFACE_DONOR_HEAD = "4faa769b406bf3ad0ba9489a77141c27f122ce51"
UC_DONOR_HEAD = "dde8d952161788f8bf21118f91edd3163e51277d"

HISTORICAL_FACES = (
    (1, 2, 4), (2, 4, 3),
    (5, 6, 8), (6, 8, 7),
    (1, 2, 6), (1, 6, 5),
    (3, 4, 8), (3, 8, 7),
    (1, 3, 7), (1, 7, 5),
    (2, 4, 8), (2, 8, 6),
)

# Same 8 box vertices and same 12-triangle budget; only face membership/winding is
# corrected so every rectangular shell is one closed, consistently outward surface.
CANDIDATE_FACES = (
    (1, 4, 3), (1, 2, 4),
    (5, 7, 8), (5, 8, 6),
    (1, 5, 6), (1, 6, 2),
    (3, 4, 8), (3, 8, 7),
    (1, 3, 7), (1, 7, 5),
    (2, 6, 8), (2, 8, 4),
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def mean_point(points):
    return tuple(sum(p[axis] for p in points) / len(points) for axis in range(3))


def local_edge_metrics(faces):
    edges = defaultdict(list)
    for face_index, face in enumerate(faces):
        a, b, c = (index - 1 for index in face)
        for start, end in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((start, end)))
            direction = 1 if (start, end) == key else -1
            edges[key].append((face_index, direction))
    boundary = sum(len(incidents) == 1 for incidents in edges.values())
    nonmanifold = sum(len(incidents) > 2 for incidents in edges.values())
    orientation = sum(
        len(incidents) == 2 and incidents[0][1] == incidents[1][1]
        for incidents in edges.values()
    )
    return {
        "edge_count": len(edges),
        "boundary_edge_count": boundary,
        "nonmanifold_edge_count": nonmanifold,
        "orientation_conflict_edge_count": orientation,
    }


def outward_counts(vertices, faces):
    center = mean_point(vertices)
    outward = inward = tangent = 0
    for face in faces:
        a, b, c = (vertices[index - 1] for index in face)
        normal = cross(sub(b, a), sub(c, a))
        face_center = mean_point((a, b, c))
        signed = dot(normal, sub(face_center, center))
        if signed > 1e-12:
            outward += 1
        elif signed < -1e-12:
            inward += 1
        else:
            tangent += 1
    return {"outward": outward, "inward": inward, "tangent": tangent}


def flat_indices(faces):
    return [index - 1 for face in faces for index in face]


def build_objects(base):
    pavilion = base.load(base.PAVILION)
    panel = base.load(base.PANEL)
    fits = [base.fit_panel(interface, panel) for interface in pavilion["interfaces"]]
    objects = []
    for component in pavilion["components"]:
        vertices = base.box_vertices(component["center"], component["size"])
        objects.append({"name": component["id"], "vertices": vertices})
    for interface, fit in zip(pavilion["interfaces"], fits):
        basis = (interface["normal"], interface["lateral"], interface["up"])
        handedness = dot(cross(basis[0], basis[1]), basis[2])
        if handedness <= 0.0:
            raise AssertionError(f"{interface['id']}: receiver frame is not right-handed")
        vertices = base.box_vertices(
            fit["panel_center_local_m"],
            panel["proof_geometry"]["size_local_xyz_m"],
            basis,
        )
        objects.append({"name": "panel-" + interface["id"], "vertices": vertices})
    return pavilion, panel, fits, objects


def obj_lines(objects, faces, header):
    lines = [header]
    offset = 0
    for item in objects:
        lines.append(f"o {item['name']}")
        for vertex in item["vertices"]:
            lines.append("v %.9f %.9f %.9f" % tuple(vertex))
        for face in faces:
            lines.append("f %d %d %d" % tuple(offset + index for index in face))
        offset += len(item["vertices"])
    return lines


def vertex_lines(lines):
    return [line for line in lines if line.startswith("v ")]


def object_names(lines):
    return [line[2:] for line in lines if line.startswith("o ")]


def build_evidence(uc_root: Path, exact_head: str):
    base = load_module(ROOT / "tools" / "build_service_pavilion.py", "service_pavilion_base")
    if tuple(tuple(face) for face in base.FACES) != HISTORICAL_FACES:
        raise AssertionError("Hard-Surface face table drifted from exact donor contract")

    topology = load_module(uc_root / "src" / "axm_uc" / "mesh_topology.py", "uc_mesh_topology")
    pavilion, panel, fits, objects = build_objects(base)
    _p, _pa, _fits, control_obj, mins, maxs, path_gap, negatives = base.build()
    candidate_obj = obj_lines(
        objects,
        CANDIDATE_FACES,
        "# AXM Geometry derived service-pavilion-001 closed box topology candidate",
    )

    if vertex_lines(control_obj) != vertex_lines(candidate_obj):
        raise AssertionError("candidate changed vertex positions/order")
    if object_names(control_obj) != object_names(candidate_obj):
        raise AssertionError("candidate changed object/component identity")

    per_object = []
    for item in objects:
        vertices = item["vertices"]
        historical = topology.inspect_mesh_topology(vertices, flat_indices(HISTORICAL_FACES))
        candidate = topology.inspect_mesh_topology(vertices, flat_indices(CANDIDATE_FACES))
        historical_outward = outward_counts(vertices, HISTORICAL_FACES)
        candidate_outward = outward_counts(vertices, CANDIDATE_FACES)

        historical_expected = (
            historical["status"] == "INVALID_EDGE_TOPOLOGY"
            and historical["boundary_edge_count"] == 6
            and historical["nonmanifold_edge_count"] == 2
            and historical["orientation_conflict_edge_count"] == 4
            and historical_outward == {"outward": 6, "inward": 6, "tangent": 0}
        )
        candidate_expected = (
            candidate["status"] == "CLOSED_ORIENTED_EDGE_MANIFOLD_CANDIDATE"
            and candidate["boundary_edge_count"] == 0
            and candidate["nonmanifold_edge_count"] == 0
            and candidate["orientation_conflict_edge_count"] == 0
            and candidate["collapsed_triangle_count"] == 0
            and candidate["triangle_component_count"] == 1
            and candidate_outward == {"outward": 12, "inward": 0, "tangent": 0}
        )
        if not historical_expected:
            raise AssertionError(f"{item['name']}: historical topology no longer matches bounded defect")
        if not candidate_expected:
            raise AssertionError(f"{item['name']}: candidate did not close/orient the box shell")

        per_object.append({
            "object": item["name"],
            "vertex_positions_identical": True,
            "historical_topology": historical,
            "historical_orientation": historical_outward,
            "candidate_topology": candidate,
            "candidate_orientation": candidate_outward,
        })

    flipped = list(CANDIDATE_FACES)
    a, b, c = flipped[0]
    flipped[0] = (a, c, b)
    negative = topology.inspect_mesh_topology(objects[0]["vertices"], flat_indices(flipped))
    if negative["status"] == "CLOSED_ORIENTED_EDGE_MANIFOLD_CANDIDATE":
        raise AssertionError("single-triangle winding negative control unexpectedly passed")

    aggregate = {
        "object_count": len(objects),
        "vertex_count": sum(len(item["vertices"]) for item in objects),
        "triangle_count": len(objects) * len(CANDIDATE_FACES),
        "historical_boundary_edges": sum(row["historical_topology"]["boundary_edge_count"] for row in per_object),
        "historical_nonmanifold_edges": sum(row["historical_topology"]["nonmanifold_edge_count"] for row in per_object),
        "historical_orientation_conflicts": sum(row["historical_topology"]["orientation_conflict_edge_count"] for row in per_object),
        "candidate_boundary_edges": sum(row["candidate_topology"]["boundary_edge_count"] for row in per_object),
        "candidate_nonmanifold_edges": sum(row["candidate_topology"]["nonmanifold_edge_count"] for row in per_object),
        "candidate_orientation_conflicts": sum(row["candidate_topology"]["orientation_conflict_edge_count"] for row in per_object),
        "historical_outward_triangles": sum(row["historical_orientation"]["outward"] for row in per_object),
        "historical_inward_triangles": sum(row["historical_orientation"]["inward"] for row in per_object),
        "candidate_outward_triangles": sum(row["candidate_orientation"]["outward"] for row in per_object),
        "candidate_inward_triangles": sum(row["candidate_orientation"]["inward"] for row in per_object),
    }
    if aggregate != {
        "object_count": 19,
        "vertex_count": 152,
        "triangle_count": 228,
        "historical_boundary_edges": 114,
        "historical_nonmanifold_edges": 38,
        "historical_orientation_conflicts": 76,
        "candidate_boundary_edges": 0,
        "candidate_nonmanifold_edges": 0,
        "candidate_orientation_conflicts": 0,
        "historical_outward_triangles": 114,
        "historical_inward_triangles": 114,
        "candidate_outward_triangles": 228,
        "candidate_inward_triangles": 0,
    }:
        raise AssertionError(f"unexpected aggregate topology signature: {aggregate}")

    receipt = {
        "schema": "axm.building-box-topology-candidate-evidence/v0.1",
        "result": "PASS_DERIVED_CLOSED_OUTWARD_BOX_TOPOLOGY_19_REAL_COMPONENTS",
        "exact_geometry_head": exact_head,
        "hard_surface_donor_head": HARD_SURFACE_DONOR_HEAD,
        "uc_topology_donor_head": UC_DONOR_HEAD,
        "pavilion_source_sha256": sha256(base.PAVILION),
        "panel_source_sha256": sha256(base.PANEL),
        "source_builder_unchanged_from_donor_required_by_workflow": True,
        "vertex_positions_and_order_unchanged": True,
        "object_identity_and_order_unchanged": True,
        "combined_bounds_local_m": {"min": mins, "max": maxs},
        "readable_path_gap_m": path_gap,
        "receiver_fits": fits,
        "inherited_negative_controls": negatives,
        "historical_face_metrics_local": local_edge_metrics(HISTORICAL_FACES),
        "candidate_face_metrics_local": local_edge_metrics(CANDIDATE_FACES),
        "aggregate": aggregate,
        "negative_control_single_triangle_flip": {
            "status": negative["status"],
            "boundary_edge_count": negative["boundary_edge_count"],
            "nonmanifold_edge_count": negative["nonmanifold_edge_count"],
            "orientation_conflict_edge_count": negative["orientation_conflict_edge_count"],
            "accepted": False,
        },
        "per_object": per_object,
        "truth_boundary": {
            "proved": [
                "same exact source vertices and component identity",
                "19 derived box shells are closed by edge incidence",
                "19 derived box shells have consistent shared-edge winding",
                "all 228 candidate triangles face outward relative to their own box centers",
                "historical malformed face table is retained as before-evidence",
            ],
            "not_proved": [
                "source migration/adoption",
                "global pavilion union/boolean topology",
                "removal of hidden/interpenetrating internal faces between components",
                "vertex-manifoldness",
                "self-intersection freedom",
                "final normals/tangents/smoothing",
                "UV readiness beyond this bounded shell structure",
                "materials or final visual quality",
                "architectural or manufacturing validity",
                "collision/navigation/gameplay",
                "runtime or target-device performance",
                "CANON, production/game readiness, or Geometry mastery",
            ],
        },
    }
    return receipt, control_obj, candidate_obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", default="evidence/service-pavilion-box-topology-001")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    receipt, control_obj, candidate_obj = build_evidence(Path(args.uc_root), args.exact_head)
    (out / "historical-control.obj").write_text("\n".join(control_obj) + "\n", encoding="utf-8")
    (out / "closed-outward-candidate.obj").write_text("\n".join(candidate_obj) + "\n", encoding="utf-8")
    (out / "topology-evidence.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    (out / "hard-surface-donor-head.txt").write_text(HARD_SURFACE_DONOR_HEAD + "\n", encoding="utf-8")
    (out / "uc-donor-head.txt").write_text(UC_DONOR_HEAD + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
