#!/usr/bin/env python3
"""Stronger conforming planar compaction for the Building boundary shell.

The first conservative compaction retained every donor patch when ear clipping met long
collinear boundary chains. This successor keeps the same truth boundary but separates
those two concerns: it first triangulates the minimal corner polygon, then deterministically
re-inserts every original collinear boundary vertex by splitting the affected boundary
triangle edge. The exact outer edge chain therefore survives, while interior partition
vertices can still disappear.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_TOOL = ROOT / "tools" / "build_service_pavilion_boundary_shell_compaction.py"
EPS = 1e-9


def load_base(name: str):
    spec = importlib.util.spec_from_file_location(name, BASE_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {BASE_TOOL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def simplify_collinear_loop(loop, vertices, axis, base):
    simplified = list(loop)
    changed = True
    while changed and len(simplified) > 3:
        changed = False
        for index in range(len(simplified)):
            previous = simplified[(index - 1) % len(simplified)]
            current = simplified[index]
            following = simplified[(index + 1) % len(simplified)]
            pa = base.project_point(vertices[previous], axis)
            pb = base.project_point(vertices[current], axis)
            pc = base.project_point(vertices[following], axis)
            if abs(base.cross2(pa, pb, pc)) <= EPS:
                del simplified[index]
                changed = True
                break
    if len(simplified) < 3:
        raise ValueError("collinear simplification collapsed planar loop")
    return simplified


def boundary_chains(loop, simplified):
    positions = {vertex: index for index, vertex in enumerate(loop)}
    if len(positions) != len(loop):
        raise ValueError("planar boundary loop repeats a vertex")
    chains = []
    for index, start in enumerate(simplified):
        end = simplified[(index + 1) % len(simplified)]
        cursor = positions[start]
        chain = [start]
        safety = 0
        while True:
            cursor = (cursor + 1) % len(loop)
            chain.append(loop[cursor])
            safety += 1
            if loop[cursor] == end:
                break
            if safety > len(loop):
                raise ValueError("failed to recover original collinear boundary chain")
        chains.append(chain)
    return chains


def ear_clip_corner_polygon(simplified, vertices, axis, sign, base):
    points = [base.project_point(vertices[index], axis) for index in simplified]
    signed_area = base.polygon_signed_area(points)
    if abs(signed_area) <= EPS:
        raise ValueError("zero-area simplified planar boundary loop")
    orientation = 1.0 if signed_area > 0 else -1.0

    working = list(simplified)
    output = []
    safety = 0
    while len(working) > 3:
        found = False
        for offset in range(len(working)):
            previous = working[(offset - 1) % len(working)]
            current = working[offset]
            following = working[(offset + 1) % len(working)]
            pa = base.project_point(vertices[previous], axis)
            pb = base.project_point(vertices[current], axis)
            pc = base.project_point(vertices[following], axis)
            turn = base.cross2(pa, pb, pc)
            if turn * orientation <= EPS:
                continue
            blocked = False
            for other in working:
                if other in (previous, current, following):
                    continue
                point = base.project_point(vertices[other], axis)
                if base.strictly_inside_triangle(point, pa, pb, pc, orientation):
                    blocked = True
                    break
            if blocked:
                continue
            output.append(base.orient_triangle(vertices, (previous, current, following), axis, sign))
            del working[offset]
            found = True
            break
        safety += 1
        if not found or safety > len(simplified) * len(simplified):
            raise ValueError("corner-polygon ear clipping stalled")

    output.append(base.orient_triangle(vertices, tuple(working), axis, sign))
    return output


def split_boundary_edge(triangles, chain, vertices, axis, sign, base):
    if len(chain) <= 2:
        return triangles
    start, end = chain[0], chain[-1]
    target = None
    third = None
    for index, triangle in enumerate(triangles):
        if start in triangle and end in triangle:
            target = index
            third = next(vertex for vertex in triangle if vertex not in (start, end))
            break
    if target is None or third is None:
        raise ValueError("simplified boundary edge missing from triangulation")

    replacement = []
    for index in range(len(chain) - 1):
        replacement.append(base.orient_triangle(vertices, (chain[index], chain[index + 1], third), axis, sign))
    return triangles[:target] + replacement + triangles[target + 1:]


def triangulate_simple_loop_v2(loop, vertices, axis: int, sign: int, base):
    """Triangulate a planar loop while preserving every original boundary edge split."""
    simplified = simplify_collinear_loop(loop, vertices, axis, base)
    chains = boundary_chains(loop, simplified)
    output = ear_clip_corner_polygon(simplified, vertices, axis, sign, base)
    for chain in chains:
        output = split_boundary_edge(output, chain, vertices, axis, sign, base)
    if len(output) != len(loop) - 2:
        raise ValueError(
            f"boundary-chain reinsertion cardinality drift: got {len(output)}, expected {len(loop) - 2}"
        )
    used = {vertex for triangle in output for vertex in triangle}
    if not set(loop).issubset(used):
        raise ValueError("boundary-chain reinsertion dropped an original boundary vertex")
    return output


def build_evidence(exact_head="LOCAL_UNBOUND"):
    historical = load_base("service_pavilion_boundary_shell_compaction_v1_control")
    _, historical_result = historical.build_evidence(exact_head)

    current = load_base("service_pavilion_boundary_shell_compaction_v2_impl")
    current.triangulate_simple_loop = lambda loop, vertices, axis, sign: triangulate_simple_loop_v2(
        loop, vertices, axis, sign, current
    )
    candidate, result = current.build_evidence(exact_head)

    predecessor = historical_result["candidate"]
    successor = result["candidate"]
    if successor["triangle_count"] >= predecessor["triangle_count"]:
        raise ValueError("v2 did not improve triangle count over conservative v1")
    if successor["vertex_count"] >= predecessor["vertex_count"]:
        raise ValueError("v2 did not improve vertex count over conservative v1")

    result["schema"] = "axm.building-boundary-shell-conforming-compaction/v0.2"
    result["result"] = "PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_COLLINEAR_CHAIN_V2"
    result["algorithm_revision"] = "corner-polygon-ear-clip__reinsert-exact-collinear-boundary-chains-v2"
    result["historical_v1_control"] = {
        "result": historical_result["result"],
        "vertex_count": predecessor["vertex_count"],
        "triangle_count": predecessor["triangle_count"],
        "vertex_reduction_vs_reference": predecessor["vertex_reduction"],
        "triangle_reduction_vs_reference": predecessor["triangle_reduction"],
        "payload_sha256": predecessor["payload_sha256"],
    }
    result["candidate"]["additional_vertex_reduction_vs_v1"] = predecessor["vertex_count"] - successor["vertex_count"]
    result["candidate"]["additional_triangle_reduction_vs_v1"] = predecessor["triangle_count"] - successor["triangle_count"]
    result["reusable_pattern_candidate"] = (
        "Conforming planar-patch retriangulation with collinear-chain preservation: simplify a patch only to its true corner polygon for "
        "interior triangulation, then split each simplified outer edge back through every original boundary vertex. This removes interior "
        "partition topology without introducing T-junctions or erasing source-owner boundary provenance."
    )
    result["truth_boundary"] = (
        "This PASS proves one stronger source-preserving planar compaction of the exact Building boundary-only reference shell. It preserves "
        "every original outer patch edge split while removing interior coplanar partition structure, with exact occupied volume, bounds, "
        "surface area, four face-connected solids, closed/oriented indexed topology and source-component boundary-area provenance."
    )
    return candidate, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", default="LOCAL_UNBOUND")
    parser.add_argument("--output-dir", default="evidence/service-pavilion-boundary-shell-compaction-v2-001")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    candidate, result = build_evidence(args.exact_head)

    base = load_base("service_pavilion_boundary_shell_compaction_v2_output")
    (output / "compacted-boundary-shell-v2.obj").write_text(base.build_obj(candidate), encoding="utf-8")
    (output / "compacted-boundary-shell-v2.json").write_text(
        json.dumps({
            "schema": result["schema"],
            "vertices": candidate["vertices"],
            "triangles": candidate["triangles"],
            "triangle_owners": candidate["triangle_owners"],
            "source_vertex_ids": candidate["source_vertex_ids"],
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "compaction-v2-evidence.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
