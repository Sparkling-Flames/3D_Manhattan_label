#!/usr/bin/env python3
"""Part A common-event assessment, independent of both type-discovery runners.

Use only frozen aliases selected within training buildings. No type selection is
performed here. Predictions are reproduced from the training-side calibrator.
"""
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, json, sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'assessment'
sys.path.insert(0,str(ROOT/'reverse'))
from selection_common import fit_calibrator,predict_calibrator,building_brier
PRIMARY='Pro_exact_fixed_background_v1';SEED=20261019
BASELINE_COLS={'Q2':'Q2_B8L2','Q3':'Q3_B8L2','old_QT':'QT_B8L2','old_QT3':'QT3_B8L2','old_QTD_archive':'fine_dtype_merged_B8L2','old_QTD_supported':'fine_dtype_merged_B8L2'}
METRICS=['stable_main','stable_strict','stable_loose','stable_D10','abs_delta_Q','abs_D10_change','delta_Q','floor_change','node_count_difference','node_changed','edge_relation_jaccard_difference','selected_shared_observation_difference','upper_bound_shift_max_deg','lower_bound_shift_max_deg','mean_height_prism_pair_iou','either_failure','complete_to_incomplete','incomplete_to_complete']

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.floating,)):return None if not np.isfinite(v) else float(v)
    return v
def savej(path,obj):Path(path).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2)+'\n')
def boolcol(s): return s.astype(str).str.lower().isin(['true','1','1.0'])

def events():
    p=ROOT/'events/common_events.csv.gz'
    header=pd.read_csv(p,nrows=0).columns
    keep=set(['event_id','panel_id','pool_id','image','image_id','building','difficulty','k','worker_a','worker_b','background_id','chain_id','nested_chain_id','request_a','request_b','team_id_a','team_id_b','entrant_origin_a','entrant_origin_b','entrant_same_point_count','source_entrant_time_a','source_entrant_time_b','target_entrant_time_a','target_entrant_time_b','stable_main','joint_stable_main','joint_stable_strict','joint_stable_wide','complete_a','complete_b','both_complete','B8L2_a','B8L2_b','D10_a','D10_b','B8L2_change','abs_B8L2_change','D10_change','abs_D10_change','node_count_difference','floor_jaccard_difference','structure_bound_cyclic_deg','source_time_complete_a','source_time_complete_b','target_time_complete_a','target_time_complete_b','source_time_total_seconds_a','source_time_total_seconds_b','target_time_total_seconds_a','target_time_total_seconds_b']+METRICS)
    # Bound the CSV parser's temporary allocation while native/event learners run.
    # Concatenation preserves every input row and its original order.
    e=pd.concat(pd.read_csv(p,usecols=[x for x in header if x in keep],chunksize=25000),ignore_index=True)
    if 'chain_id' in e:
        e['nested_chain_id']=e['chain_id']
    e['difficulty_frozen_label']=e.difficulty
    e['difficulty']=e.difficulty.replace({'简单':'easy','中等':'medium','困难':'hard'})
    for col in ['stable_main','joint_stable_main','joint_stable_strict','joint_stable_wide','complete_a','complete_b','both_complete','complete_to_incomplete','incomplete_to_complete','entrant_same_point_count']:
        if col in e:e[col]=boolcol(e[col])
    e['stable_strict']=e['joint_stable_strict'];e['stable_loose']=e['joint_stable_wide']
    e['stable_D10']=e.both_complete & e.abs_D10_change.le(2) & e.floor_change.le(.05) & e.node_count_difference.eq(0) & e.structure_bound_cyclic_deg.le(3)
    e['either_failure']=~e.both_complete;e['node_changed']=e.node_count_difference.ne(0) & e.node_count_difference.notna()
    e['pair_origin']=np.where(e.entrant_origin_a.eq('v1') & e.entrant_origin_b.eq('v1'),'old-old',np.where(e.entrant_origin_a.eq('new') & e.entrant_origin_b.eq('new'),'new-new','old-new'))
    assert e.event_id.is_unique and len(e)==286666
    return e

