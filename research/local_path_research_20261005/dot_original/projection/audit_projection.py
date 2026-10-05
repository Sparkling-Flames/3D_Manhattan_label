#!/usr/bin/env python3
"""Read-only independent numeric audit. No imported package geometry routines.
Usage: PYTHONPATH=<dependency folders> python audit_projection.py --package ../oct5-path-intake/extracted/local_path_research_20261005 --upstream ../oct5-path-upstream --out results
"""
from pathlib import Path
import argparse, json, math, hashlib, shutil, platform
from collections import Counter
import numpy as np
from numpy.polynomial import Polynomial as Poly
from scipy.optimize import brentq
from shapely.geometry import Polygon

W=1024.; H=512.; TAU=2*math.pi; TOL=1e-10
IMAGES=['rPc6DW4iMge-06','uNb9QFRL6hY-67']
SELECTION={IMAGES[0]:['R00020','R01518','R01557'],IMAGES[1]:['R02928','R02929']}
TARGETS=[(IMAGES[0],'R01557',6),(IMAGES[1],'R02928',3)]
def read(p): return json.loads(Path(p).read_text())
def write(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cross(a,b): return a[0]*b[1]-a[1]*b[0]
def theta(x): return TAU*(np.asarray(x)/W-.5)
def erp(p):
    p=np.asarray(p,float)
    return np.stack((((np.arctan2(p[...,0],-p[...,2])/TAU+.5)%1)*W,H*(.5-np.arctan2(p[...,1],np.hypot(p[...,0],p[...,2]))/math.pi)),axis=-1)
def proxy(r):
    q=np.asarray(r['points'],float).reshape(-1,2,2)
    assert np.max(abs(q[:,0,0]-q[:,1,0]))<1e-12
    u=theta(q[:,1,0]); dep=1/np.tan(math.pi*(q[:,1,1]/H-.5))
    assert np.all(dep>0)
    bottom=np.c_[dep*np.sin(u),-np.ones(len(q)),-dep*np.cos(u)]
    top=bottom.copy(); top[:,1]=dep*np.tan(math.pi*(.5-q[:,0,1]/H))
    return top,bottom

def ray_hit(a,b,u):
    """Cramer/cross-product solution, independent of original np.linalg.solve."""
    a=np.asarray(a,float); b=np.asarray(b,float); e=b-a
    ah=a[[0,2]]; eh=e[[0,2]]; r=np.array([math.sin(u),-math.cos(u)])
    scale=max(1.,float(np.linalg.norm(a)),float(np.linalg.norm(b)))
    if np.linalg.norm(e)<=TOL*scale:return {'status':'degenerate'}
    det=cross(r,eh)
    if abs(det)<=TOL*max(1.,float(np.linalg.norm(eh))):
        if abs(cross(r,ah))>TOL*scale:return {'status':'not_covered'}
        ds=np.array([r@ah,r@b[[0,2]]])
        if max(np.linalg.norm(ah),np.linalg.norm(b[[0,2]]))<=TOL*scale:return {'status':'degenerate'}
        if max(ds)<=TOL*scale:return {'status':'not_covered'}
        return {'status':'non_unique'}
    dep=cross(ah,eh)/det; t=cross(ah,r)/det
    if dep<=TOL*scale or t < -TOL or t > 1+TOL:return {'status':'not_covered'}
    p=a+np.clip(t,0,1)*e
    return {'status':'ok','depth_h':float(dep),'t':float(t),'point':p.tolist(),'xy_px':erp(p).tolist(),'det':float(det)}

def point_seg(p,a,b):
    e=b-a; t=float(np.clip((p-a)@e/(e@e),0,1)); q=a+t*e
    return float(np.linalg.norm(p-q)),q,t

def domain(a,b):
    u=float(np.arctan2(a[0],-a[2])); v=float(np.arctan2(b[0],-b[2])); du=(v-u+math.pi)%TAU-math.pi
    assert abs(du)>1e-12 and abs(du)<math.pi-1e-12
    return sorted([u,u+du])
def coefficients(a,b):
    u=np.arctan2([a[0],b[0]],[-a[2],-b[2]])
    t=np.array([a[1]/np.hypot(a[0],a[2]),b[1]/np.hypot(b[0],b[2])])
    return np.linalg.solve(np.c_[np.sin(u),np.cos(u)],t)
def elev(c,u):return np.arctan(c[0]*np.sin(u)+c[1]*np.cos(u))
def diff(cnew,cold,u):return H/math.pi*(elev(cold,u)-elev(cnew,u))
def derivative(cnew,cold,u):
    def d(c):
        f=c[0]*np.sin(u)+c[1]*np.cos(u)
        return (c[0]*np.cos(u)-c[1]*np.sin(u))/(1+f*f)
    return H/math.pi*(d(cold)-d(cnew))
def extrema(cnew,cold,lo,hi):
    # t=tan(u/2); differentiate rational F(t)/D(t). Enumerate polynomial roots,
    # then independently locate derivative sign changes directly in angle space.
    D=Poly([1.,0.,1.]); fn=Poly([cnew[1],2*cnew[0],-cnew[1]]); fo=Poly([cold[1],2*cold[0],-cold[1]])
    A=(fo.deriv()*D-fo*D.deriv())*(D*D+fn*fn)-(fn.deriv()*D-fn*D.deriv())*(D*D+fo*fo)
    co=A.coef.copy(); cut=1e-13*max(1.,float(np.max(abs(co))))
    while len(co)>1 and abs(co[-1])<cut:co=co[:-1]
    roots=Poly(co).roots() if len(co)>1 else []
    cand=[lo,hi]; rr=[]
    for z in roots:
        if abs(np.imag(z))<1e-8:
            u=2*math.atan(float(np.real(z)))
            for k in range(-3,4):
                v=u+TAU*k
                if lo<v<hi:
                    cand.append(v);rr.append({'theta':v,'derivative_px_per_rad':float(derivative(cnew,cold,v))})
    for k in range(-3,4):
        u=math.pi+TAU*k
        if lo<u<hi:cand.append(u)
    grid=np.linspace(lo,hi,16385); yy=abs(diff(cnew,cold,grid)); dd=derivative(cnew,cold,grid)
    numeric_roots=[]
    for i in np.flatnonzero(dd[:-1]*dd[1:]<0):numeric_roots.append(float(brentq(lambda u:derivative(cnew,cold,u),grid[i],grid[i+1],xtol=1e-14)))
    candidate_values=[float(diff(cnew,cold,u)) for u in cand]; ix=int(np.argmax(abs(np.array(candidate_values))))
    independent_candidates=[lo,hi]+numeric_roots
    numeric=max(abs(float(diff(cnew,cold,u))) for u in independent_candidates)
    out={'lo_x_px':(lo/TAU+.5)*W,'hi_x_px':(hi/TAU+.5)*W,'max_abs_dy_px':abs(candidate_values[ix]),'signed_dy_px':candidate_values[ix],
         'witness_x_px':((cand[ix]/TAU+.5)%1)*W,'stationary_roots':rr,'polynomial_coefficients_ascending':co.tolist(),
         'dense_scan_max_px':float(yy.max()),'direct_derivative_brentq_max_px':numeric,'brentq_roots_theta':numeric_roots,
         'polynomial_vs_brentq_gap_px':abs(abs(candidate_values[ix])-numeric)}
    assert out['polynomial_vs_brentq_gap_px']<1e-7
    assert abs(out['max_abs_dy_px']-float(yy.max()))<.0001
    return out

def continuous(a,p,b):
    lo,hi=domain(a,b); cc=coefficients(a,b); pieces=[]
    for si,(x,y) in enumerate([(a,p),(p,b)]):
        l,h=domain(x,y); oc=coefficients(x,y)
        for sh in [-TAU,0.,TAU]:
            left=max(lo,l+sh); right=min(hi,h+sh)
            if right>left+1e-12:
                part=extrema(cc,oc,left,right); part['source_edge']=si
                # Verify positive finite coverage over each declared overlap.
                probes=np.linspace(left,right,1025)
                for u in probes:
                    assert ray_hit(a,b,float(u))['status']=='ok'
                    assert ray_hit(x,y,float(u))['status']=='ok'
                pieces.append(part)
    assert abs(sum(x['hi_x_px']-x['lo_x_px'] for x in pieces)-(hi-lo)/TAU*W)<1e-8
    return {'pieces':pieces,'new_chord_unique_coverage_unwrapped_x_px':[(lo/TAU+.5)*W,(hi/TAU+.5)*W],
            'old_path_unique_coverage_matches_chord_here':True,'max_abs_dy_px':max(x['max_abs_dy_px'] for x in pieces),
            'floating_numeric_check_not_interval_certificate':True}

def min_norm_segment(a,b):return point_seg(np.zeros(len(a)),a,b)[0]
def bounds(a,p,b,u):
    de,nearest,t=point_seg(p,a,b); hit=ray_hit(a,b,u); assert hit['status']=='ok'; h=np.array(hit['point'])
    e=b-a; eh=e[[0,2]]; r=np.array([math.sin(u),-math.cos(u)])
    mu=abs(cross(r,eh))/np.linalg.norm(eh); kap=np.linalg.norm(e)/np.linalg.norm(eh)
    local_3d=de*(1+kap/mu); minnorm=min(np.linalg.norm(p),np.linalg.norm(h))
    local_pixel=H/math.pi*2*math.asin(min(1.,local_3d/(2*minnorm)))
    lo,hi=domain(a,b)
    # A finite positive segment's incidence is n dot ray with fixed sign;
    # over this under-pi interval its minimum is at an endpoint.
    mus=[abs(cross(np.array([math.sin(v),-math.cos(v)]),eh))/np.linalg.norm(eh) for v in (lo,hi)]
    mumin=min(mus)
    minrho=min(min_norm_segment(x[[0,2]],y[[0,2]]) for x,y in [(a,p),(p,b),(a,b)])
    mind=min(min_norm_segment(x,y) for x,y in [(a,p),(p,b),(a,b)])
    uniform_3d=de*(1+kap/mumin)
    uniform_angle=H/math.pi*2*math.asin(min(1.,uniform_3d/(2*mind)))
    out={'path_to_chord_max_h':de,'nearest_chord_t':t,'nearest_chord_point_h':nearest.tolist(),
         'same_longitude_chord_t':hit['t'],'original_horizontal_depth_h':float(np.linalg.norm(p[[0,2]])),
         'chord_horizontal_depth_h':hit['depth_h'],'same_longitude_3d_error_h':float(np.linalg.norm(h-p)),
         'signed_dy_px':float(erp(h)[1]-erp(p)[1]),'incidence_mu':float(mu),'slope_factor_kappa':float(kap),
         'local_oblique_bound_h':float(local_3d),'local_top_or_bottom_pixel_bound_from_depth_px':float(local_pixel),
         'uniform_mu_min':float(mumin),'uniform_horizontal_depth_min_h':float(minrho),
         'uniform_camera_distance_min_h':float(mind),'uniform_oblique_bound_h':float(uniform_3d),
         'uniform_angle_to_pixel_bound_px':float(uniform_angle)}
    assert out['same_longitude_3d_error_h']<=local_3d+1e-9
    assert abs(out['signed_dy_px'])<=local_pixel+1e-9
    if a[1]==p[1]==b[1]==-1:
        out.update(radial_error_h=abs(hit['depth_h']-out['original_horizontal_depth_h']),radial_bound_h=float(de/mu),
            local_bottom_pixel_bound_px=float(H/math.pi*de/mu/(1+min(out['original_horizontal_depth_h'],hit['depth_h'])**2)),
            uniform_bottom_pixel_bound_px=float(H/math.pi*de/mumin/(1+minrho**2)))
        assert out['radial_error_h']<=out['radial_bound_h']+1e-9
        assert abs(out['signed_dy_px'])<=out['local_bottom_pixel_bound_px']+1e-9
    return out

def counterexample():
    rng=np.random.default_rng(20261005)
    for attempt in range(1,10001):
        span=rng.uniform(.2,2.8); ang=np.array([-span/2,rng.uniform(-.4,.4)*span,span/2])
        rho=np.exp(rng.uniform(math.log(.08),math.log(20),size=3))
        pts=np.c_[rho*np.sin(ang),-np.ones(3),-rho*np.cos(ang)]; a,p,b=pts
        cc=coefficients(a,b); at=abs(float(diff(cc,coefficients(a,p),ang[1])))
        scan=[]
        for x,y in [(a,p),(p,b)]:
            lo,hi=domain(x,y); co=coefficients(x,y); us=np.linspace(lo,hi,513)
            scan.extend(abs(diff(cc,co,us)).tolist())
        if max(scan)>at+.1:
            full=continuous(a,p,b); best=max(full['pieces'],key=lambda q:q['max_abs_dy_px']); u=float(theta(best['witness_x_px']))
            part=0 if u<ang[1] else 1
            orig=ray_hit(pts[part],pts[part+1],u); ch=ray_hit(a,b,u)
            direct=abs(erp(np.array(ch['point']))[1]-erp(np.array(orig['point']))[1])
            assert direct>at+.1 and abs(direct-best['max_abs_dy_px'])<1e-9
            bb=bounds(a,p,b,ang[1]); assert full['max_abs_dy_px']<=bb['uniform_bottom_pixel_bound_px']+1e-9
            return {'found':True,'attempt':attempt,'seed':20261005,'points_xyz_h':pts.tolist(),'angles_rad':ang.tolist(),
                    'radii_h':rho.tolist(),'removed_point_x_px':float((ang[1]/TAU+.5)*W),'removed_point_abs_dy_px':at,
                    'interior_witness_x_px':best['witness_x_px'],'interior_max_abs_dy_px':best['max_abs_dy_px'],
                    'strict_excess_px':best['max_abs_dy_px']-at,'direct_finite_ray_verified_abs_dy_px':float(direct),
                    'all_positive_finite_unique_on_local_domain':True,'continuous':full,'bounds':bb,
                    'conclusion':'Counterexample to a general maximum-at-deleted-point claim; not a real annotation and not an empirical frequency.'}
    return {'found':False,'seed':20261005,'attempts':10000,'conclusion':'Bounded search found no counterexample; not proof of universal claim.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--upstream',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=False); pkg=args.package; upstream=args.upstream
    initial={str(p):digest(p) for p in pkg.rglob('*') if p.is_file()};rs={};reconcile=[]
    for image in IMAGES:
        packed=read(pkg/'inputs'/f'{image}.json'); source=read(upstream/'research/layout_reliability_20261005/pro_original/inputs'/f'{image}.json')
        rs[image]=packed['records'];byid={r['id']:r for r in source['records']};assert len(byid)==len(source['records'])
        assert len(set(r['id'] for r in packed['records']))==len(packed['records'])
        checks=[]
        for record in rs[image]:
            ref=byid[record['id']]
            checks.append({'id':record['id'],'worker':record['worker'],'fields_compared':sorted(set(record)|set(ref)),
                           'missing_from_package':sorted(set(ref)-set(record)),'extra_in_package':sorted(set(record)-set(ref)),
                           'differing_fields':[k for k in set(record)&set(ref) if record[k]!=ref[k]]})
            assert record==ref
        assert packed==source
        reconcile.append({'image':image,'records':len(checks),'full_json_equal':True,'all_top_level_metadata_equal':True,'roster_order_equal':True,
             'all_record_fields_equal':True,'record_checks':checks,'ring_confirmed_counts':dict(Counter(str(r['ring_confirmed']) for r in rs[image]))})
    distinct=set(r['worker'] for z in rs.values() for r in z)
    write(out/'roster_reconciliation.json',{'records':sum(map(len,rs.values())),'distinct_workers':len(distinct),'images':reconcile})
    existing=read(pkg/'results/final/upstream_projection/results.json'); oldby={(r['image'],r['source_record'],r['removed_pair_index']):r for r in existing['candidates']}
    ops=[];counts={'top':Counter(),'bottom':Counter()};maxgap=0.;selected=[]
    for image,ids in SELECTION.items():
        for rid in ids:
            r=next(r for r in rs[image] if r['id']==rid);top,bottom=proxy(r);n=len(top);selected.append({'image':image,'record':rid,'worker':r['worker'],'pairs':n})
            for i in range(n):
                op={'image':image,'record':rid,'pair_index_0based':i,'source_pair_index':r['source_pair_indices'][i]};old=oldby[(image,rid,i)]
                for side,pts,j in [('top',top,0),('bottom',bottom,1)]:
                    h=ray_hit(pts[(i-1)%n],pts[(i+1)%n],float(theta(r['points'][2*i+j][0]))); counts[side][h['status']]+=1
                    assert h['status']==old[side]['status']
                    h['signed_dy_px']=h['xy_px'][1]-r['points'][2*i+j][1] if h['status']=='ok' else None
                    if h['status']=='ok':
                        gap=abs(h['signed_dy_px']-old[side]['signed_dy_px']);maxgap=max(maxgap,gap);assert gap<1e-9
                    else:assert old[side]['signed_dy_px'] is None
                    op[side]=h
                candidate=Polygon(np.delete(bottom[:,[0,2]],i,axis=0));op['deleted_polygon_valid']=bool(candidate.is_valid);ops.append(op)
    assert len(ops)==51
    write(out/'all_51_operations.json',{'selected_source_rings':selected,'operations':ops,'status_counts':{k:dict(v) for k,v in counts.items()},
              'max_abs_dy_disagreement_with_packaged_px':maxgap,'candidate_polygon_valid_counts':dict(Counter(str(o['deleted_polygon_valid']) for o in ops))})
    details=[];packreal=read(pkg/'results/final/real/real_diagnostics.json')
    for image,rid,source_idx in TARGETS:
        r=next(r for r in rs[image] if r['id']==rid);i=r['source_pair_indices'].index(source_idx);top,bottom=proxy(r);n=len(top);old=next(x for x in packreal if x['record']==rid)
        row={'image':image,'record':rid,'worker':r['worker'],'source_pair_index':source_idx,'stored_pair_index_0based':i,
             'stored_pair_ordinal_1based_for_reference_only':i+1,'semantic_display_corner_number':'not_defined_by_roster',
             'source_point_indices':r['source_point_indices'][2*i:2*i+2],'source_point_labels':r['source_point_labels'][2*i:2*i+2],
             'neighbor_source_pairs':[r['source_pair_indices'][(i-1)%n],r['source_pair_indices'][(i+1)%n]],'decision':'undetermined',
             'original_png_reviewed':False,'real_GT_read':False,'units':'h = common camera height, not metres'}
        for side,pts,j in [('top',top,0),('bottom',bottom,1)]:
            a,p,b=pts[(i-1)%n],pts[i],pts[(i+1)%n];bb=bounds(a,p,b,float(theta(r['points'][2*i+j][0]))); cc=continuous(a,p,b)
            assert abs(bb['path_to_chord_max_h']-old[side]['path_to_chord_max_h'])<1e-9
            assert abs(bb['same_longitude_3d_error_h']-old[side]['same_longitude_3d_error_h'])<1e-9
            assert abs(bb['signed_dy_px']-old[side]['same_longitude_dy_px'])<1e-9
            assert abs(cc['max_abs_dy_px']-old[side]['continuous_curve_difference']['max_abs_dy_px'])<1e-9
            assert cc['max_abs_dy_px']<=bb['uniform_angle_to_pixel_bound_px']+1e-9
            if side=='bottom':assert cc['max_abs_dy_px']<=bb['uniform_bottom_pixel_bound_px']+1e-9
            row[side]={'local_xyz_h':[a.tolist(),p.tolist(),b.tolist()],**bb,'continuous':cc}
        P=Polygon(bottom[:,[0,2]]);Q=Polygon(np.delete(bottom,i,axis=0)[:,[0,2]])
        row.update(candidate_polygon_valid=bool(Q.is_valid),area_lost_vs_source_h2=float(P.difference(Q).area),area_added_vs_source_h2=float(Q.difference(P).area));details.append(row)
    write(out/'two_real_cases.json',details)
    control=counterexample();write(out/'interior_maximum_control.json',control)
    assert {str(p):digest(p) for p in pkg.rglob('*') if p.is_file()}==initial
    write(out/'summary.json',{'records':39,'distinct_workers':len(distinct),'operations':len(ops),'source_rings':len(selected),'status_counts':{k:dict(v) for k,v in counts.items()},
            'max_operation_signed_dy_gap_px':maxgap,'source_package_files_unchanged':True,'counterexample_found':control['found'],
            'real_cases_remain_undetermined':True,'original_png_reviewed':False,'real_GT_read':False,'python':platform.python_version()})
    print(json.dumps(read(out/'summary.json'),ensure_ascii=False,indent=2))
    print(json.dumps({'counterexample':{k:control[k] for k in ['found','attempt','removed_point_abs_dy_px','interior_max_abs_dy_px','strict_excess_px']}},ensure_ascii=False))
if __name__=='__main__':main()
