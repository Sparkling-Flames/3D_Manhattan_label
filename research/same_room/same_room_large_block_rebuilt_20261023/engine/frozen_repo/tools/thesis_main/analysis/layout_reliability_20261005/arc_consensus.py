"""Exact-event, all-observer ERP band aggregation (research prototype).

No corner matching, fitted room, GT, semantic clustering or input reordering.
All rings must already traverse longitude monotonically once and straddle the
horizon. The output vertices are paired *representation knots*, not established
physical corners. Constant-height ceiling and solid interior are not assumed.
"""
from __future__ import annotations
import copy
import hashlib
import json
from dataclasses import dataclass
from itertools import combinations
import math
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union

W, H, TAU = 1024., 512., 2*np.pi
EPS = 2e-11  # numerical angle deduplication only, not a matching tolerance

class Unsupported(ValueError):
    pass

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
        allow_nan=True, separators=(',', ':')).encode()).hexdigest()

def rays(p):
    p=np.asarray(p,float)
    u=TAU*(p[...,0]/W-.5); v=np.pi*(.5-p[...,1]/H)
    return np.stack((np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)),axis=-1)

def project(xyz):
    z=np.asarray(xyz,float); norm=np.linalg.norm(z,axis=-1)
    if np.any(norm<=0): raise Unsupported('projection_at_camera')
    return np.stack(((np.arctan2(z[...,0],-z[...,2])/TAU+.5)%1*W,
                     (.5-np.arcsin(np.clip(z[...,1]/norm,-1,1))/np.pi)*H),axis=-1)

def pairs(record):
    try: p=np.asarray(record['points'],float)
    except (KeyError,TypeError,ValueError) as e: raise Unsupported('points_missing_or_invalid') from e
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():
        raise Unsupported('finite_paired_array_required')
    if np.any(p[:,0]<0) or np.any(p[:,0]>W) or np.any(p[:,1]<0) or np.any(p[:,1]>H):
        raise Unsupported('outside_continuous_canvas')
    q=p.reshape(-1,2,2)
    for key,stride in [('source_point_indices',2),('source_pair_indices',1)]:
        values=record.get(key)
        if values is not None and (len(values)!=stride*len(q) or any(type(v) is not int for v in values)):
            raise Unsupported('invalid_source_identity_metadata:'+key)
    if np.any(abs((q[:,0,0]-q[:,1,0]+W/2)%W-W/2)>1e-8):
        raise Unsupported('shared_longitude_required_no_repair')
    return q

def footprint(record):
    q=pairs(record); rr=rays(q[:,1])
    if np.any(rr[:,1]>=-1e-12): raise Unsupported('bottom_not_finite_below_horizon')
    f=(-rr/rr[:,1,None])[:,[0,2]]
    poly=Polygon(f)
    if not poly.is_valid or poly.area<=1e-12: raise Unsupported('invalid_declared_polygon_no_repair')
    return f,poly

def paired_wall_proxy(record):
    q=pairs(record); f,poly=footprint(record)
    rt=rays(q[:,0]); hz=np.linalg.norm(rt[:,[0,2]],axis=1)
    if np.any(hz<1e-12): raise Unsupported('top_at_pole')
    top=rt*(np.linalg.norm(f,axis=1)/hz)[:,None]
    bottom=np.column_stack((f[:,0],-np.ones(len(f)),f[:,1]))
    return top,bottom

@dataclass
class Piece:
    lo: float
    hi: float
    coeff: np.ndarray  # side x (sin(u),cos(u)); u=2pi*x/W
    edge: int
    record: dict
    def value(self,u):
        u=np.asarray(u); return np.einsum('sj,...j->s...',self.coeff,np.stack((np.sin(u),np.cos(u)),axis=-1))

