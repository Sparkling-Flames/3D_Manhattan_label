"""Finite paired-path CSP. No image classifier, no truth access, no voter weighting.
Distances are continuous directed polyline Hausdorff distances in R^3, computed
using piecewise quadratic nearest-segment envelopes (floating-point arithmetic).
Local research fork of research/local_path_research_20261005/pro_original/src/
finite_paths.py: complete budget exclusion reasons and deterministic JSON only.
Not wired into annotation, consensus, or automatic deletion.
"""
from __future__ import annotations
import copy, itertools, json, math
from pathlib import Path
from collections import Counter
import numpy as np
from shapely.geometry import Point, Polygon, LineString
from shapely.validation import explain_validity
TOL=1e-9

def dump(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,sort_keys=True)+'\n',encoding='utf-8',newline='\n')

def project(xyz):
    a=np.asarray(xyz,float); rr=np.linalg.norm(a,axis=-1)
    if np.any(rr<=0): raise ValueError('projection_at_camera')
    return np.stack(((np.arctan2(a[...,0],-a[...,2])/(2*np.pi)+.5)%1*1024,
                      (.5-np.arctan2(a[...,1],np.linalg.norm(a[...,[0,2]],axis=-1))/np.pi)*512),-1)

def xyz(path,side):
    p=np.asarray(path['nodes_xz_top'],float)
    return np.c_[p[:,0],p[:,2] if side=='top' else -np.ones(len(p)),p[:,1]]

def point_segments_sq(p,target):
    a=target[:-1]; e=target[1:]-a; den=np.sum(e*e,axis=1)
    t=np.clip(np.sum((p-a)*e,axis=1)/np.maximum(den,1e-30),0,1)
    return np.min(np.sum((p-(a+t[:,None]*e))**2,axis=1))

def real_roots(poly,lo,hi):
    poly=np.asarray(poly,float)
    while len(poly)>1 and abs(poly[-1])<1e-13:poly=poly[:-1]
    if len(poly)<=1:return []
    rr=np.polynomial.polynomial.polyroots(poly)
    return [float(z.real) for z in rr if abs(z.imag)<1e-8 and lo+1e-12<z.real<hi-1e-12]

def directed_path_distance(source,target,return_witness=False):
    """Max_t min_segments distance. Not just max of source vertices.
    For each source segment, clamp breakpoints split each target distance into
    convex quadratics. Pairwise quadratic crossings split the lower envelope;
    its maximum is at a cell endpoint. Includes degenerate target segments.
    """
    s=np.asarray(source,float); tar=np.asarray(target,float)
    if s.ndim!=2 or tar.ndim!=2 or s.shape[1]!=tar.shape[1] or min(len(s),len(tar))<2:
        raise ValueError('polyline_arrays_required')
    if not (np.isfinite(s).all() and np.isfinite(tar).all()):raise ValueError('nonfinite_path')
    best=(-1.,None,None)
    for k,(a,b) in enumerate(zip(s[:-1],s[1:])):
        v=b-a; cuts=[0.,1.]; terms=[]
        for c,d in zip(tar[:-1],tar[1:]):
            e=d-c; ee=float(e@e); ac=a-c
            if ee<1e-24:terms.append((c,e,ee,0.,0.));continue
            q0=float(ac@e/ee);q1=float(v@e/ee)
            if abs(q1)>1e-14:
                cuts += [x for x in (-q0/q1,(1-q0)/q1) if 0<x<1]
            terms.append((c,e,ee,q0,q1))
        cuts=sorted(set(cuts))
        for lo,hi in zip(cuts[:-1],cuts[1:]):
            mid=(lo+hi)/2; polys=[]
            for c,e,ee,q0,q1 in terms:
                if ee<1e-24 or q0+q1*mid<=0:w=a-c;u=v
                elif q0+q1*mid>=1:w=a-(c+e);u=v
                else:w=a-c-q0*e;u=v-q1*e
                polys.append(np.array([w@w,2*(w@u),u@u]))
            events=[lo,hi]
            for i,j in itertools.combinations(range(len(polys)),2):events+=real_roots(polys[i]-polys[j],lo,hi)
            for t in events:
                ds=float(point_segments_sq(a+t*v,tar))
                if ds>best[0]:best=(ds,k,float(t))
    val=math.sqrt(max(0,best[0]));val=0. if val<TOL else val
    return (val,{'source_segment':best[1],'source_parameter':best[2]}) if return_witness else val

