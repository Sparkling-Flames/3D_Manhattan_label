"""Geometry-only, local-evidence-first reference routing.

No worker, image, record, point-index, quality score, height, or D is accepted.
Input reference candidates must already have been admitted externally. The
router never approves a new space and never assesses the quality of a response.
All topology descriptors are measurements of the unchanged boundary.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from shapely.geometry import Polygon, Point, mapping


def strict_polygon(vertices):
    q=np.asarray(vertices,dtype=float)
    if q.ndim!=2 or q.shape[1]!=2 or len(q)<3 or not np.isfinite(q).all():
        raise ValueError('missing_or_nonfinite_floor_ring')
    if np.min(np.linalg.norm(np.roll(q,-1,axis=0)-q,axis=1))<=1e-12:
        raise ValueError('duplicate_adjacent_vertex')
    p=Polygon(q)
    if not p.is_valid or p.is_empty or p.area<=1e-12:
        raise ValueError('invalid_or_zero_area_polygon')
    return p


def sample_ring(q,n):
    q=np.asarray(q,float);e=np.roll(q,-1,axis=0)-q;l=np.linalg.norm(e,axis=1)
    c=np.r_[0,np.cumsum(l)];s=(np.arange(n)+.5)/n*c[-1]
    ix=np.searchsorted(c,s,side='right')-1;u=(s-c[ix])/l[ix]
    return q[ix]+u[:,None]*e[ix],e[ix]/l[ix,None],ix,float(c[-1]/n)


def point_boundary_distance(points,q):
    q=np.asarray(q,float);points=np.asarray(points,float);e=np.roll(q,-1,axis=0)-q
    ll=np.sum(e*e,axis=1);v=points[:,None,:]-q[None,:,:]
    t=np.clip(np.sum(v*e[None,:,:],axis=2)/ll[None,:],0,1)
    d=np.linalg.norm(v-t[:,:,None]*e[None,:,:],axis=2);ix=np.argmin(d,axis=1)
    return d[np.arange(len(points)),ix],e[ix]/np.sqrt(ll[ix,None]),ix


def point_boundary_orientation(points,source_tangent,q):
    """Nearest boundary distance and best tangent within the same nearest set.

    At a vertex two incident segments can be equally near. Arbitrary argmin
    edge-index selection is unstable under insertion of collinear points.
    Both incident tangents belong to that identical geometric nearest point;
    retain the better aligned one, with a scale-relative roundoff tolerance.
    """
    q=np.asarray(q,float);points=np.asarray(points,float);e=np.roll(q,-1,axis=0)-q
    ll=np.sum(e*e,axis=1);v=points[:,None,:]-q[None,:,:]
    t=np.clip(np.sum(v*e[None,:,:],axis=2)/ll[None,:],0,1)
    d=np.linalg.norm(v-t[:,:,None]*e[None,:,:],axis=2);nearest=d.min(axis=1)
    tolerance=1e-10*max(float(np.linalg.norm(np.ptp(q,axis=0))),1e-10)
    tied=d<=nearest[:,None]+tolerance
    tangent=e/np.sqrt(ll[:,None]);angles=np.degrees(np.arccos(np.clip(np.abs(np.asarray(source_tangent)@tangent.T),0,1)))
    angle=np.where(tied,angles,np.inf).min(axis=1)
    return nearest,angle


def boundary_distance(a,b,n=2048):
    sa,_,_,_=sample_ring(a,n);sb,_,_,_=sample_ring(b,n)
    return .5*(point_boundary_distance(sa,b)[0].mean()+point_boundary_distance(sb,a)[0].mean())


def corners(q,min_turn):
    q=np.asarray(q,float);pre=np.roll(q,1,axis=0)-q;nex=np.roll(q,-1,axis=0)-q
    lp=np.linalg.norm(pre,axis=1);ln=np.linalg.norm(nex,axis=1)
    up=pre/lp[:,None];un=nex/ln[:,None]
    # Undirected incoming/outgoing adjacency matters. Collinear inserted points
    # have zero turn, so splitting a wall does not create a structural corner.
    turn=np.degrees(np.arccos(np.clip(np.sum(-up*un,axis=1),-1,1)))
    ids=np.where(turn>=min_turn)[0]
    # Sum complete incident runs between structural turns. Looking only at
    # the immediately adjacent edge lets a collinear point arbitrarily close
    # to a real corner drive its support to zero.
    support=[]
    for z,i in enumerate(ids):
        j=ids[(z+1)%len(ids)];k=ids[(z-1)%len(ids)]
        forward=[(i+t)%len(q) for t in range((j-i)%len(q))]
        backward=[(k+t)%len(q) for t in range((i-k)%len(q))]
        support.append(min(float(ln[forward].sum()),float(ln[backward].sum())))
    return {'points':q[ids], 'prev':up[ids], 'next':un[ids],
            'support':np.asarray(support),'index':ids,'turn_deg':turn[ids]}


def corner_similarity(a,b,tau,angle_scale):
    if len(a['points'])==0 or len(b['points'])==0:
        return np.zeros(len(a['points']))
    d=np.linalg.norm(a['points'][:,None,:]-b['points'][None,:,:],axis=2)
    def angular(u,v):
        return np.degrees(np.arccos(np.clip(u@v.T,-1,1)))
    pa=angular(a['prev'],b['prev']);nb=angular(a['next'],b['next'])
    pb=angular(a['prev'],b['next']);na=angular(a['next'],b['prev'])
    mismatch=np.minimum(pa*pa+nb*nb,pb*pb+na*na)/2
    return np.max(np.exp(-(d/(2*tau))**2-mismatch/angle_scale**2),axis=1)


def floor_metrics(a,b):
    p=strict_polygon(a);r=strict_polygon(b);x=p.intersection(r).area;u=p.union(r).area
    return {'I':float(x/u),'annotation_area_h2':float(p.area),'reference_area_h2':float(r.area),
            'intersection_area_h2':float(x),'union_area_h2':float(u),
            'missing_over_reference':float((r.area-x)/r.area),
            'extra_over_reference':float((p.area-x)/r.area),
            'extra_over_annotation':float((p.area-x)/p.area),
            'abs_log_area_ratio':float(abs(math.log(p.area/r.area)))}


def _components(g,min_area):
    parts=list(g.geoms) if hasattr(g,'geoms') else [g]
    out=[]
    for v in parts:
        if v.geom_type=='Polygon' and v.area>=min_area:out.append(v)
        elif hasattr(v,'geoms'):out.extend(_components(v,min_area))
    return out


def prepare_reference_set(candidates,config):
    """Freeze descriptors from references alone; scoring formula cannot affect them."""
    refs={c['candidate_id']:dict(c,polygon=strict_polygon(c['floor_xz_h'])) for c in candidates}
    pairs=[]
    for i,ci in enumerate(candidates):
        for cj in candidates[i+1:]:
            ai,aj=ci['candidate_id'],cj['candidate_id'];pi,pj=refs[ai]['polygon'],refs[aj]['polygon']
            scale=math.sqrt(pi.union(pj).area);tau=config['local_distance_scale_over_sqrt_union_area']*scale
            pair={'a':ai,'b':aj,'scale_h':scale,'tau_h':tau,'descriptors':{}}
            for label,other in [(ai,aj),(aj,ai)]:
                c=refs[label];o=refs[other];q=np.array(c['floor_xz_h']);oq=np.array(o['floor_xz_h'])
                sp,tan,ei,ds=sample_ring(q,config['boundary_samples']);dist=point_boundary_distance(sp,oq)[0]
                mask=dist>tau
                cc=corners(q,config['structural_corner_min_turn_deg']);oc=corners(oq,config['structural_corner_min_turn_deg'])
                sim=corner_similarity(cc,oc,tau,config['local_tangent_scale_deg'])
                cmask=sim<config['distinct_corner_max_other_similarity']
                ex=c['polygon'].difference(o['polygon']);parts=_components(ex,config['material_difference_relative_area']*scale**2)
                pair['descriptors'][label]={'sample_points':sp,'sample_tangent':tan,'sample_edge':ei,'sample_step_h':ds,
                    'distinct_mask':mask,'corners':cc,'distinct_corner_mask':cmask,
                    'exclusive':ex,'components':parts,
                    'material_exclusive_area_h2':sum(v.area for v in parts),
                    'distinctive_length_h':float(mask.sum()*ds)}
            pairs.append(pair)
    return {'references':refs,'pairs':pairs,'config':config}


def export_distinguishing_regions(prepared):
    result=[]
    for pair in prepared['pairs']:
        out={k:pair[k] for k in ['a','b','scale_h','tau_h']};out['candidates']={}
        for cid,d in pair['descriptors'].items():
            out['candidates'][cid]={
                'distinctive_length_h':d['distinctive_length_h'],
                'exclusive_regions':[mapping(x) for x in d['components']],
                'distinctive_corner_indices_zero_based':d['corners']['index'][d['distinct_corner_mask']].tolist(),
                'distinctive_corner_points':d['corners']['points'][d['distinct_corner_mask']].tolist(),
                'material_exclusive_area_h2':d['material_exclusive_area_h2']}
        result.append(out)
    return result


def _support(annotation,poly,desc,tau,scale,config):
    mask=desc['distinct_mask'];sp=desc['sample_points'];tan=desc['sample_tangent']
    dist,ang=point_boundary_orientation(sp,tan,annotation)
    support=np.exp(-(dist/tau)**2-(ang/config['local_tangent_scale_deg'])**2)
    length=desc['distinctive_length_h'];have_b=length>=config['minimum_distinctive_length_over_tau']*tau
    bs=float(support[mask].mean()) if mask.any() else None
    cc=desc['corners'];ac=corners(annotation,config['structural_corner_min_turn_deg'])
    cs=corner_similarity(cc,ac,tau,config['local_tangent_scale_deg']);cm=desc['distinct_corner_mask']
    # We cap incident support so long walls do not erase a locally diagnostic
    # corner. Extremely short reference details also receive little weight.
    weights=np.minimum(cc['support'],scale*.25);have_c=bool(cm.any() and weights[cm].sum()>tau)
    cv=float(np.average(cs[cm],weights=weights[cm])) if have_c else None
    vals=[]
    if have_b and config['local_boundary_weight']>0:vals.append((config['local_boundary_weight'],bs))
    if have_c and config['local_corner_weight']>0:vals.append((config['local_corner_weight'],cv))
    combined=sum(w*v for w,v in vals)/sum(w for w,v in vals) if vals else None
    comp=[]
    for p in desc['components']:
        comp.append({'area_h2':float(p.area),'coverage':float(poly.intersection(p).area/p.area)})
    material=desc['material_exclusive_area_h2']
    cov=sum(x['area_h2']*x['coverage'] for x in comp)/material if material else None
    hits=mask&(dist<=tau)&(ang<=config['local_tangent_scale_deg'])
    # Adjacent sample pairs support an actual connected boundary portion.
    # The statistic is deliberately descriptive, not a new quality factor.
    same_tangent=np.sum(tan*np.roll(tan,1,axis=0),axis=1)>1-1e-8
    continuous=hits&np.roll(hits,1)&same_tangent
    return {'local_support':combined,'boundary_support':bs,'corner_support':cv,
        'distinctive_boundary_length_h':length,'distinctive_corner_count':int(cm.sum()),
        'matched_contiguous_boundary_length_h':float(continuous.sum()*desc['sample_step_h']),
        'boundary_evidence_available':have_b,'corner_evidence_available':have_c,
        'material_exclusive_area_h2':float(material),'exclusive_coverage':cov,'exclusive_components':comp,
        'corner_similarities':cs[cm].tolist()}


def route_floor(annotation,prepared):
    """Select first, evaluate quality elsewhere. All fallback outcomes are provisional."""
    a=np.asarray(annotation,float);p=strict_polygon(a);cfg=prepared['config'];refs=prepared['references']
    metrics={cid:floor_metrics(a,c['floor_xz_h']) for cid,c in refs.items()}
    for cid,c in refs.items():
        b=boundary_distance(a,c['floor_xz_h'],cfg['boundary_fallback_samples'])
        metrics[cid]['boundary_mean_h']=b
        metrics[cid]['boundary_mean_over_sqrt_ref_area']=b/math.sqrt(c['polygon'].area)
    labels=list(refs);votes=[];defeated=set()
    for pair in prepared['pairs']:
        ids=[pair['a'],pair['b']];ev={cid:_support(a,p,pair['descriptors'][cid],pair['tau_h'],pair['scale_h'],cfg) for cid in ids}
        winner=None;why='local_evidence_insufficient_or_small_reference_difference'
        x,y=[ev[i]['local_support'] for i in ids]
        if x is not None and y is not None:
            leader=ids[0] if x>=y else ids[1];other=ids[1] if x>=y else ids[0]
            e,o=ev[leader],ev[other];diff=abs(x-y)
            if max(x,y)>=cfg['local_min_support'] and diff>=cfg['local_min_margin']:
                own_ok=e['exclusive_coverage'] is None or e['exclusive_coverage']>=cfg['local_exclusive_min_coverage']
                other_ok=o['exclusive_coverage'] is None or o['exclusive_coverage']<=cfg['local_other_exclusive_max_coverage']
                if own_ok and other_ok:
                    winner=leader;why='distinctive_boundary_and_turn_support_with_region_consistency';defeated.add(other)
                else:why='boundary_turn_evidence_conflicts_with_exclusive_region_coverage'
            else:why='local_support_or_candidate_margin_below_evidence_band'
        votes.append({'candidate_a':ids[0],'candidate_b':ids[1],'winner':winner,'reason':why,'evidence':ev})
    survivors=[cid for cid in labels if cid not in defeated];conflict=False
    if not survivors:survivors=labels;conflict=True
    order=lambda ids:sorted(ids,key=lambda cid:(-metrics[cid]['I'],metrics[cid]['boundary_mean_over_sqrt_ref_area'],cid))
    rank=order(survivors);chosen=rank[0]
    glob=order(labels);gap=metrics[rank[0]]['I']-metrics[rank[1]]['I'] if len(rank)>1 else None
    globalgap=metrics[glob[0]]['I']-metrics[glob[1]]['I'] if len(glob)>1 else None
    if len(labels)==1:reason='one_admitted_unique_floor';uncertainty='not_applicable_single_reference'
    elif len(survivors)==1:reason='local_differentiating_structure';uncertainty='structural_evidence_not_verified_historical_intent'
    elif conflict:reason='conflicting_local_pairwise_votes_floor_iou_fallback';uncertainty='conflict_low_confidence'
    else:
        reason='local_family_then_floor_iou_fallback' if len(survivors)<len(labels) else 'local_evidence_insufficient_floor_iou_fallback'
        uncertainty='low_margin' if gap<cfg['fallback_uncertain_iou_margin'] else 'geometric_fallback_provisional'
    area=sorted(labels,key=lambda cid:(metrics[cid]['abs_log_area_ratio'],cid))
    bound=sorted(labels,key=lambda cid:(metrics[cid]['boundary_mean_over_sqrt_ref_area'],cid))
    return {'candidate_id':chosen,'route_reason':reason,'uncertainty':uncertainty,
        'true_intent_established':False,'surviving_candidates':survivors,'pairwise_local_evidence':votes,
        'survivor_iou_gap':gap,'global_iou_gap':globalgap,'global_iou_best':glob[0],
        'area_only_best':area[0],'area_only_gap':(metrics[area[1]]['abs_log_area_ratio']-metrics[area[0]]['abs_log_area_ratio']) if len(area)>1 else None,
        'boundary_only_best':bound[0],'candidate_floor_metrics':metrics,
        'quality_or_height_used_for_route':False,'route_is_quality_acceptance':False}
