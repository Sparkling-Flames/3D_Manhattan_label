"""Fixed-input severity aggregators. No training, reference selection or writes.
F,d are transformed NONNEGATIVE burdens, not independent random residuals.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import sqrt
import numpy as np

@dataclass(frozen=True)
class Model:
    name: str
    direction_scale: float = 8.
    mechanism: str = 'l2'
    parameter: float = 0.

LAMBDA = sqrt(2.)-1.
MODELS = [Model('WQ',sqrt(37.5),'sum'), Model('A10',10.,'sum'),
          Model('S8',8.,'sum'), Model('POOL_OLD',sqrt(37.5),'l2'),
          Model('B8L2'), Model('C8_anchor_matched',8.,'ordered',LAMBDA),
          Model('P1.5',8.,'lp',1.5), Model('P3',8.,'lp',3.),
          Model('MAX8',8.,'max'), Model('MIN_SHARE25',8.,'mixed',.25)]
MODEL_MAP={x.name:x for x in MODELS}

def pool(f,d,kind='l2',param=0.):
    f,d=np.broadcast_arrays(np.asarray(f,float),np.asarray(d,float))
    if np.any(f<0)|np.any(d<0) or np.any(np.isnan(f))|np.any(np.isnan(d)):
        raise ValueError('nonnegative burdens required')
    if kind=='sum': return f+d
    if kind=='l2': return np.hypot(f,d)
    if kind=='max': return np.maximum(f,d)
    if kind=='ordered': return np.maximum(f,d)+param*np.minimum(f,d)
    if kind=='mixed': return (1-param)*np.hypot(f,d)+param*(f+d)
    if kind=='lp':
        if not np.isfinite(param) or param<1:raise ValueError('p>=1 required')
        m=np.maximum(f,d);x=np.divide(f,m,out=np.zeros_like(f),where=m>0);y=np.divide(d,m,out=np.zeros_like(d),where=m>0)
        return m*(x**param+y**param)**(1/param)
    raise ValueError(kind)

def validate(I,Sb,D,Hm,Hc):
    a=np.broadcast_arrays(*[np.asarray(v,float) for v in [I,Sb,D,Hm,Hc]])
    if any(not np.all(np.isfinite(v)) for v in a):raise ValueError('all five finite components required; NA is not zero')
    if np.any(a[0]<-1e-12)|np.any(a[0]>1+1e-12) or any(np.any(v<0) for v in a[1:]):raise ValueError('component outside domain')
    a=list(a);a[0]=np.clip(a[0],0.,1.) # numerical round-off only, same frozen policy
    return a

def terms(I,Sb,D,Hm,Hc,c=8.):
    I,Sb,D,Hm,Hc=validate(I,Sb,D,Hm,Hc)
    if not np.isfinite(c) or c<=0:raise ValueError('positive direction scale')
    with np.errstate(divide='ignore',over='ignore'):
        o=np.divide(1-I,I,out=np.full_like(I,np.inf),where=I>0)
        b=(Sb/np.sqrt(32.))**2
        g=(Hm/.8)**2;l=(Hc/.25)**2
    d=1.5*(D/np.hypot(D,c))**2
    return {'O':o,'bottom':b,'F':o+b,'d':d,'G':g,'L':l,'H':g+l}

def score(I,Sb,D,Hm,Hc,model='B8L2'):
    if isinstance(model,str):model=MODEL_MAP[model]
    I,Sb,D,Hm,Hc=validate(I,Sb,D,Hm,Hc)
    t=terms(I,Sb,D,Hm,Hc,model.direction_scale)
    # Homogeneity gives an I-scaled expression without 1/I at I=0.
    with np.errstate(invalid='ignore',over='ignore',divide='ignore'):
        ib=np.multiply(I,t['bottom'],out=np.zeros_like(I),where=I>0)
        ih=np.multiply(I,t['H'],out=np.zeros_like(I),where=I>0)
        m=pool(1-I+ib,I*t['d'],model.mechanism,model.parameter)
        q=100*I/(I+m+ih)
    return np.where(I==0,0.,q)

def from_frame(frame,model):
    return score(*[frame[c].to_numpy(float) for c in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']],model)

def structural_only_upper_bound(I,Sb,D,model='B8L2'):
    """Upper bound under missing nonnegative height burdens; NOT a complete score."""
    return score(I,Sb,D,0.,0.,model)

def anchored_score_shape(m,h,gamma=1.):
    """Mapping sensitivity only. gamma != 1 does NOT preserve pure-IoU anchor."""
    return 100/(1+(m+h)**gamma)
