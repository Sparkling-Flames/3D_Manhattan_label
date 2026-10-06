"""Ordered continuous Fréchet checks for spherical minor-arc paths.

Euclidean polygonal free-space reachability is evaluated numerically. Spherical
arcs are approximated by chords; a sagitta envelope separates approximation
uncertainty from the uncalibrated scientific threshold. No spatial shortcuts,
point deletions, best-fit rotations or per-case parameter fitting are used.
"""
from __future__ import annotations
import math
import numpy as np
try:
    from numba import njit
except ImportError:
    def njit(*args, **kwargs):
        return args[0] if args and callable(args[0]) else (lambda f:f)

@njit(cache=False)
def ball_interval(a,b,p,eps):
    # Parameters where a+t(b-a) lies in the closed Euclidean eps-ball of p.
    aa=0.;bb=0.;cc=-eps*eps
    for k in range(a.shape[0]):
        v=b[k]-a[k];u=a[k]-p[k]
        aa+=v*v;bb+=2*u*v;cc+=u*u
    tol=2e-14
    if aa<1e-28:
        if cc<=tol:return 0.,1.
        return 2.,-1.
    disc=bb*bb-4*aa*cc
    if disc < -tol*max(1.,bb*bb,abs(4*aa*cc)):return 2.,-1.
    disc=math.sqrt(max(0.,disc))
    lo=max(0.,(-bb-disc)/(2*aa));hi=min(1.,(-bb+disc)/(2*aa))
    if lo>hi+tol:return 2.,-1.
    return lo,hi

@njit(cache=False)
def continuous_decide(P,Q,eps):
    """Convex Euclidean free-space cells, arbitrary finite dimension."""
    n=P.shape[0]-1;m=Q.shape[0]-1
    if n<1 or m<1:return False
    tol=2e-12
    if np.sum((P[0]-Q[0])**2) > eps*eps+2e-14:return False
    if np.sum((P[-1]-Q[-1])**2) > eps*eps+2e-14:return False
    preP=np.ones(n+1,np.bool_);preQ=np.ones(m+1,np.bool_)
    for i in range(1,n+1):preP[i]=preP[i-1] and np.sum((P[i]-Q[0])**2)<=eps*eps+2e-14
    for j in range(1,m+1):preQ[j]=preQ[j-1] and np.sum((Q[j]-P[0])**2)<=eps*eps+2e-14
    prev=np.full(n,2.)
    right=2.
    for j in range(m):
        curr=np.full(n,2.);right=2.
        for i in range(n):
            bottom=prev[i] if j>0 else (0. if preP[i] else 2.)
            left=right if i>0 else (0. if preQ[j] else 2.)
            # Reachable boundary lower endpoints suffice: the reachable part
            # extends to the free interval's upper endpoint.
            if bottom>1.+tol and left>1.+tol:
                right=2.;continue
            rl,rh=ball_interval(Q[j],Q[j+1],P[i+1],eps)
            tl,th=ball_interval(P[i],P[i+1],Q[j+1],eps)
            right=2.
            if rl<=rh+tol:
                v=rl if bottom<=1.+tol else max(rl,left)
                if v<=rh+tol:right=v
            if tl<=th+tol:
                v=tl if left<=1.+tol else max(tl,bottom)
                if v<=th+tol:curr[i]=v
        prev=curr
    return prev[-1]<=1.+tol or right<=1.+tol

@njit(cache=False)
def discrete_distance(P,Q):
    n=P.shape[0];m=Q.shape[0];prev=np.full(m,np.inf)
    for i in range(n):
        cur=np.full(m,np.inf)
        for j in range(m):
            dij=math.sqrt(np.sum((P[i]-Q[j])**2))
            if i==0 and j==0:cur[j]=dij
            else:
                v=np.inf
                if i>0:v=min(v,prev[j])
                if j>0:v=min(v,cur[j-1])
                if i>0 and j>0:v=min(v,prev[j-1])
                cur[j]=max(dij,v)
        prev=cur
    return prev[-1]

