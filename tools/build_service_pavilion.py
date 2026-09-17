#!/usr/bin/env python3
import argparse, copy, hashlib, json, math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAVILION = ROOT / "assets/service_pavilion_001.json"
PANEL = ROOT / "assets/utility_access_panel_001.json"
EPS = 1e-9

PREDECESSOR_HARD_SURFACE_HEAD = "4faa769b406bf3ad0ba9489a77141c27f122ce51"
GEOMETRY_CANDIDATE_HEAD = "407d3aaf36c26829a64d964143e34587df6d8ea1"
MATERIALS_COMPATIBILITY_HEAD = "0c409a88c1952ca04934f9db47cb282db27b5c3c"
BOX_TOPOLOGY_REVISION = "closed-outward-12-triangle-v1"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dot(a,b): return sum(x*y for x,y in zip(a,b))
def add(a,b): return [x+y for x,y in zip(a,b)]
def sub(a,b): return [x-y for x,y in zip(a,b)]
def mul(a,s): return [x*s for x in a]
def norm(a): return math.sqrt(dot(a,a))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def validate_frame(i):
    axes = [i["normal"], i["lateral"], i["up"]]
    if any(abs(norm(a)-1.0) > EPS for a in axes):
        raise ValueError(f"{i['id']}: non-unit frame")
    if any(abs(dot(axes[a], axes[b])) > EPS for a,b in ((0,1),(0,2),(1,2))):
        raise ValueError(f"{i['id']}: non-orthogonal frame")
    if dot(cross(axes[0], axes[1]), axes[2]) <= 0.0:
        raise ValueError(f"{i['id']}: receiver frame is not right-handed")


def fit_panel(interface, panel):
    validate_frame(interface)
    if panel["accepted_tag"] != interface["accepted_tag"]:
        raise ValueError("tag mismatch")
    pf = panel["interface_footprint_m"]
    hf = interface["plate_footprint_m"]
    if pf[0] > hf[0] + EPS or pf[1] > hf[1] + EPS:
        raise ValueError("panel footprint exceeds receiver plate")
    hp = interface["mount_points_local_m"]
    pp = panel["mount_points_local_m"]
    if len(hp) != len(pp):
        raise ValueError("mount point count mismatch")
    residual = max(math.dist(a,b) for a,b in zip(hp,pp)) if hp else 0.0
    if residual > EPS:
        raise ValueError(f"mount-pattern residual {residual}")

    # The source standoff locates the panel BODY CENTER, not its nearest face.
    # Preserve the center-offset surplus as a separately named diagnostic, but
    # source-own physical body clearance from the nearest body face.
    center_surplus = panel["standoff_from_receiver_origin_m"] - interface["plate_thickness_m"]
    clearance = center_surplus - 0.5 * panel["body_depth_m"]
    if clearance + EPS < panel["required_body_clearance_beyond_plate_m"]:
        raise ValueError("insufficient nearest-body-face clearance")

    center = add(interface["origin"], mul(interface["normal"], panel["standoff_from_receiver_origin_m"]))
    return {
        "interface_id": interface["id"],
        "normal": interface["normal"],
        "lateral": interface["lateral"],
        "up": interface["up"],
        "mount_pattern_residual_m": residual,
        "footprint_margin_m": [hf[0]-pf[0], hf[1]-pf[1]],
        "body_center_surplus_beyond_plate_m": center_surplus,
        "body_clearance_beyond_plate_m": clearance,
        "panel_center_local_m": center,
    }


def box_vertices(center, size, basis=None):
    basis = basis or ([1,0,0],[0,1,0],[0,0,1])
    out=[]
    for sx in (-0.5,0.5):
      for sy in (-0.5,0.5):
       for sz in (-0.5,0.5):
        p=list(center)
        for axis,amount in zip(basis,(size[0]*sx,size[1]*sy,size[2]*sz)):
            p=add(p,mul(axis,amount))
        out.append(p)
    return out


# Historical predecessor representation, retained only as an explicit fail-closed
# regression oracle. It must never become the current emitted face table again.
HISTORICAL_FACES = [
    (1,2,4),(2,4,3),
    (5,6,8),(6,8,7),
    (1,2,6),(1,6,5),
    (3,4,8),(3,8,7),
    (1,3,7),(1,7,5),
    (2,4,8),(2,8,6),
]

