#!/usr/bin/env python3
"""Direct AC tail analysis, never supplies a fictitious same-class B arm."""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
helper=ROOT/'analysis/size_paths/code/analyze_fixed_block_paths.py'
spec=importlib.util.spec_from_file_location('fixed_paths_analysis',helper);hp=importlib.util.module_from_spec(spec);spec.loader.exec_module(hp)
META=['event_id','path_id','strict_size_path_id','parent_anchor_id','pool_id','image','building','difficulty','method','phase','n','m','pool_n','tail_step',
 'source_class','target_class','background_source_n','background_target_n','entrant_worker','entrant_class','nominal_minimum_support','nominal_threshold_change']

def cohorts(d):
 a=d.copy();a['cohort']='all_fixed_anchors_by_k'
 b=d[d.pool_n.eq(35)].copy();b['cohort']='fixed_pool_N35'
 return pd.concat([a,b],ignore_index=True)

def main(a):
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True);dd=Path(a.design)
 design=pd.read_csv(dd/'EVENTS_EXACT.csv.gz',low_memory=False);paths=pd.read_csv(dd/'ANCHOR_PATHS.csv.gz');links=pd.read_csv(dd/'PAIR_LINKS.csv.gz')
 assert design.groupby('path_id').tail_step.apply(lambda s:sorted(s)==list(range(8))).all()
 assert design.groupby('path_id')[['X','Z']].nunique().eq(1).all().all() and design.m.eq(7).all()
 assert not any(c.startswith('B_') for c in design)
 plan=dict(events=len(design),paths=len(paths),transitions=len(links),design='direct AC only',
  cohorts='All fixed anchors at each k0..7; fixed actual pool N35 at n21..28. Membership from capacity, never from success.',
  primary='Signed C-A and absolute |C-A|, actual A/C outcomes, actual AC geometry, per-arm failures. No same-vs-cross amplitude difference is computed.',
  scale='At each step one original Y7 source-class person enters common D in both arms. X7/Z7 remain fixed; m remains7.',
  support='Path mean within image, image and building means; all registered paths retained even if a fusion fails.',
  source_design_sha256=hp.sha(dd/'EVENTS_EXACT.csv.gz'),fusion_run=False)
 hp.save_json(plan,out/'ANALYSIS_PLAN.json')
 if a.prepare:print(json.dumps(plan,ensure_ascii=False));return
 measured=pd.read_csv(a.metrics,low_memory=False);assert not measured.event_id.duplicated().any()
 missing=set(design.event_id)-set(measured.event_id)
 hp.save_csv(design[design.event_id.isin(missing)],out/'UNMEASURED_EVENTS.csv.gz')
 if missing:raise RuntimeError(f'{len(missing)} AC events lack metrics; not treated as failures.')
 for arm in 'AC':
  check=design[['event_id',arm+'_team_key']].merge(measured[['event_id',arm+'_team_key']],on='event_id',validate='one_to_one',suffixes=('_d','_m'))
  assert check[arm+'_team_key_d'].eq(check[arm+'_team_key_m']).all()
 overlap=[c for c in design if c in measured and c!='event_id'];e=design.merge(measured.drop(columns=overlap),on='event_id',validate='one_to_one')
 values=[];delta_values=[];baseline=e[META].copy();step=links.copy()
 ix=e.set_index('event_id');cur=ix.reindex(step.event_id);prev=ix.reindex(step.previous_event_id);cur.index=step.index;prev.index=step.index
 for c in META:
  if c not in step:step[c]=cur[c].to_numpy()
 base=e[e.tail_step.eq(0)].set_index('path_id');ref=base.reindex(e.path_id);ref.index=e.index
 for metric in hp.SCALARS:
  if not all(arm+'_'+metric in e for arm in 'AC'):continue
  for arm in 'AC':
   c=arm+'_'+metric;e[c]=hp.num(e[c]);values.append(c)
   name=arm+'_change_'+metric;baseline[name]=e[c]-hp.num(ref[c]);step[name]=hp.num(cur[c])-hp.num(prev[c]);delta_values.append(name)
  ca=metric+'_CA';ab=metric+'_abs_CA';e[ca]=e['C_'+metric]-e['A_'+metric];e[ab]=e[ca].abs();values.extend([ca,ab])
  for d,left,right in [(baseline,e,ref),(step,cur,prev)]:
   curr_ca=hp.num(left['C_'+metric])-hp.num(left['A_'+metric]);prev_ca=hp.num(right['C_'+metric])-hp.num(right['A_'+metric])
   d['CA_change_'+metric]=curr_ca-prev_ca;d['abs_CA_change_'+metric]=curr_ca.abs()-prev_ca.abs()
   good=d[['A_change_'+metric,'C_change_'+metric,'CA_change_'+metric]].notna().all(axis=1)
   for term in ['A','C','CA']:d['joint_AC_'+term+'_change_'+metric]=d[term+'_change_'+metric].where(good)
   residual=d['CA_change_'+metric]-(d['C_change_'+metric]-d['A_change_'+metric]);assert residual.dropna().abs().max()<1e-6 if residual.notna().any() else True
  delta_values.extend(['CA_change_'+metric,'abs_CA_change_'+metric]+['joint_AC_'+term+'_change_'+metric for term in ['A','C','CA']])
 for metric in hp.GEOMETRY:
  c=metric+'_AC'
  if c not in e:continue
  e[c]=hp.num(e[c]);values.append(c);name='AC_change_'+metric
  baseline[name]=e[c]-hp.num(ref[c]);step[name]=hp.num(cur[c])-hp.num(prev[c]);delta_values.append(name)
 for arm in 'AC':
  f=arm+'_failed';e[f]=hp.truth(e[f]);values.append(f)
  if arm+'_incomplete' in e:e[arm+'_incomplete']=hp.truth(e[arm+'_incomplete']);values.append(arm+'_incomplete')
  for d,left,right in [(baseline,e,ref),(step,cur,prev)]:
   cf=hp.truth(left[f]);pf=hp.truth(right[f]);ok=cf.notna()&pf.notna();q=d[arm+'_change_B8L2']
   for tag,mask in [('new_failure',cf.eq(1)&pf.eq(0)),('recovered',cf.eq(0)&pf.eq(1)),('both_failed',cf.eq(1)&pf.eq(1)),('both_scored',cf.eq(0)&pf.eq(0))]:d[arm+'_'+tag]=mask.astype(float).where(ok)
   d[arm+'_Q_gain']=q.gt(hp.EPS).astype(float).where(q.notna());d[arm+'_Q_loss10']=q.lt(-10).astype(float).where(q.notna())
   d[arm+'_new_failure_or_loss10_given_previously_scored']=np.where(pf.eq(0),np.where(cf.eq(1),1.,np.where(cf.eq(0)&q.notna(),q.lt(-10).astype(float),np.nan)),np.nan)
  delta_values.extend([arm+'_'+c for c in ['new_failure','recovered','both_failed','both_scored','Q_gain','Q_loss10','new_failure_or_loss10_given_previously_scored']])
 for c in ['AC_scored','C_loss10_CA','C_failure_or_loss10_CA','record_time_CA_pct']:
  if c in e:e[c]=hp.truth(e[c]) if c=='AC_scored' else hp.num(e[c]);values.append(c)
 q=e.B8L2_CA;e['Q_CA_positive']=q.gt(hp.EPS).astype(float).where(q.notna());values.append('Q_CA_positive')
 for d,left,right in [(baseline,e,ref),(step,cur,prev)]:
  x=hp.num(left.C_B8L2)-hp.num(left.A_B8L2);y=hp.num(right.C_B8L2)-hp.num(right.A_B8L2);ok=x.notna()&y.notna()
  d['CA_positive_to_negative']=(y.gt(hp.EPS)&x.lt(-hp.EPS)).astype(float).where(ok);d['CA_negative_to_positive']=(y.lt(-hp.EPS)&x.gt(hp.EPS)).astype(float).where(ok)
 delta_values.extend(['CA_positive_to_negative','CA_negative_to_positive'])
 values=list(dict.fromkeys(values));delta_values=list(dict.fromkeys(delta_values))
 hp.save_csv(e[META+values],out/'PATH_EVENT_MEASURES.csv.gz');hp.save_csv(baseline,out/'FROM_STRICT_TAIL_EXACT.csv.gz');hp.save_csv(step,out/'STEP_EXACT.csv.gz')
 _,curve_summary=hp.aggregate(cohorts(e),values,out,'CURVE_BY_K',axis='tail_step')
 _,base_summary=hp.aggregate(cohorts(baseline),delta_values,out,'FROM_STRICT_TAIL_BY_K',axis='tail_step')
 hp.aggregate(cohorts(step),delta_values,out,'STEP_BY_K',axis='tail_step')
 hp.aggregate(cohorts(e).query("cohort == 'fixed_pool_N35'"),values,out,'FIXED_N35_BY_N',axis='n')
 keys=['cohort','method','phase','difficulty','tail_step']
 keep=['B8L2_CA','B8L2_abs_CA','D10_CA','IoU3D100_CA','iou_2d_CA','nodes_CA','floor_turn5_n_CA','matched_ref_top_abs_deg_CA','matched_ref_bottom_abs_deg_CA',
  'geometry_bev_distance_AC','geometry_top_angle_AC','geometry_bottom_angle_AC','A_B8L2','C_B8L2','A_failed','C_failed','C_failure_or_loss10_CA','Q_CA_positive','source_time_total_seconds_CA','record_time_CA_pct']
 sub=curve_summary[curve_summary.metric.isin(keep)];wide=sub.pivot(index=keys,columns='metric',values='image_equal').reset_index();wide.columns.name=None
 for metric in ['B8L2_CA','C_failed']:
  z=sub[sub.metric.eq(metric)][keys+['valid_images','valid_buildings','positive_images','positive_buildings','valid_path_values']]
  z=z.rename(columns={c:metric+'__'+c for c in z if c not in keys});wide=wide.merge(z,on=keys,validate='one_to_one')
 bk=['A_change_B8L2','C_change_B8L2','CA_change_B8L2','joint_AC_A_change_B8L2','joint_AC_C_change_B8L2','joint_AC_CA_change_B8L2','C_change_nodes','C_new_failure_or_loss10_given_previously_scored']
 z=base_summary[base_summary.metric.isin(bk)].pivot(index=keys,columns='metric',values='image_equal').add_prefix('from_strict_tail__').reset_index();z.columns.name=None
 wide=wide.merge(z,on=keys,validate='one_to_one');hp.save_csv(wide,out/'AC_TAIL_CONDITION_COMPARISON.csv')
 times=[]
 for path,g in e.groupby('path_id'):
  st=step[step.path_id.eq(path)];tm=hp.num(g.source_time_total_seconds_CA)
  valid=st[['A_change_source_time_total_seconds','C_change_source_time_total_seconds']].dropna()
  times.append(dict(path_id=path,valid_times=int(tm.notna().sum()),max_absolute_CA_time_change=(tm-tm.iloc[0]).abs().max(),joint_steps=len(valid),
   max_added_time_disagreement=(valid.C_change_source_time_total_seconds-valid.A_change_source_time_total_seconds).abs().max()))
 hp.save_csv(pd.DataFrame(times),out/'TIME_ADDITIVITY_CHECK.csv')
 receipt=dict(status='complete',events=len(e),paths=len(paths),transitions=len(step),images=e.pool_id.nunique(),buildings=e.building.nunique(),
  no_B_arm=True,no_same_vs_cross_comparison=True,metric_count=len(values),delta_metric_count=len(delta_values),no_fusion_run=True,
  metrics_sha256=hp.sha(a.metrics),code_sha256=hp.sha(__file__),aggregation_helper_sha256=hp.sha(helper))
 hp.save_json(receipt,out/'ANALYSIS_RECEIPT.json')
 hp.save_csv(pd.DataFrame([dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hp.sha(p)) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='FILE_MANIFEST.csv' and not p.name.endswith('_LOG.txt') and '__pycache__' not in str(p)]),out/'FILE_MANIFEST.csv')
 print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--design',default=str(ROOT/'design/large_team_ac_tail'));p.add_argument('--metrics',default=str(ROOT/'results/large_team_ac_tail/EVENT_METRICS.csv.gz'));p.add_argument('--output',default=str(ROOT/'analysis/large_team_ac_tail'));p.add_argument('--prepare',action='store_true');main(p.parse_args())
