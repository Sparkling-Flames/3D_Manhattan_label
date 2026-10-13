#!/usr/bin/env python3
"""Independent scalar replay and adversarial/precision checks for chosen candidates."""
from __future__ import annotations
import argparse,csv,json,math,sys
from pathlib import Path
import numpy as np
from structural_features import jointly_optimized_hinge,direction_descriptors
from export_real_descriptors import read,write,sha

sys.dont_write_bytecode = True


def descriptor_for_score(d):
    return {'moment4':d['weighted_abs_moments_deg_power']['p4'],
            'excess2':{k:v['positive_part_m2_deg2'] for k,v in d['excess_by_threshold_deg'].items()},
            'joint_hinge':{'t10_g2':jointly_optimized_hinge(d,10.,2.)['value_deg2']}}


def independent_score(m,c,d):
    I=m['iou_2d'];S=m['S_bottom_deg'];D=m['dir'];H=m['Hmean'];C=m['Hcenter']
    if c['combine']!='additive':raise ValueError('independent verification covers selected additive candidates only')
    B=(S/c['boundary_scale'])**c['boundary_power']
    if c['family']=='hill':
        x=(D/c['direction_scale'])**c['direction_power'];Dr=c['direction_cap']*x/(1+x)
    elif c['family']=='hill_tail':
        x=(D/c['direction_scale'])**c['direction_power'];Dr=c['direction_cap']*x/(1+x)+(D/c['tail_scale'])**4
    elif c['family']=='power':Dr=(D/c['direction_scale'])**c['direction_power']
    elif c['family']=='joint_hinge':
        Dr=jointly_optimized_hinge(d,c['tail_threshold'],c['hinge_weight'])['value_deg2']/c['direction_scale']**2
    else:raise ValueError('unrecognized independently verified family')
    Hg=(H/c['global_scale'])**c['global_power'];Hl=(C/c['local_scale'])**c['local_power']
    return {'score':100*I**c['iou_power']/(1+B+Dr+Hg+Hl),
        'floor_score':100*I**c['iou_power']/(1+B+Dr),
        'boundary_loss':B,'direction_loss':Dr,'global_height_loss':Hg,'local_height_loss':Hl,
        'height_score_drop':100*I**c['iou_power']*(1/(1+B+Dr)-1/(1+B+Dr+Hg+Hl))}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--config',required=True,type=Path)
    ap.add_argument('--out',type=Path,default=Path(__file__).parent/'results');args=ap.parse_args()
    out=args.out.resolve();data=read(args.source/'inputs/calibration_records.json');draft=read(args.config)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'calibration'))
    from score import score_metrics,BASELINE
    configs={'baseline_quad08':BASELINE,**draft['candidates']};descriptors=read(out/'real_direction_descriptors.json')
    bydesc={r['record_id']:r for r in descriptors['rows']}
    realrows=[];errors=[]
    for r in data['rows']:
        d=bydesc[r['id']];sd=descriptor_for_score(d);scores={}
        for name,c in configs.items():
            independent=independent_score(r['metrics'],c,d);actual=score_metrics(r['metrics'],c,sd)
            if actual['status']!='complete':raise AssertionError((r['id'],name,actual))
            err=max(abs(independent[k]-actual[k]) for k in independent);errors.append(err)
            scores[name]=independent
        realrows.append({'record_id':r['id'],'image_code':r['image_code'],'scores':scores,
                        'same_reference_and_metrics_for_all_candidates':True,
                        'applicability_confirmed':r['applicability_confirmed'],'gate':r['gate']})
    controls=read(out/'targeted_metrics.json')['rows'];extra=read(out/'extreme_projection_results.json')['rows']
    controlrows=[];desc_by_case={}
    for r in controls+extra:
        row={'case_id':r['case_id'],'family':r['family'],'metadata':r['metadata'],'status':r['status'],'scores':{},
             'official_corner_mean_iou3d_x100':100*r['official_corner_mean_iou3d'] if r.get('official_corner_mean_iou3d') is not None else None}
        if r['status']=='available':
            d=r['direction_descriptor'];desc_by_case[r['case_id']]=d
            m=r['metrics'] if 'metrics' in r else r['computations'][1]['metrics'];sd=descriptor_for_score(d)
            for name,c in configs.items():
                ind=independent_score(m,c,d);actual=score_metrics(m,c,sd)
                if actual['status']!='complete':raise AssertionError((r['case_id'],name,actual))
                errors.append(max(abs(ind[k]-actual[k]) for k in ind));row['scores'][name]=ind
        controlrows.append(row)
    priority=[];group={}
    for r in controlrows:
        if r['family'].startswith('matched_') and r['status']=='available':
            k=(r['metadata']['anchor_record_id'],r['metadata']['target_endpoint_rms_deg'])
            group.setdefault(k,{})[r['family']]=r
    for k,rr in group.items():
        if len(rr)!=3:continue
        row={'anchor_record_id':k[0],'endpoint_rms_budget_deg':k[1],'scores':{}}
        for name in configs:
            s,l,g=[rr['matched_'+f]['scores'][name]['score'] for f in ('floor_shear','local_height','global_height')]
            row['scores'][name]={'floor_shear':s,'local_height':l,'global_height':g,
                                'priority_structure_then_local_then_global':s<l<g,
                                'structure_minus_local':s-l,'local_minus_global':l-g}
        io=[rr['matched_'+f]['official_corner_mean_iou3d_x100'] for f in ('floor_shear','local_height','global_height')]
        row['scores']['official_corner_mean_iou3d']={'floor_shear':io[0],'local_height':io[1],'global_height':io[2],
            'priority_structure_then_local_then_global':io[0]<io[1]<io[2]}
        priority.append(row)
    sampling=read(out/'sampling_verification.json')['rows'];sampleout=[]
    for r in sampling+extra:
        d=bydesc[r['case_id']] if r['case_id'] in bydesc else desc_by_case.get(r['case_id'])
        if d is None:continue
        scores={}
        for c in r['computations']:
            if c['status']!='available':continue
            key=f's{c["spherical_samples"]}_h{c["height_samples"]}'
            scores[key]={name:independent_score(c['metrics'],cfg,d)['score'] for name,cfg in configs.items()}
        sampleout.append({'case_id':r['case_id'],'family':r['family'],'scores':scores})
    precision={}
    for name in configs:
        precision[name]={}
        for family in ('actual_response','constructed'):
            selected=[r for r in sampleout if (r['family']=='actual_response')==(family=='actual_response')]
            for source,target,label in [('s1024_h4096','s2048_h4096','sphere1024_to_2048'),
                                       ('s2048_h4096','s4096_h4096','sphere2048_to_4096'),
                                       ('s4096_h4096','s4096_h16384','height4096_to_16384')]:
                differences=[(abs(r['scores'][source][name]-r['scores'][target][name]),r['case_id']) for r in selected if source in r['scores'] and target in r['scores']]
                if differences:
                    v,cid=max(differences);precision[name][family+'_'+label]={'max_absolute_score_difference':v,'case_id':cid,'n_pairs':len(differences)}
    switches=read(out/'axis_switch_counterexample.json')['cases'];switchscores=[]
    for c in switches:
        d=c['descriptor'];m={'iou_2d':1.,'S_bottom_deg':0.,'dir':d['D_rms_deg'],'Hmean':0.,'Hcenter':0.}
        switchscores.append({'epsilon':c['epsilon'],'axis_deg':d['axis_deg'],
            'scores':{name:independent_score(m,cfg,d)['score'] for name,cfg in configs.items()},
            'purpose':'isolated direction response; I=1 and other losses zero, not a measured annotation-reference IoU'})
    pairs=[];proj={}
    for r in controlrows:
        if r['family'] in ('projection_coupling','extreme_projection_coupling') and r['status']=='available':
            m=r['metadata'];k=(m['anchor_record_id'],m['corner_selection'],m['bottom_vertical_displacement_px_ERP512'])
            proj.setdefault(k,{})[m['top_policy']]=r
    for k,rr in proj.items():
        if len(rr)!=2:continue
        pairs.append({'anchor_record_id':k[0],'corner_selection':k[1],'bottom_px':k[2],
            'extra_height_score_drop':{name:rr['fixed_world_top_height']['scores'][name]['score']-
                                           rr['fixed_top_ray']['scores'][name]['score'] for name in configs}})
    priority_counts={name:sum(r['scores'][name]['priority_structure_then_local_then_global'] for r in priority)
                     for name in [*configs,'official_corner_mean_iou3d']}
    summary={'config_path_relative':str(args.config.name),'config_sha256':sha(args.config),
        'n_real_scalar_replays':len(realrows),'n_control_attempts':len(controlrows),
        'n_complete_controls':sum(r['status']=='available' for r in controlrows),
        'maximum_independent_vs_public_evaluator_difference':max(errors),
        'n_matched_priority_triples':len(priority),'priority_count_by_candidate':priority_counts,
        'matched_priority_is_design_sensitivity_not_human_validation':True,
        'sampling_precision_by_candidate':precision,
        'max_extra_height_coupling_by_candidate':{name:max(pairs,key=lambda r:r['extra_height_score_drop'][name]) for name in configs}}
    assert max(errors)<1e-9
    write(out/'candidate_validation_real.json',{'summary':summary,'rows':realrows})
    write(out/'candidate_validation_controls.json',{'summary':summary,'rows':controlrows,'matched_priority':priority,
         'axis_switch_response':switchscores,'projection_height_attribution':pairs})
    write(out/'candidate_precision.json',{'summary':precision,'rows':sampleout})
    write(out/'candidate_validation_summary.json',summary)
    flat=[]
    for r in controlrows:
        for name,s in r['scores'].items():flat.append({'case_id':r['case_id'],'family':r['family'],'candidate':name,**s})
    with (out/'candidate_control_scores.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