# Source-owned successor adopted from the exact Geometry PR #6 candidate after
# independent Materials target-host compatibility evidence. Same 8 vertices and
# same 12-triangle budget; only triangle membership/winding differs.
FACES = [
    (1,4,3),(1,2,4),
    (5,7,8),(5,8,6),
    (1,5,6),(1,6,2),
    (3,4,8),(3,8,7),
    (1,3,7),(1,7,5),
    (2,6,8),(2,8,4),
]


def inspect_box_shell(vertices, faces):
    if len(vertices) != 8:
        raise ValueError(f"box shell requires exactly 8 vertices, got {len(vertices)}")
    if len(faces) != 12:
        raise ValueError(f"box shell requires exactly 12 triangles, got {len(faces)}")

    edge_incidence = defaultdict(list)
    center = [sum(v[axis] for v in vertices) / len(vertices) for axis in range(3)]
    outward = inward = tangent = degenerate = 0

    for face_index, face in enumerate(faces):
        if len(face) != 3 or any(index < 1 or index > len(vertices) for index in face):
            raise ValueError(f"invalid triangle index tuple: {face}")
        if len(set(face)) != 3:
            raise ValueError(f"collapsed triangle index tuple: {face}")
        a,b,c = (vertices[index-1] for index in face)
        normal = cross(sub(b,a), sub(c,a))
        if norm(normal) <= EPS:
            degenerate += 1
        face_center = [(a[axis]+b[axis]+c[axis])/3.0 for axis in range(3)]
        signed = dot(normal, sub(face_center, center))
        if signed > EPS:
            outward += 1
        elif signed < -EPS:
            inward += 1
        else:
            tangent += 1

        zero_based = tuple(index-1 for index in face)
        for start,end in ((zero_based[0],zero_based[1]),(zero_based[1],zero_based[2]),(zero_based[2],zero_based[0])):
            key = tuple(sorted((start,end)))
            direction = 1 if (start,end) == key else -1
            edge_incidence[key].append(direction)

    boundary = sum(len(rows) == 1 for rows in edge_incidence.values())
    nonmanifold = sum(len(rows) > 2 for rows in edge_incidence.values())
    orientation_conflicts = sum(len(rows) == 2 and rows[0] == rows[1] for rows in edge_incidence.values())
    return {
        "edge_count": len(edge_incidence),
        "boundary_edge_count": boundary,
        "nonmanifold_edge_count": nonmanifold,
        "orientation_conflict_edge_count": orientation_conflicts,
        "degenerate_triangle_count": degenerate,
        "outward_triangle_count": outward,
        "inward_triangle_count": inward,
        "tangent_triangle_count": tangent,
    }


def require_closed_outward_box(vertices, faces=FACES):
    metrics = inspect_box_shell(vertices, faces)
    expected = {
        "edge_count": 18,
        "boundary_edge_count": 0,
        "nonmanifold_edge_count": 0,
        "orientation_conflict_edge_count": 0,
        "degenerate_triangle_count": 0,
        "outward_triangle_count": 12,
        "inward_triangle_count": 0,
        "tangent_triangle_count": 0,
    }
    if metrics != expected:
        raise ValueError(f"box shell is not exact closed/outward successor topology: {metrics}")
    return metrics


def add_box_obj(lines, name, verts, offset):
    require_closed_outward_box(verts)
    lines.append(f"o {name}")
    for v in verts: lines.append("v %.9f %.9f %.9f" % tuple(v))
    for f in FACES: lines.append("f %d %d %d" % tuple(offset+i for i in f))
    return offset+8


