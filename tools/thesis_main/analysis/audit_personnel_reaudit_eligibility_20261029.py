"""Audit the v2.1 reaudit delivery from its repository source archive."""
from pathlib import Path
import json
import pandas as pd,numpy as np
O=Path('research/workers/personnel_v21_reselection_20261029/independent_review/reaudit_20261029');R=Path('research/workers/personnel_v21_reselection_20261029');V=Path('research/data/releases/v2.1')
ROOT=Path.cwd();A=O/'source_archive';M=pd.read_csv(A/'SOURCE_ARCHIVE_MAP.csv')
def source_file(stage,suffix):
 rows=M[(M.source_zip_name==f'HOHONET_v21_reaudit_{stage}.zip')&M.member_path.str.endswith(suffix)];assert len(rows)==1,(stage,suffix,len(rows))
 p=rows.iloc[0].repository_or_local_path
 if p.startswith('git:'):p=p.split(':',2)[2]
 p=ROOT/p;assert p.is_file(),p;return p
def read(stage,s,**kw):
 p=source_file(stage,s);return pd.read_csv(p,compression='gzip' if s.endswith('.gz') else None,low_memory=False,**kw)
src='stage06_reproducible_sources';new='stage03_completed_ABC';comp='stage02_comparison'
inv={r['object_id']:r for r in json.loads((V/'quality_inventory.json').read_text(encoding='utf-8'))};extra=json.loads((V/'admitted_space_extension/ANALYSIS_RECORDS.json').read_text(encoding='utf-8'));allowed={o for o,r in inv.items() if r['quality_usable']}|{r['object_id'] for r in extra}
ix=pd.read_csv(R.parent/'personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz',low_memory=False).set_index('object_id')
local={};pack={}
for rel in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json']:
 a=json.loads((V/rel).read_text(encoding='utf-8'));b=json.loads(source_file(src,'research/data/releases/v2.1/'+rel).read_text(encoding='utf-8'));local.update({p['pool_id']:p for p in a['images']});pack.update({p['pool_id']:p for p in b['images']})
pm={p:{r['worker']:r for r in x['records']} for p,x in pack.items()};c={};issues=[]
c['snapshot_pools']=len(pack);c['snapshots_exact_equal']=pack==local
raw=read(src,'RAW_TARGET_RESPONSE_RECORDS.csv.gz');c['history_n']=len(raw);c['history_ids_equal_authorized']=set(raw.object_id)==allowed;c['history_layer_counts']=raw.layer.value_counts().to_dict();c['history_excluded_workers']=sorted(set(raw.worker_id)&{'W019','W026'})
c['history_bad_cleaning']=sum(inv[o]['cleaning_disposition']!='retained' for o in raw.object_id);c['history_non_independent']=sum(not bool(ix.loc[o,'independent_vote_eligible']) for o in raw.object_id);c['history_other_exclusions']=sum(bool(set(inv[o]['quality_exclusion_reasons'])-{'bound_other_admitted_space'}) for o in raw.object_id)
c['history_identity_reference_mismatch']=sum(r.worker_id!=inv[r.object_id]['worker_id'] or r.reference_id!=inv[r.object_id]['reference_id'] or r.reference_version!=inv[r.object_id]['reference_version'] for r in raw.itertuples());c['history_Q_max_error']=max(abs(r.B8L2-inv[r.object_id]['diagnostic_B8L2']) for r in raw.itertuples())
ep=read(new,'ENDPOINT_SCALARS.csv.gz');d=read(new,'EVENTS_EXACT.csv.gz');req=read(new,'REQUESTS.csv.gz');lab=read(new,'FROZEN_LABELS_ALL_LOBO.csv.gz');lm={(r.method,r.heldout_building,r.worker_id):r.class_id for r in lab.itertuples() if r.known}
c.update(events=len(d),endpoints=len(ep),request_key_match=set(req.team_key)==set(ep.team_key),missing_Q=int(ep.B8L2.isna().sum()),missing_Q_reasons=ep.loc[ep.B8L2.isna(),'reasons'].fillna('NA').value_counts().to_dict())
used=set();ww=set()
for e in ep.itertuples():
 w=e.member_workers.split('|');o=set(e.member_object_ids.split('|'));pool=pack[e.pool_id]
 if len(w)!=e.k or len(set(w))!=e.k or not set(w)<=set(pm[e.pool_id]):issues.append(['endpoint_members',e.team_key])
 elif {pm[e.pool_id][v]['object_id'] for v in w}!=o:issues.append(['endpoint_objects',e.team_key])
 if not o<=allowed:issues.append(['endpoint_excluded',e.team_key])
 if e.reference_id!=pool['meta']['reference_id'] or e.reference_version!=pool['meta']['reference_version']:issues.append(['endpoint_reference',e.team_key])
 used|=o;ww|=set(w)
