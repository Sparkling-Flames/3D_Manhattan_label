"""Independent moment integration and between-event curvature audit for route B."""
from pathlib import Path
import sys,json,os
import numpy as np
from shapely.geometry import Polygon,Point
ROOT=Path('/workspace/scratch/81fa50cc64f5');STUDY=ROOT/'new_pro_return/panorama_quality_three_routes_20261016';OUT=Path(os.environ.get('GQS_TURNING_OUT',str(ROOT/'new_pro_audit/turning_continuous')));OUT.mkdir(exist_ok=False,parents=True)
sys.path.insert(0,str(STUDY/'src'))
from geomscore import turning_distance

def representation(p):
    p=np.asarray(p,float)
    if Polygon(p).exterior.is_ccw is False:p=p[::-1]
    e=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(e,axis=1)
    # Independent unwrapping from edge bearings, adjusted through each principal turn.
    bearings=np.arctan2(e[:,1],e[:,0]);angles=[float(bearings[0])]
    for prev,next0 in zip(e,e[1:]):angles.append(angles[-1]+float(np.arctan2(np.cross(prev,next0),prev@next0)))
    return np.r_[0.,np.cumsum(length)/sum(length)],np.array(angles)

def moments(A,B,shift):
    ca,va=A;cb,vb=B
    cuts=sorted(set([0.,1.,*ca[1:-1].tolist(),*np.mod(cb[:-1]-shift,1).tolist()]))
    first=second=0.
    for lo,hi in zip(cuts[:-1],cuts[1:]):
        if hi<=lo:continue
        x=(hi+lo)/2
        ia=min(max(int(np.searchsorted(ca,x,side='right')-1),0),len(va)-1)
        y=x+shift;period=np.floor(y);yy=y-period
        ib=min(max(int(np.searchsorted(cb,yy,side='right')-1),0),len(vb)-1)
        delta=va[ia]-vb[ib]-2*np.pi*period
        first+=(hi-lo)*delta;second+=(hi-lo)*delta*delta
    return first,second,max(0.,second-first*first)

rng=np.random.default_rng(2026101603);rows=[];pairs=[]
for k in range(32):
    shapes=[]
    for j in range(2):
        n=int(rng.integers(4,15));phase=rng.uniform(0,2*np.pi);theta=phase+np.arange(n)*2*np.pi/n+rng.uniform(-.1,.1,n)
        radius=rng.uniform(.7,3.,n);p=np.column_stack([np.cos(theta)*radius,np.sin(theta)*radius])
        assert Polygon(p).is_valid and Polygon(p).contains(Point(0,0));shapes.append(p)
    pa,pb=shapes;A=representation(pa);B=representation(pb)
    events=np.unique(np.r_[0.,np.mod(B[0][:-1,None]-A[0][None,:-1],1).ravel(),1.])
    vals=[moments(A,B,t) for t in events]
    indep=min(x[2] for x in vals);given=turning_distance(pa,pb)['distance_deg']
    # Every open event interval: check affine raw moments and concavity of variance.
    max_raw_nonaffine=max_mean_nonaffine=max_interior_gain=0.
    for idx,(lo,hi) in enumerate(zip(events[:-1],events[1:])):
        if hi-lo<1e-12:continue
        f0,s0,v0=vals[idx];f1,s1,v1=vals[idx+1]
        for frac in [.25,.5,.75]:
            f,s,v=moments(A,B,lo+frac*(hi-lo))
            max_raw_nonaffine=max(max_raw_nonaffine,abs(s-((1-frac)*s0+frac*s1)))
            max_mean_nonaffine=max(max_mean_nonaffine,abs(f-((1-frac)*f0+frac*f1)))
            max_interior_gain=max(max_interior_gain,min(v0,v1)-v)
    grid=min(moments(A,B,float(t))[2] for t in np.linspace(0,1,1001))
    rows.append(dict(pair=k,nA=len(pa),nR=len(pb),events=len(events),given_deg=given,independent_event_deg=float(np.degrees(np.sqrt(indep))),
                     dense_grid_upper_deg=float(np.degrees(np.sqrt(grid))),max_raw_second_moment_nonaffine=max_raw_nonaffine,max_mean_nonaffine=max_mean_nonaffine,max_interior_gain=max_interior_gain))
    pairs.append({'answer':pa.tolist(),'reference':pb.tolist()})
    print('PAIR',k,rows[-1],flush=True)
summary=dict(pairs=len(rows),seed=2026101603,max_event_distance_delta_deg=max(abs(r['given_deg']-r['independent_event_deg']) for r in rows),
             max_raw_second_moment_nonaffine=max(r['max_raw_second_moment_nonaffine'] for r in rows),max_mean_nonaffine=max(r['max_mean_nonaffine'] for r in rows),max_interior_gain=max(r['max_interior_gain'] for r in rows),
             min_dense_minus_events_deg=min(r['dense_grid_upper_deg']-r['independent_event_deg'] for r in rows),
             conclusion='No counterexample found. For closed CCW simple rings, first moment is affine with slope -2pi; raw second moment is affine between vertex-alignment events. Centered loss is concave quadratic, so continuous interval minima occur at endpoints. This supports the implementation event candidate set; it is not a claim of human validity.')
(OUT/'pairs.json').write_text(json.dumps(pairs));(OUT/'checks.json').write_text(json.dumps(rows,indent=2));(OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
