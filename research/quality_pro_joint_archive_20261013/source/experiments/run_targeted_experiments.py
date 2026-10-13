#!/usr/bin/env python3
"""Real-reference matched controls, projection coupling, and exact counterexamples.

No synthetic perturbation receives a human quality label.  Input-angle equality
is an explicit experimental budget, not an assertion of perceptual equivalence.
"""
from __future__ import annotations
import argparse, copy, csv, hashlib, json, math, sys, time
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
from structural_features import direction_descriptors
from export_real_descriptors import read, write, digest, sha

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def geometry(ring, height=2.6):
    return {'bottom3d': [[x, -1., z] for x, z in ring],
            'top3d': [[x, height-1., z] for x, z in ring]}


def ring(g):
    return np.asarray(g['bottom3d'], float)[:, [0, 2]]


def polygon_area(p):
    return abs(float(np.dot(p[:, 0], np.roll(p[:, 1], -1))-
                     np.dot(p[:, 1], np.roll(p[:, 0], -1))))/2.


def endpoint_budget_deg(a, g):
    aa = np.vstack([a['bottom3d'], a['top3d']]); gg = np.vstack([g['bottom3d'], g['top3d']])
    aa /= np.linalg.norm(aa, axis=1)[:, None]; gg /= np.linalg.norm(gg, axis=1)[:, None]
    angle = np.arctan2(np.linalg.norm(np.cross(aa, gg), axis=1), np.sum(aa*gg, axis=1))
    return float(np.degrees(np.sqrt(np.mean(angle**2))))


def control(g, family, amplitude):
    a=copy.deepcopy(g); points=ring(g)
    if family=='floor_shear':
        axis=math.radians(direction_descriptors(points)['axis_deg'])
        rot=np.array([[math.cos(axis),-math.sin(axis)],[math.sin(axis),math.cos(axis)]])
        q=points@rot; q[:,0] += amplitude*q[:,1]; q=q@rot.T
        for layer in ('bottom3d','top3d'):
            for j in range(len(q)):
                a[layer][j][0]=float(q[j,0]); a[layer][j][2]=float(q[j,1])
    else:
        edge=np.roll(points,-1,axis=0)-points; lengths=np.linalg.norm(edge,axis=1)
        vertex_weight=(lengths+np.roll(lengths,1))/(2*lengths.sum())
        heights=np.asarray(g['top3d'])[:,1]-np.asarray(g['bottom3d'])[:,1]
        mean=float(np.dot(vertex_weight,heights))
        profile=np.ones(len(points))
        if family=='local_height':
            # Angle-based profile is insensitive to ring starting index and
            # removes exactly the perimeter-weighted mean change.
            longitude=np.arctan2(points[:,1],points[:,0])
            profile=np.cos(2*longitude+.37)
            profile-=np.dot(vertex_weight,profile)
            profile/=max(abs(profile))
        for j in range(len(points)):
            a['top3d'][j][1]+=float(amplitude*mean*profile[j])
    return a


def match_angle(g, family, target):
    lo=0.; hi=.001
    for _ in range(24):
        a=control(g,family,hi)
        heights=np.asarray(a['top3d'])[:,1]-np.asarray(a['bottom3d'])[:,1]
        if np.any(heights<=.001):
            # The experiment cannot meet a larger target before its chosen
            # positive-wall-height domain ends; do not fabricate a control.
            upper=hi
            hi=brentq(lambda x:float((np.asarray(control(g,family,x)['top3d'])[:,1]-
                                     np.asarray(g['bottom3d'])[:,1]).min())-.001,lo,upper)
            if endpoint_budget_deg(control(g,family,hi),g)<target:
                return None, {'status':'budget_not_attainable_in_positive_height_domain',
                              'max_attainable_endpoint_rms_deg':endpoint_budget_deg(control(g,family,hi),g)}
            break
        if endpoint_budget_deg(a,g)>=target:
            break
        lo=hi;hi*=2
    else:
        return None, {'status':'budget_not_bracketed'}
    amplitude=brentq(lambda x:endpoint_budget_deg(control(g,family,x),g)-target,0.,hi,
                     xtol=1e-13,rtol=1e-13)
    a=control(g,family,amplitude)
    floor_delta=ring(a)-ring(g)
    top_delta=np.asarray(a['top3d'])-np.asarray(g['top3d'])
    lengths=np.linalg.norm(np.roll(ring(g),-1,axis=0)-ring(g),axis=1)
    vw=(lengths+np.roll(lengths,1))/(2*lengths.sum())
    support=float(vw[np.linalg.norm(floor_delta,axis=1)+np.linalg.norm(top_delta,axis=1)>1e-10].sum())
    return a, {'status':'constructed', 'matched_endpoint_rms_deg':endpoint_budget_deg(a,g),
        'amplitude':amplitude, 'vertex_floor_rms_over_sqrt_area':float(np.sqrt(np.mean(np.sum(floor_delta**2,axis=1)))/math.sqrt(polygon_area(ring(g)))),
        'vertex_top_displacement_rms_h':float(np.sqrt(np.mean(np.sum(top_delta**2,axis=1)))),
        'affected_vertex_perimeter_weight':support}


