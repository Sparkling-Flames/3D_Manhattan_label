"""Read-only quality components for paired 1024 x 512 panorama layouts.
No registration, reordering, matching, clustering, fusion, or total quality score.
Core units: degree, camera-height h and h^2. See METHOD.md for semantics.
"""
from __future__ import annotations
import math
from typing import Any
import numpy as np
from scipy.integrate import quad
from shapely.geometry import Polygon, Point
from arc_excerpt import Ring, Unsupported, footprint, pairs, rays, paired_wall_proxy

DEG=180/np.pi


def angle(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Stable angular distance between unit vectors, in radians."""
    return np.arctan2(np.linalg.norm(np.cross(a,b),axis=-1),np.sum(a*b,axis=-1))


def region_metrics(a, g) -> dict[str,Any]:
    if a.is_empty or g.is_empty or not a.is_valid or not g.is_valid or min(a.area,g.area)<=0:
        raise ValueError('invalid_or_empty_declared_region')
    inter=a.intersection(g).area
    o=g.difference(a).area; e=a.difference(g).area
    dx=a.centroid.x-g.centroid.x; dz=a.centroid.y-g.centroid.y
    return dict(iou=inter/(a.area+g.area-inter),omission_h2=o,extension_h2=e,
        omission_ref=o/g.area,extension_ref=e/g.area,area_symmetric_ref=(o+e)/g.area,
        area_h2=a.area,reference_area_h2=g.area,
        camera_in_or_on_object=bool(a.covers(Point(0,0))),camera_in_or_on_reference=bool(g.covers(Point(0,0))),
        centroid_dx_h=dx,centroid_dz_h=dz,
        centroid_distance_h=math.hypot(dx,dz),centroid_distance_normalized=math.hypot(dx,dz)/math.sqrt(g.area))


def height_diagnostic(r: dict) -> dict[str,Any]:
    """Original footprint, vertical walls, common floor=-1; NOT measured roof."""
    top,bottom=paired_wall_proxy(r)
    h=top[:,1]+1.;f=bottom[:,[0,2]]
    if np.any(h<=0): raise ValueError('nonpositive_wall_height')
    lengths=np.linalg.norm(np.roll(f,-1,axis=0)-f,axis=1);p=lengths.sum()
    j=np.roll(h,-1);mu=float(np.sum(lengths*(h+j)/2)/p)
    # Integrate squared deviation along each original straight edge.
    a=h-mu;b=j-mu
    rms=float(np.sqrt(np.sum(lengths*(a*a+a*b+b*b)/3)/p))
    return dict(height_mean_h=mu,height_internal_rms_h=rms,
        height_internal_relative_rms=rms/mu,height_max_deviation_h=float(np.max(np.abs(a))),
        height_min_h=float(min(h)),height_max_h=float(max(h)),
        bottom_horizon_margin_deg=float(np.min(np.asarray(r['points'])[1::2,1]-256)*180/512))


def uniform_longitude(a: dict,g: dict) -> dict[str,Any]:
    """Full-circle signed/absolute *vertical* angular discrepancy.
    Only original one-turn single-valued paired rings. Never sort GT/worker.
    Signed error > 0 means candidate is lower in the ERP canvas.
    """
    try:ra=Ring(a)
    except (Unsupported,ValueError) as ex:return dict(longitude_status='unavailable',longitude_reason='object:'+str(ex),longitude_coverage=0.)
    try:rg=Ring(g)
    except (Unsupported,ValueError) as ex:return dict(longitude_status='unavailable',longitude_reason='reference:'+str(ex),longitude_coverage=0.)
    base=sorted(set([0.,2*np.pi]+[x for r in (ra,rg) for p in r.pieces for x in (p.lo,p.hi)]))
    out=dict(longitude_status='ok',longitude_reason=None,longitude_coverage=1.)
    for side,name in enumerate(('top','bottom')):
        total_abs=0.;total_signed=0.;qerror=0.
        for lo,hi in zip(base[:-1],base[1:]):
            if hi-lo<1e-12:continue
            ca=ra.active((lo+hi)/2).coeff[side];cg=rg.active((lo+hi)/2).coeff[side]
            def fun(u):
                sv=np.array([np.sin(u),np.cos(u)])
                return float((np.arctan(cg@sv)-np.arctan(ca@sv))*DEG)
            diff=ca-cg
            cuts=[lo,hi]
            if np.linalg.norm(diff)>1e-14:
                root=math.atan2(-diff[1],diff[0])%np.pi
                cuts+= [v for v in (root,root+np.pi) if lo+1e-12<v<hi-1e-12]
            cuts.sort()
            for l,h in zip(cuts[:-1],cuts[1:]):
                val,err=quad(fun,l,h,epsabs=1e-9,epsrel=1e-9)
                total_signed+=val;total_abs+=abs(val);qerror+=err
        xs=(np.arange(4096)+.5)*2*np.pi/4096
        dd=(ra.evaluate(xs)[side]-rg.evaluate(xs)[side])*180/512
        out.update({name+'_mae_deg':total_abs/(2*np.pi),name+'_signed_deg':total_signed/(2*np.pi),
            name+'_p95_deg':float(np.quantile(np.abs(dd),.95)),name+'_sampled_max_deg':float(np.max(np.abs(dd))),
            name+'_quadrature_error_deg':qerror/(2*np.pi)})
    return out


def point_arc_distances(query:np.ndarray, starts:np.ndarray, ends:np.ndarray) -> tuple[np.ndarray,np.ndarray]:
    """Distance to finite *minor* great-circle arcs, not to infinite great circles.
    Supports seam crossings and original backwards-longitude branches.
    Returns per-query nearest distance (radian) and target edge index.
    Antipodal arcs are explicitly unsupported; zero length edges remain points.
    """
    query=np.asarray(query,float);aa=np.asarray(starts,float);bb=np.asarray(ends,float)
    if len(aa)==0:raise ValueError('empty_target_path')
    lengths=angle(aa,bb)
    if np.any(lengths>=np.pi-1e-10):raise ValueError('antipodal_arc_not_unique')
    best=np.full(len(query),np.inf);ids=np.full(len(query),-1,dtype=int)
    for j,(a,b,L) in enumerate(zip(aa,bb,lengths)):
        dist=np.minimum(angle(query,a),angle(query,b))
        if L>1e-12:
            n=np.cross(a,b);n/=np.linalg.norm(n)
            tangent=np.cross(n,a)
            dotn=query@n
            proj=query-dotn[:,None]*n
            norm=np.linalg.norm(proj,axis=1)
            good=norm>1e-14
            proj[good]/=norm[good,None]
            t=np.arctan2(proj@tangent,proj@a)
            inside=good & (t>=-1e-12) & (t<=L+1e-12)
            dist[inside]=np.arctan2(np.abs(dotn[inside]),norm[inside])
        take=dist<best
        best[take]=dist[take];ids[take]=j
    return best,ids


def sample_arcs(vertices:np.ndarray,closed:bool=True,step_deg:float=.25):
    v=np.asarray(vertices,float)
    starts=v if closed else v[:-1]
    ends=np.roll(v,-1,axis=0) if closed else v[1:]
    qs=[];weights=[];edge_ids=[]
    for i,(a,b) in enumerate(zip(starts,ends)):
        L=float(angle(a,b))
        if L>=np.pi-1e-10:raise ValueError('antipodal_arc_not_unique')
        if L<=1e-12:continue
        count=max(1,int(np.ceil(L*DEG/step_deg)))
        u=(np.arange(count)+.5)/count
        t=(b-a*np.cos(L))/np.sin(L)
        qs.append(np.cos(u*L)[:,None]*a+np.sin(u*L)[:,None]*t)
        weights.extend([L/count]*count);edge_ids.extend([i]*count)
    if not qs:raise ValueError('zero_total_path_length')
    return np.vstack(qs),np.array(weights),np.array(edge_ids,dtype=int)


def weighted_quantile(values,weights,q):
    ix=np.argsort(values);s=np.cumsum(weights[ix]);j=np.searchsorted(s,q*s[-1])
    return float(values[ix[min(j,len(ix)-1)]])


def directed_arc_measure(source:np.ndarray,target:np.ndarray,*,source_closed=True,target_closed=True,step_deg=.25)->dict:
    q,w,_=sample_arcs(source,source_closed,step_deg)
    aa=target if target_closed else target[:-1]
    bb=np.roll(target,-1,axis=0) if target_closed else target[1:]
    d,_=point_arc_distances(q,aa,bb);ends,_=point_arc_distances(np.asarray(source),aa,bb)
    return dict(mean_deg=float(np.dot(d,w)/w.sum()*DEG),p95_deg=weighted_quantile(d*DEG,w,.95),
        sampled_max_deg=float(max(np.max(d),np.max(ends))*DEG),source_arc_length_deg=float(w.sum()*DEG),
        sampling_step_deg=step_deg,mean_quadrature_bound_deg=float(w.max()*DEG/4),
        max_upper_error_bound_deg=float(w.max()*DEG/2),samples=len(q))


def arc_geometry(a:dict,g:dict,step_deg=.25)->dict:
    """Additional geometry diagnostic. NOT same-target localization or correspondence."""
    qa=pairs(a);qg=pairs(g);out=dict(arc_status='ok')
    for side,name in enumerate(('top','bottom')):
        v=rays(qa[:,side]);w=rays(qg[:,side])
        f=directed_arc_measure(v,w,step_deg=step_deg);b=directed_arc_measure(w,v,step_deg=step_deg)
        for direction,stats in [('a_to_g',f),('g_to_a',b)]:
            for stat,val in stats.items():out[f'{name}_arc_{direction}_{stat}']=val
        out[f'{name}_arc_symmetric_mean_deg']=(f['mean_deg']+b['mean_deg'])/2
    return out


def expression(r:dict)->dict:
    q=pairs(r);out=dict(pair_count=len(q),ring_confirmed=r.get('ring_confirmed',False),
        order_status=r.get('order_status'),node_descriptor='original unsimplified paired vertices')
    deviations=[]
    for side in (0,1):
        v=rays(q[:,side]);d=[]
        for j in range(len(v)):
            try:dd,_=point_arc_distances(v[j:j+1],v[(j-1)%len(v)][None],v[(j+1)%len(v)][None]);d.append(float(dd[0]*DEG))
            except ValueError:d.append(None)
        deviations.append(d)
    out['top_node_to_neighbor_chord_deg']=deviations[0];out['bottom_node_to_neighbor_chord_deg']=deviations[1]
    out['source_pair_indices']=r.get('source_pair_indices')
    out['source_point_indices']=r.get('source_point_indices')
    out['connections_processed_pair_indices']=[[j,(j+1)%len(q)] for j in range(len(q))]
    return out


def compare(a:dict,g:dict,*,arcs=True)->dict:
    """Components relative to an explicit reference/observation, never a total score."""
    out=dict(object_id=a.get('id'),reference_id=g.get('id'),pair_count=len(a.get('points') or [])//2,
        reference_pair_count=len(g.get('points') or [])//2,
        count_expression_different=(len(a.get('points') or [])!=len(g.get('points') or [])),
        same_expression_if_equal_count='unknown_without_correspondence_or_review')
    try:
        _,pa=footprint(a);_,pg=footprint(g);out.update(region_metrics(pa,pg));out['range_status']='ok'
    except (Unsupported,ValueError,TypeError) as ex:
        out.update(range_status='unavailable',range_reason=str(ex));return out
    out.update(uniform_longitude(a,g))
    try:
        ha=height_diagnostic(a);hg=height_diagnostic(g);out.update(ha)
        out['reference_height_mean_h']=hg['height_mean_h'];out['height_signed_h']=ha['height_mean_h']-hg['height_mean_h']
        intersection=pa.intersection(pg).area*min(ha['height_mean_h'],hg['height_mean_h'])
        union=pa.area*ha['height_mean_h']+pg.area*hg['height_mean_h']-intersection
        out['conditional_volume_iou']=intersection/union
        out['conditional_3d_status']='horizontal_cap_model_not_observed_roof'
    except (Unsupported,ValueError,TypeError) as ex:
        out.update(conditional_3d_status='unavailable',conditional_3d_reason=str(ex))
    if arcs:
        try:out.update(arc_geometry(a,g))
        except (Unsupported,ValueError,TypeError) as ex:out.update(arc_status='unavailable',arc_reason=str(ex))
    return out
