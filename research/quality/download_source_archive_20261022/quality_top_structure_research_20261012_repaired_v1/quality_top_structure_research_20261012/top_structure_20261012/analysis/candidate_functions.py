#!/usr/bin/env python3
"""Finite diagnostic candidates for the top/height study.

No identity, label, eligibility, point repair or reference selection occurs here.
Input names follow the frozen engine. `flat` means angular ceiling flatness,
NOT the unrelated Euclidean footprint distance also called F elsewhere.
Missing optional inputs produce None, never a zero score.
"""
from __future__ import annotations
import math

PRIMARY_METHODS = ['Q_v11','Q_floor_iou','Q_official_iou3d','Q_no_topS',
                   'Q_IHC_h050','Q_quarter_topS','Q_top_1_16',
                   'Q_max_old','Q_max_quarter','Q_no_top_stage13','Q_top_1_16_stage13']
DIAGNOSTIC_METHODS = ['Q_split_equal','Q_split_local025','Q_no_top_Xrms8','Q_no_top_Xmax8']


def _get(m, *names):
    for n in names:
        if n in m and m[n] is not None and m[n] != '':
            v=float(m[n])
            if math.isfinite(v): return v
    return None


def score(m):
    i=_get(m,'iou_2d','iou','I'); i3=_get(m,'iou_3d_corner_mean','I3')
    st=_get(m,'S_top_deg','St'); sb=_get(m,'S_bottom_deg','Sb')
    h=_get(m,'Hstar','H'); d=_get(m,'dir','D'); f=_get(m,'flat','F')
    vals=(i,st,sb,h,d,f)
    if any(v is None for v in vals):
        raise ValueError('Missing/nonfinite mandatory component; no invented score')
    if not 0<=i<=1+1e-10 or min(st,sb,h,d,f)<0:
        raise ValueError('Component outside geometric domain')
    c=1-.075*(d*d/(d*d+25)+f*f/(f*f+4))
    a=100*i*c; t=st*st/32; b=sb*sb/32; z=(h/.5)**2
    out={
        'Q_v11':a/(1+b+t+z),
        'Q_floor_iou':100*i,
        'Q_official_iou3d':None if i3 is None else 100*i3,
        'Q_no_topS':a/(1+b+z),
        'Q_IHC_h050':a/(1+z),
        'Q_quarter_topS':a/(1+b+.25*t+z),
        'Q_top_1_16':a/(1+b+.0625*t+z),
        'Q_max_old':a/(1+b+max(t,z)),
        'Q_max_quarter':a/(1+b+max(.25*t,z)),
    }
    # Exactly the previously implemented stage13 component schedule. These
    # two combinations are a separately logged, adaptive development probe.
    alpha=lambda u:.15+.30*min(1.,max(0.,(u-1.)/2.))
    cstage=1-.5*(alpha(d/5)*d*d/(d*d+25)+alpha(f/2)*f*f/(f*f+4))
    out['Q_no_top_stage13']=100*i*cstage/(1+b+z)
    out['Q_top_1_16_stage13']=100*i*cstage/(1+b+.0625*t+z)
    hm=_get(m,'Hmean'); hc=_get(m,'Hcenter')
    out['Q_split_equal']=None if hm is None or hc is None else a/(1+b+(hm/.5)**2+(hc/.5)**2)
    out['Q_split_local025']=None if hm is None or hc is None else a/(1+b+(hm/.5)**2+(hc/.25)**2)
    for key,col in [('Q_no_top_Xrms8','X_rms_deg'),('Q_no_top_Xmax8','X_max_deg')]:
        x=_get(m,col)
        out[key]=None if x is None else out['Q_no_topS']/(1+(x/8)**2)
    rt=_get(m,'S_top_raw_deg'); rb=_get(m,'S_bottom_raw_deg')
    out['Q_rawS_same_parameters']=None if rt is None or rb is None else a/(1+(rt*rt+rb*rb)/32+z)
    return out


def top_weight_score(m, gamma):
    """Analytical finite-family interpolation, not a fitted human transition."""
    if gamma<0: raise ValueError('gamma must be nonnegative')
    i=_get(m,'iou_2d','iou','I'); st=_get(m,'S_top_deg','St'); sb=_get(m,'S_bottom_deg','Sb')
    h=_get(m,'Hstar','H'); d=_get(m,'dir','D'); f=_get(m,'flat','F')
    c=1-.075*(d*d/(d*d+25)+f*f/(f*f+4))
    return 100*i*c/(1+sb*sb/32+(h/.5)**2+gamma*st*st/32)
