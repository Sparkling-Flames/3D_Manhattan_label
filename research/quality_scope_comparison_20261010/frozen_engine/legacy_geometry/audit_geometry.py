#!/usr/bin/env python3
"""Independent audit from frozen geometry, no input/GT/rating modification.

Usage: python audit_geometry.py --source SOURCE --out OUT
Requires Python 3, NumPy, SciPy. Does not require shapely or network access.
Polygon intersection is reconstructed by ear triangulation and convex clipping.
This audit is for the bundled simple rings, rejects detected proper crossings,
zero-length edges and triangulation failures, and never repairs geometry. It is
not a general-purpose validator for every collinear/degenerate polygon.
"""
import argparse,csv,hashlib,json,math,platform,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import minimize_scalar

EPS=1e-12

def cross(a,b):return float(a[0]*b[1]-a[1]*b[0])

def signed_area(p):
    return sum(cross(a,b) for a,b in zip(p,np.roll(p,-1,axis=0)))/2

def centroid(p):
    pn=np.roll(p,-1,axis=0)
    cc=np.array([cross(a,b) for a,b in zip(p,pn)])
    return np.sum((p+pn)*cc[:,None],axis=0)/(3*cc.sum())

def proper_intersection(a,b,c,d):
    e=b-a;f=d-c;den=cross(e,f)
    if abs(den)<EPS:return False
    u=cross(c-a,f)/den;v=cross(c-a,e)/den
    return EPS<u<1-EPS and EPS<v<1-EPS

def validate_simple(p):
    if abs(signed_area(p))<EPS:raise ValueError('zero_area')
    n=len(p)
    for i in range(n):
        if np.linalg.norm(p[i]-p[(i+1)%n])<EPS:raise ValueError('duplicate_adjacent_vertex')
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1):continue
            if proper_intersection(p[i],p[(i+1)%n],p[j],p[(j+1)%n]):raise ValueError('self_intersection')

def in_triangle(q,a,b,c):
    return min(cross(b-a,q-a),cross(c-b,q-b),cross(a-c,q-c))>=-EPS

def triangulate(p):
    """Analytical representation of same polygon; no geometry repair."""
    p=np.asarray(p,float)
    validate_simple(p)
    if signed_area(p)<0:p=p[::-1].copy()
    ids=list(range(len(p)));res=[]
    while len(ids)>3:
        found=False
        for k,j in enumerate(ids):
            i,l=ids[k-1],ids[(k+1)%len(ids)]
            a,b,c=p[i],p[j],p[l]
            if cross(b-a,c-b)<=EPS:continue
            if any(in_triangle(p[m],a,b,c) for m in ids if m not in [i,j,l]):continue
            res.append(np.array([a,b,c]));ids.pop(k);found=True;break
        if not found:raise ValueError('ear_triangulation_failed; geometry_not_modified')
    res.append(p[ids])
    if not math.isclose(sum(abs(signed_area(t)) for t in res),abs(signed_area(p)),rel_tol=1e-10,abs_tol=1e-10):
        raise ValueError('triangulation_area_mismatch')
    return res

def convex_clip(p,clip):
    p=[np.array(x) for x in p]
    for a,b in zip(clip,np.roll(clip,-1,axis=0)):
        if not p:break
        previous=p[-1];was_in=cross(b-a,previous-a)>=-EPS;out=[]
        for q in p:
            is_in=cross(b-a,q-a)>=-EPS
            if is_in!=was_in:
                d=q-previous;den=cross(b-a,d)
                if abs(den)>1e-20:
                    tt=-cross(b-a,previous-a)/den
                    out.append(previous+tt*d)
            if is_in:out.append(q)
            previous=q;was_in=is_in
        p=out
    return np.asarray(p)

def intersection_area(p,q):
    total=0.
    for ta in triangulate(p):
        for tb in triangulate(q):
            clip=convex_clip(ta,tb)
            if len(clip)>=3:total+=abs(signed_area(clip))
    return total

def area_metrics(a,g):
    pa=np.asarray(a['bottom3d'])[:,[0,2]];pg=np.asarray(g['bottom3d'])[:,[0,2]]
    aa=abs(signed_area(pa));ag=abs(signed_area(pg));ii=intersection_area(pa,pg)
    return dict(iou=ii/(aa+ag-ii),C=float(np.linalg.norm(centroid(pa)-centroid(pg))/math.sqrt(ag)),
        omission=(ag-ii)/ag,extension=(aa-ii)/ag,area_h2=aa,reference_area_h2=ag,intersection_area_h2=ii,
        centroid_dx_h=float(centroid(pa)[0]-centroid(pg)[0]),centroid_dz_h=float(centroid(pa)[1]-centroid(pg)[1]))

