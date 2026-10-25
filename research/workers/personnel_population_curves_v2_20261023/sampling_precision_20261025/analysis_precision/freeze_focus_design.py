#!/usr/bin/env python3
"""Freeze extra sampling using original-24 precision, before new scores exist."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--precision',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.precision)
    d=d[d.condition.eq('manual')&d.layer.isin(['ordinary_manual','doorway_manual'])]
    meta=d[['pool_id','image','building','layer','difficulty','pool_n']].drop_duplicates('pool_id')
    z=d[d.k.between(3,20)&d.k.lt(d.pool_n)]
    q=z.groupby('pool_id').agg(
        old_MCSE_rms_k3to20=('Q_mean_MCSE',lambda v:np.sqrt(np.mean(v*v))),
        old_MCSE_max_k3to20=('Q_mean_MCSE','max'),valid_k=('Q_mean_MCSE','count')
    ).reset_index().merge(meta,on='pool_id',validate='one_to_one')
    q=q.sort_values(['layer','difficulty','old_MCSE_rms_k3to20','pool_id'],ascending=[True,True,False,True])
    q['focus_eligible']=q.pool_n.gt(10)
    q['rank_in_eligible_layer_difficulty']=np.nan
    q.loc[q.focus_eligible,'rank_in_eligible_layer_difficulty']=q[q.focus_eligible].groupby(['layer','difficulty']).cumcount()+1
    q['focus_selected']=q.layer.eq('doorway_manual')|(q.layer.eq('ordinary_manual')&q.rank_in_eligible_layer_difficulty.le(12))
    q['balanced_new_paths']=24
    q['additional_focus_paths']=np.where(q.focus_selected,48,0)
    q['planned_total_natural_paths']=24+q.balanced_new_paths+q.additional_focus_paths
    rule='Manual ordinary N>10 top12 per difficulty by original24 RMS of mean-Q MCSE over k3..min(20,N-1); all doorway; no new outcomes'
    q['selection_definition']=rule
    target=a.out/'FOCUS_PRESELECTION_OLD24_RMS.csv'
    q.to_csv(target,index=False)
    rec={
        'source_commit':'40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',
        'source_precision_table':str(a.precision),'source_sha256':hashlib.sha256(a.precision.read_bytes()).hexdigest(),
        'selection_rule':rule,'full_Manual_pools':len(q),'focused_pools':int(q.focus_selected.sum()),
        'main_balanced_total_paths':48,'focused_total_paths':96,
        'endpoint_anchors':['every Manual pool: all N teams at k=N-1','Manual N<=10: all legal nonempty subsets except deferred k=2; k=1/full reused'],
        'precision_reporting_scales':{'single_image_mean_MCSE_Q':1.0,'fixed_image_panel_mean_MCSE_Q':0.5,'single_image_P10_empirical_95_halfwidth_Q':2.0},
        'stopping_rule':'Complete the registered fixed budgets once; report targets reached and not reached. No sign/significance/smoothness stopping, no seed screening, no further broad sampling.',
        'population':'fixed eligible real v2 pool, uniformly random permutation; kth-prefix uniform k-subset',
        'focus_role':'selected for old sampling noise; secondary fixed-focus-domain result, never substituted for balanced primary all-image result',
        'new_outcomes_used_for_selection':False,
        'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    (a.out/'FROZEN_PRECISION_DESIGN.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(rec,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
