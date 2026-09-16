#!/usr/bin/env python3
import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER_TOOL = ROOT / "tools/build_pavilion_utility_panel_receivers.py"
PINNED_STICKER_HEAD = "3aa93b0132eea9becefb20c716c6ec1a023ad28b"
PINNED_STICKER_MODULE_SHA256 = "1344884f14cbe2fa25617664521291b96c4bde067ba0cba31e043045ca3f1436"
PINNED_PREDECESSOR_UC_HEAD = "bd51542bc68534a6e6f3a11d421dc70216b2abf9"
STICKER_PLACEMENT_PATH = Path("src/axm_stickers/placement.py")
STICKER_UPSTREAM_PATH = Path("UPSTREAM.json")
EXPECTED_UPSTREAM_POLICY = "Explicit reviewed adoption only. UC retains its own standalone implementation."
SOCKET_KIND = "axm-building-neutral-rigid-frame-equivalence-probe"


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def validate_sticker_provenance(sticker_root, upstream=None):
    sticker_root = Path(sticker_root).resolve()
    observed_head = git_head(sticker_root)
    if observed_head != PINNED_STICKER_HEAD:
        raise ValueError(
            f"Sticker Fabric donor head drift: {observed_head} != {PINNED_STICKER_HEAD}"
        )

    placement_path = sticker_root / STICKER_PLACEMENT_PATH
    if not placement_path.is_file():
        raise ValueError(f"Sticker Fabric placement module missing: {placement_path}")
    observed_sha = sha256(placement_path)
    if observed_sha != PINNED_STICKER_MODULE_SHA256:
        raise ValueError(
            "Sticker Fabric placement module identity drift: "
            f"{observed_sha} != {PINNED_STICKER_MODULE_SHA256}"
        )

    if upstream is None:
        upstream_path = sticker_root / STICKER_UPSTREAM_PATH
        if not upstream_path.is_file():
            raise ValueError(f"Sticker Fabric upstream receipt missing: {upstream_path}")
        upstream = load_json(upstream_path)

    if upstream.get("policy") != EXPECTED_UPSTREAM_POLICY:
        raise ValueError("Sticker Fabric upstream continuity policy drift")
    upstream_files = upstream.get("files")
    if not isinstance(upstream_files, dict):
        raise ValueError("Sticker Fabric upstream file receipt missing")
    if upstream_files.get(str(STICKER_PLACEMENT_PATH)) != PINNED_STICKER_MODULE_SHA256:
        raise ValueError("Sticker Fabric upstream placement digest drift")

    return observed_head, observed_sha, upstream


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
        raise ValueError("Sticker Fabric neutral attachment matrix changed exact target frame")
    return matrix


