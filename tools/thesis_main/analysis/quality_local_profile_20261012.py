"""同均高/RMS的局部位置与支撑范围控制；仅研究分量，不计算总分。"""
from __future__ import annotations

import argparse
from copy import deepcopy
import math
from pathlib import Path
import sys

if __package__:
    from .quality_top_height_response_20261012 import profile_moments, read_json, save_json, validate_development_gates, distribution
    from .quality_height_conditioning_20261012 import coordinate_key
    from .quality_top_residual_20261012 import align_mean, spherical_sym_distance
else:
    from quality_top_height_response_20261012 import profile_moments, read_json, save_json, validate_development_gates, distribution
    from quality_height_conditioning_20261012 import coordinate_key
    from quality_top_residual_20261012 import align_mean, spherical_sym_distance

ENGINE = Path(__file__).resolve().parents[3]/'research/quality_scope_comparison_20261010/frozen_engine/height_revision'
sys.path.insert(0,str(ENGINE))
from height_revision import directed_nearest_footprint_height_mse
sys.path.pop(0)


def centered_distance(a,g,n):
    mg = profile_moments(g)['mean']
    centered = align_mean(a,mg)
    ag = directed_nearest_footprint_height_mse(centered,g,n,'max')
    ga = directed_nearest_footprint_height_mse(g,centered,n,'max')
    return math.sqrt((ag['mse_h2']+ga['mse_h2'])/2)/mg


def flattened_reference(g):
    flat = deepcopy(g)
    mean = profile_moments(g)['mean']
    for b,t in zip(flat['bottom3d'],flat['top3d']): t[1] = b[1]+mean
    return flat


def exact_same_floor_centered(a,g):
    if a['bottom3d'] != g['bottom3d']:
        raise ValueError('Exact diagnostic requires same floor and partition')
    ap,gp = profile_moments(a),profile_moments(g)
    residual = [(ha-ap['mean'])-(hg-gp['mean']) for ha,hg in zip(ap['heights'],gp['heights'])]
    variance = math.fsum(w*(u*u+u*v+v*v)/3 for w,u,v in zip(ap['lengths'],residual,residual[1:]+residual[:1]))/ap['perimeter']
    return math.sqrt(variance)/gp['mean']


def support_fraction(g,reference_mean,level):
    p = profile_moments(g)
    d = [h-p['mean'] for h in p['heights']]
    cutoff = reference_mean*level
    def above(a,b):
        if a == b: return float(a > cutoff)
        crossing = min(1.,max(0.,(cutoff-a)/(b-a)))
        return 1-crossing if b>a else crossing
    return math.fsum(w*(above(a,b)+above(-a,-b)) for w,a,b in zip(p['lengths'],d,d[1:]+d[:1]))/p['perimeter']


def diagnostics(a,g):
    ap,gp = profile_moments(a),profile_moments(g)
    peak = max(abs(h-ap['mean']) for h in ap['heights'])
    return dict(annotation_mean=ap['mean'],reference_mean=gp['mean'],
                own_std_over_reference_mean=ap['std']/gp['mean'],reference_std_over_reference_mean=gp['std']/gp['mean'],
                peak_over_reference_mean=peak/gp['mean'],peak_over_own_std=peak/ap['std'] if ap['std'] else None,
                support10=support_fraction(a,gp['mean'],.1),support20=support_fraction(a,gp['mean'],.2))


