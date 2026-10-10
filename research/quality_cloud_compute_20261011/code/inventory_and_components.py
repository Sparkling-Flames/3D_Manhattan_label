"""Read current loaders; preserve all events, gates and frozen-kernel failures."""
import argparse, copy, importlib.util, json, os, platform, sys, time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from common import read,save,sha,digest,csvwrite

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'frozen/scope_engine/core'))
from quality_v11 import score_geometry
from strict_geometry import validate_record

def task(job):
    identity,a,g=job
    result=score_geometry(a,g,spherical_samples=2048,height_samples=4096)
    return {**identity,**result}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--recovered',type=Path,required=True);ap.add_argument('--old',type=Path,required=True);ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
    sys.path.insert(0,str(args.repo))
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.materialize_current_research_input import load_current_input
    bundle=load_current_bundle();data=bundle['data'];assert data==load_current_input()
    objects={o['object_id']:o for o in data['objects']};images={i['image_id']:i for i in data['images']}
    oldbase=args.old/'inputs/baseline';oldgeom=read(oldbase/'prepared/frozen_expanded_geometry.json');oldfull=read(oldbase/'results_fixed/all_records_results.json')
    oldres={r['canonical_object_id']:r for r in oldfull};oldobjects={g['source_record']['canonical_object_id']:g for im in oldgeom['images'] for g in im['annotations']+im['groundtruths']}
    oldimages={im['imageId']:im for im in oldgeom['images']}
    spec=importlib.util.spec_from_file_location('frozen_original_adapter',ROOT/'frozen/prepare_expanded_original.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    geometries={};projection_checks=[]
    for oid,o in objects.items():
        old=oldobjects[oid];source=copy.deepcopy(old['source_record']);source.update(copy.deepcopy(o));source['id']=old['id'];source['canonical_object_id']=oid
        n=len(o.get('points_1024x512') or [])//2
        source['existing_ring_connections'].update({'top_edges':[[2*i,2*((i+1)%n)] for i in range(n)],'bottom_edges':[[2*i+1,2*((i+1)%n)+1] for i in range(n)],'paired_edges':[[2*i,2*i+1] for i in range(n)]})
        g=adapter.project_existing(source)
        # Keep original frozen floating-point representation only when ERP and the actual ring identities are exact.
        same=all(g.get(k)==old.get(k) for k in ['points','sourcePointIndices','sourcePairIndices']) and (n==0 or all((g.get('sourceExistingRingConnections') or {}).get(k)==(old.get('sourceExistingRingConnections') or {}).get(k) for k in ['top_edges','bottom_edges','paired_edges']))
        if same:
            for k in ['top3d','bottom3d']:g[k]=copy.deepcopy(old[k])
        geometries[oid]=g
        projection_checks.append({'object_id':oid,'record_id':g['id'],'object_kind':o['object_kind'],'exact_old_ERP_and_ring':same,'current_coordinates_sha256':digest(o.get('points_1024x512')),'old_coordinates_sha256':digest(old.get('points')),'projection_source':'old_frozen_exact_ERP_ring' if same else 'current_loader_existing_ring_projection','adapter_issues':g['adapter_issues']})
    registry=read(ROOT/'inputs/reference_exclusion_registry_20261010.json');restrictions={}
    for field in ['confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine','nonautomatic_review_cases','version_resolved_not_global_exclusion']:
        for row in registry[field]:
            for v in row['gt_versions']:
                restrictions.setdefault(v['gt_object_id'],[]).append({'registry_group':field,'classification':row['classification'],'restrict_primary':row['new_research_use'].get('exclude_this_reference_from_primary_gt_quality_comparison',False),'coordinate_hash':v['coordinates_sha256']})
    subset=read(args.recovered/'final_scope_reference_integration/inputs/current_formal_subset.json');overlay=read(args.recovered/'final_scope_reference_integration/inputs/normalized_confirmation_overlay.json');confirmed={r['image_id']:r for r in overlay['records']}
    scopechecks=[];ab=[]
    for im in subset['images']:
        c=confirmed[im['image_id']];A=im['original_gt'];B=c['polygon'];sel=im['selected_gt']
        from shapely.geometry import Polygon
        sys.path.insert(0,str(args.recovered/'final_scope_reference_integration'))
        from recompute_bev import project_floor, floor_change_kind
        pa,ast=project_floor(A['points_1024x512']);pb=Polygon(B)
        changed=pa is None or floor_change_kind(pb,pa)['change_kind']!='equivalent_within_tolerance'
        ar=restrictions.get(A['object_id'],[])
        ab.append({'image_id':im['image_id'],'image_code':im['image_code'],'A_object_id':A['object_id'],'A_version':A['object_kind'],'A_coordinates_sha256':digest(A['points_1024x512']),'A_geometry_status':ast,'A_restrictions':ar,'A_reference_primary_allowed':not any(x['restrict_primary'] for x in ar),'B_floor_sha256':digest(B),'B_confirmation_origin':c['confirmation_origin'],'B_decision':c['decision'],'B_top_status':'top_pending','B_reference_ready':False,'B_same_as_A_floor':not changed,'B_distinct_candidate_enabled':changed and c['decision']!='full_gt','mapping_type':'reference_only' if not im['in_current_formal_corpus'] else 'unchanged_original_only' if not changed else 'distinct_confirmed_floor','n_annotations':len(im['annotations']),'selected_reference_object_id':sel['object_id'],'selected_differs_from_A':sel['object_id']!=A['object_id'],'floor_change':floor_change_kind(pb,pa) if pa else None,'legality_basis':'latest user clarification approves A/B spaces, coordinate/top/reference restrictions remain separate'})
        for a in im['annotations']:
            o=objects[a['object_id']];ok=o['points_1024x512']==a['points_1024x512'] and o['worker_quality_gate']==a['worker_quality_gate'] and o['cleaning_disposition']==a['cleaning_disposition']
            assert ok,(im['image_code'],a['record_id']);scopechecks.append({'record_id':a['record_id'],'snapshot_equals_current_loader':ok})
    inventory=[];jobs=[];bindings=[]
    for oid,o in objects.items():
        if o['object_kind']!='annotation':continue
        im=images[o['image_id']];oi=oldimages[o['image_id']];old=oldres[oid];rid=old['record_id']
        # Retain historical fixed-reference bindings, resolving them to current object versions; never maximize Q.
        ref=next(g for g in oi['groundtruths'] if (g['id'],g['version'])==(old['reference_id'],old['reference_version']))
        gid=ref['source_record']['canonical_object_id'];g=geometries[gid];r=restrictions.get(gid,[]);restricted=any(x['restrict_primary'] for x in r)
        unresolved=any(x['registry_group']=='nonautomatic_review_cases' and any(t in x['classification'] for t in ['pending','unresolved','uncertain']) for x in r) or o['image_code'] in ['B6ByNegPMKs-37','q9vSo1VnCiC-34']
        reasons=[]
        if o['cleaning_disposition']!='retained':reasons.append('cleaning:'+o['cleaning_disposition'])
        if o['worker_quality_gate']!='candidate_pending_geometry':reasons.append('quality_gate:'+o['worker_quality_gate'])
        if restricted:reasons.append('reference_registry_restriction')
        if unresolved:reasons.append('unresolved_reference_diagnostic_only')
        c=confirmed.get(o['image_id']);probe=next(x for x in projection_checks if x['object_id']==oid)
        va=validate_record(geometries[oid],role='annotation');vg=validate_record(g,role='reference')
        row={'record_id':rid,'object_id':oid,'image_id':o['image_id'],'image_code':o['image_code'],'worker_id':o['worker_id'],'building_id':o['building_id'],'room_id':o['room_id'],'formal_input_commit':'24360ad8544d76d8aba18a8e641f784a76ca0d42','checkout_commit':'f485d49f0ccd57a7a7bf64931a81b770a37ff4df','raw_points_sha256':digest(o.get('original_export_points')),'current_points_sha256':probe['current_coordinates_sha256'],'old_points_sha256':probe['old_coordinates_sha256'],'geometry_changed_from_old':not probe['exact_old_ERP_and_ring'],'reference_object_id':gid,'reference_id':g['id'],'reference_version':objects[gid]['object_kind'],'reference_points_sha256':digest(objects[gid].get('points_1024x512')),'reference_restrictions':r,'cleaning_disposition':o['cleaning_disposition'],'worker_quality_gate':o['worker_quality_gate'],'main_quality_gate':o['main_quality_gate'],'main_consensus_gate':o['main_consensus_gate'],'independent_vote_eligible':o['independent_vote_eligible'],'ring_confirmed':o['ring_confirmed'],'condition':o['condition'],'scope_confirmation':digest(c) if c else None,'confirmed_floor_top_status':'top_pending' if c else None,'annotation_strict_available':va['available'],'reference_strict_available':vg['available'],'annotation_strict_reasons':va['reason_codes'],'reference_strict_reasons':vg['reason_codes'],'primary_gate_and_reference_allowed':not reasons,'primary_exclusion_reasons':reasons,'Manhattan_applicability_group':'domain_guard_nonorthogonal' if o['image_code']=='x8F5xyUWy9e-09' else 'ordinary_scene_supports_Manhattan' if oi.get('source_image_inventory',{}).get('later_scene_description')=='ordinary' and not reasons else 'other_or_unresolved_diagnostic','old_score_status':old['status'],'old_Q':old['quality_score'],'old_failure_codes':old['reason_codes'],'current_Q_status':'not_run'}
        inventory.append(row);bindings.append({'record_id':rid,'reference_object_id':gid,'policy':'retain_old_explicit_fixed_binding_resolved_to_current_version','chosen_using_Q':False});jobs.append((row,geometries[oid],g))
    save(ROOT/'results/loader_validation.json',{'current_bundle':bundle['validation'],'loaders_identical':True,'scope_snapshot_records_verified':len(scopechecks),'scope_snapshot_exact':all(x['snapshot_equals_current_loader'] for x in scopechecks)})
    for r in ab:
        r['original_A_distinct_from_confirmation_floor']=not r['B_same_as_A_floor']
        r['matching_A_uses_selected_existing_reference']=r['B_decision']=='full_gt'
        if r['B_decision']=='full_gt':r['mapping_type']='reference_only' if r['n_annotations']==0 else 'unchanged_existing_reference_only'
    save(ROOT/'results/AB_mapping.json',ab);csvwrite(ROOT/'results/AB_mapping.csv',ab);csvwrite(ROOT/'results/projection_checks.csv',projection_checks);csvwrite(ROOT/'results/record_inventory_before_scoring.csv',inventory);save(ROOT/'results/reference_bindings_before_scoring.json',bindings)
    save(ROOT/'inputs/current_geometry.json',{'schema':'current_loader_projection_fixed_binding_v1','geometries':geometries,'jobs':[{**r,'annotation_key':r['object_id'],'reference_key':r['reference_object_id']} for r in inventory]})
    t=time.perf_counter();save(ROOT/'results/run_contract_before_scoring.json',{'n':len(jobs),'workers':args.workers,'parameters':{'S':4,'Hstar':0.5,'D':5,'F':2,'alpha':0.15},'samples':{'sphere':2048,'height':4096},'policy':'all 3152 diagnostic scores retained; primary eligibility separate; no confirmed B top fabricated','sources':{'old_geometry':sha(oldbase/'prepared/frozen_expanded_geometry.json'),'old_results':sha(oldbase/'results_fixed/all_records_results.json'),'current_geometry':sha(ROOT/'inputs/current_geometry.json')},'Pro_input_status':'Library prepared exact reference but helper download failed; Pro definitions and 3021 per-record output not available'})
    full=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,result in enumerate(pool.map(task,jobs,chunksize=8),1):
            full.append(result)
            if i%200==0:print('scored',i,'/',len(jobs),'seconds',round(time.perf_counter()-t,1),flush=True)
    save(ROOT/'results/current_full_results.json',full)
    compact=[];delta=[]
    for x in full:
        m=x['metrics'];r={k:x[k] for k in inventory[0]};r.update(current_Q_status=x['status'],Q=x['quality_score'],failure_codes=x['reason_codes'],failure_classes=x['failure_classes'],**{k:m.get(k) for k in ['iou_2d','iou_3d_corner_mean','S_top_deg','S_bottom_deg','boundary_rms_deg','Hmean','Hlocal','Hstar','dir','flat','direction_bounded_loss','flatness_bounded_loss','range_ceiling_points','reference_factor']});r['primary_included']=r['primary_gate_and_reference_allowed'] and x['status']=='available';compact.append(r)
        old=oldres[x['object_id']];delta.append({'record_id':x['record_id'],'object_id':x['object_id'],'image_code':x['image_code'],'old_status':old['status'],'current_diagnostic_status':x['status'],'old_Q':old['quality_score'],'current_Q':x['quality_score'],'current_minus_old_Q':x['quality_score']-old['quality_score'] if x['quality_score'] is not None and old['quality_score'] is not None else None,'geometry_changed':x['geometry_changed_from_old'],'old_failure_codes':old['reason_codes'],'current_failure_codes':x['reason_codes'],'old_target_applicability':old['target_applicability'],'interpretation':'current raw mathematical diagnostic is not Pro policy or primary eligibility'})
    csvwrite(ROOT/'results/current_components.csv',compact);save(ROOT/'results/current_components.json',compact);csvwrite(ROOT/'results/old_to_current_diagnostic_delta.csv',delta)
    summary={'n_all_events':len(full),'current_mathematical_available':sum(x['status']=='available' for x in full),'old_available':sum(x['status']=='available' for x in oldfull),'primary_included':sum(x['primary_included'] for x in compact),'quality_gates':dict(Counter(x['worker_quality_gate'] for x in compact)),'AB_mapping_types':dict(Counter(x['mapping_type'] for x in ab)),'geometry_changed_annotations':sum(x['geometry_changed_from_old'] for x in compact),'elapsed_seconds':time.perf_counter()-t,'Pro_2979_to_3021_explanation':'not established without Pro per-record output; raw current diagnostic population has different reference policy','missing':['Pro alpha30/45 and stage13/24 frozen provenance','Pro target_protocol and official IoU audit','Pro 3021 per-record ledger']}
    summary['no_operation_full_gt_count']=sum(r['B_decision']=='full_gt' for r in ab)
    save(ROOT/'results/stage1_summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
