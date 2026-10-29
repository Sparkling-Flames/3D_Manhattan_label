"""Separate actual C and B increments along exact unchanged-A replacement paths.

For every pair of m values retain C_large-C_small, B_large-B_small and
their difference. Net advantage change is not called a C quality improvement.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from measure_registered_events import METRICS,save,jsave,time_signature

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pairs',required=True);ap.add_argument('--paths',required=True);ap.add_argument('--scalars',required=True);ap.add_argument('--target-conditions',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);pairs=pd.read_csv(a.pairs,low_memory=False);paths=pd.read_csv(a.paths,low_memory=False);s=pd.read_csv(a.scalars,low_memory=False)
 assert s.team_key.is_unique and paths.path_id.is_unique
 s=s.set_index('team_key');p=paths.set_index('path_id');targets=pd.read_csv(a.target_conditions).set_index('pool_id');v={};arms={}
 for c in ['image','building','condition','source_class','target_class','background_target_n','max_m','block_replicate','background_replicate']:
  v[c]=pairs.path_id.map(p[c])
 for c in ['official_difficulty','scope','geometric_challenge','structural_condition','ref_turn5','ref_H','ref_short_edges','legal_targets_in_image_condition']:
  v[c]=pairs.pool_id.map(targets[c])
 avail=[c for c in METRICS if c in s]
 for arm,col in [('A','A_team_key'),('B_small','B_small'),('B_large','B_large'),('C_small','C_small'),('C_large','C_large')]:
  assert set(pairs[col])<=set(s.index)
  r=s.reindex(pairs[col]);r.index=pairs.index;arms[arm]=r
  v[arm+'_failed']=r.B8L2.isna()
  for c in avail:v[arm+'_'+c]=pd.to_numeric(r[c],errors='coerce')
 for c in avail:
  cg=v['C_large_'+c]-v['C_small_'+c];bg=v['B_large_'+c]-v['B_small_'+c]
  v[c+'_C_increment']=cg;v[c+'_B_increment']=bg;v[c+'_net_increment']=cg-bg
  v[c+'_net_small']=v['C_small_'+c]-v['B_small_'+c];v[c+'_net_large']=v['C_large_'+c]-v['B_large_'+c]
  # Preserve each pair's broader support, then make the main decomposition on
  # exactly the same four B/C endpoints. Mean(C)-mean(B)=mean(net) on this set.
  common=cg.notna()&bg.notna();v[c+'_CB4_scored']=common
  v[c+'_C_increment_matched_CB']=cg.where(common);v[c+'_B_increment_matched_CB']=bg.where(common)
  v[c+'_net_increment_matched_CB']=(cg-bg).where(common)
  # A is physically identical at both m values: five unique endpoints suffice
  # for the all-three-arm amplitude comparison across the two m values.
  common5=common&v['A_'+c].notna();v[c+'_A_BC5_scored']=common5
  within0=(v['B_small_'+c]-v['A_'+c]).abs().where(common5)
  within1=(v['B_large_'+c]-v['A_'+c]).abs().where(common5)
  cross0=((v['C_small_'+c]-v['A_'+c]).abs()+(v['C_small_'+c]-v['B_small_'+c]).abs()).div(2).where(common5)
  cross1=((v['C_large_'+c]-v['A_'+c]).abs()+(v['C_large_'+c]-v['B_large_'+c]).abs()).div(2).where(common5)
  v[c+'_within_small_matched_ABC']=within0;v[c+'_within_large_matched_ABC']=within1
  v[c+'_cross_small_matched_ABC']=cross0;v[c+'_cross_large_matched_ABC']=cross1
  v[c+'_within_increment_matched_ABC']=within1-within0;v[c+'_cross_increment_matched_ABC']=cross1-cross0
  v[c+'_gap_increment_matched_ABC']=(cross1-within1)-(cross0-within0)
 for arm in ['B','C']:
  gain=v['B8L2_'+arm+'_increment'];v[arm+'_Q_improved']=(gain>0).astype(float).where(gain.notna());v[arm+'_Q_loss10']=(gain<-10).astype(float).where(gain.notna())
  v[arm+'_failure_or_loss10']=(v[arm+'_large_failed']|(gain<-10)).astype(float).where(~v[arm+'_small_failed'])
 # CSV blanks are NaN; the full-endpoint helper expects None for unknown time
 # histories. Preserve unknown rather than interpreting it as zero seconds.
 signatures={arm:r['record_time_by_kind_json'].map(lambda x:time_signature({'record_time_by_kind_json':x if isinstance(x,(str,dict)) else None})) for arm,r in arms.items()}
 for arm in ['B','C']:
  sig0,known0=zip(*signatures[arm+'_small']);sig1,known1=zip(*signatures[arm+'_large'])
  ok=np.asarray(known0)&np.asarray(known1)&(np.asarray(sig0)==np.asarray(sig1));v[arm+'_time_comparable']=ok
  t0,t1=v[arm+'_small_source_time_total_seconds'],v[arm+'_large_source_time_total_seconds']
  v[arm+'_record_time_increment_pct_raw']=100*(t1/t0-1).where(t0>0)
  v[arm+'_record_time_increment_pct_source_matched']=v[arm+'_record_time_increment_pct_raw'].where(ok)
 common_time=np.ones(len(pairs),dtype=bool);base_sig=np.array([x[0] for x in signatures['B_small']])
 for arm in ['B_small','B_large','C_small','C_large']:
  sig,known=zip(*signatures[arm]);common_time &= np.asarray(known)&(np.asarray(sig)==base_sig)
 v['time_comparable_CB4']=common_time
 for role in ['C','B','net']:
  v['record_time_'+role+'_increment_seconds_source_matched_CB']=v['source_time_total_seconds_'+role+'_increment'].where(common_time)
 table=pd.concat([pairs,pd.DataFrame(v)],axis=1);save(out/'EXACT_M_PATH_INCREMENT_METRICS.csv.gz',table)
 # This is a descriptive size-response, not an independent-event sample.
 # Equal pool means are saved separately from the full exact path-pair table.
 group=['method','n','m_small','m_large','pool_id','image','building'];measurecols=[c for c in table if c.endswith(('_C_increment','_B_increment','_net_increment','_matched_CB','_matched_ABC')) or c in ['B_Q_improved','C_Q_improved','B_Q_loss10','C_Q_loss10','B_failure_or_loss10','C_failure_or_loss10','C_record_time_increment_pct_source_matched','B_record_time_increment_pct_source_matched']]
 pool=table.groupby(group,dropna=False)[measurecols].mean().reset_index();save(out/'M_PATH_INCREMENT_BY_POOL.csv.gz',pool)
 denominators=table.groupby(group,dropna=False)[measurecols].count().reset_index();save(out/'M_PATH_INCREMENT_METRIC_DENOMINATORS.csv.gz',denominators)
 maxerr=0.
 for c in avail:
  cs,bs,ns=[c+'_'+arm+'_increment_matched_CB' for arm in ['C','B','net']]
  assert denominators[cs].equals(denominators[bs]) and denominators[cs].equals(denominators[ns])
  err=(pool[cs]-pool[bs]-pool[ns]).abs().dropna()
  if len(err):maxerr=max(maxerr,float(err.max()))
 assert maxerr<1e-7,maxerr
 counts=table.groupby(group,dropna=False).agg(path_pairs=('path_id','size'),distinct_paths=('path_id','nunique')).reset_index();save(out/'M_PATH_PAIR_SUPPORT_BY_POOL.csv.gz',counts)
 jsave(out/'MEASUREMENT_RECEIPT.json',dict(path_pairs=len(table),paths=table.path_id.nunique(),pools=table.pool_id.nunique(),complete=True,
  pair_input_sha256=hashlib.sha256(Path(a.pairs).read_bytes()).hexdigest(),scalar_input_sha256=hashlib.sha256(Path(a.scalars).read_bytes()).hexdigest(),
  fixed_A_verified_during_registration=True,new_fusions=0,new_scoring=0,identity='C increment minus B increment equals net advantage increment; n and original A fixed',
  main_increment_support='same four B/C endpoints per metric; matched_CB columns',amplitude_change_support='same A plus four B/C endpoints per metric; five unique endpoints because original A is fixed',broader_pairwise_support_retained=True,
  common_mean_decomposition_max_abs_error=maxerr,time_comparable_CB4='all four endpoints have all known times and the same time-source record-count vector'))
 print(json.dumps(dict(path_pairs=len(table),pools=table.pool_id.nunique(),complete=True)),flush=True)
if __name__=='__main__':main()
