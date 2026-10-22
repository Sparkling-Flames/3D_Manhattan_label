from pathlib import Path
import json
import numpy as np,pandas as pd
from concurrent.futures import ProcessPoolExecutor
from controls import geom,one
import recompute_baseline as base
ROOT=Path(__file__).resolve().parents[1]
def main():
 base.initialize();r=pd.read_csv(ROOT/'inputs/reference_catalog.csv');rows=[]
 for _,d in r.iterrows():
  cuts=json.loads(d.introduced_scope_edges) if isinstance(d.introduced_scope_edges,str) else []
  if not cuts or not d.full_reference_available:continue
  g=base.engine.geometry(json.loads(d.points_1024x512));b=np.asarray(g['bottom3d']);t=np.asarray(g['top3d']);p=b[:,[0,2]];h=t[:,1]-b[:,1];L=np.sqrt(__import__('shapely').geometry.Polygon(p).area)
  rows.append(dict(name=d.image_code+'_crop_self',family='actual_reference_derived_crop_control',provenance='approved full cropped reference; synthetic answer, not a worker',answer=g,reference=g,reference_id=d.target_id,introduced_scope_edges=cuts))
  for edge in cuts:
   for amplitude in [.00001,.001,.02,.1]:
    v=p[(edge+1)%len(p)]-p[edge];normal=np.array([-v[1],v[0]])/np.linalg.norm(v);q=p.copy();q[[edge,(edge+1)%len(p)]]+=amplitude*L*normal
    a=geom(q,h);rows.append(dict(name=d.image_code+f'_edge{edge}_move{amplitude}',family='actual_reference_derived_crop_control',provenance='fixed reference; synthetic displacement of one introduced edge and its joins',answer=a,reference=g,reference_id=d.target_id,introduced_scope_edges=cuts,displacement_side=amplitude))
 (ROOT/'inputs/crop_reference_controls.json').write_text(json.dumps(rows,ensure_ascii=False,allow_nan=False))
 with ProcessPoolExecutor(max_workers=4,initializer=base.initialize) as pool:res=list(pool.map(one,rows,chunksize=4))
 pd.DataFrame(res).to_csv(ROOT/'results/crop_reference_controls.csv',index=False)
 (ROOT/'results/crop_reference_control_summary.json').write_text(json.dumps(dict(reference_count=6,controls=len(rows),status_counts=pd.Series([x['EBC2_status'] for x in res]).value_counts().to_dict()),indent=2))
 print((ROOT/'results/crop_reference_control_summary.json').read_text())
if __name__=='__main__':main()
