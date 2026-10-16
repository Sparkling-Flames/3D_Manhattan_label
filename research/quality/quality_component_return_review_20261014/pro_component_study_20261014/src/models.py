"""Research-only scoring. No geometry repair, reference selection or eligibility grants."""
from __future__ import annotations
import numpy as np

COMPONENTS = ('direction','overlap','boundary','local_height','global_height')

def losses(I, Sb, D, Hm, Hc):
    """Broadcasted official WQ-LS08 primitives; missing/invalid -> all NaN.
    I=0 is a measured zero overlap, not a missing value. Its overlap loss is +inf.
    """
    I,Sb,D,Hm,Hc=np.broadcast_arrays(*[np.asarray(x,dtype=float) for x in (I,Sb,D,Hm,Hc)])
    valid=np.isfinite(I)&(I>=0)&(I<=1)
    for v in (Sb,D,Hm,Hc): valid &= np.isfinite(v)&(v>=0)
    with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
        a=np.stack([1.5*D**2/(D**2+37.5), 1/I-1, Sb**2/32,
                    (Hc/.25)**2,(Hm/.8)**2],axis=-1)
    return np.where(valid[...,None],a,np.nan)

def aggregate(p, weights):
    p=np.asarray(p,dtype=float); w=np.asarray(weights,dtype=float)
    if w.shape!=(5,) or not np.all(np.isfinite(w)) or np.any(w<=0) or abs(w.sum()-1)>1e-12:
        raise ValueError('Five strictly positive finite weights must sum to one')
    if p.shape[-1]!=5: raise ValueError('Expected five losses')
    valid=np.all(~np.isnan(p)&(p>=0),axis=-1)
    with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
        s=w/(w+p)
        ls=100/(1+np.sum(p,axis=-1))
        harmonic=100/np.sum(w/s,axis=-1)
        arithmetic=100*np.sum(w*s,axis=-1)
        geometric=100*np.exp(np.sum(w*np.log(s),axis=-1))
        idx=[0,2,3,4]; v=w[idx]/(1-w[1])
        aux=v/(v+p[...,idx])
        range_anchored=100/(1+p[...,1])*np.sum(v*aux,axis=-1)
    return {k:np.where(valid,v,np.nan) for k,v in
            [('WQ_LS08',ls),('harmonic_exact_rewrite',harmonic),
             ('arithmetic_candidate',arithmetic),('geometric_control',geometric),
             ('range_anchored_A',range_anchored)]},s