def labels():
    p=ROOT/'recovered/work_v2_20261019/profiles'
    old=pd.concat([pd.read_csv(p/'full_profiles.csv'),pd.read_csv(p/'fold_profiles.csv')],ignore_index=True)
    rows=[]
    for method,col in BASELINE_COLS.items():
        a=old[['heldout_building','worker_id',col,'Q_images','Q_buildings']].rename(columns={col:'class_id','Q_images':'n_images','Q_buildings':'n_buildings'}).copy()
        if method=='old_QTD_supported':a.loc[a.class_id.str.contains('unknown|sparse_child',na=True),'class_id']='unknown'
        a['method_id']=method;a['difficulty']='global';a['fold_id']=a.heldout_building;a['source_candidate_id']='archived_'+col
        rows.append(a)
    forward=ROOT/'forward/selected_classes_by_fold.csv.gz'
    if forward.exists():rows.append(pd.read_csv(forward))
    reverse=list((ROOT/'reverse/results/folds').glob('*/classes.csv.gz'))
    for p in reverse:
        a=pd.read_csv(p);a=a[a.method_id.str.startswith('reverse_selected')];rows.append(a)
    x=pd.concat(rows,ignore_index=True)
    x['heldout_building']=x.heldout_building.fillna('FULL')
    x['difficulty']=x.difficulty.fillna('global').replace({'all':'global','简单':'easy','中等':'medium','困难':'hard'})
    x['class_id']=x.class_id.fillna('unknown').astype(str)
    if 'core_images' in x:x['n_images']=x.n_images.fillna(x.core_images)
    if 'core_buildings' in x:x['n_buildings']=x.n_buildings.fillna(x.core_buildings)
    assert not x.duplicated(['heldout_building','method_id','difficulty','worker_id']).any()
    return x,old

def attach(e,l):
    a=l[l.difficulty.eq('global')].set_index('worker_id').class_id.to_dict()
    by={(str(d),str(w)):c for d,w,c in l[['difficulty','worker_id','class_id']].itertuples(index=False,name=None) if d!='global'}
    out=[]
    for side in ['a','b']:
        if not by:out.append(e['worker_'+side].map(a).fillna('unknown'))
        else:out.append(pd.Series([by.get((str(d),str(w)),a.get(str(w),'unknown')) for d,w in zip(e.difficulty,e['worker_'+side])],index=e.index))
    ca,cb=out;known=ca.ne('unknown') & cb.ne('unknown')
    rel=pd.Series(np.where(~known,'unknown',np.where(ca.eq(cb),'within','between')),index=e.index)
    return ca,cb,rel

def add_history(e,old):
    p=old[old.heldout_building.ne('FULL')].set_index(['heldout_building','worker_id'])
    for side in ['a','b']:
        ids=pd.MultiIndex.from_arrays([e.building,e['worker_'+side]])
        a=p.reindex(ids)
        for dest,col in [('beta','Q_effect_B8L2'),('q_support','Q_supported'),('time','T_source_origin_effect'),('time_support','T_source_origin_supported')]:e[dest+'_'+side]=a[col].to_numpy()
        theta=np.full(len(e),np.nan);supported=np.zeros(len(e),bool)
        for d in ['easy','medium','hard']:
            mask=e.difficulty.eq(d).to_numpy()
            theta[mask]=a['theta_'+d+'_B8L2'].to_numpy()[mask]
            supported[mask]=a['difficulty_supported_'+d].fillna(False).to_numpy(bool)[mask]
        e['theta_'+side]=theta;e['theta_support_'+side]=supported
    e['beta_abs_difference']=(e.beta_a-e.beta_b).abs()
    e['q_near']=e.beta_abs_difference.le(3) & e.q_support_a & e.q_support_b
    return e

def reproduce_predictions(e,l):
    methods=sorted(l.method_id.unique());methods=['baseline_k_difficulty']+methods
    wide=e[['event_id','building','image_id','panel_id','k','difficulty']].copy()
    for m in methods:wide['p__'+m]=np.nan;wide['rel__'+m]='unknown'
    train_primary=e[e.panel_id.eq(PRIMARY)]
    calibration=[]
    for bi,b in enumerate(sorted(e.building.unique())):
        tr=train_primary[train_primary.building.ne(b)];te=e[e.building.eq(b)]
        for m in methods:
            if m=='baseline_k_difficulty':
                rt=pd.Series('unknown',index=tr.index);rv=pd.Series('unknown',index=te.index)
            else:
                lab=l[l.heldout_building.eq(b)&l.method_id.eq(m)]
                if not len(lab):raise ValueError('missing frozen labels '+b+' '+m)
                _,_,rt=attach(tr,lab);_,_,rv=attach(te,lab)
            cal=fit_calibrator(tr,rt)
            wide.loc[te.index,'p__'+m]=predict_calibrator(cal,te,rv)
            wide.loc[te.index,'rel__'+m]=rv
            calibration.append({'heldout_building':b,'method_id':m,'train_images':tr.image_id.nunique(),'train_buildings':tr.building.nunique(),'test_images':te.image_id.nunique(),'global_training_probability':cal['global'],'rates':[(list(k),v,cal['support'][k]) for k,v in cal['rates'].items()]})
        print('assessed frozen fold',bi+1,b,flush=True)
    assert wide.filter(like='p__').notna().all().all()
    wide.to_csv(OUT/'EVENT_PREDICTIONS_WIDE.csv.gz',index=False)
    savej(OUT/'CALIBRATION_TRAINING_RECEIPT.json',calibration)
    return wide

