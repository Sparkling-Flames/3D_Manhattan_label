"""Reproduce all 35 images and 429 response routes from frozen inputs.

python routing/run_routing.py --baseline baseline --out routing/results
"""
from __future__ import annotations
import argparse,copy,csv,hashlib,json,math,sys,time
from collections import Counter
from pathlib import Path
import numpy as np
from shapely.geometry import Point
from router import strict_polygon,prepare_reference_set,export_distinguishing_regions,route_floor,floor_metrics,boundary_distance

ROOT=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text())
def dump(p,d):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvout(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r));p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def engine(baseline):
    e=baseline/'source_snapshot/research/quality_scope_comparison_20261010/frozen_engine'
    for x in ['core','legacy_geometry','height_revision','validity','traditional']:sys.path.insert(0,str(e/x))
    sys.path.insert(0,str(baseline/'scripts'))
    import audit_geometry,geometric_components,quality_v11,centered_height,strict_geometry,height_revision
    return audit_geometry,geometric_components,quality_v11,centered_height,strict_geometry,height_revision
def baseline_score(I,Sb,D,Hm=None,Hc=None):
    den=1+Sb**2/32+1.5*D**2/(D**2+37.5)
    if Hm is not None and Hc is not None:den+=(Hm/.8)**2+(Hc/.25)**2
    return 100*I/den
