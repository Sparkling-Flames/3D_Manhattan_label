"""Independent re-projection and continuous local-curve checks; no semantic decision."""
from pathlib import Path
import sys,json,math,itertools
import numpy as np
from scipy.optimize import minimize_scalar
from shapely.geometry import Polygon
from finite_paths import directed_path_distance,dump,project
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'upstream_minimal'))
from tools.thesis_main.analysis.local_shortcut_projection_20261005 import segment_at_longitude
W=1024.;H=512.;TAU=2*np.pi

def proxy(record):
    p=np.array(record['points']).reshape(-1,2,2)
    theta=TAU*(p[:,1,0]/W-.5);bt=np.pi*(.5-p[:,1,1]/H);tt=np.pi*(.5-p[:,0,1]/H)
    rho=-1/np.tan(bt)
    bottom=np.c_[rho*np.sin(theta),-np.ones(len(rho)),-rho*np.cos(theta)]
    top=bottom.copy();top[:,1]=rho*np.tan(tt)
    return top,bottom

def point_segment(p,a,b):
    e=b-a;t=np.clip((p-a)@e/(e@e),0,1);q=a+t*e
    return float(np.linalg.norm(p-q)),q

def arc_coeff(a,b):
    normal=np.cross(a,b)
    if abs(normal[1])<1e-12:raise ValueError('radial_or_singular_segment')
    return np.array([-normal[0]/normal[1],normal[2]/normal[1]])

def arc_value(c,u):return H*(.5-np.arctan(c[0]*np.sin(u)+c[1]*np.cos(u))/np.pi)

def stationary(c1,c2,lo,hi):
    P=np.polynomial.polynomial
    d=np.array([1.,0.,1.]);d2=P.polymul(d,d)
    a,b=c1;c,e=c2
    p1=np.array([b,2*a,-b]);p2=np.array([e,2*c,-e]);q1=np.array([a,-2*b,-a]);q2=np.array([c,-2*e,-c])
    pol=P.polysub(P.polymul(q1,P.polyadd(d2,P.polymul(p2,p2))),P.polymul(q2,P.polyadd(d2,P.polymul(p1,p1))))
    while len(pol)>1 and abs(pol[-1])<1e-13*max(1,np.max(abs(pol))):pol=pol[:-1]
    roots=P.polyroots(pol) if len(pol)>1 else []
    vals=[lo,hi]
    for z in roots:
        if abs(z.imag)>1e-7:continue
        theta=2*np.arctan(z.real)
        for k in range(-3,4):
            v=theta+k*TAU
            if lo<v<hi:vals.append(float(v))
    for k in range(-3,4):
        v=np.pi+k*TAU
        if lo<v<hi:vals.append(float(v))
    return sorted(set(vals))

def interval(a,b):
    t=np.arctan2(a[0],-a[2]);u=np.arctan2(b[0],-b[2]);d=(u-t+np.pi)%TAU-np.pi
    return min(t,t+d),max(t,t+d)

