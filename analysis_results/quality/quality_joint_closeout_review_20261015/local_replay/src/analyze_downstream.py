"""Same-response/reference comparisons and finite-pool downstream sensitivity.
All rankings are descriptive, not restored worker eligibility or a causal routing
trial. Target buildings are excluded from selection features. No fusion is run.
"""
from quality import *
import pandas as pd
from scipy.stats import spearmanr, kendalltau
from itertools import combinations
from collections import defaultdict,Counter

def get_frame():
 d=read(ROOT/'results/all_scores.json');gate=read(ROOT/'results/recovered_admission_3152.json')['records']
 pairs={tuple((r['record_id'],r['reference_id'],r['score_kind'])):r for r in d['records']}
 flat=[];ledger=[]
 for r in gate:
  c=d['canonical'][r['record_id']];p=pairs.get(tuple(c.get('pair_key',[])));x=dict(r,score_status=c['status'],reference_binding=c.get('binding'),same_target_unconfirmed=c.get('same_target_quality_not_certified',False),route_uncertainty=c.get('uncertainty'),scope_diagnostic_reason=c.get('reason'),reference_id=p['reference_id'] if p else None)
  if p:
   x.update(p['metrics']);x.update(p['scores']);x['IoU3D100']=p['IoU3D100'];x['calculation']=p['calculation'];x['use_layers']=p['use_layers']
  else:x.update(WQ=None,current=None,IoU3D100=None,floor_WQ=None)
  ledger.append(x)
 for p in d['records']:
  x={k:v for k,v in p.items() if k not in ['metrics','scores']};x.update(p.get('metrics') or {});x.update(p.get('scores') or {});flat.append(x)
 def csv_export(rows,name):
  df=pd.DataFrame(rows)
  for k in df:
   if df[k].apply(lambda v:isinstance(v,(list,dict))).any():df[k]=df[k].apply(lambda v:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v)
  df.to_csv(ROOT/'results'/name,index=False,encoding='utf-8-sig')
 csv_export(ledger,'ALL_3152_LEDGER.csv');csv_export(flat,'ALL_REFERENCE_PAIRS.csv')
 return pd.DataFrame(ledger),pd.DataFrame(flat),d

def describe(v):
 v=np.asarray(v,dtype=float);v=v[np.isfinite(v)]
 return dict(n=len(v),min=float(v.min()),p10=float(np.quantile(v,.1)),median=float(np.median(v)),mean=float(v.mean()),p90=float(np.quantile(v,.9)),max=float(v.max())) if len(v) else dict(n=0)

def corr(a,b):
 if len(a)<3 or len(set(a))<2 or len(set(b))<2:return None
 return float(spearmanr(a,b).statistic)

