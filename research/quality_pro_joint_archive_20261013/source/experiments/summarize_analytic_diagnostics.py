#!/usr/bin/env python3
"""Reproducible local-support shortlists, topology diagnostics, and response scales."""
import argparse,collections,json,math
from pathlib import Path
import numpy as np
from export_real_descriptors import read,write
from structural_features import jointly_optimized_hinge


def profile(g):
    p=np.asarray(g['bottom3d'],float)[:,[0,2]];edge=np.roll(p,-1,axis=0)-p
    theta=np.degrees(np.arctan2(edge[:,1],edge[:,0]));turn=(theta-np.roll(theta,1)+180)%360-180
    area=(p[:,0]@np.roll(p[:,1],-1)-p[:,1]@np.roll(p[:,0],-1))/2
    return {'point_count':len(p),'reflex_corners_over_15deg':int((turn*np.sign(area)<-15).sum()),
        'signed_turns_deg':turn.tolist(),'turn_threshold_is_descriptive_not_quality_cutoff':True}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--out',type=Path,default=Path(__file__).parent/'results');args=ap.parse_args()
    out=args.out;data=read(args.source/'inputs/calibration_records.json');desc=read(out/'real_direction_descriptors.json');rr=desc['rows']
    by=collections.defaultdict(list)
    for r in rr:by[r['image_code']].append(r)
    pairs=[]
    for image,rs in by.items():
        for i,a in enumerate(rs):
            for b in rs[i+1:]:
                delta=abs(a['D_rms_deg']-b['D_rms_deg']);ta=a['weighted_abs_moments_deg_power']['p4'];tb=b['weighted_abs_moments_deg_power']['p4']
                ratio=max(ta,tb)/max(1e-8,min(ta,tb))
                if delta<.5 and min(a['D_rms_deg'],b['D_rms_deg'])>2 and ratio>1.5:
                    pairs.append({'ratio':ratio,'image_code':image,'A':a['record_id'],'B':b['record_id'],
                        'D_A':a['D_rms_deg'],'D_B':b['D_rms_deg'],'Dmax_A':a['Dmax_deg'],'Dmax_B':b['Dmax_deg'],
                        'applicable_A':a['applicability_confirmed'],'applicable_B':b['applicability_confirmed']})
    pairs.sort(key=lambda r:tuple(r[k] for k in ('ratio','image_code','A','B')),reverse=True)
    write(out/'real_tail_pair_candidates.json',{'criterion':'same image, D difference<0.5 degrees, min D>2, ratio of weighted fourth moment>1.5; descriptive selection only','pairs':pairs})
    selfrows=[]
    for r in desc['references']:
        if r['status']=='available':
            D=r['D_rms_deg'];b=1.5*D*D/(D*D+37.5)
            selfrows.append({'reference_id':r['reference_object_id'],'D':D,'baseline_self_score':100/(1+b),
                            'main_self_score':100/(1+b+(D/12)**4)})
    write(out/'reference_intrinsic_self_response.json',{'note':'I=1,Sb=0,Hm=0,Hc=0 self-reference response; intrinsic direction still penalized; not an approval/exclusion decision','rows':selfrows})
    top=[]
    for r in data['rows']:
        a=profile(data['geometries'][r['object_id']]);g=profile(data['geometries'][r['reference_object_id']])
        if g['reflex_corners_over_15deg']>a['reflex_corners_over_15deg'] and r['metrics']['dir']<2:
            top.append({'record_id':r['id'],'image_code':r['image_code'],'annotation':a,'reference':g,
                'D_rms_deg':r['metrics']['dir'],'floor_iou':r['metrics']['iou_2d'],
                'reference_object_id':r['reference_object_id'],'gate':r['gate'],
                'scope_error_not_inferred_from_point_count_or_turn_count':True,
                'must_reinterpret_against_final_route_before_quality_conclusion':True})
    top.sort(key=lambda r:r['D_rms_deg'])
    write(out/'real_topology_diagnostics.json',{'n_descriptive_cases':len(top),'rows':top})
    direction=[]
    for D in (0.,1.,2.,3.,5.,8.,10.,12.,16.,20.,90/math.sqrt(12)):
        h=1.5*D*D/(D*D+37.5);tail=(D/12)**4
        direction.append({'D_deg':D,'baseline_direction_loss':h,'main_extra_tail_loss':tail,
                          'baseline_direction_only_Q':100/(1+h),'main_direction_only_Q':100/(1+h+tail),
                          'simple_direction_only_Q':100/(1+(D/8)**2)})
    crossing=math.sqrt((-37.5+math.sqrt(37.5**2+4*1.5*12**4))/2)
    heights=[]
    for e in (.05,.1,.2,.2335962485,.25,.5,.75,1.,1.5,2.):
        heights.append({'relative_error':e,'global_only_Q_g1':100/(1+e*e),
                        'local_only_Q_l025':100/(1+(e/.25)**2),
                        'units_not_psychophysical_equivalence':True})
    write(out/'response_transition_ranges.json',{
        'D_mathematical_upper_bound_deg':90/math.sqrt(12),
        'main_tail_loss_equals_one_at_D_deg':12.,'main_tail_loss_equals_hill_loss_at_D_deg':crossing,
        'global_loss_one_at_relative_Hm':1.,'local_loss_one_at_relative_Hc':.25,
        'these_are_model_response_scales_not_human_grade_cutoffs':True,
        'direction':direction,'heights':heights})
    print(json.dumps({'real_tail_candidate_pairs':len(pairs),'real_low_D_topology_diagnostics':len(top),
                      'reference_self_cases':len(selfrows),'main_tail_hill_crossing_deg':crossing},indent=2))


if __name__=='__main__':main()
