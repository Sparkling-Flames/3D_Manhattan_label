"""Current-label conditional analysis of frozen, actual two-view ABC teams.

No new teams, labels, quality scores, references, room facts or fusion calls.
An event is one D/X/Y/Z construction applied to BOTH direct-related views.
Physical duplicates are counted and deduplicated within each current method.
"""
from pathlib import Path
import hashlib,json,gzip
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'source';OUT=ROOT/'stage02_same_room/abc';OUT.mkdir(parents=True,exist_ok=True)
def save(d,n):
 p=OUT/n;t=p.with_name(p.name+'.tmp');d.to_csv(t,index=False,compression={'method':'gzip','compresslevel':3,'mtime':0} if n.endswith('.gz') else None);t.replace(p)
def wcorr(x,y,w):
 ok=np.isfinite(x)&np.isfinite(y)&np.isfinite(w)
 if ok.sum()<3:return np.nan
 x=np.array(x)[ok];y=np.array(y)[ok];w=np.array(w)[ok];w=w/w.sum();x=x-np.sum(w*x);y=y-np.sum(w*y)
 den=np.sqrt(np.sum(w*x*x)*np.sum(w*y*y));return np.sum(w*x*y)/den if den>1e-12 else np.nan
e=pd.read_csv(ROOT/'stage02_same_room/EXISTING_VALID_EVENT_SOURCE.csv.gz',low_memory=False)
a=pd.read_csv(ROOT/'stage02_same_room/VALID_CLASS_RELATION_SOURCE.csv.gz')
roles=pd.read_csv(SRC/'research/workers/personnel_v21_reselection_20261029/classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz').set_index(['method','heldout_building','class_id'])
d=e.merge(a[['event_id','final_method','source_labels','target_labels']],on='event_id',validate='one_to_many')
for side in ['source','target']:
 rr=roles.reindex(pd.MultiIndex.from_arrays([d.final_method,d.building,d[side+'_labels']]))
 d[side+'_semantic']=rr.semantic_training_role.to_numpy()
 tr=rr.hard_turn_rank_asc.to_numpy();fr=rr.response_hard_turn_rank_asc.to_numpy()
 d[side+'_rank']=np.where(d.final_method.str.startswith('RFUSE'),fr,tr)
 assert np.isfinite(d[side+'_rank']).all()
d['role_direction']=d.source_rank.astype(int).astype(str)+'→'+d.target_rank.astype(int).astype(str)
d['analysis_scope']=np.select([d.ordinary_comparable,d.layer_a.str.contains('doorway')|d.layer_b.str.contains('doorway')],['ordinary_comparable','doorway_or_mixed_scope'],default='ordinary_other_scope')
d['physical_event_key']=[hashlib.sha256((str(p)+'||'+str(aa)+'||'+str(bb)+'||'+str(cc)).encode()).hexdigest()[:24] for p,aa,bb,cc in zip(d.pair_key,d.A_members,d.B_members,d.C_members)]
ov=d.groupby(['final_method','physical_event_key'],as_index=False).agg(event_rows=('event_id','size'),original_event_ids=('event_id',lambda x:'|'.join(x)),original_methods=('method',lambda x:'|'.join(sorted(set(x)))))
save(ov,'PHYSICAL_EVENT_OVERLAP.csv.gz')
d=d.sort_values('event_id').drop_duplicates(['final_method','physical_event_key']).copy()
d['block_key']=d.X_members.fillna('')+' / '+d.Y_members.fillna('')+' / '+d.Z_members.fillna('')
d['ratio_band']=np.select([d.m.eq(d.n),2*d.m>d.n,2*d.m==d.n],['all','more_than_half','half'],default='less_than_half')
ids=['event_id','physical_event_key','method','final_method','building','pair_key','groups','condition','analysis_scope','scope_comparable','role_direction','source_labels','target_labels','source_semantic','target_semantic','n','m','ratio_band','common_n','known_common_n','image_a','image_b','image_id_a','image_id_b','pool_id_a','pool_id_b','reference_id_a','reference_id_b','difficulty_a','difficulty_b','D_members','X_members','Y_members','Z_members','A_members','B_members','C_members','Q_common6','complete6','time_common6','time_semantics']+[f'team_{r}_{v}' for v in ['a','b'] for r in ['A','B','C']]
save(d[ids],'EVENT_IDENTITIES.csv.gz')
status=d.groupby(['final_method','analysis_scope','ratio_band','n','m','role_direction'],dropna=False).agg(events=('event_id','size'),pairs=('pair_key','nunique'),buildings=('building','nunique'),Q_common6=('Q_common6','sum'),complete6=('complete6','sum'),time_common6=('time_common6','sum'),incomplete_fraction=('incomplete_fraction','mean'),unscorable_fraction=('score_failure_fraction','mean')).reset_index();save(status,'SUPPORT_STATUS.csv')
geom_cache=OUT/'EXISTING_GEOMETRY_SOURCE.csv.gz'
if geom_cache.exists():
 geom=pd.read_csv(geom_cache,low_memory=False)