def compare(f,names=('WQ','current','IoU3D100','WQ_no_D','WQ_no_B','WQ_no_H')):
 groups=list(f.groupby(['image_id','reference_id','condition'],dropna=False));pairs=[];cellstat=[]
 for cell,df in groups:
  # One response per worker per cell after equal-weight duplicate aggregation.
  d=df.groupby('worker_id',sort=True)[list(names)].mean();rids=df.groupby('worker_id')['record_id'].apply(list).to_dict()
  disagree=0;total=0
  for a,b in combinations(d.index,2):
   if np.max(np.abs(d.loc[a].values-d.loc[b].values))<1e-10:continue
   gaps={n:float(d.loc[a,n]-d.loc[b,n]) for n in names}
   rev=gaps['WQ']*gaps['IoU3D100'] < -1e-10;old=gaps['WQ']*gaps['current'] < -1e-10
   pair=dict(image_id=cell[0],reference_id=cell[1],condition=cell[2],building_id=df.iloc[0]['building_id'],image_code=df.iloc[0]['image_code'],A=a,B=b,A_ids=rids[a],B_ids=rids[b],WQ_IoU_reverse=rev,WQ_current_reverse=old,**{'gap_'+k:v for k,v in gaps.items()})
   pairs.append(pair);disagree+=rev;total+=1
  cellstat.append(dict(image_id=cell[0],reference_id=cell[1],condition=cell[2],building_id=df.iloc[0]['building_id'],image_code=df.iloc[0]['image_code'],workers=len(d),pairs=total,reversals=disagree,reverse_rate=disagree/total if total else None,spearman=corr(d.WQ,d.IoU3D100)))
 p=pd.DataFrame(pairs);c=pd.DataFrame(cellstat);valid=c[c.pairs>0]
 rng=np.random.default_rng(141026);ci=None
 # Cluster bootstrap of image-level rates by building. Finite development pool only.
 building_means=valid.groupby('building_id').reverse_rate.mean().to_numpy()
 if len(building_means)>1:
  boot=np.mean(rng.choice(building_means,(4000,len(building_means)),replace=True),axis=1);ci=np.quantile(boot,[.025,.975]).tolist()
 out=dict(records=len(f),workers=f.worker_id.nunique(),images=f.image_id.nunique(),buildings=f.building_id.nunique(),reference_cells=len(groups),same_cell_comparisons=len(p),WQ_IoU_reversals=int(p.WQ_IoU_reverse.sum()) if len(p) else 0,WQ_current_reversals=int(p.WQ_current_reverse.sum()) if len(p) else 0,pooled_spearman_descriptive=corr(f.WQ,f.IoU3D100),equal_image_cell_reverse_rate=float(valid.reverse_rate.mean()),equal_building_reverse_rate=float(building_means.mean()),building_cluster_descriptive_interval=ci,independent_pairs=False,superiority_claimed=False,
  WQ_change=describe(f.WQ-f.current),metrics={n:describe(f[n]) for n in names},large_disagreement_pairs=int(((p.gap_WQ.abs()>=5)&(p.gap_IoU3D100.abs()>=5)&p.WQ_IoU_reverse).sum()),large_gap_5_is_audit_threshold_not_human_effect=True)
 return out,p,c

