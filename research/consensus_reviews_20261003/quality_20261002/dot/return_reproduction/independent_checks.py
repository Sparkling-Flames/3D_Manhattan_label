#!/usr/bin/env python3
"""Independent equation/count checks. Does not import returned quality_core.

Usage: python independent_checks.py --package PACKAGE --out OUTPUT
Needs numpy and shapely. No input writes and no network access.
"""
import argparse, collections, csv, itertools, json, math
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, Point

def geometry(record):
    p=record['points']; floor=[]; heights=[]
    for i in range(0,len(p),2):
        x,yt=p[i];xb,yb=p[i+1]
        assert abs((x-xb+512)%1024-512)<1e-6
        longitude=(xb-512)*math.pi/512
        alpha=(yb-256)*math.pi/512
        beta=(256-yt)*math.pi/512
        r=1/math.tan(alpha)
        floor.append([r*math.sin(longitude),-r*math.cos(longitude)])
        heights.append(1+r*math.tan(beta))
    return np.array(floor), np.array(heights)

def perimeter_stats(xy,h):
    # Simpson integration is exact for linear h(s) and quadratic h(s)^2.
    lengths=np.linalg.norm(np.roll(xy,-1,axis=0)-xy,axis=1)
    next_h=np.roll(h,-1);mid=(h+next_h)/2
    first=np.sum(lengths*(h+4*mid+next_h)/6)/sum(lengths)
    second=np.sum(lengths*(h*h+4*mid*mid+next_h*next_h)/6)/sum(lengths)
    return float(first),math.sqrt(max(0,float(second-first*first)))

def exact_axis_rms(xy):
    # Enumerate the quadratic pieces between wrap breakpoints, no local optimizer.
    edge=np.roll(xy,-1,axis=0)-xy
    w=np.linalg.norm(edge,axis=1);theta=np.arctan2(edge[:,1],edge[:,0])
    period=math.pi/2
    breaks=sorted(set([0.,period]+list((theta+period/2)%period)))
    def residual(t):return (theta-t+period/2)%period-period/2
    candidates=[]
    for lo,hi in zip(breaks,breaks[1:]):
        mid=(lo+hi)/2;centers=mid+residual(mid)
        optimum=float(np.average(centers,weights=w))
        candidates.extend([lo,hi,max(lo,min(hi,optimum))])
    return math.degrees(math.sqrt(min(float(np.average(residual(t)**2,weights=w)) for t in candidates)))

def mask(xy,h):
    if not Polygon(xy).contains(Point(0,0)):return None
    columns=[]
    for col in range(1024):
        u=(col+.5-512)*math.pi/512;ray=np.array([math.sin(u),-math.cos(u)])
        hits=[]
        for i,p in enumerate(xy):
            edge=xy[(i+1)%len(xy)]-p
            # r*ray = p + t*edge, solved directly.
            matrix=np.column_stack([ray,-edge])
            if abs(np.linalg.det(matrix))<1e-12:continue
            r,t=np.linalg.solve(matrix,p)
            if r>0 and -1e-10<=t<=1+1e-10:
                topheight=h[i]+t*(h[(i+1)%len(h)]-h[i])
                hits.append((r,topheight))
        assert hits
        r,hh=min(hits)
        top=256-math.atan2(hh-1,r)*512/math.pi
        bottom=256+math.atan2(1,r)*512/math.pi
        y=np.arange(512)+.5
        columns.append((y>=top)&(y<=bottom))
    return np.stack(columns,axis=1)

