"""Temporal provenance audit and descriptive within-image/worker workload checks.

Submission-created timestamps are recovered from the exact original export and
annotation identity. Event fragments never replace formal active duration.
Bout boundaries are exploratory operational definitions, not physiological states.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, sys, urllib.parse, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import t as tdist
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis import personalized_simulator_v2 as s

def fetch(path,out):
 assert not Path(path).is_absolute() and '..' not in Path(path).parts
 p=out/'temporal_sources'/path;p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():
  url='https://raw.githubusercontent.com/'+s.REPO+'/'+s.INPUT_REF+'/'+urllib.parse.quote(path,safe='/')
  with urllib.request.urlopen(url,timeout=90)as r:p.write_bytes(r.read())
 return p

def iter_tasks(o):
 if isinstance(o,list):
  for v in o:yield from iter_tasks(v)
 elif isinstance(o,dict):
  if isinstance(o.get('annotations'),list) and 'id' in o:yield o
  elif isinstance(o.get('completions'),list) and 'id' in o:yield dict(o,annotations=o['completions'])
  else:
   for key in ('tasks','data','results'):
    if isinstance(o.get(key),(list,dict)):yield from iter_tasks(o[key])

def wid(x):
 if isinstance(x,dict):x=x.get('id')
 try:return f'W{int(str(x).removeprefix("W")):03d}'
 except (TypeError,ValueError):return ''

def boolv(x):return str(x).lower() in ('true','1')

def cluster_regression(data,y,xname):
 dd=data.dropna(subset=[y,xname]).copy()
 if len(dd)<40 or dd.worker_id.nunique()<5:return dict(status='insufficient')
 keys=pd.get_dummies(dd[['worker_id','image_id','stage']].astype(str),drop_first=True,dtype=float)
 nuisance=np.c_[np.ones(len(dd)),keys.to_numpy(),np.log1p(dd.previous_observed_responses.to_numpy())]
 x=dd[xname].to_numpy(float);yy=dd[y].to_numpy(float)
 xr=x-nuisance@np.linalg.lstsq(nuisance,x,rcond=1e-9)[0]
 yr=yy-nuisance@np.linalg.lstsq(nuisance,yy,rcond=1e-9)[0]
 if xr@xr<1e-8:return dict(status='unidentifiable_after_fixed_effects',rows=len(dd))
 beta=float(xr@yr/(xr@xr));res=yr-beta*xr;scores=xr*res
 W=dd.worker_id.nunique();I=dd.image_id.nunique()
 def variance(k):
  sums=pd.Series(scores,index=np.arange(len(dd))).groupby(np.asarray(k)).sum().to_numpy();G=len(sums)
  return float(np.sum(sums*sums)*G/max(1,G-1)/(xr@xr)**2)
 vw=variance(dd.worker_id);vi=variance(dd.image_id);vboth=variance(dd.worker_id.astype(str)+'|'+dd.image_id.astype(str))
 var=vw+vi-vboth
 if var<0:return dict(status='negative_two_way_covariance',rows=len(dd),coefficient=beta,worker_se=np.sqrt(vw))
 se=float(np.sqrt(var));crit=float(tdist.ppf(.975,min(W,I)-1))
 return dict(status='descriptive_not_causal',rows=len(dd),workers=W,images=I,coefficient=beta,se=se,ci_low=beta-crit*se,ci_high=beta+crit*se,residual_predictor_sd=float(np.std(xr)),design_rank=int(np.linalg.matrix_rank(nuisance)),design_columns=nuisance.shape[1])

def run(out):
 paths=s.get_inputs(out);pools,models,raw=s.load_data(paths,out);valid={c:(g,j)for g in pools for j,c in enumerate(g['ids'])};checks={r['canonical_annotation_id']:r for r in s.readj(paths['time_checks'])}
 evidence_path=fetch('analysis_results/annotation_research_prework_20260905_v2/evidence/record_evidence.csv',out)
 cols=['canonical_annotation_id','project_id','runtime_task_id','worker_id','stage']
 ev=pd.read_csv(evidence_path,dtype=str,usecols=lambda c:c in cols).fillna('');ev=ev.set_index('canonical_annotation_id');assert set(ev.index)=={r['canonical_annotation_id']for r in raw}
 events=pd.DataFrame(s.readj(paths['events']));events['event_ms']=pd.to_numeric(events['timestamp'],errors='coerce')
 events['worker_normalized']=events['annotator_id'].map(wid)
 eventindex={k:g for k,g in events.groupby(['project_id','runtime_task_id','worker_normalized'])}
 exports={};failures=[];rows=[]
 for r in raw:
  if r['worker_id'] in s.EXCLUDED:continue
  cid=r['canonical_annotation_id'];p=r.get('raw_export_path','');v=r.get('raw_annotation_version_id','').split('|');a={};status='not_found'
  if p and len(v)>=3:
   if p not in exports:
    try:
     src=fetch(p,out);obj=json.loads(src.read_text(encoding='utf-8-sig'));lookup={}
     for task in iter_tasks(obj):
      for an in task['annotations']:
       if isinstance(an,dict):lookup[(str(task['id']),wid(an.get('completed_by',an.get('annotator'))),str(an.get('id')))]=an
     exports[p]=lookup
    except Exception as e:exports[p]={};failures.append(dict(path=p,error=str(e)))
   tid,worker,aid=v[-3:];a=exports[p].get((tid,wid(worker),aid),{});status='matched_raw_identity'if a else 'annotation_identity_not_matched'
  e=ev.loc[cid];key=(str(e.get('project_id','')),str(e.get('runtime_task_id','')),r['worker_id']);eg=eventindex.get(key)
  row=dict(canonical_annotation_id=cid,image_id=r['image_id'],worker_id=r['worker_id'],condition='oos_geometry'if r['raw_condition']=='oos'else r['raw_condition'],stage=r.get('stage',e.get('stage','')),raw_source=p,raw_version_id=r.get('raw_annotation_version_id',''),raw_created_at=a.get('created_at'),raw_updated_at=a.get('updated_at'),timestamp_status=status,geometric_valid=cid in valid)
  expected=checks[cid].get('verified_owner_source_files',[])
  if eg is not None:
   eg=eg[eg.source_path.isin(expected)] if expected else eg.iloc[:0]
  row['owner_source_matched_events']=0 if eg is None else len(eg)
  row['first_verified_event_ms']=float(eg.event_ms.min()) if eg is not None and len(eg)else np.nan
  row['last_verified_event_ms']=float(eg.event_ms.max()) if eg is not None and len(eg)else np.nan
  row['source_sessions']=eg.session_id.nunique() if eg is not None else 0
  usable=checks[cid].get('speed_usable',False);x=(r.get('evidence')or{}).get('active_time_seconds')
  row['active_seconds']=float(x)if usable and x not in ('',None)else np.nan
  if cid in valid:
   g,j=valid[cid];other=[q for q in range(len(g['ids']))if q!=j]
   row['point_pairs']=len(g['points'][j])//2
   row['log_points']=math_log(row['point_pairs'])
   row['peer_disagreement']=float(np.minimum(g['dm'][j,other],1).mean()) if other else np.nan
   pp=g['points'][j];row['top_mean']=float(pp[pp[:,1]<256,1].mean()) if np.any(pp[:,1]<256)else np.nan
   row['bottom_mean']=float(pp[pp[:,1]>256,1].mean())if np.any(pp[:,1]>256)else np.nan
  rows.append(row)
 df=pd.DataFrame(rows);df['created_utc']=pd.to_datetime(df.raw_created_at,utc=True,errors='coerce',format='mixed');df['updated_utc']=pd.to_datetime(df.raw_updated_at,utc=True,errors='coerce',format='mixed')
 df['log_active']=np.log(df.active_seconds.where(df.active_seconds>0));df.to_csv(out/'temporal_response_provenance.csv.gz',index=False)
 summary=dict(rows=len(df),raw_created_found=int(df.created_utc.notna().sum()),raw_identity_matches=int(df.timestamp_status.eq('matched_raw_identity').sum()),owner_event_matches=int(df.owner_source_matched_events.gt(0).sum()),formal_active_rows=int(df.active_seconds.notna().sum()),raw_exports=len(exports),failed_exports=failures,classification='not a direct fatigue measurement')
 s.savej(out/'temporal_provenance_summary.json',summary);print('TEMPORAL_PROVENANCE',json.dumps(summary,ensure_ascii=False),flush=True)
 good=df[df.created_utc.notna()].sort_values(['worker_id','created_utc','canonical_annotation_id']).copy()
 good['previous_observed_responses']=good.groupby('worker_id').cumcount()
 allb=[];reg=[]
 for mins in (15,30,60):
  g=good.copy();gap=g.groupby('worker_id').created_utc.diff().dt.total_seconds();new=g.worker_id.ne(g.worker_id.shift())|gap.gt(mins*60)|g.stage.ne(g.stage.shift())
  g['observed_bout']=new.cumsum();g['bout_position']=g.groupby('observed_bout').cumcount();g['bout_size']=g.groupby('observed_bout').canonical_annotation_id.transform('size');g['previous_active_missing']=g.active_seconds.isna().astype(int).groupby(g.observed_bout).cumsum()-g.active_seconds.isna().astype(int)
  prior=g.active_seconds.fillna(0).groupby(g.observed_bout).cumsum()-g.active_seconds.fillna(0);g['prior_active_hours']=prior.where(g.previous_active_missing==0)/3600;g['prior_ten_tasks']=g.bout_position/10;g['bout_gap_minutes']=mins
  g.to_csv(out/f'observed_bouts_{mins}min.csv.gz',index=False)
  for w,ww in g.groupby('worker_id'):
   allb.append(dict(worker_id=w,gap_minutes=mins,observed_responses=len(ww),dated_days=ww.created_utc.dt.date.nunique(),bouts=ww.observed_bout.nunique(),max_bout_tasks=int(ww.bout_size.max()),max_bout_observed_prior_active_hours=float(ww.prior_active_hours.max())if ww.prior_active_hours.notna().any()else None))
  for arm in ('manual','semi','oos_geometry'):
   a=g[g.condition.eq(arm)&g.geometric_valid&g.bout_size.ge(3)]
   for y in ('peer_disagreement','log_points','log_active','top_mean','bottom_mean'):
    for x in ('prior_ten_tasks','prior_active_hours'):
     if y in a:reg.append(dict(condition=arm,gap_minutes=mins,outcome=y,predictor=x,**cluster_regression(a,y,x)))
 pd.DataFrame(allb).to_csv(out/'worker_observed_bouts.csv',index=False);pd.DataFrame(reg).to_csv(out/'workload_associations.csv',index=False)
 print('WORKER_COVERAGE\n'+pd.read_csv(out/'worker_coverage.csv').to_string(index=False),flush=True)
 print('WORKLOAD_ASSOCIATIONS\n'+pd.DataFrame(reg).to_string(index=False),flush=True)
 sources=[]
 for p in (out/'temporal_sources').rglob('*'):
  if p.is_file():sources.append(dict(path=str(p.relative_to(out/'temporal_sources')),ref=s.INPUT_REF,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
 s.savej(out/'temporal_source_manifest.json',sources)

def math_log(v):return float(np.log(v))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);run(ap.parse_args().output)
