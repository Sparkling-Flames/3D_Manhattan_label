"""Targeted independent rebuilding of neutral-0 summaries and whole-class modes.

Uses frozen registry+links and saved metric shards. The parent aggregation code
is not imported. Python dictionaries and math.fsum implement event -> pool ->
image -> building means. No fusion, scoring or eligibility reassessment.
"""
from pathlib import Path
from collections import defaultdict
import csv,gzip,hashlib,json,math
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parents[1]
METRICS=['B8L2_CA','D10_CA']
TARGETS=[('TARGET_DSTRUCT_K3',20,7,2,3),('OPPJOINT_K3',20,10,1,2),('V21_DSTRUCT_RAW3_K3',23,12,1,2)]
GROUP=['analysis_view','scope','condition','layer','method','role_direction','n_condition','m_condition']
def truth(x):return str(x).lower() in ['true','1','1.0']
def num(x):
 try:v=float(x)
 except (ValueError,TypeError):return math.nan
 return v if math.isfinite(v) else math.nan
def mean(x):
 y=[v for v in x if math.isfinite(v)]
 return math.fsum(y)/len(y) if y else math.nan
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
 return h.hexdigest()
def save(rows,name):
 d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows);p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with (gzip.open(p,'wt',encoding='utf-8-sig',newline='') if p.name.endswith('.gz') else open(p,'w',encoding='utf-8-sig',newline='')) as f:d.to_csv(f,index=False)
def group_values(row,fields):return tuple(row[k] for k in fields)