def sample_ring(p,n=512):
    p=np.asarray(p,float);e=np.roll(p,-1,axis=0)-p;l=np.linalg.norm(e,axis=1)
    cum=np.r_[0,np.cumsum(l)];s=(np.arange(n)+.5)/n*cum[-1]
    ix=np.searchsorted(cum,s,side='right')-1;alpha=(s-cum[ix])/l[ix]
    return p[ix]+alpha[:,None]*e[ix]

def directed_curve_distance(p,q,n=512):
    sam=sample_ring(p,n);q=np.asarray(q,float);e=np.roll(q,-1,axis=0)-q
    vec=sam[:,None,:]-q[None,:,:]
    t=np.sum(vec*e[None,:,:],axis=2)/np.sum(e*e,axis=1)[None,:]
    t=np.clip(t,0,1)
    d=np.linalg.norm(vec-t[:,:,None]*e[None,:,:],axis=2).min(axis=1)
    return float(d.mean())

def sym_distance(p,q,n=512):
    return (directed_curve_distance(p,q,n)+directed_curve_distance(q,p,n))/2

def height_stats(a):
    t,b=np.asarray(a['top3d']),np.asarray(a['bottom3d'])
    ll=np.linalg.norm(np.roll(b,-1,axis=0)-b,axis=1);h=t[:,1]+1;hn=np.roll(h,-1)
    mean=np.dot(ll,(h+hn)/2)/ll.sum()
    # Integrate centered square directly to avoid cancellation.
    dd=h-mean;ddn=np.roll(dd,-1)
    rms=np.sqrt(np.dot(ll,(dd*dd+dd*ddn+ddn*ddn)/3)/ll.sum())
    return dict(height_mean_h=float(mean),height_internal_rms_h=float(rms),height_internal_relative_rms=float(rms/mean))

def direction_data(a):
    b=np.asarray(a['bottom3d'])[:,[0,2]];e=np.roll(b,-1,axis=0)-b
    theta=np.arctan2(e[:,1],e[:,0]);w=np.linalg.norm(e,axis=1)
    return theta,w

def direction_residual(a,axis):
    theta,w=direction_data(a);period=np.pi/2
    return float(np.rad2deg(np.sqrt(np.dot(w,((theta-axis+period/2)%period-period/2)**2)/w.sum())))

def direction_axis(a):
    """Global minimum of weighted squared circular residual modulo 90deg."""
    theta,w=direction_data(a);period=np.pi/2
    breaks=np.unique(np.r_[0,(theta+period/2)%period,period]);cand=list(breaks)
    for lo,hi in zip(breaks[:-1],breaks[1:]):
        mid=(lo+hi)/2;res=(theta-mid+period/2)%period-period/2
        opt=mid+np.dot(w,res)/sum(w)
        if lo<=opt<=hi:cand.append(opt)
    return min(cand,key=lambda ax:direction_residual(a,ax))

def flatness(a,n=512):
    """Equal midpoint sampling of floor perimeter; upper edge interpolated."""
    t,b=np.asarray(a['top3d']),np.asarray(a['bottom3d'])
    ll=np.linalg.norm(np.roll(b,-1,axis=0)-b,axis=1);cum=np.r_[0,np.cumsum(ll)]
    s=(np.arange(n)+.5)/n*cum[-1];ix=np.searchsorted(cum,s,side='right')-1
    alpha=(s-cum[ix])/ll[ix]
    p=t[ix]+alpha[:,None]*(np.roll(t,-1,axis=0)[ix]-t[ix])
    r=np.linalg.norm(p[:,[0,2]],axis=1);phi=np.arctan2(p[:,1],r)
    obj=lambda ht:np.mean((phi-np.arctan2(ht,r))**2)
    lo=min(-.999,float(p[:,1].min())-1);hi=max(1,float(p[:,1].max())+1)
    opt=minimize_scalar(obj,bounds=(lo,hi),method='bounded',options={'xatol':1e-13})
    return dict(flat=float(np.rad2deg(np.sqrt(opt.fun))),flat_top_fitted_height_h=float(opt.x+1))

