"""Search-only turn-event domain. Does not change identities, votes or source rings."""
from __future__ import annotations
import copy, hashlib, json, math, sys
from collections import Counter
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent/'oct6-structure-intake/extracted/structure_paths_20261006'
SOURCE = Path(__import__('os').environ.get('STRUCTURE_SOURCE', DEFAULT_SOURCE))
sys.path.insert(0, str(SOURCE/'src'))
from baseline import key, nodes_from_records, distances
from frechet import rays, angle, arc_length, spherical_check
from structure import PathBank

POLICY = json.loads((HERE/'frozen_policy.json').read_text())
CONFIG = {"source_path_edge_counts": [1, 2],
          "maximum_side_path_length_deg": POLICY['maximum_side_path_length_deg'],
          "sphere_approximation_steps_deg": POLICY['sphere_approximation_steps_deg']}


def sides_for(metric):
    return ['top', 'bottom'] if metric == 'pair' else [metric]


def event_map(record, metric, policy=POLICY):
    """Exact ideal rule: oriented tangent changes. Numeric rule is explicitly bounded.

    Antiparallel motion is a turn, not a removable subdivision. Degenerate arcs
    are unresolved and are never silently collapsed. All raw vertices remain.
    """
    q = np.asarray(record['points'], float).reshape(-1, 2, 2)
    out = {'events': [], 'vertices': [], 'status': 'resolved_numeric_domain',
           'all_source_vertices_retained': True, 'metric': metric}
    data = {}
    for s in sides_for(metric):
        V = rays(q[:, 0 if s == 'top' else 1])
        lengths = angle(V, np.roll(V, -1, axis=0))
        normals = np.cross(V, np.roll(V, -1, axis=0))
        norm = np.linalg.norm(normals, axis=1)
        issues = []
        for i, length in enumerate(lengths):
            if length <= policy['minimum_resolved_edge_length_deg']:
                issues.append({'edge': i, 'reason': 'zero_or_near_zero_arc', 'length_deg': float(length)})
            elif length >= 180-policy['antipodal_exclusion_margin_deg']:
                issues.append({'edge': i, 'reason': 'near_antipodal_arc', 'length_deg': float(length)})
        if issues:
            out['status'] = 'unresolved_degenerate_domain'
        data[s] = {'lengths': lengths, 'normals': normals / np.maximum(norm[:, None], 1e-300), 'issues': issues}
    out['edge_issues'] = {s: d['issues'] for s,d in data.items()}
    for i in range(len(q)):
        turns = {s: float(angle(d['normals'][(i-1)%len(q)], d['normals'][i])) for s,d in data.items()}
        active = [s for s,a in turns.items() if a > policy['numerical_collinearity_tolerance_deg']]
        # Very near this numeric classification boundary is not certified invariant.
        near = [s for s,a in turns.items() if policy['numerical_collinearity_tolerance_deg']/10 <= a <= policy['numerical_collinearity_tolerance_deg']*10]
        if near and out['status'] == 'resolved_numeric_domain':
            out['status'] = 'unresolved_near_collinearity_threshold'
        if active:
            out['events'].append(i)
        out['vertices'].append({'processed_pair_index': i, 'turn_deg': turns,
                                'event_sides': active, 'near_tolerance_sides': near})
    return out


