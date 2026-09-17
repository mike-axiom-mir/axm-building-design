#!/usr/bin/env python3
"""Build one low-topology render-only receiver from the exact Building union boundary.

This Hard-Surface lane deliberately does not replace the semantic 23-box source or the
indexed Geometry shells. It consumes the exact current-source boundary oracle, then
merges only coplanar boundary cells that share solid component, material role, axis,
outward sign and plane. Each resulting rectangle keeps contributor source-component
and source-box sets. The representation is intentionally a hard-normal render surface
cover, not a collision/manufacturing/transport topology claim.
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
DONOR_TOOL = ROOT / "tools" / "build_service_pavilion_union_shell_candidate.py"
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_render_receiver_policy.json"
EPS = 1e-9
EXPECTED_ROLES = {
    "frame_galvanized",
    "infill_coating",
    "roof_membrane",
    "slab_mineral",
    "utility_panel_ochre",
}


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


def load_policy() -> dict:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy.get("schema") != "axm.building-planar-role-render-receiver-policy/v0.1":
        raise ValueError("planar-role receiver policy schema drift")
    if policy.get("owner") != "Building Hard Surface":
        raise ValueError("planar-role receiver owner drift")
    if policy.get("selection_policy") != "EXPLICIT_RECEIVING_REPRESENTATION_ID_REQUIRED__NO_DEFAULT_OR_IMPLICIT_FALLBACK":
        raise ValueError("planar-role receiver selection policy drift")
    semantic = policy.get("semantic_source", {})
    if semantic.get("variant_id") != "header-segmented-23":
        raise ValueError("planar-role receiver semantic source drift")
    candidate = policy.get("candidate", {})
    if candidate.get("representation_id") != "boundary-only-planar-role-rectangle-render-001":
        raise ValueError("planar-role receiver identity drift")
    if candidate.get("representation_kind") != "NON_INDEXED_RENDER_SURFACE_RECTANGLE_COVER":
        raise ValueError("planar-role receiver representation-kind drift")
    return policy


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


def norm(a):
    return math.sqrt(dot(a, a))


def triangle_area(vertices, triangle):
    a, b, c = (vertices[index] for index in triangle)
    return 0.5 * norm(cross(vec_sub(b, a), vec_sub(c, a)))


def signed_volume(vertices, triangles):
    total = 0.0
    for triangle in triangles:
        a, b, c = (vertices[index] for index in triangle)
        total += dot(a, cross(b, c)) / 6.0
    return q12(total)


def bounds(vertices):
    return {
        "min": [q(min(vertex[axis] for vertex in vertices)) for axis in range(3)],
        "max": [q(max(vertex[axis] for vertex in vertices)) for axis in range(3)],
    }


def quad_record(shell: dict, quad: dict, atomic_id: int) -> dict:
    source_indices = []
    for triangle_index in quad["triangle_indices"]:
        for vertex_index in shell["triangles"][triangle_index]:
            if vertex_index not in source_indices:
                source_indices.append(vertex_index)
    if len(source_indices) != 4:
        raise ValueError(f"boundary quad {atomic_id} does not resolve to four unique vertices")
    points = [shell["vertices"][index] for index in source_indices]
    axis = int(quad["axis"])
    sign = int(quad["sign"])
    other = [index for index in range(3) if index != axis]
    plane_values = {q(point[axis]) for point in points}
    if len(plane_values) != 1:
        raise ValueError(f"boundary quad {atomic_id} is not planar on declared axis")
    plane = next(iter(plane_values))
    u0 = q(min(point[other[0]] for point in points))
    u1 = q(max(point[other[0]] for point in points))
    v0 = q(min(point[other[1]] for point in points))
    v1 = q(max(point[other[1]] for point in points))
    if u1 - u0 <= EPS or v1 - v0 <= EPS:
        raise ValueError(f"boundary quad {atomic_id} has zero planar area")
    measured_area = q12((u1 - u0) * (v1 - v0))
    if abs(measured_area - float(quad["area_m2"])) > EPS:
        raise ValueError(f"boundary quad {atomic_id} area drift")
    return {
        "atomic_id": atomic_id,
        "solid_component": int(quad["solid_component"]),
        "role": str(quad["role"]),
        "axis": axis,
        "sign": sign,
        "plane": plane,
        "u0": u0,
        "u1": u1,
        "v0": v0,
        "v1": v1,
        "area_m2": measured_area,
        "source_component_id": str(quad["source_component_id"]),
        "box_id": str(quad["box_id"]),
    }


def _greedy_cover(occupied: dict, u_coords: list[float], v_coords: list[float], primary: str) -> list[dict]:
    remaining = set(occupied)
    rectangles = []
    while remaining:
        iu, iv = min(remaining, key=lambda cell: (cell[1], cell[0]))
        if primary == "u":
            iu1 = iu
            while (iu1 + 1, iv) in remaining:
                iu1 += 1
            iv1 = iv
            while all((cursor, iv1 + 1) in remaining for cursor in range(iu, iu1 + 1)):
                iv1 += 1
        elif primary == "v":
            iv1 = iv
            while (iu, iv1 + 1) in remaining:
                iv1 += 1
            iu1 = iu
            while all((iu1 + 1, cursor) in remaining for cursor in range(iv, iv1 + 1)):
                iu1 += 1
        else:
            raise ValueError("unsupported rectangle-cover primary axis")
        cells = {(u, v) for u in range(iu, iu1 + 1) for v in range(iv, iv1 + 1)}
        if not cells.issubset(remaining):
            raise ValueError("rectangle cover crossed a missing atomic face")
        remaining.difference_update(cells)
        rectangles.append({
            "iu0": iu,
            "iu1": iu1,
            "iv0": iv,
            "iv1": iv1,
            "u0": u_coords[iu],
            "u1": u_coords[iu1 + 1],
            "v0": v_coords[iv],
            "v1": v_coords[iv1 + 1],
            "cells": sorted(cells),
        })
    return rectangles


def rectangle_cover(records: list[dict]) -> list[dict]:
    if not records:
        return []
    u_coords = sorted({value for row in records for value in (row["u0"], row["u1"])})
    v_coords = sorted({value for row in records for value in (row["v0"], row["v1"])})
    u_index = {value: index for index, value in enumerate(u_coords)}
    v_index = {value: index for index, value in enumerate(v_coords)}
    occupied = {}
    for row in records:
        a, b = u_index[row["u0"]], u_index[row["u1"]]
        c, d = v_index[row["v0"]], v_index[row["v1"]]
        if b != a + 1 or d != c + 1:
            raise ValueError("donor boundary quad no longer maps to one atomic planar interval")
        key = (a, c)
        if key in occupied:
            raise ValueError("duplicate atomic planar boundary cell")
        occupied[key] = row

    candidates = [_greedy_cover(occupied, u_coords, v_coords, "u"), _greedy_cover(occupied, u_coords, v_coords, "v")]
    selected = min(
        candidates,
        key=lambda rows: (
            len(rows),
            [(r["v0"], r["u0"], r["v1"], r["u1"]) for r in rows],
        ),
    )
    for rectangle in selected:
        contributors = [occupied[cell] for cell in rectangle["cells"]]
        rectangle["atomic_ids"] = sorted(row["atomic_id"] for row in contributors)
        rectangle["source_component_ids"] = sorted({row["source_component_id"] for row in contributors})
        rectangle["box_ids"] = sorted({row["box_id"] for row in contributors})
        rectangle["atomic_face_count"] = len(contributors)
        rectangle["area_m2"] = q12((rectangle["u1"] - rectangle["u0"]) * (rectangle["v1"] - rectangle["v0"]))
        expected = q12(sum(row["area_m2"] for row in contributors))
        if abs(rectangle["area_m2"] - expected) > EPS:
            raise ValueError("merged rectangle area does not equal covered atomic faces")
    return selected


def _rectangle_points(donor, axis: int, sign: int, plane: float, u0: float, u1: float, v0: float, v1: float):
    other = [index for index in range(3) if index != axis]
    lo = [0.0, 0.0, 0.0]
    hi = [0.0, 0.0, 0.0]
    lo[axis] = hi[axis] = plane
    lo[other[0]], hi[other[0]] = u0, u1
    lo[other[1]], hi[other[1]] = v0, v1
    return [list(point) for point in donor.face_quad(axis, sign, lo, hi)]


def derive_candidate(shell: dict, donor) -> dict:
    atomic = [quad_record(shell, quad, index) for index, quad in enumerate(shell["boundary_quads"])]
    grouped = collections.defaultdict(list)
    for row in atomic:
        key = (row["solid_component"], row["role"], row["axis"], row["sign"], row["plane"])
        grouped[key].append(row)

    vertices = []
    triangles = []
    triangle_roles = []
    rectangles = []
    for key in sorted(grouped):
        solid_component, role, axis, sign, plane = key
        for merged in rectangle_cover(grouped[key]):
            points = _rectangle_points(
                donor, axis, sign, plane,
                merged["u0"], merged["u1"], merged["v0"], merged["v1"]
            )
            offset = len(vertices)
            vertices.extend(points)
            first = (offset, offset + 1, offset + 2)
            second = (offset, offset + 2, offset + 3)
            for triangle in (first, second):
                a, b, c = (vertices[index] for index in triangle)
                normal = cross(vec_sub(b, a), vec_sub(c, a))
                if norm(normal) <= EPS:
                    raise ValueError("planar-role receiver emitted degenerate triangle")
                for check_axis in range(3):
                    if check_axis == axis:
                        if normal[check_axis] * sign <= EPS:
                            raise ValueError("planar-role receiver winding is not outward")
                    elif abs(normal[check_axis]) > EPS:
                        raise ValueError("planar-role receiver normal is not cardinal")
                triangles.append(triangle)
                triangle_roles.append(role)
            rectangles.append({
                "rectangle_id": f"rect-{len(rectangles):04d}",
                "solid_component": solid_component,
                "role": role,
                "axis": axis,
                "sign": sign,
                "plane": plane,
                "u0": merged["u0"],
                "u1": merged["u1"],
                "v0": merged["v0"],
                "v1": merged["v1"],
                "area_m2": merged["area_m2"],
                "atomic_face_count": merged["atomic_face_count"],
                "atomic_ids": merged["atomic_ids"],
                "source_component_ids": merged["source_component_ids"],
                "box_ids": merged["box_ids"],
                "vertex_range": [offset, offset + 4],
                "triangle_range": [len(triangles) - 2, len(triangles)],
            })

    return {
        "vertices": vertices,
        "triangles": triangles,
        "triangle_roles": triangle_roles,
        "rectangles": rectangles,
        "atomic_faces": atomic,
    }


def role_areas_from_atomic(atomic: list[dict]) -> dict:
    values = collections.defaultdict(float)
    for row in atomic:
        values[row["role"]] += row["area_m2"]
    return {key: q12(value) for key, value in sorted(values.items())}


def role_areas_from_rectangles(rectangles: list[dict]) -> dict:
    values = collections.defaultdict(float)
    for row in rectangles:
        values[row["role"]] += row["area_m2"]
    return {key: q12(value) for key, value in sorted(values.items())}


def validate_cover(candidate: dict, donor_result: dict) -> dict:
    atomic = candidate["atomic_faces"]
    rectangles = candidate["rectangles"]
    atomic_by_id = {row["atomic_id"]: row for row in atomic}
    if len(atomic_by_id) != len(atomic):
        raise ValueError("atomic boundary face IDs are not unique")

    seen = set()
    for rectangle in rectangles:
        if not rectangle["source_component_ids"] or not rectangle["box_ids"]:
            raise ValueError("rectangle lost contributor provenance")
        contributors = []
        for atomic_id in rectangle["atomic_ids"]:
            if atomic_id in seen:
                raise ValueError("rectangle cover overlaps an atomic boundary face")
            if atomic_id not in atomic_by_id:
                raise ValueError("rectangle cover references unknown atomic boundary face")
            row = atomic_by_id[atomic_id]
            if row["role"] != rectangle["role"] or row["solid_component"] != rectangle["solid_component"]:
                raise ValueError("rectangle cover crossed role or solid-component authority")
            if row["axis"] != rectangle["axis"] or row["sign"] != rectangle["sign"] or row["plane"] != rectangle["plane"]:
                raise ValueError("rectangle cover crossed planar boundary authority")
            contributors.append(row)
            seen.add(atomic_id)
        expected_components = sorted({row["source_component_id"] for row in contributors})
        expected_boxes = sorted({row["box_id"] for row in contributors})
        if rectangle["source_component_ids"] != expected_components or rectangle["box_ids"] != expected_boxes:
            raise ValueError("rectangle contributor provenance set drift")
    if seen != set(atomic_by_id):
        raise ValueError("rectangle cover dropped atomic boundary faces")

    vertices = candidate["vertices"]
    triangles = candidate["triangles"]
    if len(vertices) != len(rectangles) * 4 or len(triangles) != len(rectangles) * 2:
        raise ValueError("rectangle render-domain cardinality drift")
    if set(candidate["triangle_roles"]) != EXPECTED_ROLES:
        raise ValueError("planar-role receiver lost exact five material roles")

    donor_role_areas = role_areas_from_atomic(atomic)
    candidate_role_areas = role_areas_from_rectangles(rectangles)
    if donor_role_areas != candidate_role_areas:
        raise ValueError("planar-role receiver changed per-role boundary area")
    total_area = q12(sum(triangle_area(vertices, triangle) for triangle in triangles))
    expected_area = q12(sum(donor_role_areas.values()))
    if abs(total_area - expected_area) > EPS:
        raise ValueError("planar-role receiver total surface area drift")
    volume = signed_volume(vertices, triangles)
    expected_volume = donor_result["source"]["occupied_union_volume_m3"]
    if abs(volume - expected_volume) > EPS:
        raise ValueError("planar-role receiver signed volume differs from occupied union")
    observed_bounds = bounds(vertices)
    if observed_bounds != donor_result["source"]["bounds"]:
        raise ValueError("planar-role receiver bounds differ from current source")

    return {
        "atomic_face_count": len(atomic),
        "rectangle_count": len(rectangles),
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "surface_area_m2": total_area,
        "signed_volume_m3": volume,
        "bounds": observed_bounds,
        "role_areas_m2": candidate_role_areas,
        "role_count": len(candidate_role_areas),
        "atomic_coverage_complete": True,
        "atomic_overlap_count": 0,
        "cardinal_hard_normals_only": True,
        "payload_sha256": canonical_sha256({
            "vertices": vertices,
            "triangles": triangles,
            "triangle_roles": candidate["triangle_roles"],
            "rectangles": [
                {key: row[key] for key in (
                    "solid_component", "role", "axis", "sign", "plane", "u0", "u1", "v0", "v1",
                    "source_component_ids", "box_ids"
                )}
                for row in rectangles
            ],
        }),
    }


def negative_controls(candidate: dict, donor_result: dict) -> dict:
    controls = {}

    dropped = {**candidate, "rectangles": [dict(row) for row in candidate["rectangles"][:-1]]}
    try:
        validate_cover(dropped, donor_result)
        controls["drop_one_rectangle"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["drop_one_rectangle"] = "REJECTED: " + str(exc)

    role_drift = {**candidate, "rectangles": [dict(row) for row in candidate["rectangles"]]}
    role_drift["rectangles"][0]["role"] = "unsupported_role"
    try:
        validate_cover(role_drift, donor_result)
        controls["role_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["role_drift"] = "REJECTED: " + str(exc)

    provenance_drift = {**candidate, "rectangles": [dict(row) for row in candidate["rectangles"]]}
    provenance_drift["rectangles"][0]["source_component_ids"] = []
    try:
        validate_cover(provenance_drift, donor_result)
        controls["missing_contributor_provenance"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["missing_contributor_provenance"] = "REJECTED: " + str(exc)

    if any(not value.startswith("REJECTED:") for value in controls.values()):
        raise ValueError("planar-role receiver negative control unexpectedly passed")
    return controls


def build_evidence(exact_head="LOCAL_UNBOUND"):
    policy = load_policy()
    donor = load_module(DONOR_TOOL, "service_pavilion_union_shell_for_planar_role_receiver")
    shell, donor_result = donor.build_evidence(exact_head)
    if donor_result.get("result") != "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE":
        raise ValueError("boundary oracle result drift")
    if donor_result["current_source_policy"]["variant_id"] != policy["semantic_source"]["variant_id"]:
        raise ValueError("boundary oracle semantic source no longer matches Hard-Surface policy")
    if donor_result["source"]["emitted_box_count"] != policy["semantic_source"]["expected_box_count"]:
        raise ValueError("current-source emitted box count drift")
    if donor_result["source"]["triangle_count_if_boxes_stored_separately"] != policy["semantic_source"]["expected_triangle_count"]:
        raise ValueError("current-source triangle count drift")

    candidate = derive_candidate(shell, donor)
    metrics = validate_cover(candidate, donor_result)
    controls = negative_controls(candidate, donor_result)

    active_triangles = int(policy["semantic_source"]["expected_triangle_count"])
    compact_v2_triangles = 2052
    candidate_triangles = metrics["triangle_count"]
    if candidate_triangles < active_triangles:
        cost_class = "LOWER_TRIANGLE_COUNT_THAN_ACTIVE_SEGMENTED_RECEIVER"
    elif candidate_triangles == active_triangles:
        cost_class = "TRIANGLE_COUNT_PARITY_WITH_ACTIVE_SEGMENTED_RECEIVER"
    else:
        cost_class = "ABOVE_ACTIVE_SEGMENTED_RECEIVER__BELOW_COMPACT_V2_REQUIRED"
    if candidate_triangles >= compact_v2_triangles:
        raise ValueError("planar-role receiver did not improve triangle count over compact-v2")

    bytes_per_triangle_corner_position_normal = 24
    active_model_bytes = active_triangles * 3 * bytes_per_triangle_corner_position_normal
    candidate_model_bytes = candidate_triangles * 3 * bytes_per_triangle_corner_position_normal
    compact_model_bytes = compact_v2_triangles * 3 * bytes_per_triangle_corner_position_normal

    result = {
        "result": "PASS_STRUCTURAL_PLANAR_ROLE_RECTANGLE_RENDER_RECEIVER_CANDIDATE",
        "schema": policy["schema"],
        "exact_hard_surface_head": exact_head,
        "representation_id": policy["candidate"]["representation_id"],
        "selection_policy": policy["selection_policy"],
        "semantic_source": {
            "variant_id": policy["semantic_source"]["variant_id"],
            "emitted_box_count": donor_result["source"]["emitted_box_count"],
            "triangle_count": active_triangles,
            "occupied_union_volume_m3": donor_result["source"]["occupied_union_volume_m3"],
            "bounds": donor_result["source"]["bounds"],
        },
        "boundary_oracle": {
            "result": donor_result["result"],
            "vertex_count": donor_result["candidate"]["vertex_count"],
            "triangle_count": donor_result["candidate"]["triangle_count"],
            "surface_area_m2": donor_result["candidate"]["surface_area_m2"],
            "internal_face_count_by_construction": donor_result["candidate"]["internal_face_count_by_construction"],
        },
        "candidate": metrics,
        "comparison": {
            "cost_class": cost_class,
            "active_segmented_triangle_count": active_triangles,
            "candidate_triangle_count": candidate_triangles,
            "compact_v2_triangle_count": compact_v2_triangles,
            "triangle_delta_vs_active": candidate_triangles - active_triangles,
            "triangle_delta_vs_compact_v2": candidate_triangles - compact_v2_triangles,
            "map_style_position_normal_model_bytes_active": active_model_bytes,
            "map_style_position_normal_model_bytes_candidate": candidate_model_bytes,
            "map_style_position_normal_model_bytes_compact_v2": compact_model_bytes,
            "model_byte_delta_vs_active": candidate_model_bytes - active_model_bytes,
            "model_byte_delta_vs_compact_v2": candidate_model_bytes - compact_model_bytes,
            "model_scope": "Triangle-corner expansion with FLOAT32 position + explicit normal only; excludes material/engine allocator/index/texture/device costs and is not Runtime acceptance."
        },
        "negative_controls": controls,
        "reusable_mechanical_pattern": (
            "For axis/cardinal manufactured box assemblies used only as a render receiver, preserve the semantic assembly separately, derive the exact occupied-union boundary, "
            "then merge coplanar boundary cells only within the same solid/material role/plane. Carry contributor source-component sets on each rectangle, keep hard cardinal normals, "
            "and require explicit consumer rebind. This can target clean manufactured planar highlights without forcing the indexed structural shell to become the render payload."
        ),
        "handoffs": {
            "environment_art_qa": "Rebuild this exact representation in the current world and compare directly against both the active segmented receiver and compact-v2. Structural surface equivalence is not visual acceptance.",
            "runtime": "Measure this exact rectangle receiver in the actual Map SurfaceTool/ArrayMesh path; the byte model here is only a bounded preflight.",
            "materials": "Reuse the existing five scalar material roles exactly; no scalar retune is authorized by this candidate.",
            "geometry": "No indexed topology replacement is requested. Compact-v2 remains the stronger conforming structural/transport candidate; this lane is render-only.",
            "technical_art": "Do not relabel this render rectangle cover as a transport/collision mesh without a separate exact contract.",
        },
        "truth_boundary": policy["truth_boundary"],
        "non_claims": [
            "visual equivalence to compact-v2 or Art Direction acceptance",
            "Environment adoption or replacement of the active segmented receiver",
            "target-device CPU/GPU/FPS/VRAM/heap or renderer-memory improvement",
            "indexed manifoldness, collision, navigation, physics, transport or manufacturing validity",
            "semantic replacement of header-segmented-23 or compact-v2/reference Geometry identities",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness or Hard-Surface mastery"
        ],
    }
    result["receipt_sha256"] = canonical_sha256({key: value for key, value in result.items() if key != "receipt_sha256"})
    return candidate, result


def build_obj(candidate: dict) -> str:
    lines = ["# AXM Building planar-role rectangle render receiver candidate"]
    for vertex in candidate["vertices"]:
        lines.append("v %.9f %.9f %.9f" % tuple(vertex))
    for rectangle in candidate["rectangles"]:
        lines.append(f"g {rectangle['role']}__{rectangle['rectangle_id']}")
        start, end = rectangle["triangle_range"]
        for triangle in candidate["triangles"][start:end]:
            lines.append("f %d %d %d" % (triangle[0] + 1, triangle[1] + 1, triangle[2] + 1))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    parser.add_argument("--output-dir", default="evidence/service-pavilion-planar-role-render-receiver-001")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    candidate, result = build_evidence(args.exact_head)

    retained_candidate = {
        "schema": result["schema"],
        "representation_id": result["representation_id"],
        "vertices": candidate["vertices"],
        "triangles": candidate["triangles"],
        "triangle_roles": candidate["triangle_roles"],
        "rectangles": candidate["rectangles"],
    }
    (output / "planar-role-render-receiver.obj").write_text(build_obj(candidate), encoding="utf-8")
    (output / "planar-role-render-receiver.json").write_text(
        json.dumps(retained_candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "planar-role-render-receiver-evidence.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "policy.json").write_text(POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    (output / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