def selected_refs(data):
    allowed=set(data['development907_ids']); refs={}
    for r in sorted(data['rows'],key=lambda r:r['id']):
        if r['id'] in allowed and r['applicability_confirmed'] and r['gate']['new_descriptive_development_allowed']:
            refs.setdefault(r['reference_object_id'],r)
    ordered=sorted(refs.values(),key=lambda r:float(np.linalg.norm(ring(data['geometries'][r['reference_object_id']]),axis=1).max()))
    indices=sorted(set(np.linspace(0,len(ordered)-1,6).round().astype(int).tolist()))
    return [ordered[i] for i in indices], ordered


def create_cases(data):
    refs, all_refs=selected_refs(data); cases=[]
    def add(cid,family,a,g,meta):
        cases.append({'case_id':cid,'family':family,'annotation':a,'reference':g,
                      'annotation_geometry_sha256':digest(a),'reference_geometry_sha256':digest(g),
                      'metadata':meta,'human_quality_label':None,'is_actual_worker_answer':False})
    bindings=[]
    for r in refs:
        g=data['geometries'][r['reference_object_id']]; radii=np.linalg.norm(ring(g),axis=1)
        binding={k:r.get(k) for k in ('image_id','image_code','building_id','room_group','reference_object_id','reference_points_sha256')}
        binding.update(anchor_record_id=r['id'],reference_version=r['gate']['reference_version'],n_vertices=len(radii),
                       min_floor_elevation_deg=float(np.degrees(np.arctan2(1.,radii.max()))),
                       max_floor_radius_h=float(radii.max()))
        bindings.append(binding)
        add(r['id']+'__self','reference_self',g,g,binding)
        for budget in (.5,1.,2.,4.,8.):
            for family in ('floor_shear','local_height','global_height'):
                a,status=match_angle(g,family,budget)
                meta={**binding,**status,'target_endpoint_rms_deg':budget,
                      'comparison_budget':'unweighted RMS geodesic displacement over corresponding top and bottom vertices',
                      'not_a_psychophysical_equivalence':True}
                add(f'{r["id"]}__matched_{family}_{budget:g}deg','matched_'+family,a,g,meta)
        order=np.argsort(radii)[::-1]
        selections={'farthest_one':order[:1].tolist(),'farthest_two':order[:2].tolist(),'all':order.tolist()}
        for selection,indices in selections.items():
            for pixels in (-8.,-2.,-.5,.5,2.,8.):
                factors={}; reasons=[]
                for i in indices:
                    new_beta=math.atan2(1.,radii[i])+pixels*math.pi/512.
                    if not 0<new_beta<math.pi/2:
                        reasons.append(f'floor_ray_leaves_projection_domain_at_corner_{i}')
                    else:factors[i]=1./math.tan(new_beta)/radii[i]
                for policy in ('fixed_top_ray','fixed_world_top_height'):
                    a=copy.deepcopy(g)
                    if not reasons:
                        for i,factor in factors.items():
                            for layer in ('bottom3d','top3d'):
                                for k in (0,2):a[layer][i][k]*=factor
                            if policy=='fixed_top_ray':a['top3d'][i][1]*=factor
                    add(f'{r["id"]}__project_{selection}_{pixels:g}px_{policy}','projection_coupling',
                        None if reasons else a,g,{**binding,'corner_selection':selection,'indices':indices,
                            'bottom_vertical_displacement_px_ERP512':pixels,'direction':('toward_horizon' if pixels<0 else 'away_from_horizon'),
                            'top_policy':policy,'radial_factors':factors,'construction_reason_codes':reasons})
    rect=geometry([(-2,-1.5),(2,-1.5),(2,1.5),(-2,1.5)])
    for cut in (.5,.1,.01,.001,.0001,.000001):
        a=geometry([(-2,-1.5),(2,-1.5),(2,1.5-cut),(2-cut,1.5),(-2,1.5)])
        add(f'vanishing_chamfer_{cut:g}','vanishing_short_oblique_edge',a,rect,
            {'cut_h':cut,'diagonal_wall_fraction':math.sqrt(2)*cut/(14.-2*cut+math.sqrt(2)*cut)})
    for width in (.4,.1,.02,.005):
        for depth in (1.,4.):
            g=geometry([(-2,-1.5),(2,-1.5),(2,-width),(2+depth,-width),(2+depth,width),(2,width),(2,1.5),(-2,1.5)])
            add(f'orthogonal_omission_w{width:g}_d{depth:g}','orthogonal_missed_region',rect,g,
                {'width_h':2*width,'depth_h':depth,'known_missing_reflex_corners':2,
                 'reference_scope_fixed_for_this_control_not_human_approved':True})
    for width in (.2,.02,.002,.00002):
        a=geometry([(-2,-1.5),(2,-1.5),(2,-width),(3,0),(2,width),(2,1.5),(-2,1.5)])
        add(f'narrow_deep_spike_{width:g}','narrow_opening_nonvanishing_edge_length',a,rect,
            {'half_opening_width_h':width,'spike_depth_h':1.,'entrance_width_is_not_affected_wall_length':True})
    for displacement in (0.,1.,3.,5.):
        a=geometry([(x+displacement,z) for x,z in ring(rect)])
        add(f'equal_area_shift_{displacement:g}','equal_area_wrong_location',a,rect,
            {'translation_x_h':displacement,'area_difference_h2':0.})
    add('equal_area_stretch','equal_area_wrong_shape',geometry([(2*x,z/2) for x,z in ring(rect)]),rect,
        {'affine_scale_x':2.,'affine_scale_z':.5,'area_difference_h2':0.})
    return cases,bindings,all_refs