class Ring:
    def __init__(self,record):
        self.record=record; self.q=pairs(record)
        q=self.q
        if np.any(q[:,0,1]<=0) or np.any(q[:,0,1]>=H/2) or np.any(q[:,1,1]<=H/2) or np.any(q[:,1,1]>=H):
            raise Unsupported('strict_horizon_straddling_required')
        u=q[:,0,0]%W/W*TAU
        d=(np.roll(u,-1)-u+np.pi)%TAU-np.pi
        if np.any(abs(d)<EPS) or np.any(abs(d)>=np.pi-EPS):
            raise Unsupported('zero_or_half_turn_longitude_edge')
        if not ((np.all(d>0) or np.all(d<0)) and abs(abs(d.sum())-TAU)<1e-8):
            raise Unsupported('source_ring_not_single_valued_one_turn')
        self.direction=1 if d[0]>0 else -1
        self.foot,self.polygon=footprint(record)
        self.pieces=[]
        for i,span in enumerate(d):
            j=(i+1)%len(q)
            M=np.array([[np.sin(u[i]),np.cos(u[i])],[np.sin(u[j]),np.cos(u[j])]])
            if abs(np.linalg.det(M))<1e-12: raise Unsupported('singular_edge_plane')
            z=np.tan(np.pi*(.5-q[[i,j],:,1]/H))
            C=np.linalg.solve(M,z).T
            lo=float(u[i] if span>0 else u[j]); end=float(u[j] if span>0 else u[i])
            # Use the identical stored endpoint for adjacent pieces, avoiding
            # machine-sized holes at knots from lo + wrapped-span arithmetic.
            if end>lo:
                self.pieces.append(Piece(lo,end,C,i,record))
            else:
                self.pieces.append(Piece(lo,TAU,C,i,record))
                if end>0.: self.pieces.append(Piece(0.,end,C,i,record))
        self.pieces.sort(key=lambda p:p.lo)
        if abs(sum(p.hi-p.lo for p in self.pieces)-TAU)>1e-8:
            raise Unsupported('incomplete_longitude_coverage')
    def active(self,u):
        u=float(u)%TAU
        pp=[p for p in self.pieces if p.lo<=u<p.hi]
        if len(pp)!=1: raise Unsupported('nonunique_active_edge')
        return pp[0]
    def evaluate(self,u):
        a=np.asarray(u,float); flat=a.reshape(-1)%TAU; out=np.empty((2,len(flat)))
        coverage=np.zeros(len(flat),int)
        for p in self.pieces:
            ix=(flat>=p.lo)&(flat<p.hi)
            out[:,ix]=p.value(flat[ix]); coverage[ix]+=1
        if np.any(coverage!=1): raise Unsupported('sampling_coverage_failure')
        return (H*(.5-np.arctan(out)/np.pi)).reshape((2,)+a.shape)

def unique_angles(values):
    out=[]
    for a in sorted(float(x) for x in values):
        if not out or a-out[-1]>EPS: out.append(a)
    return out

def equal_coeff(a,b):
    return np.allclose(a,b,rtol=2e-12,atol=2e-12)

def edge_source(p):
    r=p.record; i=p.edge; m=len(r['points'])//2
    indices=r.get('source_point_indices'); pi=r.get('source_pair_indices')
    return dict(id=r.get('id'),worker=r.get('worker'),edge_pair_indices=[i,(i+1)%m],
        source_pair_indices=None if pi is None else [pi[i],pi[(i+1)%m]],
        source_endpoint_indices=None if indices is None else
           [indices[2*i:2*i+2],indices[2*((i+1)%m):2*((i+1)%m)+2]],
        source_ring_confirmed=r.get('ring_confirmed'),source_order_status=r.get('order_status'))

def arrangement(rings):
    """All source endpoints + all within-piece analytic curve crossings."""
    base=unique_angles([0.,TAU]+[v for r in rings for p in r.pieces for v in (p.lo,p.hi)])
    atoms=[]; min_width=np.inf
    for lo,hi in zip(base[:-1],base[1:]):
        if hi-lo<EPS: continue
        active=[r.active((lo+hi)/2) for r in rings]
        C=np.array([p.coeff for p in active]); cuts=[lo,hi]
        for i,j in combinations(range(len(rings)),2):
            for side in (0,1):
                diff=C[i,side]-C[j,side]
                if np.linalg.norm(diff)<1e-13: continue  # coincident planes, all ties preserved later
                root=math.atan2(-diff[1],diff[0])%np.pi
                for v in (root,root+np.pi):
                    if lo+EPS<v<hi-EPS: cuts.append(v)
        cuts=unique_angles(cuts)
        for a,b in zip(cuts[:-1],cuts[1:]):
            if b-a<=EPS: continue
            atoms.append((a,b,active)); min_width=min(min_width,b-a)
    return atoms,min_width

