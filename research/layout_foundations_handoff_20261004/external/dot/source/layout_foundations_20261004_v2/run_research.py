"""Recompute independent foundation experiments into a new directory.
Stages are explicit to accommodate time-limited execution environments.
"""
from __future__ import annotations
import argparse,copy,csv,json,sys,platform,hashlib,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from arc_consensus import *
from quality import quality,directed,point_arc_dist
from simplify import *
from cases import *
from baseline_points import point_baseline

def dump(p,obj):
    def clean(x):
        if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
        if isinstance(x,(tuple,list,np.ndarray)):return [clean(v) for v in x]
        if isinstance(x,(np.integer,)):return int(x)
        if isinstance(x,(np.bool_,)):return bool(x)
        if isinstance(x,(np.floating,)):return float(x)
        return x
    Path(p).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def csvwrite(p,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def normalized_cases(load_refs=False):
    # Construction does not even open either isolated reference file.
    a=json.loads((ROOT/'inputs/current_excerpt.json').read_text())['images'][0]
    b=json.loads((ROOT/'inputs/real24_points.json').read_text())
    cases=[('pilot3',a['code'],a['annotations']),('real24',b['image'],b['records'])]
    out=[]
    for label,image,rs in cases:
        rs=copy.deepcopy(rs)
        for r in rs:r.update(image=image,evidence_kind='human_observed')
        ref=None
        if load_refs:
            if label=='pilot3':
                refs=json.loads((ROOT/'inputs/reference_excerpt.json').read_text())['references']
                ref=next(r for r in refs if r['code']==image and r['version']=='original')
            else:ref=json.loads((ROOT/'inputs/real24_reference.json').read_text())
        out.append((label,image,rs,ref))
    return out

def real_stage(out):
    checks=[]
    for label,image,rs,ref in normalized_cases():
        # The reference is not passed to any construction routine.
        exact=fuse(rs);dump(out/f'{label}_fusion.json',exact)
        if not exact['methods']:raise RuntimeError('unexpected_real_failure')
        for method,f in exact['methods'].items():
            A=Polygon(f['footprint']);B=tile_vote(rs,f['equivalent_bev_threshold'])
            checks.append(dict(case=label,n=len(rs),erp_method=method,pairs=f['pair_count'],
                bev_threshold=f['equivalent_bev_threshold'],max_roundtrip_px=f['max_serialization_error_px'],
                symdiff_to_independent_bev_vote_h2=A.symmetric_difference(B).area,
                top_bottom_different_donor_fraction=f['different_top_bottom_donor_longitude_fraction']))
        main=exact['methods'][exact['bev_mv50_complete_method']];costs=compression_costs(main)
        for e in [0.,.25,.5,1.,2.]:dump(out/f'{label}_compressed_{e:g}px.json',compress(main,e,costs))
        dump(out/f'{label}_point_baseline.json',point_baseline(rs,5.))
        print('constructed',label,len(rs),flush=True)
    csvwrite(out/'construction_checks.csv',checks)
    dump(out/'construction_freeze.json',dict(gt_used=False,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
       for p in sorted(out.glob('*.json')) if 'quality' not in p.name}))
    dump(out/'failure_nonmonotone.json',fuse(failure_records()))