def continuous_curve_difference(old,new):
    a,b=new;lo,hi=interval(a,b);cc=arc_coeff(a,b);pieces=[]
    for idx,(p,q) in enumerate(zip(old[:-1],old[1:])):
        ol,oh=interval(p,q);pc=arc_coeff(p,q)
        for shift in (-TAU,0.,TAU):
            l=max(lo,ol+shift);h=min(hi,oh+shift)
            if h<=l+1e-12:continue
            ts=stationary(cc,pc,l,h);vv=np.array([arc_value(cc,t)-arc_value(pc,t) for t in ts]);j=np.argmax(abs(vv));t=ts[j]
            grid=np.linspace(l,h,8193);ev=abs(arc_value(cc,grid)-arc_value(pc,grid));jj=int(np.argmax(ev))
            lower=grid[max(0,jj-1)];upper=grid[min(len(grid)-1,jj+1)]
            best=minimize_scalar(lambda u:-abs(arc_value(cc,u)-arc_value(pc,u)),bounds=(lower,upper),method='bounded',options={'xatol':1e-14})
            numeric=max(float(ev.max()),float(-best.fun))
            pieces.append({'source_edge':idx,'lo_x_px':(l/TAU+.5)*W,'hi_x_px':(h/TAU+.5)*W,
                'max_abs_dy_px':float(abs(vv[j])),'signed_dy_at_max_px':float(vv[j]),'witness_x_px':float((t/TAU+.5)%1*W),
                'stationary_candidates':len(ts),'independent_scan_local_opt_max_px':numeric,'crosscheck_difference_px':float(abs(abs(vv[j])-numeric))})
    return {'pieces':pieces,'max_abs_dy_px':max([p['max_abs_dy_px'] for p in pieces],default=None),
            'measurement':'continuous signed projection difference on overlapping declared local branches; no visibility choice',
            'certificate_kind':'floating polynomial stationary roots plus numeric scan/optimization check; not interval arithmetic'}

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);targets=[('rPc6DW4iMge-06','R01557',6),('uNb9QFRL6hY-67','R02928',3)];rr=[]
    for image,rid,source_index in targets:
        records=json.loads((ROOT/'inputs'/f'{image}.json').read_text())['records'];r=next(r for r in records if r['id']==rid)
        i=r['source_pair_indices'].index(source_index);n=len(r['points'])//2;prev=(i-1)%n;nxt=(i+1)%n;top,bottom=proxy(r)
        row={'image':image,'record':rid,'worker':r['worker'],'removed_source_pair':source_index,'removed_pair_index':i,'neighbor_source_pairs':[r['source_pair_indices'][prev],r['source_pair_indices'][nxt]],'removed_source_point_indices':r['source_point_indices'][2*i:2*i+2], 'decision':'undetermined','ring_confirmed_source':r['ring_confirmed'],'reads_GT':False}
        for side,pts,j in [('top',top,0),('bottom',bottom,1)]:
            a,p,b=pts[prev],pts[i],pts[nxt];delta,nearest=point_segment(p,a,b);x=r['points'][2*i+j][0]
            hit=segment_at_longitude(a,b,x);hit_point=np.array(hit['point_3d_h'])
            theta=TAU*(x/W-.5);ray=np.array([np.sin(theta),-np.cos(theta)]);eh=(b-a)[[0,2]];mu=abs(ray[0]*eh[1]-ray[1]*eh[0])/np.linalg.norm(eh)
            kappa=np.linalg.norm(b-a)/np.linalg.norm(eh);same=np.linalg.norm(p-hit_point)
            local={'path_to_chord_max_h':delta,'closest_chord_point_h':nearest.tolist(),'same_longitude_3d_error_h':float(same),
                   'same_longitude_dy_px':float(project(hit_point)[1]-r['points'][2*i+j][1]),'incidence_abs_sin':float(mu),'slope_length_factor':float(kappa),
                   'oblique_intersection_upper_h':float(delta*(1+kappa/mu)),
                   'continuous_curve_difference':continuous_curve_difference([a,p,b],[a,b])}
            if side=='bottom':
                rho=np.linalg.norm(p[[0,2]]);rhop=np.linalg.norm(hit_point[[0,2]])
                local['radial_error_h']=abs(rhop-rho);local['radial_error_upper_h']=delta/mu
                local['bottom_pixel_error_upper_at_this_longitude']=H/np.pi*delta/mu/(1+min(rho,rhop)**2)
            row[side]=local
        P=Polygon(bottom[:,[0,2]]);sub=np.delete(bottom,i,axis=0);Q=Polygon(sub[:,[0,2]])
        row['candidate_polygon_valid']=Q.is_valid;row['area_lost_vs_source_h2']=P.difference(Q).area if Q.is_valid else None;row['area_added_vs_source_h2']=Q.difference(P).area if Q.is_valid else None
        row['original_record']=r;rr.append(row)
    dump(out/'real_diagnostics.json',rr)
    for r in rr:
        print(r['record'],{s:{k:r[s][k] for k in ('path_to_chord_max_h','same_longitude_3d_error_h','same_longitude_dy_px','incidence_abs_sin')} for s in ('top','bottom')})
        print('max curves',{s:r[s]['continuous_curve_difference']['max_abs_dy_px'] for s in ('top','bottom')})
    return rr

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