class EventBank(PathBank):
    def __init__(self, records, nodes, config=CONFIG):
        super().__init__(records, nodes, config)
        self.event_maps = {}
        self.domain_cache = {}

    def domain(self, ni, direction, metric):
        cache_key = ni, direction, metric
        if cache_key in self.domain_cache:
            return self.domain_cache[cache_key]
        node = self.nodes[ni]; r = self.records[node['id']]
        ek = node['id'], metric
        if ek not in self.event_maps:
            self.event_maps[ek] = event_map(r, metric)
        em = self.event_maps[ek]
        result = {'status': em['status'], 'endpoint_edge_counts': [], 'excluded': [],
                  'event_processed_indices': em['events']}
        if em['status'] != 'resolved_numeric_domain':
            self.domain_cache[cache_key] = result
            return result
        events = set(em['events']); n = len(r['points'])//2
        for edges in range(1, n):
            p = self.get(ni, direction, edges)
            idx = p['processed_pair_indices'][-1]
            maximum = max(p['spherical_lengths_deg'][s] for s in sides_for(metric))
            if maximum > self.config['maximum_side_path_length_deg']:
                result['excluded'].append({'processed_pair_index': idx, 'edge_count': edges,
                                          'reason': 'arc_length_cap', 'maximum_compared_side_deg': maximum})
                break  # lengths are nonnegative; no later endpoint can re-enter this domain
            if idx in events:
                result['endpoint_edge_counts'].append(edges)
            else:
                result['excluded'].append({'processed_pair_index': idx, 'edge_count': edges,
                                          'reason': 'nonturn_search_position_only_source_retained'})
        self.domain_cache[cache_key] = result
        return result

    def witness(self, i, j, metric, g, D):
        base = dict(nodes=[i,j], focal_distance_deg=float(D[metric][i,j]), metric=metric, gate_deg=g,
                    search_policy='turn_events_with_arc_length_cap', focal_observations_retained=True,
                    joint_top_bottom_interior_pairing_inferred=False, identity_certified=False)
        if self.nodes[i]['worker'] == self.nodes[j]['worker']:
            return dict(base, status='same_person', legs=[], witnesses=[])
        if D[metric][i,j] > g+1e-10:
            return dict(base, status='focal_outside_gate', legs=[], witnesses=[])
        domains = {(u,d): self.domain(u,d,metric) for u in (i,j) for d in (-1,1)}
        public_domains = [{'node': u, 'direction': d, **v} for (u,d),v in domains.items()]
        if any(d['status'] != 'resolved_numeric_domain' for d in domains.values()):
            return dict(base, status='domain_unresolved', domains=public_domains, legs=[], witnesses=[])
        legs=[]; witnesses=[]; uncertain=False
        ni=len(self.records[self.nodes[i]['id']]['points'])//2
        nj=len(self.records[self.nodes[j]['id']]['points'])//2
        for orient in (1,-1):
            batches={}
            for da in (-1,1):
                batch=[]
                for ea in domains[(i,da)]['endpoint_edge_counts']:
                    for eb in domains[(j,da*orient)]['endpoint_edge_counts']:
                        res=self.leg(i,j,da,da*orient,ea,eb,metric,g,D)
                        res.update(orientation=orient,side_of_focal=da)
                        batch.append(len(legs));legs.append(res)
                batches[da]=batch
            for a in batches[-1]:
                for b in batches[1]:
                    left,right=legs[a],legs[b]
                    if left['steps'][0]+right['steps'][0]>=ni or left['steps'][1]+right['steps'][1]>=nj:
                        continue
                    if left['status'] in ('accept','undetermined') and right['status'] in ('accept','undetermined'):
                        if 'undetermined' in (left['status'],right['status']): uncertain=True
                        else:
                            witnesses.append({'orientation':orient,'leg_indices':[a,b],
                                              'raw_path_donors':[self.nodes[i]['worker'],self.nodes[j]['worker']],
                                              'interior_point_identities_inferred':False})
        return dict(base,status='witnessed' if witnesses else 'numerically_unresolved' if uncertain else 'not_witnessed',
                    domains=public_domains,legs=legs,witnesses=witnesses,
                    interpretation='geometric_search_candidate_only; absence is unknown, never a semantic cannot-link')


