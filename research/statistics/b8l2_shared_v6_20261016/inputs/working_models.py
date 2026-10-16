"""Versioned research scores, no production/default writes.

A10 broadens the intrinsic direction Hill scale; B8L2 pools only the floor
fidelity block and direction loss. Heights are never pooled or capped.
All returned contributions are nonlinear ablations or explicitly labelled
Shapley allocations, not fixed percentage weights or causal attributions.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from itertools import combinations
from math import factorial
import numpy as np

@dataclass(frozen=True)
class Parameters:
    version: str
    direction_scale_deg: float
    direction_cap: float = 1.5
    bottom_scale_squared_deg2: float = 32.0
    global_height_scale: float = 0.8
    local_height_scale: float = 0.25
    pooling_order: float = 1.0
    def validate(self):
        vals=[self.direction_scale_deg,self.direction_cap,self.bottom_scale_squared_deg2,
              self.global_height_scale,self.local_height_scale]
        if any(not np.isfinite(x) or x<=0 for x in vals):
            raise ValueError('positive finite scales required')
        if np.isnan(self.pooling_order) or self.pooling_order<1:
            raise ValueError('pooling order must be >=1')
        return self

WQ=Parameters('WQ-LS08-20261014',float(np.sqrt(37.5)))
A=Parameters('WQ-A10-20261015',10.0)
B=Parameters('WQ-B8L2-20261015',8.0,pooling_order=2.0)
MODELS={'WQ':WQ,'A10':A,'B8L2':B}


def checked(I,Sb,D,Hm,Hc):
    arrays=list(np.broadcast_arrays(*[np.asarray(x,dtype=float) for x in (I,Sb,D,Hm,Hc)]))
    if any(not np.isfinite(x).all() for x in arrays):
        raise ValueError('full score requires all five finite components; missing is not zero')
    if np.any((arrays[0]<-1e-12)|(arrays[0]>1+1e-12)) or any(np.any(x<0) for x in arrays[1:]):
        raise ValueError('component outside domain')
    arrays[0]=np.clip(arrays[0],0.,1.)
    return arrays


def lp(x,y,p):
    if p==1:return x+y
    if p==2:return np.hypot(x,y)
    if np.isinf(p):return np.maximum(x,y)
    scale=np.maximum(x,y)
    return scale*np.power(np.divide(x,scale,out=np.zeros_like(x),where=scale>0)**p+
                          np.divide(y,scale,out=np.zeros_like(y),where=scale>0)**p,1/p)


def terms(I,Sb,D,Hm,Hc,params=WQ):
    params.validate();I,Sb,D,Hm,Hc=checked(I,Sb,D,Hm,Hc)
    with np.errstate(over='ignore'):
        bottom=(Sb/np.sqrt(params.bottom_scale_squared_deg2))**2
    # Division before squaring remains well-behaved for extreme finite D.
    direction=params.direction_cap*(D/np.hypot(D,params.direction_scale_deg))**2
    with np.errstate(over='ignore'):
        glob=(Hm/params.global_height_scale)**2
        local=(Hc/params.local_height_scale)**2
    return I,bottom,direction,glob,local


def score(I,Sb,D,Hm,Hc,params=WQ):
    I,b,di,g,l=terms(I,Sb,D,Hm,Hc,params)
    # I-scaled reciprocal formula gives the exact continuous I=0 limit.
    with np.errstate(invalid='ignore',divide='ignore',over='ignore'):
        pooled=lp(1-I+I*b,I*di,params.pooling_order)
        value=100*I/(I+pooled+I*(g+l))
    return np.where(I==0.,0.,value)


def floor_upper_bound(I,Sb,D,params=WQ):
    """Upper bound under unknown nonnegative height losses, NOT a full score."""
    return score(I,Sb,D,0.,0.,params)


def attribution(I,Sb,D,Hm,Hc,params=WQ):
    """Scalar ablation and Shapley loss allocation on the SAME fixed inputs."""
    v=[float(x) for x in (I,Sb,D,Hm,Hc)]; checked(*v); v[0]=float(np.clip(v[0],0.,1.)); I=v[0]
    names=['floor_IoU','bottom_position','intrinsic_direction','global_height','local_height']
    ideal=[1.,0.,0.,0.,0.]
    values={}
    for bits in range(32):
        x=[v[i] if bits&(1<<i) else ideal[i] for i in range(5)]
        values[bits]=float(score(*x,params))
    q=values[31];out={'score':q,'total_loss_points':100-q}
    for i,name in enumerate(names):
        out['delete_'+name+'_gain']=values[31^(1<<i)]-q
        out['shapley_loss_'+name]=sum(factorial(bits.bit_count())*factorial(4-bits.bit_count())/factorial(5)*
             (values[bits]-values[bits|(1<<i)]) for bits in range(32) if not bits&(1<<i))
    if I>0:
        _,bot,di,glob,loc=terms(*v,params)
        F=1/I-1+float(bot); di=float(di)
        out['floor_fidelity_loss']=F
        out['direction_loss']=di
        out['pooled_geometric_loss']=float(lp(np.array(F),np.array(di),params.pooling_order))
        out['effective_extra_direction_loss']=out['pooled_geometric_loss']-F
        out['subadditive_loss_discount']=F+di-out['pooled_geometric_loss']
    return out
