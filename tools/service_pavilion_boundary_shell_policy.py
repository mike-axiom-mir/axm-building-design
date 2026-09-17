#!/usr/bin/env python3
"""Source-owner gate for the Building boundary-only receiving representation.

The current 23-box Building representation remains semantic source truth. This gate
source-owns only the policy that a separately derived boundary-only shell may be used
by explicit render/transport/material receivers after they rebind and retest it.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "assets" / "service_pavilion_001_boundary_shell_policy.json"
CANDIDATE_TOOL = ROOT / "tools" / "build_service_pavilion_union_shell_candidate.py"
GEOMETRY_EVIDENCE_HEAD = "b6d14d48c59859ae6ff2aaed7dea86b4e00a5402"
EPS = 1e-9


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text())


def build_candidate_receipt(exact_head: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="axm-building-boundary-shell-") as temp_dir:
        output = Path(temp_dir)
        subprocess.run(
            [
                sys.executable,
                str(CANDIDATE_TOOL),
                "--exact-head",
                exact_head,
                "--output-dir",
                str(output),
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return json.loads((output / "boundary-shell-evidence.json").read_text())


def verify_policy(policy: dict, candidate: dict) -> dict:
    if policy.get("schema") != "axm.building-boundary-shell-policy/v0.1":
        raise ValueError("boundary-shell policy schema drift")
    if policy.get("asset_id") != "service-pavilion-001":
        raise ValueError("boundary-shell policy asset drift")

    semantic = policy.get("semantic_source", {})
    if semantic.get("schema") != "axm.building-current-emission-policy/v0.1":
        raise ValueError("semantic-source schema drift")
    if semantic.get("variant_id") != "header-segmented-23":
        raise ValueError("semantic source must remain current header-segmented-23")
    if semantic.get("emitted_box_count") != 23:
        raise ValueError("semantic source box-count drift")
    if semantic.get("authority") != "SEMANTIC_SOURCE_OF_TRUTH":
        raise ValueError("semantic source authority weakened")

    derived = policy.get("derived_representation", {})
    if derived.get("schema") != "axm.building-current-source-boundary-shell/v0.1":
        raise ValueError("derived representation schema drift")
    if derived.get("representation_id") != "boundary-only-union-shell-001":
        raise ValueError("derived representation identity drift")
    if derived.get("geometry_evidence_head") != GEOMETRY_EVIDENCE_HEAD:
        raise ValueError("Geometry evidence head drift")
    if derived.get("status") != "SOURCE_OWNED_DERIVED_REPRESENTATION_NOT_SEMANTIC_SOURCE":
        raise ValueError("derived representation authority drift")
    if policy.get("selection_policy") != "SEMANTIC_BOXES_REMAIN_AUTHORITY__BOUNDARY_SHELL_REQUIRES_EXPLICIT_CONSUMER_REBIND":
        raise ValueError("selection policy drift")
    if policy.get("provenance_policy") != "PRESERVE_SOURCE_COMPONENT_ID_ON_EVERY_BOUNDARY_TRIANGLE":
        raise ValueError("boundary provenance policy drift")
    if policy.get("fallback_policy") != "NO_IMPLICIT_REPRESENTATION_FALLBACK":
        raise ValueError("implicit representation fallback is forbidden")

    if candidate.get("schema") != derived["schema"]:
        raise ValueError("candidate schema does not match source-owned receiving policy")
    if candidate.get("result") != "PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE":
        raise ValueError("Geometry boundary-shell prerequisite is not PASS")
    current = candidate.get("current_source_policy", {})
    if current.get("variant_id") != semantic["variant_id"]:
        raise ValueError("candidate semantic-source variant drift")
    source = candidate.get("source", {})
    shell = candidate.get("candidate", {})
    if source.get("emitted_box_count") != semantic["emitted_box_count"]:
        raise ValueError("candidate source box-count drift")
    if source.get("positive_volume_intersection_count") != 0:
        raise ValueError("candidate prerequisite source regained positive-volume overlap")
    if abs(float(shell.get("signed_volume_m3", 0.0)) - float(source.get("occupied_union_volume_m3", 0.0))) > EPS:
        raise ValueError("boundary shell no longer preserves occupied union volume")
    if shell.get("bounds") != source.get("bounds"):
        raise ValueError("boundary shell bounds drift")
    for key in (
        "boundary_edge_count",
        "nonmanifold_edge_count",
        "orientation_conflict_edge_count",
        "degenerate_triangle_count",
        "isolated_vertex_count",
        "disconnected_vertex_fan_count",
        "internal_face_count_by_construction",
    ):
        if shell.get(key) != 0:
            raise ValueError(f"boundary shell structural gate failed: {key}={shell.get(key)}")
    if shell.get("max_vertex_fan_components") != 1:
        raise ValueError("boundary shell vertex-fan connectivity drift")
    if shell.get("source_component_owner_count") != 19:
        raise ValueError("boundary shell source-component ownership coverage drift")
    removal = candidate.get("internal_face_removal", {})
    if removal.get("contact_patch_count", 0) <= 0:
        raise ValueError("boundary shell no longer proves internal-contact removal")
    if removal.get("double_sided_hidden_area_removed_m2", 0.0) <= 0.0:
        raise ValueError("boundary shell hidden-area removal disappeared")

    return {
        "schema": policy["schema"],
        "result": "PASS_SOURCE_OWNED_BOUNDARY_SHELL_RECEIVING_POLICY",
        "asset_id": policy["asset_id"],
        "policy_revision": policy["policy_revision"],
        "semantic_source": copy.deepcopy(semantic),
        "derived_representation": copy.deepcopy(derived),
        "selection_policy": policy["selection_policy"],
        "provenance_policy": policy["provenance_policy"],
        "fallback_policy": policy["fallback_policy"],
        "candidate_metrics": {
            "semantic_box_count": source["emitted_box_count"],
            "solid_component_count": candidate["partition"]["solid_component_count"],
            "boundary_vertex_count": shell["vertex_count"],
            "boundary_triangle_count": shell["triangle_count"],
            "boundary_surface_area_m2": shell["surface_area_m2"],
            "occupied_union_volume_m3": source["occupied_union_volume_m3"],
            "contact_patch_count": removal["contact_patch_count"],
            "double_sided_hidden_area_removed_m2": removal["double_sided_hidden_area_removed_m2"],
            "source_component_owner_count": shell["source_component_owner_count"],
        },
        "policy_sha256": canonical_sha256(policy),
        "candidate_payload_sha256": shell["payload_sha256"],
        "truth_boundary": (
            "The 23 named source boxes remain semantic authority. This PASS source-owns only an explicit "
            "receiving policy for the exact boundary-only derived shell, preserving per-boundary source-component "
            "provenance and requiring every consumer to opt in, rebind and retest."
        ),
        "non_claims": [
            "replacement of the 23-box semantic source or historical 19-box compatibility contract",
            "single connected solid; the exact boundary candidate currently contains four face-connected solids",
            "triangle or vertex optimization, LOD quality, UVs, normals, tangents or final materials",
            "target-host visual acceptance or shading equivalence",
            "runtime, draw-call, memory, collision, navigation, physics or gameplay acceptance",
            "architectural engineering, manufacturing validity, tolerances, loads or sealing",
            "general boolean union for rotated, curved or arbitrary meshes",
            "Universal Creation or Profession Fabric promotion",
            "CANON, production/game readiness or Hard-Surface mastery"
        ],
    }


def rejected(fn) -> str:
    try:
        fn()
    except (ValueError, KeyError) as exc:
        return f"REJECTED:{exc}"
    raise AssertionError("negative control unexpectedly accepted")


def build_receipt(exact_head: str) -> dict:
    policy = load_policy()
    candidate = build_candidate_receipt(exact_head)
    receipt = verify_policy(policy, candidate)

    bad_variant = copy.deepcopy(policy)
    bad_variant["semantic_source"]["variant_id"] = "base-closed-outward-19"
    bad_head = copy.deepcopy(policy)
    bad_head["derived_representation"]["geometry_evidence_head"] = "0" * 40
    bad_fallback = copy.deepcopy(policy)
    bad_fallback["fallback_policy"] = "ALLOW_DEFAULT_FALLBACK"
    bad_owner = copy.deepcopy(candidate)
    bad_owner["candidate"]["source_component_owner_count"] = 18
    bad_internal = copy.deepcopy(candidate)
    bad_internal["candidate"]["internal_face_count_by_construction"] = 1

    receipt["exact_hard_surface_head"] = exact_head
    receipt["geometry_evidence_head"] = GEOMETRY_EVIDENCE_HEAD
    receipt["negative_controls"] = {
        "semantic_source_variant_drift": rejected(lambda: verify_policy(bad_variant, candidate)),
        "geometry_evidence_head_drift": rejected(lambda: verify_policy(bad_head, candidate)),
        "implicit_fallback": rejected(lambda: verify_policy(bad_fallback, candidate)),
        "source_component_provenance_loss": rejected(lambda: verify_policy(policy, bad_owner)),
        "reintroduced_internal_face": rejected(lambda: verify_policy(policy, bad_internal)),
    }
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    subprocess.run(
        ["git", "merge-base", "--is-ancestor", GEOMETRY_EVIDENCE_HEAD, args.exact_head],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    receipt = build_receipt(args.exact_head)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "exact-head.txt").write_text(args.exact_head + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
