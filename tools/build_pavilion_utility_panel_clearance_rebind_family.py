#!/usr/bin/env python3
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "procedural/service_pavilion_utility_panel_clearance_rebind_family_001.json"
PAVILION_PATH = ROOT / "assets/service_pavilion_001.json"
PREDECESSOR_PANEL_PATH = ROOT / "assets/utility_access_panel_001.json"
PREDECESSOR_DOMAIN_PATH = ROOT / "assets/utility_access_panel_001_service_surface_domain.json"
EPS = 1e-12
RESULT = "PASS_BOUNDED_BUILDING_UTILITY_PANEL_CLEARANCE_REBIND_FAMILY"
DECISION = "PASS_DERIVED_CLEARANCE_SUCCESSOR_REBIND_ONLY__NO_SOURCE_REWRITE_OR_RECEIVER_ADOPTION"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def git_head(root):
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def git_blob(root, relpath):
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{relpath}"], text=True
    ).strip()


def git_blob_at(root, revision, relpath):
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", f"{revision}:{relpath}"], text=True
    ).strip()


def git_json_at(root, revision, relpath):
    payload = subprocess.check_output(
        ["git", "-C", str(root), "show", f"{revision}:{relpath}"]
    )
    return json.loads(payload.decode("utf-8"))


def add(a, b):
    return [float(x) + float(y) for x, y in zip(a, b)]


def sub(a, b):
    return [float(x) - float(y) for x, y in zip(a, b)]


def mul(a, scalar):
    return [float(x) * float(scalar) for x in a]


def dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def approx(a, b, eps=EPS):
    return abs(float(a) - float(b)) <= eps


def vec_approx(a, b, eps=EPS):
    return len(a) == len(b) and all(approx(x, y, eps) for x, y in zip(a, b))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_profile(profile, donor_root):
    if profile.get("schema") != "axm.building-utility-panel-clearance-rebind-family/v0.1":
        raise ValueError("clearance-rebind profile schema drift")
    if profile.get("family_id") != profile.get("schema"):
        raise ValueError("clearance-rebind family identity drift")
    if profile.get("receiver_ids") != ["front-utility-bay", "east-utility-bay"]:
        raise ValueError("receiver family identity/order drift")
    if profile.get("automatic_receiver_adoption") is not False:
        raise ValueError("automatic receiver adoption forbidden")
    if profile.get("transform_policy") != "REBIND_ONLY_RECEIVER_NORMAL_TRANSLATION_FROM_EXACT_SOURCE_SUCCESSOR__PRESERVE_RECEIVER_FRAME_AND_LOCAL_SERVICE_SURFACE":
        raise ValueError("clearance-rebind transform policy drift")
    if profile.get("authority") != "DERIVE_ONLY_EXACT_SUCCESSOR_PLACEMENT_AND_SERVICE_SURFACE_WORLD_FRAME":
        raise ValueError("procedural authority drift")

    source = profile.get("source_authority", {})
    if source.get("owner") != "Building Hard Surface" or source.get("pr") != 17:
        raise ValueError("source authority identity drift")
    observed_head = git_head(donor_root)
    if observed_head != source.get("head"):
        raise ValueError(f"Hard Surface donor head drift: {observed_head}")
    for path_key, blob_key in (
        ("panel_path", "panel_blob_sha"),
        ("clearance_policy_path", "clearance_policy_blob_sha"),
        ("service_surface_path", "service_surface_blob_sha"),
    ):
        observed_blob = git_blob(donor_root, source[path_key])
        if observed_blob != source[blob_key]:
            raise ValueError(f"Hard Surface donor blob drift: {source[path_key]}")

    predecessor = profile.get("predecessor", {})
    if predecessor.get("head") != "97120eb78a72b0a07aff1c65b9b92229d0a42aff":
        raise ValueError("predecessor head identity drift")
    if git_blob_at(ROOT, predecessor["head"], predecessor.get("panel_path")) != predecessor.get("panel_blob_sha"):
        raise ValueError("predecessor panel identity drift")
    if git_blob_at(ROOT, predecessor["head"], "assets/utility_access_panel_001_service_surface_domain.json") != predecessor.get("service_surface_blob_sha"):
        raise ValueError("predecessor service-surface identity drift")
    if not approx(predecessor.get("standoff_m"), 0.08):
        raise ValueError("predecessor standoff truth drift")
    if not approx(profile.get("required_successor_standoff_m"), 0.10):
        raise ValueError("successor standoff contract drift")
    if not approx(profile.get("required_standoff_delta_m"), 0.02):
        raise ValueError("standoff delta contract drift")
    if not approx(profile.get("required_physical_body_gap_m"), 0.02):
        raise ValueError("physical body-gap contract drift")


