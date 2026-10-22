"""Read-only density-invariance experiments. All derivatives are non-voting copies."""
from pathlib import Path
import sys, math, copy, json, time
sys.dont_write_bytecode=True
import numpy as np
from scipy.linalg import null_space
from scipy.optimize import minimize
import argparse
ROOT=Path(__file__).resolve().parents[2]
_parser=argparse.ArgumentParser(add_help=False)
_parser.add_argument('--source',type=Path,default=ROOT/'unpacked/full/quality_deep_20261007')
_parser.add_argument('--expanded',type=Path,default=ROOT/'unpacked/expanded_input')
_parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
_args,_unknown=_parser.parse_known_args()
FULL=_args.source.resolve();EXPANDED=_args.expanded.resolve();OUT=_args.out.resolve()
OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(FULL/'src'),str(FULL/'vendor')]
import components as comp
import geometry as up
from arc_excerpt import Ring, paired_wall_proxy, footprint, project, pairs
D=180/np.pi

def record(top,floor,source,tag,meta=None):
    r=copy.deepcopy(source)
    r['points']=np.stack([project(top),project(floor)],axis=1).reshape(-1,2).tolist()
    r.update(derived_from=source['id'],operation=tag,not_independent_vote=True,independent=False,consensus_eligible=False,quality_candidate=False)
    # Keep original expression ID. Extra vertices are synthetic, never annotation IDs.
    for k in ['source_pair_indices','source_point_indices','source_point_labels']:
        
        expected=len(top)*(2 if k!='source_pair_indices' else 1)
        if len(r.get(k,[]))!=expected:r.pop(k,None)
    r['expression_id']=source.get('expression_id',source['id'])
    r['lineage']=meta or [{'original_pair':i,'t':0.} for i in range(len(top))]
    return r

def subdivision(r,mode,k):
    t,f=paired_wall_proxy(r);n=len(f)
    length=np.linalg.norm(np.roll(f,-1,axis=0)-f,axis=1)
    edge=int(np.argmax(length)) if 'long' in mode else int(np.argmin(length)) if 'short' in mode else 0
    T=[];F=[];meta=[];old=[]
    for i in range(n):
        old.append(len(T)); ts=[0.]
        if mode=='uniform':ts=np.arange(k)/k
        elif i==edge:
            if mode=='long_cluster':ts=np.r_[0.,.03+.12*np.arange(1,k)/k]
            else:ts=np.arange(k)/k
        for a in ts:
            T.append((1-a)*t[i]+a*t[(i+1)%n]);F.append((1-a)*f[i]+a*f[(i+1)%n]);meta.append({'original_pair':i,'next_pair':(i+1)%n,'t':float(a)})
    return record(np.array(T),np.array(F),r,f'exact_3d_subdivide_{mode}_{k}',meta),old

def prepare(r,frame=None):
    try:ans=up.analyze(comp.payload(r),compute_fit=False,coordinate_convention='continuous')
    except (ValueError,TypeError,KeyError,np.linalg.LinAlgError) as ex:return {'status':'blocked','reason':str(ex)}
    issues=[i for i in ans['raw']['issues'] if i!='vertical_pair_mismatch']
    if issues:return {'status':'blocked','reason':';'.join(issues)}
    floor=np.array(ans['raw']['floor']);top=np.array(ans['raw']['ceiling']);p=floor[:,[0,2]]
    frame=up.heading_frame(p) if frame is None else frame
    basis=np.array([[math.cos(frame),math.sin(frame)],[-math.sin(frame),math.cos(frame)]])
    local=p@basis.T;e=np.roll(local,-1,axis=0)-local;direction=np.argmax(abs(e),axis=1)
    residual=np.degrees(np.arctan2(np.min(abs(e),axis=1),np.max(abs(e),axis=1)))
    if np.any(residual>=40):return {'status':'blocked','reason':'ambiguous_axis_assignment','frame':frame,'direction':direction}
    return dict(status='ok',floor=floor,top=top,frame=frame,basis=basis,local=local,edges=e,direction=direction,pairs=ans['pairs'])