def selected_piece(active,side,index,u):
    C=np.array([p.coeff[side] for p in active]); val=C@np.array([np.sin(u),np.cos(u)])
    # Descending tan(elevation) == ascending ERP y; no person identifier in selection.
    order=np.argsort(-val,kind='stable'); pick=int(order[index]); ref=C[pick]
    donors=[p for p in active if equal_coeff(p.coeff[side],ref)]
    # A coincident plane is one geometric value, but every observer still votes.
    chosen=min(donors,key=lambda p:tuple(p.coeff[side]))
    return chosen.coeff[side], [edge_source(p) for p in donors]

def serialize(rings,atoms,threshold):
    n=len(rings); selected=[]
    for lo,hi,active in atoms:
        a,sa=selected_piece(active,0,threshold-1,(lo+hi)/2)
        b,sb=selected_piece(active,1,n-threshold,(lo+hi)/2)
        selected.append(dict(lo=lo,hi=hi,coeff=np.array([a,b]),top_sources=sa,bottom_sources=sb))
    # Keep numerical/structural breaks only. Source changes on the same plane remain
    # in 'provenance_intervals', not extra physical corners or extra people.
    changes=[i for i,p in enumerate(selected) if not equal_coeff(p['coeff'],selected[i-1]['coeff'])]
    if len(changes)<3: raise Unsupported('fewer_than_three_representation_knots')
    knots=np.array([selected[i]['lo'] for i in changes]); points=[]
    for u,i in zip(knots,changes):
        y=H*(.5-np.arctan(selected[i]['coeff']@np.array([np.sin(u),np.cos(u)]))/np.pi)
        points.extend([[float(u/TAU*W),float(y[0])],[float(u/TAU*W),float(y[1])]])
    out=dict(id='generated',worker='generated',points=points)
    f,poly=footprint(out)
    out_ring=Ring(out)
    checks=np.array([(p['lo']+p['hi'])/2 for p in selected])
    expected=np.stack([H*(.5-np.arctan(p['coeff']@np.array([np.sin(u),np.cos(u)]))/np.pi)
                       for p,u in zip(selected,checks)],axis=1)
    err=float(np.max(abs(out_ring.evaluate(checks)-expected)))
    if err>2e-6: raise Unsupported('serialization_reprojection_mismatch')
    wall_top,wall_bottom=paired_wall_proxy(out)
    common=0.; nonshared=0.
    provenance=[]
    for p in selected:
        ts={s['worker'] for s in p['top_sources']}; bs={s['worker'] for s in p['bottom_sources']}
        if ts&bs: common+=p['hi']-p['lo']
        else: nonshared+=p['hi']-p['lo']
        provenance.append({k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in p.items()})
    residuals=[]
    for r in rings:
        u=r.q[:,0,0]%W/W*TAU; yy=out_ring.evaluate(u)
        for j,q in enumerate(r.q):
            residuals.append(dict(id=r.record['id'],worker=r.record['worker'],pair_index=j,
                source_points=q.tolist(),generated_top_y=float(yy[0,j]),generated_bottom_y=float(yy[1,j]),
                source_minus_generated_top_px=float(q[0,1]-yy[0,j]),
                source_minus_generated_bottom_px=float(q[1,1]-yy[1,j])))
    knot_provenance=[]
    for k,i in enumerate(changes):
        now=selected[i];before=selected[i-1];u=now['lo'];coincident=[]
        for ring in rings:
            du=(ring.q[:,0,0]/W*TAU-u+np.pi)%TAU-np.pi
            for j in np.flatnonzero(abs(du)<=EPS):
                coincident.append(dict(id=ring.record['id'],worker=ring.record['worker'],pair_index=int(j)))
        knot_provenance.append(dict(index=k,node_type='derived_pair_knot_not_semantic_corner',
            upper_curve_turn=not equal_coeff(now['coeff'][0],before['coeff'][0]),
            lower_curve_turn=not equal_coeff(now['coeff'][1],before['coeff'][1]),
            coincident_source_longitudes=coincident,
            longitude_coincidence_is_not_point_correspondence=True,
            upper_left_sources=before['top_sources'],upper_right_sources=now['top_sources'],
            lower_left_sources=before['bottom_sources'],lower_right_sources=now['bottom_sources']))
    return dict(status='conditional_complete_boundary',n=n,erp_threshold=threshold,knot_provenance=knot_provenance,
        equivalent_bev_threshold=n-threshold+1,points=points,footprint=f.tolist(),
        pair_count=len(knots),ring_confirmed=False,
        representation='paired_boundary_knots_not_semantic_corners',
        connections=[dict(pair_indices=[i,(i+1)%len(knots)],kind='straight_3d_edge_projective_arc') for i in range(len(knots))],
        provenance_intervals=provenance,source_pair_residuals=residuals,
        source_record_ids=[r.record['id'] for r in rings],source_workers=[r.record['worker'] for r in rings],
        shared_top_bottom_donor_longitude_fraction=common/TAU,
        different_top_bottom_donor_longitude_fraction=nonshared/TAU,
        height_proxy=wall_top[:,1].tolist(),bottom_xyz=wall_bottom.tolist(),top_xyz=wall_top.tolist(),
        roof_interior='not_observed_not_assumed',max_serialization_error_px=err,
        geometry_valid=bool(poly.is_valid),camera_inside=bool(poly.contains(__import__('shapely').geometry.Point(0,0))),
        numerical_epsilon_radians=EPS,
        uncertainty='Conditional vote result; no semantic correspondence, common ceiling or unique scene claim. All raw events preserved.')

