#!/usr/bin/env python3
"""Extra numeric checks for the selected low-complexity Hstar candidate."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

from height_revision import HEIGHT_KEYS,height_candidates,height_components,score_from_components


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('source/oct8-pro-quality-handoff'))
    p.add_argument('--v1-geometry',type=Path,default=Path('work/research_v1/geometry/results_v3'))
    p.add_argument('--v1-height',type=Path,default=Path('work/research_v1/height_guard/final_results'))
    p.add_argument('--results',type=Path,default=Path('work/research_v1_1/height_revision/results_4096'))
    a=p.parse_args()
    frozen=json.loads((a.source/'inputs/frozen_geometry.json').read_text())
    ids={g['id']:g for im in frozen['images'] for g in im['annotations']+im['groundtruths']}
    real=pd.read_csv(a.results/'old36_height_candidate_replay.csv')
    geos=[dict(case_id=r['case_id'],annotation=ids[r['record_id']],reference=ids[r['reference_id']],dataset='old36')
          for r in real.to_dict('records')]
    frames=[real]
    for name,path,framefile in [
        ('old251',a.v1_geometry/'control_geometries.json','existing251_height_candidate_replay.csv'),
        ('old9',a.v1_height/'large_room_uniform_height9_geometries.json','existing9_mean_height_replay.csv'),
        ('new148',a.results/'new_height_control_geometries.json','new_height_controls.csv')]:
        geos.extend({**r,'dataset':name} for r in json.loads(path.read_text()))
        frames.append(pd.read_csv(a.results/framefile))
    lookup={r['case_id']:r for frame in frames for r in frame.to_dict('records')}

    ties=[];times=[]
    for r in geos:
        start=time.perf_counter()
        cmax=height_candidates(r['annotation'],r['reference'],4096,tie_rule='max')
        times.append(time.perf_counter()-start)
        cmin=height_candidates(r['annotation'],r['reference'],4096,tie_rule='min')
        base=lookup[r['case_id']]
        qmax=score_from_components({**base,**cmax},'H_mean_nearest_max')
        qmin=score_from_components({**base,**cmin},'H_mean_nearest_max')
        ties.append(dict(case_id=r['case_id'],dataset=r['dataset'],
            AG_distinct_height_tie_fraction=cmax['nearest_AG_tied_height_fraction'],
            GA_distinct_height_tie_fraction=cmax['nearest_GA_tied_height_fraction'],
            AG_tied_height_range_h=cmax['nearest_AG_tied_height_range_h'],
            GA_tied_height_range_h=cmax['nearest_GA_tied_height_range_h'],
            Hstar_max=cmax['H_mean_nearest_max'],Hstar_min=cmin['H_mean_nearest_max'],
            absolute_Hstar_delta=abs(cmax['H_mean_nearest_max']-cmin['H_mean_nearest_max']),
            Q_max=qmax,Q_min=qmin,absolute_Q_delta=abs(qmax-qmin)))
    tieframe=pd.DataFrame(ties)
    tieframe.to_csv(a.results/'nearest_tie_rule_sensitivity444.csv',index=False,encoding='utf-8-sig')

    # A common offset must not inflate tie tolerance or destroy the identity
    # Hlocal(A,A)=0 for an otherwise representable nonflat valid rectangle.
    translations=[]
    selected=[r for r in geos if r['dataset']=='old36' or
              r.get('family') in ['audit_alternating','nonflat_reference_copy','nonflat_reference_phase_inverse',
                                  'nearest_height_correspondence_switch']]
    for r in selected:
        base=height_components(r['annotation'],r['reference'])
        for dx,dz in [(1e6,0.),(1e8,0.),(1e8,-1e8)]:
            transformed=[]
            for ring in [r['annotation'],r['reference']]:
                new={}
                for key in ['top3d','bottom3d']:
                    coords=np.array(ring[key],float,copy=True)
                    coords[:,0]+=dx;coords[:,2]+=dz
                    new[key]=coords.tolist()
                transformed.append(new)
            changed=height_components(*transformed)
            translations.append(dict(case_id=r['case_id'],dx_h=dx,dz_h=dz,
                Hstar_original=base['Hstar'],Hstar_translated=changed['Hstar'],
                absolute_Hstar_difference=abs(base['Hstar']-changed['Hstar']),
                Hlocal_original=base['Hlocal'],Hlocal_translated=changed['Hlocal'],
                absolute_Hlocal_difference=abs(base['Hlocal']-changed['Hlocal']),
                translated_AG_tie_fraction=changed['diagnostics']['nearest_AG_tied_height_fraction']))
    tf=pd.DataFrame(translations)
    tf.to_csv(a.results/'common_large_translation_height_checks.csv',index=False,encoding='utf-8-sig')

    invariance=pd.read_csv(a.results/'height_subdivision_invariance.csv')
    convergence=pd.read_csv(a.results/'nearest_height_sampling_convergence.csv')
    new=frames[-1]
    checks=[]
    def check(name,passed,**details):checks.append(dict(check=name,passed=bool(passed),**details))
    for name,frame in zip(['old36','old251','old9','new148'],frames):
        q=frame.Q_mean_nearest_max_tau_0_5 if 'Q_mean_nearest_max_tau_0_5' in frame else frame['Q_mean_nearest_max_tau_0.5']
        i=frame.iou.clip(0,1)
        upper=100*i/(1+(frame.H_v1_mean/.5)**2)
        check(name+'_retains_v1_mean_height_and_iou_cap',(q<=upper+1e-10).all())
        check(name+'_never_scores_above_v1',(q<=frame['Q_v1_mean_tau_0.5']+1e-10).all())
        check(name+'_four_moments_exact_identity',np.allclose(frame.H_rms_about_gt_mean,frame.direct_rms_about_gt_mean_check,atol=1e-12,rtol=0))
    old9=frames[2]
    check('old9_uniform_errors_unchanged',np.allclose(old9['Q_mean_nearest_max_tau_0.5'],old9['Q_v1_mean_tau_0.5'],atol=1e-10,rtol=0))
    check('all_subdivision_H_deltas_under_1e_10',(invariance.absolute_difference<1e-10).all(),n=len(invariance),max_H_delta=float(invariance.absolute_difference.max()))
    check('4096_vs_8192_Q_under_0p01',(convergence[convergence.samples.eq(4096)].absolute_Q_difference<.01).all(),n=int(convergence.samples.eq(4096).sum()))
    check('common_1e6_1e8_translation_height_stable',(tf.absolute_Hlocal_difference<1e-5).all(),
          n=len(tf),max_H_difference=float(tf.absolute_Hlocal_difference.max()))
    self_shift=tf[tf.case_id.str.startswith('nonflat_copy')]
    check('translated_nonflat_self_Hlocal_zero',(self_shift.Hlocal_translated<1e-12).all(),
          n=len(self_shift),max_Hlocal=float(self_shift.Hlocal_translated.max()))
    # Analytic alternating same-footprint RMS: linear ramp ±amplitude has
    # integral amplitude²/3, independent of physical XZ size.
    alt=new[new.family.isin(['audit_alternating','alternating_amplitude'])]
    expected=alt.height_amplitude_h/(2*np.sqrt(3))
    check('alternating_analytic_exact_moment_RMS',np.allclose(alt.H_rms_about_gt_mean,expected,atol=1e-12,rtol=0))
    check('alternating_nearest_height_RMS_numeric',np.allclose(alt.H_nearest_footprint,expected,atol=1e-6,rtol=0),max_error=float((alt.H_nearest_footprint-expected).abs().max()))
    copy=new[new.family.eq('nonflat_reference_copy')]
    check('valid_nonflat_reference_self_Hstar_zero',(copy.H_mean_nearest_max<1e-12).all())
    for k,g in new[new.family.eq('alternating_amplitude')].groupby('xz_scale'):
        seq=g.sort_values('height_amplitude_h')['Q_mean_nearest_max_tau_0.5'].to_numpy()
        check(f'alternating_amplitude_score_monotone_scale{k:g}',np.all(np.diff(seq)<0))
    width=new[new.family.eq('local_signed_pulse_width')]
    for k,g in width.groupby('xz_scale'):
        seq=g.sort_values('local_pulse_halfwidth_before_scale_h')['Q_mean_nearest_max_tau_0.5'].to_numpy()
        check(f'local_signed_width_score_monotone_scale{k:g}',np.all(np.diff(seq)<0))
    pixel=frames[1]
    pixel=pixel[pixel.family.isin(['real_reference_horizon_pixel_shift','same_one_pixel_lower_error_vs_depth'])]
    extra=pixel['Q_v1_mean_tau_0.5']-pixel['Q_mean_nearest_max_tau_0.5']
    check('one_and_fractional_pixel_extra_deduction_under_point12',(extra<.12).all(),max_extra_points=float(extra.max()))

    # Old grades are read only here as optional descriptive outputs, after all
    # candidate controls and parameters are fixed; no human columns feed Q.
    # This script deliberately does not perform that optional read.
    pairs=[]
    for i,j in itertools.combinations(range(len(real)),2):
        da=float(real.iloc[i]['Q_v1_mean_tau_0.5']-real.iloc[j]['Q_v1_mean_tau_0.5'])
        db=float(real.iloc[i]['Q_mean_nearest_max_tau_0.5']-real.iloc[j]['Q_mean_nearest_max_tau_0.5'])
        if da*db<0:pairs.append(dict(a=real.iloc[i].case_id,b=real.iloc[j].case_id,v1_gap=da,new_gap=db))
    pd.DataFrame(pairs,columns=['a','b','v1_gap','new_gap']).to_csv(a.results/'old36_v1_vs_v11_order_changes.csv',index=False,encoding='utf-8-sig')

    summary=dict(all_checks_passed=all(c['passed'] for c in checks),checks=checks,
        tie_convention='maximum_squared_height_residual_among_geometrically_nearest_finite_floor_projections',
        total_geometries=len(geos),
        by_dataset_tie_summary=[dict(dataset=name,n=len(fr),
            any_distinct_tie_count=int(((fr.AG_distinct_height_tie_fraction>0)|(fr.GA_distinct_height_tie_fraction>0)).sum()),
            max_Hstar_min_vs_max=float(fr.absolute_Hstar_delta.max()),max_Q_min_vs_max=float(fr.absolute_Q_delta.max()))
            for name,fr in tieframe.groupby('dataset')],
        score_pair_reversals_vs_v1=pairs,
        height4096_median_seconds_per_geometry=float(np.median(times)),
        height4096_max_seconds_per_geometry=float(np.max(times)),
        note='Timing is descriptive for this machine and this development geometry panel, not an asymptotic claim.',
        expanded_holdout_results_read=False,human_labels_read=False,
        component_sha256=hashlib.sha256(Path(__file__).with_name('height_revision.py').read_bytes()).hexdigest())
    (a.results/'height_numerical_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if not summary['all_checks_passed']:raise SystemExit(1)

if __name__=='__main__':main()
