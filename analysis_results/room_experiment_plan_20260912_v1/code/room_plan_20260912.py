"""Pinned room-selection audit. Read-only inputs; candidate list is not dispatch.

Run: python room_plan_20260912.py --repo DATA_ROOT --out RESULT_ROOT
Only Python, NumPy and pandas are required. No encoded executable source.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,sys
from collections import Counter,defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
PIN='b3c7de88b03e005a85f610de2576ea97a988db34'
CURRENT={1,2,6,8,10,11,12,13,15,17,*range(28,38)}
SCENE=Path('analysis_results/scene_image_exploration_20260910_v1')
VIEW=Path('analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz')
EV=Path('analysis_results/annotation_research_prework_20260905_v2/evidence/record_evidence.csv')
STAGES=Path('analysis_results/research_validation_20260909_v2/stages/image_stage_onsets.csv')
PAIRS=[('G047',15,6,'core'),('G207',15,4,'core'),('G237',26,5,'core'),('G165',15,2,'core'),('G200',70,74,'core'),('G036',33,37,'closure_challenge'),('G057',7,4,'detail_challenge_H19'),('G197',47,75,'misleading_view_challenge'),('G202',53,26,'ambiguity_challenge_pool_pending')]
EXTRAS=[('G004',8,'boundary_interior'),('G004',7,'boundary_doorway'),('G174',80,'boundary_interior'),('G174',2,'boundary_doorway'),('G002',2,'optional_multiview_regular'),('G002',5,'optional_multiview_regular'),('G002',10,'optional_multiview_difficult'),('G014',8,'OOS_existing_dense'),('G014',12,'OOS_existing_dense'),('G014',17,'OOS_optional_extension'),('G014',22,'OOS_optional_extension')]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(out,name,rows):
    d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    d.to_csv(out/name,index=False,encoding='utf-8-sig',float_format='%.12g');return d

def main(repo,out):
    out.mkdir(parents=True,exist_ok=True)
    reg=read(repo/SCENE/'same_room_selection_registry_20260912.json')
    rows=[json.loads(x) for x in gzip.open(repo/VIEW,'rt',encoding='utf-8')]
    ev=pd.read_csv(repo/EV,dtype=str,keep_default_na=False)
    assert len(rows)==2501 and len({r['canonical_annotation_id'] for r in rows})==2501
    assert set(ev.canonical_annotation_id)=={r['canonical_annotation_id'] for r in rows}
    byimage=defaultdict(list);checks=[];manifest=[]
    for r in rows:byimage[r['image_id']].append(r)
    for source in sorted({r['raw_export_path'] for r in rows}):
        assert set(ev.loc[ev.raw_export_path==source,'raw_export_sha256'])=={sha(repo/source)}
        index={}
        for t in read(repo/source):
            for a in t.get('annotations',[]):
                key=(str(t['id']),str(a['id']));assert key not in index;index[key]=(t,a)
        count=0
        for r in rows:
            if r['raw_export_path']!=source:continue
            _,_,task,worker,ann=r['raw_annotation_version_id'].split('|');t,a=index[(task,ann)]
            w=a['completed_by'];w=w['id'] if isinstance(w,dict) else w
            assert str(w)==worker==str(r['worker_id'])
            assert r['image_id'] in json.dumps(t['data'])
            pts=[[float(x['value']['x'])*1024/100,float(x['value']['y'])*512/100] for x in a.get('result',[]) if x.get('type')=='keypointlabels']
            x=np.array(pts,float).reshape(-1,2);y=np.array(r['raw_points_1024x512'],float).reshape(-1,2)
            assert x.shape==y.shape and np.allclose(x,y,atol=1e-8,rtol=0,equal_nan=True)
            assert not r['unassisted_manual_included'] or (r['calculation_included'] and r['assistance_exposure']=='none')
            checks.append(dict(canonical_annotation_id=r['canonical_annotation_id'],image_id=r['image_id'],worker_id=r['worker_id'],source=source,raw_identity_and_coordinates_match=True,processing_status=r['processing_status']));count+=1
        manifest.append(dict(path=source,sha256=sha(repo/source),canonical_rows=count))
    save(out,'raw_coordinate_and_identity_checks.csv',checks)
    images={r['image_id']:r for r in reg['images']};image_rows=[];counts={}
    for image in reg['images']:
        iid=image['image_id'];rr=byimage.get(iid,[])
        seen={int(r['worker_id']) for r in rr};manual={int(r['worker_id']) for r in rr if r['unassisted_manual_included']}
        unaided={int(r['worker_id']) for r in rr if r['assistance_exposure']=='none'};semi={int(r['worker_id']) for r in rr if r['assistance_exposure']=='model_preannotation'}
        ns=dict(n_people_any=len(seen),n_people_unassisted=len(unaided),n_people_manual_included=len(manual),n_people_model_assisted=len(semi))
        assert all(image['historical'][k]==v for k,v in ns.items())
        assert len([r for r in rr if r['unassisted_manual_included']])==len(manual)
        if rr:counts[iid]={**ns,'canonical_annotation_ids':[r['canonical_annotation_id'] for r in rr],'raw_export_paths':sorted({r['raw_export_path'] for r in rr}),'stages':dict(Counter(r['stage'] for r in rr))}
        cm=manual&CURRENT;cs=seen&CURRENT;clean=CURRENT-seen
        image_rows.append(dict(image_id=iid,building=image['building'],number=image['number'],path=image['path'],split=image['split'],main_visual_space=image['main_visual_space'],expected_annotation_extent=image['expected_annotation_extent'],ambiguity_and_information=image['ambiguity_and_information'],**ns,n_current20_manual=len(cm),n_current20_any_seen=len(cs),n_current20_no_record=len(clean),max_current20_without_reusing_seen_nonmanual=len(cm|clean),naive_historical_topup_to20=max(0,20-len(manual)),nominal_current20_topup=max(0,20-len(cm)),n_current20_seen_nonmanual=len(cs-cm),current20_manual_workers=';'.join(map(str,sorted(cm))),current20_no_record_workers=';'.join(map(str,sorted(clean))),current20_seen_nonmanual_workers=';'.join(map(str,sorted(cs-cm))),coarse_type=image['spatial_classification']['coarse_type'],coarse_label_provenance=image['spatial_review_provenance'],boundary_label=image['spatial_classification']['boundary'],user_doorway_group_codes=';'.join(image['doorway_user_comment_codes']),group_codes=';'.join(image['group_codes']),exposure_interpretation='absence_from_canonical_snapshot_is_not_proof_of_never_exposed'))
    data=save(out,'image_inventory_648_with_exposure.csv',image_rows).set_index('image_id',drop=False)
    sys.path.insert(0,str(repo))
    from tools.thesis_main.analysis.materialize_same_room_selection import assemble
    rebuilt=assemble(read(repo/SCENE/'user_group_review_20260912.json'),read(repo/SCENE/'group_comment_interpretation_20260912.json'),counts)
    for key in ['groups','candidates','images','views','summary']:assert rebuilt[key]==reg[key],key
    lowids=set(reg['views']['low_ambiguity_order']);cr=[]
    for c in reg['candidates']:
        q=data.loc[c['image_ids']]
        cr.append(dict(candidate_id=c['candidate_id'],building=c['building'],n_images=len(q),numbers=';'.join(map(str,c['numbers'])),image_ids=';'.join(c['image_ids']),manual_counts=';'.join(map(str,q.n_people_manual_included)),n_manual_ge19=int((q.n_people_manual_included>=19).sum()),n_manual_ge5=int((q.n_people_manual_included>=5).sum()),low_candidate=c['candidate_id'] in lowids,review_state=c['review_state'],raw_decision=c['raw_decision'],difficulty_similarity=c['difficulty_similarity'],physical_same_supported=c['physical_same_supported'],comparable_for_prediction=c['comparable_for_prediction'],oos_pending=c['oos_pending'],outcome_exposure=c['outcome_exposure'],issue_tags=';'.join(c['issue_tags']),selection_hold_reasons=';'.join(c['selection_hold_reasons'])))
    candidates=save(out,'candidate_units_259.csv',cr);low=candidates[candidates.low_candidate];save(out,'low_ambiguity_69_support.csv',low)
    assert set(low.loc[low.n_manual_ge19>=1,'candidate_id'])=={p[0] for p in PAIRS}
    groups={g['review_code']:g for g in reg['groups']}
    def iid(code,num):
        found=[x for x in groups[code]['image_ids'] if int(images[x]['number'])==num];assert len(found)==1;return found[0]
    pairs=[];st=[];stages=pd.read_csv(repo/STAGES)
    for code,sn,tn,role in PAIRS:
        sid=iid(code,sn);tid=iid(code,tn);s=data.loc[sid];t=data.loc[tid];c=next(x for x in reg['candidates'] if x['candidate_id']==code)
        pairs.append(dict(group_code=code,building=s.building,source_number=sn,target_number=tn,source_image_id=sid,target_image_id=tid,source_manual_N=s.n_people_manual_included,target_manual_N=t.n_people_manual_included,target_current20_manual=t.n_current20_manual,target_current20_any_seen=t.n_current20_any_seen,target_current20_clean_capacity=t.max_current20_without_reusing_seen_nonmanual,naive_mixed_history_topup_to20=t.naive_historical_topup_to20,current20_nominal_topup=t.nominal_current20_topup,current20_topup_possible_from_snapshot=t.max_current20_without_reusing_seen_nonmanual==20,new_cohort20_target_cost=20,proposed_role=role,review_state=c['review_state'],outcome_exposed_comment=c['outcome_exposure'],original_comment='\n'.join(groups[x]['raw_current']['note'] for x in c['source_group_codes']),annotation_scope_adjudication='not_established_by_room_membership',target_new_result_observed=False,conditional_H20_source_available=s.n_people_manual_included>=20,source_path=s.path,target_path=t.path))
        z=stages[(stages.image_id==sid)&stages.horizon.isin([19,20,24])&(stages.kind=='anchor_stage')&stages.config.isin(['q_0.950','ospa30_t6'])]
        for r in z.to_dict('records'):st.append(dict(group_code=code,**r,role='observed_source_not_new_target_validation'))
    pairdf=save(out,'priority_source_target_pairs.csv',pairs);save(out,'archived_source_stages_matched_horizon.csv',st)
    save(out,'boundary_multiview_oos_options.csv',[dict(group_code=code,role=role,**data.loc[iid(code,num)].to_dict(),original_comment=groups[code]['raw_current']['note']) for code,num,role in EXTRAS])
    save(out,'all_view_alternatives_selected_rooms.csv',[dict(group_code=code,**data.loc[x].to_dict()) for code,*_ in PAIRS for x in groups[code]['image_ids']])
    countmap={i:{str(r['worker_id']):int(r['effective_point_count']) for r in rr if r['unassisted_manual_included']} for i,rr in byimage.items()}
    def disagreement(v):
        x=np.asarray(v);return float((x[:,None]!=x[None,:]).sum()/(len(x)*(len(x)-1))) if len(x)>1 else np.nan
    small=[]
    for c in reg['candidates']:
        if c['candidate_id'] not in lowids:continue
        for a,b in combinations(c['image_ids'],2):
            x=countmap.get(a,{});y=countmap.get(b,{})
            if min(len(x),len(y))<5:continue
            common=sorted(set(x)&set(y),key=int)
            small.append(dict(group_code=c['candidate_id'],image_a=a,image_b=b,number_a=images[a]['number'],number_b=images[b]['number'],n_a=len(x),n_b=len(y),n_common_workers=len(common),common_worker_ids=';'.join(common),full_count_disagreement_a=disagreement(list(x.values())),full_count_disagreement_b=disagreement(list(y.values())),common_worker_count_disagreement_a=disagreement([x[w] for w in common]),common_worker_count_disagreement_b=disagreement([y[w] for w in common]),counts_a_json=json.dumps(x),counts_b_json=json.dumps(y),interpretation='endpoint_count_only_not_topology_or_convergence'))
    save(out,'existing_same_room_same_worker_count_comparison.csv',small)
    scenarios=[('A_core5',20,5,0,0,6,0,0),('B_core_and_challenge9',20,9,0,0,6,0,0),('C_main9_plus_boundary',20,9,4,0,6,0,0),('D_add_three_view_room',20,9,4,3,6,0,0),('C_plus_k20_tail4',20,9,4,0,6,5,4)]
    costs=[]
    for name,n,main,bound,multi,cal,extra,tailimages in scenarios:
        for minutes in [3,5,8]:
            actions=n*(main+bound+multi+cal)+extra*(tailimages+cal)
            costs.append(dict(plan=name,initial_workers=n,extra_workers=extra,main_target_images=main,boundary_images=bound,multiview_images=multi,calibration_images_per_person=cal,total_geometry_actions=actions,per_initial_worker_actions=main+bound+multi+cal,assumed_minutes_per_action=minutes,annotation_hours=actions*minutes/60,onboarding_hours=(n+extra)*.5,total_scenario_hours_excluding_expert_admin_fees=actions*minutes/60+(n+extra)*.5,rate_not_provided=True,not_power_justified_sample_size=True))
    save(out,'cost_scenarios.csv',costs)
    joined=pd.DataFrame(rows).merge(ev[['canonical_annotation_id','active_time_owner_valid_status','active_time_seconds']],on='canonical_annotation_id',validate='one_to_one')
    joined['seconds']=pd.to_numeric(joined.active_time_seconds,errors='coerce');joined['worker_id']=pd.to_numeric(joined.worker_id).astype(int)
    complete=joined.active_time_owner_valid_status.str.startswith('owner_valid_complete')&np.isfinite(joined.seconds)&(joined.seconds>0);times=[]
    for cohort,d in [('all_historical',joined),('current20',joined[joined.worker_id.isin(CURRENT)])]:
        for cond,mask in [('included_unassisted',d.unassisted_manual_included),('semi',d.assistance_exposure.eq('model_preannotation'))]:
            vals=d.loc[complete.reindex(d.index)&mask,'seconds'];z=d.loc[vals.index]
            times.append(dict(cohort=cohort,condition=cond,n_duration_records=len(vals),images=z.image_id.nunique(),mean_seconds=vals.mean(),median_seconds=vals.median(),p25=vals.quantile(.25),p75=vals.quantile(.75),p90=vals.quantile(.9),image_equal_mean_seconds=z.groupby('image_id').seconds.mean().mean(),role='saved_owner_complete_active_time_not_newcomer_guarantee'))
    save(out,'historical_time_context.csv',times)
    cal=[];blocked={x for code in {p[0] for p in PAIRS}|{p[0] for p in EXTRAS} for x in groups[code]['image_ids']}
    for building,num in [('7y3sRwLe3Va',4),('X7HyMhZNoso',5),('b8cTxDM8gDG',7),('e9zR4mvMWw7',10),('q9vSo1VnCiC',1),('x8F5xyUWy9e',9)]:
        x=data[(data.building==building)&(data.number==num)];assert len(x)==1;r=x.iloc[0].to_dict();assert r['image_id'] not in blocked;e=ev[ev.base_task_id==r['image_id']]
        assert (e.quality_reference_status=='adjudicated_reference').all() and (e.reference_scope_status=='in_scope').all()
        cal.append({**r,'reference_source':';'.join(sorted(set(e.reference_version))),'approval_status':'review_candidate_not_frozen_gold','required_check':'current_policy_specific_rules_and_independent_reference_check'})
    save(out,'calibration_review_candidates.csv',cal)
    save(out,'rare_mode_binomial_sensitivity.csv',[dict(assumed_independent_mode_probability=p,N=n,probability_at_least_one=1-(1-p)**n,probability_at_least_two=1-(1-p)**n-n*p*(1-p)**(n-1),role='iid_assumption_not_empirical_power') for p in [.05,.1,.2] for n in [10,15,20,25,30]])
    save(out,'number_vs_validation_horizon.csv',[dict(total_distinct_workers=n,required_tail_workers=h,max_candidate_k=n-h,can_check_k20_with_tail=n>=20+h) for n in [15,19,20,24,25,30] for h in [1,3,5]])
    for p in [SCENE/'same_room_selection_registry_20260912.json',SCENE/'user_group_review_20260912.json',SCENE/'group_comment_interpretation_20260912.json',VIEW,EV,STAGES,Path('tools/thesis_main/analysis/materialize_same_room_selection.py'),Path('docs/thesis_main/图片分类与同房间收敛预测研究SOP.md'),Path('docs/thesis_main/相似场景标注稳定性分析SOP.md')]:manifest.append(dict(path=str(p),sha256=sha(repo/p),role='pinned_planning_input'))
    save(out,'SOURCE_MANIFEST.csv',manifest)
    lowimages={i for c in reg['candidates'] if c['candidate_id'] in lowids for i in c['image_ids']}
    qa=dict(source_commit=PIN,raw_source_files=18,raw_identity_and_coordinate_checks=len(checks),registry_core_keys_reproduced=True,submitted_groups=len(reg['groups']),candidate_units=len(candidates),image_count=len(images),historical_images=len(byimage),manual_included=sum(r['unassisted_manual_included'] for r in rows),low_candidate_units=len(low),low_candidate_unique_images=len(lowimages),low_candidate_buildings=low.building.nunique(),low_with_ge1_N19=int((low.n_manual_ge19>=1).sum()),low_with_ge2_N19=int((low.n_manual_ge19>=2).sum()),low_with_ge2_N5=int((low.n_manual_ge5>=2).sum()),oos_pending_units=int(candidates.oos_pending.sum()),selected_rooms=len(pairdf),selected_buildings=pairdf.building.nunique(),primary_sources_H20=int(pairdf.conditional_H20_source_available.sum()),no_new_human_annotations=True,no_new_room_identity_or_scope_adjudication=True,not_dispatch=True,rate_not_provided=True)
    (out/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
    print(json.dumps(qa,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.repo.resolve(),a.out.resolve())
