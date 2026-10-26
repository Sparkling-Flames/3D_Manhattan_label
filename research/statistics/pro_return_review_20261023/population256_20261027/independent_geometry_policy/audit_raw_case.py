"""Recompute one reported low-k geometry case from saved native geometry, without fusion."""
import argparse,gzip,json,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--downloads',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
root=args.input_root;c=next((root/'analysis_geometry26/low_k_cases').iterdir());d=pd.read_csv(c/'CASE_ALL_PATHS_AND_ENDPOINTS.csv.gz');keys=set(d.team_key);geo={}
for p in args.downloads.glob('HOHONET_20261026_DATA_*.zip'):
 with zipfile.ZipFile(p) as z:
  for n in z.namelist():
   if 'yqstnuAEVhm-31' in n and n.endswith('geometry_compact.jsonl.gz'):
    for line in gzip.decompress(z.read(n)).splitlines():
     v=json.loads(line)
     if v['team_key'] in keys:geo[v['team_key']]=v
saved=pd.read_csv(c/'CASE_FULL_GEOMETRY_CURVE.csv.gz');out=[]
for cohort,batches in [('stage1_104',['extension_stage1_104']),('stage2_104',['extension_stage2_104']),('new208',['extension_stage1_104','extension_stage2_104'])]:
 e=d[d.batch.isin(batches)];assert all(k in geo for k in e.team_key)
 polys=[Polygon(geo[k]['geometry']['footprint']) for k in e.team_key];q=len(polys);mat=np.zeros((q,q))
 for a in range(q):
  for b in range(a):
   inter=polys[a].intersection(polys[b]).area;mat[a,b]=mat[b,a]=1-inter/(polys[a].area+polys[b].area-inter)
 value=mat.sum()/(q*(q-1));leave=np.array([np.delete(np.delete(mat,j,0),j,1).sum()/((q-1)*(q-2)) for j in range(q)]);se=np.sqrt((q-1)/q*((leave-leave.mean())**2).sum())
 row=saved[(saved.cohort==cohort)&(saved.k==5)&(saved.metric=='V_floor')].iloc[0]
 np.testing.assert_allclose([value,se],[row['mean'],row.mcse],rtol=1e-10,atol=1e-12)
 out.append(dict(cohort=cohort,paths=q,V=value,mcse=se,unique_teams=e.team_key.nunique(),lowQ=int((e.B8L2<10).sum()),Q=e.B8L2.mean(),P10=e.B8L2.quantile(.1)))
args.output.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(out).to_csv(args.output,index=False)
print(pd.DataFrame(out).to_string(index=False))
