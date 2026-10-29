"""Measure saved direct AC teams separately; never manufacture a same-class B.

Shares the existing v2.1 event metrics and geometry diagnostics. No fitting,
fusion, scoring, parameter selection or reference edits take place here.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from measure_registered_events import METRICS,save,jsave,time_signature
from legacy_geometry_diagnostics import refdiagnostic,geometry_metrics

def compute(events,rows,pool):
 assert 'B_team_key' not in events
 for r in rows.values():
  refdiagnostic(r,pool)
  if r.get('nodes') is not None:
   rn=len(pool['reference']['points_1024x512'])//2
   r['reference_node_shortfall']=max(0,rn-r['nodes']);r['reference_node_excess']=max(0,r['nodes']-rn)
  r['time_source_count_signature'],r['all_time_sources_known']=time_signature(r)
 scal=pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in rows.values()]).set_index('team_key')
 avail=[c for c in METRICS if c in scal];arms={};extra={}
 for arm in ['A','C']:
  ar=scal.reindex(events[arm+'_team_key']);ar.index=events.index;arms[arm]=ar
  extra[arm+'_failed']=ar.B8L2.isna();extra[arm+'_incomplete']=~ar.complete_evaluable.fillna(False).astype(bool)
  for c in avail:extra[arm+'_'+c]=pd.to_numeric(ar[c],errors='coerce')
 for c in avail:
  delta=extra['C_'+c]-extra['A_'+c];extra[c+'_CA']=delta;extra[c+'_abs_CA']=delta.abs()
 q=extra['B8L2_CA'];extra['AC_scored']=q.notna()
 extra['Q_improved_CA']=(q>0).astype(float).where(q.notna());extra['Q_loss10_CA']=(q<-10).astype(float).where(q.notna())
 extra['failure_or_loss10_CA']=(extra['C_failed']|(q<-10)).astype(float).where(~extra['A_failed'])
 sigA,sigC=[arms[s]['time_source_count_signature'] for s in ['A','C']]
 knownA,knownC=[arms[s]['all_time_sources_known'].fillna(False).astype(bool) for s in ['A','C']]
 ok=knownA&knownC&sigA.eq(sigC);extra['time_comparable_AC']=ok
 extra['time_source_signature_A']=sigA;extra['time_source_signature_C']=sigC
 ta,tc=[extra[s+'_source_time_total_seconds'] for s in ['A','C']]
 extra['record_time_CA_pct_raw']=100*(tc/ta-1).where(ta>0)
 extra['record_time_CA_pct_source_matched']=extra['record_time_CA_pct_raw'].where(ok)
 geo=[];cache={}
 for e in events.to_dict('records'):
  pair=tuple(sorted([e['A_team_key'],e['C_team_key']]))
  if pair not in cache:cache[pair]=geometry_metrics(rows[pair[0]],rows[pair[1]])
  geo.append({k+'_AC':v for k,v in cache[pair].items()})
 return pd.concat([events.reset_index(drop=True),pd.DataFrame(extra).reset_index(drop=True),pd.DataFrame(geo)],axis=1)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--events',required=True);ap.add_argument('--endpoints',required=True);ap.add_argument('--pools',nargs='+',required=True)
 ap.add_argument('--target-conditions',required=True);ap.add_argument('--out',required=True);ap.add_argument('--partial',action='store_true');a=ap.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);events=pd.read_csv(a.events,low_memory=False)
 pools={p['pool_id']:p for fn in a.pools for p in json.loads(Path(fn).read_text())['images']};targets=pd.read_csv(a.target_conditions).set_index('pool_id')
 done=[];pending=[];start=time.monotonic()
 for pid,g in events.groupby('pool_id',sort=True):
  g=g.reset_index(drop=True);dest=out/'metric_shards'/(pid+'.csv.gz')
  if dest.exists():
   d=pd.read_csv(dest,low_memory=False);assert list(d.event_id)==list(g.event_id);done.append(d);continue
  src=Path(a.endpoints)/'pools'/pid
  if not (src/'CHECKS.json').exists():pending.append(pid);continue
  needed=set(g.A_team_key)|set(g.C_team_key);rows={}
  for p in sorted(src.glob('part_*.jsonl.gz')):
   with gzip.open(p,'rt',encoding='utf-8-sig') as f:
    for line in f:
     r=json.loads(line)
     if r['team_key'] in needed:rows[r['team_key']]=r
  assert set(rows)==needed
  d=compute(g,rows,pools[pid])
  for c in ['official_difficulty','scope','geometric_challenge','structural_condition','ref_turn5','ref_H','ref_short_edges','legal_targets_in_image_condition']:
   d[c]=targets.at[pid,c]
  save(dest,d);done.append(d);jsave(out/'PROGRESS.json',dict(pools=len(done),events=sum(map(len,done)),pending=pending,seconds=time.monotonic()-start))
 if done:save(out/'EVENT_METRICS.csv.gz',pd.concat(done,ignore_index=True))
 receipt=dict(registered_events=len(events),measured_events=sum(map(len,done)),pending_pools=pending,pools=len(done),complete=not pending,
  events_sha256=hashlib.sha256(Path(a.events).read_bytes()).hexdigest(),design='direct_AC_no_same_class_B',same_vs_cross_amplitude_estimable=False,
  new_fusions=0,new_scoring=0,classification_adjustments=0,source_matched_time='same known time-source record-count vector',seconds=time.monotonic()-start)
 jsave(out/'MEASUREMENT_RECEIPT.json',receipt);print(json.dumps(receipt),flush=True)
 if pending and not a.partial:raise RuntimeError(f'{len(pending)} pools pending; completed measurements retained')
if __name__=='__main__':main()
