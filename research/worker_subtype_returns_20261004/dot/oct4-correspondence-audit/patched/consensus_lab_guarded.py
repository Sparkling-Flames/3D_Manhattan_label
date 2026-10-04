"""GT-free, observed-ring-anchored panorama consensus research prototype.

No input sorting by longitude, eligibility recovery, raw-point repair or reference
selection is performed. Circular shifts/reversal change correspondence only.
Input: continuous 1024 x 512, alternating top/bottom, preprocessed shared x.
New coordinates NEVER inherit human confirmation of an input ring.
"""
from __future__ import annotations
from collections import defaultdict
from itertools import combinations
import math
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from shapely.geometry import Polygon

W,H=1024.,512.
BLOCK=181.0

def wrap(x): return (np.asarray(x)+W/2)%W-W/2

def explicit_connections(m):
    return dict(index_base=0,point_array='points',pair_ring=list(range(m)),closed=True,
      top_edges=[[2*i,2*((i+1)%m)] for i in range(m)],
      bottom_edges=[[2*i+1,2*((i+1)%m)+1] for i in range(m)],
      vertical_pairs=[[2*i,2*i+1] for i in range(m)],
      confirmation='derived_connections_not_new_human_confirmation')

def eligibility_reason(r):
    """Synthetic controls are a separate evidence population, never real votes."""
    if r.get('synthetic') is True:return None
    if r.get('independent') is None:return 'independent_status_unavailable_do_not_promote'
    if r.get('independent') is not True:return 'not_independent_do_not_restore'
    if r.get('consensus_eligible') is None:return 'consensus_eligibility_unavailable_do_not_promote'
    if r.get('consensus_eligible') is not True:return 'not_consensus_eligible_do_not_restore'
    if r.get('borrowed_points') is True:return 'borrowed_points_not_independent_vote'
    return None

