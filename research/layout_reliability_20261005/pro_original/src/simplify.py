"""Optional bounded-error compression of generated paired representation knots.
No input annotation is simplified. Every exact result remains the main evidence.
The finite search minimizes node count with the first exact knot retained.
It is not a globally optimal cyclic/semantic/Manhattan layout search.
The error is max vertical ERP deviation in pixels, checked at all analytic
stationary points (degree <= 6 polynomial), not just output sampling columns.
"""
from __future__ import annotations
import copy
import numpy as np
from numpy.polynomial import polynomial as P
from arc_consensus import W,H,TAU,Unsupported,Ring,footprint,paired_wall_proxy

def extrema_error(c,d,lo,hi):
    a,b=c; e,f=d
    F=np.array([b,2*a,-b]);G=np.array([f,2*e,-f]); Q=np.array([1.,0.,1.])
    Df=np.array([2*a,-4*b,-2*a]);Dg=np.array([2*e,-4*f,-2*e])
    numerator=P.polysub(P.polymul(Df,P.polyadd(P.polymul(Q,Q),P.polymul(G,G))),
                        P.polymul(Dg,P.polyadd(P.polymul(Q,Q),P.polymul(F,F))))
    points=[lo,hi]
    while len(numerator)>1 and abs(numerator[-1])<1e-13*max(1.,np.max(abs(numerator))): numerator=numerator[:-1]
    if np.max(abs(numerator))>1e-12:
        for root in P.polyroots(numerator):
            if abs(np.imag(root))<=1e-7*(1+abs(np.real(root))):
                u=float(2*np.arctan(np.real(root)))%TAU
                for k in (-1,0,1,2):
                    v=u+k*TAU
                    if lo<v<hi: points.append(v)
    for k in (-1,0,1,2):
        if lo<np.pi+k*TAU<hi: points.append(np.pi+k*TAU)
    # Additional sample check is a numerical safeguard, not the definition of the bound.
    points.extend(np.linspace(lo,hi,9).tolist())
    ss=np.c_[np.sin(points),np.cos(points)]
    return float(H/np.pi*np.max(abs(np.arctan(ss@c)-np.arctan(ss@d))))

def compression_costs(exact):
    q=np.array(exact['points']).reshape(-1,2,2);m=len(q)
    u=q[:,0,0]/W*TAU; u=np.r_[u,u[0]+TAU]
    r=Ring(exact); C=np.array([r.active(((a+b)/2)%TAU).coeff for a,b in zip(u[:-1],u[1:])])
    costs=np.full((m+1,m+1),np.inf)
    for i in range(m):
        costs[i,i+1]=0.
        for j in range(i+2,m+1):
            if u[j]-u[i]>=np.pi-1e-10: continue
            M=np.array([[np.sin(u[i]),np.cos(u[i])],[np.sin(u[j]),np.cos(u[j])]])
            z=np.tan(np.pi*(.5-q[[i%m,j%m],:,1]/H));new=np.linalg.solve(M,z).T
            costs[i,j]=max(extrema_error(C[k,side],new[side],u[k],u[k+1]) for k in range(i,j) for side in (0,1))
    return costs

def compress(exact,epsilon_px,costs=None):
    if not np.isfinite(epsilon_px) or epsilon_px<0: raise ValueError('nonnegative_finite_epsilon')
    q=np.array(exact['points']).reshape(-1,2,2);m=len(q)
    costs=compression_costs(exact) if costs is None else costs
    dp=np.full(m+1,np.inf);dp[0]=0.; prev=[None]*(m+1)
    for j in range(1,m+1):
        for i in range(j):
            if costs[i,j]<=epsilon_px+1e-9 and dp[i]+1<dp[j]: dp[j]=dp[i]+1;prev[j]=i
    if prev[m] is None: raise Unsupported('compression_path_unavailable')
    edges=[];j=m
    while j>0:
        i=prev[j];edges.append((i,j));j=i
    edges.reverse();keep=[i for i,j in edges]
    if len(keep)<3: raise Unsupported('compressed_polygon_too_small')
    out=dict(points=q[keep].reshape(-1,2).tolist(),status='approximate_complete_boundary',
        epsilon_px=epsilon_px,retained_exact_knot_indices=keep,
        maximum_vertical_curve_error_px=max(costs[i,j] for i,j in edges),
        pair_count=len(keep),ring_confirmed=False,source_record_ids=exact['source_record_ids'],source_workers=exact['source_workers'],
        approximation='minimum number of exact knots at fixed starting knot; max upper/lower vertical ERP error',
        exact_reference='exact all-person consensus retained separately; not ground truth',
        removed_exact_knot_indices=sorted(set(range(m))-set(keep)),
        source_annotations_modified=False,roof_interior='not_observed_not_assumed',
        connections=[dict(pair_indices=[k,(k+1)%len(keep)],exact_edge_range=[i,j],error_px=float(costs[i,j])) for k,(i,j) in enumerate(edges)])
    f,poly=footprint(out); out['footprint']=f.tolist()
    t,b=paired_wall_proxy(out);out.update(top_xyz=t.tolist(),bottom_xyz=b.tolist(),height_proxy=t[:,1].tolist())
    return out