def unit_summary(f,metric):
    valid=f[metric].notna();s=f.loc[valid,['building','image_id',metric]]
    if not len(s):return {'n':0,'images':0,'buildings':0}
    s=s.copy();s[metric]=pd.to_numeric(s[metric],errors='raise').astype(float)
    im=s.groupby(['building','image_id'])[metric].mean();bm=im.groupby(level='building').mean()
    a=bm.to_numpy(float);rng=np.random.default_rng(SEED);boot=rng.choice(a,(2000,len(a)),replace=True).mean(axis=1)
    return {'n':int(valid.sum()),'images':s.image_id.nunique(),'buildings':len(a),'event_mean':float(s[metric].mean()),'image_mean':float(im.mean()),'building_mean':float(a.mean()),'building_ci_low':float(np.quantile(boot,.025)),'building_ci_high':float(np.quantile(boot,.975)),'event_median':float(s[metric].median()),'event_p90':float(s[metric].quantile(.9)),'event_p95':float(s[metric].quantile(.95)),'event_max':float(s[metric].max())}

def strata(e):
    yield 'all',np.ones(len(e),bool)
    yield 'Q_near_3',e.q_near.to_numpy(bool)
    for o in ['old-old','new-new','old-new']:yield o,e.pair_origin.eq(o).to_numpy()
    for d in ['easy','medium','hard']:yield d,e.difficulty.eq(d).to_numpy()
    yield 'same_target_points_oracle',e.entrant_same_point_count.to_numpy(bool)

def summaries(e,wide,methods):
    records=[];briers=[];contrasts=[];perimage=[];coverage=[]
    main_methods=[m for m in ['Q3','old_QT','old_QTD_archive','old_QTD_supported','forward_selected','reverse_selected','reverse_selected_global','reverse_selected_difficulty'] if m in methods]
    common=np.logical_and.reduce([wide['rel__'+m].ne('unknown').to_numpy() for m in main_methods])
    pd.DataFrame({'event_id':e.event_id,'common_core_support':common}).to_csv(OUT/'COMMON_SUPPORT_EVENTS.csv.gz',index=False)
    for m in methods:
        f=e.copy();f['relation']=wide['rel__'+m].to_numpy();f['probability']=wide['p__'+m].to_numpy()
        f['brier']=(f.probability-f.stable_main.astype(float))**2
        f['baseline_brier']=(wide['p__baseline_k_difficulty'].to_numpy()-f.stable_main.astype(float))**2
        f['brier_improvement']=f.baseline_brier-f.brier
        own=f.relation.ne('unknown')
        for panel,gp in f.groupby('panel_id'):
            for k,gk in gp.groupby('k'):
                for s,mask in [('all_events_with_unknown_fallback',np.ones(len(gk),bool)),('own_supported',own.loc[gk.index].to_numpy()),('common_core_supported',common[gk.index])]:
                    g=gk.loc[mask];coverage.append({'method_id':m,'panel_id':panel,'k':k,'support':s,'events':len(g),'images':g.image_id.nunique(),'buildings':g.building.nunique(),'within':int(g.relation.eq('within').sum()),'between':int(g.relation.eq('between').sum()),'unknown':int(g.relation.eq('unknown').sum())})
                    for metric in ['brier','brier_improvement']:briers.append({'method_id':m,'panel_id':panel,'k':k,'support':s,'metric':metric,**unit_summary(g,metric)})
        if m=='baseline_k_difficulty':continue
        for s,mask in strata(f):
            fs=f.loc[mask & own.to_numpy()]
            if m not in main_methods and s not in ['all','Q_near_3']:continue
            for (panel,k,r),g in fs.groupby(['panel_id','k','relation']):
                for metric in METRICS:
                    records.append({'method_id':m,'panel_id':panel,'k':k,'stratum':s,'relation':r,'metric':metric,**unit_summary(g,metric)})
            # Compare relations inside exactly the same image/k/background.
            keys=['panel_id','k','building','image_id','background_id']
            nums=fs.groupby(keys+['relation'])[METRICS].mean().unstack('relation')
            if 'within' not in nums.columns.get_level_values(1) or 'between' not in nums.columns.get_level_values(1):continue
            for metric in METRICS:
                z=nums[metric].dropna(subset=['within','between']).reset_index()
                z['contrast']=z.between-z.within
                for (panel,k),g in z.groupby(['panel_id','k']):
                    stats=unit_summary(g,'contrast');contrasts.append({'method_id':m,'panel_id':panel,'k':k,'stratum':s,'metric':metric,'contrast':'between_minus_within','backgrounds':len(g),**stats})
                    img=g.groupby(['building','image_id'])[['within','between','contrast']].mean().reset_index()
                    for row in img.to_dict('records'):perimage.append(dict(method_id=m,panel_id=panel,k=k,stratum=s,metric=metric,**row))
        print('summarized',m,flush=True)
    pd.DataFrame(records).to_csv(OUT/'METRIC_DISTRIBUTIONS.csv.gz',index=False)
    pd.DataFrame(briers).to_csv(OUT/'PAIRED_PREDICTION_SUMMARY.csv',index=False)
    pd.DataFrame(coverage).to_csv(OUT/'METHOD_EVENT_COVERAGE.csv',index=False)
    pd.DataFrame(contrasts).to_csv(OUT/'MATCHED_BACKGROUND_CONTRASTS.csv',index=False)
    pd.DataFrame(perimage).to_csv(OUT/'MATCHED_BACKGROUND_PER_IMAGE.csv.gz',index=False)
    savej(OUT/'COMMON_SUPPORT_DEFINITION.json',{'methods':main_methods,'known_event_intersection':int(common.sum()),'total_events':len(e),'primary_known':int((common & e.panel_id.eq(PRIMARY).to_numpy()).sum())})

