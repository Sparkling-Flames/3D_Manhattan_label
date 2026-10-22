#!/usr/bin/env python3
"""Independent synthetic diagnostic, not the repository quality algorithm.
All scores are explicitly toy I,D ablations. No manual data or GT is modified.
Reference-turn comparisons require caller-verified, identical vertex correspondence.
"""
from __future__ import annotations
from pathlib import Path
import argparse, csv, json, math, statistics, unittest
Point=tuple[float,float]
EPS=1e-10

def cross(a:Point,b:Point)->float:return a[0]*b[1]-a[1]*b[0]
def sub(a:Point,b:Point)->Point:return (a[0]-b[0],a[1]-b[1])
def dot(a:Point,b:Point)->float:return a[0]*b[0]+a[1]*b[1]
def length(a:Point)->float:return math.hypot(*a)
def area_signed(p:list[Point])->float:return .5*sum(cross(a,b) for a,b in zip(p,p[1:]+p[:1]))
def area(p:list[Point])->float:return abs(area_signed(p)) if len(p)>=3 else 0.
def ccw(p:list[Point])->list[Point]:return p[:] if area_signed(p)>0 else p[:1]+p[:0:-1]
def simplify_collinear(p:list[Point],tol:float=1e-10)->list[Point]:
    p=p[:]
    changed=True
    while changed and len(p)>3:
        changed=False
        for i in range(len(p)):
            u=sub(p[i],p[i-1]);v=sub(p[(i+1)%len(p)],p[i])
            if length(u)<tol or (abs(cross(u,v))<=tol*max(1.,length(u)*length(v)) and dot(u,v)>0):
                p.pop(i);changed=True;break
    return p

def convex_clip(subject:list[Point],clip:list[Point])->list[Point]:
    """Sutherland-Hodgman; the clip polygon must be convex and CCW."""
    clip=ccw(clip);out=subject[:]
    for a,b in zip(clip,clip[1:]+clip[:1]):
        inp=out;out=[]
        if not inp:break
        def inside(p):return cross(sub(b,a),sub(p,a))>=-EPS
        def intersection(p,q):
            r=sub(q,p);s=sub(b,a);den=cross(r,s)
            if abs(den)<EPS:return q
            t=cross(sub(a,p),s)/den
            return(p[0]+t*r[0],p[1]+t*r[1])
        prev=inp[-1]
        for cur in inp:
            ci,pi=inside(cur),inside(prev)
            if ci:
                if not pi:out.append(intersection(prev,cur))
                out.append(cur)
            elif pi:out.append(intersection(prev,cur))
            prev=cur
    return out

def iou_convex_reference(p:list[Point],ref:list[Point])->float:
    """Only the synthetic convex references in this study are accepted."""
    ref=ccw(ref)
    if any(cross(sub(ref[(i+1)%len(ref)],ref[i]),sub(ref[(i+2)%len(ref)],ref[(i+1)%len(ref)]))<-EPS for i in range(len(ref))):
        raise ValueError('Nonconvex reference is not supported by this diagnostic clipper')
    ap,ar=area(p),area(ref)
    if min(ap,ar)<=EPS:raise ValueError('Degenerate polygons are not evaluable')
    inter=area(convex_clip(p,ref));union=ap+ar-inter
    return max(0.,min(1.,inter/union))

def axial_delta(a:float,b:float,period:float=90.)->float:return abs((a-b+period/2)%period-period/2)
def edge_data(p:list[Point])->list[dict]:
    result=[]
    for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        e=sub(b,a);le=length(e)
        if le<=EPS:raise ValueError('Zero-length edge')
        result.append({'edge':i,'length':le,'azimuth_degrees':math.degrees(math.atan2(e[1],e[0]))%180})
    return result

def direction(p:list[Point],weighted:bool=True,axis:float|None=None)->dict:
    edges=edge_data(p);weights=[r['length'] if weighted else 1. for r in edges];total=sum(weights)
    candidates=[axis%90] if axis is not None else sorted(set([0.]+[(r['azimuth_degrees']+k)%90 for r in edges for k in [0.,45.]]))
    def loss(phi):return sum(w*axial_delta(r['azimuth_degrees'],phi) for w,r in zip(weights,edges))/total
    phi=min(candidates,key=lambda x:(loss(x),x));d=loss(phi)
    for r,w in zip(edges,weights):
        d0=axial_delta(r['azimuth_degrees'],phi,180);d1=axial_delta(r['azimuth_degrees'],phi+90,180)
        r.update(normalized_weight=w/total,residual_degrees=min(d0,d1),family='tie' if abs(d0-d1)<1e-8 else ('axis0' if d0<d1 else 'axis90'))
    return {'D':d,'axis_degrees_mod90':phi,'weighted':weighted,'edges':edges}