def evaluation_stage(out):
    if not (out/'construction_freeze.json').exists():raise ValueError('construct_and_freeze_first')
    freeze=json.loads((out/'construction_freeze.json').read_text())
    for name,h in freeze['files'].items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=h:raise ValueError('prediction_changed_after_freeze')
    rows=[];full=[]
    for label,image,rs,ref in normalized_cases(load_refs=True):
        exact=json.loads((out/f'{label}_fusion.json').read_text())
        outputs=[(f'exact_erp_{m}',v) for m,v in exact['methods'].items()]
        outputs += [(f'compressed_{e:g}px',json.loads((out/f'{label}_compressed_{e:g}px.json').read_text())) for e in [0.,.25,.5,1.,2.]]
        outputs += [(f'point5_{m}',v) for m,v in json.loads((out/f'{label}_point_baseline.json').read_text()).items() if v.get('footprint')]
        lee=tile_vote(rs,(len(rs)+1)//2)
        for name,p in outputs:
            q=quality(p,ref,step=.05);pgeom=Polygon(p['footprint']);lr=pgeom.symmetric_difference(lee).area
            row=dict(case=label,image=image,n=len(rs),method=name,pairs=q['pair_count'],gt_bev_iou=q['iou'],
                centroid_h=q['centroid_distance_h'],omission_h2=q['omission_h2'],extension_h2=q['extension_h2'],
                bev_symdiff_from_lee50_h2=lr,
                top_mean_deg=(q['top_candidate_to_reference']['mean_deg']+q['top_reference_to_candidate']['mean_deg'])/2,
                bottom_mean_deg=(q['bottom_candidate_to_reference']['mean_deg']+q['bottom_reference_to_candidate']['mean_deg'])/2,
                azimuth_mean_height_difference_h=q['height_profile_difference'].get('azimuth_mean_absolute_height_difference_h'),
                top_height_min_h=q['top_height_proxy_min_h'],top_height_max_h=q['top_height_proxy_max_h'])
            rows.append(row);full.append(dict(case=label,method=name,quality=q))
        csvwrite(out/'real_quality.csv',rows);dump(out/'real_quality_details.json',full)
        print('evaluated',label,flush=True)
    dump(out/'evaluation_contract.json',dict(reference='original_only',candidate_selection_by_gt=False,
        interpretation='declared geometry reference compatibility; not visual truth',
        boundary_distance='declared spherical edge union, directed arc-length midpoint quadrature',
        step_deg=.05,mean_error_bound_deg=.0125,maximum_distance_bound_deg=.025,solid_iou=None))

def controls_stage(out):
    a,b=thin_feature();rs=[copy.deepcopy(b) for _ in range(3)]
    for i,r in enumerate(rs):r.update(id=f'narrow_{i}',worker=f'narrow_{i}')
    exact=fuse(rs);main=exact['methods']['mv50'];comp=compress(main,1.)
    r1,r2=Ring(a),Ring(b);x=(np.arange(512)+.5)*W/512
    vals=dict(width_px=.4,amplitude_px=20.,sampled512_max_error_px=float(np.max(abs(r1.evaluate(x/W*TAU)-r2.evaluate(x/W*TAU)))),
       peak_exact_error_px=float(np.max(abs(r1.evaluate(100.4/W*TAU)-r2.evaluate(100.4/W*TAU)))),
       bev_iou=footprint(a)[1].intersection(footprint(b)[1]).area/footprint(a)[1].union(footprint(b)[1]).area,
       directed_top_curve=directed(b,a,0,.05),exact_pairs=main['pair_count'],compressed_pairs=comp['pair_count'],
       compressed_max_error_px=comp['maximum_vertical_curve_error_px'],
       compressed_peak_error_px=float(abs(Ring(comp).evaluate(100.4/W*TAU)[0]-r2.evaluate(100.4/W*TAU)[0])))
    dump(out/'narrow_feature.json',dict(results=vals,base=a,changed=b,fusion=exact,compressed=comp))
    # Same observed perimeter, different UNOBSERVED interior cap; no new observed points.
    flat=rectangle(2.,1.);_,P=footprint(flat)
    basevol=P.area*2.;peak=2.;roofextra=P.area*peak/3.
    dump(out/'roof_nonidentifiability.json',dict(observed_boundary=flat,perimeter_height_h=1.,floor_y_h=-1.,
       flat_volume_h3=basevol,tent_volume_h3=basevol+roofextra,solid_iou=basevol/(basevol+roofextra),
       all_observed_point_and_boundary_metrics_identical=True,
       conclusion='Roof volume is unidentified by perimeter alone; a declared flat-roof model makes a conditional volume well-defined.'))
    # Height is derived jointly from top ray and bottom depth.
    variants=[]
    for side,name in [(0,'top_only'),(1,'bottom_only')]:
        change=copy.deepcopy(flat)
        for point in change['points'][side::2]:point[1]-=4.
        variants.append(dict(change=name,quality=quality(change,flat,step=.05)))
    dump(out/'height_coupling.json',variants)
    # Two concentric rectangular observations make the dual thresholds unambiguous.
    rr=[rectangle(1.,1.,'small'),rectangle(2.,1.,'large')];ff=fuse(rr)
    dump(out/'two_person_threshold_duality.json',dict(inputs=rr,result=ff,
       erp_mv50_vs_bev_mv50_iou=area_scores(Polygon(ff['methods']['mv50']['footprint']),tile_vote(rr,1))['iou']))
    # A bounded local error can materially change a near-horizon floor depth.
    rows=[]
    for y in [300.,270.,258.,257.5]:
        for e in [.25,.5,1.]:
            r=lambda v:1/np.tan(np.pi*(v/H-.5))
            if y-e<=H/2:continue
            rows.append(dict(bottom_y=y,delta_y_px=-e,depth_before_h=r(y),depth_after_h=r(y-e),relative_change=r(y-e)/r(y)-1))
    csvwrite(out/'angular_to_depth_sensitivity.csv',rows)
    # Depth-independent projective loci: compare source endpoint-scaled 3D segments.
    rng=np.random.default_rng(20261004);err=[]
    for j in range(100):
        u=rng.uniform(0,TAU);gap=rng.uniform(.1,2.5);xx=np.array([u,u+gap])/TAU*W%W
        yy=rng.uniform(80,230,size=2);p=np.c_[xx,yy];v=rays(p);scales=rng.uniform(.2,15,size=2)
        C=np.linalg.solve(np.c_[np.sin(xx/W*TAU),np.cos(xx/W*TAU)],np.tan(np.pi*(.5-yy/H)))
        t=np.linspace(0,1,257);z=(1-t)[:,None]*(v[0]*scales[0])+t[:,None]*(v[1]*scales[1]);px=project(z)
        pred=H*(.5-np.arctan(np.c_[np.sin(px[:,0]/W*TAU),np.cos(px[:,0]/W*TAU)]@C)/np.pi)
        err.append(float(np.max(abs(pred-px[:,1]))))
    dump(out/'positive_depth_projection.json',dict(trials=100,samples_per_edge=257,max_y_error_px=max(err),
       meaning='positive endpoint depth changes reparameterize the same minor spherical arc; they do not infer the physical edge or its visibility'))
    # Continuous extremum routine checked against dense numerical samples.
    rng=np.random.default_rng(91004);under=[]
    for j in range(500):
        c=rng.normal(size=2)*10**rng.uniform(-1,1);d=rng.normal(size=2)*10**rng.uniform(-1,1)
        lo=rng.uniform(0,TAU);hi=lo+rng.uniform(.0001,3.13)
        u=np.linspace(lo,hi,5001);M=np.c_[np.sin(u),np.cos(u)]
        dense=H/np.pi*max(abs(np.arctan(M@c)-np.arctan(M@d)));stationary=extrema_error(c,d,lo,hi)
        under.append(float(dense-stationary))
    dump(out/'stationary_point_validation.json',dict(trials=500,dense_samples=5001,max_dense_minus_stationary_px=max(under),
       not_interval_arithmetic_proof=True))
    print('controls completed',flush=True)

def synthetic_stage(out):
    rng=np.random.default_rng(804610);rows=[];fail=[]
    # Every input is a known camera-star polygon; counts vary by observer.
    for case in range(40):
        n=[2,3,4,5,8][case%5];rs=[]
        for j in range(n):
            m=[4,5,6,8][(case+j)%4];u=np.arange(m)*TAU/m+rng.uniform(-.1,.1,size=m)+.25
            radius=rng.uniform(1.8,3.2,size=m);poly=np.c_[-radius*np.sin(u),radius*np.cos(u)]
            rs.append(make_record(poly,rng.uniform(.7,1.5,size=m),f's{case}_{j}',f'w{j}'))
        try:
            ff=fuse(rs)
            if not ff['methods']:raise ValueError(str(ff['failures']))
            for method,v in ff['methods'].items():
                p=Polygon(v['footprint']);b=tile_vote(rs,v['equivalent_bev_threshold'])
                u=rng.uniform(0,TAU,4096);arrays=np.stack([Ring(r).evaluate(u) for r in rs]);t=v['erp_threshold']
                expected=np.array([np.sort(arrays[:,0],axis=0)[t-1],np.sort(arrays[:,1],axis=0)[n-t]])
                err=float(np.max(abs(Ring(v).evaluate(u)-expected)))
                rows.append(dict(case=case,n=n,input_pair_counts='|'.join(str(len(r['points'])//2) for r in rs),
                    method=method,output_pairs=v['pair_count'],curve_error_px=err,
                    bev_symdiff_h2=p.symmetric_difference(b).area))
        except Exception as e:fail.append(dict(case=case,reason=repr(e),inputs=rs))
    csvwrite(out/'synthetic_validation.csv',rows);dump(out/'synthetic_failures.json',fail)
    if fail:raise RuntimeError('synthetic_failures_retained')
    print('synthetic',len(rows),'states',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--stage',choices=['construct','evaluate','controls','synthetic','all'],default='all');a=p.parse_args()
    if a.stage in ['all','construct'] and a.out.exists() and any(a.out.iterdir()):raise ValueError('use_new_output_directory')
    a.out.mkdir(parents=True,exist_ok=True)
    if a.stage in ['all','construct']:real_stage(a.out)
    if a.stage in ['all','evaluate']:evaluation_stage(a.out)
    if a.stage in ['all','controls']:controls_stage(a.out)
    if a.stage in ['all','synthetic']:synthetic_stage(a.out)