def own_metrics(a):
    r2=np.sum(np.asarray(a['bottom3d'])[:,[0,2]]**2,axis=1)
    ax=direction_axis(a)
    out=height_stats(a);out.update(flatness(a));out.update(dir=direction_residual(a,ax),axis_deg=float(np.rad2deg(ax)),
        max_depth_sensitivity_h_per_Cpx=float(np.max((1+r2)*np.pi/512)),
        bottom_horizon_margin_deg=float(np.rad2deg(np.arctan2(1,np.sqrt(r2.max())))))
    return out

def ray_intersections(p,n=4096):
    """All declared ring intersections per sampled azimuth; no envelope selection."""
    p=np.asarray(p,float);q=np.roll(p,-1,axis=0);e=q-p
    # x=-sin(2pi x/W), z=cos(2pi x/W); only uniform phase matters for MAE.
    longitude=(np.arange(n)+.5)/n*2*np.pi
    d=np.column_stack([-np.sin(longitude),np.cos(longitude)])
    pp=p[:,[0,2]];ee=e[:,[0,2]]
    den=d[:,0,None]*ee[None,:,1]-d[:,1,None]*ee[None,:,0]
    cross_pe=pp[:,0]*ee[:,1]-pp[:,1]*ee[:,0]
    cross_pd=pp[None,:,0]*d[:,1,None]-pp[None,:,1]*d[:,0,None]
    with np.errstate(divide='ignore',invalid='ignore'):
        ray_t=cross_pe[None,:]/den;seg_t=cross_pd/den
    valid=(ray_t>0)&(seg_t>=0)&(seg_t<1)&(np.abs(den)>1e-15)
    ys=p[None,:,1]+seg_t*e[None,:,1]
    elevation=np.arctan2(ys,ray_t)
    count=valid.sum(axis=1)
    return count,np.sum(np.where(valid,elevation,0),axis=1)

def ring_status(a):
    p=np.asarray(a['bottom3d'])[:,[0,2]]
    angles=np.arctan2(p[:,1],p[:,0]);inc=(np.roll(angles,-1)-angles+np.pi)%(2*np.pi)-np.pi
    positive=int(np.sum(inc>1e-10));negative=int(np.sum(inc<-1e-10))
    count,_=ray_intersections(a['bottom3d'])
    ok=bool((positive==0 or negative==0) and abs(abs(inc.sum())-2*np.pi)<1e-6 and np.all(count==1))
    return dict(single_valued_recomputed=ok,angular_backtracking_edges=min(positive,negative),
        absolute_winding=float(abs(inc.sum())/(2*np.pi)),rays_not_single=int(np.sum(count!=1)),max_intersections=int(count.max()))

def boundary_metrics(a,g):
    if not ring_status(a)['single_valued_recomputed'] or not ring_status(g)['single_valued_recomputed']:
        return dict(U=None,B=None)
    result={}
    for key,ring in [('U','top3d'),('B','bottom3d')]:
        ca,va=ray_intersections(a[ring]);cg,vg=ray_intersections(g[ring])
        if not np.all(ca==1) or not np.all(cg==1):raise ValueError('non_single_valued_boundary')
        result[key]=float(np.rad2deg(np.mean(np.abs(va-vg))))
    return result

def compare_metrics(a,g,scales,own=None,refown=None):
    out=area_metrics(a,g);own=own or own_metrics(a);refown=refown or own_metrics(g);out.update(own)
    out.update(boundary_metrics(a,g));out['T']=sym_distance(a['top3d'],g['top3d']);out['F']=sym_distance(a['bottom3d'],g['bottom3d'])
    ha,hg=own['height_mean_h'],refown['height_mean_h'];out['height_mean_signed_h']=ha-hg
    out['height_mean_relative_error']=abs(ha-hg)/hg
    vi=out['intersection_area_h2']*min(ha,hg)
    out['conditional_volume_iou']=vi/(out['area_h2']*ha+out['reference_area_h2']*hg-vi)
    out['direction_to_reference_rms_deg']=direction_residual(a,direction_axis(g))
    out['LC']=1-out['iou']+.5*out['C']
    out['LCT']=out['LC']+.3*scales['L']*out['T']/scales['T']
    out['LCG']=out['LC']+.3*scales['L']*(out['dir']/scales['dir']+out['flat']/scales['flat'])/2
    return out

