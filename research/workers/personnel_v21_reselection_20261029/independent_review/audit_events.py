"""Read-only, independent ZIP/member/pool and saved-Q arithmetic audit. No hashes or fusion."""
from pathlib import Path
import argparse,collections,io,itertools,json,zipfile
import pandas as pd
p=argparse.ArgumentParser()
p.add_argument('--downloads',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
z={t:zipfile.ZipFile(next(a.downloads.glob('*'+t+'*20261029.zip'))) for t in ['07A','07B','07C','07D']}
def read(tag,n,**kw):return pd.read_csv(io.BytesIO(z[tag].read(n)),compression='gzip' if n.endswith('.gz') else None,low_memory=False,**kw)
def members(v):return set(str(v).split('|')) if pd.notna(v) and str(v) else set()
labels=read('07A','classification/MAIN45_LABELS_ALL_LOBO.csv.gz');assert not labels.duplicated(['method','heldout_building','worker_id']).any()
lookup=labels.set_index(['method','heldout_building','worker_id']).class_id.to_dict()
pools={}
for name in ['research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json','research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json']:
 for pool in json.loads((a.repo/name).read_text(encoding='utf-8-sig'))['images']:
  assert pool['pool_id'] not in pools;pools[pool['pool_id']]=pool
workers={pid:{r['worker_id']:r['object_id'] for r in po['records']} for pid,po in pools.items()}

def check_events(ev,parent=False,endpoints=None):
 issues=[]
 for r in ev.itertuples(index=False):
  d,x,y,t=[members(getattr(r,c)) for c in 'DXYZ'];arms=[members(getattr(r,c+'_members')) for c in 'ABC'];err=[]
  if any(u&v for u,v in itertools.combinations([d,x,y,t],2)):err.append('overlap')
  if [len(d),len(x),len(y),len(t)]!=[r.n-r.m,r.m,r.m,r.m]:err.append('sizes')
  if arms!=[d|x,d|y,d|t]:err.append('membership')
  if r.heldout_building!=r.building or r.source_class==r.target_class:err.append('fold_or_class_identity')
  lab=lambda w:lookup.get((r.method,r.heldout_building,w))
  if any(lab(w)!=r.source_class for w in x|y):err.append('source_class')
  if any(lab(w)!=r.target_class for w in t):err.append('target_class')
  pool=pools.get(r.pool_id)
  if pool is None:err.append('local_pool_missing')
  else:
   if pool['meta']['reference_id']!=r.reference_id:err.append('reference_mismatch')
   if not set.union(*arms)<=workers[r.pool_id].keys():err.append('local_worker_missing')
   if endpoints is not None:
    if sum(lab(w)==r.source_class for w in workers[r.pool_id])!=r.source_capacity or sum(lab(w)==r.target_class for w in workers[r.pool_id])!=r.target_capacity:err.append('capacity')
    for arm,own in zip('ABC',arms):
     key=getattr(r,arm+'_team_key')
     if key not in endpoints.index:err.append('endpoint_missing');continue
     ep=endpoints.loc[key]
     if members(ep.member_workers)!=own or ep.k!=r.n or ep.pool_id!=r.pool_id or ep.reference_id!=r.reference_id:err.append('endpoint_identity')
  if parent:
   def pl(w):
    v=lookup.get((r.parent_method,r.heldout_building,w));return v if pd.notna(v) else 'unknown'
   vecs=[dict(collections.Counter(pl(w) for w in own)) for own in arms]
   if not vecs[0]==vecs[1]==vecs[2]:err.append('parent_composition_change')
   for arm,vec in zip('ABC',vecs):
    saved={k:int(v) for k,v in (x.split(':') for x in getattr(r,arm+'_parent_vector').split('|')) if int(v)}
    if vec!=saved:err.append('parent_vector')
  if err:issues.append({'event_id':r.event_id,'issues':err})
 return {'events':len(ev),'unique_events':int(ev.event_id.nunique()),'pools':int(ev.pool_id.nunique()),'images':int(ev.image.nunique()),'buildings':int(ev.building.nunique()),'issues':issues}

def aggregate(f):
 f=f.copy();valid=f[list('ABC')].notna().all(axis=1)
 f['within']=(f.B-f.A).abs().where(valid);f['cross']=((f.C-f.A).abs()+(f.C-f.B).abs()).div(2).where(valid);f['gap']=f['cross']-f['within'];f['CA']=f.C-f.A;f['CB']=f.C-f.B
 mm=['within','cross','gap','CA','CB'];po=f.groupby(['pool_id','image','building'])[mm].mean().reset_index();im=po.groupby(['image','building'])[mm].mean().reset_index();bu=im.groupby('building')[mm].mean()
 out={'events':len(f),'images':int(f.image.nunique()),'buildings':int(f.building.nunique()),'all_three_valid_events':int(valid.sum()),'CA_valid_events':int(f.CA.notna().sum()),'CB_valid_events':int(f.CB.notna().sum()),'CB_loss_over_10_events':int(f.CB.lt(-10).sum()),'missing_Q_events':{c:int(f[c].isna().sum()) for c in 'ABC'},'image_means':im[mm].mean().to_dict(),'image_medians':im[mm].median().to_dict(),'valid_images':im[mm].count().to_dict(),'positive_images':im[mm].gt(0).sum().to_dict(),'building_means':bu.mean().to_dict(),'valid_buildings':bu[mm].count().to_dict(),'positive_buildings':bu.gt(0).sum().to_dict()}
 return out,im,f

events=read('07B','experiment/focused_design/EVENTS_EXACT.csv.gz');endpoints=read('07B','experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz').set_index('team_key');assert endpoints.index.is_unique
result={'method':'Read-only exact member/LOBO class/capacity/local snapshot joins; arithmetic from saved endpoint B8L2, not native replay.'}
result['focused_identity']=check_events(events,endpoints=endpoints)
f=events[(events.method=='OPPJOINT_K4')&(events.n==12)&(events.m==6)].copy()
for arm in 'ABC':f[arm]=f[arm+'_team_key'].map(endpoints.B8L2)
result['oppjoint_n12m6'],im,recomputed=aggregate(f)
assert len(f)==172 and f.image.nunique()==56 and f.building.nunique()==13
stored=read('07B','analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz').set_index('event_id');recomputed=recomputed.set_index('event_id')
result['oppjoint_n12m6']['stored_effect_max_abs_errors']={c:float((recomputed[c]-stored.reindex(recomputed.index)['B8L2_'+c]).abs().max()) for c in ['within','cross','gap','CA','CB']}
assert max(result['oppjoint_n12m6']['stored_effect_max_abs_errors'].values())<1e-10
context=read('07B','analysis/focused_contexts/SCREEN_SUPPORT_BY_IMAGE.csv.gz');context=context[(context.method=='OPPJOINT_K4')&(context.n==12)&(context.m==6)][['image','building','screen_support']]
im=im.merge(context,on=['image','building'],validate='one_to_one');outside=im[im.screen_support!='screen_pool']
result['declared_outside_screen']={'provenance_limit':'SCREEN_POOL_FRAME.csv absent from these five packages; membership labels taken from delivered SCREEN_SUPPORT_BY_IMAGE; aggregation independently recalculated.','groups':im.groupby('screen_support').size().to_dict(),'images':len(outside),'CB_image_mean':float(outside.CB.mean()),'CB_positive_images':int(outside.CB.gt(0).sum())}
result['counterexamples']=im[im.CB<=0].to_dict('records');im.to_csv(a.out/'oppjoint_n12m6_by_image.csv',index=False,encoding='utf-8-sig')
# Reconstruct source-stratified time eligibility from the endpoint source counts.
def signature(row):
 x=json.loads(row.record_time_by_kind_json);good=all(v.get('known_n')==v.get('n') and v.get('total_seconds') is not None and v.get('total_seconds')>=0 for v in x.values());return tuple(sorted((k,v['n']) for k,v in x.items())),good
tr=[]
for r in f.itertuples(index=False):
 b,c=endpoints.loc[r.B_team_key],endpoints.loc[r.C_team_key];bs,bgood=signature(b);cs,cgood=signature(c)
 tr.append({'pool_id':r.pool_id,'image':r.image,'building':r.building,'pct':100*(c.source_time_total_seconds/b.source_time_total_seconds-1) if bgood and cgood and bs==cs and b.source_time_total_seconds>0 else float('nan')})
tm=pd.DataFrame(tr);ti=tm.groupby(['pool_id','image','building']).pct.mean().reset_index().groupby(['image','building']).pct.mean()
result['oppjoint_time_CB_source_matched']={'events':int(tm.pct.count()),'images':int(ti.count()),'image_mean_pct':float(ti.mean()),'positive_images':int(ti.gt(0).sum())}
fine=read('07D','analysis/fine_increment/FIXED_PARENT_EVENT_METRICS.csv.gz');result['fine_identity']=check_events(fine,parent=True)
for name,method,n,m,direction in [('fine_RFUSE_negative','RFUSE_GEOMQ_K3',12,6,'higher'),('fine_OPPJOINT_n20m6','OPPJOINT_K4',20,6,'higher_Q__higher_logtime')]:
 sub=fine[(fine.method==method)&(fine.n==n)&(fine.m==m)&(fine.role_direction==direction)&(fine.scope=='primary')].copy()
 for arm in 'ABC':sub[arm]=sub[arm+'_B8L2']
 result[name],_,_=aggregate(sub)
# Detect export defects and prove exact recovery against local source objects.
repairs=[];tables=[]
for tag in ['07B','07C','07D']:
 for name in z[tag].namelist():
  if not name.endswith('.csv.gz') or not ('ENDPOINT_SCALARS' in name or 'USED_ENDPOINT_SCALARS_AND_MEMBERS' in name):continue
  header=read(tag,name,nrows=0).columns
  if not {'team_key','pool_id','member_workers','member_object_ids'}<=set(header):
   tables.append({'package':tag,'table':name,'identity_fields_present':False});continue
  df=read(tag,name,usecols=['team_key','pool_id','member_workers','member_object_ids']);bad=[];unresolved=[]
  for r in df.itertuples(index=False):
   own=workers[r.pool_id];ws=members(r.member_workers);expected={own[w] for w in ws};raw=str(r.member_object_ids)
   if members(raw)==expected:continue
   restored=raw[::2];ok='|'.join(restored)==raw and members(restored)==expected
   rec={'package':tag,'table':name,'team_key':r.team_key,'pool_id':r.pool_id,'raw':raw,'repaired':restored,'verified_against_local_snapshot':ok}
   repairs.append(rec);bad.append(r.team_key)
   if not ok:unresolved.append(r.team_key)
  tables.append({'package':tag,'table':name,'rows':len(df),'malformed_object_ids':len(bad),'unresolved':unresolved})
result['object_id_export_tables']=tables
pd.DataFrame(repairs).to_csv(a.out/'member_object_id_repair_map.csv',index=False,encoding='utf-8-sig')
keys={r['team_key'] for r in repairs if r['package']=='07B' and r['table']=='experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz'}
result['focused_object_id_defect']={'unique_endpoints':len(keys),'affected_events':int(events[['A_team_key','B_team_key','C_team_key']].isin(keys).any(axis=1).sum()),'focus_n12m6_affected_events':int(f[['A_team_key','B_team_key','C_team_key']].isin(keys).any(axis=1).sum()),'focus_n12m6_affected_endpoints':len(keys & set(f[['A_team_key','B_team_key','C_team_key']].to_numpy().flatten()))}
result['unique_malformed_endpoints_all_tables']=len({r['team_key'] for r in repairs})
(a.out/'event_audit_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
assert not result['focused_identity']['issues'],result['focused_identity']['issues'][:3]
assert not result['fine_identity']['issues'],result['fine_identity']['issues'][:3]
assert all(r['verified_against_local_snapshot'] for r in repairs)
assert abs(result['oppjoint_n12m6']['image_means']['CB']-8.051040906167595)<1e-10
assert abs(result['fine_RFUSE_negative']['image_means']['CB']+1.7302841967533973)<1e-10
print(json.dumps(result,ensure_ascii=False,indent=2))