def donor_receipt(profile, donor_root):
    source = profile["source_authority"]
    verifier_path = donor_root / "tools/verify_utility_panel_receiver_clearance_envelope.py"
    verifier = load_module(verifier_path, "axm_building_clearance_owner_verifier")
    receipt = verifier.verify()
    if receipt.get("result") != source.get("required_result"):
        raise ValueError("Hard Surface clearance prerequisite is not PASS")
    if receipt.get("panel_source_blob") != source.get("panel_blob_sha"):
        raise ValueError("Hard Surface receipt panel identity drift")
    if not approx(receipt.get("source_standoff_changed_from_m"), 0.08):
        raise ValueError("Hard Surface predecessor standoff witness drift")
    if not approx(receipt.get("source_standoff_changed_to_m"), 0.10):
        raise ValueError("Hard Surface successor standoff witness drift")
    if receipt.get("downstream_adoption_authorized") is not False:
        raise ValueError("Hard Surface receipt unexpectedly authorizes downstream adoption")
    return receipt


def receiver_frame(interface):
    return {
        "origin": [float(v) for v in interface["origin"]],
        "normal": [float(v) for v in interface["normal"]],
        "lateral": [float(v) for v in interface["lateral"]],
        "up": [float(v) for v in interface["up"]],
    }


def derive_output(interface, predecessor_panel, donor_panel, donor_domain, owner_row, profile):
    frame = receiver_frame(interface)
    normal = frame["normal"]
    predecessor_standoff = float(predecessor_panel["standoff_from_receiver_origin_m"])
    successor_standoff = float(donor_panel["standoff_from_receiver_origin_m"])
    expected_delta = float(profile["required_standoff_delta_m"])

    predecessor_center = add(frame["origin"], mul(normal, predecessor_standoff))
    successor_center = add(frame["origin"], mul(normal, successor_standoff))
    displacement = sub(successor_center, predecessor_center)

    if not vec_approx(successor_center, owner_row["panel_center"]):
        raise ValueError(f"{interface['id']}: successor center disagrees with Hard Surface receipt")
    if not approx(norm(displacement), expected_delta):
        raise ValueError(f"{interface['id']}: successor displacement magnitude drift")
    if not vec_approx(displacement, mul(normal, expected_delta)):
        raise ValueError(f"{interface['id']}: successor displacement is not exact receiver-normal translation")
    if not approx(owner_row["physical_body_gap_m"], profile["required_physical_body_gap_m"]):
        raise ValueError(f"{interface['id']}: physical body gap drift")
    if not approx(owner_row["clearance_slack_m"], 0.0):
        raise ValueError(f"{interface['id']}: expected exact clearance closure")

    surface_origin_local = donor_domain["reference_frame"]["origin_local_m"]
    if not vec_approx(surface_origin_local, [0.04, 0.0, 0.0]):
        raise ValueError("source service-surface local origin drift")
    predecessor_surface_origin = add(predecessor_center, mul(normal, surface_origin_local[0]))
    successor_surface_origin = add(successor_center, mul(normal, surface_origin_local[0]))
    surface_displacement = sub(successor_surface_origin, predecessor_surface_origin)
    if not vec_approx(surface_displacement, displacement):
        raise ValueError(f"{interface['id']}: service-surface rebind does not preserve local source frame")

    output = {
        "receiver_id": interface["id"],
        "receiver_frame": frame,
        "predecessor_panel_center_m": predecessor_center,
        "successor_panel_center_m": successor_center,
        "panel_center_displacement_m": displacement,
        "panel_center_displacement_magnitude_m": norm(displacement),
        "predecessor_service_surface_origin_m": predecessor_surface_origin,
        "successor_service_surface_origin_m": successor_surface_origin,
        "service_surface_origin_displacement_m": surface_displacement,
        "successor_physical_body_gap_m": float(owner_row["physical_body_gap_m"]),
        "required_body_gap_m": float(owner_row["required_body_clearance_m"]),
        "clearance_slack_m": float(owner_row["clearance_slack_m"]),
        "source_service_surface_id": donor_domain["surface_id"],
        "source_service_surface_primary_extent_m": float(donor_domain["metric_domain"]["primary_extent_m"]),
        "source_service_surface_secondary_extent_m": float(donor_domain["metric_domain"]["secondary_extent_m"]),
        "source_service_surface_area_m2": float(donor_domain["metric_domain"]["area_m2"]),
    }
    output["output_digest"] = digest_json(output)
    return output


