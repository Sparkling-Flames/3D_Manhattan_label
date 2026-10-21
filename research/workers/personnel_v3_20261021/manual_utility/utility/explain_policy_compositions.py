"""Describe actual selected composition shifts using held-out-building history.

This is interpretation of already frozen choices, not a new choice rule. Full
class-count distributions remain in POLICY_CLASS_COMPOSITIONS. Comparisons of
worker history are reported only when the entire selected and ordinary team
mass is observed; unknown histories are never treated as zero.
"""
from __future__ import annotations
import argparse,json
import numpy as np
import pandas as pd
from prepare_training import HERE,OLD,atomic_csv,atomic_json
from policy_study import TAX,QT
from summarize_policy import macro_many,slices

STRUCT=['turn_history','short_history','redundancy_history','area_history',
        'height_history','simple_turn_history','complex_turn_history',
        'complex_short_history']
JOINT_QT=['joint_q_history','joint_q_downside','joint_t_history']
FIELDS=QT+STRUCT+JOINT_QT
KEY=['condition','heldout_building','worker_id']

def histories():
    q=pd.read_csv(OLD/'multivariate/continuous_features_lobo.csv.gz',low_memory=False)
    q=q[q.metric.eq('B8L2')][KEY+QT]
    s=pd.read_csv(TAX/'CONTINUOUS_FEATURES_LOBO.csv.gz',low_memory=False)[KEY+STRUCT]
    j=pd.read_csv(TAX/'JOINT_LABELS_LOBO.csv.gz',low_memory=False)
    j=j[KEY+['q_history','q_downside','t_history']].rename(columns={
        'q_history':'joint_q_history','q_downside':'joint_q_downside','t_history':'joint_t_history'})
    f=q.merge(s,on=KEY,how='outer',validate='one_to_one').merge(j,on=KEY,how='outer',validate='one_to_one')
    assert not f.duplicated(KEY).any()
    return {(c,b):g.set_index('worker_id')[FIELDS] for (c,b),g in f.groupby(['condition','heldout_building'])}

def expected_history(probs,h,n):
    workers=list(probs);weights=np.array([probs[w] for w in workers],float)
    assert np.isclose(weights.sum(),n)
    values=h.reindex(workers).to_numpy(float);known=np.isfinite(values)
    mass=(known*weights[:,None]).sum(axis=0)
    value=(np.where(known,values,0)*weights[:,None]).sum(axis=0)/n
    value[~np.isclose(mass,n)]=np.nan
    return value,mass/n

def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=['manual','semi','both'],default='both');a=p.parse_args()
    hs=histories();records=[];inputs=[]
    conditions=['manual','semi'] if a.condition=='both' else [a.condition]
    for condition in conditions:
        paths=sorted(HERE.glob(f'cross_panel_LOBO/{condition}/*/PANEL_POLICY_RESULTS.csv.gz'))
        paths+=sorted(HERE.glob(f'f01_finite_LOBO/{condition}/*/PANEL_POLICY_RESULTS.csv.gz'))
        for path in paths:
            inputs.append(str(path.relative_to(HERE)))
            d=pd.read_csv(path,low_memory=False)
            for pid,g in d.groupby('panel_id'):
                ordinary=g[g.policy.eq('ordinary_uniform')].iloc[0]
                history=hs[(condition,ordinary.building)]
                random=json.loads(ordinary.selected_worker_inclusion_probabilities)
                baseline,baseknown=expected_history(random,history,ordinary.n)
                for row in g.itertuples():
                    selected=json.loads(row.selected_worker_inclusion_probabilities)
                    value,known=expected_history(selected,history,row.n)
                    r={field:getattr(row,field) for field in ['regime','condition','family','policy','panel_id',
                        'building','image','difficulty','n','source_domain','all_candidates_time_compatible',
                        'common_candidates','candidate_support_sha256','selected_teams','delta_B8L2',
                        'failure_delta_pp','time_percent_vs_uniform']}
                    for field in ['selected_coarse_mean_counts_json','selected_fine_mean_counts_json',
                                  'ordinary_coarse_mean_counts_json','ordinary_fine_mean_counts_json']:
                        if hasattr(row,field):r[field]=getattr(row,field)
                    for i,f in enumerate(FIELDS):
                        r['selected_history_'+f]=value[i]
                        r['ordinary_history_'+f]=baseline[i]
                        r['history_shift_'+f]=value[i]-baseline[i]
                        r['selected_history_known_fraction_'+f]=known[i]
                        r['ordinary_history_known_fraction_'+f]=baseknown[i]
                    records.append(r)
    out=pd.DataFrame(records);assert len(out)
    prefix=('ALL' if a.condition=='both' else a.condition.upper())+'_SELECTED_HISTORY_SHIFTS'
    atomic_csv(out,HERE/(prefix+'.csv.gz'))
    summaries=[]
    fields=['history_shift_'+f for f in FIELDS]
    for (regime,condition,family,policy),g in out.groupby(['regime','condition','family','policy']):
        for kind,value,z in slices(g):
            results,_=macro_many(z,fields)
            for outcome,detail in results.items():
                summaries.append(dict(regime=regime,condition=condition,family=family,policy=policy,
                    slice_kind=kind,slice_value=value,outcome=outcome,**detail))
    atomic_csv(pd.DataFrame(summaries),HERE/(prefix+'_SUMMARY.csv.gz'))
    atomic_json(dict(condition=a.condition,inputs=inputs,rows=len(out),
        label_definition='the same target-building-excluded history map as selection',
        unknown='mean and shift missing unless entire selected and ordinary team probability mass observed',
        interpretation_only=True,does_not_refit_or_change_selection=True),HERE/(prefix+'_RECEIPT.json'))
    print(prefix,len(out),len(summaries),flush=True)

if __name__=='__main__':main()
