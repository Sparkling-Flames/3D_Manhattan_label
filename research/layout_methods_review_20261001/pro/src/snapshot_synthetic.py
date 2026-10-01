"""Independent transcription of the current snapshot's 74 generating rules.
Source commit 10a0fe54608f62668f73d705d6a0cf50a9179f21, path
research/pro_layout_metric_response_20261001/tools/thesis_main/analysis/layout_metric_response_20261001.py.
This is not a byte-for-byte copy of the source module.
"""
import numpy as np
from copy import deepcopy
from shapely.geometry import box
from shapely.ops import unary_union
from geometry_core import from_floor
SQ=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float);Q=['SW','SE','NE','NW']
def generate():
 def rec(p,lab=Q,h=2.7):return from_floor(p,h,lab)
 base=rec(SQ);cases=[]
 def add(f,n,v,a,b=base):cases.append(dict(family=f,case=n,amplitude=v,a=a,b=b))
 add('equivalence','cyclic_shift',0,rec(np.roll(SQ,2,axis=0),Q[2:]+Q[:2]))
 add('equivalence','reverse_ring',0,rec(SQ[::-1],Q[::-1]))
 add('equivalence','collinear_subdivision',0,rec(np.insert(SQ,1,[0,-2],axis=0),['SW','mid','SE','NE','NW']))
 p=deepcopy(base);p.update(points=(np.asarray(p['points'])-.5).tolist(),coordinate_convention='pixel_center');add('equivalence','converted_C_P',0,p)
 for d in [0,.05,.25,1,2]:
  p=SQ.copy();p[[1,2],0]+=d;add('extent','single_side_extension',d,rec(p));add('extent','symmetric_extension',d,rec(SQ*(1+d/2)))
  p=SQ.copy();p[[1,2],0]-=d;add('extent','single_side_truncation',d,rec(p))
 for d in [0,.002,.01,.05,.2]:
  for name,sign in [('convex_detail',1),('concave_detail',-1)]:
   if d==0:p=[[-2,-2],[2,-2],[2,-.1],[2,.1],[2,2],[-2,2]];lab=['SW','SE','start','end','NE','NW']
   else:p=[[-2,-2],[2,-2],[2,-.1],[2+sign*d,-.1],[2+sign*d,.1],[2,.1],[2,2],[-2,2]];lab=['SW','SE','start','out_start','out_end','end','NE','NW']
   add('detail',name,d,rec(p,lab))
 for gap in [.002,.01,.05,.1]:
  a=rec([[-2,-2],[2,-2],[2,-gap],[2.05,0],[2,gap],[2,2],[-2,2]],['SW','SE','start','mid','end','NE','NW'])
  b=rec([[-2,-2],[2,-2],[2,-gap],[2,gap],[2,2],[-2,2]],['SW','SE','start','end','NE','NW']);add('detail','near_three_pairs',gap,a,b)
 for ext,name in [(2,'ordinary'),(32,'near_horizon')]:
  ref=rec(SQ*ext/2)
  for d in [0,.1,.5,1,2,4]:
   for part in ['shared_x','bottom_y','top_y']:
    a=deepcopy(ref);p=np.asarray(a['points']).reshape(-1,2,2)
    if part=='shared_x':p[1,:,0]=(p[1,:,0]+d)%1024
    elif part=='bottom_y':p[1,1,1]-=d
    else:p[1,0,1]+=d
    a['points']=p.reshape(-1,2).tolist();add('localization',name+'_'+part,d,a,ref)
 ref=None
 for length in [4,8,12,20]:
  p=np.asarray(unary_union([box(-2,-2,2,2),box(2,.5,4,1.5),box(3,1.5,4,length)]).exterior.coords)[:-1]
  lab=[f'far_{x:g}' if z==length else f'fixed_{x:g}_{z:g}' for x,z in p];a=rec(p,lab)
  if ref is None:ref=a
  add('extent','hidden_extension',length,a,ref)
 add('equivalence','nonflat_collinear_subdivision',0,rec([[-2,-2],[2,-2],[2,0],[2,2],[-2,2]],['SW','SE','mid','NE','NW'],[1.5,3.5,3.5,3.5,1.5]),rec(SQ,Q,[1.5,3.5,3.5,1.5]))
 assert len(cases)==74
 return cases
