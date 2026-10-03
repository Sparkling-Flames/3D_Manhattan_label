"""Independent audit implementation, NOT the downloaded repository verifier.
All inputs are saved paired C coordinates (1024 x 512), camera at origin,
Y up, floor Y=-1. No sorting, raw fallback, or coordinate fitting for geometry.
The current source uses a perimeter-length mean height. Vertex-LS and
angular arclength-LS are exploratory alternatives, NOT the current model.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import minimize_scalar
from shapely.geometry import Polygon, Point

@dataclass
class Geometry:
    floor: np.ndarray
    heights: np.ndarray
    pairs: np.ndarray
    polygon: Polygon


def reconstruct(record: dict) -> Geometry:
    p=np.asarray(record['points'],dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():
        raise ValueError('invalid_point_array')
    q=p.reshape(-1,2,2)
    if np.max(abs((q[:,0,0]-q[:,1,0]+512)%1024-512))>1e-6:
        raise ValueError('vertical_pair_mismatch')
    u=2*np.pi*(q[:,1,0]/1024-.5)
    alpha=np.pi*(q[:,1,1]/512-.5)
    beta=np.pi*(.5-q[:,0,1]/512)
    if np.any(alpha<=0) or np.any(beta<=0):raise ValueError('wrong_hemisphere')
    if np.min(np.r_[alpha,beta])<np.radians(.5):raise ValueError('near_horizon')
    radius=1/np.tan(alpha)
    floor=radius[:,None]*np.c_[np.sin(u),-np.cos(u)]
    heights=1+radius*np.tan(beta)
    poly=Polygon(floor)
    if not poly.is_valid or poly.area<1e-10:raise ValueError('invalid_footprint')
    return Geometry(floor,heights,q,poly)


def record_from_geometry(floor,heights=2.7,identity='synthetic'):
    p=np.asarray(floor,float); h=np.broadcast_to(heights,(len(p),)).astype(float)
    r=np.linalg.norm(p,axis=1);u=np.arctan2(p[:,0],-p[:,1])
    x=(u/(2*np.pi)+.5)*1024
    top=(.5-np.arctan2(h-1,r)/np.pi)*512
    bottom=(.5+np.arctan2(1,r)/np.pi)*512
    return dict(id=identity,points=np.stack([np.c_[x,top],np.c_[x,bottom]],axis=1).reshape(-1,2).tolist(),
                coordinate_convention='continuous',ring_confirmed=True,order_status='synthetic_known')


def edge_quadrature(g:Geometry,order:int=32):
    """Gauss quadrature per physical segment, weighted by segment length.
    Re-evaluates the actual linear 3D wall top; not interpolation in ERP pixels.
    """
    z,w=np.polynomial.legendre.leggauss(order);t=(z+1)/2;w=w/2
    p=g.floor;e=np.roll(p,-1,axis=0)-p;l=np.linalg.norm(e,axis=1)
    h=g.heights;xy=p[:,None,:]+t[None,:,None]*e[:,None,:]
    hh=h[:,None]+t[None,:]*(np.roll(h,-1)-h)[:,None]
    ww=l[:,None]*np.broadcast_to(w,hh.shape)
    return xy.reshape(-1,2),hh.ravel(),ww.ravel()


def fit_height(g:Geometry,mode='vertex',order=32):
    if mode=='vertex':
        xy=g.floor; beta=np.pi*(.5-g.pairs[:,0,1]/512);weights=np.ones(len(xy))
    elif mode=='arclength':
        xy,h,weights=edge_quadrature(g,order);beta=np.arctan2(h-1,np.linalg.norm(xy,axis=1))
    else:raise ValueError('unknown_height_fit_mode')
    r=np.linalg.norm(xy,axis=1)
    objective=lambda H:float(np.average((np.arctan2(H-1,r)-beta)**2,weights=weights))
    res=minimize_scalar(objective,bounds=(1.000001,max(2.,float(max(g.heights))*5)),method='bounded',options={'xatol':1e-12})
    if not res.success:raise ValueError('height_optimization_failed')
    return dict(height_h=float(res.x),projection_rmse_px=math.sqrt(objective(res.x))*512/np.pi,
                mode=mode,quadrature_order=order if mode=='arclength' else None)


def sample_boundary(g:Geometry,n=512):
    p=g.floor;e=np.roll(p,-1,axis=0)-p;l=np.linalg.norm(e,axis=1)
    c=np.r_[0,np.cumsum(l)];s=np.arange(n)*c[-1]/n
    j=np.minimum(np.searchsorted(c,s,side='right')-1,len(p)-1);t=(s-c[j])/l[j]
    return p[j]+t[:,None]*e[j],g.heights[j]+t*(np.roll(g.heights,-1)[j]-g.heights[j])


def nearest_boundary(xy:np.ndarray,g:Geometry):
    p=g.floor;e=np.roll(p,-1,axis=0)-p
    t=np.clip(np.sum((xy[:,None,:]-p[None,:,:])*e[None,:,:],axis=2)/np.sum(e*e,axis=1)[None,:],0,1)
    foot=p[None,:,:]+t[:,:,None]*e[None,:,:]
    d2=np.sum((xy[:,None,:]-foot)**2,axis=2);j=np.argmin(d2,axis=1);i=np.arange(len(xy))
    h=g.heights[j]+t[i,j]*(np.roll(g.heights,-1)[j]-g.heights[j])
    return np.sqrt(d2[i,j]),h


def boundary_metrics(a:Geometry,b:Geometry,n=512):
    pa,ha=sample_boundary(a,n);pb,hb=sample_boundary(b,n)
    da,hba=nearest_boundary(pa,b);db,hab=nearest_boundary(pb,a)
    d=np.r_[da,db];dh=np.r_[ha-hba,hb-hab]
    return dict(boundary_mean_h=float(d.mean()),boundary_p95_h=float(np.quantile(d,.95)),
                boundary_sampled_max_h=float(d.max()),wall_height_rmse_h=float(np.sqrt(np.mean(dh*dh))),
                sampled_max_error_bound_h=max(a.polygon.length,b.polygon.length)/(2*n),samples_per_direction=n)


def column_bounds(g:Geometry,width=1024):
    if not g.polygon.contains(Point(0,0)):raise ValueError('camera_not_strictly_inside')
    u=2*np.pi*((np.arange(width)+.5)/width-.5);rays=np.c_[np.sin(u),-np.cos(u)]
    d=np.full(width,np.inf);h=np.full(width,np.nan)
    cross=lambda a,b:a[...,0]*b[...,1]-a[...,1]*b[...,0]
    for i,a in enumerate(g.floor):
        e=g.floor[(i+1)%len(g.floor)]-a;den=cross(rays,e);good=abs(den)>1e-12
        rr=np.full(width,np.inf);tt=np.full(width,np.inf)
        rr[good]=cross(a,e)/den[good];tt[good]=cross(a,rays[good])/den[good]
        hit=good&(rr>0)&(tt>=-1e-10)&(tt<=1+1e-10)&(rr<d)
        d[hit]=rr[hit];h[hit]=g.heights[i]+tt[hit]*(g.heights[(i+1)%len(g.floor)]-g.heights[i])-1
    if not np.isfinite(d).all():raise ValueError('uncovered_ray')
    return np.arctan2(h,d),-np.arctan2(1,d)


def mask(g:Geometry,width=1024,height=512):
    top,bottom=column_bounds(g,width);v=np.pi*(.5-(np.arange(height)+.5)/height)
    return (v[:,None]<=top)&(v[:,None]>=bottom)


def mask_iou(a,b):
    den=np.count_nonzero(a|b)
    return float(np.count_nonzero(a&b)/den) if den else None


def axis_metrics(g:Geometry):
    e=np.roll(g.floor,-1,axis=0)-g.floor;l=np.linalg.norm(e,axis=1);theta=np.arctan2(e[:,1],e[:,0])
    objective=lambda ax:float(np.average(((theta-ax+np.pi/4)%(np.pi/2)-np.pi/4)**2,weights=l))
    grid=np.linspace(0,np.pi/2,181,endpoint=False);start=min(grid,key=objective)
    res=minimize_scalar(objective,bounds=(start-np.pi/180,start+np.pi/180),method='bounded',options={'xatol':1e-12})
    return dict(self_axis_deg=float(np.degrees(res.x%(np.pi/2))),self_axis_rms_deg=float(np.degrees(np.sqrt(res.fun))))


def compare(a:Geometry,b:Geometry,width=1024,height=512):
    A,B=a.polygon.area,b.polygon.area;inter=a.polygon.intersection(b.polygon).area
    fv=[fit_height(g,'vertex') for g in (a,b)];fa=[fit_height(g,'arclength') for g in (a,b)]
    def vol(f):
        H,K=f[0]['height_h'],f[1]['height_h'];iv=inter*min(H,K)
        return float(iv/(A*H+B*K-iv))
    out=dict(bev_iou=float(inter/(A+B-inter)),area_a_h2=A,area_b_h2=B,
             coverage_of_a=float(inter/A),coverage_of_b=float(inter/B),centroid_h=float(a.polygon.centroid.distance(b.polygon.centroid)),
             vertex_ls_volume_iou=vol(fv),arclength_ls_volume_iou=vol(fa),
             vertex_height_a_h=fv[0]['height_h'],vertex_height_b_h=fv[1]['height_h'],
             vertex_fit_a_px=fv[0]['projection_rmse_px'],vertex_fit_b_px=fv[1]['projection_rmse_px'],
             arclength_height_a_h=fa[0]['height_h'],arclength_height_b_h=fa[1]['height_h'],
             **boundary_metrics(a,b),**axis_metrics(a))
    try:
        ma,mb=mask(a,width,height),mask(b,width,height)
        ta,ba=column_bounds(a,width);tb,bb=column_bounds(b,width)
        out.update(column_status='ok',column_reason=None,column_iou=mask_iou(ma,mb),different_pixels=int(np.count_nonzero(ma^mb)),
                   top_curve_rmse_px=float(np.sqrt(np.mean((ta-tb)**2))*512/np.pi),
                   bottom_curve_rmse_px=float(np.sqrt(np.mean((ba-bb)**2))*512/np.pi))
    except ValueError as exc:
        out.update(column_status='unavailable',column_reason=str(exc),column_iou=None,different_pixels=None,
                   top_curve_rmse_px=None,bottom_curve_rmse_px=None)
    return out

# Current pinned source uses boundary-length mean height, not an optimized ceiling.
def current_height_stats(g:Geometry):
    p,h=g.floor,g.heights;l=np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)
    nxt=np.roll(h,-1);mean=float(np.average((h+nxt)/2,weights=l));a=h-mean;b=nxt-mean
    rms=float(np.sqrt(np.average((a*a+a*b+b*b)/3,weights=l)))
    return dict(mean_h=mean,rms_h=rms,rms_relative=rms/mean,max_deviation_h=float(np.max(abs(h-mean))))

_exploratory_compare=compare

def compare(a:Geometry,b:Geometry,width=1024,height=512):
    """Current perimeter-mean proxy plus explicitly separate new diagnostics.
    vertex_ls and arclength_ls are EXPLORATORY alternatives, NOT current source.
    Registered wall-height RMSE is a NEW diagnostic in this independent audit.
    """
    out=_exploratory_compare(a,b,width,height)
    A,B=a.polygon.area,b.polygon.area;I=a.polygon.intersection(b.polygon).area
    ha,hb=current_height_stats(a),current_height_stats(b)
    VI=I*min(ha['mean_h'],hb['mean_h'])
    out.update(current_model_volume_iou=float(VI/(A*ha['mean_h']+B*hb['mean_h']-VI)),
        current_height_mean_a_h=ha['mean_h'],current_height_mean_b_h=hb['mean_h'],
        current_height_rms_a_h=ha['rms_h'],current_height_rms_relative_a=ha['rms_relative'],
        current_height_signed_h=ha['mean_h']-hb['mean_h'])
    return out