def build():
    pav, panel = load(PAVILION), load(PANEL)
    contract = pav.get("generated_geometry_contract", {})
    if pav.get("schema") != "axm.building-hard-surface/v0.2":
        raise ValueError("pavilion source schema is not the source-migrated v0.2 identity")
    if pav.get("source_revision") != "service-pavilion-001/closed-outward-box-shells-002":
        raise ValueError("pavilion source revision drift")
    if contract.get("box_shell_topology") != BOX_TOPOLOGY_REVISION or contract.get("owner") != "Building Hard Surface":
        raise ValueError("source-owned generated box topology contract drift")

    fits=[fit_panel(i,panel) for i in pav["interfaces"]]
    if len(fits) < 2 or abs(dot(fits[0]["normal"], fits[1]["normal"])) > EPS:
        raise ValueError("receiver orientations are not materially different/orthogonal")

    geometry=[]; obj=["# AXM service-pavilion-001 deterministic proof geometry"]; offset=0
    topology_rows=[]
    for c in pav["components"]:
        verts=box_vertices(c["center"], c["size"]); geometry += verts
        topology_rows.append({"object":c["id"], **require_closed_outward_box(verts)})
        offset=add_box_obj(obj,c["id"],verts,offset)
    for i,fit in zip(pav["interfaces"],fits):
        verts=box_vertices(fit["panel_center_local_m"], panel["proof_geometry"]["size_local_xyz_m"], (i["normal"],i["lateral"],i["up"]))
        geometry += verts
        topology_rows.append({"object":"panel-"+i["id"], **require_closed_outward_box(verts)})
        offset=add_box_obj(obj,"panel-"+i["id"],verts,offset)

    if len(topology_rows) != 19:
        raise ValueError(f"expected 19 real box outputs, got {len(topology_rows)}")

    mins=[min(v[k] for v in geometry) for k in range(3)]
    maxs=[max(v[k] for v in geometry) for k in range(3)]
    slot=pav["provenance"]["map_slot_size_m"]
    limits=([-slot[0]/2,-slot[1]/2,0.0],[slot[0]/2,slot[1]/2,slot[2]])
    if any(mins[k] < limits[0][k]-EPS or maxs[k] > limits[1][k]+EPS for k in range(3)):
        raise ValueError(f"source geometry exceeds reserved map slot: {mins}..{maxs}")
    scene_min_y=pav["provenance"]["map_slot_position_m"][1] + mins[1]
    path_gap=scene_min_y-pav["provenance"]["map_readable_path_y_max_m"]
    if path_gap + EPS < pav["provenance"]["map_minimum_gap_m"]:
        raise ValueError("candidate violates reserved readable-path gap")

    negatives={}
    tests={
      "mount_drift_0p001m": lambda p: p["mount_points_local_m"].__setitem__(0,[p["mount_points_local_m"][0][0]+0.001,p["mount_points_local_m"][0][1]]),
      "oversize_1p30m": lambda p: p.__setitem__("interface_footprint_m",[1.30,p["interface_footprint_m"][1]]),
      "insufficient_standoff_0p05m": lambda p: p.__setitem__("standoff_from_receiver_origin_m",0.05),
    }
    for name,mut in tests.items():
        bad=copy.deepcopy(panel); mut(bad)
        try: fit_panel(pav["interfaces"][0],bad); negatives[name]="UNEXPECTED_PASS"
        except ValueError as e: negatives[name]="REJECTED: "+str(e)
    if any(not v.startswith("REJECTED") for v in negatives.values()):
        raise ValueError("negative control unexpectedly passed")

    unit_box = box_vertices([0,0,0],[2,2,2])
    historical_metrics = inspect_box_shell(unit_box, HISTORICAL_FACES)
    try:
        require_closed_outward_box(unit_box, HISTORICAL_FACES)
        historical_rejection = "UNEXPECTED_PASS"
    except ValueError as e:
        historical_rejection = "REJECTED: "+str(e)
    if not historical_rejection.startswith("REJECTED"):
        raise ValueError("historical malformed face table unexpectedly passed successor topology gate")

    flipped = list(FACES)
    a,b,c = flipped[0]
    flipped[0] = (a,c,b)
    try:
        require_closed_outward_box(unit_box, flipped)
        flipped_rejection = "UNEXPECTED_PASS"
    except ValueError as e:
        flipped_rejection = "REJECTED: "+str(e)
    if not flipped_rejection.startswith("REJECTED"):
        raise ValueError("single-triangle winding negative control unexpectedly passed")

    topology_summary = {
        "revision": BOX_TOPOLOGY_REVISION,
        "object_count": len(topology_rows),
        "vertex_count": len(topology_rows)*8,
        "triangle_count": len(topology_rows)*12,
        "boundary_edge_count": sum(r["boundary_edge_count"] for r in topology_rows),
        "nonmanifold_edge_count": sum(r["nonmanifold_edge_count"] for r in topology_rows),
        "orientation_conflict_edge_count": sum(r["orientation_conflict_edge_count"] for r in topology_rows),
        "degenerate_triangle_count": sum(r["degenerate_triangle_count"] for r in topology_rows),
        "outward_triangle_count": sum(r["outward_triangle_count"] for r in topology_rows),
        "inward_triangle_count": sum(r["inward_triangle_count"] for r in topology_rows),
        "tangent_triangle_count": sum(r["tangent_triangle_count"] for r in topology_rows),
        "historical_predecessor_unit_box_metrics": historical_metrics,
        "historical_predecessor_rejection": historical_rejection,
        "single_triangle_flip_rejection": flipped_rejection,
    }
    expected_summary = {
        "object_count": 19,
        "vertex_count": 152,
        "triangle_count": 228,
        "boundary_edge_count": 0,
        "nonmanifold_edge_count": 0,
        "orientation_conflict_edge_count": 0,
        "degenerate_triangle_count": 0,
        "outward_triangle_count": 228,
        "inward_triangle_count": 0,
        "tangent_triangle_count": 0,
    }
    for key,value in expected_summary.items():
        if topology_summary[key] != value:
            raise ValueError(f"unexpected source topology aggregate {key}: {topology_summary[key]} != {value}")

    return pav,panel,fits,obj,mins,maxs,path_gap,negatives,topology_summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-dir",default="evidence/service-pavilion-001")
    ap.add_argument("--exact-head",default="LOCAL_UNBOUND")
    args=ap.parse_args(); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    pav,panel,fits,obj,mins,maxs,path_gap,negatives,topology_summary=build()
    obj_path=out/"service-pavilion-001-with-panels.obj"; obj_path.write_text("\n".join(obj)+"\n",encoding="utf-8")
    receipt={
      "result":"PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF",
      "source_topology_result":"PASS_SOURCE_OWNED_CLOSED_OUTWARD_BOX_SHELLS_19_REAL_OUTPUTS",
      "exact_hard_surface_head":args.exact_head,
      "predecessor_hard_surface_head":PREDECESSOR_HARD_SURFACE_HEAD,
      "geometry_candidate_evidence_head":GEOMETRY_CANDIDATE_HEAD,
      "materials_compatibility_evidence_head":MATERIALS_COMPATIBILITY_HEAD,
      "pavilion_asset_id":pav["asset_id"], "pavilion_source_revision":pav["source_revision"], "panel_asset_id":panel["asset_id"],
      "pavilion_source_sha256":sha256(PAVILION), "panel_source_sha256":sha256(PANEL),
      "map_reference_blob_sha":pav["provenance"]["map_reference_blob_sha"],
      "reserved_map_slot_size_m":pav["provenance"]["map_slot_size_m"],
      "combined_geometry_bounds_local_m":{"min":mins,"max":maxs,"size":[maxs[i]-mins[i] for i in range(3)]},
      "readable_path_gap_m":path_gap,
      "component_box_count":len(pav["components"]), "placed_panel_count":len(fits),
      "vertex_count":(len(pav["components"])+len(fits))*8,
      "triangle_count":(len(pav["components"])+len(fits))*12,
      "receiver_fits":fits,
      "receiver_normal_dot":dot(fits[0]["normal"], fits[1]["normal"]),
      "negative_controls":negatives,
      "source_topology":topology_summary,
      "obj_sha256":sha256(obj_path),
      "truth_boundary":pav["truth_boundary"],
      "non_claims":[
        "boolean-unioned pavilion shell",
        "hidden/interpenetrating internal-face removal between touching components",
        "vertex-manifoldness or self-intersection freedom",
        "final normals/tangents/smoothing/UVs/materials",
        "architectural/manufacturing validity",
        "runtime import/collision/navigation/gameplay",
        "target-device performance",
        "Art Direction or Visual QA acceptance",
        "CANON, production/game readiness, or Hard-Surface mastery"
      ]
    }
    (out/"receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"exact-head.txt").write_text(args.exact_head+"\n",encoding="utf-8")
    (out/"predecessor-hard-surface-head.txt").write_text(PREDECESSOR_HARD_SURFACE_HEAD+"\n",encoding="utf-8")
    (out/"geometry-evidence-head.txt").write_text(GEOMETRY_CANDIDATE_HEAD+"\n",encoding="utf-8")
    (out/"materials-evidence-head.txt").write_text(MATERIALS_COMPATIBILITY_HEAD+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2,sort_keys=True))

if __name__ == "__main__": main()