def turns(p:list[Point])->list[float]:
    return [math.degrees(math.atan2(cross(sub(p[i],p[i-1]),sub(p[(i+1)%len(p)],p[i])),dot(sub(p[i],p[i-1]),sub(p[(i+1)%len(p)],p[i])))) for i in range(len(p))]

def reference_turn_residual(p:list[Point],ref:list[Point],*,correspondence_verified:bool=False)->dict:
    if not correspondence_verified:raise ValueError('Do not infer cross-reference vertex correspondence from score')
    p=simplify_collinear(ccw(p));ref=simplify_collinear(ccw(ref))
    if len(p)!=len(ref):raise ValueError('Different nonredundant vertex counts: correspondence unresolved')
    residual=[axial_delta(a,b,360.) for a,b in zip(turns(p),turns(ref))]
    return {'mean':statistics.fmean(residual),'max':max(residual),'per_corner':residual}

def family_anchored_direction(p:list[Point],ref:list[Point],*,correspondence_verified:bool=False)->float:
    if not correspondence_verified:raise ValueError('Reference edge families must be verified independently of quality')
    p=simplify_collinear(ccw(p));ref=simplify_collinear(ccw(ref))
    if len(p)!=len(ref):raise ValueError('Unknown edge correspondence')
    a,b=edge_data(p),edge_data(ref)
    return sum(x['length']*axial_delta(x['azimuth_degrees'],y['azimuth_degrees'],180.) for x,y in zip(a,b))/sum(x['length'] for x in a)

def rhombus(theta:float)->list[Point]:
    if not 0<theta<=90:raise ValueError('theta must be in (0,90]')
    c,s=math.cos(math.radians(theta)),math.sin(math.radians(theta))
    return [(-.5-.5*c,-.5*s),(.5-.5*c,-.5*s),(.5+.5*c,.5*s),(-.5+.5*c,.5*s)]
def rhombus_iou_closed_form(theta:float)->float:
    c,s=math.cos(math.radians(theta)),math.sin(math.radians(theta))
    return s*(1-c/4)/(1+s*c/4)
def toy_q(iou:float,d:float,tau:float=8.)->float:
    if tau<=0:raise ValueError('tau must be positive')
    return 100*iou/(1+(d/tau)**2)
def rotated(p:list[Point],degrees:float)->list[Point]:
    c,s=math.cos(math.radians(degrees)),math.sin(math.radians(degrees))
    return [(c*x-s*y,s*x+c*y) for x,y in p]

def radial_distance(p:list[Point],phi:float)->float:
    v=(math.cos(phi),math.sin(phi));hits=[]
    for a,b in zip(p,p[1:]+p[:1]):
        e=sub(b,a);den=cross(v,e)
        if abs(den)<EPS:continue
        t=cross(a,e)/den;u=cross(a,v)/den
        if t>EPS and -EPS<=u<=1+EPS:hits.append(t)
    hits=sorted(hits);unique=[]
    for t in hits:
        if not unique or abs(t-unique[-1])>1e-7*max(1.,t):unique.append(t)
    if len(unique)!=1:raise ValueError('Not a unique visible floor boundary; no silent visibility/scope fallback')
    return unique[0]

def floor_y(radius:float,h:float=1.6,H:int=512)->float:
    if min(radius,h,H)<=0:raise ValueError('Positive radius, camera height, and image height are required')
    return H*(.5+math.atan(h/radius)/math.pi)
def bottom_move(p:list[Point],index:int,dy:float,h:float=1.6,H:int=512)->list[Point]:
    r=length(p[index]);y=floor_y(r,h,H)+dy;v=math.pi*(y/H-.5)
    if not 0<v<math.pi/2:raise ValueError('Bottom point reaches/crosses horizon or nadir; not evaluable')
    nr=h/math.tan(v);out=p[:];out[index]=(p[index][0]*nr/r,p[index][1]*nr/r);return out

