from pathlib import Path
import pandas as pd,numpy as np,json,gzip,itertools,sys
from shapely.geometry import Polygon
r=Path(sys.argv[1]).resolve();data=r/'research/workers/personnel_population_curves_v2_20261023';pkg=data;out=r/'analysis_results/pro_return_review_20261023'
l=pd.read_csv(data/'results/PREFIX_TEAM_LINKS.csv.gz');o=pd.read_csv(data/'design/EXACT_ORDER_DESIGN.csv.gz');hard=set(o.loc[(o.difficulty=='困难')&(o.layer=='ordinary_manual')&(o.pool_n>=20),'pool_id'])
x=l[l.pool_id.isin(hard)&l.policy.eq('natural_random')&l.k.isin([10,20])]
need=set(x.team_key);geos={};decoder=json.JSONDecoder();buf='';count=0
with gzip.open(data/'results/ENDPOINT_GEOMETRY.json.gz','rt',encoding='utf8') as f:
 done=False
 while not done:
  chunk=f.read(1024*1024);done=not chunk;buf+=chunk;buf=buf.lstrip(' \r\n\t[,')
  while buf and not buf.startswith(']'):
   try:obj,pos=decoder.raw_decode(buf)
   except json.JSONDecodeError:
    assert not done;break
   count+=1
   if obj['team_key'] in need:geos[obj['team_key']]=obj
   buf=buf[pos:].lstrip(' \r\n\t,')
print("geometry_rows",count,"needed",len(need),"found",len(geos),flush=True);assert count==318616 and set(geos)==need
s=pd.read_csv(data/'results/ENDPOINT_SCALARS.csv.gz',usecols=['team_key','complete_floor_evaluable']);valid=set(s.loc[s.complete_floor_evaluable,'team_key'])
polygons={}
for k,g in geos.items():
 f=g.get('geometry',{}).get('footprint')
 if k in valid and f is not None:
  p=Polygon(f)
  if p.is_valid and p.area>0:polygons[k]=p
v=pd.read_csv(data/'results/PREFIX_GEOMETRY_VARIATION.csv.gz').set_index(['pool_id','policy','k']);rows=[]
for (pid,k),g in x.groupby(['pool_id','k']):
 p=[polygons[t] for t in g.team_key if t in polygons];values=[1-a.intersection(b).area/a.union(b).area for a,b in itertools.combinations(p,2)];mean=np.mean(values);saved=v.loc[(pid,'natural_random',k)]
 assert len(values)==saved.V_floor_valid_pairs
 assert abs(mean-saved.V_floor_mean)<1e-12
 rows.append(dict(pool_id=pid,k=k,valid_paths=len(p),pairs=len(values),V=mean,error=mean-saved.V_floor_mean))
pd.DataFrame(rows).to_csv(out/'GEOMETRY_58_GROUPS_RECOMPUTED.csv',index=False)
print('geometry',count,'groups',len(rows),'max_error',max(abs(z['error']) for z in rows),'pairs',sum(z['pairs'] for z in rows))
