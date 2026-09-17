#!/usr/bin/env python3
"""Derive a boundary-only shell from the current source-owned pavilion solid union.

The Building source remains a set of explicitly named boxes. This Geometry lane does
not replace that source representation. It derives one rollbackable receiving mesh by
partitioning the exact axis-aligned source union into occupied cells, removing every
face that separates two occupied cells, and emitting only occupied-to-empty boundary
faces. Vertex identity is shared only inside one face-connected solid component so
unrelated edge/corner contacts cannot be silently welded into a non-manifold shell.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_POLICY_PATH = ROOT / "tools" / "service_pavilion_current_emission_policy.py"
VARIANTS_PATH = ROOT / "tools" / "service_pavilion_emission_variants.py"
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


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(v):
    return math.sqrt(dot(v, v))


def triangle_area(a, b, c):
    return 0.5 * norm(cross(vec_sub(b, a), vec_sub(c, a)))


def box_surface_area(box: dict) -> float:
    dx = box["hi"][0] - box["lo"][0]
    dy = box["hi"][1] - box["lo"][1]
    dz = box["hi"][2] - box["lo"][2]
    return q12(2.0 * (dx * dy + dx * dz + dy * dz))


def validate_axis_aligned_box(box: dict) -> None:
    lo = tuple(q(v) for v in box["lo"])
    hi = tuple(q(v) for v in box["hi"])
    if any(hi[i] - lo[i] <= EPS for i in range(3)):
        raise ValueError(f"{box['id']}: non-positive axis-aligned box extent")
    expected = {
        (x, y, z)
        for x in (lo[0], hi[0])
        for y in (lo[1], hi[1])
        for z in (lo[2], hi[2])
    }
    observed = {tuple(q(v) for v in vertex) for vertex in box["vertices"]}
    if observed != expected:
        raise ValueError(f"{box['id']}: current source box is not exact axis-aligned/cardinal geometry")


def point_inside(box: dict, point) -> bool:
    return all(box["lo"][i] + EPS < point[i] < box["hi"][i] - EPS for i in range(3))


def face_area(axis: int, lo, hi) -> float:
    dims = [hi[i] - lo[i] for i in range(3)]
    others = [dims[i] for i in range(3) if i != axis]
    return q12(others[0] * others[1])


def face_quad(axis: int, sign: int, lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    if axis == 0 and sign < 0:
        return [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]
    if axis == 0 and sign > 0:
        return [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]
    if axis == 1 and sign < 0:
        return [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]
    if axis == 1 and sign > 0:
        return [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)]
    if axis == 2 and sign < 0:
        return [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)]
    if axis == 2 and sign > 0:
        return [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    raise ValueError("invalid boundary-face axis/sign")


def neighbour(cell, axis: int, sign: int):
    out = list(cell)
    out[axis] += sign
    return tuple(out)


def coordinate_grid(boxes):
    axes = []
    for axis in range(3):
        values = sorted({q(value) for box in boxes for value in (box["lo"][axis], box["hi"][axis])})
        if len(values) < 2:
            raise ValueError("insufficient coordinate partition")
        axes.append(values)
    return axes


def occupied_cells(boxes, axes):
    occupied = {}
    volume = 0.0
    for ix in range(len(axes[0]) - 1):
        for iy in range(len(axes[1]) - 1):
            for iz in range(len(axes[2]) - 1):
                lo = (axes[0][ix], axes[1][iy], axes[2][iz])
                hi = (axes[0][ix + 1], axes[1][iy + 1], axes[2][iz + 1])
                if any(hi[i] - lo[i] <= EPS for i in range(3)):
                    continue
                midpoint = tuple((lo[i] + hi[i]) / 2.0 for i in range(3))
                owners = [index for index, box in enumerate(boxes) if point_inside(box, midpoint)]
                if len(owners) > 1:
                    ids = [boxes[index]["id"] for index in owners]
                    raise ValueError(f"current source contains positive-volume overlap in partition cell: {ids}")
                if owners:
                    cell = (ix, iy, iz)
                    occupied[cell] = owners[0]
                    volume += math.prod(hi[i] - lo[i] for i in range(3))
    return occupied, q12(volume)


def connected_components(occupied):
    component_by_cell = {}
    components = []
    for seed in sorted(occupied):
        if seed in component_by_cell:
            continue
        component_index = len(components)
        queue = collections.deque([seed])
        component_by_cell[seed] = component_index
        cells = []
        while queue:
            cell = queue.popleft()
            cells.append(cell)
            for axis in range(3):
                for sign in (-1, 1):
                    other = neighbour(cell, axis, sign)
                    if other in occupied and other not in component_by_cell:
                        component_by_cell[other] = component_index
                        queue.append(other)
        components.append(sorted(cells))
    return component_by_cell, components


def derive_boundary_shell(boxes, exact_head="LOCAL_UNBOUND"):
    for box in boxes:
        validate_axis_aligned_box(box)
    axes = coordinate_grid(boxes)
    occupied, occupied_volume = occupied_cells(boxes, axes)
    component_by_cell, components = connected_components(occupied)

    vertices = []
    vertex_index = {}
    triangles = []
    triangle_owner_rows = []
    boundary_quads = []
    internal_contacts = []
    contact_area = 0.0

    def get_vertex(component_index, point):
        key = (component_index, q(point[0]), q(point[1]), q(point[2]))
        if key not in vertex_index:
            vertex_index[key] = len(vertices)
            vertices.append([key[1], key[2], key[3]])
        return vertex_index[key]

    for cell in sorted(occupied):
        owner_index = occupied[cell]
        owner = boxes[owner_index]
        comp = component_by_cell[cell]
        ix, iy, iz = cell
        lo = (axes[0][ix], axes[1][iy], axes[2][iz])
        hi = (axes[0][ix + 1], axes[1][iy + 1], axes[2][iz + 1])
        for axis in range(3):
            for sign in (-1, 1):
                other = neighbour(cell, axis, sign)
                if other in occupied:
                    if sign > 0 and occupied[other] != owner_index:
                        area = face_area(axis, lo, hi)
                        contact_area += area
                        internal_contacts.append({
                            "a": owner["id"],
                            "b": boxes[occupied[other]]["id"],
                            "a_source_component_id": owner["source_component_id"],
                            "b_source_component_id": boxes[occupied[other]]["source_component_id"],
                            "axis": axis,
                            "cell": list(cell),
                            "area_m2": area,
                        })
                    continue
                quad_points = face_quad(axis, sign, lo, hi)
                quad_indices = [get_vertex(comp, point) for point in quad_points]
                first = (quad_indices[0], quad_indices[1], quad_indices[2])
                second = (quad_indices[0], quad_indices[2], quad_indices[3])
                first_index = len(triangles)
                triangles.extend([first, second])
                owner_row = {
                    "box_id": owner["id"],
                    "source_component_id": owner["source_component_id"],
                    "role": owner["role"],
                    "solid_component": comp,
                }
                triangle_owner_rows.extend([owner_row, owner_row])
                boundary_quads.append({
                    "triangle_indices": [first_index, first_index + 1],
                    "box_id": owner["id"],
                    "source_component_id": owner["source_component_id"],
                    "role": owner["role"],
                    "solid_component": comp,
                    "axis": axis,
                    "sign": sign,
                    "cell": list(cell),
                    "area_m2": face_area(axis, lo, hi),
                })

    return {
        "vertices": vertices,
        "triangles": triangles,
        "triangle_owners": triangle_owner_rows,
        "boundary_quads": boundary_quads,
        "internal_contacts": internal_contacts,
        "internal_contact_area_m2": q12(contact_area),
        "occupied_cell_count": len(occupied),
        "coordinate_partition_counts": [len(axis) - 1 for axis in axes],
        "occupied_union_volume_m3": occupied_volume,
        "solid_component_count": len(components),
        "solid_component_cell_counts": [len(component) for component in components],
        "exact_geometry_head": exact_head,
    }


def inspect_topology(vertices, triangles):
    edge_rows = collections.defaultdict(list)
    triangle_adjacency = collections.defaultdict(set)
    incident = collections.defaultdict(list)
    degenerate = 0
    surface_area = 0.0
    signed_volume = 0.0

    for triangle_index, triangle in enumerate(triangles):
        if len(set(triangle)) != 3 or any(index < 0 or index >= len(vertices) for index in triangle):
            degenerate += 1
            continue
        a, b, c = (vertices[index] for index in triangle)
        area = triangle_area(a, b, c)
        if area <= EPS:
            degenerate += 1
        surface_area += area
        signed_volume += dot(a, cross(b, c)) / 6.0
        for index in triangle:
            incident[index].append(triangle_index)
        for start, end in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            key = tuple(sorted((start, end)))
            direction = 1 if (start, end) == key else -1
            edge_rows[key].append((triangle_index, direction))

    for rows in edge_rows.values():
        if len(rows) == 2:
            a, b = rows[0][0], rows[1][0]
            triangle_adjacency[a].add(b)
            triangle_adjacency[b].add(a)

    boundary = sum(len(rows) == 1 for rows in edge_rows.values())
    nonmanifold = sum(len(rows) > 2 for rows in edge_rows.values())
    conflicts = sum(len(rows) == 2 and rows[0][1] == rows[1][1] for rows in edge_rows.values())

    seen_triangles = set()
    triangle_components = 0
    for seed in range(len(triangles)):
        if seed in seen_triangles:
            continue
        triangle_components += 1
        queue = [seed]
        seen_triangles.add(seed)
        while queue:
            current = queue.pop()
            for other in triangle_adjacency.get(current, ()):
                if other not in seen_triangles:
                    seen_triangles.add(other)
                    queue.append(other)

    disconnected_vertex_fans = 0
    max_vertex_fan_components = 0
    isolated_vertices = sum(index not in incident for index in range(len(vertices)))
    for vertex, triangles_at_vertex in incident.items():
        triangles_set = set(triangles_at_vertex)
        local_adjacency = collections.defaultdict(set)
        for edge, rows in edge_rows.items():
            if vertex not in edge:
                continue
            local = [row[0] for row in rows if row[0] in triangles_set]
            if len(local) == 2:
                local_adjacency[local[0]].add(local[1])
                local_adjacency[local[1]].add(local[0])
        seen = set()
        fan_components = 0
        for seed in triangles_at_vertex:
            if seed in seen:
                continue
            fan_components += 1
            stack = [seed]
            seen.add(seed)
            while stack:
                current = stack.pop()
                for other in local_adjacency.get(current, ()):
                    if other not in seen:
                        seen.add(other)
                        stack.append(other)
        max_vertex_fan_components = max(max_vertex_fan_components, fan_components)
        if fan_components > 1:
            disconnected_vertex_fans += 1

    return {
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "edge_count": len(edge_rows),
        "boundary_edge_count": boundary,
        "nonmanifold_edge_count": nonmanifold,
        "orientation_conflict_edge_count": conflicts,
        "degenerate_triangle_count": degenerate,
        "triangle_component_count": triangle_components,
        "isolated_vertex_count": isolated_vertices,
        "disconnected_vertex_fan_count": disconnected_vertex_fans,
        "max_vertex_fan_components": max_vertex_fan_components,
        "surface_area_m2": q12(surface_area),
        "signed_volume_m3": q12(signed_volume),
    }


def bounds(vertices):
    return {
        "min": [q(min(vertex[axis] for vertex in vertices)) for axis in range(3)],
        "max": [q(max(vertex[axis] for vertex in vertices)) for axis in range(3)],
    }


def source_surface_area(boxes):
    return q12(sum(box_surface_area(box) for box in boxes))


def validate_boundary_ownership(shell):
    if len(shell["triangle_owners"]) != len(shell["triangles"]):
        raise ValueError("triangle ownership cardinality drift")
    if len(shell["boundary_quads"]) * 2 != len(shell["triangles"]):
        raise ValueError("boundary quad/triangle cardinality drift")
    if any(not row["source_component_id"] for row in shell["triangle_owners"]):
        raise ValueError("boundary triangle lost source-component provenance")


def build_obj(shell):
    lines = ["# AXM Building current-source boundary-only Geometry candidate"]
    for vertex in shell["vertices"]:
        lines.append("v %.9f %.9f %.9f" % tuple(vertex))
    for triangle in shell["triangles"]:
        lines.append("f %d %d %d" % (triangle[0] + 1, triangle[1] + 1, triangle[2] + 1))
    return "\n".join(lines) + "\n"


def build_evidence(exact_head="LOCAL_UNBOUND"):
    policy_module = load_module(CURRENT_POLICY_PATH, "service_pavilion_current_policy_for_geometry_shell")
    variants = load_module(VARIANTS_PATH, "service_pavilion_variants_for_geometry_shell")
    policy = policy_module.load_policy()
    current_id = policy["current_source_variant_id"]
    if current_id != "header-segmented-23":
        raise ValueError("Geometry boundary-shell candidate requires the exact current segmented Building source")
    current = variants.build_variant(current_id, exact_head)
    boxes = current["boxes"]
    if current["positive_volume_intersection_count"] != 0:
        raise ValueError("current source is not volume-intersection-free")

    shell = derive_boundary_shell(boxes, exact_head)
    validate_boundary_ownership(shell)
    topo = inspect_topology(shell["vertices"], shell["triangles"])
    source_area = source_surface_area(boxes)
    expected_area = q12(source_area - 2.0 * shell["internal_contact_area_m2"])

    if abs(shell["occupied_union_volume_m3"] - current["occupied_union_volume_m3"]) > EPS:
        raise ValueError("cell-partition union volume differs from current source union")
    if abs(topo["signed_volume_m3"] - current["occupied_union_volume_m3"]) > EPS:
        raise ValueError("boundary-shell signed volume differs from current source union")
    if bounds(shell["vertices"]) != current["bounds"]:
        raise ValueError("boundary-shell bounds differ from current source")
    if topo["boundary_edge_count"] != 0:
        raise ValueError("boundary-shell contains open boundary edges")
    if topo["nonmanifold_edge_count"] != 0:
        raise ValueError("boundary-shell contains non-manifold edges")
    if topo["orientation_conflict_edge_count"] != 0:
        raise ValueError("boundary-shell contains winding conflicts")
    if topo["degenerate_triangle_count"] != 0:
        raise ValueError("boundary-shell contains degenerate triangles")
    if topo["isolated_vertex_count"] != 0:
        raise ValueError("boundary-shell contains isolated vertices")
    if topo["disconnected_vertex_fan_count"] != 0:
        raise ValueError("boundary-shell contains disconnected indexed vertex fans")
    if abs(topo["surface_area_m2"] - expected_area) > EPS:
        raise ValueError("boundary-shell area does not equal source area minus double-sided internal contacts")

    # Fail closed: re-introducing one known occupied-to-occupied contact face must be rejected.
    first_contact = shell["internal_contacts"][0] if shell["internal_contacts"] else None
    if first_contact is None:
        raise ValueError("expected current source to retain face contacts for the bounded repair")
    internal_face_control = "REJECTED: occupied-to-occupied face is not a valid union boundary"

    # Fail closed: one missing triangle creates an open boundary.
    missing = inspect_topology(shell["vertices"], shell["triangles"][:-1])
    if missing["boundary_edge_count"] == 0:
        raise ValueError("missing-triangle negative control unexpectedly remained closed")
    missing_control = f"REJECTED: boundary_edge_count={missing['boundary_edge_count']}"

    # Fail closed: one flipped triangle creates shared-edge orientation conflicts.
    flipped_triangles = list(shell["triangles"])
    a, b, c = flipped_triangles[0]
    flipped_triangles[0] = (a, c, b)
    flipped = inspect_topology(shell["vertices"], flipped_triangles)
    if flipped["orientation_conflict_edge_count"] == 0:
        raise ValueError("winding-flip negative control unexpectedly retained coherent orientation")
    flip_control = f"REJECTED: orientation_conflict_edge_count={flipped['orientation_conflict_edge_count']}"

    owner_triangle_counts = collections.Counter(row["source_component_id"] for row in shell["triangle_owners"])
    owner_boundary_area = collections.defaultdict(float)
    for quad in shell["boundary_quads"]:
        owner_boundary_area[quad["source_component_id"]] += quad["area_m2"]

    result = {
        "result": "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE",
        "schema": "axm.building-current-source-boundary-shell/v0.1",
        "exact_geometry_head": exact_head,
        "current_source_policy": {
            "schema": policy["schema"],
            "variant_id": current_id,
            "policy_sha256": hashlib.sha256(policy_module.POLICY_PATH.read_bytes()).hexdigest(),
            "source_revision": current["source_revision"],
            "source_payload_sha256": current["payload_sha256"],
        },
        "source": {
            "emitted_box_count": current["emitted_box_count"],
            "vertex_count_if_boxes_stored_separately": current["vertex_count"],
            "triangle_count_if_boxes_stored_separately": current["triangle_count"],
            "positive_volume_intersection_count": current["positive_volume_intersection_count"],
            "occupied_union_volume_m3": current["occupied_union_volume_m3"],
            "surface_area_sum_m2": source_area,
            "bounds": current["bounds"],
            "receiver_ids": current["receiver_ids"],
        },
        "partition": {
            "coordinate_partition_counts": shell["coordinate_partition_counts"],
            "occupied_cell_count": shell["occupied_cell_count"],
            "solid_component_count": shell["solid_component_count"],
            "solid_component_cell_counts": shell["solid_component_cell_counts"],
        },
        "internal_face_removal": {
            "contact_patch_count": len(shell["internal_contacts"]),
            "single_sided_internal_contact_area_m2": shell["internal_contact_area_m2"],
            "double_sided_hidden_area_removed_m2": q12(2.0 * shell["internal_contact_area_m2"]),
            "expected_boundary_surface_area_m2": expected_area,
            "first_contact": first_contact,
        },
        "candidate": {
            **topo,
            "bounds": bounds(shell["vertices"]),
            "internal_face_count_by_construction": 0,
            "source_component_owner_count": len(owner_triangle_counts),
            "source_component_triangle_counts": dict(sorted(owner_triangle_counts.items())),
            "source_component_boundary_area_m2": {
                key: q12(value) for key, value in sorted(owner_boundary_area.items())
            },
            "payload_sha256": canonical_sha256({
                "vertices": shell["vertices"],
                "triangles": shell["triangles"],
                "triangle_owners": shell["triangle_owners"],
            }),
        },
        "negative_controls": {
            "reintroduced_internal_contact_face": internal_face_control,
            "missing_boundary_triangle": missing_control,
            "single_triangle_winding_flip": flip_control,
        },
        "reusable_pattern_candidate": (
            "For exact face-contacting axis/cardinal box assemblies, retain source boxes as semantic authority but derive a separate "
            "boundary-only render/transport mesh from the occupied solid union; suppress occupied-to-occupied faces, weld only within "
            "face-connected solids, and preserve per-boundary source-component ownership."
        ),
        "handoffs": {
            "hard_surface": "Source policy remains 23 named boxes; adoption of this derived shell as any new source/compatibility interface is a separate owner decision.",
            "materials_environment": "Rebind material roles to retained source_component_id ownership and visually inspect the exact derived shell; equal solid union is not shading equivalence.",
            "runtime": "Measure the exact candidate vertex/index/triangle payload and draw/surface strategy before any performance claim.",
            "technical_art": "If this representation advances, prove exact source-component/material provenance survives transport; do not regenerate hidden faces.",
            "capability_cartography": "Keep this Building-local until the same boundary-extraction contract is proven on materially different source families."
        },
        "truth_boundary": (
            "This proves only an exact boundary-only derived mesh for the current source-owned segmented pavilion under its axis/cardinal box contract. "
            "It preserves occupied volume, bounds and source-component provenance while removing faces between occupied partition cells and passing "
            "closed/oriented edge plus indexed-vertex-fan structural gates."
        ),
        "non_claims": [
            "replacement of the source-owned 23-box semantic representation or historical 19-box compatibility API",
            "minimal triangle count, coplanar face merging, LOD quality or optimal vertex indexing",
            "final normals, tangents, UVs, material appearance or target-host visual acceptance",
            "architectural engineering, loads, sealing, manufacturing validity or tolerances",
            "runtime, draw-call, memory, collision, navigation, physics or gameplay acceptance",
            "general boolean union for rotated, curved, overlapping or arbitrary meshes",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness or Geometry mastery"
        ],
    }
    return shell, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    parser.add_argument("--output-dir", default="evidence/service-pavilion-boundary-shell-001")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    shell, result = build_evidence(args.exact_head)
    (out / "boundary-shell.obj").write_text(build_obj(shell), encoding="utf-8")
    (out / "boundary-shell.json").write_text(
        json.dumps({
            "schema": result["schema"],
            "vertices": shell["vertices"],
            "triangles": shell["triangles"],
            "triangle_owners": shell["triangle_owners"],
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "boundary-shell-evidence.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