def canonical_nodes(nodes):
    a=np.asarray(nodes,float).tolist(); changed=True
    while changed and len(a)>3:
        changed=False
        for i in range(len(a)):
            p,c,n=map(np.array,(a[i-1],a[i],a[(i+1)%len(a)]))
            # x,z,top are affine in 3D; both boundary polylines unchanged.
            e=n-p;den=e@e
            if den>0:
                t=(c-p)@e/den
                if -1e-12<=t<=1+1e-12 and np.linalg.norm(c-(p+t*e))<1e-10:
                    a.pop(i);changed=True;break
    a=[tuple(round(float(v),10) for v in p) for p in a]
    variants=[]
    for seq in (a,a[::-1]):variants += [tuple(seq[i:]+seq[:i]) for i in range(len(seq))]
    return min(variants)

def assemble(domain,choices):
    paths=[s['paths'][q] for s,q in zip(domain['segments'],choices)]
    issues=[]; nodes=[]; edge_sources=[]
    anchors=np.asarray(domain['anchors_xz_top'])
    for i,p in enumerate(paths):
        a=np.asarray(p['nodes_xz_top'])
        if not np.allclose(a[0],anchors[i],atol=1e-12,rtol=0) or not np.allclose(a[-1],anchors[(i+1)%len(anchors)],atol=1e-12,rtol=0):issues.append(f'anchor_mismatch:{i}')
        nodes+=p['nodes_xz_top'][:-1]
        for k in range(len(a)-1):
            edge_sources.append({'segment':i,'path_id':p['id'],'local_edge_index':k,'donors':copy.deepcopy(p['donors']),
             'construction':p['construction'],'start_xz_top':p['nodes_xz_top'][k],'end_xz_top':p['nodes_xz_top'][k+1],'independent_local_evidence':[]})
    arr=np.asarray(nodes);poly=Polygon(arr[:,:2]); geom=[]
    if not poly.is_valid:geom.append(explain_validity(poly))
    if poly.area<=1e-12:geom.append('zero_area')
    if np.any(arr[:,2]<=0):geom.append('top_not_above_camera')
    if len(issues):geom+=issues
    violated=[]
    for rule in domain['incompatibilities']:
        if all(choices[int(j)]==q for j,q in rule['assignments'].items()):violated.append(rule['id'])
    unknown=[]
    for rule in domain.get('unknown_compatibilities',[]):
        if all(choices[int(j)]==q for j,q in rule['assignments'].items()):unknown.append(rule['id'])
    points=[]
    for x,z,h in nodes:points += [project([x,h,z]).tolist(),project([x,-1.,z]).tolist()]
    key=canonical_nodes(nodes) if not geom else None
    return dict(id='C'+''.join(map(str,choices)),choices=list(choices),path_ids=[p['id'] for p in paths],
        nodes_xz_top=None if issues else nodes,points=None if issues else points,
        declared_paths_xz_top=[p['nodes_xz_top'] for p in paths],
        serialization_status='not_joinable_anchor_mismatch' if issues else 'assembled_from_given_paths',
        geometry_valid=not geom,geometry_issues=geom,
        polygon_valid=None if issues else bool(poly.is_valid),camera_inside=bool(poly.contains(Point(0,0))) if poly.is_valid and not issues else None,
        compatibility='incompatible' if violated else ('unresolved' if unknown else 'compatible'),
        violated_constraints=violated,unknown_constraints=unknown,
        admissible=not geom and not violated,area_h2=float(poly.area) if not geom else None,
        pair_count=None if issues else len(nodes),extra_knots=None if issues else len(nodes)-len(anchors),geometry_key=key,
        edges=edge_sources,ring_confirmed=False,voting_role='candidate_not_an_independent_vote')

def path_loss_tables(domain):
    tables=[]
    for s in domain['segments']:
        carrier=s['paths'][s['carrier_index']]
        tables.append([max(directed_path_distance(xyz(carrier,side),xyz(p,side)) for side in ('top','bottom')) for p in s['paths']])
    return tables

def dedup_candidates(rows):
    groups={}
    for c in rows:groups.setdefault(str(c['geometry_key']),[]).append(c)
    return groups

