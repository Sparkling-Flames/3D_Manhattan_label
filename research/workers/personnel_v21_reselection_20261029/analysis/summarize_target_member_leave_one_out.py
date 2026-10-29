"""Describe all six m5 target-member choices with one fixed A and B5 per pool.

Old m6 endpoints remain a separately labelled anchor. Deleting a target from C6
also returns a source worker, so the old/new delta is not pure target deletion.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from measure_registered_events import save,jsave

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--metrics',required=True);ap.add_argument('--anchors',required=True);ap.add_argument('--old-scalars',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);d=pd.read_csv(a.metrics,low_memory=False);anchors=pd.read_csv(a.anchors).set_index('anchor_event_id');s=pd.read_csv(a.old_scalars,low_memory=False).set_index('team_key')
 assert len(d)==336 and d.pool_id.nunique()==56 and set(d.m)=={5}
 for col in ['old_B6_team_key','old_C6_team_key']:
  d[col]=d.anchor_m6_event_id.map(anchors[col])
 for arm in ['B','C']:
  for metric in ['B8L2','D10','nodes','minimum_support','source_time_total_seconds']:
   d['old_anchor_m6_'+arm+'_'+metric]=d['old_'+arm+'6_team_key'].map(s[metric])
   current=d[arm+'_'+metric]
   d[arm+'5_minus_old_'+arm+'6_'+metric+'_with_source_returned']=current-d['old_anchor_m6_'+arm+'_'+metric]
 save(out/'TARGET_MEMBER_LEAVE_ONE_OUT_ALL_CHOICES.csv.gz',d)
 rows=[]
 for pid,g in d.groupby('pool_id',sort=True):
  assert len(g)==6 and g.omitted_target_worker.nunique()==6 and g.A_team_key.nunique()==g.B_team_key.nunique()==1
  q=g.C_B8L2;ca=g.B8L2_CA;cb=g.B8L2_CB;good=g.ABC_scored.astype(bool)
  row={k:g.iloc[0][k] for k in ['pool_id','image','building','method','source_class','target_class','n','m','anchor_m6_event_id','A_team_key','B_team_key','source_returned_to_D','source_omitted_from_Y','official_difficulty','scope']}
  row.update(target_choices=6,distinct_C5_teams=g.C_team_key.nunique(),C5_scored=int(q.notna().sum()),C5_failed=int(g.C_failed.sum()),all_three_scored=int(good.sum()),
   C5_Q_mean=q.mean(),C5_Q_min=q.min(),C5_Q_max=q.max(),C5_Q_range=q.max()-q.min(),C5_Q_sd=q.std(ddof=1),
   CA_mean=ca.mean(),CA_positive_choices=int((ca>0).sum()),CA_evaluable=int(ca.notna().sum()),
   CB_mean=cb.mean(),CB_min=cb.min(),CB_max=cb.max(),CB_positive_choices=int((cb>0).sum()),CB_evaluable=int(cb.notna().sum()),
   same_class_B5_minus_A_Q=g.B8L2_BA.iloc[0],A_Q=g.A_B8L2.iloc[0],B5_Q=g.B_B8L2.iloc[0],
   old_C6_Q=g.old_anchor_m6_C_B8L2.iloc[0],old_B6_Q=g.old_anchor_m6_B_B8L2.iloc[0],
   worst_omitted_target_workers='|'.join(sorted(g.loc[q.eq(q.min()),'omitted_target_worker'])) if q.notna().any() else '',
   failed_omitted_target_workers='|'.join(sorted(g.loc[g.C_failed.astype(bool),'omitted_target_worker'])),
   C5_minus_C6_mean_with_source_returned=g.C5_minus_old_C6_B8L2_with_source_returned.mean(),
   record_time_CA_pct_source_matched_mean=g.record_time_CA_pct_source_matched.mean(),record_time_CB_pct_source_matched_mean=g.record_time_CB_pct_source_matched.mean())
  rows.append(row)
 summary=pd.DataFrame(rows);save(out/'TARGET_MEMBER_SENSITIVITY_BY_ANCHOR.csv',summary)
 jsave(out/'MEMBER_SENSITIVITY_RECEIPT.json',dict(pools=56,events=336,all_six_choices_exhausted=True,n=12,actual_m=5,old_anchor_m=6,
  original_A_fixed=True,B5_fixed=True,outcome_blind_anchor_selection=True,classification_changed=False,
  analysis='Target-member composition sensitivity within six alternative five-person target blocks; not a universal member-importance estimate.',
  old_anchor_delta='C5 minus old C6 also returns one specified source worker; original n is unchanged but m falls from 6 to 5.',
  positive_CB_in_all_six_pools=int((summary.CB_positive_choices==6).sum()),positive_CB_in_majority_choices_pools=int((summary.CB_positive_choices>3).sum()),
  all_six_CB_evaluable_pools=int((summary.CB_evaluable==6).sum()),C5_scored_total=int(summary.C5_scored.sum()),C5_failed_total=int(summary.C5_failed.sum())))
 print(json.dumps(dict(pools=56,events=336,complete=True)),flush=True)
if __name__=='__main__':main()
