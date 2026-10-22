"""Previous research synthetic-only Sb analogue, retained without algorithm changes.
Not asserted to be current loader Sb. Original provenance in LEGACY_PROVENANCE.json.
"""
import numpy as np
from structure_quality import rays

def angular_boundary_mean(a,b,step_deg=.1):
    """Synthetic-only Sb analogue: spherical arc-length midpoint integration.
    Not asserted to reproduce the current engine's Sb sampling convention.
    """
    def samples(p):
        rr=rays(p);arr=[];weights=[]
        for x,y in zip(rr,np.roll(rr,-1,axis=0)):
            t=np.arctan2(np.linalg.norm(np.cross(x,y)),x@y)
            n=max(1,int(np.ceil(np.degrees(t)/step_deg)));f=(np.arange(n)+.5)/n
            arr.append((np.sin((1-f)*t)[:,None]*x+np.sin(f*t)[:,None]*y)/np.sin(t));weights.append(np.full(n,t/n))
        return np.concatenate(arr),np.concatenate(weights)
    def dists(q,p):
        r=rays(p);s=np.roll(r,-1,axis=0)
        n=np.cross(r,s);n/=np.linalg.norm(n,axis=1)[:,None]
        dot=q@n.T;projection=q[:,None]-dot[:,:,None]*n[None];projection/=np.linalg.norm(projection,axis=2)[:,:,None]
        total=np.arctan2(np.linalg.norm(np.cross(r,s),axis=1),np.sum(r*s,axis=1))
        d1=np.arctan2(np.linalg.norm(np.cross(projection,r[None]),axis=2),np.sum(projection*r[None],axis=2))
        d2=np.arctan2(np.linalg.norm(np.cross(projection,s[None]),axis=2),np.sum(projection*s[None],axis=2))
        on=(d1+d2)<=total[None]+1e-9
        end=np.arctan2(np.linalg.norm(np.cross(q[:,None],r[None]),axis=2),q@r.T)
        dd=np.where(on,np.arcsin(np.clip(abs(dot),0,1)),np.inf)
        return np.minimum(dd.min(axis=1),end.min(axis=1))
    qa,wa=samples(a);qb,wb=samples(b)
    da,db=dists(qa,b),dists(qb,a)
    return float(np.degrees((wa@da+wb@db)/(wa.sum()+wb.sum())))

