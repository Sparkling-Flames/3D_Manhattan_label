#!/usr/bin/env python3
"""Reference-conditioned quality functions for the 2026-10-13 joint study.

Pure numerical functions: this module never selects or approves a reference.
Missing height quantities produce a floor-only result, never a fabricated Q3D.
Angles are degrees. Heights are relative to reference perimeter-mean wall height.
"""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np

BASELINE = {
    'name': 'baseline_quad08', 'family': 'hill', 'combine': 'additive',
    'iou_power': 1.0, 'boundary_scale': math.sqrt(32.0), 'boundary_power': 2.0,
    'direction_scale': math.sqrt(37.5), 'direction_cap': 1.5, 'direction_power': 2.0,
    'global_scale': .8, 'local_scale': .25, 'global_power': 2.0, 'local_power': 2.0,
}

def normalized_metrics(m):
    """Accept frozen names and the explicit names used by the new adapter."""
    aliases = {'I': ('I', 'iou_2d', 'floor_iou'),
               'Sb': ('Sb', 'S_bottom_deg', 'bottom_boundary_mean_deg'),
               'D': ('D', 'dir', 'D_rms_deg'),
               'Hm': ('Hm', 'Hmean', 'global_height_relative'),
               'Hc': ('Hc', 'Hcenter', 'local_height_relative')}
    out = {}
    for k, aa in aliases.items():
        out[k] = next((m[a] for a in aa if a in m and m[a] is not None), None)
    return out

def direction_loss(d, config, descriptor=None):
    """L2 common-axis D, fixed-axis tails, or a jointly optimized hinge descriptor."""
    d=np.asarray(d, dtype=float)
    kind=config['family']; scale=float(config['direction_scale'])
    if kind in ('hill','hill_tail'):
        x=np.power(d/scale, config['direction_power'])
        base=config['direction_cap']*x/(1+x)
        if kind=='hill_tail': base=base+(d/config['tail_scale'])**4
        return base
    if kind=='power':
        return np.power(d/scale, config['direction_power'])
    if kind=='accelerated':
        return (d/scale)**2+(d/config['tail_scale'])**4
    if descriptor is None:
        raise ValueError('length-supported direction family requires an explicit descriptor')
    if kind=='moment4':
        return (d/scale)**2+np.asarray(descriptor['moment4'])/config['tail_scale']**4
    if kind=='joint_hinge':
        key=f"t{config['tail_threshold']:g}_g{config['hinge_weight']:g}"
        return np.asarray(descriptor['joint_hinge'][key])/scale**2
    if kind=='supported_tail':
        threshold=str(int(config['tail_threshold']))
        return (d/scale)**2+np.asarray(descriptor['excess2'][threshold])/config['tail_scale']**2
    raise ValueError('unknown direction family: '+kind)

def evaluate_arrays(m, config, descriptor=None):
    """Vectorized valid-domain evaluator used in the offline search."""
    I=np.asarray(m['I'],float); Sb=np.asarray(m['Sb'],float); D=np.asarray(m['D'],float)
    B=np.power(Sb/config['boundary_scale'],config['boundary_power'])
    if config.get('boundary_disabled'): B=np.zeros_like(I)
    Ld=direction_loss(D,config,descriptor)
    if config.get('direction_disabled'): Ld=np.zeros_like(I)
    Hm=np.asarray(m.get('Hm',np.zeros_like(I)),float)
    Hc=np.asarray(m.get('Hc',np.zeros_like(I)),float)
    Lm=np.power(Hm/config['global_scale'],config['global_power'])
    Lc=np.power(Hc/config['local_scale'],config['local_power'])
    if config.get('global_disabled'): Lm=np.zeros_like(I)
    if config.get('local_disabled'): Lc=np.zeros_like(I)
    H=Lm+Lc; Ip=np.power(I,config['iou_power'])
    if config.get('overlap_disabled'): Ip=np.ones_like(Ip)
    combine=config['combine']
    if combine=='additive':
        floor=100*Ip/(1+B+Ld); full=100*Ip/(1+B+Ld+H)
        den=1+B+Ld+H
    elif combine=='product_height':
        floor=100*Ip/(1+B+Ld); full=floor/(1+H)
        den=(1+B+Ld)*(1+H)
    elif combine=='product_all':
        floor=100*Ip/((1+B)*(1+Ld)); full=floor/(1+H)
        den=(1+B)*(1+Ld)*(1+H)
    elif combine=='max_floor':
        # Equal units: both overlap and boundary express neutral single-factor loss.
        overlap=np.divide(1.,Ip,out=np.full_like(Ip,np.inf),where=Ip>0)-1
        F=np.maximum(overlap,B)
        floor=100/(1+F+Ld); full=100/(1+F+Ld+H); den=1+F+Ld+H
    else: raise ValueError('unknown combine: '+combine)
    return dict(score=full,floor_score=floor,boundary_loss=B,direction_loss=Ld,
                global_height_loss=Lm,local_height_loss=Lc,height_loss=H,
                denominator=den,height_score_drop=floor-full)