def workers_and_teams(f):
 names=['WQ','current','IoU3D100'];cells=[]
 for cell,df in f.groupby(['image_id','reference_id','condition']):
  d=df.groupby('worker_id')[names].mean()
  if len(d)<2:continue
  for w,v in d.iterrows():
   row=dict(worker_id=w,image_id=cell[0],reference_id=cell[1],building_id=df.iloc[0]['building_id'],peers=len(d))
   for n in names:row[n]=float(v[n]);row[n+'_centered']=float(v[n]-d[n].mean());row[n+'_percentile']=float(d[n].rank(method='average',pct=True)[w])
   cells.append(row)
 c=pd.DataFrame(cells);means=c.groupby('worker_id')[[n+'_centered' for n in names]].mean();count=c.groupby('worker_id').size();building=c.groupby('worker_id').building_id.nunique()
 raw=f.groupby('worker_id')[names].mean();means['reference_cells']=count;means['buildings']=building
 for n in names:
  means[n+'_raw_mean']=raw[n];means[n+'_rank']=means[n+'_centered'].rank(ascending=False,method='min');means[n+'_sign_positive']=means[n+'_centered']>0
 # Do not invent quality grades; relative rank bins used only to show decision sensitivity.
 nworkers=len(means)
 for n in names:means[n+'_relative_third']=means[n+'_rank'].apply(lambda r:'upper_relative_third' if r<=nworkers/3 else 'middle_relative_third' if r<=2*nworkers/3 else 'lower_relative_third')
 la=[]
 for b in sorted(c.building_id.unique()):
  z=c[c.building_id!=b].groupby('worker_id')[[n+'_centered' for n in names]].mean()
  for w,row in z.iterrows():la.append(dict(worker_id=w,excluded_building=b,**{n:float(row[n+'_centered']) for n in names}))
 leave=pd.DataFrame(la)
 for n in names:
  z=leave.groupby('worker_id')[n].agg(['min','max']);means[n+'_leave_building_min']=z['min'];means[n+'_leave_building_max']=z['max']
 # Equal common task panel, not a substitute for whole-population ability.
 ws={w:set(zip(z.image_id,z.reference_id)) for w,z in c.groupby('worker_id')};common=set.intersection(*ws.values());cp=c[c.apply(lambda r:(r.image_id,r.reference_id) in common,axis=1)]
 cm=cp.groupby('worker_id')[[n+'_centered' for n in names]].mean()
 # Target-building-hidden selection among workers who actually answered each held target.
 # This is conditional finite-pool selection, NOT future assignment or fusion prediction.
 teams=[]
 for (im,ref),df in c.groupby(['image_id','reference_id']):
  b=df.iloc[0].building_id;train=c[c.building_id!=b];ag=train.groupby('worker_id')[[n+'_percentile' for n in names]].mean();cnt=train.groupby('worker_id').size();nb=train.groupby('worker_id').building_id.nunique()
  pool=[w for w in df.worker_id if w in ag.index and cnt[w]>=5 and nb[w]>=2]
  if len(pool)<6:continue
  for k in (1,3,5):
   if len(pool)<k+1:continue
   sels={n:sorted(pool,key=lambda w:(-ag.loc[w,n+'_percentile'],w))[:k] for n in names};target=df.set_index('worker_id')
   teams.append(dict(image_id=im,reference_id=ref,building_id=b,k=k,pool=len(pool),selections=sels,IoU_WQ_same_set=set(sels['WQ'])==set(sels['IoU3D100']),current_WQ_same_set=set(sels['WQ'])==set(sels['current']),jaccard=len(set(sels['WQ'])&set(sels['IoU3D100']))/len(set(sels['WQ'])|set(sels['IoU3D100'])),outcomes={select:{ev:float(target.loc[wset,ev].mean()) for ev in names} for select,wset in sels.items()},read_target_scores_for_selection=False))
 tsum={}
 for k in (1,3,5):
  rr=[r for r in teams if r['k']==k];grouped=defaultdict(list)
  for r in rr:grouped[r['building_id']].append(r)
  tsum[str(k)]=dict(targets=len(rr),buildings=len(grouped),changed_sets=sum(not r['IoU_WQ_same_set'] for r in rr),changed_current_sets=sum(not r['current_WQ_same_set'] for r in rr),mean_jaccard=float(np.mean([r['jaccard'] for r in rr])) if rr else None,differences_WQ_selected_minus_IoU_selected={ev:dict(record_weighted=float(np.mean([r['outcomes']['WQ'][ev]-r['outcomes']['IoU3D100'][ev] for r in rr])),building_equal=float(np.mean([np.mean([r['outcomes']['WQ'][ev]-r['outcomes']['IoU3D100'][ev] for r in br]) for br in grouped.values()]))) for ev in names} if rr else {})
 summary=dict(workers=nworkers,usable_cells=len(c),reference_cells=c[['image_id','reference_id']].drop_duplicates().shape[0],all_worker_common_reference_cells=len(common),per_worker_cells=describe(count),centered_rank_spearman_WQ_IoU=corr(means.WQ_centered,means.IoU3D100_centered),centered_rank_spearman_WQ_current=corr(means.WQ_centered,means.current_centered),common_only_rank_spearman_WQ_IoU=corr(cm.WQ_centered,cm.IoU3D100_centered),common_reference_cells=[list(x) for x in sorted(common)],rank_third_changes_WQ_IoU=int((means.WQ_relative_third!=means.IoU3D100_relative_third).sum()),rank_third_changes_WQ_current=int((means.WQ_relative_third!=means.current_relative_third).sum()),sign_changes_WQ_IoU=int((means.WQ_sign_positive!=means.IoU3D100_sign_positive).sum()),largest_rank_change=float((means.WQ_rank-means.IoU3D100_rank).abs().max()),top6_WQ=list(means.sort_values('WQ_rank').head(6).index),top6_IoU=list(means.sort_values('IoU3D100_rank').head(6).index),top6_current=list(means.sort_values('current_rank').head(6).index),formal_worker_classes_changed=False,rank_bins_are_exploratory_not_grades=True,teams=tsum,teams_not_fusion=True)
 means.reset_index().to_csv(ROOT/'results/WORKER_METRIC_SENSITIVITY.csv',index=False,encoding='utf-8-sig');c.to_csv(ROOT/'results/WORKER_CELL_SCORES.csv',index=False,encoding='utf-8-sig');leave.to_csv(ROOT/'results/WORKER_LEAVE_BUILDING.csv',index=False,encoding='utf-8-sig');cm.to_csv(ROOT/'results/WORKER_COMMON_PANEL.csv',encoding='utf-8-sig');dump(ROOT/'results/TEAM_SELECTION_DIAGNOSTIC.json',dict(summary=tsum,records=teams,policy='finite observed pool; train excludes target building; no future assignment or fusion benefit claimed'))
 return summary

