#!/usr/bin/env python3
"""Build bounded Procedural components from the exact Building source-owner seam graph.

Hard Surface owns which indexed boundaries exist and whether compact-v2 preserves them.
Procedural only turns the exact owner-seam edge set into deterministic owner-pair connected
components so repeated downstream work does not hand-partition 268 edges. The graph remains
representational: no physical gap, bevel, weld, fastener, gasket or material border is inferred.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "procedural" / "service_pavilion_owner_seam_component_family_001.json"
EXPECTED_SCHEMA = "axm.building-owner-seam-component-family/v0.1"
EXPECTED_FAMILY_ID = "service-pavilion-owner-seam-component-family-001"
EXPECTED_HARD_SURFACE_HEAD = "04d9a06bf8e8097c62de348d11230145b1f27686"
EXPECTED_HARD_SURFACE_POLICY_BLOB = "f40e34dfbd899fbf1ee023bacef6a915662463aa"
EXPECTED_HARD_SURFACE_VERIFIER_BLOB = "38804e319daf75a196f8c990b25b033ab088c40c"
EXPECTED_HARD_SURFACE_RESULT = "PASS_SOURCE_OWNED_COMPACT_BOUNDARY_OWNER_SEAM_GRAPH_PRESERVED"
EXPECTED_SEAM_IDENTITY_SHA256 = "75b865c2b6f0559410549c03ac1c3b44fd00a71b186289d8a2ccb1e06df2c322"
EXPECTED_RESULT = "PASS_BOUNDED_OWNER_SEAM_COMPONENT_FAMILY"
EXPECTED_DECISION = "PASS_DERIVED_OWNER_SEAM_COMPONENT_PARAMETERIZATION_ONLY__NO_PHYSICAL_SEAM_OR_RECEIVER_ADOPTION"
EPS = 1e-9


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_policy(policy: dict) -> None:
    if policy.get("schema") != EXPECTED_SCHEMA or policy.get("family_id") != EXPECTED_FAMILY_ID:
        raise ValueError("Procedural family identity/schema drift")
    if policy.get("asset_id") != "service-pavilion-001" or policy.get("owner") != "Procedural Design":
        raise ValueError("Procedural family owner/asset drift")
    authority = policy.get("source_authority", {})
    expected_authority = {
        "repository": "mike-axiom-mir/axm-building-design",
        "hard_surface_pr": 9,
        "hard_surface_head": EXPECTED_HARD_SURFACE_HEAD,
        "hard_surface_policy_path": "assets/service_pavilion_001_compact_boundary_owner_seam_policy.json",
        "hard_surface_policy_git_blob_sha": EXPECTED_HARD_SURFACE_POLICY_BLOB,
        "hard_surface_verifier_path": "tools/verify_service_pavilion_compact_boundary_owner_seams.py",
        "hard_surface_verifier_git_blob_sha": EXPECTED_HARD_SURFACE_VERIFIER_BLOB,
        "hard_surface_result": EXPECTED_HARD_SURFACE_RESULT,
        "owner_seam_identity_sha256": EXPECTED_SEAM_IDENTITY_SHA256,
    }
    if authority != expected_authority:
        raise ValueError("Hard Surface source-authority identity drift")
    expected_contract = {
        "input": "EXACT_HARD_SURFACE_OWNER_SEAM_RECORDS",
        "operation": "GROUP_BY_EXACT_OWNER_PAIR_THEN_CONNECTED_COMPONENT_BY_DONOR_SOURCE_VERTEX_ID",
        "component_identity": "OWNER_PAIR_PLUS_SORTED_SOURCE_EDGES",
        "ordering": "LEXICOGRAPHIC_OWNER_PAIR_THEN_MIN_SOURCE_VERTEX_THEN_COMPONENT_DIGEST",
        "geometry_mutation": False,
        "source_rewrite": False,
        "physical_seam_inference": False,
        "automatic_receiver_adoption": False,
        "implicit_fallback": False,
    }
    if policy.get("family_contract") != expected_contract:
        raise ValueError("Procedural component contract drift or authority inflation")
    bounds = policy.get("exact_bounds", {})
    if int(bounds.get("expected_owner_seam_edge_count", -1)) != 268:
        raise ValueError("owner-seam edge bound drift")
    if int(bounds.get("expected_owner_pair_count", -1)) != 30:
        raise ValueError("owner-pair bound drift")
    if abs(float(bounds.get("expected_total_owner_seam_length_m", -1.0)) - 34.72) > EPS:
        raise ValueError("owner-seam total-length bound drift")
    if bounds.get("expected_edge_count_classes") != [4, 6, 8, 10, 12, 14]:
        raise ValueError("edge-count variation classes drift")
    if bounds.get("expected_length_classes_m") != [0.72, 0.8, 1.44, 5.2]:
        raise ValueError("length variation classes drift")
    if int(bounds.get("length_class_round_digits", -1)) != 2:
        raise ValueError("length class rounding contract drift")
    if policy.get("failure_policy") != "FAIL_CLOSED_NO_OWNER_GUESSING_NO_EDGE_SYNTHESIS_NO_PHYSICAL_SEAM_PROMOTION_NO_RECEIVER_ADOPTION":
        raise ValueError("failure policy weakened")
    if policy.get("decision") != EXPECTED_DECISION:
        raise ValueError("decision boundary drift")
    if policy.get("universal_promotion") != "HELD_UNTIL_MATERIALLY_DIFFERENT_MANUFACTURED_DOMAIN_REPRODUCES_THE_SAME_COMPONENT_PARAMETERIZATION_NEED":
        raise ValueError("premature universal promotion")


def validate_source_records(records: list[dict]) -> list[dict]:
    normalized, seen = [], set()
    for record in records:
        pair = list(record.get("owner_pair", []))
        edge = [int(value) for value in record.get("source_edge", [])]
        endpoints = record.get("endpoints_by_source_id", {})
        length_m = float(record.get("length_m", -1.0))
        if len(pair) != 2 or any(not isinstance(value, str) or not value for value in pair):
            raise ValueError("owner pair malformed")
        if pair != sorted(pair) or pair[0] == pair[1]:
            raise ValueError("owner pair must be sorted and cross-owner")
        if len(edge) != 2 or edge != sorted(edge) or edge[0] == edge[1]:
            raise ValueError("source edge must contain two sorted distinct donor vertex ids")
        if not math.isfinite(length_m) or length_m <= 0.0:
            raise ValueError("seam length must be finite and positive")
        if set(endpoints) != {str(edge[0]), str(edge[1])}:
            raise ValueError("seam endpoint provenance does not match source edge")
        for source_id in edge:
            position = endpoints[str(source_id)]
            if len(position) != 3 or any(not math.isfinite(float(value)) for value in position):
                raise ValueError("seam endpoint is not a finite 3D point")
        identity = (tuple(pair), tuple(edge))
        if identity in seen:
            raise ValueError("duplicate source-owner seam identity")
        seen.add(identity)
        normalized.append({
            "owner_pair": pair,
            "source_edge": edge,
            "endpoints_by_source_id": {str(source_id): [float(v) for v in endpoints[str(source_id)]] for source_id in edge},
            "length_m": length_m,
        })
    normalized.sort(key=lambda row: (row["owner_pair"], row["source_edge"]))
    return normalized


def identity_digest(records: list[dict]) -> str:
    return canonical_sha256([{"owner_pair": r["owner_pair"], "source_edge": r["source_edge"]} for r in records])


def connected_components_for_pair(pair_records: list[dict]) -> list[dict]:
    by_edge = {tuple(record["source_edge"]): record for record in pair_records}
    adjacency: dict[int, set[int]] = defaultdict(set)
    for a, b in by_edge:
        adjacency[a].add(b)
        adjacency[b].add(a)
    unseen, components = set(adjacency), []
    while unseen:
        queue, vertices = deque([min(unseen)]), set()
        while queue:
            vertex = queue.popleft()
            if vertex in vertices:
                continue
            vertices.add(vertex)
            unseen.discard(vertex)
            for neighbor in sorted(adjacency[vertex]):
                if neighbor not in vertices:
                    queue.append(neighbor)
        edges = sorted(edge for edge in by_edge if edge[0] in vertices and edge[1] in vertices)
        degree_counts = sorted(len(adjacency[v]) for v in vertices)
        degree_histogram = {str(d): degree_counts.count(d) for d in sorted(set(degree_counts))}
        if len(edges) == 1:
            graph_class = "SINGLE_SEGMENT"
        elif all(d == 2 for d in degree_counts):
            graph_class = "CLOSED_CYCLE"
        elif degree_counts.count(1) == 2 and all(d in (1, 2) for d in degree_counts):
            graph_class = "OPEN_CHAIN"
        else:
            graph_class = "BRANCHED_OR_COMPLEX"
        core = {
            "source_vertex_ids": sorted(vertices),
            "source_edges": [list(edge) for edge in edges],
            "edge_count": len(edges),
            "vertex_count": len(vertices),
            "total_length_m": sum(by_edge[edge]["length_m"] for edge in edges),
            "degree_histogram": degree_histogram,
            "graph_class": graph_class,
        }
        components.append({**core, "component_sha256": canonical_sha256(core)})
    components.sort(key=lambda c: (min(c["source_vertex_ids"]), c["component_sha256"]))
    return components


def build_pair_outputs(records: list[dict]) -> list[dict]:
    normalized = validate_source_records(records)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in normalized:
        groups[tuple(record["owner_pair"])].append(record)
    outputs = []
    for pair in sorted(groups):
        pair_records = groups[pair]
        components = connected_components_for_pair(pair_records)
        core = {
            "schema": "axm.building-owner-seam-component-output/v0.1",
            "family_id": EXPECTED_FAMILY_ID,
            "owner_pair": list(pair),
            "edge_count": len(pair_records),
            "total_length_m": sum(r["length_m"] for r in pair_records),
            "connected_component_count": len(components),
            "components": components,
            "authority": "DERIVED_REPRESENTATIONAL_COMPONENTS_ONLY__NO_PHYSICAL_SEAM_SEMANTICS",
        }
        outputs.append({**core, "pair_output_sha256": canonical_sha256(core)})
    return outputs


def validate_family(policy: dict, records: list[dict], outputs: list[dict]) -> dict:
    validate_policy(policy)
    normalized = validate_source_records(records)
    bounds = policy["exact_bounds"]
    if len(normalized) != bounds["expected_owner_seam_edge_count"]:
        raise ValueError("owner-seam edge count drift")
    if identity_digest(normalized) != EXPECTED_SEAM_IDENTITY_SHA256:
        raise ValueError("owner-seam identity digest drift")
    total_length = sum(r["length_m"] for r in normalized)
    if abs(total_length - bounds["expected_total_owner_seam_length_m"]) > EPS:
        raise ValueError("owner-seam total length drift")
    expected_outputs = build_pair_outputs(normalized)
    if outputs != expected_outputs:
        raise ValueError("Procedural pair outputs differ from canonical derivation")
    if len(outputs) != bounds["expected_owner_pair_count"]:
        raise ValueError("owner-pair output count drift")
    seen_identities, output_digests = set(), set()
    edge_count_classes, length_classes = set(), set()
    graph_classes, component_count_classes = set(), set()
    for output in outputs:
        if output.get("schema") != "axm.building-owner-seam-component-output/v0.1":
            raise ValueError("pair output schema drift")
        if output.get("authority") != "DERIVED_REPRESENTATIONAL_COMPONENTS_ONLY__NO_PHYSICAL_SEAM_SEMANTICS":
            raise ValueError("pair output authority inflation")
        core = {k: v for k, v in output.items() if k != "pair_output_sha256"}
        if output.get("pair_output_sha256") != canonical_sha256(core):
            raise ValueError("pair output digest drift")
        if output["pair_output_sha256"] in output_digests:
            raise ValueError("pair output digest collision")
        output_digests.add(output["pair_output_sha256"])
        edge_count_classes.add(int(output["edge_count"]))
        length_classes.add(round(float(output["total_length_m"]), bounds["length_class_round_digits"]))
        component_count_classes.add(int(output["connected_component_count"]))
        pair = tuple(output["owner_pair"])
        for component in output["components"]:
            graph_classes.add(component["graph_class"])
            ccore = {k: v for k, v in component.items() if k != "component_sha256"}
            if component.get("component_sha256") != canonical_sha256(ccore):
                raise ValueError("component digest drift")
            for edge in component["source_edges"]:
                identity = (pair, tuple(edge))
                if identity in seen_identities:
                    raise ValueError("source-owner seam emitted more than once")
                seen_identities.add(identity)
    source_identities = {(tuple(r["owner_pair"]), tuple(r["source_edge"])) for r in normalized}
    if seen_identities != source_identities:
        raise ValueError("component outputs do not cover exact source-owner seam set once")
    if sorted(edge_count_classes) != bounds["expected_edge_count_classes"]:
        raise ValueError("material edge-count variation classes drift")
    if sorted(length_classes) != bounds["expected_length_classes_m"]:
        raise ValueError("material seam-length variation classes drift")
    if len(output_digests) != bounds["expected_owner_pair_count"]:
        raise ValueError("owner-pair outputs are not all distinct")
    family_core = {
        "schema": EXPECTED_SCHEMA,
        "family_id": EXPECTED_FAMILY_ID,
        "asset_id": policy["asset_id"],
        "owner_seam_identity_sha256": identity_digest(normalized),
        "owner_seam_edge_count": len(normalized),
        "owner_pair_count": len(outputs),
        "total_owner_seam_length_m": total_length,
        "edge_count_classes": sorted(edge_count_classes),
        "length_classes_m": sorted(length_classes),
        "graph_classes": sorted(graph_classes),
        "connected_component_count_classes": sorted(component_count_classes),
        "pair_outputs": outputs,
        "decision": policy["decision"],
    }
    return {**family_core, "family_sha256": canonical_sha256(family_core)}


def expect_hold(policy: dict, records: list[dict], outputs: list[dict]) -> str:
    try:
        validate_family(policy, records, outputs)
    except (ValueError, KeyError, TypeError) as exc:
        return f"HOLD:{exc}"
    return "UNEXPECTED_PASS"


def build_negative_controls(policy: dict, records: list[dict], outputs: list[dict]) -> dict:
    controls = {}
    duplicate = copy.deepcopy(records); duplicate.append(copy.deepcopy(duplicate[0]))
    controls["duplicate_source_owner_seam"] = expect_hold(policy, duplicate, outputs)
    omitted = copy.deepcopy(records[:-1])
    controls["omitted_source_owner_seam"] = expect_hold(policy, omitted, build_pair_outputs(omitted))
    relabeled = copy.deepcopy(records); relabeled[0]["owner_pair"] = sorted([relabeled[0]["owner_pair"][0], "zz-verifier-mutation"])
    controls["owner_pair_relabel"] = expect_hold(policy, relabeled, build_pair_outputs(relabeled))
    length_drift = copy.deepcopy(records); length_drift[0]["length_m"] += 0.001
    controls["seam_length_drift"] = expect_hold(policy, length_drift, build_pair_outputs(length_drift))
    head_policy = copy.deepcopy(policy); head_policy["source_authority"]["hard_surface_head"] = "0" * 40
    controls["hard_surface_head_drift"] = expect_hold(head_policy, records, outputs)
    physical_policy = copy.deepcopy(policy); physical_policy["family_contract"]["physical_seam_inference"] = True
    controls["physical_seam_authority_expansion"] = expect_hold(physical_policy, records, outputs)
    adoption_policy = copy.deepcopy(policy); adoption_policy["family_contract"]["automatic_receiver_adoption"] = True
    controls["automatic_receiver_adoption"] = expect_hold(adoption_policy, records, outputs)
    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("one or more negative controls unexpectedly passed")
    return controls


def load_exact_hard_surface(hard_surface_root: Path, hard_surface_head: str):
    policy_path = hard_surface_root / "assets" / "service_pavilion_001_compact_boundary_owner_seam_policy.json"
    verifier_path = hard_surface_root / "tools" / "verify_service_pavilion_compact_boundary_owner_seams.py"
    if git_blob_sha1(policy_path) != EXPECTED_HARD_SURFACE_POLICY_BLOB:
        raise ValueError("exact Hard Surface policy bytes drift")
    if git_blob_sha1(verifier_path) != EXPECTED_HARD_SURFACE_VERIFIER_BLOB:
        raise ValueError("exact Hard Surface verifier bytes drift")
    verifier = load_module(verifier_path, "hard_surface_owner_seam_exact_donor")
    donor_policy = verifier.load_policy()
    compact_policy = verifier.load_compact_policy()
    donor_shell, donor_result, compact_mesh, compact_result = verifier.build_exact_meshes(hard_surface_head)
    donor_receipt = verifier.verify(donor_policy, compact_policy, donor_shell, donor_result, compact_mesh, compact_result)
    if donor_receipt.get("result") != EXPECTED_HARD_SURFACE_RESULT:
        raise ValueError("Hard Surface owner-seam donor is not exact PASS")
    if donor_receipt.get("metrics", {}).get("owner_seam_identity_sha256") != EXPECTED_SEAM_IDENTITY_SHA256:
        raise ValueError("Hard Surface donor seam digest drift")
    compact_seams = verifier.seam_records(compact_mesh, compact_mesh.get("source_vertex_ids"))
    if compact_seams.get("identity_sha256") != EXPECTED_SEAM_IDENTITY_SHA256:
        raise ValueError("Hard Surface compact seam records drift")
    return donor_policy, donor_receipt, compact_seams["records"]


def build_evidence(hard_surface_root: Path, hard_surface_head: str) -> dict:
    policy = load_json(POLICY_PATH)
    validate_policy(policy)
    if hard_surface_head != EXPECTED_HARD_SURFACE_HEAD:
        raise ValueError("requested Hard Surface head is not pinned authority head")
    donor_policy, donor_receipt, records = load_exact_hard_surface(hard_surface_root, hard_surface_head)
    outputs = build_pair_outputs(records)
    family = validate_family(policy, records, outputs)
    reversed_records = list(reversed(copy.deepcopy(records)))
    reversed_family = validate_family(policy, reversed_records, build_pair_outputs(reversed_records))
    if family["family_sha256"] != reversed_family["family_sha256"]:
        raise ValueError("family output depends on donor seam iteration order")
    negative = build_negative_controls(policy, records, outputs)
    return {
        "schema": EXPECTED_SCHEMA,
        "result": EXPECTED_RESULT,
        "decision": EXPECTED_DECISION,
        "family_id": EXPECTED_FAMILY_ID,
        "asset_id": policy["asset_id"],
        "source_hard_surface_head": hard_surface_head,
        "source_hard_surface_result": donor_receipt["result"],
        "source_hard_surface_policy_sha256": donor_receipt["policy_sha256"],
        "source_owner_seam_identity_sha256": family["owner_seam_identity_sha256"],
        "owner_seam_edge_count": family["owner_seam_edge_count"],
        "owner_pair_count": family["owner_pair_count"],
        "total_owner_seam_length_m": family["total_owner_seam_length_m"],
        "edge_count_classes": family["edge_count_classes"],
        "length_classes_m": family["length_classes_m"],
        "graph_classes": family["graph_classes"],
        "connected_component_count_classes": family["connected_component_count_classes"],
        "distinct_pair_output_digests": len({item["pair_output_sha256"] for item in outputs}),
        "canonical_order_invariant": True,
        "family_digest": family["family_sha256"],
        "reverse_iteration_family_digest": reversed_family["family_sha256"],
        "outputs": outputs,
        "negative_controls": negative,
        "source_geometry_changed": False,
        "physical_seam_semantics_inferred": False,
        "receiver_adoption_authorized": False,
        "material_or_uv_authority_transferred": False,
        "universal_promotion_authorized": False,
        "truth_boundary": "Procedural partitions the exact Hard-Surface-owned source-owner seam edge set into deterministic owner-pair connected components by donor source-vertex identity. This removes repeated manual partitioning only. It does not create or reinterpret a physical seam, alter source/receiving geometry, select a receiver, or transfer material, UV, transport, runtime, visual or CANON authority.",
        "non_claims": [
            "physical gap, bevel, chamfer, weld, gasket, fastener or material boundary",
            "seam manufacturing method, assembly order, load, tolerance or sealing validity",
            "normal, tangent, UV, texture or material acceptance",
            "Geometry compaction adoption or Hard-Surface source replacement",
            "Technical Art transport, Environment adoption, Runtime performance or target-device acceptance",
            "Art Direction or Visual QA acceptance",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness or Procedural Design mastery"
        ],
        "source_owner_seam_policy": donor_policy,
        "source_owner_seam_receipt": donor_receipt,
    }


def write_evidence(summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "source-owner-seam-policy.json").write_text(json.dumps(summary["source_owner_seam_policy"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "source-owner-seam-receipt.json").write_text(json.dumps(summary["source_owner_seam_receipt"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for item in summary["outputs"]:
        pair_id = "__".join(item["owner_pair"])
        (output_dir / f"pair-{pair_id}.json").write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hard-surface-root", required=True, type=Path)
    parser.add_argument("--hard-surface-head", default=EXPECTED_HARD_SURFACE_HEAD)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = build_evidence(args.hard_surface_root.resolve(), args.hard_surface_head)
    write_evidence(summary, args.output_dir)
    print(json.dumps({
        "result": summary["result"],
        "family_digest": summary["family_digest"],
        "owner_pair_count": summary["owner_pair_count"],
        "edge_count_classes": summary["edge_count_classes"],
        "length_classes_m": summary["length_classes_m"],
        "graph_classes": summary["graph_classes"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
