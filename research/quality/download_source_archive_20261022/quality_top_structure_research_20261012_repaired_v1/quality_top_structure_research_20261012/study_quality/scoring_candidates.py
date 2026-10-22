#!/usr/bin/env python3
"""Pure scalar candidates. No user labels, identities, repair or reference selection."""
from __future__ import annotations
import math


def candidate_scores(m, raw_top=None, raw_bottom=None):
    i = float(m.get('iou_2d', m.get('iou')))
    st, sb, h, d, f = (float(m[k]) for k in ('S_top_deg', 'S_bottom_deg', 'Hstar', 'dir', 'flat'))
    i3 = float(m['iou_3d_corner_mean'])
    if not all(math.isfinite(x) for x in (i, st, sb, h, d, f, i3)):
        raise ValueError('nonfinite feature; missing quality is not zero')
    if not 0 <= i <= 1+1e-10 or not 0 <= i3 <= 1+1e-10 or min(st,sb,h,d,f)<0:
        raise ValueError('feature outside domain')
    ld, lf = d*d/(d*d+25), f*f/(f*f+4)
    c = 1-.075*(ld+lf)
    qpre = 100*i/(1+(st*st+sb*sb)/32+(h/.5)**2)
    alpha = lambda u: .15 + .30*min(1., max(0., (u-1.)/2.))
    out = {
        'Q_v11': qpre*c,
        'Q_floor_iou': 100*i,
        'Q_official_iou3d': 100*i3,
        'Q_stage13': qpre*(1-(alpha(d/5)*ld+alpha(f/2)*lf)/2),
        'Q_no_topS': 100*i*c/(1+sb*sb/32+(h/.5)**2),
        'Q_quarter_topS': 100*i*c/(1+(.25*st*st+sb*sb)/32+(h/.5)**2),
        'Q_IH_h050': 100*i/(1+(h/.5)**2),
        'Q_IHC_h050': 100*i*c/(1+(h/.5)**2),
        'Q_IHC_h025': 100*i*c/(1+(h/.25)**2),
        'Q_IHC_h100': 100*i*c/(1+(h/1.)**2),
        'Q_iou3dC': 100*i3*c,
    }
    if raw_top is not None and raw_bottom is not None:
        out['Q_rawS_same_parameters'] = 100*i*c/(1+(raw_top**2+raw_bottom**2)/32+(h/.5)**2)
    return out


def component_ablation(m):
    """Simultaneous deletions expose interaction; no order-dependent blame claim."""
    i=float(m.get('iou_2d',m.get('iou')))
    st,sb,h,d,f=(float(m[k]) for k in ('S_top_deg','S_bottom_deg','Hstar','dir','flat'))
    c=1-.075*(d*d/(d*d+25)+f*f/(f*f+4))
    terms={'top_S':st*st/32,'bottom_S':sb*sb/32,'height_H':(h/.5)**2}
    base=1+sum(terms.values())
    rows=[]
    for remove in [[],['top_S'],['height_H'],['top_S','height_H'],['bottom_S'],['top_S','bottom_S']]:
        den=1+sum(v for k,v in terms.items() if k not in remove)
        rows.append({'removed':remove,'denominator':den,'Q':100*i*c/den,'delta_Q':100*i*c/den-100*i*c/base})
    return {'denominator_terms':terms,'intrinsic_factor':c,'score_without_intrinsic':100*i/base,
            'intrinsic_deduction':100*i/base*(1-c),'ablations':rows}
