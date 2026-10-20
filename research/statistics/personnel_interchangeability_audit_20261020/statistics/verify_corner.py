"""Independent continuous-corner table validator and building bootstrap.
No imported research code, no threshold fitting, no raw geometry regeneration.
"""
from pathlib import Path
import argparse,json,hashlib
import pandas as pd,numpy as np
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
e=pd.read_csv(a.input/'CORNER_EVENTS.csv.gz');pair=pd.read_csv(a.input/'CORNER_PAIRS.csv.gz');pts=pd.read_csv(a.input/'CORNER_POINTS.csv.gz');rng=np.random.default_rng(20261020)
eventkeys=[x for x in ['source','replay_group','event_id'] if x in e];assert not e.duplicated(eventkeys).any();assert len(pair)==2*len(e)
pts['recomputed_bev']=np.hypot(pts.dx_h,pts.dz_h);pts['recomputed_top']=np.sqrt(pts.dx_h**2+pts.dz_h**2+pts.height_change_h**2)
point_error=max((pts.recomputed_bev-pts.bev_h).abs().max(),(pts.recomputed_top-pts.top_h).abs().max());assert point_error<1e-9
mxerr=0.;rows=0
for key,g in pts.groupby(eventkeys+['arm'],dropna=False):
 mask=pd.Series(True,index=pair.index)
 for col,val in zip(eventkeys+['arm'],key):mask &= pair[col].isna() if pd.isna(val) else pair[col].eq(val)
 z=pair[mask];assert len(z)==1;z=z.iloc[0];assert z.status=='unique_cyclic_candidate'
 for metric in ['bev','top']:
  for func in ['mean','max']:
   err=abs(getattr(g['recomputed_'+metric],func)()-z[metric+'_'+func+'_h']);mxerr=max(mxerr,err);assert err<1e-9
 rows+=1
valid=(e.within_status=='unique_cyclic_candidate')&(e.cross_status=='unique_cyclic_candidate');assert (valid==e.both_available).all()
for arm in ['within','cross']:
 for col in ['bev_mean_h','bev_max_h','top_mean_h','top_max_h']:
  assert e.loc[e[arm+'_status']!='unique_cyclic_candidate',arm+'_'+col].isna().all()
strata=[c for c in ['source','replay_group','method_id','domain','context_id','phase','k','m','direction'] if c in e];out=[];support=[];build=[]
metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pairscale','top_max_pairscale','bev_max_local_radius_fraction','top_max_local_radius_fraction']
for key,g in e.groupby(strata,dropna=False):
 base=dict(zip(strata,key));base.update(attempts=len(g),attempted_images=g.image.nunique(),attempted_buildings=g.building.nunique())
 for arm in ['within','cross']:
  for status,n in g[arm+'_status'].value_counts(dropna=False).items():support.append(dict(base,arm=arm,status=status,count=int(n)))
 for gate in ['all_common','angle_le_9','angle_le_12']:
  z=g[g.both_available].copy()
  if gate!='all_common':
   cut=float(gate.split('_')[-1]);z=z[(z.within_angle_deg<=cut)&(z.cross_angle_deg<=cut)].copy()
  meta=dict(base,gate=gate,eligible_events=len(z),eligible_images=z.image.nunique(),eligible_buildings=z.building.nunique())
  for m in metrics:
   z['delta_'+m]=z['cross_'+m]-z['within_'+m]
   z['cross_larger_'+m]=(z['delta_'+m]>1e-9).astype(float)
   b=z.groupby(['building','image'])[ ['within_'+m,'cross_'+m,'delta_'+m,'cross_larger_'+m] ].mean().groupby('building').mean()
   for name in b:
    v=b[name].dropna().to_numpy();dist=v[rng.integers(0,len(v),(50000,len(v)))].mean(axis=1) if len(v)>=3 else np.array([np.nan]);out.append(dict(meta,metric=name,uncertainty_status='descriptive_only' if len(v)>=3 else 'fewer_than_three_buildings_no_interval',estimate=float(v.mean()) if len(v) else np.nan,ci025=np.quantile(dist,.025),ci975=np.quantile(dist,.975),event_p10=z[name].quantile(.1),event_median=z[name].median(),event_p90=z[name].quantile(.9),raw_event_cross_larger_fraction=float((z['delta_'+m]>1e-9).mean()) if len(z) else np.nan,positive_buildings=int((v>1e-9).sum()),negative_buildings=int((v< -1e-9).sum()),equal_buildings=int((abs(v)<=1e-9).sum())))
    for building,val in b[name].items():build.append(dict(meta,metric=name,building=building,estimate=val))
  # Old/new flags compare all attempt denominator separately from distance-common subset.
  for denom,zz in [('all_attempts',g),('common_correspondence',z)]:
   for arm in ['within','cross']:
    for flag in ['joint_stable_main','geometry_shape_main']:
     vals=zz.groupby(['building','image'])[arm+'_'+flag].mean().groupby('building').mean()
     out.append(dict(meta,metric=arm+'_'+flag,flag_denominator=denom,flag_events=len(zz),estimate=vals.mean()))
pd.DataFrame(out).to_csv(a.output/'CORNER_INDEPENDENT_BOOTSTRAP.csv',index=False);pd.DataFrame(support).to_csv(a.output/'CORNER_INDEPENDENT_STATUS.csv',index=False);pd.DataFrame(build).to_csv(a.output/'CORNER_INDEPENDENT_BUILDINGS.csv',index=False)
r=dict(events=len(e),pairs=len(pair),points=len(pts),joint_eligible=int(valid.sum()),pointwise_formula_max_error=float(point_error),perarm_aggregate_max_error=float(mxerr),validated_pairs_with_points=rows,all_unavailable_continuous_values_null=True,bootstrap_replicates=50000,seed=20261020,interpretation='Descriptive cluster resampling conditional on selected cases/core and observed buildings; no external validity or threshold tuning',inputs={f:hashlib.sha256((a.input/f).read_bytes()).hexdigest() for f in ['CORNER_EVENTS.csv.gz','CORNER_PAIRS.csv.gz','CORNER_POINTS.csv.gz']})
(a.output/'CORNER_STATISTICS_RECEIPT.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
