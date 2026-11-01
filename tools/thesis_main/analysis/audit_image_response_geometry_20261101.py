from pathlib import Path
import pandas as pd,numpy as np,json,math,shapely
from shapely.geometry import Polygon
BASE=Path(__file__).resolve().parents[3]/'research/workers/image_response_v21_20261101'
ROOT=BASE/'HOHONET_v21_image_response_20261101'
OUT=BASE/'audit_geometry'
u=pd.read_csv(ROOT/'stage04_geometry/doorway_exact_U/GEOMETRY_U_CURVES.csv.gz')
w=pd.read_csv(ROOT/'stage04_geometry/doorway_exact_U/PATH_STATE_MULTIPLICITIES.csv.gz')
idx=pd.read_csv(ROOT/'stage02_normalized/doorway/POOL_INDEX.csv')
checks=[];samples=[]
# All floor pair denominators recomputed independently from saved multiplicities.
for (pid,k),g in w.groupby(['pool_id','k']):
 assert int(g.path_multiplicity.sum())==256
 good=g[g.floor_valid_for_pair];n=int(good.path_multiplicity.sum());den=n*(n-1)//2
 r=u[(u.pool_id==pid)&(u.k==k)&u.metric.eq('floor_distance')].iloc[0]
 assert r.valid_paths==n and r.valid_path_pairs==den
 assert r.within_identical_state_zero_pairs==sum(int(x)*(int(x)-1)//2 for x in good.path_multiplicity)
 checks.append((pid,int(k),n,den))
for image,ii in idx.groupby('image'):
 cat=pd.read_csv(ROOT/f'stage02_normalized/doorway_enriched/geometry/{image}.csv.gz');cat=cat[cat.k>=3].reset_index(drop=True)
 poly={}
 for row in ii.itertuples():
  if row.family not in ['overall_after','overall_before']:continue
  # Sample both versions at k14 and screened early/full conditions.
  ks={14} if row.family=='overall_before' else {3,14,int(row.N)}
  for k in sorted(ks):
   g=w[(w.pool_id==row.pool_id)&(w.k==k)&w.floor_valid_for_pair]
   if g.empty:continue
   ids=g.catalog_index.to_numpy(int);mult=g.path_multiplicity.to_numpy(int)
   for i in ids:
    if i not in poly:poly[i]=Polygon(json.loads(cat.loc[i,'footprint_json']))
   # Direct 256 path-index expansion independently of author's state-weighted formula.
   arr=np.array([poly[i] for i,m in zip(ids,mult) for _ in range(m)],dtype=object)
   a,b=np.triu_indices(len(arr),1)
   if len(a):
    inter=shapely.area(shapely.intersection(arr[a],arr[b]));union=shapely.area(arr[a])+shapely.area(arr[b])-inter
    dist=np.clip(1-inter/union,0,1);val=float(dist.mean())
   else:val=float('nan')
   ref=u[(u.pool_id==row.pool_id)&(u.k==k)&u.metric.eq('floor_distance')].iloc[0]
   assert np.isclose(val,ref['mean'],atol=1e-6,rtol=0,equal_nan=True),(row.pool_id,k,val,ref['mean'])
   samples.append(dict(pool_id=row.pool_id,k=k,valid_paths=len(arr),pairs=len(a),recomputed=val,saved=ref['mean']))
 print(image,'sample cells',len(samples),flush=True)
# Reaggregate key fixed-k screening geometry comparison.
f=u[u.metric.eq('floor_distance') & u.k.eq(14)];a=f[f.family.eq('overall_after')].set_index('image')['mean'];b=f[f.family.eq('overall_before')].set_index('image')['mean'];delta=(a-b).dropna()
pd.DataFrame(samples).to_csv(OUT/'GEOMETRY_DIRECT_PAIR_CHECKS.csv',index=False)
result=dict(denominator_cells=len(checks),direct_geometry_cells=len(samples),direct_geometry_pairs=sum(x['pairs'] for x in samples),max_abs_error=max(abs(x['recomputed']-x['saved']) for x in samples),screen14_images=len(delta),screen14_mean=float(delta.mean()),screen14_down=int((delta< -1e-12).sum()),screen14_up=int((delta>1e-12).sum()),screen14_same=int((delta.abs()<=1e-12).sum()))
(OUT/'CHECKS.json').write_text(json.dumps(result,indent=2));print(result)