def aggregate(events,fields):
 bypool=defaultdict(list)
 for e in events:bypool[group_values(e,fields)+tuple(e[k] for k in ['pool_id','image','building'])].append(e)
 pools=[]
 for key,es in bypool.items():
  assert len(es)==len({e['event_id'] for e in es})
  meta=dict(zip(fields+['pool_id','image','building'],key))
  for metric in METRICS:
   vals=[num(e[metric]) for e in es];ok=[v for v in vals if math.isfinite(v)]
   pools.append(dict(meta,metric=metric,registered_pairs=len(es),valid_pairs=len(ok),mean_change=mean(ok),mean_absolute=mean([abs(x) for x in ok]),
    actual_n_A_min=min(e['n'] for e in es),actual_n_A_max=max(e['n'] for e in es),actual_n_C_min=min(e['n'] for e in es),actual_n_C_max=max(e['n'] for e in es),
    actual_m_X_min=min(e['m'] for e in es),actual_m_X_max=max(e['m'] for e in es)))
 byimage=defaultdict(list)
 for r in pools:byimage[group_values(r,fields)+tuple(r[k] for k in ['metric','image','building'])].append(r)
 images=[]
 for key,ps in byimage.items():
  images.append(dict(zip(fields+['metric','image','building'],key),registered_pools=len(ps),valid_pools=sum(p['valid_pairs']>0 for p in ps),
   registered_pairs=sum(p['registered_pairs'] for p in ps),valid_pairs=sum(p['valid_pairs'] for p in ps),
   mean_change=mean([p['mean_change'] for p in ps]),mean_absolute=mean([p['mean_absolute'] for p in ps])))
 bybuilding=defaultdict(list)
 for r in images:bybuilding[group_values(r,fields)+(r['metric'],r['building'])].append(r)
 buildings=[]
 for key,ims in bybuilding.items():buildings.append(dict(zip(fields+['metric','building'],key),registered_images=len(ims),valid_images=sum(math.isfinite(i['mean_change']) for i in ims),
   mean_change=mean([i['mean_change'] for i in ims]),mean_absolute=mean([i['mean_absolute'] for i in ims])))
 byg=defaultdict(list);pg=defaultdict(list);bg=defaultdict(list)
 for r in images:byg[group_values(r,fields)+(r['metric'],)].append(r)
 for r in pools:pg[group_values(r,fields)+(r['metric'],)].append(r)
 for r in buildings:bg[group_values(r,fields)+(r['metric'],)].append(r)
 result=[]
 for key,ims in byg.items():
  ps=pg[key];bs=bg[key];values=[i['mean_change'] for i in ims if math.isfinite(i['mean_change'])];bv=[b['mean_change'] for b in bs if math.isfinite(b['mean_change'])]
  z=dict(zip(fields+['metric'],key));z.update(registered_pools=len(ps),registered_images=len(ims),registered_buildings=len(bs),registered_pairs=sum(p['registered_pairs'] for p in ps),
   valid_pairs=sum(p['valid_pairs'] for p in ps),valid_pools=sum(p['valid_pairs']>0 for p in ps),valid_images=len(values),valid_buildings=len(bv),
   image_mean=mean(values),image_median=float(np.median(values)) if values else math.nan,
   image_p10=float(np.quantile(values,.1)) if values else math.nan,image_p90=float(np.quantile(values,.9)) if values else math.nan,
   image_balanced_mean_absolute=mean([i['mean_absolute'] for i in ims]),
   positive_images=sum(x>1e-9 for x in values),negative_images=sum(x<-1e-9 for x in values),tied_images=sum(abs(x)<=1e-9 for x in values),
   positive_image_fraction=sum(x>1e-9 for x in values)/len(values) if values else math.nan,
   building_balanced_mean=mean(bv),positive_buildings=sum(x>1e-9 for x in bv),negative_buildings=sum(x<-1e-9 for x in bv),tied_buildings=sum(abs(x)<=1e-9 for x in bv))
  for field in ['actual_n_A_min','actual_n_C_min','actual_m_X_min']:z[field]=min(p[field] for p in ps)
  for field in ['actual_n_A_max','actual_n_C_max','actual_m_X_max']:z[field]=max(p[field] for p in ps)
  result.append(z)
 return result,pools,images,buildings

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 regpath=BASE/'stage01_registered/AC_EVENTS.csv.gz';linkpath=BASE/'stage01_registered/DESIGN_LINKS.csv.gz'
 core=['event_id','physical_pair_id','pool_id','image','building','scope','condition','layer','method','source_class','target_class',
       'source_role_rank','target_role_rank','n','m','D_n','whole_source','whole_target','source_class_available_n','target_class_available_n',
       'A_team_key','C_team_key','D_workers','X_workers','Z_workers','equal_team_size','pure_cross_class_blocks']
 reg=pd.read_csv(regpath,usecols=core,low_memory=False)
 reg=reg[reg.condition.eq('manual')&reg.layer.eq('ordinary_manual')&reg.equal_team_size.map(truth)&reg.pure_cross_class_blocks.map(truth)].copy()
 reg['role_direction']=reg.source_role_rank.astype(int).astype(str)+'->'+reg.target_role_rank.astype(int).astype(str)
 links=pd.read_csv(linkpath,usecols=['event_id','design_family','background_profile','at_pool_frontier','input_orientation_sign'],low_memory=False)
 links=links[links.background_profile.eq('neutral_members_0')&links.design_family.isin(['A_equal_AC','B_equal_whole_class'])]
 alinks=links[links.design_family.eq('A_equal_AC')].drop_duplicates('event_id');blinks=links[links.design_family.eq('B_equal_whole_class')].drop_duplicates('event_id')
 assert links.input_orientation_sign.eq(1).all(),'Neutral A/B inputs are expected to share canonical lower-role -> higher-role orientation'
 pooln=pd.read_csv(BASE/'stage01_capacity/POOL_METHOD_CAPACITY.csv.gz',usecols=['pool_id','pool_n']).drop_duplicates().set_index('pool_id').pool_n.to_dict()
 byid=reg.set_index('event_id');selected_A=[];selected_B=[];sources=[]
 aset=set(alinks.event_id)
 for method,n,m,s,t in TARGETS:
  rr=reg[reg.event_id.isin(aset)&reg.scope.eq('primary')&reg.method.eq(method)&reg.n.eq(n)&reg.m.eq(m)&reg.source_role_rank.eq(s)&reg.target_role_rank.eq(t)]
  for r in rr.to_dict('records'):selected_A.append(dict(r,analysis_view='A_fixed_n',n_condition=str(n),m_condition=str(m)))
 for link in blinks.itertuples():
  if link.event_id not in byid.index:continue
  r=byid.loc[link.event_id].to_dict();r['event_id']=link.event_id
  assert truth(r['whole_source'])==(int(r['m'])==int(r['source_class_available_n']))
  assert truth(r['whole_target'])==(int(r['m'])==int(r['target_class_available_n']))
  ws,wt=truth(r['whole_source']),truth(r['whole_target']);assert ws or wt
  mode='both_whole_equal' if ws and wt else 'whole_source_out_only' if ws else 'whole_target_in_only'
  r['whole_definition']=mode;r['pure_n_equals_m']=int(r['D_n'])==0
  actual_frontier=int(r['n'])+int(r['m'])==int(pooln[r['pool_id']]);assert actual_frontier==truth(link.at_pool_frontier)
  if int(r['n'])==20:
   assert int(r['D_n'])>0
   selected_B.append(dict(r,analysis_view='whole_equal_fixed_n_all_m',n_condition='20',m_condition='whole_class_actual_m'))
  if actual_frontier:
   view='whole_equal_pool_frontier'+('_pure_class' if int(r['D_n'])==0 else '')
   selected_B.append(dict(r,analysis_view=view,n_condition='N_minus_m',m_condition='whole_class_actual_m'))
 selected=selected_A+selected_B;needed=defaultdict(set)
 for r in selected:needed[r['pool_id']].add(r['event_id'])
 data={}
 columns=['event_id','physical_pair_id','A_team_key','C_team_key','A_B8L2','C_B8L2','A_D10','C_D10','B8L2_CA','D10_CA','A_output_state','C_output_state']
 for pid,ids in sorted(needed.items()):
  p=BASE/'stage04_metrics/metric_shards'/(pid+'.csv.gz');d=pd.read_csv(p,usecols=columns,low_memory=False);d=d[d.event_id.isin(ids)]
  assert set(d.event_id)==ids and not d.event_id.duplicated().any()
  for r in d.to_dict('records'):
   for metric in ['B8L2','D10']:
    a,c,v=[num(r[x]) for x in ['A_'+metric,'C_'+metric,metric+'_CA']]
    assert math.isfinite(v)==(math.isfinite(a) and math.isfinite(c))
    if math.isfinite(v):assert abs(v-(c-a))<1e-9
   data[r['event_id']]=r
  sources.append(dict(pool_id=pid,path=str(p.relative_to(BASE)),sha256=sha(p),selected_events=len(ids)))
 for r in selected:
  d=data[r['event_id']]
  for field in ['physical_pair_id','A_team_key','C_team_key']:assert r[field]==d[field]
  r.update({k:d[k] for k in columns if k not in ['event_id','physical_pair_id','A_team_key','C_team_key']})
 save(selected_A,'REPRESENTATIVE_EXACT_SELECTED_EVENT_METRICS.csv.gz');save(selected_B,'WHOLE_DEFINITION_SELECTED_EVENT_METRICS.csv.gz')
 a,ap,ai,ab=aggregate(selected_A,GROUP)
 split,bp,bi,bb=aggregate(selected_B,GROUP+['whole_definition','pure_n_equals_m'])
 merged,_,_,_=aggregate(selected_B,GROUP)
 save(a,'INDEPENDENT_REPRESENTATIVE_SUMMARY.csv');save(ai,'INDEPENDENT_REPRESENTATIVE_IMAGE_METRICS.csv')
 save(split,'WHOLE_DEFINITION_SPLIT_SUMMARY.csv');save(bp,'WHOLE_DEFINITION_POOL_METRICS.csv.gz');save(bi,'WHOLE_DEFINITION_IMAGE_METRICS.csv');save(bb,'WHOLE_DEFINITION_BUILDING_METRICS.csv')
 summarypath=BASE/'stage05_main/CONDITION_METRIC_SUMMARY.csv.gz'
 wanted_keys={group_values(r,GROUP)+(r['metric'],) for r in a+merged};parent={}
 for chunk in pd.read_csv(summarypath,chunksize=25000,low_memory=False,dtype={'n_condition':str,'m_condition':str}):
  for r in chunk[chunk.metric.isin(METRICS)&chunk.analysis_view.isin(['A_fixed_n','whole_equal_fixed_n_all_m','whole_equal_pool_frontier','whole_equal_pool_frontier_pure_class'])].to_dict('records'):
   key=group_values(r,GROUP)+(r['metric'],)
   if key in wanted_keys:assert key not in parent;parent[key]=r
 checked_fields=['registered_pools','registered_images','registered_buildings','registered_pairs','valid_pairs','valid_pools','valid_images','valid_buildings',
  'image_mean','image_median','image_p10','image_p90','image_balanced_mean_absolute','positive_images','negative_images','tied_images','positive_image_fraction',
  'building_balanced_mean','positive_buildings','negative_buildings','actual_n_A_min','actual_n_A_max','actual_n_C_min','actual_n_C_max','actual_m_X_min','actual_m_X_max']
 comparisons=[]
 for kind,records in [('representative_A',a),('recombined_B_all_whole_modes',merged)]:
  for r in records:
   key=group_values(r,GROUP)+(r['metric'],);assert key in parent,key;pr=parent[key]
   for field in checked_fields:
    x,y=num(r[field]),num(pr[field]);ok=(not math.isfinite(x) and not math.isfinite(y)) or (math.isfinite(x) and math.isfinite(y) and abs(x-y)<1e-10)
    comparisons.append(dict(check_kind=kind,**dict(zip(GROUP+['metric'],key)),field=field,independent_value=x,parent_value=y,difference=x-y,passed=ok))
 save(comparisons,'PARENT_SUMMARY_PARITY_BY_FIELD.csv')
 checks=pd.DataFrame(comparisons);assert checks.passed.all(),checks[~checks.passed].to_dict('records')
 # Explain the known estimand difference with the broader capacity funnel.
 funnel=pd.read_csv(BASE/'stage05_funnel_bridge/CAPACITY_REGISTRATION_EXECUTION_EVALUABILITY_DIRECTION_FUNNEL.csv.gz')
 explanations=[]
 for r in a:
  direction='/3->'.join(r['role_direction'].split('->'))+'/3'
  f=funnel[(funnel.scope==r['scope'])&(funnel.method==r['method'])&(funnel.n==int(r['n_condition']))&(funnel.m==int(r['m_condition']))&(funnel.role_direction==direction)&(funnel.metric==r['metric'].replace('_CA',''))]
  assert len(f)==1;f=f.iloc[0]
  explanations.append(dict(method=r['method'],role_direction=r['role_direction'],n=r['n_condition'],m=r['m_condition'],metric=r['metric'],
   neutral_A_registered_pairs=r['registered_pairs'],neutral_A_valid_pairs=r['valid_pairs'],neutral_A_mean=r['image_mean'],neutral_A_mean_absolute=r['image_balanced_mean_absolute'],neutral_A_positive_images=r['positive_images'],neutral_A_negative_images=r['negative_images'],
   broad_funnel_registered_pairs=f.registered_events,broad_funnel_valid_pairs=f.metric_valid_events,broad_funnel_mean=f.mean_change,broad_funnel_mean_absolute=f.mean_absolute_change_over_pools,
   broad_funnel_positive_pools=f.positive_pools,broad_funnel_negative_pools=f.negative_pools,
   mean_difference_neutral_minus_broad=r['image_mean']-f.mean_change,
   explanation='Main A uses only A_equal_AC + neutral_members_0, equal pools/images. Broad funnel includes all registered equal pure-class events and background strategies/families, averages backgrounds within exact XZ then blocks; differences are expected estimand changes, not conflicting arithmetic.'))
 save(explanations,'NEUTRAL_A_VS_BROAD_FUNNEL_EXPLANATION.csv')
 receipt=dict(status='passed',source_selection='frozen registry links, no target-outcome selection',independent_implementation='No import of main analysis; Python dictionaries and math.fsum implement event -> pool -> image -> building balancing',
  neutral_profile='neutral_members_0',representative_conditions=len(TARGETS),representative_metric_rows=len(a),representative_selected_unique_events=len({r['event_id'] for r in selected_A}),
  whole_definition_selected_view_events=len(selected_B),whole_definition_selected_unique_events=len({r['event_id'] for r in selected_B}),whole_definition_summary_rows=len(split),
  whole_modes=['whole_source_out_only','whole_target_in_only','both_whole_equal'],whole_modes_relative_to_canonical_direction=True,
  pure_n_equals_m_separate=True,metrics=METRICS,missing_Q_zero_filled=False,main_comparison_field_rows=len(comparisons),
  maximum_absolute_difference=float(checks.difference.abs().max()),all_checked_fields_passed=True,
  whole_merged_definitions_reproduce_parent_without_overwriting=True,original_funnel_files_unchanged=True,new_teams=0,new_fusions=0,new_scores=0,
  inputs=[dict(path=str(p.relative_to(BASE)),sha256=sha(p)) for p in [regpath,linkpath,summarypath]],metric_sources=sources)
 (OUT/'INDEPENDENT_REBUILD_RECEIPT.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False))
 print(json.dumps({k:v for k,v in receipt.items() if k not in ['inputs','metric_sources']},indent=2,ensure_ascii=False));print(pd.DataFrame(a)[['method','role_direction','n_condition','m_condition','metric','registered_pairs','valid_pairs','valid_images','valid_buildings','image_mean','image_balanced_mean_absolute','positive_images','negative_images']].to_string(index=False))

if __name__=='__main__':main()
