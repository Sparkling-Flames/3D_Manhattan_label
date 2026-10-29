"""Member/background repetition and scope-aware comparisons for the frozen focus.
No new fitting, quality evaluation, fusion, or endpoint selection occurs here.
"""
import argparse,itertools
from pathlib import Path
import numpy as np
import pandas as pd
from measure_registered_events import save,jsave
from summarize_registered_screen import add_roles,CORE,summarize

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--metrics',required=True);ap.add_argument('--roles',required=True);ap.add_argument('--frame',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 d=add_roles(pd.read_csv(a.metrics,low_memory=False),pd.read_csv(a.roles,low_memory=False))
 f=pd.read_csv(a.frame); f=f[f.selected.astype(str).str.lower().isin(['true','1','1.0'])]
 d['screen_support']=np.where(~d.building.isin(set(f.building)),'outside_screen_building',np.where(~d.pool_id.isin(set(f.pool_id)),'outside_screen_pool_same_building','screen_pool'))
 metrics=[c for c in CORE if c in d]; keys=['method','condition','scope','role_direction','n','m']
 for part in ['screen_support','official_difficulty','geometric_challenge']:
  s,p,im,b=summarize(d,keys+[part],metrics)
  save(out/(part.upper()+'_SUMMARY.csv.gz'),s);save(out/(part.upper()+'_BY_IMAGE.csv.gz'),im)
 # Count actual member/background sets, never use event count as independent n.
 rows=[]
 for kk,g in d.groupby(keys+['pool_id','image','building'],dropna=False):
  r=dict(zip(keys+['pool_id','image','building'],kk));r.update(events=len(g),XYZ_blocks=g.block_id.nunique(),backgrounds=g.background_id.nunique(),source_X_sets=g.X.nunique(),source_Y_sets=g.Y.nunique(),target_Z_sets=g.Z.nunique(),background_target_min=g.background_target_n.min(),background_target_max=g.background_target_n.max(),source_capacity=g.source_capacity.iloc[0],target_capacity=g.target_capacity.iloc[0],pool_n=g.pool_n.iloc[0])
  r['unique_endpoint_teams']=len(set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key))
  for m in ['B8L2_gap','B8L2_CA','B8L2_CB','geometry_bev_distance_gap','fusion_turn_n_CA','record_time_CB_pct_source_matched']:
   x=g[m].dropna();r.update({m+'_valid_events':len(x),m+'_mean':x.mean(),m+'_positive_fraction':(x>0).mean() if len(x) else np.nan,m+'_p10':x.quantile(.1),m+'_median':x.median(),m+'_p90':x.quantile(.9),m+'_std':x.std() if len(x)>1 else np.nan})
  for arm in 'ABC':r[arm+'_failed_events']=int(g[arm+'_failed'].sum())
  rows.append(r)
 v=pd.DataFrame(rows);save(out/'MEMBER_BACKGROUND_STABILITY_BY_POOL.csv.gz',v)
 vals=[c for c in v if c.endswith(('_mean','_positive_fraction','_std'))]
 im=v.groupby(keys+['image','building'],dropna=False)[vals].mean().reset_index()
 sums=im.groupby(keys,dropna=False)[vals].mean().add_suffix('_mean_image').reset_index()
 save(out/'MEMBER_BACKGROUND_STABILITY_SUMMARY.csv',sums)
 # Exact same XYZ, same n/m: compare actual low versus high target background.
 pairs=[]
 for _,g in d.groupby(['method','pool_id','n','m','source_class','target_class','block_id'],dropna=False):
  lo,hi=g.background_target_n.min(),g.background_target_n.max()
  if lo==hi:continue
  for (_,l),(_,h) in itertools.product(g[g.background_target_n==lo].iterrows(),g[g.background_target_n==hi].iterrows()):
   r={k:l[k] for k in keys+['pool_id','image','building','source_class','target_class','block_id','official_difficulty','geometric_challenge']}
   assert l.X==h.X and l.Y==h.Y and l.Z==h.Z
   r.update(lower_event_id=l.event_id,higher_event_id=h.event_id,lower_background_id=l.background_id,higher_background_id=h.background_id,D_low=l.D,D_high=h.D,X=l.X,Y=l.Y,Z=l.Z,target_seats_D_low=lo,target_seats_D_high=hi,D_members_changed=len(set(str(l.D).split('|'))-set(str(h.D).split('|'))))
   ok=all(pd.notna(x) for x in [l.B_B8L2,h.B_B8L2,l.C_B8L2,h.C_B8L2]);ok6=ok and pd.notna(l.A_B8L2) and pd.notna(h.A_B8L2)
   for arm in 'ABC':
    r[arm+'_Q_change']=h[arm+'_B8L2']-l[arm+'_B8L2'];r[arm+'_Q_change_matched_ABC']=r[arm+'_Q_change'] if ok6 else np.nan
   r['C_Q_change_matched_CB']=r['C_Q_change'] if ok else np.nan;r['B_Q_change_matched_CB']=r['B_Q_change'] if ok else np.nan
   r['net_CB_Q_change_matched_CB']=h.B8L2_CB-l.B8L2_CB if ok else np.nan
   for c in ['B8L2_gap','B8L2_CA','B8L2_CB','geometry_bev_distance_gap','fusion_turn_n_CA','record_time_CB_pct_source_matched']:r[c+'_change']=h[c]-l[c]
   for arm in 'ABC':r[arm+'_new_failure']=float(h[arm+'_failed']) if not l[arm+'_failed'] else np.nan
   pairs.append(r)
 pp=pd.DataFrame(pairs);save(out/'FIXED_XYZ_BACKGROUND_CONTRASTS.csv.gz',pp)
 if len(pp):
  mm=[c for c in pp if c.endswith(('_change','_matched_CB','_matched_ABC','_new_failure'))]
  p=pp.groupby(keys+['pool_id','image','building'],dropna=False)[mm].mean().reset_index();im=p.groupby(keys+['image','building'],dropna=False)[mm].mean().reset_index();b=im.groupby(keys+['building'],dropna=False)[mm].mean().reset_index()
  g=im.groupby(keys,dropna=False);s=g[mm].mean().add_suffix('_mean_image').join(g[mm].count().add_suffix('_valid_images')).reset_index()
  save(out/'FIXED_XYZ_BACKGROUND_BY_IMAGE.csv.gz',im);save(out/'FIXED_XYZ_BACKGROUND_BY_BUILDING.csv.gz',b);save(out/'FIXED_XYZ_BACKGROUND_SUMMARY.csv',s)
 # Structure alternatives on the same actual target pools, role 2 -> 3.
 dd=d[(d.method.isin(['DSTRUCT_K3','TARGET_DSTRUCT_K3','OPPSTRUCT_K3']))&(d.role_source_rank==2)&(d.role_target_rank==3)]
 p=dd.groupby(['method','pool_id','image','building','n','m'])[metrics].mean().reset_index();paired=[]
 for x,y in itertools.combinations(sorted(p.method.unique()),2):
  z=p[p.method==x].merge(p[p.method==y],on=['pool_id','image','building','n','m'],suffixes=('_x','_y'))
  for (n,m),gg in z.groupby(['n','m']):
   r=dict(method_x=x,method_y=y,n=n,m=m,pools=len(gg),images=gg.image.nunique(),buildings=gg.building.nunique())
   for c in metrics:
    ok=gg[c+'_x'].notna()&gg[c+'_y'].notna();a=gg.loc[ok,['image','building',c+'_x',c+'_y']].groupby(['image','building']).mean()
    r[c+'_x']=a[c+'_x'].mean();r[c+'_y']=a[c+'_y'].mean();r[c+'_difference_y_minus_x']=(a[c+'_y']-a[c+'_x']).mean();r[c+'_paired_images']=len(a)
   paired.append(r)
 save(out/'STRUCTURE_METHODS_SAME_POOLS.csv',pd.DataFrame(paired))
 jsave(out/'COMPLETE.json',dict(events=len(d),pools=d.pool_id.nunique(),images=d.image.nunique(),buildings=d.building.nunique(),fixed_XYZ_background_pairs=len(pp),
  context='screen support marks membership of the pre-outcome global frame; no new external blind-validation claim',new_fusion=0,member_variability='counts of distinct actual XYZ blocks, D and endpoints; within-pool effect distributions; no independent-event assumption'))
 print('complete',len(d),len(pp),flush=True)

if __name__=='__main__':main()
