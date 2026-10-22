from pathlib import Path
import sys,json,numpy as np
P=Path('/workspace/scratch/81fa50cc64f5/new_pro_return/panorama_quality_three_routes_20261016');sys.path.insert(0,str(P/'src'))
from geomscore import *
from run_controls import geom
square=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float)
rows=[]
for shear in [.3,.5,.7,1.,1.5,2.]:
 p=square@np.array([[1.,0.],[shear,1.]])
 base=score_pair(geom(p),geom(square))
 for n in [4,6,8,10,12,16,20]:
  # Replace BOTH slanted side edges by an exact orthogonal staircase, leaving the same major endpoints.
  result=[]
  for idx,a in enumerate(p):
   b=p[(idx+1)%len(p)];result.append(a.tolist())
   if abs(b[0]-a[0])>1e-9 and abs(b[1]-a[1])>1e-9:
    dx,dz=(b-a)/n
    for k in range(n):
     result.append([float(a[0]+(k+1)*dx),float(a[1]+k*dz)])
     if k+1<n:result.append([float(a[0]+(k+1)*dx),float(a[1]+(k+1)*dz)])
  q=np.array(result);score=score_pair(geom(q),geom(square));row=dict(shear=shear,steps=n,base=p.tolist(),stair=q.tolist(),base_score=base,stair_score=score);rows.append(row)
  print(shear,n,'I',round(base['I'],4),round(score['I'],4),'QA',round(base['QA'],3),round(score['QA'],3),'angle',round(base['angle_detail']['angle_penalty'],3),round(score['angle_detail']['angle_penalty'],3),'struct',round(score['angle_detail']['structural_loss'],3),'counts',[(x['nA'],x['matched']) for x in score['angle_detail']['event_scales']])
Path('/workspace/scratch/81fa50cc64f5/new_pro_audit/angle_escape_probe.json').write_text(json.dumps(rows,indent=2))
