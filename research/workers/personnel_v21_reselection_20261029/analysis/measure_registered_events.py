"""Measure exact target-separated ABC events from saved v2.1 endpoints.
Retains the original symmetric cross-vs-within definition, adds explicit CA/CB,
pairwise denominators, source-stratified time, and full geometric contrasts.
No scoring, class fitting or fusion occurs here. Each finished pool is saved.
"""
from __future__ import annotations
import os
for _v in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[_v]='1'
import argparse,collections,gzip,hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from legacy_geometry_diagnostics import geometry_metrics,refdiagnostic

METRICS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
'height_mean_ratio','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2',
'height_mean_h','height_min_h','height_max_h','centroid_x_h','centroid_z_h','ref_node_recall_5','ref_node_recall_9',
'ref_edge_recall_5','ref_edge_recall_9','reference_node_shortfall','reference_node_excess','top_y_mean_px','bottom_y_mean_px',
'matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg','matched_ref_pair_fraction',
'boundary_loss','direction_loss','global_height_loss','local_height_loss','height_loss','floor_WQ','WQ','WQ_no_D',
'WQ_no_B','WQ_no_H','height_drop_current','diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05',
'source_time_total_seconds','recorded_time_total_seconds','minimum_support','identity_groups_n','unselected_groups_n',
'half_vote_nodes','selected_support_min','target_individual_B8L2_mean','target_individual_B8L2_min']

def save(path,df):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);b=df.to_csv(index=False).encode('utf-8-sig')
 if p.name.endswith('.gz'):b=gzip.compress(b,compresslevel=4,mtime=0)
 tmp=p.with_name(p.name+'.writing')
 with tmp.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 tmp.replace(p)
def jsave(path,obj):
 p=Path(path);b=json.dumps(obj,ensure_ascii=False,indent=2).encode();tmp=p.with_name(p.name+'.writing')
 with tmp.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 tmp.replace(p)
def time_signature(r):
 x=r.get('record_time_by_kind_json')
 if isinstance(x,str):x=json.loads(x)
 if not x:return '',False
 sig=tuple(sorted((k,v.get('n',0)) for k,v in x.items()))
 good=all(v.get('known_n')==v.get('n') and v.get('total_seconds') is not None and v.get('total_seconds')>=0 for v in x.values())
 return json.dumps(sig,separators=(',',':')),good