def csv_write(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,default=HERE/'results');args=p.parse_args()
    source=args.source.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    data=read(source/'inputs/calibration_records.json')
    sys.path.insert(0,str(source/'scripts'))
    from score_frozen_geometry import evaluate
    from strict_geometry import validate_record
    config=read(source/'config/frozen_selected_candidates.json')['candidates']['P_tied_quad08']['parameters']
    cases,bindings,all_refs=create_cases(data)
    write(out/'targeted_constructed_cases.json',{'design':{
        'matched_budget_deg':[.5,1,2,4,8],'budget_target_count':6*3*5,
        'selection':'six quantiles of maximum floor radius among the 16 frozen confirmed applicable reference images',
        'selection_uses_quality_score_or_response_label':False,'bounds_chosen_before_scores':True,
        'matched_error_budget_not_psychological_equivalence':True},'reference_bindings':bindings,'cases':cases})
    results=[];start=time.time()
    for i,c in enumerate(cases):
        rr={k:v for k,v in c.items() if k not in ('annotation','reference')}
        if c['annotation'] is None:
            rr.update(status='unavailable_construction_domain',metrics=None)
        else:
            a,g=c['annotation'],c['reference']
            try:
                va=validate_record(a);vg=validate_record(g)
                rr['annotation_validity']=va;rr['reference_validity']=vg
                rr['direction_descriptor']=direction_descriptors(a['bottom3d'])
                if va['valid_2d'] and vg['valid_2d']:
                    from shapely.geometry import Polygon
                    aa,gg=Polygon(ring(a)),Polygon(ring(g))
                    rr['floor_diagnostics']={'annotation_area_h2':aa.area,'reference_area_h2':gg.area,
                        'absolute_area_difference_h2':abs(aa.area-gg.area),
                        'floor_iou':aa.intersection(gg).area/aa.union(gg).area,
                        'hausdorff_over_sqrt_reference_area':aa.boundary.hausdorff_distance(gg.boundary)/math.sqrt(gg.area)}
                v=evaluate(a,g,config,samples=2048,height_samples=4096)
                rr.update(status=v['status'],metrics=v.get('metrics'),baseline_Q=v.get('quality_score'),
                    baseline_components=v.get('components'),official_corner_mean_iou3d=v.get('official_corner_mean_iou3d'),
                    numerical_settings={'spherical_samples':2048,'height_samples':4096})
                if v['status']!='available':rr['unavailable_result']=v
            except (ValueError,ArithmeticError,TypeError) as exc:
                rr.update(status='unavailable_experiment_evaluation',reason=str(exc),metrics=None)
        results.append(rr)
        if (i+1)%25==0 or i+1==len(cases):
            print(f'geometry controls {i+1}/{len(cases)} elapsed={time.time()-start:.1f}s',flush=True)
    write(out/'targeted_metrics.json',{'rows':results,'reference_bindings':bindings,
        'source_calibration_sha256':sha(source/'inputs/calibration_records.json'),
        'n_human_validation_labels':0,'script_sha256':sha(__file__)})
    flat=[]
    for r in results:
        row={'case_id':r['case_id'],'family':r['family'],'status':r['status'],'baseline_Q':r.get('baseline_Q')}
        row.update({k:r['metadata'].get(k) for k in ('image_code','anchor_record_id','target_endpoint_rms_deg','matched_endpoint_rms_deg','top_policy','corner_selection','bottom_vertical_displacement_px_ERP512')})
        if r.get('metrics'):row.update({k:r['metrics'][k] for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')})
        if 'direction_descriptor' in r:row.update(Dmax_deg=r['direction_descriptor']['Dmax_deg'],tail10_p2=r['direction_descriptor']['excess_by_threshold_deg']['10']['normalized_excess_p2'])
        flat.append(row)
    csv_write(out/'targeted_metrics.csv',flat)
    summary={'n_cases':len(cases),'n_complete':sum(r['status']=='available' for r in results),
        'n_by_family':{f:sum(r['family']==f for r in results) for f in sorted(set(r['family'] for r in results))},
        'n_available_by_family':{f:sum(r['family']==f and r['status']=='available' for r in results) for f in sorted(set(r['family'] for r in results))},
        'n_real_reference_anchors':len(bindings),'n_buildings':len(set(r['building_id'] for r in bindings)),
        'no_independent_human_labels_created':True,'elapsed_seconds':time.time()-start}
    write(out/'targeted_summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