def make_controls(widths,rms_values):
    # All variants share one floor partition, preventing vertex count from becoming a confound.
    knots = {0.,6.,10.,16.,8.,18.}
    for center in (8.,18.):
        for width in widths: knots.update((center-10*width,center+10*width))
    knots = sorted(knots)
    def bottom(s):
        if s < 6: return [-1+s,-1.,-2.]
        if s < 10: return [5.,-1.,-2+s-6]
        if s < 16: return [5-(s-10),-1.,2.]
        return [-1.,-1.,2-(s-16)]
    floor = [bottom(s) for s in knots]
    flat = dict(bottom3d=deepcopy(floor),top3d=[[p[0],1.4,p[2]] for p in floor])
    def bump(center,width,rms):
        profile = [max(0.,1-abs(s-center)/(10*width)) for s in knots]
        trial = dict(bottom3d=deepcopy(floor),top3d=[[p[0],1.4+v,p[2]] for p,v in zip(floor,profile)])
        moments = profile_moments(trial)
        trial['top3d'] = [[p[0],1.4+(h-moments['mean'])*2.4*rms/moments['std'],p[2]] for p,h in zip(floor,moments['heights'])]
        return trial
    cases = []
    for rms in rms_values:
        for width in widths:
            for ref_type in ('flat','nonflat_near'):
                reference = flat if ref_type=='flat' else bump(18,width,rms)
                for location,center in [('near',18),('far',8)]:
                    cases.append(dict(id=f'{ref_type}_{location}_w{width}_rms{rms}',reference_type=ref_type,location=location,
                                      tent_support_fraction=width,target_rms=rms,annotation=bump(center,width,rms),reference=deepcopy(reference)))
    return cases


def measure(a,g,nh,nt):
    return dict(Hcenter=centered_distance(a,g,nh),St=float(spherical_sym_distance(a['top3d'],g['top3d'],n=nt)))


def run(inputs,design):
    validate_development_gates([dict(record_id=r['id']) for r in inputs['rows']],inputs['gates'])
    nh,nt = design['height_samples'],design['top_samples']
    controls = []
    for c in make_controls(design['support_fractions'],design['rms_over_reference_mean']):
        a,g = c['annotation'],c['reference']
        controls.append(c | diagnostics(a,g) | measure(a,g,nh,nt) | dict(
            Hcenter_exact=exact_same_floor_centered(a,g),
            high_resolution=measure(a,g,design['verification_height_samples'],design['verification_top_samples'])))
    grouped = {}
    for r in sorted(inputs['rows'],key=lambda r:r['id']):
        grouped.setdefault(coordinate_key(r,inputs['geometries'][r['object_id']]),[]).append(r)
    records, unique, groups, geometry = [], [], [], {}
    parity, profile_parity = [], []
    for members in grouped.values():
        r = members[0]
        a,g = (inputs['geometries'][r[k]] for k in ('object_id','reference_object_id'))
        hc = centered_distance(a,g,nh)
        d = diagnostics(a,g)
        geometry[r['id']] = (a,g)
        groups.append(dict(representative=r['id'],members=[m['id'] for m in members]))
        for m in members:
            parity.append(abs(hc-m['metrics']['Hcenter']))
            for key,frozen in [('own_std_over_reference_mean','annotation_own_height_std_over_gt_mean'),
                               ('peak_over_reference_mean','annotation_max_abs_deviation_from_own_mean_over_gt_mean'),
                               ('support10','annotation_support_gtmean_10'),('support20','annotation_support_gtmean_20')]:
                profile_parity.append(abs(d[key]-m['profile'][frozen]))
            out = {k:m[k] for k in ('id','image_id','image_code','building_id','applicability_confirmed')}
            out |= d | dict(coordinate_representative=r['id'],Hcenter=hc,St_frozen=m['metrics']['S_top_deg'],
                            Hcenter_own_std_gap=abs(hc-d['own_std_over_reference_mean']))
            records.append(out)
            if m is r: unique.append(out)
    if max(parity+profile_parity)>1e-9:
        raise ValueError(('Frozen Hcenter/profile mismatch',max(parity),max(profile_parity)))
    selections, strata = {}, {}
    for name,qualification in [('all',None),('confirmed',True),('unknown',False)]:
        rows=[r for r in unique if qualification is None or r['applicability_confirmed']==qualification]
        strata[name]=dict(records=sum(qualification is None or r['applicability_confirmed']==qualification for r in records),coordinate_groups=len(rows),
                         **{key:distribution([r[key] for r in rows if r[key] is not None]) for key in ('peak_over_own_std','peak_over_reference_mean','support20','reference_std_over_reference_mean','Hcenter_own_std_gap')})
        if qualification is None: continue
        for key in ('peak_over_own_std','support20','reference_std_over_reference_mean','Hcenter_own_std_gap'):
            for r in sorted([r for r in rows if r[key] is not None],key=lambda r:(-r[key],r['id']))[:3]:
                selections.setdefault(r['id'],[]).append(f'{name}:{key}')
    selected = []
    for rid,reasons in selections.items():
        r=next(r for r in unique if r['id']==rid)
        a,g=geometry[rid]
        selected.append(r | dict(reasons=reasons,human_grade=None,
                                high_resolution=measure(a,g,design['verification_height_samples'],design['verification_top_samples']),
                                flat_reference_Hcenter=centered_distance(a,flattened_reference(g),nh)))
    return dict(schema='quality_local_profile_results_v1',controls=controls,records=records,coordinate_groups=groups,selected_cases=selected,strata=strata,
                verification=dict(frozen_replays=len(records),maximum_frozen_Hcenter_error=max(parity),maximum_frozen_profile_error=max(profile_parity),
                                  maximum_control_Hcenter_exact_error=max(abs(c['Hcenter']-c['Hcenter_exact']) for c in controls),
                                  maximum_control_high_Hcenter_exact_error=max(abs(c['high_resolution']['Hcenter']-c['Hcenter_exact']) for c in controls),
                                  selected_high_resolution_groups=len(selected),
                                  maximum_selected_Hcenter_resolution_change=max(abs(r['Hcenter']-r['high_resolution']['Hcenter']) for r in selected),
                                  maximum_selected_St_resolution_change=max(abs(r['St_frozen']-r['high_resolution']['St']) for r in selected),
                                  maximum_control_St_resolution_change=max(abs(c['St']-c['high_resolution']['St']) for c in controls)),
                scope=dict(new_scores_computed=False,new_human_grades=False,holdout_used=False,raw_inputs_modified=False))