def evidence_prediction(c,probe):
    if not c['geometry_valid']:return None
    if probe['kind']=='occupancy':return bool(Polygon(np.array(c['nodes_xz_top'])[:,:2]).covers(Point(*probe['xz'])))
    if probe['kind']=='wall_top_at_x':
        # Boundary query in known segment (fixed corresponding anchors), not a learned semantic label.
        seg=probe['segment'];x=probe['x'];vals=[]
        for k,e in enumerate(c['edges']):
            if e['segment']!=seg:continue
            a=np.array(c['nodes_xz_top'][k]);b=np.array(c['nodes_xz_top'][(k+1)%len(c['nodes_xz_top'])])
            if abs(b[0]-a[0])>1e-12:
                t=(x-a[0])/(b[0]-a[0])
                if -1e-10<=t<=1+1e-10:vals.append(float(a[2]+t*(b[2]-a[2])))
        if not vals:return None
        return bool(max(vals)>probe['height_threshold_h'])
    raise ValueError('unknown_probe')

def violations(c,evidence,probes):
    groups=set();detail=[]
    for e in evidence:
        if e['status']!='observed':continue
        value=evidence_prediction(c,probes[e['probe_id']])
        if value is None or value!=e['value']:
            groups.add(e['source_group']);detail.append(e['id'])
    return sorted(groups),detail

def policy_select(candidates,domain,policy,evidence=None,probes=None):
    valid=[c for c in candidates if c['admissible']]
    excluded={}; budget=policy.get('budget_h'); kind=policy['kind']
    if kind=='budget_compact':
        eligible=[c for c in valid if max(c['carrier_loss_vector_h'])<=budget+1e-10]
        minimum_knots=min((c['extra_knots'] for c in eligible),default=math.inf)
        chosen=[c for c in eligible if c['extra_knots']==minimum_knots]
        excluded={c['id']:'path_budget_exceeded' for c in valid if c not in eligible}
        excluded.update({c['id']:'eligible_but_more_knots' for c in eligible if c['extra_knots']>minimum_knots})
    elif kind=='carrier_pareto':
        V=np.array([c['observed_loss_vector_h'] for c in valid]); chosen=[]
        for c,v in zip(valid,V):
            dom=np.any(np.all(V<=v+1e-10,axis=1)&np.any(V<v-1e-10,axis=1))
            if not dom:chosen.append(c)
            else:excluded[c['id']]='observed_path_loss_pareto_dominated'
    elif kind=='evidence':
        chosen=[]
        for c in valid:
            g,e=violations(c,evidence,probes)
            if len(g)<=policy['max_wrong_source_groups']:chosen.append(c)
            else:excluded[c['id']]={'source_groups':g,'claims':e}
    else:raise ValueError('unknown_policy')
    groups=dedup_candidates(chosen)
    if not chosen:status='no_feasible_candidate'
    elif len(groups)>1:status='multiple_candidates'
    elif any(c['compatibility']=='unresolved' for c in chosen):status='compatibility_unresolved'
    else:status='single_geometry_conditional'
    local=[]
    for i in range(len(domain['segments'])):
        vals=sorted(set(c['choices'][i] for c in chosen))
        local.append({'segment':i,'possible_path_indices':vals,'status':'no_feasible' if not vals else ('fixed_representation' if len(vals)==1 else 'multiple_representations')})
    return {'policy':policy,'status':status,'candidate_ids':[c['id'] for c in chosen],
        'geometry_count':len(groups),'representation_count':len(chosen),'local_decisions':local,'excluded':excluded,
        'evidence_claims':copy.deepcopy(evidence or []),'support_not_probability':True}

def exhaustive_addition(sizes):
    calls=0;leaves=[]
    def rec(prefix):
        nonlocal calls;calls+=1
        if len(prefix)==len(sizes):leaves.append(tuple(prefix));return
        for q in range(sizes[len(prefix)]):rec(prefix+[q])
    rec([])
    return leaves,{'initialization_atoms':len(sizes),'visited_partial_states':calls,'complete_states':len(leaves)}

def exhaustive_elimination(sizes):
    # Set-valued domains, NOT a geometric room equal to the union of alternatives.
    domains=[tuple(range(n)) for n in sizes];calls=0;removed=0;leaves=[]
    def rec(sets,depth):
        nonlocal calls,removed;calls+=1
        if depth==len(sizes):leaves.append(tuple(s[0] for s in sets));return
        for q in reversed(sets[depth]):
            nxt=list(sets);removed+=len(sets[depth])-1;nxt[depth]=(q,);rec(nxt,depth+1)
    rec(domains,0)
    return leaves,{'initialization_atoms':sum(sizes),'visited_partial_states':calls,'complete_states':len(leaves),
                  'alternative_deletions':removed,'root_is_domain_sets_not_room':True}