def pairs(record):
    if record.get('points') is None: raise ValueError('pairing_unavailable')
    p=np.asarray(record['points'],float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():
        raise ValueError('invalid_finite_paired_points')
    if np.any(p<0) or np.any(p[:,0]>W) or np.any(p[:,1]>H):
        raise ValueError('outside_continuous_canvas')
    a=p.reshape(-1,2,2)
    if np.any(abs(wrap(a[:,0,0]-a[:,1,0]))>1e-8) or np.any(a[:,0,1]>=a[:,1,1]):
        raise ValueError('invalid_preprocessed_pair')
    s=record.get('source_pair_indices')
    if s is not None and (len(s)!=len(a) or len(set(s))!=len(s)):
        raise ValueError('invalid_source_pair_identity')
    return a

def angular(a,b):
    """All-pairs spherical angles, directly in the CURRENT continuous frame."""
    a,b=np.asarray(a,float),np.asarray(b,float)
    du=wrap(a[:,None,0]-b[None,:,0])*2*np.pi/W
    va=(a[:,1]/H-.5)*np.pi;vb=(b[:,1]/H-.5)*np.pi
    q=np.clip(np.sin((va[:,None]-vb[None,:])/2)**2+
              np.cos(va[:,None])*np.cos(vb[None,:])*np.sin(du/2)**2,0,1)
    return np.degrees(2*np.arctan2(np.sqrt(q),np.sqrt(1-q)))

def costs(a,b,role='bound'):
    t=angular(a[:,0],b[:,0]);d=angular(a[:,1],b[:,1])
    return t if role=='top' else d if role=='bottom' else np.maximum(t,d)

def full_alignment(a,b,role='bound'):
    if len(a)!=len(b): return dict(distance=BLOCK,mapping=None,margin=None,ambiguous=False)
    c=costs(a,b,role);m=len(a);opts={}
    for order in (np.arange(m),np.arange(m)[::-1]):
        for s in range(m):
            ix=tuple(int(v) for v in np.roll(order,-s))
            opts[ix]=float(c[np.arange(m),ix].max())
    z=sorted((v,k) for k,v in opts.items());best=z[0]
    margin=z[1][0]-best[0] if len(z)>1 else math.inf
    return dict(distance=best[0],mapping=list(best[1]),margin=margin,ambiguous=margin<=1e-9)

def _rank_paths(values, limit=2):
    # Distinct match maps, not different orders of skip operations.
    best={}
    for count,cost,path in values:
        if path not in best or cost<best[path][1]: best[path]=(count,cost,path)
    return sorted(best.values(),key=lambda z:(-z[0],z[1],z[2]))[:limit]

def partial_alignment(a,b,tolerance=5.,role='bound',ambiguity_margin=1e-9):
    """Exact best/two-best circular, order-preserving INJECTIVE partial maps.

    Objective is lexicographic: maximize matched pairs within tolerance, then
    minimize SUM of matched angular errors. All unmatched pairs remain explicit.
    This is an exploratory objective, NOT a calibrated identity model.
    """
    c=costs(a,b,role);m,n=c.shape;options=[]
    for order in (np.arange(n),np.arange(n)[::-1]):
        for shift in range(n):
            ix=np.roll(order,-shift);dp=[[[] for _ in range(n+1)] for _ in range(m+1)]
            dp[0][0]=[(0,0.,())]
            for i in range(m+1):
                for j in range(n+1):
                    if not (i or j):continue
                    vals=[]
                    if i:vals.extend(dp[i-1][j])
                    if j:vals.extend(dp[i][j-1])
                    if i and j and c[i-1,ix[j-1]]<=tolerance+1e-10:
                        vals.extend((k+1,e+float(c[i-1,ix[j-1]]),p+((i-1,int(ix[j-1])),))
                                    for k,e,p in dp[i-1][j-1])
                    dp[i][j]=_rank_paths(vals)
            options.extend(dp[m][n])
    bests=_rank_paths(options)
    count,score,mapping=bests[0]
    comparable=len(bests)>1 and bests[1][0]==count
    gap=bests[1][1]-score if comparable else None
    match=dict(mapping)
    return dict(matched=count,sum_angle=score,mapping=[list(v) for v in mapping],
      unmatched_anchor=[i for i in range(m) if i not in match],
      unmatched_other=[j for j in range(n) if j not in match.values()],
      runner_up_mapping=[list(v) for v in bests[1][2]] if comparable else None,
      margin=gap,ambiguous=(gap is not None and gap<=ambiguity_margin),
      tolerance=tolerance,objective='maximum_cardinality_then_minimum_sum_bound_angle')

def periodic_center(stack,anchor):
    a=np.asarray(stack);c=np.median(a,axis=0)
    x=(anchor[:,0,0]+np.median(wrap(a[:,:,0,0]-anchor[:,0,0]),axis=0))%W
    c[:,:,0]=x[:,None]
    return c

def footprint(record):
    a=pairs(record);yb=a[:,1,1]
    if np.any(yb<=H/2) or np.any(yb>=H):raise ValueError('bottom_not_projectable_to_common_floor')
    r=1/np.tan(np.pi*(yb/H-.5));theta=2*np.pi*(a[:,1,0]/W-.5)
    return np.c_[r*np.sin(theta),-r*np.cos(theta)]

def polygon(record):
    p=Polygon(footprint(record))
    if not p.is_valid or p.area<=1e-12:raise ValueError('invalid_or_degenerate_original_ring_polygon')
    return p

def iou(a,b):
    u=a.union(b).area
    return float(a.intersection(b).area/u) if u else float('nan')

def ray(p):
    p=np.asarray(p);t=2*np.pi*(p[...,0]/W-.5);v=np.pi*(.5-p[...,1]/H)
    return np.stack((np.cos(v)*np.sin(t),np.sin(v),-np.cos(v)*np.cos(t)),axis=-1)

def edge_y(p,q,x):
    normal=np.cross(ray(p),ray(q));x=np.asarray(x,float)
    if abs(normal[1])<1e-12:raise ValueError('singular_edge_plane')
    theta=2*np.pi*(x/W-.5)
    z=-(normal[0]*np.sin(theta)-normal[2]*np.cos(theta))/normal[1]
    return H*(.5-np.arctan(z)/np.pi)

def band(record,samples=512,x=None):
    """Original-ring central-projection wall band, no x reordering."""
    a=pairs(record)
    if np.any(a[:,0,1]<=0) or np.any(a[:,0,1]>=H/2) or np.any(a[:,1,1]<=H/2) or np.any(a[:,1,1]>=H):
        raise ValueError('boundaries_do_not_strictly_straddle_horizon')
    u=a[:,0,0]%W;d=wrap(np.roll(u,-1)-u)
    if np.any(abs(d)<1e-8) or np.any(abs(d)>=W/2-1e-8):raise ValueError('zero_or_half_turn_edge')
    if not ((d>0).all() or (d<0).all()) or abs(abs(d.sum())-W)>1e-7:
        raise ValueError('original_ring_not_single_valued_one_turn')
    direction=1 if d[0]>0 else -1
    x=(np.arange(samples)+.5)*W/samples if x is None else np.asarray(x,float)%W
    v=np.full((2,len(x)),np.nan);cover=np.zeros(len(x),int)
    for i,dx in enumerate(d):
        progress=(direction*(x-u[i]))%W
        progress[np.isclose(progress,W,rtol=0,atol=1e-8)]=0
        active=(progress<abs(dx)) & ~np.isclose(progress,abs(dx),rtol=0,atol=1e-8)
        cover[active]+=1
        for side in (0,1):v[side,active]=edge_y(a[i,side],a[(i+1)%len(a),side],x[active])
    if np.any(cover!=1) or not np.isfinite(v).all():raise ValueError('missing_or_multiple_column_branches')
    if np.any(v[0]>=H/2) or np.any(v[1]<=H/2):raise ValueError('projected_band_not_straddling_horizon')
    return x,v

def majority(records,samples=512,strict=True):
    # Deliberately propagates unsupported status of ANY roster member.
    arrays=[band(r,samples)[1] for r in records]
    a=np.asarray(arrays);n=len(a);q=n//2+1 if strict else (n+1)//2
    return np.array([np.sort(a[:,0],axis=0)[q-1],np.sort(a[:,1],axis=0)[n-q]])

def band_iou(a,b):
    inter=np.maximum(0,np.minimum(a[1],b[1])-np.maximum(a[0],b[0])).sum()
    union=(np.maximum(a[1],b[1])-np.minimum(a[0],b[0])).sum()
    return float(inter/union)

def full_distance_matrix(records):
    a=[pairs(r) for r in records];d=np.zeros((len(a),len(a)))
    for i,j in combinations(range(len(a)),2):d[i,j]=d[j,i]=full_alignment(a[i],a[j])['distance']
    return d

def complete_groups(d,threshold):
    if len(d)<2:return [list(range(len(d)))] if len(d) else []
    labs=fcluster(linkage(squareform(d,checks=True),method='complete'),threshold,criterion='distance')
    return [np.flatnonzero(labs==k).tolist() for k in sorted(set(labs))]

def baseline_candidates(records,tolerance=5.):
    records=sorted(records,key=lambda r:str(r['id']));d=full_distance_matrix(records);out=[]
    for ids in complete_groups(d,tolerance):
        subset=[records[i] for i in ids];local=d[np.ix_(ids,ids)]
        anchor=subset[int(local.sum(axis=1).argmin())];ap=pairs(anchor);stack=[];amb=False
        for r in subset:
            align=full_alignment(ap,pairs(r));amb|=align['ambiguous'];stack.append(pairs(r)[align['mapping']])
        c=periodic_center(stack,ap)
        out.append(dict(anchor=anchor['id'],members=[r['id'] for r in subset],
          support=len(subset),diameter=float(local.max()),points=c.reshape(-1,2).tolist(),
          ring_confirmed=False,status='ambiguous' if amb else 'ok',order_status='derived_from_representative_ring'))
    return dict(groups=out,distance_matrix=d.tolist(),tolerance=tolerance)

def derive_candidates(records,tolerance=5.,ambiguity_margin=1e-9):
    """Overlapping OBSERVED anchor ring hypotheses with a per-point/edge ledger.

    No cluster chosen as winner. Pair-count differences do not force total
    incompatibility; all anchor rings and all unmatched observations survive.
    Conditional partial donors are not whole-ring votes. No physical correctness
    or calibrated probability is inferred from numerical agreement.
    """
    if not records:raise ValueError('empty_roster')
    records=sorted(records,key=lambda r:str(r['id']))
    for key in ('id','worker'):
        if any(key not in r for r in records) or len({str(r[key]) for r in records})!=len(records):
            raise ValueError('missing_or_duplicate_'+key)
    errors=[];available=[]
    for r in records:
        try:
            pairs(r)
            reason=eligibility_reason(r)
            if reason:raise ValueError(reason)
            available.append(r)
        except ValueError as e:errors.append(dict(id=r['id'],worker=r['worker'],reason=str(e)))
    out=[]
    for anchor in available:
        ap=pairs(anchor);m=len(ap);donors=[[] for _ in range(m)];edges=[[] for _ in range(m)];paths=[[] for _ in range(m)]
        mappings=[];whole=[]
        for r in available:
            bp=pairs(r)
            match=(dict(mapping=[[i,i] for i in range(m)],matched=m,unmatched_anchor=[],unmatched_other=[],margin=None,ambiguous=False)
                   if r['id']==anchor['id'] else partial_alignment(ap,bp,tolerance,ambiguity_margin=ambiguity_margin))
            mappings.append(dict(id=r['id'],worker=r['worker'],**match))
            if match['ambiguous']:continue
            mapping=dict(match['mapping'])
            for i,j in mapping.items():
                donors[i].append(dict(id=r['id'],worker=r['worker'],index=j,
                    source_pair_index=(r.get('source_pair_indices') or list(range(len(bp))))[j],
                    synthetic=r.get('synthetic',False),independent_status=r.get('independent'),
                    source_point_indices=(r.get('source_point_indices') or [])[2*j:2*j+2] or None,
                    source_point_labels=(r.get('source_point_labels') or [])[2*j:2*j+2] or None,
                    points=bp[j].tolist()))
            for i in range(m):
                k=(i+1)%m
                if i in mapping and k in mapping:
                    ja,jb=mapping[i],mapping[k]
                    witness=dict(id=r['id'],worker=r['worker'],source_indices=[ja,jb])
                    if (ja-jb)%len(bp) in (1,len(bp)-1):edges[i].append(witness)
                    else:paths[i].append(witness)
            if len(mapping)==m==len(bp):whole.append(dict(id=r['id'],worker=r['worker']))
        c=ap.copy()
        for i,values in enumerate(donors):
            vs=np.asarray([v['points'] for v in values]);c[i]=np.median(vs,axis=0)
            cx=(ap[i,0,0]+np.median(wrap(vs[:,0,0]-ap[i,0,0])))%W;c[i,:,0]=cx
        candidate=dict(id='candidate@'+str(anchor['id']),anchor=anchor['id'],points=c.reshape(-1,2).tolist(),connections=explicit_connections(m),
            ring_confirmed=False,order_status='new_geometry_on_observed_anchor_ring_not_human_confirmed',
            source_anchor_ring_confirmed=anchor.get('ring_confirmed'),point_donors=donors,
            point_support_counts=[len(v) for v in donors],direct_edge_witnesses=edges,
            endpoint_connection_with_intermediate_pairs=paths,
            complete_ring_mapping_witnesses=whole,alignments=mappings,
            warning='point donors / edge witnesses / complete ring mapping witnesses are different denominators; generated coordinates were not jointly drawn')
        try:
            poly=polygon(candidate);candidate['geometry']={'polygon_valid':True,'area_h2':float(poly.area),'scope':'floor_polygon_only_not_closed_3D_validation'}
        except ValueError as e:candidate['geometry']={'polygon_valid':False,'reason':str(e)}
        try:band(candidate);candidate['band_status']='available'
        except ValueError as e:candidate['band_status']=str(e)
        out.append(candidate)
    return dict(schema='observed_anchor_evidence_v1',n_requested=len(records),n_available=len(available),
      evidence_populations={'real_record_slots':sum(r.get('synthetic') is not True for r in records),'synthetic_control_slots':sum(r.get('synthetic') is True for r in records)},
      failures=errors,status='partial_method_coverage' if errors else 'candidate_set_not_adjudicated',
      tolerance_deg=tolerance,ambiguity_margin_deg=ambiguity_margin,candidates=out,
      historical_cross_record_constraints_loaded=False,
      interpretation='overlapping anchor hypotheses; do not sum supports or interpret as posterior modes; historical cross-record constraints require a locally verified adapter')

def from_floor(xy,height=2.5,worker='synthetic',rid=None):
    xy=np.asarray(xy,float);r=np.linalg.norm(xy,axis=1)
    t=np.arctan2(xy[:,0],-xy[:,1]);x=(t/(2*np.pi)+.5)*W
    yt=H*(.5-np.arctan2(height-1,r)/np.pi);yb=H*(.5+np.arctan2(1,r)/np.pi)
    p=np.stack((np.c_[x,yt],np.c_[x,yb]),axis=1).reshape(-1,2)
    return dict(id=rid or worker,worker=worker,points=p.tolist(),source_pair_indices=list(range(len(xy))),
                ring_confirmed=False,order_status='synthetic_declared_ring',synthetic=True,independent=None,
                evidence_role='controlled_example_not_additional_independent_humans')

def insert_subdivision(record,edge=0,fraction=.5,upper_delta_px=0.,worker='synthetic_subdivision'):
    a=pairs(record);i=edge;j=(i+1)%len(a);x=(a[i,0,0]+float(wrap(a[j,0,0]-a[i,0,0]))*fraction)%W
    extra=np.array([[x,float(edge_y(a[i,0],a[j,0],[x])[0])+upper_delta_px],
                    [x,float(edge_y(a[i,1],a[j,1],[x])[0])]])
    p=np.insert(a,i+1,extra,axis=0)
    return dict(id=worker,worker=worker,points=p.reshape(-1,2).tolist(),source_pair_indices=list(range(len(p))),
      order_status='synthetic_edge_subdivision',ring_confirmed=False,synthetic=True,independent=None,
      evidence_role='transformed_observation_not_an_additional_independent_human',
      transformation={'source':record['id'],'edge':edge,'fraction':fraction,'upper_delta_px':upper_delta_px})

def cycle_audit(records,tolerance=5.):
    """Tests *defined* full circular correspondences, not missing/partial maps.
    This is an algebraic audit, not a visual identity determination.
    """
    maps={};comparisons=[]
    for i,j in combinations(range(len(records)),2):
        z=full_alignment(pairs(records[i]),pairs(records[j]))
        comparisons.append(dict(a=records[i]['id'],b=records[j]['id'],**z))
        if z['mapping'] is not None and not z['ambiguous'] and z['distance']<=tolerance:
            maps[i,j]=z['mapping'];maps[j,i]=np.argsort(z['mapping']).tolist()
    conflicts=[];tested=0
    for i,j,k in combinations(range(len(records)),3):
        if not all(edge in maps for edge in [(i,j),(j,k),(i,k)]):continue
        tested+=1;via=[maps[j,k][p] for p in maps[i,j]];direct=maps[i,k]
        if via!=direct:conflicts.append(dict(ids=[records[a]['id'] for a in (i,j,k)],via=via,direct=direct))
    all_pairs=len(maps)//2==len(records)*(len(records)-1)//2
    return dict(comparisons=comparisons,all_pairs_compatible_and_unique=all_pairs,
                tested_triangles=tested,conflicts=conflicts,
                interpretation='No tested conflict is not evidence of consistency when maps or triangles are missing.')

def conditional_decision(records,result=None,tolerance=5.):
    """A limited computational certificate, NEVER a calibrated semantic verdict.

    A single candidate is allowed only for a full pairwise-compatible, uniquely
    and cycle-consistently matched equal-count group, valid fused geometry,
    tolerance-bounded residuals to every member and no failed roster members.
    Everything else retains anchor alternatives or a missingness state.
    """
    records=sorted(records,key=lambda r:str(r['id']))
    result=derive_candidates(records,tolerance) if result is None else result
    if result['failures']:
        return dict(status='unresolved_method_coverage',single_candidate=None,
                    reason='failed_or_ineligible_members_remain_in_denominator')
    if len(records)==1:
        return dict(status='single_observation_not_multiworker_consensus',single_candidate=result['candidates'][0])
    audit=cycle_audit(records,tolerance)
    if audit['conflicts']:
        return dict(status='unresolved_global_correspondence',single_candidate=None,cycle_audit=audit)
    if not audit['all_pairs_compatible_and_unique']:
        return dict(status='retain_alternatives_or_correspondence_uncertainty',single_candidate=None,cycle_audit=audit)
    if any(not c['geometry']['polygon_valid'] for c in result['candidates']):
        return dict(status='unresolved_fused_geometry',single_candidate=None,cycle_audit=audit)
    d=full_distance_matrix(records);anchor=records[int(d.sum(axis=1).argmin())]['id']
    c=next(c for c in result['candidates'] if c['anchor']==anchor)
    # Audit-only fail-closed guard: bind the certificate to the exact maps
    # that produced this candidate. This does not choose a semantic winner.
    m=len(pairs(c));actual={a['id']:a for a in c['alignments']};map_arrays={}
    disagreements=[]
    for r in records:
        row=actual.get(r['id'])
        if row is None or row.get('ambiguous') or len(row.get('mapping',[]))!=m:
            return dict(status='unresolved_actual_mapping_certificate_mismatch',single_candidate=None,
                        reason='candidate_missing_complete_unambiguous_member_mapping')
        mapping=dict(row['mapping']);ix=[mapping.get(i) for i in range(m)]
        expected=full_alignment(pairs(next(r0 for r0 in records if r0['id']==anchor)),pairs(r))
        if ix!=expected['mapping']:
            disagreements.append(dict(id=r['id'],actual_mapping=ix,certified_mapping=expected['mapping']))
        map_arrays[r['id']]=np.asarray(ix,dtype=int)
    induced=[]
    for ra,rb in combinations(records,2):
        distance=float(costs(pairs(ra),pairs(rb))[map_arrays[ra['id']],map_arrays[rb['id']]].max())
        induced.append(dict(a=ra['id'],b=rb['id'],distance=distance))
    if disagreements or any(v['distance']>tolerance+1e-9 for v in induced):
        return dict(status='unresolved_actual_mapping_certificate_mismatch',single_candidate=None,
                    mapping_disagreements=disagreements,actual_induced_pair_errors_deg=induced,cycle_audit=audit)
    residuals=[float(costs(pairs(c),pairs(r))[np.arange(m),map_arrays[r['id']]].max()) for r in records]
    if max(residuals)>tolerance+1e-9:
        return dict(status='unresolved_generated_candidate_residual',single_candidate=None,residuals_deg=residuals)
    return dict(status='single_candidate_conditional_on_method_tolerance',single_candidate=c,
        cycle_audit=audit,residuals_deg=residuals,
        qualification='not a unique true layout, not validated semantic equivalence, not a sufficient sample-size claim; alternatives and tolerance sensitivity must remain available')

def joint_ring_alignment(records,tolerance=5.,max_states=100000):
    """Exact small-roster synchronization of whole-ring index correspondences.

    Fix the first (ID-sorted) record as a gauge. Enumerate every circular/reversal
    map for the rest. Require ALL pair errors under their INDUCED global mapping
    to satisfy the same tolerance. Score = sum of pairwise bottleneck errors;
    retain all tied optima. Pairwise score is NOT a likelihood/independent votes.
    Original spatial adjacency of each record is never modified.
    """
    from itertools import product
    records=sorted(records,key=lambda r:str(r['id']));n=len(records)
    if not n:raise ValueError('empty_roster')
    if len({r['worker'] for r in records})!=n:raise ValueError('duplicate_worker')
    rejected=[dict(id=r['id'],reason=eligibility_reason(r)) for r in records if eligibility_reason(r)]
    if rejected:return dict(status='unavailable_eligibility',failures=rejected,n_requested=n)
    a=[pairs(r) for r in records];m=len(a[0])
    if any(len(p)!=m for p in a):return dict(status='unsupported_different_pair_counts')
    orders=sorted(set(tuple(int(x) for x in np.roll(o,-s)) for o in (np.arange(m),np.arange(m)[::-1]) for s in range(m)))
    states=len(orders)**(n-1)
    if states>max_states:return dict(status='budget_exceeded_no_exact_result',states_required=states,budget=max_states)
    cs={(i,j):costs(a[i],a[j]) for i,j in combinations(range(n),2)}
    feasible=[]
    for rest in product(orders,repeat=n-1):
        maps=(tuple(range(m)),)+rest;errors=[]
        for (i,j),c in cs.items():
            errors.append(float(c[np.array(maps[i]),np.array(maps[j])].max()))
        if errors and max(errors)>tolerance+1e-9:continue
        feasible.append(dict(score=sum(errors),maps=maps,pair_errors=errors))
    feasible.sort(key=lambda z:(z['score'],z['maps']))
    if not feasible:return dict(status='no_joint_alignment_within_tolerance',states_enumerated=states,tolerance=tolerance)
    optimum=feasible[0]['score'];best=[z for z in feasible if abs(z['score']-optimum)<=1e-9];candidates=[]
    for z in best:
        stack=[p[list(ix)] for p,ix in zip(a,z['maps'])];center=periodic_center(stack,a[0])
        c=dict(points=center.reshape(-1,2).tolist(),connections=explicit_connections(m),ring_confirmed=False,
            order_status='coordinate_median_under_joint_correspondence_on_observed_ring',
            source_pair_maps=[dict(id=r['id'],worker=r['worker'],indices=list(ix)) for r,ix in zip(records,z['maps'])],
            point_support_counts=[n]*m,score=z['score'],induced_pair_errors_deg=z['pair_errors'])
        try:c['floor_polygon_valid']=polygon(c).is_valid
        except ValueError:c['floor_polygon_valid']=False
        candidates.append(c)
    return dict(status='multiple_joint_optima' if len(best)>1 else 'unique_joint_objective_optimum_not_semantic_certainty',
        states_enumerated=states,feasible_count=len(feasible),optimal_count=len(best),best_score=optimum,
        next_distinct_score_gap=next((z['score']-optimum for z in feasible if z['score']>optimum+1e-9),None),
        feasible_assignments=feasible,candidates=candidates,tolerance=tolerance,
        objective='sum_pairwise_max_bound_angles_subject_to_global_pairwise_diameter; equal pair weights; not a statistical likelihood',
        warning='even a unique numerical optimum is not calibrated identity confidence; subset-only search; small-roster same-count scope')
