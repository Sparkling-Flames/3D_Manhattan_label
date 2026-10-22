"""Prespecified finite B8L2 parameter grid; no data-dependent score/reference selection."""
from dataclasses import dataclass,asdict
import numpy as np
@dataclass(frozen=True)
class BConfig:
    name:str='B8L2_original'
    sb2:float=32.
    direction_scale:float=8.
    direction_cap:float=1.5
    mean_scale:float=.8
    local_scale:float=.25
    sb_free:float=0.
    direction_free:float=0.
    family:str='parameter_only'

def configs():
    out=[BConfig(name='B8L2_original' if (s,d)==(32,8) else f'B8L2_s{s}_d{d}',sb2=s,direction_scale=d) for s in (32,50,72) for d in (8,10,12)]
    out += [BConfig(name='B8L2_cap1',direction_cap=1.),BConfig(name='B8L2_cap2',direction_cap=2.),BConfig(name='B8L2_height_strict',mean_scale=.6,local_scale=.2),BConfig(name='B8L2_height_soft',mean_scale=1.,local_scale=.3)]
    # These two change the penalty mapping, not the original 5 geometric measurements.
    out += [BConfig(name='B8L2_deadband',sb_free=.5,direction_free=2.,family='structural_loss_variant'),BConfig(name='B8L2_s50_d10_deadband',sb2=50,direction_scale=10,sb_free=.5,direction_free=2.,family='structural_loss_variant')]
    return out

def score(I,S,D,Hm,Hc,c=BConfig()):
    I,S,D,Hm,Hc=np.broadcast_arrays(*[np.asarray(v,float) for v in (I,S,D,Hm,Hc)])
    if any(np.any(~np.isfinite(v)) for v in [I,S,D,Hm,Hc]):raise ValueError('missing_or_nonfinite_component')
    if np.any((I<-1e-12)|(I>1+1e-12)) or any(np.any(v<0) for v in [S,D,Hm,Hc]):raise ValueError('component_domain')
    if min(c.sb2,c.direction_scale,c.direction_cap,c.mean_scale,c.local_scale)<=0:raise ValueError('nonpositive_scale')
    I=np.clip(I,0,1);S=np.maximum(S-c.sb_free,0);D=np.maximum(D-c.direction_free,0)
    B=S*S/c.sb2;LD=c.direction_cap*(D/np.hypot(D,c.direction_scale))**2
    H=(Hm/c.mean_scale)**2+(Hc/c.local_scale)**2
    den=I+np.hypot(1-I+I*B,I*LD)+I*H
    return np.divide(100*I,den,out=np.zeros_like(I),where=den>0)