def subdivide(record, factor):
    """Metamorphic same-record probe; insert shared-longitude samples on both arcs.

    The two boundaries may use DIFFERENT fractions. This is interpolation for a
    probe, not inferred cross-record or physical interior top/bottom identities.
    Every original point is copied exactly. Reject ambiguous interpolation.
    """
    if factor == 1:
        r=copy.deepcopy(record)
        r['_probe_original_pair_indices']=list(range(len(r['points'])//2))
        return r, {'factor':1,'maximum_arc_additivity_error_deg':0.,'source_originals_unchanged':True}
    q=np.asarray(record['points'],float).reshape(-1,2,2); n=len(q); inserted=[]; provenance=[]
    sp=[]; sip=[]; maximum=0.
    for k in range(n):
        a=q[k];b=q[(k+1)%n]; aa=rays(a);bb=rays(b)
        dx=(b[0,0]-a[0,0]+512)%1024-512
        if abs(abs(dx)-512)<1e-8:
            raise ValueError('ambiguous_half_turn_longitude_probe')
        edge=[a.copy()]
        for h in range(1,factor):
            t=h/factor; x=(a[0,0]+t*dx)%1024; v=[]
            for s in (0,1):
                total=float(angle(aa[s],bb[s]))
                if total < POLICY['minimum_resolved_edge_length_deg'] or total > 180-POLICY['antipodal_exclusion_margin_deg']:
                    raise ValueError('degenerate_probe_source_arc')
                if abs(dx)<1e-10:
                    th=math.radians(total)
                    ray=(math.sin((1-t)*th)*aa[s]+math.sin(t*th)*bb[s])/math.sin(th)
                    latitude=math.asin(float(np.clip(ray[1]/np.linalg.norm(ray),-1,1)))
                else:
                    longitude=2*math.pi*(x/1024-.5)
                    horizontal=np.array([math.sin(longitude),0.,-math.cos(longitude)])
                    normal=np.cross(aa[s],bb[s])
                    latitude=math.atan2(-float(normal@horizontal),float(normal[1]))
                    if latitude>math.pi/2:latitude-=math.pi
                    if latitude<-math.pi/2:latitude+=math.pi
                v.append([float(x),float(512*(.5-latitude/math.pi))])
            edge.append(np.asarray(v))
        # Check every proposed boundary path really traverses the original minor arc.
        edge.append(b.copy()); arr=np.asarray(edge)
        for side in (0,1):
            R=rays(arr[:,side]); lengths=angle(R[:-1],R[1:]); total=float(angle(R[0],R[-1]))
            error=abs(float(sum(lengths))-total); maximum=max(maximum,error)
            if error>1e-8:
                raise ValueError('probe_does_not_preserve_ordered_minor_arc')
        for h,p in enumerate(edge[:-1]):
            inserted.append(p.tolist());provenance.append(k if h==0 else None)
            sp.append(record['source_pair_indices'][k] if h==0 else None)
            sip.extend(record['source_point_indices'][2*k:2*k+2] if h==0 else [None,None])
    r=copy.deepcopy(record);r['points']=np.asarray(inserted).reshape(-1,2).tolist()
    r['source_pair_indices']=sp;r['source_point_indices']=sip;r['_probe_original_pair_indices']=provenance
    r['_probe_role']='synthetic_same_record_subdivision_not_an_independent_observation_or_vote'
    assert np.array_equal(np.asarray(r['points']).reshape(-1,2,2)[::factor],q)
    return r,{'factor':factor,'original_pairs':n,'probe_pairs':len(inserted),
              'maximum_arc_additivity_error_deg':maximum,'source_originals_unchanged':True,
              'top_bottom_interpolation_fractions_need_not_equal':True}


def event_signature(bank, row):
    """Compare candidate decisions by original source positions, not densified indices."""
    def identity(ni):
        node=bank.nodes[ni];r=bank.records[node['id']]
        p=r.get('_probe_original_pair_indices',list(range(len(r['points'])//2)))[node['pair_index']]
        if p is None:raise AssertionError('inserted_subdivision_became_search_event')
        return [node['id'],p]
    def leg(l):
        return {'orientation':l['orientation'],'side_of_focal':l['side_of_focal'],
                'ends':[identity(k) for k in l['end_nodes']], 'status':l['status'],
                'boundary_status':{s:v['status'] for s,v in l.get('sides',{}).items()}}
    ls=[leg(l) for l in row['legs']]
    witnesses=[{'orientation':w['orientation'],'legs':[ls[k] for k in w['leg_indices']]} for w in row['witnesses']]
    domains=[]
    for d in row.get('domains',[]):
        ends=[identity(bank.get(d['node'],d['direction'],e)['end_node']) for e in d['endpoint_edge_counts']]
        domains.append({'focal':identity(d['node']),'direction':d['direction'],'status':d['status'],'ends':ends})
    return {'status':row['status'],'domains':domains,'legs':ls,'witnesses':witnesses}


def summary(bank,row):
    accept=[l for l in row['legs'] if l['status']=='accept']
    used={pid for l in accept for pid in l['paths']}
    maximum=max((max(bank.paths[p]['spherical_lengths_deg'][s] for s in sides_for(row['metric'])) for p in used),default=None)
    return {'status':row['status'],'witness_count':len(row['witnesses']), 'attempted_legs':len(row['legs']),
            'leg_status_counts':dict(Counter(l['status'] for l in row['legs'])),
            'maximum_accepted_leg_length_deg':maximum,
            'maximum_accepted_source_edge_hops':max((bank.paths[p]['edge_count'] for p in used),default=None)}