def main():
 df,pairs,raw=get_frame();ordinary=df[(df.role=='manual_development_candidate')&(df.score_status=='full')].copy();assert len(ordinary)==962
 summary,comparison,cells=compare(ordinary);comparison.to_csv(ROOT/'results/ORDINARY_PAIRWISE_COMPARISONS.csv',index=False,encoding='utf-8-sig');cells.to_csv(ROOT/'results/ORDINARY_CELL_COMPARISONS.csv',index=False,encoding='utf-8-sig');ordinary.to_csv(ROOT/'results/ORDINARY_962.csv',index=False,encoding='utf-8-sig')
 own=workers_and_teams(ordinary)
 layers={}
 for label,sub in [('ordinary_962',ordinary),('severe_9',df[(df.role=='severe_exception_candidate')&df.WQ.notna()]),('semi_39',df[(df.role=='semi_secondary_candidate')&df.WQ.notna()]),('doorway_125',df[(df.stage=='doorway')&df.WQ.notna()]),('doorway_115_scope_not_flagged',df[(df.score_status=='conditional_full')]),('historical_10',df[df.score_status=='historical_only'])]:
  layers[label]=dict(n=len(sub),images=sub.image_id.nunique(),buildings=sub.building_id.nunique(),WQ=describe(sub.WQ),IoU=describe(sub.IoU3D100),corr=corr(sub.WQ,sub.IoU3D100),WQ_change=describe(sub.WQ-sub.current))
 grouped=[]
 for level in ['image_code','building_id']:
  for code,d in ordinary.groupby(level):grouped.append(dict(level=level,group=code,n=len(d),WQ=float(d.WQ.mean()),current=float(d.current.mean()),IoU3D100=float(d.IoU3D100.mean()),mean_change=float((d.WQ-d.current).mean())))
 pd.DataFrame(grouped).to_csv(ROOT/'results/ORDINARY_GROUP_SUMMARY.csv',index=False,encoding='utf-8-sig')
 vs=pairs[pairs.use_layers.apply(lambda x:any('version_sensitivity' in v for v in x))].copy();vlist=[]
 for rid,rr in vs.groupby('record_id'):
  if rr.reference_id.nunique()!=2:continue
  vlist.append(dict(record_id=rid,image_id=rr.iloc[0].image_id,image_code=rr.iloc[0].image_code,reference_ids=list(rr.reference_id),canonical_status=raw['canonical'][rid]['status'],WQ_spread=float(rr.WQ.max()-rr.WQ.min()),IoU_spread=float(rr.IoU3D100.max()-rr.IoU3D100.min())))
 dump(ROOT/'results/REFERENCE_VERSION_SENSITIVITY.json',dict(records=vlist,summary={n:describe([r[n] for r in vlist]) for n in ['WQ_spread','IoU_spread']},not_best_reference_selection=True))
 result=dict(ordinary=summary,workers=own,layers=layers,coverage=dict(all_records=len(df),canonical_status=dict(Counter(df.score_status)),response_full_scores=int(df.WQ.notna().sum()),response_floor_only=int(((df.WQ.isna())&df.floor_WQ.notna()).sum()),parameters_unchanged=True,version_sensitivity_records=len(vlist)))
 dump(ROOT/'results/COMPARISON_SUMMARY.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