def fuse(records):
    """Pure current-roster construction; reference fields are never accessed."""
    source=copy.deepcopy(records); rings=[]; failures=[]
    if not isinstance(records,list) or not records: raise ValueError('nonempty_record_list_required')
    for key in ('id','worker'):
        vals=[r.get(key) for r in records]
        if any(v is None or str(v)=='' for v in vals) or len(set(vals))!=len(vals):
            raise ValueError('missing_or_duplicate_'+key)
    for key in ('image','condition','evidence_kind'):
        if any(not r.get(key) for r in records): raise ValueError('explicit_'+key+'_required')
        if len({r[key] for r in records})!=1: raise ValueError('mixed_'+key)
    kinds={r['evidence_kind'] for r in records}
    for r in records:
        reason=None
        if r.get('independent') is not True: reason='independent_vote_not_established'
        if r.get('consensus_eligible') is not True: reason='existing_consensus_eligibility_not_true'
        try:
            if reason: raise Unsupported(reason)
            rings.append(Ring(r))
        except Unsupported as e: failures.append(dict(id=r['id'],worker=r['worker'],reason=str(e)))
    result=dict(schema='exact_arc_envelope_v1',n=len(records),record_ids=[r['id'] for r in records],
        workers=[r['worker'] for r in records],source_coordinate_hash=digest([r.get('points') for r in records]),
        methods={},failures=failures,source_order_modified=False,gt_used=False,evidence_kind=next(iter(kinds)))
    if failures: result['status']='unsupported_entire_selected_roster'; return result
    atoms,width=arrangement(rings); result.update(status='ok_conditional_representation',atomic_intervals=len(atoms),minimum_atomic_width_rad=width)
    for rule,t in (('mv50',(len(rings)+1)//2),('mv_strict',len(rings)//2+1)):
        try: result['methods'][rule]=serialize(rings,atoms,t)
        except Unsupported as e: result['methods'][rule]=dict(status='failed',reason=str(e))
    if any(v.get('status')=='failed' for v in result['methods'].values()):
        result['status']='construction_failure_retained'
    result['bev_mv50_complete_method']='mv_strict' if len(rings)%2==0 else 'mv50'
    if digest(records)!=digest(source): raise AssertionError('input_mutated')
    return result

def tile_vote(records,threshold):
    """Independent polygon arrangement verification, not used to fit arc output."""
    ps=[footprint(r)[1] for r in records]
    faces=list(polygonize(unary_union([p.boundary for p in ps])))
    chosen=[]
    for face in faces:
        p=face.representative_point(); s=sum(g.covers(p) for g in ps)
        if s>=threshold: chosen.append(face)
    return unary_union(chosen)

def area_scores(A,G):
    u=A.union(G).area
    return dict(iou=float(A.intersection(G).area/u) if u else None,
        omission_h2=float(G.difference(A).area),extension_h2=float(A.difference(G).area),
        centroid_distance_h=float(A.centroid.distance(G.centroid)) if A.area and G.area else None,
        reference_area_h2=float(G.area),candidate_area_h2=float(A.area))
