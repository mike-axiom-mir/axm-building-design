#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER_TOOL = ROOT / "tools/build_pavilion_utility_panel_receivers.py"
PINNED_UC_HEAD = "bd51542bc68534a6e6f3a11d421dc70216b2abf9"
UC_PLACEMENT_PATH = Path("src/axm_stickers/placement.py")
SOCKET_KIND = "axm-building-neutral-rigid-frame-equivalence-probe"


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"unable to load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git_head(repo_root):
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def target_frame(center, basis):
    normal, lateral, up = basis
    return [
        float(normal[0]), float(lateral[0]), float(up[0]), float(center[0]),
        float(normal[1]), float(lateral[1]), float(up[1]), float(center[1]),
        float(normal[2]), float(lateral[2]), float(up[2]), float(center[2]),
        0.0, 0.0, 0.0, 1.0,
    ]


def apply_matrix(matrix, point):
    x, y, z = [float(value) for value in point]
    return [
        matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3],
        matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7],
        matrix[8] * x + matrix[9] * y + matrix[10] * z + matrix[11],
    ]


def exact_neutral_attachment_matrix(shared, frame):
    identity = shared.identity()
    definition = {
        "attachment": {
            "space": "3d",
            "socket": SOCKET_KIND,
            "anchor": identity,
        }
    }
    placed = {"placement": {"offset": identity, "scale": 1.0}}
    target = {"space": "3d", "socket": SOCKET_KIND, "frame": frame}
    matrix = shared.attachment_matrix(definition, placed, target)
    if matrix != frame:
        raise ValueError("shared neutral attachment matrix changed the exact target frame")
    return matrix


