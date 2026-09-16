#!/usr/bin/env python3
import argparse, copy, hashlib, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAVILION = ROOT / "assets/service_pavilion_001.json"
PANEL = ROOT / "assets/utility_access_panel_001.json"
EPS = 1e-9


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dot(a,b): return sum(x*y for x,y in zip(a,b))
def add(a,b): return [x+y for x,y in zip(a,b)]
def mul(a,s): return [x*s for x in a]
def norm(a): return math.sqrt(dot(a,a))


def validate_frame(i):
    axes = [i["normal"], i["lateral"], i["up"]]
    if any(abs(norm(a)-1.0) > EPS for a in axes):
        raise ValueError(f"{i['id']}: non-unit frame")
    if any(abs(dot(axes[a], axes[b])) > EPS for a,b in ((0,1),(0,2),(1,2))):
        raise ValueError(f"{i['id']}: non-orthogonal frame")


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
    clearance = panel["standoff_from_receiver_origin_m"] - interface["plate_thickness_m"]
    if clearance + EPS < panel["required_body_clearance_beyond_plate_m"]:
        raise ValueError("insufficient body clearance")
    center = add(interface["origin"], mul(interface["normal"], panel["standoff_from_receiver_origin_m"]))
    return {
        "interface_id": interface["id"],
        "normal": interface["normal"],
        "lateral": interface["lateral"],
        "up": interface["up"],
        "mount_pattern_residual_m": residual,
        "footprint_margin_m": [hf[0]-pf[0], hf[1]-pf[1]],
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

FACES = [(1,2,4),(2,4,3),(5,6,8),(6,8,7),(1,2,6),(1,6,5),(3,4,8),(3,8,7),(1,3,7),(1,7,5),(2,4,8),(2,8,6)]


def add_box_obj(lines, name, verts, offset):
    lines.append(f"o {name}")
    for v in verts: lines.append("v %.9f %.9f %.9f" % tuple(v))
    for f in FACES: lines.append("f %d %d %d" % tuple(offset+i for i in f))
    return offset+8


def build():
    pav, panel = load(PAVILION), load(PANEL)
    fits=[fit_panel(i,panel) for i in pav["interfaces"]]
    if len(fits) < 2 or abs(dot(fits[0]["normal"], fits[1]["normal"])) > EPS:
        raise ValueError("receiver orientations are not materially different/orthogonal")

    geometry=[]; obj=["# AXM service-pavilion-001 deterministic proof geometry"]; offset=0
    for c in pav["components"]:
        verts=box_vertices(c["center"], c["size"]); geometry += verts
        offset=add_box_obj(obj,c["id"],verts,offset)
    for i,fit in zip(pav["interfaces"],fits):
        verts=box_vertices(fit["panel_center_local_m"], panel["proof_geometry"]["size_local_xyz_m"], (i["normal"],i["lateral"],i["up"]))
        geometry += verts
        offset=add_box_obj(obj,"panel-"+i["id"],verts,offset)

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

    return pav,panel,fits,obj,mins,maxs,path_gap,negatives


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output-dir",default="evidence/service-pavilion-001")
    args=ap.parse_args(); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    pav,panel,fits,obj,mins,maxs,path_gap,negatives=build()
    obj_path=out/"service-pavilion-001-with-panels.obj"; obj_path.write_text("\n".join(obj)+"\n",encoding="utf-8")
    receipt={
      "result":"PASS_BUILDING_PANEL_RECEIVER_PATTERN_PROOF",
      "pavilion_asset_id":pav["asset_id"], "panel_asset_id":panel["asset_id"],
      "pavilion_source_sha256":sha256(PAVILION), "panel_source_sha256":sha256(PANEL),
      "map_reference_blob_sha":pav["provenance"]["map_reference_blob_sha"],
      "reserved_map_slot_size_m":pav["provenance"]["map_slot_size_m"],
      "combined_geometry_bounds_local_m":{"min":mins,"max":maxs,"size":[maxs[i]-mins[i] for i in range(3)]},
      "readable_path_gap_m":path_gap,
      "component_box_count":len(pav["components"]), "placed_panel_count":len(fits),
      "vertex_count":(len(pav["components"])+len(fits))*8,
      "triangle_count":(len(pav["components"])+len(fits))*12,
      "receiver_fits":fits,
      "receiver_normal_dot":dot(fits[0]["normal"],fits[1]["normal"]),
      "negative_controls":negatives,
      "obj_sha256":sha256(obj_path),
      "truth_boundary":pav["truth_boundary"]
    }
    (out/"receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2,sort_keys=True))

if __name__ == "__main__": main()
