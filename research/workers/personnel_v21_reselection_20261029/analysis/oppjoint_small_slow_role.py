"""Exact cached m1 ABC space for OPPJOINT K4's small slow sibling class.

Finite member panels are held fixed. Every possible pair of fast siblings and
one slow target is considered at every possible n-1 common background in the
existing 12-choose-6 inventory. No consensus or scoring is recomputed.

X/Y are exchangeable: the compact unordered source-pair list represents both
orientations at half weight. This avoids arbitrary worker-ID direction effects.
"""
from pathlib import Path
from itertools import combinations
from collections import Counter
from math import comb
import gzip,hashlib,json,os
import numpy as np,pandas as pd

W=Path(__file__).resolve().parents[1];O=W/'analysis/fine_increment/oppjoint_small_slow';O.mkdir(parents=True,exist_ok=True)
def save(p,d):
 b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,compresslevel=6,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)
def truth(s):return s.astype(str).str.lower().isin(['true','1','1.0'])
def vector(ws,mapping):return '|'.join(f'{k}:{v}' for k,v in sorted(Counter(mapping.get(w,'UNKNOWN') for w in ws).items()))

roles=pd.read_csv(W/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz')
roles=roles[roles.method.eq('OPPJOINT_K4')&roles.heldout_building.ne('ALL')]
hier=pd.read_csv(W/'analysis/global_parent_links/METHOD_HIERARCHY_ALL_LOBO.csv')
hier=hier[hier.child_method.eq('OPPJOINT_K4')&hier.parent_method.eq('OPPJOINT_K3')]
label=pd.read_csv(W/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
workers=sorted(label.worker_id.unique());bits={w:1<<i for i,w in enumerate(workers)}
label=label[label.method.isin(['OPPJOINT_K4','OPPJOINT_K3'])&truth(label.known)]
lm={(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in label.groupby(['method','heldout_building'])}
fold_roles=[];chosen={}
for building,r in roles.groupby('heldout_building'):
 slow=r.loc[r.m_all_log_time.idxmax()];fold=hier[hier.heldout_building.eq(building)].set_index('child_class')
 parent=fold.at[slow.class_id,'parent_classes']
 siblings=r[r.class_id.ne(slow.class_id)&r.class_id.map(fold.parent_classes).eq(parent)]
 reason='supported_small_slow_sibling'
 if slow.workers>6 or slow.m_all_log_time<.7:reason='no_separate_small_slow_role_at_this_fold'
 elif len(siblings)!=1:reason='no_unique_sibling'
 fast=siblings.loc[siblings.m_all_log_time.idxmin()] if len(siblings) else None
 row=dict(building=building,slow_class=slow.class_id,slow_workers=slow.members,slow_class_size=int(slow.workers),
  slow_history_log_time=slow.m_all_log_time,slow_history_Q=slow.m_all_B8L2,parent_class=parent,
  fast_class=None if fast is None else fast.class_id,fast_workers=None if fast is None else fast.members,
  fast_history_log_time=np.nan if fast is None else fast.m_all_log_time,fast_history_Q=np.nan if fast is None else fast.m_all_B8L2,
  included=reason=='supported_small_slow_sibling',reason=reason)
 fold_roles.append(row)
 if row['included']:chosen[building]=row
save(O/'FROZEN_SMALL_SLOW_ROLE_BY_FOLD.csv',pd.DataFrame(fold_roles))

C=W/'composition/primary_panel_inputs';panels=pd.read_csv(C/'PANELS_USED.csv')
members=pd.read_csv(C/'TEAM_MEMBERS.csv.gz')
metrics=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
 'fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2','height_mean_h','top_y_mean_px','bottom_y_mean_px']
cols=['team_key','pool_id','complete_evaluable','recorded_time_total_seconds','recorded_time_eligible','time_source_kinds']+metrics
end=pd.read_csv(C/'ENDPOINT_SCALARS.csv.gz',usecols=cols,low_memory=False)
end=end.merge(members[['team_key','member_workers']],on='team_key',validate='one_to_one')
end['nonusable']=(~truth(end.complete_evaluable)).astype(float);metrics+=['nonusable']
val=end[metrics].to_numpy(float);time=end.recorded_time_total_seconds.to_numpy(float)
kinds=end.time_source_kinds.fillna('').to_numpy();timeok=truth(end.recorded_time_eligible).to_numpy()
keys=end.team_key.to_numpy();lookup={}
for i,r in enumerate(end[['pool_id','member_workers']].itertuples(index=False)):
 mask=sum(bits[w] for w in r.member_workers.split('|'));key=(r.pool_id,mask)
 assert key not in lookup;lookup[key]=i

backgrounds=[];pair_rows=[];stat_rows=[];coverage=[];used=set();bg_no=0
for panel in panels.itertuples():
 info=chosen.get(panel.building)
 if info is None:
  coverage.append(dict(panel_id=panel.panel_id,image=panel.image,building=panel.building,n=panel.n,status='no_fold_small_slow_role',background_targets=0,unordered_ABC=0));continue
 own=lm[('OPPJOINT_K4',panel.building)];coarse=lm[('OPPJOINT_K3',panel.building)]
 D=panel.background_workers.split('|') if pd.notna(panel.background_workers) and panel.background_workers else []
 variable=panel.variable_workers.split('|');fast=[w for w in variable if own.get(w)==info['fast_class']];slow=[w for w in variable if own.get(w)==info['slow_class']]
 begin=bg_no;count_abc=0
 if len(fast)<2 or not slow:
  coverage.append(dict(panel_id=panel.panel_id,image=panel.image,building=panel.building,n=panel.n,status='no_complete_m1_ABC_in_fixed_variable_panel',background_targets=0,unordered_ABC=0,fast_variable_n=len(fast),slow_variable_n=len(slow)));continue
 for z in slow:
  for localD in combinations([w for w in variable if w!=z],5):
   available=sorted(set(fast)-set(localD))
   if len(available)<2:continue
   common=D+list(localD);assert len(common)==int(panel.n)-1
   mask=sum(bits[w] for w in common);ci=lookup[(panel.pool_id,mask|bits[z])]
   si=np.array([lookup[(panel.pool_id,mask|bits[w])] for w in available],dtype=int)
   used.add(ci);used.update(si);npairs=comb(len(si),2);count_abc+=npairs
   bgid=bg_no;bg_no+=1
   row=dict(background_target_id=bgid,panel_id=panel.panel_id,pool_id=panel.pool_id,image=panel.image,building=panel.building,
    n=int(panel.n),m=1,scope=panel.scope,difficulty=panel.difficulty,source_domain=panel.source_domain,
    D='|'.join(sorted(common)),Z=z,source_class=info['fast_class'],target_class=info['slow_class'],parent_class=info['parent_class'],
    source_workers='|'.join(available),source_team_keys='|'.join(keys[si]),C_team_key=keys[ci],
    A_B_parent_vector=vector(common+[available[0]],coarse),C_parent_vector=vector(common+[z],coarse),
    A_B_fine_vector=vector(common+[available[0]],own),C_fine_vector=vector(common+[z],own),
    fast_source_n=len(si),unordered_ABC=npairs,oriented_ABC=2*npairs)
   assert row['A_B_parent_vector']==row['C_parent_vector']
   backgrounds.append(row)
   pair_indices=list(combinations(range(len(si)),2))
   pair_rows += [dict(background_target_id=bgid,source_i=i,source_j=j) for i,j in pair_indices]
   for k,metric in enumerate(metrics):
    a=val[si,k];c=val[ci,k];valid=np.isfinite(a);v=a[valid]
    qpairs=comb(len(v),2) if len(v)>=2 and np.isfinite(c) else 0
    if qpairs:
     within=np.mean([abs(v[j]-v[i]) for i,j in combinations(range(len(v)),2)])
     cross=np.mean(np.abs(c-v));delta=c-v.mean();loss=float(np.mean((c-v)<-10)) if metric in ['B8L2','D10'] else np.nan
    else:within=cross=delta=loss=np.nan
    stat_rows.append(dict(background_target_id=bgid,metric=metric,time_source='not_time',
     valid_ABC=qpairs,all_ABC=npairs,same_abs=within,cross_abs=cross,gap=cross-within,
     CA=delta,CB=delta,BA=0.0 if qpairs else np.nan,delta_p10=float(np.quantile(c-v,.1)) if qpairs else np.nan,quality_loss10_fraction=loss))
   tk=np.isfinite(time[si])&timeok[si]&(kinds[si]==kinds[ci])&timeok[ci]&np.isfinite(time[ci])
   tv=time[si][tk];tpairs=comb(len(tv),2) if len(tv)>=2 else 0
   source=kinds[ci] if tpairs else 'time_unavailable'
   if tpairs:
    abswithin=np.mean([abs(tv[j]-tv[i]) for i,j in combinations(range(len(tv)),2)])
    abspct=np.mean([.5*(abs(tv[j]/tv[i]-1)+abs(tv[i]/tv[j]-1))*100 for i,j in combinations(range(len(tv)),2)])
    cross=np.abs(time[ci]-tv).mean();delta=time[ci]-tv.mean();pct=(time[ci]/tv-1)*100
    ba_pct=np.mean([.5*((tv[j]/tv[i]-1)+(tv[i]/tv[j]-1))*100 for i,j in combinations(range(len(tv)),2)])
   for metric in ['record_time_seconds','record_time_pct']:
    within=abswithin if metric=='record_time_seconds' and tpairs else abspct if tpairs else np.nan
    cc=cross if metric=='record_time_seconds' and tpairs else np.abs(pct).mean() if tpairs else np.nan
    dd=delta if metric=='record_time_seconds' and tpairs else pct.mean() if tpairs else np.nan
    stat_rows.append(dict(background_target_id=bgid,metric=metric,time_source=source,valid_ABC=tpairs,all_ABC=npairs,
     same_abs=within,cross_abs=cc,gap=cc-within,CA=dd,CB=dd,BA=0.0 if metric=='record_time_seconds' and tpairs else ba_pct if tpairs else np.nan,
     delta_p10=np.quantile(time[ci]-tv,.1) if metric=='record_time_seconds' and tpairs else np.quantile(pct,.1) if tpairs else np.nan))
   for metric in ['B8L2','D10','nonusable']:
    k=metrics.index(metric);v=val[si,k][tk];v=v[np.isfinite(v)];c=val[ci,k]
    qpairs=comb(len(v),2) if len(v)>=2 and np.isfinite(c) else 0
    within=np.mean([abs(v[j]-v[i]) for i,j in combinations(range(len(v)),2)]) if qpairs else np.nan
    cross=np.abs(c-v).mean() if qpairs else np.nan;delta=c-v.mean() if qpairs else np.nan
    stat_rows.append(dict(background_target_id=bgid,metric=metric+'_on_time_support',time_source=source,valid_ABC=qpairs,all_ABC=npairs,
     same_abs=within,cross_abs=cross,gap=cross-within,CA=delta,CB=delta,BA=0.0 if qpairs else np.nan,
     delta_p10=np.quantile(c-v,.1) if qpairs else np.nan))
 coverage.append(dict(panel_id=panel.panel_id,image=panel.image,building=panel.building,n=panel.n,status='complete_finite_m1_ABC',
  background_targets=bg_no-begin,unordered_ABC=count_abc,fast_variable_n=len(fast),slow_variable_n=len(slow)))
 print('panel',panel.panel_id,'background_targets',bg_no-begin,'ABC',count_abc,flush=True)

bg=pd.DataFrame(backgrounds);stat=pd.DataFrame(stat_rows);save(O/'COMMON_BACKGROUND_TARGETS.csv.gz',bg)
save(O/'EXACT_UNORDERED_ABC_SOURCE_PAIR_INDICES.csv.gz',pd.DataFrame(pair_rows))
save(O/'BACKGROUND_TARGET_METRICS.csv.gz',stat);save(O/'PANEL_OPPORTUNITY_AND_COVERAGE.csv',pd.DataFrame(coverage))
save(O/'USED_ENDPOINT_SCALARS_AND_MEMBERS.csv.gz',end.iloc[sorted(used)])
full=stat.merge(bg[['background_target_id','panel_id','pool_id','image','building','n','Z','source_domain','difficulty']],on='background_target_id',validate='many_to_one')
means=['same_abs','cross_abs','gap','CA','CB','BA','delta_p10']
imframes=[];summaries=[]
for axis in ['all','n','Z','difficulty','source_domain']:
 group=['metric','time_source']+([] if axis=='all' else [axis])
 valid=full[full.valid_ABC.gt(0)].copy()
 p=valid.groupby(group+['panel_id','pool_id','image','building'],dropna=False)[means].mean().reset_index()
 pool=p.groupby(group+['pool_id','image','building'],dropna=False)[means].mean().reset_index()
 im=pool.groupby(group+['image','building'],dropna=False)[means].mean().reset_index();im['summary_axis']=axis
 imframes.append(im)
 bu=im.groupby(group+['building'],dropna=False)[means].mean().reset_index()
 summary=bu.groupby(group,dropna=False)[means].mean().reset_index()
 counts=im.groupby(group,dropna=False).agg(images=('image','nunique'),buildings=('building','nunique'),
   images_CA_positive=('CA',lambda v:int(v.gt(1e-9).sum())),images_CA_negative=('CA',lambda v:int(v.lt(-1e-9).sum())),
   images_gap_positive=('gap',lambda v:int(v.gt(1e-9).sum()))).reset_index()
 summary=summary.merge(counts,on=group,validate='one_to_one');summary['summary_axis']=axis;summaries.append(summary)
save(O/'SMALL_SLOW_ROLE_IMAGE_RESULTS.csv.gz',pd.concat(imframes,ignore_index=True))
save(O/'SMALL_SLOW_ROLE_SUMMARY.csv',pd.concat(summaries,ignore_index=True))
result=dict(method='OPPJOINT_K4',parent='OPPJOINT_K3',direction='fast sibling to small slow sibling',m=1,
 panels=bg.panel_id.nunique(),images=bg.image.nunique(),buildings=bg.building.nunique(),background_target_cases=len(bg),
 unordered_ABC=len(pair_rows),unique_endpoints=len(used),new_fusions=0,
 target_workers=sorted(bg.Z.unique()),role_rule='fold slowest log-time class, <=6 persons and log-time center >=0.7; compare its unique same-parent sibling',
 complete_in_finite_panel=True,all_full_pool_combinations=False,
 XY_orientation='unordered source pair stored once; both A/B orientations have half weight; CA=CB in the exact symmetric mean',
 time_rule='full recorded totals available and the same single source for A/B/C; other totals unknown; quality on same time support also saved')
(O/'COMPLETE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
