#!/usr/bin/env python3
"""Compact the source-owned Building boundary shell without changing its surface.

This Geometry lane consumes the exact boundary-only reference shell and removes only
interior coplanar partition edges/vertices inside source-owner planar patches. Every
patch keeps its exact outer indexed boundary chain, so neighbouring perpendicular
patches remain conforming and no T-junction is introduced by simplification.

The 23 named source boxes remain semantic authority. This is a derived receiving-mesh
candidate only; it is not a runtime, material, collision, or source-adoption claim.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DONOR_TOOL = ROOT / "tools" / "build_service_pavilion_union_shell_candidate.py"
EPS = 1e-9


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def q(value: float) -> float:
    return round(float(value), 9)


def q12(value: float) -> float:
    return round(float(value), 12)


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def triangle_area(vertices, triangle) -> float:
    a, b, c = (vertices[index] for index in triangle)
    return 0.5 * norm(cross(vec_sub(b, a), vec_sub(c, a)))


def edge_key(a: int, b: int):
    return (a, b) if a < b else (b, a)


def triangle_components(triangle_indices, triangles):
    """Return face-connected components inside one coplanar owner-plane group."""
    edge_to_triangles = collections.defaultdict(list)
    for triangle_index in triangle_indices:
        a, b, c = triangles[triangle_index]
        for start, end in ((a, b), (b, c), (c, a)):
            edge_to_triangles[edge_key(start, end)].append(triangle_index)

    adjacency = collections.defaultdict(set)
    for rows in edge_to_triangles.values():
        if len(rows) == 2:
            a, b = rows
            adjacency[a].add(b)
            adjacency[b].add(a)

    remaining = set(triangle_indices)
    components = []
    while remaining:
        seed = min(remaining)
        stack = [seed]
        remaining.remove(seed)
        component = []
        while stack:
            current = stack.pop()
            component.append(current)
            for other in adjacency.get(current, ()):
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
        components.append(sorted(component))
    return components


def boundary_loops(component_triangles, triangles):
    """Trace undirected boundary loops while retaining every original boundary vertex."""
    edge_counts = collections.Counter()
    for triangle_index in component_triangles:
        a, b, c = triangles[triangle_index]
        for start, end in ((a, b), (b, c), (c, a)):
            edge_counts[edge_key(start, end)] += 1

    boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
    if not boundary_edges:
        return []

    adjacency = collections.defaultdict(set)
    for a, b in boundary_edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    if any(len(neighbours) != 2 for neighbours in adjacency.values()):
        return []

    unused = set(boundary_edges)
    loops = []
    while unused:
        first_edge = min(unused)
        start = first_edge[0]
        previous = None
        current = start
        loop = []
        while True:
            loop.append(current)
            candidates = sorted(adjacency[current])
            if previous is None:
                nxt = candidates[0]
            else:
                nxt = candidates[0] if candidates[0] != previous else candidates[1]
            edge = edge_key(current, nxt)
            if edge not in unused:
                if nxt == start:
                    break
                return []
            unused.remove(edge)
            previous, current = current, nxt
            if current == start:
                break
            if len(loop) > len(boundary_edges) + 1:
                return []
        if len(loop) < 3:
            return []
        loops.append(loop)
    return loops


def project_point(point, axis: int):
    other = [index for index in range(3) if index != axis]
    return (point[other[0]], point[other[1]])


def cross2(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def polygon_signed_area(points) -> float:
    total = 0.0
    for index, point in enumerate(points):
        other = points[(index + 1) % len(points)]
        total += point[0] * other[1] - other[0] * point[1]
    return 0.5 * total


def strictly_inside_triangle(point, a, b, c, orientation: float) -> bool:
    ca = cross2(a, b, point)
    cb = cross2(b, c, point)
    cc = cross2(c, a, point)
    if orientation > 0:
        return ca > EPS and cb > EPS and cc > EPS
    return ca < -EPS and cb < -EPS and cc < -EPS


def orient_triangle(vertices, triangle, axis: int, sign: int):
    a, b, c = (vertices[index] for index in triangle)
    normal = cross(vec_sub(b, a), vec_sub(c, a))
    if abs(normal[axis]) <= EPS:
        raise ValueError("compaction emitted a degenerate/off-plane triangle")
    if normal[axis] * sign < 0:
        return (triangle[0], triangle[2], triangle[1])
    return triangle


def triangulate_simple_loop(loop, vertices, axis: int, sign: int):
    """Ear-clip a simple planar loop while preserving all loop vertices."""
    points = [project_point(vertices[index], axis) for index in loop]
    signed_area = polygon_signed_area(points)
    if abs(signed_area) <= EPS:
        raise ValueError("zero-area planar boundary loop")
    orientation = 1.0 if signed_area > 0 else -1.0

    working = list(loop)
    output = []
    safety = 0
    while len(working) > 3:
        found = False
        for offset in range(len(working)):
            previous = working[(offset - 1) % len(working)]
            current = working[offset]
            following = working[(offset + 1) % len(working)]
            pa = project_point(vertices[previous], axis)
            pb = project_point(vertices[current], axis)
            pc = project_point(vertices[following], axis)
            turn = cross2(pa, pb, pc)
            if turn * orientation <= EPS:
                continue
            blocked = False
            for other in working:
                if other in (previous, current, following):
                    continue
                po = project_point(vertices[other], axis)
                if strictly_inside_triangle(po, pa, pb, pc, orientation):
                    blocked = True
                    break
            if blocked:
                continue
            output.append(orient_triangle(vertices, (previous, current, following), axis, sign))
            del working[offset]
            found = True
            break
        safety += 1
        if not found or safety > len(loop) * len(loop):
            raise ValueError("ear clipping stalled on planar patch")

    output.append(orient_triangle(vertices, tuple(working), axis, sign))
    if len(output) != len(loop) - 2:
        raise ValueError("unexpected planar triangulation cardinality")
    return output


def derive_compacted_shell(donor_shell: dict):
    vertices = donor_shell["vertices"]
    triangles = donor_shell["triangles"]
    owners = donor_shell["triangle_owners"]

    triangle_patch_key = {}
    for quad in donor_shell["boundary_quads"]:
        triangle_index = quad["triangle_indices"][0]
        triangle = triangles[triangle_index]
        plane = q(vertices[triangle[0]][quad["axis"]])
        key = (
            quad["solid_component"],
            quad["source_component_id"],
            quad["role"],
            quad["axis"],
            quad["sign"],
            plane,
        )
        for index in quad["triangle_indices"]:
            triangle_patch_key[index] = key

    if len(triangle_patch_key) != len(triangles):
        raise ValueError("donor triangle-to-planar-patch coverage drift")

    grouped = collections.defaultdict(list)
    for triangle_index, key in triangle_patch_key.items():
        grouped[key].append(triangle_index)

    candidate_triangles = []
    candidate_owners = []
    patch_audit = []
    compacted_patch_count = 0
    preserved_patch_count = 0
    max_patch_area_residual = 0.0

    for key in sorted(grouped):
        solid_component, source_component_id, role, axis, sign, plane = key
        for component_index, component in enumerate(triangle_components(grouped[key], triangles)):
            original_area = sum(triangle_area(vertices, triangles[index]) for index in component)
            original_box_ids = sorted({owners[index]["box_id"] for index in component})
            loops = boundary_loops(component, triangles)
            replacement = None
            reason = None
            if len(loops) == 1:
                try:
                    candidate = triangulate_simple_loop(loops[0], vertices, axis, sign)
                    candidate_area = sum(triangle_area(vertices, triangle) for triangle in candidate)
                    residual = abs(candidate_area - original_area)
                    max_patch_area_residual = max(max_patch_area_residual, residual)
                    if residual > EPS:
                        reason = f"area_residual={residual}"
                    elif len(candidate) >= len(component):
                        reason = "no_triangle_reduction"
                    else:
                        replacement = candidate
                except ValueError as exc:
                    reason = str(exc)
            else:
                reason = f"boundary_loop_count={len(loops)}"

            if replacement is None:
                replacement = [triangles[index] for index in component]
                owner_rows = [copy.deepcopy(owners[index]) for index in component]
                preserved_patch_count += 1
                status = "PRESERVED_EXACT_DONOR_PATCH"
            else:
                owner_row = {
                    "box_id": original_box_ids[0] if len(original_box_ids) == 1 else None,
                    "source_box_ids": original_box_ids,
                    "source_component_id": source_component_id,
                    "role": role,
                    "solid_component": solid_component,
                }
                owner_rows = [copy.deepcopy(owner_row) for _ in replacement]
                compacted_patch_count += 1
                status = "RETRIANGULATED_CONFORMING_PLANAR_PATCH"

            first_output = len(candidate_triangles)
            candidate_triangles.extend(replacement)
            candidate_owners.extend(owner_rows)
            replacement_area = sum(triangle_area(vertices, triangle) for triangle in replacement)
            residual = abs(replacement_area - original_area)
            max_patch_area_residual = max(max_patch_area_residual, residual)
            patch_audit.append({
                "patch_id": f"{source_component_id}:{solid_component}:{axis}:{sign}:{plane}:{component_index}",
                "source_component_id": source_component_id,
                "role": role,
                "solid_component": solid_component,
                "axis": axis,
                "sign": sign,
                "plane": plane,
                "source_box_ids": original_box_ids,
                "status": status,
                "fallback_reason": reason,
                "boundary_loop_count": len(loops),
                "boundary_vertex_count": len(loops[0]) if len(loops) == 1 else None,
                "donor_triangle_count": len(component),
                "candidate_triangle_count": len(replacement),
                "donor_area_m2": q12(original_area),
                "candidate_area_m2": q12(replacement_area),
                "area_residual_m2": q12(residual),
                "candidate_triangle_range": [first_output, len(candidate_triangles)],
            })

    used_source_vertex_ids = sorted({index for triangle in candidate_triangles for index in triangle})
    remap = {source_index: compact_index for compact_index, source_index in enumerate(used_source_vertex_ids)}
    compact_vertices = [vertices[index] for index in used_source_vertex_ids]
    compact_triangles = [tuple(remap[index] for index in triangle) for triangle in candidate_triangles]

    return {
        "vertices": compact_vertices,
        "triangles": compact_triangles,
        "triangle_owners": candidate_owners,
        "source_vertex_ids": used_source_vertex_ids,
        "patch_audit": patch_audit,
        "compacted_patch_count": compacted_patch_count,
        "preserved_patch_count": preserved_patch_count,
        "max_patch_area_residual_m2": q12(max_patch_area_residual),
    }


def owner_areas(vertices, triangles, owners):
    values = collections.defaultdict(float)
    for triangle, owner in zip(triangles, owners):
        values[owner["source_component_id"]] += triangle_area(vertices, triangle)
    return {key: q12(value) for key, value in sorted(values.items())}


def validate_candidate(donor_module, donor_result: dict, donor_shell: dict, candidate: dict) -> dict:
    vertices = candidate["vertices"]
    triangles = candidate["triangles"]
    owners = candidate["triangle_owners"]
    if len(triangles) != len(owners):
        raise ValueError("candidate triangle ownership cardinality drift")
    if len(candidate["source_vertex_ids"]) != len(vertices):
        raise ValueError("candidate source-vertex provenance cardinality drift")
    if len(set(candidate["source_vertex_ids"])) != len(candidate["source_vertex_ids"]):
        raise ValueError("candidate source-vertex provenance is not one-to-one")
    if any(donor_shell["vertices"][source_id] != vertex for source_id, vertex in zip(candidate["source_vertex_ids"], vertices)):
        raise ValueError("candidate moved a donor boundary vertex")
    if any(not owner.get("source_component_id") for owner in owners):
        raise ValueError("candidate triangle lost source-component provenance")

    topology = donor_module.inspect_topology(vertices, triangles)
    donor_topology = donor_result["candidate"]
    source = donor_result["source"]
    if topology["vertex_count"] >= donor_topology["vertex_count"]:
        raise ValueError("candidate did not reduce boundary vertex count")
    if topology["triangle_count"] >= donor_topology["triangle_count"]:
        raise ValueError("candidate did not reduce boundary triangle count")
    for key in (
        "boundary_edge_count",
        "nonmanifold_edge_count",
        "orientation_conflict_edge_count",
        "degenerate_triangle_count",
        "isolated_vertex_count",
        "disconnected_vertex_fan_count",
    ):
        if topology[key] != 0:
            raise ValueError(f"candidate structural gate failed: {key}={topology[key]}")
    if topology["max_vertex_fan_components"] != 1:
        raise ValueError("candidate vertex-fan connectivity drift")
    if topology["triangle_component_count"] != donor_topology["triangle_component_count"]:
        raise ValueError("candidate face-connected solid count drift")
    if donor_module.bounds(vertices) != donor_topology["bounds"]:
        raise ValueError("candidate bounds drift")
    if abs(topology["signed_volume_m3"] - donor_topology["signed_volume_m3"]) > EPS:
        raise ValueError("candidate signed volume drift")
    if abs(topology["surface_area_m2"] - donor_topology["surface_area_m2"]) > EPS:
        raise ValueError("candidate surface area drift")
    if abs(topology["signed_volume_m3"] - source["occupied_union_volume_m3"]) > EPS:
        raise ValueError("candidate no longer preserves source occupied union")
    if candidate["max_patch_area_residual_m2"] > EPS:
        raise ValueError("candidate planar patch area drift")

    donor_owner_areas = donor_topology["source_component_boundary_area_m2"]
    candidate_owner_areas = owner_areas(vertices, triangles, owners)
    if set(candidate_owner_areas) != set(donor_owner_areas):
        raise ValueError("candidate source-component ownership coverage drift")
    maximum_owner_area_residual = 0.0
    for owner_id, donor_area in donor_owner_areas.items():
        residual = abs(candidate_owner_areas[owner_id] - donor_area)
        maximum_owner_area_residual = max(maximum_owner_area_residual, residual)
        if residual > EPS:
            raise ValueError(f"candidate source-owner area drift: {owner_id} residual={residual}")

    return {
        **topology,
        "bounds": donor_module.bounds(vertices),
        "source_component_owner_count": len(candidate_owner_areas),
        "source_component_boundary_area_m2": candidate_owner_areas,
        "maximum_source_component_area_residual_m2": q12(maximum_owner_area_residual),
        "payload_sha256": canonical_sha256({
            "vertices": vertices,
            "triangles": triangles,
            "triangle_owners": owners,
            "source_vertex_ids": candidate["source_vertex_ids"],
        }),
    }


def rejected(fn) -> str:
    try:
        fn()
    except (ValueError, KeyError, IndexError) as exc:
        return f"REJECTED:{exc}"
    raise AssertionError("negative control unexpectedly accepted")


def build_obj(candidate: dict) -> str:
    lines = ["# AXM Building conforming planar boundary-shell compaction candidate"]
    for vertex in candidate["vertices"]:
        lines.append("v %.9f %.9f %.9f" % tuple(vertex))
    for triangle in candidate["triangles"]:
        lines.append("f %d %d %d" % (triangle[0] + 1, triangle[1] + 1, triangle[2] + 1))
    return "\n".join(lines) + "\n"


def build_evidence(exact_head="LOCAL_UNBOUND"):
    donor_module = load_module(DONOR_TOOL, "service_pavilion_boundary_shell_donor_for_compaction")
    donor_shell, donor_result = donor_module.build_evidence(exact_head)
    if donor_result["result"] != "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE":
        raise ValueError("boundary-only donor prerequisite is not PASS")

    candidate = derive_compacted_shell(donor_shell)
    candidate_metrics = validate_candidate(donor_module, donor_result, donor_shell, candidate)

    missing = copy.deepcopy(candidate)
    missing["triangles"] = missing["triangles"][:-1]
    missing["triangle_owners"] = missing["triangle_owners"][:-1]

    flipped = copy.deepcopy(candidate)
    a, b, c = flipped["triangles"][0]
    flipped["triangles"][0] = (a, c, b)

    moved = copy.deepcopy(candidate)
    moved["vertices"][0] = [moved["vertices"][0][0] + 0.001, *moved["vertices"][0][1:]]

    lost_owner = copy.deepcopy(candidate)
    lost_owner["triangle_owners"][0]["source_component_id"] = ""

    controls = {
        "missing_boundary_triangle": rejected(lambda: validate_candidate(donor_module, donor_result, donor_shell, missing)),
        "single_triangle_winding_flip": rejected(lambda: validate_candidate(donor_module, donor_result, donor_shell, flipped)),
        "one_mm_boundary_vertex_drift": rejected(lambda: validate_candidate(donor_module, donor_result, donor_shell, moved)),
        "source_component_provenance_loss": rejected(lambda: validate_candidate(donor_module, donor_result, donor_shell, lost_owner)),
    }

    result = {
        "schema": "axm.building-boundary-shell-conforming-compaction/v0.1",
        "result": "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_CANDIDATE",
        "exact_geometry_head": exact_head,
        "donor": {
            "schema": donor_result["schema"],
            "result": donor_result["result"],
            "semantic_source_variant_id": donor_result["current_source_policy"]["variant_id"],
            "source_revision": donor_result["current_source_policy"]["source_revision"],
            "boundary_payload_sha256": donor_result["candidate"]["payload_sha256"],
            "vertex_count": donor_result["candidate"]["vertex_count"],
            "triangle_count": donor_result["candidate"]["triangle_count"],
            "surface_area_m2": donor_result["candidate"]["surface_area_m2"],
            "signed_volume_m3": donor_result["candidate"]["signed_volume_m3"],
            "bounds": donor_result["candidate"]["bounds"],
            "solid_component_count": donor_result["candidate"]["triangle_component_count"],
            "source_component_owner_count": donor_result["candidate"]["source_component_owner_count"],
        },
        "candidate": {
            **candidate_metrics,
            "compacted_patch_count": candidate["compacted_patch_count"],
            "preserved_patch_count": candidate["preserved_patch_count"],
            "max_patch_area_residual_m2": candidate["max_patch_area_residual_m2"],
            "vertex_reduction": donor_result["candidate"]["vertex_count"] - candidate_metrics["vertex_count"],
            "triangle_reduction": donor_result["candidate"]["triangle_count"] - candidate_metrics["triangle_count"],
            "vertex_reduction_fraction": q12(1.0 - candidate_metrics["vertex_count"] / donor_result["candidate"]["vertex_count"]),
            "triangle_reduction_fraction": q12(1.0 - candidate_metrics["triangle_count"] / donor_result["candidate"]["triangle_count"]),
        },
        "patch_audit": candidate["patch_audit"],
        "negative_controls": controls,
        "reusable_pattern_candidate": (
            "Conforming planar-patch retriangulation: remove only interior coplanar partition edges and vertices inside one exact "
            "source-owner plane patch; preserve every outer boundary vertex/edge, exact surface area, solid identity and per-triangle "
            "source provenance so perpendicular neighbouring patches remain index-conforming without T-junctions."
        ),
        "handoffs": {
            "hard_surface": "Keep header-segmented-23 as semantic source and boundary-only-union-shell-001 as the source-owned receiving policy donor. This compacted identity requires a separate owner decision before any policy adoption.",
            "materials_environment_visual": "Do not inherit appearance from the reference shell. Rebind source_component_id roles and inspect this exact triangulation because coplanar diagonal changes can alter generated normals/shading.",
            "runtime": "Measure this exact compacted payload independently before any memory/draw/FPS claim; Geometry proves only structural reduction.",
            "technical_art": "If transported, preserve exact source_component_id coverage and source-boundary identity; do not regenerate partition faces or collapse distinct solid components.",
            "capability_cartography": "Keep this compaction Building-local until the same conforming-boundary/provenance contract succeeds on materially different surface families."
        },
        "truth_boundary": (
            "This PASS proves one source-preserving, boundary-conforming planar retriangulation of the exact Building boundary-only reference shell. "
            "It removes only interior coplanar partition structure while retaining exact occupied volume, bounds, surface area, four face-connected solids, "
            "closed/oriented indexed topology and source-component boundary-area provenance."
        ),
        "non_claims": [
            "replacement of the 23-box semantic source or source-owned boundary-shell receiving policy",
            "minimum triangle count, globally optimal retopology or arbitrary non-planar simplification",
            "final normals, tangents, UVs, materials, generated-normal equivalence or visual acceptance",
            "runtime, draw-call, memory, FPS, collision, navigation, physics or gameplay acceptance",
            "architectural engineering, manufacturing validity, tolerances, loads or sealing",
            "general boolean union or simplifier for rotated, curved or arbitrary meshes",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production readiness, game readiness or Geometry mastery"
        ],
    }
    return candidate, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    parser.add_argument("--output-dir", default="evidence/service-pavilion-boundary-shell-compaction-001")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    candidate, result = build_evidence(args.exact_head)
    (output / "compacted-boundary-shell.obj").write_text(build_obj(candidate), encoding="utf-8")
    (output / "compacted-boundary-shell.json").write_text(
        json.dumps({
            "schema": result["schema"],
            "vertices": candidate["vertices"],
            "triangles": candidate["triangles"],
            "triangle_owners": candidate["triangle_owners"],
            "source_vertex_ids": candidate["source_vertex_ids"],
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "compaction-evidence.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