def canonical_digest(outputs):
    return digest_json(sorted(outputs, key=lambda item: item["receiver_id"]))


def run_negative_controls(profile, donor_root, pavilion, predecessor_panel, donor_panel, donor_domain, receipt):
    controls = {}

    def expect_hold(name, fn):
        try:
            fn()
            controls[name] = "UNEXPECTED_PASS"
        except (ValueError, KeyError) as exc:
            controls[name] = "HOLD: " + str(exc)

    bad = copy.deepcopy(profile)
    bad["source_authority"]["head"] = "0" * 40
    expect_hold("donor_head_drift", lambda: verify_profile(bad, donor_root))

    bad = copy.deepcopy(profile)
    bad["source_authority"]["panel_blob_sha"] = "0" * 40
    expect_hold("successor_panel_blob_drift", lambda: verify_profile(bad, donor_root))

    bad = copy.deepcopy(profile)
    bad["required_standoff_delta_m"] = 0.01
    expect_hold("standoff_delta_drift", lambda: verify_profile(bad, donor_root))

    bad = copy.deepcopy(profile)
    bad["automatic_receiver_adoption"] = True
    expect_hold("automatic_receiver_adoption", lambda: verify_profile(bad, donor_root))

    bad = copy.deepcopy(profile)
    bad["receiver_ids"] = ["front-utility-bay", "front-utility-bay"]
    expect_hold("duplicate_receiver_identity", lambda: verify_profile(bad, donor_root))

    interfaces = {row["id"]: row for row in pavilion["interfaces"]}
    owner_by_id = {row["interface_id"]: row for row in receipt["receiver_results"]}
    bad_owner = copy.deepcopy(owner_by_id["front-utility-bay"])
    bad_owner["panel_center"][0] += 0.001
    expect_hold(
        "successor_center_not_on_receiver_normal",
        lambda: derive_output(
            interfaces["front-utility-bay"], predecessor_panel, donor_panel, donor_domain, bad_owner, profile
        ),
    )

    bad_owner = copy.deepcopy(owner_by_id["east-utility-bay"])
    bad_owner["physical_body_gap_m"] = 0.0
    expect_hold(
        "physical_body_gap_regression",
        lambda: derive_output(
            interfaces["east-utility-bay"], predecessor_panel, donor_panel, donor_domain, bad_owner, profile
        ),
    )

    if any(not value.startswith("HOLD:") for value in controls.values()):
        raise ValueError("clearance-rebind negative control unexpectedly passed")
    return controls