def compare(a,b,with_mask=False):
    xy,h=geometry(a);ref,refh=geometry(b)
    pa,pb=Polygon(xy),Polygon(ref);ia=pa.intersection(pb).area
    ha,rmsa=perimeter_stats(xy,h);hb,_=perimeter_stats(ref,refh)
    iv=ia*min(ha,hb)
    out={'bev_iou':ia/(pa.area+pb.area-ia),'current_model_volume_iou':iv/(pa.area*ha+pb.area*hb-iv),
         'current_height_mean_a_h':ha,'current_height_rms_a_h':rmsa,'self_axis_rms_deg':exact_axis_rms(xy)}
    if with_mask:
        ma,mb=mask(xy,h),mask(ref,refh)
        out['column_iou']=float(np.sum(ma&mb)/np.sum(ma|mb)) if ma is not None and mb is not None else None
    return out

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    p=args.package
    data=json.loads((p/'inputs/current_numeric_subset.json').read_text());assert len(data['images'])==1
    im=data['images'][0];ann={r['id']:r for r in im['annotations']};ref=im['references'][0]
    with (p/'inputs/read_upstream_csv_subset.csv').open(encoding='utf-8-sig') as f:expected=list(csv.DictReader(f))
    fields=list(expected[0])[2:];rows=[];by_id={};identity_mismatches=[]
    for row in expected:
        id=row['annotation'];metrics=compare(ann[id],ref,True);by_id[id]=metrics
        if ann[id]['worker']!=row['worker_from_csv']:
            identity_mismatches.append({'annotation':id,'excerpt_worker':ann[id]['worker'],'csv_worker':row['worker_from_csv']})
        for field in fields:
            if row[field] and metrics[field] is not None:
                value,actual=float(row[field]),metrics[field]
                rows.append({'annotation':id,'field':field,'expected':value,'independent':actual,
                             'absolute_difference':abs(value-actual),'passed':math.isclose(value,actual,rel_tol=1e-9,abs_tol=1e-10)})
    assert len(rows)==35 and all(r['passed'] for r in rows)
    with (args.out/'independent_common_fields.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    cases=json.loads((p/'inputs/controlled_inputs.json').read_text());case_counts=dict(collections.Counter(c['case'] for c in cases))
    assert case_counts=={'density':7,'opposite_roofs':1,'top_bottom_dependency':1,'horizon_sensitivity':2,'derived_real_subdivision':6}
    invariant=[]
    for c in cases:
        if c['case'] in ('density','derived_real_subdivision'):
            result=compare(c['a'],c['b'])
            invariant.append({'case':c['case'],'id':c['a']['id'],'bev_loss':abs(1-result['bev_iou']),
                              'volume_loss':abs(1-result['current_model_volume_iou'])})
    assert max(max(r['bev_loss'],r['volume_loss']) for r in invariant)<1e-10
    reversals=[];valid={k:v for k,v in by_id.items() if v['column_iou'] is not None}
    for (a,ma),(b,mb) in itertools.combinations(valid.items(),2):
        for metric in ('current_model_volume_iou','column_iou'):
            if (ma['bev_iou']-mb['bev_iou'])*(ma[metric]-mb[metric])<0:
                reversals.append({'a':a,'b':b,'other_metric':metric})
    assert len(reversals)==3
    # Independent exact integrations: integral_-2^2 4*(3 - .5*abs(x)) dx.
    roof_intersection=2*4*(3*2-.25*2**2)
    roof_volume=4*3*4;roof_union=2*roof_volume-roof_intersection
    assert (roof_volume,roof_intersection,roof_union)==(48,40,56)
    roof=next(c for c in cases if c['case']=='opposite_roofs');roof_result=compare(roof['a'],roof['b'])
    assert abs(roof_result['current_model_volume_iou']-1)<1e-12
    # For these equal-location opposite slopes the wall difference is X, so
    # boundary mean(X^2) = (2*4*4 + 2*integral_-2^2 X^2 dX)/16 = 8/3.
    roof_wall_rmse_exact=math.sqrt(8/3)
    controlled=json.loads((p/'results/controlled_results.json').read_text())
    roof_wall_rmse_discrete=controlled['opposite_roofs']['wall_height_rmse_h']
    coupled=next(c for c in cases if c['case']=='top_bottom_dependency')
    q=1.25;original_height=2.7;new_height=1+q*(original_height-1)
    coupling=compare(coupled['a'],coupled['b'])
    assert abs(coupling['bev_iou']-q**-2)<1e-12
    assert abs(coupling['current_model_volume_iou']-original_height/(q*q*new_height))<1e-12
    assert np.max(abs(np.array(coupled['a']['points'])[::2]-np.array(coupled['b']['points'])[::2]))<1e-12
    horizon=[]
    for extent in (2.,32.):
        r=math.sqrt(2)*extent;alpha=math.atan(1/r);delta=1/math.tan(alpha-math.pi*.5/512)-r
        horizon.append({'half_extent_h':extent,'one_corner_shift_h':delta})
    for calculated,saved in zip(horizon,controlled['horizon']):
        assert abs(calculated['one_corner_shift_h']-saved['one_corner_shift_h'])<1e-10
    # Verify the report's Jacobian by finite differences at an interior point.
    alpha,beta=.4,.55;eps=1e-6
    radius=lambda a:1/math.tan(a)
    H=lambda a,b:1+radius(a)*math.tan(b)
    jac_analytic=[-1/math.sin(alpha)**2,-math.tan(beta)/math.sin(alpha)**2,radius(alpha)/math.cos(beta)**2]
    jac_fd=[(radius(alpha+eps)-radius(alpha-eps))/(2*eps),(H(alpha+eps,beta)-H(alpha-eps,beta))/(2*eps),(H(alpha,beta+eps)-H(alpha,beta-eps))/(2*eps)]
    assert max(abs(x-y) for x,y in zip(jac_analytic,jac_fd))<1e-8
    result={'does_not_import_returned_implementation':True,'saved_images':len(data['images']),
            'saved_annotations':len(ann),'selected_annotations':len(expected),'saved_references':len(im['references']),
            'independent_common_fields':len(rows),'all_common_fields_passed':all(r['passed'] for r in rows),
            'independent_max_difference':max(r['absolute_difference'] for r in rows),
            'identity_mismatches_in_returned_files':identity_mismatches,'controlled_case_counts':case_counts,
            'controlled_pairs':len(cases),'subdivision_invariance':invariant,'comparable_column_annotations':len(valid),
            'pair_count':math.comb(len(valid),2),'independent_reversals':reversals,
            'opposite_roofs':{'volume_a_h3':roof_volume,'intersection_h3':roof_intersection,'union_h3':roof_union,'exact_iou':roof_intersection/roof_union,
                              'current_proxy_iou':roof_result['current_model_volume_iou'],'exact_wall_height_rmse':roof_wall_rmse_exact,
                              'reported_discrete_wall_height_rmse':roof_wall_rmse_discrete,'discretization_error':roof_wall_rmse_discrete-roof_wall_rmse_exact},
            'fixed_top_coupling':{'original_height':original_height,'new_height':new_height,'range_scale':q,
                                  'expected_bev_iou':q**-2,'expected_volume_iou':original_height/(q*q*new_height)},
            'half_pixel_horizon':horizon,'jacobian_analytic':jac_analytic,'jacobian_finite_difference':jac_fd,
            'scope':'Selected numeric excerpt and controlled equations only; not full 195/390 repository reproduction or validity adjudication'}
    (args.out/'independent_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('subdivision_invariance',)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
