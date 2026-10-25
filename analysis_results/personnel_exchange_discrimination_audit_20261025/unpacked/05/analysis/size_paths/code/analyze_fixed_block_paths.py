#!/usr/bin/env python3
"""Fixed XYZ, m7 background-growth analysis; uses saved metrics, no fusion.

Prepare the outcome-free cohort plan with --prepare. Run without --prepare
after results/size_paths/EVENT_METRICS.csv.gz is complete.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,os
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
EPS=1e-9
SCALARS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
 'height_mean_ratio','nodes','floor_turn5_n','floor_redundant5_n','floor_short_edge_03_n','floor_short_edge_05_n',
 'floor_area_camera_h2','height_mean_h','height_sd_h','centroid_x_h','centroid_z_h','ref_node_recall_5','ref_node_recall_9',
 'ref_edge_recall_5','ref_edge_recall_9','reference_node_shortfall','top_y_mean_px','bottom_y_mean_px',
 'source_time_total_seconds','target_time_total_seconds','matched_ref_top_abs_deg','matched_ref_bottom_abs_deg',
 'matched_ref_horizontal_abs_deg','matched_ref_pair_fraction','boundary_loss','direction_loss','height_loss',
 'B8_direction_block','B8_floor_block','B8_global_height_block','B8_height_block','B8_local_height_block','D10_direction_block']
GEOMETRY=['geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance','geometry_pair_angle',
 'geometry_top_angle','geometry_bottom_angle','geometry_unmatched_pairs','geometry_same_pair_count']
META=['event_id','path_id','parent_anchor_id','pool_id','image','building','difficulty','method','phase','n','m',
 'source_class','target_class','background_target_n','background_source_n','background_unknown_n',
 'entrant_worker','entrant_class','nominal_minimum_support','nominal_threshold_change']
COHORTS={'all_available':None,'fixed_capacity_n20':20,'fixed_capacity_n21':21}

def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def save_csv(d,p):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);b=d.to_csv(index=False).encode('utf-8-sig')
 if str(p).endswith('.gz'):b=gzip.compress(b,compresslevel=5,mtime=0)
 t=p.with_name(p.name+'.partial');t.write_bytes(b);os.replace(t,p)
def save_json(d,p):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.partial');t.write_text(json.dumps(clean(d),ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def truth(series):
 return series.astype(str).str.lower().map({'true':1.,'false':0.,'1':1.,'0':0.,'1.0':1.,'0.0':0.})
def num(series):return pd.to_numeric(series,errors='coerce')

def validate_design(design,paths,links):
 assert not design.event_id.duplicated().any()
 assert design.m.eq(7).all() and paths.parent_m.eq(7).all()
 assert design.groupby('path_id')[['X','Y','Z','original_D3']].nunique().eq(1).all().all()
 assert design.groupby('path_id').n.apply(lambda s:sorted(s)==list(range(10,int(s.max())+1))).all()
 assert set(design.path_id)==set(paths.path_id)
 assert links.delta_n.eq(1).all() and links.delta_m.eq(0).all()
 assert len(links)==len(design)-len(paths)
 assert set(links.event_id)<=set(design.event_id) and set(links.previous_event_id)<=set(design.event_id)

def attach_cohorts(frame,paths):
 maximum=paths.set_index('path_id').max_n
 parts=[]
 for cohort,capacity in COHORTS.items():
  d=frame.copy()
  if capacity is not None:d=d[d.path_id.map(maximum).ge(capacity)&d.n.le(capacity)]
  d['cohort']=cohort;parts.append(d)
 return pd.concat(parts,ignore_index=True)

def prepare(design_dir,out):
 design=pd.read_csv(design_dir/'EVENTS_EXACT.csv.gz',low_memory=False)
 paths=pd.read_csv(design_dir/'ANCHOR_PATHS.csv.gz');links=pd.read_csv(design_dir/'PAIR_LINKS.csv.gz')
 validate_design(design,paths,links)
 d=attach_cohorts(design,paths)
 coverage=d.groupby(['cohort','method','phase','n'],dropna=False).agg(events=('event_id','nunique'),paths=('path_id','nunique'),images=('pool_id','nunique'),buildings=('building','nunique')).reset_index()
 save_csv(coverage,out/'PLANNED_COHORT_COVERAGE.csv')
 save_json(dict(stage='analysis_code_prepared',registered_events=len(design),paths=len(paths),transitions=len(links),
   cohorts=COHORTS,cohort_rule='Capacity chosen from design max_n, never from successful scores. Fixed-n20 cohort is shown only through n20; fixed-n21 through n21.',
   unit='Each exact fixed-XYZ path contributes once at each n; paths averaged within image; images and buildings reported separately.',
   amplitude='within=abs(B-A); cross=(abs(C-A)+abs(C-B))/2, jointly evaluable triples for amplitude.',
   signed='BA, CA and CB are separate pairwise changes; C(n)-C(10) and B(n)-B(10) are separately retained.',
   net_identity='[C(n)-B(n)]-[C(10)-B(10)] = [C(n)-C(10)]-[B(n)-B(10)]; a net advantage change is not C itself improving.',
   step='The same one common-background person enters all three arms; n increases by1, m stays7.',
   threshold='ceil(n/2) increase vs unchanged is descriptive, and also shown by exact n; parity/entrant/background changes are not a pure-threshold experiment.',
   missing='Actual fusion failures retained; unmeasured events are not failures; metric-specific valid paths/images/buildings.',
   time='Inventory recorded source seconds; adding a common person adds the same known time to all three teams. Absolute CA/CB seconds should remain fixed, percentages can dilute.',
   numerical_sign_tolerance=EPS,large_Q_loss_points=10,
   source_design_sha256=sha(design_dir/'EVENTS_EXACT.csv.gz'),fusion_run=False),out/'ANALYSIS_PLAN.json')
 return design,paths,links

def derived_frames(e,paths,links):
 base=e[e.n.eq(10)].set_index('path_id');assert not base.index.duplicated().any()
 reference=base.reindex(e.path_id);reference.index=e.index
 baseline=e[META].copy();steps=links.copy()
 byid=e.set_index('event_id');current=byid.reindex(steps.event_id);previous=byid.reindex(steps.previous_event_id)
 current.index=steps.index;previous.index=steps.index
 # Copy exact context from the current registered event, never infer roles from outputs.
 for c in ['image','source_class','target_class','background_target_n','background_source_n','background_unknown_n','nominal_minimum_support']:
  if c in current:steps[c]=current[c].to_numpy()
 steps['entrant_role']=np.select([steps.entrant_class.eq(steps.source_class),steps.entrant_class.eq(steps.target_class),steps.entrant_class.eq('unknown')],['source','target','unknown'],default='other')
 steps['threshold_group']=np.where(steps.nominal_threshold_change.gt(0),'increased','unchanged')
 curve_values=[];delta_values=[];availability=[]
 for metric in SCALARS:
  available=all(arm+'_'+metric in e for arm in 'ABC')
  availability.append(dict(metric=metric,available=available,kind='scalar'))
  if not available:continue
  for arm in 'ABC':
   c=arm+'_'+metric;e[c]=num(e[c]);curve_values.append(c)
   name=arm+'_change_'+metric;baseline[name]=e[c]-num(reference[c]);steps[name]=num(current[c])-num(previous[c]);delta_values.append(name)
  for contrast in ['BA','CA','CB','within','cross','gap']:
   c=metric+'_'+contrast
   if c not in e:continue
   e[c]=num(e[c]);curve_values.append(c)
   name=contrast+'_change_'+metric;baseline[name]=e[c]-num(reference[c]);steps[name]=num(current[c])-num(previous[c]);delta_values.append(name)
  # Show direct C/B motion beside net advantage change, never substitute one.
  if 'CB_change_'+metric in baseline:
   for frame in [baseline,steps]:
    residual=frame['CB_change_'+metric]-(frame['C_change_'+metric]-frame['B_change_'+metric])
    finite=residual.dropna()
    assert (finite.abs().max() < 1e-6) if len(finite) else True
   # Also provide identically supported means for the decomposition. The plain
   # arm changes retain all their own valid pairs; these joint fields require
   # B and C to score at both ends of the same path comparison.
   for frame in [baseline,steps]:
    good=frame[['B_change_'+metric,'C_change_'+metric,'CB_change_'+metric]].notna().all(axis=1)
    for term in ['B','C','CB']:
     name='joint_BC_'+term+'_change_'+metric
     frame[name]=frame[term+'_change_'+metric].where(good)
     delta_values.append(name)
 for metric in GEOMETRY:
  available=metric+'_within' in e
  availability.append(dict(metric=metric,available=available,kind='actual_between_team_geometry'))
  for contrast in ['AB','AC','BC','within','cross','gap']:
   c=metric+'_'+contrast
   if c not in e:continue
   e[c]=num(e[c]);curve_values.append(c)
   name=contrast+'_change_'+metric;baseline[name]=e[c]-num(reference[c]);steps[name]=num(current[c])-num(previous[c]);delta_values.append(name)
 for arm in 'ABC':
  c=arm+'_failed';e[c]=truth(e[c]);curve_values.append(c)
  if arm+'_incomplete' in e:e[arm+'_incomplete']=truth(e[arm+'_incomplete']);curve_values.append(arm+'_incomplete')
  for frame,cur,prev in [(baseline,e,reference),(steps,current,previous)]:
   cf=truth(cur[c]) if cur[c].dtype!=float else cur[c];pf=truth(prev[c]) if prev[c].dtype!=float else prev[c]
   good=cf.notna()&pf.notna()
   for name,mask in [('new_failure',cf.eq(1)&pf.eq(0)),('recovered',cf.eq(0)&pf.eq(1)),('both_failed',cf.eq(1)&pf.eq(1)),('both_scored',cf.eq(0)&pf.eq(0))]:
    field=arm+'_'+name;frame[field]=mask.astype(float).where(good)
    if field not in delta_values:delta_values.append(field)
   q=frame[arm+'_change_B8L2']
   for field,value in [(arm+'_Q_gain',q.gt(EPS)),(arm+'_Q_loss10',q.lt(-10)),(arm+'_Q_gain10',q.gt(10))]:
    frame[field]=value.astype(float).where(q.notna())
    if field not in delta_values:delta_values.append(field)
   name=arm+'_new_failure_or_loss10_given_previously_scored'
   frame[name]=np.where(pf.eq(0),np.where(cf.eq(1),1.,np.where(cf.eq(0)&q.notna(),q.lt(-10).astype(float),np.nan)),np.nan)
   if name not in delta_values:delta_values.append(name)
 for c in ['ABC_scored','C_loss10_CA','C_loss10_CB','C_improved_CA','C_improved_CB','C_failure_or_loss10_CA','C_failure_or_loss10_CB','record_time_CA_pct','record_time_CB_pct']:
  if c in e:
   e[c]=truth(e[c]) if c=='ABC_scored' else num(e[c]);curve_values.append(c)
 for contrast in ['BA','CA','CB']:
  q=e['B8L2_'+contrast]
  name='Q_'+contrast+'_positive';e[name]=q.gt(EPS).astype(float).where(q.notna());curve_values.append(name)
  for frame,cur,prev in [(baseline,e,reference),(steps,current,previous)]:
   c='B8L2_'+contrast;a=num(cur[c]);b=num(prev[c]);good=a.notna()&b.notna()
   for tag,mask in [('positive_to_negative',b.gt(EPS)&a.lt(-EPS)),('negative_to_positive',b.lt(-EPS)&a.gt(EPS))]:
    field=contrast+'_'+tag;frame[field]=mask.astype(float).where(good)
    if field not in delta_values:delta_values.append(field)
 for metric in ['B8L2','D10','geometry_bev_distance','geometry_top_angle','geometry_bottom_angle']:
  g=metric+'_gap'
  if g in e:
   name=metric+'_cross_larger';e[name]=e[g].gt(EPS).astype(float).where(e[g].notna());curve_values.append(name)
 return e,baseline,steps,list(dict.fromkeys(curve_values)),list(dict.fromkeys(delta_values)),pd.DataFrame(availability)

def aggregate(frame,values,out,prefix,axis='n'):
 """Exact metric denominators: paths -> images -> buildings, no fake zeros."""
 keys=['cohort','method','phase','pool_id','image','building','difficulty',axis]
 g=frame.groupby(keys,dropna=False)
 means=g[values].mean().reset_index();counts=g[values].count().reset_index()
 meta=g.agg(path_values=('path_id','size'),paths=('path_id','nunique')).reset_index()
 means=means.merge(meta,on=keys,validate='one_to_one')
 save_csv(means,out/(prefix+'_BY_IMAGE.csv.gz'));save_csv(counts,out/(prefix+'_BY_IMAGE_VALID_PATH_COUNTS.csv.gz'))
 bkeys=['cohort','method','phase','building','difficulty',axis]
 building=means.groupby(bkeys,dropna=False)[values].mean().reset_index();save_csv(building,out/(prefix+'_BY_BUILDING.csv.gz'))
 summaries=[]
 for (cohort,method,position),gg in means.groupby(['cohort','method',axis],dropna=False):
  cc=counts[(counts.cohort==cohort)&(counts.method==method)&counts[axis].eq(position)]
  for phase in ['ALL_PHASES']+sorted(gg.phase.unique()):
   pp=gg if phase=='ALL_PHASES' else gg[gg.phase.eq(phase)]
   pc=cc if phase=='ALL_PHASES' else cc[cc.phase.eq(phase)]
   for difficulty in ['ALL']+sorted(pp.difficulty.unique()):
    z=pp if difficulty=='ALL' else pp[pp.difficulty.eq(difficulty)]
    zc=pc if difficulty=='ALL' else pc[pc.difficulty.eq(difficulty)]
    if z.empty:continue
    building_values=z.groupby('building')[values].mean()
    x=z[values];bx=building_values
    table=pd.DataFrame(dict(metric=values,image_equal=x.mean().to_numpy(),building_equal=bx.mean().to_numpy(),
      valid_images=x.notna().sum().to_numpy(),valid_buildings=bx.notna().sum().to_numpy(),
      valid_path_values=zc[values].sum().to_numpy(),image_median=x.median().to_numpy(),image_q10=x.quantile(.1).to_numpy(),image_q90=x.quantile(.9).to_numpy(),
      image_sd=x.std().to_numpy(),positive_images=x.gt(EPS).sum().to_numpy(),negative_images=x.lt(-EPS).sum().to_numpy(),
      positive_buildings=bx.gt(EPS).sum().to_numpy(),negative_buildings=bx.lt(-EPS).sum().to_numpy()))
    table['cohort']=cohort;table['method']=method;table[axis]=position;table['phase']=phase;table['difficulty']=difficulty
    table['registered_images']=len(z);table['registered_buildings']=z.building.nunique();table['registered_path_values']=int(z.path_values.sum())
    table['positive_image_fraction']=table.positive_images/table.valid_images.replace(0,np.nan)
    table['positive_building_fraction']=table.positive_buildings/table.valid_buildings.replace(0,np.nan)
    summaries.append(table)
 summary=pd.concat(summaries,ignore_index=True);save_csv(summary,out/(prefix+'_SUMMARY.csv.gz'))
 return means,summary

def condition_table(summary,baseline_summary,out):
 keys=['cohort','phase','method','difficulty','n']
 keep=['B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB','B8L2_BA','D10_CA','D10_CB','D10_gap',
   'C_B8L2','C_D10','C_IoU3D100','C_iou_2d','C_nodes','C_floor_turn5_n','C_matched_ref_top_abs_deg','C_matched_ref_bottom_abs_deg',
   'C_failed','A_failed','B_failed','C_failure_or_loss10_CA','C_failure_or_loss10_CB',
   'geometry_bev_distance_within','geometry_bev_distance_cross','geometry_bev_distance_gap',
   'geometry_top_angle_gap','geometry_bottom_angle_gap','B8L2_cross_larger','Q_CA_positive','Q_CB_positive',
   'source_time_total_seconds_CA','source_time_total_seconds_CB','record_time_CA_pct','record_time_CB_pct']
 d=summary[summary.metric.isin(keep)]
 wide=d.pivot(index=keys,columns='metric',values='image_equal').reset_index();wide.columns.name=None
 for metric in ['B8L2_within','B8L2_gap','B8L2_CA','B8L2_CB','C_failed']:
  q=d[d.metric.eq(metric)][keys+['valid_images','valid_buildings','positive_images','positive_buildings','registered_path_values']]
  q=q.rename(columns={c:metric+'__'+c for c in q if c not in keys});wide=wide.merge(q,on=keys,how='left',validate='one_to_one')
 if 'B8L2_within' in wide:wide['B8L2_cross_within_ratio']=wide.B8L2_cross/wide.B8L2_within.where(wide.B8L2_within.abs()>EPS)
 if 'geometry_bev_distance_within' in wide:wide['BEV_cross_within_ratio']=wide.geometry_bev_distance_cross/wide.geometry_bev_distance_within.where(wide.geometry_bev_distance_within.abs()>EPS)
 bkeep=['A_change_B8L2','B_change_B8L2','C_change_B8L2','CB_change_B8L2','CA_change_B8L2','within_change_B8L2','cross_change_B8L2','gap_change_B8L2',
   'C_change_nodes','C_change_floor_turn5_n','C_new_failure_or_loss10_given_previously_scored','CB_positive_to_negative']
 b=baseline_summary[baseline_summary.metric.isin(bkeep)].pivot(index=keys,columns='metric',values='image_equal').add_prefix('from_n10__').reset_index();b.columns.name=None
 wide=wide.merge(b,on=keys,how='left',validate='one_to_one');wide['m']=7;wide['replacement_fraction']=7/wide.n;wide['nominal_minimum_support']=np.ceil(wide.n/2).astype(int)
 save_csv(wide,out/'SCALE_CONDITION_COMPARISON.csv')

def time_additivity(e,baseline,steps,out):
 rows=[]
 for path,g in e.groupby('path_id'):
  row=dict(path_id=path,method=g.method.iloc[0],phase=g.phase.iloc[0],pool_id=g.pool_id.iloc[0],building=g.building.iloc[0],difficulty=g.difficulty.iloc[0],available_n=len(g))
  b=g[g.n.eq(10)].iloc[0]
  for contrast in ['CA','CB']:
   c='source_time_total_seconds_'+contrast
   if c in g:
    x=num(g[c]);ref=b[c];diff=(x-ref).abs();row[contrast+'_time_valid_n']=int(x.notna().sum());row[contrast+'_max_absolute_seconds_change_from_n10']=diff.max()
  st=steps[steps.path_id.eq(path)]
  if all(x+'_change_source_time_total_seconds' in st for x in 'ABC'):
   v=st[[x+'_change_source_time_total_seconds' for x in 'ABC']].dropna()
   row['joint_time_steps']=len(v);row['max_between_arm_added_seconds_disagreement']=(v.max(axis=1)-v.min(axis=1)).max()
  rows.append(row)
 save_csv(pd.DataFrame(rows),out/'TIME_ADDITIVITY_CHECK.csv')

def plots(summary,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 s=summary[(summary.cohort=='fixed_capacity_n21')&(summary.phase=='ALL_PHASES')&(summary.difficulty=='ALL')]
 methods=sorted(s.method.unique())
 if not methods:return
 fig,axes=plt.subplots(len(methods),3,figsize=(15,4*len(methods)),squeeze=False)
 panels=[(['B8L2_within','B8L2_cross'],['Same-class change','Cross-class change'],'Absolute Q change'),
         (['B8L2_CA','B8L2_CB'],['C - A','C - B'],'Signed Q change'),
         (['A_B8L2','B_B8L2','C_B8L2'],['A original','B same-class','C cross-class'],'Actual fused Q')]
 for row,method in enumerate(methods):
  for col,(metrics,names,title) in enumerate(panels):
   ax=axes[row,col]
   for metric,name in zip(metrics,names):
    q=s[(s.method==method)&(s.metric==metric)].sort_values('n');ax.plot(q.n,q.image_equal,marker='o',ms=3,label=name)
   ax.set_title(method+'\n'+title);ax.set_xlabel('Team size n (m = 7 fixed)');ax.grid(alpha=.25);ax.legend(fontsize=8)
 fig.suptitle('Fixed XYZ; fixed cohort with n21 capacity; equal image means',fontsize=14);fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(out/'FIXED_N21_Q_CURVES.png',dpi=180);fig.savefig(out/'FIXED_N21_Q_CURVES.svg');plt.close(fig)

def main(a):
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True);dd=Path(a.design);design,paths,links=prepare(dd,out)
 if a.prepare:
  print('Analysis code and outcome-free cohort plan saved; no result analysis or fusion run.');return
 metrics=Path(a.metrics)
 if not metrics.exists():raise FileNotFoundError(f'Metrics not available: {metrics}; use --prepare while fusion is pending.')
 measured=pd.read_csv(metrics,low_memory=False);assert not measured.event_id.duplicated().any()
 missing=set(design.event_id)-set(measured.event_id);extra=set(measured.event_id)-set(design.event_id)
 save_csv(design[design.event_id.isin(missing)],out/'UNMEASURED_REGISTERED_EVENTS.csv.gz')
 save_json(dict(registered_events=len(design),measured_events=len(set(design.event_id)&set(measured.event_id)),missing_events=len(missing),unexpected_events=len(extra),complete=not missing,metrics_path=str(metrics),metrics_sha256=sha(metrics)),out/'READINESS.json')
 if missing and not a.allow_partial:raise RuntimeError(f'{len(missing)} registered events have no metrics; they are not failures. Complete measurement or explicitly use --allow-partial.')
 overlap=[c for c in design if c in measured and c!='event_id']
 check=design[['event_id','A_team_key','B_team_key','C_team_key']].merge(measured[['event_id','A_team_key','B_team_key','C_team_key']],on='event_id',suffixes=('_registered','_measured'),validate='one_to_one')
 for arm in 'ABC':assert check[arm+'_team_key_registered'].eq(check[arm+'_team_key_measured']).all()
 e=design.merge(measured.drop(columns=overlap),on='event_id',how='left',validate='one_to_one')
 # A missing measured event retains missing failure flags; never convert to failure.
 e,baseline,steps,curve_values,delta_values,availability=derived_frames(e,paths,links)
 save_csv(availability,out/'METRIC_AVAILABILITY.csv');save_csv(baseline,out/'PATH_BASELINE_CHANGES.csv.gz');save_csv(steps,out/'PATH_STEP_CHANGES.csv.gz')
 save_csv(e[META+curve_values].copy(),out/'PATH_EVENT_MEASURES.csv.gz')
 curve=attach_cohorts(e,paths);base=attach_cohorts(baseline,paths);step=attach_cohorts(steps,paths)
 _,cs=aggregate(curve,curve_values,out,'CURVE');print('Saved per-n curves',flush=True)
 _,bs=aggregate(base,delta_values,out,'FROM_N10');print('Saved paired changes from n10',flush=True)
 _,ss=aggregate(step,delta_values,out,'STEP');print('Saved adjacent-n changes',flush=True)
 condition_table(cs,bs,out);time_additivity(e,baseline,steps,out)
 # Collapse steps within path before pooling threshold groups, so longer paths
 # do not become extra independent participants in this descriptive contrast.
 gkeys=['cohort','method','phase','path_id','pool_id','image','building','difficulty','threshold_group']
 th=step.groupby(gkeys,dropna=False)[delta_values].mean().reset_index();th['n']=th.threshold_group
 save_csv(th,out/'THRESHOLD_GROUP_BY_PATH.csv.gz');aggregate(th,delta_values,out,'THRESHOLD_GROUP',axis='threshold_group')
 rolekeys=gkeys+['entrant_role'];rr=step.groupby(rolekeys,dropna=False)[delta_values].mean().reset_index();rr['threshold_entrant']=rr.threshold_group+'__'+rr.entrant_role;rr['n']=rr.threshold_entrant
 aggregate(rr,delta_values,out,'THRESHOLD_ENTRANT_ROLE',axis='threshold_entrant')
 if not a.no_plots:plots(cs,out)
 receipt=dict(status='complete' if not missing else 'explicit_partial',registered_events=len(design),measured_events=len(design)-len(missing),paths=len(paths),transitions=len(links),
  matched_membership_verified=True,metric_count=len(curve_values),delta_metric_count=len(delta_values),
  fixed_cohort='n20-capable paths truncated at n20; n21-capable paths truncated at n21; membership fixed from design capacity, not success.',
  sign_and_amplitude='Signed BA/CA/CB and within/cross magnitude kept separate; per-arm movement and net movement both retained.',
  no_net_as_C_improvement=True,failures='Per-arm flags and newly failed/recovered/large-loss transitions; no missing Q replaced by zero.',
  aggregation='Exact paths equal within image. Images equal and building means reported separately. Threshold pooling first averages eligible steps within each path.',
  threshold_caution='Step threshold increase is inseparable here from background entry and n; exact-n and entrant-role views preserved.',
  time='Recorded inventory active seconds, not newly timed production. Absolute CA/CB time cancellation and equal added time verified descriptively.',
  no_fusion_run=True,source_metrics_sha256=sha(metrics),code_sha256=sha(__file__))
 save_json(receipt,out/'ANALYSIS_RECEIPT.json')
 manifest=[]
 for p in sorted(out.rglob('*')):
  if p.is_file() and p.name!='FILE_MANIFEST.csv' and not p.name.endswith('_LOG.txt') and '__pycache__' not in str(p):manifest.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
 save_csv(pd.DataFrame(manifest),out/'FILE_MANIFEST.csv');print(json.dumps(clean(receipt),ensure_ascii=False,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--design',default=str(ROOT/'design/size_paths'));p.add_argument('--metrics',default=str(ROOT/'results/size_paths/EVENT_METRICS.csv.gz'));p.add_argument('--output',default=str(ROOT/'analysis/size_paths'));p.add_argument('--prepare',action='store_true');p.add_argument('--allow-partial',action='store_true');p.add_argument('--no-plots',action='store_true');main(p.parse_args())
