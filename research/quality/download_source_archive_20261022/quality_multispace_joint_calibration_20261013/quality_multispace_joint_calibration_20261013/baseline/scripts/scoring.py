"""Transparent research-only scalar candidates. No IDs, labels, reference search,
pairing repair, or eligibility decisions occur in this scoring function.
"""
import numpy as np

DEFAULT=dict(D_cap=1.,D_scale=5.,D_power=2.,global_scale=.5,global_power=2.,global_mix=None,
    local_scale=.25,local_power=2.,local_shoulder_threshold=None,local_shoulder_strength=0.,
    local_smooth_threshold=None,local_smooth_strength=0.,local_smooth_power=4.,top_weight=0.,F_weight=0.)

def config(**kwargs):
    unknown=set(kwargs)-set(DEFAULT)
    if unknown:raise ValueError('Unknown parameters: '+', '.join(sorted(unknown)))
    c=dict(DEFAULT);c.update(kwargs)
    for k in ['D_scale','D_power','global_scale','global_power','local_scale','local_power','local_smooth_power']:
        if not np.isfinite(c[k]) or c[k]<=0:raise ValueError(k+' must be finite and positive')
    for k in ['D_cap','local_shoulder_strength','local_smooth_strength','top_weight','F_weight']:
        if not np.isfinite(c[k]) or c[k]<0:raise ValueError(k+' must be finite and nonnegative')
    if c['F_weight']>1:raise ValueError('F_weight must not exceed 1')
    if c['global_mix'] is not None and not 0<=c['global_mix']<=1:raise ValueError('global_mix must lie in [0,1]')
    for k in ['local_shoulder_threshold','local_smooth_threshold']:
        if c[k] is not None and (not np.isfinite(c[k]) or c[k]<=0):raise ValueError(k+' must be positive or None')
    return c

def score_terms(metrics, settings=None):
    c=config(**(settings or {}))
    i,d,f,hm,hc,st,sb=(np.asarray(metrics[k],dtype=float) for k in
        ['iou_2d','dir','flat','Hmean','Hcenter','S_top_deg','S_bottom_deg'])
    if any(np.any(~np.isfinite(x)) or np.any(x<0) for x in [i,d,f,hm,hc,st,sb]):
        raise ValueError('Missing, nonfinite or negative geometry: preserve a noncomputable status instead of assigning a score')
    if np.any(i>1+1e-9):raise ValueError('iou_2d must be a fraction in [0,1]')
    dp=(d/c['D_scale'])**c['D_power']
    direction=c['D_cap']*dp/(1+dp)
    x=hm/c['global_scale']
    if c['global_mix'] is None:glob=x**c['global_power']
    else:
        alpha=c['global_mix'];glob=(1-alpha)*x*x+alpha*x**4
    local=(hc/c['local_scale'])**c['local_power']
    if c['local_shoulder_threshold'] is not None:
        local=local+c['local_shoulder_strength']*(np.maximum(hc-c['local_shoulder_threshold'],0)/c['local_scale'])**2
    if c['local_smooth_threshold'] is not None:
        ratio=(hc/c['local_smooth_threshold'])**c['local_smooth_power']
        local=local*(1+c['local_smooth_strength']*ratio/(1+ratio))
    top=c['top_weight']*st*st/32
    flat=c['F_weight']*.075*f*f/(f*f+4)
    base=1+sb*sb/32+direction
    total_top=glob+local+top
    q=100*i*(1-flat)/(base+total_top)
    without=100*i/base
    return dict(score=q,base=base,direction_loss=direction,global_loss=glob,local_loss=local,
        top_boundary_loss=top,flat_fraction=flat,total_top_loss=total_top,
        top_only_penalty=1-(1-flat)/(1+total_top),score_without_top=without,top_drop=without-q)

def stack_metrics(rows):
    return {k:np.array([r['metrics'][k] for r in rows],dtype=float) for k in
       ['iou_2d','dir','flat','Hmean','Hcenter','S_top_deg','S_bottom_deg']}

def scalar_terms(metrics,settings=None):
    return {k:float(v) for k,v in score_terms(metrics,settings).items()}