def panorama_bottom_diagnostics(p:list[Point],ref:list[Point],samples:int=720,h:float=1.6,H:int=512)->dict:
    # Periodic ray representation avoids seam and vertex-count matching in star-visible controls.
    angles=set(2*math.pi*i/samples for i in range(samples))
    angles.update(math.atan2(y,x)%(2*math.pi) for x,y in p+ref)
    diffs=[abs(floor_y(radial_distance(p,a),h,H)-floor_y(radial_distance(ref,a),h,H)) for a in sorted(angles)]
    ds=sorted(diffs)
    return {'sampled_mean_abs_y_px':statistics.fmean(diffs),'sampled_p95_abs_y_px':ds[min(len(ds)-1,math.ceil(.95*len(ds))-1)],'sampled_max_abs_y_px':max(diffs),'rays':len(diffs),'scope':'single_visible_floor_boundary_only','score_component':False}

class MechanismTests(unittest.TestCase):
    def test_exact_rhombus_iou(self):
        for t in [1,5,15,30,45,60,75,89,90]:self.assertAlmostEqual(iou_convex_reference(rhombus(t),rhombus(90)),rhombus_iou_closed_form(t),places=10)
    def test_fixed_length(self):
        for t in [5,30,45,90]:
            for e in edge_data(rhombus(t)):self.assertAlmostEqual(e['length'],1.,places=12)
    def test_direction_alias(self):
        for t in range(1,91):self.assertAlmostEqual(direction(rhombus(t))['D'],.5*min(t,90-t),places=10)
    def test_axis_and_weights_not_necessary_for_alias(self):
        for t in [5,30,45,60,85]:
            a=direction(rhombus(t))['D']
            self.assertAlmostEqual(a,direction(rhombus(t),weighted=False)['D'],places=10)
            self.assertAlmostEqual(a,direction(rhombus(t),axis=0)['D'],places=10)
    def test_toy_reversal(self):
        self.assertLess(toy_q(rhombus_iou_closed_form(45),22.5),toy_q(rhombus_iou_closed_form(30),15.))
    def test_trusted_family_monotonicity(self):
        last=-1.
        for t in range(1,91):
            p=rhombus(t);d=family_anchored_direction(p,rhombus(90),correspondence_verified=True)
            self.assertAlmostEqual(d,(90-t)/2,places=10)
            q=toy_q(rhombus_iou_closed_form(t),d);self.assertGreaterEqual(q+1e-10,last);last=q
    def test_no_unverified_correspondence(self):
        with self.assertRaises(ValueError):reference_turn_residual(rhombus(30),rhombus(90))
    def test_collinear_direction_invariance(self):
        p=rhombus(35);a,b=p[1:3];q=p[:2]+[((a[0]+b[0])/2,(a[1]+b[1])/2)]+p[2:]
        self.assertAlmostEqual(direction(p)['D'],direction(q)['D'],places=10)
        self.assertAlmostEqual(reference_turn_residual(q,p,correspondence_verified=True)['max'],0.,places=10)
    def test_nonorthogonal_reference_identity(self):
        p=rhombus(30)
        self.assertGreater(direction(p)['D'],0.)
        self.assertEqual(reference_turn_residual(p,p,correspondence_verified=True)['max'],0.)
        self.assertEqual(family_anchored_direction(p,p,correspondence_verified=True),0.)
    def test_reflex_corner_identity(self):
        p=[(-2,-2),(2,-2),(2,0),(0,0),(0,2),(-2,2)]
        self.assertIn(-90.,turns(p))
        self.assertEqual(reference_turn_residual(p,p,correspondence_verified=True)['max'],0.)
    def test_global_rotation_tradeoff(self):
        ref=rhombus(90);p=rotated(ref,20)
        self.assertAlmostEqual(direction(p)['D'],0.,places=10)
        self.assertAlmostEqual(reference_turn_residual(p,ref,correspondence_verified=True)['max'],0.,places=10)
        self.assertAlmostEqual(family_anchored_direction(p,ref,correspondence_verified=True),20.,places=10)
    def test_seam_periodic_and_redundant_samples(self):
        p=[(-3,-1),(3,-1),(3,1),(-3,1)];q=p[:2]+[(3.,0.)]+p[2:]
        self.assertAlmostEqual(radial_distance(p,.2),radial_distance(p,.2+2*math.pi),places=10)
        self.assertAlmostEqual(panorama_bottom_diagnostics(q,p)['sampled_max_abs_y_px'],0.,places=10)
    def test_horizon_rejected(self):
        p=rhombus(90)
        with self.assertRaises(ValueError):bottom_move(p,0,-256.)
    def test_same_height_prism_iou_identity(self):
        # For common identical vertical intervals, the volume factor cancels exactly.
        p,ref=rhombus(30),rhombus(90);height=2.7
        vi=area(convex_clip(p,ref))*height;vu=(area(p)+area(ref))*height-vi
        self.assertAlmostEqual(vi/vu,iou_convex_reference(p,ref),places=10)

