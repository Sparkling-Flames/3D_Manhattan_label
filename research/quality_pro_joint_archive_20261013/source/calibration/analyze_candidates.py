#!/usr/bin/env python3
"""Candidate decisions, component ablations, clustered sensitivity and controls."""
from __future__ import annotations
import argparse, copy, csv, gzip, hashlib, json, math, sys
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from score import BASELINE,evaluate_arrays,score_metrics,normalized_metrics
from run_search import (arrays,descriptors,build_evidence,evidence_eval,scalar_response,
                        selection_key,jload,dump,csv_write,BOUNDS)
HERE=Path(__file__).resolve().parent

def summary_stats(v):
    v=np.asarray(v,float)
    return dict(count=int(len(v)),min=float(v.min()),p10=float(np.quantile(v,.1)),median=float(np.median(v)),
                mean=float(np.mean(v)),p90=float(np.quantile(v,.9)),max=float(v.max())) if len(v) else dict(count=0)

def compact_descriptor(d):
    if 'moment4' in d:return dict(d)
    return dict(moment4=d['weighted_abs_moments_deg_power']['p4'],
                excess2={k:v['positive_part_m2_deg2'] for k,v in d['excess_by_threshold_deg'].items()},
                joint_hinge={})

def count_rank_flips(q0,q1,rows):
    groups={}
    for i,r in enumerate(rows):
        if r['conditional_personnel_eligible']:groups.setdefault((r['image_id'],r['reference_object_id'],r['condition']),[]).append(i)
    allpairs=flips=ties=totalpairs=identical=0;examples=[]
    for key,ii in groups.items():
      # Same exact geometry can recur among workers; do not create fake strict wins.
      for ai,i in enumerate(ii):
       for j in ii[ai+1:]:
        if rows[i]['worker_id']==rows[j]['worker_id']:continue
        totalpairs+=1
        if rows[i]['coordinate_hash']==rows[j]['coordinate_hash']:identical+=1;continue
        d0=q0[i]-q0[j];d1=q1[i]-q1[j]
        if abs(d0)<1e-10 or abs(d1)<1e-10:ties+=1;continue
        allpairs+=1
        if d0*d1<0:
            flips+=1;examples.append(dict(image_id=key[0],reference_object_id=key[1],condition=key[2],A=rows[i]['id'],B=rows[j]['id'],baseline_gap=float(d0),new_gap=float(d1)))
    return dict(all_cross_worker_pairs=totalpairs,same_coordinate_hash_pairs=identical,geometry_distinct_pairs=totalpairs-identical,
                comparable_pairs=allpairs,rank_flips=flips,ties=ties,pairs_are_dependent=True,examples=examples)

def threshold_intervals(q,grades):
    """All optimal two-cut ordinal fits. Neither cuts nor labels become truth."""
    vals=sorted(set(float(q[g['id']]) for g in grades));edges=[0.]+vals+[100.]
    intervals=[]
    for lo,hi in zip(edges,edges[1:]):
        if hi>lo:intervals.append((lo,hi,(lo+hi)/2))
    fits=[];best=math.inf
    for il,(a,b,low) in enumerate(intervals):
      for c,d,high in intervals[il+1:]:
        pred={g['id']:(0 if q[g['id']]>high else 1 if q[g['id']]>low else 2) for g in grades}
        loss=sum(abs(pred[g['id']]-g['grade']) for g in grades)
        if loss<best:best=loss;fits=[]
        if loss==best:fits.append(dict(lower_cut_open_interval=[a,b],upper_cut_open_interval=[c,d],
                                       mismatched_records=[g['id'] for g in grades if pred[g['id']]!=g['grade']]))
    return dict(records=len(grades),minimum_total_ordinal_step_error=best,optimal_intervals=fits,
                all_label_confidences_unknown=True,severe_class_absent=True,deployable_human_grade_cuts=False)