def paired_method_comparisons(e,wide):
    methods=[c[3:] for c in wide if c.startswith('p__')]
    targets=[m for m in methods if m.startswith(('forward_','reverse_selected'))]
    references=[m for m in ['baseline_k_difficulty','Q3','old_QT','old_QTD_archive'] if m in methods]
    rows=[];detail=[]
    y=e.stable_main.to_numpy(float)
    for m in targets:
        for ref in references:
            f=e[['panel_id','k','building','image_id','q_near','pair_origin']].copy()
            f['brier_improvement']=(wide['p__'+ref].to_numpy()-y)**2-(wide['p__'+m].to_numpy()-y)**2
            common=wide['rel__'+m].ne('unknown').to_numpy()
            if ref!='baseline_k_difficulty':common &= wide['rel__'+ref].ne('unknown').to_numpy()
            for s,mask in [('all_events_unknown_fallback',np.ones(len(f),bool)),('pairwise_common_support',common),('common_Q_near_3',common&e.q_near.to_numpy())]+[(o,common&e.pair_origin.eq(o).to_numpy())for o in ['old-old','new-new','old-new']]:
                for (panel,k),g in f.loc[mask].groupby(['panel_id','k']):
                    rows.append(dict(method_id=m,reference_method=ref,panel_id=panel,k=k,stratum=s,**unit_summary(g,'brier_improvement')))
                    bm=g.groupby(['building','image_id']).brier_improvement.mean().groupby('building').mean()
                    detail.extend(dict(method_id=m,reference_method=ref,panel_id=panel,k=k,stratum=s,building=b,brier_improvement=v) for b,v in bm.items())
    pd.DataFrame(rows).to_csv(OUT/'PAIRED_METHOD_BRIER_COMPARISONS.csv',index=False)
    pd.DataFrame(detail).to_csv(OUT/'PAIRED_METHOD_PER_BUILDING.csv.gz',index=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['predict','summarize','all'],default='all');args=ap.parse_args()
    e=events();l,old=labels();e=add_history(e,old)
    l.to_csv(OUT/'ALL_SELECTED_AND_BASELINE_LABELS.csv.gz',index=False)
    e.to_csv(OUT/'COMMON_EVENT_ANALYSIS_INPUT.csv.gz',index=False)
    if args.stage in ['predict','all']:w=reproduce_predictions(e,l)
    else:w=pd.read_csv(OUT/'EVENT_PREDICTIONS_WIDE.csv.gz')
    methods=[c[3:] for c in w if c.startswith('p__')]
    if args.stage in ['summarize','all']:
        summaries(e,w,methods);paired_method_comparisons(e,w)
    savej(OUT/'ASSESSMENT_RECEIPT.json',{'registration_sha256':sha(OUT/'REGISTRATION.json'),'events_sha256':sha(ROOT/'events/common_events.csv.gz'),'n_events':len(e),'methods':methods,'labels_sha256':sha(OUT/'ALL_SELECTED_AND_BASELINE_LABELS.csv.gz'),'type_discovery_or_selection_done_here':False,'new_calibrator_replay':True,'external_blind_test':False})
if __name__=='__main__':main()