def dump_csv(path:Path,rows:list[dict]):
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def run(out:Path)->dict:
    out.mkdir(parents=True,exist_ok=True);ref=rhombus(90);rows=[];edge_rows=[]
    for theta in range(1,91):
        p=rhombus(theta);di=direction(p);iou=iou_convex_reference(p,ref)
        s=reference_turn_residual(p,ref,correspondence_verified=True)
        family=family_anchored_direction(p,ref,correspondence_verified=True)
        rows.append({'theta_degrees':theta,'floor_iou':iou,'closed_form_iou':rhombus_iou_closed_form(theta),'equal_height_prism_3d_iou_not_repository':iou,'D_common_weighted':di['D'],'D_common_unweighted':direction(p,False)['D'],'D_fixed_axis_free_family':direction(p,axis=0)['D'],'D_verified_reference_family':family,'turn_error_mean':s['mean'],'turn_error_max':s['max'],'toy_q_free_D_tau8':toy_q(iou,di['D']),'toy_q_trusted_family_tau8':toy_q(iou,family),'toy_q_max_D_turnhalf_tau8':toy_q(iou,max(di['D'],s['mean']/2))})
        for e in di['edges']:edge_rows.append({'control':'equal_side_rhombus','theta_degrees':theta,'common_axis':di['axis_degrees_mod90'],**e})
    dump_csv(out/'rhombus_per_case.csv',rows);dump_csv(out/'rhombus_per_edge.csv',edge_rows)
    strength=[]
    for tau in [4.,8.,12.,16.,20.,24.,32.,48.,64.,128.,1e9]:
        reversals=[]
        for a,b in zip(rows,rows[1:]):
            # Increasing theta improves IoU; a score decrease is a synthetic severity inversion.
            qa=toy_q(a['floor_iou'],a['D_common_weighted'],tau);qb=toy_q(b['floor_iou'],b['D_common_weighted'],tau)
            if qb<qa-1e-9:reversals.append((a['theta_degrees'],b['theta_degrees'],qa-qb))
        strength.append({'tau_degrees':tau,'adjacent_reversals_of_89':len(reversals),'max_reverse_score_change':max([x[2] for x in reversals],default=0.),'toy_q_45':toy_q(rows[44]['floor_iou'],22.5,tau),'toy_q_30':toy_q(rows[29]['floor_iou'],15.,tau),'not_a_working_parameter_recommendation':True})
    dump_csv(out/'toy_direction_strength_sweep.csv',strength)
    bottom=[];bottom_edges=[]
    for width in [2.,4.,8.,16.,32.]:
      for depth in [1.,2.,4.]:
        r=[(-width/2,-depth/2),(width/2,-depth/2),(width/2,depth/2),(-width/2,depth/2)]
        for dy in [-16.,-8.,-4.,0.,2.,4.,8.,16.,24.,32.]:
          ident=f'SYN_B_w{width:g}_d{depth:g}_dy{dy:g}'
          record={'id':ident,'width':width,'depth':depth,'bottom_dy_px':dy,'status':'pending','floor_iou':None,'D':None,'common_axis':None,'reference_turn_mean':None,'reference_turn_max':None,'toy_q_free_D_tau8':None,'toy_q_max_D_turnhalf_tau8':None,'sampled_mean_abs_y_px':None,'sampled_p95_abs_y_px':None,'sampled_max_abs_y_px':None,'moved_radial_ratio':None,'error':None}
          try:
            p=bottom_move(r,0,dy);di=direction(p);iou=iou_convex_reference(p,r);s=reference_turn_residual(p,r,correspondence_verified=True);twod=panorama_bottom_diagnostics(p,r,samples=360)
            record.update(status='computed_synthetic_only',floor_iou=iou,D=di['D'],common_axis=di['axis_degrees_mod90'],reference_turn_mean=s['mean'],reference_turn_max=s['max'],toy_q_free_D_tau8=toy_q(iou,di['D']),toy_q_max_D_turnhalf_tau8=toy_q(iou,max(di['D'],s['mean']/2)),moved_radial_ratio=length(p[0])/length(r[0]))
            record.update({k:twod[k] for k in ['sampled_mean_abs_y_px','sampled_p95_abs_y_px','sampled_max_abs_y_px']})
            for e in di['edges']:bottom_edges.append({'control_id':ident,**e})
          except Exception as e:record.update(status='not_evaluable',error=repr(e))
          bottom.append(record)
    dump_csv(out/'independent_bottom_controls.csv',bottom);dump_csv(out/'independent_bottom_per_edge.csv',bottom_edges)
    reverse=[]
    for width in [2.,4.,8.,16.,32.]:
      for depth in [1.,2.,4.]:
        group=sorted([r for r in bottom if r['width']==width and r['depth']==depth and r['bottom_dy_px']>=0 and r['status']=='computed_synthetic_only'],key=lambda r:r['bottom_dy_px'])
        for a,b in zip(group,group[1:]):
          if b['floor_iou']<a['floor_iou']-1e-9 and b['toy_q_free_D_tau8']>a['toy_q_free_D_tau8']+1e-9:
            reverse.append({'earlier':a['id'],'later':b['id'],'iou_delta':b['floor_iou']-a['floor_iou'],'D_delta':b['D']-a['D'],'toy_q_delta':b['toy_q_free_D_tau8']-a['toy_q_free_D_tau8'],'turn_augmented_toy_q_delta':b['toy_q_max_D_turnhalf_tau8']-a['toy_q_max_D_turnhalf_tau8']})
    (out/'independent_bottom_reversals.json').write_text(json.dumps(reverse,ensure_ascii=False,indent=2))
    special=[]
    for name,p,r in [('same_legal_nonorthogonal',rhombus(30),rhombus(30)),('rigid_square_rotation20',rotated(ref,20),ref),('same_concave_orthogonal',[(-2,-2),(2,-2),(2,0),(0,0),(0,2),(-2,2)],[(-2,-2),(2,-2),(2,0),(0,0),(0,2),(-2,2)])]:
        sd=reference_turn_residual(p,r,correspondence_verified=True)
        special.append({'id':name,'D_intrinsic':direction(p)['D'],'verified_turn_residual':sd,'verified_family_residual':family_anchored_direction(p,r,correspondence_verified=True),'scope':'synthetic_negative_control'})
    (out/'negative_controls.json').write_text(json.dumps(special,ensure_ascii=False,indent=2))
    a,b=rows[44],rows[29]
    tau_sq=(b['floor_iou']*22.5**2-a['floor_iou']*15.**2)/(a['floor_iou']-b['floor_iou'])
    summary={'status':'standalone_synthetic_computation_not_current_algorithm_calibration','counts':{'rhombus':len(rows),'independent_bottom':len(bottom),'independent_bottom_computed':sum(r['status']=='computed_synthetic_only' for r in bottom),'independent_bottom_not_evaluable':sum(r['status']=='not_evaluable' for r in bottom)},'rhombus_45':a,'rhombus_30':b,'toy_tau_needed_for_this_pair_only':math.sqrt(tau_sq),'independent_bottom_toy_reversals':reverse,'limitations':['No preparation-package control, real manual answer, or repository full Q is represented by these synthetic results.','The supplied fourth-order-tail numbers are NOT independently reproduced here; its source formula was not reviewed.','Trusted reference families and turns are not available automatically for real unequal-vertex layouts.','The sampled panoramic residual is a diagnostic, not an added main-score component.','Same-height prism IoU is an analytical synthetic comparison, not execution of the repository current 3D IoU.','No working parameters, normal-stage freeze, doorway tuning, height calibration, visual checks, or holdout claims.']}
    (out/'synthetic_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'synthetic_results');ap.add_argument('--test',action='store_true');args=ap.parse_args()
    if args.test:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MechanismTests))
        if not result.wasSuccessful():raise SystemExit(1)
    result=run(args.output)
    print(json.dumps({k:result[k] for k in ['status','counts','rhombus_45','rhombus_30','toy_tau_needed_for_this_pair_only']},ensure_ascii=False,indent=2))