for e in d.itertuples():
 blocks=[set(getattr(e,a).split('|')) if pd.notna(getattr(e,a)) else set() for a in ['D','X','Y','Z']];bg,x,y,zz=blocks
 if [len(s) for s in blocks]!=[e.n-e.m,e.m,e.m,e.m] or len(set.union(*blocks))!=e.n+2*e.m:issues.append(['blocks',e.event_id])
 for arm,block in zip('ABC',[x,y,zz]):
  if set(getattr(e,arm+'_members').split('|'))!=bg|block:issues.append(['arm',e.event_id])
 if e.heldout_building!=e.building:issues.append(['fold',e.event_id])
 if any(lm.get((e.method,e.building,w))!=e.source_class for w in x|y) or any(lm.get((e.method,e.building,w))!=e.target_class for w in zz):issues.append(['class',e.event_id])
c.update(used_records=len(used),used_workers=len(ww),excluded_workers_in_endpoints=sorted(ww&{'W019','W026'}),new_design_issues=issues)
c['inventory_cleaning_counts']=pd.Series([r['cleaning_disposition'] for r in inv.values()]).value_counts().to_dict()
u=read(comp,'COMBINED_UNION_EVENTS_WITH_ROLES.csv.gz');needed=set(u.A_team_key)|set(u.B_team_key)|set(u.C_team_key)
fields=['team_key','B8L2','D10','IoU3D100','fusion_turn_n','geometry_area_h2','height_mean_h','boundary_loss','direction_loss','height_loss'];ss=[ep[fields]]
for p in [R/'additional_delivery/packages/05A/experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz']+list((R/'experiment').glob('*_endpoints/ENDPOINT_SCALARS.csv.gz')):
 a=pd.read_csv(p,usecols=lambda x:x in fields,low_memory=False);ss.append(a[a.team_key.isin(needed)])
sc=pd.concat(ss).drop_duplicates('team_key').set_index('team_key');c['combined_events']=len(u);c['missing_endpoint_keys']=len(needed-set(sc.index))
md={}
for p in [R/'additional_delivery/packages/05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz']+list((R/'experiment').glob('*_design/EVENTS_EXACT.csv.gz')):
 a=pd.read_csv(p,usecols=lambda x:x in ['pool_id']+[v+s for v in 'ABC' for s in ['_team_key','_members']],low_memory=False)
 for arm in 'ABC':
  if arm+'_members' in a:
   for k,m in zip(a[arm+'_team_key'],a[arm+'_members']):
    if pd.notna(m):md[k]=m
for p in [R/'additional_delivery/packages/05A/experiment/global_screen_design/REQUESTS.csv.gz']+list((R/'experiment').glob('*_design/REQUESTS.csv.gz')):
 if p.exists():
  rr=pd.read_csv(p,usecols=['team_key','member_workers']);md.update(dict(zip(rr.team_key,rr.member_workers)))
md.update(dict(zip(req.team_key,req.member_workers)))
bad=[];missing=0
for e in u.itertuples():
 for arm in 'ABC':
  val=getattr(e,arm+'_members');val=val if pd.notna(val) else md.get(getattr(e,arm+'_team_key'))
  if val is None:
   missing+=1
   if missing<4:print('MISSING',e.source_stage,getattr(e,arm+'_team_key'))
   continue
  members=set(val.split('|'))
  if e.pool_id not in pm or not members<=set(pm[e.pool_id]):bad.append([e.event_id,'missing_members'])
  elif any(pm[e.pool_id][w]['object_id'] not in allowed for w in members):bad.append([e.event_id,'excluded'])
