import json,csv,sys,platform
from pathlib import Path
import numpy as np,scipy,shapely
from geometry_core import *
from snapshot_synthetic import generate
from real_inputs import get
BASE=Path(__file__).resolve().parents[1]
def savecsv(name,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with (BASE/'results'/name).open('w',newline='') as f:
  d=csv.DictWriter(f,fields);d.writeheader();d.writerows(rows)
def measure(a,b):
 ga,gb=reconstruct(a),reconstruct(b);o={}
 if not ga['reason'] and not gb['reason']:o.update(polygon_metrics(ga['floor'],gb['floor']))
 else:o['bev_reason']=str(ga['reason'])+';'+str(gb['reason'])
 for w in (512,1024):
  try:
   ma,mb=column_mask(ga,w),column_mask(gb,w);o[f'column_iou_{w}']=iou(ma,mb);o[f'diff_pixels_{w}']=int((ma^mb).sum())
  except ValueError as err:o[f'column_reason_{w}']=str(err)
 return o
if __name__=='__main__':
 cases=generate();out=[]
 for c in cases:
  r={k:c[k] for k in ['family','case','amplitude']};r.update(measure(c['a'],c['b']));out.append(r)
 savecsv('snapshot_74_independent.csv',out)
 (BASE/'inputs/synthetic_74.json').write_text(json.dumps(cases,indent=2))
 real=get();outreal=[]
 refs=[(.8280505888014369,.9582612376447174),(.5905516359376128,.8945292542864733),(.534505707440384,.9492266043606709)]
 for (a,b),(ri,rc) in zip(real,refs):
  r=dict(image=a['image'],a=a['id'],b=b['id'],**measure(a,b));r.update(reported_bev=ri,reported_column=rc,diff_bev=r['bev_iou']-ri,diff_column=r['column_iou_1024']-rc);outreal.append(r)
 savecsv('real_recomputed.csv',outreal)
 (BASE/'inputs/real_excerpts.json').write_text(json.dumps(real,indent=2))
 (BASE/'logs/environment.json').write_text(json.dumps(dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,shapely=shapely.__version__,commit='10a0fe54608f62668f73d705d6a0cf50a9179f21',scope='independent formula reimplementation, 74 generated contrasts and 3 supplied real reference comparisons; NOT original full verifier'),indent=2))
 print('synthetic',len(out),'real',len(outreal));print(json.dumps(outreal,indent=2))