def row_scores(data,configs,out):
    rows=data['rows'];m=arrays(rows);d=descriptors(rows);ev=build_evidence(data)
    cfgs={'baseline_quad08':BASELINE,**configs};values={n:evaluate_arrays(m,c,d) for n,c in cfgs.items()}
    q0=values['baseline_quad08']['score'];elig=np.array([r['conditional_personnel_eligible'] for r in rows])
    scored=[];long=[];summ={};cuts={}
    for i,r in enumerate(rows):
        z={k:v for k,v in r.items() if k!='descriptor'};z['record_id']=r['id'];z['scores']={};z['losses']={}
        for n,v in values.items():
            parts={k:float(np.asarray(x)[i]) for k,x in v.items()};z['scores'][n]=parts['score'];z['losses'][n]=parts
            long.append(dict(record_id=r['id'],candidate=n,reference_object_id=r['reference_object_id'],reference_points_sha256=r['reference_points_sha256'],current_points_sha256=r['current_points_sha256'],conditional_personnel_eligible=r['conditional_personnel_eligible'],**parts))
        z['scores']['official_iou3d']=r['baseline_scores']['Q_official_iou3d'];scored.append(z)
    for n,v in values.items():
        q=v['score'];change=q-q0
        summ[n]=dict(config=cfgs[n],evidence=evidence_eval(q,v['floor_score'],v['height_loss'],ev),
            response=scalar_response(cfgs[n]),all922_score=summary_stats(q),all922_change=summary_stats(change),
            eligible143_score=summary_stats(q[elig]),eligible143_change=summary_stats(change[elig]),
            eligibility_count=int(elig.sum()),eligible_unique_coordinate_hashes=len({r['coordinate_hash'] for r in rows if r['conditional_personnel_eligible']}),
            changed_over_5_all=int(np.sum(abs(change)>5)),changed_over_10_all=int(np.sum(abs(change)>10)),
            down_over_5_all=int(np.sum(change < -5)),up_over_5_all=int(np.sum(change > 5)),
            changed_over_5_eligible=int(np.sum(abs(change[elig])>5)),
            rank_changes_same_image_condition=count_rank_flips(q0,q,rows),
            largest_down=[dict(record_id=rows[i]['id'],image_code=rows[i]['image_code'],worker_id=rows[i]['worker_id'],D=rows[i]['metrics']['dir'],baseline=float(q0[i]),new=float(q[i]),change=float(change[i]),eligible=rows[i]['conditional_personnel_eligible']) for i in np.argsort(change)[:15]])
        qby={r['id']:q[i] for i,r in enumerate(rows)}
        cuts[n]={'all24':threshold_intervals(qby,data['grades']),
                 'clean22':threshold_intervals(qby,[g for g in data['grades'] if not g['scope_confounded_latest']])}
    # Fair comparator: exactly the same fixed references, eligibility and cases.
    iou=np.array([r['baseline_scores']['Q_official_iou3d'] for r in rows])
    summ['official_iou3d']={'evidence':evidence_eval(iou,np.array([100*r['metrics']['iou_2d'] for r in rows]),np.zeros(len(rows)),ev),
                          'height_conditional_comparison_not_supported_by_single_iou':True,
                          'same_reference_and_same_922_records_as_composites':True}
    summ['official_iou3d']['evidence']['conditional_height_violations']=None
    summ['official_iou3d']['evidence']['P04_height_loss_margin']=None
    summ['official_iou3d']['evidence']['hard_sign_violations']=None
    dump(out/'selected_scores_922.json',dict(schema='joint_fixed_reference_selected_scores_v1',rows=scored,formula_only_comparison=True,new_reference_routing_applied=False))
    csv_write(out/'selected_components_long.csv',long)
    csv_write(out/'selected_scores_wide.csv',[dict(record_id=r['record_id'],image_code=r['image_code'],worker_id=r['worker_id'],condition=r['condition'],eligible=r['conditional_personnel_eligible'],**r['scores']) for r in scored])
    dump(out/'selected_candidate_summary.json',summ);dump(out/'grade_cut_identification.json',cuts)
    return values,summ

