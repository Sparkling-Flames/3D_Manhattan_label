#!/usr/bin/env python3
"""Fixed-selection D10-history and frozen explanation-rule event assessments.

Rules/family/K come from the training-side discovery runners. This script never
selects a candidate. Shared calibrated probabilities use the audited equivalent
encoder, with an independent original-function parity check on the first fold.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'forward'))
from evaluate_common import attach,boolcol,unit_summary,savej,PRIMARY,fit_calibrator as original_fit,predict_calibrator as original_predict
from selection_fast import EncodedPanel
from atomic_exports import csv_verified

def load_labels():
    a=pd.read_csv(ROOT/'forward/selected_classes_by_fold_D10.csv.gz')
    a=a[a.method_id.isin(['forward_selected','forward_full','forward_base_plus_difficulty'])].copy()
    a['source_method_id']=a.method_id;a['method_id']=a.method_id+'__D10_history';a['history_quality_metric']='D10'
    b=pd.read_csv(ROOT/'reverse/explanations/rule_classes.csv.gz');b['history_quality_metric']='B8L2'
    p=ROOT/'recovered/work_v2_20261019/profiles'
    old=pd.concat([pd.read_csv(p/'full_profiles.csv'),pd.read_csv(p/'fold_profiles.csv')],ignore_index=True)
    rows=[a,b]
    for m,col in [('Q3','Q3_D10'),('old_QT','QT_D10'),('old_QTD_archive','fine_dtype_merged_D10')]:
        z=old[['heldout_building','worker_id',col]].rename(columns={col:'class_id'}).copy();z['method_id']=m+'__D10_history';z['source_method_id']=m;z['history_quality_metric']='D10';z['difficulty']='global';rows.append(z)
    l=pd.concat(rows,ignore_index=True);l['heldout_building']=l.heldout_building.fillna('FULL');l['difficulty']=l.difficulty.replace({'all':'global','简单':'easy','中等':'medium','困难':'hard'});l['class_id']=l.class_id.fillna('unknown')
    assert not l.duplicated(['method_id','heldout_building','worker_id','difficulty']).any()
    return l

def main():
    cols=['event_id','panel_id','building','image_id','difficulty','k','worker_a','worker_b','stable_main','stable_D10','q_near','pair_origin','abs_delta_Q','floor_change','either_failure','background_id']
    e=pd.concat(pd.read_csv(HERE/'COMMON_EVENT_ANALYSIS_INPUT.csv.gz',usecols=cols,chunksize=25000),ignore_index=True)
    for c in ['stable_main','stable_D10','q_near','either_failure']:e[c]=boolcol(e[c])
    base=pd.read_csv(HERE/'EVENT_PREDICTIONS_WIDE.csv.gz');assert np.array_equal(base.event_id,e.event_id)
    l=load_labels();csv_verified(l,HERE/'SENSITIVITY_CLASSES_BY_FOLD.csv.gz')
    methods=sorted(l.method_id.unique());wide=e[['event_id']].copy();parity=[]
    for m in methods:wide['p_B8__'+m]=np.nan;wide['p_D10__'+m]=np.nan;wide['rel__'+m]='unknown'
    for bi,b in enumerate(sorted(e.building.unique())):
        tr=e[e.panel_id.eq(PRIMARY)&e.building.ne(b)];te=e[e.building.eq(b)]
        enc8=EncodedPanel(tr,'stable_main');enc10=EncodedPanel(tr,'stable_D10');encv=EncodedPanel(te,'stable_main')
        for m in methods:
            lab=l[l.heldout_building.eq(b)&l.method_id.eq(m)];assert len(lab)
            _,_,rt=attach(tr,lab);_,_,rv=attach(te,lab)
            c8=enc8.fit(rt);c10=enc10.fit(rt)
            p8=encv.predict(c8,rv);p10=encv.predict(c10,rv)
            wide.loc[te.index,'p_B8__'+m]=p8;wide.loc[te.index,'p_D10__'+m]=p10;wide.loc[te.index,'rel__'+m]=rv
            if bi==0:
                for outcome,pred in [('stable_main',p8),('stable_D10',p10)]:
                    original=original_predict(original_fit(tr,rt,outcome),te,rv)
                    diff=float(np.abs(original-pred).max());assert diff<1e-12
                    parity.append(dict(method_id=m,heldout_building=b,outcome=outcome,max_probability_difference=diff))
        print('sensitivity fold',bi+1,b,flush=True)
    csv_verified(wide,HERE/'RULE_AND_METRIC_EVENT_PREDICTIONS.csv.gz');savej(HERE/'SENSITIVITY_ORIGINAL_PARITY.json',parity)
    rows=[];metric_rows=[];coverage=[]
    for m in methods:
        source=l.loc[l.method_id.eq(m),'source_method_id'].iloc[0]
        rel=wide['rel__'+m];known=rel.ne('unknown')
        reference=base['p__'+source].to_numpy();p8=wide['p_B8__'+m].to_numpy();p10=wide['p_D10__'+m].to_numpy()
        for cal_name,prob in [('B8_calibration',p8),('D10_calibration',p10)]:
            for outcome in ['stable_main','stable_D10']:
                f=e.copy();y=f[outcome].to_numpy(float);f['brier']=(prob-y)**2;f['improvement_vs_fixed_B8_class_and_calibration']=(reference-y)**2-f.brier
                for s,mask in [('all_with_unknown_fallback',np.ones(len(f),bool)),('own_supported',known.to_numpy()),('Q_near_3',known.to_numpy()&e.q_near.to_numpy())]+[(o,known.to_numpy()&e.pair_origin.eq(o).to_numpy())for o in ['old-old','new-new','old-new']]:
                    for (panel,k),g in f.loc[mask].groupby(['panel_id','k']):
                        for metric in ['brier','improvement_vs_fixed_B8_class_and_calibration']:rows.append(dict(method_id=m,source_method_id=source,calibration=cal_name,outcome=outcome,panel_id=panel,k=k,stratum=s,metric=metric,**unit_summary(g,metric)))
        f=e.copy();f['relation']=rel
        for (panel,k),g in f.groupby(['panel_id','k']):coverage.append(dict(method_id=m,panel_id=panel,k=k,events=len(g),images=g.image_id.nunique(),buildings=g.building.nunique(),known_events=int(g.relation.ne('unknown').sum()),within=int(g.relation.eq('within').sum()),between=int(g.relation.eq('between').sum()),unknown=int(g.relation.eq('unknown').sum())))
        for (panel,k,r),g in f.groupby(['panel_id','k','relation']):
            for metric in ['stable_main','stable_D10','abs_delta_Q','floor_change','either_failure']:metric_rows.append(dict(method_id=m,panel_id=panel,k=k,relation=r,metric=metric,**unit_summary(g,metric)))
    csv_verified(pd.DataFrame(rows),HERE/'RULE_AND_METRIC_PAIRED_SUMMARY.csv')
    csv_verified(pd.DataFrame(metric_rows),HERE/'RULE_AND_METRIC_DISTRIBUTIONS.csv')
    csv_verified(pd.DataFrame(coverage),HERE/'RULE_AND_METRIC_COVERAGE.csv')
    savej(HERE/'RULE_METRIC_ASSESSMENT_RECEIPT.json',{'type_selection_here':False,'families_K_frozen_by_B8_training_selection':True,'rule_training':'training-building historical features only','B8_fixed_members_D10_outcomes':'already in main common-event outcome file','D10_history_refit':'distinct from fixed-member measurement','joint_tolerance_unchanged':True,'methods':methods,'n_events':len(e),'parity_checks':len(parity)})
if __name__=='__main__':main()
