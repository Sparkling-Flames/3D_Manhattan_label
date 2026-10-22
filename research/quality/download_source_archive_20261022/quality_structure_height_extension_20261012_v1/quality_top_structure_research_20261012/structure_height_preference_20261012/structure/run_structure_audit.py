#!/usr/bin/env python3
"""Exact own-structure audit of frozen rings; no geometry repair or label fitting.

Run from the delivered workspace using --root PATH. The default output is the
sibling results directory. A latest exposure registry is required for real data.
Only outputs under --out are created or replaced.
"""
from __future__ import annotations
import argparse, copy, csv, hashlib, json, math, platform, sys
from pathlib import Path
import numpy as np

PERIOD = 90.0
COLLINEAR_TOL_DEG = 1e-8  # numerical representation tolerance, not quality cutoff

def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k,v in x.items()}
    if isinstance(x, (tuple,list)): return [clean(v) for v in x]
    if isinstance(x, np.ndarray): return clean(x.tolist())
    if isinstance(x, np.generic): return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x): return None
    return x

def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def csvwrite(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(clean(rows))

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def wrap90(x): return (np.asarray(x)+45.0)%90.0-45.0
def wrap180(x): return (np.asarray(x)+180.0)%360.0-180.0

def weighted_quantile(x,w,p):
    ids=np.argsort(x,kind='stable');cum=np.cumsum(w[ids])/sum(w)
    return float(x[ids[min(int(np.searchsorted(cum,p,side='left')),len(x)-1)]])

def direction_minima(theta,w):
    """Independent degree-valued implementation; all tied global axes retained."""
    breaks=np.unique(np.r_[0.0,(theta+45)%90,90.0]);candidates=list(breaks)
    for lo,hi in zip(breaks[:-1],breaks[1:]):
        mid=(lo+hi)/2;opt=mid+np.dot(w,wrap90(theta-mid))/w.sum()
        if lo-1e-12<=opt<=hi+1e-12: candidates.append(float(np.clip(opt,lo,hi)))
    scores=np.array([np.dot(w,wrap90(theta-a)**2)/w.sum() for a in candidates])
    best=float(min(scores)); axes=[]
    for ax,z in zip(candidates,scores):
        if z<=best+1e-9:
            a=ax%90
            if all(abs(float(wrap90(a-b)))>1e-8 for b in axes):axes.append(float(a))
    return best,sorted(axes)

def remove_forward_collinear(p):
    """Diagnostic-only view; original ring remains untouched and must be valid."""
    p=np.asarray(p,float);ids=list(range(len(p)))
    changed=True
    while changed and len(ids)>3:
        changed=False
        for k,i in enumerate(ids):
            a=p[i]-p[ids[k-1]];b=p[ids[(k+1)%len(ids)]]-p[i]
            turn=math.degrees(math.atan2(float(a[0]*b[1]-a[1]*b[0]),float(np.dot(a,b))))
            if abs(turn)<=COLLINEAR_TOL_DEG and float(np.dot(a,b))>0:
                ids.pop(k);changed=True;break
    return p[ids],ids

def structural_diagnostics(g):
    p=np.asarray(g['bottom3d'],float)[:,[0,2]]
    e=np.roll(p,-1,axis=0)-p;w=np.linalg.norm(e,axis=1)
    if np.any(w<=1e-12): raise ValueError('zero edge; no repair')
    theta=np.rad2deg(np.arctan2(e[:,1],e[:,0]));best,axes=direction_minima(theta,w)
    turns=wrap180(np.roll(theta,-1)-theta);raw=np.abs(wrap90(turns))
    pc,retained=remove_forward_collinear(p);ec=np.roll(pc,-1,axis=0)-pc
    tc=np.rad2deg(np.arctan2(ec[:,1],ec[:,0]));turnc=wrap180(np.roll(tc,-1)-tc)
    orientation=float(np.sign(np.sum(pc[:,0]*np.roll(pc[:,1],-1)-pc[:,1]*np.roll(pc[:,0],-1))))
    if orientation==0:raise ValueError('zero-area ring; no repair')
    corner=np.abs(wrap90(turnc))
    interior=180-orientation*turnc
    admissible=np.min(abs(interior[:,None]-np.array([90.,180.,270.])[None,:]),axis=1)
    rows=[]
    for ax in axes:
        r=np.abs(wrap90(theta-ax))
        rows.append({'axis_deg':ax,'max_deg':float(r.max()),
                     'p95_deg':weighted_quantile(r,w,.95),
                     **{f'support_gt{q}_fraction':float(w[r>q+1e-10].sum()/w.sum()) for q in [5,10,20]}})
    d=math.sqrt(max(best,0.0))
    out={'D_independent_deg':d,'D_minima_count':len(axes),'D_axis_first_deg':axes[0],
         'D_theoretical_upper_bound_deg':90/math.sqrt(12),
         'own_D_old_relative_discount':.075*d*d/(d*d+25),
         'edge_count':len(p),'noncollinear_node_count':len(pc),
         'exact_forward_collinear_removed':len(p)-len(pc),
         'adjacent_turn_rms_raw_deg':float(np.sqrt(np.mean(raw**2))),
         'adjacent_turn_rms_after_collinear_deg':float(np.sqrt(np.mean(corner**2))),
         'adjacent_turn_max_deg':float(corner.max()),
         'corner_admissible_rms_deg':float(np.sqrt(np.mean(admissible**2))),
         'corner_admissible_max_deg':float(admissible.max()),
         'minimum_interior_angle_deg':float(interior.min()),
         'maximum_interior_angle_deg':float(interior.max()),
         'convex_turns_count':int((orientation*turnc>COLLINEAR_TOL_DEG).sum()),
         'concave_turns_count':int((orientation*turnc<-COLLINEAR_TOL_DEG).sum()),
         'floor_perimeter_h':float(w.sum()),'shortest_edge_perimeter_fraction':float(w.min()/w.sum())}
    for name in ['max_deg','p95_deg']+[f'support_gt{q}_fraction' for q in [5,10,20]]:
        out['direction_'+name+'_min_over_ties']=min(x[name] for x in rows)
        out['direction_'+name+'_max_over_ties']=max(x[name] for x in rows)
    detail={'edge_heading_deg':theta.tolist(),'edge_length_h':w.tolist(),
            'optimal_axes':rows,'corner_turn_deg':turnc.tolist(),
            'corner_error_mod90_deg':corner.tolist(),'corner_admissible_error_deg':admissible.tolist(),
            'corner_interior_angle_deg':interior.tolist(),
            'corner_turn_at_source_indices':np.roll(retained,-1).tolist(),
            'corner_view_retained_source_indices':retained}
    return out,detail

def geom(xz,height=2.4):
    p=np.asarray(xz,float);h=np.broadcast_to(height,(len(p),))
    return {'bottom3d':np.c_[p[:,0],-np.ones(len(p)),p[:,1]].tolist(),
            'top3d':np.c_[p[:,0],h-1,p[:,1]].tolist()}

def subdivide(g,edge,n):
    result={}
    for key in ['bottom3d','top3d']:
        p=np.asarray(g[key]);out=[]
        for j,x in enumerate(p):
            out.append(x)
            if j==edge:out.extend((1-t)*x+t*p[(j+1)%len(p)] for t in np.arange(1,n+1)/(n+1))
        result[key]=np.asarray(out).tolist()
    return result

def reorder(g,mode):
    return {k:(np.asarray(g[k])[::-1] if mode=='reverse' else np.roll(np.asarray(g[k]),-1,axis=0)).tolist() for k in ['bottom3d','top3d']}

RECT=np.array([[-2.,-1.],[2.,-1.],[2.,1.],[-2.,1.]])

def design(helper):
    cases=[]
    def add(cid,family,a,g,**meta):
        cases.append({'case_id':cid,'family':family,'annotation':a,'reference':g,
                      'synthetic_human_label':None,**meta})
    base=geom(RECT)
    add('rectangle_correct','valid_structure',base,copy.deepcopy(base))
    L=np.array([[-3.,-2.],[3.,-2.],[3.,0.],[1.,0.],[1.,2.],[-3.,2.]])
    add('concave_correct','valid_structure',geom(L),geom(L))
    for deg in [2,10,30]:
        q=math.radians(deg);R=np.array([[math.cos(q),-math.sin(q)],[math.sin(q),math.cos(q)]])
        add(f'rigid_rotation_{deg}','reference_orientation_error',geom(RECT@R.T),base,rotation_deg=deg)
    for deg in [2,5,10,20]:
        for scale in [.5,2.,10.]:
            p=RECT.copy();p[:,0]+=p[:,1]*math.tan(math.radians(deg))
            add(f'shear_{deg}_scale{scale:g}','common_corner_deviation',geom(p*scale),geom(RECT*scale),corner_departure_deg=deg,horizontal_scale=scale)
    for eps in [.005,.02,.1,.5,1.]:
        p=[[-2,-1],[2,-1],[2,1-eps],[2-eps,1],[-2,1]]
        add(f'chamfer_{eps:g}','short_structural_edge',geom(p),base,chamfer_leg_h=eps)
    for cid,p in [('omitted_notch_bounding_rectangle',[[-3,-2],[3,-2],[3,2],[-3,2]]),
                  ('omitted_branch_inner_rectangle',[[-3,-2],[1,-2],[1,2],[-3,2]])]:
        add(cid,'regular_structure_omission',geom(p),geom(L))
    add('triangle','three_pairs_not_universal_label',geom([[-2,-1],[2,-1],[0,2]]),base)
    q=np.arange(8)*math.pi/4
    add('regular_octagon','tied_global_axes',geom(np.c_[2*np.cos(q),2*np.sin(q)]),base)
    q=np.arange(36)*2*math.pi/36
    add('regular_36gon_slow_turn','small_local_turn_accumulation',geom(np.c_[2*np.cos(q),2*np.sin(q)]),base,
        protocol_addendum='protocol_addendum_after_initial40.json')
    for eps in [.001,.1]:
        p=[[-2,-1],[-eps,-1],[0,-2],[eps,-1],[2,-1],[2,1],[-2,1]]
        add(f'needle_halfwidth{eps:g}','sharp_legal_interior_angle',geom(p),base,
            needle_depth_h=1,needle_halfwidth_h=eps,protocol_addendum='protocol_addendum_sharp_angles.json')
    parent=next(x for x in cases if x['case_id']=='chamfer_0.1')
    for edge in [0,2]:
        for n in [1,40]:
            add(f'chamfer_same_curve_edge{edge}_plus{n}','same_curve_redundant_nodes',subdivide(parent['annotation'],edge,n),base,parent='chamfer_0.1')
    for mode in ['reverse','rotate']:
        add(f'chamfer_same_curve_{mode}','same_curve_order',reorder(parent['annotation'],mode),base,parent='chamfer_0.1')
    for scale in [.5,2.,10.,50.]:
        g=geom(RECT*scale);p=helper.erp_points(g);p[1,1]-=1
        a,reason=helper.from_erp(p)
        add(f'bottom_minus1_scale{scale:g}','near_horizon_fixed_input_error',a,g,
            horizontal_scale=scale,bottom_pixel_change=-1,top_ray_unchanged=True,
            reference_bottom_horizon_margin_px=float(helper.erp_points(g)[1,1]-256),projection_failure=reason)
        ac=geom(np.asarray(a['bottom3d'])[:,[0,2]]) if a else None
        add(f'bottom_minus1_preserved_height_scale{scale:g}','near_horizon_height_control',ac,g,
            horizontal_scale=scale,bottom_pixel_change=-1,top_ray_unchanged=False,
            controlled_height_preservation_not_real_annotation=True)
    return cases

def controls(root,out,quality_v11,audit_geometry,helper,centered_height):
    cases=design(helper);dump(out/'synthetic_design.json',cases);rows=[];details=[]
    for j,c in enumerate(cases):
        row={k:v for k,v in c.items() if k not in ['annotation','reference']}
        if c['annotation'] is None:
            row['status']='unavailable';rows.append(row);continue
        sc=quality_v11.score_geometry(c['annotation'],c['reference'])
        row['status']=sc['status']
        d,detail=structural_diagnostics(c['annotation']);row.update(d)
        details.append({'case_id':c['case_id'],'directions':detail,'engine':sc})
        if sc['status']=='available':
            m=sc['metrics'];row.update({k:m[k] for k in ['iou_2d','iou_3d_corner_mean','Hmean','Hlocal','Hstar','S_top_deg','S_bottom_deg','dir','flat']})
            row.update(centered_height.centered_height_components(c['annotation'],c['reference']))
            row.update(helper.scores_from_metrics(m))
            row['D_frozen_parity_error']=abs(d['D_independent_deg']-m['dir'])
        else:row['unavailable_reasons']='|'.join(sc['reason_codes'])
        rows.append(row)
        if (j+1)%10==0:print(f'structure controls {j+1}/{len(cases)}',flush=True)
    csvwrite(out/'synthetic_metrics.csv',rows);dump(out/'synthetic_details.json',details)
    return rows

def audit_eligibility(root,registry_path,selected39,selected907):
    b=root/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    holdpath=b/'results/room_holdout_manifest.csv';reg=json.loads(registry_path.read_text())
    manifest=list(csv.DictReader(holdpath.open(encoding='utf-8-sig')))
    # Resolve explicit recorded flag; no inferred fresh split.
    held=[r for r in manifest if str(r.get('held_out_of_sample_and_future_calibration','')).lower()=='true']
    if len(held)!=reg['original_heldout_records']:
        raise ValueError(f'holdout field/count mismatch: {len(held)}; observed columns {list(manifest[0])}')
    heldids={r['record_id'] for r in held}; exposedids={r['record_id'] for r in reg['screen_records_in_original_holdout']}
    groups=set(reg['groups_touched_by_this_screen'])
    for name,rows in [('aligned39',selected39),('descriptive907',selected907)]:
        ids={r['record_id'] for r in rows}
        assert not ids&heldids,(name,'original holdout overlap')
        assert not ids&exposedids,(name,'screen exposure overlap')
        if name=='descriptive907':assert not {r['room_group'] for r in rows}&groups
    return {'registry_sha256':sha(registry_path),'holdout_manifest_sha256':sha(holdpath),
            'original_holdout_count':len(held),'exposed_record_count':len(exposedids),
            'exposed_group_count':len(groups),'all_original_holdout_records_used':0,
            'exposed_records_used':0,'remaining_103_certified_clean':False,
            'explicit_registry_applied':True}

def real(root,out,registry_path,audit_geometry):
    b=root/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    gs=json.loads((b/'inputs/current_geometry_compact.json').read_text())['geometries']
    cs={r['record_id']:r for r in json.loads((b/'results/current_components.json').read_text())}
    old=json.loads((root/'study_quality/results/candidate_scores.json').read_text())
    filters=json.loads((root/'top_structure_20261012/evidence/results/development_907_filter.json').read_text())
    pool=[r for r in filters if r['descriptive_development_allowed']]
    assert len(old)==39 and len(pool)==907
    gate=audit_eligibility(root,registry_path,old,pool);dump(out/'explicit_exposure_application.json',gate)
    center={r['record_id']:r for r in csv.DictReader((root/'top_structure_20261012/mechanisms/results/real_39_centered_components.csv').open(encoding='utf-8-sig'))}
    rows39=[];rowspool=[];details=[];invariance=[]
    for layer,recset,output in [('aligned39',old,rows39),('descriptive907',pool,rowspool)]:
        for f in recset:
            c=cs[f['record_id']] if layer=='descriptive907' else f
            a=gs[c['object_id']];g=gs[c['reference_object_id']]
            d,detail=structural_diagnostics(a);dg,_=structural_diagnostics(g)
            row={k:f.get(k,c.get(k)) for k in ['record_id','object_id','reference_object_id','image_id','image_code','building_id','room_id','room_group','worker_id','applicability_confirmed','evidence_layer']}
            row['case_id']=f.get('old_case_id') or f.get('new_case_id')
            row['frozen_coordinate_sequence_sha256']=hashlib.sha256(json.dumps({k:a[k] for k in ['bottom3d','top3d']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
            row.update({k:c.get(k) for k in ['iou_2d','iou_3d_corner_mean','Hmean','Hlocal','Hstar','S_top_deg','S_bottom_deg','dir','flat','Q_v11','Q_no_topS']})
            row.update(d);row['reference_D_deg']=dg['D_independent_deg']
            row['reference_edge_count']=dg['edge_count']
            row['D_frozen_parity_error']=abs(d['D_independent_deg']-c['dir'])
            if layer=='aligned39':
                row['Hcenter']=float(center[f['record_id']]['Hcenter'])
                details.append({'record_id':f['record_id'],'case_id':row['case_id'],'diagnostics':detail})
                for mode in ['reverse','rotate','subdivide_good_long_edge40']:
                    aa=reorder(a,mode) if mode!='subdivide_good_long_edge40' else subdivide(a,int(np.argmax(detail['edge_length_h'])),40)
                    dd,_=structural_diagnostics(aa)
                    for key in ['D_independent_deg','adjacent_turn_rms_after_collinear_deg','adjacent_turn_max_deg','corner_admissible_rms_deg','corner_admissible_max_deg','minimum_interior_angle_deg','maximum_interior_angle_deg','direction_max_deg_min_over_ties','direction_max_deg_max_over_ties','direction_p95_deg_min_over_ties','direction_p95_deg_max_over_ties','direction_support_gt5_fraction_min_over_ties','direction_support_gt10_fraction_min_over_ties','direction_support_gt20_fraction_min_over_ties','convex_turns_count','concave_turns_count']:
                        invariance.append({'record_id':f['record_id'],'case_id':row['case_id'],'operation':mode,'metric':key,'before':d[key],'after':dd[key],'absolute_change':abs(dd[key]-d[key])})
            output.append(row)
    csvwrite(out/'real39_structural_metrics.csv',rows39);csvwrite(out/'development907_structural_metrics.csv',rowspool)
    dump(out/'real39_direction_details.json',details);csvwrite(out/'real39_same_curve_invariance.csv',invariance)
    summary={'real39_count':len(rows39),'real39_images':len({x['image_id'] for x in rows39}),
             'pool_count':len(rowspool),'pool_images':len({x['image_id'] for x in rowspool}),
             'pool_distinct_frozen_coordinate_sequences':len({x['frozen_coordinate_sequence_sha256'] for x in rowspool}),
             'frozen_D_max_absolute_error':max(x['D_frozen_parity_error'] for x in rows39+rowspool),
             'invariance_checks':len(invariance),'invariance_max_absolute_change':max(x['absolute_change'] for x in invariance),
             'no_new_human_labels':True,'no_severe_rate_or_FPR':True,'diagnostic_probe_levels_not_human_cutoffs':True}
    conditions={
        'D_lt5_adjacent_max_gt20':lambda x:x['dir']<5 and x['adjacent_turn_max_deg']>20,
        'D_lt5_direction_max_gt20_all_ties':lambda x:x['dir']<5 and x['direction_max_deg_min_over_ties']>20,
        'D_lt2_floor_IoU_lt0_75':lambda x:x['dir']<2 and x['iou_2d']<.75,
        'direction_gt20_support_between0_and0_01':lambda x:0<x['direction_support_gt20_fraction_min_over_ties']<.01,
        'D_ge10':lambda x:x['dir']>=10,
        'D_lt5_interior_lt45_or_gt315':lambda x:x['dir']<5 and (x['minimum_interior_angle_deg']<45 or x['maximum_interior_angle_deg']>315),
    }
    counts=[]
    for stratum,rr in [('all_conditional',rowspool),('explicit_applicability', [x for x in rowspool if x['applicability_confirmed']]),('unknown_applicability',[x for x in rowspool if not x['applicability_confirmed']])]:
        for condition,fun in conditions.items():
            sel=[x for x in rr if fun(x)]
            counts.append({'stratum':stratum,'condition':condition,'denominator_records':len(rr),'denominator_images':len({x['image_id'] for x in rr}),'denominator_distinct_frozen_sequences':len({x['frozen_coordinate_sequence_sha256'] for x in rr}),'records':len(sel),'images':len({x['image_id'] for x in sel}),'distinct_frozen_sequences':len({x['frozen_coordinate_sequence_sha256'] for x in sel}),'record_ids':'|'.join(x['record_id'] for x in sel),'no_quality_label_inferred':True})
    csvwrite(out/'descriptive_conditions_counts.csv',counts);dump(out/'real_summary.json',summary)
    return summary

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path.cwd());ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'results');ap.add_argument('--controls-only',action='store_true');ap.add_argument('--real-only',action='store_true');ap.add_argument('--exposure-registry',type=Path);args=ap.parse_args()
    root=args.root.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    b=root/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    sys.path.insert(0,str(b/'frozen/scope_engine/core'));sys.path.insert(0,str(root/'top_structure_20261012/mechanisms'))
    import quality_v11,audit_geometry,run_mechanisms,centered_height
    protocol=Path(__file__).with_name('protocol_before_results.json')
    manifest={'script_sha256':sha(Path(__file__)),'protocol_sha256':sha(protocol),'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,
              'addendum_sha256':sha(Path(__file__).with_name('protocol_addendum_after_initial40.json')),
              'sharp_angle_addendum_sha256':sha(Path(__file__).with_name('protocol_addendum_sharp_angles.json')),
              'source_hashes':{str(p.relative_to(root)):sha(p) for p in [b/'frozen/scope_engine/legacy_geometry/audit_geometry.py',b/'frozen/scope_engine/core/quality_v11.py',b/'inputs/current_geometry_compact.json',b/'results/current_components.json']}}
    if not args.real_only:
        rs=controls(root,out,quality_v11,audit_geometry,run_mechanisms,centered_height)
        manifest['synthetic_count']=len(rs);manifest['synthetic_available']=sum(x['status']=='available' for x in rs)
    if not args.controls_only:
        if args.exposure_registry is None:raise ValueError('--exposure-registry is required for real data; no implicit historical filter is enough')
        manifest['real_summary']=real(root,out,args.exposure_registry.resolve(),audit_geometry)
    dump(out/'run_manifest.json',manifest);print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