def fit_node(r,frame=None,starts=1):
    q=prepare(r,frame)
    if q['status']!='ok':return q
    local=q['local'];n=len(local);direction=q['direction'];basis=q['basis']
    constraints=np.zeros((n,2*n))
    for i,axis in enumerate(direction):
        constraints[i,2*i+1-axis]=1;constraints[i,2*((i+1)%n)+1-axis]=-1
    kernel=null_space(constraints);start=np.r_[kernel.T@local.ravel(),max(.05,float(np.median(q['top'][:,1])))]
    rays_top=q['top']/np.linalg.norm(q['top'],axis=1)[:,None];rays_floor=q['floor']/np.linalg.norm(q['floor'],axis=1)[:,None]
    signs=np.sign(q['edges'][np.arange(n),direction])
    def decode(v):
        c=(kernel@v[:-1]).reshape(n,2);world=c@basis
        return c,np.c_[world[:,0],np.full(n,-1.),world[:,1]],np.c_[world[:,0],np.full(n,v[-1]),world[:,1]]
    def errors(v):
        _,f,t=decode(v);return np.r_[up.angular_errors(t,rays_top),up.angular_errors(f,rays_floor)]
    def ordered(v):
        c,_,_=decode(v);return (np.roll(c,-1,axis=0)-c)[np.arange(n),direction]*signs-1e-6
    results=[]
    for scale in [1.,.8,1.25][:starts]:
        st=start.copy();st[:-1]*=scale;st[-1]*=scale
        sol=minimize(lambda v:float(np.mean(errors(v)**2)),st,method='SLSQP',bounds=[(None,None)]*(len(st)-1)+[(1e-5,None)],constraints=[{'type':'ineq','fun':ordered}],options={'ftol':1e-12,'maxiter':500})
        _,f,t=decode(sol.x);issues=up.geometry_issues(f[:,[0,2]])
        ok=sol.success and not issues and np.min(ordered(sol.x))>=-1e-7
        results.append(dict(status='ok' if ok else 'blocked',reason=';'.join(issues) if issues else '' if ok else 'optimizer_failed',solver=str(sol.message),iterations=sol.nit,objective=float(sol.fun),floor=f,top=t,x=sol.x))
    valid=[v for v in results if v['status']=='ok'];best=min(valid or results,key=lambda v:v['objective'])
    best.update(frame=q['frame'],direction=direction,starts=[dict(status=x['status'],objective=x['objective'],iterations=x['iterations']) for x in results])
    if best['status']=='ok':best['record']=record(best['top'],best['floor'],r,'equal_node_projection',r.get('lineage'))
    return best

def node_loss(r,candidate):
    t,f=paired_wall_proxy(r);ct,cf=paired_wall_proxy(candidate)
    return float(np.mean(np.r_[up.angular_errors(ct,t/np.linalg.norm(t,axis=1)[:,None]),up.angular_errors(cf,f/np.linalg.norm(f,axis=1)[:,None])]**2))

def boundary_loss(a,b,n=4096):
    u=(np.arange(n)+.5)*2*np.pi/n
    delta=(Ring(a).evaluate(u)-Ring(b).evaluate(u))*np.pi/512
    return float(np.mean(delta**2))

def compare_shapes(a,b):
    z=comp.compare(a,b,nlongitude=4096,ncurve=512)
    keep=['iou','centroid_distance_h','top_mae_deg','bottom_mae_deg','top3d_symmetric_mean_h','floor3d_symmetric_mean_h']
    return {k:z[k] for k in keep if k in z}

def save_json(name,obj):
    def default(x):
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,np.generic):return x.item()
        raise TypeError(type(x).__name__)
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=default))

def save_csv(name,rows):
    import csv
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader();wr.writerows(rows)

