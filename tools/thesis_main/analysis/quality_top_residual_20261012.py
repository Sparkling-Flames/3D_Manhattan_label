"""均高对齐后的顶部球面距离诊断；不生成新的质量分。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys

if __package__:
    from .quality_top_height_response_20261012 import analytic_case, distribution, profile_moments, read_json, save_json, validate_development_gates
    from .quality_height_conditioning_20261012 import coordinate_key, perturb_bottom
else:
    from quality_top_height_response_20261012 import analytic_case, distribution, profile_moments, read_json, save_json, validate_development_gates
    from quality_height_conditioning_20261012 import coordinate_key, perturb_bottom

ENGINE = Path(__file__).resolve().parents[3] / 'research/quality_scope_comparison_20261010/frozen_engine/legacy_geometry'
sys.path.insert(0, str(ENGINE))
from geometric_components import spherical_sym_distance
sys.path.pop(0)


def align_mean(geometry, target_mean):
    shifted = deepcopy(geometry)
    delta = target_mean - profile_moments(geometry)['mean']
    for point in shifted['top3d']:
        point[1] += delta
    return shifted


def aligned_distance(a, g, samples):
    minimum = min(p[1] for geo in (a, g) for p in geo['top3d'])
    return dict(status='available' if minimum > 0 else 'out_of_camera_domain',
                minimum_top_y=minimum,
                deg=float(spherical_sym_distance(a['top3d'], g['top3d'], n=samples)) if minimum > 0 else None)


def diagnose(a, g, samples):
    ma, mg = profile_moments(a)['mean'], profile_moments(g)['mean']
    original = aligned_distance(a, g, samples)
    to_g = aligned_distance(align_mean(a, mg), g, samples)
    to_a = aligned_distance(a, align_mean(g, ma), samples)
    return dict(original_camera_domain=original['status'] == 'available',
                original_minimum_top_y=original['minimum_top_y'], original_deg=original['deg'],
                annotation_mean=ma, reference_mean=mg, mean_delta=ma-mg,
                to_reference=to_g, to_annotation=to_a,
                change_deg=to_g['deg']-original['deg'] if to_g['deg'] is not None and original['deg'] is not None else None,
                alignment_gap_deg=abs(to_g['deg']-to_a['deg']) if to_g['deg'] is not None and to_a['deg'] is not None else None)


def make_controls(scales):
    cases = []
    for scale in scales:
        for family, ratio, rms in [('exact',1,0), ('global_low_20pct',.8,0),
                                   ('global_high_20pct',1.2,0), ('local_rms_10pct',1,.1),
                                   ('global_low_plus_local',.8,.1), ('floor_radial_20pct',1,0),
                                   ('floor_radial_and_cancelled_projection',1,0),
                                   ('fixed_top_all_bottom_plus1px',1,0), ('nonflat_exact',1,.1)]:
            c = analytic_case(ratio, rms)
            # The analytic helper shares an unchanged floor; these controls mutate it.
            a, g = deepcopy(c['annotation']), deepcopy(c['reference'])
            for geo in (a, g):
                for ring in geo.values():
                    for point in ring:
                        point[0] *= scale
                        point[2] *= scale
            if family.startswith('floor_radial'):
                for ring in a.values():
                    for point in ring:
                        point[0] *= 1.2
                        point[2] *= 1.2
                if family == 'floor_radial_and_cancelled_projection':
                    for point in a['top3d']: point[1] *= 1.2
            if family == 'fixed_top_all_bottom_plus1px':
                a = perturb_bottom(a, range(4), 1, 512)['geometry']
            if family == 'nonflat_exact': g = deepcopy(a)
            cases.append(dict(id=f'{family}_scale{scale}',family=family,scale=scale,annotation=a,reference=g))
    cases.append(dict(id='alignment_domain',family='alignment_out_of_camera_domain',scale=1,
                      annotation=analytic_case(1,.2)['annotation'],reference=analytic_case(.5,0)['annotation']))
    return cases


def statistics(rows):
    available = [r for r in rows if r['change_deg'] is not None]
    gap = [r for r in rows if r['alignment_gap_deg'] is not None]
    return dict(count=len(rows),available=len(available),
                increased_count=sum(r['change_deg'] > 1e-8 for r in available),
                original_deg=distribution([r['original_deg'] for r in rows if r['original_deg'] is not None]),
                aligned_deg=distribution([r['to_reference']['deg'] for r in available]),
                change_deg=distribution([r['change_deg'] for r in available]),
                alignment_gap_deg=distribution([r['alignment_gap_deg'] for r in gap]))


def run(inputs, design):
    validate_development_gates([dict(record_id=r['id']) for r in inputs['rows']], inputs['gates'])
    rows = sorted(inputs['rows'], key=lambda r:r['id'])
    groups = {}
    for r in rows:
        groups.setdefault(coordinate_key(r,inputs['geometries'][r['object_id']]),[]).append(r)
    unique, records, group_list, parity, geometries = [], [], [], [], {}
    for members in groups.values():
        r = members[0]
        a,g = (inputs['geometries'][r[k]] for k in ('object_id','reference_object_id'))
        d = diagnose(a,g,design['samples'])
        geometries[r['id']] = (a,g)
        group_list.append(dict(representative=r['id'],members=[m['id'] for m in members]))
        for m in members:
            if d['original_deg'] is None:
                raise ValueError(('Original development geometry outside camera domain',m['id']))
            parity.append(abs(d['original_deg']-m['metrics']['S_top_deg']))
            out = {k:m[k] for k in ('id','image_id','image_code','building_id','applicability_confirmed')}
            out |= dict(coordinate_representative=r['id'],Hcenter_frozen=m['metrics']['Hcenter'],
                        S_bottom_frozen=m['metrics']['S_bottom_deg'],iou_2d_frozen=m['metrics']['iou_2d']) | d
            records.append(out)
            if m is r: unique.append(out)
    if max(parity) > 1e-9:
        raise ValueError(('Frozen St replay mismatch',max(parity)))
    strata, selected = {}, {}
    for name, qualification in [('all',None),('confirmed',True),('unknown',False)]:
        rr = [r for r in records if qualification is None or r['applicability_confirmed'] == qualification]
        uu = [r for r in unique if qualification is None or r['applicability_confirmed'] == qualification]
        strata[name] = dict(record_statistics=statistics(rr),coordinate_group_statistics=statistics(uu))
        if qualification is None: continue
        for key in ('original_deg','change_deg','alignment_gap_deg','aligned_deg'):
            value = lambda r:r['to_reference']['deg'] if key == 'aligned_deg' else r[key]
            for r in sorted([r for r in uu if value(r) is not None],key=lambda r:(-value(r),r['id']))[:3]:
                selected.setdefault(r['id'],[]).append(f'{name}:{key}')
    t20 = next(r for r in records if r['id']=='R00397')
    selected.setdefault(t20['coordinate_representative'],[]).append('reviewed_T20')
    selected_rows = []
    for rid,reasons in selected.items():
        r = next(r for r in unique if r['id']==rid)
        high = diagnose(*geometries[rid],design['verification_samples'])
        selected_rows.append(r | dict(reasons=reasons,human_grade=None,high_resolution=high))
    controls = []
    for c in make_controls(design['controls']['horizontal_scales']):
        controls.append(c | dict(diagnostic=diagnose(c['annotation'],c['reference'],design['samples']),
                                high_resolution=diagnose(c['annotation'],c['reference'],design['verification_samples'])))
    errors = []
    for low,high in [(r,r['high_resolution']) for r in selected_rows]+[(c['diagnostic'],c['high_resolution']) for c in controls]:
        for key in ('original_deg','to_reference','to_annotation'):
            x,y = (low[key],high[key]) if key == 'original_deg' else (low[key]['deg'],high[key]['deg'])
            if x is not None and y is not None: errors.append(abs(x-y))
    return dict(schema='quality_top_residual_results_v1',records=records,coordinate_groups=group_list,
                strata=strata,selected_cases=selected_rows,controls=controls,reviewed_T20=t20,
                verification=dict(frozen_scalar_replays=len(parity),maximum_frozen_St_error=max(parity),
                                  high_resolution_real_groups=len(selected_rows),high_resolution_controls=len(controls),
                                  maximum_2048_8192_difference_deg=max(errors)),
                scope=dict(new_scores_computed=False,new_human_grades=False,holdout_used=False,
                           raw_input_repaired=False,full_layout_validity_recertified=False))


def figure(result, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    representatives = {g['representative'] for g in result['coordinate_groups']}
    unique = [r for r in result['records'] if r['id'] in representatives]
    fig, axes = plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for qualification,color,label in [(False,'#9babb7','Applicability unknown (625)'),(True,'#146c94','Applicability confirmed (114)')]:
        rows = [r for r in unique if r['applicability_confirmed'] == qualification]
        axes[0].scatter([r['original_deg'] for r in rows],[r['to_reference']['deg'] for r in rows],s=15,c=color,alpha=.65,label=label)
    axes[0].plot([0,23],[0,23],color='black',lw=.8,ls='--')
    for rid,label in [('R00397','T20'),('R03346','R03346'),('R02330','R02330')]:
        r = next(r for r in unique if r['id']==rid)
        axes[0].annotate(label,(r['original_deg'],r['to_reference']['deg']),xytext=(8,5),textcoords='offset points',fontsize=9)
    axes[0].set(xlabel='Original top distance (degrees)',ylabel='After aligning annotation mean to reference (degrees)',title='739 distinct coordinate groups; no new quality labels')
    axes[0].legend(fontsize=8,loc='lower right')
    families = ['global_low_20pct','local_rms_10pct','floor_radial_20pct','floor_radial_and_cancelled_projection','fixed_top_all_bottom_plus1px']
    cases = [next(c for c in result['controls'] if c['scale']==2 and c['family']==family)['diagnostic'] for family in families]
    x = np.arange(len(cases))
    for offset,key,label,color in [(-.18,'original_deg','Original','#9babb7'),(.18,'to_reference','Mean aligned','#146c94')]:
        values = [c[key] if key=='original_deg' else c[key]['deg'] for c in cases]
        bars = axes[1].bar(x+offset,values,.36,label=label,color=color)
        axes[1].bar_label(bars,fmt='%.2f',fontsize=8,padding=2)
    axes[1].set(xticks=x,xticklabels=['Global\n-20%','Local\nRMS 10%','Floor\n+20%','Floor/top\ncancellation','Bottom\n+1 px'],ylabel='Top distance (degrees)',title='Fixed square controls, horizontal scale = 2',ylim=(0,11))
    axes[1].legend(fontsize=8)
    fig.savefig(path,dpi=170)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=Path('research/quality_top_height_response_20261012'))
    parser.add_argument('--figures',action='store_true')
    args = parser.parse_args()
    result = run(read_json(args.study/'inputs.json'),read_json(args.study/'top_residual_design.json'))
    save_json(args.study/'top_residual.json',result)
    if args.figures: figure(result,args.study/'top_residual.png')
    print(result['verification'])
    for name,s in result['strata'].items():
        print(name,s['coordinate_group_statistics'])


if __name__ == '__main__': main()
