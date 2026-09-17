#!/usr/bin/env python3
"""Repair the Building boundary-shell Materials packet with tolerance-safe invariants.

The first packet correctly failed on strict serialized float equality for donor vs
candidate surface area (a ~1e-12 representation difference). This successor keeps
all source/material/geometry gates and uses the Geometry lane's existing 1e-9
measurement tolerance for measured float invariants only.
"""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/'lookdev'/'building_material_profile_001.json'
GEOMETRY_HEAD='43ace6fc44e6f6c0f637cd3436a94099c97c2d48'
PAYLOAD_SCHEMA='axm.building-material-boundary-shell-compaction-lookdev/v0.1'
EPS=1e-9

def load(path):
    value=json.loads(Path(path).read_text())
    assert isinstance(value,dict), path
    return value

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def rgba(value):
    assert isinstance(value,str) and len(value)==9 and value[0]=='#'
    return [int(value[i:i+2],16)/255.0 for i in (1,3,5,7)]

def close(a,b): return abs(float(a)-float(b)) <= EPS

def mesh_stats(name,mesh,schema,mapping):
    assert mesh.get('schema')==schema,(name,mesh.get('schema'))
    vertices=mesh['vertices']; triangles=mesh['triangles']; owners=mesh['triangle_owners']
    assert len(triangles)==len(owners)
    owner_ids={row.get('source_component_id') for row in owners}
    assert None not in owner_ids
    assert owner_ids==set(mapping),(name,sorted(owner_ids),sorted(mapping))
    counts={material_id:0 for material_id in sorted(set(mapping.values()))}
    for tri,owner in zip(triangles,owners):
        assert len(tri)==3 and all(isinstance(i,int) and 0<=i<len(vertices) for i in tri)
        counts[mapping[owner['source_component_id']]]+=1
    return {'vertex_count':len(vertices),'triangle_count':len(triangles),'source_component_owner_count':len(owner_ids),'material_triangle_counts':counts}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--geometry-root',required=True,type=Path); ap.add_argument('--exact-head',required=True); ap.add_argument('--out',default='lookdev-boundary-shell-compaction-proof/generated',type=Path); args=ap.parse_args()
    g=args.geometry_root
    rr=g/'evidence/service-pavilion-boundary-shell-001'; cr=g/'evidence/service-pavilion-boundary-shell-compaction-001'
    reference_path=rr/'boundary-shell.json'; compact_path=cr/'compacted-boundary-shell.json'; re_path=rr/'boundary-shell-evidence.json'; ce_path=cr/'compaction-evidence.json'
    reference=load(reference_path); compact=load(compact_path); re=load(re_path); ce=load(ce_path); profile=load(PROFILE)
    assert (cr/'exact-head.txt').read_text().strip()==GEOMETRY_HEAD
    assert ce['exact_geometry_head']==GEOMETRY_HEAD
    assert re['result']=='PASS_CURRENT_SOURCE_BOUNDARY_ONLY_UNION_SHELL_CANDIDATE'
    assert ce['result']=='PASS_BOUNDARY_SHELL_CONFORMING_PLANAR_COMPACTION_CANDIDATE'
    mapping=profile['component_materials']; assert len(mapping)==19
    rs=mesh_stats('reference',reference,'axm.building-current-source-boundary-shell/v0.1',mapping)
    cs=mesh_stats('compact',compact,'axm.building-boundary-shell-conforming-compaction/v0.1',mapping)
    assert (rs['vertex_count'],rs['triangle_count'])==(1420,2884),rs
    assert (cs['vertex_count'],cs['triangle_count'])==(1402,2848),cs
    donor=ce['donor']; candidate=ce['candidate']
    assert candidate['bounds']==donor['bounds']
    assert candidate['source_component_owner_count']==donor['source_component_owner_count']==19
    assert close(candidate['signed_volume_m3'],donor['signed_volume_m3'])
    assert close(candidate['surface_area_m2'],donor['surface_area_m2'])
    assert float(candidate['maximum_source_component_area_residual_m2'])<=EPS
    materials={}
    for mid,spec in profile['candidate'].items():
        metallic=float(spec['metallic']); roughness=float(spec['roughness']); assert 0<=metallic<=1 and 0<=roughness<=1
        materials[mid]={'albedo':rgba(spec['albedo']),'albedo_hex':spec['albedo'],'metallic':metallic,'roughness':roughness}
    payload={'schema':PAYLOAD_SCHEMA,'exact_materials_head':args.exact_head.strip(),'geometry_donor_head':GEOMETRY_HEAD,'geometry_reference_sha256':sha(reference_path),'geometry_compact_sha256':sha(compact_path),'geometry_compaction_evidence_sha256':sha(ce_path),'material_profile_sha256':sha(PROFILE),'materials':materials,'component_materials':mapping,'normal_policy':'EXPLICIT_PER_TRIANGLE_PLANE_NORMAL__NO_VERTEX_SMOOTHING__HARD_SURFACE_REVIEW','contexts':['front_service','east_service','three_quarter'],'reference':reference,'compact':compact,'reference_stats':rs,'compact_stats':cs,'geometry_evidence':{'reference_result':re['result'],'compact_result':ce['result'],'signed_volume_m3':candidate['signed_volume_m3'],'surface_area_m2':candidate['surface_area_m2'],'surface_area_residual_vs_donor_m2':abs(float(candidate['surface_area_m2'])-float(donor['surface_area_m2'])),'source_component_owner_count':candidate['source_component_owner_count'],'maximum_source_component_area_residual_m2':candidate['maximum_source_component_area_residual_m2'],'vertex_reduction':rs['vertex_count']-cs['vertex_count'],'triangle_reduction':rs['triangle_count']-cs['triangle_count']},'truth_boundary':{'material_scalars_changed':False,'source_component_material_mapping_changed':False,'geometry_owned_by_materials':False,'reference_and_compact_material_family_identical':True,'hard_surface_normal_policy_explicit':True,'vertex_smooth_generated_normals_tested':False,'uvs_or_textures_tested':False,'environment_adoption':False,'runtime_acceptance':False,'art_direction_acceptance':False,'visual_qa_acceptance':False}}
    receipt={'schema':'axm.building-material-boundary-shell-compaction-build-receipt/v0.2','result':'PASS_BUILDING_BOUNDARY_SHELL_COMPACTION_MATERIAL_BINDING_PACKET','exact_materials_head':args.exact_head.strip(),'geometry_donor_head':GEOMETRY_HEAD,'reference_stats':rs,'compact_stats':cs,'geometry_evidence':payload['geometry_evidence'],'material_profile_sha256':payload['material_profile_sha256'],'payload_sha256':canonical(payload),'failed_predecessor_reason':'STRICT_SERIALIZED_FLOAT_EQUALITY_REJECTED_~1E-12_SURFACE_AREA_NOISE','truth_boundary':payload['truth_boundary']}
    args.out.mkdir(parents=True,exist_ok=True); (args.out/'payload.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); (args.out/'build_receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n'); print(json.dumps(receipt,indent=2,sort_keys=True))
if __name__=='__main__': main()
