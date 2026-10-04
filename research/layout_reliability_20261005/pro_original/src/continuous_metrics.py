"""Fixed-longitude, event and rational-height diagnostics.
Uses source ring domain as supplied. No GT in structural/approximation routines.
Root calculations and scipy quadrature are floating-point, not interval proofs.
"""
from __future__ import annotations
import math
import numpy as np
from numpy.polynomial import polynomial as P
from scipy.integrate import quad
from arc_consensus import Ring, TAU, W, H, EPS, unique_angles, equal_coeff


def linear_roots(c,lo,hi):
    c=np.asarray(c,float)
    if np.linalg.norm(c)<1e-12:return []
    r=math.atan2(-c[1],c[0])%np.pi
    return [v for k in range(-1,4) if lo+1e-12 < (v:=r+k*np.pi) < hi-1e-12]


def poly_theta_roots(p,lo,hi):
    p=np.asarray(p,float)
    scale=np.max(abs(p)) if len(p) else 0.
    if scale<1e-14:return []
    p=p/scale
    while len(p)>1 and abs(p[-1])<1e-12:p=p[:-1]
    out=[]
    for t in P.polyroots(p):
        if abs(t.imag)<1e-8*(1+abs(t.real)):
            a=math.atan(float(t.real))%np.pi
            out.extend(v for k in range(-1,4) if lo+1e-12<(v:=a+k*np.pi)<hi-1e-12)
    return out


def partitions(rings):
    cuts=unique_angles([0.,TAU]+[v for r in rings for p in r.pieces for v in (p.lo,p.hi)])
    for lo,hi in zip(cuts[:-1],cuts[1:]):
        if hi-lo>EPS:yield lo,hi,[r.active((lo+hi)/2).coeff for r in rings]


def stationary_points(c,d,lo,hi):
    """Derivative of atan(c dot v)-atan(d dot v), via tan(theta/2)."""
    a,b=c;e,f=d
    F=np.array([b,2*a,-b]);G=np.array([f,2*e,-f]);Q=np.array([1.,0.,1.])
    Df=np.array([2*a,-4*b,-2*a]);Dg=np.array([2*e,-4*f,-2*e])
    num=P.polysub(P.polymul(Df,P.polyadd(P.polymul(Q,Q),P.polymul(G,G))),P.polymul(Dg,P.polyadd(P.polymul(Q,Q),P.polymul(F,F))))
    pts=[lo,hi]
    scale=max(1.,float(np.max(abs(num))))
    while len(num)>1 and abs(num[-1])<1e-13*scale:num=num[:-1]
    if np.max(abs(num))>1e-12:
        for r in P.polyroots(num):
            if abs(r.imag)<=1e-7*(1+abs(r.real)):
                a=float(2*np.arctan(r.real))%TAU
                pts.extend(v for k in range(-1,3) if lo<(v:=a+k*TAU)<hi)
    pts.extend(v for k in range(-1,3) if lo<(v:=np.pi+k*TAU)<hi)
    pts.extend(np.linspace(lo,hi,9))
    return np.array(pts)


def signed_extrema(c,d,lo,hi):
    u=stationary_points(c,d,lo,hi);v=np.c_[np.sin(u),np.cos(u)]
    y=-H/np.pi*(np.arctan(v@c)-np.arctan(v@d))
    i,j=int(np.argmin(y)),int(np.argmax(y))
    return float(y[i]),float(y[j]),float(u[i]),float(u[j])


