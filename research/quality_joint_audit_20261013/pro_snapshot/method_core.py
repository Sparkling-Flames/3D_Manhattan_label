"""Independent, transparent research candidates. No repair or reference search.

Units: D and S_bottom in degrees; Hmean and Hcenter are relative to the
reference perimeter mean *whole-wall* height. None of the constants is a
human acceptance threshold. The two X_ candidates are challenge functions.
"""
from __future__ import annotations
import math

CANDIDATES = (
    'P_tied_quad08', 'P_tied_mix08',
    'N_anchor4_beta2_v1', 'X_anchor6_beta32_v1', 'X_pooled_quad08_v1',
)

def height_loss(error: float, candidate: str) -> float:
    e = float(error)
    if not math.isfinite(e) or e < 0:
        raise ValueError('height error must be finite and nonnegative')
    if candidate in ('P_tied_quad08', 'X_pooled_quad08_v1'):
        return e*e / .8**2
    if candidate == 'P_tied_mix08':
        return .8*e*e + 12.8*e**4
    if candidate == 'N_anchor4_beta2_v1':
        return e*e / .8**2 + 2*e**4
    if candidate == 'X_anchor6_beta32_v1':
        return e*e / .8**2 + 32*e**6
    raise ValueError('unknown candidate: '+candidate)

def evaluate_metrics(metrics: dict, candidate: str='P_tied_quad08',
                     pooled: dict | None=None) -> dict:
    if candidate not in CANDIDATES:
        raise ValueError('unknown candidate: '+candidate)
    required = ('iou_2d','dir','S_bottom_deg','Hmean','Hcenter')
    try:
        values = [float(metrics[k]) for k in required]
    except (KeyError, TypeError, ValueError):
        return dict(status='missing_or_invalid_metrics', quality_score=None,
                    candidate_id=candidate)
    if (any(not math.isfinite(x) or x < 0 for x in values)
            or values[0] > 1+1e-9 or values[1] > 90/math.sqrt(12)+1e-7
            or values[2] > 180+1e-9):
        return dict(status='invalid_metric_domain', quality_score=None,
                    candidate_id=candidate)
    i,d,sb,e,local=values
    if candidate == 'X_pooled_quad08_v1':
        if not pooled or pooled.get('status')!='available':
            return dict(status='pooled_correspondence_unavailable', quality_score=None,
                        candidate_id=candidate)
        try:
            e=abs(float(pooled['pooled_bias_relative']))
            local=float(pooled['pooled_sd_relative'])
        except (KeyError, TypeError, ValueError):
            return dict(status='invalid_pooled_metrics', quality_score=None,
                        candidate_id=candidate)
        if not math.isfinite(e) or not math.isfinite(local) or local < 0:
            return dict(status='invalid_pooled_metrics', quality_score=None,
                        candidate_id=candidate)
    base=1+sb*sb/32+1.5*d*d/(d*d+37.5)
    try:
        gl=height_loss(e,candidate)
        ll=(local/.25)**2
    except OverflowError:
        return dict(status='nonfinite_loss', quality_score=None, candidate_id=candidate)
    if not math.isfinite(gl+ll):
        return dict(status='nonfinite_loss', quality_score=None, candidate_id=candidate)
    q=100*i/(base+gl+ll)
    return dict(status='available',candidate_id=candidate,quality_score=q,
                bottom_loss=sb*sb/32,direction_loss=base-1-sb*sb/32,
                global_loss=gl,local_loss=ll,base=base,
                top_only_penalty=1-1/(1+gl+ll),
                score_without_height=100*i/base,
                scope_acceptance_not_inferred=True,
                original_input_quality_not_certified=True,
                human_grade=None)

def independent_p04_beta_bound(a: dict,b: dict,power:int=4) -> float:
    """B top penalty > A; only the frozen whole-wall and local coordinates."""
    numerator=(b['Hcenter']**2-a['Hcenter']**2)/.25**2 - (
        a['Hmean']**2-b['Hmean']**2)/.8**2
    return numerator/(a['Hmean']**power-b['Hmean']**power)

def p04_quadratic_scale_lower_bound(a:dict,b:dict,local_scale:float=.25) -> dict:
    if not math.isfinite(local_scale) or local_scale <= 0:
        raise ValueError('local scale must be finite and positive')
    for item in (a,b):
        if any(not math.isfinite(item[k]) or item[k] < 0 for k in ('Hmean','Hcenter')):
            raise ValueError('height metrics must be finite and nonnegative')
    x=a['Hmean']**2-b['Hmean']**2
    y=b['Hcenter']**2-a['Hcenter']**2
    if y>0 and x>0:
        return dict(kind='lower_bound',global_scale_lower_exclusive=local_scale*math.sqrt(x/y))
    if (y>0 and x<=0) or (y==0 and x<0):
        return dict(kind='all_positive_scales',global_scale_lower_exclusive=0.)
    if y<=0 and x>=0:
        return dict(kind='no_positive_scale_solution',global_scale_lower_exclusive=None)
    return dict(kind='upper_bound',global_scale_upper_exclusive=local_scale*math.sqrt(x/y))