def to_number(x):return None if x is None or x in ['', 'None','nan','NaN'] else float(x)

def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def clean(o):
    if isinstance(o,dict):return {str(k):clean(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)):return [clean(v) for v in o]
    if isinstance(o,np.generic):return o.item()
    return o

def write_json(path,obj):path.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    source=args.source.resolve();out=args.out.resolve()
    if out==source or source in out.parents:raise ValueError('Outputs must be outside source package')
    out.mkdir(parents=True,exist_ok=True)
    geom=json.loads((source/'inputs/frozen_geometry.json').read_text());ratings=json.loads((source/'inputs/review36_user_20261008.json').read_text())
    ratings={r['recordId']:r for r in ratings['ratings']}
    raw={(r['id'],r['reference_version'],r['reference_id']):r for r in csv.DictReader((source/'inputs/selected48_raw_metrics.csv').open(encoding='utf-8-sig'))}
    mainrows={r['record_id']:r for r in csv.DictReader((source/'data/unified36_existing_metrics.csv').open(encoding='utf-8-sig'))}
    fields=[r['field'] for r in csv.DictReader((source/'data/metric_dictionary.csv').open(encoding='utf-8-sig'))]
    raw_map={'iou':'iou','C':'centroid_distance_normalized','U':'top_mae_deg','B':'bottom_mae_deg','T':'top3d_symmetric_mean_h','F':'floor3d_symmetric_mean_h','dir':'direction_rms_deg','flat':'flat_top_angular_rms_deg','omission':'omission_ref','extension':'extension_ref'}
    comparisons=[];recomputed=[];statuses=[];algebra=[];sensitivity=[];common=[];projection=[]
    all_records=[r for im in geom['images'] for r in im['annotations']+im['groundtruths']]
    cache={r['id']:own_metrics(r) for r in all_records}
    for im in geom['images']:
        gt={r['version']:r for r in im['groundtruths']}
        for record in im['annotations']+im['groundtruths']:
            statuses.append(dict(image_code=im['code'],record_id=record['id'],review_id=record.get('reviewId'),version=record.get('version'),**ring_status(record),source_longitude_status=record['longitudeStatus']))
            points=np.asarray(record['points']);top=points[::2];bottom=points[1::2]
            # Frozen points already embody original stored common-x preprocessing.
            phi_b=(.5-bottom[:,1]/512)*np.pi;theta_b=bottom[:,0]/1024*2*np.pi
            rr=-1/np.tan(phi_b);pb=np.column_stack([-rr*np.sin(theta_b),-np.ones(len(rr)),rr*np.cos(theta_b)])
            phi_t=(.5-top[:,1]/512)*np.pi;theta_t=top[:,0]/1024*2*np.pi
            pt=np.column_stack([-rr*np.sin(theta_t),rr*np.tan(phi_t),rr*np.cos(theta_t)])
            projection.append(dict(record_id=record['id'],review_id=record.get('reviewId'),max_abs_bottom_coordinate_error=float(np.max(np.abs(pb-np.asarray(record['bottom3d'])))),max_abs_top_coordinate_error=float(np.max(np.abs(pt-np.asarray(record['top3d']))))))
        for a in im['annotations']:
            h=ratings[a['id']];assert mainrows[a['id']]['reference_version']==h['referenceVersion']
            for version,source_metrics in a['metricsByReference'].items():
                g=gt[version];assert g['id']==source_metrics['referenceId'];rawrow=raw[(a['id'],version,g['id'])]
                m=compare_metrics(a,g,geom['scales'],cache[a['id']],cache[g['id']])
                metadata=dict(review_id=a['reviewId'],record_id=a['id'],image_code=im['code'],reference_version=version,reference_id=g['id'],rating_reference=(version==h['referenceVersion']))
                recomputed.append(dict(**metadata,**m))
                for k in fields:
                    original=source_metrics['metrics'].get(k,to_number(rawrow.get(k)))
                    new=m[k]
                    err=abs(original-new) if original is not None and new is not None else None
                    passed=(original is None and new is None) or (err is not None and math.isclose(original,new,rel_tol=1e-8,abs_tol=1e-8))
                    comparisons.append(dict(**metadata,metric=k,frozen_value=original,recomputed_value=new,absolute_error=err,passed=passed,
                        provenance='independent_from_frozen_vertices; formulas reconstructed from dictionary and raw output'))
                for k,rawk in raw_map.items():
                    x=to_number(rawrow[rawk]);y=source_metrics['metrics'][k]
                    common.append(dict(**metadata,metric=k,raw_value=x,frozen_value=y,passed=(x is None and y is None) or (x is not None and y is not None and math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-12))))
                om,ex=m['omission'],m['extension'];ha=m['height_mean_h'];hg=ha-m['height_mean_signed_h'];z=ha/hg
                volume_formula=(1-om)*min(z,1)/((1-om+ex)*z+1-(1-om)*min(z,1))
                algebra.append(dict(**metadata,iou_identity_error=abs(m['iou']-(1-om)/(1+ex)),area_ratio_identity_error=abs(m['area_h2']/m['reference_area_h2']-(1-om+ex)),conditional_volume_identity_error=abs(m['conditional_volume_iou']-volume_formula),
                    height_relative_identity_error=abs(m['height_mean_relative_error']-abs(m['height_mean_signed_h'])/hg),internal_relative_identity_error=abs(m['height_internal_relative_rms']-m['height_internal_rms_h']/ha)))
                if metadata['rating_reference']:
                    # Parametric measurement sensitivity, not actual error distribution or quality penalty.
                    radius=np.linalg.norm(np.asarray(a['bottom3d'])[:,[0,2]],axis=1)
                    j=int(np.argmax(radius));theta=math.atan2(1,radius[j]);dtheta=math.pi/512
                    for delta_px in [-1,1]:
                        angle=theta+delta_px*dtheta
                        rnew=1/math.tan(angle)
                        sensitivity.append(dict(**metadata,pair_index_zero_based=j,canonical_lower_y_px=float(256+theta*512/math.pi),horizon_margin_deg=math.degrees(theta),radius_h=float(radius[j]),delta_canonical_pixel=delta_px,depth_change_h=float(rnew-radius[j]),linear_prediction_h=float(-delta_px*(1+radius[j]**2)*math.pi/512),
                            interpretation='hypothetical one-pixel bottom perturbation at farthest vertex; inputs unchanged; not measured annotator noise'))
    write_csv(out/'independent_metric_comparisons_48x21.csv',comparisons);write_csv(out/'recomputed_reference_rows48.csv',recomputed)
    write_csv(out/'common480_join_checks.csv',common);write_csv(out/'ring_single_value_audit44.csv',statuses);write_csv(out/'algebraic_redundancy_checks48.csv',algebra)
    write_csv(out/'one_pixel_depth_sensitivity72.csv',sensitivity);write_csv(out/'projection_checks44.csv',projection)
    summary=[]
    for key in fields:
        rs=[r for r in comparisons if r['metric']==key];errors=[r['absolute_error'] for r in rs if r['absolute_error'] is not None]
        summary.append(dict(metric=key,n_rows=len(rs),n_numeric=len(errors),n_both_missing=sum(r['frozen_value'] is None and r['recomputed_value'] is None for r in rs),max_absolute_error=max(errors) if errors else None,n_failed=sum(not r['passed'] for r in rs)))
    write_csv(out/'metric_recomputation_summary.csv',summary)
    checks=dict(source=str(source),dataset_fingerprint=geom['datasetFingerprintSha256'],python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),
        records36=len(mainrows),reference_rows48=len(recomputed),independent_metric_cells=len(comparisons),numeric_cells=sum(r['absolute_error'] is not None for r in comparisons),
        independent_metric_failed=sum(not r['passed'] for r in comparisons),common_join_cells=len(common),common_join_numeric_cells=sum(r['raw_value'] is not None for r in common),common_join_null_cells=sum(r['raw_value'] is None for r in common),common_join_failures=sum(not r['passed'] for r in common),
        all_main_records_included=set(mainrows)=={r['record_id'] for r in recomputed if r['rating_reference']},
        source_gt_and_ratings_mutated=False,no_weight_fitting=True,
        projection_max_coordinate_error=max(max(r['max_abs_bottom_coordinate_error'],r['max_abs_top_coordinate_error']) for r in projection),
        interpretation='Numerical reproduction of frozen conditional geometry; not validation of scene truth or unified human-quality labels.')
    write_json(out/'verification_summary.json',checks)
    print(json.dumps(clean(checks),ensure_ascii=False))

if __name__=='__main__':main()