def measure(ev,rows,pool):
 for r in rows.values():
  refdiagnostic(r,pool)
  if r.get('nodes') is not None:
   r['reference_node_shortfall']=max(0,len(pool['reference']['points_1024x512'])//2-r['nodes'])
   r['reference_node_excess']=max(0,r['nodes']-len(pool['reference']['points_1024x512'])//2)
  r['time_source_count_signature'],r['all_time_sources_known']=time_signature(r)
 scal=pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in rows.values()]).set_index('team_key')
 avail=[c for c in METRICS if c in scal];values={};arms={}
 for arm in 'ABC':
  ar=scal.reindex(ev[arm+'_team_key']);ar.index=ev.index;arms[arm]=ar
  values[arm+'_failed']=ar.B8L2.isna();values[arm+'_incomplete']=~ar.complete_evaluable.fillna(False).astype(bool)
  for c in avail:values[arm+'_'+c]=pd.to_numeric(ar[c],errors='coerce')
 for c in avail:
  a,b,z=[values[arm+'_'+c] for arm in 'ABC'];valid=a.notna()&b.notna()&z.notna();within=(b-a).abs().where(valid)
  ca=z-a;cb=z-b;cross=(ca.abs()+cb.abs()).div(2).where(valid)
  values.update({c+'_within':within,c+'_cross':cross,c+'_gap':cross-within,c+'_AC_absolute':ca.abs().where(valid),c+'_AC_gap':ca.abs().where(valid)-within,
   c+'_BA':b-a,c+'_CA':ca,c+'_CB':cb})
 values['ABC_scored']=~(values['A_failed']|values['B_failed']|values['C_failed'])
 source_sig=[arms[arm]['time_source_count_signature'] for arm in 'ABC']
 time_known=[arms[arm]['all_time_sources_known'].fillna(False).astype(bool) for arm in 'ABC']
 values['time_comparable_ABC']=time_known[0]&time_known[1]&time_known[2]&source_sig[0].eq(source_sig[1])&source_sig[0].eq(source_sig[2])
 values['time_source_signature_A']=source_sig[0];values['time_source_signature_B']=source_sig[1];values['time_source_signature_C']=source_sig[2]
 for comp,base in [('BA','A'),('CA','A'),('CB','B')]:
  top='B' if comp=='BA' else 'C';d=values['B8L2_'+comp]
  values['Q_improved_'+comp]=(d>0).astype(float).where(d.notna());values['Q_loss10_'+comp]=(d<-10).astype(float).where(d.notna())
  values['failure_or_loss10_'+comp]=(values[top+'_failed']|(d<-10)).astype(float).where(~values[base+'_failed'])
  if 'source_time_total_seconds' in avail:
   ta,tb=values[top+'_source_time_total_seconds'],values[base+'_source_time_total_seconds']
   values['record_time_'+comp+'_pct_raw']=100*(ta/tb-1).where(tb>0)
   ok=time_known['ABC'.index(top)]&time_known['ABC'.index(base)]&source_sig['ABC'.index(top)].eq(source_sig['ABC'.index(base)])
   values['record_time_'+comp+'_pct_source_matched']=values['record_time_'+comp+'_pct_raw'].where(ok)
  if 'recorded_time_total_seconds' in avail:
   ta,tb=values[top+'_recorded_time_total_seconds'],values[base+'_recorded_time_total_seconds']
   values['record_time_'+comp+'_pct_single_source']=100*(ta/tb-1).where(tb>0)
 geo=[];paircache={}
 for e in ev.to_dict('records'):
  pp={}
  for a,b in [('A','B'),('A','C'),('B','C')]:
   k=tuple(sorted([e[a+'_team_key'],e[b+'_team_key']]))
   if k not in paircache:paircache[k]=geometry_metrics(rows[k[0]],rows[k[1]])
   pp[a+b]=paircache[k]
  out={}
  for m in set(pp['AB'])|set(pp['AC'])|set(pp['BC']):
   ab,ac,bc=[pp[k].get(m,np.nan) for k in ['AB','AC','BC']]
   out.update({m+'_AB':ab,m+'_AC':ac,m+'_BC':bc})
   if all(np.isfinite(v) for v in [ab,ac,bc]):out.update({m+'_within':ab,m+'_cross':(ac+bc)/2,m+'_gap':(ac+bc)/2-ab,m+'_AC_gap':ac-ab})
  geo.append(out)
 return pd.concat([ev.reset_index(drop=True),pd.DataFrame(values).reset_index(drop=True),pd.DataFrame(geo)],axis=1)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--events',required=True);ap.add_argument('--endpoints',required=True);ap.add_argument('--pools',nargs='+',required=True)
 ap.add_argument('--target-conditions',required=True);ap.add_argument('--out',required=True);ap.add_argument('--partial',action='store_true');args=ap.parse_args()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True);ev=pd.read_csv(args.events,low_memory=False);pools={p['pool_id']:p for fn in args.pools for p in json.loads(Path(fn).read_text())['images']}
 targets=pd.read_csv(args.target_conditions).set_index('pool_id');done=[];pending=[];start=time.monotonic();endpointseen=set()
 for pid,g in ev.groupby('pool_id',sort=True):
  path=out/'metric_shards'/(pid+'.csv.gz');g=g.reset_index(drop=True)
  if path.exists():
   d=pd.read_csv(path,low_memory=False);assert list(d.event_id)==list(g.event_id);done.append(d);continue
  root=Path(args.endpoints)/'pools'/pid
  if not (root/'CHECKS.json').exists():pending.append(pid);continue
  needed=set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key);rows={}
  for p in sorted(root.glob('part_*.jsonl.gz')):
   with gzip.open(p,'rt',encoding='utf-8-sig') as f:
    for l in f:
     r=json.loads(l)
     if r['team_key'] in needed:rows[r['team_key']]=r
  assert needed==set(rows),pid
  d=measure(g,rows,pools[pid])
  for c in ['official_difficulty','scope','geometric_challenge','structural_condition','ref_turn5','ref_H','ref_short_edges','legal_targets_in_image_condition']:
   d[c]=targets.at[pid,c]
  d['data_release']='v2.1';save(path,d);done.append(d);endpointseen.update(needed)
  jsave(out/'PROGRESS.json',dict(pools=len(done),events=sum(map(len,done)),pending=pending,seconds=time.monotonic()-start));print(pid,len(d),flush=True)
 if done:
  allrows=pd.concat(done,ignore_index=True);save(out/'EVENT_METRICS.csv.gz',allrows)
  jsave(out/'MEASUREMENT_RECEIPT.json',dict(registered_events=len(ev),measured_events=len(allrows),pools=len(done),pending_pools=pending,complete=not pending,
    events_sha256=hashlib.sha256(Path(args.events).read_bytes()).hexdigest(),new_fusions=0,new_scoring=0,classification_adjustments=0,
    symmetric_cross_definition='(|C-A|+|C-B|)/2 on all-three-valid metric-specific support',within_definition='|B-A| on same support',
    source_matched_time='all logged values known; same per-source record-count vector in compared arms; raw sum retained separately',seconds=time.monotonic()-start))
 if pending and not args.partial:raise RuntimeError(f'{len(pending)} pools not complete; completed pool shards retained')
if __name__=='__main__':main()