def fixed_longitude(candidate,reference):
    a,b=Ring(candidate),Ring(reference);res={};ninterval=0
    totals=np.zeros((2,3));maxes=np.zeros(2);args=np.zeros(2);mins=np.zeros(2);positives=np.zeros(2);errors=np.zeros(2)
    for lo,hi,(ca,cb) in partitions([a,b]):
        ninterval+=1
        for s in (0,1):
            def fun(u):
                v=np.array([np.sin(u),np.cos(u)])
                return float(-H/np.pi*(np.arctan(ca[s]@v)-np.arctan(cb[s]@v)))
            cuts=[lo]+linear_roots(ca[s]-cb[s],lo,hi)+[hi];cuts.sort()
            for l,h in zip(cuts[:-1],cuts[1:]):
                val,err=quad(fun,l,h,epsabs=1e-9,epsrel=1e-10,limit=60)
                totals[s,0]+=abs(val);totals[s,1]+=val;errors[s]+=err
                if fun((l+h)/2)>1e-9:positives[s]+=h-l
            vmin,vmax,umin,umax=signed_extrema(ca[s],cb[s],lo,hi)
            if max(abs(vmin),abs(vmax))>maxes[s]:
                maxes[s]=max(abs(vmin),abs(vmax));args[s]=umin if abs(vmin)>abs(vmax) else umax
            mins[s]=min(mins[s],vmin)
    for s,k in enumerate(['top','bottom']):
        res[k+'_mean_abs_px']=totals[s,0]/TAU;res[k+'_mean_signed_px']=totals[s,1]/TAU
        res[k+'_max_abs_px']=maxes[s];res[k+'_max_at_x']=float(args[s]/TAU*W)%W
        res[k+'_positive_longitude_share']=positives[s]/TAU
        res[k+'_quadrature_error_estimate_px']=errors[s]/TAU
    res['intervals']=ninterval
    res['measurement']='uniform longitude; same-longitude vertical boundary discrepancy, not semantic matching'
    return res


def prod(c,d):return P.polymul(np.asarray(c)[::-1],np.asarray(d)[::-1])

def rational_extrema(n,d,lo,hi,fun):
    deriv=P.polysub(P.polymul(P.polyder(n),d),P.polymul(n,P.polyder(d)))
    u=[lo,hi]+poly_theta_roots(deriv,lo,hi)
    u.extend(v for k in range(-1,4) if lo<(v:=np.pi/2+k*np.pi)<hi)
    u.extend(np.linspace(lo,hi,7));u=np.array(u);v=np.c_[np.sin(u),np.cos(u)]
    vals=np.asarray(fun(v));i,j=int(np.argmin(vals)),int(np.argmax(vals))
    return float(vals[i]),float(vals[j]),float(u[i]),float(u[j])


def height_delta_extrema(c,d,lo,hi):
    # Hc-Hd = (-ct db + dt cb)/(cb db), camera-relative top Y.
    n=P.polysub(prod(d[0],c[1]),prod(c[0],d[1]));den=prod(c[1],d[1])
    return rational_extrema(n,den,lo,hi,lambda v:-(v@c[0])/(v@c[1])+(v@d[0])/(v@d[1]))


def depth_height_change(candidate,exact):
    a,b=Ring(candidate),Ring(exact);hmax=0.;harg=0.;rmax=0.;rarg=0.;hiint=0.;numerr=0.
    for lo,hi,(c,d) in partitions([a,b]):
        mn,mx,um,ux=height_delta_extrema(c,d,lo,hi)
        if max(abs(mn),abs(mx))>hmax:hmax=max(abs(mn),abs(mx));harg=um if abs(mn)>abs(mx) else ux
        us=np.array([lo,hi]);v=np.c_[np.sin(us),np.cos(us)]
        rr=abs((v@d[1])/(v@c[1])-1)
        if max(rr)>rmax:rmax=float(max(rr));rarg=float(us[np.argmax(rr)])
        def fun(u):
            v=np.array([np.sin(u),np.cos(u)])
            return abs(-(v@c[0])/(v@c[1])+(v@d[0])/(v@d[1]))
        val,e=quad(fun,lo,hi,epsabs=1e-10,epsrel=1e-9,limit=100);hiint+=val;numerr+=e
    return dict(height_max_change_h=hmax,height_max_at_x=float(harg/TAU*W)%W,height_mean_change_h=hiint/TAU,height_quad_error_h=numerr/TAU,radial_max_relative_change=rmax,radial_max_at_x=float(rarg/TAU*W)%W)