def ablations(data,main,out):
    cases={}
    for key in ['direction','boundary','overlap','global','local']:
        c=copy.deepcopy(main);c['name']='ablate_'+key;c[key+'_disabled']=True;cases[c['name']]=c
    c={**main,'name':'ablate_new_direction_tail','family':'hill'};cases[c['name']]=c
    c={**main,'name':'restore_global_scale08','global_scale':.8};cases[c['name']]=c
    for combine in ['product_height','product_all','max_floor']:
        c={**main,'name':'same_terms_'+combine,'combine':combine};cases[c['name']]=c
    m=arrays(data['rows']);d=descriptors(data['rows']);ev=build_evidence(data)
    ref=evaluate_arrays(m,main,d);eligible=np.array([r['conditional_personnel_eligible'] for r in data['rows']])
    result=[]
    for name,c in cases.items():
        v=evaluate_arrays(m,c,d)
        result.append(dict(name=name,config=c,evidence=evidence_eval(v['score'],v['floor_score'],v['height_loss'],ev),
                           eligible143_change=summary_stats((v['score']-ref['score'])[eligible]),
                           all922_change=summary_stats(v['score']-ref['score']),
                           added_or_removed_role='One specified factor changed; same geometries and reference; no causal interpretation of human agreement gain.'))
    dump(out/'ablation_summary.json',result)
    return cases

def policy_sensitivity(grid,configs,out):
    results=[]
    for small in [.15,.2,.3]:
     for large in [1.,2.,3.]:
      for growth in [3.,4.,6.]:
        keep=[]
        for r in grid:
            okay=(int(r['hard_sign_violations'])==0 and float(r['D_2_loss'])<=small and float(r['D_15_loss'])>=large and float(r['D15_to_D5_loss_ratio'])>=growth and float(r['Hm_0.2_loss'])<=.35 and float(r['Hm_1_loss'])>=.5 and float(r['Hc_0.2_loss'])>=float(r['Hm_0.2_loss']))
            if okay:keep.append(r)
        clean=[r for r in keep if float(r['clean22_inversions'])==0]
        best=min(clean,key=lambda r:float(r['weak_close_mean_log_ratio'])) if clean else None
        acceptance={}
        for name,c in {'baseline_quad08':BASELINE,**configs}.items():
            r=scalar_response(c)
            acceptance[name]=(r['D_2_loss']<=small and r['D_15_loss']>=large and r['D15_to_D5_loss_ratio']>=growth and r['Hm_0.2_loss']<=.35 and r['Hm_1_loss']>=.5 and r['Hc_0.2_loss']>=r['Hm_0.2_loss'])
        results.append(dict(D2_max_loss=small,D15_min_loss=large,min_growth_15_vs5=growth,feasible=len(keep),clean22_zero_inversion=len(clean),
                            families={f:sum(r['family']==f for r in keep) for f in sorted({r['family'] for r in grid})},
                            selected_candidate_passes=acceptance,best_by_weak_display_diagnostic=None if best is None else {k:best[k] for k in ['candidate','family','combine','weak_close_mean_log_ratio']}))
    unconfounded=[r for r in grid if int(r['hard_sign_violations'])==0 and int(r['response_design_violations'])==0 and float(r['clean22_inversions'])==0]
    region={}
    for key in BOUNDS:
        vals=[float(r[key]) for r in unconfounded if r.get(key) not in ('',None)]
        if vals:region[key]=summary_stats(vals)
    byfamily={}
    for family in sorted({r['family'] for r in unconfounded}):
        rr=[r for r in unconfounded if r['family']==family]
        active=['iou_power','boundary_scale','global_scale','local_scale','direction_scale']
        if family in ('hill','hill_tail'):active+=['direction_cap']
        if family in ('accelerated','hill_tail','moment4','supported_tail'):active+=['tail_scale']
        byfamily[family]={k:summary_stats([float(r[k]) for r in rr if r.get(k) not in ('',None)]) for k in active}
    dump(out/'response_policy_sensitivity.json',dict(model_design_not_human_class_thresholds=True,policies=results,
         full24_not_in_region_filter=True,unconfounded_region_count=len(unconfounded),unconfounded_parameter_region=region,
         active_parameter_region_by_family=byfamily,
         region_is_coordinatewise_projection_not_joint_confidence_interval=True))

def vector_evidence(q,f,h,ev):
    n=q.shape[0];hard=np.zeros(n,int)
    for _,i,j in ev['overall']:hard+=q[:,i]<=q[:,j]
    for _,i,j in ev['floor']:hard+=f[:,i]<=f[:,j]
    for _,i,j in ev['conditional']:hard+=h[:,i]<=h[:,j]
    groups=[]
    for pairs in ev['sets']['clean22']['groups']:
        if pairs:
            aa=np.array([a for a,b in pairs]);bb=np.array([b for a,b in pairs]);delta=q[:,aa]-q[:,bb]
            groups.append(np.mean((delta < -1e-10)+.5*(abs(delta)<=1e-10),axis=1))
    error=np.mean(groups,axis=0) if groups else np.zeros(n)
    close=np.mean([abs(np.log(np.maximum(q[:,i],1e-300)/np.maximum(q[:,j],1e-300))) for _,i,j in ev['close']],axis=0) if ev['close'] else np.zeros(n)
    return hard,error,close

