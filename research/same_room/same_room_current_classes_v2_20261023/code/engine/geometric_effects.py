"""Within-view A/B geometry comparisons; never align different camera views.

Preparation caches per-endpoint validation/projected points. Correspondence is
the existing corner_distance.py unique cyclic candidate (same formula and
tolerances). It is a geometric correspondence candidate, not a semantic label.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import numpy as np
if (Path(__file__).resolve().parent/'deps').exists():
    sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'))
from shapely.geometry import Polygon

_repo_value=os.environ.get('HOHONET_REPO')
if not _repo_value:
    raise RuntimeError('Set HOHONET_REPO to the frozen repository checkout; see code/engine/README.md.')
REPO=Path(_repo_value).expanduser().resolve()
sys.path.insert(0,str(REPO/'research/workers/personnel_interchangeability_followup_20261020/audit_corner'))
from corner_distance import angular, project, area


def prepare(row):
    """One endpoint, from a complete row or compact geometry CSV row."""
    out={k:row.get(k) for k in ['team_key','pool_id','reference_id','reference_version','k']}
    geometry=row.get('geometry')
    if geometry is None and row.get('geometry_json'):
        geometry=json.loads(row['geometry_json'])
    points=(geometry or {}).get('points')
    out['geometry']=geometry
    out['points']=points
    out['complete']=row.get('complete_evaluable') in (True,1,'True','true','1')
    if points is None:
        return dict(out,status='missing_connected_geometry')
    if not out['complete']:
        return dict(out,status='incomplete_geometry')
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1:]!=(2,) or len(p)<6 or len(p)%2 or not np.isfinite(p).all():
        return dict(out,status='invalid_point_pairs')
    out['n_corners']=len(p)//2
    if np.max(np.abs((p[::2,0]-p[1::2,0]+512)%1024-512))>1e-6:
        return dict(out,status='vertical_pair_mismatch')
    if np.any(p[1::2,1]<=256) or np.any(p[1::2,1]>=512) or np.any(p[::2,1]<=0) or np.any(p[::2,1]>=256):
        return dict(out,status='invalid_or_horizon_rays')
    bottom,top=project(p);poly=Polygon(bottom[:,[0,2]])
    if not poly.is_valid or poly.area<=0:
        return dict(out,status='invalid_floor')
    footprint=(geometry or {}).get('footprint')
    if footprint is None or np.asarray(footprint).shape!=bottom[:,[0,2]].shape:
        return dict(out,status='missing_or_mismatched_footprint')
    if not np.allclose(footprint,bottom[:,[0,2]],rtol=1e-7,atol=1e-8):
        return dict(out,status='footprint_projection_mismatch')
    p2=bottom[:,[0,2]];u=p2-np.roll(p2,1,axis=0);v=np.roll(p2,-1,axis=0)-p2
    turn=u[:,0]*v[:,1]-u[:,1]*v[:,0]
    signed_area=area(bottom)
    reflex=turn*np.sign(signed_area)<-1e-10
    return dict(out,status='ok',p=p,bottom=bottom,top=top,poly=poly,area=signed_area,reflex=reflex)


def compare(a,b,include_floor=False,include_details=False):
    """Prepared A/B must belong to the same image/reference; B−A orientation."""
    for k in ['pool_id','reference_id','reference_version']:
        if a.get(k) is not None and b.get(k) is not None and a[k]!=b[k]:
            raise ValueError('within-view geometry required: different '+k)
    both=a['complete'] and b['complete']
    same=a['points'] is not None and b['points'] is not None and len(a['points'])==len(b['points'])
    result=dict(complete=bool(both),same_count=bool(same))
    if a['points'] is None or b['points'] is None:
        return dict(result,status='missing_connected_geometry')
    if not both:
        return dict(result,status='incomplete_geometry')
    if not same:
        return dict(result,status='different_corner_count')
    if a['status']!='ok' or b['status']!='ok':
        return dict(result,status=a['status'] if a['status']!='ok' else b['status'])
    n=a['n_corners'];pa,pb=a['p'],b['p'];rev=np.sign(a['area'])!=np.sign(b['area'])
    src=np.arange(n)[::-1] if rev else np.arange(n)
    top_cost=angular(pa[::2],pb[::2]);bottom_cost=angular(pa[1::2],pb[1::2])
    cost=np.maximum(top_cost,bottom_cost)[:,src]
    shifts=(np.arange(n)[None,:]+np.arange(n)[:,None])%n
    values=cost[np.arange(n)[None,:],shifts].max(axis=1)
    shift=int(np.argmin(values));best=float(values[shift]);second=float(np.sort(values)[1])
    result.update(corners=n,ring_reversed=bool(rev),shift=shift,angle_deg=best,
                  second_angle_deg=second,match_gap_deg=second-best)
    if second-best<=1e-9:
        return dict(result,status='ambiguous_cyclic_match')
    idx=src[(np.arange(n)+shift)%n]
    ba,ta=a['bottom'],a['top'];bb,tb=b['bottom'][idx],b['top'][idx]
    bev=np.linalg.norm(bb-ba,axis=1);top=np.linalg.norm(tb-ta,axis=1)
    bottom_angles=bottom_cost[np.arange(n),idx];top_angles=top_cost[np.arange(n),idx]
    result.update(status='unique_cyclic_candidate',bev_mean_h=float(bev.mean()),bev_max_h=float(bev.max()),
        top_mean_h=float(top.mean()),top_max_h=float(top.max()),
        bottom_angular_mean_deg=float(bottom_angles.mean()),bottom_angular_max_deg=float(bottom_angles.max()),
        top_angular_mean_deg=float(top_angles.mean()),top_angular_max_deg=float(top_angles.max()),
        signed_height_change_mean_h=float((tb[:,1]-ta[:,1]).mean()),
        matched_reflex_disagreement_n=int(np.sum(a['reflex']!=b['reflex'][idx])),
        high_angle_correspondence_warning=best>12,
        exact_geometry_equal=bool(np.array_equal(pa,pb)),
        cyclic_geometry_equal=bool(np.allclose(ba,bb,rtol=0,atol=1e-12) and np.allclose(ta,tb,rtol=0,atol=1e-12)))
    if include_floor:
        inter=a['poly'].intersection(b['poly']).area
        union=a['poly'].area+b['poly'].area-inter
        result['floor_jaccard_difference']=float(1-inter/union)
        result['floor_symdiff_h2']=float(a['poly'].area+b['poly'].area-2*inter)
    if include_details:
        result['details']=[dict(corner_A_index=j,corner_B_index=int(idx[j]),
            bev_h=float(bev[j]),top_h=float(top[j]),bottom_angular_deg=float(bottom_angles[j]),
            top_angular_deg=float(top_angles[j]),dx_h=float(bb[j,0]-ba[j,0]),dz_h=float(bb[j,2]-ba[j,2]),
            height_change_h=float(tb[j,1]-ta[j,1])) for j in range(n)]
    return result


def paired_effect_state(source_delta,target_delta,tolerance=2.):
    """Keep double-null separate from nontrivial same-sign effects."""
    if source_delta is None or target_delta is None or not np.isfinite([source_delta,target_delta]).all():
        return 'unavailable'
    a,b=float(source_delta),float(target_delta)
    small_a=abs(a)<=tolerance;small_b=abs(b)<=tolerance
    if small_a and small_b:return 'both_within_tolerance'
    if small_a:return 'target_only'
    if small_b:return 'source_only'
    if np.sign(a)==np.sign(b):return 'both_nontrivial_same_direction'
    return 'both_nontrivial_opposite_direction'