c['combined_eligibility_issues']=bad;c['combined_missing_member_checks']=missing
q={a:sc.B8L2.reindex(u[a+'_team_key']).to_numpy() for a in 'ABC'};errs={}
for t,a,b in [('BA','B','A'),('CA','C','A'),('CB','C','B')]:
 vals=q[a]-q[b];saved=u['B8L2_'+t].to_numpy();errs[t]=dict(missing_mismatch=int((np.isnan(vals)!=np.isnan(saved)).sum()),max_error=float(np.nanmax(abs(vals-saved))))
c['Q_difference_checks']=errs
v=np.isfinite(q['A'])&np.isfinite(q['B'])&np.isfinite(q['C'])
u['within']=np.where(v,abs(q['B']-q['A']),np.nan);u['cross_A']=np.where(v,abs(q['C']-q['A']),np.nan);u['cross_sym']=np.where(v,(abs(q['C']-q['A'])+abs(q['C']-q['B']))/2,np.nan);u['gap_A']=u.cross_A-u.within;u['gap_sym']=u.cross_sym-u.within;u['Qmean']=np.where(v,(q['A']+q['B']+q['C'])/3,np.nan);u['Qrange']=np.where(v,np.maximum.reduce(list(q.values()))-np.minimum.reduce(list(q.values())),np.nan);u['three_Q']=v.astype(float)
for a in 'ABC':u['Q'+a]=np.where(v,q[a],np.nan)
keys=['method','scope','n','m','axis','rank_direction'];metrics=['within','cross_A','cross_sym','gap_A','gap_sym','Qmean','Qrange','three_Q','QA','QB','QC']
b=u.groupby(keys+['pool_id','image','building','block_id'],dropna=False)[metrics].mean().reset_index();p=b.groupby(keys+['pool_id','image','building'],dropna=False)[metrics].mean().reset_index();im=p.groupby(keys+['image','building'],dropna=False)[metrics].mean().reset_index();dm={p['meta']['image']:p['meta']['difficulty'] for p in local.values() if p['meta'].get('layer')=='ordinary_manual' and p['meta'].get('difficulty') in ['简单','中等','困难']};im['difficulty']=im.image.map(dm);im.loc[im.scope.ne('primary'),'difficulty']='未分级'
rows=[]
for key,g in im.groupby(keys,dropna=False):
 r=dict(zip(keys,key));a=g.dropna(subset=['gap_A']);r.update(registered=len(g),valid=len(a),within=a.within.mean(),cross_A=a.cross_A.mean(),gap_A=a.gap_A.mean(),pos_A=int((a.gap_A>1e-9).sum()),cross_sym=a.cross_sym.mean(),gap_sym=a.gap_sym.mean(),pos_sym=int((a.gap_sym>1e-9).sum()),small_neg_A=int(((a.gap_A<=0)&(a.gap_A>=-1)).sum()));rows.append(r)
sm=pd.DataFrame(rows);sm.to_csv(O/'ALL_DIRECTION_RECOMPUTED.csv',index=False,encoding='utf-8-sig');im.to_csv(O/'ALL_IMAGE_RECOMPUTED.csv.gz',index=False,compression='gzip')
f=im[(im.method=='TARGET_DSTRUCT_K3')&(im.scope=='primary')&(im.rank_direction=='2/3->3/3')&im.n.isin([14,20])&(im.m==7)];f.to_csv(O/'TARGET_MAIN_IMAGES.csv',index=False,encoding='utf-8-sig');summary=[]
for key,g in f.dropna(subset=['gap_A']).groupby(['n','m','difficulty'],dropna=False):
 summary.append(dict(n=key[0],m=key[1],difficulty=key[2],images=len(g),pos_A=int((g.gap_A>0).sum()),pos_sym=int((g.gap_sym>0).sum()),gap_A=g.gap_A.mean(),gap_sym=g.gap_sym.mean(),within=g.within.mean(),cross_A=g.cross_A.mean(),Qmean=g.Qmean.mean(),Qrange=g.Qrange.mean(),negative_Q=g.loc[g.gap_A<=0,'Qmean'].mean(),positive_Q=g.loc[g.gap_A>0,'Qmean'].mean()))
