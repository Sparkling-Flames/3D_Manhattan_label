from pathlib import Path
import sys,json,os,numpy as np
P=Path('/workspace/scratch/81fa50cc64f5/new_pro_return/panorama_quality_three_routes_20261016');sys.path.insert(0,str(P/'src'))
from geomscore import *
from run_controls import geom
square=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float)
rows=[]
for shear in [.3,.5,.7,1.]:
 base=square@np.array([[1,0],[shear,1.]])
 bs=score_pair(geom(base),geom(square))
 for n in [2,3,4,6,8,12,16,20]:
  dz=4/n;z=np.linspace(-2,2,n+1);mid=(z[1:]+z[:-1])/2
  q=[[-2+shear*mid[0],-2],[2+shear*mid[0],-2]]
  for k in range(n):
   q.append([2+shear*mid[k],z[k+1]])
   if k+1<n:q.append([2+shear*mid[k+1],z[k+1]])
  q.append([-2+shear*mid[-1],2])
  for k in range(n-1,-1,-1):
   q.append([-2+shear*mid[k],z[k]])
   if k>0:q.append([-2+shear*mid[k-1],z[k]])
  q=np.array(q[:-1]);s=score_pair(geom(q),geom(square));dist=Polygon(base).boundary.hausdorff_distance(Polygon(q).boundary)
  row=dict(shear=shear,steps_per_side=n,base=base.tolist(),answer=q.tolist(),reference=square.tolist(),base_score=bs,answer_score=s,hausdorff_to_base_h=dist,area_base=Polygon(base).area,area_answer=Polygon(q).area)
  rows.append(row)
  if n in [2,3,4,12,20]:print(shear,n,'nverts',len(q),'I',bs['I'],s['I'],'QA',bs['QA'],s['QA'],'maxdev',dist,'pen',s['angle_detail']['angle_penalty'])
out=Path(os.environ.get('GQS_STAIR_OUT','/workspace/scratch/81fa50cc64f5/new_pro_audit/symmetric_stair_angle_escape.json'));assert not out.exists();out.write_text(json.dumps(rows,indent=2))