def build(donor_root):
    donor_root = Path(donor_root).resolve()
    profile = load(PROFILE_PATH)
    verify_profile(profile, donor_root)
    receipt = donor_receipt(profile, donor_root)

    pavilion = load(PAVILION_PATH)
    predecessor = profile["predecessor"]
    predecessor_panel = git_json_at(ROOT, predecessor["head"], predecessor["panel_path"])
    predecessor_domain = git_json_at(
        ROOT,
        predecessor["head"],
        "assets/utility_access_panel_001_service_surface_domain.json",
    )
    donor_panel = load(donor_root / profile["source_authority"]["panel_path"])
    donor_domain = load(donor_root / profile["source_authority"]["service_surface_path"])

    if predecessor_panel["asset_id"] != donor_panel["asset_id"]:
        raise ValueError("panel asset identity changed across clearance successor")
    if predecessor_domain["surface_id"] != donor_domain["surface_id"]:
        raise ValueError("service-surface identity changed across clearance successor")
    if predecessor_domain["reference_frame"] != donor_domain["reference_frame"]:
        raise ValueError("service-surface local frame changed across clearance successor")
    if predecessor_domain["metric_domain"] != donor_domain["metric_domain"]:
        raise ValueError("service-surface metric domain changed across clearance successor")
    if not approx(donor_panel["standoff_from_receiver_origin_m"] - predecessor_panel["standoff_from_receiver_origin_m"], profile["required_standoff_delta_m"]):
        raise ValueError("source successor delta disagrees with Procedural rebind contract")

    interfaces = {row["id"]: row for row in pavilion["interfaces"]}
    owner_by_id = {row["interface_id"]: row for row in receipt["receiver_results"]}
    outputs = [
        derive_output(
            interfaces[receiver_id], predecessor_panel, donor_panel, donor_domain, owner_by_id[receiver_id], profile
        )
        for receiver_id in profile["receiver_ids"]
    ]

    if len({item["output_digest"] for item in outputs}) != 2:
        raise ValueError("successor outputs are not materially distinct")
    if abs(dot(outputs[0]["receiver_frame"]["normal"], outputs[1]["receiver_frame"]["normal"])) > EPS:
        raise ValueError("expected orthogonal receiver normals drifted")

    family_digest = canonical_digest(outputs)
    if family_digest != canonical_digest(list(reversed(outputs))):
        raise ValueError("canonical family digest depends on generation order")

    negatives = run_negative_controls(
        profile, donor_root, pavilion, predecessor_panel, donor_panel, donor_domain, receipt
    )

    return {
        "schema": "axm.building-utility-panel-clearance-rebind-family-evidence/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "family_id": profile["family_id"],
        "source_authority_head": profile["source_authority"]["head"],
        "source_authority_panel_blob": profile["source_authority"]["panel_blob_sha"],
        "source_authority_clearance_policy_blob": profile["source_authority"]["clearance_policy_blob_sha"],
        "predecessor_panel_blob": profile["predecessor"]["panel_blob_sha"],
        "predecessor_standoff_m": float(predecessor_panel["standoff_from_receiver_origin_m"]),
        "successor_standoff_m": float(donor_panel["standoff_from_receiver_origin_m"]),
        "standoff_delta_m": float(profile["required_standoff_delta_m"]),
        "receiver_count": len(outputs),
        "distinct_output_count": len({item["output_digest"] for item in outputs}),
        "receiver_normal_dot": dot(outputs[0]["receiver_frame"]["normal"], outputs[1]["receiver_frame"]["normal"]),
        "canonical_family_digest": family_digest,
        "reverse_order_family_digest": canonical_digest(list(reversed(outputs)),),
        "outputs": sorted(outputs, key=lambda item: item["receiver_id"]),
        "negative_controls": negatives,
        "source_service_surface_local_frame_changed": False,
        "source_service_surface_metric_domain_changed": False,
        "source_geometry_rewritten": False,
        "automatic_receiver_adoption": False,
        "authority": profile["authority"],
        "failure_policy": profile["failure_policy"],
        "truth_boundary": profile["truth_boundary"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--donor-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = build(args.donor_root)
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
