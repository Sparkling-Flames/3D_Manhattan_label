"""30 distinct developer records; read-only sources, deterministic private selection.
No Q-based spatial intention or final user answer is generated.
"""
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data): Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def rows(path): return list(csv.DictReader(open(path,encoding='utf-8-sig',newline='')))
def nearest(pool,key,value,side):
    p=[r for r in pool if (r[key]<value if side=='below' else r[key]>value)]
    return min(p,key=lambda r:(abs(r[key]-value),r['image_code'],r['record_id'])) if p else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--frozen-root',type=Path,required=True);ap.add_argument('--photo-root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();out=args.out;out.mkdir(exist_ok=True,parents=True);res=args.frozen_root/'results'
    components=read(res/'current_components.json');comp={r['record_id']:r for r in components};alignment={r['record_id']:r for r in read(res/'target_alignment_ledger.json')};holdout={r['record_id']:r for r in rows(res/'room_holdout_manifest.csv')};variants={r['record_id']:r for r in rows(res/'Pro_variants_replayed_current.csv')};AB={r['image_code']:r for r in read(res/'AB_mapping.json')};margins={r['record_id']:r for r in read(res/'AB_margins_all_events.json')}
    old=read(args.frozen_root/'blind_sample/answer_mapping_private.json');exposed_records={};exposed_images={}
    for r in old:
        exposed_images.setdefault(r['image_code'],[]).append(r['case_id'])
        for k in ['record_1','record_2']:
            if r.get(k):exposed_records.setdefault(r[k],[]).append(r['case_id'])
    held={r for r,h in holdout.items() if h['held_out_of_sample_and_future_calibration']=='True'}
    pool=[r for r in components if alignment[r['record_id']]['target_unconfounded_conservative'] and r['record_id'] not in held]
    assert len(pool)==907 and len({r['image_code'] for r in pool})==83 and len(held)==282
    control=lambda r:r['iou_2d']>=.6 and r['boundary_rms_deg']<=6 and r['Hstar']<=.4
    Dpool=[r for r in pool if control(r) and r['flat']<=3];Fpool=[r for r in pool if control(r) and r['dir']<=5]
    chosen=[];inventory=[]
    def add(r,reason,**extra):
        assert r is not None
        if r['record_id'] in [x['record_id'] for x in chosen]:
            next(x for x in chosen if x['record_id']==r['record_id'])['selection_labels'].append(reason)
            return
        chosen.append({'record_id':r['record_id'],'selection_labels':[reason],**extra})
    for metric,key,levels,subset in [('Q','Q',[95,85,50,90,75,60],pool),('D','dir',[5,10,15,20],Dpool),('F','flat',[2,4,6,8],Fpool)]:
        for level in levels:
            for side in ['below','above']:
                r=nearest(subset,key,level,side);raw=nearest(pool,key,level,side)
                inventory.append({'metric':metric,'level':level,'side':side,'candidate_pool_n':len(subset),'control':'frozen S=boundary_rms_deg; I>=.6,S<=6,Hstar<=.4,'+('F<=3' if metric=='D' else 'D<=5') if metric!='Q' else '907 development records','nearest_record_id':r['record_id'] if r else None,'nearest_value':r[key] if r else None,'absolute_distance':abs(r[key]-level) if r else None,'uncontrolled_nearest_record_id':raw['record_id'] if raw else None,'uncontrolled_nearest_value':raw[key] if raw else None})
                if metric=='Q' and level in [95,85,50] or metric=='D' and (level<20 or side=='below') or metric=='F' and level in [2,4,6]:
                    if r:add(r,f'{metric}{level}_{side}_controlled_nearest' if metric!='Q' else f'Q_v11_{level}_{side}_exact_pool_nearest',selection_metric=metric,selection_boundary=level,selection_side=side,control_satisfied=True)
                    elif metric=='F' and level==6 and side=='above':
                        add(raw,'F6_above_uncontrolled_nearest_mixed_D_F_diagnostic',selection_metric=metric,selection_boundary=level,selection_side=side,control_satisfied=False)
    # Additional contrasts are sampling proxies, never claims of real human severity.
    hp=[r for r in pool if r['iou_2d']>=.7 and r['dir']<=5 and r['flat']<=2]
    add(min(hp,key=lambda r:(-r['Hstar'],r['image_code'],r['record_id'])),'high_Hstar_with_high_floor_I_low_D_F; S_also_large_not_single_error')
    sp=[r for r in pool if r['dir']<=5 and r['flat']<=2]
    add(min(sp,key=lambda r:(r['iou_2d'],r['image_code'],r['record_id'])),'lowest_floor_I_under_low_D_F_scope_position_proxy')
    lp=[r for r in pool if r['iou_2d']>=.6 and r['dir']<=5 and r['flat']<=2]
    add(min(lp,key=lambda r:(-(r['Hlocal']-r['Hmean']),r['image_code'],r['record_id'])),'largest_Hlocal_minus_Hmean_under_control; structural_proxy_not_confirmed_cause')
    for rid in ['R01973','R02447']:add(comp[rid],'same_image_same_reference_existing_alpha30_rank_conflict; general_absolute_rating_first')
    assert len(chosen)==24
    spacepool=[r for r in margins.values() if r['target_count']==2 and r['status']=='valid' and AB[r['image_code']]['A_reference_primary_allowed'] and comp[r['record_id']]['primary_gate_and_reference_allowed'] and r['record_id'] not in held]
    assert len(spacepool)==272 and len({r['image_code'] for r in spacepool})==21
    # Explicit reviewed candidates. The fine six-stratum choices are adaptive;
    # recorded transparently after numeric inventory, no prior blinded-selection claim.
    spatial=[('R00169','A_only_sensitivity_nonidentical_floor'),('R02061','B_only_sensitivity'),('R03438','both_compatible_sensitivity'),('R03091','boundary_corner_preference_conflict_detail'),('R03192','both_exclusive_regions_intersected_and_absolute_far; not_proven_diagonal_intention'),('R02962','both_far_sensitivity_separate_image')]
    for rid,label in spatial:
        assert rid in {r['record_id'] for r in spacepool};add(comp[rid],label,control_satisfied=False)
    assert len(chosen)==30 and len({r['record_id'] for r in chosen})==30
    quality=chosen[:24];result=[]
    for i,s in enumerate(chosen,1):
        r=comp[s['record_id']];p=args.photo_root/(r['image_code']+'.jpg');assert p.is_file();cid=f'T{i:02d}';is_quality=i<=24
        from PIL import Image
        with Image.open(p) as im:im.load();size=list(im.size)
        assert r['record_id'] not in held and r['primary_gate_and_reference_allowed']
        assert all(not x.get('restrict_primary',False) for x in r['reference_restrictions'])
        value={'case_id':cid,'case_type':'single_absolute_quality' if is_quality else 'single_floor_space_compatibility','object_id':r['object_id'],'image_code':r['image_code'],'image_id':r['image_id'],'worker_id_private':r['worker_id'],'room_group':holdout[r['record_id']]['room_group'],'room_id':r['room_id'],'building_id':r['building_id'],'held_out':False,'selection_private':s,'formal_gate_and_reference_allowed':r['primary_gate_and_reference_allowed'],'target_unconfounded_conservative':alignment[r['record_id']]['target_unconfounded_conservative'],'target_alignment_ledger':alignment[r['record_id']],'reference_object_id':r['reference_object_id'],'reference_id':r['reference_id'],'reference_version':r['reference_version'],'reference_points_sha256':r['reference_points_sha256'],'current_points_sha256':r['current_points_sha256'],'reference_restrictions':r['reference_restrictions'],'components':{k:r[k] for k in ['Q','iou_2d','iou_3d_corner_mean','boundary_rms_deg','S_top_deg','S_bottom_deg','Hmean','Hlocal','Hstar','dir','flat','annotation_strict_available','reference_strict_available','annotation_strict_reasons','reference_strict_reasons','Manhattan_applicability_group']},'frozen_formulas':{k:float(variants[r['record_id']][k]) for k in ['Q_v11','Q_alpha30','Q_alpha45','Q_stage13','Q_stage24']},'Q_values_scope':'existing frozen A/reference only; no B full Q; spatial rows are diagnostics, not strict calibration','formula_boundary_distances':{k:{str(b):float(variants[r['record_id']][k])-b for b in [50,60,75,85,90,95]} for k in ['Q_v11','Q_alpha30','Q_alpha45','Q_stage13','Q_stage24']},'direction_boundary_distances':{str(b):r['dir']-b for b in [5,10,15,20]},'flatness_boundary_distances':{str(b):r['flat']-b for b in [2,4,6,8]},'photo_source_asset_name':p.name,'photo_sha256':sha(p),'photo_size':size,'pixel_decode_succeeded':True,'visual_applicability_final_owner_pending':True,'historical_material':True,'historically_unseen_claimed':False,'old8_record_exposure':exposed_records.get(r['record_id'],[]),'old8_image_exposure':exposed_images.get(r['image_code'],[]),'pure_single_error_claimed':False,'user_answers_prefilled':False}
        if not is_quality:value.update({'AB_reference_ledger':AB[r['image_code']],'space_geometry_metrics':margins[r['record_id']],'new_B_top_status':'top_pending','new_B_full_quality_available':False,'spatial_intention_inferred':False,'sampling_boundary_rms_absolute_h':.25,'sampling_threshold_is_final':False})
        result.append(value)
    assert len({r['object_id'] for r in result})==30
    source_paths=[res/'current_components.json',res/'target_alignment_ledger.json',res/'room_holdout_manifest.csv',res/'AB_mapping.json',res/'AB_margins_all_events.json',res/'Pro_variants_replayed_current.csv']
    manifest={'selection_version':'quality_review30_selection_v1','main_checked_and_merged':'9c1d91173bf8ec50de4983daaff325b339965e04','formal_input_commit':'24360ad8544d76d8aba18a8e641f784a76ca0d42','source_handoff_commit':'f485d49f0ccd57a7a7bf64931a81b770a37ff4df','scope_baseline_commit':'42f7ea569c591c0cb3472e1b8bb8c0d883bbd3cb','official_HoHoNet_IoU_upstream_commit':'2bbc0866789cf7ad728064bc52aaf1d11b67c885','Pro_original_archive_sha256':'d54895af3620d8dd6bc3bd04537c1842dcd1fc79b0f7d729453af52dbe9ba292','selection_status':'frozen_candidate_list_for_owner_review_before_final_render','counting_unit':'distinct record_id AND object_id; optional pair is not another record','selection_adaptations_disclosed':['S means frozen boundary_rms_deg, not S_top+S_bottom. First unsaved diagnostic accidentally used sum; corrected before freezing.','F6 upper has no controlled record. One uncontrolled global-nearest high D/F record reserved as mixed diagnostic, not controlled endpoint evidence.','Six spatial fine choices use observed metric conflicts and distinct photos; not a fully blinded or wholly predeclared fine selection.','Hstar, I and Hlocal-Hmean are auxiliary sampling proxies; they do not label human severity or causes.'],'sources':[{'relative_path':str(p.relative_to(args.frozen_root)),'sha256':sha(p)} for p in source_paths],'case_count':30,'quality_count':24,'space_count':6,'quality_pool_n':907,'quality_pool_images':83,'frozen_holdout_n':282,'strict_1059_held_overlap':152,'space_pool_n':272,'space_pool_images':21,'quality_selected_room_groups':len({r['room_group'] for r in result[:24]}),'selected_images':len({r['image_code'] for r in result}),'optional_pair_questions':[{'pair_id':'P01','left_case_id':'T23','right_case_id':'T24','independent_of_30_single_answers':True,'same_image':True,'same_reference':True,'private_reason':'known alpha30 vs v11 ranking inversion','not_cross_image_ranking':True}],'records':result,'no_final_thresholds_selected':True,'no_human_judgments_generated':True,'cannot_estimate_population_severity_prevalence':True,'not_66_candidate_joint_tuning_or_generalization_claim':True}
    for inv in inventory:
        metric,key=inv['metric'],{'Q':'Q','D':'dir','F':'flat'}[inv['metric']];ids=[r['record_id'] for r in quality];selected=[comp[rid] for rid in ids];near=nearest(selected,key,inv['level'],inv['side']);inv.update({'selected_nearest_record_id':near['record_id'] if near else None,'selected_nearest_value':near[key] if near else None,'selected_distance':abs(near[key]-inv['level']) if near else None,'global_controlled_nearest_is_selected':bool(inv['nearest_record_id'] in ids if inv['nearest_record_id'] else False),'selected_nearest_satisfies_control':bool(near and (metric=='Q' or (control(near) and (near['flat']<=3 if metric=='D' else near['dir']<=5))))})
    save(out/'selection_private.json',manifest);save(out/'boundary_coverage_private.json',inventory)
    fields=['case_id','record_id','object_id','case_type','image_code','room_group','selection_reason','Q_v11','Q_alpha30','Q_alpha45','Q_stage13','Q_stage24','I','S_deg','Hstar','D_deg','F_deg','old8_record_exposure','old8_image_exposure','photo_sha256']
    with (out/'selection_private.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        for r in result:
            c=r['components'];w.writerow({'case_id':r['case_id'],'record_id':r['selection_private']['record_id'],'object_id':r['object_id'],'case_type':r['case_type'],'image_code':r['image_code'],'room_group':r['room_group'],'selection_reason':'; '.join(r['selection_private']['selection_labels']),**r['frozen_formulas'],'I':c['iou_2d'],'S_deg':c['boundary_rms_deg'],'Hstar':c['Hstar'],'D_deg':c['dir'],'F_deg':c['flat'],'old8_record_exposure':','.join(r['old8_record_exposure']),'old8_image_exposure':','.join(r['old8_image_exposure']),'photo_sha256':r['photo_sha256']})
    save(out/'selection_audit.json',{k:v for k,v in manifest.items() if k!='records'}|{'record_ids_unique':True,'object_ids_unique':True,'quality_all_in_907':True,'holdout_intersection':[],'errors_or_holds_restored':False,'current_main_pushed':False,'photo_bytes_decoded':30,'all_quality_mathematics_available':True,'max_quality_records_per_image':max(Counter(r['image_code'] for r in result[:24]).values()),'source_photo_unique_hash_count':len({r['photo_sha256'] for r in result}),'private_mapping_sha256':sha(out/'selection_private.json')})
    print(json.dumps({'cases':30,'quality':24,'space':6,'images':manifest['selected_images'],'quality_room_groups':manifest['quality_selected_room_groups'],'mapping_sha256':sha(out/'selection_private.json')},ensure_ascii=False))
if __name__=='__main__':main()
