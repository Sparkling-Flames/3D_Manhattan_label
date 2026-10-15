#!/usr/bin/env python3
"""Replay v1 geometry and a limited, label-free height-component comparison.

No old grade/remark is read. No held-out expanded-image score is read. The
new figures in this development study are constructed known-geometry controls.
"""
import argparse
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from height_revision import (HEIGHT_KEYS,height_candidates,height_moments,
                             score_from_components)


def dump(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def score_candidates(row):
    for key in HEIGHT_KEYS:
        label=key.removeprefix('H_')
        for tau in [.4,.5,.6]:
            row[f'Q_{label}_tau_{tau:g}']=score_from_components(row,key,tau)
        row[f'delta_{label}_vs_v1']=row[f'Q_{label}_tau_0.5']-row['Q_v1_mean_tau_0.5']
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('source/oct8-pro-quality-handoff'))
    p.add_argument('--v1-code',type=Path,default=Path('work/research_v1/geometry'))
    p.add_argument('--v1-results',type=Path,default=Path('work/research_v1/geometry/results_v3'))
    p.add_argument('--v1-height-results',type=Path,default=Path('work/research_v1/height_guard/final_results'))
    p.add_argument('--audit',type=Path,default=Path('work/research_v1_1/new_independent_audit/layout_quality_v1_independent_audit'))
    p.add_argument('--out',type=Path,default=Path('work/research_v1_1/height_revision/results'))
    p.add_argument('--height-samples',type=int,default=4096)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(a.v1_code.resolve()))
    from geometry_experiments import room,xz_scale,top_shift,top_warp,translate,subdivision,lowest_elevation_pixel_shift
    from audit_geometry import area_metrics,own_metrics
    from geometric_components import additional_components
    frozen=json.loads((a.source/'inputs/frozen_geometry.json').read_text())
    identities={g['id']:g for im in frozen['images'] for g in im['annotations']+im['groundtruths']}
    real=pd.read_csv(a.v1_results/'real_metrics36.csv',usecols=lambda c:c!='human_score_original')
    replays=[]
    geometry_pairs=[]
    for r in real.to_dict('records'):
        an,gt=identities[r['record_id']],identities[r['reference_id']]
        r.update(height_candidates(an,gt,samples=a.height_samples))
        r['case_id']=r['review_id'];r['case_kind']='old36_development_replay'
        replays.append(score_candidates(r))
        geometry_pairs.append(dict(case_id=r['review_id'],annotation=an,reference=gt))
    real_out=pd.DataFrame(replays)
    real_out.to_csv(a.out/'old36_height_candidate_replay.csv',index=False,encoding='utf-8-sig')

    old_metrics=pd.read_csv(a.v1_results/'control_metrics.csv').set_index('case_id')
    old_geometry=json.loads((a.v1_results/'control_geometries.json').read_text())
    old_rows=[]
    for r in old_geometry:
        row=old_metrics.loc[r['case_id']].to_dict();row['case_id']=r['case_id']
        row.update(height_candidates(r['annotation'],r['reference'],samples=a.height_samples))
        old_rows.append(score_candidates(row))
    old_out=pd.DataFrame(old_rows)
    old_out.to_csv(a.out/'existing251_height_candidate_replay.csv',index=False,encoding='utf-8-sig')

    old9metrics=pd.read_csv(a.v1_height_results/'large_room_uniform_height9.csv').set_index('case_id')
    old9geo=json.loads((a.v1_height_results/'large_room_uniform_height9_geometries.json').read_text())
    rows9=[]
    for r in old9geo:
        row=old9metrics.loc[r['case_id']].to_dict();row['case_id']=r['case_id']
        row.update(height_candidates(r['annotation'],r['reference'],samples=a.height_samples))
        rows9.append(score_candidates(row))
    pd.DataFrame(rows9).to_csv(a.out/'existing9_mean_height_replay.csv',index=False,encoding='utf-8-sig')

    new_rows=[];new_geometry=[]
    def add(case_id,family,annotation,reference,**metadata):
        row=dict(case_id=case_id,family=family,**metadata)
        row.update(additional_components(annotation,reference,n=2048,
                   base={**area_metrics(annotation,reference),**own_metrics(annotation)}))
        row.update(height_candidates(annotation,reference,samples=a.height_samples))
        new_rows.append(score_candidates(row))
        new_geometry.append(dict(case_id=case_id,family=family,**metadata,annotation=annotation,reference=reference))

    audit=json.loads((a.audit/'numeric/independent_counterexample_geometries.json').read_text())
    for r in audit:
        if r['case'].startswith('alternating_height'):
            add(r['case'],'audit_alternating',r['annotation'],r['reference'],
                xz_scale=float(r['case'].split('_')[-1]),height_amplitude_h=.99)

    rect=room([[-3,-2],[3,-2],[3,2],[-3,2]],top=1.)
    for k in [1.,4.,16.,64.]:
        g=xz_scale(rect,k)
        for amp in [.002,.02,.1,.2,.5,.99,1.5,1.98]:
            add(f'alt_k{k:g}_a{amp:g}','alternating_amplitude',top_warp(g,amp),g,
                xz_scale=k,height_amplitude_h=amp)
        for delta in [-.99,-.2,-.02,.02,.2,.99,3.]:
            add(f'uniform_k{k:g}_delta{delta:g}','uniform_signed_height',top_shift(g,delta),g,
                xz_scale=k,height_shift_h=delta)
        for delta,amp in [(.02,.02),(.1,.1),(.2,.2),(.5,.5)]:
            add(f'mixed_k{k:g}_d{delta:g}_a{amp:g}','mixed_mean_variance',
                top_shift(top_warp(g,amp),delta),g,xz_scale=k,height_shift_h=delta,height_amplitude_h=amp)

        # A positive triangular pulse and an equal negative opposite-wall pulse.
        # Footprint stays the exact same rectangle; added floor nodes are valid
        # collinear subdivisions, but top curvature intentionally changes.
        for w in [.01,.05,.25,.5,1.,2.]:
            foot=np.array([[-3,-2],[-w,-2],[0,-2],[w,-2],[3,-2],[3,2],
                           [w,2],[0,2],[-w,2],[-3,2]],float)*k
            tops=np.ones(10);tops[2]+=.99;tops[7]-=.99
            pred=room(foot,top=tops)
            add(f'local_cancel_k{k:g}_halfwidth{w:g}','local_signed_pulse_width',pred,g,
                xz_scale=k,local_pulse_halfwidth_before_scale_h=w,height_amplitude_h=.99)

        nonflat=top_warp(g,.99)
        inverse=top_warp(g,-.99)
        add(f'nonflat_copy_k{k:g}','nonflat_reference_copy',nonflat,nonflat,xz_scale=k)
        add(f'nonflat_inverse_k{k:g}','nonflat_reference_phase_inverse',inverse,nonflat,xz_scale=k)
        add(f'nonflat_flatten_k{k:g}','nonflat_reference_flatten',g,nonflat,xz_scale=k)

        # Both geometries lie on the same sloping top plane but have different
        # footprints. Nearest-footprint height residual is not the discrepancy
        # between those two height fields evaluated at the SAME world point.
        bg=np.array(g['bottom3d'])
        nonflat_plane=room(bg[:,[0,2]],top=1+.99*bg[:,0]/(3*k))
        for frac in [.01,.1,.25]:
            dx=frac*6*k
            shifted=translate(nonflat_plane,dx)
            field_correct=copy.deepcopy(shifted)
            for point in field_correct['top3d']:
                point[1]=1+.99*point[0]/(3*k)
            add(f'plane_range_shift_k{k:g}_frac{frac:g}','same_sloped_field_changed_range',
                field_correct,nonflat_plane,xz_scale=k,footprint_shift_fraction_width=frac)
            add(f'plane_translated_k{k:g}_frac{frac:g}','sloped_plane_co_moving_height',
                shifted,nonflat_plane,xz_scale=k,footprint_shift_fraction_width=frac)
    new_out=pd.DataFrame(new_rows)
    new_out.to_csv(a.out/'new_height_controls.csv',index=False,encoding='utf-8-sig')
    dump(a.out/'new_height_control_geometries.json',new_geometry)

    # A finite nearest-wall tie is a correspondence ambiguity, not an invalid
    # loop: a small rectangle may sit midway between two distant target walls.
    reference=room([[-3,-2],[3,-2],[3,2],[-3,2]],top=[.1,.1,1.9,1.9])
    annotation=room([[-1,-.1],[1,-.1],[1,.1],[-1,.1]],top=1.)
    add('nearest_wall_narrow_midroom','nearest_wall_correspondence',annotation,reference)
    for dx in [-1e-5,-1e-7,0.,1e-7,1e-5]:
        thin=room([[-1,0],[1,0],[1,.1],[-1,.1]],top=.1)
        shifted=translate(thin,0,dx)
        add(f'nearest_tie_shift_{dx:g}','nearest_height_correspondence_switch',
            shifted,reference,footprint_delta_h=dx)

    convergence=[]
    score_lookup={r['case_id']:r for r in new_rows+replays+old_rows+rows9}
    all_geometries=new_geometry+geometry_pairs+old_geometry+old9geo
    for r in all_geometries:
        an,gt=r['annotation'],r['reference']
        cached={n:height_candidates(an,gt,samples=n) for n in [2048,4096,8192]}
        base=score_lookup[r['case_id']]
        qmax=score_from_components({**base,**cached[8192]},'H_mean_nearest_max')
        for n in [2048,4096]:
            qn=score_from_components({**base,**cached[n]},'H_mean_nearest_max')
            convergence.append(dict(case_id=r['case_id'],samples=n,
                H_nearest_footprint=cached[n]['H_nearest_footprint'],
                H_nearest_footprint_8192=cached[8192]['H_nearest_footprint'],
                absolute_H_difference=abs(cached[n]['H_nearest_footprint']-cached[8192]['H_nearest_footprint']),
                Hstar=cached[n]['H_mean_nearest_max'],Hstar_8192=cached[8192]['H_mean_nearest_max'],
                Q_Hstar=qn,Q_Hstar_8192=qmax,absolute_Q_difference=abs(qn-qmax)))
    pd.DataFrame(convergence).to_csv(a.out/'nearest_height_sampling_convergence.csv',index=False,encoding='utf-8-sig')

    invariance=[]
    for r in geometry_pairs+new_geometry[::5]:
        an,gt=r['annotation'],r['reference']
        base=height_candidates(an,gt,samples=a.height_samples)
        for factor in [2,3,7]:
            split=height_candidates(subdivision(an,factor),subdivision(gt,factor),samples=a.height_samples)
            for key in HEIGHT_KEYS:
                invariance.append(dict(case_id=r['case_id'],subdivision_factor=factor,component=key,
                                       original=base[key],subdivided=split[key],absolute_difference=abs(base[key]-split[key])))
        nonuniform={}
        # Exactly the same paired 3D segments at unequal fractional lengths.
        for key in ['bottom3d','top3d']:
            ring=np.array(an[key],float)
            nonuniform[key]=np.array([u+t*(v-u) for j,(u,v) in enumerate(zip(ring,np.roll(ring,-1,axis=0)))
                                     for t in ([0,.03,.13,.87] if j%2 else [0,.001,.3,.3001,.91])]).tolist()
        split=height_candidates(nonuniform,gt,samples=a.height_samples)
        for key in HEIGHT_KEYS:
            invariance.append(dict(case_id=r['case_id'],subdivision_factor='nonuniform_annotation_only',component=key,
                                   original=base[key],subdivided=split[key],absolute_difference=abs(base[key]-split[key])))
    pd.DataFrame(invariance).to_csv(a.out/'height_subdivision_invariance.csv',index=False,encoding='utf-8-sig')

    summaries=[]
    allsets=[('old36',real_out),('existing251',old_out),('old9',pd.DataFrame(rows9)),('new_controls',pd.DataFrame(new_rows))]
    for name,frame in allsets:
        for key in HEIGHT_KEYS:
            label=key.removeprefix('H_')
            d=frame[f'delta_{label}_vs_v1']
            summaries.append(dict(dataset=name,n=len(frame),candidate=key,
                min_delta_points=float(d.min()),median_delta_points=float(d.median()),
                max_delta_points=float(d.max()),
                largest_drop_case=str(frame.loc[d.idxmin(),'case_id']),
                height_scale=.5))
    pd.DataFrame(summaries).to_csv(a.out/'candidate_replay_summary.csv',index=False,encoding='utf-8-sig')

    controls_with_pixel=old_out[old_out.family.isin(['real_reference_horizon_pixel_shift','same_one_pixel_lower_error_vs_depth'])]
    controls_with_pixel.to_csv(a.out/'pixel_noise_replay29.csv',index=False,encoding='utf-8-sig')
    # Final write includes the explicit correspondence example appended above.
    pd.DataFrame(new_rows).to_csv(a.out/'new_height_controls.csv',index=False,encoding='utf-8-sig')
    dump(a.out/'new_height_control_geometries.json',new_geometry)

    inv=pd.DataFrame(invariance); conv=pd.DataFrame(convergence)
    out_summary=dict(old36=len(real_out),existing_controls=len(old_out),existing_mean_controls=len(rows9),
        new_controls=len(new_rows),candidate_count=len(HEIGHT_KEYS),height_scales=[.4,.5,.6],
        max_subdivision_H_difference=float(inv.absolute_difference.max()),
        frozen_height_samples=a.height_samples,
        max_nearest_2048_vs_8192_H_difference=float(conv[conv.samples.eq(2048)].absolute_H_difference.max()),
        max_nearest_4096_vs_8192_H_difference=float(conv[conv.samples.eq(4096)].absolute_H_difference.max()),
        max_nearest_2048_vs_8192_Q_difference=float(conv[conv.samples.eq(2048)].absolute_Q_difference.max()),
        max_nearest_4096_vs_8192_Q_difference=float(conv[conv.samples.eq(4096)].absolute_Q_difference.max()),
        exact_rms_identity_max_error=float(max(abs(r['H_rms_about_gt_mean']-r['direct_rms_about_gt_mean_check']) for _,fr in allsets for r in fr.to_dict('records'))),
        grade_columns_read=False,expanded_holdout_scores_read=False,
        input_geometry_sha256=hashlib.sha256((a.source/'inputs/frozen_geometry.json').read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        component_code_sha256=hashlib.sha256(Path(__file__).with_name('height_revision.py').read_bytes()).hexdigest())
    dump(a.out/'height_revision_experiment_summary.json',out_summary)
    print(json.dumps(out_summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