def euclidean_distance(P,Q,iterations=28):
    P=np.ascontiguousarray(P,float);Q=np.ascontiguousarray(Q,float)
    lo=max(np.linalg.norm(P[0]-Q[0]),np.linalg.norm(P[-1]-Q[-1]))
    hi=float(discrete_distance(P,Q))
    if continuous_decide(P,Q,lo):return float(lo),float(lo)
    for _ in range(iterations):
        mid=(lo+hi)/2
        if continuous_decide(P,Q,mid):hi=mid
        else:lo=mid
    return float(lo),float(hi)

def rays(points):
    p=np.asarray(points,float);u=2*np.pi*(p[:,0]/1024-.5);v=np.pi*(.5-p[:,1]/512)
    return np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]

def angle(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float)
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b),axis=-1),np.sum(a*b,axis=-1)))

def arc_length(V):return float(np.sum(angle(V[:-1],V[1:])))

def polygonal_arc(V,step_deg):
    V=np.asarray(V,float);out=[V[0]];maxstep=0.
    for a,b in zip(V[:-1],V[1:]):
        th=math.atan2(float(np.linalg.norm(np.cross(a,b))),float(a@b))
        if th>=np.pi-1e-9:raise ValueError('antipodal_arc_undefined')
        if th<1e-12:out.append(b);continue
        count=max(1,int(np.ceil(np.degrees(th)/step_deg)));maxstep=max(maxstep,th/count)
        t=np.arange(1,count+1)/count
        vv=(np.sin((1-t)*th)[:,None]*a+np.sin(t*th)[:,None]*b)/np.sin(th)
        vv[-1]=b
        out.extend(vv)
    return np.ascontiguousarray(out,float),float(1-np.cos(maxstep/2))

def angular_from_chord(x):return float(np.degrees(2*np.arcsin(np.clip(x/2,0,1))))

def spherical_check(A,B,gate_deg,steps=(5.,2.,.5),cache=None,key=None):
    A=np.asarray(A,float);B=np.asarray(B,float)
    endpoint=float(max(angle(A[0],B[0]),angle(A[-1],B[-1])))
    if endpoint>gate_deg+1e-10:
        return {'status':'reject','reason':'endpoint_lower_bound','lower_deg':endpoint,'upper_deg':None}
    limit=2*np.sin(np.radians(gate_deg)/2)
    for step in steps:
        ka=(key[0],step) if key else None;kb=(key[1],step) if key else None
        if cache is not None and ka in cache:P,ea=cache[ka]
        else:
            P,ea=polygonal_arc(A,step)
            if cache is not None and ka is not None:cache[ka]=(P,ea)
        if cache is not None and kb in cache:Q,eb=cache[kb]
        else:
            Q,eb=polygonal_arc(B,step)
            if cache is not None and kb is not None:cache[kb]=(Q,eb)
        err=ea+eb
        if continuous_decide(P,Q,max(0.,limit-err-1e-10)):
            return {'status':'accept','reason':'sagitta_bounded_free_space','lower_deg':endpoint,
                    'upper_deg':float(gate_deg),'step_deg':step,'chord_error_bound':err,
                    'vertices':[len(P),len(Q)]}
        if not continuous_decide(P,Q,limit+err+1e-10):
            return {'status':'reject','reason':'sagitta_bounded_free_space','lower_deg':float(gate_deg),
                    'upper_deg':None,'step_deg':step,'chord_error_bound':err,'vertices':[len(P),len(Q)]}
    return {'status':'undetermined','reason':'numerical_threshold_boundary','lower_deg':endpoint,
            'upper_deg':None,'step_deg':step,'chord_error_bound':err,'vertices':[len(P),len(Q)]}

def spherical_distance_interval(A,B,step_deg=1.):
    P,ea=polygonal_arc(A,step_deg);Q,eb=polygonal_arc(B,step_deg)
    lo,hi=euclidean_distance(P,Q)
    return {'lower_deg':angular_from_chord(max(0.,lo-ea-eb)),
            'upper_deg':angular_from_chord(hi+ea+eb),'step_deg':step_deg,
            'chord_error_bound':ea+eb,'euclidean_interval':[lo,hi]}
