#!/usr/bin/env python3
"""Predeclared ±16/±32 pixel extension; retain horizon-crossing failures."""
from __future__ import annotations
import argparse,copy,json,math,sys
from pathlib import Path
import numpy as np
from export_real_descriptors import read,write,digest,sha
from run_targeted_experiments import selected_refs,ring
from structural_features import direction_descriptors

sys.dont_write_bytecode = True


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--out',type=Path,default=Path(__file__).parent/'results');args=ap.parse_args()
    source=args.source.resolve();out=args.out.resolve();data=read(source/'inputs/calibration_records.json')
    refs,_=selected_refs(data);cases=[]
    for r in refs:
        g=data['geometries'][r['reference_object_id']];radii=np.linalg.norm(ring(g),axis=1);order=np.argsort(radii)[::-1]
        for selection,indices in {'farthest_one':order[:1].tolist(),'farthest_two':order[:2].tolist(),'all':order.tolist()}.items():
            for pixels in (-32.,-16.,16.,32.):
                factors={};reasons=[]
                for j in indices:
                    beta=math.atan2(1.,radii[j])+pixels*math.pi/512.
                    if not 0<beta<math.pi/2:reasons.append(f'floor_ray_leaves_domain_corner_{j}')
                    else:factors[j]=1/math.tan(beta)/radii[j]
                for policy in ('fixed_top_ray','fixed_world_top_height'):
                    a=copy.deepcopy(g)
                    if not reasons:
                        for j,f in factors.items():
                            for layer in ('bottom3d','top3d'):
                                for k in (0,2):a[layer][j][k]*=f
                            if policy=='fixed_top_ray':a['top3d'][j][1]*=f
                    else:a=None
                    cases.append({'case_id':f'{r["id"]}__extreme_{selection}_{pixels:g}px_{policy}',
                        'family':'extreme_projection_coupling','annotation':a,'reference':g,
                        'metadata':{'image_code':r['image_code'],'image_id':r['image_id'],'building_id':r['building_id'],
                            'anchor_record_id':r['id'],'reference_object_id':r['reference_object_id'],
                            'reference_points_sha256':r['reference_points_sha256'],'reference_geometry_sha256':digest(g),
                            'reference_version':r['gate']['reference_version'],'corner_selection':selection,
                            'indices':indices,'radial_factors':factors,'bottom_vertical_displacement_px_ERP512':pixels,
                            'top_policy':policy,'construction_reason_codes':reasons,
                            'min_reference_floor_elevation_deg':float(np.degrees(np.arctan2(1.,radii.max()))),
                            'not_a_human_label':True}})
    write(out/'extreme_projection_cases.json',{'cases':cases,'source_calibration_sha256':sha(source/'inputs/calibration_records.json')})
    sys.path.insert(0,str(source/'scripts'));from score_frozen_geometry import evaluate
    config=read(source/'config/frozen_selected_candidates.json')['candidates']['P_tied_quad08']['parameters']
    rows=[]
    for i,c in enumerate(cases):
        rr={k:v for k,v in c.items() if k not in ('annotation','reference')}
        rr['computations']=[]
        if c['annotation'] is None:rr['status']='unavailable_construction_floor_ray_domain'
        else:
            rr['direction_descriptor']=direction_descriptors(c['annotation']['bottom3d'])
            for sphere in (1024,2048,4096):
                v=evaluate(c['annotation'],c['reference'],config,samples=sphere,height_samples=4096)
                rr['computations'].append({'spherical_samples':sphere,'height_samples':4096,'status':v['status'],
                                          'baseline_Q':v.get('quality_score'),'metrics':v.get('metrics'),
                                          'unavailable_result':v if v['status']!='available' else None})
            rr['status']='available' if all(x['status']=='available' for x in rr['computations']) else 'unavailable_evaluation'
        rows.append(rr)
        if (i+1)%24==0:print(f'extreme projection {i+1}/{len(cases)}',flush=True)
    summary={'n_constructed_attempts':len(cases),'n_complete':sum(x['status']=='available' for x in rows),
        'n_unavailable_construction_domain':sum(x['status']=='unavailable_construction_floor_ray_domain' for x in rows),
        'n_unavailable_evaluation':sum(x['status']=='unavailable_evaluation' for x in rows),
        'n_evaluations':sum(len(x['computations']) for x in rows),'zero_scores_not_used_for_unavailable':True}
    available=[x for x in rows if x['status']=='available']
    summary['max_baseline_Q_difference_2048_to_4096']=max(abs(x['computations'][1]['baseline_Q']-x['computations'][2]['baseline_Q']) for x in available)
    by={}
    for r in available:
        m=r['metadata'];key=(m['anchor_record_id'],m['corner_selection'],m['bottom_vertical_displacement_px_ERP512'])
        by.setdefault(key,{})[m['top_policy']]=r
    pairs=[]
    for key,items in by.items():
        if len(items)==2:
            ray=items['fixed_top_ray']['computations'][1];world=items['fixed_world_top_height']['computations'][1]
            pairs.append({'anchor_record_id':key[0],'corner_selection':key[1],'bottom_px':key[2],
                          'extra_height_score_drop':world['baseline_Q']-ray['baseline_Q'],
                          'fixed_ray_Q':ray['baseline_Q'],'fixed_world_Q':world['baseline_Q'],
                          'Hm_fixed_ray':ray['metrics']['Hmean'],'Hc_fixed_ray':ray['metrics']['Hcenter']})
    summary['maximum_extra_height_score_drop']=max(pairs,key=lambda r:r['extra_height_score_drop'])
    write(out/'extreme_projection_results.json',{'summary':summary,'rows':rows,'paired_policy_comparisons':pairs})
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