def negative_controls(shared, valid_frame):
    controls = {}

    reflected = list(valid_frame)
    reflected[0] *= -1.0
    reflected[4] *= -1.0
    reflected[8] *= -1.0
    try:
        exact_neutral_attachment_matrix(shared, reflected)
        controls["reflected_target_frame"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["reflected_target_frame"] = "HOLD: " + str(exc)

    definition = {
        "attachment": {
            "space": "3d",
            "socket": SOCKET_KIND,
            "anchor": shared.identity(),
        }
    }
    placed = {"placement": {"offset": shared.identity(), "scale": 1.0}}
    target = {"space": "3d", "socket": SOCKET_KIND + "-wrong", "frame": valid_frame}
    try:
        shared.attachment_matrix(definition, placed, target)
        controls["socket_identity_mismatch"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["socket_identity_mismatch"] = "HOLD: " + str(exc)

    placed_scaled = {"placement": {"offset": shared.identity(), "scale": 1.001}}
    target_ok = {"space": "3d", "socket": SOCKET_KIND, "frame": valid_frame}
    scaled = shared.attachment_matrix(definition, placed_scaled, target_ok)
    if scaled == valid_frame:
        controls["non_unit_scale_changes_frame"] = "UNEXPECTED_PASS"
    else:
        controls["non_unit_scale_changes_frame"] = "HOLD: non-unit scale is not exact neutral placement"

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("shared-frame equivalence negative control unexpectedly passed")
    return controls


def build(uc_root):
    uc_root = Path(uc_root).resolve()
    observed_uc_head = git_head(uc_root)
    if observed_uc_head != PINNED_UC_HEAD:
        raise ValueError(
            f"shared-frame donor head drift: {observed_uc_head} != {PINNED_UC_HEAD}"
        )

    shared_path = uc_root / UC_PLACEMENT_PATH
    if not shared_path.is_file():
        raise ValueError(f"shared placement module missing: {shared_path}")

    receiver_mod = load_module(RECEIVER_TOOL, "build_pavilion_utility_panel_receivers")
    shared = load_module(shared_path, "axm_shared_placement_probe")

    existing = receiver_mod.build()
    if existing.get("result") != "PASS_EXACT_UTILITY_PANEL_RECEIVER_PLACEMENT_FAMILY":
        raise ValueError("existing Building receiver family prerequisite is not PASS")
    if existing.get("receiver_count") != 2:
        raise ValueError("expected the exact two-receiver Building family")

    hard_surface = receiver_mod.load_hard_surface_builder()
    panel = receiver_mod.load(receiver_mod.PANEL)
    size = [float(value) for value in panel["proof_geometry"]["size_local_xyz_m"]]
    local_vertices = hard_surface.box_vertices(
        [0.0, 0.0, 0.0],
        size,
        ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]),
    )
    local_digest = digest_json(local_vertices)

    rows = []
    for current in existing["placements"]:
        frame = target_frame(
            current["center_m"],
            current["basis_normal_lateral_up"],
        )
        matrix = exact_neutral_attachment_matrix(shared, frame)
        shared_vertices = [apply_matrix(matrix, point) for point in local_vertices]
        residual = max(
            abs(observed - expected)
            for observed_vertex, expected_vertex in zip(
                shared_vertices, current["vertices"]
            )
            for observed, expected in zip(observed_vertex, expected_vertex)
        )
        shared_mesh_digest = digest_json(shared_vertices)
        exact_vertices = shared_vertices == current["vertices"]
        exact_mesh_digest = shared_mesh_digest == current["mesh_digest"]
        if not exact_vertices or not exact_mesh_digest or residual != 0.0:
            raise ValueError(
                f"{current['receiver_id']}: shared rigid-frame path is not exact "
                f"(vertices={exact_vertices}, digest={exact_mesh_digest}, residual={residual})"
            )

        rows.append(
            {
                "receiver_id": current["receiver_id"],
                "target_frame": frame,
                "target_frame_digest": digest_json(frame),
                "local_vertices_digest": local_digest,
                "existing_mesh_digest": current["mesh_digest"],
                "shared_mesh_digest": shared_mesh_digest,
                "exact_vertex_list_match": exact_vertices,
                "exact_mesh_digest_match": exact_mesh_digest,
                "maximum_position_residual_m": residual,
            }
        )

    if len({row["target_frame_digest"] for row in rows}) != 2:
        raise ValueError("shared-frame probe did not retain two distinct target frames")
    if len({row["shared_mesh_digest"] for row in rows}) != 2:
        raise ValueError("shared-frame probe did not retain two distinct transformed outputs")

    controls = negative_controls(shared, rows[0]["target_frame"])

    return {
        "schema": "axm.building-shared-rigid-frame-equivalence-evidence/v0.1",
        "result": "PASS_EXACT_SHARED_RIGID_FRAME_EQUIVALENCE_BUILDING_RECEIVERS",
        "authority": "RECEIVING_DOMAIN_EQUIVALENCE_PROBE_ONLY",
        "consolidation_decision": "HOLD_SHARED_CONSOLIDATION_PENDING_OBJECT_DOMAIN_EQUIVALENCE",
        "building_family_result": existing["result"],
        "building_receiver_count": existing["receiver_count"],
        "building_receiver_ids": existing["receiver_ids"],
        "building_transform_policy": existing["transform_policy"],
        "shared_donor_repo": "mike-axiom-mir/axm-universal-creation",
        "shared_donor_head": observed_uc_head,
        "shared_donor_module": str(UC_PLACEMENT_PATH),
        "shared_donor_module_sha256": sha256(shared_path),
        "shared_capability": "renderer-independent rigid 3D attachment matrix",
        "probe_socket_kind": SOCKET_KIND,
        "source_anchor": "identity",
        "local_offset": "identity",
        "scale": 1.0,
        "local_vertices_digest": local_digest,
        "exact_receiver_equivalence_count": sum(
            row["exact_vertex_list_match"] and row["exact_mesh_digest_match"]
            for row in rows
        ),
        "distinct_target_frame_digests": len(
            {row["target_frame_digest"] for row in rows}
        ),
        "distinct_shared_mesh_digests": len(
            {row["shared_mesh_digest"] for row in rows}
        ),
        "maximum_position_residual_m": max(
            row["maximum_position_residual_m"] for row in rows
        ),
        "receivers": rows,
        "negative_controls": controls,
        "truth_boundary": (
            "This proves only that the exact existing Building utility-panel proof geometry "
            "for the two source-owned orthogonal receiver frames is reproduced byte-semantically "
            "at the retained JSON vertex/digest contract by the pinned standalone axm_stickers "
            "neutral rigid-frame matrix path using identity source anchor, identity offset and "
            "unit scale. Building keeps receiver IDs, tags, fit, mount, clearance, source and "
            "acceptance semantics. It does not migrate the generator, prove Object equivalence, "
            "authorize shared consolidation, create a universal attachment schema, prove runtime "
            "attachment/physics/gameplay, or establish CANON/production readiness."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    summary = build(args.uc_root)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