def leave_groups(data,searchconfigs,out):
    ids={g['id'] for g in data['grades']}
    ids.update(r for c in data['constraints'] for r in c.get('record_ids',[]))
    small={**data,'rows':[r for r in data['rows'] if r['id'] in ids]}
    m=arrays(small['rows']);d=descriptors(small['rows'])
    vals=[evaluate_arrays(m,c,d) for c in searchconfigs]
    q=np.stack([v['score'] for v in vals]);f=np.stack([v['floor_score'] for v in vals]);h=np.stack([v['height_loss'] for v in vals])
    response=np.array([scalar_response(c)['response_design_violations'] for c in searchconfigs])
    output=[]
    for field,label in [('building_id','leave_building'),('image_id','leave_image')]:
      for held in sorted({r[field] for r in small['rows']}):
        ev=build_evidence(small,excluded_building=held if field=='building_id' else None,excluded_image=held if field=='image_id' else None)
        hard,error,close=vector_evidence(q,f,h,ev)
        idx=int(np.lexsort((np.arange(len(searchconfigs)),close,error,response,hard))[0])
        heldgrades=[g for g in small['grades'] if g[field]==held]
        rididx={r['id']:i for i,r in enumerate(small['rows'])}
        pairs=[(a,b) for a in heldgrades for b in heldgrades if a['grade']<b['grade']]
        inv=sum(q[idx,rididx[a['id']]]<q[idx,rididx[b['id']]] for a,b in pairs)
        output.append(dict(mode=label,held_group=held,selected_config=searchconfigs[idx],training_hard_violations=int(hard[idx]),
                           training_clean22_macro_error=float(error[idx]),training_weak_display_logratio=float(close[idx]),
                           held_grade_records=len(heldgrades),held_internal_comparable_pairs=len(pairs),
                           held_internal_inversions=int(inv) if pairs else None,
                           no_independent_validation=True))
    dump(out/'leave_group_sensitivity.json',dict(folds=output,scope='Same development cases; fixed grid/family decisions seen across groups. This is sensitivity, not nested unbiased generalization.',
             selected_family_counts={m:{f:sum(r['mode']==m and r['selected_config']['family']==f for r in output) for f in sorted({r['selected_config']['family'] for r in output})} for m in ['leave_building','leave_image']},
             folds_without_internal_test_pairs=sum(r['held_internal_comparable_pairs']==0 for r in output)))