def score_metrics(metrics, config, descriptor=None, *, reference_height_available=None):
    """Public scalar interface. Floor validity and full-height availability are explicit.

    A floor-only reference must omit Hm/Hc, set either to None, or explicitly
    pass reference_height_available=False; its score is None. The returned
    floor_score is never named a complete quality score. descriptor can be a
    row of real_direction_descriptors.json for fixed-axis local families, or
    the normalized descriptor in inputs/search_inputs.json for all families.
    """
    try:
        required=['iou_power','boundary_scale','boundary_power','direction_scale','global_scale','local_scale','global_power','local_power']
        if config['family'] in ('hill','hill_tail'):required+=['direction_cap','direction_power']
        if config['family']=='power':required+=['direction_power']
        if config['family'] in ('accelerated','hill_tail','moment4','supported_tail'):required+=['tail_scale']
        if config['family']=='joint_hinge':required+=['hinge_weight']
        if config['family'] not in ('hill','power','accelerated','hill_tail','moment4','supported_tail','joint_hinge'):
            raise ValueError('unknown_family')
        if config['combine'] not in ('additive','product_height','product_all','max_floor'):
            raise ValueError('unknown_combination')
        if any(not math.isfinite(float(config[k])) or float(config[k])<=0 for k in required):
            raise ValueError('nonpositive_or_nonfinite_parameter')
    except (TypeError,KeyError,ValueError,OverflowError) as e:
        return dict(status='unavailable',reason='invalid_config:'+str(e),score=None,floor_score=None)
    try:m=normalized_metrics(metrics)
    except (TypeError,KeyError,ValueError) as e:
        return dict(status='unavailable',reason='invalid_metrics:'+str(e),score=None,floor_score=None)
    try:
        m={k:(float(v) if v is not None else None) for k,v in m.items()}
    except (TypeError,ValueError,OverflowError) as e:
        return dict(status='unavailable',reason='nonnumeric_metrics:'+str(e),score=None,floor_score=None)
    for k in ('I','Sb','D'):
        if m[k] is None or not math.isfinite(float(m[k])):
            return dict(status='unavailable',reason='missing_or_nonfinite_'+k,
                        score=None,floor_score=None)
    iou_roundoff_clamped=False
    if 1<m['I']<=1+64*np.finfo(float).eps:
        m['I']=1.; iou_roundoff_clamped=True
    if not 0<=m['I']<=1 or not 0<=m['Sb']<=180 or not 0<=m['D']<=90/math.sqrt(12)+1e-8:
        return dict(status='unavailable',reason='outside_metric_domain',score=None,floor_score=None)
    invalid_height=any(m[k] is not None and (not math.isfinite(m[k]) or m[k]<0) for k in ('Hm','Hc'))
    complete=all(m[k] is not None and math.isfinite(float(m[k])) and m[k]>=0 for k in ('Hm','Hc')) and reference_height_available is not False
    d=None
    if config['family'] in ('moment4','supported_tail','joint_hinge'):
        if descriptor is None:
            return dict(status='unavailable',reason='missing_direction_support_descriptor',score=None,floor_score=None)
        try:
            if 'moment4' in descriptor or 'joint_hinge' in descriptor:
                d=descriptor
            else:
                d={'moment4':descriptor['weighted_abs_moments_deg_power']['p4'],
                   'excess2':{k:v['positive_part_m2_deg2'] for k,v in descriptor['excess_by_threshold_deg'].items()}}
            if config['family']=='moment4':support=d['moment4']
            elif config['family']=='supported_tail':support=d['excess2'][str(int(config['tail_threshold']))]
            else:support=d['joint_hinge'][f"t{config['tail_threshold']:g}_g{config['hinge_weight']:g}"]
            support=np.asarray(support,dtype=float)
            if support.size!=1 or not np.all(np.isfinite(support)) or np.any(support<0):
                raise ValueError('support_must_be_one_finite_nonnegative_value')
        except (TypeError,KeyError,ValueError,OverflowError,AttributeError) as e:
            return dict(status='unavailable',reason='invalid_direction_support_descriptor:'+str(e),score=None,floor_score=None)
    arr={k:np.array([float(m[k]) if m[k] is not None else 0.]) for k in m}
    if not complete: arr['Hm']=arr['Hc']=np.array([0.])
    try:
        with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
            val=evaluate_arrays(arr,config,d)
    except (TypeError,KeyError,ValueError,OverflowError) as e:
        return dict(status='unavailable',reason='invalid_descriptor_or_formula:'+str(e),score=None,floor_score=None)
    out={k:float(np.asarray(v).reshape(-1)[0]) for k,v in val.items()}
    if not all(math.isfinite(v) for k,v in out.items() if k!='denominator'):
        return dict(status='unavailable',reason='nonfinite_formula_result',score=None,floor_score=None)
    if not math.isfinite(out['denominator']):
        if m['I']==0 and out['score']==0:
            out['denominator']=None
            out['zero_overlap_limit_evaluated']=True
        else:
            return dict(status='unavailable',reason='nonfinite_formula_denominator',score=None,floor_score=None)
    out['status']='complete' if complete else ('height_unavailable' if invalid_height else 'floor_only')
    if not complete:
        for k in ('score','height_score_drop','global_height_loss','local_height_loss','height_loss'):
            out[k]=None
    out['reference_selected_by_this_function']=False
    out['iou_roundoff_clamped']=iou_roundoff_clamped
    out['raw_input_quality_certified']=False
    if not complete:
        out['height_unavailability_reason']='invalid_height_metrics' if invalid_height else ('reference_top_not_available' if reference_height_available is False else 'height_metrics_missing')
    out['human_grade']=None
    return out

def load_config(path, name=None):
    x=json.loads(Path(path).read_text())
    if name is None: name=x['recommended']
    return x['candidates'][name]

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--metrics',required=True)
    p.add_argument('--config',required=True);p.add_argument('--candidate')
    a=p.parse_args();print(json.dumps(score_metrics(json.loads(a.metrics),load_config(a.config,a.candidate)),indent=2))