def negative_controls(shared, valid_frame, upstream):
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

    bad_upstream = copy.deepcopy(upstream)
    bad_upstream["files"][str(STICKER_PLACEMENT_PATH)] = "0" * 64
    try:
        # Head/file identity are already exact; this isolates the retained upstream receipt gate.
        if bad_upstream.get("policy") != EXPECTED_UPSTREAM_POLICY:
            raise ValueError("Sticker Fabric upstream continuity policy drift")
        if bad_upstream.get("files", {}).get(str(STICKER_PLACEMENT_PATH)) != PINNED_STICKER_MODULE_SHA256:
            raise ValueError("Sticker Fabric upstream placement digest drift")
        controls["upstream_placement_digest_drift"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["upstream_placement_digest_drift"] = "HOLD: " + str(exc)

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("Sticker Fabric rebind negative control unexpectedly passed")
    return controls


def build(sticker_root):
    sticker_root = Path(sticker_root).resolve()
    observed_sticker_head, observed_module_sha, upstream = validate_sticker_provenance(sticker_root)
    shared_path = sticker_root / STICKER_PLACEMENT_PATH

    receiver_mod = load_module(RECEIVER_TOOL, "build_pavilion_utility_panel_receivers")
    shared = load_module(shared_path, "axm_sticker_fabric_placement_probe")

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
        frame = target_frame(current["center_m"], current["basis_normal_lateral_up"])
        matrix = exact_neutral_attachment_matrix(shared, frame)
        shared_vertices = [apply_matrix(matrix, point) for point in local_vertices]
        residual = max(
            abs(observed - expected)
            for observed_vertex, expected_vertex in zip(shared_vertices, current["vertices"])
            for observed, expected in zip(observed_vertex, expected_vertex)
        )
        shared_mesh_digest = digest_json(shared_vertices)
        exact_vertices = shared_vertices == current["vertices"]
        exact_mesh_digest = shared_mesh_digest == current["mesh_digest"]
        if not exact_vertices or not exact_mesh_digest or residual != 0.0:
            raise ValueError(
                f"{current['receiver_id']}: Sticker Fabric rigid-frame path is not exact "
                f"(vertices={exact_vertices}, digest={exact_mesh_digest}, residual={residual})"
            )

        rows.append(
            {
                "receiver_id": current["receiver_id"],
                "target_frame": frame,
                "target_frame_digest": digest_json(frame),
                "local_vertices_digest": local_digest,
                "existing_mesh_digest": current["mesh_digest"],
                "sticker_fabric_mesh_digest": shared_mesh_digest,
                "exact_vertex_list_match": exact_vertices,
                "exact_mesh_digest_match": exact_mesh_digest,
                "maximum_position_residual_m": residual,
            }
        )

    if len({row["target_frame_digest"] for row in rows}) != 2:
        raise ValueError("Sticker Fabric rebind did not retain two distinct target frames")
    if len({row["sticker_fabric_mesh_digest"] for row in rows}) != 2:
        raise ValueError("Sticker Fabric rebind did not retain two distinct transformed outputs")

    controls = negative_controls(shared, rows[0]["target_frame"], upstream)

    return {
        "schema": "axm.building-sticker-fabric-rigid-frame-rebind-evidence/v0.1",
        "result": "PASS_EXACT_STICKER_FABRIC_REBIND_BUILDING_RECEIVERS",
        "authority": "RECEIVING_DOMAIN_SUCCESSOR_REBIND_ONLY",
        "migration_decision": "PASS_FIRST_CONSUMER_REBIND__LOCAL_HELPER_REMOVAL_HELD",
        "building_family_result": existing["result"],
        "building_receiver_count": existing["receiver_count"],
        "building_receiver_ids": existing["receiver_ids"],
        "building_transform_policy": existing["transform_policy"],
        "shared_home_repo": "mike-axiom-mir/axm-sticker-fabric",
        "shared_home_head": observed_sticker_head,
        "shared_home_module": str(STICKER_PLACEMENT_PATH),
        "shared_home_module_sha256": observed_module_sha,
        "shared_home_upstream_policy": upstream["policy"],
        "shared_home_upstream_placement_sha256": upstream["files"][str(STICKER_PLACEMENT_PATH)],
        "predecessor_equivalence_donor_repo": "mike-axiom-mir/axm-universal-creation",
        "predecessor_equivalence_donor_head": PINNED_PREDECESSOR_UC_HEAD,
        "predecessor_equivalence_module_sha256": PINNED_STICKER_MODULE_SHA256,
        "shared_capability": "renderer-independent rigid 3D attachment matrix",
        "probe_socket_kind": SOCKET_KIND,
        "source_anchor": "identity",
        "local_offset": "identity",
        "scale": 1.0,
        "local_vertices_digest": local_digest,
        "exact_receiver_equivalence_count": sum(
            row["exact_vertex_list_match"] and row["exact_mesh_digest_match"] for row in rows
        ),
        "distinct_target_frame_digests": len({row["target_frame_digest"] for row in rows}),
        "distinct_sticker_fabric_mesh_digests": len({row["sticker_fabric_mesh_digest"] for row in rows}),
        "maximum_position_residual_m": max(row["maximum_position_residual_m"] for row in rows),
        "receivers": rows,
        "negative_controls": controls,
        "truth_boundary": (
            "This proves only that the exact existing Building utility-panel proof geometry for the "
            "two source-owned orthogonal receiver frames can be rebound to the pinned standalone "
            "Sticker Fabric placement module with unchanged retained vertex lists, mesh digests and "
            "0.0 m residual under identity source anchor, identity offset and unit scale. The prior "
            "UC-pinned equivalence receipt remains historical provenance. Building keeps receiver "
            "IDs, tags, fit, mount, clearance, source, generator and acceptance semantics. This does "
            "not yet remove the local placement implementation, migrate Object, create a universal "
            "attachment schema, prove runtime attachment/physics/gameplay, or establish CANON or "
            "production readiness."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sticker-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    summary = build(args.sticker_root)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