def raw_x(obj):
    p=obj.get('before_preprocessing_points');links=obj.get('links_zero_based')
    if p is None or not links:return {'status':'missing_original_pairing'}
    a=np.asarray(p,float);d=[]
    for i,j in links:d.append((((a[i,0]-a[j,0]+512)%1024)-512)*360/1024)
    x=float(np.sqrt(np.mean(np.square(d))))
    return {'status':'available','X_rms_deg':x,'Eperp_deg':x/2,'max_pair_x_difference_deg':float(np.max(np.abs(d))),
            'definition':'X_rms_deg=RMS(raw upper-lower shortest-periodic x difference); Eperp_deg=X_rms_deg/2',
            'source':'before_preprocessing_points + supplied links_zero_based; not averaged geometry'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,default=ROOT/'inputs/prepared_input.json');ap.add_argument('--config',type=Path,default=ROOT/'config.json');ap.add_argument('--baseline',type=Path,default=ROOT.parent/'baseline');ap.add_argument('--out',type=Path,default=ROOT/'results');args=ap.parse_args();start=time.time()
    data=load(args.inputs);cfg=load(args.config);au,sp,qv,ch,strict,hm=engine(args.baseline)
    prepared={};registry=[]
    for im in data['candidate_images']:
        allowed=[c for c in im['candidates'] if c['admitted_for_routing']]
        prepared[im['image_code']]=prepare_reference_set(allowed,cfg)
        registry.append({**im,'differentiating_regions_and_structures':export_distinguishing_regions(prepared[im['image_code']])})
    images={r['image_code']:r for r in data['candidate_images']};bycand={c['candidate_id']:c for im in data['candidate_images'] for c in im['candidates']}
    routes=[];metrics=[];full_by={};convergence=[];oldchecks=[];rawrows=[]
    for no,r in enumerate(data['records']):
        rid=r['record_id'];im=images[r['image_code']];g=r['geometry'];obj=r['source_object'];gate=r['current_eligibility_ledger'];manual=data['manual_overrides'].get(rid);family=data['manual_family_directives'].get(rid)
        raw=raw_x(obj);rawrows.append({'record_id':rid,'object_id':r['object_id'],**raw})
        base={k:r[k] for k in ['record_id','object_id','image_code','image_id','worker_id','condition','room_id','building_id','input_version','current_points_sha256_canonical_v1','raw_points_sha256_canonical_v1']}
        base.update(current_formal_gate=gate['current_formal_gate'],original_conditional_personnel_eligible=gate['conditional_personnel_eligible'],original_use_barriers=gate['use_barriers'],scene_oos_status=gate['scene_oos_status'],scene_doorway_status=gate['scene_doorway_status'],formal_eligibility_unchanged=True,raw_input_diagnostics=raw)
        if g is None:
            routes.append({**base,'status':'unavailable','selected_candidate_id':None,'route_reason':r['reconstruction_reason'],'quality_or_height_used_for_route':False});continue
        q=np.asarray(g['bottom3d'])[:,[0,2]]
        try:p=strict_polygon(q)
        except ValueError as e:
            routes.append({**base,'status':'unavailable','selected_candidate_id':None,'route_reason':str(e),'quality_or_height_used_for_route':False});continue
        if not p.contains(Point(0,0)):
            routes.append({**base,'status':'unavailable','selected_candidate_id':None,
                'route_reason':'camera_not_inside_preserved_floor_protocol',
                'geometric_footprint_available':True,'routing_protocol_applicable':False,
                'diagnostic_planar_metrics_only':{c['candidate_id']:floor_metrics(q,c['floor_xz_h']) for c in im['candidates']},
                'quality_or_height_used_for_route':False});continue
        auto=route_floor(q,prepared[r['image_code']]);effective=copy.deepcopy(auto);actual_manual=False
        if family:
            famrefs=[c for c in im['candidates'] if c['candidate_id'] in family['allowed_candidate_ids'] and c['admitted_for_routing']]
            effective=route_floor(q,prepare_reference_set(famrefs,cfg));effective['route_reason']='manual_structural_family_then_'+effective['route_reason'];effective['manual_family_source']=family
        if manual:
            assert manual['object_id']==r['object_id'] and manual['image_code']==r['image_code']
            chosen=manual['selected_candidate_id'];assert bycand[chosen]['admitted_for_routing'];effective['candidate_id']=chosen;effective['route_reason']='explicit_user_reference_assignment';effective['uncertainty']='manual_directive_quality_and_confidence_not_inferred';effective['manual_source']=manual;actual_manual=True
        selected=effective['candidate_id'];D=float(au.direction_residual(g,au.direction_axis(g)));theta,weight=au.direction_data(g);axis=au.direction_axis(g);res=np.degrees((theta-axis+np.pi/4)%(np.pi/2)-np.pi/4)
        direction={'D_deg':D,'axis_deg':float(np.degrees(axis)),'wall_lengths_h':weight.tolist(),'wall_residuals_deg':res.tolist(),'wall_length_fraction':(weight/weight.sum()).tolist()}
        m_this={}
        for c in im['candidates']:
            cid=c['candidate_id'];floor=c['floor_xz_h'];fm=floor_metrics(q,floor);refbottom=np.column_stack((np.array(floor)[:,0],np.full(len(floor),-1.),np.array(floor)[:,1])).tolist()
            Sb=float(sp.spherical_sym_distance(g['bottom3d'],refbottom,cfg['spherical_samples']));Sb1024=float(sp.spherical_sym_distance(g['bottom3d'],refbottom,1024))
            m={**base,'candidate_id':cid,'space_label':c['space_label'],'reference_object_id':c['reference_object_id'],'reference_version':c['reference_version'],
               'reference_points_sha256_canonical_v1':c['points_sha256_canonical_v1'],'reference_floor_sha256_canonical_v1':c['floor_sha256_canonical_v1'],
               'admitted_for_routing':c['admitted_for_routing'],'top_status':c['top_status'],'full_reference_available':c['full_reference_available'],
               'floor_status':'available','full_status':'unavailable_top_pending','full_unavailable_reasons':['top_pending'],'metric_samples':{'spherical':cfg['spherical_samples'],'height':cfg['height_samples']},
               **fm,'Sb_deg':Sb,'D_deg':D,'direction_diagnostics':direction,'Hm':None,'Hc':None,'IoU3D_corner_mean':None,'IoU3D_perimeter_mean':None,
               'Q_full_baseline':None,'Q_floor_baseline':baseline_score(fm['I'],Sb,D),'Q_v11_fixed_this_reference':None}
            if c['full_reference_available']:
                ref=c['full_geometry'];old=qv.score_geometry(g,ref,spherical_samples=cfg['spherical_samples'],height_samples=cfg['height_samples'])
                m['full_status']=old['status'];m['full_unavailable_reasons']=old['reason_codes'];m['full_geometry_validity']={'annotation':old['annotation_validity'],'reference':old['reference_validity']}
                om=old['metrics'];m['IoU3D_corner_mean']=om.get('iou_3d_corner_mean');m['IoU3D_perimeter_mean']=om.get('iou_3d_perimeter_mean')
                if old['status']=='available':
                    hh=ch.centered_height_components(g,ref,samples=cfg['height_samples'],height_module=hm)
                    m['Hm']=om['Hmean'];m['Hc']=hh['Hcenter'];m['S_top_deg']=om['S_top_deg'];m['Q_v11_fixed_this_reference']=old['quality_score'];m['Q_full_baseline']=baseline_score(fm['I'],Sb,D,m['Hm'],m['Hc'])
                    m['height_diagnostics']=hh
                    if abs(om['S_bottom_deg']-Sb)>1e-9:raise AssertionError('same floor spherical metric mismatch')
            m['full_primary_use_permitted']=c['admitted_for_routing'] and m['full_status']=='available' and gate['current_formal_gate']=='candidate_pending_geometry'
            m['quality_grade']=None;m['scope_routing_is_quality_approval']=False
            metrics.append(m);m_this[cid]=m
            convergence.append({'record_id':rid,'candidate_id':cid,'Sb_1024_deg':Sb1024,'Sb_2048_deg':Sb,'absolute_delta_deg':abs(Sb1024-Sb),
                 'Q_floor_1024':baseline_score(fm['I'],Sb1024,D),'Q_floor_2048':m['Q_floor_baseline'],'absolute_Q_floor_delta':abs(baseline_score(fm['I'],Sb1024,D)-m['Q_floor_baseline'])})
        current=m_this[selected];original=m_this[im['original_reference_candidate']];fixed=m_this[im['previous_fixed_selected_reference_candidate']]
        old=r['old_scope_metrics'];oldI=(old.get('selected_gt_metrics') or {}).get('bev_iou')
        if oldI is not None:oldchecks.append({'record_id':rid,'old_I':oldI,'new_recompute_same_reference_I':fixed['I'],'absolute_difference':abs(oldI-fixed['I']),'old_geometry_status':old['geometry_status'],'new_geometry_status':'valid'})
        row={**base,'status':'available','selected_candidate_id':selected,'selected_reference_version':bycand[selected]['reference_version'],
             'selected_reference_floor_sha256_canonical_v1':bycand[selected]['floor_sha256_canonical_v1'],'selected_top_status':bycand[selected]['top_status'],
             'selected_full_status':current['full_status'],'selected_full_unavailable_reasons':current['full_unavailable_reasons'],
             'route_reason':effective['route_reason'],'uncertainty':effective['uncertainty'],'manual_directive_applied':actual_manual,'manual_family_applied':bool(family),
             'automatic_without_manual':auto,'effective_local_routing':effective,'previous_fixed_candidate_id':im['previous_fixed_selected_reference_candidate'],
             'historical_original_candidate_id':im['original_reference_candidate'],'I_original':original['I'],'I_previous_fixed':fixed['I'],'I_selected':current['I'],
             'Sb_original_deg':original['Sb_deg'],'Sb_selected_deg':current['Sb_deg'],'D_deg':D,
             'Q_floor_original':original['Q_floor_baseline'],'Q_floor_previous_fixed':fixed['Q_floor_baseline'],'Q_floor_selected':current['Q_floor_baseline'],
             'Q_full_original':original['Q_full_baseline'],'Q_full_previous_fixed':fixed['Q_full_baseline'],'Q_full_selected':current['Q_full_baseline'],
             'IoU3D_original':original['IoU3D_corner_mean'],'IoU3D_selected':current['IoU3D_corner_mean'],
             'floor_quality_available':True,'floor_scoring_is_not_full_quality':True,'quality_or_height_used_for_route':False,'true_intent_established':False,'route_is_quality_acceptance':False}
        routes.append(row)
        if (no+1)%50==0:print(f'Processed {no+1}/{len(data["records"])}',flush=True)
    image_results=[]
    for im in data['candidate_images']:
        rr=[x for x in routes if x['image_code']==im['image_code']];ok=[x for x in rr if x['status']=='available'];allowed=[c for c in im['candidates'] if c['admitted_for_routing']]
        image_results.append({'image_code':im['image_code'],'image_id':im['image_id'],'room_id':im['room_id'],'confirmed_at':im['source_reference_registry_entry']['confirmation_provenance'].get('confirmed_at'),
            'in_formal_corpus':im['in_formal_corpus'],'unique_candidates_total':len(im['candidates']),'admitted_candidate_count':len(allowed),'admitted_full_candidate_count':sum(c['full_reference_available'] for c in allowed),
            'admitted_candidate_ids':[c['candidate_id'] for c in allowed],'records':len(rr),'floor_routes_available':len(ok),'floor_routes_unavailable':len(rr)-len(ok),
            'routes_to_floor_only_reference':sum(x['selected_top_status']=='top_pending' for x in ok),'selected_candidate_counts':dict(Counter(x['selected_candidate_id'] for x in ok)),
            'route_reason_counts':dict(Counter(x['route_reason'] for x in ok)),
            'switches_vs_previous_fixed':sum(x['selected_candidate_id']!=x['previous_fixed_candidate_id'] for x in ok),
            'reference_gap':im['reference_only_reason'],'original_reference_restriction':im['original_reference_restriction']})
    ok=[r for r in routes if r['status']=='available'];multi=[r for r in ok if len([c for c in images[r['image_code']]['candidates'] if c['admitted_for_routing']])>1]
    comparisons=[]
    old30={r['record_id']:r for r in data['old_T30_local_evidence']['rows']}
    for r in routes:
        if r['record_id'] in old30 and r['status']=='available':
            old=old30[r['record_id']];comparisons.append({'record_id':r['record_id'],'old_candidate':old['geometric_candidate_space'],'old_reason':old['geometric_candidate_route'],
                'new_auto_candidate':r['automatic_without_manual']['candidate_id'].rsplit(':',1)[-1],'new_effective_candidate':r['selected_candidate_id'].rsplit(':',1)[-1],
                'new_route_reason':r['route_reason'],'old_front_coverage':old['front_difference_coverage'],'new_uncertainty':r['uncertainty']})
    reviewchecks=[]
    byrid={r['record_id']:r for r in routes}
    for ev in data['development_space_review_evidence']:
        r=byrid[ev['record_id']];reviewchecks.append({**ev,'automatic_candidate':r.get('automatic_without_manual',{}).get('candidate_id'),'effective_candidate':r.get('selected_candidate_id'),
            'automatic_agrees_with_effective_human_target':(r.get('automatic_without_manual',{}).get('candidate_id')==ev['image_code']+':'+ev['effective_target']) if ev['effective_target'] else None})
    summary={'counts':data['counts'],'routes_available':len(ok),'routes_unavailable':len(routes)-len(ok),'multi_candidate_record_count':len(multi),
             'route_reason_counts':dict(Counter(r['route_reason'] for r in ok)),'uncertainty_counts':dict(Counter(r['uncertainty'] for r in ok)),
             'selected_floor_only_count':sum(r['selected_top_status']=='top_pending' for r in ok),'selected_full_quality_available_count':sum(r['selected_full_status']=='available' for r in ok),
             'switches_vs_previous_fixed':sum(r['selected_candidate_id']!=r['previous_fixed_candidate_id'] for r in ok),
             'auto_vs_global_IoU_disagreement_count':sum(r['automatic_without_manual']['candidate_id']!=r['automatic_without_manual']['global_iou_best'] for r in multi),
             'area_only_vs_main_auto_disagreement_count':sum(r['automatic_without_manual']['candidate_id']!=r['automatic_without_manual']['area_only_best'] for r in multi),
             'boundary_only_vs_main_auto_disagreement_count':sum(r['automatic_without_manual']['candidate_id']!=r['automatic_without_manual']['boundary_only_best'] for r in multi),
             'maximum_prior_floor_IoU_recompute_difference':max(x['absolute_difference'] for x in oldchecks),'prior_comparison_rows':len(oldchecks),
             'max_Sb_1024_2048_deg':max(x['absolute_delta_deg'] for x in convergence),'max_Q_floor_1024_2048':max(x['absolute_Q_floor_delta'] for x in convergence),
             'all_noncomputable_kept_not_zeroed':True,'top_grafting_performed':False,'parameters_are_provisional_evidence_bands_not_quality_grade_cuts':True}
    dump(args.out/'reference_candidates.json',{'schema':'confirmed_multispace_candidates_v1','images':registry,'counts':data['counts']});dump(args.out/'routes.json',{'schema':'multispace_response_routes_v1','config':cfg,'rows':routes})
    candidate_rows=[]
    for im in registry:
        for c in im['candidates']:
            candidate_rows.append({'image_code':im['image_code'],'image_id':im['image_id'],'candidate_id':c['candidate_id'],'space_label':c['space_label'],
                'reference_object_id':c['reference_object_id'],'reference_version':c['reference_version'],'floor_sha256_canonical_v1':c['floor_sha256_canonical_v1'],
                'points_sha256_canonical_v1':c['points_sha256_canonical_v1'],'admitted_for_routing':c['admitted_for_routing'],'top_status':c['top_status'],
                'full_reference_available':c['full_reference_available'],'confirmed_at':c.get('confirmed_at'),'candidate_area_h2':strict_polygon(c['floor_xz_h']).area,
                'candidate_vertices':len(c['floor_xz_h']),'human_confirmation_source':c['human_confirmation_source'],'restriction':c['restriction'],'aliases':c['aliases']})
    csvout(args.out/'reference_candidates.csv',candidate_rows)
    oracle=[]
    for r in ok:
        allowed=[m for m in metrics if m['record_id']==r['record_id'] and m['admitted_for_routing']]
        bestfloor=max(allowed,key=lambda m:m['Q_floor_baseline']);full=[m for m in allowed if m['Q_full_baseline'] is not None]
        bestfull=max(full,key=lambda m:m['Q_full_baseline']) if full else None
        oracle.append({'record_id':r['record_id'],'image_code':r['image_code'],'protocol_candidate':r['selected_candidate_id'],
            'oracle_floor_candidate':bestfloor['candidate_id'],'oracle_floor_Q':bestfloor['Q_floor_baseline'],
            'oracle_full_candidate':bestfull['candidate_id'] if bestfull else None,'oracle_full_Q':bestfull['Q_full_baseline'] if bestfull else None,
            'oracle_full_admitted_subset_only':True,'full_reference_missing_for_other_candidates':any(m['Q_full_baseline'] is None for m in allowed),
            'is_protocol_reference_selection':False,'oracle_maximum_is_quality_diagnostic_only':True})
    dump(args.out/'oracle_diagnostic_separate.json',{'rows':oracle,'warning':'Never infer the selected reference from this file. Full oracle excludes candidates with unconfirmed ceilings and is not a complete allowed-set score.'})
    dump(args.out/'all_candidate_metrics.json',{'schema':'all_legal_and_restricted_candidate_metrics_v1','rows':metrics,'definition':'restricted references retained only as explicit diagnostics; never route or primary comparison'});dump(args.out/'image_manifest.json',{'images':image_results});csvout(args.out/'image_manifest.csv',image_results)
    compact=[{k:v for k,v in r.items() if k not in ['automatic_without_manual','effective_local_routing','input_version','raw_input_diagnostics']} for r in routes]
    csvout(args.out/'routes.csv',compact);csvout(args.out/'all_candidate_metrics.csv',[{k:v for k,v in r.items() if k not in ['input_version','direction_diagnostics','height_diagnostics','full_geometry_validity','raw_input_diagnostics']} for r in metrics])
    dump(args.out/'sampling_convergence_1024_2048.json',{'rows':convergence});dump(args.out/'prior_floor_recompute_check.json',{'rows':oldchecks});dump(args.out/'old_T30_route_comparison.json',{'rows':comparisons});dump(args.out/'human_space_development_check.json',{'rows':reviewchecks});dump(args.out/'raw_x_diagnostics.json',{'rows':rawrows});dump(args.out/'summary.json',summary)
    dump(args.out/'run_provenance.json',{'input_sha256':hashlib.sha256(args.inputs.read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(args.config.read_bytes()).hexdigest(),'python':sys.version,'numpy':np.__version__,'elapsed_seconds':time.time()-start,'records_executed':len(routes),'candidate_metric_rows':len(metrics),'baseline_argument':str(args.baseline.resolve())})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