def figure(result,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    widths=[.04,.1,.18]
    for width,color in zip(widths,['#b44b43','#146c94','#698c42']):
        c=next(c for c in result['controls'] if c['reference_type']=='flat' and c['location']=='near' and c['target_rms']==.05 and c['tent_support_fraction']==width)
        p=profile_moments(c['annotation'])
        x=np.r_[0,np.cumsum(p['lengths'])]/p['perimeter']
        y=[100*(h-p['mean'])/c['reference_mean'] for h in p['heights']]
        axes[0].plot(x,y+y[:1],color=color,label=f'Tent support {width:.0%}; peak {100*c["peak_over_reference_mean"]:.1f}%')
    axes[0].axhline(0,lw=.6,color='grey')
    axes[0].set(xlabel='Fraction of floor perimeter',ylabel='Height deviation / reference mean (%)',title='Same floor and mean; exact local RMS = 5%')
    axes[0].legend(fontsize=8)
    for offset,location,color in [(-.18,'near','#146c94'),(.18,'far','#9babb7')]:
        vals=[next(c['St'] for c in result['controls'] if c['reference_type']=='flat' and c['location']==location and c['target_rms']==.05 and c['tent_support_fraction']==w) for w in widths]
        bars=axes[1].bar(np.arange(3)+offset,vals,.36,color=color,label=f'{location.capitalize()} wall')
        axes[1].bar_label(bars,fmt='%.3f',padding=2,fontsize=9)
    axes[1].set(xticks=np.arange(3),xticklabels=['4%','10%','18%'],xlabel='Tent support before mean removal',ylabel='Top spherical distance (degrees)',title='Flat reference: taller narrow peaks can have smaller St',ylim=(0,2))
    axes[1].legend(fontsize=8)
    fig.savefig(path,dpi=170)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,default=Path('research/quality_top_height_response_20261012'))
    p.add_argument('--figures',action='store_true')
    args=p.parse_args()
    result=run(read_json(args.study/'inputs.json'),read_json(args.study/'local_profile_design.json'))
    save_json(args.study/'local_profile.json',result)
    if args.figures: figure(result,args.study/'local_profile.png')
    print(result['verification'])


if __name__=='__main__': main()