def height_envelope(records):
    rs=[Ring(r) for r in records];pieces=[]
    for lo,hi,cs in partitions(rs):
        cuts=[lo,hi]
        for i in range(len(cs)):
            for j in range(i):
                num=P.polysub(prod(cs[i][0],cs[j][1]),prod(cs[j][0],cs[i][1]))
                cuts+=poly_theta_roots(num,lo,hi)
        cuts=unique_angles(cuts)
        for l,h in zip(cuts[:-1],cuts[1:]):
            v=np.array([np.sin((l+h)/2),np.cos((l+h)/2)]);heights=np.array([-c[0]@v/(c[1]@v) for c in cs]);mi,ma=int(np.argmin(heights)),int(np.argmax(heights))
            if pieces and abs(pieces[-1]['hi']-l)<EPS and equal_coeff(pieces[-1]['low'],cs[mi]) and equal_coeff(pieces[-1]['high'],cs[ma]):pieces[-1]['hi']=h
            else:pieces.append(dict(lo=l,hi=h,low=cs[mi],high=cs[ma],low_id=records[mi]['id'],high_id=records[ma]['id']))
    return pieces


def height_envelope_audit(candidate,env):
    r=Ring(candidate);worst=0.;arg=0.;bounds=None
    for p in r.pieces:
        for e in env:
            lo,hi=max(p.lo,e['lo']),min(p.hi,e['hi'])
            if hi-lo<EPS:continue
            mn,mx,umin,umax=height_delta_extrema(p.coeff,e['low'],lo,hi)
            if -mn>worst:worst=-mn;arg=umin;bounds=[e['low_id'],'below']
            mn,mx,umin,umax=height_delta_extrema(p.coeff,e['high'],lo,hi)
            if mx>worst:worst=mx;arg=umax;bounds=[e['high_id'],'above']
    return dict(height_envelope_violation_h=max(0.,worst),height_envelope_violation_at_x=float(arg/TAU*W)%W,height_envelope_source=bounds)


def witness_and_provenance(candidate,records,threshold):
    rs=[Ring(candidate)]+[Ring(r) for r in records];dist={};intervals=[];plain=[0.,0.];joint_exact=0.;n=len(records);lower=max(0,2*threshold-n)
    for lo,hi,cs in partitions(rs):
        cuts=[lo,hi]
        for c in cs[1:]:
            cuts+=linear_roots(c[0]-cs[0][0],lo,hi);cuts+=linear_roots(c[1]-cs[0][1],lo,hi)
        cuts=unique_angles(cuts)
        for l,h in zip(cuts[:-1],cuts[1:]):
            v=np.array([np.sin((l+h)/2),np.cos((l+h)/2)]);z=np.array([c@v for c in cs]);q=z[0]
            inds=np.flatnonzero((z[1:,0]>=q[0]-1e-10)&(z[1:,1]<=q[1]+1e-10));k=len(inds)
            dist[k]=dist.get(k,0.)+(h-l)/TAU
            donors=[]
            for s in (0,1):
                d=[records[i]['id'] for i,c in enumerate(cs[1:]) if equal_coeff(cs[0][s],c[s])];donors.append(d)
                if d:plain[s]+=(h-l)/TAU
            if set(donors[0])&set(donors[1]):joint_exact+=(h-l)/TAU
            if k<lower:intervals.append(dict(x_lo=l/TAU*W,x_hi=h/TAU*W,witness_count=k,witness_records=[records[i]['id'] for i in inds],top_source_curves=donors[0],bottom_source_curves=donors[1]))
    # Merge adjacent failure intervals; split at seam is retained.
    merged=[]
    for row in intervals:
        if merged and abs(merged[-1]['x_hi']-row['x_lo'])<1e-8 and merged[-1]['witness_records']==row['witness_records']:
            merged[-1]['x_hi']=row['x_hi']
        else:merged.append(row.copy())
    return dict(min_whole_column_witness_count=min(dist),theoretical_exact_lower_bound=lower,longitude_share_below_exact_lower_bound=sum(v for k,v in dist.items() if k<lower),longitude_share_zero_witness=dist.get(0,0.),witness_count_distribution=dist,top_exact_source_curve_longitude_share=plain[0],bottom_exact_source_curve_longitude_share=plain[1],same_person_exact_source_curve_share=joint_exact,below_bound_intervals=merged,interpretation='column set inclusion, not approval, probability or error rate; approximate curves get no inherited exact donors')