else:
 pool_geom=ROOT.parent/'repo/research/data/releases/v2.1/same_room_current_results/large/geometry/pools'
 gg=[];allids=set(d.event_id)
 for p in sorted(pool_geom.glob('*.csv.gz')):
  z=pd.read_csv(p,low_memory=False);z=z[z.event_id.isin(allids)]
  if len(z):gg.append(z)
 if not gg:raise FileNotFoundError('Missing packaged abc/EXISTING_GEOMETRY_SOURCE.csv.gz; archive extraction requires the frozen repository')
 geom=pd.concat(gg,ignore_index=True);save(geom,'EXISTING_GEOMETRY_SOURCE.csv.gz')
assert not geom.duplicated(['event_id','view','comparison']).any()
basekeys=['final_method','analysis_scope','condition','building','groups','pair_key','role_direction','n','m','ratio_band']
qcols=[c[:-5] for c in d.columns if c.endswith('_a_BA')]
metric_specs=[(m,'scalar') for m in qcols]+[(m,'geometry') for m in ['bev_mean_h','top_mean_h','bev_max_h','top_max_h','angle_deg','matched_reflex_disagreement_n']]
pair_rows=[];cfg_rows=[];summary_rows=[];image_rows=[];building_rows=[]
for metric,kind in metric_specs:
 z=d[basekeys+['event_id','physical_event_key','block_key','D_members','image_a','image_b']].copy()
 for v in ['a','b']:
  if kind=='scalar':
   ba=d[f'{metric}_{v}_BA'].to_numpy(float);ca=d[f'{metric}_{v}_CA'].to_numpy(float);cb=d[f'{metric}_{v}_CB'].to_numpy(float)
   valid=np.isfinite(ba)&np.isfinite(ca)&np.isfinite(cb)
   if metric=='recorded_time_total_seconds':valid &= d.time_common6.to_numpy(bool)
   W=np.abs(ba);AC=np.abs(ca);BC=np.abs(cb)
  else:
   gp=geom[geom.view.eq(v)].pivot(index='event_id',columns='comparison',values=metric)
   ss=geom[geom.view.eq(v)].pivot(index='event_id',columns='comparison',values='status')
   arr=gp.reindex(d.event_id)[['AB','AC','BC']].to_numpy(float)
   statuses=ss.reindex(d.event_id)[['AB','AC','BC']].to_numpy()
   valid=np.all(np.isfinite(arr),axis=1)&np.all(statuses=='unique_cyclic_candidate',axis=1)
   W,AC,BC=arr.T;ba=np.full(len(d),np.nan);ca=ba.copy();cb=ba.copy()
  for name,val in [('W',W),('AC',AC),('BC',BC),('GA',AC-W),('GS',(AC+BC)/2-W),('BA',ba),('CA',ca),('CB',cb)]:z[f'{name}_{v}']=np.where(valid,val,np.nan)
 z['joint_valid']=z.W_a.notna()&z.W_b.notna()
 # Each metric has its own six-endpoint / six-pair denominator.
 vals=[f'{x}_{v}' for v in ['a','b'] for x in ['W','AC','BC','GA','GS','BA','CA','CB']]
 z.loc[~z.joint_valid,vals]=np.nan
 z['metric']=metric;z['kind']=kind
 for c in ['GA','GS','CB']:
  z[c+'_mean']=(z[c+'_a']+z[c+'_b'])/2
  z[c+'_both_positive']=np.where(z.joint_valid,(z[c+'_a']>1e-9)&(z[c+'_b']>1e-9),np.nan)
  z[c+'_opposite']=np.where(z.joint_valid,z[c+'_a']*z[c+'_b']< -1e-9,np.nan)
 if kind=='scalar':
  for eps in ([0,2] if metric in ['B8L2','D10'] else [0]):
   sa=np.where(z.CB_a>eps+1e-9,1,np.where(z.CB_a< -eps-1e-9,-1,0));sb=np.where(z.CB_b>eps+1e-9,1,np.where(z.CB_b< -eps-1e-9,-1,0))
   z[f'source_trigger_{eps}']=np.where(z.joint_valid,(sa!=0).astype(int)+(sb!=0).astype(int),np.nan)
   z[f'source_repeat_{eps}']=np.where(z.joint_valid,2*((sa==sb)&(sa!=0)).astype(int),np.nan)
   z[f'source_opposite_{eps}']=np.where(z.joint_valid,2*((sa*sb)<0).astype(int),np.nan)
 cs=[c for c in z if c not in basekeys+['event_id','physical_event_key','block_key','D_members','image_a','image_b','metric','kind','joint_valid']]
 # Backgrounds within each fixed XYZ block, then blocks within condition.
 block=z.groupby(basekeys+['block_key'],dropna=False)[cs].mean().reset_index()
 cfg=block.groupby(basekeys,dropna=False)[cs].mean().reset_index()
 counts=z.groupby(basekeys,dropna=False).agg(events=('event_id','size'),valid_events=('joint_valid','sum'),blocks=('block_key','nunique'),backgrounds=('D_members','nunique')).reset_index()
 cfg=cfg.merge(counts,on=basekeys);cfg['metric']=metric;cfg['kind']=kind;cfg_rows.append(cfg)
 # View/image effects are kept distinct; no merging a room into a synthetic image.
 for v in ['a','b']:
  iz=z.copy();iz['image']=z['image_'+v]
  iv=[c+'_'+v for c in ['W','AC','BC','GA','GS','BA','CA','CB']]
  ig=iz.groupby(basekeys+['image','block_key'],dropna=False)[iv].mean().groupby(level=list(range(len(basekeys)+1))).mean().reset_index()
  ig=ig.rename(columns={c+'_'+v:c for c in ['W','AC','BC','GA','GS','BA','CA','CB']});ig['view']=v;ig['metric']=metric;image_rows.append(ig)
 # Report ALL, ratio strata, n/m, and aligned role directions separately.
 partitions=[('all',[]),('ratio',['ratio_band']),('nm',['n','m']),('direction',['role_direction']),('direction_nm',['role_direction','n','m'])]
 for level,extra in partitions:
  for keys,sc in cfg.groupby(['final_method','analysis_scope','condition']+extra,dropna=False):
   keys=keys if isinstance(keys,tuple) else (keys,);meta=dict(zip(['final_method','analysis_scope','condition']+extra,keys));meta.update(level=level,metric=metric,kind=kind)
   pk=['building','groups','pair_key'];pair=sc.groupby(pk,dropna=False)[cs].mean().reset_index()
   pair['metric']=metric;pair['level']=level
   for k,v in meta.items():pair[k]=v
   pair_rows.append(pair)
   ex=pair.assign(group_id=pair.groups.fillna('unknown').str.split('|')).explode('group_id')
   building=ex.groupby(['building','group_id'])[cs].mean().groupby('building').mean().reset_index()
   for k,v in meta.items():building[k]=v
   building_rows.append(building)
   good=pair.GS_mean.notna();p=pair[good]
   row={**meta,'events':int(sc.events.sum()),'valid_events':int(sc.valid_events.sum()),'registered_pairs':len(pair),'valid_pairs':len(p),'valid_buildings':p.building.nunique(),'pair_positive_GA':int((p.GA_mean>1e-9).sum()),'pair_positive_GS':int((p.GS_mean>1e-9).sum()),'pair_positive_CB':int((p.CB_mean>1e-9).sum()),'pair_GS_p10':p.GS_mean.quantile(.1),'pair_GS_median':p.GS_mean.median(),'pair_CB_p10':p.CB_mean.quantile(.1),'pair_CB_median':p.CB_mean.median()}
   for c in cs:row['building_equal_'+c]=building[c].mean();row['pair_equal_'+c]=pair[c].mean()
   for c in ['CB','GA','GS']:
    ww=1/p.groupby('building').pair_key.transform('size') if len(p) else np.array([])
    row['pair_crossview_corr_'+c]=wcorr(p[c+'_a'].to_numpy(),p[c+'_b'].to_numpy(),np.asarray(ww)) if len(p) else np.nan
   for eps in ([0,2] if metric in ['B8L2','D10'] else [0]):
    den=f'source_trigger_{eps}'
    if den in pair:
     rate=pair[f'source_repeat_{eps}']/pair[den].replace(0,np.nan)
     opp=pair[f'source_opposite_{eps}']/pair[den].replace(0,np.nan)
     row[f'pair_source_trigger_repeat_{eps}']=rate.mean();row[f'pair_source_trigger_opposite_{eps}']=opp.mean();row[f'trigger_pairs_{eps}']=int(rate.notna().sum())
   summary_rows.append(row)
 print('ANALYZED',metric,flush=True)