pd.DataFrame(summary).to_csv(O/'TARGET_DIFFICULTY.csv',index=False,encoding='utf-8-sig');(O/'CHECKS.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
assert c['snapshots_exact_equal'] and c['history_ids_equal_authorized'] and not issues and not bad and not missing
assert not c['history_excluded_workers'] and not c['history_bad_cleaning'] and not c['history_non_independent'] and not c['history_other_exclusions']
assert not c['history_identity_reference_mismatch'] and c['history_Q_max_error']<1e-9 and not c['missing_endpoint_keys']
assert c['request_key_match'] and req.team_key.is_unique and ep.team_key.is_unique and d.event_id.is_unique
assert all(e['missing_mismatch']==0 and e['max_error']<1e-9 for e in errs.values())

# Re-aggregate saved per-image original-answer distances, independently of the summary.
gz=z('stage01_classification');gi=read(gz,'RAW_GEOMETRY_BY_IMAGE.csv.gz');gs=read(gz,'RAW_GEOMETRY_SUMMARY.csv');gr=[]
for method in ['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3','V21_DSTRUCT_FULL_K3','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4']:
 a=gi[gi.method.eq(method)&gi.support.eq('common_old45_new')&gi.subset.eq('same_corner_count')&gi.scope_summary.eq('ALL_TARGETS')&gi.difficulty_summary.eq('ALL')]
 v=a.geometry_pair_angle_gap.dropna();r=dict(method=method,images=len(v),positive=int((v>0).sum()),gap=v.mean(),buildings_positive=int((a.groupby('building').geometry_pair_angle_gap.mean()>0).sum()))
 saved=gs[gs.method.eq(method)&gs.support.eq('common_old45_new')&gs.subset.eq('same_corner_count')&gs.scope_summary.eq('ALL_TARGETS')&gs.difficulty_summary.eq('ALL')&gs.metric.eq('geometry_pair_angle')].iloc[0]
 assert len(v)==saved.images and r['positive']==saved.positive_gap_images and abs(r['gap']-saved.gap)<1e-9
 gr.append(r)
pd.DataFrame(gr).to_csv(O/'RAW_GEOMETRY_REAGGREGATED.csv',index=False)

# These cases diagnose why a negative Q gap need not mean unchanged geometry.
ce=u[u.method.eq('TARGET_DSTRUCT_K3')&u.scope.eq('primary')&u.rank_direction.eq('2/3->3/3')&u.n.eq(20)&u.m.eq(7)&u.image.isin(['7y3sRwLe3Va-21','B6ByNegPMKs-47'])]
ck=set(ce.A_team_key)|set(ce.B_team_key)|set(ce.C_team_key)
cf=['team_key','B8L2','nodes','node_supports','minimum_support','ref_node_recall_9','iou_2d','boundary_loss','direction_loss','height_loss']
caseframes=[ep[[c for c in cf if c in ep.columns]]]
for path in (R/'experiment').glob('*_endpoints/ENDPOINT_SCALARS.csv.gz'):
 a=pd.read_csv(path,usecols=lambda x:x in cf,low_memory=False);caseframes.append(a[a.team_key.isin(ck)])
cs=pd.concat(caseframes).drop_duplicates('team_key').set_index('team_key');cr=[]
assert ck<=set(cs.index) and len(ce)>0
assert cs.loc[list(ck),['nodes','node_supports','minimum_support','ref_node_recall_9','iou_2d']].notna().all().all()
for e in ce.itertuples():
 for arm in 'ABC':
  key=getattr(e,arm+'_team_key');cr.append(dict(event_id=e.event_id,image=e.image,n=e.n,m=e.m,arm=arm,team_key=key,**cs.loc[key].to_dict()))
pd.DataFrame(cr).to_csv(O/'EXCEPTION_ENDPOINT_COMPONENTS.csv',index=False,encoding='utf-8-sig')
print(json.dumps(c,ensure_ascii=False,indent=2));print(sm[(sm.method.isin(['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3','OPPSTRUCT_K3']))&(sm.scope=='primary')&(sm.rank_direction=='2/3->3/3')&sm.n.isin([12,14,16,20])&sm.m.isin([7,8])].to_string(index=False));print(pd.DataFrame(summary).to_string(index=False))
