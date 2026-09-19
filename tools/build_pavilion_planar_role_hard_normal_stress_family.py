#!/usr/bin/env python3
"""Build deterministic Procedural stress cohorts from the exact Building hard-normal quotient.

Hard Surface owns the 604-class render equivalence. Geometry owns the exact 312-group
attribute-dropping diagnostic. Procedural only partitions that already-proven quotient into
bounded review cohorts so downstream consumers can exercise materially different hard-normal
boundary cases without hand-picking groups or silently promoting the quotient to source truth.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILY_POLICY_PATH = ROOT / "procedural" / "service_pavilion_planar_role_hard_normal_stress_family_001.json"
HARD_SURFACE_POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_hard_normal_authority_policy.json"
HARD_SURFACE_TOOL_PATH = ROOT / "tools" / "verify_service_pavilion_planar_role_hard_normal_authority.py"
GEOMETRY_POLICY_PATH = ROOT / "assets" / "service_pavilion_001_planar_role_normal_boundary_quotient_policy.json"
GEOMETRY_TOOL_PATH = ROOT / "tools" / "analyze_service_pavilion_planar_role_normal_boundary_quotient.py"

EXPECTED_HARD_SURFACE_HEAD = "7b86b1a9da1ef8dc670ca01cf4918728e68ece92"
EXPECTED_HARD_SURFACE_POLICY_BLOB = "598d06f09b7e0c05690e38b9cb12300132498ea2"
EXPECTED_HARD_SURFACE_RESULT = "PASS_SOURCE_OWNED_PLANAR_ROLE_HARD_NORMAL_AUTHORITY_BOUNDARY"
EXPECTED_GEOMETRY_HEAD = "7dfb1153dc5f80bcbf1b48803f044236d4ebb030"
EXPECTED_GEOMETRY_POLICY_BLOB = "e66d3704a908f191fc959422818899556d432511"
EXPECTED_GEOMETRY_TOOL_BLOB = "f3ce268cc0d25fa1ced48053416c60f1208cf4ba"
EXPECTED_SOURCE_REBIND_HEAD = "fcf3c2a0d3f2f7ee973fb0d7f090f65abf9b8c4e"
EXPECTED_GEOMETRY_QUOTIENT_SHA256 = "3ab469a8033f139370f278b8b4940512594262ea5291991ff086952a5959989e"
EXPECTED_GEOMETRY_RESULT = "PASS_HARD_NORMAL_IDENTITY_REMOVAL_YIELDS_EXACT_312_GROUP_STRUCTURAL_QUOTIENT"
EXPECTED_RESULT = "PASS_BOUNDED_PLANAR_ROLE_HARD_NORMAL_STRESS_FAMILY"
EXPECTED_DECISION = "PASS_DIAGNOSTIC_STRESS_COHORT_FAMILY_ONLY__NO_RECEIVER_OR_SOURCE_ADOPTION"

EXPECTED_COHORTS = {
    "single-normal-control": {
        "distinct_source_normal_count": 1,
        "expected_quotient_group_count": 124,
        "expected_source_render_identity_count": 124,
        "classification": "CONTROL_NO_HARD_NORMAL_BOUNDARY_CROSS",
    },
    "two-normal-boundary": {
        "distinct_source_normal_count": 2,
        "expected_quotient_group_count": 84,
        "expected_source_render_identity_count": 168,
        "classification": "TWO_WAY_HARD_NORMAL_BOUNDARY_STRESS",
    },
    "three-normal-boundary": {
        "distinct_source_normal_count": 3,
        "expected_quotient_group_count": 104,
        "expected_source_render_identity_count": 312,
        "classification": "THREE_WAY_HARD_NORMAL_BOUNDARY_STRESS",
    },
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_policy(policy: dict) -> None:
    if policy.get("schema") != "axm.building-planar-role-hard-normal-stress-family/v0.1":
        raise ValueError("Procedural family schema drift")
    if policy.get("asset_id") != "service-pavilion-001" or policy.get("owner") != "Procedural Design":
        raise ValueError("Procedural family identity/owner drift")

    authority = policy.get("source_authority", {})
    if authority.get("source_rebind_head") != EXPECTED_SOURCE_REBIND_HEAD:
        raise ValueError("source-rebind identity drift")
    if authority.get("hard_surface_pr") != 14 or authority.get("hard_surface_head") != EXPECTED_HARD_SURFACE_HEAD:
        raise ValueError("Hard Surface authority identity drift")
    if authority.get("hard_surface_policy_git_blob_sha") != EXPECTED_HARD_SURFACE_POLICY_BLOB:
        raise ValueError("declared Hard Surface policy blob drift")
    if git_blob_sha1(HARD_SURFACE_POLICY_PATH) != EXPECTED_HARD_SURFACE_POLICY_BLOB:
        raise ValueError("Hard Surface policy bytes drift")
    if authority.get("geometry_pr") != 13 or authority.get("geometry_head") != EXPECTED_GEOMETRY_HEAD:
        raise ValueError("Geometry diagnostic identity drift")
    if authority.get("geometry_policy_git_blob_sha") != EXPECTED_GEOMETRY_POLICY_BLOB:
        raise ValueError("declared Geometry policy blob drift")
    if git_blob_sha1(GEOMETRY_POLICY_PATH) != EXPECTED_GEOMETRY_POLICY_BLOB:
        raise ValueError("Geometry policy bytes drift")
    if authority.get("geometry_tool_git_blob_sha") != EXPECTED_GEOMETRY_TOOL_BLOB:
        raise ValueError("declared Geometry tool blob drift")
    if git_blob_sha1(GEOMETRY_TOOL_PATH) != EXPECTED_GEOMETRY_TOOL_BLOB:
        raise ValueError("Geometry tool bytes drift")
    if authority.get("geometry_quotient_sha256") != EXPECTED_GEOMETRY_QUOTIENT_SHA256:
        raise ValueError("declared Geometry quotient digest drift")

    declared = {entry.get("cohort_id"): entry for entry in policy.get("cohorts", [])}
    if set(declared) != set(EXPECTED_COHORTS):
        raise ValueError("Procedural cohort allowlist drift")
    for cohort_id, expected in EXPECTED_COHORTS.items():
        if declared[cohort_id] != {"cohort_id": cohort_id, **expected}:
            raise ValueError(f"Procedural cohort declaration drift: {cohort_id}")

    invariants = policy.get("family_invariants", {})
    if invariants.get("expected_total_quotient_groups") != 312:
        raise ValueError("quotient group bound drift")
    if invariants.get("expected_total_source_render_identities") != 604:
        raise ValueError("source render identity bound drift")
    for key in (
        "cohorts_must_be_disjoint",
        "cohorts_must_cover_all_quotient_groups",
        "source_render_identities_must_be_covered_exactly_once",
        "preserve_material_role",
        "preserve_exact_position",
        "preserve_protected_split_id",
    ):
        if invariants.get(key) is not True:
            raise ValueError(f"required family invariant weakened: {key}")
    for key in (
        "emit_product_mesh",
        "automatic_receiver_adoption",
        "source_rewrite",
        "normal_generation_or_repacking",
        "implicit_fallback",
    ):
        if invariants.get(key) is not False:
            raise ValueError(f"authority inflation or fallback enabled: {key}")
    if policy.get("universal_promotion") != (
        "HELD_UNTIL_MATERIALLY_DIFFERENT_DOMAIN_REPRODUCES_THE_SAME_STRESS_COHORT_NEED"
    ):
        raise ValueError("premature universal promotion")


def validate_donors(hard_surface_evidence: dict, geometry_evidence: dict) -> None:
    if hard_surface_evidence.get("result") != EXPECTED_HARD_SURFACE_RESULT:
        raise ValueError("Hard Surface authority evidence is not the pinned PASS")
    if hard_surface_evidence.get("geometry_diagnostic_head") != EXPECTED_GEOMETRY_HEAD:
        raise ValueError("Hard Surface authority references a different Geometry diagnostic")
    if hard_surface_evidence.get("geometry_quotient_sha256") != EXPECTED_GEOMETRY_QUOTIENT_SHA256:
        raise ValueError("Hard Surface authority quotient digest drift")
    if hard_surface_evidence.get("geometry_source_rebind_head") != EXPECTED_SOURCE_REBIND_HEAD:
        raise ValueError("Hard Surface source-rebind identity drift")
    classification = hard_surface_evidence.get("classification", {})
    if classification.get("source_604") != "SOURCE_AUTHORIZED_RENDER_EQUIVALENCE":
        raise ValueError("Hard Surface 604-class authority weakened")
    if classification.get("quotient_312") != "DERIVED_ATTRIBUTE_DROPPING_PARTITION_NOT_SOURCE_EQUIVALENT":
        raise ValueError("Hard Surface 312 quotient was promoted")

    if geometry_evidence.get("result") != EXPECTED_GEOMETRY_RESULT:
        raise ValueError("Geometry quotient evidence is not the pinned PASS")
    if geometry_evidence.get("parent_geometry_head") != "b9b4ab63e23b9756ab79597e86ecc41ea75ea8b7":
        raise ValueError("Geometry parent indexed-domain identity drift")
    if geometry_evidence.get("parent_geometry_source_rebind_head") != EXPECTED_SOURCE_REBIND_HEAD:
        raise ValueError("Geometry source-rebind identity drift")
    if geometry_evidence.get("quotient_sha256") != EXPECTED_GEOMETRY_QUOTIENT_SHA256:
        raise ValueError("Geometry quotient digest drift")
    metrics = geometry_evidence.get("metrics", {})
    expected_metrics = {
        "parent_render_vertex_count": 604,
        "diagnostic_quotient_group_count": 312,
        "single_source_group_count": 124,
        "two_hard_normal_group_count": 84,
        "three_hard_normal_group_count": 104,
        "hard_normal_crossing_group_count": 188,
        "maximum_source_hard_normals_per_quotient_group": 3,
    }
    for key, expected in expected_metrics.items():
        if metrics.get(key) != expected:
            raise ValueError(f"Geometry quotient metric drift: {key}")


def group_record(group: dict) -> dict:
    return {
        "quotient_group_index": int(group["quotient_group_index"]),
        "material_role": group["material_role"],
        "position": list(group["position"]),
        "protected_split_id": group["protected_split_id"],
        "source_render_vertex_indices": sorted(int(v) for v in group["source_render_vertex_indices"]),
        "distinct_source_normal_count": int(group["distinct_source_normal_count"]),
    }


def build_cohorts(quotient: dict) -> dict[str, dict]:
    groups = sorted(quotient["groups"], key=lambda group: int(group["quotient_group_index"]))
    outputs: dict[str, dict] = {}
    for cohort_id, spec in EXPECTED_COHORTS.items():
        members = [
            group_record(group)
            for group in groups
            if int(group["distinct_source_normal_count"]) == spec["distinct_source_normal_count"]
        ]
        core = {
            "schema": "axm.building-planar-role-hard-normal-stress-cohort/v0.1",
            "family_id": "service-pavilion-planar-role-hard-normal-stress-family-001",
            "cohort_id": cohort_id,
            "classification": spec["classification"],
            "distinct_source_normal_count": spec["distinct_source_normal_count"],
            "quotient_group_count": len(members),
            "source_render_identity_count": sum(len(group["source_render_vertex_indices"]) for group in members),
            "groups": members,
            "authority": "DIAGNOSTIC_COHORT_ONLY__NOT_SOURCE_EQUIVALENCE_NOT_RECEIVER_ADOPTION",
        }
        outputs[cohort_id] = {**core, "cohort_sha256": canonical_sha256(core)}
    return outputs


def validate_outputs(policy: dict, quotient: dict, outputs: dict[str, dict]) -> None:
    validate_policy(policy)
    if set(outputs) != set(EXPECTED_COHORTS):
        raise ValueError("unsupported or missing cohort output")

    quotient_by_index = {int(group["quotient_group_index"]): group_record(group) for group in quotient["groups"]}
    if set(quotient_by_index) != set(range(312)):
        raise ValueError("Geometry quotient group-index domain drift")

    seen_groups: set[int] = set()
    seen_source_vertices: set[int] = set()
    digests: set[str] = set()

    for cohort_id, spec in EXPECTED_COHORTS.items():
        output = outputs[cohort_id]
        if output.get("schema") != "axm.building-planar-role-hard-normal-stress-cohort/v0.1":
            raise ValueError(f"cohort schema drift: {cohort_id}")
        if output.get("classification") != spec["classification"]:
            raise ValueError(f"cohort classification drift: {cohort_id}")
        if output.get("distinct_source_normal_count") != spec["distinct_source_normal_count"]:
            raise ValueError(f"cohort normal cardinality drift: {cohort_id}")
        if output.get("quotient_group_count") != spec["expected_quotient_group_count"]:
            raise ValueError(f"cohort quotient count drift: {cohort_id}")
        if output.get("source_render_identity_count") != spec["expected_source_render_identity_count"]:
            raise ValueError(f"cohort source-identity count drift: {cohort_id}")
        if output.get("authority") != "DIAGNOSTIC_COHORT_ONLY__NOT_SOURCE_EQUIVALENCE_NOT_RECEIVER_ADOPTION":
            raise ValueError(f"cohort authority inflation: {cohort_id}")

        core = {key: value for key, value in output.items() if key != "cohort_sha256"}
        if output.get("cohort_sha256") != canonical_sha256(core):
            raise ValueError(f"cohort digest drift: {cohort_id}")
        digests.add(output["cohort_sha256"])

        groups = output.get("groups", [])
        if len(groups) != spec["expected_quotient_group_count"]:
            raise ValueError(f"cohort group payload count drift: {cohort_id}")
        for record in groups:
            index = int(record["quotient_group_index"])
            if index in seen_groups:
                raise ValueError("quotient group appears in more than one Procedural cohort")
            if record != quotient_by_index.get(index):
                raise ValueError("Procedural cohort record differs from exact Geometry quotient")
            if int(record["distinct_source_normal_count"]) != spec["distinct_source_normal_count"]:
                raise ValueError("Procedural cohort contains wrong hard-normal cardinality")
            seen_groups.add(index)
            for source_vertex in record["source_render_vertex_indices"]:
                source_vertex = int(source_vertex)
                if source_vertex in seen_source_vertices:
                    raise ValueError("source render identity appears in more than one Procedural cohort")
                seen_source_vertices.add(source_vertex)

    if len(digests) != 3:
        raise ValueError("Procedural cohort outputs are not materially distinct by digest")
    if seen_groups != set(range(312)):
        raise ValueError("Procedural cohorts do not cover the exact 312-group quotient")
    if seen_source_vertices != set(range(604)):
        raise ValueError("Procedural cohorts do not cover the exact 604 source render identities")


def expect_rejection(policy: dict, quotient: dict, outputs: dict[str, dict]) -> str:
    try:
        validate_outputs(policy, quotient, outputs)
    except ValueError as exc:
        return f"REJECTED:{exc}"
    return "UNEXPECTED_PASS"


def negative_controls(policy: dict, quotient: dict, outputs: dict[str, dict]) -> dict:
    controls = {}

    unsupported = copy.deepcopy(outputs)
    unsupported["four-normal-boundary"] = copy.deepcopy(outputs["single-normal-control"])
    unsupported["four-normal-boundary"]["cohort_id"] = "four-normal-boundary"
    controls["unsupported_four_normal_cohort"] = expect_rejection(policy, quotient, unsupported)

    duplicate = copy.deepcopy(outputs)
    duplicate["two-normal-boundary"]["groups"].append(
        copy.deepcopy(duplicate["single-normal-control"]["groups"][0])
    )
    duplicate["two-normal-boundary"]["quotient_group_count"] += 1
    controls["duplicate_group_across_cohorts"] = expect_rejection(policy, quotient, duplicate)

    omitted = copy.deepcopy(outputs)
    omitted["three-normal-boundary"]["groups"].pop()
    omitted["three-normal-boundary"]["quotient_group_count"] -= 1
    omitted["three-normal-boundary"]["source_render_identity_count"] -= 3
    controls["omitted_three_normal_group"] = expect_rejection(policy, quotient, omitted)

    source_drift = copy.deepcopy(outputs)
    source_drift["single-normal-control"]["groups"][0]["source_render_vertex_indices"][0] = 999
    controls["source_render_identity_drift"] = expect_rejection(policy, quotient, source_drift)

    authority_drift = copy.deepcopy(policy)
    authority_drift["source_authority"]["hard_surface_head"] = "0" * 40
    controls["hard_surface_authority_head_drift"] = expect_rejection(authority_drift, quotient, outputs)

    adoption = copy.deepcopy(policy)
    adoption["family_invariants"]["automatic_receiver_adoption"] = True
    controls["automatic_receiver_adoption"] = expect_rejection(adoption, quotient, outputs)

    return controls


def build_evidence(exact_head: str) -> tuple[dict[str, dict], dict]:
    policy = load_json(FAMILY_POLICY_PATH)
    validate_policy(policy)

    hard_surface = load_module(HARD_SURFACE_TOOL_PATH, "building_hard_normal_authority_for_procedural")
    hard_surface_evidence = hard_surface.build_evidence(exact_head)

    geometry = load_module(GEOMETRY_TOOL_PATH, "building_hard_normal_quotient_for_procedural")
    quotient, geometry_evidence = geometry.build_evidence(exact_head)
    validate_donors(hard_surface_evidence, geometry_evidence)

    outputs = build_cohorts(quotient)
    validate_outputs(policy, quotient, outputs)

    replay = build_cohorts({"groups": list(reversed(quotient["groups"]))})
    if {key: value["cohort_sha256"] for key, value in replay.items()} != {
        key: value["cohort_sha256"] for key, value in outputs.items()
    }:
        raise ValueError("Procedural cohort output is sensitive to donor group iteration order")

    controls = negative_controls(policy, quotient, outputs)
    if not controls or not all(str(value).startswith("REJECTED:") for value in controls.values()):
        raise ValueError(f"one or more Procedural negative controls did not fail closed: {controls}")

    output_summary = {
        cohort_id: {
            "quotient_group_count": output["quotient_group_count"],
            "source_render_identity_count": output["source_render_identity_count"],
            "distinct_source_normal_count": output["distinct_source_normal_count"],
            "cohort_sha256": output["cohort_sha256"],
        }
        for cohort_id, output in outputs.items()
    }

    evidence = {
        "schema": "axm.building-planar-role-hard-normal-stress-family-evidence/v0.1",
        "result": EXPECTED_RESULT,
        "decision": EXPECTED_DECISION,
        "exact_head": exact_head,
        "asset_id": "service-pavilion-001",
        "family_id": policy["family_id"],
        "family_policy_sha256": canonical_sha256(policy),
        "hard_surface_authority_head": EXPECTED_HARD_SURFACE_HEAD,
        "hard_surface_authority_result": hard_surface_evidence["result"],
        "geometry_diagnostic_head": EXPECTED_GEOMETRY_HEAD,
        "source_rebind_head": EXPECTED_SOURCE_REBIND_HEAD,
        "geometry_diagnostic_result": geometry_evidence["result"],
        "geometry_quotient_sha256": geometry_evidence["quotient_sha256"],
        "source_authorized_render_identity_count": 604,
        "diagnostic_quotient_group_count": 312,
        "cohort_count": 3,
        "distinct_cohort_digests": len({output["cohort_sha256"] for output in outputs.values()}),
        "cohorts_cover_all_312_quotient_groups_exactly_once": True,
        "cohorts_cover_all_604_source_render_identities_exactly_once": True,
        "canonical_replay_under_reversed_input_order": "PASS_EXACT_COHORT_DIGESTS_REPRODUCED",
        "outputs": output_summary,
        "negative_controls": controls,
        "source_mesh_changed": False,
        "source_equivalence_changed": False,
        "product_mesh_emitted": False,
        "normal_field_generated_or_repacked": False,
        "receiver_adoption": False,
        "uc_or_profession_fabric_changed": False,
        "truth_boundary": policy["truth_boundary"],
    }
    return outputs, evidence


def write_evidence(outputs: dict[str, dict], evidence: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "exact-head.txt").write_text(evidence["exact_head"] + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for cohort_id, output in outputs.items():
        (output_dir / f"{cohort_id}.json").write_text(
            json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    for source in (FAMILY_POLICY_PATH, HARD_SURFACE_POLICY_PATH, GEOMETRY_POLICY_PATH):
        (output_dir / source.name).write_bytes(source.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs, evidence = build_evidence(args.exact_head)
    write_evidence(outputs, evidence, args.output_dir)
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