save(pd.concat(cfg_rows,ignore_index=True),'CONDITION_METRICS.csv.gz')
save(pd.concat(pair_rows,ignore_index=True),'PAIR_METRICS.csv.gz')
save(pd.concat(image_rows,ignore_index=True),'IMAGE_METRICS.csv.gz')
save(pd.concat(building_rows,ignore_index=True),'BUILDING_METRICS.csv.gz')
save(pd.DataFrame(summary_rows),'SUMMARY.csv')
checks={'input_class_projection_rows':len(a),'unique_original_events':e.event_id.nunique(),'physical_class_projection_rows':len(d),'duplicate_projections_removed':int(len(a)-len(d)),'target_K3_original_rows':int(a.final_method.eq('TARGET_DSTRUCT_K3').sum()),'target_K3_physical_rows':int(d.final_method.eq('TARGET_DSTRUCT_K3').sum()),'geometry_rows':len(geom),'current_classification_is_working_object_not_final_adoption':True,'no_new_teams':True,'no_new_room_relations':True,'new_fusion_calls':0,'per_metric_validity':'joint two-view support; Q missing is never zero','weighting':'within XYZ block backgrounds equal, within condition blocks equal, conditions within pair equal, pairs within declaration equal, declarations within building equal, buildings equal','coordinate_sign_limitation':'centroid X/Z signs use camera frames and are not physical world-direction replication'}
(OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
print(json.dumps(checks,ensure_ascii=False),flush=True)
