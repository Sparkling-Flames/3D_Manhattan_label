#!/usr/bin/env python3
"""Bind selected existing fusion endpoints to frozen sources without re-running fusion."""
from __future__ import annotations
import argparse,collections,csv,hashlib,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,Point
from audit_qualification import read,dump,csvout,digest

def datahash(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def project_vertical_pairs(points):
    p=np.asarray(points,float)
    assert p.ndim==2 and p.shape[1]==2 and len(p)>=6 and len(p)%2==0 and np.isfinite(p).all()
    a,b=p[::2],p[1::2]
    assert np.max(np.abs((a[:,0]-b[:,0]+512)%1024-512))<1e-9
    assert np.all((b[:,1]>256)&(b[:,1]<512)) and np.all((a[:,1]>=0)&(a[:,1]<b[:,1]))
    radius=1/np.tan(np.pi*(b[:,1]/512-.5));theta=b[:,0]/1024*2*np.pi
    x=-radius*np.sin(theta);z=radius*np.cos(theta)
    height_above_camera=radius*np.tan(np.pi*(.5-a[:,1]/512))
    assert np.all(height_above_camera+1>0)
    return dict(bottom3d=np.c_[x,-np.ones(len(x)),z].tolist(),top3d=np.c_[x,height_above_camera,z].tolist())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path.cwd());ap.add_argument('--out',type=Path);a=ap.parse_args();W=a.workspace.resolve()
    E=W/'top_structure_20261012/evidence';O=a.out or E/'results';O.mkdir(parents=True,exist_ok=True)
    B=W/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    sources=dict(protocol=E/'demo_protocol_before_new_scores.json',formal=B/'inputs/current_formal_loader_data.json',
        components=B/'results/current_components.json',geometry=B/'inputs/current_geometry_compact.json',registry=B/'inputs/reference_exclusion_registry_20261010.json',
        holdout=B/'results/room_holdout_manifest.csv',fusion_manifest=E/'repo_snapshot/FUSION_SOURCE_MANIFEST.json')
    protected={k:digest(p) for k,p in sources.items()}
    protocol=read(sources['protocol']);formal=read(sources['formal']);obj={r['object_id']:r for r in formal['objects']}
    comp={r['record_id']:r for r in read(sources['components'])};geo=read(sources['geometry'])['geometries']
    hold={r['record_id']:r for r in csv.DictReader(sources['holdout'].open(encoding='utf-8-sig'))};reg=read(sources['registry'])
    blocks={r['image_id'] for sec in ['confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine'] for r in reg[sec]}
    blocks|={r['image_id'] for r in reg['all_current_hold_images'] if all(k.startswith('hold_') or k in {'excluded','out_of_primary_scene'} for k in r['gate_counts'])}
    sf=E/'repo_snapshot/analysis_results/consensus_delivery_20261008'
    binding=[];inputs=[];endpoints=[];availability=[];refs={};p_to_w={};pairchecks=0;max_error=0.;max_floor_error=0.
    source_manifest=[]
    for code in protocol['preregistered_core_images']:
        path=sf/f'{code}.json'
        if not path.exists():
            availability.append(dict(image_code=code,state='not_in_current_delivery_directory',notes='The inspected directory has no complete fixed endpoint for this core image. T20 is a semi-assisted input condition; no output is fabricated.'))
            continue
        doc=read(path);source_manifest.append(dict(path=str(path.relative_to(W)),sha256=digest(path)))
        assert doc['image_id'] not in blocks
        auto=doc['automatic'];members={};member_pairs={}
        for g in auto['identity_groups']:
            for m in g['members']:
                rid=m['id'];r=comp[rid];o=obj[r['object_id']];pi=m['pair_index']
                assert r['image_id']==doc['image_id'] and r['image_code']==code
                assert r['primary_included'] and r['annotation_strict_available'] and r['reference_strict_available']
                assert r['primary_gate_and_reference_allowed'] and not r['reference_restrictions'] and not r['reference_strict_reasons']
                assert hold[rid]['held_out_of_sample_and_future_calibration']=='False'
                assert r['worker_id']!='W019' and r['condition']=='manual'
                p=np.asarray(m['points']);q=np.asarray(o['points_1024x512'][2*pi:2*pi+2]);assert p.shape==q.shape
                err=float(np.max(np.abs(p-q)));assert err<1e-12
                assert (rid,pi) not in member_pairs;member_pairs[(rid,pi)]=m
                pairchecks+=1;max_error=max(max_error,err)
                p_to_w.setdefault(m['worker'],set()).add(r['worker_id'])
                members[rid]=r
        expected={r['record_id'] for r in comp.values() if r['image_code']==code and r['primary_included']}
        assert set(members)==expected and len(members)==doc['n']==auto['n']
        assert {x['id'] for x in auto['assignments']}==set(members)
        assert len({r['reference_object_id'] for r in members.values()})==1
        ridref=next(iter(members.values()))['reference_object_id'];refs[ridref]=geo[ridref]
        current_scope=collections.Counter()
        for rid in sorted(members):
            r=members[rid];o=obj[r['object_id']]
            assert {i for rr,i in member_pairs if rr==rid}==set(range(len(o['points_1024x512'])//2))
            projected=project_vertical_pairs(o['points_1024x512'])
            for k in ['top3d','bottom3d']:assert np.max(np.abs(np.asarray(projected[k])-np.asarray(geo[r['object_id']][k])))<1e-10
            current_scope[(o.get('scene_oos_status'),o.get('scene_doorway_status'))]+=1
            raw=np.asarray(o['before_preprocessing_points'],float);links=o['links_zero_based'];assert links and raw.ndim==2
            dx=np.array([((raw[j,0]-raw[i,0]+512)%1024)-512 for i,j in links])*360/1024
            b=dict(record_id=rid,object_id=r['object_id'],image_id=r['image_id'],image_code=code,worker_id=r['worker_id'],
                source_display_worker=next(m['worker'] for (rr,_),m in member_pairs.items() if rr==rid),condition=r['condition'],
                reference_object_id=ridref,reference_points_sha256=r['reference_points_sha256'],current_points_sha256=r['current_points_sha256'],
                raw_export_hash=datahash(o['original_export_points']),edited_before_shared_hash=datahash(o['before_preprocessing_points']),
                shared_ordered_hash=datahash(o['points_1024x512']),geometry_hash=datahash(geo[r['object_id']]),
                Xrms=float(np.sqrt(np.mean(dx*dx))),Xmax=float(np.max(np.abs(dx))),pairing_basis=o['pairing_basis'],
                ring_human_confirmed=bool(o['ring_confirmed']),order_status=o['order_status'],
                room_group=hold[rid]['room_group'],original_holdout=False,original_formal_gate=o['main_quality_gate'],
                reference_acceptance='preserved existing reference; not newly accepted by this endpoint audit')
            binding.append(b)
            inputs.append(dict(**b,original_export_points=o['original_export_points'],before_preprocessing_points=o['before_preprocessing_points'],
                preprocessed_points=o['preprocessed_points'],points_1024x512=o['points_1024x512'],links_zero_based=links,
                ordered_source_point_indices=o['ordered_source_point_indices'],geometry=geo[r['object_id']],reference_geometry=geo[ridref],
                inherited_components={k:r[k] for k in ['Q','iou_2d','iou_3d_corner_mean','S_top_deg','S_bottom_deg','Hmean','Hlocal','Hstar','dir','flat']}))
        unique={}
        for mode in ['automatic','assisted']:
            route=doc.get(mode)
            if not isinstance(route,dict):continue
            cand=route['candidate'];pts=cand.get('points');key=f'{code}:{mode}'
            if pts is None:
                endpoints.append(dict(endpoint_id=key,image_code=code,status=cand['status'],points=None,geometry=None,score_available=False,n=doc['n']))
                continue
            g=project_vertical_pairs(pts);fp=np.asarray(g['bottom3d'])[:,[0,2]];ferr=float(np.max(np.abs(fp-np.asarray(cand['footprint']))));assert ferr<1e-10
            max_floor_error=max(max_floor_error,ferr);poly=Polygon(fp);assert poly.is_valid
            ph=datahash(pts);duplicate=unique.get(ph);unique[ph]=key
            endpoints.append(dict(endpoint_id=key,image_code=code,image_id=doc['image_id'],n=doc['n'],condition='manual',member_record_ids=sorted(members),
                reference_object_id=ridref,reference_points_sha256=next(iter(members.values()))['reference_points_sha256'],
                source_commit=protocol['main_sha'],source_file=str(path.relative_to(W)),source_file_sha256=digest(path),
                source_fusion_method='cyclic_identity_all_person_MV50_coordinate_median',source_gap=doc['gap'],route=mode,
                source_candidate_status=cand['status'],source_candidate_reason=cand.get('reason'),source_geometry_status=cand['geometry_status'],
                source_ring_confirmed=bool(cand['ring_confirmed']),source_order_status=cand['order_status'],
                human_assisted_may_have_consulted_GT=(mode=='assisted'),applied_reviews=doc['applied_reviews'],
                exact_existing_points=pts,point_hash=ph,geometry=g,geometry_hash=datahash(g),reference_geometry=geo[ridref],
                reference_geometry_hash=datahash(geo[ridref]),independent_output=(duplicate is None),duplicate_of=duplicate,
                footprint_reprojection_error=ferr,camera_inside_or_on=bool(poly.covers(Point(0,0))),
                score_available=True,reference_acceptance='conditional on existing frozen reference, top/extent not newly human-approved',
                raw_original_input_diagnostic_available=False,raw_Xrms=None,raw_X_note='A fused shared-x result has no independent pre-average paired input; missing raw diagnostic is not zero error.',
                scope_marks=[dict(oos=k[0],doorway=k[1],n=v) for k,v in sorted(current_scope.items())]))
        availability.append(dict(image_code=code,state='complete_fixed_candidate_conditional',n=doc['n'],member_binding='all exact current pairs; no source added/removed',n_distinct_point_outputs=len(unique),count_trajectory_available=False))
    assert all(len(v)==1 for v in p_to_w.values());assert len(binding)==len({r['record_id'] for r in binding})==67
    assert protected=={k:digest(p) for k,p in sources.items()}
    summary=dict(schema='fixed_fusion_source_binding_v1',n_endpoint_rows=len(endpoints),n_independent_coordinate_outputs=sum(r.get('independent_output',False) for r in endpoints),
        n_images=3,n_source_records=67,n_source_workers=len({r['worker_id'] for r in binding}),n_source_pair_checks=pairchecks,max_source_pair_coordinate_difference_px=max_error,
        max_endpoint_footprint_reprojection_error=max_floor_error,availability=availability,
        worker_display_map={k:next(iter(v)) for k,v in sorted(p_to_w.items())},
        no_fusion_recomputed=True,no_member_removed_or_added=True,no_holdout_or_W019_personnel_restored=True,
        source_version_interpretation='67 existing source records exactly equal current shared ordered pairs; original and edited-before-shared arrays preserved separately for diagnostics.',
        endpoint_qualification='Geometrically computed candidates remain geometry_review; existing human order does not approve node identity, task scope, or reference top.',
        existing_count_curves='20261006 expected-area curves and floor-only GeoJSON do not provide per-team complete 3D source outputs; cannot re-score top penalties along those trajectories.',
        missing_inputs_for_count_or_composition_study=protocol['missing_inputs_for_count_or_composition_study'],
        source_manifest=source_manifest,protected_input_hashes=protected)
    dump(O/'fixed_fusion_source_audit.json',summary);dump(O/'fixed_fusion_endpoint_inputs.json',endpoints)
    dump(O/'fixed_fusion_member_inputs_67.json',inputs);csvout(O/'fixed_fusion_member_bindings_67.csv',binding)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['source_manifest','protected_input_hashes','worker_display_map']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
