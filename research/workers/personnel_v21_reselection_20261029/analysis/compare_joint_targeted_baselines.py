"""Fixed n12/m6 support, compare the selected fine role to its actual K3 parent
and Q median split. Parent roles are mapped from frozen labels, not chosen using
the strongest K3 outcome. Common-label block support is reported separately.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from measure_registered_events import save,jsave
from summarize_registered_screen import CORE

w=Path(__file__).resolve().parents[1];out=w/'analysis/joint_baseline_comparison';out.mkdir(parents=True,exist_ok=True)
f=pd.read_csv(w/'analysis/focused/EVENT_METRICS.csv.gz',low_memory=False)
f=f[(f.method=='OPPJOINT_K4')&(f.n==12)&(f.m==6)].copy()
b=pd.read_csv(w/'analysis/refinement_baseline/EVENT_METRICS.csv.gz',low_memory=False)
h=pd.read_csv(w/'analysis/global_parent_links/METHOD_HIERARCHY_ALL_LOBO.csv')
h=h[(h.child_method=='OPPJOINT_K4')&(h.parent_method=='OPPJOINT_K3')]
mapping={(r.heldout_building,r.child_class):r.parent_classes for r in h.itertuples()}
target=f[['pool_id','heldout_building','source_class','target_class']].drop_duplicates()
target['parent_source']=[mapping[(x,y)] for x,y in zip(target.heldout_building,target.source_class)]
target['parent_target']=[mapping[(x,y)] for x,y in zip(target.heldout_building,target.target_class)]
assert target.pool_id.is_unique
q=b[b.method=='Q_MEDIAN2'].copy();q['comparison_method']='Q_MEDIAN2_low_to_high'
c=b[b.method=='OPPJOINT_K3'].merge(target[['pool_id','parent_source','parent_target']],on='pool_id')
c=c[c.source_class.eq(c.parent_source)&c.target_class.eq(c.parent_target)].copy();c['comparison_method']='OPPJOINT_K3_exact_parent_direction'
f['comparison_method']='OPPJOINT_K4_selected_direction'
d=pd.concat([f,c,q],ignore_index=True)
labels=pd.read_csv(w/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',usecols=['method','heldout_building','worker_id','known'],low_memory=False)
known={k:set(g.worker_id) for k,g in labels[(labels.method=='OPPJOINT_K4')&labels.known.astype(str).str.lower().isin(['true','1'])].groupby('heldout_building')}
d['all_replacement_blocks_have_joint_history']=[set(str(x).split('|')+str(y).split('|')+str(z).split('|')).issubset(known[fold]) for x,y,z,fold in zip(d.X,d.Y,d.Z,d.heldout_building)]
metrics=[m for m in CORE if m in d]
outputs=[];pairrows=[]
for support,dd in [('same_target_pool',d),('same_pool_and_joint_known_blocks',d[d.all_replacement_blocks_have_joint_history])]:
 p=dd.groupby(['comparison_method','pool_id','image','building'])[metrics].mean().reset_index()
 counts=dd.groupby(['comparison_method','pool_id']).size().rename('events').reset_index();p=p.merge(counts,on=['comparison_method','pool_id'])
 methods=p.comparison_method.unique();common=set.intersection(*(set(p[p.comparison_method==x].pool_id) for x in methods));p=p[p.pool_id.isin(common)]
 im=p.groupby(['comparison_method','image','building'])[metrics].mean().reset_index();bl=im.groupby(['comparison_method','building'])[metrics].mean().reset_index()
 for method,g in im.groupby('comparison_method'):
  rr=dict(support=support,comparison_method=method,pools=len(common),images=len(g),buildings=g.building.nunique(),events=int(dd[(dd.comparison_method==method)&dd.pool_id.isin(common)].shape[0]))
  bg=bl[bl.comparison_method==method]
  for m in metrics:
   xx=g[m].dropna();yy=bg[m].dropna();rr[m+'_mean_image']=xx.mean();rr[m+'_valid_images']=len(xx);rr[m+'_positive_images']=int((xx>0).sum());rr[m+'_mean_building']=yy.mean();rr[m+'_positive_buildings']=int((yy>0).sum());rr[m+'_valid_buildings']=len(yy)
  outputs.append(rr)
 for other in ['OPPJOINT_K3_exact_parent_direction','Q_MEDIAN2_low_to_high']:
  z=p[p.comparison_method=='OPPJOINT_K4_selected_direction'].merge(p[p.comparison_method==other],on=['pool_id','image','building'],suffixes=('_K4','_other'))
  for r in z.to_dict('records'):
   rr=dict(support=support,other=other,pool_id=r['pool_id'],image=r['image'],building=r['building'])
   for m in metrics:rr[m+'_K4']=r[m+'_K4'];rr[m+'_other']=r[m+'_other'];rr[m+'_difference_K4_minus_other']=r[m+'_K4']-r[m+'_other']
   pairrows.append(rr)
save(out/'EXACT_PARENT_DIRECTIONS_BY_POOL.csv',target)
save(out/'ALL_TARGETED_BASELINE_EVENT_LINKS.csv.gz',d[['event_id','comparison_method','pool_id','image','building','method','n','m','source_class','target_class','X','Y','Z','D','A_team_key','B_team_key','C_team_key','all_replacement_blocks_have_joint_history']])
save(out/'SAME_SUPPORT_COMPARISON.csv',pd.DataFrame(outputs));save(out/'PAIRED_BY_POOL.csv.gz',pd.DataFrame(pairrows))
jsave(out/'COMPLETE.json',dict(fine_events=len(f),exact_parent_events=len(c),Q_baseline_events=len(q),fine_pools=f.pool_id.nunique(),parent_pools=c.pool_id.nunique(),Q_pools=q.pool_id.nunique(),
 common_history_block_events=d.groupby('comparison_method').all_replacement_blocks_have_joint_history.agg(['sum','count']).to_dict('index'),
 interpretation='Same actual target pools and n/m; each method uses its own prespecified member draws. Not a claim of identical individual teams across methods. Actual K3 parent mapped before outcomes; no best-of-two K3 selection.',new_fusion=0))
print(pd.DataFrame(outputs)[['support','comparison_method','images','B8L2_within_mean_image','B8L2_cross_mean_image','B8L2_gap_mean_image','B8L2_CB_mean_image']].to_string(index=False),flush=True)