def fit_boundary(r,frame=None,nquad=4096,starts=1):
    """Equal-longitude L2 integral of top/bottom elevation. No GT is read.

    Consecutive same-axis edges share a supporting line, exactly as the original
    Manhattan constraints require. All original nodes are returned in the same
    order; their positions on the line retain original perimeter fractions.
    These fractions are a gauge for redundant collinear model coordinates, not
    deletion, a new annotation, or a semantic decision. True input bends and
    top-height variations remain in the observed continuous boundary objective.
    """
    q=prepare(r,frame)
    if q['status']!='ok':return q
    try:source_ring=Ring(r)
    except ValueError as ex:return dict(status='blocked',reason='boundary_domain:'+str(ex))
    local=q['local'];axis=q['direction'];n=len(local)
    corners=np.flatnonzero(axis!=np.roll(axis,1));m=len(corners)
    if m<4:return dict(status='blocked',reason='less_than_four_axis_runs')
    runaxis=axis[corners];support=[];node_run=np.empty(n,int);fraction=np.empty(n);runsigns=[]
    for j,a in enumerate(corners):
        b=int(corners[(j+1)%m]);ids=np.arange(a,b if b>a else b+n)%n
        lengths=np.linalg.norm(q['edges'][ids],axis=1);total=float(lengths.sum())
        signs=np.sign(q['edges'][ids,axis[ids]])
        if np.any(signs!=signs[0]):return dict(status='blocked',reason='axis_run_backtrack')
        runsigns.append(signs[0]);normal=1-runaxis[j]
        support.append(float(np.sum(lengths*(local[ids,normal]+local[(ids+1)%n,normal])/2)/total))
        node_run[ids]=j;fraction[ids]=np.r_[0,np.cumsum(lengths)[:-1]]/total
    support=np.array(support);runsigns=np.array(runsigns)
    orientation=np.sign(sum(up.cross(local[i],local[(i+1)%n]) for i in range(n)))
    normals=1-runaxis
    def decode_corner(v):
        c=np.empty((m,2));c[np.arange(m),normals]=v[:-1];c[np.arange(m),np.roll(normals,1)]=np.roll(v[:-1],1);return c
    def decode(v):
        corner=decode_corner(v);loc=(1-fraction[:,None])*corner[node_run]+fraction[:,None]*corner[(node_run+1)%m]
        world=loc@q['basis'];return np.c_[world[:,0],np.full(n,-1.),world[:,1]],np.c_[world[:,0],np.full(n,v[-1]),world[:,1]]
    u=(np.arange(nquad)+.5)*2*np.pi/nquad
    rays=np.stack([-np.sin(u),np.cos(u)],axis=-1)@q['basis'].T
    source=(.5-source_ring.evaluate(u)/512)*np.pi
    normal_rays=rays[:,normals]
    def objective(v,grad=False):
        c=decode_corner(v);e=np.roll(c,-1,axis=0)-c
        with np.errstate(divide='ignore',invalid='ignore'):
            radial=v[:-1][None,:]/normal_rays
            tangent=rays[:,runaxis]*radial
            frac=(tangent-c[np.arange(m),runaxis])/e[np.arange(m),runaxis]
        valid=(radial>0)&(frac>=-1e-9)&(frac<=1+1e-9)&np.isfinite(radial)
        choices=np.where(valid,radial,np.inf);chosen=np.argmin(choices,axis=1)
        missing=~np.isfinite(choices[np.arange(nquad),chosen])
        if np.any(missing):
            # Infeasible transient is penalized; accepted output is checked below.
            safe=np.where(radial>0,radial,np.inf);chosen[missing]=np.argmin(safe[missing],axis=1)
        s=v[chosen];nr=normal_rays[np.arange(nquad),chosen];inv=nr/s
        top=np.arctan(v[-1]*inv);bot=-np.arctan(inv);err=np.stack([top,bot])-source
        loss=float(np.mean(err**2))
        if not grad:return loss
        dt=-v[-1]*inv/s/(1+(v[-1]*inv)**2);db=inv/s/(1+inv**2)
        gv=np.zeros(m+1);np.add.at(gv,chosen,(err[0]*dt+err[1]*db)/nquad)
        gv[-1]=np.sum(err[0]*inv/(1+(v[-1]*inv)**2))/nquad
        return gv
    def ordered(v):
        c=decode_corner(v);e=np.roll(c,-1,axis=0)-c
        return e[np.arange(m),runaxis]*runsigns-1e-6
    # Origin strictly in the visibility kernel; this is an applicability guard.
    side=orientation*runsigns*np.where(runaxis==0,-1.,1.)
    def camera(v):return side*v[:-1]-1e-8
    lengths=np.linalg.norm(q['edges'],axis=1)
    height_start=float(np.sum(lengths*(q['top'][:,1]+np.roll(q['top'][:,1],-1))/2)/lengths.sum())
    start=np.r_[support,max(.05,height_start)]
    results=[]
    for scale in [1.,.8,1.25][:starts]:
        st=start*scale
        sol=minimize(objective,st,jac=lambda v:objective(v,True),method='SLSQP',bounds=[(None,None)]*m+[(1e-5,None)],constraints=[{'type':'ineq','fun':ordered},{'type':'ineq','fun':camera}],options={'ftol':1e-13,'maxiter':500})
        f,t=decode(sol.x);issues=up.geometry_issues(f[:,[0,2]])
        ok=sol.success and not issues and np.min(ordered(sol.x))>=-1e-7 and np.min(camera(sol.x))>=-1e-7
        results.append(dict(status='ok' if ok else 'blocked',reason=';'.join(issues) if issues else '' if ok else 'optimizer_failed',solver=str(sol.message),iterations=int(sol.nit),objective=float(sol.fun),floor=f,top=t,support_parameters=sol.x))
    valid=[a for a in results if a['status']=='ok'];best=min(valid or results,key=lambda a:a['objective'])
    best.update(frame=q['frame'],direction=axis,axis_runs=m,quadrature=nquad,starts=[dict(status=a['status'],objective=a['objective'],iterations=a['iterations']) for a in results])
    if best['status']=='ok':best['record']=record(best['top'],best['floor'],r,'continuous_longitude_boundary_projection',r.get('lineage'))
    return best
