"""Fixed-membership-block nested path audit; original reference and metrics kept."""
from pathlib import Path
import pandas as pd,numpy as np,json,gzip,hashlib
B=Path('/workspace/shared/interchangeability_audit_20261020');D=B/'audit_corner/fresh_blocks';O=B/'audit_statistics/fresh_curves';O.mkdir(exist_ok=True)
e=pd.read_csv(D/'CORNER_EVENTS.csv.gz',low_memory=False);pts=pd.read_csv(D/'CORNER_POINTS.csv.gz',low_memory=False);pairs=pd.read_csv(D/'CORNER_PAIRS.csv.gz',low_memory=False);q=json.load(gzip.open(B/'audit_learning/fresh_blocks/fresh_block_requests.json.gz','rt'));mp={z['event_id']:z for z in q['events']};assert set(e.event_id)==set(mp) and e.event_id.is_unique
assert np.allclose(pts.bev_h,np.hypot(pts.dx_h,pts.dz_h),atol=1e-9);assert np.allclose(pts.top_h,np.sqrt(pts.dx_h**2+pts.dz_h**2+pts.height_change_h**2),atol=1e-9)
e['path_id']=e.event_id.map(lambda x:mp[x]['nested_group_id']);assert (e.k==e.event_id.map(lambda x:mp[x]['n'])).all()
metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pairscale','top_max_pairscale','bev_max_local_radius_fraction','top_max_local_radius_fraction','abs_B8L2_change']
rows=[]
for pid,g in e.groupby('path_id'):
 g=g.sort_values('k');r={x:g.iloc[0][x] for x in ['method_id','direction','m','pool_id','image_id','building']};r.update(path_id=pid,observed_n=len(g),n_min=g.k.min(),n_max=g.k.max(),all_n5_to17=set(g.k)==set(range(5,18)),joint_distance_nodes=int(g.both_available.sum()))
 for arm in ['within','cross']:
  r[arm+'_different_count_nodes']=int((g[arm+'_status']=='different_corner_count').sum());r[arm+'_noncomplete_nodes']=int((~g[arm+'_complete']).sum());r[arm+'_any_structural_break']=bool((g[arm+'_status']!='unique_cyclic_candidate').any())
  for flag in ['joint_stable_main','geometry_shape_main']:
   r[arm+'_'+flag+'_all_n']=bool(g[arm+'_'+flag].all()) if r['all_n5_to17'] else np.nan
  r[arm+'_angle_max_deg']=g[arm+'_angle_deg'].max()
 r['common_full_curve']=r['all_n5_to17'] and g.both_available.all()
 r['common_full_curve_angle9']=r['common_full_curve'] and max(r['within_angle_max_deg'],r['cross_angle_max_deg'])<=9
 r['common_full_curve_angle12']=r['common_full_curve'] and max(r['within_angle_max_deg'],r['cross_angle_max_deg'])<=12
 for m in metrics:
  # Both arms and every n are required for a full curve comparison, per metric.
  ok=r['all_n5_to17'] and g[['within_'+m,'cross_'+m]].notna().all().all()
  r[m+'_full_curve_available']=ok
  for arm in ['within','cross']:
   x=g[arm+'_'+m].to_numpy()
   for label,val in [('mean',np.mean(x)),('max',np.max(x)),('integrated_mean',np.trapezoid(x,g.k.to_numpy())/12)]:
    r[arm+'_'+m+'_curve_'+label]=float(val) if ok else np.nan
  for label in ['mean','max','integrated_mean']:
   r['delta_'+m+'_curve_'+label]=r['cross_'+m+'_curve_'+label]-r['within_'+m+'_curve_'+label] if ok else np.nan
 rows.append(r)
f=pd.DataFrame(rows);f.to_csv(O/'PER_PATH_CURVE_EVIDENCE.csv',index=False);s=[];rng=np.random.default_rng(20261020);keys=['method_id','direction','m']
for k,g in f.groupby(keys):
 base=dict(zip(keys,k));base.update(paths=len(g),images=g.image_id.nunique(),buildings=g.building.nunique(),full_n_paths=int(g.all_n5_to17.sum()),capacity_truncated_paths=int((~g.all_n5_to17).sum()),full_common_distance_paths=int(g.common_full_curve.sum()),full_common_angle9_paths=int(g.common_full_curve_angle9.sum()),full_common_angle12_paths=int(g.common_full_curve_angle12.sum()))
 for gate in ['full_n_attempts','common_full_curve','common_full_curve_angle9','common_full_curve_angle12']:
  z=g[g.all_n5_to17] if gate=='full_n_attempts' else g[g[gate]]
  if gate=='full_n_attempts':cols=[c for c in f if c.endswith('_all_n') or c.endswith('_any_structural_break')]
  else:cols=[c for c in f if '_curve_' in c and not c.endswith('_available')]
  bb=z.groupby(['building','image_id'])[cols].mean().groupby('building').mean()
  for c in cols:
   x=bb[c].dropna().to_numpy();dist=x[rng.integers(0,len(x),(50000,len(x)))].mean(axis=1) if len(x)>=3 else np.array([np.nan])
   s.append(dict(base,gate=gate,eligible_paths=len(z),eligible_images=z.image_id.nunique(),eligible_buildings=len(x),metric=c,estimate=x.mean() if len(x) else np.nan,ci025=np.quantile(dist,.025),ci975=np.quantile(dist,.975),positive_buildings=int((x>1e-9).sum()),negative_buildings=int((x< -1e-9).sum()),event_path_positive_fraction=float((z[c].dropna()>1e-9).mean()) if len(z[c].dropna()) else np.nan))
pd.DataFrame(s).to_csv(O/'CURVE_BUILDING_SUMMARY.csv',index=False)
receipt=dict(events=len(e),nested_paths=len(f),full_n5to17_paths=int(f.all_n5_to17.sum()),capacity_truncated_paths=int((~f.all_n5_to17).sum()),both_arms_all_n_distance_valid_paths=int(f.common_full_curve.sum()),curve_integral='trapezoid over integer n5..17 divided by12; per-path max/mean also retained',denominators='All attempted paths and structural breaks retained. Fullcurve distance comparisons require all13n and botharms finite; partial paths never substituted or interpolated.',interpretation='Class-specific curves are conditional own-class designs, not fair head-to-head method ranking. Curves share fixed blocks and nested core; no extra independent samples from13n.')
(O/'CURVE_AUDIT_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
