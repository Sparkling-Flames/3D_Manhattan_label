"""Read-only corresponding-corner supplement. h=camera height, never metres.

No geometric alignment/repair, labels or score changes. A unique cyclic match is
only a correspondence candidate, not proof of semantic structural equivalence.
"""
import numpy as np
from shapely.geometry import Polygon

SCHEMA = 'corresponding_corner_distance_v2'

def angular(a,b):
    du=((a[:,None,0]-b[None,:,0]+512)%1024-512)*2*np.pi/1024
    va=((a[:,1]+.5)/512-.5)*np.pi; vb=((b[:,1]+.5)/512-.5)*np.pi
    h=np.sin((va[:,None]-vb[None,:])/2)**2+np.cos(va[:,None])*np.cos(vb[None,:])*np.sin(du/2)**2
    return np.degrees(2*np.arcsin(np.sqrt(np.clip(h,0,1))))

def project(points):
    p=np.asarray(points,float); top,bottom=p[::2],p[1::2]
    phi=2*np.pi*(bottom[:,0]/1024-.5)
    r=1/np.tan(np.pi*(bottom[:,1]/512-.5))
    y=r*np.tan(np.pi*(.5-top[:,1]/512))
    b=np.column_stack((r*np.sin(phi),-np.ones(len(r)),-r*np.cos(phi)))
    t=b.copy();t[:,1]=y
    return b,t

def area(b):
    x,z=b[:,0],b[:,2]
    return .5*np.sum(x*np.roll(z,-1)-z*np.roll(x,-1))

def corner_compare(a,b):
    """Return scalar diagnostics and per-corner rows; unavailable distances omitted.

    Inputs: final team rows with geometry.points (alternating top/bottom),
    geometry.footprint and complete_evaluable. Pair must use the same frame.
    """
    for key in ['pool_id','reference_id','reference_version']:
        if key in a and key in b and a[key]!=b[key]: raise ValueError('different '+key)
    pa=(a.get('geometry') or {}).get('points');pb=(b.get('geometry') or {}).get('points')
    out=dict(corner_metric_schema=SCHEMA,complete=bool(a.get('complete_evaluable') and b.get('complete_evaluable')),same_count=pa is not None and pb is not None and len(pa)==len(pb))
    if pa is None or pb is None:return dict(out,status='missing_connected_geometry'),[]
    if not out['complete']:return dict(out,status='incomplete_geometry'),[]
    if not out['same_count']:return dict(out,status='different_corner_count'),[]
    pa,pb=np.asarray(pa,float),np.asarray(pb,float)
    for p in [pa,pb]:
        if p.ndim!=2 or p.shape[1:]!=(2,) or len(p)<6 or len(p)%2 or not np.isfinite(p).all():return dict(out,status='invalid_point_pairs'),[]
        if np.max(np.abs((p[::2,0]-p[1::2,0]+512)%1024-512))>1e-6:return dict(out,status='vertical_pair_mismatch'),[]
        if np.any(p[1::2,1]<=256) or np.any(p[1::2,1]>=512) or np.any(p[::2,1]<=0) or np.any(p[::2,1]>=256):return dict(out,status='invalid_or_horizon_rays'),[]
    ba,ta=project(pa);bb,tb=project(pb)
    for row,bottom in [(a,ba),(b,bb)]:
        poly=Polygon(bottom[:,[0,2]])
        if not poly.is_valid or poly.area<=0:return dict(out,status='invalid_floor'),[]
        floor=(row.get('geometry') or {}).get('footprint')
        if floor is None or np.asarray(floor).shape!=bottom[:,[0,2]].shape:return dict(out,status='missing_or_mismatched_footprint'),[]
        if not np.allclose(floor,bottom[:,[0,2]],rtol=1e-7,atol=1e-8):return dict(out,status='footprint_projection_mismatch'),[]
    n=len(ba);rev=bool(np.sign(area(ba))!=np.sign(area(bb)))
    src=np.arange(n)[::-1] if rev else np.arange(n)
    cost=np.maximum(angular(pa[::2],pb[::2]),angular(pa[1::2],pb[1::2]))
    old=min(cost[np.arange(n),(np.arange(n)+s)%n].max() for s in range(n))
    costs=cost[:,src]; vals=np.array([costs[np.arange(n),(np.arange(n)+s)%n].max() for s in range(n)])
    shift=int(vals.argmin());best=float(vals[shift]);second=float(np.sort(vals)[1])
    out.update(corners=n,ring_reversed=rev,shift=shift,legacy_angle_deg=float(old),angle_deg=best,second_angle_deg=second,match_gap_deg=second-best)
    if second-best<=1e-9:return dict(out,status='ambiguous_cyclic_match'),[]
    idx=src[(np.arange(n)+shift)%n]
    def reflex(bottom):
        p=bottom[:,[0,2]];u=p-np.roll(p,1,axis=0);v=np.roll(p,-1,axis=0)-p
        turn=u[:,0]*v[:,1]-u[:,1]*v[:,0]
        return turn*np.sign(area(bottom)) < -1e-10
    out['matched_reflex_disagreement_n']=int(np.sum(reflex(ba)!=reflex(bb)[idx]))
    out['high_angle_correspondence_warning']=best>12
    bb,tb=bb[idx],tb[idx]
    bev=np.linalg.norm(bb-ba,axis=1);top=np.linalg.norm(tb-ta,axis=1)
    scale=np.sqrt((abs(area(ba))+abs(area(bb)))/2)
    radius=(np.linalg.norm(ba[:,[0,2]],axis=1)+np.linalg.norm(bb[:,[0,2]],axis=1))/2
    diag=np.linalg.norm(np.ptp(ba[:,[0,2]],axis=0))
    out.update(status='unique_cyclic_candidate',pair_area_scale_h=float(scale),near_horizon_bottom_min_deg=float(np.min(np.concatenate((pa[1::2,1],pb[1::2,1]))-256)*180/512))
    for name,v in [('bev',bev),('top',top)]:
        out.update({name+'_mean_h':float(v.mean()),name+'_max_h':float(v.max()),name+'_p95_h':float(np.quantile(v,.95)),name+'_mean_pairscale':float(v.mean()/scale),name+'_max_pairscale':float(v.max()/scale),name+'_max_local_radius_fraction':float((v/radius).max()),name+'_max_pct_diagonal':float(100*v.max()/diag)})
    details=[dict(corner_A_index=j,corner_other_index=int(idx[j]),bev_h=float(bev[j]),top_h=float(top[j]),dx_h=float(bb[j,0]-ba[j,0]),dz_h=float(bb[j,2]-ba[j,2]),height_change_h=float(tb[j,1]-ta[j,1]),bev_local_radius_fraction=float(bev[j]/radius[j]),top_local_radius_fraction=float(top[j]/radius[j])) for j in range(n)]
    return out,details