def controls(configs,ablation_cfgs,out,experiment_results):
    sys.path.insert(0,str(HERE.parent/'experiments'))
    from structural_features import direction_descriptors,jointly_optimized_hinge
    cfgs={'baseline_quad08':BASELINE,**configs,**ablation_cfgs}
    physical=jload(out/'physical_controls.json')['rows']
    targeted=jload(experiment_results/'targeted_metrics.json')['rows']
    outputs=[]
    for dataset,rr in [('boundary_displacement',physical),('endpoint_spherical_and_counterexamples',targeted)]:
      for r in rr:
        if r.get('status')!='available':continue
        sd=r['direction_descriptor']
        if 'edge_direction_deg' not in sd:sd=direction_descriptors(r['annotation_geometry']['bottom3d'])
        desc=compact_descriptor(sd);desc['joint_hinge']={}
        for c in cfgs.values():
            if c['family']=='joint_hinge':
                key=f"t{c['tail_threshold']:g}_g{c['hinge_weight']:g}"
                desc['joint_hinge'][key]=jointly_optimized_hinge(sd,c['tail_threshold'],c['hinge_weight'])['value_deg2']
        scores={name:score_metrics(r['metrics'],c,desc) for name,c in cfgs.items()}
        bad=[n for n,v in scores.items() if v['status']!='complete']
        if bad:raise AssertionError((r['case_id'],bad))
        outputs.append(dict(dataset=dataset,case_id=r['case_id'],family=r.get('family',r.get('kind')),
                            metadata=r.get('metadata',{k:r.get(k) for k in ['reference_case','target_budget','actual_budget']}),
                            metrics={k:normalized_metrics(r['metrics'])[k] for k in ['I','Sb','D','Hm','Hc']},
                            scores={n:v['score'] for n,v in scores.items()},losses=scores,
                            official_iou3d_x100=100*r.get('official_corner_mean_iou3d',r.get('official_iou3d')),human_label=None))
    triples=[]
    for ds in ['boundary_displacement','endpoint_spherical_and_counterexamples']:
        rows=[r for r in outputs if r['dataset']==ds]
        gg={}
        for r in rows:
            if ds=='boundary_displacement':
                if r['family'] not in ('shear','local_height','global_height_high'):continue
                key=(r['metadata']['reference_case'],r['metadata']['target_budget']);kind={'shear':'structure','local_height':'local','global_height_high':'global'}[r['family']]
            else:
                if r['family'] not in ('matched_floor_shear','matched_local_height','matched_global_height'):continue
                key=(r['metadata']['image_code'],r['metadata']['target_endpoint_rms_deg']);kind={'matched_floor_shear':'structure','matched_local_height':'local','matched_global_height':'global'}[r['family']]
            gg.setdefault(key,{})[kind]=r
        for key,z in sorted(gg.items()):
            if len(z)!=3:continue
            vals={n:{k:r['scores'][n] for k,r in z.items()} for n in cfgs}
            vals['official_iou3d']={k:r['official_iou3d_x100'] for k,r in z.items()}
            triples.append(dict(dataset=ds,reference_case=key[0],budget=key[1],scores=vals,
                                ordered={n:v['structure']<v['local']<v['global'] for n,v in vals.items()},
                                perceived_error_equivalence_not_validated=True))
    summary={ds:{n:dict(ordered=sum(t['dataset']==ds and t['ordered'][n] for t in triples),total=sum(t['dataset']==ds for t in triples),failures=[t for t in triples if t['dataset']==ds and not t['ordered'][n]]) for n in cfgs|{'official_iou3d':{}}} for ds in ['boundary_displacement','endpoint_spherical_and_counterexamples']}
    dump(out/'all_controls_rescored.json',dict(rows=outputs));dump(out/'matched_priority_triplets.json',dict(triplets=triples,summary=summary))

def correlation(data,out):
    rows=data['rows'];elig=[r for r in rows if r['conditional_personnel_eligible']]
    seen={};[seen.setdefault(r['coordinate_hash'],r) for r in elig];unique=list(seen.values())
    results={}
    for name,rr in [('all922',rows),('eligible143',elig),('eligible_unique_geometry',unique)]:
        x=arrays(rr);xx=np.column_stack([1-x['I'],x['Sb'],x['D'],x['Hm'],x['Hc']])
        results[name]=dict(count=len(rr),columns=['1-I','Sb_deg','D_deg','Hm','Hc'],
                           spearman=spearmanr(xx,axis=0).statistic.tolist(),pearson=np.corrcoef(xx,rowvar=False).tolist(),
                           correlation_does_not_prove_double_counting=True)
    dump(out/'component_association.json',results)

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=HERE/'inputs/search_inputs.json')
    p.add_argument('--configs',type=Path,default=HERE/'recommended_parameters.json');p.add_argument('--out',type=Path,default=HERE/'results')
    p.add_argument('--experiment-results',type=Path,default=HERE.parent/'experiments/results')
    p.add_argument('--skip-group-refits',action='store_true');a=p.parse_args()
    data=jload(a.inputs);doc=jload(a.configs);configs=doc['candidates'];main=configs[doc['recommended']]
    grid=list(csv.DictReader(gzip.open(a.out/'all_search_results.csv.gz','rt',encoding='utf-8')))
    searchconfigs=json.load(gzip.open(a.out/'all_search_configs.json.gz','rt'))['configs']
    _,summ=row_scores(data,configs,a.out);ab=ablations(data,main,a.out)
    policy_sensitivity(grid,configs,a.out);correlation(data,a.out)
    controls(configs,ab,a.out,a.experiment_results)
    if not a.skip_group_refits:leave_groups(data,searchconfigs,a.out)
    print(json.dumps({n:{'evidence':s.get('evidence'),'eligible143_change':s.get('eligible143_change')} for n,s in summ.items()},ensure_ascii=False))

if __name__=='__main__':main()
