#!/usr/bin/env python3
"""Frozen-category origin controls and paired last-seat policy comparisons.

The origin recalibration is a post-freeze confounding diagnostic, not a candidate
selection result. Both its unconditional and conditional effects are retained.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'forward'))
from evaluate_common import attach,boolcol,unit_summary,fit_calibrator,predict_calibrator,savej,PRIMARY
from selection_fast import EncodedPanel
from atomic_exports import csv_verified

def origin_control(e,l,wide):
    methods=['Q3','old_QT','old_QTD_archive','forward_selected','forward_full','reverse_selected','reverse_selected_swap','reverse_selected_difficulty']
    savej(HERE/'ORIGIN_CONTROL_DESIGN.json',{'status':'post-class-freeze sensitivity; no K, threshold, feature or label changes','reason':'FULL reverse partition strongly associated with source batch; preserve overall effects and additionally check remaining relation information conditional on known source pair','training_panel':PRIMARY,'heldout':'building','conditional_cell':'k x frozen difficulty x old-old/new-new/old-new','not_type_feature':'origin is only a calibration control, never an input to the discovered class','new_panel':'evaluation only'})
    f=e[['event_id','panel_id','building','image_id','difficulty','k','worker_a','worker_b','stable_main','pair_origin','q_near']].copy()
    f['difficulty']=f.difficulty+'|'+f.pair_origin
    pred=f[['event_id']].copy();pred['p_origin_baseline']=np.nan
    for m in methods:pred['p_origin__'+m]=np.nan
    parity=[]
    for bi,b in enumerate(sorted(e.building.unique())):
        tr=f[f.panel_id.eq(PRIMARY)&f.building.ne(b)];te=f[f.building.eq(b)]
        rawtr=e.loc[tr.index];rawte=e.loc[te.index]
        unknown=pd.Series('unknown',index=tr.index);base=fit_calibrator(tr,unknown)
        enc=EncodedPanel(tr);ev=EncodedPanel(te)
        # Several origin cells occur per image. Use original aggregation for the
        # k/global fallbacks rather than the single-difficulty shortcut.
        enc.cells=base['cells'];enc.k_rates=base['k'];enc.global_rate=base['global']
        pred.loc[te.index,'p_origin_baseline']=predict_calibrator(base,te,pd.Series('unknown',index=te.index))
        for m in methods:
            lab=l[l.method_id.eq(m)&l.heldout_building.eq(b)]
            _,_,rt=attach(rawtr,lab);_,_,rv=attach(rawte,lab)
            cal=enc.fit(rt);values=ev.predict(cal,rv);pred.loc[te.index,'p_origin__'+m]=values
            if bi==0:
                orig=predict_calibrator(fit_calibrator(tr,rt),te,rv);delta=float(np.abs(orig-values).max());assert delta<1e-12
                parity.append(dict(method_id=m,max_probability_difference=delta))
    rows=[]
    for m in methods:
        for name,a,b in [('origin_only_vs_k_difficulty',pred.p_origin_baseline,wide['p__baseline_k_difficulty']),('class_after_origin_vs_origin_only',pred['p_origin__'+m],pred.p_origin_baseline),('class_after_origin_vs_original_class',pred['p_origin__'+m],wide['p__'+m])]:
            z=e[['panel_id','k','building','image_id','q_near','pair_origin']].copy();y=e.stable_main.to_numpy(float);z['brier_improvement']=(b.to_numpy()-y)**2-(a.to_numpy()-y)**2
            for s,mask in [('all',np.ones(len(z),bool)),('Q_near_3',z.q_near.to_numpy())]+[(o,z.pair_origin.eq(o).to_numpy())for o in ['old-old','new-new','old-new']]:
                for (panel,k),g in z.loc[mask].groupby(['panel_id','k']):rows.append(dict(method_id=m,comparison=name,panel_id=panel,k=k,stratum=s,**unit_summary(g,'brier_improvement')))
    csv_verified(pred,HERE/'ORIGIN_CONTROL_PREDICTIONS.csv.gz');csv_verified(pd.DataFrame(rows),HERE/'ORIGIN_CONTROL_SUMMARY.csv');savej(HERE/'ORIGIN_CONTROL_ORIGINAL_PARITY.json',parity)

def paired_selection(e):
    choices=pd.read_csv(HERE/'LAST_SEAT_CHOICES.csv.gz');assert choices.event_id.equals(e.event_id)
    rows=[];details=[]
    for policy,reference in [('QT','Q'),('QTD','Q'),('QTD','QT'),('QD','Q'),('class_mean_Q__forward_selected','Q'),('class_mean_Q__reverse_selected','Q'),('class_mean_Q__reverse_selected_swap','Q')]:
        dp=choices['choose_a_probability__'+policy]-choices['choose_a_probability__'+reference]
        f=e[['panel_id','k','building','image_id','pair_origin','q_near']].copy()
        f['Q_change']=dp*(e.B8L2_a-e.B8L2_b);f['completion_change']=dp*(e.complete_a.astype(float)-e.complete_b.astype(float));f['source_seconds_change']=dp*(e.source_entrant_time_a-e.source_entrant_time_b)
        for s,mask in [('all_common_policy_support',dp.notna()),('Q_near_3',dp.notna()&e.q_near)]+[(o,dp.notna()&e.pair_origin.eq(o))for o in ['old-old','new-new','old-new']]:
            for (panel,k),g in f.loc[mask].groupby(['panel_id','k']):
                for metric in ['Q_change','completion_change','source_seconds_change']:rows.append(dict(policy=policy,reference_policy=reference,panel_id=panel,k=k,stratum=s,metric=metric,**unit_summary(g,metric)))
    csv_verified(pd.DataFrame(rows),HERE/'PAIRED_LAST_SEAT_POLICY_COMPARISONS.csv')

def practical_image_summary():
    d=pd.read_csv(HERE/'MATCHED_BACKGROUND_PER_IMAGE.csv.gz')
    f=d[d.metric.eq('stable_main')];rows=[]
    for (m,p,k,s),g in f.groupby(['method_id','panel_id','k','stratum']):
        rows.append(dict(method_id=m,panel_id=p,k=k,stratum=s,matched_images=len(g),matched_buildings=g.building.nunique(),within_image_mean=g.within.mean(),between_image_mean=g.between.mean(),within_building_mean=g.groupby('building').within.mean().mean(),between_building_mean=g.groupby('building').between.mean().mean(),images_with_within_rate_above_half=int(g.within.gt(.5).sum()),images_with_between_rate_above_half=int(g.between.gt(.5).sum()),images_with_within_rate_at_least_80pct=int(g.within.ge(.8).sum()),images_with_within_better=int(g.within.gt(g.between+1e-12).sum()),images_with_equal_rates=int(np.isclose(g.within,g.between,rtol=0,atol=1e-12).sum()),images_with_within_worse=int(g.within.lt(g.between-1e-12).sum())))
    csv_verified(pd.DataFrame(rows),HERE/'PRACTICAL_MATCHED_IMAGE_COVERAGE.csv')

def main():
    e=pd.read_csv(HERE/'COMMON_EVENT_ANALYSIS_INPUT.csv.gz',low_memory=False);l=pd.read_csv(HERE/'ALL_SELECTED_AND_BASELINE_LABELS.csv.gz');w=pd.read_csv(HERE/'EVENT_PREDICTIONS_WIDE.csv.gz')
    for c in ['stable_main','q_near','complete_a','complete_b']:e[c]=boolcol(e[c])
    paired_selection(e);practical_image_summary();print('paired selection and practical image counts done',flush=True)
    origin_control(e,l,w);print('origin diagnostic complete',flush=True)
if __name__=='__main__':main()
